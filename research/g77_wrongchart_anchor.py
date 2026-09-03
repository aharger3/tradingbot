"""g77_wrongchart_anchor.py -- did the CHART itself differ, not just the label?

The homework card marks nothing (probe_chart.render(..., marks=[])), so at first
glance the picture is the same whichever signal the deck picks. It is not: HOD and
LOD are drawn as they stood at the CARD'S setup bar (g71_homework_build.running_extremes,
anchored on `hodlod_anchor_bar`). Pick a different signal and those two lines move.

For every card where the engine traded a signal that was not the card, print the
HOD/LOD as drawn versus HOD/LOD as they would have been drawn for the engine's
real trade, plus the 09:30-10:00 tape around Austin's minute for the two cases the
board flagged.

Read-only. Writes research/g77_wrongchart_anchor.json.
"""
from __future__ import annotations
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd  # noqa: E402

CENSUS = os.path.join(HERE, "g77_wrongchart_census.json")
CACHE = os.path.join(HERE, "g77_wrongchart_signals.json")
OUT = os.path.join(HERE, "g77_wrongchart_anchor.json")

TAPE_DAYS = [("MSFT", "2025-08-29", "09:38"), ("NVDA", "2026-05-11", "09:43")]


def running_extremes(candles, i):
    pre = candles[:i]
    if not pre:
        return None, None
    return max(c.high for c in pre), min(c.low for c in pre)


def main():
    d = json.load(open(CENSUS, encoding="utf-8"))
    raw = json.load(open(CACHE, encoding="utf-8"))
    man = raw["manifest"]
    sig = raw["signals"]

    out = []
    for p in d["cards"]:
        if p["card_traded"] or p["n_traded"] == 0:
            continue
        sym, day = p["symbol"], p["date"]
        candles = bd.session_candles(sym, day)
        m = man[p["card_id"]]
        card_i = m["hodlod_anchor_bar"]
        rows = sig["%s|%s" % (sym, day)]
        tr = [r for r in rows if r["traded"]]
        tr.sort(key=lambda r: r["et"])
        t = tr[0]
        hod_c, lod_c = running_extremes(candles, card_i)
        hod_t, lod_t = running_extremes(candles, t["entry_i"])
        out.append({
            "card_id": p["card_id"],
            "card": "%s %s %s" % (p["card_setup"], p["card_et"], p["card_dir"]),
            "engine_trade": "%s %s %s on %s" % (
                {"break_and_retest": "BR", "one_candle_rule": "OCR",
                 "reentry_84_rule": "84"}.get(t["setup"], t["setup"]),
                t["et"], t["dir"], t["level_name"]),
            "engine_r": t["r"], "engine_pnl": t["pnl"],
            "card_bar": card_i, "trade_bar": t["entry_i"],
            "hod_drawn": round(hod_c, 2), "hod_if_real_trade": round(hod_t, 2),
            "lod_drawn": round(lod_c, 2), "lod_if_real_trade": round(lod_t, 2),
            "hod_moves": abs(hod_c - hod_t) > 0.005,
            "lod_moves": abs(lod_c - lod_t) > 0.005,
            "same_direction": p["card_dir"] == t["dir"],
            "same_arm": p["card_setup"] == {"break_and_retest": "BR",
                                            "one_candle_rule": "OCR",
                                            "reentry_84_rule": "84"}.get(t["setup"]),
        })

    print("cards where the engine traded a DIFFERENT signal on the same chart: %d" % len(out))
    print("%-18s %-16s %-34s %6s %6s  %-16s %-16s %s"
          % ("card", "the card", "what the engine actually traded", "bar", "bar",
             "HOD drawn/real", "LOD drawn/real", "dir"))
    for r in out:
        print("%-18s %-16s %-34s %6d %6d  %7.2f/%-7.2f %7.2f/%-7.2f %s"
              % (r["card_id"], r["card"], r["engine_trade"], r["card_bar"],
                 r["trade_bar"], r["hod_drawn"], r["hod_if_real_trade"],
                 r["lod_drawn"], r["lod_if_real_trade"],
                 "same" if r["same_direction"] else "OPPOSITE"))
    n_moved = sum(1 for r in out if r["hod_moves"] or r["lod_moves"])
    n_opp = sum(1 for r in out if not r["same_direction"])
    print()
    print("HOD or LOD line actually moves on %d of %d" % (n_moved, len(out)))
    print("card points the OPPOSITE way to the engine's real trade on %d of %d"
          % (n_opp, len(out)))

    # the tape around his minute, for the two flagged cases
    tape = {}
    for sym, day, hm in TAPE_DAYS:
        candles = bd.session_candles(sym, day)
        m = man["%s_%s" % (sym, day)]
        lv = m["drawn_levels"]
        print()
        print("=== %s %s   his minute %s   levels %s" % (sym, day, hm, lv))
        rowsd = []
        for i, c in enumerate(candles[:40]):
            t = "%02d:%02d" % (9 + (30 + i) // 60, (30 + i) % 60)
            rowsd.append({"i": i, "et": t, "o": c.open, "h": c.high,
                          "l": c.low, "c": c.close})
            flag = " <== his minute" if t == hm else ""
            print("  %s bar%-3d O%.2f H%.2f L%.2f C%.2f%s"
                  % (t, i, c.open, c.high, c.low, c.close, flag))
        tape[sym] = rowsd

    json.dump({"anchor": out, "tape": tape}, open(OUT, "w", encoding="utf-8"), indent=1)
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
