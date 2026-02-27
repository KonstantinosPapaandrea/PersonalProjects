# scripts/generate_music.py
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoProcessor, MusicgenForConditionalGeneration
from scipy.io import wavfile


def find_project_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for p in [here.parent] + list(here.parents):
        if (p / "outputs").is_dir():
            return p
    return Path.cwd().resolve()


def resolve_output_path(p: str, root: Path) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def save_wav(out_path: Path, sr: int, audio: np.ndarray) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.asarray(audio, dtype=np.float32)

    peak = float(np.max(np.abs(audio))) if audio.size else 1.0
    if peak < 1e-8:
        peak = 1.0

    audio_i16 = np.clip(audio / peak, -1.0, 1.0)
    audio_i16 = (audio_i16 * 32767.0).astype(np.int16)
    wavfile.write(str(out_path), sr, audio_i16)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate music with MusicGen (transformers).")
    parser.add_argument("--prompt", type=str, default="", help="Text prompt for MusicGen.")
    parser.add_argument("--prompt-file", type=str, default="", help="Path to a .txt file containing the prompt.")
    parser.add_argument("--model", type=str, default="facebook/musicgen-small", help="HF model id.")
    parser.add_argument("--duration", type=float, default=8.0, help="Target duration in seconds (approx).")
    parser.add_argument("--out", type=str, default="", help="Output .wav path (relative to project root is OK).")
    parser.add_argument("--seed", type=int, default=1234, help="Random seed.")
    parser.add_argument("--cpu", action="store_true", help="Force CPU even if CUDA is available.")
    args = parser.parse_args()

    root = find_project_root()

    # Load prompt
    prompt = args.prompt.strip()
    if args.prompt_file:
        pf = resolve_output_path(args.prompt_file, root)
        if not pf.exists():
            raise SystemExit(f"Error: prompt file not found: {pf}")
        prompt = pf.read_text(encoding="utf-8").strip()

    if not prompt:
        raise SystemExit("Error: Provide --prompt or --prompt-file.")

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    device = "cpu" if args.cpu or not torch.cuda.is_available() else "cuda"
    dtype = torch.float16 if device == "cuda" else torch.float32

    print(f"[musicgen] model={args.model}")
    print(f"[musicgen] device={device} dtype={dtype}")
    print(f"[musicgen] prompt={prompt}")

    processor = AutoProcessor.from_pretrained(args.model)
    model = MusicgenForConditionalGeneration.from_pretrained(args.model, torch_dtype=dtype)
    model.to(device)
    model.eval()

    # MusicGen uses ~50 tokens/sec => max_new_tokens ≈ duration * 50
    max_new_tokens = max(1, int(round(args.duration * 50)))
    print(f"[musicgen] duration≈{args.duration}s -> max_new_tokens={max_new_tokens}")

    inputs = processor(text=[prompt], padding=True, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        audio_values = model.generate(**inputs, max_new_tokens=max_new_tokens)

    audio = audio_values.detach().cpu().float()
    if audio.ndim == 3:
        audio = audio[0, 0].numpy()
    elif audio.ndim == 2:
        audio = audio[0].numpy()
    else:
        raise RuntimeError(f"Unexpected audio tensor shape: {tuple(audio.shape)}")

    sr = int(model.config.audio_encoder.sampling_rate)

    if args.out:
        out_path = resolve_output_path(args.out, root)
    else:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = (root / "outputs" / f"musicgen_{stamp}.wav").resolve()

    save_wav(out_path, sr, audio)
    print(f"[musicgen] wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
