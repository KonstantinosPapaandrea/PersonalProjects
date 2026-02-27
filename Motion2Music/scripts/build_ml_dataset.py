#!/usr/bin/env python3

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

"""
build_ml_dataset_with_audio.py

End-to-end pipeline:
  - For each BVH in --bvh-dir, find matching audio in --audio-dir
    (handles AIST++ style names like gBR_sBM_cAll_d04_mBR0_ch01.bvh
     -> gBR_sBM_c01_d04_mBR0_ch01.mp3).
  - Detect beats from audio (librosa).
  - Build audio onset envelope + motion energy envelope.
  - Auto-estimate global offset between audio & motion.
  - Map audio beats -> BVH frames using that offset.
  - Run BeatExtraction v2 on motion to get cues + fused score.
  - Build frame-level dataset: features X, labels y (0/1).
  - Optionally save per-BVH beat frames as <bvh>.beats.npy.

Output:
  An .npz file (default: ml_dataset.npz) with:
    - X        : (N_total_frames, D)   feature matrix
    - y        : (N_total_frames,)     labels 0/1 (beat vs non-beat)
    - fps_all  : (n_clips,)            fps per clip
    - clip_ids : (N_total_frames,)     integer clip index for each frame
"""

import argparse
import os
import re
from typing import Tuple, Optional

import numpy as np
import librosa

from motion2music.io.loadbvh import loadbvh
from motion2music.config import JOINT_INDICES, N_TOTAL_JOINTS
from motion2music.beats.BeatExtraction import extract_beats_v2, BeatParamsV2


# ------------------------------------------------------------
# Skeleton / positions helpers (same logic as visualizer)
# ------------------------------------------------------------

def stack_positions(skeleton):
    """Convert skeleton joint data to (T, J, 3) positions array."""
    J = len(skeleton)
    T = skeleton[0].d_xyz.shape[1]
    P = np.zeros((T, J, 3), dtype=float)
    for j in range(J):
        P[:, j, :] = skeleton[j].d_xyz.T  # (3,T) -> (T,3)
    return P


def reorient_positions(positions, up: str = "auto"):
    """
    Reorient positions so that the 'up' axis becomes +Y.

    - If up is 'x', 'y', or 'z', we trust the user.
    - If up is 'auto', we:
        * compute median joint positions over time (cancels translation),
        * pick the axis with the largest joint-median spread as vertical.
    """
    P = np.asarray(positions, dtype=float)
    if up not in ("auto", "x", "y", "z"):
        return P

    if up == "auto":
        med = np.median(P, axis=0)          # (J, 3)
        rng = np.ptp(med, axis=0)           # [range_x, range_y, range_z]
        axis = int(np.argmax(rng))
    else:
        axis = {"x": 0, "y": 1, "z": 2}[up]

    if axis == 1:      # already y-up
        return P
    elif axis == 2:    # z-up -> y-up (swap y,z)
        return P[:, :, [0, 2, 1]]
    elif axis == 0:    # x-up -> y-up (swap x,y)
        return P[:, :, [1, 0, 2]]


def auto_rig_indices(skeleton, positions) -> Tuple[int, int, int]:
    """
    Return (pelvis_idx, left_foot_idx, right_foot_idx).

    - Tries name matching first (hip/pelvis, left/right + foot/toe/ankle)
    - Falls back to geometry (lowest two joints by median Y, split by X wrt pelvis)
    """
    J = len(skeleton)
    P = np.asarray(positions)  # (T, J, 3) in canonical y-up space
    assert P.ndim == 3 and P.shape[1] == J

    names = [(getattr(j, "name", "") or "").lower() for j in skeleton]

    # --- Pelvis (name → root fallback) ---
    pelvis_idx = next((i for i, n in enumerate(names) if ("hip" in n or "pelvis" in n)), None)
    if pelvis_idx is None:
        pelvis_idx = next((i for i, j in enumerate(skeleton) if getattr(j, "is_root", False)), 0)
    pelvis_idx = int(pelvis_idx)

    # --- Helpers for feet ---
    def name_candidates(side):
        s0 = side[0]  # 'l'/'r'
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

    # --- Try name-based feet first ---
    l_idx = pick_lowest_y(name_candidates("left"))
    r_idx = pick_lowest_y(name_candidates("right"))

    # --- Geometric fallback (lowest joints) if missing one/both feet ---
    if (l_idx is None) or (r_idx is None):
        ymed_all = np.median(P[:, :, 1], axis=0)          # median Y per joint
        order = np.argsort(ymed_all)                      # low → high
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


