from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple
import numpy as np

# -----------------------------
# Small utilities
# -----------------------------
# 1D moving average smoother
# Input:
#   x : 1D array (values over time, e.g. speed, height, etc.)
#   k : window size (number of samples to average)
# What:
#   Smooths the signal by replacing each point with the average of its neighbors
#   in a window of size k, with padding at the edges so the output length
#   matches the input length.
# Why:
#   Reduces noise, micro-jitters and spikes so the overall trend of the signal
#   is cleaner and more reliable for later steps (e.g. beat / cue detection).
# Output:
#   1D array of the same length as x, but smoothed.
def _ma1d(x: np.ndarray, k: int) -> np.ndarray:
    k = int(max(1, k))
    x = np.asarray(x, dtype=float)
    if k == 1:
        return x.copy()
    pad = k // 2
    xp = np.pad(x, (pad, pad), mode="edge")
    return np.convolve(xp, np.ones(k) / k, mode="valid")


# 3D moving average smoother (applies _ma1d to each coordinate)
# Input:
#   v : 2D array of shape (T, 3)
#       A sequence of 3D vectors over time (e.g. joint positions: x,y,z per frame).
#   k : window size (number of samples to average).
# What:
#   Smooths each coordinate (x, y, z) of the 3D time series independently
#   using the 1D moving average _ma1d.
# Why:
#   Cleans up noisy 3D trajectories (like joint motion) so downstream features
#   (speed, acceleration, height changes, etc.) are less sensitive to jitter.
# Output:
#   2D array of shape (T, 3) with smoothed 3D vectors.
def _ma3(v: np.ndarray, k: int) -> np.ndarray:
    out = np.empty_like(v, dtype=float)
    out[:, 0] = _ma1d(v[:, 0], k)
    out[:, 1] = _ma1d(v[:, 1], k)
    out[:, 2] = _ma1d(v[:, 2], k)
    return out

# Numerical time derivative (gradient over time)
# Input:
#   x  : array of shape (T,) or (T, ... )
#        Time series data. Can be 1D (e.g. height over time) or multi-dimensional
#        (e.g. positions (T, J, 3), speeds, features over time).
#   dt : float
#        Time step between samples (e.g. 1 / fps).
# What:
#   Approximates the time derivative of x:
#   - For 1D: gives the rate of change per frame (like velocity from position).
#   - For multi-D: does the same along the time axis for every element.
#   Uses forward/backward differences at the ends and central differences inside.
# Why:
#   We often need velocities or accelerations instead of raw positions:
#   - detect when motion speeds up/slows down,
#   - find decelerations, reversals, and other cues that are important for beats.
# Output:
#   g : array with the same shape as x
#       Estimated derivative of x with respect to time.
def _grad(x: np.ndarray, dt: float) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    g = np.empty_like(x, dtype=float)
    if x.ndim == 1:
        n = x.shape[0]
        if n == 1:
            g[0] = 0.0
            return g
        g[0] = (x[1] - x[0]) / dt
        g[-1] = (x[-1] - x[-2]) / dt
        if n > 2:
            g[1:-1] = (x[2:] - x[:-2]) / (2 * dt)
    else:
        n = x.shape[0]
        g[0, ...] = (x[1, ...] - x[0, ...]) / dt
        g[-1, ...] = (x[-1, ...] - x[-2, ...]) / dt
        if n > 2:
            g[1:-1, ...] = (x[2:, ...] - x[:-2, ...]) / (2 * dt)
    return g
# Detect local minima in a 1D signal
# Input:
#   x : 1D array (values over time, e.g. speed, height, energy, etc.)
# What:
#   Marks positions where x goes “down then up”:
#   x[t] is strictly smaller than the previous value and
#   less than or equal to the next value.
#   The first and last elements are never marked (no neighbors on both sides).
# Why:
#   Local minima often correspond to "bottom" moments:
#   - lowest point of a bounce,
#   - end of a downward motion,
#   - valley between two peaks.
#   These can be useful cues for events like foot landing, pelvis lowest points,
#   or turning points in motion.
# Output:
#   m : 1D boolean array, same length as x
#       True where x has a local minimum, False elsewhere.
def _local_minima(x: np.ndarray) -> np.ndarray:
    m = np.zeros_like(x, dtype=bool)
    if x.shape[0] >= 3:
        m[1:-1] = (x[1:-1] < x[:-2]) & (x[1:-1] <= x[2:])
    return m


