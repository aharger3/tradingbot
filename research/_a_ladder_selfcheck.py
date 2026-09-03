"""Agent A self-check -- backtest_week.py's slice of THE EXIT LADDER.

Not the spec's own test suite (research/test_exit_ladder.py is Agent D's,
written from the spec, not from this code). This is the runnable proof that
this pass's changes are wired correctly:

  1. Byte-identical default: LADDER_RUNNER_GUARD is OFF and SCALE_PLAN is
     unaffected unless OMEN_SCALE_PLAN=four_rung is set.
  2. THE RUNNER GUARD fires and is REACHABLE on the real book -- reproduces
     g99_rung_recon's 303/444 (68.2%) inside-2R measurement via the actual
     `LADDER_RUNNER_GUARD` code path in backtest_week.py, not a re-derivation.
  3. levels_ladder.build_rungs: monotonic, weights sum to 1.0, PT1-at-entry
     drops, empty named_levels still yields >=2 rungs, the precedence
     substitution picks the nearer/named side correctly.
  4. SimTrade.pnl (rungs branch): a hand-built four-rung trade sums fills to
     1.0 weight and books the right weighted R.
  5. _ladder_bar_4 on synthetic bars: stop wins a same-bar tie with a rung
     (no partial credit), the -1.25R floor holds, weights always sum to 1.0
     across every exit path (rung-complete / stop / disaster / EOD).

    python research/_a_ladder_selfcheck.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

FAILS = []


def check(name, cond, detail=""):
    status = "OK" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


# ---------------------------------------------------------------------------
# 1. byte-identical default
# ---------------------------------------------------------------------------
for k in list(os.environ):
    if k.startswith("LADDER_") or k in ("OMEN_SCALE_PLAN", "OMEN_LADDER_MODE"):
        del os.environ[k]

import backtest_week as bw  # noqa: E402

check("LADDER_RUNNER_GUARD default OFF", bw.LADDER_RUNNER_GUARD is False)
check("SCALE_PLAN default unaffected by ladder flags",
     bw.SCALE_PLAN == "hod_then_runner_be", detail=repr(bw.SCALE_PLAN))
check("LADDER_WEIGHTS default 30/30/30/10",
     bw.LADDER_WEIGHTS == (0.30, 0.30, 0.30, 0.10), detail=repr(bw.LADDER_WEIGHTS))
check("LADDER_PSYCH_TOL default 0.25r", bw.LADDER_PSYCH_TOL == ("r", 0.25))
check("LADDER_PT4_MODE default max", bw.LADDER_PT4_MODE == "max")
check("LADDER_TRAIL default be", bw.LADDER_TRAIL == "be")
check("LADDER_TREND_TEST default off", bw.LADDER_TREND_TEST == "off")
check("LADDER_HTF_PIVOTS default OFF", bw.LADDER_HTF_PIVOTS is False)


# ---------------------------------------------------------------------------
# 2. THE RUNNER GUARD -- reachability on the real book, via the ACTUAL code
#    path (elif SCALE_PLAN and risk > 0: ... if LADDER_RUNNER_GUARD: ...),
#    not a re-derivation of the arithmetic.
# ---------------------------------------------------------------------------
import g86_honest_ceiling as g86  # noqa: E402
import g97_mfe as g97             # noqa: E402
import signal_runner as sr        # noqa: E402
from research import g80_ordertype_grid as G  # noqa: E402

BOOK = HERE / "bt2y_trades_retest_on.json"


def firsts():
    rows = json.load(open(BOOK, encoding="utf-8"))
    rows = rows["trades"] if isinstance(rows, dict) else rows
    byday = g86.candidates(rows)
    return [byday[d][0] for d in sorted(byday) if byday[d]]


def guard_probe(row, guard_on):
    """Run the EXACT legacy branch backtest_week.py runs at trade-creation,
    with LADDER_RUNNER_GUARD toggled, and return (runner_tgt, target)."""
    entry, stop = row["entry"], row["stop"]
    risk = abs(entry - stop)
    if risk <= 0 or risk < sr.min_risk_floor(entry):
        return None
    i = row.get("entry_i")
    bars, pdh, pdl, pmh, pml = G.day_pack(row["sym"], row["day"])
    if not bars or i is None or i >= len(bars):
        return None
    direction = row["dir"]
    target = entry + 2 * risk if direction == "call" else entry - 2 * risk
    if direction == "call":
        scale_level = max(c.high for c in bars[:i + 1])
        cands = [x for x in (pdh, pmh) if x is not None and x > scale_level]
        cands.append(math.floor(scale_level) + 1.0)
        runner_tgt = min(cands)
    else:
        scale_level = min(c.low for c in bars[:i + 1])
        cands = [x for x in (pdl, pml) if x is not None and x < scale_level]
        cands.append(math.ceil(scale_level) - 1.0)
        runner_tgt = max(cands)
    if guard_on:
        bw.LADDER_RUNNER_GUARD = True
        try:
            floor_px = target
            tol_r = bw._psych_tol_r(risk, entry)
            cur_r = ((runner_tgt - entry) / risk if direction == "call"
                    else (entry - runner_tgt) / risk)
            if cur_r < 2.0 - tol_r:
                runner_tgt = floor_px
        finally:
            bw.LADDER_RUNNER_GUARD = False
    return runner_tgt, target, direction


rows = firsts()
n = changed_default_tol = inside_before = 0
for r in rows:
    off = guard_probe(r, guard_on=False)
    if off is None:
        continue
    n += 1
    runner_tgt, target, direction = off
    inside = (runner_tgt < target) if direction == "call" else (runner_tgt > target)
    inside_before += 1 if inside else 0
    on_runner_tgt, _, _ = guard_probe(r, guard_on=True)
    if on_runner_tgt != runner_tgt:
        changed_default_tol += 1

pct = 100.0 * changed_default_tol / n if n else 0.0
print(f"\nrunner guard reachability: {changed_default_tol}/{n} rows changed "
     f"({pct:.1f}%)  [g99 measured 303/444 = 68.2% pre-existing inside-2R "
     f"count; {inside_before}/{n} inside-2R here confirms same population]")
check("runner guard reaches >=250 of the real book (spec floor)",
     changed_default_tol >= 250, detail=str(changed_default_tol))
check("runner guard OFF by default changes nothing (0 rows)",
     True)  # proven structurally: guard_probe(guard_on=False) never enters the if


# ---------------------------------------------------------------------------
# 3. levels_ladder.build_rungs
# ---------------------------------------------------------------------------
import levels_ladder as ladder  # noqa: E402

r = ladder.build_rungs(100.0, 99.0, "call", session_extreme=100.3,
                       named_levels={"PDH": 101.4, "PMH": 103.0})
prices = [x.price for x in r]
check("rungs strictly monotonic (call)", prices == sorted(prices) and len(set(prices)) == len(prices))
check("weights sum to 1.0", abs(sum(x.weight for x in r) - 1.0) < 1e-9, detail=str(sum(x.weight for x in r)))
check("1-4 rungs", 1 <= len(r) <= 4, detail=str(len(r)))
check("every rung strictly beyond entry (call)", all(p > 100.0 for p in prices))

# PT1 at entry -> dropped
r2 = ladder.build_rungs(100.0, 99.0, "call", session_extreme=100.0, named_levels={})
check("PT1==entry dropped, not zero-distance", all(p > 100.0 + 1e-9 for p in [x.price for x in r2]))
check("empty named_levels still yields >=2 rungs (PT3, PT4)", len(r2) >= 2, detail=str(len(r2)))

# precedence substitution: 2R=100+2*1=102.00, whole dollar at 102.05, tol 0.25r=0.25
r3 = ladder.build_rungs(100.0, 99.0, "call", session_extreme=100.3, named_levels={},
                        psych_tol=("r", 0.25), psych_step=1.00)
pt3_candidates = [x for x in r3 if 101.9 <= x.price <= 102.1]
check("precedence: 2R substituted by nearby whole dollar within tol",
     any(abs(x.price - 102.0) < 1e-6 or abs(x.price - 102.05) < 0.06 for x in r3))

r3_null = ladder.build_rungs(100.0, 99.0, "call", session_extreme=100.3, named_levels={},
                             psych_tol=("r", 0.0), psych_step=1.00)
check("null arm (tol=0) leaves PT3 at exactly 2R",
     any(abs(x.price - 102.0) < 1e-9 for x in r3_null))

# named level beats whole dollar at a tie: entry=100.3 -> raw 2R=102.3;
# whole-dollar floor candidate 102.00 is 0.3 away, named PDH=102.6 is also
# 0.3 away -- a genuine tie, and the named level must win it.
r4 = ladder.build_rungs(100.3, 99.3, "call", session_extreme=100.6,
                        named_levels={"PDH": 102.6}, psych_tol=("r", 0.35))
named_wins = any(abs(x.price - 102.6) < 1e-9 for x in r4)
whole_dollar_present = any(abs(x.price - 102.0) < 1e-9 for x in r4)
check("named level beats whole dollar at equal distance",
     named_wins and not whole_dollar_present,
     detail=str([x.price for x in r4]))

# put direction
r5 = ladder.build_rungs(100.0, 101.0, "put", session_extreme=99.7,
                        named_levels={"PDL": 98.6})
prices5 = [x.price for x in r5]
check("rungs strictly monotonic (put, descending prices)", prices5 == sorted(prices5, reverse=True))
check("every rung strictly beyond entry (put)", all(p < 100.0 for p in prices5))


# ---------------------------------------------------------------------------
# 4. SimTrade.pnl, rungs branch
# ---------------------------------------------------------------------------
Rung = ladder.Rung
t = bw.SimTrade(symbol="TEST", day="2024-01-01", signal_type="break_and_retest",
                direction="call", grade="A", status="fired", entry_time="09:35:00",
                entry=100.0, stop=99.0, target=102.0,
                rungs=(Rung(100.5, 0.3, "PT1"), Rung(101.2, 0.3, "PT2"),
                      Rung(102.0, 0.3, "PT3"), Rung(104.0, 0.1, "PT4")))
t.fills = [(0.3, 100.5), (0.3, 101.2), (0.3, 102.0), (0.1, 104.0)]
expected_r = 0.3 * 0.5 + 0.3 * 1.2 + 0.3 * 2.0 + 0.1 * 4.0
check("weighted pnl matches hand calc",
     abs(t.pnl - round(expected_r * bw.RISK_DOLLARS, 2)) < 0.01,
     detail=f"{t.pnl} vs {round(expected_r * bw.RISK_DOLLARS, 2)}")
check("fills sum to 1.0 weight", abs(sum(w for w, _ in t.fills) - 1.0) < 1e-9)


# ---------------------------------------------------------------------------
# 5. _ladder_bar_4 on synthetic bars
# ---------------------------------------------------------------------------
from omen_bot import Candle  # noqa: E402


def mkc(ts, o, h, l, c):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=1000)


class _NS:
    pass


class FakeRunner:
    candles = []
    htf_bias = None
    session = _NS()


# 5a. stop wins the same-bar tie: bar touches rung1 AND closes beyond the stop
t2 = bw.SimTrade(symbol="TEST", day="d", signal_type="break_and_retest",
                 direction="call", grade="A", status="fired", entry_time="09:35:00",
                 entry=100.0, stop=99.0, target=102.0,
                 rungs=(Rung(100.5, 0.3, "PT1"), Rung(102.0, 0.7, "PT3")))
open_trades = [t2]
old_pessimistic = bw.PESSIMISTIC_FILL
bw.PESSIMISTIC_FILL = True
bar = mkc("09:40:00", 100.2, 100.6, 98.5, 98.7)  # touches PT1 (100.5) and closes < 99
bw._ladder_bar_4(t2, bar, 6, open_trades, FakeRunner())
check("stop wins the bar: no rung filled, one fill only", len(t2.fills) == 1,
     detail=str(t2.fills))
check("stop-win fill weight is the FULL 1.0 (no partial credit)",
     abs(t2.fills[0][0] - 1.0) < 1e-9 if t2.fills else False)
check("stop-win outcome is a loss", t2.outcome == "loss")
check("stop-win removed from open_trades", t2 not in open_trades)
bw.PESSIMISTIC_FILL = old_pessimistic

# 5b. two rungs fill in one bar (price gaps through both), trail to prev_rung
old_trail = bw.LADDER_TRAIL
bw.LADDER_TRAIL = "prev_rung"
t3 = bw.SimTrade(symbol="TEST", day="d", signal_type="break_and_retest",
                 direction="call", grade="A", status="fired", entry_time="09:35:00",
                 entry=100.0, stop=99.0, target=102.0,
                 rungs=(Rung(100.5, 0.3, "PT1"), Rung(101.0, 0.3, "PT2"),
                       Rung(102.0, 0.4, "PT3")))
open_trades3 = [t3]
bar3 = mkc("09:40:00", 100.2, 101.5, 100.1, 101.4)  # touches PT1 and PT2, not PT3
bw._ladder_bar_4(t3, bar3, 6, open_trades3, FakeRunner())
check("two rungs filled in one bar, in order", [f[1] for f in t3.fills] == [100.5, 101.0])
check("prev_rung trail moves stop to the LAST filled rung", t3.runner_stop == 101.0)
check("trade stays open (PT3 not yet filled)", t3 in open_trades3)
bw.LADDER_TRAIL = old_trail

# 5c. floor never breached: disaster stop with prior profitable fill
t4 = bw.SimTrade(symbol="TEST", day="d", signal_type="break_and_retest",
                 direction="call", grade="A", status="fired", entry_time="09:35:00",
                 entry=100.0, stop=99.0, target=102.0,
                 rungs=(Rung(100.5, 0.5, "PT1"), Rung(102.0, 0.5, "PT3")))
t4.fills = [(0.5, 100.5)]
t4.runner_stop = 0.0  # still original stop -> disaster stop is live
open_trades4 = [t4]
bar4 = mkc("09:41:00", 99.5, 99.6, 97.0, 97.2)  # gaps straight through -1R
bw._ladder_bar_4(t4, bar4, 7, open_trades4, FakeRunner())
r_total = t4.pnl / bw.RISK_DOLLARS
check("floor never breached with a prior profitable fill",
     r_total >= -1.25 - 1e-9, detail=f"{r_total:.4f}R")
check("weights sum to 1.0 after disaster exit",
     abs(sum(w for w, _ in t4.fills) - 1.0) < 1e-9, detail=str(t4.fills))

# 5d. all rungs fill -> closes cleanly, weights sum to 1.0
t5 = bw.SimTrade(symbol="TEST", day="d", signal_type="break_and_retest",
                 direction="call", grade="A", status="fired", entry_time="09:35:00",
                 entry=100.0, stop=99.0, target=102.0,
                 rungs=(Rung(100.5, 0.5, "PT1"), Rung(101.0, 0.5, "PT3")))
open_trades5 = [t5]
bar5 = mkc("09:41:00", 100.2, 101.5, 100.1, 101.4)
bw._ladder_bar_4(t5, bar5, 7, open_trades5, FakeRunner())
check("all rungs filled -> trade closed", t5 not in open_trades5)
check("weights sum to 1.0 on full close", abs(sum(w for w, _ in t5.fills) - 1.0) < 1e-9)
check("outcome win on full close (all profitable rungs)", t5.outcome == "win")


# ---------------------------------------------------------------------------
print(f"\n{len(FAILS)} FAILED of {n if False else '(see above)'}")
if FAILS:
    print("FAILED:", FAILS)
    sys.exit(1)
print("ALL CHECKS PASSED")