# ------------------------------------------------------------
# Audio/motion envelope + offset estimation (no BeatExtraction)
# ------------------------------------------------------------

def compute_motion_envelope(positions, frame_times):
    """
    Very simple motion "energy" envelope from positions:
      - compute velocities via finite differences
      - speed_j = ||v|| per joint
      - envelope = median speed across joints, per frame
    Returns:
      motion_env  : (T,) float
      motion_times: (T,) float (frame_times)
    """
    positions = np.asarray(positions, dtype=float)
    T = positions.shape[0]
    frame_times = np.asarray(frame_times, dtype=float)
    if T < 2:
        return np.zeros(T, dtype=float), frame_times

    if frame_times.size == T and T >= 2:
        dt = float(np.median(np.diff(frame_times)))
    else:
        dt = 1.0

    V = np.gradient(positions, dt, axis=0)  # (T, J, 3)
    speed_j = np.linalg.norm(V, axis=2)    # (T, J)
    motion_env = np.median(speed_j, axis=1)
    return motion_env, frame_times


def compute_audio_envelope(y, sr, hop_length):
    """
    Audio onset envelope using librosa:
      oenv = onset_strength over time
    Returns:
      audio_env  : (Na,) float
      audio_times: (Na,) float
    """
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    times = librosa.frames_to_time(np.arange(len(oenv)), sr=sr, hop_length=hop_length)
    return oenv.astype(float), times.astype(float)


def estimate_offset_sec_from_env(
    audio_env, audio_times,
    motion_env, motion_times,
    max_offset_sec=1.0,
    dt_grid=0.01,
):
    """
    Estimate a *global* time offset that best aligns audio_env with motion_env.

    We search offsets in [-max_offset_sec, +max_offset_sec]. For each offset 'offset',
    we align:

        audio_shifted(t) = audio_env(t - offset)
        motion(t)        = motion_env(t)

    and compute normalized correlation over their overlapping time region.

    Returns:
      offset_sec: float (what you should ADD to audio times to align them with motion)
    """
    audio_env = np.asarray(audio_env, dtype=float)
    audio_times = np.asarray(audio_times, dtype=float)
    motion_env = np.asarray(motion_env, dtype=float)
    motion_times = np.asarray(motion_times, dtype=float)

    if audio_env.size < 4 or motion_env.size < 4:
        return 0.0

    def norm_env(x):
        x = x.astype(float)
        x = x - x.mean()
        s = x.std()
        if s < 1e-9:
            return np.zeros_like(x)
        return x / s

    audio_env_n = norm_env(audio_env)
    motion_env_n = norm_env(motion_env)

    if np.allclose(audio_env_n, 0.0) or np.allclose(motion_env_n, 0.0):
        return 0.0

    offsets = np.linspace(-max_offset_sec, max_offset_sec, int(2 * max_offset_sec / dt_grid) + 1)
    best_score = -np.inf
    best_offset = 0.0

    for offset in offsets:
        t_a0 = audio_times[0] + offset
        t_a1 = audio_times[-1] + offset

        t_m0 = motion_times[0]
        t_m1 = motion_times[-1]

        t0 = max(t_a0, t_m0)
        t1 = min(t_a1, t_m1)
        if t1 <= t0 + 2 * dt_grid:
            continue

        t = np.arange(t0, t1, dt_grid)

        a_vals = np.interp(t - offset, audio_times, audio_env_n)
        m_vals = np.interp(t,          motion_times, motion_env_n)

        a_vals = a_vals - a_vals.mean()
        m_vals = m_vals - m_vals.mean()
        denom = (np.linalg.norm(a_vals) * np.linalg.norm(m_vals) + 1e-9)
        if denom <= 1e-9:
            continue

        score = float(np.dot(a_vals, m_vals) / denom)
        if score > best_score:
            best_score = score
            best_offset = offset

    return best_offset