# Detect local maxima in a 1D signal
# Input:
#   x : 1D array (values over time)
# What:
#   Marks positions where x goes “up then down”:
#   x[t] is strictly larger than the previous value and
#   greater than or equal to the next value.
#   The first and last elements are never marked (no neighbors on both sides).
# Why:
#   Local maxima correspond to "top" moments:
#   - peak of a jump,
#   - highest speed,
#   - crest of a wave in any feature.
#   These peaks are key candidates for beat-like events or motion accents.
# Output:
#   m : 1D boolean array, same length as x
#       True where x has a local maximum, False elsewhere.
def _local_maxima(x: np.ndarray) -> np.ndarray:
    m = np.zeros_like(x, dtype=bool)
    if x.shape[0] >= 3:
        m[1:-1] = (x[1:-1] > x[:-2]) & (x[1:-1] >= x[2:])
    return m
# Robust normalization to [0, 1] using percentiles
# Input:
#   x  : array of any shape (e.g. cue values over time)
#   lo : lower percentile (default 5.0)
#   hi : upper percentile (default 95.0)
#   eps: small threshold to avoid division by zero
# What:
#   Scales the values in x so that:
#   - the lo-th percentile maps to 0,
#   - the hi-th percentile maps to 1,
#   and everything in between is linearly mapped to [0, 1].
#   Values below the lo-th percentile are clipped to 0,
#   and values above the hi-th percentile are clipped to 1.
# Why:
#   This makes different cues comparable and bounded, while being robust
#   to outliers. Extreme spikes won’t dominate the scaling because we
#   use percentiles instead of min/max. Great for combining cues or
#   thresholding them in a stable way.
# Output:
#   y : array of same shape as x
#       Normalized values in the range [0, 1].
def _robust_norm(x: np.ndarray, lo: float = 5.0, hi: float = 95.0, eps: float = 1e-9) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return x.copy()
    a, b = np.percentile(x, [lo, hi])
    if b - a < eps:
        return np.zeros_like(x, dtype=float)
    y = (x - a) / (b - a)
    return np.clip(y, 0.0, 1.0)
# Non-maximum suppression (NMS) on a 1D score over time
# Input:
#   score     : 1D array of per-frame scores (e.g. beat strength per frame).
#   fps       : frames per second of the motion.
#   min_sep_s : minimum allowed separation between picked peaks, in seconds.
# What:
#   1) Finds all local maxima in the score (candidate events).
#   2) Sorts them from highest score to lowest.
#   3) Greedily keeps the strongest peaks, and suppresses (removes) any
#      other peaks within a time window of ± min_sep_s around each kept peak.
#   The window size is converted from seconds to frames using fps.
# Why:
#   Raw peak detection often produces many nearby peaks around the same
#   true event (e.g. a footstep). NMS cleans this up by:
#   - keeping only the strongest peak in a neighborhood,
#   - enforcing a minimum time gap between detected events,
#   so we get a clearer, more regular sequence of beats.
# Output:
#   picked_idx : 1D array of int
#                Sorted frame indices of the selected peaks after suppression.
def _nms_basic(score: np.ndarray, fps: float, min_sep_s: float) -> np.ndarray:
    idx = np.where(_local_maxima(score))[0]
    if idx.size == 0:
        return idx
    order = idx[np.argsort(score[idx])[::-1]]
    taken = np.zeros(score.shape[0], dtype=bool)
    win = max(1, int(round(float(min_sep_s) * float(fps))))
    picked = []
    for i in order:
        if not taken[i]:
            picked.append(i)
            lo, hi = max(0, i - win), min(score.shape[0], i + win + 1)
            taken[lo:hi] = True
    return np.array(sorted(picked), dtype=int)
