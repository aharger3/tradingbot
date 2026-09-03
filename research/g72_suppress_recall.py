"""G7.2 (suppress) — what the fix does to RECALL on the 100 held-out cards.

research/g71_router_bookdedupe.py found the harness and the book disagree because
the BOOK's dedupe was armed by rejected rows and the HARNESS's was not
(t4_engine_recall keeps `seen` inside `if status == "fired"`). It scored the book
arm at 20.6% recall on Austin's 34 S cards.

This script runs the same arm twice — once with the reject-armed window (the
control, which must reproduce 20.6% exactly, or the mirror is wrong) and once
with the shipped fix, where only a fire arms it. Same cards, same router, same
bars: the only thing that moves is who may claim the level.

Mark files are read-only here; nothing is written but research/g72_suppress_recall.json.

Usage:  python research/g72_suppress_recall.py
"""
from __future__ import annotations
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import research.t4_engine_recall as t4                      # noqa: E402
from research.g71_router_recall import (                    # noqa: E402
    _delegating_route, _ORIGINAL_ROUTE, rows, SWEEP)
from backtest_week import dedupe_window                     # noqa: E402

CONTROL_RECALL = 20.6   # g71_router_bookdedupe.json, the published book arm


def run_day(symbol, day, fires_only: bool):
    """t4.run_day walked with backtest_week.simulate_day's dedupe. When
    fires_only, only a FIRED signal opens or extends the window."""
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
            claims = (sig["status"] == "fired") or not fires_only
            if key in seen and i - seen[key] < win:
                if claims:
                    seen[key] = i
                continue
            if claims:
                seen[key] = i
            if sig["status"] == "fired":
                entries.append({"bar": i, "timestamp": c.timestamp,
                                "grade": sig["grade"],
                                "signal_type": sig["signal_type"].value})
    return entries


def score(cards, his_s, his_no, fires_only):
    fired = {}
    for r in sorted({(x["symbol"], x["date"]) for x in cards}):
        fired[r] = bool(run_day(r[0], r[1], fires_only))
    hit = [r for r in his_s if fired.get((r["symbol"], r["date"]))]
    fp = [r for r in his_no if fired.get((r["symbol"], r["date"]))]
    return {
        "fired_on_S": len(hit), "n_S": len(his_s),
        "recall_pct": round(len(hit) / len(his_s) * 100, 1),
        "fired_on_no": len(fp), "n_no": len(his_no),
        "precision_pct": (round(len(hit) / (len(hit) + len(fp)) * 100, 1)
                          if (hit or fp) else 0.0),
        "hit_S": sorted(r["card_id"] for r in hit),
    }


def main():
    cards = [r for r in rows(SWEEP) if r["answers"].get("s")]
    his_s = [r for r in cards if r["answers"]["s"] == ["s"]]
    his_no = [r for r in cards if r["answers"]["s"] != ["s"]]

    t4.CaptureRunner._route = _delegating_route
    try:
        before = score(cards, his_s, his_no, fires_only=False)
        after = score(cards, his_s, his_no, fires_only=True)
    finally:
        t4.CaptureRunner._route = _ORIGINAL_ROUTE

    out = {"window_bars": dedupe_window(),
           "control_matches_g71": before["recall_pct"] == CONTROL_RECALL,
           "before_reject_arms_window": before,
           "after_only_a_fire_arms_window": after,
           "newly_hit_S": sorted(set(after["hit_S"]) - set(before["hit_S"])),
           "lost_S": sorted(set(before["hit_S"]) - set(after["hit_S"]))}
    with open(os.path.join(HERE, "g72_suppress_recall.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=1)

    print("control reproduces g71_router_bookdedupe (%.1f%%): %s"
          % (CONTROL_RECALL, out["control_matches_g71"]))
    for label, d in (("reject arms the window (bug)", before),
                     ("only a fire arms it (fixed)", after)):
        print("  %-30s recall %2d/%d = %5.1f%%   precision %5.1f%%"
              % (label, d["fired_on_S"], d["n_S"], d["recall_pct"],
                 d["precision_pct"]))
    print("  S days newly reached: %s" % (out["newly_hit_S"] or "none"))
    print("  S days lost         : %s" % (out["lost_S"] or "none"))
    print("wrote research/g72_suppress_recall.json")


if __name__ == "__main__":
    main()
