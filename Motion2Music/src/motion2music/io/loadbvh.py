from abc import abstractmethod
from collections.abc import MutableSequence
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Dict, Iterator, List, Tuple, Union

import h5py
import numpy as np

X_ASCII_ORD = ord("X")


@dataclass()
class Joint:
    name: str = field(default="")
    nest_depth: int = field(default=-1)
    parent: Union["Joint", None] = field(default=None)
    offset: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=float))
    n_channels: int = field(default=0)
    d_order: np.ndarray = field(default_factory=lambda: np.asarray([0, 1, 2]))
    order: np.ndarray = field(
        default_factory=lambda: np.array((-1, -1), dtype=np.int32)
    )
    d_xyz: np.ndarray = field(default=None)
    r_xyz: np.ndarray = field(default=None)
    trans: np.ndarray = field(default=None)
    is_root: bool = field(default=False)
    is_end_site: bool = field(default=False)
    joint_index: int = field(default=-1)


class Skeleton(MutableSequence):
    joints: List[Joint]

    @property
    def d_xyz(self) -> np.ndarray:
        return np.array([joint.d_xyz for joint in self.joints])

    def __init__(self, joints: List[Joint] = None):
        self.joints = joints if joints is not None else []

    def __len__(self) -> int:
        return len(self.joints)

    def __getitem__(self, index: int) -> Joint:
        return self.joints[index]

    def __setitem__(self, index: int, value: Joint) -> None:
        self.joints[index] = value

    def __delitem__(self, index: int) -> None:
        del self.joints[index]

    def insert(self, index: int, value: Joint) -> None:
        self.joints.insert(index, value)

    def __iter__(self) -> Iterator[Joint]:
        return iter(self.joints)

    def append(self, joint: Joint) -> None:
        self.joints.append(joint)


