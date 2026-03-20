#!/usr/bin/env python3
"""
build_clap_genre_split.py

Build a CLAP + genre dataset split from m2m outputs:
- align meta rows with CLAP embeddings via clip_id
- derive genre labels
- stratified per-genre train/test split
- save train/test npz + meta csv + report
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


GENRE_RE = re.compile(r"(g[A-Z]{2})_")


def _derive_genre(audio_path: str, db: str) -> str:
    p = str(audio_path)
    m = GENRE_RE.search(p)
    if m:
        return m.group(1)
    # Fallback for datasets without explicit gXX token (e.g., FineDance)
    d = str(db).strip()
    return d if d else "unknown"


def _stratified_indices(y: np.ndarray, test_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.RandomState(int(seed))
    train_idx: list[int] = []
    test_idx: list[int] = []
    y = np.asarray(y, dtype=object)

    for cls in sorted(np.unique(y).tolist()):
        idx = np.where(y == cls)[0]
        idx = idx.copy()
        rng.shuffle(idx)
        n = len(idx)
        if n <= 1:
            train_idx.extend(idx.tolist())
            continue
        n_test = int(round(float(test_fraction) * n))
        n_test = max(1, min(n - 1, n_test))
        test_idx.extend(idx[:n_test].tolist())
        train_idx.extend(idx[n_test:].tolist())

    return np.array(sorted(train_idx), dtype=int), np.array(sorted(test_idx), dtype=int)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True, help="Folder containing meta.csv and clap_audio_emb.npz.")
    ap.add_argument("--out-dir", default="", help="Output folder for split files.")
    ap.add_argument("--test-fraction", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    meta_path = dataset_dir / "meta.csv"
    clap_path = dataset_dir / "clap_audio_emb.npz"
    if not meta_path.exists() or not clap_path.exists():
        raise FileNotFoundError("dataset-dir must contain meta.csv and clap_audio_emb.npz")

    out_dir = Path(args.out_dir) if args.out_dir else (dataset_dir.parent / f"{dataset_dir.name}_clap_genre_split")
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = pd.read_csv(meta_path)
    z = np.load(clap_path, allow_pickle=True)
    clap_ids = np.array([str(x) for x in z["ids"]], dtype=object)
    clap_emb = np.asarray(z["emb"], dtype=np.float32)
    id2j = {k: i for i, k in enumerate(clap_ids.tolist())}

    # Align rows that exist in CLAP npz
    rows = []
    for i, r in enumerate(meta.itertuples(index=False)):
        cid = str(getattr(r, "clip_id"))
        j = id2j.get(cid)
        if j is None:
            continue
        db = str(getattr(r, "db", ""))
        audio_path = str(getattr(r, "audio_path", ""))
        genre = _derive_genre(audio_path=audio_path, db=db)
        rows.append((i, j, genre))

    if not rows:
        raise RuntimeError("No meta rows aligned with CLAP ids.")

    I = np.array([a for a, b, g in rows], dtype=int)
    J = np.array([b for a, b, g in rows], dtype=int)
    y = np.array([g for a, b, g in rows], dtype=object)

    aligned_meta = meta.iloc[I].copy().reset_index(drop=True)
    aligned_meta["genre"] = y
    X = clap_emb[J]
    clip_ids = aligned_meta["clip_id"].astype(str).to_numpy()

    tr_idx, te_idx = _stratified_indices(y=y, test_fraction=float(args.test_fraction), seed=int(args.seed))
    if len(tr_idx) == 0 or len(te_idx) == 0:
        raise RuntimeError("Split failed: empty train or test set.")

    # Save npz
    np.savez_compressed(
        out_dir / "clap_genre_train.npz",
        ids=clip_ids[tr_idx].astype(object),
        emb=X[tr_idx].astype(np.float32),
        genre=y[tr_idx].astype(object),
    )
    np.savez_compressed(
        out_dir / "clap_genre_test.npz",
        ids=clip_ids[te_idx].astype(object),
        emb=X[te_idx].astype(np.float32),
        genre=y[te_idx].astype(object),
    )

    # Save meta csvs
    aligned_meta.iloc[tr_idx].to_csv(out_dir / "meta_train.csv", index=False)
    aligned_meta.iloc[te_idx].to_csv(out_dir / "meta_test.csv", index=False)
    aligned_meta.to_csv(out_dir / "meta_all_aligned.csv", index=False)

    classes = sorted(np.unique(y).tolist())
    class_to_idx = {c: i for i, c in enumerate(classes)}
    (out_dir / "genre_label_map.json").write_text(json.dumps(class_to_idx, indent=2), encoding="utf-8")

    train_counts = pd.Series(y[tr_idx]).value_counts().to_dict()
    test_counts = pd.Series(y[te_idx]).value_counts().to_dict()
    all_counts = pd.Series(y).value_counts().to_dict()

    report = (
        f"dataset_dir={dataset_dir}\n"
        f"clap_npz={clap_path}\n"
        f"rows_meta={len(meta)}\n"
        f"rows_clap={len(clap_ids)}\n"
        f"rows_aligned={len(y)}\n"
        f"clap_dim={X.shape[1]}\n"
        f"num_genres={len(classes)}\n"
        f"genres={classes}\n"
        f"test_fraction={float(args.test_fraction):.3f}\n"
        f"seed={int(args.seed)}\n"
        f"train_rows={len(tr_idx)}\n"
        f"test_rows={len(te_idx)}\n"
        f"all_genre_counts={all_counts}\n"
        f"train_genre_counts={train_counts}\n"
        f"test_genre_counts={test_counts}\n"
        f"out_dir={out_dir}\n"
    )
    (out_dir / "split_report.txt").write_text(report, encoding="utf-8")

    print("[done] wrote split to:", out_dir)
    print(report)


if __name__ == "__main__":
    main()
