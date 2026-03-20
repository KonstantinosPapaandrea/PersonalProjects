#!/usr/bin/env python3
"""
train_semantic_motion_model.py

Train a motion-only semantic model:
X_motion features -> semantic control vector scores.

Targets are computed from the current hand-crafted semantic equations, then
learned with a regression model to improve consistency and provide a deployable
predictor with optional temporal smoothing at inference.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import semantic_prompt_from_motion as sem

TARGET_COLS = [
    "energy_score",
    "heaviness_score",
    "sharpness_score",
    "control_score",
    "expansiveness_score",
    "rhythmic_stability_score",
    "arousal_score",
    "valence_score",
    "dynamic_score",
]

TAG_COLS = [
    "energy_tag",
    "weight_tag",
    "flow_tag",
    "attack_tag",
    "space_tag",
    "rhythm_tag",
    "dynamic_tag",
    "mood_tag",
    "style_tag",
]


def _parse_db_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _split_mask(
    db: np.ndarray,
    stem: np.ndarray,
    test_dbs: list[str],
    test_db_fraction: float,
    seed: int,
) -> np.ndarray:
    if not test_dbs:
        raise RuntimeError("Use --test-dbs to define a holdout split.")

    if float(test_db_fraction) >= 1.0:
        return np.isin(db, test_dbs)

    rng = np.random.RandomState(int(seed))
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


def _build_train_stats_from_x(xdf_train: pd.DataFrame) -> dict[str, tuple[float, float]]:
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
        if hi <= lo + 1e-12:
            continue
        stats[feat_key] = (lo, hi)

    if "bpm_motion" in xdf_train.columns and pd.api.types.is_numeric_dtype(xdf_train["bpm_motion"]):
        bpm_raw = xdf_train["bpm_motion"].to_numpy(dtype=float)
        bpm = np.array([sem._normalize_bpm(v) for v in bpm_raw], dtype=float)
        bpm = bpm[np.isfinite(bpm)]
        if bpm.size >= 5:
            lo = float(np.min(bpm))
            hi = float(np.max(bpm))
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

    dyn_cols = [
        "lma_std_BODY",
        "lma_std_EFFORT_WEIGHT_STRONG",
        "lma_std_EFFORT_TIME_SUDDEN",
        "lma_std_EFFORT_FLOW_BOUND",
        "lma_std_SPACE",
    ]
    if all((c in xdf_train.columns and pd.api.types.is_numeric_dtype(xdf_train[c])) for c in dyn_cols):
        dyn = (
            0.25 * xdf_train["lma_std_BODY"].to_numpy(dtype=float)
            + 0.25 * xdf_train["lma_std_EFFORT_WEIGHT_STRONG"].to_numpy(dtype=float)
            + 0.20 * xdf_train["lma_std_EFFORT_TIME_SUDDEN"].to_numpy(dtype=float)
            + 0.15 * xdf_train["lma_std_EFFORT_FLOW_BOUND"].to_numpy(dtype=float)
            + 0.15 * xdf_train["lma_std_SPACE"].to_numpy(dtype=float)
        )
        dyn = dyn[np.isfinite(dyn)]
        if dyn.size >= 5:
            lo = float(np.min(dyn))
            hi = float(np.max(dyn))
            if hi > lo + 1e-12:
                stats["dynamic_score"] = (lo, hi)

    return stats


def _raw_feature_row_from_x(xrow: pd.Series) -> dict[str, float]:
    ibi_mean = float(xrow.get("ibi_mean_s", 0.0))
    ibi_std = float(xrow.get("ibi_std_s", 0.0))
    return {
        "BODY_mean": float(xrow.get("lma_mean_BODY", 0.0)),
        "BODY_std": float(xrow.get("lma_std_BODY", 0.0)),
        "EFFORT_WEIGHT_STRONG_mean": float(xrow.get("lma_mean_EFFORT_WEIGHT_STRONG", 0.0)),
        "EFFORT_WEIGHT_STRONG_std": float(xrow.get("lma_std_EFFORT_WEIGHT_STRONG", 0.0)),
        "EFFORT_TIME_SUDDEN_mean": float(xrow.get("lma_mean_EFFORT_TIME_SUDDEN", 0.0)),
        "EFFORT_TIME_SUDDEN_std": float(xrow.get("lma_std_EFFORT_TIME_SUDDEN", 0.0)),
        "EFFORT_FLOW_BOUND_mean": float(xrow.get("lma_mean_EFFORT_FLOW_BOUND", 0.0)),
        "EFFORT_FLOW_BOUND_std": float(xrow.get("lma_std_EFFORT_FLOW_BOUND", 0.0)),
        "SPACE_mean": float(xrow.get("lma_mean_SPACE", 0.0)),
        "SPACE_std": float(xrow.get("lma_std_SPACE", 0.0)),
        "tempo_bpm": float(xrow.get("bpm_motion", 120.0)),
        "rhythm_cv": float(ibi_std / (ibi_mean + 1e-8)),
    }


def _make_targets(xdf: pd.DataFrame, train_stats: dict[str, tuple[float, float]]) -> np.ndarray:
    y = np.zeros((len(xdf), len(TARGET_COLS)), dtype=np.float32)
    for i, row in enumerate(xdf.itertuples(index=False)):
        xrow = pd.Series(row._asdict())
        raw = _raw_feature_row_from_x(xrow)
        norm = sem.normalize_features(raw, train_stats)
        scores = sem.compute_semantic_scores(norm)
        y[i, :] = np.array([scores[k] for k in TARGET_COLS], dtype=np.float32)
    return y


def _scores_to_tag_rows(y: np.ndarray) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for i in range(y.shape[0]):
        scores = {k: float(v) for k, v in zip(TARGET_COLS, y[i])}
        rows.append(sem.scores_to_tags(scores))
    return rows


def _tag_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    t_true = _scores_to_tag_rows(y_true)
    t_pred = _scores_to_tag_rows(y_pred)
    out: dict[str, float] = {}
    for c in TAG_COLS:
        hits = [1.0 if t_true[i].get(c, "") == t_pred[i].get(c, "") else 0.0 for i in range(len(t_true))]
        out[c] = float(np.mean(hits)) if hits else 0.0
    out["tag_acc_mean"] = float(np.mean([out[c] for c in TAG_COLS])) if TAG_COLS else 0.0
    return out


def _parse_hidden(text: str) -> tuple[int, ...]:
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return (128, 64)
    return tuple(int(p) for p in parts)


def _make_model(model_name: str, seed: int, ridge_alpha: float, mlp_hidden: tuple[int, ...], mlp_max_iter: int):
    if model_name == "ridge":
        reg = MultiOutputRegressor(Ridge(alpha=float(ridge_alpha), random_state=int(seed)))
    elif model_name == "mlp":
        reg = MLPRegressor(
            hidden_layer_sizes=mlp_hidden,
            random_state=int(seed),
            max_iter=int(mlp_max_iter),
            early_stopping=True,
            n_iter_no_change=20,
        )
    else:
        raise ValueError(f"Unsupported model: {model_name}")
    return Pipeline([("scaler", StandardScaler()), ("reg", reg)])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--out-model", default="")
    ap.add_argument("--out-report", default="")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-dbs", default="simonalexanderson")
    ap.add_argument("--test-db-fraction", type=float, default=1.0)
    ap.add_argument("--model", default="auto", choices=["auto", "ridge", "mlp"])
    ap.add_argument("--ridge-alpha", type=float, default=20.0)
    ap.add_argument("--mlp-hidden", type=str, default="128,64")
    ap.add_argument("--mlp-max-iter", type=int, default=600)
    ap.add_argument("--val-fraction", type=float, default=0.15)
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    models_dir = dataset_dir / "models"
    reports_dir = dataset_dir / "reports"
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    out_model = Path(args.out_model) if args.out_model else (models_dir / "semantic_motion_model.joblib")
    out_report = Path(args.out_report) if args.out_report else (reports_dir / "train_report_semantic_motion_model.txt")

    xp = dataset_dir / "X_motion.csv"
    mp = dataset_dir / "meta.csv"
    if not xp.exists() or not mp.exists():
        raise FileNotFoundError("dataset-dir must contain X_motion.csv and meta.csv")

    xdf = pd.read_csv(xp)
    meta = pd.read_csv(mp)
    if len(xdf) != len(meta):
        raise RuntimeError(f"X/meta row mismatch: {len(xdf)} vs {len(meta)}")

    x_cols = [c for c in xdf.columns if pd.api.types.is_numeric_dtype(xdf[c])]
    if not x_cols:
        raise RuntimeError("No numeric X columns found.")

    db = meta["db"].astype(str).to_numpy() if "db" in meta.columns else np.array(["unknown"] * len(meta))
    stem = meta["stem"].astype(str).to_numpy() if "stem" in meta.columns else np.array([str(i) for i in range(len(meta))])

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
        raise RuntimeError("All rows are in test; no training data.")

    x_train_df = xdf.loc[~mask_test].reset_index(drop=True)
    x_test_df = xdf.loc[mask_test].reset_index(drop=True)
    db_train = db[~mask_test]
    db_test = db[mask_test]

    # Build semantic target generator stats from TRAIN only.
    train_stats = _build_train_stats_from_x(x_train_df)

    # Build X arrays.
    xtr_num_df = x_train_df[x_cols].copy()
    xte_num_df = x_test_df[x_cols].copy()
    med = xtr_num_df.median(numeric_only=True)
    xtr_num_df = xtr_num_df.fillna(med)
    xte_num_df = xte_num_df.fillna(med)
    Xtr = xtr_num_df.to_numpy(dtype=np.float32)
    Xte = xte_num_df.to_numpy(dtype=np.float32)

    # Build pseudo-semantic targets.
    Ytr = _make_targets(x_train_df, train_stats=train_stats)
    Yte = _make_targets(x_test_df, train_stats=train_stats)

    hidden = _parse_hidden(args.mlp_hidden)
    model_choice = str(args.model)

    if model_choice == "auto":
        X_sub, X_val, Y_sub, Y_val = train_test_split(
            Xtr,
            Ytr,
            test_size=float(np.clip(args.val_fraction, 0.05, 0.40)),
            random_state=int(args.seed),
            shuffle=True,
        )
        cand = {
            "ridge": _make_model("ridge", int(args.seed), float(args.ridge_alpha), hidden, int(args.mlp_max_iter)),
            "mlp": _make_model("mlp", int(args.seed), float(args.ridge_alpha), hidden, int(args.mlp_max_iter)),
        }
        val_scores: dict[str, float] = {}
        for name, mdl in cand.items():
            mdl.fit(X_sub, Y_sub)
            pred_val = mdl.predict(X_val)
            val_scores[name] = float(mean_absolute_error(Y_val, pred_val))
        chosen = min(val_scores, key=val_scores.get)
        model = cand[chosen]
        model_name = f"auto->{chosen}"
    else:
        model = _make_model(model_choice, int(args.seed), float(args.ridge_alpha), hidden, int(args.mlp_max_iter))
        model_name = model_choice

    model.fit(Xtr, Ytr)
    Yhat = model.predict(Xte).astype(np.float32)

    mae_all = float(mean_absolute_error(Yte, Yhat))
    mae_per_target = {c: float(mean_absolute_error(Yte[:, i], Yhat[:, i])) for i, c in enumerate(TARGET_COLS)}

    r2_per_target = {}
    for i, c in enumerate(TARGET_COLS):
        yt = Yte[:, i]
        yp = Yhat[:, i]
        r2_per_target[c] = float(r2_score(yt, yp)) if np.std(yt) > 1e-12 else 0.0
    r2_mean = float(np.mean(list(r2_per_target.values())))

    tag_metrics = _tag_accuracy(Yte, Yhat)

    payload = {
        "bundle_type": "semantic_motion_model_v1",
        "model": model,
        "x_cols": x_cols,
        "target_cols": TARGET_COLS,
        "train_stats": train_stats,
        "seed": int(args.seed),
        "model_name": model_name,
        "ridge_alpha": float(args.ridge_alpha),
        "mlp_hidden": hidden,
        "mlp_max_iter": int(args.mlp_max_iter),
        "test_dbs": test_dbs,
        "test_db_fraction": float(args.test_db_fraction),
        "metrics": {
            "mae_all": mae_all,
            "r2_mean": r2_mean,
            "mae_per_target": mae_per_target,
            "r2_per_target": r2_per_target,
            "tag_metrics": tag_metrics,
        },
    }
    joblib.dump(payload, out_model)

    lines = [
        f"rows={len(xdf)} X_dim={len(x_cols)} Y_dim={len(TARGET_COLS)}",
        f"split=db-holdout ({','.join(test_dbs)}) fraction={float(args.test_db_fraction):.3f}",
        f"train_rows={len(x_train_df)} test_rows={len(x_test_df)}",
        f"train_db_counts={pd.Series(db_train).value_counts().to_dict()}",
        f"test_db_counts={pd.Series(db_test).value_counts().to_dict()}",
        f"model={model_name}",
        f"mae_all={mae_all:.6f}",
        f"r2_mean={r2_mean:.6f}",
    ]
    for c in TARGET_COLS:
        lines.append(f"mae_{c}={mae_per_target[c]:.6f}")
    for c in TARGET_COLS:
        lines.append(f"r2_{c}={r2_per_target[c]:.6f}")
    for c in TAG_COLS + ["tag_acc_mean"]:
        lines.append(f"{c}={tag_metrics[c]:.6f}")
    lines.append(f"model_path={out_model}")

    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[done] saved model:", out_model)
    print("[done] saved report:", out_report)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
