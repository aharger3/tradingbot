"""G7.1/btrverify -- downgrade-variable trip census straight off the committed
book's own `downgrades` field. No bars fetched, no re-grading: this reads what
backtest_2y.py stored, so it is the same population the scanners census counted.

Usage: python research/g71_btrverify_census.py
"""
import json, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.load(open(ROOT / "research" / "bt2y_trades.json", encoding="utf-8"))
rows = d["trades"]
print("book meta: signals=%s traded=%s generated=%s"
      % (d["meta"]["signals"], d["meta"].get("traded"), d["meta"]["generated"]))

c = collections.Counter()
for r in rows:
    for t in r.get("downgrades") or []:
        c[t] += 1
print("rows: %d   traded rows: %d" % (len(rows), sum(1 for r in rows if r["traded"])))
for k in ("no_displacement", "stale_retest", "level_not_respected", "exhausted",
          "counter_trend_not_respected", "break_then_rejection", "no_retest",
          "ocr_not_respected", "chase"):
    print("  %7d  %6.2f%%  %s" % (c[k], 100.0 * c[k] / len(rows), k))

# geometry the branch needs: entry price on the wrong side of its own stop
bad = sum(1 for r in rows
          if ((r["entry"] < r["stop"]) if r["dir"] == "call" else (r["entry"] > r["stop"])))
print("\nentry PRICE on the wrong side of its own stop: %d of %d" % (bad, len(rows)))
