"""eye1: train an interpretable S classifier on Austin's marks, test OOS by date.

Split = o2: train marks before 2026-03-04, test on/after.
Label = 1 if grade == S, 0 if one-off / two-off.
Primary (pre-declared) model = L2 logistic regression, C picked by 5-fold CV on
train. Secondary = depth-2 gradient boosting, reported only as a check.

Run: python train_eval.py [--csv path/to/s_trades.csv]
Writes model.json (primary) and results.json next to this file.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from eye1_features import FEATURES, featurize

HERE = Path(__file__).parent
SPLIT = "2026-03-04"
NPERM = 5000
RNG = np.random.default_rng(7)


def matrix(df):
    return np.array([[np.nan if v is None else v for v in featurize(r)]
                     for r in df.to_dict("records")], dtype=float)


def perm_p(stat_fn, y, obs, n=NPERM):
    hits = 0
    for _ in range(n):
        if stat_fn(RNG.permutation(y)) >= obs:
            hits += 1
    return (hits + 1) / (n + 1)


def split_R(mask, R):
    return float(np.nanmean(R[mask])) if mask.any() else float("nan"), \
        float(np.nanmean(R[~mask])) if (~mask).any() else float("nan")


def r_diff_p(mask, R, n=NPERM):
    """One-sided: is mean R of the flagged set above the rest by more than a random
    same-size subset would be?"""
    a, b = split_R(mask, R)
    obs = a - b
    hits = 0
    for _ in range(n):
        m = RNG.permutation(mask)
        x, y = split_R(m, R)
        if x - y >= obs:
            hits += 1
    return obs, (hits + 1) / (n + 1)


def evaluate(name, p, y, df):
    out = {"model": name, "n": int(len(y)), "base_rate": float(y.mean())}
    auc = roc_auc_score(y, p)
    out["auc"] = auc
    out["auc_perm_p"] = perm_p(lambda yy: roc_auc_score(yy, p), y, auc)
    out["brier"] = brier_score_loss(y, p)
    out["brier_baseline"] = brier_score_loss(y, np.full_like(p, y.mean()))
    # calibration: quartile bins + logistic recalibration slope/intercept
    q = pd.qcut(p, 4, labels=False, duplicates="drop")
    out["calib_bins"] = [
        {"bin": int(b), "n": int((q == b).sum()), "mean_p": float(p[q == b].mean()),
         "obs_S": float(y[q == b].mean())} for b in sorted(set(q))]
    lp = np.log(np.clip(p, 1e-6, 1 - 1e-6) / np.clip(1 - p, 1e-6, 1))
    rc = LogisticRegression(C=1e6).fit(lp.reshape(-1, 1), y)
    out["calib_slope"] = float(rc.coef_[0, 0])
    out["calib_intercept"] = float(rc.intercept_[0])
    # precision at top 30%
    k = int(round(0.3 * len(y)))
    top = np.zeros(len(y), bool)
    top[np.argsort(-p, kind="stable")[:k]] = True
    prec = y[top].mean()
    out["top30_k"] = k
    out["prec_top30"] = float(prec)
    out["prec_top30_perm_p"] = perm_p(lambda yy: yy[top].mean(), y, prec)
    # mean R: predicted-S (p >= 0.5) vs predicted-not-S, and top30 vs rest
    predS = p >= 0.5
    out["n_predS"] = int(predS.sum())
    out["predS_is_his_S"] = float(y[predS].mean()) if predS.any() else float("nan")
    for rcol in ("R2_eng", "R2_wick"):
        R = df[rcol].to_numpy(float)
        a, b = split_R(predS, R)
        d, pp = r_diff_p(predS, R)
        out[rcol] = {"predS_R": a, "predNotS_R": b, "diff": d, "perm_p": pp}
        a, b = split_R(top, R)
        d, pp = r_diff_p(top, R)
        out[rcol]["top30_R"] = a
        out[rcol]["rest_R"] = b
        out[rcol]["top30_diff"] = d
        out[rcol]["top30_perm_p"] = pp
        his = y.astype(bool)
        a, b = split_R(his, R)
        out[rcol]["his_S_R"] = a
        out[rcol]["his_notS_R"] = b
        out[rcol]["his_eye"] = a - b
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(HERE / "s_trades.csv"))
    args = ap.parse_args()
    df = pd.read_csv(args.csv)
    df = df[df.grade.isin(["S", "one-off", "two-off"])].reset_index(drop=True)
    y_all = (df.grade == "S").astype(int).to_numpy()
    tr = (df.date < SPLIT).to_numpy()
    te = ~tr
    X = matrix(df)
    med = np.nanmedian(X[tr], axis=0)
    X = np.where(np.isnan(X), med, X)
    mu, sd = X[tr].mean(0), X[tr].std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    ytr, yte = y_all[tr], y_all[te]

    # --- primary: logistic, C by CV on train
    skf = StratifiedKFold(5, shuffle=True, random_state=0)
    cv = {}
    for C in (0.01, 0.03, 0.1, 0.3, 1.0, 3.0):
        pcv = cross_val_predict(LogisticRegression(C=C, max_iter=2000), Z[tr], ytr,
                                cv=skf, method="predict_proba")[:, 1]
        cv[C] = roc_auc_score(ytr, pcv)
    C = max(cv, key=cv.get)
    lr = LogisticRegression(C=C, max_iter=2000).fit(Z[tr], ytr)
    p_lr = lr.predict_proba(Z[te])[:, 1]

    # --- secondary: shallow GBM (raw features, trees need no scaling)
    gb = GradientBoostingClassifier(n_estimators=150, max_depth=2, learning_rate=0.05,
                                    subsample=0.8, random_state=0).fit(X[tr], ytr)
    p_gb = gb.predict_proba(X[te])[:, 1]
    gb_cv = roc_auc_score(ytr, cross_val_predict(
        GradientBoostingClassifier(n_estimators=150, max_depth=2, learning_rate=0.05,
                                   subsample=0.8, random_state=0),
        X[tr], ytr, cv=skf, method="predict_proba")[:, 1])

    dte = df[te].reset_index(drop=True)
    res = {
        "split": SPLIT, "n_train": int(tr.sum()), "n_test": int(te.sum()),
        "S_train": int(ytr.sum()), "S_test": int(yte.sum()),
        "features": FEATURES,
        "logit_cv_auc_by_C": {str(k): v for k, v in cv.items()}, "logit_C": C,
        "gbm_train_cv_auc": gb_cv,
        "logit_coef_std": dict(zip(FEATURES, lr.coef_[0].tolist())),
        "gbm_importance": dict(zip(FEATURES, gb.feature_importances_.tolist())),
        "test_logit": evaluate("logit", p_lr, yte, dte),
        "test_gbm": evaluate("gbm", p_gb, yte, dte),
    }
    model = {"type": "logistic_l2", "C": C, "features": FEATURES,
             "median": med.tolist(), "mean": mu.tolist(), "std": sd.tolist(),
             "coef": lr.coef_[0].tolist(), "intercept": float(lr.intercept_[0]),
             "trained_on": f"s_trades.csv grade S vs one-off/two-off, date < {SPLIT}",
             "n_train": int(tr.sum())}
    (HERE / "model.json").write_text(json.dumps(model, indent=2))
    (HERE / "results.json").write_text(json.dumps(res, indent=2, default=float))
    # test predictions for audit
    dte.assign(y=yte, p_logit=p_lr, p_gbm=p_gb)[
        ["sig_id", "date", "grade", "y", "p_logit", "p_gbm", "R2_eng", "R2_wick"]
    ].to_csv(HERE / "test_predictions.csv", index=False)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
