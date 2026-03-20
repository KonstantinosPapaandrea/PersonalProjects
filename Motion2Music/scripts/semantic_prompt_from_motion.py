#!/usr/bin/env python3
"""
semantic_prompt_from_motion.py

Descriptor-free semantic baseline:
LMA + beat structure -> semantic control vector -> prompt.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

LMA_KEYS = [
    "BODY",
    "EFFORT_WEIGHT_STRONG",
    "EFFORT_TIME_SUDDEN",
    "EFFORT_FLOW_BOUND",
    "SHAPE",
    "SPACE",
]

FEATURE_TO_XCOL = {
    "BODY_mean": "lma_mean_BODY",
    "BODY_std": "lma_std_BODY",
    "EFFORT_WEIGHT_STRONG_mean": "lma_mean_EFFORT_WEIGHT_STRONG",
    "EFFORT_WEIGHT_STRONG_std": "lma_std_EFFORT_WEIGHT_STRONG",
    "EFFORT_TIME_SUDDEN_mean": "lma_mean_EFFORT_TIME_SUDDEN",
    "EFFORT_TIME_SUDDEN_std": "lma_std_EFFORT_TIME_SUDDEN",
    "EFFORT_FLOW_BOUND_mean": "lma_mean_EFFORT_FLOW_BOUND",
    "EFFORT_FLOW_BOUND_std": "lma_std_EFFORT_FLOW_BOUND",
    "SPACE_mean": "lma_mean_SPACE",
    "SPACE_std": "lma_std_SPACE",
}

SCORE_KEYS = [
    "energy_score",
    "heaviness_score",
    "sharpness_score",
    "control_score",
    "expansiveness_score",
    "rhythmic_stability_score",
    "arousal_score",
    "valence_score",
    "dynamic_score",
]

BASE_TAG_LEVELS = {
    "energy_tag": ["low", "medium", "high"],
    "weight_tag": ["light", "medium", "heavy"],
    "flow_tag": ["free", "mixed", "bound-controlled"],
    "attack_tag": ["soft", "mixed", "sharp"],
    "space_tag": ["compact", "medium", "expansive"],
    "rhythm_tag": ["variable", "mixed", "steady"],
    "dynamic_tag": ["flat", "evolving", "highly dynamic"],
}

BASE_TAG_TO_SCORE = {
    "energy_tag": "energy_score",
    "weight_tag": "heaviness_score",
    "flow_tag": "control_score",
    "attack_tag": "sharpness_score",
    "space_tag": "expansiveness_score",
    "rhythm_tag": "rhythmic_stability_score",
    "dynamic_tag": "dynamic_score",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_path(p: str, root: Path) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _find_time_col(df: pd.DataFrame) -> str:
    cols = [str(c).strip() for c in df.columns]
    low = {c.lower(): c for c in cols}
    for k in ("time_s", "time", "seconds", "sec", "timestamp", "beat_time"):
        if k in low:
            return low[k]
    num = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    if len(num) == 1:
        return num[0]
    raise KeyError(f"Could not infer beat-time column from {list(df.columns)}")


def _normalize_bpm(bpm: float, lo: float = 80.0, hi: float = 200.0) -> float:
    if not np.isfinite(bpm):
        return float("nan")
    b = float(bpm)
    if b <= 1e-9:
        return float("nan")
    while b < lo:
        b *= 2.0
    while b > hi:
        b /= 2.0
    return b


def _clip01(x: float) -> float:
    return float(np.clip(float(x), 0.0, 1.0))


def _minmax_norm(v: float, lo: float, hi: float) -> float:
    if not np.isfinite(v) or not np.isfinite(lo) or not np.isfinite(hi):
        return 0.5
    if hi <= lo + 1e-12:
        return 0.5
    return _clip01((float(v) - float(lo)) / (float(hi) - float(lo)))


def _finite_arr(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    return arr[np.isfinite(arr)]


def compute_beat_features(beat_times: np.ndarray) -> dict[str, float]:
    t = _finite_arr(beat_times)
    t = np.unique(t)
    t.sort()

    out = {
        "beat_count": float(len(t)),
        "beat_rate_hz": 0.0,
        "tempo_bpm_raw": 120.0,
        "tempo_bpm": 120.0,
        "ibi_mean_s": 0.5,
        "ibi_std_s": 0.0,
        "rhythm_cv": 0.0,
    }
    if len(t) < 2:
        return out

    ibi = np.diff(t)
    ibi = ibi[ibi > 1e-6]
    if ibi.size == 0:
        return out

    ibi_mean = float(np.mean(ibi))
    ibi_std = float(np.std(ibi))
    bpm_raw = float(60.0 / max(np.median(ibi), 1e-9))
    bpm = float(_normalize_bpm(bpm_raw))
    if not np.isfinite(bpm):
        bpm = 120.0

    duration = float(max(t[-1] - t[0], 1e-9))
    beat_rate_hz = float(len(t) / duration) if duration > 0 else 0.0

    out.update(
        {
            "beat_rate_hz": beat_rate_hz,
            "tempo_bpm_raw": bpm_raw,
            "tempo_bpm": bpm,
            "ibi_mean_s": ibi_mean,
            "ibi_std_s": ibi_std,
            "rhythm_cv": float(ibi_std / (ibi_mean + 1e-8)),
        }
    )
    return out


def _lma_stat(df: pd.DataFrame, col: str) -> np.ndarray:
    if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
        return np.array([], dtype=float)
    return _finite_arr(df[col].to_numpy(dtype=float))


def compute_lma_features(lma_df: pd.DataFrame) -> dict[str, float]:
    feats: dict[str, float] = {}
    for name in LMA_KEYS:
        arr = _lma_stat(lma_df, name)
        if arr.size == 0:
            feats[f"{name}_mean"] = 0.0
            feats[f"{name}_std"] = 0.0
            feats[f"{name}_min"] = 0.0
            feats[f"{name}_max"] = 0.0
            feats[f"{name}_range"] = 0.0
            continue
        mn = float(np.min(arr))
        mx = float(np.max(arr))
        feats[f"{name}_mean"] = float(np.mean(arr))
        feats[f"{name}_std"] = float(np.std(arr))
        feats[f"{name}_min"] = mn
        feats[f"{name}_max"] = mx
        feats[f"{name}_range"] = float(mx - mn)

    body = _lma_stat(lma_df, "BODY")
    feats["BODY_p90"] = float(np.percentile(body, 90)) if body.size else 0.0
    return feats


def _series_minmax(arr: np.ndarray) -> tuple[float, float] | None:
    a = _finite_arr(arr)
    if a.size < 5:
        return None
    lo = float(np.min(a))
    hi = float(np.max(a))
    if hi <= lo + 1e-12:
        return None
    return (lo, hi)


def load_train_stats(dataset_dir: Path) -> dict[str, tuple[float, float]]:
    xp = dataset_dir / "X_motion.csv"
    if not xp.exists():
        return {}

    xdf = pd.read_csv(xp)
    stats: dict[str, tuple[float, float]] = {}

    for feat_key, col in FEATURE_TO_XCOL.items():
        if col in xdf.columns and pd.api.types.is_numeric_dtype(xdf[col]):
            mm = _series_minmax(xdf[col].to_numpy(dtype=float))
            if mm is not None:
                stats[feat_key] = mm

    if "bpm_motion" in xdf.columns and pd.api.types.is_numeric_dtype(xdf["bpm_motion"]):
        b = xdf["bpm_motion"].to_numpy(dtype=float)
        b_norm = np.array([_normalize_bpm(v) for v in b], dtype=float)
        mm = _series_minmax(b_norm)
        if mm is not None:
            stats["tempo_bpm"] = mm

    if {"ibi_std_s", "ibi_mean_s"}.issubset(set(xdf.columns)):
        if pd.api.types.is_numeric_dtype(xdf["ibi_std_s"]) and pd.api.types.is_numeric_dtype(xdf["ibi_mean_s"]):
            cv = xdf["ibi_std_s"].to_numpy(dtype=float) / (xdf["ibi_mean_s"].to_numpy(dtype=float) + 1e-8)
            mm = _series_minmax(cv)
            if mm is not None:
                stats["rhythm_cv"] = mm

    dyn_cols = [
        "lma_std_BODY",
        "lma_std_EFFORT_WEIGHT_STRONG",
        "lma_std_EFFORT_TIME_SUDDEN",
        "lma_std_EFFORT_FLOW_BOUND",
        "lma_std_SPACE",
    ]
    if all((c in xdf.columns and pd.api.types.is_numeric_dtype(xdf[c])) for c in dyn_cols):
        dyn = (
            0.25 * xdf["lma_std_BODY"].to_numpy(dtype=float)
            + 0.25 * xdf["lma_std_EFFORT_WEIGHT_STRONG"].to_numpy(dtype=float)
            + 0.20 * xdf["lma_std_EFFORT_TIME_SUDDEN"].to_numpy(dtype=float)
            + 0.15 * xdf["lma_std_EFFORT_FLOW_BOUND"].to_numpy(dtype=float)
            + 0.15 * xdf["lma_std_SPACE"].to_numpy(dtype=float)
        )
        mm = _series_minmax(dyn)
        if mm is not None:
            stats["dynamic_score"] = mm

    return stats


def normalize_features(
    features: dict[str, float],
    train_stats: dict[str, tuple[float, float]],
) -> dict[str, float]:
    norm: dict[str, float] = {}

    for k, v in features.items():
        vv = float(v) if np.isfinite(v) else 0.0

        if k == "tempo_bpm":
            if "tempo_bpm" in train_stats:
                lo, hi = train_stats["tempo_bpm"]
                norm["tempo_norm"] = _minmax_norm(vv, lo, hi)
            else:
                norm["tempo_norm"] = _clip01((vv - 80.0) / 120.0)
            continue

        if k == "rhythm_cv":
            if "rhythm_cv" in train_stats:
                lo, hi = train_stats["rhythm_cv"]
                norm["rhythm_variability_norm"] = _minmax_norm(vv, lo, hi)
            else:
                norm["rhythm_variability_norm"] = _clip01(vv)
            continue

        if k in train_stats:
            lo, hi = train_stats[k]
            norm[k] = _minmax_norm(vv, lo, hi)
        elif any(k.endswith(suf) for suf in ("_mean", "_std", "_min", "_max", "_range")):
            norm[k] = _clip01(vv)
        else:
            norm[k] = vv

    needed = [
        "BODY_mean",
        "BODY_std",
        "EFFORT_WEIGHT_STRONG_mean",
        "EFFORT_WEIGHT_STRONG_std",
        "EFFORT_TIME_SUDDEN_mean",
        "EFFORT_TIME_SUDDEN_std",
        "EFFORT_FLOW_BOUND_mean",
        "EFFORT_FLOW_BOUND_std",
        "SPACE_mean",
        "SPACE_std",
        "tempo_norm",
        "rhythm_variability_norm",
    ]
    for k in needed:
        if k not in norm or not np.isfinite(norm[k]):
            norm[k] = 0.0

    return norm


def compute_semantic_scores(features: dict[str, float]) -> dict[str, float]:
    f = features

    body_mean = f["BODY_mean"]
    weight_mean = f["EFFORT_WEIGHT_STRONG_mean"]
    sudden_mean = f["EFFORT_TIME_SUDDEN_mean"]
    flow_mean = f["EFFORT_FLOW_BOUND_mean"]
    space_mean = f["SPACE_mean"]

    body_std = f["BODY_std"]
    weight_std = f["EFFORT_WEIGHT_STRONG_std"]
    sudden_std = f["EFFORT_TIME_SUDDEN_std"]
    flow_std = f["EFFORT_FLOW_BOUND_std"]
    space_std = f["SPACE_std"]

    tempo_norm = f["tempo_norm"]
    rhythm_variability_norm = f["rhythm_variability_norm"]
    rhythm_stability_score_proxy = _clip01(1.0 - rhythm_variability_norm)

    energy_score = (
        0.35 * body_mean
        + 0.25 * weight_mean
        + 0.20 * sudden_mean
        + 0.10 * space_mean
        + 0.10 * tempo_norm
    )

    heaviness_score = (
        0.55 * weight_mean
        + 0.20 * body_mean
        + 0.15 * flow_mean
        + 0.10 * space_mean
    )

    sharpness_score = (
        0.60 * sudden_mean
        + 0.20 * sudden_std
        + 0.10 * rhythm_variability_norm
        + 0.10 * tempo_norm
    )

    control_score = (
        0.70 * flow_mean
        + 0.15 * flow_std
        + 0.15 * rhythm_stability_score_proxy
    )

    expansiveness_score = (
        0.70 * space_mean
        + 0.20 * body_mean
        + 0.10 * space_std
    )

    rhythmic_stability_score = _clip01(1.0 - rhythm_variability_norm)

    arousal_score = (
        0.35 * energy_score
        + 0.30 * sharpness_score
        + 0.20 * heaviness_score
        + 0.15 * tempo_norm
    )

    valence_score = (
        0.40 * expansiveness_score
        + 0.20 * (1.0 - control_score)
        + 0.20 * rhythmic_stability_score
        + 0.20 * (1.0 - heaviness_score)
    )

    dynamic_score = (
        0.25 * body_std
        + 0.25 * weight_std
        + 0.20 * sudden_std
        + 0.15 * flow_std
        + 0.15 * space_std
    )

    scores = {
        "energy_score": _clip01(energy_score),
        "heaviness_score": _clip01(heaviness_score),
        "sharpness_score": _clip01(sharpness_score),
        "control_score": _clip01(control_score),
        "expansiveness_score": _clip01(expansiveness_score),
        "rhythmic_stability_score": _clip01(rhythmic_stability_score),
        "arousal_score": _clip01(arousal_score),
        "valence_score": _clip01(valence_score),
        "dynamic_score": _clip01(dynamic_score),
    }
    return scores


def build_x_motion_features(lma_features: dict[str, float], beat_features: dict[str, float]) -> dict[str, float]:
    return {
        "beat_count": float(beat_features.get("beat_count", 0.0)),
        "beat_rate_hz": float(beat_features.get("beat_rate_hz", 0.0)),
        "bpm_motion": float(beat_features.get("tempo_bpm", 120.0)),
        "ibi_mean_s": float(beat_features.get("ibi_mean_s", 0.5)),
        "ibi_std_s": float(beat_features.get("ibi_std_s", 0.0)),
        "lma_body_p90": float(lma_features.get("BODY_p90", 0.0)),
        "lma_mean_BODY": float(lma_features.get("BODY_mean", 0.0)),
        "lma_mean_EFFORT_FLOW_BOUND": float(lma_features.get("EFFORT_FLOW_BOUND_mean", 0.0)),
        "lma_mean_EFFORT_TIME_SUDDEN": float(lma_features.get("EFFORT_TIME_SUDDEN_mean", 0.0)),
        "lma_mean_EFFORT_WEIGHT_STRONG": float(lma_features.get("EFFORT_WEIGHT_STRONG_mean", 0.0)),
        "lma_mean_SHAPE": float(lma_features.get("SHAPE_mean", 0.0)),
        "lma_mean_SPACE": float(lma_features.get("SPACE_mean", 0.0)),
        "lma_std_BODY": float(lma_features.get("BODY_std", 0.0)),
        "lma_std_EFFORT_FLOW_BOUND": float(lma_features.get("EFFORT_FLOW_BOUND_std", 0.0)),
        "lma_std_EFFORT_TIME_SUDDEN": float(lma_features.get("EFFORT_TIME_SUDDEN_std", 0.0)),
        "lma_std_EFFORT_WEIGHT_STRONG": float(lma_features.get("EFFORT_WEIGHT_STRONG_std", 0.0)),
        "lma_std_SHAPE": float(lma_features.get("SHAPE_std", 0.0)),
        "lma_std_SPACE": float(lma_features.get("SPACE_std", 0.0)),
    }


def _predict_scores_from_bundle(bundle: dict, x_motion: dict[str, float]) -> dict[str, float]:
    if "model" not in bundle:
        raise KeyError("Model bundle missing key 'model'.")
    x_cols = list(bundle.get("x_cols", []))
    if not x_cols:
        raise KeyError("Model bundle missing x_cols.")

    target_cols = list(bundle.get("target_cols", []))
    if not target_cols:
        raise KeyError("Model bundle missing target_cols.")

    x = np.zeros((1, len(x_cols)), dtype=np.float32)
    for i, c in enumerate(x_cols):
        x[0, i] = float(x_motion.get(c, 0.0))

    yhat = bundle["model"].predict(x)[0]
    out = {k: 0.0 for k in SCORE_KEYS}
    for c, v in zip(target_cols, yhat):
        if c in out:
            out[c] = _clip01(float(v))
    return out


def apply_ema_scores(
    current_scores: dict[str, float],
    prev_scores: dict[str, float] | None,
    alpha: float,
) -> dict[str, float]:
    a = float(np.clip(alpha, 0.0, 1.0))
    if prev_scores is None:
        return {k: float(v) for k, v in current_scores.items()}
    out: dict[str, float] = {}
    for k in SCORE_KEYS:
        c = float(current_scores.get(k, 0.0))
        p = float(prev_scores.get(k, c))
        out[k] = _clip01(a * c + (1.0 - a) * p)
    return out


def _apply_dance_phrase(tags: dict[str, str]) -> None:
    if tags["energy_tag"] == "high" and tags["attack_tag"] == "sharp":
        tags["dance_phrase"] = "explosive athletic choreography"
    elif tags["flow_tag"] == "free" and tags["space_tag"] == "expansive":
        tags["dance_phrase"] = "fluid expressive dance"
    elif tags["weight_tag"] == "heavy":
        tags["dance_phrase"] = "grounded powerful movement"
    else:
        tags["dance_phrase"] = "rhythmic contemporary dance"


def apply_tag_hysteresis(
    scores: dict[str, float],
    tags: dict[str, str],
    prev_tags: dict[str, str] | None,
    margin: float,
) -> dict[str, str]:
    if prev_tags is None:
        return tags

    m = float(max(0.0, margin))
    out = dict(tags)
    t1 = 0.33
    t2 = 0.66
    for tag_name, levels in BASE_TAG_LEVELS.items():
        prev = str(prev_tags.get(tag_name, ""))
        if prev not in levels:
            continue
        prev_idx = levels.index(prev)
        score_key = BASE_TAG_TO_SCORE[tag_name]
        s = float(scores.get(score_key, 0.0))

        if prev_idx == 0:
            if s > (t2 + m):
                idx = 2
            elif s > (t1 + m):
                idx = 1
            else:
                idx = 0
        elif prev_idx == 1:
            if s < (t1 - m):
                idx = 0
            elif s > (t2 + m):
                idx = 2
            else:
                idx = 1
        else:
            if s < (t1 - m):
                idx = 0
            elif s < (t2 - m):
                idx = 1
            else:
                idx = 2

        out[tag_name] = levels[idx]

    _apply_dance_phrase(out)
    return out


def _tri_tag(v: float, low: str, mid: str, high: str) -> str:
    if v < 0.33:
        return low
    if v < 0.66:
        return mid
    return high


def scores_to_tags(scores: dict[str, float]) -> dict[str, str]:
    tags = {
        "energy_tag": _tri_tag(scores["energy_score"], "low", "medium", "high"),
        "weight_tag": _tri_tag(scores["heaviness_score"], "light", "medium", "heavy"),
        "flow_tag": _tri_tag(scores["control_score"], "free", "mixed", "bound-controlled"),
        "attack_tag": _tri_tag(scores["sharpness_score"], "soft", "mixed", "sharp"),
        "space_tag": _tri_tag(scores["expansiveness_score"], "compact", "medium", "expansive"),
        "rhythm_tag": _tri_tag(scores["rhythmic_stability_score"], "variable", "mixed", "steady"),
        "dynamic_tag": _tri_tag(scores["dynamic_score"], "flat", "evolving", "highly dynamic"),
    }

    arousal = scores["arousal_score"]
    valence = scores["valence_score"]
    sharpness = scores["sharpness_score"]
    heaviness = scores["heaviness_score"]
    control = scores["control_score"]
    energy = scores["energy_score"]
    expansiveness = scores["expansiveness_score"]

    if arousal < 0.35 and valence > 0.55:
        mood_tag = "calm"
    elif arousal < 0.35 and valence <= 0.55:
        mood_tag = "cinematic"
    elif arousal >= 0.35 and arousal < 0.65 and valence > 0.60:
        mood_tag = "joyful"
    elif arousal >= 0.65 and sharpness > 0.60 and heaviness > 0.55:
        mood_tag = "aggressive"
    elif control > 0.65 and valence < 0.50:
        mood_tag = "tense"
    else:
        mood_tag = "cinematic"
    tags["mood_tag"] = mood_tag

    if energy > 0.70 and sharpness > 0.65:
        style_tag = "electronic"
    elif heaviness > 0.65 and sharpness > 0.55:
        style_tag = "percussion-driven"
    elif expansiveness > 0.65 and control < 0.55:
        style_tag = "cinematic"
    elif energy < 0.40 and control < 0.45:
        style_tag = "ambient"
    else:
        style_tag = "hybrid"
    tags["style_tag"] = style_tag

    _apply_dance_phrase(tags)

    return tags


def generate_prompt(tags: dict[str, str], bpm: float) -> str:
    energy_phrase = {
        "low": "soft restrained",
        "medium": "moderately energetic",
        "high": "high-energy driving",
    }[tags["energy_tag"]]

    weight_phrase = {
        "light": "light articulated motion",
        "medium": "grounded rhythmic motion",
        "heavy": "powerful grounded impact",
    }[tags["weight_tag"]]

    attack_phrase = {
        "soft": "smooth gentle attacks",
        "mixed": "balanced flowing motion with clear accents",
        "sharp": "sharp staccato accents",
    }[tags["attack_tag"]]

    flow_phrase = {
        "free": "free-flowing texture",
        "mixed": "controlled flow with expressive release",
        "bound-controlled": "tight controlled tension",
    }[tags["flow_tag"]]

    space_phrase = {
        "compact": "intimate compact atmosphere",
        "medium": "balanced spatial presence",
        "expansive": "wide expansive atmosphere",
    }[tags["space_tag"]]

    rhythm_phrase = {
        "steady": "steady pulse",
        "mixed": "evolving rhythmic motion",
        "variable": "shifting rhythmic accents",
    }[tags["rhythm_tag"]]

    mood_phrase = {
        "calm": "calm reflective mood",
        "joyful": "uplifting confident mood",
        "tense": "tense dramatic mood",
        "aggressive": "aggressive powerful mood",
        "cinematic": "cinematic expressive mood",
    }[tags["mood_tag"]]

    dynamic_phrase = {
        "flat": "consistent intensity throughout",
        "evolving": "gradually evolving intensity",
        "highly dynamic": "strong shifts in intensity and phrasing",
    }[tags["dynamic_tag"]]

    bpm_round = int(round(float(bpm))) if np.isfinite(bpm) else 120
    style_tag = tags["style_tag"]
    dance_phrase = tags["dance_phrase"]

    prompt = (
        f"{energy_phrase} {style_tag} track, "
        f"{weight_phrase}, {attack_phrase}, {flow_phrase}, {rhythm_phrase}, "
        f"{dynamic_phrase}, {mood_phrase}, {space_phrase}, "
        f"at {bpm_round} BPM, suitable for {dance_phrase}, no vocals"
    )
    return prompt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lma-csv", required=True)
    ap.add_argument("--beats-csv", required=True)
    ap.add_argument("--dataset-dir", default="outputs/m2m_train")
    ap.add_argument("--semantic-model", default="", help="Optional trained semantic model bundle (.joblib).")
    ap.add_argument("--ema-alpha", type=float, default=1.0, help="Score smoothing factor in [0,1]; 1=no smoothing.")
    ap.add_argument("--hysteresis-margin", type=float, default=0.05, help="Tag-switch margin for base semantic tags.")
    ap.add_argument("--prev-state-json", default="", help="Optional previous state json for smoothing/hysteresis.")
    ap.add_argument("--write-state-json", default="", help="Write current state json for next-step chaining.")
    ap.add_argument("--write-prompt", default="")
    ap.add_argument("--write-semantics", default="")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    root = project_root()
    lma_csv = _resolve_path(args.lma_csv, root)
    beats_csv = _resolve_path(args.beats_csv, root)
    dataset_dir = _resolve_path(args.dataset_dir, root)
    semantic_model_path = _resolve_path(args.semantic_model, root) if args.semantic_model else None
    prev_state_path = _resolve_path(args.prev_state_json, root) if args.prev_state_json else None
    write_state_path = _resolve_path(args.write_state_json, root) if args.write_state_json else None

    if not lma_csv.exists():
        raise SystemExit(f"Missing LMA CSV: {lma_csv}")
    if not beats_csv.exists():
        raise SystemExit(f"Missing beats CSV: {beats_csv}")
    if semantic_model_path is not None and not semantic_model_path.exists():
        raise SystemExit(f"Missing semantic model: {semantic_model_path}")
    if prev_state_path is not None and not prev_state_path.exists():
        raise SystemExit(f"Missing prev state json: {prev_state_path}")

    lma_df = pd.read_csv(lma_csv)
    beats_df = pd.read_csv(beats_csv)
    tcol = _find_time_col(beats_df)

    beat_features = compute_beat_features(beats_df[tcol].to_numpy(dtype=float))
    lma_features = compute_lma_features(lma_df)
    x_motion = build_x_motion_features(lma_features=lma_features, beat_features=beat_features)

    raw_features = {
        **lma_features,
        "tempo_bpm": float(beat_features["tempo_bpm"]),
        "rhythm_cv": float(beat_features["rhythm_cv"]),
    }

    prev_scores: dict[str, float] | None = None
    prev_tags: dict[str, str] | None = None
    if prev_state_path is not None:
        prev_obj = json.loads(prev_state_path.read_text(encoding="utf-8"))
        if isinstance(prev_obj, dict):
            if isinstance(prev_obj.get("scores"), dict):
                prev_scores = {}
                for k, v in prev_obj["scores"].items():
                    try:
                        vv = float(v)
                    except Exception:
                        continue
                    if np.isfinite(vv):
                        prev_scores[k] = vv
            if isinstance(prev_obj.get("tags"), dict):
                prev_tags = {k: str(v) for k, v in prev_obj["tags"].items()}

    score_source = "rules"
    model_info: dict[str, str] = {}
    train_stats = load_train_stats(dataset_dir)
    normalized = normalize_features(raw_features, train_stats)
    if semantic_model_path is not None:
        bundle = joblib.load(semantic_model_path)
        btype = str(bundle.get("bundle_type", ""))
        if btype != "semantic_motion_model_v1":
            raise SystemExit(f"Unsupported semantic model bundle_type='{btype}'")
        scores_raw = _predict_scores_from_bundle(bundle, x_motion=x_motion)
        score_source = "model"
        model_info = {
            "model_path": str(semantic_model_path),
            "bundle_type": btype,
            "model_name": str(bundle.get("model_name", "")),
        }
    else:
        scores_raw = compute_semantic_scores(normalized)

    scores = apply_ema_scores(scores_raw, prev_scores=prev_scores, alpha=float(args.ema_alpha))
    tags = scores_to_tags(scores)
    tags = apply_tag_hysteresis(scores, tags, prev_tags=prev_tags, margin=float(args.hysteresis_margin))
    prompt = generate_prompt(tags, beat_features["tempo_bpm"])

    state = {
        "scores": {k: float(scores[k]) for k in SCORE_KEYS},
        "tags": tags,
    }

    semantics = {
        "beat_features": beat_features,
        "raw_features": raw_features,
        "x_motion_features": x_motion,
        "normalized_features": normalized,
        "scores_raw": scores_raw,
        "scores": scores,
        "tags": tags,
        "score_source": score_source,
        "consistency": {
            "ema_alpha": float(args.ema_alpha),
            "hysteresis_margin": float(args.hysteresis_margin),
            "used_prev_state": bool(prev_state_path is not None),
        },
        "model_info": model_info,
        "state": state,
        "prompt": prompt,
    }

    print("[semantics]")
    print(json.dumps(semantics, indent=2))
    print("\n[prompt]")
    print(prompt)

    if args.write_prompt:
        out = _resolve_path(args.write_prompt, root)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(prompt + "\n", encoding="utf-8")
        print(f"[wrote] {out}")

    if args.write_semantics:
        out = _resolve_path(args.write_semantics, root)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(semantics, indent=2), encoding="utf-8")
        print(f"[wrote] {out}")

    if write_state_path is not None:
        write_state_path.parent.mkdir(parents=True, exist_ok=True)
        write_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"[wrote] {write_state_path}")

    if args.debug:
        print(f"[debug] lma_csv={lma_csv}")
        print(f"[debug] beats_csv={beats_csv}")
        print(f"[debug] dataset_dir={dataset_dir}")
        print(f"[debug] train_stats_keys={sorted(list(train_stats.keys()))}")
        if semantic_model_path is not None:
            print(f"[debug] semantic_model={semantic_model_path}")
        if prev_state_path is not None:
            print(f"[debug] prev_state={prev_state_path}")


if __name__ == "__main__":
    main()
