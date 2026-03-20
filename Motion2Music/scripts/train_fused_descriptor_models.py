#!/usr/bin/env python3
"""
train_fused_descriptor_models.py

Train a fused descriptor system:
1) motion -> descriptor
2) motion -> CLAP embedding
3) CLAP embedding -> descriptor
4) fused prediction = w * (motion->descriptor) + (1-w) * (clap->descriptor(motion->clap))

This script is designed for the current m2m dataset layout:
  <dataset-dir>/X_motion.csv
  <dataset-dir>/Y_audio.csv
  <dataset-dir>/meta.csv

Outputs:
  <dataset-dir>/models/fused_motion_audio.joblib
  <dataset-dir>/reports/train_report_fusion.txt
  <dataset-dir>/clap_audio_emb.npz
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import joblib


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

TEMPO_PRIORITY_COLS = {"audio_tempo_bpm", "audio_beat_count"}


def _parse_db_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _parse_csv_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _resolve_ids(df: pd.DataFrame, meta: pd.DataFrame, preferred_col: str) -> tuple[pd.DataFrame, str]:
    if preferred_col in df.columns:
        return df, preferred_col

    if len(df) == len(meta) and "clip_id" in meta.columns:
        out = df.copy()
        out.insert(0, "clip_id", meta["clip_id"].to_numpy())
        return out, "clip_id"

    return df, df.columns[0]


def _is_aux_col(col: str, id_col: str) -> bool:
    cl = col.lower()
    if cl == id_col.lower() or cl in ("db", "stem", "clip_id") or cl.startswith("clip_id_"):
        return True
    if cl == "audio_path" or cl.startswith("audio_path_"):
        return True
    return False


def _targets_from_profile(y_cols: list[str], profile: str) -> set[str]:
    p = (profile or "").strip().lower()
    if p in ("", "all"):
        return set(y_cols)
    if p == "rhythm_energy":
        return {c for c in y_cols if c in RHYTHM_ENERGY_TARGETS}
    if p == "rhythm_core":
        return {c for c in y_cols if c in RHYTHM_CORE_TARGETS}
    raise ValueError(f"Unknown target profile: {profile}")


def _load_joint_df(dataset_dir: Path) -> tuple[pd.DataFrame, list[str], list[str]]:
    xp = dataset_dir / "X_motion.csv"
    yp = dataset_dir / "Y_audio.csv"
    mp = dataset_dir / "meta.csv"
    if not xp.exists():
        raise FileNotFoundError(f"Missing {xp}")
    if not yp.exists():
        raise FileNotFoundError(f"Missing {yp}")
    if not mp.exists():
        raise FileNotFoundError(f"Missing {mp}")

    xdf = pd.read_csv(xp)
    ydf = pd.read_csv(yp)
    meta = pd.read_csv(mp)

    xdf, xid = _resolve_ids(xdf, meta, "clip_id")
    ydf, yid = _resolve_ids(ydf, meta, "clip_id")

    if "clip_id" in meta.columns and "db" in meta.columns:
        cols = ["clip_id", "db"]
        if "stem" in meta.columns:
            cols.append("stem")
        if "audio_path" in meta.columns:
            cols.append("audio_path")
        m = meta[cols].copy()
        m["clip_id"] = m["clip_id"].astype(str)
        xdf[xid] = xdf[xid].astype(str)
        ydf[yid] = ydf[yid].astype(str)
        xdf = xdf.merge(m, left_on=xid, right_on="clip_id", how="left")
        ydf = ydf.merge(m, left_on=yid, right_on="clip_id", how="left")
        if xid != "clip_id":
            xdf = xdf.drop(columns=["clip_id"])
        if yid != "clip_id":
            ydf = ydf.drop(columns=["clip_id"])
    else:
        xdf["db"] = "unknown"
        ydf["db"] = "unknown"

    df = xdf.merge(ydf, left_on=xid, right_on=yid, how="inner", suffixes=("", "_y"))
    if df.empty:
        raise RuntimeError("No aligned rows between X_motion.csv and Y_audio.csv.")

    x_candidates = [c for c in xdf.columns if not _is_aux_col(c, xid)]
    x_num = df[x_candidates].select_dtypes(include=[np.number]).fillna(0.0)
    x_cols = x_num.columns.to_list()
    for c in x_cols:
        df[c] = x_num[c]

    y_candidates = [c for c in ydf.columns if not _is_aux_col(c, yid)]
    y_num = df[y_candidates].select_dtypes(include=[np.number]).fillna(0.0)
    y_cols = y_num.columns.to_list()
    for c in y_cols:
        df[c] = y_num[c]

    if "clip_id" not in df.columns:
        df["clip_id"] = df[xid].astype(str)
    else:
        df["clip_id"] = df["clip_id"].astype(str)
    if "db" not in df.columns:
        df["db"] = "unknown"
    if "stem" not in df.columns:
        df["stem"] = df[xid].astype(str)
    if "audio_path" not in df.columns:
        raise RuntimeError("audio_path missing in merged dataframe; cannot compute CLAP embeddings.")

    return df, x_cols, y_cols


def _compute_clap_embeddings(df: pd.DataFrame, clip_ids: np.ndarray, out_npz: Path, sr: int, max_seconds: float, batch: int, force: bool) -> dict[str, np.ndarray]:
    if out_npz.exists() and not force:
        z = np.load(out_npz, allow_pickle=True)
        ids = z["ids"].astype(str)
        emb = z["emb"].astype(np.float32)
        return {cid: emb[i] for i, cid in enumerate(ids)}

    try:
        import torch
        import librosa
        import laion_clap
    except Exception as e:
        raise RuntimeError(
            "CLAP dependencies are missing in current env. Install librosa + laion_clap + torch."
        ) from e

    row_by_id = {str(r.clip_id): str(r.audio_path) for r in df.itertuples(index=False)}
    use_ids = [str(cid) for cid in clip_ids if str(cid) in row_by_id]
    if not use_ids:
        raise RuntimeError("No clip ids available for CLAP embedding.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    clap_model = laion_clap.CLAP_Module(enable_fusion=False, device=device)
    clap_model.load_ckpt()

    ids: list[str] = []
    embs: list[np.ndarray] = []
    buf_audio: list[np.ndarray] = []
    buf_ids: list[str] = []

    def flush():
        if not buf_audio:
            return
        with torch.no_grad():
            e = clap_model.get_audio_embedding_from_data(x=buf_audio, use_tensor=False)
        e = np.asarray(e, dtype=np.float32)
        n = np.linalg.norm(e, axis=1, keepdims=True)
        e = e / (n + 1e-12)
        ids.extend(buf_ids)
        embs.append(e)
        buf_audio.clear()
        buf_ids.clear()

    for cid in use_ids:
        ap = Path(row_by_id[cid])
        if not ap.exists():
            continue
        y, _ = librosa.load(str(ap), sr=sr, mono=True)
        if max_seconds > 0:
            y = y[: int(sr * max_seconds)]
        if y.size == 0:
            continue
        buf_audio.append(y.astype(np.float32))
        buf_ids.append(cid)
        if len(buf_audio) >= int(max(1, batch)):
            flush()
    flush()

    if not embs:
        raise RuntimeError("CLAP embedding extraction produced zero rows.")

    E = np.vstack(embs).astype(np.float32)
    out_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_npz, ids=np.array(ids), emb=E)
    return {cid: E[i] for i, cid in enumerate(ids)}


def _split_mask(db: np.ndarray, stem: np.ndarray, test_dbs: list[str], test_db_fraction: float, seed: int) -> np.ndarray:
    if not test_dbs:
        raise ValueError("test_dbs must not be empty for this script.")

    if test_db_fraction >= 1.0:
        return np.isin(db, test_dbs)

    rng = np.random.RandomState(seed)
    mask_test = np.zeros(len(db), dtype=bool)
    for db_name in test_dbs:
        idx = np.where(db == db_name)[0]
        if idx.size == 0:
            continue
        groups = np.unique(stem[idx])
        if groups.size == 0:
            continue
        n_test = int(round(groups.size * float(test_db_fraction)))
        n_test = max(1, min(groups.size, n_test))
        picked = rng.choice(groups, size=n_test, replace=False)
        mask_test[idx] = np.isin(stem[idx], picked)
    return mask_test


def _r2_stats(y_true: np.ndarray, y_pred: np.ndarray, cols: list[str]) -> dict:
    vals = []
    for j, c in enumerate(cols):
        try:
            vals.append(float(r2_score(y_true[:, j], y_pred[:, j])))
        except Exception:
            vals.append(float("nan"))
    arr = np.array(vals, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {"mean": float("nan"), "median": float("nan"), "positive": 0}
    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "positive": int(np.sum(arr > 0)),
    }


def _make_ridge(alpha: float, seed: int) -> Pipeline:
    base = Ridge(alpha=alpha, random_state=seed)
    return Pipeline(
        [
            ("scaler", StandardScaler(with_mean=True, with_std=True)),
            ("reg", MultiOutputRegressor(base)),
        ]
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--out-model", default="")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-dbs", type=str, default="simonalexanderson")
    ap.add_argument("--test-db-fraction", type=float, default=1.0)
    ap.add_argument("--target-profile", type=str, default="rhythm_energy")
    ap.add_argument("--include-targets", type=str, default="")
    ap.add_argument("--exclude-targets", type=str, default="audio_duration_s")
    ap.add_argument("--exclude-target-suffixes", type=str, default="_min,_max")
    ap.add_argument("--fusion-alpha", type=float, default=0.65, help="Default blend weight for motion->descriptor.")
    ap.add_argument("--fusion-tempo-alpha", type=float, default=0.90, help="Blend weight for tempo/beat descriptor cols.")
    ap.add_argument("--clap-npz", type=str, default="", help="Optional path to cache/load CLAP embeddings npz.")
    ap.add_argument("--clap-force-recompute", action="store_true")
    ap.add_argument("--clap-sr", type=int, default=48000)
    ap.add_argument("--clap-max-seconds", type=float, default=30.0)
    ap.add_argument("--clap-batch", type=int, default=8)
    ap.add_argument("--alpha-motion2desc", type=float, default=1.0)
    ap.add_argument("--alpha-motion2clap", type=float, default=10.0)
    ap.add_argument("--alpha-clap2desc", type=float, default=1.0)
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    models_dir = dataset_dir / "models"
    reports_dir = dataset_dir / "reports"
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    out_model = Path(args.out_model) if args.out_model else (models_dir / "fused_motion_audio.joblib")
    clap_npz = Path(args.clap_npz) if args.clap_npz else (dataset_dir / "clap_audio_emb.npz")

    test_dbs = _parse_db_list(args.test_dbs)
    include_targets = _parse_csv_list(args.include_targets)
    exclude_targets = _parse_csv_list(args.exclude_targets)
    exclude_suffixes = _parse_csv_list(args.exclude_target_suffixes)

    df, x_cols, y_cols_all = _load_joint_df(dataset_dir)
    y_allowed = _targets_from_profile(y_cols_all, args.target_profile)
    y_cols = []
    for c in y_cols_all:
        keep = True
        if include_targets:
            keep = c in include_targets
        if keep:
            keep = c in y_allowed
        if keep and c in exclude_targets:
            keep = False
        if keep and exclude_suffixes:
            keep = not any(c.endswith(sfx) for sfx in exclude_suffixes)
        if keep:
            y_cols.append(c)
    if not y_cols:
        raise RuntimeError("No target columns left after filters.")

    db = df["db"].astype(str).to_numpy()
    stem = df["stem"].astype(str).to_numpy()
    clip_ids = df["clip_id"].astype(str).to_numpy()
    x = df[x_cols].to_numpy(dtype=np.float32)
    y = df[y_cols].to_numpy(dtype=np.float32)

    emb_map = _compute_clap_embeddings(
        df=df,
        clip_ids=clip_ids,
        out_npz=clap_npz,
        sr=int(args.clap_sr),
        max_seconds=float(args.clap_max_seconds),
        batch=int(args.clap_batch),
        force=bool(args.clap_force_recompute),
    )

    has_emb = np.array([cid in emb_map for cid in clip_ids], dtype=bool)
    if not np.any(has_emb):
        raise RuntimeError("No rows matched CLAP embeddings.")
    x = x[has_emb]
    y = y[has_emb]
    db = db[has_emb]
    stem = stem[has_emb]
    clip_ids = clip_ids[has_emb]
    e = np.stack([emb_map[cid] for cid in clip_ids], axis=0).astype(np.float32)

    mask_test = _split_mask(
        db=db,
        stem=stem,
        test_dbs=test_dbs,
        test_db_fraction=float(args.test_db_fraction),
        seed=int(args.seed),
    )
    if not np.any(mask_test):
        raise RuntimeError(f"No test rows for dbs={test_dbs}.")
    if np.all(mask_test):
        raise RuntimeError("All rows are in test set.")

    xtr, xte = x[~mask_test], x[mask_test]
    ytr, yte = y[~mask_test], y[mask_test]
    etr, ete = e[~mask_test], e[mask_test]
    dbtr, dbte = db[~mask_test], db[mask_test]

    m2d = _make_ridge(alpha=float(args.alpha_motion2desc), seed=int(args.seed))
    m2c = _make_ridge(alpha=float(args.alpha_motion2clap), seed=int(args.seed))
    c2d = _make_ridge(alpha=float(args.alpha_clap2desc), seed=int(args.seed))

    m2d.fit(xtr, ytr)
    m2c.fit(xtr, etr)
    c2d.fit(etr, ytr)

    y_motion = m2d.predict(xte)
    e_pred = m2c.predict(xte)
    y_from_clap = c2d.predict(e_pred)

    alpha_default = float(np.clip(args.fusion_alpha, 0.0, 1.0))
    alpha_tempo = float(np.clip(args.fusion_tempo_alpha, 0.0, 1.0))
    per_col_alpha = {c: (alpha_tempo if c in TEMPO_PRIORITY_COLS else alpha_default) for c in y_cols}

    y_fused = np.zeros_like(y_motion, dtype=np.float32)
    for j, c in enumerate(y_cols):
        a = float(per_col_alpha[c])
        y_fused[:, j] = (a * y_motion[:, j]) + ((1.0 - a) * y_from_clap[:, j])

    def _metric_block(name: str, yp: np.ndarray) -> dict:
        mae = float(mean_absolute_error(yte, yp))
        r2 = _r2_stats(yte, yp, y_cols)
        return {"name": name, "mae": mae, "r2_mean": r2["mean"], "r2_median": r2["median"], "r2_positive": r2["positive"]}

    motion_metrics = _metric_block("motion_only", y_motion)
    fused_metrics = _metric_block("fused", y_fused)
    baseline = np.tile(np.mean(ytr, axis=0, keepdims=True), (yte.shape[0], 1))
    baseline_metrics = _metric_block("train_mean_baseline", baseline)

    bundle = {
        "bundle_type": "fused_descriptor_bundle_v1",
        "seed": int(args.seed),
        "target_profile": args.target_profile,
        "x_cols": x_cols,
        "y_cols": y_cols,
        "test_dbs": test_dbs,
        "test_db_fraction": float(args.test_db_fraction),
        "motion2desc": m2d,
        "motion2clap": m2c,
        "clap2desc": c2d,
        "clap_npz": str(clap_npz),
        "clap_dim": int(e.shape[1]),
        "fusion_alpha_default": alpha_default,
        "fusion_alpha_tempo": alpha_tempo,
        "fusion_per_col_alpha": per_col_alpha,
        "tempo_priority_cols": sorted(TEMPO_PRIORITY_COLS),
        "metrics": {
            "motion_only": motion_metrics,
            "fused": fused_metrics,
            "baseline": baseline_metrics,
        },
    }
    joblib.dump(bundle, out_model)

    report = (
        f"rows={len(x)} X_dim={x.shape[1]} Y_dim={y.shape[1]} CLAP_dim={e.shape[1]}\n"
        f"split=db-holdout ({','.join(test_dbs)}) fraction={float(args.test_db_fraction):.3f}\n"
        f"train_rows={len(xtr)} test_rows={len(xte)}\n"
        f"train_db_counts={pd.Series(dbtr).value_counts().to_dict()}\n"
        f"test_db_counts={pd.Series(dbte).value_counts().to_dict()}\n"
        f"target_profile={args.target_profile}\n"
        f"targets={y_cols}\n"
        f"fusion_alpha_default={alpha_default}\n"
        f"fusion_alpha_tempo={alpha_tempo}\n"
        f"motion_only: MAE={motion_metrics['mae']:.6f} R2_mean={motion_metrics['r2_mean']:.6f} R2_median={motion_metrics['r2_median']:.6f} R2_positive={motion_metrics['r2_positive']}/{len(y_cols)}\n"
        f"fused: MAE={fused_metrics['mae']:.6f} R2_mean={fused_metrics['r2_mean']:.6f} R2_median={fused_metrics['r2_median']:.6f} R2_positive={fused_metrics['r2_positive']}/{len(y_cols)}\n"
        f"baseline: MAE={baseline_metrics['mae']:.6f} R2_mean={baseline_metrics['r2_mean']:.6f} R2_median={baseline_metrics['r2_median']:.6f} R2_positive={baseline_metrics['r2_positive']}/{len(y_cols)}\n"
        f"model_path={out_model}\n"
        f"clap_npz={clap_npz}\n"
    )
    (reports_dir / "train_report_fusion.txt").write_text(report, encoding="utf-8")
    print("[done] saved model:", out_model)
    print(report)


if __name__ == "__main__":
    main()

