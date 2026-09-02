"""g94 -- did the RETEST_REQUIRED book reproduce what g93 predicted?

`research/g93_retest_gate_ab.py` priced the gate as a SELECTION arm: it removed
candidates tripping `no_retest` from the committed book's own recorded fields and
re-picked the day's first. That is cheap and it is not the engine. This compares
it against a real `backtest_2y.py` run with `RETEST_REQUIRED=1`.

    RETEST_REQUIRED=1 python backtest_2y.py --out research/bt2y_trades_retest_on.json
    python research/g94_retest_book_compare.py

THE INVARIANT THIS SCRIPT ORIGINALLY ASSERTED WAS WRONG, and the correction is
the most useful thing it now knows. "A C cap cannot change the candidate
population" is false in this engine, by design:

  * `backtest_week.DEDUPE_FIRES_ONLY` defaults to 1, and at
    backtest_week.py:973 only a signal whose `status == "fired"` claims or
    extends the dedupe suppression window. A capped candidate is not fired, so
    it RELEASES the window and later candidates on the same level -- previously
    suppressed -- become rows. That is why the ON book has MORE signals.
  * the 84% re-entry is a detection that only exists if a prior trade stopped
    out, so capping one removes its re-entry entirely.
  * `loss_halt` halts a symbol after 2 consecutive losses; changing which trades
    are taken moves the halt pattern, opening and closing whole days.

All three are trade-SEQUENCE effects. None can be modelled by a selection arm
over a fixed book, which is precisely why g93's table is a FORECAST and this
re-run is the answer. The population delta is reported and classified by setup
type; what must NOT change is any row present in both books.
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

# The matched pair: same commit, same window, ONLY the flag differs. The
# shipped research/bt2y_trades.json is NOT usable as the OFF arm here -- it was
# built 2026-08-30 at a different commit with research/downgrade.py dirty, and
# --days 730 counts back from today so its window is 500 sessions to the ON
# book's 498. Comparing against it confounds the flag with three days of
# calendar and one dirty engine file.
OFF = os.path.join(HERE, "bt2y_trades_retest_off.json")
ON = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_MD = os.path.join(HERE, "g94_retest_book_compare.md")

# What g93's selection arm forecast for the full pool, one trade a day.
FORECAST = {"per_day": 36.0, "cands_per_day": 14.2, "green_n": 15, "win": 46.9}


def load(p):
    b = json.load(open(p, encoding="utf-8"))
    return (b["trades"], b.get("meta", {})) if isinstance(b, dict) else (b, {})


def common_window(off, on):
    """Restrict both books to the sessions they share.

    `backtest_2y.py --days 730` counts back from TODAY, so a book built on
    2026-08-30 and one built on 2026-09-02 cover different windows (500 vs 498
    sessions here) and differ in signal count for a reason that has nothing to do
    with the flag. Detection is independent per session, so intersecting the day
    sets gives an exact controlled comparison without paying for a second
    four-hour rebuild. Without this the "detection unchanged" gate below fails on
    the calendar rather than on the code, which would be a false alarm loud
    enough to bury the real result.
    """
    days = {r["day"] for r in off} & {r["day"] for r in on}
    return ([r for r in off if r["day"] in days],
            [r for r in on if r["day"] in days], days)


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

    # --- control for the calendar before comparing anything --------------
    raw_off, raw_on = len(off), len(on)
    off, on, days = common_window(off, on)
    print("\ncommon window: %d sessions %s..%s  (dropped %d OFF rows, %d ON rows "
          "that fall outside it)"
          % (len(days), min(days), max(days), raw_off - len(off), raw_on - len(on)))

    # --- the real gate: no SHARED row may move ---------------------------
    import collections
    key = lambda r: (r["day"], r["sym"], r["et"], r["dir"])
    mo = {key(r): r for r in off}
    mn = {key(r): r for r in on}
    shared = set(mo) & set(mn)
    moved = [k for k in shared
             if abs(mo[k]["entry"] - mn[k]["entry"]) > 1e-9
             or abs(mo[k]["stop"] - mn[k]["stop"]) > 1e-9]
    print("SHARED ROWS UNMOVED: %s (%d shared; %d with a changed entry or stop)"
          % ("PASS" if not moved else "*** FAIL ***", len(shared), len(moved)))
    for k in moved[:3]:
        print("      %s entry %.4f->%.4f stop %.4f->%.4f"
              % (k, mo[k]["entry"], mn[k]["entry"], mo[k]["stop"], mn[k]["stop"]))

    # The population delta is EXPECTED (see the module docstring): a capped row
    # releases the dedupe window, and the 84% re-entry is itself a detection.
    oo, nn = set(mo) - set(mn), set(mn) - set(mo)
    print("population delta: %d OFF-only, %d ON-only  (expected -- dedupe release "
          "+ 84%% re-entry, NOT a wiring bug)" % (len(oo), len(nn)))
    for lab, sset, m in (("  OFF-only", oo, mo), ("  ON-only ", nn, mn)):
        print("%s by setup: %s" % (lab, dict(collections.Counter(
            m[k]["setup"] for k in sset))))

    # --- what actually moved ---------------------------------------------
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
          "", "Shared rows unmoved: **%s** (%d shared, %d moved). Population "
          "delta %d OFF-only / %d ON-only -- expected, from dedupe release and "
          "the 84%% re-entry. Rows carrying the cap: **%d**."
          % ("PASS" if not moved else "FAIL", len(shared), len(moved),
             len(oo), len(nn), capped),
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
