"""ADVERSARIAL VERIFY: run the DECK's own engine on days the trio script calls FIRE.

Samples fresh in-window days that have a bt2y row but no status="fired" row, and
asks build_deck.day_fires() -- the exact function pick() buckets on -- whether the
engine fires. Every 0 here is a silent deck card the trio script threw away.
Also reports the <60-candle attrition pick() applies.

    python research/g71_advsymverify_live.py
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

import build_deck as bd

BOOK = os.path.join(HERE, "bt2y_trades.json")
ARCHIVE = os.path.join(ROOT, "data_archive")
N = 30


def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    lo, hi = b["meta"]["first"], b["meta"]["last"]
    anyrow, firedd = defaultdict(set), defaultdict(set)
    for t in b["trades"]:
        anyrow[t["sym"]].add(t["day"])
        if t["status"] == "fired":
            firedd[t["sym"]].add(t["day"])
    seen = bd.seen_card_ids()
    rng = random.Random(71)
    for sym in ("SPY", "TSLA", "AAPL"):
        d = os.path.join(ARCHIVE, sym)
        days = [f[:-4] for f in os.listdir(d) if f.endswith(".csv")]
        cand = [x for x in days if lo <= x <= hi
                and "%s_%s" % (sym, x) not in seen
                and x in anyrow[sym] and x not in firedd[sym]]
        rng.shuffle(cand)
        fires = short = silent = 0
        for day in cand[:N]:
            c = bd.session_candles(sym, day)
            if len(c) < 60:
                short += 1
                continue
            n, _et = bd.day_fires(sym, day)
            if n > 0:
                fires += 1
            else:
                silent += 1
        print("%-5s pool=%4d  sampled=%d -> deck-SILENT %d, deck-FIRE %d, "
              "<60 candles %d" % (sym, len(cand), min(N, len(cand)),
                                  silent, fires, short))


if __name__ == "__main__":
    main()
