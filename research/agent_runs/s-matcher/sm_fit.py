"""s-matcher step 2: walk-forward interpretable models of his S label, scored on AUC and on forward R of the trades the
rule takes. Everything is split by DATE (train < cut <= test); thresholds use only train-side scores.
Usage: python sm_fit.py DATADIR OUTJSON
"""
import os, sys, json, warnings
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sm_features import FEATURES, NQ_CTX

warnings.filterwarnings("ignore")
RNG = np.random.default_rng(7)
LAB = ["S", "A", "B", "C", "none"]


# ---------------------------------------------------------------- walk-forward machinery
def wf_folds(dates, n_folds=4, first=0.4):
    """dates: Series of ISO date strings (positional). -> [(train_pos, test_pos)], test blocks equal in unique dates."""
    d = np.asarray(dates)
    u = np.array(sorted(set(d)))
    edges = [int(round(first * len(u) + i * (1 - first) * len(u) / n_folds)) for i in range(n_folds + 1)]
    edges[-1] = len(u)
    folds = []
    for i in range(n_folds):
        lo, hi = u[edges[i]], (u[edges[i + 1]] if edges[i + 1] < len(u) else "9999")
        tr = np.where(d < lo)[0]
        te = np.where((d >= lo) & (d < hi))[0]
        if len(tr) and len(te):
            folds.append((tr, te))
    return folds


def subsample_neg(X, y, max_neg=12000, seed=7):
    """keep every positive and at most max_neg random negatives (class_weight=balanced makes this equivalent in
    expectation, and keeps the 60k-row population fit fast)."""
    y = np.asarray(y)
    neg = np.where(y == 0)[0]
    if len(neg) > max_neg:
        keep = np.sort(np.concatenate([np.where(y == 1)[0], np.random.default_rng(seed).choice(neg, max_neg, False)]))
        return X.iloc[keep], y[keep]
    return X, y


def make_model(kind, X, y):
    X, y = subsample_neg(X, y)
    if kind == "tree":
        return make_pipeline(SimpleImputer(strategy="median"),
                             DecisionTreeClassifier(max_depth=3, min_samples_leaf=max(5, int(0.02 * len(y))),
                                                    class_weight="balanced", random_state=7)).fit(X, y)
    if kind == "l1":
        n_pos = int(y.sum())
        cv = min(5, n_pos) if n_pos >= 2 else 2
        m = LogisticRegressionCV(penalty="l1", solver="liblinear", Cs=[0.01, 0.03, 0.1, 0.3, 1], cv=cv,
                                 scoring="roc_auc", class_weight="balanced", random_state=7, max_iter=300)
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), m).fit(X, y)
    raise ValueError(kind)


def score(model, X):
    return model.predict_proba(X)[:, 1]


def walk_forward_auc(X, y, dates, model="l1", n_folds=4, first=0.4):
    X = pd.DataFrame(X).reset_index(drop=True)
    y = np.asarray(y)
    folds = wf_folds(pd.Series(dates).reset_index(drop=True), n_folds, first)
    oos_idx, oos_s, fold_auc = [], [], []
    for tr, te in folds:
        if len(set(y[tr])) < 2:
            continue
        m = make_model(model, X.iloc[tr], y[tr])
        s = score(m, X.iloc[te])
        oos_idx.append(te); oos_s.append(s)
        fold_auc.append(round(float(roc_auc_score(y[te], s)), 3) if len(set(y[te])) == 2 else None)
    idx = np.concatenate(oos_idx)
    s = np.concatenate(oos_s)
    return dict(auc=float(roc_auc_score(y[idx], s)), fold_auc=fold_auc, idx=idx, score=s, n=len(idx),
                n_pos=int(y[idx].sum()))


def boot_auc(y, s, groups, n=2000):
    y, s = np.asarray(y), np.asarray(s)
    g = pd.Series(groups).reset_index(drop=True)
    keys = g.unique()
    by = {k: np.where(g.to_numpy() == k)[0] for k in keys}
    out = []
    for _ in range(n):
        pick = RNG.choice(len(keys), len(keys))
        ii = np.concatenate([by[keys[p]] for p in pick])
        if len(set(y[ii])) == 2:
            out.append(roc_auc_score(y[ii], s[ii]))
    return [round(float(np.percentile(out, 2.5)), 3), round(float(np.percentile(out, 97.5)), 3)]


