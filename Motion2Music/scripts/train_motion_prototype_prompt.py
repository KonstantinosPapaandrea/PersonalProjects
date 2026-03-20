#!/usr/bin/env python3
"""
train_motion_prototype_prompt.py

Final v2 trainer:
- Input: motion features (temporal LMA + beat-motion recommended)
- Target: CLAP audio prototypes (5s or 30s)
- Model: motion -> prototype classifier/ranker
- Output: bundle for top-k prototype-conditioned prompt inference
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, normalized_mutual_info_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import semantic_prompt_from_motion as sem
import tune_semantic_prompt_params as tuner


def _parse_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _root(stem: str) -> str:
    m = re.search(r"_ch(\d+)$", stem)
    return stem[: m.start()] if m else stem


def _split_test_mask(db: np.ndarray, stem: np.ndarray, test_dbs: list[str], frac: float, seed: int) -> np.ndarray:
    if not test_dbs:
        raise RuntimeError("Use --test-dbs for holdout.")
    if float(frac) >= 1.0:
        return np.isin(db, test_dbs)

    rng = np.random.RandomState(int(seed))
    mask = np.zeros(len(db), dtype=bool)
    for d in test_dbs:
        ix = np.where(db == d)[0]
        if ix.size == 0:
            continue
        groups = np.unique(stem[ix])
        n = int(max(1, min(len(groups), round(float(frac) * len(groups)))))
        pick = rng.choice(groups, size=n, replace=False)
        mask[ix] = np.isin(stem[ix], pick)
    return mask


def _train_val_split(pool_idx: np.ndarray, db: np.ndarray, stem: np.ndarray, val_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    from sklearn.model_selection import GroupShuffleSplit

    keys = np.array([f"{db[i]}::{_root(stem[i])}" for i in pool_idx], dtype=object)
    gss = GroupShuffleSplit(n_splits=1, test_size=float(np.clip(val_fraction, 0.05, 0.45)), random_state=int(seed))
    tr_rel, va_rel = next(gss.split(pool_idx, groups=keys))
    return pool_idx[tr_rel], pool_idx[va_rel]


def _norm_mode(raw: np.ndarray, db: np.ndarray, tr_idx: np.ndarray, mode: str) -> np.ndarray:
    x = raw.astype(np.float64).copy()
    if mode == "l2":
        return tuner._l2norm(x.astype(np.float32))
    if mode == "dataset_center_l2":
        means: dict[str, np.ndarray] = {}
        gmu = np.mean(x[tr_idx], axis=0)
        for d in np.unique(db):
            ix = tr_idx[db[tr_idx] == d]
            if ix.size:
                means[str(d)] = np.mean(x[ix], axis=0)
        y = np.zeros_like(x)
        for i in range(x.shape[0]):
            y[i] = x[i] - means.get(str(db[i]), gmu)
        return tuner._l2norm(y.astype(np.float32))
    if mode == "global_zscore_l2":
        mu = np.mean(x[tr_idx], axis=0)
        sd = np.std(x[tr_idx], axis=0) + 1e-8
        y = (x - mu) / sd
        return tuner._l2norm(y.astype(np.float32))
    raise ValueError(f"Unsupported --cluster-norm: {mode}")


def _greedy_align(sim: np.ndarray) -> dict[int, int]:
    n_l, n_r = sim.shape
    used_l: set[int] = set()
    used_r: set[int] = set()
    out: dict[int, int] = {}
    order = np.argsort(-sim.reshape(-1))
    for f in order.tolist():
        li = int(f // n_r)
        ri = int(f % n_r)
        if li in used_l or ri in used_r:
            continue
        out[li] = ri
        used_l.add(li)
        used_r.add(ri)
        if len(used_l) == n_l or len(used_r) == n_r:
            break
    return out


def _fit_kmeans_dsalign(xtr: np.ndarray, dbtr: np.ndarray, k: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    dbv = np.asarray(dbtr, dtype=object)
    udb = np.unique(dbv)
    counts = [(str(d), int(np.sum(dbv == d))) for d in udb.tolist()]
    counts.sort(key=lambda z: z[1], reverse=True)
    ref_db = counts[0][0]

    ix_ref = np.where(dbv == ref_db)[0]
    if ix_ref.size < k:
        km = KMeans(n_clusters=k, random_state=seed, n_init=20)
        y = km.fit_predict(xtr).astype(np.int32)
        c = tuner._l2norm(np.asarray(km.cluster_centers_, dtype=np.float32))
        return y, c

    km_ref = KMeans(n_clusters=k, random_state=seed, n_init=20)
    y_ref = km_ref.fit_predict(xtr[ix_ref]).astype(np.int32)
    c_ref = tuner._l2norm(np.asarray(km_ref.cluster_centers_, dtype=np.float32))

    y = np.full(xtr.shape[0], -1, dtype=np.int32)
    y[ix_ref] = y_ref
    c_sum = np.zeros_like(c_ref, dtype=np.float64)
    w_sum = np.zeros(k, dtype=np.float64)
    for c in range(k):
        n = int(np.sum(y_ref == c))
        if n > 0:
            c_sum[c] += c_ref[c] * n
            w_sum[c] += n

    for d in udb.tolist():
        d = str(d)
        if d == ref_db:
            continue
        ix = np.where(dbv == d)[0]
        if ix.size < 2:
            y[ix] = np.argmax(np.matmul(tuner._l2norm(xtr[ix].astype(np.float32)), c_ref.T), axis=1).astype(np.int32)
            continue

        k_loc = int(min(k, ix.size))
        km = KMeans(n_clusters=k_loc, random_state=seed, n_init=20)
        y_loc = km.fit_predict(xtr[ix]).astype(np.int32)
        c_loc = tuner._l2norm(np.asarray(km.cluster_centers_, dtype=np.float32))
        m = _greedy_align(np.matmul(c_loc, c_ref.T))

        mapped = np.array([m.get(int(v), int(np.argmax(np.matmul(c_loc[int(v)], c_ref.T)))) for v in y_loc], dtype=np.int32)
        y[ix] = mapped
        for lc in range(k_loc):
            gid = int(m.get(lc, int(np.argmax(np.matmul(c_loc[lc], c_ref.T)))))
            n = int(np.sum(y_loc == lc))
            if n > 0:
                c_sum[gid] += c_loc[lc] * n
                w_sum[gid] += n

    miss = np.where(y < 0)[0]
    if miss.size:
        y[miss] = np.argmax(np.matmul(tuner._l2norm(xtr[miss].astype(np.float32)), c_ref.T), axis=1).astype(np.int32)

    c = np.zeros_like(c_ref, dtype=np.float32)
    for i in range(k):
        c[i] = (c_sum[i] / w_sum[i]).astype(np.float32) if w_sum[i] > 0 else c_ref[i]
    c = tuner._l2norm(c.astype(np.float32))
    return y, c


def _fit_prototypes(xtr: np.ndarray, dbtr: np.ndarray, method: str, k: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    if method == "kmeans":
        km = KMeans(n_clusters=k, random_state=seed, n_init=20)
        y = km.fit_predict(xtr).astype(np.int32)
        c = tuner._l2norm(np.asarray(km.cluster_centers_, dtype=np.float32))
        return y, c
    if method == "kmeans_dsalign":
        return _fit_kmeans_dsalign(xtr=xtr, dbtr=dbtr, k=k, seed=seed)
    raise ValueError(f"Unsupported --cluster-method: {method}")


def _assign(x: np.ndarray, c: np.ndarray) -> np.ndarray:
    return np.argmax(np.matmul(x, c.T), axis=1).astype(np.int32)


def _topk_metrics(proba: np.ndarray, y_true: np.ndarray, classes: np.ndarray, ks: tuple[int, ...] = (1, 3)) -> dict[str, float]:
    order = np.argsort(-proba, axis=1)
    c2i = {int(c): i for i, c in enumerate(classes.tolist())}
    ranks = []
    for i in range(len(y_true)):
        yi = c2i.get(int(y_true[i]))
        if yi is None:
            continue
        r = int(np.where(order[i] == yi)[0][0]) + 1
        ranks.append(r)
    if not ranks:
        return {f"top{k}": 0.0 for k in ks} | {"mrr": 0.0}
    r = np.array(ranks, dtype=np.int32)
    out = {f"top{k}": float(np.mean(r <= int(k))) for k in ks}
    out["mrr"] = float(np.mean(1.0 / r))
    return out


def _cluster_purity(y: np.ndarray, db: np.ndarray, k: int) -> float:
    den = float(len(y))
    if den <= 0:
        return 0.0
    acc = 0.0
    for c in range(int(k)):
        ix = np.where(y == c)[0]
        if ix.size == 0:
            continue
        vc = pd.Series(db[ix]).value_counts(normalize=True)
        acc += (ix.size / den) * float(vc.iloc[0])
    return float(acc)


def _build_semantic_stats_from_x(xdf_train: pd.DataFrame) -> dict[str, tuple[float, float]]:
    stats: dict[str, tuple[float, float]] = {}
    for feat_key, col in sem.FEATURE_TO_XCOL.items():
        if col not in xdf_train.columns or not pd.api.types.is_numeric_dtype(xdf_train[col]):
            continue
        arr = xdf_train[col].to_numpy(dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size < 5:
            continue
        lo = float(np.min(arr))
        hi = float(np.max(arr))
        if hi > lo + 1e-12:
            stats[feat_key] = (lo, hi)

    if "bpm_motion" in xdf_train.columns and pd.api.types.is_numeric_dtype(xdf_train["bpm_motion"]):
        b = np.array([sem._normalize_bpm(v) for v in xdf_train["bpm_motion"].to_numpy(dtype=float)], dtype=float)
        b = b[np.isfinite(b)]
        if b.size >= 5:
            lo = float(np.min(b))
            hi = float(np.max(b))
            if hi > lo + 1e-12:
                stats["tempo_bpm"] = (lo, hi)

    if {"ibi_std_s", "ibi_mean_s"}.issubset(set(xdf_train.columns)):
        if pd.api.types.is_numeric_dtype(xdf_train["ibi_std_s"]) and pd.api.types.is_numeric_dtype(xdf_train["ibi_mean_s"]):
            cv = xdf_train["ibi_std_s"].to_numpy(dtype=float) / (xdf_train["ibi_mean_s"].to_numpy(dtype=float) + 1e-8)
            cv = cv[np.isfinite(cv)]
            if cv.size >= 5:
                lo = float(np.min(cv))
                hi = float(np.max(cv))
                if hi > lo + 1e-12:
                    stats["rhythm_cv"] = (lo, hi)
    return stats


def _suggest_prototype_names(centroids_orig: np.ndarray, device: str) -> dict[int, str]:
    labels = [
        "rhythmic electronic",
        "groove-heavy pop",
        "break hard-hitting",
        "softer expressive lyrical",
        "cinematic dramatic",
        "ambient atmospheric",
        "percussive dance",
        "club groove",
        "hip hop beat-driven",
    ]
    try:
        clap = tuner._load_clap_model(device=device)
        cache: dict[str, np.ndarray] = {}
        txt = tuner._l2norm(tuner._embed_texts(labels, model=clap, cache=cache, batch=64))
        out: dict[int, str] = {}
        for c in range(centroids_orig.shape[0]):
            sim = np.dot(txt, centroids_orig[c])
            out[int(c)] = labels[int(np.argmax(sim))]
        return out
    except Exception:
        return {int(c): f"cluster_{int(c)}" for c in range(centroids_orig.shape[0])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="outputs/m2m_train")
    ap.add_argument("--x-motion-csv", default="X_motion_temporal.csv")
    ap.add_argument("--clap-npz", default="clap_audio_emb_5s.npz")
    ap.add_argument("--test-dbs", default="simonalexanderson")
    ap.add_argument("--test-db-fraction", type=float, default=1.0)
    ap.add_argument("--val-fraction", type=float, default=0.20)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--cluster-method", default="kmeans_dsalign", choices=["kmeans", "kmeans_dsalign"])
    ap.add_argument("--cluster-norm", default="dataset_center_l2", choices=["l2", "dataset_center_l2", "global_zscore_l2"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out-model", default="")
    ap.add_argument("--out-report", default="")
    ap.add_argument("--out-assignments", default="")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    ddir = (root / args.dataset_dir).resolve() if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    xcsv = (ddir / args.x_motion_csv).resolve() if not Path(args.x_motion_csv).is_absolute() else Path(args.x_motion_csv)
    cnpz = (ddir / args.clap_npz).resolve() if not Path(args.clap_npz).is_absolute() else Path(args.clap_npz)
    models_dir = ddir / "models"
    reports_dir = ddir / "reports"
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    out_model = Path(args.out_model) if args.out_model else (models_dir / "motion_prototype_prompt_v2.joblib")
    out_report = Path(args.out_report) if args.out_report else (reports_dir / "train_report_motion_prototype_prompt_v2.txt")
    out_assign = Path(args.out_assignments) if args.out_assignments else (reports_dir / "motion_prototype_assignments.csv")

    xdf = pd.read_csv(xcsv)
    meta = pd.read_csv(ddir / "meta.csv")
    if len(xdf) != len(meta):
        raise RuntimeError(f"X/meta mismatch: {len(xdf)} vs {len(meta)}")
    if not cnpz.exists():
        raise FileNotFoundError(cnpz)

    z = np.load(cnpz, allow_pickle=True)
    id2j = {str(k): i for i, k in enumerate(z["ids"].tolist())}
    keep = np.array([str(cid) in id2j for cid in meta["clip_id"].astype(str).to_numpy()], dtype=bool)
    if not np.any(keep):
        raise RuntimeError("No CLAP alignment rows found.")

    xdf = xdf.loc[keep].reset_index(drop=True)
    meta = meta.loc[keep].reset_index(drop=True)
    ids = meta["clip_id"].astype(str).to_numpy()
    emb_raw = np.stack([z["emb"][id2j[cid]] for cid in ids], axis=0).astype(np.float32)
    emb_l2 = tuner._l2norm(emb_raw)

    db = meta["db"].astype(str).to_numpy()
    stem = meta["stem"].astype(str).to_numpy()
    idx_all = np.arange(len(meta), dtype=int)
    mask_test = _split_test_mask(db=db, stem=stem, test_dbs=_parse_list(args.test_dbs), frac=float(args.test_db_fraction), seed=int(args.seed))
    if not np.any(mask_test):
        raise RuntimeError("No test rows after holdout.")
    if np.all(mask_test):
        raise RuntimeError("All rows in test.")
    idx_test = idx_all[mask_test]
    idx_pool = idx_all[~mask_test]
    idx_train, idx_val = _train_val_split(pool_idx=idx_pool, db=db, stem=stem, val_fraction=float(args.val_fraction), seed=int(args.seed))

    ec = _norm_mode(raw=emb_raw, db=db, tr_idx=idx_train, mode=str(args.cluster_norm))
    y_train, c_mode = _fit_prototypes(xtr=ec[idx_train], dbtr=db[idx_train], method=str(args.cluster_method), k=int(args.k), seed=int(args.seed))
    y_val = _assign(ec[idx_val], c_mode)
    y_test = _assign(ec[idx_test], c_mode)

    # Original-space centroids for interpretation/prototype naming.
    c_orig = []
    for c in range(int(args.k)):
        ix = np.where(y_train == c)[0]
        if ix.size == 0:
            c_orig.append(np.zeros((emb_l2.shape[1],), dtype=np.float32))
        else:
            c_orig.append(np.mean(emb_l2[idx_train[ix]], axis=0).astype(np.float32))
    c_orig = tuner._l2norm(np.stack(c_orig, axis=0).astype(np.float32))

    x_cols = [c for c in xdf.columns if pd.api.types.is_numeric_dtype(xdf[c])]
    X = xdf[x_cols].copy()
    X = X.fillna(X.iloc[idx_train].median(numeric_only=True))
    X = X.to_numpy(dtype=np.float32)
    Xtr, Xva, Xte = X[idx_train], X[idx_val], X[idx_test]

    clf = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=6000, class_weight="balanced", random_state=int(args.seed))),
        ]
    )
    clf.fit(Xtr, y_train)
    p_val = clf.predict(Xva)
    p_test = clf.predict(Xte)
    pr_val = clf.predict_proba(Xva)
    pr_test = clf.predict_proba(Xte)
    classes = clf.named_steps["clf"].classes_

    val_acc = float(accuracy_score(y_val, p_val))
    val_f1 = float(f1_score(y_val, p_val, average="macro"))
    test_acc = float(accuracy_score(y_test, p_test))
    test_f1 = float(f1_score(y_test, p_test, average="macro"))
    rv = _topk_metrics(pr_val, y_val, classes=classes, ks=(1, 3))
    rt = _topk_metrics(pr_test, y_test, classes=classes, ks=(1, 3))

    nmi = float(normalized_mutual_info_score(db[idx_train], y_train))
    purity = _cluster_purity(y_train, db[idx_train], int(args.k))

    dev = str(args.device)
    if dev == "cuda":
        try:
            import torch

            if not torch.cuda.is_available():
                dev = "cpu"
        except Exception:
            dev = "cpu"
    names = _suggest_prototype_names(c_orig, device=dev)
    phrases = {
        "rhythmic electronic": "driving electronic pulse with crisp accents",
        "groove-heavy pop": "groove-forward pop rhythm with clear hooks",
        "break hard-hitting": "hard-hitting breakbeat impact and punch",
        "softer expressive lyrical": "softer lyrical phrasing with expressive flow",
        "cinematic dramatic": "cinematic dramatic arc with wide atmosphere",
        "ambient atmospheric": "ambient atmospheric texture with space",
        "percussive dance": "percussive dance rhythm and tight sync",
        "club groove": "club-oriented groove and steady drive",
        "hip hop beat-driven": "hip-hop beat-driven groove and punchy rhythm",
    }
    class_to_name = {int(c): str(names.get(int(c), f"cluster_{int(c)}")) for c in classes.tolist()}

    train_stats = _build_semantic_stats_from_x(xdf.iloc[idx_train].reset_index(drop=True))

    bundle = {
        "bundle_type": "motion_prototype_prompt_v2",
        "classifier": clf,
        "x_cols": x_cols,
        "classes": [int(c) for c in classes.tolist()],
        "prototype_centroids_orig": c_orig,
        "class_to_name": class_to_name,
        "name_to_phrase": phrases,
        "semantic_train_stats": train_stats,
        "train_config": {
            "dataset_dir": str(ddir),
            "x_motion_csv": str(xcsv),
            "clap_npz": str(cnpz),
            "k": int(args.k),
            "cluster_method": str(args.cluster_method),
            "cluster_norm": str(args.cluster_norm),
            "test_dbs": _parse_list(args.test_dbs),
            "test_db_fraction": float(args.test_db_fraction),
            "val_fraction": float(args.val_fraction),
            "seed": int(args.seed),
        },
        "metrics": {
            "val_acc": val_acc,
            "val_f1_macro": val_f1,
            "val_top1": rv["top1"],
            "val_top3": rv["top3"],
            "val_mrr": rv["mrr"],
            "test_acc": test_acc,
            "test_f1_macro": test_f1,
            "test_top1": rt["top1"],
            "test_top3": rt["top3"],
            "test_mrr": rt["mrr"],
            "cluster_dataset_nmi_train": nmi,
            "cluster_dataset_purity_train": purity,
        },
    }
    joblib.dump(bundle, out_model)

    split_col = np.full(len(meta), "train", dtype=object)
    split_col[idx_val] = "val"
    split_col[idx_test] = "test"
    y_all = np.zeros(len(meta), dtype=np.int32)
    y_all[idx_train] = y_train
    y_all[idx_val] = y_val
    y_all[idx_test] = y_test
    pd.DataFrame(
        {
            "clip_id": meta["clip_id"].to_numpy(),
            "db": db,
            "stem": stem,
            "split": split_col,
            "prototype": y_all.astype(int),
            "prototype_name": [class_to_name.get(int(p), f"cluster_{int(p)}") for p in y_all.tolist()],
        }
    ).to_csv(out_assign, index=False)

    lines = [
        f"dataset_dir={ddir}",
        f"x_motion_csv={xcsv}",
        f"clap_npz={cnpz}",
        f"rows_total={len(meta)} rows_train={len(idx_train)} rows_val={len(idx_val)} rows_test={len(idx_test)}",
        f"cluster_method={args.cluster_method}",
        f"cluster_norm={args.cluster_norm}",
        f"k={int(args.k)}",
        f"cluster_dataset_nmi_train={nmi:.6f}",
        f"cluster_dataset_purity_train={purity:.6f}",
        "",
        "[motion->prototype]",
        f"val_acc={val_acc:.6f}",
        f"val_f1_macro={val_f1:.6f}",
        f"val_top1={rv['top1']:.6f} val_top3={rv['top3']:.6f} val_mrr={rv['mrr']:.6f}",
        f"test_acc={test_acc:.6f}",
        f"test_f1_macro={test_f1:.6f}",
        f"test_top1={rt['top1']:.6f} test_top3={rt['top3']:.6f} test_mrr={rt['mrr']:.6f}",
        "",
        "prototype_names=" + json.dumps({str(k): v for k, v in sorted(class_to_name.items())}, ensure_ascii=True),
        f"model_path={out_model}",
        f"assignments_csv={out_assign}",
    ]
    out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[done] model:", out_model)
    print("[done] report:", out_report)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
