# BeatExtraction.py
from __future__ import annotations
from ..ml.ml_helpers import refine_events_with_tempo

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import numpy as np

# Low-level helpers
from .helpers import (
    _robust_norm,
    _hysteresis_mask,
    _estimate_period_from_autocorr,
    _nms_basic,
    _valid_idx,
    _local_minima,
    _local_maxima,
    _prominence_and_area,
    _grad,
)

# Cue-level functions
from .cues import (
    _body_speed_trace,
    _cue_deceleration,
    _cue_pelvis_drop,
    _cue_foot_contact,
    _cue_global_accel,
    _cue_reversal,
    _leg_length,
)

# -----------------------------
# Parameter sets
# -----------------------------

@dataclass
class BeatParamsV1:
    # smoothing & thresholds
    smooth_win: int = 5
    score_threshold: float = 0.6
    nms_separation_s: float = 0.12
    # cue weights
    w_decel: float  = 0.40
    w_pelvis: float = 0.30
    w_foot: float   = 0.30
    # foot-contact specifics
    foot_speed_q: float = 0.20
    ground_q: float     = 0.05
    use_leg_norm: bool  = True
    # score post-processing
    adaptive_nms: bool   = True
    hysteresis_low_fac: float = 0.8  # low = 0.8 * score_threshold
    phase_snap_radius: int = 3       # ±frames to search for better alignment
    snap_recheck_radius: int = 2     # (used only in v2 hard recheck)


@dataclass
class BeatParamsV2(BeatParamsV1):
    # extra cues
    w_accel: float    = 0.20
    w_reversal: float = 0.20
    # event filtering
    prom_window_s: float = 0.12
    min_prominence: float = 0.10
    min_area: float = 0.10


# -----------------------------
# Extractors
# -----------------------------

def extract_beats_v1(
    positions: np.ndarray,              # (T, N, 3)
    fps: float,
    joint_indices: Iterable[int],
    params: Optional[BeatParamsV1] = None,
    pelvis_idx: Optional[int] = None,
    left_foot_idx: Optional[int] = None,
    right_foot_idx: Optional[int] = None,
) -> Dict[str, np.ndarray]:
    """v1: decel + pelvis-drop + foot contacts + adaptive NMS + optional phase snap."""
    if params is None:
        params = BeatParamsV1()

    positions = np.asarray(positions, dtype=float)
    assert positions.ndim == 3 and positions.shape[2] == 3
    T, N, _ = positions.shape
    if T == 0 or fps <= 0:
        return {
            "beat_score":     np.zeros(0),
            "candidate_mask": np.zeros(0, bool),
            "events_idx":     np.array([], int),
            "C_decel":        np.zeros(0),
            "C_pelvis":       np.zeros(0),
            "C_foot":         np.zeros(0),
        }

    dt = 1.0 / float(fps)

    # Clamp joint subset to valid range
    Jidx_all = np.asarray(list(joint_indices), dtype=int)
    Jidx = Jidx_all[(Jidx_all >= 0) & (Jidx_all < N)]
    if Jidx.size == 0:
        Jidx = np.arange(N, dtype=int)
    sel = positions[:, Jidx, :]

    # Actor-invariant scale
    leg_scale = _leg_length(positions, pelvis_idx, left_foot_idx, right_foot_idx) if params.use_leg_norm else 1.0

    # Cues
    speed    = _body_speed_trace(sel, dt, params.smooth_win)
    C_decel  = _cue_deceleration(speed, dt)
    C_pelvis = _cue_pelvis_drop(positions, pelvis_idx, dt, params.smooth_win)
    C_lfoot  = _cue_foot_contact(
        positions, left_foot_idx, dt, params.smooth_win,
        params.foot_speed_q, params.ground_q, leg_scale,
    )
    C_rfoot  = _cue_foot_contact(
        positions, right_foot_idx, dt, params.smooth_win,
        params.foot_speed_q, params.ground_q, leg_scale,
    )
    C_foot   = np.maximum(C_lfoot, C_rfoot)

    # Fuse
    score = (
        params.w_decel  * C_decel +
        params.w_pelvis * C_pelvis +
        params.w_foot   * C_foot
    )
    score = _robust_norm(score)

    # Hysteresis mask (soft gating for plots/diagnostics)
    thr_hi = params.score_threshold
    thr_lo = params.score_threshold * params.hysteresis_low_fac
    mask_hyst = _hysteresis_mask(score, thr_hi, thr_lo)

    # Adaptive NMS
    nms_sep = params.nms_separation_s
    if params.adaptive_nms:
        estT = _estimate_period_from_autocorr(score, fps)
        if estT is not None:
            nms_sep = max(0.08, min(0.25, 0.5 * estT))

    events_idx = _nms_basic(score, fps, nms_sep)

    # Optional phase snap to nearest foot y-min/jerk within radius (no hard drop here)
    if params.phase_snap_radius > 0 and (_valid_idx(left_foot_idx, N) or _valid_idx(right_foot_idx, N)) and events_idx.size:
        snapped = []
        for ei in events_idx:
            # choose foot with higher cue at ei
            use_left = (C_lfoot[ei] >= C_rfoot[ei])
            fidx = left_foot_idx if use_left else right_foot_idx
            if not _valid_idx(fidx, N):
                snapped.append(int(ei))
                continue
            y = positions[:, int(fidx), 1]
            vy = _grad(y, dt)
            ay = _grad(vy, dt)
            jy = np.abs(_grad(ay, dt))
            lo = max(0, int(ei) - params.phase_snap_radius)
            hi = min(T, int(ei) + params.phase_snap_radius + 1)
            win = np.arange(lo, hi)
            mins = _local_minima(y)[lo:hi]
            if mins.any():
                cand = win[mins]
                snapped.append(int(cand[np.argmin(np.abs(cand - ei))]))
            else:
                snapped.append(int(lo + np.argmax(jy[lo:hi])))
        events_idx = np.array(sorted(set(snapped)), dtype=int)

    return {
        "beat_score":     score,
        "candidate_mask": mask_hyst,
        "events_idx":     events_idx,
        "C_decel":        C_decel,
        "C_pelvis":       C_pelvis,
        "C_foot":         C_foot,
    }


