"""G71/symbols -- does scoring R on the CONTRACT instead of the SHARE change the
per-symbol ranking, and specifically does it change NVDA/TSLA?

Austin: "nvda and tsla is where i lean but ... they are always top options
volatility." That is a testable claim with two halves:
  1. are they in fact the highest-IV names in the universe?   -> sigma column
  2. does that make share-scored R the wrong unit for them?   -> delta column

Everything here reuses research/t7_real_contracts.py -- its Contract class, its
Black-Scholes pricer, its prior-session-only volatility input. Nothing is
re-implemented; if T7's pricing is wrong this file is wrong in exactly the same
way, which is the point.

    python research/g71_symbols_options.py
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t7_real_contracts as t7
from universe import MIN_SAMPLE_N

BOOT = 4000
SEED = 71


def paired_ci(diffs, boot=BOOT, seed=SEED):
    """95% bootstrap CI on the PAIRED contract-minus-underlying difference.

    Paired, because both arms score the same rows: the unpaired bar
    (research/omen-error-bar-exceeds-arms) is far wider than the effect and
    would call everything a tie by construction.
    """
    if len(diffs) < 2:
        return None, None
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(boot):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return means[int(0.025 * boot)], means[int(0.975 * boot)]


def main():
    book = t7.load_book()
    cache = t7.load_cache()
    traded = [r for r in book if r.get("traded")]
    cons = t7.priced(traded, cache)

    per = {}
    for c in cons:
        s = per.setdefault(c.row["sym"], {"cr": [], "ur": [], "sig": [],
                                          "prem": [], "real": 0, "n": 0})
        s["n"] += 1
        s["cr"].append(c.cr_ladder())
        s["ur"].append(c.ur_ladder())
        s["sig"].append(c.sigma)
        # premium as a % of the underlying: the R denominator's real size
        s["prem"].append(100.0 * c.p0 / c.S0 if c.S0 else 0.0)
        s["real"] += 1 if c.real else 0

    rows = []
    for sym, s in per.items():
        d = [a - b for a, b in zip(s["cr"], s["ur"])]
        lo, hi = paired_ci(d)
        rows.append({
            "sym": sym, "n": s["n"],
            "real_pct": 100.0 * s["real"] / s["n"],
            "iv": statistics.median(s["sig"]),          # annualised, prior-session Parkinson x1.2
            "prem_pct": statistics.median(s["prem"]),   # ATM 0DTE premium as % of spot
            "contract_R": sum(s["cr"]) / s["n"],
            "underly_R": sum(s["ur"]) / s["n"],
            "delta": sum(d) / s["n"],
            "lo": lo, "hi": hi,
            "sig": (lo is not None and (lo > 0 or hi < 0)),
        })

    rows.sort(key=lambda x: -x["iv"])
    print("book:", t7.BOOK, " traded rows:", len(traded), " priced:", len(cons))
    print("IV = prior-session Parkinson sigma x %.1f, annualised (t7 HEADLINE_IV)"
          % t7.HEADLINE_IV)
    print("delta = contract R - underlying R, PAIRED, ladder convention;"
          " 95%% bootstrap CI, n>=%d marked" % MIN_SAMPLE_N)
    print()
    print("sym      n  real%    IV   prem%   contractR  underlyR    delta   "
          "[  95% CI  ]  sig  thin")
    for x in rows:
        print("%-5s %4d %5.0f%% %6.2f %6.2f%%   %+8.4f %+9.4f %+8.4f  "
              "[%+.3f,%+.3f]  %-4s %s" % (
                  x["sym"], x["n"], x["real_pct"], x["iv"], x["prem_pct"],
                  x["contract_R"], x["underly_R"], x["delta"],
                  x["lo"], x["hi"], "YES" if x["sig"] else "-",
                  "THIN" if x["n"] < MIN_SAMPLE_N else ""))

    out = os.path.join(HERE, "g71_symbols_options.json")
    json.dump(rows, open(out, "w", encoding="utf-8"), indent=1)
    print("\nwrote", out)


if __name__ == "__main__":
    main()
