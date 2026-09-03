"""G7.1 / track `capture` -- held-out S recall under the two routers.

The governing gate (DIRECTION.md, method rule 2) is held-out S recall on
`research/marks/probe_s_sweep_2026-08-28.jsonl` (34 blind S cards). It is
scored by `research/t0_heldout_recall.py`, which replays through
`research/t4_engine_recall.run_day` -> `CaptureRunner`, a hand-rolled router
that never calls `super()._route`.

This scores the SAME cards twice: once on the shipped CaptureRunner, once on a
router that delegates to `SignalRunner._route` the way
`backtest_week.BacktestRunner` has since omen-5.0. It also reports how many of
the hits are on symbols `universe.BACKTEST_SYMBOLS` never trades, which is the
other half of why 67.6% on the harness is 1/34 on the book.

No engine file is modified. Marks are read, never written.

Usage:  python research/g71_capture_heldout_ab.py
"""
from __future__ import annotations
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as t4                     # noqa: E402
from universe import BACKTEST_SYMBOLS             # noqa: E402
from g71_capture_route_ab import DelegatingCaptureRunner  # noqa: E402

SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")


def rows(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def score(cards):
    """(recall tuple, precision tuple, per-card fired flag)."""
    his_s = [r for r in cards if r["answers"]["s"] == ["s"]]
    his_no = [r for r in cards if r["answers"]["s"] != ["s"]]
    fired = {}
    for sym, day in sorted({(r["symbol"], r["date"]) for r in cards}):
        try:
            entries, _sigs, _raw = t4.run_day(sym, day)
        except Exception:
            entries = None
        fired[(sym, day)] = bool(entries)
    tp = [r for r in his_s if fired.get((r["symbol"], r["date"]))]
    fp = [r for r in his_no if fired.get((r["symbol"], r["date"]))]
    return his_s, his_no, tp, fp


def report(tag, his_s, his_no, tp, fp):
    in_uni = [r for r in tp if r["symbol"] in BACKTEST_SYMBOLS]
    print(f"\n== {tag} ==")
    print(f"  S cards: {len(his_s)}   recall: {len(tp)}/{len(his_s)} = "
          f"{len(tp)/max(1,len(his_s))*100:.1f}%")
    print(f"  of those hits, in universe.BACKTEST_SYMBOLS: {len(in_uni)}/{len(tp)}"
          f"  -> book-reachable recall {len(in_uni)}/{len(his_s)} = "
          f"{len(in_uni)/max(1,len(his_s))*100:.1f}%")
    off = Counter(r["symbol"] for r in tp if r["symbol"] not in BACKTEST_SYMBOLS)
    if off:
        print(f"  hits on symbols the book never trades: {dict(off)}")
    print(f"  false fires on his 'no' cards: {len(fp)}/{len(his_no)} = "
          f"{len(fp)/max(1,len(his_no))*100:.1f}%")
    print(f"  precision: {len(tp)}/{len(tp)+len(fp)} = "
          f"{len(tp)/max(1,len(tp)+len(fp))*100:.1f}%")
    return {r["card_id"] for r in tp}


def main():
    cards = [r for r in rows(SWEEP) if r["answers"].get("s")]
    print(f"cards with an S answer: {len(cards)}")

    incumbent = t4.CaptureRunner
    a = score(cards)
    hits_a = report("A: shipped CaptureRunner (no super()._route)", *a)

    t4.CaptureRunner = DelegatingCaptureRunner
    try:
        b = score(cards)
    finally:
        t4.CaptureRunner = incumbent
    hits_b = report("B: delegating router (BacktestRunner shape)", *b)

    print("\n== A vs B ==")
    print("  S cards A hits and B misses:", sorted(hits_a - hits_b) or "none")
    print("  S cards B hits and A misses:", sorted(hits_b - hits_a) or "none")


if __name__ == "__main__":
    main()