def extract_beats_v2(
    positions: np.ndarray,           # (T, N, 3)
    fps: float,
    joint_indices: Iterable[int],
    params: Optional[BeatParamsV2] = None,
    pelvis_idx: Optional[int] = None,
    left_foot_idx: Optional[int] = None,
    right_foot_idx: Optional[int] = None,
) -> Dict[str, np.ndarray]:
    """
    v2: v1 + global acceleration and reversal cues, stricter event gating
    (hysteresis + prominence/area), adaptive NMS, phase-snap, and hard recheck.
    """
    if params is None:
        params = BeatParamsV2()

    positions = np.asarray(positions, dtype=float)
    assert positions.ndim == 3 and positions.shape[2] == 3
    T, N, _ = positions.shape
    if T == 0 or fps <= 0:
        return {
            "beat_score":     np.zeros(0),
            "candidate_mask": np.zeros(0, bool),
            "events_idx":     np.array([], int),
            "C_decel":        np.zeros(0),
            "C_pelvis":       np.zeros(0),
            "C_foot":         np.zeros(0),
            "C_accel":        np.zeros(0),
            "C_reversal":     np.zeros(0),
        }

    dt = 1.0 / float(fps)

    # Clamp joint subset to valid range
    Jidx_all = np.asarray(list(joint_indices), dtype=int)
    Jidx = Jidx_all[(Jidx_all >= 0) & (Jidx_all < N)]
    if Jidx.size == 0:
        Jidx = np.arange(N, dtype=int)
    sel = positions[:, Jidx, :]

    # Actor-invariant scale
    leg_scale = _leg_length(positions, pelvis_idx, left_foot_idx, right_foot_idx) if params.use_leg_norm else 1.0

    # Cues
    speed    = _body_speed_trace(sel, dt, params.smooth_win)
    C_decel  = _cue_deceleration(speed, dt)
    C_pelvis = _cue_pelvis_drop(positions, pelvis_idx, dt, params.smooth_win)
    C_lfoot  = _cue_foot_contact(
        positions, left_foot_idx, dt, params.smooth_win,
        params.foot_speed_q, params.ground_q, leg_scale,
    )
    C_rfoot  = _cue_foot_contact(
        positions, right_foot_idx, dt, params.smooth_win,
        params.foot_speed_q, params.ground_q, leg_scale,
    )
    C_foot   = np.maximum(C_lfoot, C_rfoot)

    C_accel  = _cue_global_accel(sel, dt, params.smooth_win)
    C_rev    = _cue_reversal(sel, dt, params.smooth_win)

    # Fuse
    score = (
        params.w_decel    * C_decel +
        params.w_pelvis   * C_pelvis +
        params.w_foot     * C_foot +
        params.w_accel    * C_accel +
        params.w_reversal * C_rev
    )
    score = _robust_norm(score)

    # Hysteresis
    thr_hi = params.score_threshold
    thr_lo = params.score_threshold * params.hysteresis_low_fac
    mask_hyst = _hysteresis_mask(score, thr_hi, thr_lo)

    # Prominence/area filtering on local maxima that pass hysteresis
    prom_win = max(1, int(round(params.prom_window_s * fps)))
    cand_idx = np.where(_local_maxima(score) & mask_hyst)[0]
    keep = []
    for i in cand_idx:
        prom, area = _prominence_and_area(score, int(i), prom_win)
        if (prom >= params.min_prominence) and (area >= params.min_area):
            keep.append(int(i))
    cand_idx = np.array(keep, dtype=int)

    # Adaptive NMS
    nms_sep = params.nms_separation_s
    if params.adaptive_nms:
        estT = _estimate_period_from_autocorr(score, fps)
        if estT is not None:
            nms_sep = max(0.08, min(0.25, 0.5 * estT))

    if cand_idx.size:
        tmp = np.zeros_like(score)
        tmp[cand_idx] = score[cand_idx]
        events_idx = _nms_basic(tmp, fps, nms_sep)
    else:
        events_idx = np.array([], dtype=int)

    # Phase snap + hard recheck
    if params.phase_snap_radius > 0 and (_valid_idx(left_foot_idx, N) or _valid_idx(right_foot_idx, N)) and events_idx.size:
        snapped = []
        for ei in events_idx:
            use_left = (C_lfoot[ei] >= C_rfoot[ei])
            fidx = left_foot_idx if use_left else right_foot_idx
            if not _valid_idx(fidx, N):
                snapped.append(int(ei))
                continue
            y = positions[:, int(fidx), 1]
            vy = _grad(y, dt)
            ay = _grad(vy, dt)
            jy = np.abs(_grad(ay, dt))
            lo = max(0, int(ei) - params.phase_snap_radius)
            hi = min(T, int(ei) + params.phase_snap_radius + 1)
            win = np.arange(lo, hi)
            mins = _local_minima(y)[lo:hi]
            if mins.any():
                cand = win[mins]
                snapped.append(int(cand[np.argmin(np.abs(cand - ei))]))
            else:
                snapped.append(int(lo + np.argmax(jy[lo:hi])))
        events_idx = np.array(sorted(set(snapped)), dtype=int)

        # hard recheck: require threshold around snapped location
        if events_idx.size:
            r = int(max(0, params.snap_recheck_radius))
            strong = []
            for ei in events_idx:
                lo = max(0, ei - r)
                hi = min(T, ei + r + 1)
                if np.max(score[lo:hi]) >= thr_hi:
                    strong.append(int(ei))
            events_idx = np.array(strong, dtype=int)

        events_idx = refine_events_with_tempo(
            events_idx=events_idx,
            score=score,  # fused cue score
            fps=fps,
            max_drift_frames=3,
            min_events=3,
            verbose=False,
        )
    return {
        "beat_score":     score,
        "candidate_mask": mask_hyst,
        "events_idx":     events_idx,
        "C_decel":        C_decel,
        "C_pelvis":       C_pelvis,
        "C_foot":         C_foot,
        "C_accel":        C_accel,
        "C_reversal":     C_rev,
    }
