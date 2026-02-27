#!/usr/bin/env python3
"""
make_final_model.py

Automates:
  datasets_root/
    DB1/{bvh/, audio/}
    DB2/{bvh/, audio/}
    ...

Pipeline:
  - build_ml_dataset.py for each DB
  - merge datasets (offset clip_ids)
  - widen_labels_in_dataset.py
  - train_beat_refiner.py
  - save final .joblib to requested output directory/name
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


def find_child_dir(parent: Path, candidates: list[str]) -> Path | None:
    for name in candidates:
        p = parent / name
        if p.exists() and p.is_dir():
            return p
    return None


def add_py_paths(env: dict, repo_root: Path) -> dict:
    # Make the existing scripts robust no matter where you run from.
    extra = [
        str(repo_root),
        str(repo_root / "src"),
        str(repo_root / "src" / "io"),
        str(repo_root / "src" / "beats"),
        str(repo_root / "src" / "ml"),
        str(repo_root / "scripts"),
    ]
    old = env.get("PYTHONPATH", "")
    sep = os.pathsep
    env["PYTHONPATH"] = sep.join([p for p in ([old] + extra) if p])
    return env


def run(cmd: list[str], env: dict) -> None:
    print("\n[cmd]", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def merge_npz(npz_paths: list[Path], out_path: Path) -> dict:
    X_list, y_list, clip_ids_list, fps_list = [], [], [], []
    clip_offset = 0
    total_clips = 0

    for p in npz_paths:
        data = np.load(p)
        X = data["X"]
        y = data["y"]
        clip_ids = data["clip_ids"]
        fps_all = data["fps_all"]

        # offset clip ids so each DB has unique clip IDs
        clip_ids = clip_ids.astype(np.int64) + clip_offset

        X_list.append(X)
        y_list.append(y)
        clip_ids_list.append(clip_ids)
        fps_list.append(fps_all)

        clip_offset += len(fps_all)
        total_clips += len(fps_all)

        print(f"[merge] {p.name}: frames={X.shape[0]}, clips={len(fps_all)}")

    X_all = np.concatenate(X_list, axis=0)
    y_all = np.concatenate(y_list, axis=0).astype(np.int8)
    clip_ids_all = np.concatenate(clip_ids_list, axis=0).astype(np.int64)
    fps_all = np.concatenate(fps_list, axis=0).astype(np.float32)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, X=X_all, y=y_all, clip_ids=clip_ids_all, fps_all=fps_all)

    print(f"\n[merged] frames={X_all.shape[0]}, clips={total_clips}, D={X_all.shape[1]}")
    print(f"[save] merged dataset -> {out_path}")
    return {"frames": X_all.shape[0], "clips": total_clips, "D": X_all.shape[1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets-root", required=True,
                    help="Folder containing DB subfolders. Each DB folder must contain bvh/ and audio/ inside.")
    ap.add_argument("--out-dir", required=True, help="Directory to save final .joblib")
    ap.add_argument("--out-name", required=True, help="Final joblib filename (e.g. beat_refiner_final.joblib)")

    # dataset build defaults (same spirit as your usual workflow)
    ap.add_argument("--up", choices=["auto", "x", "y", "z"], default="auto")
    ap.add_argument("--label-tol-sec", type=float, default=0.05)
    ap.add_argument("--max-auto-offset", type=float, default=1.0)
    ap.add_argument("--offset-sec", type=float, default=None, help="If set, use fixed offset for ALL clips.")
    ap.add_argument("--hop-length", type=int, default=512)
    ap.add_argument("--max-files-per-db", type=int, default=None, help="Debug: limit files per DB.")
    ap.add_argument("--save-beats", action="store_true", help="Save <bvh>.beats.npy per clip (debug).")

    # label widening (helps stability a lot)
    ap.add_argument("--widen-radius", type=int, default=2, help="Frames to widen positives per side.")

    # intermediate handling
    ap.add_argument("--work-dir", default=None, help="Optional work dir for intermediate npz files.")
    ap.add_argument("--keep-work", action="store_true", help="Do not delete work dir at end.")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    datasets_root = Path(args.datasets_root).expanduser().resolve()

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    out_name = args.out_name
    if not out_name.lower().endswith(".joblib"):
        out_name += ".joblib"
    out_model_path = out_dir / out_name

    # locate scripts
    build_py = repo_root / "scripts" / "build_ml_dataset.py"
    widen_py = repo_root / "scripts" / "widen_labels_in_dataset.py"
    train_py = repo_root / "scripts" / "train_beat_refiner.py"

    # work directory
    if args.work_dir:
        work_dir = Path(args.work_dir).expanduser().resolve()
    else:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        work_dir = repo_root / "outputs" / f"final_model_build_{stamp}"
    work_dir.mkdir(parents=True, exist_ok=True)

    env = add_py_paths(os.environ.copy(), repo_root)

    print(f"[root] repo={repo_root}")
    print(f"[root] datasets={datasets_root}")
    print(f"[work] {work_dir}")
    print(f"[out]  {out_model_path}")

    # discover DB folders
    db_folders = [p for p in sorted(datasets_root.iterdir()) if p.is_dir()]
    if not db_folders:
        raise SystemExit(f"No subfolders found inside: {datasets_root}")

    built_npz = []
    for db in db_folders:
        bvh_dir = find_child_dir(db, ["bvh", "BVH", "bvhs", "BVHS"])
        audio_dir = find_child_dir(db, ["audio", "AUDIO", "wav", "WAV", "music", "MUSIC"])

        if not bvh_dir or not audio_dir:
            print(f"[skip] {db.name} (missing bvh/ or audio/)")
            continue

        out_npz = work_dir / f"{db.name}_dataset.npz"

        cmd = [
            sys.executable, str(build_py),
            "--bvh-dir", str(bvh_dir),
            "--audio-dir", str(audio_dir),
            "--out", str(out_npz),
            "--up", args.up,
            "--label-tol-sec", str(args.label_tol_sec),
            "--max-auto-offset", str(args.max_auto_offset),
            "--hop-length", str(args.hop_length),
        ]
        if args.offset_sec is not None:
            cmd += ["--offset-sec", str(args.offset_sec)]
        if args.max_files_per_db is not None:
            cmd += ["--max-files", str(args.max_files_per_db)]
        if args.save_beats:
            cmd += ["--save-beats"]

        print(f"\n[db] {db.name}")
        run(cmd, env=env)

        if out_npz.exists():
            built_npz.append(out_npz)

    if not built_npz:
        raise SystemExit("No datasets were built. Check folder structure and matching filenames (BVH stem == audio stem).")

    # merge datasets
    merged_npz = work_dir / "merged_dataset.npz"
    merge_npz(built_npz, merged_npz)

    # widen labels
    widened_npz = work_dir / "merged_dataset_wide.npz"
    run([
        sys.executable, str(widen_py),
        "--in", str(merged_npz),
        "--out", str(widened_npz),
        "--radius", str(args.widen_radius),
    ], env=env)

    # train final model
    run([
        sys.executable, str(train_py),
        "--dataset", str(widened_npz),
        "--out-model", str(out_model_path),
    ], env=env)

    print(f"\n[DONE] Final model saved: {out_model_path}")

    if not args.keep_work:
        try:
            shutil.rmtree(work_dir)
            print(f"[cleanup] removed work dir: {work_dir}")
        except Exception as e:
            print(f"[cleanup-warning] could not remove work dir: {e}")


if __name__ == "__main__":
    main()