# Hysteresis thresholding on a 1D score
# Input:
#   score  : 1D array of values over time (e.g. cue strength per frame).
#   thr_hi : high threshold for turning "on".
#   thr_lo : low threshold for turning "off" (thr_lo <= thr_hi).
# What:
#   Produces a boolean mask that is True in "active" regions and False elsewhere.
#   - The mask switches from False -> True only when score >= thr_hi.
#   - Once "on", it stays True until score drops below thr_lo.
#   This creates a hysteresis effect: you need a strong score to start an
#   active region, but a weaker score is enough to keep it going.
# Why:
#   Avoids flickering around a single threshold when the score is noisy or
#   hovers near the boundary. This gives more stable on/off segments which
#   are easier to interpret as continuous events (e.g. a stance phase, high
#   energy segment, or reliable beat region).
# Output:
#   m : 1D boolean array, same length as score
#       True where the signal is considered "on"/active, False otherwise.
def _hysteresis_mask(score: np.ndarray, thr_hi: float, thr_lo: float) -> np.ndarray:
    score = np.asarray(score, dtype=float)
    m = np.zeros_like(score, dtype=bool)
    on = False
    for i, s in enumerate(score):
        if not on and s >= thr_hi:
            on = True
        elif on and s < thr_lo:
            on = False
        m[i] = on
    return m
# Peak prominence and local area around a given index
# Input:
#   x      : 1D array (e.g. a cue or score over time).
#   i      : int, index of the candidate peak in x.
#   radius : int, half-window size around the peak (in frames).
# What:
#   Looks at a local window [i - radius, i + radius] around the peak and:
#   - Prominence (prom):
#       How much higher the peak x[i] is compared to the local "baseline".
#       The baseline is approximated from the minimum values in the window
#       and its edges. Higher prominence = a more standout / salient peak.
#   - Area (area):
#       The area under the curve in that window, after clipping negatives
#       to zero. This measures how much "mass" or energy the signal has
#       around that peak, not just its single-frame height.
# Why:
#   Not all peaks are equally important. Some are small ripples, others are
#   big and wide bumps. Using prominence and area helps rank or filter peaks
#   so we focus on strong, meaningful events for beats or motion accents.
# Output:
#   (prom, area) : tuple of floats
#       prom : peak prominence relative to local baseline.
#       area : local area under x around the peak.
def _prominence_and_area(x: np.ndarray, i: int, radius: int) -> Tuple[float, float]:
    lo, hi = max(0, i - radius), min(x.shape[0], i + radius + 1)
    win = x[lo:hi]
    peak = x[i]
    base = (np.min(win), np.min([x[lo] if lo > 0 else peak, x[hi - 1] if hi < x.shape[0] else peak]))
    prom = float(peak - max(base))
    area = float(np.trapz(np.clip(win, 0.0, None), dx=1.0))
    return prom, area
# Estimate dominant period (in seconds) from autocorrelation
# Input:
#   x   : 1D array (e.g. a cue or score over time).
#   fps : frames per second of the signal.
# What:
#   Uses autocorrelation to estimate the main repeating time interval
#   (period) in the signal:
#   - If the signal has a rhythmic pattern (e.g. steps, bounces),
#     its autocorrelation will have a clear peak at a lag that
#     corresponds to the typical repetition interval.
#   - This lag (in frames) is converted to seconds using fps.
#   If the signal is too short or no clear peak is found, returns None.
# Why:
#   Gives us an approximate "natural rhythm" or beat period of the motion.
#   This can be used to guide other steps (e.g. expected spacing between
#   beats, filtering out peaks that are too dense or too sparse).
# Output:
#   period_s : float or None
#              Estimated period in seconds if detected, otherwise None.
def _estimate_period_from_autocorr(x: np.ndarray, fps: float) -> Optional[float]:
    if x.size < 8:
        return None
    x = (x - np.mean(x)) / (np.std(x) + 1e-9)
    ac = np.correlate(x, x, mode="full")[x.size - 1:]
    ac[:2] = 0.0
    k = int(np.argmax(ac))
    if k <= 0:
        return None
    return float(k) / float(fps)


