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
    lma_df = annotator.fit_to_joints(skeleton.d_xyz)

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
