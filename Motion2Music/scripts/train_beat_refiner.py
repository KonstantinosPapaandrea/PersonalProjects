from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# train_beat_refiner.py
import argparse
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, precision_recall_fscore_support
import joblib

# You can tune this: larger radius = more temporal context
CONTEXT_RADIUS = 5  # you were already using 5 (window=11 frames)


def build_context_features(X: np.ndarray, clip_ids: np.ndarray, radius: int) -> np.ndarray:
    """
    Build context-augmented features.

    For each frame i, we take the base features from [i-radius .. i+radius],
    clamped within the same clip, and concatenate them.

    X:         (N, D)
    clip_ids:  (N,)
    radius:    int >= 0
    returns:   (N, D * (2*radius+1))
    """
    X = np.asarray(X, dtype=float)
    clip_ids = np.asarray(clip_ids, dtype=int)
    N, D = X.shape
    if radius <= 0:
        return X.copy()

    K = 2 * radius + 1
    X_ctx = np.zeros((N, D * K), dtype=float)

    unique_clips = np.unique(clip_ids)
    for clip in unique_clips:
        idx = np.where(clip_ids == clip)[0]  # indices of this clip in global array
        Xc = X[idx]                          # (Tc, D)
        Tc = Xc.shape[0]
        for local_t, global_i in enumerate(idx):
            cols = []
            for d in range(-radius, radius + 1):
                t2 = local_t + d
                if t2 < 0:
                    t2 = 0
                elif t2 >= Tc:
                    t2 = Tc - 1
                cols.append(Xc[t2])
            X_ctx[global_i] = np.concatenate(cols, axis=0)

    return X_ctx


# ---------- EVENT-LEVEL HELPERS ----------

def frames_to_segments(y_bin: np.ndarray):
    """
    Turn a binary 0/1 sequence into a list of [start, end) segments
    of consecutive ones.
    """
    y_bin = np.asarray(y_bin, dtype=int)
    T = y_bin.shape[0]
    if T == 0:
        return []

    padded = np.r_[0, y_bin, 0]
    diff = np.diff(padded)
    starts = np.where(diff == 1)[0]  # where we go 0->1
    ends   = np.where(diff == -1)[0] # where we go 1->0
    segments = [(int(s), int(e)) for s, e in zip(starts, ends)]
    return segments


def segments_overlap(seg_a, seg_b) -> bool:
    """
    seg_a: (start_a, end_a), end-exclusive
    seg_b: (start_b, end_b)
    Overlap if intervals intersect.
    """
    sa, ea = seg_a
    sb, eb = seg_b
    return not (ea <= sb or eb <= sa)


def event_level_metrics(prob: np.ndarray, y_true: np.ndarray, thr: float):
    """
    Compute event-level precision/recall/F1 given:
      - per-frame probabilities 'prob'
      - widened frame labels y_true (0/1)
      - threshold thr

    Steps:
      1) prob >= thr -> y_pred (0/1)
      2) convert y_true, y_pred to segments of consecutive 1s
      3) a predicted segment is TP if it overlaps at least one true segment
    """
    prob = np.asarray(prob, dtype=float)
    y_true = np.asarray(y_true, dtype=int)
    assert prob.shape[0] == y_true.shape[0]

    # frame-level predictions
    y_pred = (prob >= float(thr)).astype(int)

    true_segments = frames_to_segments(y_true)
    pred_segments = frames_to_segments(y_pred)

    n_true = len(true_segments)
    n_pred = len(pred_segments)

    if n_true == 0 and n_pred == 0:
        return 1.0, 1.0, 1.0, n_true, n_pred  # degenerate but "perfect"
    if n_pred == 0:
        return 0.0, 0.0, 0.0, n_true, n_pred
    if n_true == 0:
        return 0.0, 1.0, 0.0, n_true, n_pred  # all preds are FP

    matched_true = np.zeros(n_true, dtype=bool)
    matched_pred = np.zeros(n_pred, dtype=bool)

    for i, pseg in enumerate(pred_segments):
        for j, tseg in enumerate(true_segments):
            if segments_overlap(pseg, tseg):
                matched_pred[i] = True
                matched_true[j] = True

    tp = matched_pred.sum()

    precision = tp / n_pred if n_pred > 0 else 0.0
    recall    = matched_true.sum() / n_true if n_true > 0 else 0.0
    if precision + recall > 0:
        f1 = 2.0 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    return precision, recall, f1, n_true, n_pred


