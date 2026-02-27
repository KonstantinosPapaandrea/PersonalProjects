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

def _load_xy(dataset_dir: Path):
    Xp = dataset_dir / "X_motion.csv"
    Yp = dataset_dir / "Y_audio.csv"
    if not Xp.exists():
        raise FileNotFoundError(f"Missing {Xp}. Run build_motion2music_dataset first.")
    if not Yp.exists():
        raise FileNotFoundError(f"Missing {Yp}. Run precompute_audio_targets.py first.")

    Xdf = pd.read_csv(Xp)
    Ydf = pd.read_csv(Yp)

    xid = "clip_id" if "clip_id" in Xdf.columns else Xdf.columns[0]
    yid = "clip_id" if "clip_id" in Ydf.columns else Ydf.columns[0]

    df = Xdf.merge(Ydf, left_on=xid, right_on=yid, how="inner", suffixes=("", "_y"))
    if df.empty:
        raise RuntimeError("No aligned rows between X_motion.csv and Y_audio.csv. Check clip_id naming.")

    X_cols = [c for c in Xdf.columns if c != xid]
    X = df[X_cols].select_dtypes(include=[np.number]).fillna(0.0).to_numpy(dtype=np.float32)

    Y_cols = [c for c in Ydf.columns if c not in (yid, "audio_path")]
    Y = df[Y_cols].select_dtypes(include=[np.number]).fillna(0.0).to_numpy(dtype=np.float32)

    ids = df[xid].astype(str).to_numpy()
    return X, Y, ids, X_cols, Y_cols

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", type=str, required=True)
    ap.add_argument("--model", type=str, default="ridge", choices=["ridge", "rf"])
    ap.add_argument("--test-size", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    X, Y, ids, X_cols, Y_cols = _load_xy(dataset_dir)

    Xtr, Xte, Ytr, Yte = train_test_split(X, Y, test_size=args.test_size, random_state=args.seed)

    if args.model == "ridge":
        from sklearn.linear_model import Ridge
        base = Ridge(alpha=1.0, random_state=args.seed)
        model = Pipeline([
            ("scaler", StandardScaler(with_mean=True, with_std=True)),
            ("reg", MultiOutputRegressor(base))
        ])
    else:
        from sklearn.ensemble import RandomForestRegressor
        base = RandomForestRegressor(
            n_estimators=300,
            random_state=args.seed,
            n_jobs=-1,
            max_depth=None,
        )
        model = MultiOutputRegressor(base)

    model.fit(Xtr, Ytr)
    pred = model.predict(Xte)

    mae = float(mean_absolute_error(Yte, pred))
    r2s = []
    for j in range(Yte.shape[1]):
        try:
            r2s.append(float(r2_score(Yte[:, j], pred[:, j])))
        except Exception:
            pass
    r2_mean = float(np.mean(r2s)) if r2s else float("nan")

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
    }, out_model_path)

    report = (
        f"rows={X.shape[0]}  X_dim={X.shape[1]}  Y_dim={Y.shape[1]}\n"
        f"model={args.model}\n"
        f"MAE(mean over all targets)={mae:.6f}\n"
        f"R2(mean over targets)={r2_mean:.6f}\n"
    )
    (out_reports / "train_report.txt").write_text(report, encoding="utf-8")
    print("[done] saved:", out_model_path)
    print(report)

if __name__ == "__main__":
    main()