def perm_auc_p(y, s, n=3000):
    y, s = np.asarray(y), np.asarray(s)
    obs = roc_auc_score(y, s)
    ge = sum(roc_auc_score(RNG.permutation(y), s) >= obs for _ in range(n))
    return round((ge + 1) / (n + 1), 4)


# ---------------------------------------------------------------- R statistics
def cluster_boot_diff(R_pick, g_pick, R_all, g_all, n=2000):
    """95% CI of mean(picked) - mean(all), resampling clusters (symbol-day) within each set."""
    def boot(R, g):
        g = np.asarray(g)
        u, inv = np.unique(g, return_inverse=True)
        sums = np.bincount(inv, weights=R); cnt = np.bincount(inv)
        out = np.empty(n)
        for i in range(n):
            p = RNG.integers(0, len(u), len(u))
            out[i] = sums[p].sum() / max(cnt[p].sum(), 1)
        return out
    d = boot(np.asarray(R_pick), g_pick) - boot(np.asarray(R_all), g_all)
    return [round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)]


def random_subset_p(R_all, k, obs_mean, n=5000):
    R_all = np.asarray(R_all)
    if k == 0:
        return None
    m = np.array([R_all[RNG.integers(0, len(R_all), k)].mean() for _ in range(n)])
    return round(float(((m >= obs_mean).sum() + 1) / (n + 1)), 4)


def strat_null_p(pick_strata, all_strata, all_R, pick_R, n=3000):
    """null: replace each pick by a random candidate from the same stratum (time slot x side). Vectorised.
    Draws are independent, so picks that share a symbol-day are treated as independent: p is too small when picks
    cluster. Use strat_null_cluster (symbol-day cluster bootstrap) for the p-values that are quoted."""
    all_strata = np.asarray(all_strata); all_R = np.asarray(all_R, float); pick_strata = np.asarray(pick_strata)
    keys, counts = np.unique(pick_strata, return_counts=True)
    obs = float(np.mean(pick_R))
    sims = np.zeros(n)
    for k, c in zip(keys, counts):
        pool = all_R[all_strata == k]
        if len(pool) == 0:
            pool = all_R
        sims += pool[RNG.integers(0, len(pool), (n, c))].sum(axis=1)
    sims /= counts.sum()
    return round(float(sims.mean()), 3), round(float(((sims >= obs).sum() + 1) / (n + 1)), 4)


def strat_null_cluster(pick_strata, pick_cl, pick_R, all_strata, all_R, n=3000):
    """symbol-day cluster bootstrap of the stratum-adjusted edge. excess_i = R_i - mean R of all candidates in the
    same stratum (time slot x side); resample the pick clusters (symbol-day) with replacement n times and take the
    mean excess of each resample. -> (edge, [2.5, 97.5] CI, one-sided p = share of resamples with edge <= 0).
    Picks on the same symbol-day move together, so this p is wider than strat_null_p's."""
    all_strata = np.asarray(all_strata); all_R = np.asarray(all_R, float)
    pick_strata = np.asarray(pick_strata); pick_R = np.asarray(pick_R, float)
    keys = np.unique(all_strata)
    mu = {k: float(all_R[all_strata == k].mean()) for k in keys}
    mall = float(all_R.mean())
    ex = pick_R - np.array([mu.get(k, mall) for k in pick_strata])
    u, inv = np.unique(np.asarray(pick_cl), return_inverse=True)
    sums = np.bincount(inv, weights=ex); cnt = np.bincount(inv)
    boot = np.empty(n)
    for i in range(n):
        p = RNG.integers(0, len(u), len(u))
        boot[i] = sums[p].sum() / max(cnt[p].sum(), 1)
    return (round(float(ex.mean()), 3), [round(float(np.percentile(boot, 2.5)), 3), round(float(np.percentile(boot, 97.5)), 3)],
            round(float(((boot <= 0).sum() + 1) / (n + 1)), 4))


def summ(R):
    R = np.asarray(R, float)
    if len(R) == 0:
        return dict(n=0, meanR=None, win=None)
    return dict(n=int(len(R)), meanR=round(float(R.mean()), 3), win=round(100 * float((R > 0).mean()), 1))


def slot(tod):
    """time-of-day strata (minutes after 09:30): 0-5-10-15-20-30-45-60-90"""
    return np.digitize(tod, [5, 10, 15, 20, 30, 45, 60]).astype(str)


