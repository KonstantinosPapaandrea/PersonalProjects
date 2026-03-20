#!/usr/bin/env python3
"""
train_motion_controller.py

Trains a baseline supervised model that maps motion features -> audio descriptor targets.

Inputs expected inside --dataset-dir:
  X_motion.csv   (from build_motion2music_dataset*)
  Y_audio.csv    (from precompute_audio_targets.py)

Outputs:
  <dataset-dir>/models/motion2audio_<model>.joblib
  <dataset-dir>/reports/train_report.txt

Usage:
  python scripts/train_motion_controller.py --dataset-dir outputs/m2m_train --model ridge
"""

from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

LMA_EXCLUDE_COLS = {
    "START_FRAME",
    "END_FRAME",
    "START_FRAME_ORIG",
    "END_FRAME_ORIG",
    "START_TIME_S",
    "END_TIME_S",
}

RHYTHM_ENERGY_TARGETS = {
    "audio_tempo_bpm",
    "audio_beat_count",
    "rms_mean",
    "rms_std",
    "zcr_mean",
    "zcr_std",
    "centroid_mean",
    "centroid_std",
    "bandwidth_mean",
    "bandwidth_std",
    "rolloff85_mean",
    "rolloff85_std",
    "flatness_mean",
    "flatness_std",
}

RHYTHM_CORE_TARGETS = {
    "audio_tempo_bpm",
    "audio_beat_count",
    "rms_mean",
    "rms_std",
    "zcr_mean",
    "zcr_std",
}


def _compute_motion_features(lma_df: pd.DataFrame, beats_df: pd.DataFrame) -> dict[str, float]:
    feats: dict[str, float] = {}

    num_cols = [c for c in lma_df.columns if c not in LMA_EXCLUDE_COLS]
    num_cols = [c for c in num_cols if pd.api.types.is_numeric_dtype(lma_df[c])]
    if len(num_cols) == 0:
        raise ValueError("No numeric LMA columns found in chunk.")

    for c in num_cols:
        x = lma_df[c].astype(float).to_numpy()
        feats[f"lma_mean_{c}"] = float(np.nanmean(x))
        feats[f"lma_std_{c}"] = float(np.nanstd(x))

    if "BODY" in lma_df.columns and pd.api.types.is_numeric_dtype(lma_df["BODY"]):
        feats["lma_body_p90"] = float(np.nanpercentile(lma_df["BODY"].astype(float), 90))

    if beats_df is None or len(beats_df) == 0:
        feats["beat_count"] = 0.0
        feats["beat_rate_hz"] = 0.0
        feats["bpm_motion"] = 0.0
        feats["ibi_mean_s"] = 0.0
        feats["ibi_std_s"] = 0.0
        return feats

    if "time_s" not in beats_df.columns:
        num_candidates = [
            c for c in beats_df.columns if pd.api.types.is_numeric_dtype(beats_df[c])
        ]
        if not num_candidates:
            raise ValueError("Chunk beats csv has no numeric time column.")
        t = beats_df[num_candidates[0]].astype(float).to_numpy()
    else:
        t = beats_df["time_s"].astype(float).to_numpy()

    t = np.unique(t)
    t.sort()
    feats["beat_count"] = float(len(t))
    if len(t) == 0:
        feats["beat_rate_hz"] = 0.0
        feats["bpm_motion"] = 0.0
        feats["ibi_mean_s"] = 0.0
        feats["ibi_std_s"] = 0.0
        return feats

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