# Check if an index is valid for a given length
# Input:
#   idx : index (could be int or None).
#   N   : total length / number of elements.
# What:
#   Returns True if:
#     - idx is not None, and
#     - 0 <= idx < N.
#   Otherwise returns False.
# Why:
#   Small utility to safely test whether a candidate frame index is usable
#   before accessing arrays. Helps avoid out-of-bounds errors and keeps
#   index-related code cleaner.
# Output:
#   is_valid : bool
#              True if idx is a valid index in [0, N), False otherwise.
def _valid_idx(idx: Optional[int], N: int) -> bool:
    return (idx is not None) and (0 <= int(idx) < int(N))
# -----------------------------
# Public helper (textures -> positions)
# -----------------------------

# Reconstruct joint positions (T, J, 3) from texture-style data
# Input:
#   textures      : 2D array of shape (3 * len(joint_indices), T_tex)
#                   Rows are grouped per joint in (x, z, y) order, exactly
#                   as produced by create_textures (StyleWords layout).
#   joint_indices : iterable of joint indices (global joint IDs in the skeleton)
#                   saying which joints are stored in textures and where
#                   they should be placed in the full joint array.
#   n_total_joints: total number of joints in the full skeleton (J_total).
#   coord_order   : coordinate order in textures, default "xzy".
#                   Currently only "xzy" is supported (matching create_textures).
# What:
#   Builds a full 3D position array over time with shape (T_tex, n_total_joints, 3).
#   For each joint index in joint_indices, it:
#     - reads its 3 rows from textures (x, z, y),
#     - writes them into the correct joint slot jidx in the positions tensor
#       as (x, y, z) in standard coordinate order.
#   Joints not listed in joint_indices remain zero.
# Why:
#   After exporting motion into textures (e.g. for a CNN or style model),
#   we often need to reconstruct a normal (T, J, 3) positions array again
#   to run beat extraction, visualization, or other motion analysis on the
#   processed / reconstructed data.
# Output:
#   pos : array of shape (T_tex, n_total_joints, 3)
#         Reconstructed joint positions over time.
def pack_positions_from_textures(
    textures: np.ndarray,          # (3*len(JI), T_tex) in (x,z,y) per joint
    joint_indices: Iterable[int],
    n_total_joints: int,
    coord_order: str = "xzy",
) -> np.ndarray:
    JI = list(joint_indices)
    T_tex = int(textures.shape[1])
    pos = np.zeros((T_tex, n_total_joints, 3), dtype=float)

    if coord_order.lower() != "xzy":
        raise ValueError("This helper currently assumes create_textures' (x,z,y) layout.")

    for k, jidx in enumerate(JI):
        if not _valid_idx(jidx, n_total_joints):
            continue
        x = textures[3 * k + 0, :]
        z = textures[3 * k + 1, :]
        y = textures[3 * k + 2, :]
        pos[:, jidx, 0] = x
        pos[:, jidx, 1] = y
        pos[:, jidx, 2] = z

    return pos
def _safe_idx(idx, J):
    return idx if (idx is not None and 0 <= idx < J) else None

# Estimate ground level from a vertical (height) trajectory
# Input:
#   y_traj : 1D array of vertical positions (e.g. foot or pelvis height over time).
#   q      : float in [0, 1], quantile to use (e.g. 0.05 for 5%).
# What:
#   Uses a lower quantile of the vertical trajectory as an estimate of the
#   ground height. For example, if q = 0.05, it finds a value such that
#   roughly 5% of the samples are below it.
# Why:
#   Feet and pelvis are not perfectly glued to the floor; they bounce.
#   Taking a low quantile gives a robust guess of "where the ground is"
#   without being too sensitive to noise or occasional deep dips.
# Output:
#   g : float
#       Estimated ground level.
def _estimate_ground_level(y_traj: np.ndarray, q: float) -> float:
    if y_traj.size == 0:
        return 0.0
    return float(np.percentile(y_traj, q * 100.0))
