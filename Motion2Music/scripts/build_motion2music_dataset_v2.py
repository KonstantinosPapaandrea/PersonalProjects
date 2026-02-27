#!/usr/bin/env python3
"""build_motion2music_dataset.py

Builds a supervised dataset from aligned (BVH motion, audio) pairs.

Why this script exists
----------------------
You already have:
  • Motion -> LMA window features + kinematic beat events (from BVH)
  • Original audio for each BVH (aligned)

To train a "middle" ML model, you need a clean dataset:
  X_motion  (features from motion)
  Y_audio   (features extracted from the original audio)
  + metadata that keeps paths + stems aligned.

Folder layout (same spirit as make_final_model.py)
--------------------------------------------------
<datasets_root>/
  DB1/
    bvh/   (or BVH/)
    audio/ (or wav/, music/, ...)
  DB2/
    ...

For each BVH stem "clip_0001.bvh" the script expects an audio file:
  audio/clip_0001.(wav|mp3|flac|ogg|m4a)

Outputs
-------
<out_dir>/
  features/                 (cached per-clip)
    <stem>_lma.csv
    <stem>_beats.csv
  meta.csv                  (paths, durations, beats, etc.)
  X_motion.csv              (aggregated motion features)
  Y_audio.csv               (aggregated audio features)
  dataset.npz               (numpy arrays + column names)

Notes
-----
• Motion features are aggregated stats over the LMA windows + beat times.
• Audio features are aggregated stats (MFCC/chroma/spectral) using librosa.
  If you don't want audio features yet, pass --no-audio-feats.

Place this file in your repo's scripts/ folder.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------
# Repo/path helpers
# ---------------------------

def infer_repo_root() -> Path:
    """Infer repo root whether the script lives in scripts/ or is called elsewhere."""
    p = Path(__file__).resolve()
    if p.parent.name.lower() == "scripts":
        return p.parents[1]
    return p.parent


def find_child_dir(parent: Path, candidates: List[str]) -> Optional[Path]:
    for name in candidates:
        p = parent / name
        if p.exists() and p.is_dir():
            return p
    return None


# ---------------------------
# Pair discovery
# ---------------------------

AUDIO_EXTS_DEFAULT = ["wav", "mp3", "flac", "ogg", "m4a", "aac"]


@dataclass
class Pair:
    db_name: str
    stem: str
    bvh_path: Path
    audio_path: Path


_CAM_TOKEN_RE = re.compile(r"_c([^_]+)_", re.IGNORECASE)


def _audio_ext_ok(p: Path, audio_exts: List[str]) -> bool:
    return p.suffix.lower().lstrip(".") in audio_exts


def _camera_rank_from_stem(stem: str) -> int:
    """
    AIST++ quirk: BVH may contain cAll while audio is duplicated as c01/c02/...
    We want deterministic selection among duplicates.
      • prefer cAll (rank 0) if present
      • then prefer smallest numeric camera (c01 < c02 < ...)
      • otherwise fallback to a large rank
    """
    m = _CAM_TOKEN_RE.search(stem)
    if not m:
        return 999
    tok = m.group(1)
    if tok.lower() == "all":
        return 0
    if tok.isdigit():
        try:
            return 1 + int(tok)
        except Exception:
            return 500
    return 500


def _pick_best_audio(hits: List[Path], audio_exts: List[str]) -> Optional[Path]:
    if not hits:
        return None

    def key(p: Path):
        ext = p.suffix.lower().lstrip(".")
        ext_rank = audio_exts.index(ext) if ext in audio_exts else 999
        cam_rank = _camera_rank_from_stem(p.stem)
        return (ext_rank, cam_rank, p.name.lower())

    return sorted(hits, key=key)[0]


def find_audio_for_stem(audio_dir: Path, stem: str, audio_exts: List[str]) -> Optional[Path]:
    # 1) Fast path: exact match by extension order
    for ext in audio_exts:
        p = audio_dir / f"{stem}.{ext}"
        if p.exists():
            return p

    # 2) Exact stem, any extension
    hits = [p for p in audio_dir.glob(f"{stem}.*") if _audio_ext_ok(p, audio_exts)]
    best = _pick_best_audio(hits, audio_exts)
    if best:
        return best

    # 3) AIST++ fallback: ignore camera token variations (cAll vs c01/c02/...)
    # Example:
    #   BVH : gWA_sBM_cAll_d25_mWA1_ch07.bvh
    #   AUD : gWA_sBM_c01_d25_mWA1_ch07.wav  (duplicates for c02, c03, ...)
    if "_c" in stem:
        cam_wild = re.sub(r"_c[^_]+_", "_c*_", stem, flags=re.IGNORECASE)
        hits = [p for p in audio_dir.glob(f"{cam_wild}.*") if _audio_ext_ok(p, audio_exts)]
        best = _pick_best_audio(hits, audio_exts)
        if best:
            return best

        # 4) Extra conservative fallbacks (sometimes one side uses cAll, the other uses digits)
        if re.search(r"_c\d\d_", stem, flags=re.IGNORECASE):
            alt = re.sub(r"_c\d\d_", "_cAll_", stem, flags=re.IGNORECASE)
            hits = [p for p in audio_dir.glob(f"{alt}.*") if _audio_ext_ok(p, audio_exts)]
            best = _pick_best_audio(hits, audio_exts)
            if best:
                return best
        if re.search(r"_cAll_", stem, flags=re.IGNORECASE):
            alt = re.sub(r"_cAll_", "_c01_", stem, flags=re.IGNORECASE)
            hits = [p for p in audio_dir.glob(f"{alt}.*") if _audio_ext_ok(p, audio_exts)]
            best = _pick_best_audio(hits, audio_exts)
            if best:
                return best

    return None



def collect_pairs(datasets_root: Path, audio_exts: List[str], max_files_per_db: Optional[int]) -> List[Pair]:
    pairs: List[Pair] = []

    db_folders = [p for p in sorted(datasets_root.iterdir()) if p.is_dir()]
    if not db_folders:
        raise SystemExit(f"No subfolders found inside: {datasets_root}")

    for db in db_folders:
        bvh_dir = find_child_dir(db, ["bvh", "BVH", "bvhs", "BVHS"])
        audio_dir = find_child_dir(db, ["audio", "AUDIO", "wav", "WAV", "music", "MUSIC"])
        if not bvh_dir or not audio_dir:
            print(f"[skip] {db.name} (missing bvh/ or audio/)")
            continue

        bvh_files = sorted(bvh_dir.glob("*.bvh"))
        if max_files_per_db is not None:
            bvh_files = bvh_files[: int(max_files_per_db)]

        for bvh_path in bvh_files:
            stem = bvh_path.stem
            audio_path = find_audio_for_stem(audio_dir, stem, audio_exts)
            if audio_path is None:
                print(f"[warn] no audio for {db.name}/{stem} (looked in {audio_dir})")
                continue
            pairs.append(Pair(db_name=db.name, stem=stem, bvh_path=bvh_path, audio_path=audio_path))

    if not pairs:
        raise SystemExit(
            "No (BVH,audio) pairs found. Check folder structure and matching filenames (BVH stem == audio stem)."
        )

    return pairs


# ---------------------------
# Feature extraction helpers
# ---------------------------

LMA_EXCLUDE_COLS = {
    "START_FRAME",
    "END_FRAME",
    "START_FRAME_ORIG",
    "END_FRAME_ORIG",
    "START_TIME_S",
    "END_TIME_S",
}


def compute_motion_features(lma_df: pd.DataFrame, beats_df: pd.DataFrame) -> Dict[str, float]:
    """Aggregates LMA windows + beat times into one fixed-length feature dict."""

    feats: Dict[str, float] = {}

    # ---- LMA window stats
    num_cols = [c for c in lma_df.columns if c not in LMA_EXCLUDE_COLS]
    # keep only numeric
    num_cols = [c for c in num_cols if pd.api.types.is_numeric_dtype(lma_df[c])]

    if len(num_cols) == 0:
        raise ValueError("No numeric LMA columns found to aggregate.")

    for c in num_cols:
        x = lma_df[c].astype(float).to_numpy()
        feats[f"lma_mean_{c}"] = float(np.nanmean(x))
        feats[f"lma_std_{c}"] = float(np.nanstd(x))

    # a couple of derived, stable aggregates
    if "BODY" in lma_df.columns and pd.api.types.is_numeric_dtype(lma_df["BODY"]):
        feats["lma_body_p90"] = float(np.nanpercentile(lma_df["BODY"].astype(float), 90))

    # ---- Beats stats
    if beats_df is None or len(beats_df) == 0:
        feats["beat_count"] = 0.0
        feats["beat_rate_hz"] = 0.0
        feats["bpm_motion"] = 0.0
        feats["ibi_mean_s"] = 0.0
        feats["ibi_std_s"] = 0.0
        return feats

    t = beats_df["time_s"].astype(float).to_numpy()
    t = np.unique(t)
    t.sort()
    feats["beat_count"] = float(len(t))

    duration = float(max(t[-1], 1e-9) - t[0]) if len(t) >= 2 else float(max(t[0], 1e-9))
    feats["beat_rate_hz"] = float(len(t) / max(duration, 1e-9))

    if len(t) >= 2:
        ibi = np.diff(t)
        feats["ibi_mean_s"] = float(np.mean(ibi))
        feats["ibi_std_s"] = float(np.std(ibi))
        feats["bpm_motion"] = float(60.0 / max(np.mean(ibi), 1e-9))
    else:
        feats["ibi_mean_s"] = 0.0
        feats["ibi_std_s"] = 0.0
        feats["bpm_motion"] = 0.0

    return feats


def safe_audio_duration_seconds(audio_path: Path) -> Optional[float]:
    """Best-effort duration; avoids hard dependencies."""
    try:
        import soundfile as sf

        info = sf.info(str(audio_path))
        if info.frames > 0 and info.samplerate > 0:
            return float(info.frames / info.samplerate)
    except Exception:
        pass

    # librosa fallback
    try:
        import librosa

        return float(librosa.get_duration(path=str(audio_path)))
    except Exception:
        return None


def compute_audio_features_librosa(audio_path: Path, sr: int, hop_length: int, n_mfcc: int) -> Dict[str, float]:
    """Aggregated audio feature dict using librosa."""
    import librosa

    y, sr = librosa.load(str(audio_path), sr=sr, mono=True)
    if y.size == 0:
        raise ValueError("Empty audio signal")

    feats: Dict[str, float] = {}

    # tempo estimate
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)
    feats["bpm_audio"] = float(tempo)

    # MFCC
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc, hop_length=hop_length)
    mfcc_mean = mfcc.mean(axis=1)
    mfcc_std = mfcc.std(axis=1)
    for i in range(n_mfcc):
        feats[f"mfcc_mean_{i:02d}"] = float(mfcc_mean[i])
        feats[f"mfcc_std_{i:02d}"] = float(mfcc_std[i])

    # Chroma
    chroma = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=hop_length)
    chroma_mean = chroma.mean(axis=1)
    for i in range(chroma_mean.shape[0]):
        feats[f"chroma_mean_{i:02d}"] = float(chroma_mean[i])

    # Spectral features
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=hop_length)
    rms = librosa.feature.rms(y=y, hop_length=hop_length)
    zcr = librosa.feature.zero_crossing_rate(y, hop_length=hop_length)

    feats["spec_centroid_mean"] = float(centroid.mean())
    feats["spec_centroid_std"] = float(centroid.std())
    feats["spec_rolloff_mean"] = float(rolloff.mean())
    feats["spec_rolloff_std"] = float(rolloff.std())
    feats["rms_mean"] = float(rms.mean())
    feats["rms_std"] = float(rms.std())
    feats["zcr_mean"] = float(zcr.mean())
    feats["zcr_std"] = float(zcr.std())

    return feats


# ---------------------------
# LMA+beats CSV generation
# ---------------------------

def run_lma_tempo_export(
    lma_export_py: Path,
    bvh_path: Path,
    lma_repo: Path,
    features_dir: Path,
    window_style_word: int,
    step_style_word: int,
    min_interval_s: float,
    dedup_within_s: float,
    env: Optional[dict] = None,
) -> None:
    cmd = [
        sys.executable,
        str(lma_export_py),
        "--bvh",
        str(bvh_path),
        "--lma-repo",
        str(lma_repo),
        "--out",
        str(features_dir),
        "--window-style-word",
        str(window_style_word),
        "--step-style-word",
        str(step_style_word),
        "--min-interval-s",
        str(min_interval_s),
        "--dedup-within-s",
        str(dedup_within_s),
    ]

    print("[cmd]", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


# ---------------------------
# Main
# ---------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets-root", required=True, help="Folder containing DB subfolders (each with bvh/ and audio/)")

    ap.add_argument(
        "--lma-repo",
        required=True,
        help="Path to lma-feature-extraction-main folder (contains create_annotator.py, loadbvh.py)",
    )

    ap.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default: <repo_root>/outputs/m2m_dataset_<timestamp>)",
    )

    ap.add_argument("--max-files-per-db", type=int, default=None, help="Debug: limit files per DB")
    ap.add_argument("--audio-exts", default=",".join(AUDIO_EXTS_DEFAULT), help="Comma list of audio extensions")

    ap.add_argument("--skip-existing", action="store_true", help="Skip LMA/beat CSV generation if already cached")

    # LMA params
    ap.add_argument("--window-style-word", type=int, default=16)
    ap.add_argument("--step-style-word", type=int, default=4)

    # beat params
    ap.add_argument("--min-interval-s", type=float, default=0.25)
    ap.add_argument("--dedup-within-s", type=float, default=0.10)

    # audio feature extraction
    ap.add_argument("--no-audio-feats", action="store_true", help="Do not compute audio features (Y_audio)")
    ap.add_argument("--sr", type=int, default=22050)
    ap.add_argument("--hop-length", type=int, default=512)
    ap.add_argument("--n-mfcc", type=int, default=20)

    args = ap.parse_args()

    repo_root = infer_repo_root()
    datasets_root = Path(args.datasets_root).expanduser().resolve()
    lma_repo = Path(args.lma_repo).expanduser().resolve()

    # locate lmaTempoExport.py
    lma_export_py = repo_root / "scripts" / "lmaTempoExport_v2.py"
    if not lma_export_py.exists():
        # fallback: allow running from the same folder as this script
        alt = Path(__file__).resolve().parent / "lmaTempoExport_v2.py"
        if alt.exists():
            lma_export_py = alt
        else:
            raise SystemExit(
                "Could not find scripts/lmaTempoExport.py. Put lmaTempoExport.py in your repo's scripts/ folder."
            )

    audio_exts = [e.strip().lower() for e in args.audio_exts.split(",") if e.strip()]

    # out dir
    if args.out_dir:
        out_dir = Path(args.out_dir).expanduser().resolve()
    else:
        import time

        stamp = time.strftime("%Y%m%d_%H%M%S")
        out_dir = repo_root / "outputs" / f"m2m_dataset_{stamp}"

    out_dir.mkdir(parents=True, exist_ok=True)
    features_dir = out_dir / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    print(f"[root] repo={repo_root}")
    print(f"[root] datasets={datasets_root}")
    print(f"[out]  {out_dir}")
    print(f"[feat] {features_dir}")

    pairs = collect_pairs(datasets_root, audio_exts=audio_exts, max_files_per_db=args.max_files_per_db)
    print(f"[pairs] {len(pairs)}")

    # best-effort: keep your scripts import-stable like make_final_model does
    env = os.environ.copy()
    # add common PYTHONPATH hints
    extras = [
        str(repo_root),
        str(repo_root / "scripts"),
        str(repo_root / "src"),
    ]
    old = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([p for p in ([old] + extras) if p])

    meta_rows = []
    X_rows: List[Dict[str, float]] = []
    Y_rows: List[Dict[str, float]] = []

    for i, pair in enumerate(pairs):
        clip_id = i
        stem = pair.stem

        lma_csv = features_dir / f"{stem}_lma.csv"
        beats_csv = features_dir / f"{stem}_beats.csv"

        need_extract = not (lma_csv.exists() and beats_csv.exists())
        if need_extract or not args.skip_existing:
            # if skip_existing is set, only run when missing
            if need_extract or not args.skip_existing:
                try:
                    run_lma_tempo_export(
                        lma_export_py=lma_export_py,
                        bvh_path=pair.bvh_path,
                        lma_repo=lma_repo,
                        features_dir=features_dir,
                        window_style_word=args.window_style_word,
                        step_style_word=args.step_style_word,
                        min_interval_s=args.min_interval_s,
                        dedup_within_s=args.dedup_within_s,
                        env=env,
                    )
                except subprocess.CalledProcessError as e:
                    print(f"[error] LMA/beat extraction failed for {pair.bvh_path}: {e}")
                    continue

        if not (lma_csv.exists() and beats_csv.exists()):
            print(f"[error] Missing expected CSVs for {stem} after extraction. Skipping.")
            continue

        # load CSVs
        try:
            lma_df = pd.read_csv(lma_csv)
            beats_df = pd.read_csv(beats_csv)
        except Exception as e:
            print(f"[error] Failed reading CSVs for {stem}: {e}")
            continue

        # compute X
        try:
            x = compute_motion_features(lma_df, beats_df)
        except Exception as e:
            print(f"[error] Motion feature aggregation failed for {stem}: {e}")
            continue

        # compute Y
        y = {}
        if not args.no_audio_feats:
            try:
                y = compute_audio_features_librosa(
                    pair.audio_path,
                    sr=args.sr,
                    hop_length=args.hop_length,
                    n_mfcc=args.n_mfcc,
                )
            except ModuleNotFoundError:
                raise SystemExit(
                    "Audio features require librosa. Install it in your venv:\n"
                    "  pip install librosa soundfile\n"
                    "If you want to skip audio features for now, rerun with --no-audio-feats."
                )
            except Exception as e:
                print(f"[warn] Audio feature extraction failed for {stem}: {e}")
                y = {}

        audio_dur = safe_audio_duration_seconds(pair.audio_path)
        bpm_motion = float(x.get("bpm_motion", 0.0))
        bpm_audio = float(y.get("bpm_audio", 0.0)) if y else 0.0

        meta_rows.append(
            {
                "clip_id": clip_id,
                "db": pair.db_name,
                "stem": stem,
                "bvh_path": str(pair.bvh_path),
                "audio_path": str(pair.audio_path),
                "audio_duration_s": audio_dur,
                "lma_rows": int(len(lma_df)),
                "beat_count": int(len(beats_df)) if beats_df is not None else 0,
                "bpm_motion": bpm_motion,
                "bpm_audio": bpm_audio,
            }
        )

        X_rows.append(x)
        Y_rows.append(y)

        if (clip_id + 1) % 25 == 0 or (clip_id + 1) == len(pairs):
            print(f"[progress] {clip_id+1}/{len(pairs)}")

    if not meta_rows:
        raise SystemExit("No clips were successfully processed. Check errors above.")

    meta_df = pd.DataFrame(meta_rows)
    X_df = pd.DataFrame(X_rows)
    Y_df = pd.DataFrame(Y_rows) if not args.no_audio_feats else pd.DataFrame([])

    # keep deterministic column order
    X_df = X_df.reindex(sorted(X_df.columns), axis=1)
    if not args.no_audio_feats and not Y_df.empty:
        Y_df = Y_df.reindex(sorted(Y_df.columns), axis=1)

    # save CSVs
    meta_path = out_dir / "meta.csv"
    X_path = out_dir / "X_motion.csv"
    meta_df.to_csv(meta_path, index=False)
    X_df.to_csv(X_path, index=False)

    if not args.no_audio_feats:
        Y_path = out_dir / "Y_audio.csv"
        Y_df.to_csv(Y_path, index=False)

    # save NPZ
    X = X_df.to_numpy(dtype=np.float32)
    clip_ids = meta_df["clip_id"].to_numpy(dtype=np.int64)

    if not args.no_audio_feats and not Y_df.empty:
        Y = Y_df.to_numpy(dtype=np.float32)
        y_cols = Y_df.columns.to_list()
    else:
        Y = np.zeros((X.shape[0], 0), dtype=np.float32)
        y_cols = []

    out_npz = out_dir / "dataset.npz"
    np.savez_compressed(
        out_npz,
        X=X,
        Y=Y,
        clip_ids=clip_ids,
        x_cols=np.array(X_df.columns.to_list(), dtype=object),
        y_cols=np.array(y_cols, dtype=object),
        db=np.array(meta_df["db"].to_list(), dtype=object),
        stem=np.array(meta_df["stem"].to_list(), dtype=object),
        bvh_path=np.array(meta_df["bvh_path"].to_list(), dtype=object),
        audio_path=np.array(meta_df["audio_path"].to_list(), dtype=object),
        config_json=json.dumps(
            {
                "sr": args.sr,
                "hop_length": args.hop_length,
                "n_mfcc": args.n_mfcc,
                "window_style_word": args.window_style_word,
                "step_style_word": args.step_style_word,
                "min_interval_s": args.min_interval_s,
                "dedup_within_s": args.dedup_within_s,
                "no_audio_feats": bool(args.no_audio_feats),
            }
        ),
    )

    print("\n[DONE]")
    print(f"  meta   -> {meta_path}")
    print(f"  X      -> {X_path}")
    if not args.no_audio_feats:
        print(f"  Y      -> {out_dir / 'Y_audio.csv'}")
    print(f"  npz    -> {out_npz}")
    print(f"  clips  -> {len(meta_df)}")
    print(f"  X_dim  -> {X.shape[1]}")
    print(f"  Y_dim  -> {Y.shape[1]}")


if __name__ == "__main__":
    main()
