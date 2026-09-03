"""G71/symbols -- per-symbol money with an error bar, and per-symbol durability.

A per-symbol mean R quoted without its bar is the mistake this repo has already
made once (research/omen-error-bar-exceeds-arms). Every headline here carries a
bootstrap CI and the count of green months, so "SPY is the best symbol" can be
checked against "SPY has 55 trades and the bar is +/-0.6R".

    python research/g71_symbols_money.py
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from universe import MIN_SAMPLE_N

BOOK = os.path.join(HERE, "bt2y_trades.json")
BOOT = 4000
SEED = 71


def ci(xs, boot=BOOT, seed=SEED):
    if len(xs) < 2:
        return None, None
    rng = random.Random(seed)
    n = len(xs)
    ms = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(boot))
    return ms[int(0.025 * boot)], ms[int(0.975 * boot)]


def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    per = defaultdict(list)
    months = defaultdict(lambda: defaultdict(list))
    for t in b["trades"]:
        if not t.get("traded"):
            continue
        per[t["sym"]].append(t["r"])
        months[t["sym"]][t["ym"]].append(t["r"])
    rows = []
    for s, r in per.items():
        lo, hi = ci(r)
        mm = months[s]
        green = sum(1 for m in mm.values() if sum(m) > 0)
        rows.append({"sym": s, "n": len(r), "meanR": sum(r) / len(r),
                     "win": sum(1 for x in r if x > 0) / len(r),
                     "lo": lo, "hi": hi, "months": len(mm), "green": green,
                     "totalR": sum(r),
                     "gate_meanR": (lo is not None and lo >= 2.0),
                     "thin": len(r) < MIN_SAMPLE_N})
    rows.sort(key=lambda x: -x["meanR"])
    print("book %s  traded %d  MIN_SAMPLE_N %d" % (BOOK, sum(x["n"] for x in rows),
                                                   MIN_SAMPLE_N))
    print("sym      n    meanR   [  95% CI  ]   win%   totalR  green/months  thin")
    for x in rows:
        print("%-5s %4d %+8.4f [%+.3f,%+.3f] %6.1f %+9.1f      %2d/%-2d      %s" % (
            x["sym"], x["n"], x["meanR"], x["lo"], x["hi"], 100 * x["win"],
            x["totalR"], x["green"], x["months"], "THIN" if x["thin"] else ""))
    allr = [r for v in per.values() for r in v]
    lo, hi = ci(allr)
    print("\nWHOLE BOOK n=%d meanR %+0.4f [%+.3f,%+.3f] win %.1f%%" % (
        len(allr), sum(allr) / len(allr), lo, hi,
        100 * sum(1 for x in allr if x > 0) / len(allr)))
    out = os.path.join(HERE, "g71_symbols_money.json")
    json.dump(rows, open(out, "w", encoding="utf-8"), indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
