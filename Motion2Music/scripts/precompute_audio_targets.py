#!/usr/bin/env python3
"""
precompute_audio_targets.py

Reads meta.csv produced by build_motion2music_dataset*, loads each original audio file,
computes a compact set of audio descriptors (tempo + spectral + MFCC stats),
and writes Y_audio.csv (targets) aligned by clip_id.

Usage (run from repo root):
  python scripts/precompute_audio_targets.py --dataset-dir outputs/m2m_train
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd

def _find_col(df: pd.DataFrame, candidates: list[str]) -> str:
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    # try partial match
    for c in df.columns:
        cl = c.lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c
    raise KeyError(f"Could not find any of columns {candidates} in meta.csv. Available: {list(df.columns)[:30]}...")

def _audio_features_librosa(audio_path: Path, sr: int = 32000) -> dict[str, float]:
    try:
        import librosa
    except Exception as e:
        raise RuntimeError(
            "librosa is required for audio targets. Install inside your venv:\n"
            "  pip install librosa soundfile\n"
            f"Original import error: {e}"
        )

    y, sr = librosa.load(str(audio_path), sr=sr, mono=True)
    if y.size == 0:
        raise RuntimeError("Empty audio")

    # Beat / tempo
    try:
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
        beat_count = int(len(beats))
    except Exception:
        tempo, beat_count = np.nan, 0

    # Basic energy
    rms = librosa.feature.rms(y=y)[0]
    zcr = librosa.feature.zero_crossing_rate(y)[0]

    # Spectral
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    centroid = librosa.feature.spectral_centroid(S=S, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(S=S, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(S=S, sr=sr, roll_percent=0.85)[0]
    flatness = librosa.feature.spectral_flatness(S=S)[0]

    # MFCC
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

    def agg(prefix: str, arr: np.ndarray):
        return {
            f"{prefix}_mean": float(np.mean(arr)),
            f"{prefix}_std": float(np.std(arr)),
            f"{prefix}_min": float(np.min(arr)),
            f"{prefix}_max": float(np.max(arr)),
        }

    feats: dict[str, float] = {}
    feats["audio_duration_s"] = float(len(y) / sr)
    feats["audio_tempo_bpm"] = float(tempo) if np.isfinite(tempo) else np.nan
    feats["audio_beat_count"] = float(beat_count)

    feats |= agg("rms", rms)
    feats |= agg("zcr", zcr)
    feats |= agg("centroid", centroid)
    feats |= agg("bandwidth", bandwidth)
    feats |= agg("rolloff85", rolloff)
    feats |= agg("flatness", flatness)

    # MFCC per-coefficient mean/std
    for i in range(mfcc.shape[0]):
        feats[f"mfcc{i+1}_mean"] = float(np.mean(mfcc[i]))
        feats[f"mfcc{i+1}_std"] = float(np.std(mfcc[i]))

    return feats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", type=str, required=True, help="Folder that contains meta.csv (e.g., outputs/m2m_train)")
    ap.add_argument("--sr", type=int, default=32000)
    ap.add_argument("--limit", type=int, default=0, help="Debug: process only first N rows (0 = all)")
    ap.add_argument("--skip-existing", action="store_true", help="If Y_audio.csv exists, skip clips already in it")
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    meta_path = dataset_dir / "meta.csv"
    if not meta_path.exists():
        print(f"[error] meta.csv not found at: {meta_path}", file=sys.stderr)
        sys.exit(2)

    meta = pd.read_csv(meta_path)
    clip_col = _find_col(meta, ["clip_id", "id", "stem", "name"])
    audio_col = _find_col(meta, ["audio_path", "audio", "wav_path", "music_path"])

    out_path = dataset_dir / "Y_audio.csv"
    done = set()
    if args.skip_existing and out_path.exists():
        old = pd.read_csv(out_path)
        if "clip_id" in old.columns:
            done = set(old["clip_id"].astype(str).tolist())

    rows = []
    count = 0
    for r in meta.itertuples(index=False):
        clip_id = str(getattr(r, clip_col))
        audio_path = Path(str(getattr(r, audio_col)))
        if clip_id in done:
            continue
        if not audio_path.exists():
            print(f"[warn] missing audio for {clip_id}: {audio_path}")
            continue
        try:
            feats = _audio_features_librosa(audio_path, sr=args.sr)
            feats["clip_id"] = clip_id
            feats["audio_path"] = str(audio_path)
            rows.append(feats)
            count += 1
            if count % 50 == 0:
                print(f"[ok] processed {count} audio files...")
        except Exception as e:
            print(f"[warn] failed audio feats for {clip_id}: {e}")

        if args.limit and count >= args.limit:
            break

    if not rows:
        print("[error] No audio targets produced. Check paths and audio formats.", file=sys.stderr)
        sys.exit(3)

    df = pd.DataFrame(rows)
    cols = ["clip_id", "audio_path"] + [c for c in df.columns if c not in ("clip_id", "audio_path")]
    df = df[cols]

    if out_path.exists() and args.skip_existing:
        old = pd.read_csv(out_path)
        df = pd.concat([old, df], ignore_index=True)

    df.to_csv(out_path, index=False)
    print(f"[done] Wrote {len(df)} rows -> {out_path}")

if __name__ == "__main__":
    main()
