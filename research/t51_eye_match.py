"""omen-5.1 T7: eye-match agreement scorer.

The metric that replaces P&L for judging tiers. `research/t8_significance.md`
showed P&L cannot separate the tiers -- every observed gap is smaller than the
smallest gap the sample could detect. Tier quality is instead scored as
**agreement with Austin's grade on the same bar**: for every mark where the
engine also produced a signal within +-2 bars of the marked entry, compare the
engine's `austin_tier` to Austin's grade and report a confusion matrix, exact
and adjacent agreement, the two directional error rates (over-grading /
under-grading), and a Cohen's kappa.

"Engine did not fire" is its own column, never a missing value -- a silent
engine on an S bar is the failure this project exists to fix, and dropping
those rows would hide it.

Method: replay the shipped engine over each marked (symbol, day) pair, capture
every routed signal with its computed `austin_tier`, then for each mark pick
the nearest engine fire within +-2 bars of the marked entry (earliest bar on a
tie). No fire within tolerance -> "no-fire".

Usage:
  python research/t51_eye_match.py [--marks research/austin_marks_v7.jsonl]
Writes research/t51_eye_match.md.
"""
from __future__ import annotations
import os
import sys
import json
import argparse
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE) if os.path.basename(HERE) == "research" else HERE
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

# backtest_week / signal_runner import yfinance at top level; the replay never
# fetches, so a bare stub satisfies the import without touching the engine.
import types as _types
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = _types.ModuleType("yfinance")

import signal_runner as sr  # noqa: E402
from t3_session_extreme import day_inputs  # noqa: E402

DEFAULT_MARKS = os.path.join(HERE, "austin_marks_v7.jsonl")
OUT_MD = os.path.join(HERE, "t51_eye_match.md")

TOL = 2              # +- bars around the marked entry that still counts as a match
GRADE_ORDER = ["S", "A", "C", "X"]          # Austin's grade universe (ordinal)
ENGINE_COLS = ["S", "A", "C", "X", "no-fire"]  # engine tier + the silent column
RANK = {g: i for i, g in enumerate(GRADE_ORDER)}  # S=0 A=1 C=2 X=3 (for adjacency)


class Capture(sr.SignalRunner):
    """Collect every routed (emitted) signal with its computed tier."""

    def __init__(self, symbol):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.fired = []

    def _route(self, signals, sig):
        before = len(signals)
        super()._route(signals, sig)
        if len(signals) > before:
            self.fired.append(sig)


def load_marks(path):
    """Group scorable marks (austin_tier in S/A/C/X, with an entry bar) by (symbol, day)."""
    out = defaultdict(list)
    skipped = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("entry_i") is None:
                skipped += 1
                continue
            if r.get("austin_tier") not in GRADE_ORDER:
                skipped += 1  # non-canonical grades (e.g. B, blank) are not scorable here
                continue
            out[(r["symbol"], r["day"])].append(r)
    return out, skipped


def replay_day(symbol, day):
    """All routed engine fires on (symbol, day) as (bar, austin_tier)."""
    got = day_inputs(symbol, day)
    if got is None:
        return None  # day not in the archive -> engine is silent
    candles = got[0]
    r = Capture(symbol)
    r.pdh, r.pdl, r.pmh, r.pml = got[1], got[2], got[5], got[6]
    r.pd_open, r.pd_close, r.htf_bias = got[3], got[4], got[7]
    fires = []
    for i in range(5, len(candles)):
        r.candles = candles[: i + 1]
        before = len(r.fired)
        r.detect_signals()
        for sig in r.fired[before:]:
            t = sig.get("austin_tier")
            if t not in RANK:
                continue
            fires.append((i, t))
    return fires


def match(marks, fires_by_day):
    """One (austin_grade, engine_tier) pair per scored mark."""
    rows = []
    for (symbol, day), mks in marks.items():
        fires = fires_by_day.get((symbol, day))
        for m in mks:
            g = m["austin_tier"]
            ei = m["entry_i"]
            if not fires:
                rows.append((g, "no-fire"))
                continue
            # nearest fire within +-TOL; earliest bar breaks a distance tie
            cand = sorted(
                ((abs(b - ei), b, t) for (b, t) in fires if abs(b - ei) <= TOL),
                key=lambda x: (x[0], x[1]),
            )
            rows.append((g, cand[0][2]) if cand else (g, "no-fire"))
    return rows


def cohen_kappa(rows):
    """Kappa over the shared S/A/C/X labels; the no-fire column contributes 0
    to both observed and expected agreement (Austin never labels a bar no-fire)."""
    n = len(rows)
    if n == 0:
        return 0.0
    austin_m = Counter(a for a, _ in rows)
    eng_m = Counter(e for _, e in rows)
    cell = Counter((a, e) for a, e in rows)
    po = sum(cell[(g, g)] for g in GRADE_ORDER) / n
    pe = sum((austin_m[g] / n) * (eng_m[g] / n) for g in GRADE_ORDER)
    if (1.0 - pe) == 0:
        return 0.0
    return (po - pe) / (1.0 - pe)


