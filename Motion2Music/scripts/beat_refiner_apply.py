from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# beat_refiner_apply.py
import argparse
import re
import numpy as np
import joblib

from motion2music.ml.ml_helpers import combine_rule_and_ml_events, subdivide_events_uniform
from motion2music.ml.ml_helpers import refine_events_with_tempo

from motion2music.io.loadbvh import loadbvh
from motion2music.config import JOINT_INDICES
from motion2music.beats.BeatExtraction import (
    extract_beats_v1,
    extract_beats_v2,
    BeatParamsV1,
    BeatParamsV2,
)


# --- Minimal helpers (same logic as visualize_beats_on_bvh) ---

def stack_positions(skeleton):
    J = len(skeleton)
    T = skeleton[0].d_xyz.shape[1]
    P = np.zeros((T, J, 3), dtype=float)
    for j in range(J):
        P[:, j, :] = skeleton[j].d_xyz.T  # (3,T) -> (T,3)
    return P


def reorient_positions(positions, up: str = "auto"):
    """
    Reorient positions so that the 'up' axis becomes +Y.
    Same logic as in visualize_beats_on_bvh.py.
    """
    P = np.asarray(positions, dtype=float)
    if up not in ("auto", "x", "y", "z"):
        return P

    if up == "auto":
        med = np.median(P, axis=0)        # (J,3)
        rng = np.ptp(med, axis=0)         # [range_x, range_y, range_z]
        axis = int(np.argmax(rng))
    else:
        axis = {"x": 0, "y": 1, "z": 2}[up]

    if axis == 1:      # already y-up
        return P
    elif axis == 2:    # z-up -> y-up (swap y,z)
        return P[:, :, [0, 2, 1]]
    elif axis == 0:    # x-up -> y-up (swap x,y)
        return P[:, :, [1, 0, 2]]


def _valid_idx(i, N):
    return (i is not None) and isinstance(i, (int, np.integer)) and 0 <= int(i) < N


def auto_rig_indices(skeleton, positions):
    """
    Return (pelvis_idx, left_foot_idx, right_foot_idx).
    Same logic as in visualize_beats_on_bvh.py.
    """
    J = len(skeleton)
    P = np.asarray(positions)  # (T, J, 3)
    assert P.ndim == 3 and P.shape[1] == J

    names = [(getattr(j, "name", "") or "").lower() for j in skeleton]

    # Pelvis
    pelvis_idx = next((i for i, n in enumerate(names) if ("hip" in n or "pelvis" in n)), None)
    if pelvis_idx is None:
        pelvis_idx = next((i for i, j in enumerate(skeleton) if getattr(j, "is_root", False)), 0)
    pelvis_idx = int(pelvis_idx)

    def name_candidates(side):
        s0 = side[0]
        idxs = []
        for i, n in enumerate(names):
            if ("foot" in n or "feet" in n or "toe" in n or "ankle" in n):
                if side in n or n.startswith(s0):
                    idxs.append(i)
        return idxs

    def pick_lowest_y(idxs):
        if not idxs:
            return None
        ymed = [np.median(P[:, i, 1]) for i in idxs]
        return int(idxs[int(np.argmin(ymed))])

    l_idx = pick_lowest_y(name_candidates("left"))
    r_idx = pick_lowest_y(name_candidates("right"))

    if (l_idx is None) or (r_idx is None):
        ymed_all = np.median(P[:, :, 1], axis=0)
        order = np.argsort(ymed_all)
        pool = [i for i in order[:max(8, J)] if i != pelvis_idx]

        xpel = np.median(P[:, pelvis_idx, 0])
        lefts  = [i for i in pool if np.median(P[:, i, 0]) >= xpel]
        rights = [i for i in pool if np.median(P[:, i, 0]) <  xpel]

        if l_idx is None and lefts:
            l_idx = int(lefts[0])
        if r_idx is None and rights:
            r_idx = int(rights[0])

        if l_idx is None and len(pool) >= 1:
            l_idx = int(pool[0])
        if r_idx is None and len(pool) >= 2:
            r_idx = int(pool[1] if pool[1] != l_idx else (pool[2] if len(pool) > 2 else pool[0]))

    return pelvis_idx, l_idx, r_idx


# --- Context builder for a single clip ---

def build_context_single_clip(X: np.ndarray, radius: int) -> np.ndarray:
    """
    Build context-augmented features for a single continuous clip.

    X: (T, D)
    radius: >= 0
    returns: (T, D * (2*radius+1))
    """
    X = np.asarray(X, dtype=float)
    T, D = X.shape
    if radius <= 0:
        return X.copy()

    K = 2 * radius + 1
    X_ctx = np.zeros((T, D * K), dtype=float)
    for t in range(T):
        cols = []
        for d in range(-radius, radius + 1):
            t2 = t + d
            if t2 < 0:
                t2 = 0
            elif t2 >= T:
                t2 = T - 1
            cols.append(X[t2])
        X_ctx[t] = np.concatenate(cols, axis=0)
    return X_ctx


# --- Utility to turn probs into discrete events (ML-only) ---

