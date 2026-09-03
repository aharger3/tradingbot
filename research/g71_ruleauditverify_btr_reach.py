"""G7.1/btrverify -- is downgrade.break_then_rejection reachable?

Adversarial check of the ruleaudit claim that it is "a branch that can never be
true ... unrepresentable by construction". Pure synthetic bars, no book needed.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import downgrade as dg

def bar(o, h, l, c):
    return {"o": o, "h": h, "l": l, "c": c}

# LONG. level = 100.
# 0..3 base below, 4 closes THROUGH (up-cross), 5 closes back BELOW (rejection),
# 6..8 stay at/below the level -> no new up-cross -> _break_bar still returns 4.
bars = [
    bar(99.0, 99.3, 98.7, 99.0),
    bar(99.0, 99.4, 98.8, 99.1),
    bar(99.1, 99.5, 98.9, 99.2),
    bar(99.2, 99.6, 99.0, 99.4),
    bar(99.4, 101.0, 99.3, 100.6),   # 4: prev.c 99.4 <= 100 < 100.6  -> BREAK
    bar(100.6, 100.8, 99.2, 99.5),   # 5: close 99.5 < 100            -> REJECTION
    bar(99.5, 99.9, 99.0, 99.6),
    bar(99.6, 99.95, 99.1, 99.7),
    bar(99.7, 99.99, 99.2, 99.8),    # 8: entry bar, still below level
]
i = len(bars) - 1
lvl = 100.0
print("LONG  _break_bar(i=%d) = %s   (expect 4)" % (i, dg._break_bar(bars, i, lvl, True)))
print("LONG  break_then_rejection = %s   (claim says this can NEVER be True)"
      % dg.break_then_rejection(bars, i, lvl, True))

# SHORT mirror.
sb = [bar(2 * lvl - b["o"], 2 * lvl - b["l"], 2 * lvl - b["h"], 2 * lvl - b["c"]) for b in bars]
print("SHORT _break_bar = %s" % dg._break_bar(sb, i, lvl, False))
print("SHORT break_then_rejection = %s" % dg.break_then_rejection(sb, i, lvl, False))

# and the full grader records it in `tripped`
rec = dg.score(bars, i, lvl, True)
print("score().tripped =", rec["tripped"])
print("btr in tripped:", "break_then_rejection" in rec["tripped"], "| grade:", rec["grade"])

# --- what the claim SHOULD have said: the true exclusion ------------------
# reject at br+1, then close back ABOVE the level before bar i -> new up-cross
# becomes br, and the rejection is no longer "after" it.
bars2 = list(bars)
bars2[6] = bar(99.5, 100.9, 99.4, 100.7)   # re-cross up at 6
bars2[7] = bar(100.7, 101.2, 100.5, 100.9)
bars2[8] = bar(100.9, 101.4, 100.7, 101.1)
print()
print("re-cross case: _break_bar =", dg._break_bar(bars2, i, lvl, True),
      "| btr =", dg.break_then_rejection(bars2, i, lvl, True))
