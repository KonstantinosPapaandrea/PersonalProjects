#!/usr/bin/env python3
"""
train_motion_to_clap_pca_m2m.py

Train motion -> reduced CLAP (PCA components), then reconstruct to CLAP-512.
Useful for learning "important CLAP features" instead of regressing all 512 dims.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from train_motion_to_clap_m2m import _load_clap_map, _load_motion_with_meta, _parse_db_list, _split_mask


def _l2n(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    return x / (n + eps)


def _retrieval_topk(yhat: np.ndarray, ytrue: np.ndarray, k: int) -> float:
    if yhat.shape[0] == 0:
        return 0.0
    yh = _l2n(yhat)
    yt = _l2n(ytrue)
    sim = yh @ yt.T
    kk = int(min(max(1, k), sim.shape[1]))
    idx = np.arange(sim.shape[0], dtype=int)
    topk = np.argpartition(-sim, kth=np.arange(kk), axis=1)[:, :kk]
    return float(np.mean([idx[i] in topk[i] for i in range(len(idx))]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--clap-npz", default="")
    ap.add_argument("--out-model", default="")
    ap.add_argument("--out-report", default="")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--alpha", type=float, default=30.0, help="Ridge alpha for motion->CLAP_PCA model.")
    ap.add_argument("--pca-dim", type=int, default=64, help="Number of CLAP PCA components to predict.")
    ap.add_argument("--test-dbs", default="simonalexanderson")
    ap.add_argument("--test-db-fraction", type=float, default=1.0)
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    models_dir = dataset_dir / "models"
    reports_dir = dataset_dir / "reports"
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    pca_dim = int(args.pca_dim)
    out_model = Path(args.out_model) if args.out_model else (models_dir / f"motion2clap_pca{pca_dim}_ridge.joblib")
    out_report = Path(args.out_report) if args.out_report else (reports_dir / f"train_report_motion2clap_pca{pca_dim}.txt")
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
    y = np.stack([clap_map[cid] for cid in ids], axis=0).astype(np.float32)  # (N,512)

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

    pca = PCA(n_components=pca_dim, random_state=int(args.seed))
    ztr = pca.fit_transform(ytr)
    zte = pca.transform(yte)
    z_dim = int(ztr.shape[1])
    explained = float(np.sum(pca.explained_variance_ratio_))

    model = Pipeline(
        [
            ("scaler", StandardScaler(with_mean=True, with_std=True)),
            ("reg", MultiOutputRegressor(Ridge(alpha=float(args.alpha), random_state=int(args.seed)))),
        ]
    )
    model.fit(xtr, ztr.astype(np.float32))
    zhat = model.predict(xte).astype(np.float32)
    yhat = pca.inverse_transform(zhat).astype(np.float32)

    # Metrics in latent space
    mae_z = float(np.mean(np.abs(zhat - zte)))
    l2_z = float(np.mean(np.linalg.norm(zhat - zte, axis=1)))

    # Metrics in reconstructed CLAP-512 space
    yhat_n = _l2n(yhat)
    yte_n = _l2n(yte)
    cos_diag = np.sum(yhat_n * yte_n, axis=1)
    cos_mean = float(np.mean(cos_diag))
    cos_med = float(np.median(cos_diag))
    l2_full = float(np.mean(np.linalg.norm(yhat - yte, axis=1)))
    top1 = _retrieval_topk(yhat, yte, 1)
    top5 = _retrieval_topk(yhat, yte, 5)

    payload = {
        "bundle_type": "motion2clap_pca_bundle_v1",
        "model": model,
        "pca": pca,
        "x_cols": x_cols,
        "emb_dim": int(y.shape[1]),
        "pca_dim": z_dim,
        "pca_explained_variance_ratio_sum": explained,
        "seed": int(args.seed),
        "alpha": float(args.alpha),
        "test_dbs": test_dbs,
        "test_db_fraction": float(args.test_db_fraction),
        "metrics": {
            "latent_mae": mae_z,
            "latent_l2_mean": l2_z,
            "cosine_mean_recon": cos_mean,
            "cosine_median_recon": cos_med,
            "retrieval_top1_acc_recon": top1,
            "retrieval_top5_acc_recon": top5,
            "l2_mean_recon": l2_full,
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
        f"pca_dim={z_dim}\n"
        f"pca_explained_variance_ratio_sum={explained:.6f}\n"
        f"latent_mae={mae_z:.6f}\n"
        f"latent_l2_mean={l2_z:.6f}\n"
        f"cosine_mean_recon={cos_mean:.6f}\n"
        f"cosine_median_recon={cos_med:.6f}\n"
        f"retrieval_top1_acc_recon={top1:.6f}\n"
        f"retrieval_top5_acc_recon={top5:.6f}\n"
        f"l2_mean_recon={l2_full:.6f}\n"
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
