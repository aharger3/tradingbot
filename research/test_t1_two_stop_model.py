"""T1 — sanity checks on `research/t1_two_stop_model.py`'s own scoring code,
on hand-built rows. Not a re-check of the disaster-stop mechanism itself
(`research/test_t0_disaster_stop.py` owns that, 7/7 green) — this only checks
that T1's `stats()` and `recovery_cost()` compute what they claim to on a
book small enough to verify by hand.

Run: python research/test_t1_two_stop_model.py   (exit 0 = green)
"""
from __future__ import annotations
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t1_two_stop_model as t1

FAIL = []


def check(cond, msg):
    print(("  ok  " if cond else "  FAIL") + "  " + msg)
    if not cond:
        FAIL.append(msg)


def row(sym="AAA", day="2026-01-02", et="09:45", setup="break_and_retest",
       dir="call", out="loss", r=-1.0, exit_via="disaster", entry=100.0):
    return {"key": (sym, day, et, setup, dir, round(entry, 4)),
            "sym": sym, "cls": "stock", "day": day, "ym": day[:7], "dow": "Fri",
            "et": et, "setup": setup, "dir": dir, "grade": "B", "traded": True,
            "out": out, "r": r, "exit_via": exit_via, "level": "other",
            "dret": "bull"}


print("t1_two_stop_model — stats()")

# 2 wins (+2R each), 1 loss (-1R), one green month, one red -> months differ.
book = [
    row(day="2026-01-05", r=2.0, out="win", exit_via="target"),
    row(day="2026-01-06", r=2.0, out="win", exit_via="target"),
    row(day="2026-02-05", r=-1.0, out="loss", exit_via="disaster"),
]
s = t1.stats(book)
check(abs(s["mean_r"] - 1.0) < 1e-9, "mean_r averages the three rows correctly")
check(abs(s["win_rate"] - 100.0 * 2 / 3) < 1e-9, "win_rate = wins / (wins+losses)")
check(s["months_green"] == 1 and s["months"] == 2,
      "Jan (+4R) green, Feb (-1R) red -- 1 of 2 months green")
check(s["exit_via"]["disaster"] == 1 and s["exit_via"]["target"] == 2,
      "exit_via tally matches the tagged rows")
check(s["max_dd_r"] == 1.0,
      "drawdown from the +4R peak down to +3R after the Feb loss is 1.0R")
check(t1.stats([]) is None, "an empty book returns None, not a crash")

print("\nt1_two_stop_model — recovery_cost()")

# Two disaster exits with a matching key in the clamp book: one recovers to a
# win, one stays a loss under the clamp too. A third disaster exit has NO
# match in clamp (simulating a missing/duplicate key) and must be counted as
# unmatched, never silently dropped or silently counted as a win.
disaster_book = [
    row(sym="WON", r=-1.0, exit_via="disaster"),
    row(sym="LOST", r=-1.0, exit_via="disaster"),
    row(sym="ORPHAN", r=-1.0, exit_via="disaster"),
    row(sym="NOTKILLED", r=2.0, out="win", exit_via="target"),  # not a disaster exit
]
clamp_book = [
    row(sym="WON", r=3.5, out="win", exit_via="target"),   # recovered under clamp
    row(sym="LOST", r=-1.25, out="loss", exit_via="level"),  # stayed a loss
]
rc = t1.recovery_cost(disaster_book, clamp_book, "test-arm")
check(rc["disaster_exits"] == 3, "only the 3 disaster-tagged rows count, not the target exit")
check(rc["matched_to_clamp"] == 2, "2 of 3 disaster exits have a clamp-arm match")
check(rc["unmatched_or_duplicate_key"] == 1, "the orphan key is reported, not dropped")
check(rc["would_have_won_under_clamp"] == 1, "WON recovers to a win under the clamp")
check(rc["would_have_lost_under_clamp"] == 1, "LOST stays a loss under the clamp too")
check(abs(rc["recovery_rate_pct"] - 50.0) < 1e-9, "recovery rate is of MATCHED trades (1 of 2), not all 3")
check(abs(rc["total_r_given_up"] - (3.5 - -1.0)) < 1e-9,
      "R given up on the recovered trade is the clamp outcome minus the disaster exit's own R")

print("\n%d checks, %d failed" % (7 + 8, len(FAIL)))
sys.exit(1 if FAIL else 0)
