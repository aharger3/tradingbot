"""G76 — proof that the published two-year book fills at prices that had already
traded before the signal existed.

THE LINE
--------
`signal_runner.py:1330`, the last line of `fill_price`:

    return min(max(level, candle.low), candle.high)

reached whenever `bar_extreme_veto` or `near_session_extreme` says the signal
bar's close is jammed against an extreme. `level` is the level the setup just
broke and retested; every detector that reaches this line has already required
the bar to CLOSE THROUGH that level:

    break-and-retest long   `current.close > level_hi`      (signal_runner.py:2722)
    one candle rule long    `current.close > block.high`    (signal_runner.py:2879)
    84% re-entry long       `current.close >= entry_price`  (signal_runner.py:2946)

so on a long `level < close`, and the booked fill is BELOW the minute's last
price. The close IS the minute's last trade. Therefore the fill price traded
strictly BEFORE the moment the signal came into existence. Only an order already
resting at the level gets it.

THE ARITHMETIC IS NOT A MODEL. It reads the book and the archived bars:

  * how many traded rows book a price other than the signal minute's close,
  * the mean R of those against the ones that book the close,
  * a worked example, printed bar by bar.

Usage:  python research/g76_rebuild_lookahead.py
Writes: research/g76_lookahead.json
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf     # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
OUT = ROOT / "research" / "g76_lookahead.json"
EPS = 0.005                   # the book rounds prices to 2dp


def main():
    print("loading %s ..." % BOOK.name, flush=True)
    book = json.load(open(BOOK, encoding="utf-8"))
    rows = [r for r in book["trades"] if r.get("traded")]
    print("%d traded rows" % len(rows), flush=True)

    bycache = {}

    def bars(sym, day):
        k = (sym, day)
        if k not in bycache:
            if len(bycache) > 40:
                bycache.clear()
            bycache[k] = pf.rth(pf.fetch_day(sym, day))
        return bycache[k]

    rows.sort(key=lambda r: (r["sym"], r["day"]))
    intrabar, atclose, unmatched = [], [], 0
    examples = []
    for r in rows:
        b = bars(r["sym"], r["day"])
        i = r["entry_i"]
        if i >= len(b):
            unmatched += 1
            continue
        c = b[i]
        long = r["dir"] == "call"
        # "the price already traded this minute, and it is not the last price
        # of the minute" -- the fill is inside the bar's range, on the far side
        # of the close from the trade's direction.
        gap = (c.close - r["entry"]) if long else (r["entry"] - c.close)
        rec = {"sym": r["sym"], "day": r["day"], "et": r["et"], "dir": r["dir"],
               "setup": r["setup"], "entry": r["entry"], "stop": r["stop"],
               "o": c.open, "h": c.high, "l": c.low, "close": c.close,
               "gap": round(gap, 4), "r": r["r"], "pnl": r["pnl"]}
        if gap > EPS:
            intrabar.append(rec)
        else:
            atclose.append(rec)

    def sm(xs):
        rs = [x["r"] for x in xs]
        return {"n": len(xs),
                "mean_r": round(statistics.fmean(rs), 4) if rs else 0.0,
                "median_r": round(statistics.median(rs), 4) if rs else 0.0,
                "win_pct": round(sum(1 for x in xs if x["pnl"] > 0) / len(xs) * 100, 1)
                if xs else 0.0,
                "total_dollars": round(sum(x["pnl"] for x in xs), 0)}

    # a worked example: the biggest winner whose fill is a full cent or more
    # below the close it was signalled on, on a plain break-and-retest
    cands = [x for x in intrabar
             if x["setup"] == "break_and_retest" and x["gap"] >= 0.01]
    cands.sort(key=lambda x: -x["r"])
    examples = cands[:3] + sorted(cands, key=lambda x: -x["gap"])[:3]

    out = {"book": str(BOOK), "traded_rows": len(rows), "unmatched": unmatched,
           "line": "signal_runner.py:1330  return min(max(level, candle.low), candle.high)",
           "intrabar": sm(intrabar), "at_close": sm(atclose),
           "intrabar_pct": round(len(intrabar) / (len(intrabar) + len(atclose)) * 100, 1),
           "examples": examples}
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2)

    print()
    print("fills that are NOT the signal minute's close: %d of %d  (%.1f%%)"
          % (len(intrabar), len(intrabar) + len(atclose), out["intrabar_pct"]))
    print("  intrabar fills   mean R %+.3f   win %.1f%%   $%s"
          % (out["intrabar"]["mean_r"], out["intrabar"]["win_pct"],
             format(int(out["intrabar"]["total_dollars"]), ",")))
    print("  close fills      mean R %+.3f   win %.1f%%   $%s"
          % (out["at_close"]["mean_r"], out["at_close"]["win_pct"],
             format(int(out["at_close"]["total_dollars"]), ",")))
    print()
    print("worked examples (all long/short shown as the book has them):")
    for e in examples:
        print("  %s %s %s %s  fill %.2f  bar o%.2f h%.2f l%.2f c%.2f  "
              "fill is %.2f %s the close   R %+.2f"
              % (e["sym"], e["day"], e["et"], e["dir"], e["entry"],
                 e["o"], e["h"], e["l"], e["close"], abs(e["gap"]),
                 "below" if e["dir"] == "call" else "above", e["r"]))
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
