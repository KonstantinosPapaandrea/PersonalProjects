from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# visualize_beats_on_bvh.py
import argparse
import re

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from motion2music.beats.cues import _cue_foot_contact  # not strictly needed but kept for future debug
from motion2music.beats.helpers import _ma3, _grad, _estimate_ground_level, _local_minima, _robust_norm

from motion2music.io.loadbvh import loadbvh
from motion2music.config import JOINT_INDICES, N_TOTAL_JOINTS  # N_TOTAL_JOINTS unused but kept
from motion2music.beats.BeatExtraction import extract_beats_v1, extract_beats_v2, BeatParamsV1, BeatParamsV2


# -----------------------------
# Skeleton helpers
# -----------------------------

def skeleton_edges(skeleton):
    edges = []
    for j in skeleton:
        if j.parent is not None:
            edges.append((j.parent.joint_index, j.joint_index))
    return edges


def stack_positions(skeleton):
    J = len(skeleton)
    T = skeleton[0].d_xyz.shape[1]
    P = np.zeros((T, J, 3), dtype=float)
    for j in range(J):
        P[:, j, :] = skeleton[j].d_xyz.T  # (3,T) -> (T,3)
    return P


def reorient_positions(positions, up: str = "auto"):
    """
    Reorient positions so that the 'up' axis becomes +Y.

    - If up is 'x', 'y', or 'z', we trust the user.
    - If up is 'auto', we:
        * compute median joint positions over time (cancels translation),
        * pick the axis with the largest joint-median spread as vertical.
    """
    P = np.asarray(positions, dtype=float)
    if up not in ("auto", "x", "y", "z"):
        return P

    if up == "auto":
        # Use medians to cancel global translation
        med = np.median(P, axis=0)        # (J,3)
        rng = np.ptp(med, axis=0)         # [range_x, range_y, range_z]
        axis = int(np.argmax(rng))
    else:
        axis = {"x": 0, "y": 1, "z": 2}[up]

    if axis == 1:      # already y-up
        return P
    elif axis == 2:    # z-up -> y-up (swap y,z)
        return P[:, :, [0, 2, 1]]
    elif axis == 0:    # x-up -> y-up (swap x,y)
        return P[:, :, [1, 0, 2]]


def _valid_idx(i, N):
    return (i is not None) and isinstance(i, (int, np.integer)) and 0 <= int(i) < N


def auto_rig_indices(skeleton, positions):
    """
    Return (pelvis_idx, left_foot_idx, right_foot_idx).
    - Tries name matching first (hip/pelvis, left/right + foot/toe/ankle)
    - Falls back to geometry (lowest two joints by median Y, split by X wrt pelvis)
    - Never raises; always returns a triple (ints or None for feet if really unknown).
    """
    J = len(skeleton)
    P = np.asarray(positions)  # (T, J, 3) in *canonical* y-up space
    assert P.ndim == 3 and P.shape[1] == J

    names = [(getattr(j, "name", "") or "").lower() for j in skeleton]

    # --- Pelvis (name → root fallback) ---
    pelvis_idx = next((i for i, n in enumerate(names) if ("hip" in n or "pelvis" in n)), None)
    if pelvis_idx is None:
        pelvis_idx = next((i for i, j in enumerate(skeleton) if getattr(j, "is_root", False)), 0)
    pelvis_idx = int(pelvis_idx)

    # --- Helpers for feet ---
    def name_candidates(side):
        s0 = side[0]  # 'l'/'r'
        idxs = []
        for i, n in enumerate(names):
            if ("foot" in n or "feet" in n or "toe" in n or "ankle" in n):
                if side in n or n.startswith(s0):
                    idxs.append(i)
        return idxs

    def pick_lowest_y(idxs):
        if not idxs:
            return None
        ymed = [np.median(P[:, i, 1]) for i in idxs]
        return int(idxs[int(np.argmin(ymed))])

    # --- Try name-based feet first ---
    l_idx = pick_lowest_y(name_candidates("left"))
    r_idx = pick_lowest_y(name_candidates("right"))

    # --- Geometric fallback (lowest joints) if missing one/both feet ---
    if (l_idx is None) or (r_idx is None):
        ymed_all = np.median(P[:, :, 1], axis=0)          # median Y per joint
        order = np.argsort(ymed_all)                      # low → high
        # keep a small pool of lowest joints, excluding pelvis
        pool = [i for i in order[:max(8, J)] if i != pelvis_idx]

        # split by X side relative to pelvis
        xpel = np.median(P[:, pelvis_idx, 0])
        lefts  = [i for i in pool if np.median(P[:, i, 0]) >= xpel]
        rights = [i for i in pool if np.median(P[:, i, 0]) <  xpel]

        if l_idx is None and lefts:
            l_idx = int(lefts[0])
        if r_idx is None and rights:
            r_idx = int(rights[0])

        # absolute fallback: just take two lowest different joints
        if l_idx is None and len(pool) >= 1:
            l_idx = int(pool[0])
        if r_idx is None and len(pool) >= 2:
            r_idx = int(pool[1] if pool[1] != l_idx else (pool[2] if len(pool) > 2 else pool[0]))

    return pelvis_idx, l_idx, r_idx


