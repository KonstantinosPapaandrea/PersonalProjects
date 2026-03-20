from pathlib import Path
import argparse
import csv
import json
import numpy as np
import joblib
from sklearn.metrics import precision_recall_fscore_support

from train_beat_refiner import build_context_features, event_level_metrics, frames_to_segments


def probs_to_events(prob: np.ndarray, thr: float) -> np.ndarray:
    prob = np.asarray(prob, dtype=float)
    if prob.size == 0:
        return np.zeros(0, dtype=int)
    mask = prob >= float(thr)
    padded = np.r_[False, mask, False]
    changes = np.diff(padded.astype(int))
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]
    out = []
    for s, e in zip(starts, ends):
        if e <= s:
            continue
        seg = prob[s:e]
        out.append(int(s + np.argmax(seg)))
    return np.asarray(out, dtype=int)


def segments_to_centers(y_bin: np.ndarray) -> np.ndarray:
    segs = frames_to_segments(y_bin)
    if not segs:
        return np.zeros(0, dtype=int)
    centers = [int((s + (e - 1)) // 2) for s, e in segs]
    return np.asarray(centers, dtype=int)


def greedy_match_by_distance(true_idx: np.ndarray, pred_idx: np.ndarray, max_dist_frames: int | None = None):
    true_idx = np.asarray(true_idx, dtype=int)
    pred_idx = np.asarray(pred_idx, dtype=int)
    if true_idx.size == 0 or pred_idx.size == 0:
        return []

    pairs = []
    for i, t in enumerate(true_idx):
        for j, p in enumerate(pred_idx):
            pairs.append((abs(int(t) - int(p)), i, j))
    pairs.sort(key=lambda x: x[0])

    used_t = set()
    used_p = set()
    out = []
    for dist, i, j in pairs:
        if max_dist_frames is not None and dist > int(max_dist_frames):
            continue
        if i in used_t or j in used_p:
            continue
        used_t.add(i)
        used_p.add(j)
        out.append((i, j, dist))
    return out


def parse_model_payload(path: Path):
    payload = joblib.load(path)
    if isinstance(payload, dict) and "model" in payload:
        clf = payload["model"]
        thr = float(payload.get("threshold", 0.5))
        radius = payload.get("context_radius", 0)
        radius = 0 if radius is None else int(radius)
    else:
        clf = payload
        thr = 0.5
        radius = 0
    return clf, thr, radius


def build_split_masks(clip_ids: np.ndarray):
    unique_clips = np.unique(clip_ids)
    rng = np.random.RandomState(0)
    rng.shuffle(unique_clips)
    n_train = int(0.8 * unique_clips.size)
    n_val = int(0.1 * unique_clips.size)
    train_clips = unique_clips[:n_train]
    val_clips = unique_clips[n_train : n_train + n_val]
    test_clips = unique_clips[n_train + n_val :]
    train_mask = np.isin(clip_ids, train_clips)
    val_mask = np.isin(clip_ids, val_clips)
    test_mask = np.isin(clip_ids, test_clips)
    return train_clips, val_clips, test_clips, train_mask, val_mask, test_mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Path to .npz with X,y,clip_ids,fps_all")
    ap.add_argument("--model", required=True, help="Path to beat refiner .joblib")
    ap.add_argument("--out-dir", default="outputs/beat_eval", help="Output directory")
    ap.add_argument("--thr-min", type=float, default=0.05)
    ap.add_argument("--thr-max", type=float, default=0.95)
    ap.add_argument("--thr-step", type=float, default=0.01)
    ap.add_argument(
        "--match-max-sec",
        type=float,
        default=0.20,
        help="Maximum |pred-true| time distance (sec) for a pair to count as matched in exported pairs CSV.",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = np.load(args.dataset)
    required = {"X", "y", "clip_ids", "fps_all"}
    if not required.issubset(set(data.files)):
        raise ValueError(f"Dataset must contain {required}. Found: {data.files}")

    X = data["X"].astype(float)
    y = data["y"].astype(int)
    clip_ids = data["clip_ids"].astype(int)
    fps_all = data["fps_all"].astype(float)

    _, val_clips, test_clips, _, val_mask, test_mask = build_split_masks(clip_ids)

    clf, model_thr, context_radius = parse_model_payload(Path(args.model))
    X_ctx = build_context_features(X, clip_ids, radius=context_radius)

    prob_val = clf.predict_proba(X_ctx[val_mask])[:, 1]
    y_val = y[val_mask]
    prob_test = clf.predict_proba(X_ctx[test_mask])[:, 1]
    y_test = y[test_mask]

    thresholds = np.arange(args.thr_min, args.thr_max + 1e-12, args.thr_step)
    rows = []
    best_f1 = -1.0
    best_recall = -1.0
    best_thr = float(model_thr)
    for thr in thresholds:
        thr = float(np.round(thr, 6))
        y_val_pred = (prob_val >= thr).astype(int)
        fp, fr, ff1, _ = precision_recall_fscore_support(
            y_val, y_val_pred, average="binary", zero_division=0
        )
        ep, er, ef1, n_true_ev, n_pred_ev = event_level_metrics(prob_val, y_val, thr)
        rows.append(
            {
                "threshold": thr,
                "frame_precision": fp,
                "frame_recall": fr,
                "frame_f1": ff1,
                "event_precision": ep,
                "event_recall": er,
                "event_f1": ef1,
                "val_true_events": n_true_ev,
                "val_pred_events": n_pred_ev,
            }
        )
        if (ef1 > best_f1) or (np.isclose(ef1, best_f1) and er > best_recall):
            best_f1 = ef1
            best_recall = er
            best_thr = thr

    # Evaluate on test with selected threshold.
    y_test_pred = (prob_test >= best_thr).astype(int)
    tfp, tfr, tff1, _ = precision_recall_fscore_support(
        y_test, y_test_pred, average="binary", zero_division=0
    )
    tep, ter, tef1, t_true_ev, t_pred_ev = event_level_metrics(prob_test, y_test, best_thr)

    # Write threshold sweep CSV.
    sweep_csv = out_dir / "threshold_sweep.csv"
    with sweep_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # Export true/pred events on test clips.
    # Reconstruct local test arrays per clip.
    test_long_rows = []
    pair_rows = []
    clip_summary_rows = []

    for clip in test_clips:
        gidx = np.where(clip_ids == clip)[0]
        if gidx.size == 0:
            continue
        fps = float(fps_all[int(clip)]) if int(clip) < fps_all.size else float(np.nanmean(fps_all))
        y_clip = y[gidx]
        prob_clip = clf.predict_proba(X_ctx[gidx])[:, 1]

        true_ev = segments_to_centers(y_clip)
        pred_ev = probs_to_events(prob_clip, best_thr)
        max_dist_frames = int(round(float(args.match_max_sec) * fps))
        matches = greedy_match_by_distance(true_ev, pred_ev, max_dist_frames=max_dist_frames)

        for k, idx in enumerate(true_ev):
            test_long_rows.append(
                {
                    "clip_id": int(clip),
                    "event_type": "true",
                    "event_rank": k,
                    "frame_idx_local": int(idx),
                    "time_sec": float(idx / fps),
                    "prob": "",
                }
            )

        for k, idx in enumerate(pred_ev):
            test_long_rows.append(
                {
                    "clip_id": int(clip),
                    "event_type": "pred",
                    "event_rank": k,
                    "frame_idx_local": int(idx),
                    "time_sec": float(idx / fps),
                    "prob": float(prob_clip[idx]),
                }
            )

        used_true = set()
        used_pred = set()
        for mi, (ti, pi, dist) in enumerate(matches):
            used_true.add(ti)
            used_pred.add(pi)
            t_idx = int(true_ev[ti])
            p_idx = int(pred_ev[pi])
            pair_rows.append(
                {
                    "clip_id": int(clip),
                    "pair_rank": mi,
                    "matched": 1,
                    "true_frame": t_idx,
                    "true_time_sec": float(t_idx / fps),
                    "pred_frame": p_idx,
                    "pred_time_sec": float(p_idx / fps),
                    "delta_frames": int(p_idx - t_idx),
                    "delta_sec": float((p_idx - t_idx) / fps),
                }
            )

        for ti, t_idx in enumerate(true_ev):
            if ti in used_true:
                continue
            pair_rows.append(
                {
                    "clip_id": int(clip),
                    "pair_rank": -1,
                    "matched": 0,
                    "true_frame": int(t_idx),
                    "true_time_sec": float(t_idx / fps),
                    "pred_frame": "",
                    "pred_time_sec": "",
                    "delta_frames": "",
                    "delta_sec": "",
                }
            )

        for pi, p_idx in enumerate(pred_ev):
            if pi in used_pred:
                continue
            pair_rows.append(
                {
                    "clip_id": int(clip),
                    "pair_rank": -1,
                    "matched": 0,
                    "true_frame": "",
                    "true_time_sec": "",
                    "pred_frame": int(p_idx),
                    "pred_time_sec": float(p_idx / fps),
                    "delta_frames": "",
                    "delta_sec": "",
                }
            )

        tp = len(matches)
        n_true = int(true_ev.size)
        n_pred = int(pred_ev.size)
        ev_p = float(tp / n_pred) if n_pred else 0.0
        ev_r = float(tp / n_true) if n_true else 0.0
        ev_f1 = float((2 * ev_p * ev_r / (ev_p + ev_r)) if (ev_p + ev_r) > 0 else 0.0)
        clip_summary_rows.append(
            {
                "clip_id": int(clip),
                "fps": fps,
                "true_events": n_true,
                "pred_events": n_pred,
                "matched_events": tp,
                "event_precision": ev_p,
                "event_recall": ev_r,
                "event_f1": ev_f1,
            }
        )

    events_csv = out_dir / "test_events_true_pred.csv"
    with events_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["clip_id", "event_type", "event_rank", "frame_idx_local", "time_sec", "prob"],
        )
        writer.writeheader()
        writer.writerows(test_long_rows)

    pairs_csv = out_dir / "test_event_pairs.csv"
    with pairs_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "clip_id",
                "pair_rank",
                "matched",
                "true_frame",
                "true_time_sec",
                "pred_frame",
                "pred_time_sec",
                "delta_frames",
                "delta_sec",
            ],
        )
        writer.writeheader()
        writer.writerows(pair_rows)

    clip_csv = out_dir / "test_clip_event_metrics.csv"
    with clip_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(clip_summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(clip_summary_rows)

    summary = {
        "model_path": str(args.model),
        "dataset_path": str(args.dataset),
        "context_radius": int(context_radius),
        "model_threshold": float(model_thr),
        "best_threshold_by_val_event_f1": float(best_thr),
        "val_best_event_f1": float(best_f1),
        "test_frame_precision": float(tfp),
        "test_frame_recall": float(tfr),
        "test_frame_f1": float(tff1),
        "test_event_precision": float(tep),
        "test_event_recall": float(ter),
        "test_event_f1": float(tef1),
        "test_true_events": int(t_true_ev),
        "test_pred_events": int(t_pred_ev),
        "outputs": {
            "threshold_sweep_csv": str(sweep_csv),
            "test_events_true_pred_csv": str(events_csv),
            "test_event_pairs_csv": str(pairs_csv),
            "test_clip_event_metrics_csv": str(clip_csv),
        },
    }
    summary_path = out_dir / "threshold_tuning_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
