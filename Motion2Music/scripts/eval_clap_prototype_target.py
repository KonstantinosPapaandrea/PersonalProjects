#!/usr/bin/env python3
"""
eval_clap_prototype_target.py

Hypothesis test:
- Exact target: cosine( CLAP(text prompt), CLAP(audio clip) )
- Prototype target: cosine( CLAP(text prompt), centroid_of_audio_cluster )

If prototype-target similarity is clearly higher, it supports target-mismatch:
motion semantics may map better to broad audio style prototypes than to exact
track-level embeddings.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.model_selection import GroupShuffleSplit

import semantic_prompt_from_motion as sem
import tune_semantic_prompt_params as tuner


def _parse_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _track_root(stem: str) -> tuple[str, int]:
    m = re.search(r"_ch(\d+)$", stem)
    if not m:
        return stem, -1
    return stem[: m.start()], int(m.group(1))


def _build_subset_groups(meta: pd.DataFrame, subset_idx: np.ndarray) -> list[np.ndarray]:
    sub = meta.loc[subset_idx].copy()
    roots: list[str] = []
    chs: list[int] = []
    for s in sub["stem"].astype(str).tolist():
        r, c = _track_root(s)
        roots.append(r)
        chs.append(c)
    sub["track_root"] = roots
    sub["chunk_idx"] = chs
    sub["__gidx__"] = subset_idx
    sub = sub.sort_values(by=["db", "track_root", "chunk_idx", "clip_id"], kind="mergesort")
    out: list[np.ndarray] = []
    for _, g in sub.groupby(["db", "track_root"], sort=False):
        out.append(g["__gidx__"].to_numpy(dtype=int))
    return out


def _load_params(params_json: Path | None) -> dict[str, Any]:
    if params_json is None:
        return tuner._default_params()
    obj = json.loads(params_json.read_text(encoding="utf-8"))
    if "best" in obj and isinstance(obj["best"], dict) and "params" in obj["best"]:
        src = obj["best"]["params"]
    else:
        src = obj

    p = {
        "sigma": float(src.get("sigma", 0.0)),
        "t1": float(src.get("t1", 0.33)),
        "t2": float(src.get("t2", 0.66)),
        "ema_alpha": float(src.get("ema_alpha", 1.0)),
        "hysteresis_margin": float(src.get("hysteresis_margin", 0.05)),
    }
    for k, base in tuner.BASE_WEIGHTS.items():
        arr = np.asarray(src.get(k, base.tolist()), dtype=np.float64)
        if arr.shape[0] != base.shape[0]:
            arr = base.copy()
        arr = np.maximum(arr, 1e-8)
        p[k] = arr / np.sum(arr)
    return p


def _build_prompts_for_subset(
    idx: np.ndarray,
    groups: list[np.ndarray],
    score_mat: np.ndarray,
    tempo_bpm: np.ndarray,
    params: dict[str, Any],
) -> tuple[list[str], float]:
    t1 = float(params["t1"])
    t2 = float(params["t2"])
    alpha = float(params["ema_alpha"])
    margin = float(params["hysteresis_margin"])

    prompts_by_idx: dict[int, str] = {}
    transitions = 0
    switched = 0

    for g in groups:
        prev_scores: dict[str, float] | None = None
        prev_tags: dict[str, str] | None = None
        for gi in g:
            srow = {k: float(v) for k, v in zip(tuner.BASE_SCORE_KEYS, score_mat[gi])}
            if prev_scores is not None:
                smoothed = {}
                for k in tuner.BASE_SCORE_KEYS:
                    smoothed[k] = float(np.clip(alpha * srow[k] + (1.0 - alpha) * prev_scores[k], 0.0, 1.0))
            else:
                smoothed = dict(srow)

            tags = tuner._tags_from_scores(smoothed, t1=t1, t2=t2)
            tags = tuner._hysteresis(smoothed, tags, prev_tags=prev_tags, margin=margin, t1=t1, t2=t2)
            prompts_by_idx[int(gi)] = sem.generate_prompt(tags, float(tempo_bpm[gi]))

            if prev_tags is not None:
                transitions += 1
                if any(tags[k] != prev_tags[k] for k in tuner.BASE_TAG_KEYS):
                    switched += 1

            prev_scores = smoothed
            prev_tags = tags

    prompts = [prompts_by_idx[int(i)] for i in idx.tolist()]
    switch_rate = float(switched / transitions) if transitions > 0 else 0.0
    return prompts, switch_rate


def _bootstrap_mean_ci(delta: np.ndarray, rng: np.random.RandomState, n_boot: int = 2000) -> tuple[float, float]:
    d = np.asarray(delta, dtype=np.float64)
    if d.size == 0:
        return 0.0, 0.0
    means = np.zeros(n_boot, dtype=np.float64)
    n = d.size
    for i in range(n_boot):
        idx = rng.randint(0, n, size=n)
        means[i] = float(np.mean(d[idx]))
    lo = float(np.percentile(means, 2.5))
    hi = float(np.percentile(means, 97.5))
    return lo, hi


def _eval_subset_for_k(
    idx: np.ndarray,
    text_emb_norm: np.ndarray,
    audio_emb_norm: np.ndarray,
    kmeans: KMeans,
    cent_norm: np.ndarray,
    rng: np.random.RandomState,
) -> dict[str, float]:
    exact = np.sum(text_emb_norm * audio_emb_norm[idx], axis=1)
    labels = kmeans.predict(audio_emb_norm[idx])
    proto = np.sum(text_emb_norm * cent_norm[labels], axis=1)

    delta = proto - exact
    ci_lo, ci_hi = _bootstrap_mean_ci(delta, rng=rng, n_boot=2000)
    return {
        "n": int(len(idx)),
        "exact_mean_cos": float(np.mean(exact)),
        "prototype_mean_cos": float(np.mean(proto)),
        "delta_mean": float(np.mean(delta)),
        "delta_median": float(np.median(delta)),
        "improved_fraction": float(np.mean(delta > 0.0)),
        "delta_ci95_lo": ci_lo,
        "delta_ci95_hi": ci_hi,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="outputs/m2m_train")
    ap.add_argument("--params-json", default="outputs/m2m_train/reports/semantic_tune_search/best_params.json")
    ap.add_argument("--test-dbs", default="simonalexanderson")
    ap.add_argument("--test-db-fraction", type=float, default=1.0)
    ap.add_argument("--val-fraction", type=float, default=0.20)
    ap.add_argument("--k-list", default="4,6,8,12,16")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    dataset_dir = (root / args.dataset_dir).resolve() if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    params_json = (root / args.params_json).resolve() if args.params_json and not Path(args.params_json).is_absolute() else Path(args.params_json)
    out_dir = Path(args.out_dir) if args.out_dir else (dataset_dir / "reports" / "prototype_target_eval")
    out_dir.mkdir(parents=True, exist_ok=True)

    xp = dataset_dir / "X_motion.csv"
    mp = dataset_dir / "meta.csv"
    cp = dataset_dir / "clap_audio_emb.npz"
    if not xp.exists() or not mp.exists() or not cp.exists():
        raise FileNotFoundError("dataset-dir must contain X_motion.csv, meta.csv, clap_audio_emb.npz")

    xdf = pd.read_csv(xp)
    meta = pd.read_csv(mp)
    if len(xdf) != len(meta):
        raise RuntimeError(f"X/meta mismatch: {len(xdf)} vs {len(meta)}")
    if "clip_id" not in meta.columns or "db" not in meta.columns or "stem" not in meta.columns:
        raise RuntimeError("meta.csv must contain clip_id, db, stem")

    z = np.load(cp, allow_pickle=True)
    clap_ids = np.array([str(x) for x in z["ids"]], dtype=object)
    clap_emb = np.asarray(z["emb"], dtype=np.float32)
    id2j = {k: i for i, k in enumerate(clap_ids.tolist())}

    clip_ids = meta["clip_id"].astype(str).to_numpy()
    keep = np.array([cid in id2j for cid in clip_ids], dtype=bool)
    if not np.any(keep):
        raise RuntimeError("No rows aligned with CLAP ids.")

    xdf = xdf.loc[keep].reset_index(drop=True)
    meta = meta.loc[keep].reset_index(drop=True)
    clip_ids = meta["clip_id"].astype(str).to_numpy()
    emb = np.stack([clap_emb[id2j[cid]] for cid in clip_ids], axis=0).astype(np.float32)
    emb_norm = tuner._l2norm(emb)

    db = meta["db"].astype(str).to_numpy()
    stems = meta["stem"].astype(str).to_numpy()
    test_dbs = _parse_list(args.test_dbs)
    if not test_dbs:
        raise RuntimeError("--test-dbs cannot be empty.")

    mask_test = np.isin(db, test_dbs)
    if float(args.test_db_fraction) < 1.0:
        rng_tmp = np.random.RandomState(int(args.seed))
        sub_mask = np.zeros_like(mask_test, dtype=bool)
        for d in test_dbs:
            idx_d = np.where(db == d)[0]
            if idx_d.size == 0:
                continue
            groups = np.unique(stems[idx_d])
            n = max(1, int(round(float(args.test_db_fraction) * groups.size)))
            pick = rng_tmp.choice(groups, size=min(n, groups.size), replace=False)
            sub_mask[idx_d] = np.isin(stems[idx_d], pick)
        mask_test = sub_mask

    if not np.any(mask_test):
        raise RuntimeError("No test rows after db holdout.")
    if np.all(mask_test):
        raise RuntimeError("All rows are in test; no train/val rows.")

    idx_all = np.arange(len(meta), dtype=int)
    idx_pool = idx_all[~mask_test]
    idx_test = idx_all[mask_test]

    group_keys = []
    for i in idx_pool.tolist():
        root_stem, _ = _track_root(stems[i])
        group_keys.append(f"{db[i]}::{root_stem}")
    group_keys = np.array(group_keys, dtype=object)
    gss = GroupShuffleSplit(n_splits=1, test_size=float(np.clip(args.val_fraction, 0.05, 0.45)), random_state=int(args.seed))
    tr_rel, va_rel = next(gss.split(idx_pool, groups=group_keys))
    idx_train = idx_pool[tr_rel]
    idx_val = idx_pool[va_rel]

    params = _load_params(params_json if params_json.exists() else None)
    feat = tuner._build_norm_features(xdf, train_idx=idx_train)
    score_mat = tuner._compute_score_matrix(feat, params)
    tempo_bpm = feat["tempo_bpm"]

    val_groups = _build_subset_groups(meta, idx_val)
    test_groups = _build_subset_groups(meta, idx_test)

    # Prompt -> CLAP text embedding (once per subset)
    device = str(args.device)
    if device == "cuda":
        try:
            import torch

            if not torch.cuda.is_available():
                device = "cpu"
        except Exception:
            device = "cpu"
    clap_model = tuner._load_clap_model(device=device)
    text_cache: dict[str, np.ndarray] = {}

    val_prompts, val_switch_rate = _build_prompts_for_subset(
        idx=idx_val,
        groups=val_groups,
        score_mat=score_mat,
        tempo_bpm=tempo_bpm,
        params=params,
    )
    test_prompts, test_switch_rate = _build_prompts_for_subset(
        idx=idx_test,
        groups=test_groups,
        score_mat=score_mat,
        tempo_bpm=tempo_bpm,
        params=params,
    )

    val_text = tuner._embed_texts(val_prompts, model=clap_model, cache=text_cache, batch=64)
    test_text = tuner._embed_texts(test_prompts, model=clap_model, cache=text_cache, batch=64)
    val_text = tuner._l2norm(val_text)
    test_text = tuner._l2norm(test_text)

    # Prototype clustering on TRAIN audio embeddings only
    k_list = [int(x) for x in _parse_list(args.k_list)]
    if not k_list:
        raise RuntimeError("--k-list is empty")
    k_list = [k for k in k_list if k >= 2]
    if not k_list:
        raise RuntimeError("--k-list must include >=2 values")

    rng = np.random.RandomState(int(args.seed))
    rows: list[dict[str, Any]] = []
    best_k = None
    best_val_delta = -1e9

    train_emb = emb_norm[idx_train]
    for k in k_list:
        if k > len(idx_train):
            continue
        km = KMeans(n_clusters=k, random_state=int(args.seed), n_init=20)
        km.fit(train_emb)
        cent = km.cluster_centers_.astype(np.float32)
        cent = tuner._l2norm(cent)

        val_stats = _eval_subset_for_k(
            idx=idx_val,
            text_emb_norm=val_text,
            audio_emb_norm=emb_norm,
            kmeans=km,
            cent_norm=cent,
            rng=rng,
        )
        test_stats = _eval_subset_for_k(
            idx=idx_test,
            text_emb_norm=test_text,
            audio_emb_norm=emb_norm,
            kmeans=km,
            cent_norm=cent,
            rng=rng,
        )

        row = {
            "k": int(k),
            "val_exact_mean_cos": val_stats["exact_mean_cos"],
            "val_prototype_mean_cos": val_stats["prototype_mean_cos"],
            "val_delta_mean": val_stats["delta_mean"],
            "val_delta_median": val_stats["delta_median"],
            "val_improved_fraction": val_stats["improved_fraction"],
            "val_delta_ci95_lo": val_stats["delta_ci95_lo"],
            "val_delta_ci95_hi": val_stats["delta_ci95_hi"],
            "val_switch_rate": float(val_switch_rate),
            "test_exact_mean_cos": test_stats["exact_mean_cos"],
            "test_prototype_mean_cos": test_stats["prototype_mean_cos"],
            "test_delta_mean": test_stats["delta_mean"],
            "test_delta_median": test_stats["delta_median"],
            "test_improved_fraction": test_stats["improved_fraction"],
            "test_delta_ci95_lo": test_stats["delta_ci95_lo"],
            "test_delta_ci95_hi": test_stats["delta_ci95_hi"],
            "test_switch_rate": float(test_switch_rate),
        }
        rows.append(row)
        if row["val_delta_mean"] > best_val_delta:
            best_val_delta = float(row["val_delta_mean"])
            best_k = int(k)

    if not rows:
        raise RuntimeError("No valid k values were evaluated.")

    rows_df = pd.DataFrame(rows).sort_values(by="k")
    rows_csv = out_dir / "prototype_vs_exact.csv"
    rows_df.to_csv(rows_csv, index=False)

    best_row = rows_df.loc[rows_df["k"] == best_k].iloc[0].to_dict()
    clear_improvement = bool(float(best_row["test_delta_ci95_lo"]) > 0.0 and float(best_row["test_delta_mean"]) > 0.0)

    summary = {
        "dataset_dir": str(dataset_dir),
        "params_json": str(params_json) if params_json else "",
        "split": {
            "rows_total": int(len(meta)),
            "rows_train": int(len(idx_train)),
            "rows_val": int(len(idx_val)),
            "rows_test": int(len(idx_test)),
            "test_dbs": test_dbs,
            "test_db_fraction": float(args.test_db_fraction),
        },
        "search": {
            "k_list": k_list,
            "best_k_by_val_delta_mean": int(best_k),
        },
        "best_result": best_row,
        "hypothesis_support": {
            "clear_improvement": clear_improvement,
            "criterion": "test_delta_mean > 0 and test_delta_ci95_lo > 0",
        },
        "outputs": {
            "table_csv": str(rows_csv),
        },
    }
    summary_json = out_dir / "summary.json"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = out_dir / "report.txt"
    lines = [
        f"dataset_dir={dataset_dir}",
        f"rows_total={len(meta)} rows_train={len(idx_train)} rows_val={len(idx_val)} rows_test={len(idx_test)}",
        f"test_dbs={test_dbs} test_db_fraction={float(args.test_db_fraction):.3f}",
        f"k_list={k_list}",
        "",
        "[best by val delta]",
        f"k={best_k}",
        f"val_exact_mean_cos={best_row['val_exact_mean_cos']:.6f}",
        f"val_prototype_mean_cos={best_row['val_prototype_mean_cos']:.6f}",
        f"val_delta_mean={best_row['val_delta_mean']:.6f}",
        f"val_delta_ci95=[{best_row['val_delta_ci95_lo']:.6f}, {best_row['val_delta_ci95_hi']:.6f}]",
        f"test_exact_mean_cos={best_row['test_exact_mean_cos']:.6f}",
        f"test_prototype_mean_cos={best_row['test_prototype_mean_cos']:.6f}",
        f"test_delta_mean={best_row['test_delta_mean']:.6f}",
        f"test_delta_ci95=[{best_row['test_delta_ci95_lo']:.6f}, {best_row['test_delta_ci95_hi']:.6f}]",
        f"test_improved_fraction={best_row['test_improved_fraction']:.6f}",
        "",
        f"clear_improvement={clear_improvement}",
        "criterion=test_delta_mean > 0 and test_delta_ci95_lo > 0",
        "",
        f"table_csv={rows_csv}",
        f"summary_json={summary_json}",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[done] report:", report)
    print("[done] summary:", summary_json)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
