#!/usr/bin/env python3
"""
infer_prototype_prompt.py

Inference for motion_prototype_prompt_v2 bundle:
- Input: lma.csv + beats.csv
- Output: top-k prototype probabilities + prototype-conditioned prompts
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import semantic_prompt_from_motion as sem
from predict_prompt_and_generate import compute_motion_features


LMA_KEYS = [
    "BODY",
    "EFFORT_WEIGHT_STRONG",
    "EFFORT_TIME_SUDDEN",
    "EFFORT_FLOW_BOUND",
    "SPACE",
]


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
    return float(off / used) if used > 0 else 0.0


def compute_temporal_features(lma_df: pd.DataFrame, beats_df: pd.DataFrame, n_win: int = 4) -> dict[str, float]:
    out: dict[str, float] = {}
    if len(lma_df) == 0:
        for k in LMA_KEYS:
            for i in range(n_win):
                out[f"{k}_win{i+1}"] = 0.0
            out[f"{k}_slope"] = 0.0
            out[f"{k}_drift"] = 0.0
            out[f"{k}_peak_count"] = 0.0
            out[f"{k}_change_rate"] = 0.0
        out["motion_periodicity"] = 0.0
    else:
        if "START_TIME_S" in lma_df.columns and "END_TIME_S" in lma_df.columns:
            t = 0.5 * (
                pd.to_numeric(lma_df["START_TIME_S"], errors="coerce").to_numpy(dtype=np.float64)
                + pd.to_numeric(lma_df["END_TIME_S"], errors="coerce").to_numpy(dtype=np.float64)
            )
        else:
            t = np.arange(len(lma_df), dtype=np.float64)

        for k in LMA_KEYS:
            x = pd.to_numeric(lma_df[k], errors="coerce").to_numpy(dtype=np.float64) if k in lma_df.columns else np.zeros(len(lma_df), dtype=np.float64)
            x = np.nan_to_num(x, nan=0.0)
            wins, slope, drift = _win_means(t=t, x=x, n_win=n_win)
            for i, v in enumerate(wins, start=1):
                out[f"{k}_win{i}"] = float(v)
            out[f"{k}_slope"] = float(slope)
            out[f"{k}_drift"] = float(drift)
            out[f"{k}_peak_count"] = _peak_count(x)
            out[f"{k}_change_rate"] = float(np.mean(np.abs(np.diff(x)))) if x.size > 1 else 0.0

        sud = pd.to_numeric(lma_df["EFFORT_TIME_SUDDEN"], errors="coerce").to_numpy(dtype=np.float64) if "EFFORT_TIME_SUDDEN" in lma_df.columns else np.zeros(len(lma_df), dtype=np.float64)
        sud = np.nan_to_num(sud, nan=0.0)
        out["motion_periodicity"] = _autocorr_peak(sud)

    beat_t = pd.to_numeric(beats_df.get("time_s", pd.Series([], dtype=float)), errors="coerce").to_numpy(dtype=np.float64)
    beat_t = beat_t[np.isfinite(beat_t)]
    if beat_t.size < 2:
        out["beat_motion_mean_dist_s"] = 0.0
        out["beat_motion_alignment"] = 0.0
        out["beat_sync_tightness"] = 0.0
        out["beat_offbeat_tendency"] = 0.0
        out["beat_accent_consistency"] = 0.0
        out["beat_interval_cv"] = 0.0
        return out

    if len(lma_df) > 0:
        sud = pd.to_numeric(lma_df.get("EFFORT_TIME_SUDDEN", pd.Series(np.zeros(len(lma_df)))), errors="coerce").to_numpy(dtype=np.float64)
        sud = np.nan_to_num(sud, nan=0.0)
        if "START_TIME_S" in lma_df.columns and "END_TIME_S" in lma_df.columns:
            t = 0.5 * (
                pd.to_numeric(lma_df["START_TIME_S"], errors="coerce").to_numpy(dtype=np.float64)
                + pd.to_numeric(lma_df["END_TIME_S"], errors="coerce").to_numpy(dtype=np.float64)
            )
        else:
            t = np.arange(len(lma_df), dtype=np.float64)
        thr = float(np.mean(sud) + 0.5 * np.std(sud))
        peak_idx = []
        for i in range(1, len(sud) - 1):
            if sud[i] >= sud[i - 1] and sud[i] >= sud[i + 1] and sud[i] >= thr:
                peak_idx.append(i)
        peak_t = t[np.array(peak_idx, dtype=int)] if peak_idx else np.zeros((0,), dtype=np.float64)
    else:
        peak_t = np.zeros((0,), dtype=np.float64)

    ibi = np.diff(np.sort(beat_t))
    cv = float(np.std(ibi) / (np.mean(ibi) + 1e-8))
    d = _nearest_beat_dist(peak_t=peak_t, beat_t=beat_t)
    md = float(np.mean(d)) if d.size else 0.0
    align = float(np.exp(-md / 0.10))
    tight = float(np.mean(d <= 0.08)) if d.size else 0.0
    offb = _offbeat_fraction(peak_t=peak_t, beat_t=beat_t)
    acc = float(np.clip(1.0 - (np.std(d) / 0.10), 0.0, 1.0)) if d.size > 1 else 0.0

    out["beat_motion_mean_dist_s"] = md
    out["beat_motion_alignment"] = align
    out["beat_sync_tightness"] = tight
    out["beat_offbeat_tendency"] = offb
    out["beat_accent_consistency"] = acc
    out["beat_interval_cv"] = cv
    return out


def build_semantic_prompt(lma_df: pd.DataFrame, beats_df: pd.DataFrame, train_stats: dict[str, tuple[float, float]]) -> tuple[str, dict[str, float], dict[str, str], float]:
    lma_feats = sem.compute_lma_features(lma_df)
    tcol = sem._find_time_col(beats_df)
    beat_times = pd.to_numeric(beats_df[tcol], errors="coerce").to_numpy(dtype=float)
    beat_feats = sem.compute_beat_features(beat_times)

    raw = {
        "BODY_mean": float(lma_feats.get("BODY_mean", 0.0)),
        "BODY_std": float(lma_feats.get("BODY_std", 0.0)),
        "EFFORT_WEIGHT_STRONG_mean": float(lma_feats.get("EFFORT_WEIGHT_STRONG_mean", 0.0)),
        "EFFORT_WEIGHT_STRONG_std": float(lma_feats.get("EFFORT_WEIGHT_STRONG_std", 0.0)),
        "EFFORT_TIME_SUDDEN_mean": float(lma_feats.get("EFFORT_TIME_SUDDEN_mean", 0.0)),
        "EFFORT_TIME_SUDDEN_std": float(lma_feats.get("EFFORT_TIME_SUDDEN_std", 0.0)),
        "EFFORT_FLOW_BOUND_mean": float(lma_feats.get("EFFORT_FLOW_BOUND_mean", 0.0)),
        "EFFORT_FLOW_BOUND_std": float(lma_feats.get("EFFORT_FLOW_BOUND_std", 0.0)),
        "SPACE_mean": float(lma_feats.get("SPACE_mean", 0.0)),
        "SPACE_std": float(lma_feats.get("SPACE_std", 0.0)),
        "tempo_bpm": float(beat_feats.get("tempo_bpm", 120.0)),
        "rhythm_cv": float(beat_feats.get("rhythm_cv", 0.0)),
    }
    norm = sem.normalize_features(raw, train_stats if isinstance(train_stats, dict) else {})
    scores = sem.compute_semantic_scores(norm)
    tags = sem.scores_to_tags(scores)
    bpm = float(beat_feats.get("tempo_bpm", 120.0))
    prompt = sem.generate_prompt(tags, bpm)
    return prompt, scores, tags, bpm


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lma-csv", required=True)
    ap.add_argument("--beats-csv", required=True)
    ap.add_argument("--model-bundle", required=True)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    lma_path = Path(args.lma_csv)
    beats_path = Path(args.beats_csv)
    model_path = Path(args.model_bundle)
    if not lma_path.exists() or not beats_path.exists() or not model_path.exists():
        raise FileNotFoundError("Need existing --lma-csv, --beats-csv, --model-bundle")

    bundle = joblib.load(model_path)
    if str(bundle.get("bundle_type", "")) != "motion_prototype_prompt_v2":
        raise RuntimeError("Unsupported bundle_type. Expected motion_prototype_prompt_v2.")

    lma_df = pd.read_csv(lma_path)
    beats_df = pd.read_csv(beats_path)

    feat = compute_motion_features(lma_df, beats_df)
    feat |= compute_temporal_features(lma_df, beats_df, n_win=4)

    x_cols = list(bundle["x_cols"])
    x = np.zeros((1, len(x_cols)), dtype=np.float32)
    for j, c in enumerate(x_cols):
        v = feat.get(c, 0.0)
        x[0, j] = float(v) if np.isfinite(v) else 0.0

    clf = bundle["classifier"]
    proba = clf.predict_proba(x)[0]
    classes = clf.named_steps["clf"].classes_
    order = np.argsort(-proba)
    topk = int(max(1, min(int(args.top_k), len(order))))

    class_to_name = {int(k): str(v) for k, v in bundle.get("class_to_name", {}).items()}
    name_to_phrase = {str(k): str(v) for k, v in bundle.get("name_to_phrase", {}).items()}
    sem_stats = bundle.get("semantic_train_stats", {})
    base_prompt, sem_scores, sem_tags, bpm = build_semantic_prompt(lma_df, beats_df, sem_stats)

    ranked = []
    for r in range(topk):
        j = int(order[r])
        cid = int(classes[j])
        p = float(proba[j])
        name = class_to_name.get(cid, f"cluster_{cid}")
        phrase = name_to_phrase.get(name, name)
        prompt_proto = base_prompt if phrase in base_prompt else f"{base_prompt}, {phrase}"
        ranked.append(
            {
                "rank": int(r + 1),
                "prototype_id": cid,
                "prototype_name": name,
                "probability": p,
                "prototype_phrase": phrase,
                "prompt": prompt_proto,
            }
        )

    out_dir = Path(args.out_dir) if args.out_dir else (model_path.parent.parent / "inference" / lma_path.stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_bundle": str(model_path),
        "lma_csv": str(lma_path),
        "beats_csv": str(beats_path),
        "base_prompt": base_prompt,
        "bpm": float(bpm),
        "semantic_scores": {k: float(v) for k, v in sem_scores.items()},
        "semantic_tags": {k: str(v) for k, v in sem_tags.items()},
        "topk": ranked,
    }
    (out_dir / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "prompt_top1.txt").write_text(ranked[0]["prompt"] + "\n", encoding="utf-8")
    (out_dir / "prompts_topk.txt").write_text(
        "\n".join([f"{r['rank']}. p={r['probability']:.4f} {r['prototype_name']} -> {r['prompt']}" for r in ranked]) + "\n",
        encoding="utf-8",
    )

    print(f"[done] out_dir={out_dir}")
    print(f"[done] top1={ranked[0]['prototype_name']} p={ranked[0]['probability']:.4f}")
    print(f"[done] prompt_top1={out_dir / 'prompt_top1.txt'}")


if __name__ == "__main__":
    main()