# ---------------------------------------------------------------- analysis
def population_eval(A, nqc, do_nq, exclude_marked=False):
    """exclude_marked: models are trained exactly as before (labels included), but the evaluated candidates (picks AND
    the pool they are compared with) drop every row he marked (S/A/B/C/none), so no row he saw with hindsight is scored."""
    A = A.copy()
    A["cl"] = A["sym"] + "_" + A["day"]
    A["sl"] = [a + b for a, b in zip(slot(A["tod"].to_numpy()), A["side"].astype(str))]
    yA = (A["lab"] == "S").astype(int).to_numpy()
    folds = wf_folds(A["day"], 4, 0.4)
    cuts = [A["day"].to_numpy()[te].min() for _, te in folds]
    out = {"n": len(A), "n_S": int(yA.sum()), "cut_dates": cuts, "folds": []}
    keys = ("l2_l1", "l2_tree", "l1model_on_all", "tree_on_all")
    P = {k: dict(R=[], cl=[], sl=[], S=[]) for k in keys}
    aR, aC, aS, ay = [], [], [], []
    sc = {"l1": [], "tree": [], "tod": []}
    nqP = {"l1": dict(R=[], cl=[], first=[]), "tree": dict(R=[], cl=[], first=[])}
    nqA = dict(R=[], cl=[])
    for fi, (tr, te) in enumerate(folds):
        cut = cuts[fi]
        tr_df, te_df = A.iloc[tr], A.iloc[te]
        ev = (~te_df["lab"].isin(LAB)).to_numpy() if exclude_marked else np.ones(len(te_df), bool)
        aR.append(te_df["R"].to_numpy()[ev]); aC.append(te_df["cl"].to_numpy()[ev]); aS.append(te_df["sl"].to_numpy()[ev]); ay.append(yA[te][ev])
        lab_tr = tr_df[tr_df["lab"].isin(LAB)]
        yl = (lab_tr["lab"] == "S").astype(int).to_numpy()
        mt = make_model("l1", tr_df[["tod"]], yA[tr])
        sc["tod"].append(score(mt, te_df[["tod"]]))
        for kind in ("l1", "tree"):
            mp = make_model(kind, tr_df[FEATURES], yA[tr])
            s_tr, s_te = score(mp, tr_df[FEATURES]), score(mp, te_df[FEATURES])
            sc[kind].append(s_te)
            mm = make_model(kind, lab_tr[FEATURES], yl)
            s_tr2, s_te2 = score(mm, tr_df[FEATURES]), score(mm, te_df[FEATURES])
            for key, st_, se_ in (("l2_" + kind, s_tr, s_te), ("l1model_on_all" if kind == "l1" else "tree_on_all", s_tr2, s_te2)):
                take = (se_ >= np.quantile(st_, 0.90)) & ev
                P[key]["R"].append(te_df["R"].to_numpy()[take]); P[key]["cl"].append(te_df["cl"].to_numpy()[take])
                P[key]["sl"].append(te_df["sl"].to_numpy()[take]); P[key]["S"].append(int(yA[te][take].sum()))
            if do_nq:
                nxt = [c for c in cuts if c > cut]
                block = nqc[nqc["day"] >= cut]
                if nxt:
                    block = block[block["day"] < nxt[0]]
                train_nq = nqc[nqc["day"] < cut]
                if len(block) and len(train_nq):
                    thr_nq = np.quantile(score(mm, train_nq[FEATURES]), 0.90)    # scores only, no outcomes
                    tk = score(mm, block[FEATURES]) >= thr_nq
                    nqP[kind]["R"].append(block["R"].to_numpy()[tk]); nqP[kind]["cl"].append(block["day"].to_numpy()[tk])
                    nqP[kind]["first"].append(block["first_of_day"].to_numpy()[tk])
                    if kind == "l1":
                        nqA["R"].append(block["R"].to_numpy()); nqA["cl"].append(block["day"].to_numpy())
        out["folds"].append({"cut": cut, "n_test": int(len(te))})
    aR, aC, aS, ay = (np.concatenate(x) for x in (aR, aC, aS, ay))
    out["oos_all"] = summ(aR)
    if not exclude_marked:      # with his marked rows removed there is no S left to score
        out["oos_his_S"] = summ(aR[ay == 1])
        for kind in ("l1", "tree", "tod"):
            s = np.concatenate(sc[kind])
            out[f"auc_{kind}_pooled"] = round(float(roc_auc_score(ay, s)), 3)
            out[f"auc_{kind}_ci"] = boot_auc(ay, s, aC, n=300)
    out["picks"] = {}
    for key in keys:
        R = np.concatenate(P[key]["R"]); cl = np.concatenate(P[key]["cl"]); sl = np.concatenate(P[key]["sl"])
        d = summ(R)
        d["his_S_inside_picks"] = int(sum(P[key]["S"]))
        if len(R) > 5:
            d["diff_vs_all_ci"] = cluster_boot_diff(R, cl, aR, aC)
            d["p_randsubset"] = random_subset_p(aR, len(R), float(R.mean()))
            d["slot_matched_null_mean"], d["p_slot_matched_iid"] = strat_null_p(sl, aS, aR, R)
            d["slot_matched_edge"], d["slot_matched_edge_ci_cluster"], d["p_slot_matched_cluster"] = \
                strat_null_cluster(sl, cl, R, aS, aR)
        out["picks"][key] = d
    if do_nq:
        na = np.concatenate(nqA["R"]) if nqA["R"] else None
        nc = np.concatenate(nqA["cl"]) if nqA["R"] else None
        out["nq_transfer"] = {"all_nq_candidates_oos": summ(na) if na is not None else None}
        for kind in ("l1", "tree"):
            if nqP[kind]["R"]:
                R = np.concatenate(nqP[kind]["R"]); cl = np.concatenate(nqP[kind]["cl"])
                d = summ(R)
                d["first_of_day_share"] = round(float(np.concatenate(nqP[kind]["first"]).mean()), 3)
                if len(R) > 5:
                    d["diff_vs_all_ci"] = cluster_boot_diff(R, cl, na, nc)
                    d["p_randsubset"] = random_subset_p(na, len(R), float(R.mean()))
                out["nq_transfer"][f"picks_{kind}"] = d
    return out


