# scripts/quick_view.py
import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("\n[cmd]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def base_prefix_for_bvh(bvh_path: str) -> str:
    # outputs are saved as: <bvh_without_ext>.ml_prob.npy, .hybrid_events.npy, etc.
    p = Path(bvh_path)
    s = str(p)
    if s.lower().endswith(".bvh"):
        return s[:-4]
    return s


def main():
    root = Path(__file__).resolve().parents[1]
    default_model = root / "models" / "beat_refiner_FINAL.joblib"
    refiner_py = root / "scripts" / "beat_refiner_apply.py"
    visual_py = root / "scripts" / "visualize_beats_on_bvh.py"

    ap = argparse.ArgumentParser(
        description="Run beat_refiner_apply then visualize beats with sensible defaults."
    )
    ap.add_argument("--bvh", required=True, help="Path to .bvh")
    ap.add_argument("--model", default=str(default_model), help="Path to beat_refiner.joblib")
    ap.add_argument("--thr", type=float, default=0.40, help="Refiner threshold override")
    ap.add_argument("--up", choices=["auto", "x", "y", "z"], default="auto", help="Up-axis")
    ap.add_argument("--v1", action="store_true", help="Use v1 cues (default is v2)")
    ap.add_argument("--skip-refine", action="store_true", help="Only visualize (don't run refiner)")

    # Which events to overlay as the "ML track" in the viewer
    ap.add_argument("--events", choices=["hybrid", "ml", "rule"], default="hybrid",
                    help="Which saved event file to show as the overlay track")
    ap.add_argument("--events-mode", choices=["rule", "ml", "both"], default="both",
                    help="What the viewer shows: rule / ml overlay / both")

    # Viewer defaults (your usual)
    ap.add_argument("--plot-cues", action="store_true", default=True)
    ap.add_argument("--signals", default="score,C_foot,ml_prob")
    ap.add_argument("--ml-min-sep", type=float, default=0.25)
    ap.add_argument("--playback-speed", type=float, default=1.0)
    ap.add_argument("--max-display-fps", type=float, default=30.0,
                    help="Cap viewer display FPS by auto-increasing stride (when framerate override is not used).")
    ap.add_argument("--audio", default=None, help="Optional audio file to play in sync with BVH.")
    ap.add_argument("--audio-start", type=float, default=0.0, help="Audio start offset in seconds.")
    ap.add_argument("--audio-volume", type=float, default=1.0, help="Audio volume in [0,1].")
    ap.add_argument("--audio-loop", action="store_true", help="Loop audio and animation.")
    ap.add_argument("--sync-offset", type=float, default=0.0,
                    help="Shift motion time vs audio in seconds (+ moves motion forward).")
    ap.add_argument("--auto-sync", action="store_true",
                    help="Estimate per-clip audio-motion offset automatically.")
    ap.add_argument("--auto-sync-max-offset", type=float, default=1.0,
                    help="Maximum absolute offset searched by --auto-sync.")
    ap.add_argument("--auto-sync-hop-length", type=int, default=512,
                    help="Hop length for onset envelope in --auto-sync.")

    # Optional overrides if you want to point at a different .npy explicitly
    ap.add_argument("--ml-events", default=None, help="Override: path to events .npy")
    ap.add_argument("--ml-prob", default=None, help="Override: path to prob .npy")

    args = ap.parse_args()

    # --- Compute expected output paths (saved next to BVH by default) ---
    base = base_prefix_for_bvh(args.bvh)
    default_prob = base + ".ml_prob.npy"
    default_events = {
        "hybrid": base + ".hybrid_events.npy",
        "ml":     base + ".ml_events.npy",
        "rule":   base + ".rule_events.npy",
    }[args.events]

    ml_prob_path = args.ml_prob or default_prob
    ml_events_path = args.ml_events or default_events

    # --- 1) Run refiner (unless skipped) ---
    if not args.skip_refine:
        cmd_refine = [
            sys.executable, str(refiner_py),
            "--bvh", args.bvh,
            "--model", args.model,
            "--up", args.up,
            "--thr", str(args.thr),
        ]
        if not args.v1:
            cmd_refine.append("--v2")  # default behavior
        run(cmd_refine)

    # --- 2) Visualize ---
    cmd_vis = [
        sys.executable, str(visual_py),
        "--bvh", args.bvh,
        "--up", args.up,
        "--events-mode", args.events_mode,
        "--plot-cues",
        "--signals", args.signals,
        "--ml-min-sep", str(args.ml_min_sep),
        "--playback-speed", str(args.playback_speed),
        "--max-display-fps", str(args.max_display_fps),
    ]

    # Only pass ML overlay files when needed
    if args.events_mode in ("ml", "both"):
        cmd_vis += ["--ml-events", ml_events_path, "--ml-prob", ml_prob_path]
    if args.audio:
        cmd_vis += [
            "--audio", args.audio,
            "--audio-start", str(args.audio_start),
            "--audio-volume", str(args.audio_volume),
            "--sync-offset", str(args.sync_offset),
        ]
        if args.audio_loop:
            cmd_vis.append("--audio-loop")
        if args.auto_sync:
            cmd_vis += [
                "--auto-sync",
                "--auto-sync-max-offset", str(args.auto_sync_max_offset),
                "--auto-sync-hop-length", str(args.auto_sync_hop_length),
            ]

    run(cmd_vis)


if __name__ == "__main__":
    main()
