import os
import re
import json
import argparse
import numpy as np
import pandas as pd
from tqdm import tqdm

from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import joblib


# --------- Matching ---------

AIST_RE = re.compile(
    r"^(g[^_]+)_(s[^_]+)_(c[^_]+)_(d[^_]+)_(m[^_]+)_(ch[^_]+)"
)

def parse_key(stem: str):
    """
    Extract a robust matching key from AIST-like stems.
    We ignore c and ch because they differ between LMA and audio names in your example.
    Key = (g, s, d, m)
    """
    m = AIST_RE.match(stem)
    if not m:
        return None
    g, s, c, d, music, ch = m.groups()
    return (g, s, d, music)

def build_audio_index(audio_dir: str):
    """
    Build index: key(g,s,d,m) -> list of audio file paths
    """
    idx = {}
    for fn in os.listdir(audio_dir):
        if not fn.lower().endswith(".mp3"):
            continue
        stem = os.path.splitext(fn)[0]
        key = parse_key(stem)
        if key is None:
            continue
        idx.setdefault(key, []).append(os.path.join(audio_dir, fn))
    return idx


# --------- Feature extraction ---------

def summarize_lma(df: pd.DataFrame) -> dict:
    # Expect columns like BODY, EFFORT_..., SHAPE, SPACE (from your files)
    # Keep only numeric columns
    num = df.select_dtypes(include=["number"]).copy()
    out = {}
    for c in num.columns:
        v = num[c].astype(float).values
        v = v[np.isfinite(v)]
        if len(v) == 0:
            out[f"{c}_mean"] = np.nan
            out[f"{c}_std"] = np.nan
            out[f"{c}_p10"] = np.nan
            out[f"{c}_p90"] = np.nan
        else:
            out[f"{c}_mean"] = float(np.mean(v))
            out[f"{c}_std"]  = float(np.std(v))
            out[f"{c}_p10"]  = float(np.percentile(v, 10))
            out[f"{c}_p90"]  = float(np.percentile(v, 90))
    return out


def summarize_beats(df: pd.DataFrame) -> dict:
    # Robust time column detection
    df.columns = [c.strip() for c in df.columns]
    candidates = ["time_s", "time", "t", "timestamp", "seconds", "sec", "beat_time", "start_time_s"]
    col_map = {c.lower(): c for c in df.columns}

    time_col = None
    for cand in candidates:
        if cand in col_map:
            time_col = col_map[cand]
            break

    if time_col is None:
        if df.shape[1] == 1:
            time_col = df.columns[0]
        else:
            raise KeyError(f"Beats CSV has no time column. Columns={list(df.columns)}")

    t = df[time_col].astype(float).values
    t = np.sort(t[np.isfinite(t)])

    out = {"beat_count": int(len(t))}
    if len(t) < 2:
        out.update({"bpm": np.nan, "ioi_mean": np.nan, "ioi_std": np.nan, "ioi_cv": np.nan, "density": np.nan})
        return out

    ioi = np.diff(t)
    ioi = ioi[(ioi > 1e-4) & (ioi < 10.0)]

    if len(ioi) == 0:
        out.update({"bpm": np.nan, "ioi_mean": np.nan, "ioi_std": np.nan, "ioi_cv": np.nan, "density": np.nan})
        return out

    bpm = 60.0 / np.median(ioi)
    ioi_mean = float(np.mean(ioi))
    ioi_std = float(np.std(ioi))
    ioi_cv = float(ioi_std / (ioi_mean + 1e-9))

    duration = float(t[-1] - t[0]) if len(t) >= 2 else np.nan
    density = float(len(t) / (duration + 1e-9)) if np.isfinite(duration) and duration > 0 else np.nan

    out.update({"bpm": float(bpm), "ioi_mean": ioi_mean, "ioi_std": ioi_std, "ioi_cv": ioi_cv, "density": density})
    return out


def row_to_vector(row: dict, feature_names: list) -> np.ndarray:
    return np.array([row.get(f, np.nan) for f in feature_names], dtype=np.float32)