def find_joint_index(skeleton, name_candidates):
    names = [j.name.lower() for j in skeleton]
    for pat in name_candidates:  # e.g., ["leftfoot", "l_foot", "left_foot", "lf_foot", "leftankle"]
        if pat in names:
            return names.index(pat)
    # relaxed substring fallback
    for i, n in enumerate(names):
        if any(pat in n for pat in name_candidates):
            return i
    return None

def _dedup_events_by_time(events, fps, min_sep_s: float):
    """
    Simple 1D NMS on a list/array of event frame indices:
    - Keep events at least `min_sep_s` seconds apart (in frames).
    - If multiple events fall inside the same window, we keep the earliest.
    """
    if events is None:
        return None
    events = np.asarray(events, dtype=int)
    if events.size == 0 or min_sep_s <= 0.0 or fps <= 0.0:
        return events

    events = np.sort(events)
    min_sep_frames = int(round(min_sep_s * fps))
    if min_sep_frames <= 1:
        return events

    kept = [events[0]]
    last = events[0]
    for e in events[1:]:
        if e - last >= min_sep_frames:
            kept.append(e)
            last = e

    return np.asarray(kept, dtype=int)

# -----------------------------
# Main
# -----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bvh", required=True, help="Path to .bvh file")
    ap.add_argument("--stride", type=int, default=1, help="Frame stride for display")
    ap.add_argument("--framerate", type=float, default=None, help="Override display FPS")
    ap.add_argument("--view", choices=["xy", "xz", "yz"], default="xy")
    ap.add_argument("--up", choices=["auto", "x", "y", "z"], default="auto", help="Up-axis of source BVH")
    ap.add_argument(
        "--events-mode",
        choices=["rule", "ml", "both"],
        default="both",
        help="Which events to visualize: rule (BeatExtraction), ml (ML refined), or both."
    )

    ap.add_argument(
        "--plot-cues", action="store_true",
        help="If set, plot selected signals above the animation and sync with a moving cursor."
    )
    ap.add_argument(
        "--signals",
        type=str,
        default="score",
        help=(
            "Comma-separated list of signals to plot with the animation. "
            "Available: score,C_decel,C_pelvis,C_foot,C_accel,C_reversal,"
            "dbg_y_rel,dbg_sp,dbg_vy_abs,dbg_mins,ml_prob"
        ),
    )
    ap.add_argument(
        "--ml-min-sep",
        type=float,
        default=0.18,
        help="Minimum separation between ML events in seconds (0 disables)."
    )
    ap.add_argument("--pelvis", type=int, default=None)
    ap.add_argument("--left-foot", type=int, default=None)
    ap.add_argument("--right-foot", type=int, default=None)
    ap.add_argument("--auto-rig", action="store_true")
    ap.add_argument("--v2", action="store_true")

    ap.add_argument(
        "--win-seconds",
        type=float,
        default=5.0,
        help="Length of time window (in seconds) shown in cue plot; use 0 for full sequence."
    )
    ap.add_argument(
        "--playback-speed",
        type=float,
        default=1.0,
        help="Playback speed factor: 1.0 = real-time, 0.5 = half-speed, 0.25 = quarter-speed, 2.0 = double speed."
    )

    # Optional ML overlays
    ap.add_argument(
        "--ml-events",
        type=str,
        default=None,
        help="Path to .npy of ML-refined event indices (e.g. from beat_refiner_apply.py)."
    )
    ap.add_argument(
        "--ml-prob",
        type=str,
        default=None,
        help="Path to .npy of ML beat probabilities per frame."
    )

    args = ap.parse_args()

    # -------- Load BVH + positions --------
    skeleton, frame_times, total_time, fps = loadbvh(args.bvh)
    positions0 = stack_positions(skeleton)
    positions = reorient_positions(positions0, args.up)
    print(f"[up-axis] using: {args.up}")

    T = positions.shape[0]
    N = positions.shape[1]

    # -------- Auto rig or manual indices --------
    if args.auto_rig or (args.pelvis is None and args.left_foot is None and args.right_foot is None):
        pelvis_idx, LFOOT_IDX, RFOOT_IDX = auto_rig_indices(skeleton, positions)
    else:
        pelvis_idx, LFOOT_IDX, RFOOT_IDX = args.pelvis, args.left_foot, args.right_foot
    print(f"[rig] pelvis={pelvis_idx}, Lfoot={LFOOT_IDX}, Rfoot={RFOOT_IDX}")

    # -------- DEBUG: pick one foot to inspect (prefer left if valid) --------
    dt = 1.0 / float(fps)
    debug_foot_idx = LFOOT_IDX if _valid_idx(LFOOT_IDX, N) else RFOOT_IDX

    debug_y_rel   = np.zeros(T)
    debug_sp      = np.zeros(T)
    debug_vy_abs  = np.zeros(T)
    debug_mins    = np.zeros(T)

    if _valid_idx(debug_foot_idx, N):
        print(
            f"[debug] Using foot joint {debug_foot_idx} "
            f"({getattr(skeleton[debug_foot_idx], 'name', 'unknown')}) for debug signals"
        )

        foot = _ma3(positions[:, int(debug_foot_idx), :],5)
        y = foot[:, 1]
        xy = foot[:, [0, 2]]

        # Ground + normalized height
        g = _estimate_ground_level(y, q=0.05)
        leg_scale = 1.0  # for debug, just use 1; we only care about relative shape
        y_rel = np.maximum(0.0, y - g) / max(leg_scale, 1e-6)

        # Horizontal speed
        vxy = _grad(xy, dt)
        sp = np.linalg.norm(vxy, axis=1)

        # Vertical velocity
        vy = _grad(y_rel, dt)

        # Local minima
        mins = _local_minima(y_rel).astype(float)

        # Store debug signals (robust_norm so they all sit in [0,1])
        debug_y_rel   = _robust_norm(y_rel)           # 0 = low, 1 = high
        debug_sp      = _robust_norm(sp)              # 0 = slow, 1 = fast
        debug_vy_abs  = _robust_norm(np.abs(vy))      # 0 = still, 1 = moving vertically a lot
        debug_mins    = mins                          # 0 or 1
    else:
        print("[debug] No valid foot index for debug signals.")

    edges = skeleton_edges(skeleton)
    root_idx = next((j.joint_index for j in skeleton if getattr(j, "is_root", False)), 0)

    # -------- Extract beats (v1 or v2) --------
    if args.v2:
        params = BeatParamsV2()
        out = extract_beats_v2(
            positions, fps, JOINT_INDICES, params,
            pelvis_idx=pelvis_idx, left_foot_idx=LFOOT_IDX, right_foot_idx=RFOOT_IDX
        )
    else:
        params = BeatParamsV1()
        out = extract_beats_v1(
            positions, fps, JOINT_INDICES, params,
            pelvis_idx=pelvis_idx, left_foot_idx=LFOOT_IDX, right_foot_idx=RFOOT_IDX
        )

    events = out["events_idx"]       # rule-based events
    # ----------------- Optional ML events -----------------
    events_ml = None
    if args.ml_events is not None:
        events_ml = np.load(args.ml_events).astype(int)

        # clamp to valid range [0, T-1] and deduplicate indices
        events_ml = events_ml[(events_ml >= 0) & (events_ml < T)]
        events_ml = np.unique(events_ml)

        # apply simple time-based NMS to avoid double triggers
        events_ml = _dedup_events_by_time(events_ml, fps, args.ml_min_sep)
        print(f"[ml] loaded {events_ml.size} ML events after min-sep={args.ml_min_sep:.3f}s")
    else:
        print("[ml] no ML events file provided (use --ml-events path/to/file.ml_events.npy)")

    score = out["beat_score"]

    print(f"File: {args.bvh}")
    print(f"Frames: {T}  FPS: {fps}  Duration: {T / fps:.2f}s  Events (rule-based): {len(events)}")
    if len(events) > 1:
        ibi = np.diff(events) / fps
        print(f"  IBI mean={ibi.mean():.3f}s std={ibi.std():.3f}s  (~{60/ibi.mean():.1f} BPM)")

    # -------- Collect signals --------
    C_dec   = out.get("C_decel",    np.zeros(T))
    C_pel   = out.get("C_pelvis",   np.zeros(T))
    C_foot  = out.get("C_foot",     np.zeros(T))
    C_accel = out.get("C_accel",    np.zeros(T))
    C_rev   = out.get("C_reversal", np.zeros(T))

    # Optional ML probability
    ml_prob = None
    if args.ml_prob is not None:
        try:
            ml_prob = np.load(args.ml_prob)
            if ml_prob.shape[0] != T:
                print(f"[ml-prob] WARNING: length mismatch (prob={ml_prob.shape[0]}, T={T}) -> ignoring")
                ml_prob = None
            else:
                print(f"[ml-prob] loaded {args.ml_prob}")
        except Exception as e:
            print(f"[ml-prob] failed to load {args.ml_prob}: {e}")
            ml_prob = None

    all_signals = {
        "score":      score,
        "C_decel":    C_dec,
        "C_pelvis":   C_pel,
        "C_foot":     C_foot,
        "C_accel":    C_accel,
        "C_reversal": C_rev,
        # debug-only signals for the selected foot
        "dbg_y_rel":  debug_y_rel,   # normalized height
        "dbg_sp":     debug_sp,      # normalized horizontal speed
        "dbg_vy_abs": debug_vy_abs,  # normalized |vertical velocity|
        "dbg_mins":   debug_mins,    # 0/1 local minima
    }
    if ml_prob is not None:
        all_signals["ml_prob"] = ml_prob


    # Decide which event sources to show
    show_rule = (args.events_mode in ("rule", "both"))
    show_ml   = (args.events_mode in ("ml", "both")) and (events_ml is not None)

    # -------- 2D stick animation setup --------
    plane = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}[args.view]
    XY = positions[:, :, plane]
    XY = XY - XY[:, root_idx:root_idx + 1, :]

    mins_xy = XY.reshape(-1, 2).min(axis=0)
    maxs_xy = XY.reshape(-1, 2).max(axis=0)
    span = (maxs_xy - mins_xy)
    margin = 0.1 * np.max(span)
    xlim = (mins_xy[0] - margin, maxs_xy[0] + margin)
    ylim = (mins_xy[1] - margin, maxs_xy[1] + margin)

    stride = max(1, int(args.stride))
    disp_fps = (fps / stride) if args.framerate is None else args.framerate
    win_sec = max(0.0, float(args.win_seconds))

    # playback speed: 1.0 = normal, 0.5 = half-speed, etc.
    playback_speed = float(args.playback_speed)
    if playback_speed <= 0:
        playback_speed = 1.0  # safety fallback

    # Figure and axes: skeleton only, or signals + skeleton
    if args.plot_cues:
        fig, (ax_sig, ax) = plt.subplots(
            2, 1, figsize=(10, 8),
            gridspec_kw={"height_ratios": [1, 3]}
        )
    else:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax_sig = None

    # Skeleton axis formatting
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    title_extra = ""
    if show_rule and show_ml:
        title_extra = " (red = rule, cyan = ML)"
    elif show_ml and not show_rule:
        title_extra = " (cyan = ML)"
    elif show_rule and not show_ml:
        title_extra = " (red = rule)"

    ax.set_title(f"{args.bvh} — beats flash red{title_extra}")
    ax.set_xlabel(["X", "X", "Y"][plane[0]] + " axis")
    ax.set_ylabel(["Y", "Z", "Z"][plane[1]] + " axis")

    # Prepare lines for skeleton plot
    edges = skeleton_edges(skeleton)
    lines = [ax.plot([], [], lw=2)[0] for _ in edges]
    joints_plot, = ax.plot([], [], "o", ms=3)
    flash_rule, = ax.plot([], [], "o", ms=10, mfc="none", mec="red",  mew=2)
    flash_ml,   = ax.plot([], [], "o", ms=10, mfc="none", mec="cyan", mew=2)
    frame_text = ax.text(0.02, 0.95, "", transform=ax.transAxes)

    frames = range(0, T, stride)

    # Decide which events we use for flashing on the skeleton
    if args.events_mode == "ml" and events_ml is not None:
        events_display = events_ml
    else:
        # fall back to rule-based events (also used if ml_events is missing)
        events_display = events

    evset = set(map(int, events_display))

    evset_rule = set(map(int, events)) if show_rule else set()
    evset_ml   = set(map(int, events_ml)) if show_ml else set()

    # Signals axis (if requested)
    vline = None
    t = np.arange(T) / fps
    if ax_sig is not None:
        requested = [s.strip() for s in args.signals.split(",") if s.strip()]
        selected = [s for s in requested if s in all_signals]
        if not selected:
            print(f"[signals] No valid signals in {requested}, defaulting to ['score']")
            selected = ["score"]

        for name in selected:
            ax_sig.plot(t, all_signals[name], label=name)

        if "score" in selected:
            ax_sig.axhline(params.score_threshold, color="k", ls=":", lw=0.8)

        # Vertical lines for rule events (red) and ML events (cyan)
        # rule events in red
        for e in events:
            ax_sig.axvline(e / fps, color="r", lw=0.5, alpha=0.3)

        # optional ML events in blue if requested / available
        if args.events_mode in ("ml", "both") and events_ml is not None:
            for e in events_ml:
                ax_sig.axvline(e / fps, color="b", lw=0.5, alpha=0.5)

        vline = ax_sig.axvline(0.0, color="k", lw=1.0, ls="--")  # moving cursor
        ax_sig.set_ylabel("signal value")
        ax_sig.legend(loc="upper right")

        # initial x-limits based on window length
        if win_sec > 0.0:
            ax_sig.set_xlim(0.0, min(win_sec, t[-1]))
        else:
            ax_sig.set_xlim(t[0], t[-1])

    # ------- Animation state for pause + labelling -------
    current_frame = 0
    anim_running = True
    labeled_beats = set()  # frames you've toggled with 'b'

    def init():
        for ln in lines:
            ln.set_data([], [])
        joints_plot.set_data([], [])
        flash_rule.set_data([], [])
        flash_ml.set_data([], [])
        frame_text.set_text("")
        if vline is not None:
            vline.set_xdata([0.0, 0.0])
        return []

    def update(fi):
        nonlocal current_frame
        current_frame = fi

        XYf = XY[fi]
        # draw bones
        for ln, (p, c) in zip(lines, edges):
            seg = XYf[[p, c], :]
            ln.set_data(seg[:, 0], seg[:, 1])
        # draw joints
        joints_plot.set_data(XYf[:, 0], XYf[:, 1])

        # flash near rule events (red)
        if fi in evset_rule or (fi - 1) in evset_rule or (fi + 1) in evset_rule:
            xr, yr = XYf[root_idx, 0], XYf[root_idx, 1]
            flash_rule.set_data([xr], [yr])
        else:
            flash_rule.set_data([], [])

        # flash near ML events (cyan)
        if evset_ml and (fi in evset_ml or (fi - 1) in evset_ml or (fi + 1) in evset_ml):
            xm, ym = XYf[root_idx, 0], XYf[root_idx, 1]
            flash_ml.set_data([xm], [ym])
        else:
            flash_ml.set_data([], [])

        frame_text.set_text(f"frame {fi}/{T - 1} | {fi / fps:.3f}s")

        # move vertical line on signals plot
        if vline is not None:
            t_cur = fi / fps
            vline.set_xdata([t_cur, t_cur])

            # jump the cue plot to the current win_sec chunk
            if win_sec > 0.0:
                seg_idx = int(t_cur // win_sec)         # 0→0–5, 1→5–10, etc.
                start = seg_idx * win_sec
                end = start + win_sec

                # clamp to end
                if end > t[-1]:
                    end = t[-1]
                    start = max(0.0, end - win_sec)

                ax_sig.set_xlim(start, end)

        artists = lines + [joints_plot, flash_rule, flash_ml, frame_text]
        if vline is not None:
            artists.append(vline)
        return artists

    interval_ms = 1000.0 / (disp_fps * playback_speed)
    anim = FuncAnimation(
        fig, update, frames=frames, init_func=init,
        interval=interval_ms, repeat=True, blit=False
    )

    # ------- Key handler: pause + label beats + save -------
    def print_debug_for_frame(fi: int):
        t_cur = fi / fps
        print(f"[PAUSE] frame = {fi} time = {t_cur:.3f}s")

        def safe(name, arr):
            if arr is not None and arr.shape[0] == T:
                print(f"  {name}: {float(arr[fi]):.4f}")

        safe("score", score)
        safe("C_foot", C_foot)
        safe("dbg_y_rel", debug_y_rel)
        safe("dbg_sp", debug_sp)
        safe("dbg_vy_abs", debug_vy_abs)
        safe("dbg_mins", debug_mins)
        if ml_prob is not None and ml_prob.shape[0] == T:
            safe("ml_prob", ml_prob)

    def on_key(event):
        nonlocal anim_running, labeled_beats
        if event.key == " ":
            # toggle pause/play AND print debug values at this frame
            if anim_running:
                anim.event_source.stop()
                anim_running = False
                print_debug_for_frame(current_frame)
            else:
                anim.event_source.start()
                anim_running = True
                print("[PLAY]")
        elif event.key == "b":
            # toggle beat at current_frame
            fi = current_frame
            if fi in labeled_beats:
                labeled_beats.remove(fi)
                print(f"[label] removed beat at frame {fi}")
            else:
                labeled_beats.add(fi)
                print(f"[label] added beat at frame {fi}")
        elif event.key == "s":
            # save labels to <bvh>.beats.npy
            if labeled_beats:
                beats = np.array(sorted(labeled_beats), dtype=int)
                base = re.sub(r"\.bvh$", "", args.bvh, flags=re.IGNORECASE)
                outpath = base + ".beats.npy"
                np.save(outpath, beats)
                print(f"[label] saved {beats.size} beats to {outpath}")
            else:
                print("[label] no beats to save")

    fig.canvas.mpl_connect("key_press_event", on_key)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
