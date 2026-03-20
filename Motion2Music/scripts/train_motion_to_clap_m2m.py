#!/usr/bin/env python3
"""
train_motion_to_clap_m2m.py

Train a dedicated motion -> CLAP embedding model on the m2m dataset format.

Inputs:
  <dataset-dir>/X_motion.csv
  <dataset-dir>/meta.csv
  <dataset-dir>/clap_audio_emb.npz (ids=clip_id, emb=<N,D>)

Outputs:
  <dataset-dir>/models/motion2clap_ridge.joblib
  <dataset-dir>/reports/train_report_motion2clap.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def _parse_db_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _load_motion_with_meta(dataset_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    xp = dataset_dir / "X_motion.csv"
    mp = dataset_dir / "meta.csv"
    if not xp.exists():
        raise FileNotFoundError(f"Missing {xp}")
    if not mp.exists():
        raise FileNotFoundError(f"Missing {mp}")

    xdf = pd.read_csv(xp)
    meta = pd.read_csv(mp)
    if len(xdf) != len(meta):
        raise RuntimeError(f"X/meta row mismatch: {len(xdf)} vs {len(meta)}")

    out = xdf.copy()
    if "clip_id" not in out.columns and "clip_id" in meta.columns:
        out.insert(0, "clip_id", meta["clip_id"].to_numpy())
    if "db" in meta.columns:
        out["db"] = meta["db"].astype(str).to_numpy()
    else:
        out["db"] = "unknown"
    if "stem" in meta.columns:
        out["stem"] = meta["stem"].astype(str).to_numpy()
    else:
        out["stem"] = out["clip_id"].astype(str).to_numpy()

    x_cols = [c for c in out.columns if c not in ("clip_id", "db", "stem")]
    x_cols = [c for c in x_cols if pd.api.types.is_numeric_dtype(out[c])]
    if not x_cols:
        raise RuntimeError("No numeric X columns found.")
    return out, x_cols


def _load_clap_map(clap_npz: Path) -> dict[str, np.ndarray]:
    if not clap_npz.exists():
        raise FileNotFoundError(f"Missing {clap_npz}")
    z = np.load(clap_npz, allow_pickle=True)
    ids = z["ids"].astype(str)
    emb = z["emb"].astype(np.float32)
    return {ids[i]: emb[i] for i in range(len(ids))}


def _split_mask(db: np.ndarray, stem: np.ndarray, test_dbs: list[str], test_db_fraction: float, seed: int) -> np.ndarray:
    if not test_dbs:
        raise RuntimeError("Use --test-dbs for this trainer.")

    if test_db_fraction >= 1.0:
        return np.isin(db, test_dbs)

    rng = np.random.RandomState(seed)
    mask = np.zeros(len(db), dtype=bool)
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
        mask[idx] = np.isin(stem[idx], picked)
    return mask


def _l2n(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    return x / (n + eps)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--clap-npz", default="")
    ap.add_argument("--out-model", default="")
    ap.add_argument("--out-report", default="")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--alpha", type=float, default=10.0, help="Ridge alpha for motion->CLAP model.")
    ap.add_argument("--test-dbs", default="simonalexanderson")
    ap.add_argument("--test-db-fraction", type=float, default=1.0)
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    models_dir = dataset_dir / "models"
    reports_dir = dataset_dir / "reports"
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    out_model = Path(args.out_model) if args.out_model else (models_dir / "motion2clap_ridge.joblib")
    out_report = Path(args.out_report) if args.out_report else (reports_dir / "train_report_motion2clap.txt")
    clap_npz = Path(args.clap_npz) if args.clap_npz else (dataset_dir / "clap_audio_emb.npz")

    df, x_cols = _load_motion_with_meta(dataset_dir)
    clap_map = _load_clap_map(clap_npz)

    clip_ids = df["clip_id"].astype(str).to_numpy()
    has = np.array([cid in clap_map for cid in clip_ids], dtype=bool)
    if not np.any(has):
        raise RuntimeError("No rows aligned with CLAP ids.")

    x = df.loc[has, x_cols].to_numpy(dtype=np.float32)
    db = df.loc[has, "db"].astype(str).to_numpy()
    stem = df.loc[has, "stem"].astype(str).to_numpy()
    ids = df.loc[has, "clip_id"].astype(str).to_numpy()
    y = np.stack([clap_map[cid] for cid in ids], axis=0).astype(np.float32)

    test_dbs = _parse_db_list(args.test_dbs)
    mask_test = _split_mask(
        db=db,
        stem=stem,
        test_dbs=test_dbs,
        test_db_fraction=float(args.test_db_fraction),
        seed=int(args.seed),
    )
    if not np.any(mask_test):
        raise RuntimeError(f"No test rows for --test-dbs={test_dbs}")
    if np.all(mask_test):
        raise RuntimeError("All rows fall into test set.")

    xtr, xte = x[~mask_test], x[mask_test]
    ytr, yte = y[~mask_test], y[mask_test]
    dbtr, dbte = db[~mask_test], db[mask_test]

    model = Pipeline(
        [
            ("scaler", StandardScaler(with_mean=True, with_std=True)),
            ("reg", MultiOutputRegressor(Ridge(alpha=float(args.alpha), random_state=int(args.seed)))),
        ]
    )
    model.fit(xtr, ytr)
    yhat = model.predict(xte).astype(np.float32)

    yhat_n = _l2n(yhat)
    yte_n = _l2n(yte)
    cos_diag = np.sum(yhat_n * yte_n, axis=1)
    cos_mean = float(np.mean(cos_diag))
    cos_med = float(np.median(cos_diag))

    sim = yhat_n @ yte_n.T
    top1 = np.argmax(sim, axis=1)
    gt = np.arange(sim.shape[0], dtype=int)
    top1_acc = float(np.mean(top1 == gt))
    k = int(min(5, sim.shape[1]))
    topk = np.argpartition(-sim, kth=np.arange(k), axis=1)[:, :k]
    top5_acc = float(np.mean([gt[i] in topk[i] for i in range(len(gt))]))

    l2 = float(np.mean(np.linalg.norm(yhat - yte, axis=1)))

    payload = {
        "bundle_type": "motion2clap_bundle_v1",
        "model": model,
        "x_cols": x_cols,
        "emb_dim": int(y.shape[1]),
        "seed": int(args.seed),
        "alpha": float(args.alpha),
        "test_dbs": test_dbs,
        "test_db_fraction": float(args.test_db_fraction),
        "metrics": {
            "cosine_mean": cos_mean,
            "cosine_median": cos_med,
            "retrieval_top1_acc": top1_acc,
            "retrieval_top5_acc": top5_acc,
            "l2_mean": l2,
        },
    }
    joblib.dump(payload, out_model)

    report = (
        f"rows={len(x)} X_dim={x.shape[1]} CLAP_dim={y.shape[1]}\n"
        f"split=db-holdout ({','.join(test_dbs)}) fraction={float(args.test_db_fraction):.3f}\n"
        f"train_rows={len(xtr)} test_rows={len(xte)}\n"
        f"train_db_counts={pd.Series(dbtr).value_counts().to_dict()}\n"
        f"test_db_counts={pd.Series(dbte).value_counts().to_dict()}\n"
        f"model=ridge alpha={float(args.alpha)}\n"
        f"cosine_mean={cos_mean:.6f}\n"
        f"cosine_median={cos_med:.6f}\n"
        f"retrieval_top1_acc={top1_acc:.6f}\n"
        f"retrieval_top5_acc={top5_acc:.6f}\n"
        f"l2_mean={l2:.6f}\n"
        f"model_path={out_model}\n"
        f"clap_npz={clap_npz}\n"
    )
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(report, encoding="utf-8")
    print("[done] saved model:", out_model)
    print("[done] saved report:", out_report)
    print(report)


if __name__ == "__main__":
    main()
