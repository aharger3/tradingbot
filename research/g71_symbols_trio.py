"""G71/symbols -- score every SPY + two-companion trio Austin could pick.

Austin: "for next test, we should focus on 3 stocks, spy since indecies is big,
and pick 2 others."

SPY is fixed by him. This enumerates the pairs and scores each trio on the four
things that actually differ between symbols:

  MONEY       the 2-year book restricted to the trio, with a bootstrap CI and
              green-month count (durability is defined per month, not per symbol)
  RECALL      his S days on file for the trio, and how many of them survive in
              the CURRENT held-out sample (probe_s_sweep_2026-08-28)
  SUPPLY      fresh symbol-days never judged and never served, split FIRE/SILENT,
              because the deck standard is half-and-half and SILENT is the scarce
              half
  REDUNDANCY  max pairwise 09:30-11:00 return correlation inside the trio

    python research/g71_symbols_trio.py
"""
from __future__ import annotations

import csv
import itertools
import json
import os
import random
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd
import g71_symbols_census as census
from universe import MIN_SAMPLE_N

BOOK = os.path.join(HERE, "bt2y_trades.json")
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
ARCHIVE = os.path.join(ROOT, "data_archive")
ANCHOR = "SPY"
# Full-archive, book-covered names only. A companion with 275 archived sessions
# would halve the measurable history, so CRM/UBER/TSM/MARA/SOFI/IREN are out
# before any scoring happens -- see the arch column of g71_symbols_census.
POOL = ["TSLA", "NVDA", "AAPL", "MU", "AMD", "PLTR", "META", "MSFT",
        "GOOGL", "AMZN", "INTC", "COIN", "ORCL", "NFLX", "QQQ"]
BOOT = 4000
SEED = 71


def ci(xs):
    if len(xs) < 2:
        return None, None
    rng = random.Random(SEED)
    n = len(xs)
    ms = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOT))
    return ms[int(0.025 * BOOT)], ms[int(0.975 * BOOT)]


def window_returns(sym):
    d = os.path.join(ARCHIVE, sym)
    out = {}
    for f in sorted(x for x in os.listdir(d) if x.endswith(".csv")):
        o = c = None
        with open(os.path.join(d, f), newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                t = row["Datetime"][11:16]
                if not ("09:30" <= t < "11:00"):
                    continue
                try:
                    if o is None:
                        o = float(row["Open"])
                    c = float(row["Close"])
                except (TypeError, ValueError):
                    continue
        if o and c:
            out[f[:-4]] = (c - o) / o
    return out


def pearson(a, b):
    days = sorted(set(a) & set(b))
    xs = [a[d] for d in days]
    ys = [b[d] for d in days]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy)


def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    lo, hi = b["meta"]["first"], b["meta"]["last"]
    trades = defaultdict(list)
    months = defaultdict(lambda: defaultdict(list))
    fire = defaultdict(set)
    for t in b["trades"]:
        fire[t["sym"]].add(t["day"])
        if t.get("traded"):
            trades[t["sym"]].append(t)
            months[t["sym"]][t["ym"]].append(t["r"])

    marks, _src, _dg = census.marks_census()
    seen = bd.seen_card_ids()

    sweep = [json.loads(l) for l in open(SWEEP, encoding="utf-8") if l.strip()]
    sweep_S = defaultdict(int)
    for r in sweep:
        if (r.get("answers") or {}).get("s") == ["s"]:
            sweep_S[r["symbol"]] += 1

    syms = sorted(set([ANCHOR] + POOL))
    rets = {s: window_returns(s) for s in syms}

    fresh_fire, fresh_sil = {}, {}
    for s in syms:
        d = os.path.join(ARCHIVE, s)
        days = [f[:-4] for f in os.listdir(d) if f.endswith(".csv")]
        fr = [x for x in days if "%s_%s" % (s, x) not in seen]
        fresh_fire[s] = sum(1 for x in fr if x in fire[s])
        # OUTSIDE the book window the engine was never run, so silence is
        # unknown; only in-window days can be called silent from the book.
        fresh_sil[s] = sum(1 for x in fr if lo <= x <= hi and x not in fire[s])

    rows = []
    for pair in itertools.combinations(POOL, 2):
        trio = (ANCHOR,) + pair
        r = [t["r"] for s in trio for t in trades[s]]
        if not r:
            continue
        clo, chi = ci(r)
        mm = defaultdict(float)
        for s in trio:
            for ym, v in months[s].items():
                mm[ym] += sum(v)
        rows.append({
            "trio": "+".join(trio),
            "n": len(r),
            "meanR": sum(r) / len(r),
            "lo": clo, "hi": chi,
            "win": sum(1 for x in r if x > 0) / len(r),
            "green": sum(1 for v in mm.values() if v > 0),
            "months": len(mm),
            "S_on_file": sum(len(marks.get(s, {}).get("S", ())) for s in trio),
            "graded": sum(len(marks.get(s, {}).get("ALL", ())) for s in trio),
            "heldout_S": sum(sweep_S.get(s, 0) for s in trio),
            "fresh_fire": sum(fresh_fire[s] for s in trio),
            "fresh_silent": sum(fresh_sil[s] for s in trio),
            "maxcorr": max(pearson(rets[a], rets[c])
                           for a, c in itertools.combinations(trio, 2)),
        })

    rows.sort(key=lambda x: -x["S_on_file"])
    print("book %s  window %s..%s  MIN_SAMPLE_N %d" % (BOOK, lo, hi, MIN_SAMPLE_N))
    print("held-out sample = %s (34 S of 100)" % os.path.basename(SWEEP))
    print()
    print("%-22s %5s %8s %-17s %6s %7s %7s %5s %8s %6s %7s %6s" % (
        "trio", "n", "meanR", "[  95% CI  ]", "win%", "green", "graded",
        "S", "heldoutS", "frFIRE", "frSILENT", "maxr"))
    for x in rows:
        print("%-22s %5d %+8.4f [%+.3f,%+.3f] %6.1f %5d/%-2d %7d %5d %8d %6d %7d %6.2f" % (
            x["trio"], x["n"], x["meanR"], x["lo"], x["hi"], 100 * x["win"],
            x["green"], x["months"], x["graded"], x["S_on_file"], x["heldout_S"],
            x["fresh_fire"], x["fresh_silent"], x["maxcorr"]))
    out = os.path.join(HERE, "g71_symbols_trio.json")
    json.dump(rows, open(out, "w", encoding="utf-8"), indent=1)
    print("\nwrote", out)


if __name__ == "__main__":
    main()
