"""g72_target25_price.py -- re-price "aim 2.5R instead of 2R" on the CURRENT book.

Austin's standing instruction: take any measured edge without asking. The board
(`research/g71_board.md` -> `research/g71_exitfam.md`) measured aiming 2.5R
instead of 2R at **+$40 a trade, real, free** -- but that number was measured on
a 2,437-trade book. Between that measurement and this one, a different agent
fixed the reject-suppression bug (G7.2, `backtest_week.py` DEDUPE_FIRES_ONLY)
and regenerated `research/bt2y_trades.json`: it is now **4,508 traded rows**,
not 2,437. This file re-runs the exact same paired rig on the book actually on
disk right now -- it does not assume the old number still holds.

RIG: identical to `research/g71_exitfam.py`'s F1/F3/F4 -- same `ride()`
exit engine (both shipped stops: the level stop on the close floored at
-1.25R, the resting -1.0R disaster stop on touch), same paired bootstrap
error bar (10,000 resamples of the per-row difference, the only interval
that fits a same-rows A/B). Nothing here reimplements a fill or an exit --
every function is imported from `research.g71_exitfam` / `research.exit_lab`.

Scope, per the G7.2 "target25" ticket:
  1. Re-price flat_2.5R vs flat_2R (the change under consideration).
  2. CONFIRM, do not change: flat_5R vs flat_2R, break-even-at-1R vs ride,
     and the faster-cut time-stop clocks vs ride.

Run:  python research/g72_target25_price.py            (writes g72_target25_report.md)
      python research/g72_target25_price.py --selftest  (sanity checks only)
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import date

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from research.g71_exitfam import (       # noqa: E402  -- reuse, never reimplement
    ride, first_adverse_close, load_rows, agg, months_green, paired_ci,
    survives, Bars, BOOK, BOOTSTRAP, SEED, EOD,
)

OUT_MD = os.path.join(_HERE, "g72_target25_report.md")
RISK_DOLLARS = 1000.0  # $1 = 1R, per CLAUDE.md / the book's own meta.risk_dollars


def weeks_green(rows, key):
    """Same convention as g71_exitfam.months_green, grouped by ISO (year, week)
    of the session date instead of calendar month."""
    by = defaultdict(list)
    for r in rows:
        y, w, _ = date.fromisoformat(r["day"]).isocalendar()
        by[(y, w)].append(r[key])
    g = sum(1 for v in by.values() if sum(v) > 0)
    return g, len(by)


ARMS = {
    "flat_2r":   dict(target_r=2.0),
    "flat_2.5r": dict(target_r=2.5),
    "flat_5r":   dict(target_r=5.0),
    "ride":      dict(),
    "be_1.00":   dict(be_at=1.00),
    "time_15":   dict(time_stop=15),
    "time_30":   dict(time_stop=30),
    "time_45":   dict(time_stop=45),
}


def score(rows):
    for name, kw in ARMS.items():
        for r in rows:
            r[name] = ride(r["bars"], r["entry_i"], r["entry"], r["stop"],
                           r["side"], clock=EOD, **kw)[0]
    for r in rows:
        r["fac"] = first_adverse_close(r["bars"], r["entry_i"], r["entry"],
                                       r["stop"], r["side"], clock=EOD)[0]


def row_line(rows, name, base, label):
    a = agg([r[name] for r in rows])
    mg, mt = months_green(rows, name)
    wg, wt = weeks_green(rows, name)
    if name == base:
        return (f"| {label} | {a['n']} | {a['wr']:.1f}% | ${a['mean']*RISK_DOLLARS:+.0f} "
                f"| {mg}/{mt} | {wg}/{wt} | baseline | -- |")
    obs, lo, hi, _ = paired_ci(rows, name, base)
    real = survives(lo, hi)
    return (f"| {label} | {a['n']} | {a['wr']:.1f}% | ${a['mean']*RISK_DOLLARS:+.0f} "
            f"| {mg}/{mt} | {wg}/{wt} | "
            f"{obs*RISK_DOLLARS:+.0f} [{lo*RISK_DOLLARS:+.0f}, {hi*RISK_DOLLARS:+.0f}] | "
            f"{'**yes**' if real else 'no'} |")


def selftest():
    cache = Bars()
    rows, meta, gaps = load_rows(cache)
    assert len(rows) > 3000, f"only {len(rows)} rows replayed -- book looks wrong"
    assert gaps == {"day": 0, "bar": 0, "index": 0}, gaps
    score(rows[:50])
    for r in rows[:50]:
        assert -1.26 <= r["flat_2r"] <= 2.01, r["flat_2r"]
    print(f"selftest OK: {len(rows)} rows, gaps={gaps}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    cache = Bars()
    rows, meta, gaps = load_rows(cache)
    n = len(rows)
    score(rows)

    A = []
    W = A.append
    W("# G7.2 `target25` -- re-priced on the current book")
    W("")
    W(f"Book `research/bt2y_trades.json` (generated {meta.get('generated')}), "
      f"**{n} traded rows** replayed from `data_archive/`. Gaps: {gaps}. "
      "Same rig as `research/g71_exitfam.py` F1/F3/F4: both shipped stops live "
      "(level stop on the close floored at -1.25R, resting -1.0R disaster stop "
      "on touch), paired bootstrap error bar (10,000 resamples of the per-row "
      "difference). $1,000 = 1R.")
    W("")
    W("**This is not the book the +$40 figure in `research/g71_exitfam.md` was "
      "measured on.** That file's book had 2,437 traded rows. Between that "
      "measurement and this one, the reject-suppression bug (G7.2) was fixed "
      "and the book was regenerated -- it is now "
      f"**{n} traded rows**. Everything below is re-derived from scratch on "
      "the book actually on disk.")
    W("")
    W("## 1. The change under consideration: aim 2.5R instead of 2R")
    W("")
    W("| arm | n | win% | $/trade | months green | weeks green | paired delta vs flat_2R (95% CI) | real? |")
    W("|---|---:|---:|---:|---:|---:|---|---|")
    W(row_line(rows, "flat_2r", "flat_2r", "flat_2r (the shipped plan)"))
    W(row_line(rows, "flat_2.5r", "flat_2r", "**flat_2.5r**"))
    W("")
    a2 = agg([r["flat_2r"] for r in rows])
    a25 = agg([r["flat_2.5r"] for r in rows])
    obs, lo, hi, _ = paired_ci(rows, "flat_2.5r", "flat_2r")
    verdict = "SURVIVES" if survives(lo, hi) else "DOES NOT SURVIVE"
    W(f"**Verdict: {verdict}.** Aiming 2.5R instead of 2R is worth "
      f"**${obs*RISK_DOLLARS:+.0f} a trade** on this book, 95% paired interval "
      f"[${lo*RISK_DOLLARS:+.0f}, ${hi*RISK_DOLLARS:+.0f}]. "
      f"Win rate {a2['wr']:.1f}% -> {a25['wr']:.1f}%. "
      f"Months green {'/'.join(map(str, months_green(rows,'flat_2r')))} -> "
      f"{'/'.join(map(str, months_green(rows,'flat_2.5r')))}. "
      f"Weeks green {'/'.join(map(str, weeks_green(rows,'flat_2r')))} -> "
      f"{'/'.join(map(str, weeks_green(rows,'flat_2.5r')))}.")
    W("")
    W("## 2. Confirmed, not changed")
    W("")
    W("| arm | n | win% | $/trade | months green | weeks green | paired delta (95% CI) | real? | note |")
    W("|---|---:|---:|---:|---:|---:|---|---|---|")
    o5, l5, h5, _ = paired_ci(rows, "flat_5r", "flat_2r")
    a5 = agg([r["flat_5r"] for r in rows])
    mg5 = months_green(rows, "flat_5r")
    W(f"| flat_5r vs flat_2r | {a5['n']} | {a5['wr']:.1f}% | ${a5['mean']*RISK_DOLLARS:+.0f} "
      f"| {mg5[0]}/{mg5[1]} | {'/'.join(map(str, weeks_green(rows,'flat_5r')))} | "
      f"{o5*RISK_DOLLARS:+.0f} [{l5*RISK_DOLLARS:+.0f}, {h5*RISK_DOLLARS:+.0f}] | "
      f"{'**yes**' if survives(l5,h5) else 'no'} | wins only {a5['wr']:.1f}% of the time |")
    ob, lb, hb, _ = paired_ci(rows, "be_1.00", "ride")
    ab = agg([r["be_1.00"] for r in rows])
    W(f"| break-even at 1R vs never | {ab['n']} | {ab['wr']:.1f}% | ${ab['mean']*RISK_DOLLARS:+.0f} "
      f"| {'/'.join(map(str, months_green(rows,'be_1.00')))} | {'/'.join(map(str, weeks_green(rows,'be_1.00')))} | "
      f"{ob*RISK_DOLLARS:+.0f} [{lb*RISK_DOLLARS:+.0f}, {hb*RISK_DOLLARS:+.0f}] | "
      f"{'**yes**' if survives(lb,hb) else 'no'} | |")
    for tname, label in (("time_15", "15-min time stop"), ("time_30", "30-min time stop"),
                        ("time_45", "45-min time stop")):
        ot, lt, ht, _ = paired_ci(rows, tname, "ride")
        at = agg([r[tname] for r in rows])
        W(f"| {label} vs no clock | {at['n']} | {at['wr']:.1f}% | ${at['mean']*RISK_DOLLARS:+.0f} "
          f"| {'/'.join(map(str, months_green(rows,tname)))} | {'/'.join(map(str, weeks_green(rows,tname)))} | "
          f"{ot*RISK_DOLLARS:+.0f} [{lt*RISK_DOLLARS:+.0f}, {ht*RISK_DOLLARS:+.0f}] | "
          f"{'**yes**' if survives(lt,ht) else 'no'} | |")
    ofc, lfc, hfc, _ = paired_ci(rows, "fac", "ride")
    afc = agg([r["fac"] for r in rows])
    W(f"| first adverse close vs no clock | {afc['n']} | {afc['wr']:.1f}% | ${afc['mean']*RISK_DOLLARS:+.0f} "
      f"| {'/'.join(map(str, months_green(rows,'fac')))} | {'/'.join(map(str, weeks_green(rows,'fac')))} | "
      f"{ofc*RISK_DOLLARS:+.0f} [{lfc*RISK_DOLLARS:+.0f}, {hfc*RISK_DOLLARS:+.0f}] | "
      f"{'**yes**' if survives(lfc,hfc) else 'no'} | |")
    W("")

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(A) + "\n")
    print(f"wrote {OUT_MD} (n={n})")
    print(f"flat_2.5r vs flat_2r: {obs*RISK_DOLLARS:+.0f}/trade [{lo*RISK_DOLLARS:+.0f}, {hi*RISK_DOLLARS:+.0f}]  real={survives(lo,hi)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
