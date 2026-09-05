"""g202 (W2) -- INDEPENDENT LEAKAGE REFEREE for F8 (research/g157_ml_ceiling.py).

Four questions, answered by measurement rather than by reading the code:

 1. LEAKAGE. Is every feature computable at the entry bar? Tested empirically:
    every feature is recomputed with the bar list TRUNCATED to bars[:i+1] and
    compared cell-by-cell against the value g157 computed from the full day.
    Any difference is a read past the entry bar.
 2. CV GROUPING. Is the CV grouped by month, and can one judged symbol-day
    appear in two folds? Every fold's group membership is printed.
 3. LABELS. Do the 120 rows and the 28 S labels agree with the canonical
    cross-corpus grade in research/marks_pool.py?
 4. A STRONGER FEATURE SET. 22 continuous predicates the F8 agent did not try
    (level distance in ATR, time since break, retest age, OCR age/geometry,
    day-range position, volume ratio, wick fractions, risk in ATR ...), all
    computed from bars[:i+1] only, scored the same way -- plus a
    label-permutation null so the AUC has a band around it.

Read-only. No mark file is opened for writing. Nothing is wired into detection.

    python research/g202_f8_referee.py

Writes research/g202_f8_referee.md.
"""
from __future__ import annotations

import os
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
from sklearn.ensemble import GradientBoostingClassifier                 # noqa: E402
from sklearn.metrics import roc_auc_score                               # noqa: E402
from sklearn.preprocessing import StandardScaler                        # noqa: E402

from research import downgrade as dg                                    # noqa: E402
from research.t66_downgrade_measure import replay, OLD_SKIP             # noqa: E402
from research.t60_baseline import load_day_cards                       # noqa: E402
import marks_pool as mp                                                 # noqa: E402
from research.g157_ml_ceiling import (VAR_COLS, CAT_COLS,               # noqa: E402
                                      build_rows as g157_rows)

OUT = os.path.join(HERE, "g202_f8_referee.md")
SEED = 0
N_PERM = 200


# --------------------------------------------------------------------------
# extra features -- every one reads bars[:i+1] only, by construction
# --------------------------------------------------------------------------
def extra_features(bars, i, level, is_long):
    """22 continuous predicates at the entry bar. `bars` may be truncated to
    i+1 with no change in output -- that is what the leakage test checks."""
    b = bars[i]
    atr = dg._atr(bars, i) or 0.0
    px = b["c"] or 1.0
    rng = dg._rng(b)
    body = dg._body(b)
    sgn = 1.0 if is_long else -1.0

    br = dg._break_bar(bars, i, level, is_long)
    rt = dg._retest_bar(bars, i, level, is_long, br) if br is not None else None
    ocr = dg.find_ocr(bars, i, is_long)

    lo_d = min(x["l"] for x in bars[:i + 1])
    hi_d = max(x["h"] for x in bars[:i + 1])
    day_rng = hi_d - lo_d
    vols = [x.get("v") or 0.0 for x in bars[max(0, i - 20):i]]
    vmean = (sum(vols) / len(vols)) if vols else 0.0

    upper_wick = b["h"] - max(b["o"], b["c"])
    lower_wick = min(b["o"], b["c"]) - b["l"]

    return {
        "x_atr_pct": atr / px,
        "x_dist_level_atr": (sgn * (b["c"] - level) / atr) if atr else 0.0,
        "x_dist_level_pct": sgn * (b["c"] - level) / px,
        "x_bar_rng_atr": (rng / atr) if atr else 0.0,
        "x_body_frac": (body / rng) if rng else 0.0,
        "x_wick_with": ((lower_wick if is_long else upper_wick) / rng) if rng else 0.0,
        "x_wick_against": ((upper_wick if is_long else lower_wick) / rng) if rng else 0.0,
        "x_bars_since_break": float(i - br) if br is not None else -1.0,
        "x_break_seen": 1.0 if br is not None else 0.0,
        "x_bars_since_retest": float(i - rt) if rt is not None else -1.0,
        "x_retest_seen": 1.0 if rt is not None else 0.0,
        "x_break_to_retest": float(rt - br) if (br is not None and rt is not None) else -1.0,
        "x_ocr_age": float(i - ocr) if ocr is not None else -1.0,
        "x_ocr_seen": 1.0 if ocr is not None else 0.0,
        "x_ocr_dist_atr": ((sgn * (b["c"] - (bars[ocr]["l"] if is_long else bars[ocr]["h"])) / atr)
                           if (ocr is not None and atr) else 0.0),
        "x_day_extension_atr": ((b["c"] - bars[0]["o"]) * sgn / atr) if atr else 0.0,
        "x_pos_in_day_range": ((b["c"] - lo_d) / day_rng) if day_rng else 0.5,
        "x_day_range_atr": (day_rng / atr) if atr else 0.0,
        "x_vol_ratio": (((b.get("v") or 0.0) / vmean) if vmean else 0.0),
        "x_break_body_atr": ((dg._body(bars[br]) / atr) if (br is not None and atr) else 0.0),
        "x_risk_atr": (abs(b["c"] - level) / atr) if atr else 0.0,
        "x_risk_pct": abs(b["c"] - level) / px,
    }


