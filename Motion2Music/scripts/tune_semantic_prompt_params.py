#!/usr/bin/env python3
"""
tune_semantic_prompt_params.py

Search semantic prompt parameters using validation-only optimization:
- motion features -> semantic scores -> tags -> prompt text
- CLAP(text prompt) cosine CLAP(audio embedding) as quality signal
- optional tag-switch penalty for temporal consistency

Outputs:
- trials CSV
- best params JSON
- text report (baseline vs tuned on val/test)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

import semantic_prompt_from_motion as sem


BASE_SCORE_KEYS = [
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

BASE_TAG_KEYS = [
    "energy_tag",
    "weight_tag",
    "flow_tag",
    "attack_tag",
    "space_tag",
    "rhythm_tag",
    "dynamic_tag",
]

BASE_WEIGHTS = {
    "w_energy": np.array([0.35, 0.25, 0.20, 0.10, 0.10], dtype=np.float64),  # body, weight, sudden, space, tempo
    "w_heavy": np.array([0.55, 0.20, 0.15, 0.10], dtype=np.float64),  # weight, body, flow, space
    "w_sharp": np.array([0.60, 0.20, 0.10, 0.10], dtype=np.float64),  # sudden_mean, sudden_std, rhythm_var, tempo
    "w_control": np.array([0.70, 0.15, 0.15], dtype=np.float64),  # flow_mean, flow_std, rhythm_stability
    "w_space": np.array([0.70, 0.20, 0.10], dtype=np.float64),  # space_mean, body_mean, space_std
    "w_arousal": np.array([0.35, 0.30, 0.20, 0.15], dtype=np.float64),  # energy, sharp, heavy, tempo
    "w_valence": np.array([0.40, 0.20, 0.20, 0.20], dtype=np.float64),  # space, (1-control), rhythm_stability, (1-heavy)
    "w_dynamic": np.array([0.25, 0.25, 0.20, 0.15, 0.15], dtype=np.float64),  # body_std, weight_std, sudden_std, flow_std, space_std
}


def _clip01(v: float | np.ndarray) -> float | np.ndarray:
    return np.clip(v, 0.0, 1.0)


def _parse_list(text: str) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _sample_weights(base: np.ndarray, rng: np.random.RandomState, sigma: float) -> np.ndarray:
    # Positive multiplicative noise around base, then normalize.
    w = np.asarray(base, dtype=np.float64) * np.exp(rng.normal(0.0, sigma, size=base.shape[0]))
    w = np.maximum(w, 1e-8)
    return w / np.sum(w)


def _sample_params(rng: np.random.RandomState) -> dict[str, Any]:
    sigma = float(rng.uniform(0.05, 0.45))
    t1 = float(rng.uniform(0.25, 0.40))
    t2 = float(rng.uniform(0.55, 0.78))
    if t2 <= t1 + 0.12:
        t2 = min(0.85, t1 + 0.12)

    return {
        "sigma": sigma,
        "t1": t1,
        "t2": t2,
        "ema_alpha": float(rng.uniform(0.75, 1.00)),
        "hysteresis_margin": float(rng.uniform(0.00, 0.12)),
        "w_energy": _sample_weights(BASE_WEIGHTS["w_energy"], rng, sigma),
        "w_heavy": _sample_weights(BASE_WEIGHTS["w_heavy"], rng, sigma),
        "w_sharp": _sample_weights(BASE_WEIGHTS["w_sharp"], rng, sigma),
        "w_control": _sample_weights(BASE_WEIGHTS["w_control"], rng, sigma),
        "w_space": _sample_weights(BASE_WEIGHTS["w_space"], rng, sigma),
        "w_arousal": _sample_weights(BASE_WEIGHTS["w_arousal"], rng, sigma),
        "w_valence": _sample_weights(BASE_WEIGHTS["w_valence"], rng, sigma),
        "w_dynamic": _sample_weights(BASE_WEIGHTS["w_dynamic"], rng, sigma),
    }


def _default_params() -> dict[str, Any]:
    return {
        "sigma": 0.0,
        "t1": 0.33,
        "t2": 0.66,
        "ema_alpha": 1.0,
        "hysteresis_margin": 0.05,
        "w_energy": BASE_WEIGHTS["w_energy"].copy(),
        "w_heavy": BASE_WEIGHTS["w_heavy"].copy(),
        "w_sharp": BASE_WEIGHTS["w_sharp"].copy(),
        "w_control": BASE_WEIGHTS["w_control"].copy(),
        "w_space": BASE_WEIGHTS["w_space"].copy(),
        "w_arousal": BASE_WEIGHTS["w_arousal"].copy(),
        "w_valence": BASE_WEIGHTS["w_valence"].copy(),
        "w_dynamic": BASE_WEIGHTS["w_dynamic"].copy(),
    }


def _track_root(stem: str) -> tuple[str, int]:
    m = re.search(r"_ch(\d+)$", stem)
    if not m:
        return stem, -1
    ch = int(m.group(1))
    root = stem[: m.start()]
    return root, ch


def _minmax_stats(arr: np.ndarray, lo_fallback: float, hi_fallback: float) -> tuple[float, float]:
    a = np.asarray(arr, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size < 5:
        return float(lo_fallback), float(hi_fallback)
    lo = float(np.min(a))
    hi = float(np.max(a))
    if hi <= lo + 1e-12:
        return float(lo_fallback), float(hi_fallback)
    return lo, hi


def _minmax_norm(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
    if hi <= lo + 1e-12:
        return np.full_like(v, 0.5, dtype=np.float64)
    return _clip01((v - lo) / (hi - lo))


def _build_norm_features(xdf: pd.DataFrame, train_idx: np.ndarray) -> dict[str, np.ndarray]:
    def col(name: str) -> np.ndarray:
        return xdf[name].to_numpy(dtype=np.float64) if name in xdf.columns else np.zeros(len(xdf), dtype=np.float64)

    raw = {
        "BODY_mean": col("lma_mean_BODY"),
        "BODY_std": col("lma_std_BODY"),
        "EFFORT_WEIGHT_STRONG_mean": col("lma_mean_EFFORT_WEIGHT_STRONG"),
        "EFFORT_WEIGHT_STRONG_std": col("lma_std_EFFORT_WEIGHT_STRONG"),
        "EFFORT_TIME_SUDDEN_mean": col("lma_mean_EFFORT_TIME_SUDDEN"),
        "EFFORT_TIME_SUDDEN_std": col("lma_std_EFFORT_TIME_SUDDEN"),
        "EFFORT_FLOW_BOUND_mean": col("lma_mean_EFFORT_FLOW_BOUND"),
        "EFFORT_FLOW_BOUND_std": col("lma_std_EFFORT_FLOW_BOUND"),
        "SPACE_mean": col("lma_mean_SPACE"),
        "SPACE_std": col("lma_std_SPACE"),
    }

    bpm_raw = col("bpm_motion")
    tempo_bpm = np.array([sem._normalize_bpm(v) for v in bpm_raw], dtype=np.float64)
    ibi_mean = col("ibi_mean_s")
    ibi_std = col("ibi_std_s")
    rhythm_cv = ibi_std / (ibi_mean + 1e-8)

    norm: dict[str, np.ndarray] = {}
    for k, arr in raw.items():
        lo, hi = _minmax_stats(arr[train_idx], 0.0, 1.0)
        norm[k] = _minmax_norm(arr, lo, hi)

    tlo, thi = _minmax_stats(tempo_bpm[train_idx], 80.0, 200.0)
    norm["tempo_norm"] = _minmax_norm(tempo_bpm, tlo, thi)
    rlo, rhi = _minmax_stats(rhythm_cv[train_idx], 0.0, 0.5)
    norm["rhythm_variability_norm"] = _minmax_norm(rhythm_cv, rlo, rhi)

    out = {
        **norm,
        "tempo_bpm": tempo_bpm,
    }
    return out


def _compute_score_matrix(feat: dict[str, np.ndarray], p: dict[str, Any]) -> np.ndarray:
    bm = feat["BODY_mean"]
    wm = feat["EFFORT_WEIGHT_STRONG_mean"]
    sm = feat["EFFORT_TIME_SUDDEN_mean"]
    fm = feat["EFFORT_FLOW_BOUND_mean"]
    xm = feat["SPACE_mean"]

    bs = feat["BODY_std"]
    ws = feat["EFFORT_WEIGHT_STRONG_std"]
    ss = feat["EFFORT_TIME_SUDDEN_std"]
    fs = feat["EFFORT_FLOW_BOUND_std"]
    xs = feat["SPACE_std"]

    tempo = feat["tempo_norm"]
    rvar = feat["rhythm_variability_norm"]
    rstab = _clip01(1.0 - rvar)

    w = p
    energy = (
        w["w_energy"][0] * bm
        + w["w_energy"][1] * wm
        + w["w_energy"][2] * sm
        + w["w_energy"][3] * xm
        + w["w_energy"][4] * tempo
    )
    heavy = (
        w["w_heavy"][0] * wm
        + w["w_heavy"][1] * bm
        + w["w_heavy"][2] * fm
        + w["w_heavy"][3] * xm
    )
    sharp = (
        w["w_sharp"][0] * sm
        + w["w_sharp"][1] * ss
        + w["w_sharp"][2] * rvar
        + w["w_sharp"][3] * tempo
    )
    control = (
        w["w_control"][0] * fm
        + w["w_control"][1] * fs
        + w["w_control"][2] * rstab
    )
    space = (
        w["w_space"][0] * xm
        + w["w_space"][1] * bm
        + w["w_space"][2] * xs
    )
    rhythm = rstab
    arousal = (
        w["w_arousal"][0] * energy
        + w["w_arousal"][1] * sharp
        + w["w_arousal"][2] * heavy
        + w["w_arousal"][3] * tempo
    )
    valence = (
        w["w_valence"][0] * space
        + w["w_valence"][1] * (1.0 - control)
        + w["w_valence"][2] * rhythm
        + w["w_valence"][3] * (1.0 - heavy)
    )
    dynamic = (
        w["w_dynamic"][0] * bs
        + w["w_dynamic"][1] * ws
        + w["w_dynamic"][2] * ss
        + w["w_dynamic"][3] * fs
        + w["w_dynamic"][4] * xs
    )

    M = np.stack(
        [
            _clip01(energy),
            _clip01(heavy),
            _clip01(sharp),
            _clip01(control),
            _clip01(space),
            _clip01(rhythm),
            _clip01(arousal),
            _clip01(valence),
            _clip01(dynamic),
        ],
        axis=1,
    ).astype(np.float32)
    return M


def _tri_tag(v: float, t1: float, t2: float, low: str, mid: str, high: str) -> str:
    if v < t1:
        return low
    if v < t2:
        return mid
    return high


def _apply_dance_phrase(tags: dict[str, str]) -> None:
    if tags["energy_tag"] == "high" and tags["attack_tag"] == "sharp":
        tags["dance_phrase"] = "explosive athletic choreography"
    elif tags["flow_tag"] == "free" and tags["space_tag"] == "expansive":
        tags["dance_phrase"] = "fluid expressive dance"
    elif tags["weight_tag"] == "heavy":
        tags["dance_phrase"] = "grounded powerful movement"
    else:
        tags["dance_phrase"] = "rhythmic contemporary dance"


def _tags_from_scores(scores: dict[str, float], t1: float, t2: float) -> dict[str, str]:
    tags = {
        "energy_tag": _tri_tag(scores["energy_score"], t1, t2, "low", "medium", "high"),
        "weight_tag": _tri_tag(scores["heaviness_score"], t1, t2, "light", "medium", "heavy"),
        "flow_tag": _tri_tag(scores["control_score"], t1, t2, "free", "mixed", "bound-controlled"),
        "attack_tag": _tri_tag(scores["sharpness_score"], t1, t2, "soft", "mixed", "sharp"),
        "space_tag": _tri_tag(scores["expansiveness_score"], t1, t2, "compact", "medium", "expansive"),
        "rhythm_tag": _tri_tag(scores["rhythmic_stability_score"], t1, t2, "variable", "mixed", "steady"),
        "dynamic_tag": _tri_tag(scores["dynamic_score"], t1, t2, "flat", "evolving", "highly dynamic"),
    }

    arousal = scores["arousal_score"]
    valence = scores["valence_score"]
    sharpness = scores["sharpness_score"]
    heaviness = scores["heaviness_score"]
    control = scores["control_score"]
    energy = scores["energy_score"]
    expansiveness = scores["expansiveness_score"]

    if arousal < 0.35 and valence > 0.55:
        tags["mood_tag"] = "calm"
    elif arousal < 0.35 and valence <= 0.55:
        tags["mood_tag"] = "cinematic"
    elif arousal >= 0.35 and arousal < 0.65 and valence > 0.60:
        tags["mood_tag"] = "joyful"
    elif arousal >= 0.65 and sharpness > 0.60 and heaviness > 0.55:
        tags["mood_tag"] = "aggressive"
    elif control > 0.65 and valence < 0.50:
        tags["mood_tag"] = "tense"
    else:
        tags["mood_tag"] = "cinematic"

    if energy > 0.70 and sharpness > 0.65:
        tags["style_tag"] = "electronic"
    elif heaviness > 0.65 and sharpness > 0.55:
        tags["style_tag"] = "percussion-driven"
    elif expansiveness > 0.65 and control < 0.55:
        tags["style_tag"] = "cinematic"
    elif energy < 0.40 and control < 0.45:
        tags["style_tag"] = "ambient"
    else:
        tags["style_tag"] = "hybrid"

    _apply_dance_phrase(tags)
    return tags


def _hysteresis(
    scores: dict[str, float],
    tags: dict[str, str],
    prev_tags: dict[str, str] | None,
    margin: float,
    t1: float,
    t2: float,
) -> dict[str, str]:
    if prev_tags is None:
        return tags

    levels = sem.BASE_TAG_LEVELS
    score_for = sem.BASE_TAG_TO_SCORE
    out = dict(tags)
    m = float(max(0.0, margin))

    for tag_name, lvls in levels.items():
        prev = str(prev_tags.get(tag_name, ""))
        if prev not in lvls:
            continue
        prev_idx = lvls.index(prev)
        s = float(scores[score_for[tag_name]])

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
        out[tag_name] = lvls[idx]

    _apply_dance_phrase(out)
    return out


def _l2norm(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
    return x / n


def _load_clap_model(device: str):
    import laion_clap

    model = laion_clap.CLAP_Module(enable_fusion=False, device=device)
    model.load_ckpt()
    return model


def _embed_texts(texts: list[str], model, cache: dict[str, np.ndarray], batch: int = 64) -> np.ndarray:
    uniq = []
    seen = set()
    for t in texts:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    miss = [t for t in uniq if t not in cache]
    for i in range(0, len(miss), batch):
        chunk = miss[i : i + batch]
        emb = model.get_text_embedding(chunk, use_tensor=False)
        emb = np.asarray(emb, dtype=np.float32)
        for s, e in zip(chunk, emb):
            cache[s] = e.astype(np.float32)
    out = np.stack([cache[t] for t in texts], axis=0).astype(np.float32)
    return out


def _build_subset_groups(meta: pd.DataFrame, subset_idx: np.ndarray) -> list[np.ndarray]:
    sub = meta.loc[subset_idx].copy()
    roots: list[str] = []
    chs: list[int] = []
    for s in sub["stem"].astype(str).tolist():
        r, c = _track_root(s)
        roots.append(r)
        chs.append(c)
    sub["track_root"] = roots
    sub["chunk_idx"] = chs
    sub["__gidx__"] = subset_idx
    sub = sub.sort_values(by=["db", "track_root", "chunk_idx", "clip_id"], kind="mergesort")
    groups = []
    for _, g in sub.groupby(["db", "track_root"], sort=False):
        groups.append(g["__gidx__"].to_numpy(dtype=int))
    return groups


def _evaluate_subset(
    idx: np.ndarray,
    groups: list[np.ndarray],
    score_mat: np.ndarray,
    tempo_bpm: np.ndarray,
    audio_emb_norm: np.ndarray,
    params: dict[str, Any],
    clap_model,
    text_cache: dict[str, np.ndarray],
    consistency_lambda: float,
) -> dict[str, Any]:
    t1 = float(params["t1"])
    t2 = float(params["t2"])
    alpha = float(params["ema_alpha"])
    margin = float(params["hysteresis_margin"])

    prompts_by_idx: dict[int, str] = {}
    transitions = 0
    switched = 0

    for g in groups:
        prev_scores: dict[str, float] | None = None
        prev_tags: dict[str, str] | None = None
        for gi in g:
            srow = {k: float(v) for k, v in zip(BASE_SCORE_KEYS, score_mat[gi])}
            if prev_scores is not None:
                smoothed = {}
                for k in BASE_SCORE_KEYS:
                    smoothed[k] = float(_clip01(alpha * srow[k] + (1.0 - alpha) * prev_scores[k]))
            else:
                smoothed = dict(srow)

            tags = _tags_from_scores(smoothed, t1=t1, t2=t2)
            tags = _hysteresis(smoothed, tags, prev_tags=prev_tags, margin=margin, t1=t1, t2=t2)
            prompt = sem.generate_prompt(tags, float(tempo_bpm[gi]))
            prompts_by_idx[int(gi)] = prompt

            if prev_tags is not None:
                transitions += 1
                changed = any(tags[k] != prev_tags[k] for k in BASE_TAG_KEYS)
                if changed:
                    switched += 1

            prev_scores = smoothed
            prev_tags = tags

    prompts = [prompts_by_idx[int(i)] for i in idx.tolist()]
    text_emb = _embed_texts(prompts, model=clap_model, cache=text_cache, batch=64)
    text_emb = _l2norm(text_emb)
    sim = np.sum(text_emb * audio_emb_norm[idx], axis=1)
    mean_cos = float(np.mean(sim))
    std_cos = float(np.std(sim))
    switch_rate = float(switched / transitions) if transitions > 0 else 0.0
    objective = float(mean_cos - float(consistency_lambda) * switch_rate)
    return {
        "objective": objective,
        "mean_cos": mean_cos,
        "std_cos": std_cos,
        "switch_rate": switch_rate,
        "n_rows": int(len(idx)),
        "n_groups": int(len(groups)),
        "n_transitions": int(transitions),
    }


def _flatten_params(p: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in p.items():
        if isinstance(v, np.ndarray):
            out[k] = ",".join(f"{float(x):.6f}" for x in v.tolist())
        else:
            out[k] = float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="outputs/m2m_train")
    ap.add_argument("--test-dbs", default="simonalexanderson")
    ap.add_argument("--test-db-fraction", type=float, default=1.0)
    ap.add_argument("--val-fraction", type=float, default=0.20)
    ap.add_argument("--trials", type=int, default=80)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--consistency-lambda", type=float, default=0.05)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    dataset_dir = (root / args.dataset_dir).resolve() if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    out_dir = Path(args.out_dir) if args.out_dir else (dataset_dir / "reports" / "semantic_tune_search")
    out_dir.mkdir(parents=True, exist_ok=True)

    xp = dataset_dir / "X_motion.csv"
    mp = dataset_dir / "meta.csv"
    cp = dataset_dir / "clap_audio_emb.npz"
    if not xp.exists() or not mp.exists() or not cp.exists():
        raise FileNotFoundError("dataset-dir must contain X_motion.csv, meta.csv, clap_audio_emb.npz")

    xdf = pd.read_csv(xp)
    meta = pd.read_csv(mp)
    if len(xdf) != len(meta):
        raise RuntimeError(f"X/meta mismatch: {len(xdf)} vs {len(meta)}")
    if "clip_id" not in meta.columns or "db" not in meta.columns or "stem" not in meta.columns:
        raise RuntimeError("meta.csv must contain clip_id, db, stem")

    z = np.load(cp, allow_pickle=True)
    clap_ids = np.array([str(x) for x in z["ids"]], dtype=object)
    clap_emb = np.asarray(z["emb"], dtype=np.float32)
    id2j = {k: i for i, k in enumerate(clap_ids.tolist())}

    clip_ids = meta["clip_id"].astype(str).to_numpy()
    keep = np.array([cid in id2j for cid in clip_ids], dtype=bool)
    if not np.any(keep):
        raise RuntimeError("No rows aligned with CLAP ids.")

    xdf = xdf.loc[keep].reset_index(drop=True)
    meta = meta.loc[keep].reset_index(drop=True)
    clip_ids = meta["clip_id"].astype(str).to_numpy()
    emb = np.stack([clap_emb[id2j[cid]] for cid in clip_ids], axis=0).astype(np.float32)
    emb_norm = _l2norm(emb)

    db = meta["db"].astype(str).to_numpy()
    stems = meta["stem"].astype(str).to_numpy()
    test_dbs = _parse_list(args.test_dbs)
    if not test_dbs:
        raise RuntimeError("--test-dbs cannot be empty.")

    mask_test = np.isin(db, test_dbs)
    if float(args.test_db_fraction) < 1.0:
        rng_tmp = np.random.RandomState(int(args.seed))
        sub_mask = np.zeros_like(mask_test, dtype=bool)
        for d in test_dbs:
            idx_d = np.where(db == d)[0]
            if idx_d.size == 0:
                continue
            groups = np.unique(stems[idx_d])
            n = max(1, int(round(float(args.test_db_fraction) * groups.size)))
            pick = rng_tmp.choice(groups, size=min(n, groups.size), replace=False)
            sub_mask[idx_d] = np.isin(stems[idx_d], pick)
        mask_test = sub_mask

    if not np.any(mask_test):
        raise RuntimeError("No test rows after db holdout.")
    if np.all(mask_test):
        raise RuntimeError("All rows are in test; no train/val rows.")

    idx_all = np.arange(len(meta), dtype=int)
    idx_pool = idx_all[~mask_test]
    idx_test = idx_all[mask_test]

    group_keys = []
    for i in idx_pool.tolist():
        root_stem, _ = _track_root(stems[i])
        group_keys.append(f"{db[i]}::{root_stem}")
    group_keys = np.array(group_keys, dtype=object)

    gss = GroupShuffleSplit(n_splits=1, test_size=float(np.clip(args.val_fraction, 0.05, 0.45)), random_state=int(args.seed))
    tr_rel, va_rel = next(gss.split(idx_pool, groups=group_keys))
    idx_train = idx_pool[tr_rel]
    idx_val = idx_pool[va_rel]

    feat = _build_norm_features(xdf, train_idx=idx_train)
    tempo_bpm = feat["tempo_bpm"]

    val_groups = _build_subset_groups(meta, idx_val)
    test_groups = _build_subset_groups(meta, idx_test)

    # CLAP text model
    device = str(args.device)
    if device == "cuda":
        try:
            import torch

            if not torch.cuda.is_available():
                device = "cpu"
        except Exception:
            device = "cpu"
    clap_model = _load_clap_model(device=device)
    text_cache: dict[str, np.ndarray] = {}

    # Baseline
    baseline_params = _default_params()
    baseline_score = _compute_score_matrix(feat, baseline_params)
    base_val = _evaluate_subset(
        idx=idx_val,
        groups=val_groups,
        score_mat=baseline_score,
        tempo_bpm=tempo_bpm,
        audio_emb_norm=emb_norm,
        params=baseline_params,
        clap_model=clap_model,
        text_cache=text_cache,
        consistency_lambda=float(args.consistency_lambda),
    )
    base_test = _evaluate_subset(
        idx=idx_test,
        groups=test_groups,
        score_mat=baseline_score,
        tempo_bpm=tempo_bpm,
        audio_emb_norm=emb_norm,
        params=baseline_params,
        clap_model=clap_model,
        text_cache=text_cache,
        consistency_lambda=float(args.consistency_lambda),
    )

    # Search
    rng = np.random.RandomState(int(args.seed))
    trials: list[dict[str, Any]] = []
    best_params = baseline_params
    best_val = dict(base_val)
    best_score_mat = baseline_score

    n_trials = int(max(1, args.trials))
    for t in range(n_trials):
        p = _sample_params(rng)
        sm = _compute_score_matrix(feat, p)
        ev = _evaluate_subset(
            idx=idx_val,
            groups=val_groups,
            score_mat=sm,
            tempo_bpm=tempo_bpm,
            audio_emb_norm=emb_norm,
            params=p,
            clap_model=clap_model,
            text_cache=text_cache,
            consistency_lambda=float(args.consistency_lambda),
        )
        row = {
            "trial": int(t + 1),
            **ev,
            **_flatten_params(p),
        }
        trials.append(row)
        if ev["objective"] > best_val["objective"]:
            best_params = p
            best_val = ev
            best_score_mat = sm
        if (t + 1) % 10 == 0 or (t + 1) == n_trials:
            print(
                f"[trial {t+1}/{n_trials}] val_obj={ev['objective']:.6f} "
                f"best_val_obj={best_val['objective']:.6f}"
            )

    best_test = _evaluate_subset(
        idx=idx_test,
        groups=test_groups,
        score_mat=best_score_mat,
        tempo_bpm=tempo_bpm,
        audio_emb_norm=emb_norm,
        params=best_params,
        clap_model=clap_model,
        text_cache=text_cache,
        consistency_lambda=float(args.consistency_lambda),
    )

    # Save trials CSV
    trials_csv = out_dir / "trials.csv"
    if trials:
        with trials_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(trials[0].keys()))
            writer.writeheader()
            writer.writerows(trials)

    best_json = out_dir / "best_params.json"
    best_payload = {
        "search": {
            "trials": n_trials,
            "seed": int(args.seed),
            "consistency_lambda": float(args.consistency_lambda),
            "device": device,
        },
        "split": {
            "rows_total": int(len(meta)),
            "rows_train": int(len(idx_train)),
            "rows_val": int(len(idx_val)),
            "rows_test": int(len(idx_test)),
            "test_dbs": test_dbs,
            "test_db_fraction": float(args.test_db_fraction),
        },
        "baseline": {
            "val": base_val,
            "test": base_test,
        },
        "best": {
            "val": best_val,
            "test": best_test,
            "params": {
                k: (v.tolist() if isinstance(v, np.ndarray) else float(v))
                for k, v in best_params.items()
            },
        },
    }
    best_json.write_text(json.dumps(best_payload, indent=2), encoding="utf-8")

    report_txt = out_dir / "report.txt"
    lines = [
        f"dataset_dir={dataset_dir}",
        f"rows_total={len(meta)} rows_train={len(idx_train)} rows_val={len(idx_val)} rows_test={len(idx_test)}",
        f"test_dbs={test_dbs} test_db_fraction={float(args.test_db_fraction):.3f}",
        f"trials={n_trials} seed={int(args.seed)} consistency_lambda={float(args.consistency_lambda):.4f}",
        "",
        "[baseline]",
        f"val_objective={base_val['objective']:.6f}",
        f"val_mean_cos={base_val['mean_cos']:.6f}",
        f"val_switch_rate={base_val['switch_rate']:.6f}",
        f"test_objective={base_test['objective']:.6f}",
        f"test_mean_cos={base_test['mean_cos']:.6f}",
        f"test_switch_rate={base_test['switch_rate']:.6f}",
        "",
        "[best]",
        f"val_objective={best_val['objective']:.6f}",
        f"val_mean_cos={best_val['mean_cos']:.6f}",
        f"val_switch_rate={best_val['switch_rate']:.6f}",
        f"test_objective={best_test['objective']:.6f}",
        f"test_mean_cos={best_test['mean_cos']:.6f}",
        f"test_switch_rate={best_test['switch_rate']:.6f}",
        "",
        "[delta best-baseline]",
        f"val_objective_delta={best_val['objective'] - base_val['objective']:.6f}",
        f"val_mean_cos_delta={best_val['mean_cos'] - base_val['mean_cos']:.6f}",
        f"val_switch_rate_delta={best_val['switch_rate'] - base_val['switch_rate']:.6f}",
        f"test_objective_delta={best_test['objective'] - base_test['objective']:.6f}",
        f"test_mean_cos_delta={best_test['mean_cos'] - base_test['mean_cos']:.6f}",
        f"test_switch_rate_delta={best_test['switch_rate'] - base_test['switch_rate']:.6f}",
        "",
        f"trials_csv={trials_csv}",
        f"best_params_json={best_json}",
    ]
    report_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[done] report:", report_txt)
    print("[done] best params:", best_json)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
