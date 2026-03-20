#!/usr/bin/env python3
"""
eval_clap_genre_split.py

Evaluate genre prediction on an existing CLAP genre split:
- CLAP embeddings -> genre
- Motion features (X_motion) -> genre (baseline)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def _load_npz(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z = np.load(path, allow_pickle=True)
    ids = np.array([str(x) for x in z["ids"]], dtype=object)
    emb = np.asarray(z["emb"], dtype=np.float32)
    genre = np.array([str(x) for x in z["genre"]], dtype=object)
    return ids, emb, genre


def _fit_eval_classifier(xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray, yte: np.ndarray, seed: int) -> dict:
    clf = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=5000, random_state=int(seed))),
        ]
    )
    clf.fit(xtr, ytr)
    pred = clf.predict(xte)
    return {
        "accuracy": float(accuracy_score(yte, pred)),
        "f1_macro": float(f1_score(yte, pred, average="macro")),
        "f1_weighted": float(f1_score(yte, pred, average="weighted")),
        "pred": pred,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split-dir", required=True)
    ap.add_argument("--dataset-dir", default="outputs/m2m_train", help="Needed for motion baseline lookup.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-report", default="")
    ap.add_argument("--save-preds", action="store_true")
    args = ap.parse_args()

    split_dir = Path(args.split_dir)
    dataset_dir = Path(args.dataset_dir)
    train_npz = split_dir / "clap_genre_train.npz"
    test_npz = split_dir / "clap_genre_test.npz"
    if not train_npz.exists() or not test_npz.exists():
        raise FileNotFoundError("split-dir must contain clap_genre_train.npz and clap_genre_test.npz")

    out_report = Path(args.out_report) if args.out_report else (split_dir / "eval_report.txt")

    ids_tr, emb_tr, ytr = _load_npz(train_npz)
    ids_te, emb_te, yte = _load_npz(test_npz)
    classes = sorted(np.unique(np.concatenate([ytr, yte])).tolist())

    # CLAP model
    clap_eval = _fit_eval_classifier(emb_tr, ytr, emb_te, yte, seed=int(args.seed))
    clap_pred = clap_eval["pred"]

    # Motion baseline on same split
    mp = dataset_dir / "meta.csv"
    xp = dataset_dir / "X_motion.csv"
    motion_eval = None
    motion_pred = None
    if mp.exists() and xp.exists():
        meta = pd.read_csv(mp)
        xdf = pd.read_csv(xp)
        if len(meta) == len(xdf):
            id2i = {str(cid): i for i, cid in enumerate(meta["clip_id"].astype(str).to_list())}
            tr_idx = np.array([id2i.get(cid, -1) for cid in ids_tr], dtype=int)
            te_idx = np.array([id2i.get(cid, -1) for cid in ids_te], dtype=int)
            keep_tr = tr_idx >= 0
            keep_te = te_idx >= 0
            x_num = xdf.apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)
            xtr_m = x_num[tr_idx[keep_tr]]
            ytr_m = ytr[keep_tr]
            xte_m = x_num[te_idx[keep_te]]
            yte_m = yte[keep_te]
            if len(xtr_m) > 0 and len(xte_m) > 0:
                motion_eval = _fit_eval_classifier(xtr_m, ytr_m, xte_m, yte_m, seed=int(args.seed))
                motion_pred = motion_eval["pred"]
                # Align for report consistency when some ids are missing.
                if np.any(~keep_te):
                    filled = np.array(["<missing>"] * len(yte), dtype=object)
                    filled[keep_te] = motion_pred
                    motion_pred = filled

    # Save confusion matrices
    cm_clap = confusion_matrix(yte, clap_pred, labels=classes)
    pd.DataFrame(cm_clap, index=classes, columns=classes).to_csv(split_dir / "confusion_clap.csv")
    if motion_pred is not None:
        yte_motion = yte.copy()
        keep = motion_pred != "<missing>"
        cm_motion = confusion_matrix(yte_motion[keep], motion_pred[keep], labels=classes)
        pd.DataFrame(cm_motion, index=classes, columns=classes).to_csv(split_dir / "confusion_motion.csv")

    # Save per-class metrics (CLAP)
    rep_clap = classification_report(yte, clap_pred, output_dict=True, zero_division=0)
    (split_dir / "class_report_clap.json").write_text(json.dumps(rep_clap, indent=2), encoding="utf-8")
    if motion_pred is not None:
        keep = motion_pred != "<missing>"
        rep_motion = classification_report(yte[keep], motion_pred[keep], output_dict=True, zero_division=0)
        (split_dir / "class_report_motion.json").write_text(json.dumps(rep_motion, indent=2), encoding="utf-8")

    if args.save_preds:
        pred_df = pd.DataFrame(
            {
                "clip_id": ids_te,
                "genre_true": yte,
                "genre_pred_clap": clap_pred,
                "genre_pred_motion": motion_pred if motion_pred is not None else [""] * len(yte),
            }
        )
        pred_df.to_csv(split_dir / "predictions_test.csv", index=False)

    lines = [
        f"split_dir={split_dir}",
        f"train_rows={len(ytr)}",
        f"test_rows={len(yte)}",
        f"num_genres={len(classes)}",
        f"genres={classes}",
        f"train_genre_counts={pd.Series(ytr).value_counts().to_dict()}",
        f"test_genre_counts={pd.Series(yte).value_counts().to_dict()}",
        f"seed={int(args.seed)}",
        f"clap_accuracy={clap_eval['accuracy']:.6f}",
        f"clap_f1_macro={clap_eval['f1_macro']:.6f}",
        f"clap_f1_weighted={clap_eval['f1_weighted']:.6f}",
    ]
    if motion_eval is not None:
        lines.extend(
            [
                f"motion_accuracy={motion_eval['accuracy']:.6f}",
                f"motion_f1_macro={motion_eval['f1_macro']:.6f}",
                f"motion_f1_weighted={motion_eval['f1_weighted']:.6f}",
            ]
        )
    else:
        lines.append("motion_baseline=unavailable")

    lines.extend(
        [
            f"confusion_clap={split_dir / 'confusion_clap.csv'}",
            f"class_report_clap={split_dir / 'class_report_clap.json'}",
        ]
    )
    if motion_eval is not None:
        lines.extend(
            [
                f"confusion_motion={split_dir / 'confusion_motion.csv'}",
                f"class_report_motion={split_dir / 'class_report_motion.json'}",
            ]
        )
    if args.save_preds:
        lines.append(f"predictions_test={split_dir / 'predictions_test.csv'}")

    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[done] report:", out_report)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
