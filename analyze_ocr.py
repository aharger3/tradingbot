"""One-shot: split last backtest's one_candle_rule trades by grade/direction/symbol/retest."""
import json
from collections import defaultdict

recs = json.load(open("backtest_charts.json", encoding="utf-8"))
ocr = [r for r in recs if r["setup"] == "one_candle_rule" and not r["alert_only"]]
print(f"{len(ocr)} traded OCR signals")


def split(key):
    by = defaultdict(lambda: [0, 0, 0.0])
    for r in ocr:
        k = key(r)
        by[k][0] += 1
        by[k][1] += r["outcome"] == "win"
        by[k][2] += r["pnl"]
    for k, v in sorted(by.items(), key=lambda x: x[1][2]):
        print(f"  {k}: {v[0]}tr {v[1]/v[0]*100:.0f}%W ${v[2]:,.0f}")


print("by grade:"); split(lambda r: r["grade"])
print("by direction:"); split(lambda r: r["direction"])
print("by symbol:"); split(lambda r: r["symbol"])
print("by stop width (reason has block):")
split(lambda r: "wide" if (abs(r["entry"] - r["stop"]) / r["entry"]) > 0.004 else "tight")
