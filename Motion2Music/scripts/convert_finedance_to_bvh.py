#!/usr/bin/env python3
"""
convert_finedance_to_bvh.py

Convert FineDance motion tensors (.npy) into BVH files and place them in a
Motion2Music-compatible dataset folder:

  <out_dataset_dir>/
    bvh/
      <stem>.bvh
    audio/
      <stem>.wav

FineDance motion format expected here: (T, 315) where
  - first 3 values: root translation
  - remaining 312 values: 52 joints * 6D rotation representation
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


JOINT_NAMES = [
    "pelvis",
    "left_hip",
    "right_hip",
    "spine1",
    "left_knee",
    "right_knee",
    "spine2",
    "left_ankle",
    "right_ankle",
    "spine3",
    "left_foot",
    "right_foot",
    "neck",
    "left_collar",
    "right_collar",
    "head",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_index1",
    "left_index2",
    "left_index3",
    "left_middle1",
    "left_middle2",
    "left_middle3",
    "left_pinky1",
    "left_pinky2",
    "left_pinky3",
    "left_ring1",
    "left_ring2",
    "left_ring3",
    "left_thumb1",
    "left_thumb2",
    "left_thumb3",
    "right_index1",
    "right_index2",
    "right_index3",
    "right_middle1",
    "right_middle2",
    "right_middle3",
    "right_pinky1",
    "right_pinky2",
    "right_pinky3",
    "right_ring1",
    "right_ring2",
    "right_ring3",
    "right_thumb1",
    "right_thumb2",
    "right_thumb3",
]

# parent index for each joint; root has -1
JOINT_PARENTS = [
    -1,  # pelvis
    0,   # left_hip
    0,   # right_hip
    0,   # spine1
    1,   # left_knee
    2,   # right_knee
    3,   # spine2
    4,   # left_ankle
    5,   # right_ankle
    6,   # spine3
    7,   # left_foot
    8,   # right_foot
    9,   # neck
    12,  # left_collar
    12,  # right_collar
    12,  # head
    13,  # left_shoulder
    14,  # right_shoulder
    16,  # left_elbow
    17,  # right_elbow
    18,  # left_wrist
    19,  # right_wrist
    20,  # left_index1
    22,  # left_index2
    23,  # left_index3
    20,  # left_middle1
    25,  # left_middle2
    26,  # left_middle3
    20,  # left_pinky1
    28,  # left_pinky2
    29,  # left_pinky3
    20,  # left_ring1
    31,  # left_ring2
    32,  # left_ring3
    20,  # left_thumb1
    34,  # left_thumb2
    35,  # left_thumb3
    21,  # right_index1
    37,  # right_index2
    38,  # right_index3
    21,  # right_middle1
    40,  # right_middle2
    41,  # right_middle3
    21,  # right_pinky1
    43,  # right_pinky2
    44,  # right_pinky3
    21,  # right_ring1
    46,  # right_ring2
    47,  # right_ring3
    21,  # right_thumb1
    49,  # right_thumb2
    50,  # right_thumb3
]

# Approximate rest offsets in centimeters; enough for stable kinematics / LMA.
JOINT_OFFSETS = np.array(
    [
        [0.0, 0.0, 0.0],    # pelvis
        [7.0, -9.0, 0.0],   # left_hip
        [-7.0, -9.0, 0.0],  # right_hip
        [0.0, 9.0, 0.0],    # spine1
        [0.0, -41.0, 0.0],  # left_knee
        [0.0, -41.0, 0.0],  # right_knee
        [0.0, 10.0, 0.0],   # spine2
        [0.0, -41.0, 0.0],  # left_ankle
        [0.0, -41.0, 0.0],  # right_ankle
        [0.0, 10.0, 0.0],   # spine3
        [0.0, -8.0, 12.0],  # left_foot
        [0.0, -8.0, 12.0],  # right_foot
        [0.0, 11.0, 0.0],   # neck
        [5.0, 8.0, 0.0],    # left_collar
        [-5.0, 8.0, 0.0],   # right_collar
        [0.0, 12.0, 0.0],   # head
        [14.0, 0.0, 0.0],   # left_shoulder
        [-14.0, 0.0, 0.0],  # right_shoulder
        [24.0, 0.0, 0.0],   # left_elbow
        [-24.0, 0.0, 0.0],  # right_elbow
        [22.0, 0.0, 0.0],   # left_wrist
        [-22.0, 0.0, 0.0],  # right_wrist
        [6.0, 0.0, 4.0],    # left_index1
        [4.0, 0.0, 0.0],    # left_index2
        [3.0, 0.0, 0.0],    # left_index3
        [7.0, 0.0, 1.0],    # left_middle1
        [4.0, 0.0, 0.0],    # left_middle2
        [3.0, 0.0, 0.0],    # left_middle3
        [5.0, 0.0, -4.0],   # left_pinky1
        [3.0, 0.0, 0.0],    # left_pinky2
        [2.5, 0.0, 0.0],    # left_pinky3
        [6.0, 0.0, -2.0],   # left_ring1
        [4.0, 0.0, 0.0],    # left_ring2
        [3.0, 0.0, 0.0],    # left_ring3
        [3.0, -2.0, 3.0],   # left_thumb1
        [3.0, 0.0, 0.0],    # left_thumb2
        [2.5, 0.0, 0.0],    # left_thumb3
        [-6.0, 0.0, 4.0],   # right_index1
        [-4.0, 0.0, 0.0],   # right_index2
        [-3.0, 0.0, 0.0],   # right_index3
        [-7.0, 0.0, 1.0],   # right_middle1
        [-4.0, 0.0, 0.0],   # right_middle2
        [-3.0, 0.0, 0.0],   # right_middle3
        [-5.0, 0.0, -4.0],  # right_pinky1
        [-3.0, 0.0, 0.0],   # right_pinky2
        [-2.5, 0.0, 0.0],   # right_pinky3
        [-6.0, 0.0, -2.0],  # right_ring1
        [-4.0, 0.0, 0.0],   # right_ring2
        [-3.0, 0.0, 0.0],   # right_ring3
        [-3.0, -2.0, 3.0],  # right_thumb1
        [-3.0, 0.0, 0.0],   # right_thumb2
        [-2.5, 0.0, 0.0],   # right_thumb3
    ],
    dtype=np.float64,
)


def _normalize(v: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.clip(n, eps, None)


def rot6d_to_matrix(rot_6d: np.ndarray) -> np.ndarray:
    """
    rot_6d: (..., 6)
    returns: (..., 3, 3)
    """
    a1 = rot_6d[..., 0:3]
    a2 = rot_6d[..., 3:6]
    b1 = _normalize(a1)
    b2 = a2 - np.sum(b1 * a2, axis=-1, keepdims=True) * b1
    b2 = _normalize(b2)
    b3 = np.cross(b1, b2, axis=-1)
    return np.stack([b1, b2, b3], axis=-1)


def _leaf_end_offset(joint_name: str) -> np.ndarray:
    if joint_name.startswith("left_"):
        return np.array([2.0, 0.0, 0.0], dtype=float)
    if joint_name.startswith("right_"):
        return np.array([-2.0, 0.0, 0.0], dtype=float)
    if "foot" in joint_name:
        return np.array([0.0, 0.0, 4.0], dtype=float)
    return np.array([0.0, 4.0, 0.0], dtype=float)


def write_bvh(
    out_bvh: Path,
    root_xyz: np.ndarray,
    joint_euler_zxy_deg: np.ndarray,
    fps: float,
) -> None:
    """
    root_xyz: (T,3)
    joint_euler_zxy_deg: (T,52,3) in Z,X,Y order (degrees)
    """
    t_frames = root_xyz.shape[0]
    if joint_euler_zxy_deg.shape[0] != t_frames:
        raise ValueError("root and rotation frame count mismatch")
    if joint_euler_zxy_deg.shape[1] != len(JOINT_NAMES):
        raise ValueError("expected 52 joints")

    children: dict[int, list[int]] = {i: [] for i in range(len(JOINT_NAMES))}
    for i, p in enumerate(JOINT_PARENTS):
        if p >= 0:
            children[p].append(i)

    lines: list[str] = []
    lines.append("HIERARCHY")

    def rec_joint(i: int, indent: int) -> None:
        pad = "  " * indent
        if i == 0:
            lines.append(f"{pad}ROOT {JOINT_NAMES[i]}")
        else:
            lines.append(f"{pad}JOINT {JOINT_NAMES[i]}")
        lines.append(f"{pad}" + "{")
        ox, oy, oz = JOINT_OFFSETS[i]
        lines.append(f"{pad}  OFFSET {ox:.6f} {oy:.6f} {oz:.6f}")
        if i == 0:
            lines.append(
                f"{pad}  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation"
            )
        else:
            lines.append(f"{pad}  CHANNELS 3 Zrotation Xrotation Yrotation")

        if children[i]:
            for c in children[i]:
                rec_joint(c, indent + 1)
        else:
            ex, ey, ez = _leaf_end_offset(JOINT_NAMES[i])
            lines.append(f"{pad}  End Site")
            lines.append(f"{pad}  " + "{")
            lines.append(f"{pad}    OFFSET {ex:.6f} {ey:.6f} {ez:.6f}")
            lines.append(f"{pad}  " + "}")

        lines.append(f"{pad}" + "}")

    rec_joint(0, 0)

    lines.append("MOTION")
    lines.append(f"Frames: {t_frames}")
    lines.append(f"Frame Time: {1.0 / float(fps):.8f}")

    for fi in range(t_frames):
        vals: list[float] = []
        vals.extend(root_xyz[fi].tolist())
        vals.extend(joint_euler_zxy_deg[fi, 0, :].tolist())
        for ji in range(1, len(JOINT_NAMES)):
            vals.extend(joint_euler_zxy_deg[fi, ji, :].tolist())
        lines.append(" ".join(f"{v:.6f}" for v in vals))

    out_bvh.parent.mkdir(parents=True, exist_ok=True)
    out_bvh.write_text("\n".join(lines) + "\n", encoding="utf-8")


def convert_single_motion(motion_path: Path, trans_scale: float, fps: float) -> tuple[np.ndarray, np.ndarray]:
    arr = np.load(motion_path)
    if arr.ndim != 2 or arr.shape[1] != 315:
        raise ValueError(f"Unexpected motion shape {arr.shape} for {motion_path.name}. Expected (T,315).")

    root_xyz = arr[:, 0:3].astype(np.float64) * float(trans_scale)
    rot6d = arr[:, 3:].astype(np.float64).reshape(arr.shape[0], 52, 6)
    mats = rot6d_to_matrix(rot6d)

    # Convert to ZXY Euler in degrees to match BVH channels order.
    eul = Rotation.from_matrix(mats.reshape(-1, 3, 3)).as_euler("zxy", degrees=True)
    eul = eul.reshape(arr.shape[0], 52, 3).astype(np.float64)
    return root_xyz, eul


def _link_or_copy(src: Path, dst: Path, use_links: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    if use_links:
        try:
            os.link(src, dst)
            return
        except Exception:
            pass
    shutil.copy2(src, dst)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--finedance-root", type=str, required=True, help="FineDance root folder (contains motion/, music_wav/).")
    ap.add_argument("--out-dataset-dir", type=str, required=True, help="Output dataset folder under TrainData (e.g. .../TrainData/FineDance)")
    ap.add_argument("--trans-scale", type=float, default=100.0, help="Scale factor for root translation before writing BVH.")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--limit", type=int, default=0, help="Debug limit; 0 = all.")
    ap.add_argument("--copy-audio", action="store_true", help="Copy audio files instead of hard-linking them.")
    args = ap.parse_args()

    fd_root = Path(args.finedance_root).resolve()
    motion_dir = fd_root / "motion"
    audio_dir = fd_root / "music_wav"
    if not motion_dir.exists() or not audio_dir.exists():
        raise SystemExit(f"FineDance root must contain motion/ and music_wav/: {fd_root}")

    out_root = Path(args.out_dataset_dir).resolve()
    out_bvh = out_root / "bvh"
    out_audio = out_root / "audio"
    out_bvh.mkdir(parents=True, exist_ok=True)
    out_audio.mkdir(parents=True, exist_ok=True)

    motion_stems = {p.stem: p for p in sorted(motion_dir.glob("*.npy"))}
    audio_stems = {p.stem: p for p in sorted(audio_dir.glob("*.wav"))}
    common = sorted(set(motion_stems.keys()) & set(audio_stems.keys()))
    only_audio = sorted(set(audio_stems.keys()) - set(motion_stems.keys()))

    if args.limit > 0:
        common = common[: int(args.limit)]

    print(f"[finedance] root={fd_root}")
    print(f"[pairs] motion={len(motion_stems)} audio={len(audio_stems)} common={len(common)}")
    if only_audio:
        print(f"[warn] audio-only stems (no motion): {only_audio}")

    ok = 0
    bad = 0
    for i, stem in enumerate(common, start=1):
        m_path = motion_stems[stem]
        a_path = audio_stems[stem]
        bvh_path = out_bvh / f"{stem}.bvh"
        wav_path = out_audio / f"{stem}.wav"

        try:
            root_xyz, eul = convert_single_motion(
                motion_path=m_path,
                trans_scale=float(args.trans_scale),
                fps=float(args.fps),
            )
            write_bvh(
                out_bvh=bvh_path,
                root_xyz=root_xyz,
                joint_euler_zxy_deg=eul,
                fps=float(args.fps),
            )
            _link_or_copy(a_path, wav_path, use_links=not bool(args.copy_audio))
            ok += 1
        except Exception as e:
            bad += 1
            print(f"[error] {stem}: {e}")

        if i % 20 == 0 or i == len(common):
            print(f"[progress] {i}/{len(common)} ok={ok} bad={bad}")

    print(f"[done] out={out_root}")
    print(f"[done] converted_ok={ok} failed={bad}")
    print(f"[done] bvh_dir={out_bvh}")
    print(f"[done] audio_dir={out_audio}")


if __name__ == "__main__":
    main()
