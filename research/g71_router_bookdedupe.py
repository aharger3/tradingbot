"""G7.1 / track `router` - the OTHER half of the harness-vs-book gap.

T23 blamed the whole 67.6%-harness / 1-of-34-book gap on the router. Fixing the
router (research/g71_router_recall.py) moves the harness by exactly one card,
and the book already runs the correct router - `backtest_week.BacktestRunner`
was fixed in omen-5.0. So the router is not what separates them.

What separates them is the DEDUPE, and the two rigs apply it differently:

  backtest_week.simulate_day:864-870 applies `dedupe_window()` to EVERY captured
  signal - X-grade skips included - and `continue`s, so an X row both hides the
  row from the book AND arms (and re-arms) the suppression window against every
  later signal on the same (setup, direction, level) key.

  research/t4_engine_recall.run_day:206-216 keeps two maps: `seen_any` for the
  all-signal list and `seen` for entries, and `seen` is only written on a FIRED
  signal. An X row therefore suppresses nothing.

`dedupe_window`'s own docstring is "Bars of suppression after a FIRE"
(backtest_week.py:88).

This script scores a third arm: the CORRECT router plus the BOOK's dedupe rule,
so the three numbers sit on one axis:

  A  hand-rolled router + harness dedupe  (the published 23/34)
  B  base router       + harness dedupe   (g71_router_recall)
  C  base router       + BOOK dedupe      (what the two-year book actually sees)

No engine file is edited. Mark files are read-only.

Usage:  python research/g71_router_bookdedupe.py
"""
from __future__ import annotations
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import research.t4_engine_recall as t4          # noqa: E402
from research.g71_router_recall import (        # noqa: E402
    _delegating_route, _ORIGINAL_ROUTE, rows, SWEEP)
from backtest_week import dedupe_window          # noqa: E402


def run_day_bookdedupe(symbol, day):
    """t4.run_day with backtest_week.simulate_day's dedupe: ONE `seen` map,
    written on every captured signal regardless of status, `continue` on a hit."""
    candles = t4.rth_candles(symbol, day)
    if not candles:
        return None
    pdh, pdl, pdo, pdc = t4.prior_day_levels(symbol, day)
    pmh, pml = t4.premarket_extremes(symbol, day)
    runner = t4.CaptureRunner(symbol)
    runner.pdh, runner.pdl = pdh, pdl
    runner.pmh, runner.pml = pmh, pml
    runner.pd_open, runner.pd_close = pdo, pdc
    runner.htf_bias = t4.htf_bias(symbol, day)
    runner.qqq_breaks = None

    win = dedupe_window()
    entries, seen = [], {}
    for i in range(5, len(candles)):
        c = candles[i]
        if t4.ENTRY_CUTOFF and c.timestamp >= t4.ENTRY_CUTOFF:
            continue
        runner.candles = candles[: i + 1]
        before = len(runner.captured)
        runner.detect_signals()
        for sig in runner.captured[before:]:
            idea = (sig.get("stop_level_name")
                    if sig["signal_type"].value == "break_and_retest"
                    else round(sig["stop"], 2))
            key = (sig["signal_type"].value, sig["direction"], idea)
            if key in seen and i - seen[key] < win:
                seen[key] = i          # book behaviour: extend the suppression
                continue
            seen[key] = i
            if sig["status"] == "fired":
                entries.append({"bar": i, "timestamp": c.timestamp,
                                "grade": sig["grade"],
                                "signal_type": sig["signal_type"].value})
    return entries


def main():
    cards = [r for r in rows(SWEEP) if r["answers"].get("s")]
    his_s = [r for r in cards if r["answers"]["s"] == ["s"]]
    his_no = [r for r in cards if r["answers"]["s"] != ["s"]]

    t4.CaptureRunner._route = _delegating_route
    fired = {}
    for r in sorted({(x["symbol"], x["date"]) for x in cards}):
        e = run_day_bookdedupe(*r)
        fired[r] = bool(e)
    t4.CaptureRunner._route = _ORIGINAL_ROUTE

    hit = [r for r in his_s if fired.get((r["symbol"], r["date"]))]
    fp = [r for r in his_no if fired.get((r["symbol"], r["date"]))]
    res = {
        "arm": "base router + BOOK dedupe (dedupe_window()=%d bars, armed by "
               "X rows too)" % dedupe_window(),
        "fired_on_S": len(hit), "n_S": len(his_s),
        "recall_pct": round(len(hit) / len(his_s) * 100, 1),
        "fired_on_no": len(fp), "n_no": len(his_no),
        "precision_pct": (round(len(hit) / (len(hit) + len(fp)) * 100, 1)
                          if (hit or fp) else 0.0),
        "hit_S": sorted(r["card_id"] for r in hit),
        "missed_S": sorted(r["card_id"] for r in his_s if r not in hit),
    }
    print(json.dumps({k: v for k, v in res.items() if k != "missed_S"}, indent=2))
    with open(os.path.join(HERE, "g71_router_bookdedupe.json"), "w",
              encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print("wrote research/g71_router_bookdedupe.json")


if __name__ == "__main__":
    main()
