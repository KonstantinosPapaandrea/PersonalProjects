"""
Motion2Music: Prompt model (motion -> text prompt)

This module trains:
1) A genre classifier (from AIST++ filename labels, when available)
2) A style clusterer (unsupervised) to produce consistent adjective sets
and then generates a text prompt from LMA + beat CSVs.

Dependencies: numpy, pandas, scikit-learn, joblib
"""
from __future__ import annotations

import os, re, io
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
import joblib


AIST_GENRE_MAP = {
    "gBR": "break",
    "gPO": "pop",
    "gLO": "lock",
    "gMH": "middle hip-hop",
    "gLH": "LA style hip-hop",
    "gHO": "house",
    "gWA": "waack",
    "gKR": "krump",
    "gJS": "street jazz",
    "gJB": "ballet jazz",
}

AIST_PATTERN = re.compile(
    r"^(g[A-Z]{2})_(s[A-Z]{2})_c([A-Za-z0-9]+)_d([0-9]{2})_m([A-Z]{2}[0-9])_ch([0-9]{2})$"
)

LMA_COLS = ["BODY","EFFORT_WEIGHT_STRONG","EFFORT_TIME_SUDDEN","EFFORT_FLOW_BOUND","SHAPE","SPACE"]


def parse_aist_name(stem: str) -> Optional[Dict[str,str]]:
    m = AIST_PATTERN.match(stem)
    if not m:
        return None
    return {
        "genre_code": m.group(1),
        "situation": m.group(2),
        "camera": m.group(3),
        "dancer": m.group(4),
        "music_id": m.group(5),
        "choreo": m.group(6),
    }


def _robust_bpm_and_cv(beat_times: np.ndarray) -> Tuple[float, float]:
    if beat_times.size < 2:
        return (np.nan, np.nan)
    intervals = np.diff(beat_times)
    # IQR outlier removal
    q1, q3 = np.percentile(intervals, [25, 75])
    iqr = q3 - q1
    lo = q1 - 1.5 * iqr
    hi = q3 + 1.5 * iqr
    iv = intervals[(intervals >= lo) & (intervals <= hi)]
    if iv.size == 0:
        iv = intervals
    med = float(np.median(iv))
    bpm = 60.0 / med if med > 1e-9 else np.nan
    cv = float(np.std(iv) / np.mean(iv)) if np.mean(iv) > 1e-9 else np.nan
    return bpm, cv


def normalize_bpm(bpm: float, lo: float = 80.0, hi: float = 200.0) -> float:
    """Map bpm into a typical EDM/dance range by doubling/halving."""
    if np.isnan(bpm):
        return bpm
    b = float(bpm)
    while b < lo:
        b *= 2.0
    while b > hi:
        b /= 2.0
    return b


def summarize_lma(df_lma: pd.DataFrame) -> Dict[str,float]:
    X = df_lma[LMA_COLS].astype(float).values
    stats: Dict[str,float] = {}
    for i, c in enumerate(LMA_COLS):
        v = X[:, i]
        stats[f"{c}_mean"] = float(np.mean(v))
        stats[f"{c}_std"]  = float(np.std(v))
        stats[f"{c}_p10"]  = float(np.percentile(v, 10))
        stats[f"{c}_p90"]  = float(np.percentile(v, 90))
        if X.shape[0] > 1:
            stats[f"{c}_madiff"] = float(np.mean(np.abs(np.diff(v))))
        else:
            stats[f"{c}_madiff"] = 0.0
    return stats


def summarize_beats(df_beats: pd.DataFrame) -> Dict[str,float]:
    t = df_beats["time_s"].astype(float).values
    bpm, cv = _robust_bpm_and_cv(t)
    bpm_n = normalize_bpm(bpm)
    return {
        "bpm_raw": float(bpm) if not np.isnan(bpm) else np.nan,
        "bpm": float(bpm_n) if not np.isnan(bpm_n) else np.nan,
        "beat_count": float(len(t)),
        "beat_cv": float(cv) if not np.isnan(cv) else np.nan,
    }


def build_feature_row(stem: str, lma_csv: str, beats_csv: str) -> Dict[str, float]:
    df_lma = pd.read_csv(lma_csv)
    df_beats = pd.read_csv(beats_csv)
    row: Dict[str, float] = {}
    row.update(summarize_lma(df_lma))
    row.update(summarize_beats(df_beats))
    meta = parse_aist_name(stem)
    row["has_aist_label"] = 1.0 if meta else 0.0

    # keep labels separately
    return row


def collect_pairs(outputs_dir: str) -> List[Tuple[str,str,str]]:
    """
    Find *_lma.csv and *_beats.csv pairs under outputs_dir (recursive).
    Returns list of (stem, lma_path, beats_path)
    """
    lma_paths = {}
    beats_paths = {}
    for root, _, files in os.walk(outputs_dir):
        for fn in files:
            if fn.endswith("_lma.csv"):
                stem = fn[:-8]
                lma_paths[stem] = os.path.join(root, fn)
            elif fn.endswith("_beats.csv"):
                stem = fn[:-10]
                beats_paths[stem] = os.path.join(root, fn)
    stems = sorted(set(lma_paths) & set(beats_paths))
    return [(s, lma_paths[s], beats_paths[s]) for s in stems]


