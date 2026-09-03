"""G7.1 / scanners — prove class D for break_then_rejection.

Hypothesis: `downgrade._break_bar(bars, i, level, is_long)` returns `i` itself
on a B&R entry bar (the confirm bar IS the close through the level), so
`break_then_rejection`'s scan `range(br+1, min(br+1+REJECT_BARS, i+1))` is an
EMPTY RANGE and the variable can never be True. 0 trips in 76,019 book rows.
Read-only sample over the archive.
"""
import json, random, collections, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import polygon_feed as pf
from research import downgrade as dg

book = json.load(open(ROOT / "research" / "bt2y_trades.json", encoding="utf-8"))
rows = book["trades"]
random.seed(7)
sample = random.sample(rows, 1500)

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

dist = collections.Counter()
trips = 0
n = 0
for r in sample:
    b = bars_for(r["sym"], r["day"])
    i = r["entry_i"]
    if not b or i >= len(b):
        continue
    n += 1
    lvl, is_long = r["stop"], r["dir"] == "call"
    br = dg._break_bar(b, i, lvl, is_long)
    if br is None:
        dist["no break bar"] += 1
    elif br == i:
        dist["break bar IS the entry bar (scan range empty)"] += 1
    elif i - br < 1:
        dist["br > i"] += 1
    else:
        dist["break bar %d+ bars back (scan CAN run)" % 1] += 1
    if dg.break_then_rejection(b, i, lvl, is_long):
        trips += 1

print("sampled %d rows with bars" % n)
for k, v in dist.most_common():
    print("  %6d  %5.1f%%  %s" % (v, 100.0 * v / max(n, 1), k))
print("break_then_rejection True on %d of %d" % (trips, n))

# --- the structural proof -------------------------------------------------
# `_break_bar` returns the MOST RECENT close-through in the trade direction.
# If any bar after it closed BACK through the level, price must cross forward
# again before bar i (bar i closes on the break side), and that later crossing
# would be the one `_break_bar` returned. So every bar in (br, i] is on the
# break side and `break_then_rejection`'s test can never be True.
# Checked directly below.
wrong_side_at_i = 0
any_back_after_br = 0
checked = 0
for r in sample:
    b = bars_for(r["sym"], r["day"])
    i = r["entry_i"]
    if not b or i >= len(b):
        continue
    lvl, is_long = r["stop"], r["dir"] == "call"
    br = dg._break_bar(b, i, lvl, is_long)
    if br is None:
        continue
    checked += 1
    if (b[i]["c"] < lvl) if is_long else (b[i]["c"] > lvl):
        wrong_side_at_i += 1
    if any(((b[j]["c"] < lvl) if is_long else (b[j]["c"] > lvl))
           for j in range(br + 1, i + 1)):
        any_back_after_br += 1
print("\nstructural check over %d rows with a break bar:" % checked)
print("  entry bar closes on the WRONG side of its own level : %d" % wrong_side_at_i)
print("  ANY bar in (br, i] closes back through the level    : %d" % any_back_after_br)