@dataclass
class BVHLoader:
    filename: Path
    skeleton: Skeleton = field(default_factory=Skeleton)
    time: float = 0.0
    fps: int = 0
    motion_data: Dict[str, np.ndarray] = field(default_factory=dict)
    frame_times: np.ndarray = field(default_factory=lambda: np.array([]))
    frame_count: int = field(init=False, default=0)
    frame_time: float = field(init=False, default=0.0)

    def load(self):
        hierarchy_section, motion_section = self._get_sections()
        self._parse_hierarchy(hierarchy_section)
        self._parse_motion(motion_section)

    def _get_sections(self) -> Tuple[List[str], List[str]]:
        with open(self.filename, "r") as file:
            lines = file.readlines()

        hierarchy_section = []
        motion_section = []

        has_motion_section_started = False
        for line in lines:
            line = line.strip()
            if "MOTION" in line:
                has_motion_section_started = True
            if has_motion_section_started:
                motion_section.append(line)
            else:
                hierarchy_section.append(line)
        hierarchy_section = hierarchy_section[1:]  # remove "HIERARCHY" line
        motion_section = motion_section[1:]  # remove "MOTION" line
        return hierarchy_section, motion_section

    def _parse_hierarchy(self, hierarchy_section: List[str]):
        # Parse the hierarchy section to populate the skeleton structure
        current_joint: Union[Joint, None] = None
        brace_count = 0
        joint_index = 0
        joints_stack = [None]

        for i, line in enumerate(hierarchy_section):
            if "{" in line:
                brace_count += 1
            elif "}" in line:
                brace_count -= 1
                if joints_stack:
                    joints_stack.pop()
                if joints_stack:
                    current_joint = joints_stack[-1]
            elif "ROOT" in line or "JOINT" in line:
                # ROOT Hips
                # JOINT LHipJoin
                prev_joint = joints_stack[-1]
                assert (
                    "ROOT" in line
                    and brace_count == 0
                    and joint_index == 0
                    and prev_joint is None
                ) or (
                    "JOINT" in line
                    and brace_count >= 1
                    and joint_index >= 1
                    and prev_joint is not None
                )
                joint_name = line.split()[1]
                current_joint = Joint(
                    name=joint_name,
                    nest_depth=brace_count,
                    parent=prev_joint,
                    is_root="ROOT" in line and brace_count == 0,
                    joint_index=joint_index,
                )
                self.skeleton.append(current_joint)
                joints_stack.append(current_joint)
                joint_index += 1
            elif "OFFSET" in line:
                # OFFSET -0.087 1.94 -0.2889
                line_tokens = line.split()[1:]
                offset_numbers = [float(s) for s in line_tokens]
                current_joint.offset = np.asarray(offset_numbers)
                self.skeleton[-1] = current_joint
                joints_stack[-1] = current_joint
            elif "CHANNELS" in line:
                # CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
                line_tokens = line.split()[1:]
                n_channels = int(line_tokens[0])
                if n_channels == 6:
                    # get the first character of Xrotation, Zrotation, Yrotation and remove 88 to get 0, 1, 2
                    order = np.asarray(
                        [ord(s[0]) - X_ASCII_ORD for s in line_tokens[-3:]]
                    )
                elif n_channels == 3:
                    order = np.asarray(
                        [ord(s[0]) - X_ASCII_ORD for s in line_tokens[1:4]]
                    )
                else:
                    raise NotImplementedError(
                        "Channels other than 3 or 6 not implemented"
                    )
                if tuple(sorted(order.tolist())) != (0, 1, 2):
                    raise ValueError(
                        "Cannot read channels order correctly. Should be some permutation of [''X'' ''Y'' ''Z'']."
                    )
                current_joint.order = order
                current_joint.n_channels = n_channels
                self.skeleton[-1] = current_joint
                joints_stack[-1] = current_joint
            elif "End Site" in line:
                prev_joint = joints_stack[-1]
                current_joint = Joint(
                    name="",
                    parent=prev_joint,
                    nest_depth=brace_count,
                    n_channels=0,
                    joint_index=joint_index,
                    is_end_site=True,
                )
                joint_index += 1
                joints_stack.append(current_joint)
                self.skeleton.append(current_joint)

    def _parse_motion(self, motion_section: List[str]):
        # Count total channels across joints (end sites have 0)
        n_channels = sum(j.n_channels for j in self.skeleton)

        # ---- read headers (Frames, Frame Time) robustly ----
        found_frame_count = False
        found_frame_time = False
        data_start_idx = None

        for i, line in enumerate(motion_section):
            tok = line.strip().split()
            if not tok:
                continue
            if (not found_frame_count) and tok[0].lower().startswith("frames"):
                # e.g. "Frames: 123"
                # tokens like ["Frames:", "123"] or ["Frames:", "123", "..."]
                self.frame_count = int(tok[1])
                found_frame_count = True
            elif (not found_frame_time) and tok[0].lower() == "frame" and tok[1].lower().startswith("time"):
                # e.g. "Frame Time: 0.0333333"
                # tokens like ["Frame", "Time:", "0.0333333"]
                self.frame_time = float(tok[2])
                found_frame_time = True
            elif found_frame_count and found_frame_time:
                data_start_idx = i
                break

        if data_start_idx is None:
            raise AssertionError("Error reading BVH file: could not find motion data start.")

        # ---- flatten ALL numeric tokens after headers ----
        nums: List[float] = []
        for line in motion_section[data_start_idx:]:
            for s in line.strip().split():
                # keep only numeric tokens
                try:
                    nums.append(float(s))
                except ValueError:
                    # ignore any stray non-numeric tokens
                    continue

        if n_channels <= 0:
            raise AssertionError("Error reading BVH file: zero channel count.")

        total_values = len(nums)
        if total_values % n_channels != 0:
            raise AssertionError(
                f"Error reading BVH file: motion values ({total_values}) not divisible by channels ({n_channels})."
            )

        frames_found = total_values // n_channels
        # If the declared Frames differ from what we actually have, prefer the actual data.
        if self.frame_count != frames_found:
            # You can switch this to a hard assert if you prefer to fail fast.
            # For robustness, we trust the data but warn via print.
            print(f"[BVHLoader] Warning: header Frames={self.frame_count} "
                  f"but data contains {frames_found} frames. Using {frames_found}.")
            self.frame_count = frames_found

        raw_motion_data = np.asarray(nums, dtype=float).reshape(self.frame_count, n_channels)

        # ---- timing (fix off-by-one total time) ----
        self.fps = int(round(1.0 / self.frame_time))
        # Total duration is (N-1)*dt so that frame_times[-1] equals the last frame time.
        self.time = (self.frame_count - 1) * self.frame_time
        self.frame_times = np.arange(self.frame_count, dtype=float) * self.frame_time

        # ---- fill joint motion buffers and forward kinematics ----
        self._apply_initial_motion_data_to_skeleton(raw_motion_data)
        self._apply_kinematics_to_skeleton()

    def _apply_initial_motion_data_to_skeleton(self, raw_motion_data: np.ndarray):
        channel_count = 0
        for joint_idx, joint in enumerate(self.skeleton):
            if joint.n_channels == 6:  # root node
                # shape is Fx3
                d_xyz = joint.offset + raw_motion_data[:, channel_count + joint.d_order]
                d_xyz = d_xyz.T
                r_xyz = np.empty((3, self.frame_count))
                r_xyz[joint.order, :] = raw_motion_data[
                    :, channel_count + np.asarray([3, 4, 5])
                ].T
                trans = np.empty(shape=(4, 4, self.frame_count))
                for f_idx in range(self.frame_count):
                    trans[:, :, f_idx] = transformation_matrix(
                        d_xyz[:, f_idx], r_xyz[:, f_idx], order=joint.order
                    )
            elif joint.n_channels == 3:  # joint node
                r_xyz = np.empty((3, self.frame_count))
                r_xyz[joint.order, :] = raw_motion_data[
                    :, channel_count + np.asarray([0, 1, 2])
                ].T
                d_xyz = np.empty(shape=(3, self.frame_count))
                d_xyz.fill(np.nan)
                trans = np.empty(shape=(4, 4, self.frame_count))
                trans.fill(np.nan)
            elif joint.n_channels == 0:  # end node
                d_xyz = np.empty(shape=(3, self.frame_count))
                d_xyz[...] = np.nan
                trans = np.empty(shape=0)
                r_xyz = np.empty(shape=0)
            else:
                raise ValueError(
                    f"Motion with channels {joint.n_channels} not implemented."
                )

            joint.d_xyz = d_xyz
            joint.r_xyz = r_xyz
            joint.trans = trans
            channel_count += joint.n_channels

    def _apply_kinematics_to_skeleton(self):
        for joint_idx, joint in enumerate(self.skeleton):
            if joint.is_end_site or joint.is_root:
                continue

            parent = joint.parent
            for fi in range(self.frame_count):
                transM = transformation_matrix(
                    joint.offset, joint.r_xyz[:, fi], joint.order
                )
                joint.trans[:, :, fi] = parent.trans[:, :, fi] @ transM
                joint.d_xyz[:, fi] = joint.trans[[0, 1, 2], 3, fi]

        end_size_joints = [j for j in self.skeleton if j.is_end_site]
        for joint in end_size_joints:
            parent = joint.parent
            for fi in range(self.frame_count):
                transM = np.r_[np.c_[np.eye(3), joint.offset], [[0, 0, 0, 1]]]
                transM = parent.trans[:, :, fi] @ transM
                joint.d_xyz[:, fi] = transM[[0, 1, 2], 3]


