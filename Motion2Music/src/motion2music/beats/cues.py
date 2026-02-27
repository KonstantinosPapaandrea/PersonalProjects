import numpy as np
from typing import Optional

# Import all the low-level helpers from helpers.py
from .helpers import (
    _ma3,
    _grad,
    _local_minima,
    _robust_norm,
    _valid_idx,
    _safe_idx,
)

# -----------------------------
# Cues
# -----------------------------

# Body speed trace over selected joints
# Input:
#   positions_sel : array of shape (T, J_sel, 3)
#                   3D positions over time for a subset of joints
#                   (e.g. main body joints).
#   dt            : float
#                   Time step between frames (1 / fps).
#   smooth_win    : int
#                   Window size for smoothing the joint trajectories.
# What:
#   1) Smooths each selected joint trajectory in 3D using _ma3.
#   2) Computes the velocity vectors over time via _grad.
#   3) Converts velocities to speeds (length of the velocity vector) per joint.
#   4) Takes the median speed across the selected joints at each frame.
#   The result is a single 1D time series describing how fast the body
#   is moving overall, frame by frame.
# Why:
#   This gives a robust global measure of motion intensity that is less
#   sensitive to any single noisy joint. Peaks and valleys in this trace
#   often align with steps, hits, or accented movements that are relevant
#   for beat detection.
# Output:
#   body_speed : 1D array of length T
#                Median body speed over time.
def _body_speed_trace(positions_sel: np.ndarray, dt: float, smooth_win: int) -> np.ndarray:
    Xs = np.empty_like(positions_sel, dtype=float)
    for j in range(positions_sel.shape[1]):
        Xs[:, j, :] = _ma3(positions_sel[:, j, :], smooth_win)
    V = _grad(Xs, dt)
    speed_j = np.linalg.norm(V, axis=2)  # (T, J_sel)
    return np.median(speed_j, axis=1)


# Deceleration cue based on speed
# Input:
#   speed : 1D array of length T
#           Overall body speed over time (e.g. from _body_speed_trace).
#   dt    : float
#           Time step between frames (1 / fps).
# What:
#   1) Computes the time derivative of speed (change of speed per frame).
#   2) Keeps only negative changes (when speed is decreasing) as deceleration.
#   3) Multiplies this deceleration by a mask of local minima in speed,
#      so we focus on moments where speed is low AND coming out of a slowdown.
#   4) Normalizes the resulting cue to [0, 1] with _robust_norm.
# Why:
#   Many beat-like events happen when motion slows down and "lands"
#   (e.g. end of a step or hit). This cue highlights those decelerating
#   valleys in the speed curve as potential beat candidates.
# Output:
#   cue : 1D array of length T, values in [0, 1]
#         Higher values indicate stronger deceleration-related events.
def _cue_deceleration(speed: np.ndarray, dt: float) -> np.ndarray:
    ds_dt = _grad(speed, dt)
    decel = np.clip(-ds_dt, 0.0, None)
    raw = _local_minima(speed).astype(float) * decel
    return _robust_norm(raw)
# Pelvis drop / bounce cue
# Input:
#   positions  : array of shape (T, J, 3)
#                Full 3D joint positions over time.
#   pelvis_idx : int
#                Index of the pelvis joint in the second dimension of positions.
#   dt         : float
#                Time step between frames (1 / fps).
#   smooth_win : int
#                Window size for smoothing the pelvis trajectory.
# What:
#   1) Smooths the 3D pelvis trajectory to reduce jitter.
#   2) Extracts the vertical (y) coordinate of the pelvis over time.
#   3) Computes vertical velocity (vy) and vertical acceleration (ay).
#   4) Finds local minima of the pelvis height (lowest points of the bounce).
#   5) Keeps only positive acceleration (pelvis accelerating upwards) at
#      those minima — i.e. moments when the pelvis reaches a low point and
#      starts bouncing back up.
#   6) Normalizes the resulting cue to [0, 1].
# Why:
#   Walking, running and many dance moves create a clear up–down motion
#   of the pelvis. The "drop then bounce up" moments often align with
#   steps or strong rhythmic accents, making them useful beat candidates.
# Output:
#   cue : 1D array of length T, values in [0, 1]
#         Higher values indicate stronger pelvis bounce events.
def _cue_pelvis_drop(positions: np.ndarray, pelvis_idx: int, dt: float, smooth_win: int) -> np.ndarray:
    T = positions.shape[0]
    if not _valid_idx(pelvis_idx, positions.shape[1]):
        return np.zeros(T, dtype=float)
    pelvis = _ma3(positions[:, pelvis_idx, :], smooth_win)
    y = pelvis[:, 1]
    vy = _grad(y, dt)
    ay = _grad(vy, dt)
    mins = _local_minima(y).astype(float)
    bounce = np.clip(ay, 0.0, None)
    return _robust_norm(mins * bounce)


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