# ------------------------------------------------------------
# Mapping BVH name -> audio name (handles cAll ↔ c01)
# ------------------------------------------------------------

AUDIO_EXTS = (".mp3", ".wav", ".flac", ".m4a", ".ogg")


def find_matching_audio(bvh_path: str, audio_dir: str) -> Optional[str]:
    """
    For AIST++ style names, e.g.:

      BVH:  gBR_sBM_cAll_d04_mBR0_ch01.bvh
      Audio: gBR_sBM_c01_d04_mBR0_ch01.mp3

    Strategy:
      1) Exact stem match (same name, different ext) if it exists.
      2) Replace '_cAll_' -> '_c01_' and try each audio extension.
      3) Regex fallback: (.*)_cAll_(.*) and look for (.*)_cXX_(.*) in audio_dir.
    """
    bvh_name = os.path.basename(bvh_path)
    stem = os.path.splitext(bvh_name)[0]

    # 1) exact stem match
    for ext in AUDIO_EXTS:
        cand = os.path.join(audio_dir, stem + ext)
        if os.path.isfile(cand):
            return cand

    # 2) cAll -> c01 direct replacement
    if "_cAll_" in stem:
        stem_c01 = stem.replace("_cAll_", "_c01_")
        for ext in AUDIO_EXTS:
            cand = os.path.join(audio_dir, stem_c01 + ext)
            if os.path.isfile(cand):
                return cand

    # 3) regex fallback: prefix/suffix pattern
    m = re.match(r"^(.*)_cAll_(.*)$", stem)
    if m:
        prefix, suffix = m.group(1), m.group(2)
        for f in os.listdir(audio_dir):
            if not f.lower().endswith(AUDIO_EXTS):
                continue
            fstem = os.path.splitext(f)[0]
            # something like: prefix_cXX_suffix
            if fstem.startswith(prefix + "_c") and fstem.endswith("_" + suffix):
                return os.path.join(audio_dir, f)

    return None


# ------------------------------------------------------------
# Build features + labels for a single BVH+audio pair
# ------------------------------------------------------------

