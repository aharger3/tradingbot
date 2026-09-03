"""g75_lateness_brcensus.py -- the control arm for the gate census.

Same 120 symbol-days, same bars, but walking the BREAK-AND-RETEST chain on
Austin's four pre-bell levels (PDH/PDL/PMH/PML). If the one-candle rule's
early-window blackout is mechanical -- caused by the level not existing yet --
then break-and-retest, whose level DOES exist at 9:30, should show no blackout.

Read-only. Writes research/g75_lateness_brcensus.json.
"""
from __future__ import annotations
import json, os, random, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as T4
from g75_lateness_cases import br_trace

BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT = os.path.join(HERE, "g75_lateness_brcensus.json")
N = int(os.environ.get("G75_SAMPLE", "120"))
RNG = random.Random(7503)          # SAME seed as the gate census -> same days

rows = json.load(open(BOOK, encoding="utf-8"))["trades"]
days = sorted({(r["sym"], r["day"]) for r in rows})
RNG.shuffle(days)
days = days[:N]

PLAIN = {
    "no_break": "price never closed through the level in the window",
    "no_leave": "it broke but never actually left the level",
    "no_retest": "it left but never came back to the level",
    "stale_retest": "the retest was too long ago to enter on this bar",
    "no_confirm_close": "this bar is not a confirm close",
    "adverse_wick": "the entry bar has a big wick against the trade",
    "too_short": "not enough bars yet",
    "passed": "PASS -- an entry",
}
early, late = Counter(), Counter()
for k, (sym, day) in enumerate(days):
    candles = T4.rth_candles(sym, day)
    if not candles or len(candles) < 40:
        continue
    pdh, pdl, _o, _c = T4.prior_day_levels(sym, day)
    pmh, pml = T4.premarket_extremes(sym, day)
    lv = [(pdh, True), (pmh, True), (pdl, False), (pml, False)]
    lv = [(p, L) for p, L in lv if p]
    end = min(len(candles) - 1, 90)
    for i in range(5, end + 1):
        for p, is_long in lv:
            s = br_trace(candles, i, p, is_long)
            (early if i < 30 else late)[s] += 1
    if (k + 1) % 40 == 0:
        print("  ... %d/%d" % (k + 1, len(days)), flush=True)

te, tl = sum(early.values()), sum(late.values())
print()
print("=" * 96)
print("WHERE THE BREAK-AND-RETEST CHAIN DIES, ON HIS FOUR PRE-BELL LEVELS (%d days)" % N)
print("=" * 96)
print("  %-58s %11s %11s" % ("first condition that was false", "9:30-10:00", "10:00-11:00"))
for s in ["too_short", "no_break", "no_leave", "no_retest", "stale_retest",
          "no_confirm_close", "adverse_wick", "passed"]:
    if not early[s] and not late[s]:
        continue
    print("  %-58s %10.2f%% %10.2f%%"
          % (PLAIN[s], 100.0 * early[s] / te, 100.0 * late[s] / tl))
print("  %-58s %10d  %10d" % ("(level-bars examined)", te, tl))
print()
print("  entry rate 9:30-10:00 vs 10:00-11:00: %.3f%% vs %.3f%%  (ratio %.2fx)"
      % (100.0 * early["passed"] / te, 100.0 * late["passed"] / tl,
         (early["passed"] / te) / (late["passed"] / tl) if late["passed"] else float("nan")))
json.dump({"early": dict(early), "late": dict(late), "n_days": N},
          open(OUT, "w"), indent=1)
print()
print("wrote", OUT)
