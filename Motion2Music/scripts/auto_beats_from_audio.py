#!/usr/bin/env python3

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import argparse
import re
import os

import numpy as np
import librosa

from motion2music.io.loadbvh import loadbvh


def stack_positions(skeleton):
    """
    Convert BVH skeleton joints to a (T, J, 3) array of positions.
    Each joint has d_xyz of shape (3, T).
    """
    J = len(skeleton)
    T = skeleton[0].d_xyz.shape[1]
    P = np.zeros((T, J, 3), dtype=float)
    for j in range(J):
        P[:, j, :] = skeleton[j].d_xyz.T  # (3,T) -> (T,3)
    return P


def compute_motion_envelope(positions: np.ndarray, frame_times: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Motion envelope: median body speed over joints.
    This does NOT use the beat algorithm; it's just low-level kinematics.
    """
    positions = np.asarray(positions, dtype=float)
    assert positions.ndim == 3 and positions.shape[2] == 3
    T = positions.shape[0]
    if T < 2:
        return np.zeros(T, dtype=float), frame_times

    # approximate dt from frame_times (BVH)
    if frame_times is not None and len(frame_times) == T:
        dt = float(np.median(np.diff(frame_times)))
    else:
        # if frame_times missing for some reason, assume 1.0
        dt = 1.0

    # velocity via finite differences
    V = np.gradient(positions, dt, axis=0)           # (T, J, 3)
    speed_j = np.linalg.norm(V, axis=2)             # (T, J)
    env = np.median(speed_j, axis=1)                # (T,)
    times = frame_times if frame_times is not None else np.arange(T) * dt
    return env, np.asarray(times, dtype=float)


def compute_audio_onset_envelope(y: np.ndarray, sr: int, hop_length: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Audio onset strength envelope and its time axis (seconds).
    """
    # onset envelope
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    oenv_frames = np.arange(len(oenv))
    oenv_times = librosa.frames_to_time(oenv_frames, sr=sr, hop_length=hop_length)
    return oenv, oenv_times


def estimate_offset_audio_to_motion(
    audio_env: np.ndarray,
    audio_times: np.ndarray,
    motion_env: np.ndarray,
    motion_times: np.ndarray,
    max_offset_sec: float = 1.0,
    dt_grid: float = 0.01,
) -> float:
    """
    Estimate a global time offset (seconds) so that:
        motion(t) ≈ audio(t + offset)

    Uses cross-correlation between:
        - audio onset envelope (audio-only)
        - motion energy envelope (motion-only)
    """
    audio_env = np.asarray(audio_env, dtype=float)
    audio_times = np.asarray(audio_times, dtype=float)
    motion_env = np.asarray(motion_env, dtype=float)
    motion_times = np.asarray(motion_times, dtype=float)

    if audio_env.size < 5 or motion_env.size < 5:
        return 0.0

    # Overlapping time window
    t_min = max(audio_times[0], motion_times[0])
    t_max = min(audio_times[-1], motion_times[-1])
    if t_max <= t_min + 5 * dt_grid:
        # Too little overlap, give up
        return 0.0

    grid = np.arange(t_min, t_max, dt_grid)
    if grid.size < 10:
        return 0.0

    # Resample both envelopes to the common grid
    audio_grid = np.interp(grid, audio_times, audio_env)
    motion_grid = np.interp(grid, motion_times, motion_env)

    # Normalize to zero-mean, unit-variance
    audio_grid = (audio_grid - audio_grid.mean()) / (audio_grid.std() + 1e-9)
    motion_grid = (motion_grid - motion_grid.mean()) / (motion_grid.std() + 1e-9)

    # Cross-correlation
    corr = np.correlate(audio_grid, motion_grid, mode="full")
    lags = np.arange(-len(grid) + 1, len(grid))

    # Restrict to reasonable offsets
    max_lag_steps = int(max_offset_sec / dt_grid)
    mask = np.abs(lags) <= max_lag_steps
    if not np.any(mask):
        return 0.0

    subcorr = corr[mask]
    sublags = lags[mask]

    best_idx = int(np.argmax(subcorr))
    best_lag = int(sublags[best_idx])

    # If motion is delayed by +delay, best_lag ≈ -delay/dt_grid
    # We want offset_sec such that: beat_time_shifted = beat_time + offset_sec
    offset_sec = -best_lag * dt_grid
    return float(offset_sec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True, help="Path to audio file (mp3/wav/etc.)")
    ap.add_argument("--bvh", required=True, help="Path to BVH file")
    ap.add_argument(
        "--offset-sec",
        type=float,
        default=0.0,
        help="Extra manual time offset (seconds) to add after automatic alignment (can be negative).",
    )
    ap.add_argument(
        "--hop-length",
        type=int,
        default=512,
        help="Hop length for librosa onset/beat calculations.",
    )
    ap.add_argument(
        "--max-auto-offset",
        type=float,
        default=1.0,
        help="Maximum absolute auto-offset (seconds) searched via cross-correlation.",
    )

    args = ap.parse_args()

    # --------------------
    # 1) Load audio
    # --------------------
    print(f"[audio] loading {args.audio}")
    y, sr = librosa.load(args.audio, sr=None, mono=True)
    duration = len(y) / float(sr)
    print(f"        sr={sr}, duration={duration:.3f}s")

    hop_length = int(args.hop_length)

    # Audio beats
    tempo, beat_frames = librosa.beat.beat_track(
        y=y,
        sr=sr,
        hop_length=hop_length,
        trim=False,
    )
    tempo_arr = np.atleast_1d(tempo)
    tempo_val = float(tempo_arr[0])
    beat_frames = np.asarray(beat_frames, dtype=int)
    beat_times_audio = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)

    print(f"[audio] estimated tempo ~ {tempo_val:.2f} BPM, beats detected: {len(beat_frames)}")

    # Onset envelope for offset estimation
    audio_env, audio_times = compute_audio_onset_envelope(y, sr, hop_length)

    # --------------------
    # 2) Load BVH & motion envelope
    # --------------------
    print(f"[bvh] loading {args.bvh}")
    skeleton, frame_times, total_time, fps = loadbvh(args.bvh)
    positions = stack_positions(skeleton)  # (T, J, 3)
    T = positions.shape[0]

    print(f"[bvh] frames={T}, fps={fps:.2f}, duration={T / fps:.3f}s")

    motion_env, motion_times = compute_motion_envelope(positions, frame_times)

    # --------------------
    # 3) Estimate automatic offset
    # --------------------
    auto_offset_sec = estimate_offset_audio_to_motion(
        audio_env=audio_env,
        audio_times=audio_times,
        motion_env=motion_env,
        motion_times=motion_times,
        max_offset_sec=float(args.max_auto_offset),
        dt_grid=0.01,
    )
    print(f"[offset] auto-estimated ≈ {auto_offset_sec:.3f}s")

    # Combine auto-offset with user-supplied offset
    total_offset_sec = auto_offset_sec + float(args.offset_sec)
    if abs(args.offset_sec) > 1e-6:
        print(f"[offset] user extra offset {args.offset_sec:+.3f}s → total={total_offset_sec:+.3f}s")
    else:
        print(f"[offset] total offset applied to audio beats: {total_offset_sec:+.3f}s")

    # --------------------
    # 4) Apply offset to audio beats and map to BVH frames
    # --------------------
    beat_times_shifted = beat_times_audio + total_offset_sec
    beat_frames_bvh = np.round(beat_times_shifted * fps).astype(int)

    # Keep only beats within BVH range
    valid = (beat_frames_bvh >= 0) & (beat_frames_bvh < T)
    beat_frames_bvh = beat_frames_bvh[valid]
    beat_frames_bvh = np.unique(beat_frames_bvh)  # sort & remove duplicates

    print(f"[beats] after offset + trimming: {beat_frames_bvh.size} beats in BVH frame indices")

    # --------------------
    # 5) Save to <bvh>.beats.npy
    # --------------------
    base = re.sub(r"\.bvh$", "", args.bvh, flags=re.IGNORECASE)
    outpath = base + ".beats.npy"
    np.save(outpath, beat_frames_bvh)
    print(f"[done] saved beats to {outpath}")


if __name__ == "__main__":
    main()