def _audio_features_librosa_chunk(audio_path: Path, offset_s: float, duration_s: float, sr: int) -> dict[str, float]:
    import librosa

    y, sr = librosa.load(
        str(audio_path),
        sr=sr,
        mono=True,
        offset=max(0.0, float(offset_s)),
        duration=max(0.01, float(duration_s)),
    )
    if y.size == 0:
        raise RuntimeError("Empty audio chunk")

    try:
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
        beat_count = int(len(beats))
    except Exception:
        tempo, beat_count = np.nan, 0
    if isinstance(tempo, np.ndarray):
        tempo = float(np.ravel(tempo)[0]) if tempo.size else np.nan

    rms = librosa.feature.rms(y=y)[0]
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    centroid = librosa.feature.spectral_centroid(S=S, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(S=S, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(S=S, sr=sr, roll_percent=0.85)[0]
    flatness = librosa.feature.spectral_flatness(S=S)[0]
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
    for i in range(mfcc.shape[0]):
        feats[f"mfcc{i+1}_mean"] = float(np.mean(mfcc[i]))
        feats[f"mfcc{i+1}_std"] = float(np.std(mfcc[i]))
    return feats


def _build_chunked_set(
    dataset_dir: Path,
    dbs: list[str],
    x_cols: list[str],
    y_cols: list[str],
    chunk_seconds: float,
    hop_seconds: float,
    chunk_sr: int,
    min_lma_rows: int,
    max_chunks_per_clip: int,
    allowed_stems: set[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
    meta_path = dataset_dir / "meta.csv"
    features_dir = dataset_dir / "features"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path} for chunked test mode.")
    if not features_dir.exists():
        raise FileNotFoundError(f"Missing {features_dir} for chunked test mode.")

    meta = pd.read_csv(meta_path)
    meta = meta[meta["db"].astype(str).isin(dbs)].copy()
    if allowed_stems is not None:
        meta = meta[meta["stem"].astype(str).isin(allowed_stems)].copy()
    if meta.empty:
        raise RuntimeError(f"No meta rows found for dbs: {dbs}")

    hop = hop_seconds if hop_seconds > 0 else chunk_seconds
    x_rows: list[np.ndarray] = []
    y_rows: list[np.ndarray] = []
    db_rows: list[str] = []
    used_clips = 0
    used_chunks = 0

    for row in meta.itertuples(index=False):
        stem = str(getattr(row, "stem"))
        db_name = str(getattr(row, "db"))
        audio_path = Path(str(getattr(row, "audio_path")))
        lma_path = features_dir / f"{stem}_lma.csv"
        beats_path = features_dir / f"{stem}_beats.csv"
        if not lma_path.exists() or not beats_path.exists() or not audio_path.exists():
            continue

        lma_df = pd.read_csv(lma_path)
        beats_df = pd.read_csv(beats_path)
        if "START_TIME_S" not in lma_df.columns or "END_TIME_S" not in lma_df.columns:
            continue

        dur = float(getattr(row, "audio_duration_s", np.nan))
        if not np.isfinite(dur) or dur <= 0:
            try:
                import librosa
                dur = float(librosa.get_duration(path=str(audio_path)))
            except Exception:
                continue
        if dur <= 0:
            continue

        starts = []
        cur = 0.0
        while cur + (0.5 * chunk_seconds) <= dur:
            starts.append(cur)
            cur += hop
        tail_start = max(0.0, dur - chunk_seconds)
        if (not starts) or (abs(tail_start - starts[-1]) > 1e-6 and (dur - starts[-1]) > 0.5 * chunk_seconds):
            starts.append(tail_start)
        if max_chunks_per_clip > 0 and len(starts) > max_chunks_per_clip:
            pick_idx = np.linspace(0, len(starts) - 1, num=max_chunks_per_clip, dtype=int)
            starts = [starts[int(i)] for i in sorted(set(pick_idx.tolist()))]

        clip_used = False
        for s in starts:
            e = min(dur, s + chunk_seconds)
            if e - s < 0.5 * chunk_seconds:
                continue
            lma_chunk = lma_df[(lma_df["END_TIME_S"] > s) & (lma_df["START_TIME_S"] < e)].copy()
            if len(lma_chunk) < min_lma_rows:
                continue

            if "time_s" in beats_df.columns:
                b_chunk = beats_df[(beats_df["time_s"] >= s) & (beats_df["time_s"] < e)].copy()
                if not b_chunk.empty:
                    b_chunk["time_s"] = b_chunk["time_s"].astype(float) - float(s)
            else:
                b_chunk = beats_df.copy()

            try:
                x_feat = _compute_motion_features(lma_chunk, b_chunk)
                y_feat = _audio_features_librosa_chunk(audio_path, s, e - s, sr=chunk_sr)
            except Exception:
                continue

            x_vec = np.array([x_feat.get(c, 0.0) for c in x_cols], dtype=np.float32)
            y_vec = np.array([y_feat.get(c, np.nan) for c in y_cols], dtype=np.float32)
            x_rows.append(np.nan_to_num(x_vec, nan=0.0, posinf=0.0, neginf=0.0))
            y_rows.append(np.nan_to_num(y_vec, nan=0.0, posinf=0.0, neginf=0.0))
            db_rows.append(db_name)
            used_chunks += 1
            clip_used = True

        if clip_used:
            used_clips += 1

    if not x_rows:
        raise RuntimeError("Chunking produced zero valid chunks.")
    return (
        np.stack(x_rows, axis=0),
        np.stack(y_rows, axis=0),
        np.array(db_rows),
        used_clips,
        used_chunks,
    )


def _compute_r2_stats(y_true: np.ndarray, y_pred: np.ndarray, y_cols: list[str]) -> dict:
    rows = []
    for j, col in enumerate(y_cols):
        try:
            r2 = float(r2_score(y_true[:, j], y_pred[:, j]))
        except Exception:
            continue
        var = float(np.var(y_true[:, j]))
        mae = float(np.mean(np.abs(y_true[:, j] - y_pred[:, j])))
        rows.append({"target": col, "r2": r2, "var": var, "mae": mae})

    if not rows:
        return {
            "rows": [],
            "r2_mean": float("nan"),
            "r2_median": float("nan"),
            "r2_p10": float("nan"),
            "r2_p90": float("nan"),
            "r2_positive": 0,
            "low_var_count": 0,
        }

    r2_vals = np.array([r["r2"] for r in rows], dtype=float)
    low_var_count = int(sum(1 for r in rows if r["var"] < 1e-6))
    return {
        "rows": rows,
        "r2_mean": float(np.mean(r2_vals)),
        "r2_median": float(np.median(r2_vals)),
        "r2_p10": float(np.percentile(r2_vals, 10)),
        "r2_p90": float(np.percentile(r2_vals, 90)),
        "r2_positive": int(np.sum(r2_vals > 0.0)),
        "low_var_count": low_var_count,
    }

def _parse_db_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _parse_csv_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _targets_from_profile(y_cols: list[str], profile: str) -> set[str]:
    profile = (profile or "").strip().lower()
    if profile in ("", "all"):
        return set(y_cols)
    if profile == "rhythm_energy":
        return {c for c in y_cols if c in RHYTHM_ENERGY_TARGETS}
    if profile == "rhythm_core":
        return {c for c in y_cols if c in RHYTHM_CORE_TARGETS}
    raise ValueError(f"Unknown --target-profile='{profile}'.")


def _resolve_ids(df: pd.DataFrame, meta: pd.DataFrame, preferred_col: str) -> tuple[pd.DataFrame, str]:
    """
    Ensure a dataframe has a stable clip id column.
    If preferred_col does not exist, fall back to meta.csv row alignment.
    """
    if preferred_col in df.columns:
        return df, preferred_col

    if len(df) == len(meta) and "clip_id" in meta.columns:
        out = df.copy()
        out.insert(0, "clip_id", meta["clip_id"].to_numpy())
        return out, "clip_id"

    # Last-resort fallback kept for backward compatibility.
    return df, df.columns[0]


def _load_xy(
    dataset_dir: Path,
    test_dbs: list[str],
    test_size: float,
    seed: int,
    test_db_fraction: float,
):
    Xp = dataset_dir / "X_motion.csv"
    Yp = dataset_dir / "Y_audio.csv"
    Mp = dataset_dir / "meta.csv"
    if not Xp.exists():
        raise FileNotFoundError(f"Missing {Xp}. Run build_motion2music_dataset first.")
    if not Yp.exists():
        raise FileNotFoundError(f"Missing {Yp}. Run precompute_audio_targets.py first.")
    if not Mp.exists():
        raise FileNotFoundError(f"Missing {Mp}. Needed for db-based split.")

    Xdf = pd.read_csv(Xp)
    Ydf = pd.read_csv(Yp)
    meta = pd.read_csv(Mp)

    Xdf, xid = _resolve_ids(Xdf, meta, "clip_id")
    Ydf, yid = _resolve_ids(Ydf, meta, "clip_id")

    # Add db labels by clip_id; used for deterministic train/test holdout by dataset.
    if "clip_id" in meta.columns and "db" in meta.columns:
        cols = ["clip_id", "db"]
        if "stem" in meta.columns:
            cols.append("stem")
        if "audio_path" in meta.columns:
            cols.append("audio_path")
        db_map = meta[cols].copy()
        db_map["clip_id"] = db_map["clip_id"].astype(str)
        Xdf[xid] = Xdf[xid].astype(str)
        Ydf[yid] = Ydf[yid].astype(str)
        Xdf = Xdf.merge(db_map, left_on=xid, right_on="clip_id", how="left")
        Ydf = Ydf.merge(db_map, left_on=yid, right_on="clip_id", how="left")
        if xid != "clip_id":
            Xdf = Xdf.drop(columns=["clip_id"])
        if yid != "clip_id":
            Ydf = Ydf.drop(columns=["clip_id"])
    else:
        Xdf["db"] = "unknown"
        Ydf["db"] = "unknown"

    df = Xdf.merge(Ydf, left_on=xid, right_on=yid, how="inner", suffixes=("", "_y"))
    if df.empty:
        raise RuntimeError("No aligned rows between X_motion.csv and Y_audio.csv. Check clip_id naming.")

    def _is_aux_col(col: str, id_col: str) -> bool:
        cl = col.lower()
        if cl == id_col.lower() or cl in ("db", "stem", "clip_id") or cl.startswith("clip_id_"):
            return True
        if cl == "audio_path" or cl.startswith("audio_path_"):
            return True
        return False

    x_candidates = [c for c in Xdf.columns if not _is_aux_col(c, xid)]
    X_num_df = df[x_candidates].select_dtypes(include=[np.number]).fillna(0.0)
    X_cols = X_num_df.columns.to_list()
    X = X_num_df.to_numpy(dtype=np.float32)

    y_candidates = [c for c in Ydf.columns if not _is_aux_col(c, yid)]
    Y_num_df = df[y_candidates].select_dtypes(include=[np.number]).fillna(0.0)
    Y_cols = Y_num_df.columns.to_list()
    Y = Y_num_df.to_numpy(dtype=np.float32)

    db = df["db"].astype(str).to_numpy() if "db" in df.columns else np.array(["unknown"] * len(df))
    if "stem" in df.columns:
        stem = df["stem"].astype(str).to_numpy()
    else:
        stem = df[xid].astype(str).to_numpy()

    if test_dbs:
        if test_db_fraction >= 1.0:
            mask_test = np.isin(db, test_dbs)
        else:
            rng = np.random.RandomState(seed)
            mask_test = np.zeros(len(db), dtype=bool)
            for db_name in test_dbs:
                db_idx = np.where(db == db_name)[0]
                if db_idx.size == 0:
                    continue
                groups = np.unique(stem[db_idx])
                if groups.size == 0:
                    continue
                n_test = int(round(groups.size * float(test_db_fraction)))
                n_test = max(1, min(groups.size, n_test))
                picked = rng.choice(groups, size=n_test, replace=False)
                mask_test[db_idx] = np.isin(stem[db_idx], picked)
        if not np.any(mask_test):
            raise RuntimeError(
                f"No rows found for --test-dbs={test_dbs}. Available db values: {sorted(set(db.tolist()))}"
            )
        if np.all(mask_test):
            raise RuntimeError("All rows fall into test set. Need at least one training db.")
        split = {
            "Xtr": X[~mask_test],
            "Xte": X[mask_test],
            "Ytr": Y[~mask_test],
            "Yte": Y[mask_test],
            "db_tr": db[~mask_test],
            "db_te": db[mask_test],
            "stem_tr": stem[~mask_test],
            "stem_te": stem[mask_test],
        }
    else:
        Xtr, Xte, Ytr, Yte, db_tr, db_te, stem_tr, stem_te = train_test_split(
            X, Y, db, stem, test_size=test_size, random_state=seed
        )
        split = {
            "Xtr": Xtr,
            "Xte": Xte,
            "Ytr": Ytr,
            "Yte": Yte,
            "db_tr": db_tr,
            "db_te": db_te,
            "stem_tr": stem_tr,
            "stem_te": stem_te,
        }

    return split, X_cols, Y_cols

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", type=str, required=True)
    ap.add_argument("--model", type=str, default="ridge", choices=["ridge", "rf", "mlp"])
    ap.add_argument("--test-size", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--test-dbs",
        type=str,
        default="",
        help="Comma-separated db names to hold out as test only (e.g. simonalexanderson).",
    )
    ap.add_argument(
        "--test-db-fraction",
        type=float,
        default=1.0,
        help="If <1 and --test-dbs is set, hold out this fraction of clips from each test db; remaining clips from that db stay in training.",
    )
    ap.add_argument(
        "--chunk-train-seconds",
        type=float,
        default=0.0,
        help="If >0, rebuild training set as audio/LMA chunks of this duration (seconds).",
    )
    ap.add_argument(
        "--chunk-train-hop-seconds",
        type=float,
        default=0.0,
        help="Chunk hop for training chunking (seconds). Default: same as --chunk-train-seconds.",
    )
    ap.add_argument(
        "--chunk-train-sr",
        type=int,
        default=32000,
        help="Sample rate used for chunked training audio target extraction.",
    )
    ap.add_argument(
        "--chunk-train-min-lma-rows",
        type=int,
        default=4,
        help="Minimum LMA rows required for a training chunk to be kept.",
    )
    ap.add_argument(
        "--chunk-train-max-per-clip",
        type=int,
        default=0,
        help="If >0, keep at most this many train chunks per clip (uniformly over time).",
    )
    ap.add_argument(
        "--chunk-test-seconds",
        type=float,
        default=0.0,
        help="If >0 and --test-dbs is set, rebuild test set as audio/LMA chunks of this duration (seconds).",
    )
    ap.add_argument(
        "--chunk-test-hop-seconds",
        type=float,
        default=0.0,
        help="Chunk hop for test chunking (seconds). Default: same as --chunk-test-seconds.",
    )
    ap.add_argument(
        "--chunk-test-sr",
        type=int,
        default=32000,
        help="Sample rate used for chunked audio target extraction.",
    )
    ap.add_argument(
        "--chunk-test-min-lma-rows",
        type=int,
        default=4,
        help="Minimum LMA rows required for a chunk to be kept.",
    )
    ap.add_argument(
        "--chunk-test-max-per-clip",
        type=int,
        default=0,
        help="If >0, keep at most this many test chunks per clip (uniformly over time).",
    )
    ap.add_argument(
        "--target-profile",
        type=str,
        default="all",
        help="Y-target profile: all, rhythm_energy, or rhythm_core.",
    )
    ap.add_argument(
        "--include-targets",
        type=str,
        default="",
        help="Optional comma-separated Y target allowlist applied before excludes.",
    )
    ap.add_argument(
        "--exclude-targets",
        type=str,
        default="",
        help="Comma-separated Y target columns to remove from training/eval (e.g. audio_duration_s,audio_beat_count).",
    )
    ap.add_argument(
        "--exclude-target-suffixes",
        type=str,
        default="",
        help="Comma-separated suffixes to drop from Y targets (e.g. _min,_max).",
    )
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    test_dbs = _parse_db_list(args.test_dbs)
    split, X_cols, Y_cols = _load_xy(
        dataset_dir,
        test_dbs=test_dbs,
        test_size=args.test_size,
        seed=args.seed,
        test_db_fraction=float(args.test_db_fraction),
    )
    Xtr, Xte, Ytr, Yte = split["Xtr"], split["Xte"], split["Ytr"], split["Yte"]
    db_tr, db_te = split["db_tr"], split["db_te"]
    stem_tr, stem_te = split["stem_tr"], split["stem_te"]
    chunked_train_info = None
    chunked_test_info = None
    include_targets = _parse_csv_list(args.include_targets)
    target_profile = (args.target_profile or "all").strip().lower()
    profile_targets = _targets_from_profile(Y_cols, target_profile)
    excluded_targets = _parse_csv_list(args.exclude_targets)
    excluded_suffixes = _parse_csv_list(args.exclude_target_suffixes)

    if include_targets or target_profile != "all" or excluded_targets or excluded_suffixes:
        keep = []
        for c in Y_cols:
            allow = True
            if include_targets:
                allow = c in include_targets
            if allow and target_profile != "all":
                allow = c in profile_targets
            drop = (not allow) or (c in excluded_targets)
            if not drop and excluded_suffixes:
                drop = any(c.endswith(sfx) for sfx in excluded_suffixes)
            keep.append(not drop)
        keep = np.array(keep, dtype=bool)
        if not np.any(keep):
            raise RuntimeError(
                "All targets were filtered out. Adjust --target-profile/--include-targets/"
                "--exclude-targets/--exclude-target-suffixes."
            )
        Y_cols = [c for c, k in zip(Y_cols, keep) if k]
        Ytr = Ytr[:, keep]
        Yte = Yte[:, keep]

    if args.chunk_train_seconds > 0:
        train_dbs = sorted(set(db_tr.tolist()))
        Xtr, Ytr, db_tr, used_clips, used_chunks = _build_chunked_set(
            dataset_dir=dataset_dir,
            dbs=train_dbs,
            x_cols=X_cols,
            y_cols=Y_cols,
            chunk_seconds=float(args.chunk_train_seconds),
            hop_seconds=float(args.chunk_train_hop_seconds),
            chunk_sr=int(args.chunk_train_sr),
            min_lma_rows=int(args.chunk_train_min_lma_rows),
            max_chunks_per_clip=int(args.chunk_train_max_per_clip),
            allowed_stems=set(stem_tr.tolist()),
        )
        chunked_train_info = {
            "seconds": float(args.chunk_train_seconds),
            "hop_seconds": float(args.chunk_train_hop_seconds) if args.chunk_train_hop_seconds > 0 else float(args.chunk_train_seconds),
            "sr": int(args.chunk_train_sr),
            "max_per_clip": int(args.chunk_train_max_per_clip),
            "used_clips": int(used_clips),
            "used_chunks": int(used_chunks),
        }

    if args.chunk_test_seconds > 0:
        if not test_dbs:
            raise RuntimeError("--chunk-test-seconds requires --test-dbs.")
        Xte, Yte, db_te, used_clips, used_chunks = _build_chunked_set(
            dataset_dir=dataset_dir,
            dbs=test_dbs,
            x_cols=X_cols,
            y_cols=Y_cols,
            chunk_seconds=float(args.chunk_test_seconds),
            hop_seconds=float(args.chunk_test_hop_seconds),
            chunk_sr=int(args.chunk_test_sr),
            min_lma_rows=int(args.chunk_test_min_lma_rows),
            max_chunks_per_clip=int(args.chunk_test_max_per_clip),
            allowed_stems=set(stem_te.tolist()),
        )
        chunked_test_info = {
            "seconds": float(args.chunk_test_seconds),
            "hop_seconds": float(args.chunk_test_hop_seconds) if args.chunk_test_hop_seconds > 0 else float(args.chunk_test_seconds),
            "sr": int(args.chunk_test_sr),
            "max_per_clip": int(args.chunk_test_max_per_clip),
            "used_clips": int(used_clips),
            "used_chunks": int(used_chunks),
        }

    if args.model == "ridge":
        from sklearn.linear_model import Ridge
        base = Ridge(alpha=1.0, random_state=args.seed)
        model = Pipeline([
            ("scaler", StandardScaler(with_mean=True, with_std=True)),
            ("reg", MultiOutputRegressor(base))
        ])
    else:
        if args.model == "rf":
            from sklearn.ensemble import RandomForestRegressor
            base = RandomForestRegressor(
                n_estimators=300,
                random_state=args.seed,
                n_jobs=-1,
                max_depth=None,
            )
            model = MultiOutputRegressor(base)
        else:
            from sklearn.neural_network import MLPRegressor
            from sklearn.compose import TransformedTargetRegressor
            model = Pipeline([
                ("scaler", StandardScaler(with_mean=True, with_std=True)),
                ("reg", TransformedTargetRegressor(
                    regressor=MLPRegressor(
                        hidden_layer_sizes=(256, 128),
                        activation="relu",
                        solver="adam",
                        alpha=1e-4,
                        learning_rate_init=1e-3,
                        max_iter=600,
                        early_stopping=True,
                        validation_fraction=0.1,
                        n_iter_no_change=20,
                        random_state=args.seed,
                    ),
                    transformer=StandardScaler(with_mean=True, with_std=True),
                )),
            ])

    model.fit(Xtr, Ytr)
    pred = model.predict(Xte)

    mae = float(mean_absolute_error(Yte, pred))
    r2_stats = _compute_r2_stats(Yte, pred, Y_cols)
    r2_mean = r2_stats["r2_mean"]

    # Baseline: predict train mean for every target.
    baseline = np.tile(np.mean(Ytr, axis=0, keepdims=True), (Yte.shape[0], 1))
    baseline_mae = float(mean_absolute_error(Yte, baseline))
    baseline_r2_stats = _compute_r2_stats(Yte, baseline, Y_cols)

    # Standardized MAE: average absolute error in train-std units.
    y_std = np.std(Ytr, axis=0)
    y_std = np.where(y_std < 1e-8, np.nan, y_std)
    model_smae = float(np.nanmean(np.abs((Yte - pred) / y_std)))
    baseline_smae = float(np.nanmean(np.abs((Yte - baseline) / y_std)))

    out_models = dataset_dir / "models"
    out_reports = dataset_dir / "reports"
    out_models.mkdir(parents=True, exist_ok=True)
    out_reports.mkdir(parents=True, exist_ok=True)

    import joblib
    out_model_path = out_models / f"motion2audio_{args.model}.joblib"
    joblib.dump({
        "model": model,
        "X_cols": X_cols,
        "Y_cols": Y_cols,
        "seed": args.seed,
        "test_size": args.test_size,
        "test_dbs": test_dbs,
        "test_db_fraction": float(args.test_db_fraction),
        "exclude_targets": excluded_targets,
        "exclude_target_suffixes": excluded_suffixes,
        "target_profile": target_profile,
        "include_targets": include_targets,
        "chunk_train_seconds": float(args.chunk_train_seconds),
        "chunk_train_hop_seconds": float(args.chunk_train_hop_seconds),
        "chunk_train_sr": int(args.chunk_train_sr),
        "chunk_train_min_lma_rows": int(args.chunk_train_min_lma_rows),
        "chunk_train_max_per_clip": int(args.chunk_train_max_per_clip),
        "chunk_test_seconds": float(args.chunk_test_seconds),
        "chunk_test_hop_seconds": float(args.chunk_test_hop_seconds),
        "chunk_test_sr": int(args.chunk_test_sr),
        "chunk_test_min_lma_rows": int(args.chunk_test_min_lma_rows),
        "chunk_test_max_per_clip": int(args.chunk_test_max_per_clip),
    }, out_model_path)

    train_db_counts = pd.Series(db_tr).value_counts().to_dict()
    test_db_counts = pd.Series(db_te).value_counts().to_dict()
    train_stem_count = int(len(np.unique(stem_tr)))
    test_stem_count = int(len(np.unique(stem_te)))
    split_mode = f"db-holdout ({','.join(test_dbs)})" if test_dbs else f"random test_size={args.test_size}"
    if test_dbs and args.test_db_fraction < 1.0:
        split_mode += f" fraction={args.test_db_fraction:.3f}"
    if chunked_train_info is not None:
        split_mode += f" + chunked_train({chunked_train_info['seconds']}s)"
    if chunked_test_info is not None:
        split_mode += f" + chunked_test({chunked_test_info['seconds']}s)"
    worst_targets = sorted(r2_stats["rows"], key=lambda r: r["r2"])[:8]
    worst_txt = ", ".join([f"{w['target']}:{w['r2']:.3f}" for w in worst_targets])
    chunk_txt = ""
    if chunked_train_info is not None:
        chunk_txt += (
            f"chunk_train_seconds={chunked_train_info['seconds']}\n"
            f"chunk_train_hop_seconds={chunked_train_info['hop_seconds']}\n"
            f"chunk_train_sr={chunked_train_info['sr']}\n"
            f"chunk_train_max_per_clip={chunked_train_info['max_per_clip']}\n"
            f"chunk_train_used_clips={chunked_train_info['used_clips']}\n"
            f"chunk_train_used_chunks={chunked_train_info['used_chunks']}\n"
        )
    if chunked_test_info is not None:
        chunk_txt = (
            f"{chunk_txt}"
            f"chunk_test_seconds={chunked_test_info['seconds']}\n"
            f"chunk_test_hop_seconds={chunked_test_info['hop_seconds']}\n"
            f"chunk_test_sr={chunked_test_info['sr']}\n"
            f"chunk_test_max_per_clip={chunked_test_info['max_per_clip']}\n"
            f"chunk_test_used_clips={chunked_test_info['used_clips']}\n"
            f"chunk_test_used_chunks={chunked_test_info['used_chunks']}\n"
        )
    target_filter_txt = ""
    if include_targets or target_profile != "all" or excluded_targets or excluded_suffixes:
        target_filter_txt = (
            f"target_profile={target_profile}\n"
            f"include_targets={include_targets}\n"
            f"exclude_targets={excluded_targets}\n"
            f"exclude_target_suffixes={excluded_suffixes}\n"
        )

    report = (
        f"rows={Xtr.shape[0] + Xte.shape[0]}  X_dim={Xtr.shape[1]}  Y_dim={Ytr.shape[1]}\n"
        f"split={split_mode}\n"
        f"train_rows={Xtr.shape[0]} test_rows={Xte.shape[0]}\n"
        f"train_db_counts={train_db_counts}\n"
        f"test_db_counts={test_db_counts}\n"
        f"train_unique_stems={train_stem_count} test_unique_stems={test_stem_count}\n"
        f"model={args.model}\n"
        f"MAE(mean over all targets)={mae:.6f}\n"
        f"R2(mean over targets)={r2_mean:.6f}\n"
        f"R2(median over targets)={r2_stats['r2_median']:.6f}\n"
        f"R2(p10/p90)=({r2_stats['r2_p10']:.6f},{r2_stats['r2_p90']:.6f})\n"
        f"R2(positive targets)={r2_stats['r2_positive']}/{len(Y_cols)}\n"
        f"R2(low-variance targets in test)={r2_stats['low_var_count']}\n"
        f"Baseline_MAE(train-mean predictor)={baseline_mae:.6f}\n"
        f"Baseline_R2_mean(train-mean predictor)={baseline_r2_stats['r2_mean']:.6f}\n"
        f"Std_MAE(train-std units): model={model_smae:.6f} baseline={baseline_smae:.6f}\n"
        f"{target_filter_txt}"
        f"{chunk_txt}"
        f"Worst_R2_targets={worst_txt}\n"
    )
    (out_reports / "train_report.txt").write_text(report, encoding="utf-8")
    print("[done] saved:", out_model_path)
    print(report)

if __name__ == "__main__":
    main()
