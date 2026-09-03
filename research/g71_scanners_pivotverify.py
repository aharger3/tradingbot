"""G7.1 adversarial verify -- does PIVOT_LEVELS carry 5 of "the 23 held-out S
days the engine currently finds"?

Read-only. Three checks the original claim did not run:

 1. The 23/34 is scored by research/t4_engine_recall.CaptureRunner, whose
    _route (t4_engine_recall.py:141) never calls super()._route() -- the exact
    bug backtest_week.BacktestRunner fixed in omen-5.0 (backtest_week.py:619).
    So ask the SHIPPED BOOK (research/bt2y_trades.json) what it does on the
    same 34 cards, and on the 5 cards PIVOT_LEVELS=0 loses.
 2. The harness counts a grade-C fire as a hit. C is alert-only --
    backtest_week.Trade.counted (:283) -- so a C-only card is not a trade the
    engine takes. Count them.
 3. The report's pivot economics are a SUBSET of the base book
    (g71_scanners_econ.py: named = [r for r in traded if not
    r["level"].startswith("pivot")]). The real PIVOT_LEVELS=0 re-run is on disk
    as research/g71_arm_no_pivot.json. Print both.

Usage: python research/g71_scanners_pivotverify.py
"""
from __future__ import annotations
import json, os, sys, collections, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
BOOK = os.path.join(HERE, "bt2y_trades.json")
NOPIV = os.path.join(HERE, "g71_arm_no_pivot.json")

# base.missed_S minus nopivot.missed_S, from the two arms re-run one process each
FIVE = ["ARM_2024-10-28", "BABA_2025-04-07", "MU_2025-06-25",
        "PLTR_2025-07-01", "SPCX_2026-06-25"]


def s_cards():
    out = []
    with open(SWEEP, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                if r["answers"].get("s") == ["s"]:
                    out.append(r)
    return out


def book_index(path):
    d = json.load(open(path, encoding="utf-8"))
    idx = collections.defaultdict(list)
    for r in d["trades"]:
        idx[(r["sym"], r["day"])].append(r)
    return d["meta"], idx


def stats(rows):
    R = [r["r"] for r in rows]
    g = collections.defaultdict(float)
    for r in rows:
        g[r["ym"]] += r["r"]
    green = sum(1 for v in g.values() if v > 0)
    return ("traded=%5d win%%=%5.2f meanR=%+.4f totR=%+8.1f months %d/%d green  red=%s"
            % (len(rows), 100.0 * sum(1 for x in R if x > 0) / len(R),
               statistics.fmean(R), sum(R), green, len(g),
               sorted(k for k, v in g.items() if v <= 0)))


def main():
    import universe
    meta, idx = book_index(BOOK)
    S = s_cards()

    print("== 1. the 34 held-out S cards, scored on the SHIPPED BOOK ==")
    traded = sum(1 for r in S if any(x["traded"] for x in idx.get((r["symbol"], r["date"]), [])))
    fired = sum(1 for r in S if any(x["status"] == "fired" for x in idx.get((r["symbol"], r["date"]), [])))
    print("   book traded on %d/%d;  book has a 'fired' row on %d/%d" % (traded, len(S), fired, len(S)))
    print("   (harness t0_heldout_recall.py scores 23/34 on the same cards)")

    print("\n== 2. the 5 cards PIVOT_LEVELS=0 loses, on the SHIPPED BOOK ==")
    for cid in FIVE:
        sym, day = cid.rsplit("_", 1)
        rs = idx.get((sym, day), [])
        print("   %-16s in_backtest_universe=%-5s book_rows=%2d traded=%d  statuses=%s"
              % (cid, sym in universe.BACKTEST_SYMBOLS, len(rs),
                 sum(1 for x in rs if x["traded"]),
                 dict(collections.Counter(x["status"] for x in rs))))

    print("\n== 3. book traded-grade mix (C never trades: Trade.counted, backtest_week.py:283) ==")
    allt = [x for v in idx.values() for x in v if x["traded"]]
    print("  ", dict(collections.Counter(x["grade"] for x in allt)))

    print("\n== 4. pivot vs named, on the book the report used ==")
    piv = [x for x in allt if x["level"].startswith("pivot")]
    nam = [x for x in allt if not x["level"].startswith("pivot")]
    print("   pivot      ", stats(piv))
    print("   named      ", stats(nam))
    print("   -> pivots WIN more and mean MORE R than the named half.")

    print("\n== 5. subset arithmetic vs the real PIVOT_LEVELS=0 re-run ==")
    print("   base book             ", stats(allt))
    print("   subset 'named only'   ", stats(nam), "  <- what g71_scanners_econ.py reports")
    if os.path.exists(NOPIV):
        m2, i2 = book_index(NOPIV)
        t2 = [x for v in i2.values() for x in v if x["traded"]]
        print("   REAL PIVOT_LEVELS=0   ", stats(t2),
              "  (signals %d, halted %d)" % (m2["signals"], m2["halted"]))
        print("   delta on the real arm: %+d trades, %+.1f R, meanR %+.4f"
              % (len(t2) - len(allt), sum(x["r"] for x in t2) - sum(x["r"] for x in allt),
                 statistics.fmean([x["r"] for x in t2]) - statistics.fmean([x["r"] for x in allt])))


if __name__ == "__main__":
    main()
