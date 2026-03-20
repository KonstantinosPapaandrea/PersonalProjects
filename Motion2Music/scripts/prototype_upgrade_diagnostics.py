#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, normalized_mutual_info_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import semantic_prompt_from_motion as sem
import tune_semantic_prompt_params as tuner


def _parse_list(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()] if s else []


def _root(stem: str) -> str:
    m = re.search(r"_ch(\d+)$", stem)
    return stem[: m.start()] if m else stem


def _groups(meta: pd.DataFrame, idx: np.ndarray) -> list[np.ndarray]:
    sub = meta.loc[idx].copy()
    sub["trk"] = [_root(s) for s in sub["stem"].astype(str).tolist()]
    sub["gidx"] = idx
    out = []
    for _, g in sub.groupby(["db", "trk"], sort=False):
        out.append(g["gidx"].to_numpy(dtype=int))
    return out


def _load_params(path: Path | None) -> dict:
    if path is None or not path.exists():
        return tuner._default_params()
    o = json.loads(path.read_text(encoding="utf-8"))
    src = o.get("best", {}).get("params", o)
    p = {
        "sigma": float(src.get("sigma", 0.0)),
        "t1": float(src.get("t1", 0.33)),
        "t2": float(src.get("t2", 0.66)),
        "ema_alpha": float(src.get("ema_alpha", 1.0)),
        "hysteresis_margin": float(src.get("hysteresis_margin", 0.05)),
    }
    for k, base in tuner.BASE_WEIGHTS.items():
        a = np.asarray(src.get(k, base.tolist()), dtype=np.float64)
        if a.shape[0] != base.shape[0]:
            a = base.copy()
        a = np.maximum(a, 1e-8)
        p[k] = a / np.sum(a)
    return p


def _build_prompts_tags(idx: np.ndarray, groups: list[np.ndarray], score_mat: np.ndarray, tempo_bpm: np.ndarray, p: dict):
    t1, t2 = float(p["t1"]), float(p["t2"])
    a, m = float(p["ema_alpha"]), float(p["hysteresis_margin"])
    byp, byt = {}, {}
    tr, sw = 0, 0
    for g in groups:
        prev_s, prev_t = None, None
        for gi in g.tolist():
            srow = {k: float(v) for k, v in zip(tuner.BASE_SCORE_KEYS, score_mat[gi])}
            if prev_s is None:
                sm = dict(srow)
            else:
                sm = {k: float(np.clip(a * srow[k] + (1 - a) * prev_s[k], 0, 1)) for k in tuner.BASE_SCORE_KEYS}
            t = tuner._tags_from_scores(sm, t1=t1, t2=t2)
            t = tuner._hysteresis(sm, t, prev_tags=prev_t, margin=m, t1=t1, t2=t2)
            byp[int(gi)] = sem.generate_prompt(t, float(tempo_bpm[gi]))
            byt[int(gi)] = t
            if prev_t is not None:
                tr += 1
                if any(t[k] != prev_t[k] for k in tuner.BASE_TAG_KEYS):
                    sw += 1
            prev_s, prev_t = sm, t
    return [byp[int(i)] for i in idx.tolist()], [byt[int(i)] for i in idx.tolist()], (float(sw / tr) if tr > 0 else 0.0)


def _norm_mode(raw: np.ndarray, db: np.ndarray, tr: np.ndarray, mode: str) -> np.ndarray:
    x = raw.astype(np.float64).copy()
    if mode == "l2":
        return tuner._l2norm(x.astype(np.float32))
    if mode == "dataset_center_l2":
        means = {}
        gmu = np.mean(x[tr], axis=0)
        for d in np.unique(db):
            ix = tr[db[tr] == d]
            if ix.size:
                means[d] = np.mean(x[ix], axis=0)
        y = np.zeros_like(x)
        for i in range(x.shape[0]):
            y[i] = x[i] - means.get(str(db[i]), gmu)
        return tuner._l2norm(y.astype(np.float32))
    if mode == "global_zscore_l2":
        mu = np.mean(x[tr], axis=0)
        sd = np.std(x[tr], axis=0) + 1e-8
        y = (x - mu) / sd
        return tuner._l2norm(y.astype(np.float32))
    raise ValueError(mode)


