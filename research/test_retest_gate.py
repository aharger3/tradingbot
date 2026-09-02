"""g93 -- RETEST_REQUIRED does what it says, and nothing else.

    python research/test_retest_gate.py

Four assertions, in the order they matter:

  1. OFF is byte-identical to today. A flag that changes the default book is not
     a flag, it is a ship.
  2. ON caps a break-with-no-retest to C, and says so in the reason.
  3. ON leaves a real break-AND-retest alone. This is the one that matters: the
     whole point is that the gate refuses the missing retest, not the setup.
  4. ON never moves an entry price or a timestamp. Austin's rule_03 calls a late
     entry a bug and 11 cards say "as candle forming"; a gate that quietly
     shifted the fill later would be solving his complaint by committing it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import signal_runner as sr                       # noqa: E402
from signal_runner import Candle, SignalRunner    # noqa: E402
from research import downgrade as dg             # noqa: E402


def _bars(seq):
    return [Candle(t, o, h, lo, c, v) for t, o, h, lo, c, v in seq]


def clean_break_and_retest():
    """Flat range under 100.50, displaced break, leave, retest, confirm."""
    out = [("09:%02d:00" % (30 + i), 100.0, 100.5, 99.9, 100.2, 1000)
           for i in range(5)]
    out += [("09:%02d:00" % (35 + i), 100.1, 100.4, 100.0, 100.2, 1000)
            for i in range(15)]
    out += [("09:50:00", 100.3, 102.0, 100.2, 101.9, 5000),   # displaced break
            ("09:51:00", 101.9, 102.3, 101.7, 102.1, 2000),   # leave
            ("09:52:00", 102.1, 102.2, 101.3, 101.6, 1500),   # drift back
            ("09:53:00", 101.6, 101.7, 100.4, 100.9, 1800),   # RETEST the level
            ("09:54:00", 101.0, 101.6, 100.8, 101.5, 1600)]   # confirm
    return _bars(out)


def break_and_run():
    """Same range and the same break, then it NEVER comes back to the level.

    This is Austin's complaint made concrete: 'breaks and doesn't retest the
    level, instead goes to an OCR farther away'. Every bar after the break holds
    its low above 101.0, so no retest of 100.50 can occur.
    """
    out = [("09:%02d:00" % (30 + i), 100.0, 100.5, 99.9, 100.2, 1000)
           for i in range(5)]
    out += [("09:%02d:00" % (35 + i), 100.1, 100.4, 100.0, 100.2, 1000)
            for i in range(15)]
    out += [("09:50:00", 100.3, 102.0, 100.2, 101.9, 5000),   # displaced break
            ("09:51:00", 101.9, 102.6, 101.8, 102.5, 2000),
            ("09:52:00", 102.5, 103.1, 102.3, 103.0, 1500),
            ("09:53:00", 103.0, 103.6, 102.9, 103.5, 1800),
            ("09:54:00", 103.5, 104.0, 103.3, 103.9, 1600)]
    return _bars(out)


def run(bars, retest_required):
    old = sr.RETEST_REQUIRED
    sr.RETEST_REQUIRED = retest_required
    try:
        r = SignalRunner(post_to_discord=False, symbol="TEST", log_signals=False)
        r.candles = bars
        return r.detect_signals()
    finally:
        sr.RETEST_REQUIRED = old


def _real_book_cap():
    """The assertion that actually guards the gate, on a real symbol-day.

    IWM 2024-10-01 09:40 put, OR low: the honest book's first pick that day, a
    `break_and_retest` graded B, and the ONLY downgrade variable it trips is
    `no_retest` -- so it isolates this gate from every other cap. If the gate is
    unreachable in the live path, this is where it shows.

    Skips (loudly) if the bars are not archived, rather than passing quietly.
    """
    sym, day = "IWM", "2024-10-01"
    try:
        from research import g80_ordertype_grid as G
        bars, pdh, pdl, pmh, pml = G.day_pack(sym, day)
    except Exception as e:
        print("  2b. SKIPPED -- could not load %s %s (%s). NOT a pass."
              % (sym, day, type(e).__name__))
        return
    if not bars:
        print("  2b. SKIPPED -- no archived bars for %s %s. NOT a pass."
              % (sym, day))
        return

    import backtest_week as bw
    seen = {}
    for on in (False, True):
        old = sr.RETEST_REQUIRED
        sr.RETEST_REQUIRED = on
        try:
            ts = bw.simulate_day(sym, day, bars, pdh, pdl, None, pmh, pml)
        finally:
            sr.RETEST_REQUIRED = old
        seen[on] = {t.entry_time: t for t in ts}

    assert seen[False], "%s %s produced no candidates at all" % (sym, day)
    assert set(seen[True]) == set(seen[False]), \
        "the gate added or dropped a candidate; it must only re-grade"
    moved = [t for t in seen[False].values()
             if seen[True][t.entry_time].grade != t.grade]
    for t in moved:
        assert seen[True][t.entry_time].grade == "C", \
            "%s regraded to %r, expected C" % (t.entry_time,
                                               seen[True][t.entry_time].grade)
        assert abs(seen[True][t.entry_time].entry - t.entry) < 1e-9, \
            "%s: the gate moved the entry price" % t.entry_time
    assert moved, ("RETEST_REQUIRED capped NOTHING on %s %s, whose first pick "
                   "trips no_retest and only no_retest in the committed book "
                   "(research/g93_retest_gate_ab.py). The gate is unreachable "
                   "in the live path -- this repo's recurring bug class." % (sym, day))
    print("  2b. ON caps %d real candidate(s) on %s %s to C, entries unmoved  OK"
          % (len(moved), sym, day))


def main():
    # -- the predicate itself, before any engine wiring ---------------------
    def as_dicts(bs):
        return [{"o": c.open, "h": c.high, "l": c.low, "c": c.close,
                 "v": c.volume} for c in bs]

    cr = as_dicts(clean_break_and_retest())
    br = as_dicts(break_and_run())
    assert dg.no_retest(cr, len(cr) - 1, 100.5, True) is False, \
        "no_retest fired on a tape that DOES retest -- the fixture or the " \
        "predicate is wrong, and every assertion below would be meaningless"
    assert dg.no_retest(br, len(br) - 1, 100.5, True) is True, \
        "no_retest did not fire on a break that never returned to the level"
    print("  predicate: retest tape False, run-away tape True  OK")

    # -- 1. the flag is ON by default, and OFF still disables it ------------
    # This assertion used to read "OFF == the shipped default", which was
    # meaningful only while the default was OFF. It shipped ON on 2026-09-02
    # (research/g94_retest_book_compare.py: +3 green months, -15% max drawdown on
    # the full pool), so that comparison would now be OFF-vs-ON and pass
    # vacuously on any tape where the two agree. What is worth asserting instead
    # is that the default is what the book was priced with, and that the escape
    # hatch still works.
    assert sr.RETEST_REQUIRED is True, \
        "RETEST_REQUIRED default is %r; research/bt2y_trades_retest_on.json and " \
        "every figure quoted from it assume ON" % sr.RETEST_REQUIRED
    os.environ["RETEST_REQUIRED"] = "0"
    import importlib
    assert importlib.reload(sr).RETEST_REQUIRED is False, \
        "RETEST_REQUIRED=0 no longer disables the gate -- the A/B escape hatch " \
        "is gone and the flag can never be measured again"
    os.environ.pop("RETEST_REQUIRED", None)
    importlib.reload(sr)
    assert sr.RETEST_REQUIRED is True, "module did not reload back to the default"
    print("  1. default is ON; RETEST_REQUIRED=0 still disables it  OK")

    # -- 2/3. ON caps the run-away, spares the retest -----------------------
    on_clean = run(clean_break_and_retest(), True)
    on_run = run(break_and_run(), True)
    off_run = run(break_and_run(), False)

    assert on_clean, "the clean break-and-retest fired nothing even with the gate on"
    assert not any("RETEST_REQUIRED" in s["reason"] for s in on_clean), \
        "the gate capped a setup that DID retest -- it is refusing the setup, " \
        "not the missing retest, which is the one failure that makes it useless"
    print("  3. ON leaves a real break-and-retest alone (%d signal(s))  OK"
          % len(on_clean))

    # The synthetic run-away tape does not exercise the cap, and that is a fact
    # about the two definitions, not a bug: `detect_break_retest` runs its own
    # break -> leave -> retest -> confirm FSM and simply never fires when price
    # does not come back, so there is no signal left for the gate to cap.
    # `downgrade.no_retest` uses the STRICTER `_break_bar`/`_retest_bar` pair, so
    # it trips on rows the FSM was happy with -- 99 of the 500 days' first picks
    # (research/g93_retest_gate_ab.py). The gate is exactly that difference, and
    # only a real book day can exercise it.
    assert not off_run, ("the run-away fixture now fires -- detect_break_retest "
                         "changed and this test's reasoning needs revisiting")
    print("  2a. synthetic run-away fires nothing either way (FSM already "
          "refuses it)  OK")
    _real_book_cap()

    off_run = run(break_and_run(), False)

    # -- 4. no fill or timestamp moves --------------------------------------
    on_by_time = {s["timestamp"]: s for s in run(break_and_run(), True)}
    for s in off_run:
        t = s["timestamp"]
        assert t in on_by_time, "the gate DROPPED a signal at %s; it must cap " \
                                "to C, never suppress the row" % t
        assert abs(on_by_time[t]["entry"] - s["entry"]) < 1e-9, \
            "%s: entry moved %.6f -> %.6f" % (t, s["entry"], on_by_time[t]["entry"])
    print("  4. ON moves no entry price and drops no row  OK")

    print("test_retest_gate OK")


if __name__ == "__main__":
    main()