def make_dataframe(outputs_dir: str) -> pd.DataFrame:
    pairs = collect_pairs(outputs_dir)
    rows = []
    labels = []
    for stem, lma_csv, beats_csv in pairs:
        row = build_feature_row(stem, lma_csv, beats_csv)
        meta = parse_aist_name(stem)
        label = meta["genre_code"] if meta else None
        rows.append({"stem": stem, **row})
        labels.append(label)
    df = pd.DataFrame(rows)
    df["genre_code"] = labels
    return df


def _adjectives_from_centroid(centroid: np.ndarray, feature_names: List[str]) -> List[str]:
    """Turn a centroid vector (in original feature space) into a stable adjective set."""
    f = dict(zip(feature_names, centroid))
    energy = 0.6 * f.get("EFFORT_WEIGHT_STRONG_mean", 0) + 0.4 * f.get("EFFORT_TIME_SUDDEN_mean", 0)
    sudden = f.get("EFFORT_TIME_SUDDEN_mean", 0)
    bound = f.get("EFFORT_FLOW_BOUND_mean", 0)
    space = f.get("SPACE_mean", 0)
    beat_cv = f.get("beat_cv", np.nan)

    words: List[str] = []

    if energy > 0.70:
        words += ["hard-hitting", "high-energy"]
    elif energy > 0.55:
        words += ["driving", "energetic"]
    elif energy > 0.40:
        words += ["steady"]
    else:
        words += ["smooth", "relaxed"]

    if sudden > 0.60:
        words += ["punchy", "staccato"]
    elif sudden < 0.35:
        words += ["legato", "flowing"]

    if bound > 0.60:
        words += ["tight", "controlled"]
    elif bound < 0.35:
        words += ["loose", "free-flowing"]

    if space > 0.60:
        words += ["wide", "spacious"]
    elif space < 0.30:
        words += ["compact"]

    if isinstance(beat_cv, (int, float)) and not np.isnan(beat_cv):
        if beat_cv < 0.12:
            words += ["steady groove", "clear beat"]
        elif beat_cv < 0.25:
            words += ["groovy"]
        else:
            words += ["syncopated", "rhythmically varied"]
    else:
        words += ["clear beat"]

    # de-duplicate while keeping order
    out = []
    seen = set()
    for w in words:
        if w not in seen:
            out.append(w); seen.add(w)
    return out


@dataclass
class PromptModel:
    feature_names: List[str]
    genre_pipeline: Pipeline
    kmeans: KMeans
    cluster_adjectives: Dict[int, List[str]]

    def predict_genre(self, X: pd.DataFrame) -> List[str]:
        return list(self.genre_pipeline.predict(X[self.feature_names]))

    def predict_cluster(self, X: pd.DataFrame) -> np.ndarray:
        return self.kmeans.predict(X[self.feature_names])

    def make_prompt(self, X_row: pd.Series, genre_code: Optional[str] = None) -> str:
        bpm = X_row.get("bpm", np.nan)
        bpm_txt = f"tempo {int(round(bpm))} bpm" if not np.isnan(bpm) else "tempo medium"

        # Build a single-row DataFrame and ensure all expected features exist
        Xdf = X_row.to_frame().T
        for c in self.feature_names:
            if c not in Xdf.columns:
                Xdf[c] = 0.0
        Xdf = Xdf[self.feature_names]

        # genre
        if genre_code is None:
            genre_code = self.genre_pipeline.predict(Xdf)[0]

        genre = AIST_GENRE_MAP.get(str(genre_code), "dance")

        # style adjectives from cluster
        cl = int(self.kmeans.predict(Xdf)[0])
        adj = self.cluster_adjectives.get(cl, [])
        adj_txt = ", ".join(adj) if adj else "driving, clear beat"

        return f"instrumental {genre} dance, {adj_txt}, {bpm_txt}, high quality mix, no vocals"


def train_prompt_model(df: pd.DataFrame, n_clusters: int = 12, random_state: int = 42) -> PromptModel:
    # Use only rows with AIST genre labels to train classifier
    df_lab = df[df["genre_code"].notna()].copy()
    # Feature columns = all numeric columns except identifiers/labels
    ignore = {"stem", "genre_code"}
    feature_names = [c for c in df.columns if c not in ignore and np.issubdtype(df[c].dtype, np.number)]
    # classifier
    genre_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=400,
            random_state=random_state,
            class_weight="balanced_subsample",
            n_jobs=-1
        ))
    ])
    genre_pipe.fit(df_lab[feature_names], df_lab["genre_code"])
    # clusterer (unsupervised on ALL data)
    X_all = df[feature_names].fillna(df[feature_names].median(numeric_only=True))
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init="auto")
    kmeans.fit(X_all)
    # centroid -> adjectives
    centroids = kmeans.cluster_centers_
    cluster_adjs = {i: _adjectives_from_centroid(centroids[i], feature_names) for i in range(n_clusters)}
    return PromptModel(feature_names=feature_names, genre_pipeline=genre_pipe, kmeans=kmeans, cluster_adjectives=cluster_adjs)


def save(model: PromptModel, path: str) -> None:
    joblib.dump(model, path)


def load(path: str) -> PromptModel:
    return joblib.load(path)
