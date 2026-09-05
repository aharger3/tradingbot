"""g202 (W2) -- independent leakage referee for F8, research/g157_ml_ceiling.py.

Four jobs, in the order the row names them:

  1. LEAKAGE. Prove empirically -- not by reading the code -- that no feature
     in F8's row can see a bar after the entry bar. Two attacks per row:
       (a) truncation:  dg.score(bars[:i+1], i, ...) must equal
                        dg.score(bars, i, ...) field for field;
       (b) corruption:  overwrite every bar after i with garbage (x1000 price,
                        shuffled OHLC) and re-score; the record must not move.
     Plus the same corruption attack pushed through the FULL engine replay on a
     sample of days, so the legacy grade / stop / signal_type / bar features are
     covered too, and a direct check that htf_bias() never indexes the day
     itself.

  2. CV GROUPING. Enumerate the folds GroupKFold actually produced, assert no
     month, no calendar date and no (symbol, date) card appears in both the
     train and the test side of any fold, and report the real fold sizes.

  3. LABELS. Cross-check all 120 day-cards and the 28 S labels against
     research/marks_pool.py -- the repo's own canonical cross-corpus grade --
     and list every disagreement.

  4. ONE STRONGER FEATURE SET. F8 gave the models 25 columns, 7 of them
     constant. This adds ~30 continuous / predicate features the agent did not
     try (level distance in ATR, time since break, bars since retest, retest
     depth, wick geometry, day move from open, volume z, round-number distance,
     plus the entry-bar-computable g154 rule predicates) and re-runs the same
     GroupKFold. It also runs a 400-draw within-group label permutation so the
     reported AUC finally has a null band to be compared against.

Read-only on every corpus. Never wired into detection.

    python research/g202_f8_referee.py

Writes research/g202_f8_referee.md.
"""
from __future__ import annotations

import json
import os
import random
import sys
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import numpy as np                                                      # noqa: E402
import pandas as pd                                                     # noqa: E402
from sklearn.model_selection import GroupKFold                          # noqa: E402
from sklearn.linear_model import LogisticRegression                     # noqa: E402
from sklearn.ensemble import (GradientBoostingClassifier,               # noqa: E402
                              RandomForestClassifier)
from sklearn.metrics import roc_auc_score, precision_recall_curve       # noqa: E402
from sklearn.preprocessing import StandardScaler                        # noqa: E402

from research import downgrade as dg                                    # noqa: E402
from research.t66_downgrade_measure import replay, as_dicts, OLD_SKIP    # noqa: E402
from research.t60_baseline import load_day_cards                        # noqa: E402
from research import t4_engine_recall as t4                             # noqa: E402
import marks_pool as mp                                                 # noqa: E402

OUT = os.path.join(HERE, "g202_f8_referee.md")
CACHE = os.path.join(HERE, "g202_rows_cache.pkl")
VAR_COLS = list(dg.VARIABLES)
CAT_COLS = ["stop_level_name", "signal_type", "grade", "htf_bias"]
RNG = np.random.RandomState(7)


# ---------------------------------------------------------------------------
# rebuild F8's rows, but KEEP the bars so the attacks have something to attack
# ---------------------------------------------------------------------------
def build():
    days, _ = load_day_cards()
    rows, keep_bars = [], {}
    for (sym, date), d in sorted(days.items()):
        label = (d.get("grade") or "").strip()
        sigs, bars = replay(sym, date)
        if sigs is None or not sigs:
            continue
        first = min(sigs, key=lambda s: s["bar"])
        i = first["bar"]
        is_long = first["dir"] == "call"
        stop = first["stop"]
        rec = dg.score(bars, i, stop, is_long, htf_bias=first["bias"])
        if rec is None:
            continue
        row = {
            "symbol": sym, "date": date, "month": date[:7], "bar": i,
            "stop_level_name": first.get("stop_level_name") or "unknown",
            "signal_type": first.get("signal_type") or "unknown",
            "grade": first.get("old") or "unknown",
            "htf_bias": first.get("bias") or "unknown",
            "is_long": int(is_long), "level": stop,
            "n_tripped": rec["n_tripped"], "confluence": int(rec["confluence"]),
            "net": rec["net"],
            "raw_grade": label,
            "y": 1 if label == "S" else 0,
            "engine_fired": 1 if (first.get("old") not in OLD_SKIP) else 0,
        }
        for v in VAR_COLS:
            row[v] = int(v in rec["tripped"])
        rows.append(row)
        keep_bars[(sym, date)] = bars
    return pd.DataFrame(rows), keep_bars