def probs_to_events(prob: np.ndarray, thr: float) -> np.ndarray:
    """
    Convert per-frame probabilities into a list of event indices:
      - threshold -> binary mask
      - group consecutive positives into segments
      - choose frame with max prob in each segment as event
    """
    prob = np.asarray(prob, dtype=float)
    T = prob.shape[0]
    if T == 0:
        return np.zeros(0, dtype=int)

    mask = prob >= float(thr)
    padded = np.r_[False, mask, False]
    changes = np.diff(padded.astype(int))
    starts = np.where(changes == 1)[0]
    ends   = np.where(changes == -1)[0]

    events = []
    for s, e in zip(starts, ends):
        if e <= s:
            continue
        seg = prob[s:e]
        idx = s + int(np.argmax(seg))
        events.append(idx)

    return np.array(events, dtype=int)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bvh", required=True, help="Path to BVH file")
    ap.add_argument("--model", required=True, help="Path to beat_refiner.joblib")
    ap.add_argument(
        "--v2",
        action="store_true",
        help="Use extract_beats_v2 (includes accel + reversal cues). If not set, use v1."
    )
    ap.add_argument(
        "--up",
        type=str,
        default="auto",
        choices=["auto", "x", "y", "z"],
        help="Up-axis of source BVH (same as visualize_beats_on_bvh)."
    )
    ap.add_argument(
        "--out-prefix",
        type=str,
        default=None,
        help="Prefix for output files (.ml_prob.npy, .ml_events.npy, .hybrid_events.npy, .rule_events.npy). "
             "Default: <bvh path without .bvh>"
    )
    ap.add_argument(
        "--thr",
        type=float,
        default=None,
        help="Override probability threshold for events (default: use value saved in model).",
    )
    ap.add_argument(
        "--snap-radius-sec",
        type=float,
        default=0.10,
        help="Time window (sec) around each rule event to search for best ML prob (for hybrid)."
    )
    ap.add_argument(
        "--hybrid-min-sep",
        type=float,
        default=0.18,
        help="Minimum separation (sec) between hybrid events (time NMS)."
    )
    ap.add_argument(
        "--subdivide",
        type=int,
        default=1,
        help=(
            "If >1, subdivide the refined ML beat grid uniformly. "
            "Example: 4 anchors, --subdivide 2 -> ~8 beats, 4 -> ~16, 8 -> ~32."
        ),
    )
    ap.add_argument(
        "--target-beats",
        type=int,
        default=None,
        help=(
            "If set (>0), automatically choose a subdivision factor so that the "
            "final ML beat count is roughly this number. "
            "Example: 4 anchors, --target-beats 16 -> subdiv ≈ 4."
        ),
    )

    args = ap.parse_args()

    # --- Load BVH & positions ---
    skeleton, frame_times, total_time, fps = loadbvh(args.bvh)
    positions0 = stack_positions(skeleton)
    positions = reorient_positions(positions0, args.up)

    T, N, _ = positions.shape
    print(f"[bvh] {args.bvh}  frames={T}  fps={fps:.3f}  duration={T / fps:.3f}s")

    # --- Auto-rig pelvis & feet ---
    pelvis_idx, LFOOT_IDX, RFOOT_IDX = auto_rig_indices(skeleton, positions)
    print(f"[rig] pelvis={pelvis_idx}, Lfoot={LFOOT_IDX}, Rfoot={RFOOT_IDX}")

    # --- Extract rule-based cues & score (v1 or v2) ---
    if args.v2:
        params = BeatParamsV2()
        out = extract_beats_v2(
            positions, fps, JOINT_INDICES, params,
            pelvis_idx=pelvis_idx, left_foot_idx=LFOOT_IDX, right_foot_idx=RFOOT_IDX
        )
        print("[beats] using v2 cues (decel, pelvis, foot, accel, reversal)")
    else:
        params = BeatParamsV1()
        out = extract_beats_v1(
            positions, fps, JOINT_INDICES, params,
            pelvis_idx=pelvis_idx, left_foot_idx=LFOOT_IDX, right_foot_idx=RFOOT_IDX
        )
        print("[beats] using v1 cues (decel, pelvis, foot)")

    score        = out["beat_score"]
    C_decel      = out["C_decel"]
    C_pelvis     = out["C_pelvis"]
    C_foot       = out["C_foot"]
    C_accel      = out.get("C_accel",    np.zeros_like(score))
    C_rev        = out.get("C_reversal", np.zeros_like(score))
    events_rule  = out["events_idx"]

    assert score.shape[0] == T
    print(f"[rule] events_rule={events_rule.size}")

    # --- Base feature matrix (must match training order) ---
    # [score, C_foot, C_decel, C_pelvis, C_accel, C_reversal]
    X_base = np.stack([score, C_foot, C_decel, C_pelvis, C_accel, C_rev], axis=1)
    print(f"[features] X_base shape={X_base.shape} (T x 6)")

    # --- Load ML model + metadata ---
    payload = joblib.load(args.model)
    if isinstance(payload, dict) and "model" in payload:
        clf = payload["model"]
        thr = float(payload.get("threshold", 0.5))
        context_radius = int(payload.get("context_radius", 0))
        print(f"[model] loaded dict from {args.model}, thr={thr:.3f}, context_radius={context_radius}")
    else:
        clf = payload
        thr = 0.5
        context_radius = 0
        print(f"[model] loaded bare model from {args.model}, DEFAULT thr={thr:.3f}, context_radius={context_radius}")

    # CLI override of threshold (if provided)
    if args.thr is not None:
        thr = float(args.thr)
        print(f"[model] overriding threshold from CLI: thr={thr:.3f}")

    # --- Build context features for this single clip ---
    if context_radius > 0:
        X = build_context_single_clip(X_base, radius=context_radius)
    else:
        X = X_base
    print(f"[features] final X shape={X.shape}")

    # --- Predict probabilities & events (ML-only) ---
    prob = clf.predict_proba(X)[:, 1]
    events_ml = probs_to_events(prob, thr)

    frac_pos = float((prob >= thr).mean())
    print(
        f"[ml] prob range=({prob.min():.4f}, {prob.max():.4f}), thr={thr:.3f}, "
        f"frac>=thr={frac_pos:.3f}, events_ml={events_ml.size}"
    )

    # --- Hybrid events: rule anchors + ML probabilities ---
    events_hybrid = combine_rule_and_ml_events(
        events_rule=events_rule,
        prob=prob,
        fps=fps,
        snap_radius_s=float(args.snap_radius_sec),
        thr_ml=float(thr),
        min_sep_s=float(args.hybrid_min_sep),
    )
    # --- Optional tempo refinement for HYBRID events ---
    events_hybrid = refine_events_with_tempo(
        events_idx=events_hybrid,
        score=prob,  # use ML prob as the smooth beat-strength curve
        fps=fps,
        max_drift_frames=3,  # how far each beat is allowed to move
        min_events=3,  # if fewer than this, skip refinement
        verbose=True,
    )
    print(f"[hybrid-tempo] events_hybrid_refined={events_hybrid.size}")

    events_ml = probs_to_events(prob, thr)

    events_ml = refine_events_with_tempo(
        events_idx=events_ml,
        score=prob,  # or fused score if you use one
        fps=fps,
        max_drift_frames=3,
        min_events=3,
        verbose=True,
    )

    print(f"[ml-tempo] events_ml_refined={events_ml.size}")

    # --- Optional subdivision of refined ML grid ---
    # Decide effective subdivision:
    # - If --target-beats is set, compute subdiv ≈ target / anchors.
    # - Otherwise, use --subdivide as given.
    effective_subdiv = args.subdivide

    if args.target_beats is not None and args.target_beats > 0 and events_ml.size >= 2:
        auto_subdiv = int(round(float(args.target_beats) / float(events_ml.size)))
        auto_subdiv = max(1, auto_subdiv)
        if args.subdivide != 1 and auto_subdiv != args.subdivide:
            print(
                f"[ml-subdivide] WARNING: both --subdivide={args.subdivide} and "
                f"--target-beats={args.target_beats} given; using auto_subdiv={auto_subdiv}."
            )
        effective_subdiv = auto_subdiv
        print(
            f"[ml-subdivide] anchors={events_ml.size}, target_beats={args.target_beats}, "
            f"auto_subdiv={effective_subdiv}"
        )

    if effective_subdiv > 1 and events_ml.size >= 2:
        in_n = events_ml.size
        events_ml = subdivide_events_uniform(events_ml, effective_subdiv, T)
        print(
            f"[ml-subdivide] factor={effective_subdiv}, "
            f"in={in_n} -> out={events_ml.size}"
        )


    print(f"[ml-tempo] events_ml_refined={events_ml.size}")

    # --- Optional subdivision of refined ML grid ---
    if args.subdivide > 1 and events_ml.size >= 2:
        events_ml_sub = subdivide_events_uniform(events_ml, args.subdivide, T)
        print(
            f"[ml-subdivide] factor={args.subdivide}, "
            f"in={events_ml.size} -> out={events_ml_sub.size}"
        )
        events_ml = events_ml_sub

    print(f"[hybrid] events_hybrid={events_hybrid.size}  (snap_radius={args.snap_radius_sec:.3f}s, min_sep={args.hybrid_min_sep:.3f}s)")

    # --- Save outputs ---
    if args.out_prefix is not None:
        base = args.out_prefix
    else:
        base = re.sub(r"\.bvh$", "", args.bvh, flags=re.IGNORECASE)

    prob_path        = base + ".ml_prob.npy"
    events_ml_path   = base + ".ml_events.npy"
    events_rule_path = base + ".rule_events.npy"
    events_hyb_path  = base + ".hybrid_events.npy"

    np.save(prob_path,        prob)
    np.save(events_ml_path,   events_ml)
    np.save(events_rule_path, events_rule)
    np.save(events_hyb_path,  events_hybrid)

    print(f"[save] prob          -> {prob_path}")
    print(f"[save] ml_events     -> {events_ml_path}")
    print(f"[save] rule_events   -> {events_rule_path}")
    print(f"[save] hybrid_events -> {events_hyb_path}")


if __name__ == "__main__":
    main()
