#!/usr/bin/env python3
"""
Extract LMA features + beat events from a BVH.

Outputs:
- <out_dir>/<stem>_lma.csv
- <out_dir>/<stem>_beats.csv

Beat detection (default): heuristic based on foot contacts (min Y + low velocity).
LMA extraction: uses LMAAnnotator from lma-feature-extraction project.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd


# -----------------------------
# Helpers: import LMA repo code
# -----------------------------
def add_lma_repo_to_path(lma_repo: Path) -> None:
    """
    lma_repo should point to the folder that contains create_annotator.py, loadbvh.py, etc.
    Example:
      .../lma-feature-extraction-main
    """
    lma_repo = lma_repo.resolve()
    if not lma_repo.exists():
        raise FileNotFoundError(f"--lma-repo does not exist: {lma_repo}")
    sys.path.insert(0, str(lma_repo))


# -----------------------------
# Beat detection (heuristic)
# -----------------------------
def _moving_average(x: np.ndarray, w: int) -> np.ndarray:
    if w <= 1:
        return x
    w = int(w)
    pad = w // 2
    xpad = np.pad(x, (pad, pad), mode="edge")
    kernel = np.ones(w, dtype=float) / w
    return np.convolve(xpad, kernel, mode="valid")


def _find_joint_by_name(joint_names: List[str], keywords: List[str]) -> int | None:
    """
    Return the first joint index whose name contains ALL keywords (case-insensitive).
    """
    names = [n.lower() for n in joint_names]
    kws = [k.lower() for k in keywords]
    for i, n in enumerate(names):
        if all(k in n for k in kws):
            return i
    return None


def _pick_feet_joints(skeleton) -> Tuple[int, int]:
    """
    Tries to locate left/right foot joints by name.
    Falls back to the two joints with the lowest average Y.
    """
    joint_names = [j.name for j in skeleton.joints]

    # common BVH naming patterns
    left_candidates = [
        ["left", "foot"],
        ["l", "foot"],
        ["leftfoot"],
        ["lfoot"],
        ["left", "ankle"],
        ["l", "ankle"],
        ["left", "toe"],
        ["l", "toe"],
    ]
    right_candidates = [
        ["right", "foot"],
        ["r", "foot"],
        ["rightfoot"],
        ["rfoot"],
        ["right", "ankle"],
        ["r", "ankle"],
        ["right", "toe"],
        ["r", "toe"],
    ]

    li = None
    ri = None

    for kws in left_candidates:
        li = _find_joint_by_name(joint_names, kws)
        if li is not None:
            break
    for kws in right_candidates:
        ri = _find_joint_by_name(joint_names, kws)
        if ri is not None:
            break

    if li is not None and ri is not None and li != ri:
        return li, ri

    # fallback: pick two joints with lowest mean Y over time
    all_xyz = np.array([j.d_xyz for j in skeleton.joints])  # (J, 3, F)
    y_means = all_xyz[:, 1, :].mean(axis=1)
    idx_sorted = np.argsort(y_means)  # lowest first
    a, b = int(idx_sorted[0]), int(idx_sorted[1])
    return a, b


def detect_beats_from_foot_contacts(
    skeleton,
    fps: float,
    min_interval_s: float = 0.25,
    dedup_within_s: float = 0.10,
    smooth_w: int = 5,
) -> np.ndarray:
    """
    Returns beat frames (int) using foot contact heuristics:
    - foot Y local minima (near ground)
    - low foot velocity at that moment
    """
    li, ri = _pick_feet_joints(skeleton)

    def foot_candidates(joint_index: int) -> np.ndarray:
        pos = skeleton.joints[joint_index].d_xyz  # (3, F)
        y = pos[1, :].astype(float)
        y_s = _moving_average(y, smooth_w)

        v = np.linalg.norm(np.diff(pos, axis=1), axis=0) * float(fps)  # speed per sec
        v = np.r_[v[0], v]  # match length F

        # local minima in y
        y_prev = np.r_[y_s[0], y_s[:-1]]
        y_next = np.r_[y_s[1:], y_s[-1]]
        is_min = (y_s < y_prev) & (y_s < y_next)

        # near-ground threshold
        y_low = np.percentile(y_s, 20)
        y_span = float(np.max(y_s) - np.min(y_s) + 1e-9)
        y_th = y_low + 0.05 * y_span

        # velocity threshold (adaptive)
        v_th = np.percentile(v, 30)

        cand = np.where(is_min & (y_s <= y_th) & (v <= v_th))[0]
        return cand

    cL = foot_candidates(li)
    cR = foot_candidates(ri)

    # merge & sort
    c = np.unique(np.r_[cL, cR])
    c.sort()

    # enforce min interval (greedy)
    min_frames = int(round(min_interval_s * fps))
    chosen = []
    last = -10**9
    for f in c:
        if f - last >= min_frames:
            chosen.append(int(f))
            last = int(f)
    chosen = np.array(chosen, dtype=int)

    # dedup very close events (left+right near same time)
    if chosen.size <= 1:
        return chosen

    dedup_frames = int(round(dedup_within_s * fps))
    deduped = [int(chosen[0])]
    for f in chosen[1:]:
        if f - deduped[-1] <= dedup_frames:
            # keep earlier (already kept)
            continue
        deduped.append(int(f))

    return np.array(deduped, dtype=int)


# -----------------------------
# Fallback LMA extractor (for skeletons that don't match the LMA repo joint layout)
# -----------------------------

def _minmax01(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    mn = np.nanmin(x) if x.size else 0.0
    mx = np.nanmax(x) if x.size else 0.0
    denom = mx - mn
    if not np.isfinite(denom) or denom < 1e-12:
        return np.zeros_like(x, dtype=np.float64)
    return (x - mn) / denom

def _find_joint_idx(joint_names_lc, candidates):
    """Return first joint index whose lowercased name contains any candidate substring."""
    for cand in candidates:
        cand = cand.lower()
        for i, name in enumerate(joint_names_lc):
            if cand and cand in name:
                return i
    return None

def _pick_joint_indices(joints):
    names = [(j.name or "").strip().lower() for j in joints]

    root = _find_joint_idx(names, ["hips", "hip", "pelvis", "root"]) or 0
    head = _find_joint_idx(names, ["head"])
    # Hands / wrists
    lh = _find_joint_idx(names, ["lefthand", "left hand", "lhand", "hand_l", "wrist_l", "leftwrist", "lwrist"])
    rh = _find_joint_idx(names, ["righthand", "right hand", "rhand", "hand_r", "wrist_r", "rightwrist", "rwrist"])
    # Feet / ankles
    lf = _find_joint_idx(names, ["leftfoot", "left foot", "lfoot", "foot_l", "ankle_l", "leftankle", "lankle"])
    rf = _find_joint_idx(names, ["rightfoot", "right foot", "rfoot", "foot_r", "ankle_r", "rightankle", "rankle"])

    # Fallbacks if some are missing
    if head is None:
        head = _find_joint_idx(names, ["neck"])  # better than nothing
    if lh is None:
        lh = _find_joint_idx(names, ["left", "l_"])  # weak fallback
    if rh is None:
        rh = _find_joint_idx(names, ["right", "r_"])  # weak fallback
    if lf is None:
        lf = _find_joint_idx(names, ["lefttoe", "toe_l", "toel"])
    if rf is None:
        rf = _find_joint_idx(names, ["righttoe", "toe_r", "toer"])

    # Final hard fallback: use root if still missing (keeps shapes valid)
    head = head if head is not None else root
    lh = lh if lh is not None else root
    rh = rh if rh is not None else root
    lf = lf if lf is not None else root
    rf = rf if rf is not None else root

    return dict(root=root, head=head, lh=lh, rh=rh, lf=lf, rf=rf)

def _simple_lma_from_skeleton(d_xyz, joints, fps, downsample_step, window_style_word, step_style_word):
    """
    Build a *proxy* set of LMA-like features (BODY / EFFORT_* / SHAPE / SPACE)
    for BVHs whose joint layout doesn't match the LMA repo config (e.g. AIST++).
    Outputs the same columns that Motion2Music expects downstream.
    """
    # d_xyz: (J,3,T)
    d_xyz = np.asarray(d_xyz, dtype=np.float64)
    if d_xyz.ndim != 3 or d_xyz.shape[1] != 3:
        raise ValueError(f"Unexpected d_xyz shape {d_xyz.shape} (expected (J,3,T)).")

    J, _, T = d_xyz.shape
    Td = (T + downsample_step - 1) // downsample_step
    pos = d_xyz[:, :, ::downsample_step]  # (J,3,Td)

    idx = _pick_joint_indices(joints)
    root = pos[idx["root"], :, :]   # (3,Td)
    head = pos[idx["head"], :, :]
    lh   = pos[idx["lh"],   :, :]
    rh   = pos[idx["rh"],   :, :]
    lf   = pos[idx["lf"],   :, :]
    rf   = pos[idx["rf"],   :, :]

    dt = downsample_step / float(fps)
    eps = 1e-9

    # A rough body scale to normalize (prevents different dancer sizes from dominating).
    scale_series = np.linalg.norm(head - root, axis=0)
    scale = float(np.nanmedian(scale_series)) if np.isfinite(scale_series).any() else 1.0
    if not np.isfinite(scale) or scale < eps:
        scale = 1.0

    starts = []
    ends = []
    body_raw = []
    weight_raw = []
    time_raw = []
    flow_raw = []
    shape_raw = []
    space_raw = []

    def _traj_stats(p):  # p: (3,N)
        # Velocity and acceleration magnitudes
        if p.shape[1] < 4:
            vmag = np.zeros(0)
            amag = np.zeros(0)
            jmag = np.zeros(0)
        else:
            v = np.diff(p, axis=1) / dt
            a = np.diff(v, axis=1) / dt
            j = np.diff(a, axis=1) / dt
            vmag = np.linalg.norm(v, axis=0)
            amag = np.linalg.norm(a, axis=0)
            jmag = np.linalg.norm(j, axis=0)
        return vmag, amag, jmag

    def _indirectness(p):  # p: (3,N)
        if p.shape[1] < 2:
            return 0.0
        diffs = np.diff(p, axis=1)
        path = float(np.sum(np.linalg.norm(diffs, axis=0)))
        net = float(np.linalg.norm(p[:, -1] - p[:, 0]))
        if path < eps:
            return 0.0
        directness = net / (path + eps)
        directness = max(0.0, min(1.0, directness))
        return 1.0 - directness

    win = int(window_style_word)
    step = int(step_style_word)
    if Td < win:
        raise RuntimeError(f"Not enough frames after downsampling: Td={Td} < window={win}")

    for s in range(0, Td - win + 1, step):
        e = s + win - 1
        starts.append(s)
        ends.append(e)

        r = root[:, s:e+1]
        # Relative trajectories
        lh_w = lh[:, s:e+1] - r
        rh_w = rh[:, s:e+1] - r
        lf_w = lf[:, s:e+1] - r
        rf_w = rf[:, s:e+1] - r
        head_w = head[:, s:e+1] - r

        # BODY: average radius of extremities from root (normalized)
        rad = np.vstack([
            np.linalg.norm(lh_w, axis=0),
            np.linalg.norm(rh_w, axis=0),
            np.linalg.norm(lf_w, axis=0),
            np.linalg.norm(rf_w, axis=0),
        ])
        body_raw.append(float(np.nanmean(rad)) / scale)

        # SHAPE: vertical range relative to horizontal range (normalized)
        all_pts = np.hstack([lh_w, rh_w, lf_w, rf_w, head_w, np.zeros_like(head_w)])
        rng = np.nanmax(all_pts, axis=1) - np.nanmin(all_pts, axis=1)  # (3,)
        rng_xz = float(rng[0] + rng[2])
        rng_y = float(rng[1])
        shape_raw.append((rng_y / (rng_xz + eps)))

        # EFFORT weight/time/flow from hand motion (more stable than feet)
        vmag_l, amag_l, jmag_l = _traj_stats(lh[:, s:e+1])
        vmag_r, amag_r, jmag_r = _traj_stats(rh[:, s:e+1])
        amag = np.concatenate([amag_l, amag_r]) if amag_l.size or amag_r.size else np.zeros(1)
        jmag = np.concatenate([jmag_l, jmag_r]) if jmag_l.size or jmag_r.size else np.zeros(1)
        vmag = np.concatenate([vmag_l, vmag_r]) if vmag_l.size or vmag_r.size else np.zeros(1)

        weight_raw.append(float(np.nanmean(amag)) / (scale + eps))  # strong = higher accel
        time_raw.append(float(np.nanmean(jmag)) / (scale + eps))    # sudden = higher jerk

        # FLOW bound: bursty/stop-start motion → high bound score
        p90 = float(np.nanpercentile(vmag, 90)) if np.isfinite(vmag).any() else 0.0
        mean = float(np.nanmean(vmag)) if np.isfinite(vmag).any() else 0.0
        flow = 1.0 - (mean / (p90 + eps))
        flow_raw.append(max(0.0, min(1.0, flow)))

        # SPACE: indirectness of hand paths
        space_raw.append(float(np.mean([_indirectness(lh[:, s:e+1]), _indirectness(rh[:, s:e+1])])))

    # Scale to 0..1 per-clip to mimic the original LMA pipeline outputs
    body = _minmax01(np.array(body_raw))
    weight = _minmax01(np.array(weight_raw))
    time = _minmax01(np.array(time_raw))
    flow = _minmax01(np.array(flow_raw))
    shape = _minmax01(np.array(shape_raw))
    space = _minmax01(np.array(space_raw))

    df = pd.DataFrame({
        "START_FRAME": starts,
        "END_FRAME": ends,
        "BODY": body,
        "EFFORT_WEIGHT_STRONG": weight,
        "EFFORT_TIME_SUDDEN": time,
        "EFFORT_FLOW_BOUND": flow,
        "SHAPE": shape,
        "SPACE": space,
        "LMA_MODE": ["simple"] * len(starts),
    })
    return df

# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bvh", required=True, type=str, help="Path to input .bvh")
    ap.add_argument(
        "--lma-repo",
        required=True,
        type=str,
        help="Path to lma-feature-extraction-main folder (contains create_annotator.py)",
    )
    ap.add_argument(
        "--out",
        default="out_features",
        type=str,
        help="Output directory (default: out_features)",
    )

    # LMA params (auto-adjust to fps)
    ap.add_argument("--window-style-word", type=int, default=16)
    ap.add_argument("--step-style-word", type=int, default=4)

    # Beat params
    ap.add_argument("--min-interval-s", type=float, default=0.25)
    ap.add_argument("--dedup-within-s", type=float, default=0.10)

    # LMA mode (repo vs fallback for mismatched skeletons e.g. AIST++)
    ap.add_argument("--lma-mode", choices=["auto", "repo", "simple"], default="auto",
                    help="LMA feature extraction mode. auto=try LMA repo, fallback to simple when skeleton layout mismatches; repo=only LMA repo; simple=only fallback.")

    args = ap.parse_args()

    bvh_path = Path(args.bvh).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    lma_repo = Path(args.lma_repo).resolve()
    add_lma_repo_to_path(lma_repo)

    # import from LMA repo (after sys.path injection)
    from loadbvh import loadbvh
    from create_annotator import LMAAnnotator

    # load BVH
    skeleton, frame_times, duration, fps = loadbvh(bvh_path)
    fps = float(fps)

    # create annotator (downsample = fps/5 like your pipeline)
    downsample_step = max(1, int(round(fps / 20.0)))
    annotator = LMAAnnotator.create(
        fps=int(round(fps)),
        downsample_step=downsample_step,
        window_style_word=args.window_style_word,
        step_style_word=args.step_style_word,
    )

    # compute LMA (window-based with START_FRAME/END_FRAME)
    lma_mode = args.lma_mode
    if lma_mode == "simple":
        lma_df = _simple_lma_from_skeleton(
            skeleton.d_xyz, skeleton.joints, fps=fps, downsample_step=downsample_step,
            window_style_word=args.window_style_word, step_style_word=args.step_style_word,
        )
    else:
        try:
            lma_df = annotator.fit_to_joints(skeleton.d_xyz)
            # keep extra debug columns (harmless for downstream)
            if "LMA_MODE" not in lma_df.columns:
                lma_df["LMA_MODE"] = "repo"
        except Exception as e:
            if lma_mode == "repo":
                raise
            print(f"[WARN] LMA repo extractor failed (joints={len(skeleton.joints)}). Falling back to simple extractor. Error: {e}", file=sys.stderr)
            lma_df = _simple_lma_from_skeleton(
                skeleton.d_xyz, skeleton.joints, fps=fps, downsample_step=downsample_step,
                window_style_word=args.window_style_word, step_style_word=args.step_style_word,
            )
    lma_df["START_FRAME_ORIG"] = lma_df["START_FRAME"] * downsample_step
    lma_df["END_FRAME_ORIG"] = lma_df["END_FRAME"] * downsample_step
    lma_df["START_TIME_S"] = lma_df["START_FRAME_ORIG"] / fps
    lma_df["END_TIME_S"] = lma_df["END_FRAME_ORIG"] / fps

    # compute beats (frames + seconds)
    beat_frames = detect_beats_from_foot_contacts(
        skeleton,
        fps=fps,
        min_interval_s=args.min_interval_s,
        dedup_within_s=args.dedup_within_s,
    )
    beat_times = beat_frames / fps

    beats_df = pd.DataFrame(
        {
            "beat_index": np.arange(len(beat_frames), dtype=int),
            "frame": beat_frames.astype(int),
            "time_s": beat_times.astype(float),
            "method": ["heuristic_foot_contacts"] * len(beat_frames),
        }
    )

    # save
    stem = bvh_path.stem
    lma_out = out_dir / f"{stem}_lma.csv"
    beats_out = out_dir / f"{stem}_beats.csv"

    lma_df.to_csv(lma_out, index=False)
    beats_df.to_csv(beats_out, index=False)

    print(f"[OK] BVH: {bvh_path}")
    print(f"[OK] FPS: {fps:.3f}  duration: {duration:.3f}s  frames: {len(frame_times)}")
    print(f"[OK] LMA rows: {len(lma_df)}  saved: {lma_out}")
    print(f"[OK] Beats: {len(beats_df)}  saved: {beats_out}")
    print(f"[INFO] downsample_step={downsample_step} window_style_word={args.window_style_word} step_style_word={args.step_style_word}")


if __name__ == "__main__":
    main()
