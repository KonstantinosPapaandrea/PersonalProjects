#!/usr/bin/env python3
"""
predict_prompt_and_generate.py

Given LMA CSV + beats CSV:
1) compute motion feature vector (same schema as X_motion.csv)
2) load trained motion2audio model
3) predict audio descriptors
4) build a richer text prompt
5) optionally call MusicGen multiple times and (optionally) rerank candidates vs predicted targets

Usage (from project root):
  python scripts/predict_prompt_and_generate.py ^
    --dataset-dir outputs/m2m_train ^
    --model-path outputs/m2m_train/models/motion2audio_ridge.joblib ^
    --lma-csv outputs/m2m_train/features/<stem>_lma.csv ^
    --beats-csv outputs/m2m_train/features/<stem>_beats.csv ^
    --style "instrumental dance" ^
    --duration 12 ^
    --num 4 ^
    --out-dir outputs/generated
"""

from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

# Match dataset-builder behavior: exclude non-numeric / indexing columns
LMA_EXCLUDE_COLS = {"window_index", "start_s", "end_s", "time_s"}

def project_root() -> Path:
    return Path(__file__).resolve().parents[1]

def compute_motion_features(lma_df: pd.DataFrame, beats_df: pd.DataFrame) -> dict[str, float]:
    feats: dict[str, float] = {}

    # ---- LMA window stats
    num_cols = [c for c in lma_df.columns if c not in LMA_EXCLUDE_COLS]
    num_cols = [c for c in num_cols if pd.api.types.is_numeric_dtype(lma_df[c])]
    if not num_cols:
        raise ValueError("No numeric LMA columns found to aggregate.")

    for c in num_cols:
        x = lma_df[c].astype(float).to_numpy()
        feats[f"lma_mean_{c}"] = float(np.nanmean(x))
        feats[f"lma_std_{c}"]  = float(np.nanstd(x))

    if "BODY" in lma_df.columns and pd.api.types.is_numeric_dtype(lma_df["BODY"]):
        feats["lma_body_p90"] = float(np.nanpercentile(lma_df["BODY"].astype(float), 90))

    # ---- Beats stats
    if beats_df is None or len(beats_df) == 0:
        feats.update({
            "beat_count": 0.0,
            "beat_rate_hz": 0.0,
            "bpm_motion": 0.0,
            "ibi_mean_s": 0.0,
            "ibi_std_s": 0.0
        })
        return feats

    t = beats_df["time_s"].astype(float).to_numpy()
    t = np.unique(t)
    t.sort()
    feats["beat_count"] = float(len(t))

    if len(t) >= 2:
        duration = float(max(t[-1] - t[0], 1e-9))
        ibi = np.diff(t)
        feats["beat_rate_hz"] = float(len(t) / duration)
        feats["ibi_mean_s"]   = float(np.mean(ibi))
        feats["ibi_std_s"]    = float(np.std(ibi))
        feats["bpm_motion"]   = float(60.0 / max(np.mean(ibi), 1e-9))
    else:
        feats["beat_rate_hz"] = 0.0
        feats["ibi_mean_s"]   = 0.0
        feats["ibi_std_s"]    = 0.0
        feats["bpm_motion"]   = 0.0

    return feats

def _describe_from_stats(val: float, p33: float, p66: float, low_word: str, mid_word: str, high_word: str) -> str:
    if val < p33:
        return low_word
    if val < p66:
        return mid_word
    return high_word

def build_prompt(style: str, bpm: float, pred: dict[str, float], y_stats: dict[str, tuple[float,float]]) -> str:
    # We prefer motion bpm (directly from movement). If it's missing, fallback to predicted audio bpm if present.
    bpm_use = bpm if bpm > 0 else float(pred.get("bpm_audio", pred.get("audio_tempo_bpm", 120.0)))
    bpm_round = int(round(bpm_use))

    # Use whichever columns exist in your Y_audio
    # Common ones from your scripts/dataset builder:
    #   rms_mean, spec_centroid_mean, spec_rolloff_mean, zcr_mean, bpm_audio
    rms = float(pred.get("rms_mean", 0.0))
    cen = float(pred.get("spec_centroid_mean", pred.get("centroid_mean", 0.0)))
    rol = float(pred.get("spec_rolloff_mean", pred.get("rolloff85_mean", 0.0)))
    zcr = float(pred.get("zcr_mean", 0.0))

    # Percentile thresholds from training Y_audio distribution (computed below)
    def p(name: str):
        if name not in y_stats:
            return (0.0, 0.0)
        return y_stats[name]

    energy_word = _describe_from_stats(rms, *p("rms_mean"), "calm", "driving", "energetic")
    bright_word = _describe_from_stats(cen, *p("spec_centroid_mean"), "warm", "balanced", "bright")
    perc_word   = _describe_from_stats(rol, *p("spec_rolloff_mean"), "soft percussion", "clear drums", "hard-hitting drums")
    tex_word    = _describe_from_stats(zcr, *p("zcr_mean"), "smooth texture", "clean texture", "crisp texture")

    return (
        f"{style}, {energy_word}, {bright_word}, {perc_word}, {tex_word}, "
        f"clear beat, tempo {bpm_round} bpm, tight timing, high quality mix, no vocals"
    )