# ---------- MAIN ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Path to ml_dataset_aist_wide.npz (widened labels)")
    ap.add_argument("--out-model", required=True, help="Path to save beat_refiner.joblib")
    ap.add_argument("--no-shuffle-clips", action="store_true",
                    help="If set, do not shuffle clip IDs before splitting (debug).")
    args = ap.parse_args()

    # ---- Load dataset ----
    print(f"[load] {args.dataset}")
    data = np.load(args.dataset)
    if not {"X", "y", "clip_ids"}.issubset(data.files):
        raise ValueError(f"Dataset must contain X, y, clip_ids. Found keys: {data.files}")

    X_base = data["X"]        # (N, 6)
    y = data["y"].astype(int) # (N,)
    clip_ids = data["clip_ids"].astype(int)

    N, D = X_base.shape
    unique_clips = np.unique(clip_ids)
    n_clips = unique_clips.size

    print(f"[data] X shape={X_base.shape}, y shape={y.shape}, clips={n_clips}")
    pos_frames = int(y.sum())
    print(f"[data] positive frames: {pos_frames}  ({100.0 * pos_frames / N:.2f}% of frames)")

    # ---- Build context features ----
    print(f"[context] building context features with radius={CONTEXT_RADIUS} "
          f"(window size={2*CONTEXT_RADIUS+1}).")
    X_ctx = build_context_features(X_base, clip_ids, radius=CONTEXT_RADIUS)
    print(f"[context] X_ctx shape={X_ctx.shape}")

    # ---- Split by clip: 80% train, 10% val, 10% test ----
    if not args.no_shuffle_clips:
        rng = np.random.RandomState(0)
        rng.shuffle(unique_clips)

    n_train = int(0.8 * n_clips)
    n_val   = int(0.1 * n_clips)
    n_test  = n_clips - n_train - n_val

    train_clips = unique_clips[:n_train]
    val_clips   = unique_clips[n_train:n_train + n_val]
    test_clips  = unique_clips[n_train + n_val:]

    print(f"[split] train clips={train_clips.size}, val clips={val_clips.size}, test clips={test_clips.size}")

    train_mask = np.isin(clip_ids, train_clips)
    val_mask   = np.isin(clip_ids, val_clips)
    test_mask  = np.isin(clip_ids, test_clips)

    X_train, y_train = X_ctx[train_mask], y[train_mask]
    X_val,   y_val   = X_ctx[val_mask],   y[val_mask]
    X_test,  y_test  = X_ctx[test_mask],  y[test_mask]

    print(f"[split] X_train={X_train.shape}, X_val={X_val.shape}, X_test={X_test.shape}")
    print(f"[split] y_train pos%={100.0 * y_train.mean():.2f}, "
          f"y_val pos%={100.0 * y_val.mean():.2f}, y_test pos%={100.0 * y_test.mean():.2f}")

    # ---- Train Logistic Regression ----
    print("[train] Fitting LogisticRegression (class_weight='balanced') on context features.")
    clf = LogisticRegression(
        class_weight="balanced",
        max_iter=500,
        solver="lbfgs",
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    # ---- Validation: evaluate threshold grid (frame + event level) ----
    print("[val] Evaluating on validation set.")
    prob_val = clf.predict_proba(X_val)[:, 1]

    thr_grid = np.linspace(0.1, 0.9, 17)
    best_thr_event = 0.5
    best_event_f1 = -1.0

    print("[val] threshold sweep:")
    print("  thr | frame_P  frame_R  frame_F1 | ev_P   ev_R   ev_F1   n_true_ev  n_pred_ev")
    for thr in thr_grid:
        thr_f = float(thr)
        y_pred = (prob_val >= thr_f).astype(int)
        p_f, r_f, f1_f, _ = precision_recall_fscore_support(
            y_val, y_pred, average="binary", zero_division=0
        )
        p_ev, r_ev, f1_ev, n_true_ev, n_pred_ev = event_level_metrics(prob_val, y_val, thr=thr_f)

        print(f" {thr_f:4.2f} |  {p_f:6.3f}  {r_f:6.3f}  {f1_f:6.3f} | "
              f"{p_ev:6.3f} {r_ev:6.3f} {f1_ev:6.3f}   {n_true_ev:5d}      {n_pred_ev:5d}")

        # choose best threshold by event-level F1
        if f1_ev > best_event_f1:
            best_event_f1 = f1_ev
            best_thr_event = thr_f

    print(f"[val] best event-level threshold={best_thr_event:.3f}, best event-level F1={best_event_f1:.4f}")

    # Detailed val frame-level report at best *event* threshold
    y_val_pred = (prob_val >= best_thr_event).astype(int)
    print("[val] frame-level classification report at best event-threshold:")
    print(classification_report(y_val, y_val_pred, digits=3, zero_division=0))
    p_f, r_f, f1_f, _ = precision_recall_fscore_support(
        y_val, y_val_pred, average="binary", zero_division=0
    )
    print(f"[val] frame-level precision={p_f:.3f}, recall={r_f:.3f}, f1={f1_f:.3f}")

    # Validation: event-level metrics at best event threshold
    p_ev, r_ev, f1_ev, n_true_ev, n_pred_ev = event_level_metrics(prob_val, y_val, thr=best_thr_event)
    print(f"[val-events] event-level precision={p_ev:.3f}, recall={r_ev:.3f}, f1={f1_ev:.3f}, "
          f"n_true_events={n_true_ev}, n_pred_events={n_pred_ev}")

    # ---- Test set evaluation (frame-level + event-level) ----
    print("[test] Evaluating on held-out test set.")
    prob_test = clf.predict_proba(X_test)[:, 1]
    y_test_pred = (prob_test >= best_thr_event).astype(int)
    print("[test] frame-level classification report at best event-threshold:")
    print(classification_report(y_test, y_test_pred, digits=3, zero_division=0))
    p_ft, r_ft, f1_ft, _ = precision_recall_fscore_support(
        y_test, y_test_pred, average="binary", zero_division=0
    )
    print(f"[test] frame-level precision={p_ft:.3f}, recall={r_ft:.3f}, f1={f1_ft:.3f}")

    p_evt, r_evt, f1_evt, n_true_evt, n_pred_evt = event_level_metrics(prob_test, y_test, thr=best_thr_event)
    print(f"[test-events] event-level precision={p_evt:.3f}, recall={r_evt:.3f}, f1={f1_evt:.3f}, "
          f"n_true_events={n_true_evt}, n_pred_events={n_pred_evt}")

    # ---- Save model + metadata ----
    payload = {
        "model": clf,
        "threshold": best_thr_event,     # <= NOTE: event-optimized threshold
        "context_radius": CONTEXT_RADIUS,
    }
    print(f"[save] model + threshold + context_radius -> {args.out_model}")
    joblib.dump(payload, args.out_model)


if __name__ == "__main__":
    main()