# Estimate a characteristic leg length from pelvis–foot distances
# Input:
#   positions  : array of shape (T, J, 3)
#                Full 3D joint positions over time.
#   pelvis_idx : optional int, index of pelvis joint.
#   lfoot_idx  : optional int, index of left foot joint.
#   rfoot_idx  : optional int, index of right foot joint.
# What:
#   1) Safely resolves the joint indices (ignores invalid ones).
#   2) Computes the distance from pelvis to each available foot over time.
#   3) Concatenates those distances and takes their median.
#   4) Returns the larger of:
#        - that median distance, and
#        - a small floor value (1e-6) to avoid division by zero.
# Why:
#   Provides a typical leg length scale for this motion, used to normalize
#   vertical distances (e.g. foot height above ground). This makes foot
#   cues more comparable across characters of different sizes.
# Output:
#   L : float
#       Estimated leg length (always > 0).
def _leg_length(positions: np.ndarray, pelvis_idx: Optional[int],
                lfoot_idx: Optional[int], rfoot_idx: Optional[int]) -> float:
    J = positions.shape[1]
    pelvis_idx = _safe_idx(pelvis_idx, J)
    lfoot_idx  = _safe_idx(lfoot_idx,  J)
    rfoot_idx  = _safe_idx(rfoot_idx,  J)
    if pelvis_idx is None or (lfoot_idx is None and rfoot_idx is None):
        return 1.0
    pel = positions[:, pelvis_idx, :]
    dists = []
    if lfoot_idx is not None:
        dists.append(np.linalg.norm(pel - positions[:, lfoot_idx, :], axis=1))
    if rfoot_idx is not None:
        dists.append(np.linalg.norm(pel - positions[:, rfoot_idx, :], axis=1))
    if not dists:
        return 1.0
    return float(max(np.median(np.concatenate(dists)), 1e-6))


# Foot contact cue based on height, horizontal speed and jerk
# Input:
#   positions : array of shape (T, J, 3)
#               Full 3D joint positions over time.
#   foot_idx  : optional int
#               Index of the foot joint to analyze (e.g. left or right foot).
#   dt        : float
#               Time step between frames (1 / fps).
#   smooth_win: int
#               Window size for smoothing the foot trajectory.
#   q_speed   : float in [0, 1]
#               Quantile threshold for defining "stationary" horizontal speed
#               (e.g. q_speed = 0.3 means bottom 30% speeds are considered still).
#   ground_q  : float in [0, 1]
#               Quantile for estimating ground level from foot height
#               (e.g. 0.05 for a low percentile).
#   leg_scale : float
#               Characteristic leg length used to normalize vertical distances.
# What:
#   1) Smooths the foot trajectory and splits it into:
#        - y  : vertical height,
#        - xy : horizontal (x, z) position.
#   2) Estimates ground level from y using _estimate_ground_level and normalizes
#      foot height above the ground by leg_scale → y_rel.
#   3) Computes:
#        - vxy  : horizontal velocity,   sp   : horizontal speed,
#        - vy   : vertical velocity,     ay   : vertical acceleration,
#        - axy  : horizontal acceleration,
#        - jerk : magnitude of change of acceleration (jerk) in the horizontal plane.
#   4) Builds logical conditions for foot contact:
#        - stationary : horizontal speed in the low-velocity quantile (almost not moving),
#        - near_gnd   : foot height is in the lower part of its range,
#        - vy_up      : vertical velocity crosses from negative to non-negative
#                       (foot stops going down and starts moving up),
#        - ay_up      : positive vertical acceleration (pushing up from the ground).
#   5) Finds local minima in y_rel (lowest points of the foot above ground) and:
#        - First term: selects frames that satisfy (mins & stationary & near_gnd & vy_up)
#          and weights them by ay_up (strong upward push).
#        - Second term: adds another component: minima weighted by normalized jerk
#          (sharp changes in motion around the contact).
#   6) Normalizes the combined raw cue to [0, 1] with _robust_norm.
# Why:
#   Foot contacts (heel strikes, steps) typically happen when:
#     - the foot is low and close to the ground,
#     - horizontal speed is small (planted on the floor),
#     - the foot trajectory turns from downwards to upwards,
#     - there is a sharp change in forces (jerk).
#   This cue tries to capture those moments as strong candidates for beats.
# Output:
#   cue : 1D array of length T, values in [0, 1]
#         Higher values indicate stronger foot contact events.
def _cue_foot_contact(positions: np.ndarray, foot_idx: Optional[int],
                      dt: float, smooth_win: int, q_speed: float,
                      ground_q: float, leg_scale: float) -> np.ndarray:
    """
    Foot contact / impact cue (continuous).

    High when the foot is:
      - relatively low above the ground,
      - not sliding too fast horizontally,
      - moving strongly in vertical direction (impact-like).

    This is closer to "heel strike" than to a long flat stance.
    """
    T, N, _ = positions.shape
    if not _valid_idx(foot_idx, N) or T == 0:
        return np.zeros(T, dtype=float)

    # Smooth foot trajectory
    foot = _ma3(positions[:, int(foot_idx), :], smooth_win)
    y = foot[:, 1]
    xy = foot[:, [0, 2]]

    # Ground estimate + normalized height above ground (leg-length units)
    g = _estimate_ground_level(y, ground_q)
    y_rel = np.maximum(0.0, y - g) / max(leg_scale, 1e-6)

    # Horizontal speed
    vxy = _grad(xy, dt)
    sp = np.linalg.norm(vxy, axis=1)

    # Vertical velocity
    vy = _grad(y_rel, dt)
    vy_abs = np.abs(vy)

    # Normalize components
    h_norm  = _robust_norm(y_rel)     # 0=low, 1=high
    s_norm  = _robust_norm(sp)        # 0=slow, 1=fast
    vy_norm = _robust_norm(vy_abs)    # 0=still, 1=strong vertical motion

    # 1) Height score: lower height ⇒ higher score
    height_score = 1.0 - h_norm       # [0,1]

    # 2) Speed score: slower horizontally ⇒ higher score
    speed_score = 1.0 - s_norm        # [0,1]

    # 3) Impact score: more vertical motion ⇒ higher score
    impact_score = vy_norm            # [0,1]

    # Base: low & slow
    base = height_score * speed_score  # [0,1]

    # Optional: small bonus at height minima to sharpen peaks a bit
    mins = _local_minima(y_rel).astype(float)
    minima_bonus = 1.0 + 0.3 * mins    # 1.0–1.3

    # Combine: “impact-like” = (low & slow) * strong vertical motion * minima_bonus
    raw = base * impact_score * minima_bonus

    return _robust_norm(raw)