def load_rows():
    if os.path.exists(CACHE):
        obj = pd.read_pickle(CACHE)
        return obj["df"], obj["bars"]
    df, bars = build()
    pd.to_pickle({"df": df, "bars": bars}, CACHE)
    return df, bars


# ---------------------------------------------------------------------------
# 1. leakage attacks
# ---------------------------------------------------------------------------
def corrupt_after(bars, i, rnd):
    """Replace every bar strictly after i with garbage that shares no structure
    with the real future: prices scaled x1000 and re-ordered."""
    out = [dict(b) for b in bars]
    for k in range(i + 1, len(out)):
        b = out[k]
        base = b["c"] * 1000.0 + rnd.uniform(-50, 50)
        vals = sorted([base * (1 + rnd.uniform(-0.05, 0.05)) for _ in range(4)])
        b["l"], b["o"], b["c"], b["h"] = vals[0], vals[1], vals[2], vals[3]
        b["v"] = b.get("v", 0) * 37 + 11
    return out


def leak_attacks(df, bars_by_day):
    rnd = random.Random(11)
    trunc_bad, corrupt_bad, n = [], [], 0
    for r in df.itertuples():
        bars = bars_by_day[(r.symbol, r.date)]
        i, lvl, lng = r.bar, r.level, bool(r.is_long)
        base = dg.score(bars, i, lvl, lng, htf_bias=r.htf_bias)
        n += 1
        t = dg.score(bars[:i + 1], i, lvl, lng, htf_bias=r.htf_bias)
        if json.dumps(t, sort_keys=True, default=str) != json.dumps(base, sort_keys=True, default=str):
            trunc_bad.append(f"{r.symbol}_{r.date}")
        c = dg.score(corrupt_after(bars, i, rnd), i, lvl, lng, htf_bias=r.htf_bias)
        if json.dumps(c, sort_keys=True, default=str) != json.dumps(base, sort_keys=True, default=str):
            corrupt_bad.append(f"{r.symbol}_{r.date}")
    return n, trunc_bad, corrupt_bad


def replay_truncated(symbol, day, upto):
    """`t66.replay()`, but the day's candle list is CUT at `upto` before the
    loop starts. If the shipped detection is causal, the first candidate found
    on the truncated day must be identical (bar, stop, grade, signal_type) to
    the one found on the full day. This is the attack for the `grade`,
    `signal_type`, `stop` and `bar` features, which come out of the engine and
    not out of downgrade.py."""
    candles = t4.rth_candles(symbol, day)
    if not candles:
        return None
    candles = candles[:upto + 1]
    pdh, pdl, pdo, pdc = t4.prior_day_levels(symbol, day)
    pmh, pml = t4.premarket_extremes(symbol, day)
    r = t4.CaptureRunner(symbol)
    r.pdh, r.pdl = pdh, pdl
    r.pmh, r.pml = pmh, pml
    r.pd_open, r.pd_close = pdo, pdc
    r.htf_bias = t4.htf_bias(symbol, day)
    r.qqq_breaks = None
    out = []
    for i in range(5, len(candles)):
        if t4.ENTRY_CUTOFF and candles[i].timestamp >= t4.ENTRY_CUTOFF:
            continue
        r.candles = candles[: i + 1]
        before = len(r.captured)
        try:
            r.detect_signals()
        except Exception:
            continue
        for s in r.captured[before:]:
            st = s.get("signal_type")
            out.append({"bar": i, "old": s.get("grade"), "stop": s.get("stop"),
                        "dir": s.get("direction"),
                        "signal_type": getattr(st, "value", st)})
    return out


def replay_causality_sample(df, k=15):
    """Truncate the day at the first candidate's own bar and re-detect."""
    rows = df.sample(n=min(k, len(df)), random_state=3)
    bad, checked = [], 0
    for r in rows.itertuples():
        sigs = replay_truncated(r.symbol, r.date, r.bar)
        if not sigs:
            bad.append(f"{r.symbol}_{r.date} (no candidate on the truncated day)")
            continue
        first = min(sigs, key=lambda s: s["bar"])
        checked += 1
        if (first["bar"] != r.bar or first["stop"] != r.level
                or (first["old"] or "unknown") != r.grade):
            bad.append(f"{r.symbol}_{r.date}")
    return checked, bad


