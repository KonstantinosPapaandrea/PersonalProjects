#!/usr/bin/env python
"""
Train Motion2Music prompt model from your existing outputs/*_lma.csv + *_beats.csv.

Usage:
  python train_prompt_model.py --project "C:\...\Motion2Music" --out models/prompt_model.joblib
"""
import argparse, os
import pandas as pd
from m2m_prompt_model import make_dataframe, train_prompt_model, save

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="Path to Motion2Music project root (folder containing outputs/)")
    ap.add_argument("--out", default="models/prompt_model.joblib", help="Output joblib path")
    ap.add_argument("--clusters", type=int, default=12)
    args = ap.parse_args()

    outputs_dir = os.path.join(args.project, "outputs")
    if not os.path.isdir(outputs_dir):
        raise SystemExit(f"outputs/ not found under: {args.project}")

    df = make_dataframe(outputs_dir)
    print(f"[data] sequences={len(df)}  labeled={df['genre_code'].notna().sum()}  cols={df.shape[1]}")
    model = train_prompt_model(df, n_clusters=args.clusters)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    save(model, args.out)
    print(f"[ok] saved -> {args.out}")

if __name__ == "__main__":
    main()