def transformation_matrix(displ, rxyz, order):
    """
    Constructs the transformation matrix for given displacement (displ)
    and rotations (rxyz). The vector rxyz is of length three corresponding to
    rotations around the X, Y, Z axes.

    The third input, order, is a list indicating which order to apply
    the planar rotations. E.g., [3, 1, 2] refers applying rotations rxyz
    around Z first, then X, then Y.

    Precalculating the cosines and sines saves around 38% in execution time.
    """

    # deg = np.deg2rad(np.mod(rxyz, 360.0))
    deg = np.deg2rad(rxyz)
    c = np.cos(deg)
    s = np.sin(deg)

    RxRyRz = np.zeros((3, 3, 3))

    RxRyRz[:, :, 0] = np.array([[1, 0, 0], [0, c[0], -s[0]], [0, s[0], c[0]]])
    RxRyRz[:, :, 1] = np.array([[c[1], 0, s[1]], [0, 1, 0], [-s[1], 0, c[1]]])
    RxRyRz[:, :, 2] = np.array([[c[2], -s[2], 0], [s[2], c[2], 0], [0, 0, 1]])

    rotM = np.dot(
        np.dot(RxRyRz[:, :, order[0]], RxRyRz[:, :, order[1]]),
        RxRyRz[:, :, order[2]],
    )

    transM = np.vstack(
        (np.hstack((rotM, np.array(displ).reshape(3, 1))), np.array([0, 0, 0, 1]))
    )

    return transM


