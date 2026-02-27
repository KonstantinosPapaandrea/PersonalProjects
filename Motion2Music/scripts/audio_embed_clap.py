import os
import json
import argparse
import numpy as np
from tqdm import tqdm

import torch
import librosa
import laion_clap


def l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / (n + eps)


def load_audio_mono(path: str, target_sr: int = 48000, max_seconds: float = 30.0) -> np.ndarray:
    y, sr = librosa.load(path, sr=target_sr, mono=True)
    if max_seconds is not None:
        max_len = int(target_sr * max_seconds)
        if len(y) > max_len:
            y = y[:max_len]
    return y.astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio-dir", required=True)
    ap.add_argument("--used-audio-list", required=True)
    ap.add_argument("--out-npz", required=True)
    ap.add_argument("--sr", type=int, default=48000)
    ap.add_argument("--max-seconds", type=float, default=30.0)
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[clap-laion] device={device}")

    clap_model = laion_clap.CLAP_Module(enable_fusion=False, device=device)
    # Default checkpoint (laion-clap handles download)
    clap_model.load_ckpt()

    with open(args.used_audio_list, "r", encoding="utf-8") as f:
        audio_list = json.load(f)

    abs_paths = []
    for p in audio_list:
        abs_paths.append(p if os.path.isabs(p) else os.path.join(args.audio_dir, p))

    ids = []
    embs = []

    buf = []
    buf_ids = []

    for p in tqdm(abs_paths, desc="Embedding audio"):
        if not os.path.exists(p):
            raise FileNotFoundError(p)

        wav = load_audio_mono(p, target_sr=args.sr, max_seconds=args.max_seconds)
        buf.append(wav)
        buf_ids.append(os.path.splitext(os.path.basename(p))[0])

        if len(buf) >= args.batch:
            # LAION CLAP expects list of numpy arrays
            with torch.no_grad():
                e = clap_model.get_audio_embedding_from_data(x=buf, use_tensor=False)
            e = np.asarray(e, dtype=np.float32)
            e = l2_normalize(e)
            ids.extend(buf_ids)
            embs.append(e)
            buf, buf_ids = [], []

    if buf:
        with torch.no_grad():
            e = clap_model.get_audio_embedding_from_data(x=buf, use_tensor=False)
        e = np.asarray(e, dtype=np.float32)
        e = l2_normalize(e)
        ids.extend(buf_ids)
        embs.append(e)

    E = np.vstack(embs).astype(np.float32)
    np.savez_compressed(args.out_npz, ids=np.array(ids), emb=E)
    print(f"[ok] saved {len(ids)} embeddings -> {args.out_npz}")


if __name__ == "__main__":
    main()
