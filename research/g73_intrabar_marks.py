"""G73 / intrabar -- DID HIS OWN TAPE STOP HIM OUT ON A WICK?

Austin, 2026-08-29:

    "stop loss is not on candle close i dont like that, stop happen when they do
     in middle of timeframes. weve talked about stops a lot so that seems like a
     stale opinion."

CLAUDE.md and DIRECTION.md carry the opposite as a standing invariant. This
script does not argue with either of them. It goes to the only umpire that
outranks both -- his own marks -- and asks a question that has a factual answer:

    On the marked symbol-days that carry BOTH an entry bar AND a stop PRICE,
    did price WICK through his stop and recover before any candle CLOSED
    through it? And on those days, does his own note say he was still in the
    trade afterwards?

If price wicked his stop and he wrote "no stop out" / "stop out happened later",
he was close-only IN PRACTICE whatever he says now. If he wrote that he was out
at the wick, he was intrabar.

READ-ONLY. Loads mark corpora through `research.p25_midcandle_entry` (the same
loader `research/g71_stops.py::his_marks` uses, imported not reimplemented) and
bars through `research.t4_engine_recall.rth_candles`. Writes nothing but its own
`research/_g73_marks.json`.

    python research/g73_intrabar_marks.py            # measure -> json + tables
    python research/g73_intrabar_marks.py --selfcheck
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = os.path.join(HERE, "_g73_marks.json")

# His session. Flat by 11:00 (rulebook, ballot q6) -- the runner may live past
# it, so the wider 16:00 scan is reported beside it rather than instead of it.
WINDOW_END = "11:00"
DAY_END = "16:00"


def _touch(bar, stop, long):
    """Did this bar's WICK reach the stop? The intrabar reading."""
    return bar.low <= stop if long else bar.high >= stop


def _closed(bar, stop, long):
    """Did this bar CLOSE beyond the stop? The shipped reading
    (`stop_rule.stop_hit_on_close`, same predicate, Candle-shaped)."""
    return bar.close <= stop if long else bar.close >= stop


def scan(bars, i0, stop, long, end=WINDOW_END):
    """First wick-touch and first close-through after the entry bar."""
    touch = close_i = None
    n = 0
    for j in range(i0 + 1, len(bars)):
        if bars[j].timestamp[:5] > end:
            break
        n += 1
        if touch is None and _touch(bars[j], stop, long):
            touch = j
        if close_i is None and _closed(bars[j], stop, long):
            close_i = j
        if touch is not None and close_i is not None:
            break
    return touch, close_i, n


# Notes that assert he was STILL IN the trade -- the whole point of the exercise.
STILL_IN = [
    r"no stop out",
    r"i don'?t see (a|the) stop out",
    r"i dont see (a|the) stop out",
    r"stop out (would'?ve|would have)? ?(been|happened)",
    r"stop out (doesn'?t|does not|didn'?t) happen",
    r"never closed below the stop",
    r"didn'?t close below",
    r"did ?n'?t close BELOW",
    r"wouldn'?t (have|of) been stopped out",
    r"still would'?ve been in the trade",
    r"stop out happens when candle CLOSES",
    r"stop outs only happen when candle closes",
]
STILL_IN_RE = re.compile("|".join(STILL_IN), re.I)