def load_y_percentiles(dataset_dir: Path) -> dict[str, tuple[float,float]]:
    """
    Return {col: (p33, p66)} for a small set of useful Y columns.
    This makes prompt wording scale to YOUR dataset.
    """
    yp = dataset_dir / "Y_audio.csv"
    if not yp.exists():
        return {}
    df = pd.read_csv(yp)
    stats = {}
    for col in ["rms_mean", "spec_centroid_mean", "spec_rolloff_mean", "zcr_mean"]:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            v = df[col].dropna().to_numpy(dtype=float)
            if v.size >= 10:
                stats[col] = (float(np.percentile(v, 33)), float(np.percentile(v, 66)))
    return stats

def maybe_rerank_candidates(dataset_dir: Path, wav_paths: list[Path], pred: dict[str, float]) -> Path:
    """
    Optional reranking: compute audio features on each generated WAV and choose closest to predicted targets.
    If librosa isn't installed, returns first wav.
    """
    try:
        import librosa
    except Exception:
        return wav_paths[0]

    # Use same feature names as build_motion2music_dataset_v2.py
    keys = ["rms_mean", "spec_centroid_mean", "spec_rolloff_mean", "zcr_mean"]

    # Estimate normalization from training set
    yp = dataset_dir / "Y_audio.csv"
    mu = {}
    sd = {}
    if yp.exists():
        ydf = pd.read_csv(yp)
        for k in keys:
            if k in ydf.columns:
                arr = ydf[k].dropna().to_numpy(dtype=float)
                if arr.size:
                    mu[k] = float(arr.mean())
                    sd[k] = float(arr.std() + 1e-9)

    def feats_for_wav(p: Path):
        y, sr = librosa.load(str(p), sr=22050, mono=True)
        hop = 512
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)
        rolloff  = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=hop)
        rms      = librosa.feature.rms(y=y, hop_length=hop)
        zcr      = librosa.feature.zero_crossing_rate(y, hop_length=hop)
        return {
            "rms_mean": float(rms.mean()),
            "spec_centroid_mean": float(centroid.mean()),
            "spec_rolloff_mean": float(rolloff.mean()),
            "zcr_mean": float(zcr.mean()),
        }

    # Target vector from prediction (only the keys we have)
    tgt = {}
    for k in keys:
        if k in pred:
            tgt[k] = float(pred[k])

    best_p = wav_paths[0]
    best_d = float("inf")

    for p in wav_paths:
        f = feats_for_wav(p)
        d = 0.0
        for k in keys:
            if k in tgt:
                # normalize if we have stats
                if k in mu:
                    d += abs((f[k] - tgt[k]) / sd[k])
                else:
                    d += abs(f[k] - tgt[k])
        if d < best_d:
            best_d = d
            best_p = p

    return best_p

def main():
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
    args = ap.parse_args()

    root = project_root()
    dataset_dir = (root / args.dataset_dir).resolve() if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    out_dir = (root / args.out_dir).resolve() if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle = joblib.load(args.model_path)
    model = bundle["model"]
    X_cols: list[str] = bundle["X_cols"]
    Y_cols: list[str] = bundle["Y_cols"]

    lma_df = pd.read_csv(args.lma_csv)
    beats_df = pd.read_csv(args.beats_csv)

    xdict = compute_motion_features(lma_df, beats_df)
    bpm_motion = float(xdict.get("bpm_motion", 0.0))

    # Build X vector in training column order
    x = np.zeros((1, len(X_cols)), dtype=np.float32)
    missing = []
    for i, c in enumerate(X_cols):
        if c in xdict:
            x[0, i] = float(xdict[c])
        else:
            missing.append(c)

    pred_vec = model.predict(x)[0]
    pred = {c: float(v) for c, v in zip(Y_cols, pred_vec)}

    y_stats = load_y_percentiles(dataset_dir)
    prompt = build_prompt(args.style, bpm_motion, pred, y_stats)

    print("\n[prompt]")
    print(prompt)

    # Generate N candidates
    gen_script = root / "scripts" / "generate_music.py"
    wavs = []
    for k in range(args.num):
        seed = int(args.seed + k * 101)
        out_wav = out_dir / f"musicgen_{Path(args.lma_csv).stem}_s{seed}.wav"

        cmd = [
            sys.executable, str(gen_script),
            "--prompt", prompt,
            "--model", args.musicgen_model,
            "--duration", str(args.duration),
            "--out", str(out_wav),
            "--seed", str(seed),
        ]
        if args.cpu:
            cmd.append("--cpu")

        print("\n[cmd]", " ".join(cmd))
        subprocess.run(cmd, check=True)
        wavs.append(out_wav)

    if args.rerank and len(wavs) > 1:
        best = maybe_rerank_candidates(dataset_dir, wavs, pred)
        print(f"\n[best] {best}")
    else:
        print(f"\n[done] generated {len(wavs)} wav(s) -> {out_dir}")

if __name__ == "__main__":
    main()