# --------- Training ---------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features-dir", required=True)
    ap.add_argument("--audio-dir", required=True)
    ap.add_argument("--embeddings-npz", required=False, help="Audio embeddings npz (from audio_embed_clap.py)")
    ap.add_argument("--used-audio-json", default="used_audio.json")
    ap.add_argument("--out-model", default="motion2audio.joblib")
    ap.add_argument("--limit", type=int, default=0, help="Optional limit for quick tests")
    args = ap.parse_args()

    audio_index = build_audio_index(args.audio_dir)
    print(f"[audio] indexed keys={len(audio_index)}")

    lma_files = [f for f in os.listdir(args.features_dir) if f.endswith("_lma.csv")]
    lma_files.sort()

    samples = []
    used_audio = set()

    for fn in tqdm(lma_files, desc="Pairing CSV->audio"):
        stem = fn[:-8]  # remove _lma.csv
        beats_fn = stem + "_beats.csv"
        lma_path = os.path.join(args.features_dir, fn)
        beats_path = os.path.join(args.features_dir, beats_fn)

        if not os.path.exists(beats_path):
            continue

        key = parse_key(stem)
        if key is None:
            continue

        # match audio by key (g,s,d,m), ignoring c/ch differences
        candidates = audio_index.get(key, [])
        if not candidates:
            continue

        audio_path = candidates[0]  # if multiple, pick first (you can improve later)
        used_audio.add(audio_path)

        samples.append((lma_path, beats_path, audio_path))

        if args.limit and len(samples) >= args.limit:
            break

    print(f"[pairing] samples={len(samples)}  unique_audio={len(used_audio)}")

    # Save used audio list for embedding step
    used_audio_list = sorted(list(used_audio))
    with open(args.used_audio_json, "w", encoding="utf-8") as f:
        json.dump(used_audio_list, f, indent=2)
    print(f"[ok] wrote {args.used_audio_json} (audio files needed for embeddings)")

    if not args.embeddings_npz:
        print("\nNext, compute embeddings:\n"
              f"  python audio_embed_clap.py --audio-dir \"{args.audio_dir}\" "
              f"--used-audio-list \"{args.used_audio_json}\" --out-npz audio_emb.npz\n")
        return

    # Load embeddings
    data = np.load(args.embeddings_npz, allow_pickle=True)
    emb_ids = data["ids"]
    emb_mat = data["emb"].astype(np.float32)

    id_to_emb = {str(i): emb_mat[k] for k, i in enumerate(emb_ids)}

    # Build dataset X,Y
    rows = []
    Ys = []
    for lma_path, beats_path, audio_path in tqdm(samples, desc="Building X,Y"):
        df_lma = pd.read_csv(lma_path)
        df_beats = pd.read_csv(beats_path)

        feats = {}
        feats.update(summarize_lma(df_lma))
        feats.update(summarize_beats(df_beats))

        audio_id = os.path.splitext(os.path.basename(audio_path))[0]
        if audio_id not in id_to_emb:
            continue

        rows.append(feats)
        Ys.append(id_to_emb[audio_id])

    if not rows:
        raise RuntimeError("No training rows built. Check embeddings match audio ids.")

    # Feature names = union of all keys (stable ordering)
    feature_names = sorted({k for r in rows for k in r.keys()})
    X = np.stack([row_to_vector(r, feature_names) for r in rows], axis=0)
    Y = np.stack(Ys, axis=0)

    # NaN handling: replace NaNs with column means
    col_means = np.nanmean(X, axis=0)
    inds = np.where(np.isnan(X))
    X[inds] = np.take(col_means, inds[1])

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=10.0))
    ])

    print(f"[train] X={X.shape} Y={Y.shape} features={len(feature_names)}")
    model.fit(X, Y)

    payload = {
        "model": model,
        "feature_names": feature_names,
        "audio_dir": args.audio_dir,
        "features_dir": args.features_dir,
        "embeddings_npz": args.embeddings_npz,
        "used_audio_json": args.used_audio_json,
    }

    joblib.dump(payload, args.out_model)
    print(f"[ok] saved model -> {args.out_model}")


if __name__ == "__main__":
    main()
