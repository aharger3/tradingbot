"""F8/g157 -- the ML ceiling: can a learned model beat the rule engine at S-vs-not?

Feature row = one judged symbol-day, built from that day's FIRST book candidate
(the engine's own detection replay, exactly as research/t66_downgrade_measure.py
runs it): the eight research/downgrade.py variables (tripped booleans), BR+OCR
confluence, level type (stop_level_name), setup (signal_type), the legacy engine
tier (grade), the engine's own displacement flag, HTF bias, and the candidate's
bar index (time of first candidate, minutes from 09:30 open).

Label = 1 if Austin graded the DAY "S", else 0 ("A"/"C"/"none" all count as
"not"). This is a day-level label attached to that day's first candidate row,
not a per-signal ground truth -- Austin grades days, not individual candidates,
and the report says so plainly.

LEAKAGE GUARD: every feature is computed by research/downgrade.py functions and
the engine's own bar-by-bar replay, both of which only ever index bars[<=i] for
the signal bar i (verified by inspection: _break_bar, _retest_bar, find_ocr,
ocr_not_respected, level_not_respected, exhausted, counter_trend_not_respected
all bound their loops at i or i+1 at most, never reading bars[i+1:] as an
unbounded slice). Nothing here reads a bar after the entry bar.

Never wired into detection -- measured only, like downgrade.py itself.

    python research/g157_ml_ceiling.py

Writes research/g157_ml_ceiling.md.
"""
from __future__ import annotations

import os
import sys
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import numpy as np                                                     # noqa: E402
import pandas as pd                                                     # noqa: E402
from sklearn.model_selection import GroupKFold                          # noqa: E402
from sklearn.linear_model import LogisticRegression                    # noqa: E402
from sklearn.ensemble import GradientBoostingClassifier                # noqa: E402
from sklearn.metrics import precision_recall_curve, roc_auc_score      # noqa: E402
from sklearn.preprocessing import StandardScaler                      # noqa: E402

from research import downgrade as dg                                   # noqa: E402
from research.t66_downgrade_measure import replay, as_dicts, OLD_SKIP  # noqa: E402
from research.t60_baseline import load_day_cards                       # noqa: E402

OUT = os.path.join(HERE, "g157_ml_ceiling.md")
CAT_COLS = ["stop_level_name", "signal_type", "grade", "htf_bias"]
VAR_COLS = list(dg.VARIABLES)  # the eight downgrade variables


def build_rows():
    """One row per judged symbol-day that has at least one book candidate."""
    days, _ = load_day_cards()
    rows = []
    skipped_no_candles = 0
    skipped_no_candidate = 0
    days_run = 0
    for (sym, date), d in sorted(days.items()):
        label = (d.get("grade") or "").strip()
        sigs, bars = replay(sym, date)
        if sigs is None:
            skipped_no_candles += 1
            continue
        days_run += 1
        if not sigs:
            skipped_no_candidate += 1
            continue
        # first book candidate that day, by bar index (arrival order)
        first = min(sigs, key=lambda s: s["bar"])
        i = first["bar"]
        is_long = first["dir"] == "call"
        stop = first["stop"]
        rec = dg.score(bars, i, stop, is_long, htf_bias=first["bias"])
        if rec is None:
            continue
        row = {
            "symbol": sym, "date": date, "month": date[:7],
            "bar": i,
            "stop_level_name": first.get("stop_level_name") or "unknown",
            "signal_type": first.get("signal_type") or "unknown",
            "grade": first.get("old") or "unknown",
            "displacement": (bool(first.get("displacement"))
                             if first.get("displacement") is not None
                             else ("no_displacement" not in rec["tripped"])),
            "htf_bias": first.get("bias") or "unknown",
            "n_tripped": rec["n_tripped"],
            "confluence": int(rec["confluence"]),
            "net": rec["net"],
            "y": 1 if label == "S" else 0,
            "engine_fired": 1 if (first.get("old") not in OLD_SKIP) else 0,
        }
        for v in VAR_COLS:
            row[v] = int(v in rec["tripped"])
        rows.append(row)
    meta = {"days_total": len(days), "days_run": days_run,
            "skipped_no_candles": skipped_no_candles,
            "skipped_no_candidate": skipped_no_candidate,
            "n_rows": len(rows)}
    return pd.DataFrame(rows), meta


def make_xy(df):
    X = pd.get_dummies(df[VAR_COLS + ["confluence", "n_tripped", "net", "bar"] + CAT_COLS],
                        columns=CAT_COLS, dummy_na=True)
    y = df["y"].to_numpy()
    groups = df["month"].to_numpy()
    return X, y, groups


def cv_oof(df, X, y, groups, model_name):
    n = len(y)
    oof = np.zeros(n)
    n_groups = len(set(groups))
    n_splits = min(5, n_groups)
    if n_splits < 2:
        return None
    gkf = GroupKFold(n_splits=n_splits)
    for tr, te in gkf.split(X, y, groups):
        Xtr, Xte = X.iloc[tr], X.iloc[te]
        ytr = y[tr]
        if model_name == "logreg":
            sc = StandardScaler()
            Xtr_s = sc.fit_transform(Xtr)
            Xte_s = sc.transform(Xte)
            if len(set(ytr)) < 2:
                oof[te] = ytr.mean()
                continue
            m = LogisticRegression(max_iter=1000, class_weight="balanced")
            m.fit(Xtr_s, ytr)
            oof[te] = m.predict_proba(Xte_s)[:, 1]
        else:
            if len(set(ytr)) < 2:
                oof[te] = ytr.mean()
                continue
            m = GradientBoostingClassifier(random_state=0)
            m.fit(Xtr, ytr)
            oof[te] = m.predict_proba(Xte)[:, 1]
    return oof