def build_clip_features_labels(
    bvh_path: str,
    audio_path: str,
    up_axis: str = "auto",
    label_tolerance_sec: float = 0.05,
    user_offset_sec: Optional[float] = None,
    max_auto_offset: float = 1.0,
    hop_length: int = 512,
    save_beats: bool = False,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    For a single BVH + audio pair:
      - load BVH
      - reorient to y-up
      - auto-rig pelvis + feet
      - run extract_beats_v2 to get cues & fused score (features)
      - load audio, detect audio beats
      - build audio & motion envelopes, estimate offset (if user_offset_sec is None)
      - shift audio beats to BVH time & map to frames
      - build frame-level labels y (0/1) with a tolerance window

    Returns:
      X   : (T, D) features
      y   : (T,)   labels 0/1
      fps : float
    """
    print(f"  [clip] BVH={os.path.basename(bvh_path)} | audio={os.path.basename(audio_path)}")

    # --- Load BVH ---
    skeleton, frame_times, total_time, fps = loadbvh(bvh_path)
    fps = float(fps)
    T = len(frame_times)
    if T == 0 or fps <= 0.0:
        raise ValueError("Empty BVH or invalid fps")

    positions0 = stack_positions(skeleton)
    positions = reorient_positions(positions0, up_axis)

    # --- Auto rig (pelvis + feet) ---
    pelvis_idx, LFOOT_IDX, RFOOT_IDX = auto_rig_indices(skeleton, positions)
    print(f"    [rig] pelvis={pelvis_idx}, Lfoot={LFOOT_IDX}, Rfoot={RFOOT_IDX}")

    # --- BeatExtraction v2: compute cues + score (features) ---
    params = BeatParamsV2()
    out = extract_beats_v2(
        positions, fps, JOINT_INDICES, params,
        pelvis_idx=pelvis_idx,
        left_foot_idx=LFOOT_IDX,
        right_foot_idx=RFOOT_IDX,
    )

    C_decel  = out["C_decel"]      # (T,)
    C_pelvis = out["C_pelvis"]     # (T,)
    C_foot   = out["C_foot"]       # (T,)
    C_accel  = out["C_accel"]      # (T,)
    C_rev    = out["C_reversal"]   # (T,)
    score    = out["beat_score"]   # (T,)

    # Feature vector per frame: [score, C_decel, C_pelvis, C_foot, C_accel, C_reversal]
    X = np.stack(
        [score, C_decel, C_pelvis, C_foot, C_accel, C_rev],
        axis=1
    )  # (T, 6)

    # --- Load audio + compute envelopes + beats ---
    print(f"    [audio] loading {audio_path}")
    y_audio, sr = librosa.load(audio_path, sr=None)
    print(f"            sr={sr}, duration={len(y_audio)/sr:.3f}s")

    audio_env, audio_env_times = compute_audio_envelope(y_audio, sr, hop_length)
    motion_env, motion_times   = compute_motion_envelope(positions, frame_times)

    # Beat tracking from audio (ground truth beats in *audio* timeline)
    tempo, beat_frames = librosa.beat.beat_track(
        y=y_audio,
        sr=sr,
        hop_length=hop_length,
        trim=False,
    )
    tempo_val = float(np.atleast_1d(tempo)[0])
    print(f"    [audio] tempo≈{tempo_val:.2f} BPM, beats_detected={len(beat_frames)}")

    beat_times_audio = librosa.frames_to_time(
        beat_frames, sr=sr, hop_length=hop_length
    )

    # --- Estimate or use provided offset ---
    if user_offset_sec is not None:
        offset_sec = float(user_offset_sec)
        print(f"    [offset] using user-specified offset_sec = {offset_sec:.3f} s")
    else:
        offset_sec = estimate_offset_sec_from_env(
            audio_env, audio_env_times,
            motion_env, motion_times,
            max_offset_sec=max_auto_offset,
            dt_grid=0.01,
        )
        print(f"    [offset] auto-estimated offset_sec ≈ {offset_sec:.3f} s")

    # --- Map audio beats -> BVH frames using offset ---
    if beat_times_audio.size == 0:
        print("    [warn] no beats returned by librosa.beat.beat_track.")
        beat_frames_bvh = np.zeros((0,), dtype=int)
    else:
        beat_times = beat_times_audio + offset_sec
        mask = (beat_times >= 0.0) & (beat_times <= total_time)
        beat_times = beat_times[mask]

        if beat_times.size == 0:
            print("    [warn] no beats inside BVH time range after applying offset.")
            beat_frames_bvh = np.zeros((0,), dtype=int)
        else:
            beat_frames_bvh = np.round(beat_times * fps).astype(int)
            beat_frames_bvh = np.clip(beat_frames_bvh, 0, T - 1)
            beat_frames_bvh = np.unique(beat_frames_bvh)
            print(f"    [beats] mapped to {beat_frames_bvh.size} BVH frames.")

    # Optionally save beats for later visualisation/debug
    if save_beats:
        base = re.sub(r"\.bvh$", "", bvh_path, flags=re.IGNORECASE)
        out_beats = base + ".beats.npy"
        np.save(out_beats, beat_frames_bvh)
        print(f"    [beats] saved to {out_beats}")

    # --- Build frame-level labels with tolerance window ---
    y = np.zeros(T, dtype=np.int64)
    if beat_frames_bvh.size > 0:
        tol_frames = int(round(label_tolerance_sec * fps))
        tol_frames = max(0, tol_frames)
        for b in beat_frames_bvh:
            lo = max(0, b - tol_frames)
            hi = min(T, b + tol_frames + 1)
            y[lo:hi] = 1

    return X, y, fps


# ------------------------------------------------------------
# Dataset builder over many BVHs
# ------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--bvh-dir",
        required=True,
        help="Directory containing .bvh files.",
    )
    ap.add_argument(
        "--audio-dir",
        required=True,
        help="Directory containing audio files (mp3/wav/etc.).",
    )
    ap.add_argument(
        "--out",
        default="ml_dataset.npz",
        help="Output .npz path for the dataset.",
    )
    ap.add_argument(
        "--up",
        choices=["auto", "x", "y", "z"],
        default="auto",
        help="Up-axis for BVH reorientation.",
    )
    ap.add_argument(
        "--label-tol-sec",
        type=float,
        default=0.05,
        help="Frames within ±tol seconds of an audio beat are labeled as 1.",
    )
    ap.add_argument(
        "--offset-sec",
        type=float,
        default=None,
        help=(
            "If set, use this fixed audio->BVH offset (sec) for ALL clips. "
            "If omitted, we auto-estimate per clip."
        ),
    )
    ap.add_argument(
        "--max-auto-offset",
        type=float,
        default=1.0,
        help="Max absolute offset (seconds) to search when auto-aligning envelopes.",
    )
    ap.add_argument(
        "--hop-length",
        type=int,
        default=512,
        help="librosa STFT hop length (in samples). 512 is standard.",
    )
    ap.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional: process at most this many BVH files (for quick tests).",
    )
    ap.add_argument(
        "--save-beats",
        action="store_true",
        help="If set, save per-BVH beat frames as <bvh>.beats.npy.",
    )
    args = ap.parse_args()

    bvh_dir = args.bvh_dir
    audio_dir = args.audio_dir
    out_path = args.out
    up_axis = args.up
    label_tol_sec = float(args.label_tol_sec)
    user_offset_sec = args.offset_sec
    max_auto_offset = float(args.max_auto_offset)
    hop_length = int(args.hop_length)
    max_files = args.max_files
    save_beats = bool(args.save_beats)

    # Collect BVH files
    all_bvhs = [
        os.path.join(bvh_dir, f)
        for f in os.listdir(bvh_dir)
        if f.lower().endswith(".bvh")
    ]
    all_bvhs.sort()

    if max_files is not None:
        all_bvhs = all_bvhs[:max_files]

    print(f"[build] found {len(all_bvhs)} BVH files in {bvh_dir}")

    X_list = []
    y_list = []
    fps_list = []
    clip_ids = []

    clip_index = 0

    for bvh_path in all_bvhs:
        audio_path = find_matching_audio(bvh_path, audio_dir)
        if audio_path is None:
            print(f"[skip] no audio match found for {os.path.basename(bvh_path)}")
            continue

        try:
            X_clip, y_clip, fps = build_clip_features_labels(
                bvh_path,
                audio_path,
                up_axis=up_axis,
                label_tolerance_sec=label_tol_sec,
                user_offset_sec=user_offset_sec,
                max_auto_offset=max_auto_offset,
                hop_length=hop_length,
                save_beats=save_beats,
            )
        except Exception as e:
            print(f"[error] failed on {bvh_path}: {e}")
            continue

        T_clip = X_clip.shape[0]
        X_list.append(X_clip)
        y_list.append(y_clip)
        fps_list.append(fps)
        clip_ids.append(np.full(T_clip, clip_index, dtype=np.int64))
        clip_index += 1

    if not X_list:
        print("[build] no data collected; nothing to save.")
        return

    X = np.vstack(X_list)              # (N_frames, D)
    y = np.concatenate(y_list)         # (N_frames,)
    clip_ids_arr = np.concatenate(clip_ids)  # (N_frames,)
    fps_all = np.array(fps_list, dtype=float)  # (n_clips,)

    print(f"[build] final dataset:")
    print(f"        X shape = {X.shape}")
    print(f"        y shape = {y.shape}")
    print(f"        clips   = {len(fps_all)}")

    np.savez_compressed(
        out_path,
        X=X,
        y=y,
        fps_all=fps_all,
        clip_ids=clip_ids_arr,
    )
    print(f"[done] saved dataset to {out_path}")


if __name__ == "__main__":
    main()
