#!/usr/bin/env python3
"""
predict_prompt_and_generate.py

Given LMA CSV + beats CSV:
1) compute motion feature vector (same schema as X_motion.csv)
2) load trained motion2audio model
3) predict audio descriptors
4) optionally retrieve nearest real descriptor profiles and blend them
5) build a text prompt
6) optionally call MusicGen multiple times and (optionally) rerank candidates
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# Match dataset-builder behavior: exclude non-numeric / indexing columns
LMA_EXCLUDE_COLS = {"window_index", "start_s", "end_s", "time_s"}

STAT_ALIAS_MAP: dict[str, list[str]] = {
    "audio_tempo_bpm": ["audio_tempo_bpm", "bpm_audio"],
    "rms_mean": ["rms_mean"],
    "rms_std": ["rms_std"],
    "zcr_mean": ["zcr_mean"],
    "zcr_std": ["zcr_std"],
    "centroid_mean": ["centroid_mean", "spec_centroid_mean"],
    "centroid_std": ["centroid_std", "spec_centroid_std"],
    "rolloff85_mean": ["rolloff85_mean", "spec_rolloff_mean"],
    "rolloff85_std": ["rolloff85_std", "spec_rolloff_std"],
    "flatness_mean": ["flatness_mean"],
    "flatness_std": ["flatness_std"],
}

DEFAULT_RETRIEVAL_QUERY_COLS = [
    "audio_tempo_bpm",
    "audio_beat_count",
    "rms_mean",
    "rms_std",
    "zcr_mean",
    "zcr_std",
]

FUSED_BUNDLE_TYPE = "fused_descriptor_bundle_v1"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_csv_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _pick_numeric_col(df: pd.DataFrame, names: list[str]) -> str | None:
    for name in names:
        if name in df.columns and pd.api.types.is_numeric_dtype(df[name]):
            return name
    return None


def _pred_value(pred: dict[str, float], canonical: str, default: float = 0.0) -> float:
    for name in STAT_ALIAS_MAP.get(canonical, [canonical]):
        v = pred.get(name, np.nan)
        if np.isfinite(v):
            return float(v)
    return float(default)


def get_bundle_x_cols(bundle: dict) -> list[str]:
    if "x_cols" in bundle:
        return list(bundle["x_cols"])
    if "X_cols" in bundle:
        return list(bundle["X_cols"])
    raise KeyError("Could not resolve X columns from model bundle.")


def get_bundle_y_cols(bundle: dict) -> list[str]:
    if "y_cols" in bundle:
        return list(bundle["y_cols"])
    if "Y_cols" in bundle:
        return list(bundle["Y_cols"])
    raise KeyError("Could not resolve Y columns from model bundle.")


def predict_descriptors_from_bundle(bundle: dict, x: np.ndarray) -> tuple[dict[str, float], dict]:
    btype = str(bundle.get("bundle_type", ""))
    if btype == FUSED_BUNDLE_TYPE:
        y_cols = get_bundle_y_cols(bundle)
        m2d = bundle["motion2desc"]
        m2c = bundle["motion2clap"]
        c2d = bundle["clap2desc"]
        pred_motion = m2d.predict(x)[0].astype(np.float32)
        pred_clap = m2c.predict(x).astype(np.float32)
        pred_from_clap = c2d.predict(pred_clap)[0].astype(np.float32)

        alpha_default = float(bundle.get("fusion_alpha_default", 0.65))
        per_col_alpha = bundle.get("fusion_per_col_alpha", {})
        fused = np.zeros_like(pred_motion, dtype=np.float32)
        for j, c in enumerate(y_cols):
            a = float(per_col_alpha.get(c, alpha_default))
            fused[j] = (a * pred_motion[j]) + ((1.0 - a) * pred_from_clap[j])

        pred = {c: float(v) for c, v in zip(y_cols, fused)}
        aux = {
            "bundle_type": btype,
            "pred_motion2desc": {c: float(v) for c, v in zip(y_cols, pred_motion)},
            "pred_clap2desc": {c: float(v) for c, v in zip(y_cols, pred_from_clap)},
            "fusion_alpha_default": alpha_default,
            "fusion_per_col_alpha": per_col_alpha,
        }
        return pred, aux

    model = bundle["model"]
    y_cols = get_bundle_y_cols(bundle)
    pred_vec = model.predict(x)[0]
    pred = {c: float(v) for c, v in zip(y_cols, pred_vec)}
    aux = {"bundle_type": "single_model"}
    return pred, aux


def compute_motion_features(lma_df: pd.DataFrame, beats_df: pd.DataFrame) -> dict[str, float]:
    feats: dict[str, float] = {}

    num_cols = [c for c in lma_df.columns if c not in LMA_EXCLUDE_COLS]
    num_cols = [c for c in num_cols if pd.api.types.is_numeric_dtype(lma_df[c])]
    if not num_cols:
        raise ValueError("No numeric LMA columns found to aggregate.")

    for c in num_cols:
        x = lma_df[c].astype(float).to_numpy()
        feats[f"lma_mean_{c}"] = float(np.nanmean(x))
        feats[f"lma_std_{c}"] = float(np.nanstd(x))

    if "BODY" in lma_df.columns and pd.api.types.is_numeric_dtype(lma_df["BODY"]):
        feats["lma_body_p90"] = float(np.nanpercentile(lma_df["BODY"].astype(float), 90))

    if beats_df is None or len(beats_df) == 0:
        feats.update(
            {
                "beat_count": 0.0,
                "beat_rate_hz": 0.0,
                "bpm_motion": 0.0,
                "ibi_mean_s": 0.0,
                "ibi_std_s": 0.0,
            }
        )
        return feats

    if "time_s" not in beats_df.columns:
        num_candidates = [
            c for c in beats_df.columns if pd.api.types.is_numeric_dtype(beats_df[c])
        ]
        if not num_candidates:
            raise ValueError("No numeric beat time column found.")
        t = beats_df[num_candidates[0]].astype(float).to_numpy()
    else:
        t = beats_df["time_s"].astype(float).to_numpy()

    t = np.unique(t)
    t.sort()
    feats["beat_count"] = float(len(t))

    if len(t) >= 2:
        duration = float(max(t[-1] - t[0], 1e-9))
        ibi = np.diff(t)
        feats["beat_rate_hz"] = float(len(t) / duration)
        feats["ibi_mean_s"] = float(np.mean(ibi))
        feats["ibi_std_s"] = float(np.std(ibi))
        feats["bpm_motion"] = float(60.0 / max(np.mean(ibi), 1e-9))
    else:
        feats["beat_rate_hz"] = 0.0
        feats["ibi_mean_s"] = 0.0
        feats["ibi_std_s"] = 0.0
        feats["bpm_motion"] = 0.0

    return feats


def _describe_from_stats(
    val: float,
    p33: float,
    p66: float,
    low_word: str,
    mid_word: str,
    high_word: str,
) -> str:
    if val < p33:
        return low_word
    if val < p66:
        return mid_word
    return high_word


def build_prompt(
    style: str,
    bpm_motion: float,
    pred: dict[str, float],
    y_stats: dict[str, tuple[float, float]],
) -> str:
    bpm_pred = _pred_value(pred, "audio_tempo_bpm", default=120.0)
    bpm_use = float(bpm_motion) if float(bpm_motion) > 0 else float(bpm_pred)
    bpm_round = int(round(bpm_use))

    rms = _pred_value(pred, "rms_mean", default=0.0)
    cen = _pred_value(pred, "centroid_mean", default=0.0)
    rol = _pred_value(pred, "rolloff85_mean", default=0.0)
    zcr = _pred_value(pred, "zcr_mean", default=0.0)
    flt = _pred_value(pred, "flatness_mean", default=0.0)

    def p(name: str, ref_val: float) -> tuple[float, float]:
        if name in y_stats:
            return y_stats[name]
        return (ref_val - 1e-6, ref_val + 1e-6)

    energy_word = _describe_from_stats(rms, *p("rms_mean", rms), "calm", "driving", "energetic")
    bright_word = _describe_from_stats(cen, *p("centroid_mean", cen), "warm", "balanced", "bright")
    drum_word = _describe_from_stats(
        rol,
        *p("rolloff85_mean", rol),
        "soft percussion",
        "clear drums",
        "hard-hitting drums",
    )
    texture_word = _describe_from_stats(zcr, *p("zcr_mean", zcr), "smooth texture", "clean texture", "crisp texture")
    tone_word = _describe_from_stats(flt, *p("flatness_mean", flt), "tonal", "hybrid tonal/noisy", "grainy/noisy")

    return (
        f"{style}, {energy_word}, {bright_word}, {drum_word}, {texture_word}, "
        f"{tone_word}, clear beat, tempo {bpm_round} bpm, tight timing, high quality mix, no vocals"
    )


def load_y_percentiles(dataset_dir: Path) -> dict[str, tuple[float, float]]:
    yp = dataset_dir / "Y_audio.csv"
    if not yp.exists():
        return {}

    df = pd.read_csv(yp)
    stats: dict[str, tuple[float, float]] = {}
    for canonical in ("rms_mean", "centroid_mean", "rolloff85_mean", "zcr_mean", "flatness_mean"):
        col = _pick_numeric_col(df, STAT_ALIAS_MAP.get(canonical, [canonical]))
        if col is None:
            continue
        v = df[col].dropna().to_numpy(dtype=float)
        if v.size >= 10:
            stats[canonical] = (float(np.percentile(v, 33)), float(np.percentile(v, 66)))
    return stats


def load_retrieval_bank(dataset_dir: Path) -> dict | None:
    yp = dataset_dir / "Y_audio.csv"
    if not yp.exists():
        return None

    ydf = pd.read_csv(yp)
    num = ydf.select_dtypes(include=[np.number]).copy()
    drop_cols = []
    for c in num.columns:
        if c == "clip_id" or c == "audio_duration_s" or c.endswith("_min") or c.endswith("_max"):
            drop_cols.append(c)
    if drop_cols:
        num = num.drop(columns=drop_cols, errors="ignore")
    num = num.dropna(axis=1, how="all")
    if num.empty:
        return None

    med = num.median(numeric_only=True)
    num = num.fillna(med)
    cols = num.columns.to_list()
    arr = num.to_numpy(dtype=np.float32)
    mu = np.mean(arr, axis=0).astype(np.float32)
    sd = (np.std(arr, axis=0) + 1e-8).astype(np.float32)

    clip_to_meta: dict[str, dict] = {}
    mp = dataset_dir / "meta.csv"
    if mp.exists():
        meta = pd.read_csv(mp)
        if "clip_id" in meta.columns:
            for row in meta.itertuples(index=False):
                cid = str(getattr(row, "clip_id"))
                clip_to_meta[cid] = {
                    "db": str(getattr(row, "db", "")),
                    "stem": str(getattr(row, "stem", "")),
                }

    row_meta: list[dict] = []
    for row in ydf.itertuples(index=False):
        cid = str(getattr(row, "clip_id", ""))
        audio_path = str(getattr(row, "audio_path", ""))
        extra = clip_to_meta.get(cid, {})
        row_meta.append(
            {
                "clip_id": cid,
                "audio_path": audio_path,
                "db": extra.get("db", ""),
                "stem": extra.get("stem", ""),
            }
        )

    return {"cols": cols, "arr": arr, "mu": mu, "sd": sd, "meta": row_meta}


def retrieve_and_blend_descriptors(
    pred: dict[str, float],
    retrieval_bank: dict | None,
    bpm_motion: float,
    query_cols: list[str],
    k: int,
    alpha: float,
) -> tuple[dict[str, float], dict | None]:
    if retrieval_bank is None or k <= 0:
        return pred.copy(), None

    cols: list[str] = retrieval_bank["cols"]
    arr: np.ndarray = retrieval_bank["arr"]
    sd: np.ndarray = retrieval_bank["sd"]
    meta: list[dict] = retrieval_bank["meta"]

    query: dict[str, float] = {}
    for key in query_cols:
        if key == "audio_tempo_bpm" and np.isfinite(bpm_motion) and float(bpm_motion) > 0:
            query[key] = float(bpm_motion)
            continue
        v = pred.get(key, np.nan)
        if np.isfinite(v):
            query[key] = float(v)

    used_keys = [k0 for k0 in query.keys() if k0 in cols]
    if not used_keys:
        return pred.copy(), None

    idx = np.array([cols.index(k0) for k0 in used_keys], dtype=int)
    qv = np.array([query[k0] for k0 in used_keys], dtype=np.float32)

    z = (arr[:, idx] - qv[None, :]) / sd[idx][None, :]
    dist = np.mean(np.abs(z), axis=1)

    top_k = int(max(1, min(int(k), len(dist))))
    top_idx = np.argpartition(dist, top_k - 1)[:top_k]
    top_idx = top_idx[np.argsort(dist[top_idx])]

    w = 1.0 / (dist[top_idx] + 1e-6)
    w = w / np.sum(w)
    proto = np.sum(arr[top_idx] * w[:, None], axis=0)

    alpha = float(np.clip(alpha, 0.0, 1.0))
    blended: dict[str, float] = {}
    for j, c in enumerate(cols):
        rv = float(proto[j])
        pv = pred.get(c, np.nan)
        if np.isfinite(pv):
            blended[c] = float(alpha * float(pv) + (1.0 - alpha) * rv)
        else:
            blended[c] = rv
    for c, v in pred.items():
        if c not in blended and np.isfinite(v):
            blended[c] = float(v)

    nearest = []
    for i in top_idx[: min(3, len(top_idx))]:
        m = meta[int(i)] if int(i) < len(meta) else {}
        nearest.append(
            {
                "idx": int(i),
                "dist": float(dist[int(i)]),
                "clip_id": m.get("clip_id", ""),
                "db": m.get("db", ""),
                "stem": m.get("stem", ""),
                "audio_path": m.get("audio_path", ""),
            }
        )

    info = {
        "used_query_keys": used_keys,
        "k": int(top_k),
        "alpha": float(alpha),
        "nearest": nearest,
    }
    return blended, info


def maybe_rerank_candidates(dataset_dir: Path, wav_paths: list[Path], pred: dict[str, float]) -> Path:
    try:
        import librosa
    except Exception:
        return wav_paths[0]

    keys = ["rms_mean", "centroid_mean", "rolloff85_mean", "zcr_mean", "flatness_mean"]

    yp = dataset_dir / "Y_audio.csv"
    mu: dict[str, float] = {}
    sd: dict[str, float] = {}
    if yp.exists():
        ydf = pd.read_csv(yp)
        for k in keys:
            c = _pick_numeric_col(ydf, STAT_ALIAS_MAP.get(k, [k]))
            if c is None:
                continue
            arr = ydf[c].dropna().to_numpy(dtype=float)
            if arr.size:
                mu[k] = float(arr.mean())
                sd[k] = float(arr.std() + 1e-9)

    target = {}
    for k in keys:
        v = _pred_value(pred, k, default=np.nan)
        if np.isfinite(v):
            target[k] = float(v)
    if not target:
        return wav_paths[0]

    def feats_for_wav(p: Path) -> dict[str, float]:
        y, sr = librosa.load(str(p), sr=22050, mono=True)
        hop = 512
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=hop)[0]
        rms = librosa.feature.rms(y=y, hop_length=hop)[0]
        zcr = librosa.feature.zero_crossing_rate(y, hop_length=hop)[0]
        flatness = librosa.feature.spectral_flatness(y=y, hop_length=hop)[0]
        return {
            "rms_mean": float(np.mean(rms)),
            "centroid_mean": float(np.mean(centroid)),
            "rolloff85_mean": float(np.mean(rolloff)),
            "zcr_mean": float(np.mean(zcr)),
            "flatness_mean": float(np.mean(flatness)),
        }

    best_p = wav_paths[0]
    best_d = float("inf")
    for p in wav_paths:
        f = feats_for_wav(p)
        d = 0.0
        for k in keys:
            if k not in target:
                continue
            if k in mu:
                d += abs((f[k] - target[k]) / sd[k])
            else:
                d += abs(f[k] - target[k])
        if d < best_d:
            best_d = d
            best_p = p

    return best_p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--model-path", required=True)
    ap.add_argument("--lma-csv", required=True)
    ap.add_argument("--beats-csv", required=True)
    ap.add_argument("--style", default="instrumental dance")
    ap.add_argument("--duration", type=float, default=12.0)
    ap.add_argument("--num", type=int, default=1, help="How many candidates to generate")
    ap.add_argument("--out-dir", default="outputs/generated")
    ap.add_argument("--musicgen-model", default="facebook/musicgen-small")
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--rerank", action="store_true", help="Rerank generated candidates vs predicted descriptors (needs librosa)")
    ap.add_argument("--retrieval-k", type=int, default=5, help="Top-K nearest descriptor rows used for timbre retrieval. Set 0 to disable.")
    ap.add_argument("--retrieval-alpha", type=float, default=0.65, help="Blend weight for model prediction vs retrieved profile.")
    ap.add_argument(
        "--retrieval-query-cols",
        type=str,
        default=",".join(DEFAULT_RETRIEVAL_QUERY_COLS),
        help="Comma-separated descriptor keys used as retrieval query.",
    )
    ap.add_argument("--save-run-json", action="store_true", help="Save run metadata json in out-dir.")
    args = ap.parse_args()

    root = project_root()
    dataset_dir = (root / args.dataset_dir).resolve() if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    model_path = (root / args.model_path).resolve() if not Path(args.model_path).is_absolute() else Path(args.model_path)
    lma_csv = (root / args.lma_csv).resolve() if not Path(args.lma_csv).is_absolute() else Path(args.lma_csv)
    beats_csv = (root / args.beats_csv).resolve() if not Path(args.beats_csv).is_absolute() else Path(args.beats_csv)
    out_dir = (root / args.out_dir).resolve() if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle = joblib.load(model_path)
    x_cols: list[str] = get_bundle_x_cols(bundle)
    y_cols: list[str] = get_bundle_y_cols(bundle)

    lma_df = pd.read_csv(lma_csv)
    beats_df = pd.read_csv(beats_csv)
    xdict = compute_motion_features(lma_df, beats_df)
    bpm_motion = float(xdict.get("bpm_motion", 0.0))

    x = np.zeros((1, len(x_cols)), dtype=np.float32)
    missing = []
    for i, c in enumerate(x_cols):
        if c in xdict:
            x[0, i] = float(xdict[c])
        else:
            missing.append(c)

    pred_raw, pred_aux = predict_descriptors_from_bundle(bundle, x)

    retrieval_query_cols = _parse_csv_list(args.retrieval_query_cols)
    if not retrieval_query_cols:
        retrieval_query_cols = list(DEFAULT_RETRIEVAL_QUERY_COLS)
    retrieval_bank = load_retrieval_bank(dataset_dir) if int(args.retrieval_k) > 0 else None
    pred_prompt, retrieval_info = retrieve_and_blend_descriptors(
        pred=pred_raw,
        retrieval_bank=retrieval_bank,
        bpm_motion=bpm_motion,
        query_cols=retrieval_query_cols,
        k=int(args.retrieval_k),
        alpha=float(args.retrieval_alpha),
    )

    y_stats = load_y_percentiles(dataset_dir)
    prompt = build_prompt(args.style, bpm_motion, pred_prompt, y_stats)

    print("\n[prompt]")
    print(prompt)
    if retrieval_info is not None:
        print("\n[retrieval]")
        for hit in retrieval_info.get("nearest", []):
            print(f"  db={hit.get('db','')} stem={hit.get('stem','')} dist={hit.get('dist',0.0):.4f}")

    gen_script = root / "scripts" / "generate_music.py"
    wavs: list[Path] = []
    for k in range(args.num):
        seed = int(args.seed + k * 101)
        out_wav = out_dir / f"musicgen_{lma_csv.stem}_s{seed}.wav"

        cmd = [
            sys.executable,
            str(gen_script),
            "--prompt",
            prompt,
            "--model",
            args.musicgen_model,
            "--duration",
            str(args.duration),
            "--out",
            str(out_wav),
            "--seed",
            str(seed),
        ]
        if args.cpu:
            cmd.append("--cpu")

        print("\n[cmd]", " ".join(cmd))
        subprocess.run(cmd, check=True)
        wavs.append(out_wav)

    if args.rerank and len(wavs) > 1:
        best = maybe_rerank_candidates(dataset_dir, wavs, pred_prompt)
        print(f"\n[best] {best}")
    else:
        print(f"\n[done] generated {len(wavs)} wav(s) -> {out_dir}")

    if args.save_run_json:
        run_info = {
            "dataset_dir": str(dataset_dir),
            "model_path": str(model_path),
            "lma_csv": str(lma_csv),
            "beats_csv": str(beats_csv),
            "x_cols_count": int(len(x_cols)),
            "y_cols_count": int(len(y_cols)),
            "missing_x_cols": missing,
            "bpm_motion": float(bpm_motion),
            "prompt": prompt,
            "retrieval": retrieval_info,
            "pred_raw": pred_raw,
            "prediction_aux": pred_aux,
            "pred_for_prompt": pred_prompt,
            "generated_wavs": [str(p) for p in wavs],
        }
        info_path = out_dir / f"{lma_csv.stem}_prompt_run.json"
        info_path.write_text(json.dumps(run_info, indent=2), encoding="utf-8")
        print(f"[meta] {info_path}")


if __name__ == "__main__":
    main()
