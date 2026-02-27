"""ML / post-processing helpers used by the CLI scripts.

The repository evolved over time, so some scripts expect these helpers to exist
as a standalone module.

Functions here are intentionally dependency-light (numpy only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np


def _as_int_sorted_unique(x: Iterable[int]) -> np.ndarray:
    a = np.asarray(list(x), dtype=int)
    if a.size == 0:
        return np.array([], dtype=int)
    a = np.unique(a)
    a.sort()
    return a


def probs_to_events(prob: np.ndarray, thr: float) -> np.ndarray:
    """Convert per-frame probabilities into discrete event indices.

    Logic:
      - threshold → binary mask
      - group consecutive positives into segments
      - choose frame with max prob in each segment as an event

    This mirrors the helper in beat_refiner_apply.py, so ml_helpers can be used
    standalone if needed.
    """
    prob = np.asarray(prob, dtype=float)
    if prob.ndim != 1:
        prob = prob.reshape(-1)
    T = prob.shape[0]
    if T == 0:
        return np.zeros(0, dtype=int)

    mask = prob >= float(thr)
    padded = np.r_[False, mask, False]
    changes = np.diff(padded.astype(int))
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]

    events: list[int] = []
    for s, e in zip(starts, ends):
        if e <= s:
            continue
        seg = prob[s:e]
        events.append(int(s + np.argmax(seg)))

    return _as_int_sorted_unique(events)


def combine_rule_and_ml_events(
    events_rule: Iterable[int],
    prob: np.ndarray,
    fps: float,
    snap_radius_s: float = 0.12,
    thr_ml: float = 0.5,
    min_sep_s: float = 0.08,
) -> np.ndarray:
    """Hybrid events = rule anchors snapped to ML peaks + extra ML peaks.

    Parameters
    - events_rule: indices from rule-based BeatExtraction
    - prob:        per-frame ML probability (length T)
    - fps:         motion fps
    - snap_radius_s: how far (seconds) to move a rule anchor to the best nearby ML peak
    - thr_ml:      ML probability threshold for adding ML-only peaks
    - min_sep_s:   minimum separation between final events

    Returns
    - sorted unique event indices
    """
    prob = np.asarray(prob, dtype=float)
    if prob.ndim != 1:
        prob = prob.reshape(-1)
    T = prob.shape[0]
    if T == 0:
        return np.zeros(0, dtype=int)

    events_rule = _as_int_sorted_unique(events_rule)

    snap_r = int(round(float(snap_radius_s) * float(fps)))
    snap_r = max(0, snap_r)

    # 1) Snap rule events to best ML peak in a window
    snapped: list[int] = []
    for e in events_rule.tolist():
        lo = max(0, e - snap_r)
        hi = min(T, e + snap_r + 1)
        if hi <= lo:
            continue
        best = int(lo + np.argmax(prob[lo:hi]))
        # If the best peak is very weak, keep the original anchor.
        # (This makes the hybrid mode still usable if the ML model misses.)
        if prob[best] < float(thr_ml):
            best = int(e)
        snapped.append(best)

    events_snapped = _as_int_sorted_unique(snapped)

    # 2) Add ML-only events from prob segments above threshold
    events_ml = probs_to_events(prob, float(thr_ml))

    # 3) Merge + enforce min separation by keeping the stronger prob
    min_sep = int(round(float(min_sep_s) * float(fps)))
    min_sep = max(1, min_sep)

    all_e = _as_int_sorted_unique(np.concatenate([events_snapped, events_ml]))

    kept: list[int] = []
    for e in all_e.tolist():
        if not kept:
            kept.append(e)
            continue
        if e - kept[-1] < min_sep:
            # keep whichever has higher prob
            if prob[e] > prob[kept[-1]]:
                kept[-1] = e
        else:
            kept.append(e)

    return _as_int_sorted_unique(kept)


def refine_events_with_tempo(
    events_idx: Iterable[int],
    score: np.ndarray,
    fps: float,
    max_drift_frames: int = 3,
    min_events: int = 3,
    verbose: bool = False,
) -> np.ndarray:
    """Tempo-aware refinement.

    Goal: keep a roughly uniform beat grid while snapping each beat to the
    strongest nearby score peak.

    This is a lightweight version (no heavy DP):
      1) fit a line event_frame ~ a + b*k (k = beat number)
      2) use predicted frames from that fit
      3) snap each predicted frame within ±max_drift_frames to the best peak

    If too few events are provided, returns input unchanged.
    """
    score = np.asarray(score, dtype=float)
    if score.ndim != 1:
        score = score.reshape(-1)
    T = score.shape[0]

    ev = _as_int_sorted_unique(events_idx)
    if ev.size < int(min_events) or ev.size < 2 or T == 0:
        return ev

    # Clamp
    ev = ev[(ev >= 0) & (ev < T)]
    if ev.size < int(min_events):
        return ev

    k = np.arange(ev.size, dtype=float)

    # Robust-ish linear fit: use polyfit, then re-fit after removing gross outliers
    b, a = np.polyfit(k, ev.astype(float), 1)  # ev ≈ a + b*k
    if not np.isfinite(b) or b <= 0.5:
        return ev

    pred = a + b * k
    resid = ev - pred
    mad = np.median(np.abs(resid - np.median(resid))) + 1e-9
    good = np.abs(resid) <= (3.5 * mad)

    if good.sum() >= int(min_events) and good.sum() < ev.size:
        k2 = k[good]
        ev2 = ev[good].astype(float)
        b, a = np.polyfit(k2, ev2, 1)
        if not np.isfinite(b) or b <= 0.5:
            return ev
        pred = a + b * k

    drift = int(max(0, max_drift_frames))

    snapped: list[int] = []
    for p in pred:
        c = int(round(p))
        lo = max(0, c - drift)
        hi = min(T, c + drift + 1)
        if hi <= lo:
            continue
        best = int(lo + np.argmax(score[lo:hi]))
        snapped.append(best)

    out = _as_int_sorted_unique(snapped)

    if verbose:
        period_s = float(b) / float(fps) if fps > 0 else float("nan")
        print(f"[tempo] refined events: in={ev.size}, out={out.size}, fitted period≈{b:.2f} frames ({period_s:.3f}s)")

    return out


def subdivide_events_uniform(events_idx: Iterable[int], factor: int, T: int) -> np.ndarray:
    """Uniformly subdivide intervals between events.

    Example:
      events=[0, 10], factor=2 -> [0, 5, 10]
      events=[0, 10], factor=4 -> [0, 2, 5, 8, 10]  (after rounding)

    Returns sorted unique indices clamped to [0, T-1].
    """
    ev = _as_int_sorted_unique(events_idx)
    factor = int(max(1, factor))
    T = int(T)
    if ev.size < 2 or factor == 1:
        return ev[(ev >= 0) & (ev < T)]

    out: list[int] = [int(ev[0])]
    for i in range(ev.size - 1):
        a = int(ev[i])
        b = int(ev[i + 1])
        if b <= a:
            continue
        # internal subdivision points
        for k in range(1, factor):
            t = a + (b - a) * (k / factor)
            out.append(int(round(t)))
        out.append(b)

    # keep order, remove duplicates
    cleaned: list[int] = []
    seen = set()
    for e in out:
        e = int(max(0, min(T - 1, e)))
        if e not in seen:
            seen.add(e)
            cleaned.append(e)

    return np.asarray(cleaned, dtype=int)
