"""G7.1 / track `router` - why one card flips, and does the +5/-0 X-lift move
survive on the correct router.

Part A: dump every captured signal on the one card that changed
        (QQQ 2025-09-23) under both routers, with the skip reason the base
        router stamped into sig["reason"].
Part B: re-run the four-cell A/B - {X_LIFT=off, X_LIFT=clean} x
        {hand_rolled router, delegating router} - so T23's "+5 gained / 0 lost"
        can be re-read on the right router.

No engine file is edited; the router swap and the X_LIFT flip are in-process.
Mark files are read-only.

Usage:  python research/g71_router_diag.py
"""
from __future__ import annotations
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import research.t4_engine_recall as t4          # noqa: E402
import signal_runner as sr                      # noqa: E402
from research.g71_router_recall import (        # noqa: E402
    _delegating_route, _ORIGINAL_ROUTE, rows, SWEEP, replay, score)


def part_a(symbol="QQQ", day="2025-09-23"):
    print("=" * 70)
    print("A. %s %s - every captured signal, both routers" % (symbol, day))
    for name, fn in (("hand_rolled", _ORIGINAL_ROUTE), ("delegating", _delegating_route)):
        t4.CaptureRunner._route = fn
        entries, sigs, raw = t4.run_day(symbol, day)
        print("\n--- %s: %d entries, %d deduped signals, %d raw" % (
            name, len(entries or []), len(sigs or []), len(raw or [])))
        for r in (raw or []):
            print("   bar %3d %s %-20s %-4s grade=%-2s status=%-24s "
                  "entry=%.4f stop=%.4f width=%.4f%%" % (
                      r["bar"], r["timestamp"][11:16], r["signal_type"],
                      r["direction"], r["grade"], r.get("status", "?"),
                      r["entry"], r["stop"],
                      abs(r["entry"] - r["stop"]) / abs(r["entry"]) * 100))
    t4.CaptureRunner._route = _ORIGINAL_ROUTE


def part_b():
    print("\n" + "=" * 70)
    print("B. four cells: X_LIFT x router, recall / precision on the 100 cards")
    cards = [r for r in rows(SWEEP) if r["answers"].get("s")]
    pairs = {(r["symbol"], r["date"]) for r in cards}
    out = {}
    hits = {}
    for xl in ("off", "clean"):
        sr.X_LIFT = xl
        for rname, fn in (("hand_rolled", _ORIGINAL_ROUTE),
                          ("delegating", _delegating_route)):
            t4.CaptureRunner._route = fn
            t0 = time.time()
            rep = replay(pairs)
            s = score(cards, rep)
            key = "X_LIFT=%s / %s" % (xl, rname)
            out[key] = {k: v for k, v in s.items()
                        if k in ("fired_on_S", "n_S", "recall_pct",
                                 "precision_pct", "fired_on_no")}
            hits[key] = set(s["hit_S"])
            print("  %-32s  S %2d/%d = %5.1f%%   prec %5.1f%%   FP %d   [%.0fs]" % (
                key, s["fired_on_S"], s["n_S"], s["recall_pct"],
                s["precision_pct"], s["fired_on_no"], time.time() - t0))
    sr.X_LIFT = "clean"
    t4.CaptureRunner._route = _ORIGINAL_ROUTE

    for rname in ("hand_rolled", "delegating"):
        a = hits["X_LIFT=off / %s" % rname]
        b = hits["X_LIFT=clean / %s" % rname]
        print("\n  %s router - X_LIFT off -> clean:" % rname)
        print("    gained: %s" % sorted(b - a))
        print("    lost  : %s" % sorted(a - b))

    with open(os.path.join(HERE, "g71_router_diag.json"), "w", encoding="utf-8") as fh:
        json.dump({"cells": out,
                   "hits": {k: sorted(v) for k, v in hits.items()}}, fh, indent=2)
    print("\nwrote research/g71_router_diag.json")


if __name__ == "__main__":
    part_a()
    part_b()
