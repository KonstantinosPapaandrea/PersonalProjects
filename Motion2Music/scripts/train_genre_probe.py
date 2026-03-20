#!/usr/bin/env python3
"""
train_genre_probe.py

Quick probe:
1) CLAP embedding -> genre code
2) Motion features -> same genre code

Genre labels are parsed from audio filename tokens like gBR_ / gPO_.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def _load_clap_npz(path: Path) -> tuple[np.ndarray, np.ndarray]:
    z = np.load(path, allow_pickle=True)
    ids = np.array([str(x) for x in z["ids"]], dtype=object)
    emb = np.asarray(z["emb"], dtype=np.float32)
    return ids, emb


def _parse_genre_from_audio_path(p: str) -> str | None:
    m = re.search(r"(g[A-Z]{2})_", str(p))
    if not m:
        return None
    return m.group(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--clap-npz", default="")
    ap.add_argument("--min-class-count", type=int, default=100)
    ap.add_argument("--test-size", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--save-models", action="store_true")
    ap.add_argument("--out-report", default="")
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    reports_dir = dataset_dir / "reports"
    models_dir = dataset_dir / "models"
    reports_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    out_report = Path(args.out_report) if args.out_report else (reports_dir / "train_report_genre_probe.txt")
    clap_npz = Path(args.clap_npz) if args.clap_npz else (dataset_dir / "clap_audio_emb.npz")

    mp = dataset_dir / "meta.csv"
    xp = dataset_dir / "X_motion.csv"
    if not mp.exists() or not xp.exists() or not clap_npz.exists():
        raise FileNotFoundError("Need meta.csv, X_motion.csv, and clap_audio_emb.npz")

    meta = pd.read_csv(mp)
    xdf = pd.read_csv(xp)
    if len(meta) != len(xdf):
        raise RuntimeError(f"X/meta row mismatch: {len(xdf)} vs {len(meta)}")

    clap_ids, clap_emb = _load_clap_npz(clap_npz)
    id2j = {k: i for i, k in enumerate(clap_ids.tolist())}

    labels = np.array([_parse_genre_from_audio_path(p) for p in meta["audio_path"].astype(str)], dtype=object)
    clip_ids = meta["clip_id"].astype(str).to_numpy()

    rows = []
    for i, cid in enumerate(clip_ids):
        j = id2j.get(cid)
        y = labels[i]
        if j is None or y is None:
            continue
        rows.append((i, j, y))
    if not rows:
        raise RuntimeError("No aligned rows with genre labels found.")

    I = np.array([a for a, b, y in rows], dtype=int)
    J = np.array([b for a, b, y in rows], dtype=int)
    y_all = np.array([y for a, b, y in rows], dtype=object)

    vc = pd.Series(y_all).value_counts()
    keep = set(vc[vc >= int(args.min_class_count)].index.tolist())
    keep_mask = np.array([yy in keep for yy in y_all], dtype=bool)

    X_motion = xdf.iloc[I].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)[keep_mask]
    X_clap = clap_emb[J][keep_mask]
    y = y_all[keep_mask]

    if len(np.unique(y)) < 2:
        raise RuntimeError("Not enough classes after filtering.")

    idx = np.arange(len(y), dtype=int)
    idx_tr, idx_te = train_test_split(
        idx,
        test_size=float(np.clip(args.test_size, 0.05, 0.50)),
        random_state=int(args.seed),
        stratify=y,
    )
    ytr, yte = y[idx_tr], y[idx_te]

    m_motion = Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=5000))])
    m_clap = Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=5000))])

    m_motion.fit(X_motion[idx_tr], ytr)
    m_clap.fit(X_clap[idx_tr], ytr)

    p_motion = m_motion.predict(X_motion[idx_te])
    p_clap = m_clap.predict(X_clap[idx_te])

    motion_acc = float(accuracy_score(yte, p_motion))
    motion_f1 = float(f1_score(yte, p_motion, average="macro"))
    clap_acc = float(accuracy_score(yte, p_clap))
    clap_f1 = float(f1_score(yte, p_clap, average="macro"))

    lines = [
        f"rows_aligned_labeled={len(y_all)}",
        f"rows_used={len(y)}",
        f"classes={sorted(np.unique(y).tolist())}",
        f"class_counts={pd.Series(y).value_counts().to_dict()}",
        f"seed={int(args.seed)}",
        f"test_size={float(args.test_size):.3f}",
        f"motion_acc={motion_acc:.6f}",
        f"motion_f1_macro={motion_f1:.6f}",
        f"clap_acc={clap_acc:.6f}",
        f"clap_f1_macro={clap_f1:.6f}",
    ]

    if args.save_models:
        out_motion = models_dir / "motion2genre_probe.joblib"
        out_clap = models_dir / "clap2genre_probe.joblib"
        joblib.dump({"model": m_motion, "classes": sorted(np.unique(y).tolist())}, out_motion)
        joblib.dump({"model": m_clap, "classes": sorted(np.unique(y).tolist())}, out_clap)
        lines.append(f"motion_model_path={out_motion}")
        lines.append(f"clap_model_path={out_clap}")

    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[done] report:", out_report)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
