"""G7.1 / scanners — candidate fix for the unreachable `break_then_rejection`.

`downgrade._break_bar` returns the MOST RECENT close-through in the trade
direction, so every bar after it is on the break side by construction and the
rejection scan can never be True (0 of 76,019 book rows, 0 of 1,500 replayed).
The rule Austin stated -- "it broke, then immediately gave it back" -- is about
the FIRST break in the lookback, not the last. This measures the trip rate of
that reading before anyone ships it. Read-only.
"""
import json, random, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import polygon_feed as pf
from research import downgrade as dg


def first_break_bar(bars, i, level, is_long, look=30):
    """FIRST bar in the lookback that closed through the level, direction-wise."""
    lo = max(1, i - look)
    for j in range(lo, i + 1):
        prev, cur = bars[j - 1], bars[j]
        crossed = ((prev["c"] <= level < cur["c"]) if is_long
                   else (prev["c"] >= level > cur["c"]))
        if crossed:
            return j
    return None


def fixed_rejection(bars, i, level, is_long):
    br = first_break_bar(bars, i, level, is_long)
    if br is None:
        return False
    for j in range(br + 1, min(br + 1 + dg.REJECT_BARS, i + 1)):
        back = (bars[j]["c"] < level) if is_long else (bars[j]["c"] > level)
        if back:
            return True
    return False


book = json.load(open(ROOT / "research" / "bt2y_trades.json", encoding="utf-8"))
random.seed(7)
sample = random.sample(book["trades"], 1500)
cache = {}
def bars_for(sym, day):
    k = (sym, day)
    if k not in cache:
        try:
            r = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            r = []
        cache[k] = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
                    for c in r]
    return cache[k]

n = ship = fix = 0
by_sgrade = collections.Counter()
for r in sample:
    b = bars_for(r["sym"], r["day"])
    i = r["entry_i"]
    if not b or i >= len(b):
        continue
    n += 1
    lvl, is_long = r["stop"], r["dir"] == "call"
    if dg.break_then_rejection(b, i, lvl, is_long):
        ship += 1
    if fixed_rejection(b, i, lvl, is_long):
        fix += 1
        by_sgrade[r["sgrade"]] += 1

print("sample %d rows" % n)
print("  shipped break_then_rejection trips : %d  (%.2f%%)" % (ship, 100.0 * ship / n))
print("  first-break reading trips          : %d  (%.2f%%)" % (fix, 100.0 * fix / n))
print("  fixed trips by Austin sgrade:", dict(by_sgrade))
