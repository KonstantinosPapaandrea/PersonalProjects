#!/usr/bin/env python3
"""
build_motion_temporal_features.py

Create an extended motion feature table with temporal windows and beat-motion
interaction features from per-clip LMA/beat CSV files under:
  <dataset-dir>/features/<stem>_lma.csv
  <dataset-dir>/features/<stem>_beats.csv

Output:
  <dataset-dir>/X_motion_temporal.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


LMA_KEYS = [
    "BODY",
    "EFFORT_WEIGHT_STRONG",
    "EFFORT_TIME_SUDDEN",
    "EFFORT_FLOW_BOUND",
    "SPACE",
]


def _safe_read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _win_means(t: np.ndarray, x: np.ndarray, n_win: int) -> tuple[list[float], float, float]:
    if x.size == 0 or t.size == 0:
        return [0.0] * n_win, 0.0, 0.0
    t0 = float(np.min(t))
    t1 = float(np.max(t))
    if t1 <= t0 + 1e-9:
        m = float(np.mean(x))
        return [m] * n_win, 0.0, 0.0
    edges = np.linspace(t0, t1, num=n_win + 1)
    out: list[float] = []
    for i in range(n_win):
        if i == n_win - 1:
            m = (t >= edges[i]) & (t <= edges[i + 1])
        else:
            m = (t >= edges[i]) & (t < edges[i + 1])
        out.append(float(np.mean(x[m])) if np.any(m) else float(np.mean(x)))
    slope = float(out[-1] - out[0]) if out else 0.0
    drift = float(np.mean(np.abs(np.diff(out)))) if len(out) > 1 else 0.0
    return out, slope, drift


def _peak_count(x: np.ndarray) -> float:
    if x.size < 3:
        return 0.0
    thr = float(np.mean(x) + 0.5 * np.std(x))
    c = 0
    for i in range(1, x.size - 1):
        if x[i] >= x[i - 1] and x[i] >= x[i + 1] and x[i] >= thr:
            c += 1
    return float(c)


def _autocorr_peak(x: np.ndarray) -> float:
    if x.size < 8:
        return 0.0
    y = x.astype(np.float64) - float(np.mean(x))
    den = float(np.dot(y, y))
    if den <= 1e-12:
        return 0.0
    ac = np.correlate(y, y, mode="full")[x.size - 1 :] / den
    hi = min(len(ac), 60)
    if hi <= 3:
        return 0.0
    return float(np.clip(np.max(ac[2:hi]), 0.0, 1.0))


def _nearest_beat_dist(peak_t: np.ndarray, beat_t: np.ndarray) -> np.ndarray:
    if peak_t.size == 0 or beat_t.size == 0:
        return np.zeros((0,), dtype=np.float64)
    bt = np.sort(beat_t.astype(np.float64))
    out = np.zeros_like(peak_t, dtype=np.float64)
    for i, t in enumerate(peak_t.tolist()):
        j = int(np.searchsorted(bt, t))
        cand = []
        if j > 0:
            cand.append(abs(t - bt[j - 1]))
        if j < len(bt):
            cand.append(abs(t - bt[j]))
        out[i] = min(cand) if cand else 0.0
    return out


def _offbeat_fraction(peak_t: np.ndarray, beat_t: np.ndarray) -> float:
    if peak_t.size == 0 or beat_t.size < 2:
        return 0.0
    bt = np.sort(beat_t.astype(np.float64))
    off = 0
    used = 0
    for t in peak_t.tolist():
        j = int(np.searchsorted(bt, t))
        if j <= 0 or j >= len(bt):
            continue
        lo, hi = bt[j - 1], bt[j]
        span = hi - lo
        if span <= 1e-6:
            continue
        ph = (t - lo) / span
        used += 1
        if 0.35 <= ph <= 0.65:
            off += 1
    if used == 0:
        return 0.0
    return float(off / used)


def _clip_feats(lma_path: Path, beats_path: Path, n_win: int) -> dict[str, float]:
    lma = _safe_read_csv(lma_path)
    beats = _safe_read_csv(beats_path)
    out: dict[str, float] = {}

    if len(lma) == 0:
        for k in LMA_KEYS:
            for i in range(n_win):
                out[f"{k}_win{i+1}"] = 0.0
            out[f"{k}_slope"] = 0.0
            out[f"{k}_drift"] = 0.0
            out[f"{k}_peak_count"] = 0.0
            out[f"{k}_change_rate"] = 0.0
        out["motion_periodicity"] = 0.0
    else:
        if "START_TIME_S" in lma.columns and "END_TIME_S" in lma.columns:
            t = 0.5 * (
                lma["START_TIME_S"].to_numpy(dtype=np.float64)
                + lma["END_TIME_S"].to_numpy(dtype=np.float64)
            )
        else:
            t = np.arange(len(lma), dtype=np.float64)
        for k in LMA_KEYS:
            x = lma[k].to_numpy(dtype=np.float64) if k in lma.columns else np.zeros(len(lma), dtype=np.float64)
            wins, slope, drift = _win_means(t=t, x=x, n_win=n_win)
            for i, v in enumerate(wins, start=1):
                out[f"{k}_win{i}"] = float(v)
            out[f"{k}_slope"] = float(slope)
            out[f"{k}_drift"] = float(drift)
            out[f"{k}_peak_count"] = _peak_count(x)
            out[f"{k}_change_rate"] = float(np.mean(np.abs(np.diff(x)))) if x.size > 1 else 0.0
        x_sud = lma["EFFORT_TIME_SUDDEN"].to_numpy(dtype=np.float64) if "EFFORT_TIME_SUDDEN" in lma.columns else np.zeros(len(lma), dtype=np.float64)
        out["motion_periodicity"] = _autocorr_peak(x_sud)

    beat_t = beats["time_s"].to_numpy(dtype=np.float64) if "time_s" in beats.columns else np.zeros((0,), dtype=np.float64)
    if len(lma) > 0:
        x_sud = lma["EFFORT_TIME_SUDDEN"].to_numpy(dtype=np.float64) if "EFFORT_TIME_SUDDEN" in lma.columns else np.zeros(len(lma), dtype=np.float64)
        if "START_TIME_S" in lma.columns and "END_TIME_S" in lma.columns:
            t = 0.5 * (
                lma["START_TIME_S"].to_numpy(dtype=np.float64)
                + lma["END_TIME_S"].to_numpy(dtype=np.float64)
            )
        else:
            t = np.arange(len(lma), dtype=np.float64)
        thr = float(np.mean(x_sud) + 0.5 * np.std(x_sud))
        peak_idx = []
        for i in range(1, len(x_sud) - 1):
            if x_sud[i] >= x_sud[i - 1] and x_sud[i] >= x_sud[i + 1] and x_sud[i] >= thr:
                peak_idx.append(i)
        peak_t = t[np.array(peak_idx, dtype=int)] if peak_idx else np.zeros((0,), dtype=np.float64)
    else:
        peak_t = np.zeros((0,), dtype=np.float64)

    if beat_t.size < 2:
        out["beat_motion_mean_dist_s"] = 0.0
        out["beat_motion_alignment"] = 0.0
        out["beat_sync_tightness"] = 0.0
        out["beat_offbeat_tendency"] = 0.0
        out["beat_accent_consistency"] = 0.0
        out["beat_interval_cv"] = 0.0
    else:
        ibi = np.diff(np.sort(beat_t))
        cv = float(np.std(ibi) / (np.mean(ibi) + 1e-8))
        d = _nearest_beat_dist(peak_t=peak_t, beat_t=beat_t)
        md = float(np.mean(d)) if d.size else 0.0
        align = float(np.exp(-md / 0.10))
        tight = float(np.mean(d <= 0.08)) if d.size else 0.0
        offb = _offbeat_fraction(peak_t=peak_t, beat_t=beat_t)
        acc = 0.0
        if d.size > 1:
            acc = float(np.clip(1.0 - (np.std(d) / 0.10), 0.0, 1.0))

        out["beat_motion_mean_dist_s"] = md
        out["beat_motion_alignment"] = align
        out["beat_sync_tightness"] = tight
        out["beat_offbeat_tendency"] = offb
        out["beat_accent_consistency"] = acc
        out["beat_interval_cv"] = cv

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="outputs/m2m_train")
    ap.add_argument("--n-windows", type=int, default=4)
    ap.add_argument("--out-csv", default="")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    ddir = (root / args.dataset_dir).resolve() if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    meta_path = ddir / "meta.csv"
    x_path = ddir / "X_motion.csv"
    feat_dir = ddir / "features"
    if not meta_path.exists() or not x_path.exists() or not feat_dir.exists():
        raise FileNotFoundError("dataset-dir must contain meta.csv, X_motion.csv, and features/")

    meta = pd.read_csv(meta_path)
    x = pd.read_csv(x_path)
    if len(meta) != len(x):
        raise RuntimeError(f"meta/X rows mismatch: {len(meta)} vs {len(x)}")
    if "stem" not in meta.columns:
        raise RuntimeError("meta.csv must include stem")

    rows = []
    miss = 0
    n_win = int(max(2, args.n_windows))
    for r in meta.itertuples(index=False):
        stem = str(getattr(r, "stem"))
        lp = feat_dir / f"{stem}_lma.csv"
        bp = feat_dir / f"{stem}_beats.csv"
        if not lp.exists() or not bp.exists():
            miss += 1
        rows.append(_clip_feats(lp, bp, n_win=n_win))

    extra = pd.DataFrame(rows)
    out = pd.concat([x.reset_index(drop=True), extra.reset_index(drop=True)], axis=1)
    out_path = Path(args.out_csv) if args.out_csv else (ddir / "X_motion_temporal.csv")
    out.to_csv(out_path, index=False)
    print(f"[done] wrote {len(out)} rows, {len(out.columns)} cols -> {out_path}")
    print(f"[info] missing feature files for {miss} rows")


if __name__ == "__main__":
    main()
