from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# widen_labels_in_dataset.py
import argparse
import numpy as np


def widen_labels_per_clip(y, clip_ids, radius):
    """
    y:        (N,) int array (0/1)
    clip_ids: (N,) int array (clip index per frame)
    radius:   int, how many frames left/right to turn into 1 around each positive
    """
    y = np.asarray(y, dtype=int)
    clip_ids = np.asarray(clip_ids, dtype=int)
    y_new = y.copy()

    if radius <= 0:
        return y_new

    unique_clips = np.unique(clip_ids)
    total_pos_before = int(y.sum())
    total_pos_after = 0

    for clip in unique_clips:
        idx = np.where(clip_ids == clip)[0]  # global indices of this clip
        yc = y[idx].copy()                   # local labels for this clip
        Tc = yc.shape[0]

        pos = np.where(yc == 1)[0]          # local positions of beats
        for p in pos:
            a = max(0, p - radius)
            b = min(Tc, p + radius + 1)     # [a, b)
            yc[a:b] = 1

        y_new[idx] = yc
        total_pos_after += int(yc.sum())

    print(f"[widen] positives before={total_pos_before}, after={total_pos_after}")
    return y_new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Path to original ml_dataset_aist.npz")
    ap.add_argument("--out", dest="out_path", required=True, help="Path to save widened dataset")
    ap.add_argument(
        "--radius",
        type=int,
        default=2,
        help="Number of frames left/right to mark as positive around each beat (default=2).",
    )
    args = ap.parse_args()

    print(f"[load] {args.in_path}")
    data = np.load(args.in_path)

    if not {"X", "y", "clip_ids"}.issubset(data.files):
        raise ValueError(f"Dataset must contain X, y, clip_ids. Found keys: {data.files}")

    X = data["X"]
    y = data["y"].astype(int)
    clip_ids = data["clip_ids"].astype(int)

    print(f"[data] X shape={X.shape}, y shape={y.shape}")
    print(f"[data] positives before={int(y.sum())} ({100.0 * y.mean():.2f}% of frames)")

    y_wide = widen_labels_per_clip(y, clip_ids, radius=args.radius)
    print(f"[data] positives after={int(y_wide.sum())} ({100.0 * y_wide.mean():.2f}% of frames)")

    # Save everything, keep original y as y_orig for debugging
    out_dict = dict(data)  # copy all existing arrays
    out_dict["y_orig"] = y
    out_dict["y"] = y_wide

    print(f"[save] -> {args.out_path}")
    np.savez(args.out_path, **out_dict)


if __name__ == "__main__":
    main()
