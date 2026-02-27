# scripts/musicPromptCreate.py
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def find_project_root(start: Path | None = None) -> Path:
    """
    Find project root by searching upward for an 'outputs' folder.
    This makes the script immune to where you run it from (CWD).
    """
    here = (start or Path(__file__)).resolve()
    for p in [here.parent] + list(here.parents):
        if (p / "outputs").is_dir():
            return p
    # fallback: current working dir
    return Path.cwd().resolve()


def resolve_input_path(p: str, root: Path) -> Path:
    """
    Resolve a user-provided path.
    - If absolute: use it.
    - Else: try relative to root first, then relative to CWD.
    """
    path = Path(p)
    if path.is_absolute():
        return path
    cand_root = (root / path).resolve()
    if cand_root.exists():
        return cand_root
    cand_cwd = (Path.cwd() / path).resolve()
    return cand_cwd


def estimate_bpm(beats_df: pd.DataFrame) -> float:
    t = beats_df["time_s"].to_numpy()
    if len(t) < 2:
        return 120.0
    idx = beats_df["beat_index"].to_numpy()
    A = np.vstack([idx, np.ones_like(idx)]).T
    slope, _ = np.linalg.lstsq(A, t, rcond=None)[0]  # sec/beat
    bpm = 60.0 / max(slope, 1e-6)
    return float(bpm)


def summarize_lma(lma_df: pd.DataFrame) -> dict:
    energy = (
        0.4 * lma_df["BODY"]
        + 0.3 * lma_df["EFFORT_WEIGHT_STRONG"]
        + 0.3 * lma_df["EFFORT_TIME_SUDDEN"]
    )

    m = lma_df[
        ["EFFORT_WEIGHT_STRONG", "EFFORT_TIME_SUDDEN", "EFFORT_FLOW_BOUND", "SHAPE", "SPACE"]
    ].mean()

    energy_mean = float(energy.mean())

    def level(x: float) -> str:
        if x < 0.33:
            return "low"
        if x < 0.66:
            return "medium"
        return "high"

    energy_level = level(energy_mean)

    rhythm_words = []
    rhythm_words += ["staccato", "punchy"] if m["EFFORT_TIME_SUDDEN"] > 0.55 else ["steady"]
    rhythm_words += ["tight", "controlled"] if m["EFFORT_FLOW_BOUND"] > 0.55 else ["flowing"]

    mood_words = []
    if energy_level == "high":
        mood_words += ["energetic"]
    elif energy_level == "medium":
        mood_words += ["driving"]
    else:
        mood_words += ["calm"]

    if m["SPACE"] < 0.35:
        mood_words += ["focused"]
    if m["SHAPE"] > 0.60:
        mood_words += ["expansive"]

    return {
        "energy_mean": energy_mean,
        "energy_level": energy_level,
        "rhythm_words": rhythm_words,
        "mood_words": mood_words,
    }


def build_prompt(bpm: float, lma_summary: dict, style_hint: str) -> str:
    bpm_round = int(round(bpm))
    mood = ", ".join(dict.fromkeys(lma_summary["mood_words"]))
    rhythm = ", ".join(dict.fromkeys(lma_summary["rhythm_words"]))
    return f"{style_hint}, {mood}, {rhythm}, clear beat, tempo {bpm_round} bpm, high quality mix, no vocals"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a MusicGen prompt from *_beats.csv and *_lma.csv.")
    parser.add_argument("--name", type=str, default="", help="Base name (loads outputs/<name>_beats.csv and outputs/<name>_lma.csv).")
    parser.add_argument("--beats", type=str, default="", help="Path to *_beats.csv (optional if --name is given).")
    parser.add_argument("--lma", type=str, default="", help="Path to *_lma.csv (optional if --name is given).")
    parser.add_argument("--outputs-dir", type=str, default="outputs", help="Outputs folder name (default: outputs).")
    parser.add_argument("--style-hint", type=str, default="instrumental dance", help="Style/genre hint added to the prompt.")
    parser.add_argument("--write", type=str, default="", help="Write prompt to a text file (e.g., outputs/prompt.txt).")
    parser.add_argument("--debug", action="store_true", help="Print debug info about resolved paths.")
    args = parser.parse_args()

    root = find_project_root()
    out_dir = (root / args.outputs_dir).resolve()

    # Determine inputs
    if args.name and not (args.beats or args.lma):
        beats_path = out_dir / f"{args.name}_beats.csv"
        lma_path = out_dir / f"{args.name}_lma.csv"
    else:
        if not args.beats or not args.lma:
            raise SystemExit("Error: Provide --name OR both --beats and --lma.")
        beats_path = resolve_input_path(args.beats, root)
        lma_path = resolve_input_path(args.lma, root)

    if args.debug:
        print("[debug] CWD :", Path.cwd())
        print("[debug] ROOT:", root)
        print("[debug] OUT :", out_dir)
        print("[debug] beats:", beats_path, "exists?", beats_path.exists())
        print("[debug] lma  :", lma_path, "exists?", lma_path.exists())

    if not beats_path.exists():
        raise SystemExit(f"Error: beats CSV not found: {beats_path}")
    if not lma_path.exists():
        raise SystemExit(f"Error: lma CSV not found: {lma_path}")

    beats = pd.read_csv(beats_path)
    lma = pd.read_csv(lma_path)

    bpm = estimate_bpm(beats)
    lma_sum = summarize_lma(lma)
    prompt = build_prompt(bpm, lma_sum, style_hint=args.style_hint)

    print(prompt)

    if args.write:
        write_path = resolve_input_path(args.write, root)
        write_path.parent.mkdir(parents=True, exist_ok=True)
        write_path.write_text(prompt + "\n", encoding="utf-8")
        if args.debug:
            print("[debug] wrote prompt to:", write_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