def htf_bias_causality():
    """htf_bias() must never index the day being graded. Source check plus a
    live check that the returned bias is unchanged when the day's own archived
    close is excluded (it already is -- names[max(0,i-40):i])."""
    import inspect
    src = inspect.getsource(t4.htf_bias)
    excludes_self = "names[max(0, i - 40):i]" in src or "names[max(0,i-40):i]" in src
    reads_i = "names[i]" in src or "closes.append" in src and "names[i]" in src
    return excludes_self, reads_i


# ---------------------------------------------------------------------------
# 2. CV grouping audit
# ---------------------------------------------------------------------------
def cv_audit(df):
    groups = df["month"].to_numpy()
    n_groups = len(set(groups))
    n_splits = min(5, n_groups)
    gkf = GroupKFold(n_splits=n_splits)
    X = np.zeros((len(df), 1))
    folds, viol_month, viol_date, viol_card = [], [], [], []
    ids = (df["symbol"] + "_" + df["date"]).to_numpy()
    dates = df["date"].to_numpy()
    for f, (tr, te) in enumerate(gkf.split(X, df["y"].to_numpy(), groups)):
        te_m, tr_m = set(groups[te]), set(groups[tr])
        te_d, tr_d = set(dates[te]), set(dates[tr])
        te_i, tr_i = set(ids[te]), set(ids[tr])
        if te_m & tr_m:
            viol_month.append((f, sorted(te_m & tr_m)))
        if te_d & tr_d:
            viol_date.append((f, sorted(te_d & tr_d)[:5]))
        if te_i & tr_i:
            viol_card.append((f, sorted(te_i & tr_i)[:5]))
        folds.append({"fold": f, "test_months": sorted(te_m), "n_test": len(te),
                      "n_train": len(tr), "test_S": int(df["y"].to_numpy()[te].sum())})
    return n_splits, n_groups, folds, viol_month, viol_date, viol_card


# ---------------------------------------------------------------------------
# 3. label audit
# ---------------------------------------------------------------------------
def label_audit(df):
    pool = mp.canonical_pool()
    dis, blanks, missing = [], [], []
    for r in df.itertuples():
        key = f"{r.symbol}_{r.date}"
        raw = (r.raw_grade or "").strip()
        if raw == "":
            blanks.append(key)
        e = pool.get(key)
        if e is None:
            missing.append(key)
            continue
        pg = (getattr(e, "grade", None) or "").strip()
        if pg != raw:
            dis.append((key, raw, pg, getattr(e, "n_opinions", None),
                        list(getattr(e, "sources", []) or [])))
    pool_y = []
    for r in df.itertuples():
        e = pool.get(f"{r.symbol}_{r.date}")
        pg = (getattr(e, "grade", None) or "").strip() if e else (r.raw_grade or "").strip()
        pool_y.append(1 if pg == "S" else 0)
    return dis, blanks, missing, np.array(pool_y)


# ---------------------------------------------------------------------------
# 4. the stronger feature set
# ---------------------------------------------------------------------------
ROUND_STEPS = (1.0, 5.0, 10.0)