def _fit_cluster(xtr: np.ndarray, method: str, k: int, seed: int):
    if method == "kmeans":
        m = KMeans(n_clusters=k, random_state=seed, n_init=20)
        ytr = m.fit_predict(xtr)
        c = np.asarray(m.cluster_centers_, dtype=np.float32)
    elif method == "kmeans_dsalign":
        raise RuntimeError("kmeans_dsalign requires db_train; use _fit_cluster_with_db().")
    else:
        try:
            m = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average")
        except TypeError:
            m = AgglomerativeClustering(n_clusters=k, affinity="cosine", linkage="average")
        ytr = m.fit_predict(xtr)
        c = []
        for i in range(k):
            ix = np.where(ytr == i)[0]
            c.append(np.mean(xtr[ix], axis=0) if ix.size else np.zeros(xtr.shape[1], dtype=np.float32))
        c = np.stack(c, axis=0).astype(np.float32)
    return ytr.astype(np.int32), tuner._l2norm(c.astype(np.float32))


def _greedy_align(sim: np.ndarray) -> dict[int, int]:
    # Greedy max matching local->ref; fast and dependency-free.
    n_local, n_ref = sim.shape
    if n_local == 0 or n_ref == 0:
        return {}
    used_l = set()
    used_r = set()
    out: dict[int, int] = {}
    flat = np.argsort(-sim.reshape(-1))
    for f in flat.tolist():
        li = int(f // n_ref)
        ri = int(f % n_ref)
        if li in used_l or ri in used_r:
            continue
        out[li] = ri
        used_l.add(li)
        used_r.add(ri)
        if len(used_l) == n_local or len(used_r) == n_ref:
            break
    return out


def _fit_cluster_with_db(xtr: np.ndarray, dbtr: np.ndarray, method: str, k: int, seed: int):
    if method != "kmeans_dsalign":
        return _fit_cluster(xtr=xtr, method=method, k=k, seed=seed)

    dbv = np.asarray(dbtr, dtype=object)
    udb = np.unique(dbv)
    if udb.size == 0:
        return _fit_cluster(xtr=xtr, method="kmeans", k=k, seed=seed)

    # Reference dataset: largest in training split.
    counts = [(d, int(np.sum(dbv == d))) for d in udb.tolist()]
    counts.sort(key=lambda z: z[1], reverse=True)
    ref_db = str(counts[0][0])
    ix_ref = np.where(dbv == ref_db)[0]
    if ix_ref.size < k:
        return _fit_cluster(xtr=xtr, method="kmeans", k=k, seed=seed)

    km_ref = KMeans(n_clusters=k, random_state=seed, n_init=20)
    y_ref = km_ref.fit_predict(xtr[ix_ref]).astype(np.int32)
    c_ref = tuner._l2norm(np.asarray(km_ref.cluster_centers_, dtype=np.float32))

    y = np.full(xtr.shape[0], -1, dtype=np.int32)
    y[ix_ref] = y_ref

    c_sum = np.zeros_like(c_ref, dtype=np.float64)
    w_sum = np.zeros(k, dtype=np.float64)
    for c in range(k):
        n = int(np.sum(y_ref == c))
        if n > 0:
            c_sum[c] += c_ref[c] * n
            w_sum[c] += n

    # Cluster each non-ref dataset locally, then align local clusters to ref clusters.
    for d in udb.tolist():
        d = str(d)
        if d == ref_db:
            continue
        ix = np.where(dbv == d)[0]
        if ix.size == 0:
            continue
        if ix.size < 2:
            y[ix] = np.argmax(np.matmul(tuner._l2norm(xtr[ix].astype(np.float32)), c_ref.T), axis=1).astype(np.int32)
            continue
        k_loc = int(min(k, ix.size))
        km = KMeans(n_clusters=k_loc, random_state=seed, n_init=20)
        y_loc = km.fit_predict(xtr[ix]).astype(np.int32)
        c_loc = tuner._l2norm(np.asarray(km.cluster_centers_, dtype=np.float32))
        mapping = _greedy_align(np.matmul(c_loc, c_ref.T))
        mapped = np.array([mapping.get(int(v), int(np.argmax(np.matmul(c_loc[int(v)], c_ref.T)))) for v in y_loc], dtype=np.int32)
        y[ix] = mapped

        for lc in range(k_loc):
            gid = int(mapping.get(lc, int(np.argmax(np.matmul(c_loc[lc], c_ref.T)))))
            n = int(np.sum(y_loc == lc))
            if n > 0:
                c_sum[gid] += c_loc[lc] * n
                w_sum[gid] += n

    # Fill any unassigned with nearest ref center.
    miss = np.where(y < 0)[0]
    if miss.size:
        y[miss] = np.argmax(np.matmul(tuner._l2norm(xtr[miss].astype(np.float32)), c_ref.T), axis=1).astype(np.int32)

    c = np.zeros_like(c_ref, dtype=np.float32)
    for i in range(k):
        if w_sum[i] > 0:
            c[i] = (c_sum[i] / w_sum[i]).astype(np.float32)
        else:
            c[i] = c_ref[i]
    c = tuner._l2norm(c.astype(np.float32))
    return y.astype(np.int32), c


def _assign(x: np.ndarray, c: np.ndarray) -> np.ndarray:
    return np.argmax(np.matmul(x, c.T), axis=1).astype(np.int32)


def _ret(sim: np.ndarray, y: np.ndarray):
    ords = np.argsort(-sim, axis=1)
    r = np.array([int(np.where(ords[i] == y[i])[0][0]) + 1 for i in range(sim.shape[0])], dtype=np.int32)
    return float(np.mean(r <= 1)), float(np.mean(r <= 3)), float(np.mean(1.0 / r))


def _fit_motion(X: np.ndarray, y: np.ndarray, tr: np.ndarray, te: np.ndarray):
    if np.unique(y[tr]).size < 2:
        return 0.0, 0.0
    m = Pipeline([("s", StandardScaler()), ("c", LogisticRegression(max_iter=5000, class_weight="balanced"))])
    m.fit(X[tr], y[tr])
    p = m.predict(X[te])
    return float(accuracy_score(y[te], p)), float(f1_score(y[te], p, average="macro"))


def _cluster_dataset_purity(y: np.ndarray, db: np.ndarray, k: int) -> float:
    # 1.0 means clusters are mostly single-dataset (high leakage risk); lower is better mixed.
    yy = np.asarray(y, dtype=np.int32)
    dd = np.asarray(db, dtype=object)
    den = float(len(yy))
    if den <= 0:
        return 0.0
    acc = 0.0
    for c in range(int(k)):
        ix = np.where(yy == c)[0]
        if ix.size == 0:
            continue
        vc = pd.Series(dd[ix]).value_counts(normalize=True)
        maj = float(vc.iloc[0]) if len(vc) else 0.0
        acc += (ix.size / den) * maj
    return float(acc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="outputs/m2m_train")
    ap.add_argument("--x-motion-csv", default="X_motion.csv")
    ap.add_argument("--clap-npz", default="clap_audio_emb.npz")
    ap.add_argument("--params-json", default="outputs/m2m_train/reports/semantic_tune_search/best_params.json")
    ap.add_argument("--test-dbs", default="simonalexanderson")
    ap.add_argument("--test-db-fraction", type=float, default=1.0)
    ap.add_argument("--val-fraction", type=float, default=0.20)
    ap.add_argument("--k-list", default="4,5,6,8,10")
    ap.add_argument("--methods", default="kmeans,agglo,kmeans_dsalign")
    ap.add_argument("--norm-modes", default="l2,dataset_center_l2,global_zscore_l2")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    ddir = (root / args.dataset_dir).resolve() if not Path(args.dataset_dir).is_absolute() else Path(args.dataset_dir)
    out = Path(args.out_dir) if args.out_dir else (ddir / "reports" / "prototype_upgrade")
    out.mkdir(parents=True, exist_ok=True)
    pjson = (root / args.params_json).resolve() if args.params_json and not Path(args.params_json).is_absolute() else Path(args.params_json)
    cnpz = (ddir / args.clap_npz).resolve() if not Path(args.clap_npz).is_absolute() else Path(args.clap_npz)
    xcsv = (ddir / args.x_motion_csv).resolve() if not Path(args.x_motion_csv).is_absolute() else Path(args.x_motion_csv)

    xdf = pd.read_csv(xcsv)
    meta = pd.read_csv(ddir / "meta.csv")
    z = np.load(cnpz, allow_pickle=True)
    id2j = {str(k): i for i, k in enumerate(z["ids"].tolist())}
    keep = np.array([str(cid) in id2j for cid in meta["clip_id"].astype(str).to_numpy()], dtype=bool)
    xdf = xdf.loc[keep].reset_index(drop=True)
    meta = meta.loc[keep].reset_index(drop=True)
    ids = meta["clip_id"].astype(str).to_numpy()
    emb_raw = np.stack([z["emb"][id2j[cid]] for cid in ids], axis=0).astype(np.float32)
    emb_l2 = tuner._l2norm(emb_raw)
    db = meta["db"].astype(str).to_numpy()
    stems = meta["stem"].astype(str).to_numpy()

    test_dbs = _parse_list(args.test_dbs)
    mtest = np.isin(db, test_dbs)
    if float(args.test_db_fraction) < 1.0:
        rng = np.random.RandomState(int(args.seed))
        mm = np.zeros_like(mtest, dtype=bool)
        for d in test_dbs:
            ix = np.where(db == d)[0]
            if ix.size == 0:
                continue
            g = np.unique(stems[ix])
            n = max(1, int(round(float(args.test_db_fraction) * g.size)))
            pick = rng.choice(g, size=min(n, g.size), replace=False)
            mm[ix] = np.isin(stems[ix], pick)
        mtest = mm

    idx = np.arange(len(meta), dtype=int)
    pool = idx[~mtest]
    test = idx[mtest]
    gkeys = np.array([f"{db[i]}::{_root(stems[i])}" for i in pool], dtype=object)
    gss = GroupShuffleSplit(n_splits=1, test_size=float(np.clip(args.val_fraction, 0.05, 0.45)), random_state=int(args.seed))
    tr_rel, va_rel = next(gss.split(pool, groups=gkeys))
    tr, va = pool[tr_rel], pool[va_rel]

    p = _load_params(pjson if pjson.exists() else None)
    feat = tuner._build_norm_features(xdf, train_idx=tr)
    smat = tuner._compute_score_matrix(feat, p)
    bpm = feat["tempo_bpm"]
    vp, vt, vsw = _build_prompts_tags(va, _groups(meta, va), smat, bpm, p)
    tp, tt, tsw = _build_prompts_tags(test, _groups(meta, test), smat, bpm, p)
    allp, allt, _ = _build_prompts_tags(idx, _groups(meta, idx), smat, bpm, p)

    dev = args.device
    if dev == "cuda":
        try:
            import torch
            if not torch.cuda.is_available():
                dev = "cpu"
        except Exception:
            dev = "cpu"
    clap = tuner._load_clap_model(device=dev)
    cache = {}
    vtxt = tuner._l2norm(tuner._embed_texts(vp, model=clap, cache=cache, batch=64))
    ttxt = tuner._l2norm(tuner._embed_texts(tp, model=clap, cache=cache, batch=64))

    # dataset leakage classifier
    if np.unique(db).size > 1:
        i_tr, i_te = train_test_split(np.arange(len(db)), test_size=0.2, random_state=int(args.seed), stratify=db)
        dc = Pipeline([("s", StandardScaler()), ("c", LogisticRegression(max_iter=4000, class_weight="balanced"))])
        dc.fit(emb_l2[i_tr], db[i_tr])
        dp = dc.predict(emb_l2[i_te])
        leak_acc = float(accuracy_score(db[i_te], dp))
        leak_f1 = float(f1_score(db[i_te], dp, average="macro"))
    else:
        leak_acc = 1.0
        leak_f1 = 1.0

    rows = []
    best, best_art, best_key = None, {}, -1e9
    for nm in _parse_list(args.norm_modes):
        ec = _norm_mode(emb_raw, db=db, tr=tr, mode=nm)
        for meth in _parse_list(args.methods):
            for k in [int(x) for x in _parse_list(args.k_list)]:
                if k < 2 or k > len(tr):
                    continue
                ytr, cc = _fit_cluster_with_db(ec[tr], dbtr=db[tr], method=meth, k=k, seed=int(args.seed))
                yv = _assign(ec[va], cc)
                yt = _assign(ec[test], cc)
                co = []
                for c in range(k):
                    ix = np.where(ytr == c)[0]
                    co.append(np.mean(emb_l2[tr[ix]], axis=0) if ix.size else np.zeros(emb_l2.shape[1], dtype=np.float32))
                co = tuner._l2norm(np.stack(co, axis=0).astype(np.float32))
                ve = np.sum(vtxt * emb_l2[va], axis=1)
                vpv = np.sum(vtxt * co[yv], axis=1)
                te = np.sum(ttxt * emb_l2[test], axis=1)
                tpv = np.sum(ttxt * co[yt], axis=1)
                s1, s3, mrr = _ret(np.matmul(vtxt, co.T), yv)
                ts1, ts3, tmrr = _ret(np.matmul(ttxt, co.T), yt)
                nmi = float(normalized_mutual_info_score(db[tr], ytr))
                purity = _cluster_dataset_purity(ytr, db[tr], k=int(k))
                key = float(np.mean(vpv - ve) + 0.1 * s1 - 0.02 * nmi - 0.02 * purity)
                row = {
                    "norm_mode": nm, "method": meth, "k": int(k),
                    "val_exact_mean_cos": float(np.mean(ve)),
                    "val_proto_mean_cos": float(np.mean(vpv)),
                    "val_delta_mean": float(np.mean(vpv - ve)),
                    "val_top1": s1, "val_top3": s3, "val_mrr": mrr,
                    "test_exact_mean_cos": float(np.mean(te)),
                    "test_proto_mean_cos": float(np.mean(tpv)),
                    "test_delta_mean": float(np.mean(tpv - te)),
                    "test_top1": ts1, "test_top3": ts3, "test_mrr": tmrr,
                    "cluster_dataset_nmi_train": nmi,
                    "cluster_dataset_purity_train": purity,
                    "val_switch_rate": vsw, "test_switch_rate": tsw,
                }
                rows.append(row)
                print(f"[cfg] {nm} {meth} k={k} val_delta={row['val_delta_mean']:.6f} test_delta={row['test_delta_mean']:.6f}")
                if key > best_key:
                    best_key = key
                    best = dict(row)
                    best_art = {"nm": nm, "co": co.copy(), "cc": cc.copy(), "ytr": ytr.copy(), "k": int(k)}

    if not rows or best is None:
        raise RuntimeError("No config evaluated")

    comp = pd.DataFrame(rows).sort_values(by=["norm_mode", "method", "k"])
    comp.to_csv(out / "config_comparison.csv", index=False)

    ec_best = _norm_mode(emb_raw, db=db, tr=tr, mode=best_art["nm"])
    y_all = np.zeros(len(meta), dtype=np.int32)
    y_all[tr] = best_art["ytr"]
    y_all[va] = _assign(ec_best[va], best_art["cc"])
    y_all[test] = _assign(ec_best[test], best_art["cc"])

    split = np.full(len(meta), "train", dtype=object)
    split[va] = "val"
    split[test] = "test"
    assigned = pd.DataFrame(
        {
            "clip_id": meta["clip_id"].to_numpy(),
            "db": db,
            "stem": stems,
            "split": split,
            "prototype": y_all.astype(int),
            "prompt": np.array(allp, dtype=object),
            "signature": np.array(
                [
                    "|".join(
                        [
                            t.get("energy_tag", ""),
                            t.get("attack_tag", ""),
                            t.get("flow_tag", ""),
                            t.get("space_tag", ""),
                            t.get("rhythm_tag", ""),
                            t.get("style_tag", ""),
                            t.get("mood_tag", ""),
                        ]
                    )
                    for t in allt
                ],
                dtype=object,
            ),
        }
    )
    assigned.to_csv(out / "assigned_prototypes.csv", index=False)

    x_cols = [c for c in xdf.columns if pd.api.types.is_numeric_dtype(xdf[c])]
    Xn = xdf[x_cols].copy()
    Xn = Xn.fillna(Xn.iloc[tr].median(numeric_only=True))
    X = Xn.to_numpy(dtype=np.float32)
    v_acc, v_f1 = _fit_motion(X, y_all, tr, va)
    t_acc, t_f1 = _fit_motion(X, y_all, tr, test)

    # within/cross
    within = []
    for d in np.unique(db):
        ix = np.where(db == d)[0]
        if ix.size < 60:
            continue
        g = np.array([_root(stems[i]) for i in ix], dtype=object)
        if np.unique(g).size < 4:
            continue
        sp = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=int(args.seed))
        a, b = next(sp.split(ix, groups=g))
        acc, f1m = _fit_motion(X, y_all, ix[a], ix[b])
        within.append({"db": d, "n_train": int(len(a)), "n_test": int(len(b)), "acc": acc, "f1_macro": f1m})
    pd.DataFrame(within).to_csv(out / "motion_proto_within_dataset.csv", index=False)

    cross = []
    for sdb in np.unique(db):
        si = np.where(db == sdb)[0]
        if si.size < 80 or np.unique(y_all[si]).size < 2:
            continue
        for tdb in np.unique(db):
            if tdb == sdb:
                continue
            ti = np.where(db == tdb)[0]
            if ti.size < 40:
                continue
            acc, f1m = _fit_motion(X, y_all, si, ti)
            cross.append({"train_db": sdb, "test_db": tdb, "n_train": int(len(si)), "n_test": int(len(ti)), "acc": acc, "f1_macro": f1m})
    pd.DataFrame(cross).to_csv(out / "motion_proto_cross_dataset.csv", index=False)

    # name suggestions
    cand = [
        "rhythmic electronic", "groove-heavy pop", "break hard-hitting",
        "softer expressive lyrical", "cinematic dramatic", "ambient atmospheric",
        "percussive dance", "club groove", "hip hop beat-driven",
    ]
    te = tuner._l2norm(tuner._embed_texts(cand, model=clap, cache=cache, batch=64))
    name_rows = []
    for c in range(best_art["co"].shape[0]):
        sim = np.dot(te, best_art["co"][c])
        ords = np.argsort(-sim)
        name_rows.append({
            "cluster": int(c),
            "suggested_name": cand[int(ords[0])],
            "alt_name_1": cand[int(ords[1])],
            "alt_name_2": cand[int(ords[2])],
            "sim_main": float(sim[int(ords[0])]),
        })
    pd.DataFrame(name_rows).to_csv(out / "cluster_names_suggested.csv", index=False)
    np.save(out / "best_centroids_orig.npy", best_art["co"])

    ex = []
    for c in range(best_art["k"]):
        rel = np.where(best_art["ytr"] == c)[0]
        if rel.size == 0:
            continue
        gi = tr[rel]
        sim = np.sum(emb_l2[gi] * best_art["co"][c], axis=1)
        o = np.argsort(-sim)
        for rnk, oi in enumerate(o[:10], start=1):
            i = int(gi[oi])
            ex.append({
                "cluster": int(c), "rank": int(rnk),
                "clip_id": int(meta.iloc[i]["clip_id"]), "db": str(meta.iloc[i]["db"]),
                "stem": str(meta.iloc[i]["stem"]), "audio_path": str(meta.iloc[i]["audio_path"]),
                "cos_to_centroid": float(sim[oi]),
                "suggested_name": next((n["suggested_name"] for n in name_rows if n["cluster"] == c), ""),
            })
    pd.DataFrame(ex).to_csv(out / "cluster_examples.csv", index=False)

    # Prototype-conditioned prompt view (debug/control path).
    proto_name = {int(r["cluster"]): str(r["suggested_name"]) for r in name_rows}
    proto_phrase = {
        "rhythmic electronic": "driving electronic pulse with crisp accents",
        "groove-heavy pop": "groove-forward pop rhythm with clear hooks",
        "break hard-hitting": "hard-hitting breakbeat impact and punch",
        "softer expressive lyrical": "softer lyrical phrasing with expressive flow",
        "cinematic dramatic": "cinematic dramatic arc with wide atmosphere",
        "ambient atmospheric": "ambient atmospheric texture with space",
        "percussive dance": "percussive dance rhythm and tight sync",
        "club groove": "club-oriented groove and steady drive",
        "hip hop beat-driven": "hip-hop beat-driven groove and punchy rhythm",
    }
    assigned["prototype_name"] = [proto_name.get(int(p), f"cluster_{int(p)}") for p in assigned["prototype"].astype(int).tolist()]
    assigned["prototype_phrase"] = [proto_phrase.get(n, n) for n in assigned["prototype_name"].tolist()]
    assigned["prompt_proto"] = [
        f"{p}, {ph}" if ph not in p else p for p, ph in zip(assigned["prompt"].astype(str).tolist(), assigned["prototype_phrase"].tolist())
    ]
    assigned.to_csv(out / "assigned_prototypes.csv", index=False)

    # signature overlap
    sig = np.array(["|".join([t.get("energy_tag",""), t.get("attack_tag",""), t.get("flow_tag",""), t.get("space_tag",""), t.get("rhythm_tag",""), t.get("style_tag",""), t.get("mood_tag","")]) for t in allt], dtype=object)
    ov = []
    pairs = 0
    for s in np.unique(sig):
        ix = np.where(sig == s)[0]
        if ix.size < 8:
            continue
        ds = np.unique(db[ix])
        if ds.size < 2:
            continue
        dmap = {}
        for d in ds:
            jx = ix[db[ix] == d]
            if jx.size < 4:
                continue
            h = np.bincount(y_all[jx], minlength=int(best_art["k"])).astype(np.float64)
            h = h / (np.sum(h) + 1e-12)
            dmap[d] = h
        ks = list(dmap.keys())
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                ov.append(float(np.sum(np.minimum(dmap[ks[i]], dmap[ks[j]]))))
                pairs += 1
    ov_mean = float(np.mean(ov)) if ov else 0.0

    summary = {
        "dataset_dir": str(ddir),
        "x_motion_csv": str(xcsv),
        "clap_npz": str(cnpz),
        "split": {
            "rows_total": int(len(meta)), "rows_train": int(len(tr)), "rows_val": int(len(va)), "rows_test": int(len(test)),
            "test_dbs": test_dbs, "test_db_fraction": float(args.test_db_fraction),
        },
        "dataset_leakage_classifier": {"acc": leak_acc, "f1_macro": leak_f1},
        "best_config": best,
        "motion_to_prototype": {"val_acc": v_acc, "val_f1_macro": v_f1, "test_acc": t_acc, "test_f1_macro": t_f1},
        "semantic_signature_overlap": {"signature_pairs": int(pairs), "signature_proto_overlap_mean": ov_mean},
        "outputs": {
            "config_table_csv": str(out / "config_comparison.csv"),
            "within_dataset_csv": str(out / "motion_proto_within_dataset.csv"),
            "cross_dataset_csv": str(out / "motion_proto_cross_dataset.csv"),
            "assigned_prototypes_csv": str(out / "assigned_prototypes.csv"),
            "cluster_names_csv": str(out / "cluster_names_suggested.csv"),
            "cluster_examples_csv": str(out / "cluster_examples.csv"),
            "best_centroids_npy": str(out / "best_centroids_orig.npy"),
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        f"dataset_dir={ddir}",
        f"rows_total={len(meta)} rows_train={len(tr)} rows_val={len(va)} rows_test={len(test)}",
        f"test_dbs={test_dbs} test_db_fraction={float(args.test_db_fraction):.3f}",
        f"dataset_clf_acc={leak_acc:.6f}",
        f"dataset_clf_f1_macro={leak_f1:.6f}",
        "",
        "[best config]",
        f"norm_mode={best['norm_mode']} method={best['method']} k={best['k']}",
        f"val_exact_mean_cos={best['val_exact_mean_cos']:.6f}",
        f"val_proto_mean_cos={best['val_proto_mean_cos']:.6f}",
        f"val_delta_mean={best['val_delta_mean']:.6f}",
        f"val_top1={best['val_top1']:.6f} val_top3={best['val_top3']:.6f} val_mrr={best['val_mrr']:.6f}",
        f"test_exact_mean_cos={best['test_exact_mean_cos']:.6f}",
        f"test_proto_mean_cos={best['test_proto_mean_cos']:.6f}",
        f"test_delta_mean={best['test_delta_mean']:.6f}",
        f"test_top1={best['test_top1']:.6f} test_top3={best['test_top3']:.6f} test_mrr={best['test_mrr']:.6f}",
        f"cluster_dataset_nmi_train={best['cluster_dataset_nmi_train']:.6f}",
        "",
        "[motion->prototype]",
        f"val_acc={v_acc:.6f} val_f1_macro={v_f1:.6f}",
        f"test_acc={t_acc:.6f} test_f1_macro={t_f1:.6f}",
        "",
        "[signature overlap]",
        f"signature_pairs={pairs}",
        f"signature_proto_overlap_mean={ov_mean:.6f}",
        "",
        f"summary_json={out / 'summary.json'}",
    ]
    (out / "report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
