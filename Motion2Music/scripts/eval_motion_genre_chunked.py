#!/usr/bin/env python3
"""
eval_motion_genre_chunked.py

Evaluate motion->genre with fixed-length chunking using an existing clip-level split.

Key design:
- Uses clip-level train/test split from meta_train.csv / meta_test.csv
- Chunks are created ONLY inside each split (no leakage)
- Reports both chunk-level and clip-level metrics
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from predict_prompt_and_generate import compute_motion_features


def _duration_s(lma_df: pd.DataFrame, beats_df: pd.DataFrame) -> float:
    if "END_TIME_S" in lma_df.columns:
        v = pd.to_numeric(lma_df["END_TIME_S"], errors="coerce").to_numpy(dtype=float)
        if np.any(np.isfinite(v)):
            return float(np.nanmax(v))
    if "time_s" in beats_df.columns:
        v = pd.to_numeric(beats_df["time_s"], errors="coerce").to_numpy(dtype=float)
        if np.any(np.isfinite(v)):
            return float(np.nanmax(v))
    return 0.0


def _chunk_starts(duration_s: float, chunk_s: float, hop_s: float) -> list[float]:
    if duration_s <= 0 or chunk_s <= 0:
        return []
    hop = hop_s if hop_s > 0 else chunk_s
    out: list[float] = []
    cur = 0.0
    while cur + (0.5 * chunk_s) <= duration_s:
        out.append(float(cur))
        cur += hop
    tail = max(0.0, duration_s - chunk_s)
    if not out:
        out = [tail]
    elif abs(tail - out[-1]) > 1e-6 and (duration_s - out[-1]) > 0.5 * chunk_s:
        out.append(float(tail))
    # unique/sorted
    out = sorted(set(round(x, 6) for x in out))
    return out


def _extract_chunk(lma_df: pd.DataFrame, beats_df: pd.DataFrame, s: float, e: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "START_TIME_S" in lma_df.columns and "END_TIME_S" in lma_df.columns:
        l = lma_df[
            (pd.to_numeric(lma_df["END_TIME_S"], errors="coerce") > float(s))
            & (pd.to_numeric(lma_df["START_TIME_S"], errors="coerce") < float(e))
        ].copy()
    else:
        # fallback: no time columns; use full frame
        l = lma_df.copy()

    if "time_s" in beats_df.columns:
        b = beats_df[
            (pd.to_numeric(beats_df["time_s"], errors="coerce") >= float(s))
            & (pd.to_numeric(beats_df["time_s"], errors="coerce") < float(e))
        ].copy()
        if not b.empty:
            b["time_s"] = b["time_s"].astype(float) - float(s)
    else:
        b = beats_df.copy()
        if "time_s" not in b.columns:
            b["time_s"] = 0.0

    return l, b


def _rows_to_chunks(
    meta_df: pd.DataFrame,
    features_dir: Path,
    x_cols: list[str],
    chunk_seconds: float,
    hop_seconds: float,
    min_lma_rows: int,
) -> tuple[np.ndarray, np.ndarray, list[str], list[str], list[int]]:
    X_chunks: list[np.ndarray] = []
    y_chunks: list[str] = []
    clip_ids: list[str] = []
    stems: list[str] = []
    chunk_idx: list[int] = []

    for row in meta_df.itertuples(index=False):
        stem = str(getattr(row, "stem"))
        cid = str(getattr(row, "clip_id"))
        genre = str(getattr(row, "genre"))

        lma_path = features_dir / f"{stem}_lma.csv"
        beats_path = features_dir / f"{stem}_beats.csv"
        if not lma_path.exists() or not beats_path.exists():
            continue

        lma_df = pd.read_csv(lma_path)
        beats_df = pd.read_csv(beats_path)
        dur = _duration_s(lma_df, beats_df)
        starts = _chunk_starts(dur, chunk_seconds, hop_seconds)
        if not starts:
            starts = [0.0]

        kept = 0
        for j, s in enumerate(starts):
            e = min(float(dur), float(s + chunk_seconds)) if dur > 0 else float(s + chunk_seconds)
            if dur > 0 and (e - s) < 0.5 * float(chunk_seconds):
                continue

            l_chunk, b_chunk = _extract_chunk(lma_df, beats_df, s, e)
            if len(l_chunk) < int(min_lma_rows):
                continue

            try:
                feat = compute_motion_features(l_chunk, b_chunk)
            except Exception:
                continue

            x = np.zeros((len(x_cols),), dtype=np.float32)
            for k, c in enumerate(x_cols):
                v = feat.get(c, 0.0)
                x[k] = float(v) if np.isfinite(v) else 0.0

            X_chunks.append(x)
            y_chunks.append(genre)
            clip_ids.append(cid)
            stems.append(stem)
            chunk_idx.append(j)
            kept += 1

        # ensure at least one chunk fallback with full clip
        if kept == 0:
            try:
                feat = compute_motion_features(lma_df, beats_df)
                x = np.zeros((len(x_cols),), dtype=np.float32)
                for k, c in enumerate(x_cols):
                    v = feat.get(c, 0.0)
                    x[k] = float(v) if np.isfinite(v) else 0.0
                X_chunks.append(x)
                y_chunks.append(genre)
                clip_ids.append(cid)
                stems.append(stem)
                chunk_idx.append(0)
            except Exception:
                pass

    if not X_chunks:
        return np.zeros((0, len(x_cols)), dtype=np.float32), np.array([], dtype=object), [], [], []

    X = np.stack(X_chunks, axis=0).astype(np.float32)
    y = np.array(y_chunks, dtype=object)
    return X, y, clip_ids, stems, chunk_idx


def _clip_vote(
    clip_ids: list[str],
    y_true_chunks: np.ndarray,
    proba: np.ndarray,
    classes: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    by_clip_idx: dict[str, list[int]] = defaultdict(list)
    for i, cid in enumerate(clip_ids):
        by_clip_idx[cid].append(i)

    y_true_clip: list[str] = []
    y_pred_clip: list[str] = []
    clip_list: list[str] = []
    for cid, idxs in by_clip_idx.items():
        # assume same true label across chunks from same clip
        true_label = str(y_true_chunks[idxs[0]])
        p = np.mean(proba[idxs], axis=0)
        pred_label = str(classes[int(np.argmax(p))])
        clip_list.append(cid)
        y_true_clip.append(true_label)
        y_pred_clip.append(pred_label)
    return np.array(y_true_clip, dtype=object), np.array(y_pred_clip, dtype=object), clip_list


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split-dir", required=True, help="Folder containing meta_train.csv/meta_test.csv with genre column.")
    ap.add_argument("--dataset-dir", default="outputs/m2m_train", help="Used to load X_motion schema.")
    ap.add_argument("--features-dir", default="outputs/m2m_train/features")
    ap.add_argument("--chunk-seconds", type=float, default=12.0)
    ap.add_argument("--hop-seconds", type=float, default=12.0)
    ap.add_argument("--min-lma-rows", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-report", default="")
    ap.add_argument("--save-preds", action="store_true")
    args = ap.parse_args()

    split_dir = Path(args.split_dir)
    dataset_dir = Path(args.dataset_dir)
    features_dir = Path(args.features_dir)

    mt = split_dir / "meta_train.csv"
    ms = split_dir / "meta_test.csv"
    xp = dataset_dir / "X_motion.csv"
    if not mt.exists() or not ms.exists() or not xp.exists():
        raise FileNotFoundError("Need meta_train.csv, meta_test.csv, and X_motion.csv.")

    out_report = Path(args.out_report) if args.out_report else (split_dir / "eval_motion_genre_chunked_report.txt")

    meta_tr = pd.read_csv(mt)
    meta_te = pd.read_csv(ms)
    if "genre" not in meta_tr.columns or "genre" not in meta_te.columns:
        raise RuntimeError("meta_train/meta_test must contain a 'genre' column.")

    x_cols = pd.read_csv(xp).select_dtypes(include=[np.number]).columns.to_list()
    if not x_cols:
        raise RuntimeError("No numeric columns found in X_motion.csv")

    Xtr, ytr, cid_tr, _, _ = _rows_to_chunks(
        meta_df=meta_tr,
        features_dir=features_dir,
        x_cols=x_cols,
        chunk_seconds=float(args.chunk_seconds),
        hop_seconds=float(args.hop_seconds),
        min_lma_rows=int(args.min_lma_rows),
    )
    Xte, yte, cid_te, _, _ = _rows_to_chunks(
        meta_df=meta_te,
        features_dir=features_dir,
        x_cols=x_cols,
        chunk_seconds=float(args.chunk_seconds),
        hop_seconds=float(args.hop_seconds),
        min_lma_rows=int(args.min_lma_rows),
    )
    if len(ytr) == 0 or len(yte) == 0:
        raise RuntimeError("Chunking produced empty train or test set.")

    clf = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=5000, random_state=int(args.seed))),
        ]
    )
    clf.fit(Xtr, ytr)
    pred_chunk = clf.predict(Xte)
    proba_chunk = clf.predict_proba(Xte)
    classes = clf.named_steps["lr"].classes_

    chunk_acc = float(accuracy_score(yte, pred_chunk))
    chunk_f1_macro = float(f1_score(yte, pred_chunk, average="macro"))
    chunk_f1_weighted = float(f1_score(yte, pred_chunk, average="weighted"))

    y_true_clip, y_pred_clip, clip_list = _clip_vote(cid_te, yte, proba_chunk, classes)
    clip_acc = float(accuracy_score(y_true_clip, y_pred_clip))
    clip_f1_macro = float(f1_score(y_true_clip, y_pred_clip, average="macro"))
    clip_f1_weighted = float(f1_score(y_true_clip, y_pred_clip, average="weighted"))

    # Save confusion + class report (clip-level primary)
    all_classes = sorted(np.unique(np.concatenate([ytr, yte])).tolist())
    cm_clip = confusion_matrix(y_true_clip, y_pred_clip, labels=all_classes)
    pd.DataFrame(cm_clip, index=all_classes, columns=all_classes).to_csv(split_dir / "confusion_motion_chunked_clip.csv")
    rep_clip = classification_report(y_true_clip, y_pred_clip, output_dict=True, zero_division=0)
    (split_dir / "class_report_motion_chunked_clip.json").write_text(json.dumps(rep_clip, indent=2), encoding="utf-8")

    cm_chunk = confusion_matrix(yte, pred_chunk, labels=all_classes)
    pd.DataFrame(cm_chunk, index=all_classes, columns=all_classes).to_csv(split_dir / "confusion_motion_chunked_chunk.csv")
    rep_chunk = classification_report(yte, pred_chunk, output_dict=True, zero_division=0)
    (split_dir / "class_report_motion_chunked_chunk.json").write_text(json.dumps(rep_chunk, indent=2), encoding="utf-8")

    if args.save_preds:
        pd.DataFrame(
            {
                "clip_id": cid_te,
                "genre_true": yte,
                "genre_pred_chunk": pred_chunk,
            }
        ).to_csv(split_dir / "predictions_motion_chunked_chunks.csv", index=False)
        pd.DataFrame(
            {
                "clip_id": clip_list,
                "genre_true": y_true_clip,
                "genre_pred_clip": y_pred_clip,
            }
        ).to_csv(split_dir / "predictions_motion_chunked_clips.csv", index=False)

    lines = [
        f"split_dir={split_dir}",
        f"features_dir={features_dir}",
        f"chunk_seconds={float(args.chunk_seconds):.3f}",
        f"hop_seconds={float(args.hop_seconds):.3f}",
        f"min_lma_rows={int(args.min_lma_rows)}",
        f"seed={int(args.seed)}",
        f"x_dim={len(x_cols)}",
        f"train_clips={len(meta_tr)}",
        f"test_clips={len(meta_te)}",
        f"train_chunks={len(ytr)}",
        f"test_chunks={len(yte)}",
        f"chunk_accuracy={chunk_acc:.6f}",
        f"chunk_f1_macro={chunk_f1_macro:.6f}",
        f"chunk_f1_weighted={chunk_f1_weighted:.6f}",
        f"clip_accuracy={clip_acc:.6f}",
        f"clip_f1_macro={clip_f1_macro:.6f}",
        f"clip_f1_weighted={clip_f1_weighted:.6f}",
        f"confusion_chunk={split_dir / 'confusion_motion_chunked_chunk.csv'}",
        f"class_report_chunk={split_dir / 'class_report_motion_chunked_chunk.json'}",
        f"confusion_clip={split_dir / 'confusion_motion_chunked_clip.csv'}",
        f"class_report_clip={split_dir / 'class_report_motion_chunked_clip.json'}",
    ]
    if args.save_preds:
        lines.extend(
            [
                f"pred_chunks={split_dir / 'predictions_motion_chunked_chunks.csv'}",
                f"pred_clips={split_dir / 'predictions_motion_chunked_clips.csv'}",
            ]
        )

    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[done] report:", out_report)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