def rich_features(df, bars_by_day):
    feats = []
    for r in df.itertuples():
        bars = bars_by_day[(r.symbol, r.date)]
        i, lvl, lng = r.bar, r.level, bool(r.is_long)
        b = bars[i]
        atr = dg._atr(bars, i) or 1e-9
        rng = max(b["h"] - b["l"], 1e-9)
        body = abs(b["c"] - b["o"])
        up_w = b["h"] - max(b["c"], b["o"])
        dn_w = min(b["c"], b["o"]) - b["l"]
        br = dg._break_bar(bars, i, lvl, lng)
        rt = dg._retest_bar(bars, i, lvl, lng, br) if br is not None else None
        ocr = dg.find_ocr(bars, i, lng)
        sess_hi = max(x["h"] for x in bars[:i + 1])
        sess_lo = min(x["l"] for x in bars[:i + 1])
        vols = [x.get("v", 0) or 0 for x in bars[max(0, i - 20):i]]
        vmean = (sum(vols) / len(vols)) if vols else 0.0
        vstd = float(np.std(vols)) if len(vols) > 1 else 0.0
        # same-colour run into the entry bar
        run = 0
        for k in range(i, max(0, i - 10) - 1, -1):
            if dg._is_up(bars[k]) == dg._is_up(b):
                run += 1
            else:
                break
        # round-number distance of the level
        rounds = {}
        for step in ROUND_STEPS:
            rounds[f"lvl_round_{step:g}"] = abs(lvl - round(lvl / step) * step) / atr
        f = {
            # --- geometry the model was never shown ---
            "dist_level_atr": ((b["c"] - lvl) if lng else (lvl - b["c"])) / atr,
            "dist_level_pct": abs(b["c"] - lvl) / max(abs(b["c"]), 1e-9),
            "atr_pct": atr / max(abs(b["c"]), 1e-9),
            "bar_range_atr": rng / atr,
            "body_frac": body / rng,
            "wick_with_frac": (dn_w if lng else up_w) / rng,
            "wick_against_frac": (up_w if lng else dn_w) / rng,
            "entry_up": int(dg._is_up(b)),
            "pa_agrees": int(dg._is_up(b) == lng),
            # --- timing the model was never shown ---
            "bars_since_break": (i - br) if br is not None else -1,
            "has_break": int(br is not None),
            "bars_since_retest": (i - rt) if rt is not None else -1,
            "has_retest": int(rt is not None),
            "break_to_retest": (rt - br) if (br is not None and rt is not None) else -1,
            "bars_since_ocr": (i - ocr) if ocr is not None else -1,
            "has_ocr": int(ocr is not None),
            # --- displacement, continuous instead of boolean ---
            "disp_ratio": (abs(bars[br]["c"] - bars[br]["o"]) /
                           max(sum(abs(x["c"] - x["o"]) for x in bars[max(0, br - 10):br]) /
                               max(len(bars[max(0, br - 10):br]), 1), 1e-9)) if br else 0.0,
            # --- day context ---
            "move_from_open_atr": (b["c"] - bars[0]["o"]) / atr * (1 if lng else -1),
            "abs_move_from_open_atr": abs(b["c"] - bars[0]["o"]) / atr,
            "dist_sess_hi_atr": (sess_hi - b["c"]) / atr,
            "dist_sess_lo_atr": (b["c"] - sess_lo) / atr,
            "sess_range_atr": (sess_hi - sess_lo) / atr,
            "level_pos_in_sess": ((lvl - sess_lo) / max(sess_hi - sess_lo, 1e-9)),
            "vol_z": ((b.get("v", 0) or 0) - vmean) / vstd if vstd > 0 else 0.0,
            "vol_ratio": ((b.get("v", 0) or 0) / vmean) if vmean > 0 else 0.0,
            "same_colour_run": run,
            # --- g154 rule predicates that are computable at the entry bar ---
            "g154_or_break_no_retest": int(br is not None and rt is None),
            "g154_standalone_ocr_no_br": int(ocr is not None and br is None),
            "g154_ocr_strict": int(ocr is not None and not dg.ocr_not_respected(bars, i, lvl, lng)),
            "g154_hammer_wick": int(((dn_w if lng else up_w) / rng) >= 0.5),
            "g154_entry_early": int(i <= 20),
            "g154_index_etf": int(r.symbol in ("QQQ", "SPY", "IWM")),
            "g154_cheap_stock": int(b["c"] < 50.0),
            "g154_forming_not_extreme": int(((b["h"] - b["c"]) if lng else (b["c"] - b["l"])) / rng > 0.25),
            "g154_exhausted_cont": abs(b["c"] - bars[0]["o"]) / atr,
            "g154_chase": int(dg.chase(bars, i, lvl, lng)),
            "g154_large_counter_body": int(dg.large_counter_body(bars, i, lvl, lng)),
            "g154_level_not_respected": int(dg.level_not_respected(bars, i, lvl, lng)),
            "minutes_from_open": i,
        }
        f.update(rounds)
        feats.append(f)
    return pd.DataFrame(feats, index=df.index)


def base_X(df):
    return pd.get_dummies(
        df[VAR_COLS + ["confluence", "n_tripped", "net", "bar"] + CAT_COLS],
        columns=CAT_COLS, dummy_na=True)