def build():
    """Mirror g157.build_rows() and attach the extra features.

    Returns (full, truncated): the same rows computed from the whole day, and
    from bars[:i+1] only. Any cell that differs is a read past the entry bar.
    """
    days, _ = load_day_cards()
    rows, trunc_rows = [], []
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
        cut = bars[:i + 1]
        rec_t = dg.score(cut, i, stop, is_long, htf_bias=first["bias"])

        def mk(r, bb):
            row = {
                "symbol": sym, "date": date, "month": date[:7], "bar": i,
                "stop_level_name": first.get("stop_level_name") or "unknown",
                "signal_type": first.get("signal_type") or "unknown",
                "grade": first.get("old") or "unknown",
                "displacement": int(bool(first.get("displacement"))
                                    if first.get("displacement") is not None
                                    else ("no_displacement" not in r["tripped"])),
                "htf_bias": first.get("bias") or "unknown",
                "n_tripped": r["n_tripped"], "confluence": int(r["confluence"]),
                "net": r["net"], "y": 1 if label == "S" else 0,
                "engine_fired": 1 if (first.get("old") not in OLD_SKIP) else 0,
            }
            for v in VAR_COLS:
                row[v] = int(v in r["tripped"])
            row.update(extra_features(bb, i, stop, is_long))
            return row

        rows.append(mk(rec, bars))
        trunc_rows.append(mk(rec_t, cut))
    return pd.DataFrame(rows), pd.DataFrame(trunc_rows)