def loadbvh(filename: Union[str, PathLike]) -> Tuple[Skeleton, np.ndarray, float, int]:
    filename = Path(filename).with_suffix(".bvh")
    bvh_loader = BVHLoader(filename)
    bvh_loader.load()
    return (
        bvh_loader.skeleton,
        bvh_loader.frame_times,
        bvh_loader.time,
        bvh_loader.fps,
    )


def loadmat(filename: Union[str, PathLike]) -> Dict[str, np.ndarray]:
    def correct_shape(arr):
        if arr.ndim == 1 and np.array_equal(arr, np.zeros(2)):
            arr = np.empty(shape=0)
        elif arr.ndim >= 2:
            # Reverse the axes for multi-dimensional arrays to match MATLAB's column-major order
            arr = np.transpose(arr, axes=range(arr.ndim)[::-1])
        return arr

    with h5py.File(filename, "r") as f:
        data = {k: correct_shape(np.asarray(v)) for k, v in f.items()}
    return data


if __name__ == "__main__":
    import sys
    from pathlib import Path

    def iter_bvh_inputs(args):
        """Yield BVH paths from CLI args: file, dir, or glob."""
        if not args:
            # Default: look in ./BVHs for *.bvh
            yield from Path("BVHs").glob("*.bvh")
            return
        for arg in args:
            # Handle glob patterns in the current working dir
            if any(ch in arg for ch in "*?[]"):
                for p in Path().glob(arg):
                    if p.is_file() and p.suffix.lower() == ".bvh":
                        yield p
                continue

            p = Path(arg)
            if p.is_dir():
                yield from p.glob("*.bvh")
            elif p.is_file() and p.suffix.lower() == ".bvh":
                yield p

    any_found = False
    for bvh_path in iter_bvh_inputs(sys.argv[1:]):
        any_found = True
        # Correct unpacking: your loader returns (skeleton, frame_times, total_time, fps)
        skeleton, frame_times, total_time, fps = loadbvh(bvh_path)

        n_frames = len(frame_times)
        dt = (frame_times[1] - frame_times[0]) if n_frames > 1 else float("nan")

        print(f"\nLoaded BVH: {bvh_path}")
        print(f" Root joint: {skeleton[0].name if len(skeleton) else '(none)'}")
        print(f" Joints: {len(skeleton)}")
        print(f" Frames: {n_frames}")
        print(f" Frame time: {dt:.6f} s  |  FPS: {fps:.3f}")
        print(f" Duration: {total_time:.3f} s")
        print("-" * 40)

    if not any_found:
        print("No BVH files found. Pass a BVH file, directory, or glob pattern (e.g., BVHs/*.bvh).")
