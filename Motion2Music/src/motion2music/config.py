"""Central configuration constants.

This project started as a set of standalone scripts.
After reorganizing folders, keeping *all* code importable on both Windows
(case-insensitive) and Linux (case-sensitive) requires a single source of truth.

Adjust JOINT_INDICES if you want the beat extractor to consider only a subset of joints.
"""

from __future__ import annotations

# If you know the canonical joint count for your BVH rig, set it here.
# It's currently used only for sanity / documentation (most code clamps indices anyway).
N_TOTAL_JOINTS: int = 24

# Default: use the first N_TOTAL_JOINTS joints.
# For BVHs with different joint counts, the extractor will clamp to the valid range.
JOINT_INDICES = list(range(N_TOTAL_JOINTS))