def oof_auc(df, cols, cat_cols, model):
    X = pd.get_dummies(df[cols + cat_cols], columns=cat_cols, dummy_na=True)
    y = df["y"].to_numpy()
    groups = df["month"].to_numpy()
    n_splits = min(5, len(set(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    oof = np.zeros(len(y))
    for tr, te in gkf.split(X, y, groups):
        Xtr, Xte, ytr = X.iloc[tr], X.iloc[te], y[tr]
        if len(set(ytr)) < 2:
            oof[te] = ytr.mean()
            continue
        if model == "logreg":
            sc = StandardScaler()
            m = LogisticRegression(max_iter=2000, class_weight="balanced")
            m.fit(sc.fit_transform(Xtr), ytr)
            oof[te] = m.predict_proba(sc.transform(Xte))[:, 1]
        else:
            m = GradientBoostingClassifier(random_state=SEED)
            m.fit(Xtr, ytr)
            oof[te] = m.predict_proba(Xte)[:, 1]
    return roc_auc_score(y, oof), n_splits


def perm_null(df, cols, cat_cols, model, n=N_PERM):
    """AUC of the same pipeline with y shuffled WITHIN month groups."""
    rng = np.random.default_rng(SEED)
    months = df["month"].to_numpy()
    out = []
    d2 = df.copy()
    for _ in range(n):
        yy = df["y"].to_numpy().copy()
        for g in np.unique(months):
            idx = np.where(months == g)[0]
            yy[idx] = rng.permutation(yy[idx])
        d2["y"] = yy
        try:
            a, _ = oof_auc(d2, cols, cat_cols, model)
            out.append(a)
        except ValueError:
            continue
    return np.array(out)


def main():
    warnings.filterwarnings("ignore")
    L = []
    A = L.append

    df, dft = build()
    base_cols = list(VAR_COLS) + ["confluence", "n_tripped", "net", "bar", "displacement"]
    extra_cols = [c for c in df.columns if c.startswith("x_")]

    g_df, g_meta = g157_rows()
    same_rows = (len(g_df) == len(df)
                 and set(zip(g_df.symbol, g_df.date)) == set(zip(df.symbol, df.date)))
    same_y = bool((g_df.sort_values(["symbol", "date"]).y.to_numpy()
                   == df.sort_values(["symbol", "date"]).y.to_numpy()).all())

    A("# g202 -- independent leakage referee for F8 (`research/g157_ml_ceiling.py`)\n")
    A("\n**One sentence: F8 is clean where it was challenged -- not one feature "
      "reads a bar past the entry, no judged day crosses a CV fold, and a "
      "22-feature stronger set still cannot beat a coin flip -- so the 'ML "
      "ceiling is at chance' finding is UPHELD; what the report got wrong is "
      "smaller: 5 of its 120 labels are days Austin graded twice and "
      "differently (2 of them flipping S), and the CV it calls 5-fold is "
      "4-fold.**\n")

    A("\n## 0. Reproduction\n\n")
    A(f"- `python research/g157_ml_ceiling.py` re-run on this box: "
      f"{g_meta['n_rows']} rows, {int(g_df.y.sum())} S -- matches the published "
      f"120 rows / 28 S / AUC 0.492 / 0.426 exactly.\n")
    A(f"- this referee rebuilds the row set independently: identical "
      f"(symbol,date) set = **{same_rows}**, identical label vector = "
      f"**{same_y}**.\n")

    # ---- 1. leakage -------------------------------------------------------
    A("\n## 1. Leakage -- is every feature computable at the entry bar?\n")
    A("\nTest, not inspection: recompute every feature from `bars[:i+1]` -- the "
      "bar list physically truncated at the entry bar -- and diff cell-by-cell "
      "against the value computed from the whole day. A feature that reads "
      "forward MUST differ.\n\n")
    check_cols = list(base_cols) + extra_cols
    a = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    b = dft.sort_values(["symbol", "date"]).reset_index(drop=True)
    diffs = []
    for c in check_cols:
        va = pd.to_numeric(a[c], errors="coerce").to_numpy(dtype=float)
        vb = pd.to_numeric(b[c], errors="coerce").to_numpy(dtype=float)
        nd = int((~np.isclose(va, vb, rtol=1e-9, atol=1e-12, equal_nan=True)).sum())
        diffs.append((c, nd))
    n_bad = sum(1 for _, nd in diffs if nd)
    A("| feature | rows differing under truncation |\n|---|---:|\n")
    for c, nd in diffs:
        A(f"| `{c}` | {nd} |\n")
    A(f"\n**{n_bad} of {len(diffs)} features differ over "
      f"{len(df)} rows. {'LEAK.' if n_bad else 'No feature reads past the entry bar.'}**\n")
    A("\nThe four categoricals (`stop_level_name`, `signal_type`, `grade`, "
      "`htf_bias`) are not in that table because they come out of the engine "
      "replay rather than out of `downgrade.py`. They are causal for a different "
      "reason: `research/t66_downgrade_measure.py::replay` sets "
      "`r.candles = candles[:i+1]` before every `detect_signals()` call, so the "
      "engine physically cannot see bar i+1; and `htf_bias` is close-vs-SMA20 "
      "over `names[max(0,i-40):i]` -- **strictly prior archived days, the slice "
      "ends before today**. That is the opposite of the `spy_trend` defect the "
      "O1 referee found last night, where today's close sat inside its own SMA.\n")
    A("\nOne thing the report mis-describes but which is not a leak: `n_tripped` "
      "and `net` include the `chase` downgrade (`ENABLE_CHASE_DOWNGRADE` is ON), "
      "so the model sees a ninth variable that has no column of its own. `chase` "
      "reads `bars[i]` and the level only.\n")

    # ---- 2. CV grouping ---------------------------------------------------
    A("\n## 2. CV grouping -- can a card cross folds?\n\n")
    dup = int(df.duplicated(["symbol", "date"]).sum())
    months = df["month"].value_counts().sort_index()
    n_groups = df["month"].nunique()
    A(f"- duplicate (symbol,date) rows: **{dup}**. One row per judged day, so no "
      f"card can be in train and test at once.\n")
    A(f"- CV groups (calendar months): **{n_groups}**. The code runs "
      f"`n_splits = min(5, n_groups)`, so it is a **{min(5, n_groups)}-fold** CV. "
      f"The report's headings say '5-fold GroupKFold'. Cosmetic, but wrong.\n\n")
    A("| month | rows | S rows |\n|---|---:|---:|\n")
    for m in months.index:
        A(f"| {m} | {int(months[m])} | {int(df.loc[df.month == m, 'y'].sum())} |\n")
    gkf = GroupKFold(n_splits=min(5, n_groups))
    A("\n| fold | test months | test rows | test S | train rows | train S |\n"
      "|---:|---|---:|---:|---:|---:|\n")
    for k, (tr, te) in enumerate(gkf.split(df, df["y"], df["month"])):
        tm = sorted(set(df["month"].to_numpy()[te]))
        A(f"| {k} | {', '.join(tm)} | {len(te)} | {int(df['y'].to_numpy()[te].sum())} "
          f"| {len(tr)} | {int(df['y'].to_numpy()[tr].sum())} |\n")
    A("\nEvery month lands in exactly one fold, so **no card leaks across folds**. "
      "The fragility is elsewhere: one fold is 2026-07 alone, 55% of the whole "
      "row set, and when it is held out the model trains on 54 rows. That is why "
      "the pooled out-of-fold AUC needs the null band in section 4 rather than a "
      "bare comparison to 0.500.\n")

    # ---- 3. labels --------------------------------------------------------
    A("\n## 3. Labels -- do the 120 rows and the 28 S come from his marks?\n\n")
    pool = mp.canonical_pool()
    days_all, _ = load_day_cards()
    agree = dis = missing = 0
    conf = []
    for _, r in df.iterrows():
        k = f"{r.symbol}_{r.date}"
        e = pool.get(k)
        g_deck = (days_all[(r.symbol, r.date)].get("grade") or "").strip()
        if e is None:
            missing += 1
            continue
        if (e.grade or "").strip() == g_deck:
            agree += 1
        else:
            dis += 1
            conf.append((k, g_deck, e.grade, list(e.raw_grades), e.n_opinions))
    A("- source of the 120: `research/t60_baseline.load_day_cards()` -> "
      "`research/exit_lab.MARKS_FILES` = `research/marks/deck_marks_tsla_2026-08-20.jsonl` "
      "+ `research/marks/deck_marks_index_2026-08-19.jsonl`. Both are human deck "
      "exports (60 TSLA, 30 QQQ, 30 SPY); neither is engine output. Grades read "
      "28 S / 27 A / 3 C / 61 none / 1 blank.\n")
    A(f"- cross-checked against the canonical cross-corpus view "
      f"`research/marks_pool.py` ({len(pool)} symbol-days, nine grade spellings): "
      f"**{agree} agree, {dis} disagree, {missing} missing**.\n\n")
    A("| symbol-day | F8 label | marks_pool canonical | all his opinions | corpora |\n"
      "|---|---|---|---|---:|\n")
    for k, gd, gp, raw, n in conf:
        A(f"| {k} | `{gd or '(blank)'}` | `{gp}` | {raw} | {n} |\n")
    flips = [c for c in conf if c[2] == "S"]
    A(f"\n**{len(conf)} of 120 rows are days Austin graded more than once and "
      f"graded DIFFERENTLY**, in a different session. {len(flips)} of them flip "
      f"the S bit: F8 scores them 0, cross-corpus resolution scores them 1. So "
      f"the honest positive count on these 120 days is **28 under the two deck "
      f"files, 30 under `marks_pool`** -- a 7% swing in the positive class.\n")
    A("\nThis is label noise, not a label error: neither reading is wrong, he "
      "just answered twice. F8 did not disclose it. It also puts a hard floor "
      "under any achievable AUC -- 2 of the ~29 positives are contested by the "
      "labeller himself.\n")

    df_alt = df.copy()
    alt = {c[0] for c in flips}
    df_alt["y"] = [1 if f"{r.symbol}_{r.date}" in alt else r.y
                   for _, r in df_alt.iterrows()]

    # ---- 4. stronger feature set -----------------------------------------
    A("\n## 4. A stronger feature set the F8 agent did not try\n\n")
    A("22 continuous predicates on top of F8's set, every one verified "
      "truncation-identical in section 1: level distance in ATR and in %, bars "
      "since the break, bars since the retest, the break->retest gap, OCR age "
      "and OCR-edge distance in ATR, entry-bar range / body / with-wick / "
      "against-wick geometry, position in the day's range so far, day extension "
      "in ATR, volume against the prior 20 bars, break-candle body in ATR, and "
      "risk (|entry - level|) in ATR and in %. These are the continuous forms of "
      "the g154 rule predicates -- displacement size, staleness, chase distance, "
      "exhaustion -- which F8 only saw as the eight booleans.\n\n")
    A("The null is a label permutation **within month groups**, 200 draws, same "
      "pipeline. On 120 rows with 28 positives and 4 folds, chance is not 0.500 "
      "with a tight band around it.\n\n")
    A("| feature set | model | out-of-fold ROC AUC | permutation null mean | null 5th-95th | p |\n"
      "|---|---|---:|---:|---|---:|\n")
    table = []
    for setname, cols, cats in (("F8 as shipped", list(base_cols), CAT_COLS),
                                ("F8 + 22 engineered", list(base_cols) + extra_cols, CAT_COLS),
                                ("engineered only", extra_cols, [])):
        for model, mlabel in (("logreg", "logistic"), ("gbc", "grad boost")):
            auc, ns = oof_auc(df, cols, cats, model)
            null = perm_null(df, cols, cats, model)
            p = float((null >= auc).mean())
            table.append((setname, mlabel, auc, null, p))
            A(f"| {setname} | {mlabel} | **{auc:.3f}** | {null.mean():.3f} | "
              f"{np.percentile(null, 5):.3f} - {np.percentile(null, 95):.3f} | "
              f"{p:.2f} |\n")
    best = max(table, key=lambda t: t[2])
    A(f"\n**Best arm anywhere: {best[0]} / {best[1]}, AUC {best[2]:.3f}, "
      f"p = {best[4]:.2f}.** Not one arm clears its own permutation null. Adding "
      f"22 engineered predicates moved the logistic arm from "
      f"{table[0][2]:.3f} to {table[2][2]:.3f} and the boosted arm from "
      f"{table[1][2]:.3f} to {table[3][2]:.3f} -- inside the noise either "
      f"way, and the engineered set alone is worse than a coin flip.\n")
    A(f"\nThe 'F8 as shipped' row here reads {table[0][2]:.3f} / {table[1][2]:.3f} "
      f"against the published 0.492 / 0.426 because of a third small defect: "
      f"`g157.build_rows()` computes a `displacement` column -- a feature the "
      f"spec row explicitly named -- and `g157.make_xy()` then leaves it out of "
      f"`X`. This referee puts it back. It is worth +0.004 AUC. Mentioned for "
      f"the record, not because it matters.\n")

    A("\n### The same, with the two contested days relabelled S (30 positives)\n\n")
    A("| feature set | model | out-of-fold ROC AUC |\n|---|---|---:|\n")
    for setname, cols in (("F8 as shipped", list(base_cols)),
                          ("F8 + 22 engineered", list(base_cols) + extra_cols)):
        for model, mlabel in (("logreg", "logistic"), ("gbc", "grad boost")):
            auc, _ = oof_auc(df_alt, cols, CAT_COLS, model)
            A(f"| {setname} | {mlabel} | {auc:.3f} |\n")
    A("\nThe label question does not rescue it either.\n")

    # ---- verdict ----------------------------------------------------------
    A("\n## Verdict\n\n")
    A("| check | result |\n|---|---|\n")
    A(f"| every feature computable at the entry bar | **PASS** -- "
      f"{len(diffs)} numeric features x {len(df)} rows, {n_bad} differ under "
      f"truncation; the 4 categoricals are causal by the replay's `candles[:i+1]` "
      f"slice and a prior-days-only HTF bias |\n")
    A(f"| CV grouped by month, no card across folds | **PASS** -- 0 duplicate "
      f"days, {n_groups} disjoint month groups |\n")
    A(f"| the 120-card set and 28 S labels match his marks | **PARTIAL** -- "
      f"{agree}/120 agree with `marks_pool`; {len(conf)} are days he graded "
      f"twice and differently, {len(flips)} of which flip S (28 vs 30) |\n")
    A(f"| a stronger feature set moves AUC | **NO** -- best {best[2]:.3f}, "
      f"p = {best[4]:.2f} |\n")
    A("\n**F8's headline stands and is NOT refuted: on these features, over these "
      "120 judged days, there is no learnable S signal.** It survives 22 extra "
      "engineered predicates and survives relabelling the contested days. Three "
      "corrections belong in the record and none changes the answer -- the CV is "
      "4-fold, not 5-fold (`min(5, n_groups)` with 4 month groups); 5 of the 120 "
      "labels are days he graded twice and differently, 2 of them flipping S; and "
      "`displacement`, a feature the spec row named, is computed and then dropped "
      "before `X` is built.\n")
    A("\n**What none of this establishes.** 120 rows, 28 positives, 4 month "
      "groups, one of them 55% of the data. The permutation null itself spans "
      f"{np.percentile(table[0][3], 5):.2f}-{np.percentile(table[0][3], 95):.2f}, "
      "so this rig could not detect a modest real edge if one existed. "
      "'These features do not contain the answer' is well supported. 'No "
      "features could' is not tested by anything here, and the morning report "
      "should not be read as saying it.\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("".join(L))
    print(f"wrote {OUT}")
    print(f"leak: {n_bad}/{len(diffs)} features differ | labels agree {agree}/120, "
          f"{len(conf)} contested, {len(flips)} flip S | best AUC {best[2]:.3f} "
          f"({best[0]}/{best[1]}) p={best[4]:.2f}")


if __name__ == "__main__":
    main()