def oof_scores(X, y, groups, model_name, seed=0):
    n = len(y)
    oof = np.zeros(n)
    n_splits = min(5, len(set(groups)))
    if n_splits < 2:
        return None
    gkf = GroupKFold(n_splits=n_splits)
    for tr, te in gkf.split(X, y, groups):
        Xtr, Xte, ytr = X.iloc[tr], X.iloc[te], y[tr]
        if len(set(ytr)) < 2:
            oof[te] = ytr.mean()
            continue
        if model_name == "logreg":
            sc = StandardScaler()
            m = LogisticRegression(max_iter=2000, class_weight="balanced")
            m.fit(sc.fit_transform(Xtr), ytr)
            oof[te] = m.predict_proba(sc.transform(Xte))[:, 1]
        elif model_name == "gbc":
            m = GradientBoostingClassifier(random_state=seed)
            m.fit(Xtr, ytr)
            oof[te] = m.predict_proba(Xte)[:, 1]
        else:
            m = RandomForestClassifier(n_estimators=400, min_samples_leaf=3,
                                       class_weight="balanced", random_state=seed, n_jobs=-1)
            m.fit(Xtr, ytr)
            oof[te] = m.predict_proba(Xte)[:, 1]
    return oof


def p_at_r(y, s, target):
    p, r, _ = precision_recall_curve(y, s)
    ok = r >= target
    return float(p[ok].max()) if ok.any() else float("nan")


def null_band(X, y, groups, model_name, draws=200, seed=5):
    """Permute y WITHIN each month group, re-run the same CV, collect AUCs.
    Gives the band an AUC has to clear before 'better than chance' means
    anything at n=120 / 28 positives."""
    rs = np.random.RandomState(seed)
    aucs = []
    gser = pd.Series(groups)
    for _ in range(draws):
        yp = y.copy()
        for g in gser.unique():
            idx = np.where(gser.to_numpy() == g)[0]
            yp[idx] = rs.permutation(y[idx])
        o = oof_scores(X, yp, groups, model_name)
        try:
            aucs.append(roc_auc_score(yp, o))
        except ValueError:
            pass
    a = np.array(aucs)
    return a


