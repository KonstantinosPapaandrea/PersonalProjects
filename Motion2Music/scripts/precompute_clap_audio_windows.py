#!/usr/bin/env python3
"""
precompute_clap_audio_windows.py

Build CLAP audio embedding targets from meta.csv audio_path using short windows.
Saves one NPZ per window as:
  <dataset-dir>/clap_audio_emb_<Ns>.npz
with arrays:
  ids: clip_id (string)
  emb: [N, D] float32 L2-normalized CLAP audio embeddings
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def _parse_list(text: str) -> list[float]:
    out: list[float] = []
    if not text:
        return out
    for x in text.split(","):
        x = x.strip()
        if not x:
            continue
        out.append(float(x))
    return out


def _l2n(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / (n + eps)


def _load_audio(path: str, sr: int, max_seconds: float) -> np.ndarray:
    import librosa

    y, _ = librosa.load(path, sr=sr, mono=True, duration=float(max_seconds))
    if y.size == 0:
        return np.zeros((1,), dtype=np.float32)
    max_len = int(sr * float(max_seconds))
    if y.shape[0] > max_len:
        y = y[:max_len]
    return y.astype(np.float32)


def _embed_window(meta: pd.DataFrame, model, sr: int, win_s: float, batch: int) -> tuple[np.ndarray, np.ndarray]:
    ids: list[str] = []
    embs: list[np.ndarray] = []

    wav_buf: list[np.ndarray] = []
    id_buf: list[str] = []
    done = 0

    for r in meta.itertuples(index=False):
        cid = str(getattr(r, "clip_id"))
        ap = str(getattr(r, "audio_path"))
        y = _load_audio(ap, sr=sr, max_seconds=win_s)
        wav_buf.append(y)
        id_buf.append(cid)

        if len(wav_buf) >= int(batch):
            e = model.get_audio_embedding_from_data(x=wav_buf, use_tensor=False)
            e = _l2n(np.asarray(e, dtype=np.float32))
            ids.extend(id_buf)
            embs.append(e)
            done += len(id_buf)
            print(f"[window {win_s:.2f}s] embedded {done}/{len(meta)}")
            wav_buf, id_buf = [], []

    if wav_buf:
        e = model.get_audio_embedding_from_data(x=wav_buf, use_tensor=False)
        e = _l2n(np.asarray(e, dtype=np.float32))
        ids.extend(id_buf)
        embs.append(e)
        done += len(id_buf)
        print(f"[window {win_s:.2f}s] embedded {done}/{len(meta)}")

    E = np.concatenate(embs, axis=0).astype(np.float32) if embs else np.zeros((0, 0), dtype=np.float32)
    I = np.array(ids, dtype=object)
    return I, E


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="outputs/m2m_train")
    ap.add_argument("--windows", default="5,8,10", help="Comma-separated seconds, e.g. 5,8,10")
    ap.add_argument("--sr", type=int, default=48000)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    ddir = (root / args.dataset_dir).resolve() if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    meta_path = ddir / "meta.csv"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}")

    meta = pd.read_csv(meta_path)
    req = {"clip_id", "audio_path"}
    if not req.issubset(set(meta.columns)):
        raise RuntimeError(f"meta.csv must include {sorted(req)}")
    meta = meta[["clip_id", "audio_path"]].copy()
    meta["clip_id"] = meta["clip_id"].astype(str)
    meta["audio_path"] = meta["audio_path"].astype(str)

    miss = (~meta["audio_path"].map(lambda p: Path(p).exists())).sum()
    if int(miss) > 0:
        raise RuntimeError(f"Missing audio files in meta.csv: {int(miss)}")

    wins = [w for w in _parse_list(args.windows) if w > 0.0]
    if not wins:
        raise RuntimeError("No valid --windows")

    dev = str(args.device)
    if dev == "cuda":
        try:
            import torch

            if not torch.cuda.is_available():
                dev = "cpu"
        except Exception:
            dev = "cpu"
    print(f"[clap] device={dev}")

    import laion_clap
    import torch

    model = laion_clap.CLAP_Module(enable_fusion=False, device=dev)
    model.load_ckpt()

    for w in wins:
        tag = f"{int(round(w))}s"
        out_npz = ddir / f"clap_audio_emb_{tag}.npz"
        if out_npz.exists() and args.skip_existing:
            print(f"[skip] {out_npz}")
            continue
        print(f"[run] window={w:.2f}s -> {out_npz}")
        with torch.no_grad():
            ids, emb = _embed_window(meta=meta, model=model, sr=int(args.sr), win_s=float(w), batch=int(args.batch))
        np.savez_compressed(out_npz, ids=ids, emb=emb)
        print(f"[done] rows={len(ids)} dim={emb.shape[1] if emb.ndim==2 else 0} file={out_npz}")


if __name__ == "__main__":
    main()
