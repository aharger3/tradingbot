"""G71 adversarial verify of track `sigfire`'s WATCH-collision claim.

Re-emulates live_scanner._tier() over the shipped book instead of using the
grade-only shortcut research/g71_sigfire_funnel.py uses at its LIVE GATE
section. The difference is live_scanner.py:577-578: `reentry_84_rule` returns
TRADE regardless of grade (documented again at :616 and :625-628), so the
grade!="A+" test at :579 is NOT reached for that signal type.

Session-state branches (:574 R31 account halt, :581 consecutive_losses,
:583 GOVERNOR_S_CAP) are not reconstructable from a book row; this emulation
is therefore an UPPER bound on live TRADEs and a LOWER bound on demotions --
which is the direction that matters, because the claim under test asserts the
demotion count is 2,433.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "research" / "bt2y_trades.json").read_text())
meta, rows = d["meta"], d["trades"]
traded = [r for r in rows if r["traded"]]

# omen_bot.SignalType.REENTRY_84_RULE.value == "reentry_84_rule"; backtest_2y.py:165
# writes t.signal_type into "setup", so the two strings are the same token.
def live_tier(r):
    if r["setup"] == "reentry_84_rule":      # live_scanner.py:577-578
        return "TRADE"
    return "TRADE" if r["grade"] == "A+" else "WATCH"   # :579-580

print("book meta        : %s" % {k: v for k, v in meta.items() if k != "symbols"})
print("routed rows      : %d" % len(rows))
print("booked trades    : %d" % len(traded))
print()
for label, pool in (("ALL ROUTED", rows), ("BOOKED", traded)):
    c = Counter(live_tier(r) for r in pool)
    n = len(pool)
    ap = sum(1 for r in pool if r["grade"] == "A+")
    r84 = sum(1 for r in pool if r["setup"] == "reentry_84_rule")
    both = sum(1 for r in pool if r["grade"] == "A+" and r["setup"] == "reentry_84_rule")
    print("%s  n=%d" % (label, n))
    print("  grade A+                       %6d" % ap)
    print("  setup reentry_84_rule          %6d  (overlap with A+: %d)" % (r84, both))
    print("  live TRADE (:577 or :579 pass) %6d  %6.2f%%" % (c["TRADE"], 100.0 * c["TRADE"] / n))
    print("  live WATCH (demoted)           %6d  %6.2f%%" % (c["WATCH"], 100.0 * c["WATCH"] / n))
    print("  claim's grade-only TRADE       %6d" % ap)
    print("  claim's grade-only WATCH       %6d  %6.2f%%" % (n - ap, 100.0 * (n - ap) / n))
    print()