def main():
    ap = argparse.ArgumentParser(description="Eye-match agreement scorer")
    ap.add_argument("--marks", default=DEFAULT_MARKS,
                    help="path to austin marks jsonl (default: research/austin_marks_v7.jsonl)")
    args = ap.parse_args()

    marks_path = args.marks if os.path.exists(args.marks) else os.path.join(HERE, args.marks)
    marks, skipped = load_marks(marks_path)

    fires_by_day = {}
    missing_days = 0
    for (symbol, day) in marks:
        f = replay_day(symbol, day)
        if f is None:
            missing_days += 1
            continue
        fires_by_day[(symbol, day)] = f

    rows = match(marks, fires_by_day)
    n = len(rows)
    cell = Counter((a, e) for a, e in rows)
    austin_m = Counter(a for a, _ in rows)
    eng_m = Counter(e for _, e in rows)

    # ---- metrics ----
    exact = sum(cell[(g, g)] for g in GRADE_ORDER)
    exact_pct = round(exact / n * 100, 2) if n else 0.0
    per_grade_exact = {
        g: round(cell[(g, g)] / austin_m[g] * 100, 2) if austin_m[g] else 0.0
        for g in GRADE_ORDER
    }
    adjacent = sum(
        1 for (a, e) in rows
        if e in RANK and a != e and abs(RANK[a] - RANK[e]) == 1
    )
    adjacent_pct = round(adjacent / n * 100, 2) if n else 0.0
    over = sum(1 for (a, e) in rows if e == "S" and a in ("C", "X"))
    under = sum(1 for (a, e) in rows if a == "S" and e in ("C", "X", "no-fire"))
    over_rate = round(over / n * 100, 2) if n else 0.0
    under_rate = round(under / n * 100, 2) if n else 0.0
    kappa = round(cohen_kappa(rows), 4)
    s_total = austin_m["S"]
    s_hit = cell[("S", "S")]
    s_recall = f"{s_hit}/{s_total}"

    # ---- report ----
    L = []
    L.append("# T7 -- eye-match agreement (engine tier vs Austin's grade)")
    L.append("")
    L.append(f"Scorer: `research/t51_eye_match.py` on `{os.path.basename(marks_path)}`.")
    L.append("For each mark, the shipped engine is replayed over that (symbol, day); the "
             "nearest routed signal within +-2 bars of the marked entry supplies the engine's "
             "tier. No fire within tolerance is its own column (`no-fire`), never dropped -- "
             "a silent engine on an S bar is the failure this project exists to fix.")
    L.append("")
    L.append(f"- marks scored: **{n}** (skipped {skipped} non-S/A/C/X grades; "
             f"{missing_days} marked (symbol, day) pairs absent from the archive -> silent)")
    L.append(f"- unique (symbol, day) days replayed: **{len(fires_by_day)}**")
    L.append("")
    L.append("## Confusion matrix")
    L.append("")
    L.append("Rows = Austin's grade; columns = engine's tier. `no-fire` = the engine produced "
             "no routed signal within +-2 bars of the marked entry.")
    L.append("")
    header = "| Austin \\ Engine | " + " | ".join(ENGINE_COLS) + " | row total |"
    sep = "|" + "---|" * (len(ENGINE_COLS) + 2)
    L.append(header)
    L.append(sep)
    for g in GRADE_ORDER:
        vals = [str(cell[(g, c)]) for c in ENGINE_COLS]
        L.append(f"| **{g}** | " + " | ".join(vals) + f" | {austin_m[g]} |")
    col_tot = [str(eng_m[c]) for c in ENGINE_COLS]
    L.append("| **col total** | " + " | ".join(col_tot) + f" | **{n}** |")
    L.append("")
    L.append("## Agreement")
    L.append("")
    L.append(f"- **exact agreement (overall): {exact_pct}%**  ({exact}/{n})")
    L.append("- exact per Austin-grade:  " +
              ",  ".join(f"{g}={per_grade_exact[g]}%" for g in GRADE_ORDER))
    L.append(f"- **adjacent agreement (off by one tier): {adjacent_pct}%**  ({adjacent}/{n})")
    L.append(f"- **Cohen's kappa: {kappa}**  (agreement vs chance; <0 less than chance, "
             f"0 chance, >0.41 moderate, >0.61 substantial)")
    L.append("")
    L.append("## Directional error rates")
    L.append("")
    L.append(f"- **over-grading: {over_rate}%**  ({over}/{n}) -- engine says S, Austin says C or X")
    L.append(f"- **under-grading: {under_rate}%**  ({under}/{n}) -- Austin says S, engine says C, "
             f"X, or did not fire")
    L.append("")
    L.append(f"- **S recall: {s_recall}** -- of Austin's S bars, the share the engine also "
             f"called S within +-2 bars")
    L.append("")
    L.append("---")
    L.append("")
    L.append(f"marks_scored: {n}")
    L.append(f"exact_agreement: {exact_pct}")
    L.append(f"kappa: {kappa}")
    L.append(f"over_grade_rate: {over_rate}")
    L.append(f"under_grade_rate: {under_rate}")
    L.append(f"s_recall: {s_recall}")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    print(f"wrote {OUT_MD}")
    print(f"marks_scored={n} exact={exact_pct}% kappa={kappa} "
          f"over={over_rate}% under={under_rate}% s_recall={s_recall}")


if __name__ == "__main__":
    main()