# Global acceleration cue from selected joints
# Input:
#   positions_sel : array of shape (T, J_sel, 3)
#                   3D positions over time for a subset of joints
#                   (e.g. main body joints).
#   dt            : float
#                   Time step between frames (1 / fps).
#   smooth_win    : int
#                   Window size for smoothing the joint trajectories.
# What:
#   1) Smooths each selected joint trajectory in 3D with _ma3.
#   2) Computes velocities (V) and then accelerations (A) over time using _grad.
#   3) For each frame, computes the magnitude of acceleration per joint.
#   4) Takes the median acceleration magnitude across selected joints.
#   5) Normalizes this global acceleration trace to [0, 1].
# Why:
#   Sudden, strong changes in motion (high acceleration) are often perceived
#   as impactful, accent-like moments that align with beats or hits.
#   Using the median across joints makes this cue robust to outliers and
#   focuses on global "body impact" rather than any single joint.
# Output:
#   cue : 1D array of length T, values in [0, 1]
#         Higher values indicate stronger global acceleration events.
def _cue_global_accel(positions_sel: np.ndarray, dt: float, smooth_win: int) -> np.ndarray:
    """Global acceleration cue from selected joints."""
    Xs = np.empty_like(positions_sel, dtype=float)
    for j in range(positions_sel.shape[1]):
        Xs[:, j, :] = _ma3(positions_sel[:, j, :], smooth_win)
    V = _grad(Xs, dt)
    A = _grad(V, dt)
    acc_j = np.linalg.norm(A, axis=2)
    return _robust_norm(np.median(acc_j, axis=1))


# Reversal cue: emphasize points where median speed turns around
# Input:
#   positions_sel : array of shape (T, J_sel, 3)
#                   3D positions over time for a subset of joints.
#   dt            : float
#                   Time step between frames (1 / fps).
#   smooth_win    : int
#                   Window size for smoothing the joint trajectories.
# What:
#   1) Smooths the selected joint trajectories in 3D using _ma3.
#   2) Computes velocities over time (V) and converts them to per-joint speeds.
#   3) For each frame, takes the median speed across the selected joints → m.
#   4) Computes dm/dt (how median speed changes over time).
#   5) Builds a reversal signal:
#        - Uses negative dm (speed decreasing) clipped to >= 0,
#        - Multiplies by a mask of local minima in m (places where speed
#          hits a valley).
#   6) Normalizes the result to [0, 1].
# Why:
#   Many expressive movements have clear "reversals": the body slows down,
#   stops, and then moves in a different direction or builds up again.
#   These turning points in speed often align with musically meaningful
#   moments and are good beat/event candidates.
# Output:
#   cue : 1D array of length T, values in [0, 1]
#         Higher values indicate stronger speed reversal events.
def _cue_reversal(positions_sel: np.ndarray, dt: float, smooth_win: int) -> np.ndarray:
    """Reversal cue: emphasize points where median speed turns around."""
    Xs = np.empty_like(positions_sel, dtype=float)
    for j in range(positions_sel.shape[1]):
        Xs[:, j, :] = _ma3(positions_sel[:, j, :], smooth_win)
    V = _grad(Xs, dt)  # (T,J,3)
    speed_j = np.linalg.norm(V, axis=2)      # (T,J)
    m = np.median(speed_j, axis=1)
    dm = _grad(m, dt)
    rev = np.clip(-dm, 0.0, None) * _local_minima(m).astype(float)
    return _robust_norm(rev)
