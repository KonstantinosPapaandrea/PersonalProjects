#!/usr/bin/env python
"""
Generate a prompt from a *_lma.csv + *_beats.csv using a trained prompt_model.joblib.

Usage:
  python infer_prompt.py --model models/prompt_model.joblib --lma path/to/file_lma.csv --beats path/to/file_beats.csv
"""
import argparse
import pandas as pd
from m2m_prompt_model import summarize_lma, summarize_beats, load

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--lma", required=True)
    ap.add_argument("--beats", required=True)
    args = ap.parse_args()

    model = load(args.model)
    df_lma = pd.read_csv(args.lma)
    df_beats = pd.read_csv(args.beats)

    row = {}
    row.update(summarize_lma(df_lma))
    row.update(summarize_beats(df_beats))
    X_row = pd.Series(row)
    prompt = model.make_prompt(X_row)
    print(prompt)

if __name__ == "__main__":
    main()
