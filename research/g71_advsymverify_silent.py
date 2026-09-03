"""ADVERSARIAL VERIFY (g71/advsymverify): recount the fresh SILENT half.

g71_symbols_trio.py builds `fire[sym]` from EVERY row in research/bt2y_trades.json
(76,019 rows, 69,624 of them status=skipped_d / grade X).  build_deck.pick()
calls day_fires() -> run_day()[0], which is entries with status "fired" only.
So the trio script calls a day FIRE whenever the engine merely *considered*
something, and the book has a row on 468-493 of ~500 in-window days per symbol.
This recounts silent with the deck's own definition, and separately reports the
out-of-window archive the deck may also draw from (build_deck runs the engine
live; it never reads the book).

    python research/g71_advsymverify_silent.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd

BOOK = os.path.join(HERE, "bt2y_trades.json")
ARCHIVE = os.path.join(ROOT, "data_archive")
SYMS = ["SPY", "AAPL", "TSLA", "NVDA", "MU", "QQQ"]


def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    lo, hi = b["meta"]["first"], b["meta"]["last"]
    anyrow = defaultdict(set)
    firedd = defaultdict(set)
    for t in b["trades"]:
        anyrow[t["sym"]].add(t["day"])
        if t["status"] == "fired":
            firedd[t["sym"]].add(t["day"])

    seen = bd.seen_card_ids()
    print("book %s..%s  rows=%d  fired-rows=%d  seen(judged|served)=%d"
          % (lo, hi, len(b["trades"]),
             sum(1 for t in b["trades"] if t["status"] == "fired"), len(seen)))
    print()
    hdr = ("%-6s %5s %5s %6s %6s   trio-script:%5s %7s   deck-def:%6s %8s %8s"
           % ("sym", "arch", "inwin", "bookd", "fired", "frFIRE", "frSIL",
              "frFIRE", "frSIL_in", "frOUTwin"))
    print(hdr)
    tot = {}
    for s in SYMS:
        d = os.path.join(ARCHIVE, s)
        days = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv"))
        fresh = [x for x in days if "%s_%s" % (s, x) not in seen]
        inwin = [x for x in fresh if lo <= x <= hi]
        outwin = [x for x in fresh if not (lo <= x <= hi)]
        t_fire = sum(1 for x in fresh if x in anyrow[s])
        t_sil = sum(1 for x in inwin if x not in anyrow[s])
        d_fire = sum(1 for x in fresh if x in firedd[s])
        d_sil = sum(1 for x in inwin if x not in firedd[s])
        tot[s] = (t_sil, d_sil, len(outwin))
        print("%-6s %5d %5d %6d %6d              %5d %7d       %6d %8d %8d"
              % (s, len(days), sum(1 for x in days if lo <= x <= hi),
                 len(anyrow[s]), len(firedd[s]), t_fire, t_sil,
                 d_fire, d_sil, len(outwin)))
    print()
    for trio in [("SPY", "TSLA", "AAPL"), ("SPY", "TSLA", "NVDA"),
                 ("SPY", "TSLA", "MU"), ("SPY", "AAPL", "MU")]:
        t = sum(tot[s][0] for s in trio)
        dd = sum(tot[s][1] for s in trio)
        ow = sum(tot[s][2] for s in trio)
        print("%-18s trio-script frSILENT=%3d   deck-def in-window=%4d "
              "(+%3d fresh out-of-window days, silence unmeasured)"
              % ("+".join(trio), t, dd, ow))


if __name__ == "__main__":
    main()