def precision_at_recall(y, scores, target_recall):
    precision, recall, thresh = precision_recall_curve(y, scores)
    # precision_recall_curve returns recall descending as threshold rises;
    # find points with recall >= target_recall, take the one with max precision
    ok = recall >= target_recall
    if not ok.any():
        return None
    return float(precision[ok].max())


def main():
    warnings.filterwarnings("ignore")
    df, meta = build_rows()
    lines = []
    lines.append("# g157 -- the ML ceiling (F8)\n")
    lines.append("**One sentence: on the judged symbol-days with a book candidate, "
                 "a gradient-boosted model's out-of-fold precision at the rule "
                 "engine's own recall is reported below; it is measured only, "
                 "never wired into detection.**\n")

    if df.empty or meta["n_rows"] < 20:
        lines.append(f"\nBLOCKED-ish: only {meta['n_rows']} usable rows "
                     f"(days_total={meta['days_total']}, days_run={meta['days_run']}, "
                     f"skipped_no_candles={meta['skipped_no_candles']}, "
                     f"skipped_no_candidate={meta['skipped_no_candidate']}). "
                     "Not enough data for a 5-fold CV; reporting counts only.\n")
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"wrote {OUT} (insufficient rows: {meta['n_rows']})")
        return

    lines.append(f"\n- judged symbol-days: {meta['days_total']}, "
                 f"days with archived bars: {meta['days_run']}, "
                 f"days with >=1 book candidate: {meta['n_rows']}\n"
                 f"- label: `y=1` iff Austin graded that day S; A/C/none all count as 0\n"
                 f"- feature row = day's FIRST book candidate only (arrival order, "
                 f"bar index = time of first candidate)\n")

    n_s = int(df["y"].sum())
    lines.append(f"- S-day rows: {n_s} / {len(df)} ({100.0*n_s/len(df):.1f}%)\n")
    n_months = df["month"].nunique()
    lines.append(f"- months (CV groups): {n_months}\n")

    X, y, groups = make_xy(df)

    # rule engine's own recall on these same rows: fraction of S-day rows the
    # engine actually fired on (grade not in OLD_SKIP = X/D)
    engine_recall = float(df.loc[df["y"] == 1, "engine_fired"].mean()) if n_s else 0.0
    lines.append(f"\n**Rule engine's own recall on this row set: "
                 f"{engine_recall*100:.1f}%** (fraction of S-day first-candidates "
                 f"the legacy grader did not skip/X).\n")

    results = []
    for name, label in (("logreg", "Logistic regression"), ("gbc", "Gradient boosting")):
        oof = cv_oof(df, X, y, groups, name)
        if oof is None:
            lines.append(f"\n{label}: not enough month-groups for 5-fold CV.\n")
            continue
        try:
            auc = roc_auc_score(y, oof)
        except ValueError:
            auc = float("nan")
        p_at_r = precision_at_recall(y, oof, engine_recall) if engine_recall > 0 else None
        results.append((label, auc, p_at_r))
        precision, recall, thresh = precision_recall_curve(y, oof)
        # sample the curve at a few recall levels for the report
        sample_pts = []
        for target in (0.25, 0.5, 0.75, 1.0):
            ok = recall >= target
            if ok.any():
                sample_pts.append((target, float(precision[ok].max())))
        lines.append(f"\n## {label} (5-fold GroupKFold CV by month)\n")
        lines.append(f"- ROC AUC (out-of-fold): {auc:.3f}\n")
        if p_at_r is not None:
            lines.append(f"- precision at engine's recall "
                         f"({engine_recall*100:.1f}%): **{p_at_r*100:.1f}%**\n")
        else:
            lines.append("- precision at engine's recall: n/a (engine recall is 0)\n")
        lines.append("- precision/recall curve samples:\n\n")
        lines.append("| recall >= | best precision |\n|---:|---:|\n")
        for r, p in sample_pts:
            lines.append(f"| {r:.2f} | {p*100:.1f}% |\n")

    lines.append("\n## Baseline for comparison\n")
    lines.append(f"- S-day rate in this row set (predict-all-positive precision): "
                 f"{100.0*n_s/len(df):.1f}%\n")

    lines.append("\n## What this is not\n")
    lines.append("- Not wired into detection anywhere. `signal_runner.py` is unchanged.\n")
    lines.append("- Label is a DAY-level grade attached to that day's first candidate row, "
                 "not a per-signal ground truth -- Austin did not grade each candidate "
                 "individually.\n")
    lines.append(f"- Small-N: {len(df)} rows across {n_months} months. A held-out AUC/precision "
                 "computed from this many rows carries a wide error bar; treat this as a "
                 "ceiling sketch, not a shippable number.\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {OUT}: {len(df)} rows, {n_s} S-days, engine_recall={engine_recall:.3f}")
    for label, auc, p_at_r in results:
        print(f"  {label}: AUC={auc:.3f} precision_at_engine_recall="
              f"{'n/a' if p_at_r is None else f'{p_at_r:.3f}'}")


if __name__ == "__main__":
    main()
