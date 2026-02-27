import os
import json
import argparse
import numpy as np
import pandas as pd
import joblib


# ----------------- helpers -----------------

def l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / (n + eps)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # a: (D,), b: (N,D)
    a = l2_normalize(a.reshape(1, -1))[0]
    b = l2_normalize(b)
    return b @ a


def find_time_column(df: pd.DataFrame) -> str:
    df.columns = [c.strip() for c in df.columns]
    candidates = ["time_s", "time", "t", "timestamp", "seconds", "sec", "beat_time", "start_time_s"]
    col_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in col_map:
            return col_map[cand]
    if df.shape[1] == 1:
        return df.columns[0]
    raise KeyError(f"Beats CSV has no time column. Columns={list(df.columns)}")


# ----------------- feature summaries -----------------

def summarize_lma(df: pd.DataFrame) -> dict:
    """
    Generic numeric summary. Works with your LMA CSVs without needing exact column names.
    """
    num = df.select_dtypes(include=["number"]).copy()
    out = {}
    for c in num.columns:
        v = num[c].astype(float).values
        v = v[np.isfinite(v)]
        if len(v) == 0:
            out[f"{c}_mean"] = np.nan
            out[f"{c}_std"] = np.nan
        else:
            out[f"{c}_mean"] = float(np.mean(v))
            out[f"{c}_std"]  = float(np.std(v))
    return out


def summarize_beats(df: pd.DataFrame) -> dict:
    time_col = find_time_column(df)
    t = df[time_col].astype(float).values
    t = np.sort(t[np.isfinite(t)])

    out = {"beat_count": int(len(t))}
    if len(t) < 2:
        out.update({"bpm": np.nan, "ioi_cv": np.nan, "density": np.nan, "bpm_std": np.nan})
        return out

    ioi = np.diff(t)
    ioi = ioi[(ioi > 1e-4) & (ioi < 10.0)]
    if len(ioi) < 2:
        bpm = 60.0 / np.median(ioi) if len(ioi) == 1 else np.nan
        out.update({"bpm": float(bpm) if np.isfinite(bpm) else np.nan,
                    "ioi_cv": np.nan, "density": np.nan, "bpm_std": np.nan})
        return out

    bpm_inst = 60.0 / ioi
    bpm = float(np.median(bpm_inst))
    bpm_std = float(np.std(bpm_inst))
    ioi_cv = float(np.std(ioi) / (np.mean(ioi) + 1e-9))

    duration = float(t[-1] - t[0])
    density = float(len(t) / (duration + 1e-9)) if duration > 0 else np.nan

    out.update({"bpm": bpm, "ioi_cv": ioi_cv, "density": density, "bpm_std": bpm_std})
    return out


def row_to_vector(row: dict, feature_names: list) -> np.ndarray:
    x = np.array([row.get(f, np.nan) for f in feature_names], dtype=np.float32)
    return x


# ----------------- motion modifiers (richness) -----------------

def pick_lma_signal(feats: dict, include_keywords):
    """
    Heuristic: find LMA mean features whose original column name contains any keyword.
    Works across different naming schemes because we match substrings.
    """
    keys = [k for k in feats.keys() if k.endswith("_mean")]
    scored = []
    for k in keys:
        base = k[:-5].lower()  # remove _mean
        if any(kw in base for kw in include_keywords):
            v = feats.get(k, np.nan)
            if np.isfinite(v):
                scored.append((k, float(v)))
    # pick the strongest magnitude signal if multiple
    scored.sort(key=lambda x: abs(x[1]), reverse=True)
    return scored[0] if scored else (None, np.nan)


def bucket(v, lo, hi):
    if not np.isfinite(v):
        return None
    if v < lo:
        return "low"
    if v > hi:
        return "high"
    return "medium"