def main(datadir, outjson):
    st = pd.read_csv(os.path.join(datadir, "stock.csv.gz"))
    nqc = pd.read_csv(os.path.join(datadir, "nq.csv.gz"))
    lab = pd.read_csv(os.path.join(datadir, "labeled_nqctx.csv.gz"))
    res = {}

    # --- his S trades' own R (hindsight caveat applies; see t04) ---------------------------------
    st["cl"] = st["sym"] + "_" + st["day"]
    st["sl"] = [a + b for a, b in zip(slot(st["tod"].to_numpy()), st["side"].astype(str))]
    unm = st[st["lab"] == "unmarked"]
    his = {}
    for g in ["S", "A", "B", "C", "none"]:
        s = st[st["lab"] == g]
        d = summ(s["R"])
        if g in ("S", "A", "C", "none") and len(s):
            d["ci_vs_unmarked"] = cluster_boot_diff(s["R"], s["cl"], unm["R"], unm["cl"])
            d["null_mean"], d["p_stratified_iid"] = strat_null_p(s["sl"], unm["sl"], unm["R"].to_numpy(), s["R"].to_numpy())
            d["edge_cluster"], d["edge_ci_cluster"], d["p_stratified_cluster"] = \
                strat_null_cluster(s["sl"], s["cl"], s["R"], unm["sl"], unm["R"].to_numpy())
        his[g] = d
    his["unmarked_all"] = summ(unm["R"])
    s_rows = st[st["lab"] == "S"]
    mid = s_rows["day"].sort_values().iloc[len(s_rows) // 2]
    his["S_h1"] = summ(s_rows[s_rows["day"] < mid]["R"]); his["S_h2"] = summ(s_rows[s_rows["day"] >= mid]["R"])
    his["S_split_date"] = mid
    his["S_how"] = s_rows["how"].value_counts().to_dict()
    res["his_S_R"] = his

    # --- L1: S vs his Not-S (A/B/C/none) among matched marks ------------------------------------
    L = st[st["lab"].isin(LAB)].reset_index(drop=True)
    y = (L["lab"] == "S").astype(int).to_numpy()
    L1 = {"n": len(L), "n_S": int(y.sum()), "base_rate": round(float(y.mean()), 3), "models": {}}
    sets = {"features": FEATURES, "tod_only": ["tod"], "tod+side": ["tod", "is_long"]}
    for name, cols in sets.items():
        for kind in (["tree", "l1"] if name == "features" else ["l1"]):
            w = walk_forward_auc(L[cols], y, L["day"], kind)
            e = {"auc": round(w["auc"], 3), "fold_auc": w["fold_auc"], "n_oos": w["n"], "n_S_oos": w["n_pos"]}
            e["auc_ci"] = boot_auc(y[w["idx"]], w["score"], L["cl"].to_numpy()[w["idx"]])
            e["perm_p"] = perm_auc_p(y[w["idx"]], w["score"])
            L1["models"][f"{name}/{kind}"] = e
            if name == "features":
                # rule takes: predicted-S (score >= train-balanced 0.5) among marked OOS rows
                take = w["score"] >= 0.5
                R = L["R"].to_numpy()[w["idx"]]
                gcl = L["cl"].to_numpy()[w["idx"]]
                e["marked_oos_all"] = summ(R)
                e["marked_oos_takes"] = summ(R[take])
                e["marked_oos_skips"] = summ(R[~take])
                if take.sum() > 5 and (~take).sum() > 5:
                    e["takes_minus_all_ci"] = cluster_boot_diff(R[take], gcl[take], R, gcl)
                    e["takes_p_randsubset"] = random_subset_p(R, int(take.sum()), float(R[take].mean()))
                e["his_S_oos"] = summ(R[y[w["idx"]] == 1])
    # NQ market-context add-on (rows with NQ context only; sessions after the reserved window)
    LL = lab[lab["lab"].isin(LAB)].reset_index(drop=True)
    LL = LL[LL["nq_mom15_atr"].notna()].reset_index(drop=True)
    yy = (LL["lab"] == "S").astype(int).to_numpy()
    ctx = {"n": len(LL), "n_S": int(yy.sum())}
    for name, cols in {"own": FEATURES, "own+nq_ctx": FEATURES + NQ_CTX}.items():
        w = walk_forward_auc(LL[cols], yy, LL["day"], "l1")
        ctx[name] = {"auc": round(w["auc"], 3), "fold_auc": w["fold_auc"], "n_oos": w["n"],
                     "auc_ci": boot_auc(yy[w["idx"]], w["score"], (LL["sym"] + LL["day"]).to_numpy()[w["idx"]])}
    L1["nq_context_test"] = ctx
    res["L1_S_vs_notS"] = L1

    # --- L2: S vs other engine candidates; the rule takes the top decile of score ------------------------------
    res["L2_all_candidates"] = population_eval(st.dropna(subset=["R"]).reset_index(drop=True), nqc, do_nq=True)
    judged = st[(st["lab"] != "unmarked")].dropna(subset=["R"]).reset_index(drop=True)
    res["L2_judged_days_only"] = population_eval(judged, nqc, do_nq=False)
    res["L2_judged_days_unmarked_only"] = population_eval(judged, nqc, do_nq=False, exclude_marked=True)


    # --- final fit on all labels: the rule as it would be written down (descriptive, not a result) ------
    m_l1 = make_model("l1", L[FEATURES], y)
    coefs = m_l1[-1].coef_[0]
    scaler = m_l1[1]
    imp = m_l1[0]
    res["final_l1"] = {"C": float(m_l1[-1].C_[0]),
                       "coef_std": {f: round(float(c), 3) for f, c in zip(FEATURES, coefs) if abs(c) > 1e-9},
                       "median": {f: round(float(v), 4) for f, v in zip(FEATURES, imp.statistics_)},
                       "scale": {f: round(float(v), 4) for f, v in zip(FEATURES, scaler.scale_)},
                       "mean": {f: round(float(v), 4) for f, v in zip(FEATURES, scaler.mean_)},
                       "intercept": round(float(m_l1[-1].intercept_[0]), 4)}
    m_t = make_model("tree", L[FEATURES], y)
    res["final_tree_text"] = export_text(m_t[-1], feature_names=FEATURES)
    # feature-level AUCs (single feature vs S, marked rows) for the descriptive table
    fa = {}
    for f in FEATURES:
        v = L[f]
        ok = v.notna()
        if ok.sum() > 30 and len(set(y[ok])) == 2:
            fa[f] = round(float(roc_auc_score(y[ok], v[ok])), 3)
    res["single_feature_auc_in_sample"] = fa
    json.dump(res, open(outjson, "w"), indent=1, default=str)
    return res


if __name__ == "__main__":
    r = main(sys.argv[1], sys.argv[2])
    print(json.dumps({k: r[k] for k in ("his_S_R", "L1_S_vs_notS")}, indent=1, default=str)[:6000])