def followthrough(wicked, rth_candles):
    """On the marks a wick pierced: what did the trade do AFTERWARDS?

    Measured from the bar after the wick, and stopped at whichever comes first:
    the bar that CLOSES through the stop, or 11:00. So this is strictly what
    the close-only rule would have collected and the intrabar rule would have
    thrown away. Favourable excursion in R off his own entry and risk."""
    import statistics
    mfes = []
    for r in wicked:
        bars = rth_candles(r["sym"], r["day"])
        if not bars:
            continue
        long, e = r["side"] == "L", r["entry"]
        risk = abs(e - r["stop"])
        seg = []
        for j in range(r["touch_i"] + 1, len(bars)):
            if bars[j].timestamp[:5] > WINDOW_END:
                break
            if r["close_i"] is not None and j > r["close_i"]:
                break
            seg.append(bars[j])
        mfe = 0.0 if not seg else max(
            ((b.high - e) if long else (e - b.low)) / risk for b in seg)
        mfes.append((mfe, r))
    if not mfes:
        return
    v = sorted(x for x, _ in mfes)
    print()
    print("AFTER the wick, before any candle closed through the stop (or 11:00):")
    print("  reached +2R: %d of %d" % (sum(1 for x, _ in mfes if x >= 2.0), len(mfes)))
    print("  reached +1R: %d of %d" % (sum(1 for x, _ in mfes if x >= 1.0), len(mfes)))
    print("  median favourable move %+0.2fR, best %+0.2fR (%s %s)"
          % (v[len(v) // 2], v[-1], max(mfes)[1]["sym"], max(mfes)[1]["day"]))
    return mfes


def book(rows, rth_candles):
    """His 113 marked trades, run to a result under each rule.

    The exit model is deliberately the plainest thing that is his: enter at his
    entry price, target 2R (the engine's own `entry +/- 2 x risk`), flat at
    11:00. The ONLY difference between the two arms is what ends the trade on
    the losing side -- a wick through the stop (fill AT the stop, a resting
    order) versus a candle closing through it (fill at that close, floored at
    -1.25R by `stop_rule.stop_fill_price`). Same trades, same targets, same
    clock, so the delta is the stop rule and nothing else.

    This is not the two-year book and does not pretend to be. It is 113 rows
    HE picked, which is the point: it is the only sample where the entry, the
    stop and the judgement are all his."""
    from stop_rule import stop_fill_price
    out = {}
    for arm in ("intrabar", "close_only"):
        rs = []
        for r in rows:
            bars = rth_candles(r["sym"], r["day"])
            if not bars:
                continue
            long, e, st = r["side"] == "L", r["entry"], r["stop"]
            risk = abs(e - st)
            tgt = e + 2 * risk if long else e - 2 * risk
            res = None
            for j in range(r["entry_i"] + 1, len(bars)):
                b = bars[j]
                if b.timestamp[:5] > WINDOW_END:
                    break
                stopped = (_touch(b, st, long) if arm == "intrabar"
                           else _closed(b, st, long))
                if stopped:
                    px = st if arm == "intrabar" else stop_fill_price(
                        b.close, e, risk, long)
                    res = ((px - e) if long else (e - px)) / risk
                    break
                if (b.high >= tgt) if long else (b.low <= tgt):
                    res = 2.0
                    break
            if res is None:
                last = [b for b in bars[r["entry_i"] + 1:]
                        if b.timestamp[:5] <= WINDOW_END]
                if not last:
                    continue
                res = ((last[-1].close - e) if long else (e - last[-1].close)) / risk
            rs.append(res)
        out[arm] = rs
    import statistics
    print()
    print("HIS 113 MARKS, run to a result -- 2R target, flat 11:00, only the stop rule differs")
    for arm in ("intrabar", "close_only"):
        rs = out[arm]
        w = sum(1 for x in rs if x > 0)
        print("  %-11s n=%d  mean %+0.4f R  ($%+d/trade)  win %.1f%%  worst %+0.2f R"
              % (arm, len(rs), statistics.fmean(rs), round(statistics.fmean(rs) * 1000),
                 100.0 * w / len(rs), min(rs)))
    a, b = out["close_only"], out["intrabar"]
    d = [x - y for x, y in zip(a, b)]
    m = statistics.fmean(d)
    se = statistics.stdev(d) / (len(d) ** 0.5)
    print("  close_only MINUS intrabar, paired on the same 113 rows: %+0.4f R  SE %0.4f  t %+0.2f  ($%+d/trade)"
          % (m, se, m / se if se else 0, round(m * 1000)))
    return out


def main():
    from research import p25_midcandle_entry as p25
    from research.t4_engine_recall import rth_candles

    rows, skipped = [], Counter()
    for row in p25.iter_marks():
        if not p25.usable(row):
            skipped["no_entry"] += 1
            continue
        stop = p25.clean_stop(row)
        if stop is None:
            skipped["stop_is_a_note"] += 1
            continue
        sym, day, i = row["symbol"], row["date"], row["entry_i"]
        bars = rth_candles(sym, day)
        if not bars or i < 0 or i >= len(bars):
            skipped["no_bars"] += 1
            continue
        entry = float(row["entry_p"])
        long = (row.get("side") or "L").upper().startswith("L")
        risk = abs(entry - stop)
        if risk <= 0:
            skipped["zero_risk"] += 1
            continue
        # The stop must be on the LOSING side of the entry or it is not a stop.
        if (long and stop >= entry) or ((not long) and stop <= entry):
            skipped["stop_wrong_side"] += 1
            continue

        t11, c11, n11 = scan(bars, i, stop, long, WINDOW_END)
        t16, c16, n16 = scan(bars, i, stop, long, DAY_END)

        if t11 is None:
            verdict = "never_reached"
        elif c11 is None:
            verdict = "wick_only"              # touched, never closed through
        elif t11 < c11:
            verdict = "wick_then_close"        # touched first, closed later
        else:
            verdict = "same_bar"               # first touch bar also closed through

        note = (row.get("note") or row.get("notes") or "")
        if isinstance(note, dict):
            note = " ".join(str(v) for v in note.values())
        rows.append({
            "sym": sym, "day": day, "side": "L" if long else "S",
            "entry": entry, "stop": stop, "risk": round(risk, 4),
            "entry_i": i, "bars_scanned_11": n11,
            "touch_i": t11, "close_i": c11,
            "gap_bars": (c11 - t11) if (t11 is not None and c11 is not None) else None,
            "touch_i_16": t16, "close_i_16": c16,
            "verdict": verdict,
            "tier": row.get("austin_tier") or row.get("grade") or "",
            "setup": row.get("setup") or row.get("setup_type") or "",
            "result": row.get("result") or "",
            "src": row.get("_src", ""),
            "note": note,
            "says_still_in": bool(STILL_IN_RE.search(note)),
        })

    # --- tables -----------------------------------------------------------
    V = Counter(r["verdict"] for r in rows)
    wicked = [r for r in rows if r["verdict"] in ("wick_only", "wick_then_close")]
    said = [r for r in rows if r["says_still_in"]]
    said_wicked = [r for r in said if r["verdict"] in ("wick_only", "wick_then_close")]

    print("MARKS WITH AN ENTRY BAR AND A STOP PRICE: %d" % len(rows))
    print("skipped: %s" % dict(skipped))
    print()
    print("what the tape did after his entry, inside his 09:30-11:00 window")
    for k in ("never_reached", "wick_only", "wick_then_close", "same_bar"):
        print("  %-16s %4d  (%.1f%%)" % (k, V[k], 100.0 * V[k] / max(1, len(rows))))
    print()
    print("price WICKED his stop and did not close through on that bar: %d of %d (%.1f%%)"
          % (len(wicked), len(rows), 100.0 * len(wicked) / max(1, len(rows))))
    print("  of those, never closed through it at all (pure wick):  %d" % V["wick_only"])
    print("  of those, closed through it LATER:                     %d" % V["wick_then_close"])
    gaps = [r["gap_bars"] for r in rows if r["gap_bars"]]
    if gaps:
        gaps.sort()
        print("  when it did close through later, the wick came %d bars earlier (median), max %d"
              % (gaps[len(gaps) // 2], gaps[-1]))
    print()
    print("HIS OWN WORDS -- marks whose note asserts he was still in the trade: %d" % len(said))
    print("  of those, the tape shows a wick through his stop first: %d" % len(said_wicked))
    for r in said_wicked:
        print("   %-6s %s %s  touch +%s, close-through %s -- %s"
              % (r["sym"], r["day"], r["side"], r["touch_i"] - r["entry_i"],
                 ("+%d" % (r["close_i"] - r["entry_i"])) if r["close_i"] else "never",
                 r["note"][:110]))
    print()
    print("  the same notes whose tape did NOT wick the stop:")
    for r in said:
        if r not in said_wicked:
            print("   %-6s %s %s  verdict=%-14s -- %s"
                  % (r["sym"], r["day"], r["side"], r["verdict"], r["note"][:100]))
    print()
    print("wicked-and-recovered by his grade: %s"
          % dict(Counter(r["tier"] for r in wicked)))
    print("all marks by his grade:            %s"
          % dict(Counter(r["tier"] for r in rows)))

    followthrough(wicked, rth_candles)
    book(rows, rth_candles)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"n": len(rows), "skipped": dict(skipped),
                   "verdicts": dict(V), "rows": rows}, fh, indent=1)
    print("\nwrote %s" % OUT)


def _selfcheck():
    class B:
        def __init__(s, ts, o, h, l, c):
            s.timestamp, s.open, s.high, s.low, s.close = ts, o, h, l, c
    # long, stop 99. bar1 wicks to 98.5 closes 100.2; bar2 closes 98.0
    bars = [B("09:40:00", 100, 101, 99.9, 100.5),
            B("09:41:00", 100.5, 100.6, 98.5, 100.2),
            B("09:42:00", 100.2, 100.3, 97.9, 98.0)]
    assert scan(bars, 0, 99.0, True) == (1, 2, 2)
    # short, stop 101: bar1 wicks nothing above 101 -> never reached
    assert scan(bars, 0, 101.0, False) == (None, None, 2)
    # short, stop 100.55: bar1 high 100.6 touches, closes 100.2 -> wick only
    t, c, n = scan(bars, 0, 100.55, False)
    assert t == 1 and c is None, (t, c)
    # never reached
    assert scan(bars, 0, 90.0, True) == (None, None, 2)
    # the window cap bites
    t, c, n = scan([B("10:59:00", 1, 1, 1, 1), B("11:01:00", 1, 1, 0, 0)], -1, 0.5, True)
    assert n == 1 and t is None
    assert STILL_IN_RE.search("I dont see the stop out until later")
    assert STILL_IN_RE.search("stop outs only happen when candle closes by the way")
    assert STILL_IN_RE.search("your entry never closed below the stop so no need")
    assert not STILL_IN_RE.search("lots of consolidation but clear stop")
    print("g73 marks selfcheck ok: 9 checks")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
