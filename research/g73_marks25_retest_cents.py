"""g73_marks25_retest_cents.py -- "the retest missed by a few cents", priced.

Austin on AVGO 2025-12-03 (probe_g71_homework_s3_2026-08-29.jsonl, READ-ONLY):

    "i dont see anything: 9:33 can be a great break of pdl but the retest missed
     by a few cents"

He is describing a rejection: a break he liked, killed by a retest that did not
tag the level. This script turns "a few cents" into a number and puts it beside
the tolerances the engine actually ships, so the ballot question can be asked
with an arithmetic answer attached.

WHAT THE ENGINE SHIPS TODAY
    omen_bot.detect_break_retest step 3 uses `retest_tol_mult * avg_range`, and
    signal_runner._retest_tol() returns 0.0 unless DETECT_WIDE -- which is
    False. So the shipped retest test is an EXACT TOUCH: zero cents.
    The off-by-default alternative is DETECT_WIDE_RETEST_MULT = 1.0, a WHOLE
    average candle range.
    The project's single tolerance unit, BAR_EXTREME_FRAC, is 0.25 -- and it
    governs the ON WATCH trigger, the 84% reclaim window and stop slippage, but
    NOT this step.

So there are three numbers on the table (0.00x, 0.25x, 1.00x of a bar range) and
the retest step uses the one Austin never picked.

    python research/g73_marks25_retest_cents.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd                                    # noqa: E402
from signal_runner import BAR_EXTREME_FRAC, DETECT_WIDE, DETECT_WIDE_RETEST_MULT  # noqa: E402

OUT = os.path.join(HERE, "g73_marks25_retest_cents.json")

# The card, the level he named, and the minute he named.
SYM, DAY, HIS_MIN, LEVEL_NAME = "AVGO", "2025-12-03", "09:33", "PDL"


def main():
    candles = bd.session_candles(SYM, DAY)
    if not candles:
        print("no bars for", SYM, DAY)
        return
    def _hm(ts):
        return ts[11:16] if "T" in ts else ts[:5]

    rows = [{"t": _hm(c.timestamp), "o": c.open, "h": c.high,
             "l": c.low, "c": c.close} for c in candles]

    # PDL as the book itself labelled it on that symbol-day, so the level is not
    # re-derived by hand. Fall back to the card's own level_px.
    manifest = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
    level_px = None
    for l in open(manifest, encoding="utf-8"):
        r = json.loads(l)
        if r["card_id"] == f"{SYM}_{DAY}":
            level_px = (r.get("drawn_levels") or {}).get("pdl")
            drawn = r.get("drawn_levels")
            break
    res = {"symbol": SYM, "day": DAY, "his_minute": HIS_MIN,
           "level": LEVEL_NAME, "level_px": level_px, "drawn_levels": drawn,
           "shipped_retest_tolerance": {
               "DETECT_WIDE": DETECT_WIDE,
               "effective_mult": DETECT_WIDE_RETEST_MULT if DETECT_WIDE else 0.0,
               "means": "exact touch -- the retest bar must trade AT or through "
                        "the level" if not DETECT_WIDE else "widened",
               "DETECT_WIDE_RETEST_MULT_if_on": DETECT_WIDE_RETEST_MULT,
               "BAR_EXTREME_FRAC": BAR_EXTREME_FRAC,
           }}

    if level_px is None:
        print(json.dumps(res, indent=1))
        return

    # He named a break at 09:33 of PDL. Find it, then measure how close price
    # came back afterwards, bar by bar, in cents and in bar-ranges.
    idx = {r["t"]: i for i, r in enumerate(rows)}
    i0 = idx.get(HIS_MIN)
    res["his_bar_index"] = i0
    if i0 is None:
        print(json.dumps(res, indent=1))
        return

    b = rows[i0]
    res["his_bar"] = b
    is_long = b["c"] > level_px            # which side the entry points
    res["direction"] = (f"long (entry above {LEVEL_NAME})" if is_long
                        else f"short (entry below {LEVEL_NAME})")

    # THE BREAK IS NOT HIS MINUTE. His minute is the CONFIRM -- the bar he would
    # have entered on. The break is the first earlier bar that closed through
    # the level; the retest is what happens between the two. Getting this the
    # wrong way round is the difference between a $1.74 miss and an $0.08 one.
    brk = None
    for j in range(1, i0 + 1):
        prev, cur = rows[j - 1], rows[j]
        crossed = ((prev["c"] >= level_px > cur["c"]) if not is_long
                   else (prev["c"] <= level_px < cur["c"]))
        if crossed:
            brk = j
    if brk is None:
        # the level was already broken on the opening bar -- take the first bar
        # that CLOSED through it, which is the same event without a prior bar
        for j in range(0, i0 + 1):
            through = ((rows[j]["c"] < level_px) if not is_long
                       else (rows[j]["c"] > level_px))
            if through:
                brk = j
                break
    res["break_bar"] = {"index": brk, "t": rows[brk]["t"] if brk is not None else None,
                        "close": rows[brk]["c"] if brk is not None else None}

    # avg candle range over the 12-bar detection window ending at HIS bar --
    # the same window detect_break_retest uses (omen_bot.py: w = candles[-12:]).
    w = rows[max(0, i0 - 11):i0 + 1]
    avg_rng = sum(r["h"] - r["l"] for r in w) / len(w)
    res["avg_bar_range_12_at_his_bar"] = round(avg_rng, 4)
    res["window_bars"] = len(w)

    # The retest step is step 3 of FOUR, and the order is the whole point
    # (omen_bot.detect_break_retest): BREAK -> LEAVE (a later bar fully clears
    # the level) -> RETEST (a still-later bar comes back and touches it) ->
    # CONFIRM. So the closest approach is measured only over the bars AFTER the
    # leave and up to his entry bar. Measuring from the break bar instead counts
    # the break bar's own wick as a retest, which is how a 9-cent miss reads as
    # a touch.
    leave = None
    for j in range(brk + 1, i0 + 1):
        cleared = ((rows[j]["l"] > level_px) if is_long
                   else (rows[j]["h"] < level_px))
        if cleared:
            leave = j
            break
    res["leave_bar"] = {"index": leave,
                        "t": rows[leave]["t"] if leave is not None else None}
    start = (leave + 1) if leave is not None else (brk + 1)
    best = None
    for j in range(start, i0 + 1):
        r = rows[j]
        miss = (r["l"] - level_px) if is_long else (level_px - r["h"])
        if best is None or miss < best[1]:
            best = (j, miss, r)
    if best is None:
        res["closest_approach"] = {"error": "no bars between leave and his entry"}
        print(json.dumps(res, indent=1))
        return
    j, miss, r = best
    res["closest_approach"] = {
        "bar": r["t"], "bars_after_leave": j - (leave if leave is not None else brk),
        "miss_dollars": round(miss, 4),
        "miss_cents": round(miss * 100, 1),
        "miss_in_bar_ranges": round(miss / avg_rng, 4) if avg_rng else None,
        "miss_pct_of_price": round(100 * miss / level_px, 4),
        "touched": miss <= 0,
    }
    res["verdict"] = {
        "exact_touch_would_fire": miss <= 0,
        "at_BAR_EXTREME_FRAC_0.25_would_fire": miss <= 0.25 * avg_rng,
        "at_DETECT_WIDE_1.00_would_fire": miss <= 1.00 * avg_rng,
        "tolerance_needed_in_bar_ranges": round(miss / avg_rng, 4) if avg_rng else None,
    }
    res["tolerance_in_cents"] = {
        "shipped_0.00x": 0.0,
        "BAR_EXTREME_FRAC_0.25x": round(0.25 * avg_rng * 100, 1),
        "DETECT_WIDE_1.00x": round(1.00 * avg_rng * 100, 1),
    }
    # every bar's approach, so the shape is visible and not just one number
    res["approach_track"] = [
        {"t": rows[k]["t"],
         "miss_cents": round(((rows[k]["l"] - level_px) if is_long
                              else (level_px - rows[k]["h"])) * 100, 1)}
        for k in range(0, min(i0 + 8, len(rows)))]

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "approach_track"},
                     indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
