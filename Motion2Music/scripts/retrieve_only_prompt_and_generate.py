#!/usr/bin/env python3
"""
retrieve_only_prompt_and_generate.py

Pure retrieval baseline for Motion2Music.

Flow:
1) Compute query motion features from LMA + beats CSV.
2) Retrieve nearest rows in X_motion.csv (optionally excluding dbs).
3) Transfer/blend their Y_audio descriptor profiles.
4) Build prompt from retrieved descriptors.
5) Optionally run MusicGen and save run metadata.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from predict_prompt_and_generate import build_prompt, compute_motion_features, load_y_percentiles, project_root


def _parse_csv_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _safe_fill_nan(x: np.ndarray, fill: np.ndarray) -> np.ndarray:
    out = x.copy()
    if out.ndim == 1:
        mask = ~np.isfinite(out)
        out[mask] = fill[mask]
        return out
    mask = ~np.isfinite(out)
    if np.any(mask):
        out[mask] = np.take(fill, np.where(mask)[1])
    return out


def _load_banks(dataset_dir: Path, exclude_dbs: list[str]) -> dict:
    xp = dataset_dir / "X_motion.csv"
    yp = dataset_dir / "Y_audio.csv"
    mp = dataset_dir / "meta.csv"
    if not xp.exists() or not yp.exists() or not mp.exists():
        raise FileNotFoundError("dataset-dir must contain X_motion.csv, Y_audio.csv, meta.csv")

    xdf = pd.read_csv(xp)
    ydf = pd.read_csv(yp)
    meta = pd.read_csv(mp)
    if not (len(xdf) == len(ydf) == len(meta)):
        raise RuntimeError(f"Row mismatch X/Y/meta: {len(xdf)} / {len(ydf)} / {len(meta)}")

    x_cols = [c for c in xdf.columns if pd.api.types.is_numeric_dtype(xdf[c])]
    if not x_cols:
        raise RuntimeError("No numeric X_motion columns found.")
    x_arr = xdf[x_cols].to_numpy(dtype=np.float32)
    x_med = np.nanmedian(x_arr, axis=0).astype(np.float32)
    x_arr = _safe_fill_nan(x_arr, x_med)
    x_sd = (np.nanstd(x_arr, axis=0) + 1e-8).astype(np.float32)

    y_num = ydf.select_dtypes(include=[np.number]).copy()
    drop_cols: list[str] = []
    for c in y_num.columns:
        if c == "clip_id" or c == "audio_duration_s" or c.endswith("_min") or c.endswith("_max"):
            drop_cols.append(c)
    if drop_cols:
        y_num = y_num.drop(columns=drop_cols, errors="ignore")
    y_num = y_num.dropna(axis=1, how="all")
    if y_num.empty:
        raise RuntimeError("No usable numeric Y_audio descriptor columns after filtering.")

    y_cols = y_num.columns.to_list()
    y_arr = y_num.to_numpy(dtype=np.float32)
    y_med = np.nanmedian(y_arr, axis=0).astype(np.float32)
    y_arr = _safe_fill_nan(y_arr, y_med)

    db = meta["db"].astype(str) if "db" in meta.columns else pd.Series(["unknown"] * len(meta))
    stem = meta["stem"].astype(str) if "stem" in meta.columns else pd.Series([""] * len(meta))
    clip_id = meta["clip_id"].astype(str) if "clip_id" in meta.columns else pd.Series([str(i) for i in range(len(meta))])
    audio_path = ydf["audio_path"].astype(str) if "audio_path" in ydf.columns else pd.Series([""] * len(ydf))

    keep = np.ones(len(meta), dtype=bool)
    ex = {d.lower() for d in exclude_dbs}
    if ex:
        keep = ~db.str.lower().isin(ex).to_numpy()
    if not np.any(keep):
        raise RuntimeError(f"All rows filtered out by --exclude-dbs={exclude_dbs}")

    row_meta: list[dict] = []
    for i in range(len(meta)):
        row_meta.append(
            {
                "row_index": int(i),
                "clip_id": str(clip_id.iat[i]),
                "db": str(db.iat[i]),
                "stem": str(stem.iat[i]),
                "audio_path": str(audio_path.iat[i]),
            }
        )

    return {
        "x_cols": x_cols,
        "x_arr": x_arr[keep],
        "x_med": x_med,
        "x_sd": x_sd,
        "y_cols": y_cols,
        "y_arr": y_arr[keep],
        "meta": [row_meta[i] for i in np.where(keep)[0]],
        "total_rows": int(len(meta)),
        "kept_rows": int(np.sum(keep)),
    }


def _retrieve_motion_neighbors(
    bank: dict,
    x_query: np.ndarray,
    k: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_arr: np.ndarray = bank["x_arr"]
    x_sd: np.ndarray = bank["x_sd"]
    z = (x_arr - x_query[None, :]) / x_sd[None, :]
    dist = np.mean(np.abs(z), axis=1)

    top_k = int(max(1, min(int(k), len(dist))))
    idx = np.argpartition(dist, top_k - 1)[:top_k]
    idx = idx[np.argsort(dist[idx])]

    w = 1.0 / (dist[idx] + 1e-6)
    w = w / np.sum(w)
    return idx, dist, w


def _copy_nearest_audio(nearest: list[dict], out_dir: Path, top_n: int) -> list[str]:
    copied: list[str] = []
    n = int(max(0, min(int(top_n), len(nearest))))
    for rank in range(n):
        hit = nearest[rank]
        src = Path(str(hit.get("audio_path", "")))
        if not src.exists() or not src.is_file():
            continue
        dst = out_dir / f"nearest_{rank+1}_{src.name}"
        shutil.copy2(src, dst)
        copied.append(str(dst))
    return copied


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--lma-csv", required=True)
    ap.add_argument("--beats-csv", required=True)
    ap.add_argument("--style", default="instrumental dance")
    ap.add_argument("--duration", type=float, default=12.0)
    ap.add_argument("--k", type=int, default=5, help="Nearest neighbors in motion-feature space.")
    ap.add_argument("--exclude-dbs", type=str, default="", help="Comma-separated db names excluded from retrieval bank.")
    ap.add_argument("--num", type=int, default=1, help="How many MusicGen candidates to generate.")
    ap.add_argument("--out-dir", default="outputs/generated_retrieval_only")
    ap.add_argument("--musicgen-model", default="facebook/musicgen-small")
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--copy-nearest-audio", action="store_true", help="Copy nearest source audio files into out-dir.")
    ap.add_argument("--copy-nearest-topn", type=int, default=1)
    ap.add_argument("--save-run-json", action="store_true")
    args = ap.parse_args()

    root = project_root()
    dataset_dir = (root / args.dataset_dir).resolve() if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    lma_csv = (root / args.lma_csv).resolve() if not Path(args.lma_csv).is_absolute() else Path(args.lma_csv)
    beats_csv = (root / args.beats_csv).resolve() if not Path(args.beats_csv).is_absolute() else Path(args.beats_csv)
    out_dir = (root / args.out_dir).resolve() if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    exclude_dbs = _parse_csv_list(args.exclude_dbs)
    bank = _load_banks(dataset_dir, exclude_dbs=exclude_dbs)
    x_cols: list[str] = bank["x_cols"]
    y_cols: list[str] = bank["y_cols"]

    lma_df = pd.read_csv(lma_csv)
    beats_df = pd.read_csv(beats_csv)
    xdict = compute_motion_features(lma_df, beats_df)
    bpm_motion = float(xdict.get("bpm_motion", 0.0))

    xq = np.zeros((len(x_cols),), dtype=np.float32)
    missing_x_cols: list[str] = []
    x_med: np.ndarray = bank["x_med"]
    for i, c in enumerate(x_cols):
        if c in xdict and np.isfinite(xdict[c]):
            xq[i] = float(xdict[c])
        else:
            xq[i] = float(x_med[i])
            missing_x_cols.append(c)

    idx, dist, w = _retrieve_motion_neighbors(bank=bank, x_query=xq, k=int(args.k))
    y_arr: np.ndarray = bank["y_arr"]
    proto = np.sum(y_arr[idx] * w[:, None], axis=0)
    pred_prompt = {c: float(v) for c, v in zip(y_cols, proto)}

    nearest: list[dict] = []
    meta: list[dict] = bank["meta"]
    for rank, i in enumerate(idx.tolist(), start=1):
        m = meta[int(i)]
        nearest.append(
            {
                "rank": int(rank),
                "dist": float(dist[int(i)]),
                "weight": float(w[rank - 1]),
                "clip_id": m.get("clip_id", ""),
                "db": m.get("db", ""),
                "stem": m.get("stem", ""),
                "audio_path": m.get("audio_path", ""),
            }
        )

    y_stats = load_y_percentiles(dataset_dir)
    prompt = build_prompt(args.style, bpm_motion, pred_prompt, y_stats)

    print("\n[prompt]")
    print(prompt)
    print("\n[retrieval_motion]")
    for hit in nearest[: min(3, len(nearest))]:
        print(
            f"  rank={hit['rank']} db={hit.get('db','')} stem={hit.get('stem','')} "
            f"dist={hit['dist']:.4f} w={hit['weight']:.3f}"
        )

    copied_audio: list[str] = []
    if args.copy_nearest_audio:
        copied_audio = _copy_nearest_audio(nearest=nearest, out_dir=out_dir, top_n=int(args.copy_nearest_topn))
        for p in copied_audio:
            print(f"[copied] {p}")

    wavs: list[Path] = []
    gen_script = root / "scripts" / "generate_music.py"
    for n in range(int(max(0, args.num))):
        seed = int(args.seed + n * 101)
        out_wav = out_dir / f"musicgen_retrieval_only_{lma_csv.stem}_s{seed}.wav"
        cmd = [
            sys.executable,
            str(gen_script),
            "--prompt",
            prompt,
            "--model",
            args.musicgen_model,
            "--duration",
            str(args.duration),
            "--out",
            str(out_wav),
            "--seed",
            str(seed),
        ]
        if args.cpu:
            cmd.append("--cpu")
        print("\n[cmd]", " ".join(cmd))
        subprocess.run(cmd, check=True)
        wavs.append(out_wav)

    if wavs:
        print(f"\n[done] generated {len(wavs)} wav(s) -> {out_dir}")
    else:
        print(f"\n[done] prompt/retrieval only (no generation) -> {out_dir}")

    if args.save_run_json:
        run_info = {
            "dataset_dir": str(dataset_dir),
            "lma_csv": str(lma_csv),
            "beats_csv": str(beats_csv),
            "x_cols_count": int(len(x_cols)),
            "y_cols_count": int(len(y_cols)),
            "bank_total_rows": int(bank["total_rows"]),
            "bank_kept_rows": int(bank["kept_rows"]),
            "exclude_dbs": exclude_dbs,
            "k": int(args.k),
            "bpm_motion": float(bpm_motion),
            "prompt": prompt,
            "nearest": nearest,
            "pred_for_prompt": pred_prompt,
            "missing_x_cols": missing_x_cols,
            "copied_nearest_audio": copied_audio,
            "generated_wavs": [str(p) for p in wavs],
        }
        info_path = out_dir / f"{lma_csv.stem}_retrieval_only_run.json"
        info_path.write_text(json.dumps(run_info, indent=2), encoding="utf-8")
        print(f"[meta] {info_path}")


if __name__ == "__main__":
    main()