def build_motion_modifiers(lma_feats: dict, beat_feats: dict):
    mods = []
    debug = {}

    # Tempo
    bpm = beat_feats.get("bpm", np.nan)
    if np.isfinite(bpm):
        mods.append(f"tempo {int(round(bpm))} bpm")
        debug["bpm"] = float(bpm)

    # Rhythm feel
    ioi_cv = beat_feats.get("ioi_cv", np.nan)
    density = beat_feats.get("density", np.nan)
    bpm_std = beat_feats.get("bpm_std", np.nan)

    if np.isfinite(bpm_std):
        if bpm_std < 3:
            mods.append("steady tempo")
        elif bpm_std > 8:
            mods.append("tempo variations")
        debug["bpm_std"] = float(bpm_std)

    if np.isfinite(ioi_cv):
        if ioi_cv > 0.35:
            mods.append("syncopated, rhythmically varied")
        elif ioi_cv < 0.15:
            mods.append("straight, consistent rhythm")
        debug["ioi_cv"] = float(ioi_cv)

    if np.isfinite(density):
        if density > 3.0:
            mods.append("busy percussion, frequent hits")
        elif density < 1.2:
            mods.append("sparser rhythm, fewer hits")
        debug["density"] = float(density)

    # LMA-based feel (heuristics)
    # Try to detect classic LMA-ish columns by substring match
    weight_k, weight_v = pick_lma_signal(lma_feats, ["weight", "strong", "heavy"])
    time_k, time_v = pick_lma_signal(lma_feats, ["time", "sudden", "quick", "sharp"])
    flow_k, flow_v = pick_lma_signal(lma_feats, ["flow", "bound", "free", "control"])
    space_k, space_v = pick_lma_signal(lma_feats, ["space", "direct", "indirect", "wide"])

    # Bucket thresholds are heuristic; later you can calibrate per-dataset with percentiles.
    w_b = bucket(weight_v, lo=-0.2, hi=0.2)
    t_b = bucket(time_v, lo=-0.2, hi=0.2)
    f_b = bucket(flow_v, lo=-0.2, hi=0.2)
    s_b = bucket(space_v, lo=-0.2, hi=0.2)

    # Add modifiers
    if w_b == "high":
        mods.append("heavy-hitting energy")
    elif w_b == "low":
        mods.append("lightweight feel")

    if t_b == "high":
        mods.append("punchy, staccato hits")
    elif t_b == "low":
        mods.append("smoother, more legato motion")

    if f_b == "high":
        mods.append("tight, controlled groove")
    elif f_b == "low":
        mods.append("looser, flowing groove")

    if s_b == "high":
        mods.append("wide, spacious feel")
    elif s_b == "low":
        mods.append("compact, focused feel")

    # Debug which columns were used
    debug["lma_used"] = {
        "weight": (weight_k, weight_v),
        "time": (time_k, time_v),
        "flow": (flow_k, flow_v),
        "space": (space_k, space_v),
    }

    return mods, debug


def dedupe_keep_order(items):
    seen = set()
    out = []
    for it in items:
        k = it.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


# ----------------- main -----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--lma", required=True)
    ap.add_argument("--beats", required=True)
    ap.add_argument("--prompts-json", default="audio_prompts.json")
    ap.add_argument("--topk", type=int, default=5)
    args = ap.parse_args()

    pack = joblib.load(args.model)
    reg = pack["model"]
    feature_names = pack["feature_names"]

    emb_npz = pack["embeddings_npz"]
    data = np.load(emb_npz, allow_pickle=True)
    ids = [str(x) for x in data["ids"]]
    E = data["emb"].astype(np.float32)

    prompts = {}
    if os.path.exists(args.prompts_json):
        with open(args.prompts_json, "r", encoding="utf-8") as f:
            prompts = json.load(f)

    df_lma = pd.read_csv(args.lma)
    df_beats = pd.read_csv(args.beats)

    lma_feats = summarize_lma(df_lma)
    beat_feats = summarize_beats(df_beats)

    feats = {}
    feats.update(lma_feats)
    feats.update(beat_feats)

    x = row_to_vector(feats, feature_names)
    x = np.nan_to_num(x, nan=0.0)

    yhat = reg.predict(x.reshape(1, -1))[0].astype(np.float32)
    yhat = l2_normalize(yhat)

    sims = cosine_sim(yhat, E)
    order = np.argsort(-sims)

    best_i = int(order[0])
    best_id = ids[best_i]
    best_sim = float(sims[best_i])

    base_prompt = prompts.get(best_id, "")
    if not base_prompt:
        base_prompt = "instrumental dance track, clean modern mix, no vocals"

    motion_mods, dbg = build_motion_modifiers(lma_feats, beat_feats)
    motion_mods = dedupe_keep_order(motion_mods)

    # Final prompt: base + motion modifiers + constraints (ensure no vocals at end)
    final_parts = [base_prompt] + motion_mods
    final_parts = dedupe_keep_order([p.strip().strip(",") for p in final_parts if p.strip()])
    final_prompt = ", ".join(final_parts)

    if "no vocals" not in final_prompt.lower():
        final_prompt = final_prompt + ", no vocals"

    # -------- print report --------
    print(f"[nearest] {best_id}  sim={best_sim:.3f}")
    print("\n[base_prompt]")
    print(base_prompt)

    print("\n[motion_modifiers]")
    for m in motion_mods:
        print(f"- {m}")

    print("\n[final_prompt]")
    print(final_prompt)

    if args.topk > 1:
        print(f"\n[top{args.topk} candidates]")
        for rank in range(min(args.topk, len(ids))):
            i = int(order[rank])
            print(f"{rank+1:>2}. {ids[i]}  sim={float(sims[i]):.3f}")

    # optional debug (uncomment if you want)
    # print("\n[debug]")
    # print(dbg)


if __name__ == "__main__":
    main()
