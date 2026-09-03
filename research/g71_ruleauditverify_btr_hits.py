"""Identify the rows where break_then_rejection is TRUE at the shipped level
proxy on real bars (book stop, 2dp), and print the geometry."""
import json, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import polygon_feed as pf
from research import downgrade as dg
from backtest_2y import dg_bars

T = json.load(open(ROOT / "research" / "bt2y_trades.json"))["trades"]
by_day = collections.defaultdict(list)
for r in T:
    by_day[(r["sym"], r["day"])].append(r)
hits = 0
wrong = 0
n = 0
for (sym, day), rows in sorted(by_day.items()):
    try:
        bars = dg_bars(pf.rth(pf.fetch_day(sym, day)))
    except Exception:
        continue
    if not bars:
        continue
    for r in rows:
        i = r["entry_i"]
        if i is None or i >= len(bars):
            continue
        n += 1
        L, is_long = r["stop"], r["side"] == "L"
        c = bars[i]["c"]
        if (c <= L) if is_long else (c >= L):
            wrong += 1
        if dg.break_then_rejection(bars, i, L, is_long):
            hits += 1
            br = dg._break_bar(bars, i, L, is_long)
            print("HIT %s %s %s %s traded=%s grade=%s sgrade=%s stop=%.2f entry=%.2f "
                  "entry_i=%d break_bar=%d close_i=%.2f close_br1=%.2f"
                  % (sym, day, r["et"], r["side"], r["traded"], r["grade"], r["sgrade"],
                     L, r["entry"], i, br, c, bars[br + 1]["c"] if br + 1 < len(bars) else float("nan")))
print("scanned %d rows; btr TRUE %d; entry-bar close on wrong side of stop %d" % (n, hits, wrong))