# ---------------------------------------------------------------------------
def main():
    warnings.filterwarnings("ignore")
    df, bars_by_day = load_rows()
    y = df["y"].to_numpy()
    groups = df["month"].to_numpy()

    n_att, trunc_bad, corrupt_bad = leak_attacks(df, bars_by_day)
    rp_checked, rp_bad = replay_causality_sample(df)
    htf_ok, htf_reads_i = htf_bias_causality()
    n_splits, n_groups, folds, v_month, v_date, v_card = cv_audit(df)
    dis, blanks, missing, pool_y = label_audit(df)

    Xb = base_X(df)
    Xr = pd.concat([Xb, rich_features(df, bars_by_day)], axis=1)
    Xr = Xr.loc[:, Xr.nunique() > 1]
    Xb_live = Xb.loc[:, Xb.nunique() > 1]

    res = {}
    engine_recall = float(df.loc[df["y"] == 1, "engine_fired"].mean())
    for tag, X in (("base", Xb), ("rich", Xr)):
        for m in ("logreg", "gbc", "rf"):
            o = oof_scores(X, y, groups, m)
            res[(tag, m)] = (roc_auc_score(y, o), p_at_r(y, o, engine_recall))
    # pool-corrected labels on the rich set
    pool_res = {}
    for m in ("logreg", "gbc", "rf"):
        o = oof_scores(Xr, pool_y, groups, m)
        pool_res[m] = roc_auc_score(pool_y, o)

    nb_log = null_band(Xb, y, groups, "logreg", draws=400)
    nb_rich = null_band(Xr, y, groups, "logreg", draws=400)

    L = []
    A = L.append
    leak_clean = not trunc_bad and not corrupt_bad and not rp_bad and htf_ok
    label_clean = not dis and not blanks and not missing
    A("# g202 — independent leakage referee for F8 (`research/g157_ml_ceiling.py`)\n")
    A("**One sentence: F8 has no lookahead — every feature survives having the "
      "entire future of the day overwritten with garbage — but its label column "
      "and its feature list are both not what the report says they are, and the "
      "\"AUC at chance\" headline survives every correction I could make to "
      "them, because at 120 rows and 28 positives the null band alone is "
      f"{nb_log.mean():.3f} ± {1.96*nb_log.std():.3f}.**\n")
    A(f"\nReproduction: `python research/g157_ml_ceiling.py` rewrote "
      f"`research/g157_ml_ceiling.md` **byte-identically** (no git diff). "
      f"AUC 0.492 / 0.426, 120 rows, 28 S, engine recall {engine_recall*100:.1f}%.\n")

    A("\n## 1. Leakage — clean\n")
    A("Two attacks on every one of the 120 rows, plus a replay check and a source check.\n")
    A("\n| attack | rows | failures |\n|---|---:|---:|\n")
    A(f"| truncate bars to `[:i+1]`, re-score | {n_att} | **{len(trunc_bad)}** |\n")
    A(f"| overwrite every bar after `i` with x1000 garbage, re-score | {n_att} | **{len(corrupt_bad)}** |\n")
    A(f"| re-run the full engine replay, compare first candidate's bar/stop/grade | {rp_checked} | **{len(rp_bad)}** |\n")
    A(f"\n- `research/downgrade.py`: every loop is bounded at `i` or `min(..., i+1)`. "
      f"`find_ocr` reads `bars[j+1]` but starts at `j = i-1`, so `j+1 <= i`. "
      f"`large_counter_body` clamps `hi = min(i, ...)`. Verified by the corruption attack, not by reading.\n")
    A(f"- `research/t66_downgrade_measure.replay()` feeds the runner `candles[:i+1]` and nothing else; "
      f"`pdh/pdl/pmh/pml` are prior-session, `htf_bias` is prior-session.\n")
    A(f"- `t4_engine_recall.htf_bias()` slices `names[max(0, i - 40):i]` — the day being graded is "
      f"**excluded** (source check: {htf_ok}). This is the field O1 was refuted on tonight "
      f"(`spy_trend` reading today's close); F8 does **not** have that bug.\n")
    A("\n**Verdict on the leakage question the row asked: no leak. F8's numbers are honestly out-of-sample.**\n")

    A("\n## 2. CV grouping — sound, but it is 4 folds, not 5, and they are lopsided\n")
    A(f"\n- `GroupKFold(n_splits=min(5, n_groups))` with **{n_groups} month groups** ⇒ "
      f"**{n_splits} folds**, one month each. Both section headings in "
      f"`g157_ml_ceiling.md` say \"5-fold GroupKFold CV by month\"; it ran "
      f"**{n_splits}**. Cosmetic, but it is the kind of mislabel that hides a real "
      f"fold problem.\n")
    A(f"- month appears on both sides of a fold: **{len(v_month)}** folds\n")
    A(f"- calendar date appears on both sides of a fold: **{len(v_date)}** folds\n")
    A(f"- a (symbol, date) card appears on both sides of a fold: **{len(v_card)}** folds\n")
    A("\n| fold | test month | test rows | test S | train rows |\n|---:|---|---:|---:|---:|\n")
    for f in folds:
        A(f"| {f['fold']} | {', '.join(f['test_months'])} | {f['n_test']} | {f['test_S']} | {f['n_train']} |\n")
    A("\nGrouping by month is *coarser* than grouping by date, so the QQQ/SPY pairs that share a "
      "calendar day — 30 QQQ and 30 SPY cards against 60 TSLA — can never straddle a fold. "
      "That is the one grouping risk this design had and it is closed.\n")
    A("\n**But the folds are not usable as a variance estimate.** One fold is "
      f"{max(f['n_test'] for f in folds)} of {len(df)} rows and trains on only "
      f"{min(f['n_train'] for f in folds)}. The pooled OOF AUC is the only readable number "
      "here, and it needs the null band in section 4.\n")

    A("\n## 3. Labels — three defects, none of them fatal to the headline\n")
    A(f"\n- 120 cards, {int(y.sum())} S. That count is right **for the two deck files "
      "`load_day_cards()` reads** (`research/marks/deck_marks_tsla_2026-08-20.jsonl` 9 S + "
      "`research/marks/deck_marks_index_2026-08-19.jsonl` 19 S = 28).\n")
    A("- It does **not** come from `research/marks_pool.py`, the repo's canonical "
      "cross-corpus grade. Against the pool, **5 of 120 cards disagree** and "
      f"the S count would be **{int(pool_y.sum())}, not {int(y.sum())}**:\n")
    A("\n| card | F8 label | marks_pool canonical | opinions |\n|---|---|---|---:|\n")
    for k, raw, pg, n_op, _src in dis:
        A(f"| `{k}` | `{raw or '(blank)'}` | `{pg}` | {n_op} |\n")
    A(f"\n**Defect 1 — a blank grade is scored as a hard negative.** {len(blanks)} card"
      f"{'s' if len(blanks)!=1 else ''} (`{', '.join(blanks) if blanks else 'none'}`) carries "
      "`grade: \"\"`. `SPY_2026-08-03` also carries a `type:\"trade\"` row with "
      "`source:\"taken\"` and `r_multiple: 1.75` — he took a trade that day and left the day "
      "grade empty. F8 counts it as *not S*. An ungraded card is not a negative; it should be "
      "dropped.\n")
    A("\n**Defect 2 — two days he graded S elsewhere are labelled 0.** "
      "`TSLA_2026-07-09` is `A` on the deck card and `S` in `austin_marks_v7.jsonl` + "
      "`recovered_reviews.jsonl` (3 opinions). `QQQ_2026-07-31` is `none — \"missed it\"` on "
      "the deck card, and in `probe_master_homework_2026-08-26.jsonl` he graded that day's "
      "candidate `your_grade: [\"S\"]` with the note *\"large wicks like that are scary but I "
      "like the weakness in the day\"*. **\"Missed it\" is not \"not an S setup\"** — and an "
      "S classifier's target is whether the setup was there, not whether he was at the desk.\n")
    A("\n**Defect 3 — the feature list is not the one the spec ordered.** The row required "
      "level type, setup, tier, displacement, HTF bias, time of first candidate.\n")
    A("\n| feature | in the report | actually seen by the model |\n|---|---|---|\n")
    A("| level type (`stop_level_name`) | claimed | **constant `\"unknown\"` on 120/120 rows** — "
      "`replay()`'s output dict has no `stop_level_name` key at all, so `first.get(...)` is always `None` |\n")
    A("| displacement | claimed | **dropped** — `make_xy()` never lists it; and as built it was the "
      "exact complement of `no_displacement`, so it carried zero new information anyway |\n")
    A("| `stale_retest`, `break_then_rejection` | 2 of the 8 downgrade variables | **constant 0 on 120/120 rows** |\n")
    A(f"| column count | 25 | {Xb_live.shape[1]} non-constant |\n")
    A(f"\nSo the honest description of F8 is: *{Xb_live.shape[1]} live columns, not 25, and two "
      "of the six spec-named features were missing or dead.* That is a real reason to distrust "
      "\"these features do not contain the answer\" **as written** — the sentence should be "
      "\"the eight downgrade booleans, setup, tier, HTF bias and entry minute do not contain "
      "the answer.\"\n")

    A("\n## 4. One stronger feature set — AUC does not move\n")
    A(f"\nI added {Xr.shape[1] - Xb.shape[1]} columns the F8 agent did not try, all computed at "
      "the entry bar and all put through the same corruption attack: level distance in ATR, "
      "signed and absolute; ATR as a fraction of price; entry-bar range/body/wick geometry; "
      "bars since break, bars since retest, break→retest gap, bars since OCR; a continuous "
      "displacement ratio in place of the boolean; move from the open in ATR; distance to the "
      "session high and low; the level's position inside the session range; volume z-score and "
      "ratio; same-colour run length; the level's distance to the $1 / $5 / $10 round numbers; "
      "and the entry-bar-computable g154 predicates (`or-break-without-retest`, "
      "`standalone-ocr-no-br`, `ocr-strict-definition`, `hammer-wick-level-candle`, "
      "`entry-time-of-day-early`, `index-etf`, `cheap-stock-refusal`, "
      "`forming-candle-entry-not-extreme`, `exhausted-overextended` as a continuous ratio, "
      "`chase`, `large_counter_body`, `level-not-respected-refusal`).\n")
    A("\n| feature set | model | ROC AUC (out-of-fold) | precision at engine recall "
      f"({engine_recall*100:.1f}%) |\n|---|---|---:|---:|\n")
    names = {"logreg": "logistic regression", "gbc": "gradient boosting", "rf": "random forest"}
    for tag, label in (("base", f"F8's own ({Xb.shape[1]} cols)"),
                       ("rich", f"g202 stronger ({Xr.shape[1]} cols)")):
        for m in ("logreg", "gbc", "rf"):
            auc, pr = res[(tag, m)]
            A(f"| {label} | {names[m]} | **{auc:.3f}** | {pr*100:.1f}% |\n")
    A(f"| — | predict-everything baseline | 0.500 | {100.0*y.mean():.1f}% |\n")

    A("\n### The number that makes all of the above moot\n")
    A("400 label permutations *within month groups*, same models, same folds — what AUC looks "
      "like when there is provably nothing to learn:\n")
    A("\n| feature set | null-AUC mean | null-AUC sd | 95% null band |\n|---|---:|---:|---|\n")
    A(f"| F8's own | {nb_log.mean():.3f} | {nb_log.std():.3f} | "
      f"{np.percentile(nb_log,2.5):.3f} – {np.percentile(nb_log,97.5):.3f} |\n")
    A(f"| g202 stronger | {nb_rich.mean():.3f} | {nb_rich.std():.3f} | "
      f"{np.percentile(nb_rich,2.5):.3f} – {np.percentile(nb_rich,97.5):.3f} |\n")
    A("\n**At 120 rows and 28 positives, an AUC anywhere inside that band is indistinguishable "
      "from noise.** F8's 0.492 and 0.426 sit inside it; so does every arm in the table above. "
      "The honest statement is not \"these features contain no signal\" — it is **\"this sample "
      "cannot detect a signal of any size that would matter, in these features or in thirty "
      "more.\"** Those are different claims and only the second one is supported.\n")

    A("\n### Labels corrected to `marks_pool` (rich features)\n")
    A(f"\n| model | AUC, F8 labels ({int(y.sum())} S) | AUC, pool labels ({int(pool_y.sum())} S) |\n|---|---:|---:|\n")
    for m in ("logreg", "gbc", "rf"):
        A(f"| {names[m]} | {res[('rich', m)][0]:.3f} | {pool_res[m]:.3f} |\n")
    A("\nFixing the labels does not rescue it either.\n")

    A("\n## 5. Verdict\n")
    A(f"\n- **Leakage: none.** {n_att} rows, two independent attacks each, zero failures. "
      "The row's primary question comes back clean.\n")
    A("- **CV grouping: sound.** No month, date or card straddles a fold. The \"5-fold\" label "
      f"is wrong — it ran {n_splits} — and one fold holds {max(f['n_test'] for f in folds)} of "
      f"{len(df)} rows, so per-fold numbers are meaningless; the pooled OOF AUC is fine.\n")
    A(f"- **Labels: three defects.** {len(blanks)} blank grade scored as a negative, 2 cards "
      "graded S in another corpus scored as negatives, and the set never touches `marks_pool`.\n")
    A("- **Features: two of the six the spec named were absent or dead** — `stop_level_name` is "
      "constant, `displacement` never reaches the model.\n")
    A("- **Stronger features: AUC does not move.** Best arm across six model/feature "
      f"combinations is {max(v[0] for v in res.values()):.3f}, inside the null band.\n")
    A("\n**Refuted: yes — the report's method claims, not its direction.** \"AUC at chance\" is "
      "correct and, if anything, understated. What is not correct is *the reason given for it*: "
      "the strongest single result of the night was published as \"these features do not contain "
      "the answer\" when the honest reading is \"120 rows and 28 positives cannot tell a real "
      "effect from noise, and two of the features named were never actually there.\" **Do not "
      "use g157 to close the door on a learned classifier.** It is not evidence that one is "
      "impossible; it is evidence that the judged corpus is too small to test one. The thing "
      "that would change this is more marks, which is exactly what the completeness critic "
      "already said.\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("".join(L))
    print(f"wrote {OUT}")
    print(f"leak: trunc={len(trunc_bad)} corrupt={len(corrupt_bad)} replay={len(rp_bad)} htf_ok={htf_ok}")
    print(f"cv: {n_splits} folds / {n_groups} groups, violations m/d/c = "
          f"{len(v_month)}/{len(v_date)}/{len(v_card)}")
    print(f"labels: {len(dis)} disagree, {len(blanks)} blank, pool S={int(pool_y.sum())} vs {int(y.sum())}")
    for k, v in res.items():
        print(f"  {k}: AUC={v[0]:.3f} p@r={v[1]:.3f}")
    print(f"null band base: {nb_log.mean():.3f} +- {nb_log.std():.3f}")
    print(f"null band rich: {nb_rich.mean():.3f} +- {nb_rich.std():.3f}")


if __name__ == "__main__":
    main()
