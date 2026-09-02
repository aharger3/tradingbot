"""g94 -- did the RETEST_REQUIRED book reproduce what g93 predicted?

`research/g93_retest_gate_ab.py` priced the gate as a SELECTION arm: it removed
candidates tripping `no_retest` from the committed book's own recorded fields and
re-picked the day's first. That is cheap and it is not the engine. This compares
it against a real `backtest_2y.py` run with `RETEST_REQUIRED=1`.

    RETEST_REQUIRED=1 python backtest_2y.py --out research/bt2y_trades_retest_on.json
    python research/g94_retest_book_compare.py

WHAT MUST MATCH, AND WHAT MAY NOT. Detection is unchanged by a C cap, so the
candidate POPULATION must be identical row-for-row; only grades move. If signal
count differs at all, the wiring is touching detection and the gate is wrong.

The MONEY may legitimately differ, and pretending otherwise would be the mistake:

  * `loss_halt` halts a symbol after 2 consecutive losses. Removing trades
    changes which losses are consecutive, so the halt pattern moves and days the
    selection arm never modelled open or close.
  * the 84% re-entry arms off a stop-out that may no longer be taken.
  * dedupe is per level and per window; a capped row changes what the next row
    de-dupes against.

So the selection arm is a FORECAST, not a specification. This script reports the
gap and names it. A large gap is information about the flag's second-order
effects, not automatically a bug — but a gap in the SIGNAL COUNT is always a bug.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g91_lane_slice as g91                      # noqa: E402

OFF = os.path.join(HERE, "bt2y_trades.json")
ON = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_MD = os.path.join(HERE, "g94_retest_book_compare.md")

# What g93's selection arm forecast for the full pool, one trade a day.
FORECAST = {"per_day": 36.0, "cands_per_day": 14.2, "green_n": 15, "win": 46.9}


def load(p):
    b = json.load(open(p, encoding="utf-8"))
    return (b["trades"], b.get("meta", {})) if isinstance(b, dict) else (b, {})


def oneaday(rows, pred=lambda r: True):
    sub = [r for r in rows if pred(r)]
    byday = g86.candidates(sub)
    firsts = [byday[d][0] for d in sorted(byday) if byday[d]]
    daily = defaultdict(float)
    for r in firsts:
        daily[r["day"]] += r["pnl"]
    n = len(daily)
    if not n:
        return {}
    g, m = g91.months_green(daily)
    path = g91.path_risk(daily, 2000.0, 2500.0)
    return {"cands_per_day": round(sum(len(v) for v in byday.values()) / n, 1),
            "days": n, "green": "%d/%d" % (g, m), "green_n": g,
            "max_dd": path["max_dd"], "funded_per_day": path["funded_per_day"],
            **g86.stats(firsts, n)}


def main():
    if not os.path.exists(ON):
        raise SystemExit("no ON book yet -- run:\n  RETEST_REQUIRED=1 python "
                         "backtest_2y.py --out research/bt2y_trades_retest_on.json")
    off, moff = load(OFF)
    on, mon = load(ON)

    print("OFF book: %s  signals=%d traded=%d  flags.RETEST_REQUIRED=%s"
          % (moff.get("stamp", {}).get("book_id", "?")[:12], len(off),
             moff.get("traded"),
             moff.get("stamp", {}).get("flags", {}).get(
                 "signal_runner.RETEST_REQUIRED", "NOT STAMPED")))
    print("ON  book: %s  signals=%d traded=%d  flags.RETEST_REQUIRED=%s"
          % (mon.get("stamp", {}).get("book_id", "?")[:12], len(on),
             mon.get("traded"),
             mon.get("stamp", {}).get("flags", {}).get(
                 "signal_runner.RETEST_REQUIRED", "NOT STAMPED")))

    # --- the hard gate: detection must not have moved --------------------
    ok_pop = len(off) == len(on)
    print("\nDETECTION UNCHANGED: %s (%d vs %d signals)"
          % ("PASS" if ok_pop else "*** FAIL ***", len(off), len(on)))
    if ok_pop:
        key = lambda r: (r["day"], r["sym"], r["et"], r["dir"])
        same = sum(1 for a, b in zip(sorted(off, key=key), sorted(on, key=key))
                   if key(a) == key(b))
        print("  row-for-row identity on (day, sym, et, dir): %d/%d" % (same, len(off)))

    # --- what actually moved ---------------------------------------------
    import collections
    go = collections.Counter(r["grade"] for r in off)
    gn = collections.Counter(r["grade"] for r in on)
    print("\ngrade mix   %-28s -> %s" % (dict(sorted(go.items())),
                                         dict(sorted(gn.items()))))
    capped = sum(1 for r in on if "RETEST_REQUIRED" in (r.get("reason") or ""))
    print("rows carrying the cap reason: %d" % capped)

    rows_md = []
    for lane, pred in (("full pool", lambda r: True),
                       ("index QQQ/SPY/IWM", lambda r: r["sym"] in g91.INDEX)):
        a, b = oneaday(off, pred), oneaday(on, pred)
        if not a or not b:
            continue
        print("\n=== %s, one trade a day ===" % lane)
        print("  %-12s %8s %8s %8s" % ("", "OFF", "ON", "delta"))
        for k, lab, fmt in (("cands_per_day", "cand/day", "%.1f"),
                            ("per_day", "$/day", "%.0f"),
                            ("win_pct", "win %", "%.1f"),
                            ("green_n", "green mo", "%d"),
                            ("max_dd", "max DD", "%.0f"),
                            ("funded_per_day", "funded $/d", "%.2f")):
            va, vb = a.get(k), b.get(k)
            if va is None or vb is None:
                continue
            print(("  %-12s " + fmt + " " * 4 + fmt + " " * 4 + "%+.1f")
                  % (lab, va, vb, vb - va))
        rows_md.append((lane, a, b))

    # --- forecast vs reality ---------------------------------------------
    full_on = oneaday(on)
    print("\n=== g93 selection FORECAST vs the real book (full pool) ===")
    verdict = []
    for k, lab, tol in (("per_day", "$/day", 8.0),
                        ("cands_per_day", "cand/day", 1.5),
                        ("green_n", "green months", 2)):
        want, got = FORECAST[k], full_on.get(k)
        hit = got is not None and abs(got - want) <= tol
        verdict.append(hit)
        print("  %-13s forecast %-8s real %-8s  %s"
              % (lab, want, got, "within tol" if hit else "*** OUTSIDE tol ***"))
    print("\n%s" % ("FORECAST HELD -- the selection arm modelled the flag well."
                    if all(verdict) else
                    "FORECAST MISSED. Not automatically a bug: loss_halt, the 84% "
                    "re-entry and dedupe all depend on trade SEQUENCE, which a "
                    "selection arm cannot model. The real book is the answer; "
                    "g93's table must be re-labelled a forecast wherever it is quoted."))

    md = ["# g94 -- RETEST_REQUIRED, the real 2-year book", "",
          "`RETEST_REQUIRED=1 python backtest_2y.py`. OFF book "
          "`research/bt2y_trades.json`, ON book `research/bt2y_trades_retest_on.json`.",
          "", "Detection unchanged: **%s** (%d vs %d signals). Rows carrying the "
          "cap: **%d**." % ("PASS" if ok_pop else "FAIL", len(off), len(on), capped),
          "", "| lane | metric | OFF | ON | delta |", "|---|---|---:|---:|---:|"]
    for lane, a, b in rows_md:
        for k, lab, fmt in (("cands_per_day", "cand/day", "%.1f"),
                            ("per_day", "$/day", "%.0f"),
                            ("win_pct", "win %", "%.1f"),
                            ("green_n", "green months", "%d"),
                            ("max_dd", "max DD $", "%.0f")):
            if a.get(k) is None or b.get(k) is None:
                continue
            md.append(("| %s | %s | " + fmt + " | " + fmt + " | %+.1f |")
                      % (lane, lab, a[k], b[k], b[k] - a[k]))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s" % OUT_MD)


if __name__ == "__main__":
    main()
