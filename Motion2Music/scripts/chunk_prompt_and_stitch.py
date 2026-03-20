#!/usr/bin/env python3
"""
chunk_prompt_and_stitch.py

Chunked motion->prompt->music pipeline for long clips.

What it does:
1) Split one LMA/beats sequence into fixed-length chunks (optional beat-snapped starts)
2) Predict audio descriptors per chunk using motion2audio model
3) Build one prompt per chunk
4) Generate one wav per chunk with MusicGen
5) Stitch chunks with equal-power crossfade

Usage (from repo root):
  python scripts/chunk_prompt_and_stitch.py ^
    --dataset-dir outputs/m2m_train ^
    --model-path outputs/m2m_train/models/motion2audio_rf.joblib ^
    --lma-csv outputs/m2m_train/features/<stem>_lma.csv ^
    --beats-csv outputs/m2m_train/features/<stem>_beats.csv ^
    --chunk-seconds 12 ^
    --overlap-seconds 2 ^
    --out-dir outputs/chunked_generated
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.io import wavfile

from predict_prompt_and_generate import (
    build_prompt,
    compute_motion_features,
    get_bundle_x_cols,
    get_bundle_y_cols,
    load_y_percentiles,
    load_retrieval_bank,
    predict_descriptors_from_bundle,
    retrieve_and_blend_descriptors,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _to_abs(root: Path, p: str) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _parse_csv_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lc = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lc:
            return lc[cand.lower()]
    return None


def _motion_duration_s(lma_df: pd.DataFrame, beats_df: pd.DataFrame) -> float:
    end_col = _find_col(lma_df, ["END_TIME_S", "end_s"])
    if end_col is not None:
        v = pd.to_numeric(lma_df[end_col], errors="coerce").to_numpy(dtype=float)
        if v.size:
            mx = float(np.nanmax(v))
            if np.isfinite(mx) and mx > 0:
                return mx

    time_col = _find_col(beats_df, ["time_s", "TIME_S"])
    if time_col is not None:
        v = pd.to_numeric(beats_df[time_col], errors="coerce").to_numpy(dtype=float)
        if v.size:
            mx = float(np.nanmax(v))
            if np.isfinite(mx) and mx > 0:
                return mx

    raise RuntimeError("Could not infer motion duration from LMA/beats csv.")


def _extract_beat_times(beats_df: pd.DataFrame) -> np.ndarray:
    time_col = _find_col(beats_df, ["time_s", "TIME_S"])
    if time_col is None:
        return np.zeros((0,), dtype=float)
    t = pd.to_numeric(beats_df[time_col], errors="coerce").to_numpy(dtype=float)
    t = t[np.isfinite(t)]
    if t.size == 0:
        return np.zeros((0,), dtype=float)
    t = np.unique(t)
    t.sort()
    return t


def _build_chunk_starts(
    duration_s: float,
    chunk_seconds: float,
    hop_seconds: float,
    beat_times: np.ndarray,
    beat_snap_window_s: float,
    max_chunks: int,
) -> list[float]:
    if duration_s <= 0:
        return [0.0]
    hop = hop_seconds if hop_seconds > 0 else chunk_seconds
    starts = [0.0]

    while True:
        cand = starts[-1] + hop
        if cand + (0.5 * chunk_seconds) > duration_s:
            break

        if beat_times.size > 0 and beat_snap_window_s > 0:
            i = int(np.argmin(np.abs(beat_times - cand)))
            bt = float(beat_times[i])
            if (
                abs(bt - cand) <= beat_snap_window_s
                and bt > (starts[-1] + 0.25 * hop)
                and bt < (duration_s - 0.5 * chunk_seconds)
            ):
                cand = bt

        starts.append(float(cand))
        if max_chunks > 0 and len(starts) >= max_chunks:
            return starts[:max_chunks]

    tail = max(0.0, duration_s - chunk_seconds)
    need_tail = (
        abs(tail - starts[-1]) > 1e-6
        and (duration_s - starts[-1]) > 0.5 * chunk_seconds
    )
    if need_tail:
        starts.append(float(tail))

    out: list[float] = []
    for s in starts:
        if not out or abs(s - out[-1]) > 1e-6:
            out.append(s)
    if max_chunks > 0:
        out = out[:max_chunks]
    return out


def _extract_motion_chunk(
    lma_df: pd.DataFrame,
    beats_df: pd.DataFrame,
    start_s: float,
    end_s: float,
    min_lma_rows: int,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    lma_start = _find_col(lma_df, ["START_TIME_S", "start_s"])
    lma_end = _find_col(lma_df, ["END_TIME_S", "end_s"])
    if lma_start is None or lma_end is None:
        raise RuntimeError("LMA csv missing START/END time columns.")

    lma_chunk = lma_df[
        (pd.to_numeric(lma_df[lma_end], errors="coerce") > start_s)
        & (pd.to_numeric(lma_df[lma_start], errors="coerce") < end_s)
    ].copy()
    if len(lma_chunk) < int(min_lma_rows):
        return None

    beats_time = _find_col(beats_df, ["time_s", "TIME_S"])
    if beats_time is not None:
        b_chunk = beats_df[
            (pd.to_numeric(beats_df[beats_time], errors="coerce") >= start_s)
            & (pd.to_numeric(beats_df[beats_time], errors="coerce") < end_s)
        ].copy()
        if beats_time != "time_s":
            b_chunk["time_s"] = pd.to_numeric(b_chunk[beats_time], errors="coerce")
        if not b_chunk.empty:
            b_chunk["time_s"] = b_chunk["time_s"].astype(float) - float(start_s)
    else:
        b_chunk = beats_df.copy()
        if "time_s" not in b_chunk.columns:
            b_chunk["time_s"] = 0.0
    return lma_chunk, b_chunk


def _load_wav_mono_float(path: Path) -> tuple[int, np.ndarray]:
    sr, y = wavfile.read(str(path))
    if y.ndim == 2:
        y = y.mean(axis=1)
    if np.issubdtype(y.dtype, np.integer):
        scale = float(max(abs(np.iinfo(y.dtype).min), np.iinfo(y.dtype).max))
        x = y.astype(np.float32) / max(scale, 1.0)
    else:
        x = y.astype(np.float32)
    return int(sr), x


def _save_wav_mono_float(path: Path, sr: int, y: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    y = np.asarray(y, dtype=np.float32)
    peak = float(np.max(np.abs(y))) if y.size else 1.0
    if peak < 1e-8:
        peak = 1.0
    out = np.clip(y / peak, -1.0, 1.0)
    out = (out * 32767.0).astype(np.int16)
    wavfile.write(str(path), int(sr), out)


def _crossfade_append(base: np.ndarray, nxt: np.ndarray, overlap_samples: int) -> np.ndarray:
    ov = int(min(overlap_samples, len(base), len(nxt)))
    if ov <= 0:
        return np.concatenate([base, nxt], axis=0)
    if ov < 8:
        return np.concatenate([base, nxt], axis=0)

    t = np.linspace(0.0, 1.0, ov, endpoint=False, dtype=np.float32)
    fade_out = np.cos(0.5 * np.pi * t)
    fade_in = np.sin(0.5 * np.pi * t)

    mixed = base[-ov:] * fade_out + nxt[:ov] * fade_in
    return np.concatenate([base[:-ov], mixed, nxt[ov:]], axis=0)


def _stitch_chunks(chunk_paths: list[Path], overlap_seconds: float, out_wav: Path) -> tuple[int, int]:
    if not chunk_paths:
        raise RuntimeError("No chunk wavs to stitch.")

    sr0, y0 = _load_wav_mono_float(chunk_paths[0])
    mix = y0
    for p in chunk_paths[1:]:
        sr, y = _load_wav_mono_float(p)
        if sr != sr0:
            raise RuntimeError(f"Sample rate mismatch during stitch: {sr0} vs {sr} ({p})")
        ov = int(round(max(0.0, float(overlap_seconds)) * sr0))
        mix = _crossfade_append(mix, y, ov)

    _save_wav_mono_float(out_wav, sr0, mix)
    return sr0, int(len(mix))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--model-path", required=True)
    ap.add_argument("--lma-csv", required=True)
    ap.add_argument("--beats-csv", required=True)
    ap.add_argument("--style", default="instrumental dance")
    ap.add_argument("--musicgen-model", default="facebook/musicgen-small")
    ap.add_argument("--chunk-seconds", type=float, default=12.0)
    ap.add_argument("--overlap-seconds", type=float, default=2.0)
    ap.add_argument("--hop-seconds", type=float, default=0.0, help="Default: chunk-seconds - overlap-seconds.")
    ap.add_argument("--beat-snap-window", type=float, default=0.50, help="Snap chunk starts to nearest beat within this many seconds; 0 disables.")
    ap.add_argument("--min-lma-rows", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--max-chunks", type=int, default=0, help="Debug limit, 0 = all.")
    ap.add_argument("--retrieval-k", type=int, default=5, help="Top-K nearest descriptor rows used for timbre retrieval. Set 0 to disable.")
    ap.add_argument("--retrieval-alpha", type=float, default=0.65, help="Blend weight for model prediction vs retrieved profile.")
    ap.add_argument(
        "--retrieval-query-cols",
        type=str,
        default="audio_tempo_bpm,audio_beat_count,rms_mean,rms_std,zcr_mean,zcr_std",
        help="Comma-separated descriptor keys used as retrieval query.",
    )
    ap.add_argument("--out-dir", default="outputs/chunked_generated")
    ap.add_argument("--out-name", default="", help="Final stitched wav name. Default: <lma_stem>_stitched.wav")
    ap.add_argument("--cpu", action="store_true")
    args = ap.parse_args()

    if args.chunk_seconds <= 0:
        raise RuntimeError("--chunk-seconds must be > 0.")
    if args.overlap_seconds < 0:
        raise RuntimeError("--overlap-seconds must be >= 0.")
    if args.overlap_seconds >= args.chunk_seconds:
        raise RuntimeError("--overlap-seconds must be smaller than --chunk-seconds.")

    root = _project_root()
    dataset_dir = _to_abs(root, args.dataset_dir)
    model_path = _to_abs(root, args.model_path)
    lma_csv = _to_abs(root, args.lma_csv)
    beats_csv = _to_abs(root, args.beats_csv)
    out_dir = _to_abs(root, args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle = joblib.load(model_path)
    x_cols: list[str] = get_bundle_x_cols(bundle)
    y_cols: list[str] = get_bundle_y_cols(bundle)

    lma_df = pd.read_csv(lma_csv)
    beats_df = pd.read_csv(beats_csv)
    beat_times = _extract_beat_times(beats_df)
    duration_s = _motion_duration_s(lma_df, beats_df)

    hop = float(args.hop_seconds) if args.hop_seconds > 0 else float(args.chunk_seconds - args.overlap_seconds)
    starts = _build_chunk_starts(
        duration_s=duration_s,
        chunk_seconds=float(args.chunk_seconds),
        hop_seconds=hop,
        beat_times=beat_times,
        beat_snap_window_s=float(args.beat_snap_window),
        max_chunks=int(args.max_chunks),
    )
    if not starts:
        raise RuntimeError("No chunk starts computed.")

    y_stats = load_y_percentiles(dataset_dir)
    retrieval_bank = load_retrieval_bank(dataset_dir) if int(args.retrieval_k) > 0 else None
    retrieval_query_cols = _parse_csv_list(args.retrieval_query_cols)
    gen_script = root / "scripts" / "generate_music.py"
    chunk_dir = out_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)

    chunks_meta: list[dict] = []
    chunk_wavs: list[Path] = []

    for idx, start_s in enumerate(starts):
        end_s = min(float(duration_s), float(start_s + args.chunk_seconds))
        if end_s - start_s < 0.5 * float(args.chunk_seconds):
            continue
        sub = _extract_motion_chunk(
            lma_df=lma_df,
            beats_df=beats_df,
            start_s=float(start_s),
            end_s=float(end_s),
            min_lma_rows=int(args.min_lma_rows),
        )
        if sub is None:
            continue
        lma_chunk, beats_chunk = sub
        x_dict = compute_motion_features(lma_chunk, beats_chunk)
        bpm_motion = float(x_dict.get("bpm_motion", 0.0))

        x = np.zeros((1, len(x_cols)), dtype=np.float32)
        for i, c in enumerate(x_cols):
            x[0, i] = float(x_dict.get(c, 0.0))
        pred, pred_aux = predict_descriptors_from_bundle(bundle, x)
        pred_prompt, retrieval_info = retrieve_and_blend_descriptors(
            pred=pred,
            retrieval_bank=retrieval_bank,
            bpm_motion=bpm_motion,
            query_cols=retrieval_query_cols,
            k=int(args.retrieval_k),
            alpha=float(args.retrieval_alpha),
        )
        prompt = build_prompt(args.style, bpm_motion, pred_prompt, y_stats)

        seed = int(args.seed + idx * 101)
        out_chunk = chunk_dir / f"chunk_{idx:03d}_s{start_s:.2f}_e{end_s:.2f}_seed{seed}.wav"
        cmd = [
            sys.executable,
            str(gen_script),
            "--prompt",
            prompt,
            "--model",
            args.musicgen_model,
            "--duration",
            str(float(end_s - start_s)),
            "--out",
            str(out_chunk),
            "--seed",
            str(seed),
        ]
        if args.cpu:
            cmd.append("--cpu")

        print(f"[chunk {idx+1}/{len(starts)}] {start_s:.2f}s -> {end_s:.2f}s seed={seed}")
        print(f"[prompt] {prompt}")
        subprocess.run(cmd, check=True)
        chunk_wavs.append(out_chunk)
        chunks_meta.append(
            {
                "chunk_idx": idx,
                "start_s": float(start_s),
                "end_s": float(end_s),
                "duration_s": float(end_s - start_s),
                "seed": seed,
                "prompt": prompt,
                "prediction_aux": pred_aux,
                "retrieval": retrieval_info,
                "wav_path": str(out_chunk),
            }
        )

    if not chunk_wavs:
        raise RuntimeError("No chunk wavs generated.")

    out_name = args.out_name.strip()
    if not out_name:
        out_name = f"{lma_csv.stem}_stitched.wav"
    stitched_wav = out_dir / out_name
    sr, n_samples = _stitch_chunks(
        chunk_paths=chunk_wavs,
        overlap_seconds=float(args.overlap_seconds),
        out_wav=stitched_wav,
    )

    info = {
        "dataset_dir": str(dataset_dir),
        "model_path": str(model_path),
        "lma_csv": str(lma_csv),
        "beats_csv": str(beats_csv),
        "duration_s": float(duration_s),
        "chunk_seconds": float(args.chunk_seconds),
        "overlap_seconds": float(args.overlap_seconds),
        "hop_seconds": float(hop),
        "beat_snap_window": float(args.beat_snap_window),
        "seed_base": int(args.seed),
        "musicgen_model": args.musicgen_model,
        "stitched_wav": str(stitched_wav),
        "stitched_sr": int(sr),
        "stitched_samples": int(n_samples),
        "chunks_generated": len(chunk_wavs),
        "chunks": chunks_meta,
    }
    info_path = out_dir / f"{lma_csv.stem}_chunk_run.json"
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")

    print(f"[done] chunks={len(chunk_wavs)} stitched={stitched_wav}")
    print(f"[meta] {info_path}")


if __name__ == "__main__":
    main()
