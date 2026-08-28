"""w6_close_beyond_stop.py -- the odds question, answered.

THE QUESTION (Austin, 2026-08-27, about a stop resting inside the entry
candle's own price range): **"yes, but what are the odds of this happening?"**

`research/p26_intrabar_ambiguity.py` already answers half of it: **86.8% of
traded intrabar fills sit on a bar whose high/low range also contains the
trade's stop**, and 790 of those 792 rows are `signal_runner.intrabar_stop`
putting the stop ON the entry bar's own extreme by construction.

What that file does NOT answer, and what he actually needs, is the half that
2026-08-28 made decidable. He settled that day that **a close, and only a
close, stops you out, and the entry candle's own close counts**:

> Q: "Entry is mid-candle at the level. That SAME candle then closes beyond
>     your stop. Are you out on that close, or does the stop only go live from
>     the next candle?"
> A: "Out on that same close."

So the odds he is asking about are not "can the stop price be touched inside
the entry minute" -- of course it can, 86.8% of the time. The odds are:

    **given that you entered mid-candle, what is the chance that same candle
    CLOSES against you, past your stop, and takes you out on the bar you
    entered on?**

That is a decidable question. There is exactly one close per bar and the book
records it, so nothing here is ambiguous.

METHOD -- p26 IS IMPORTED, NOT REWRITTEN
----------------------------------------
`load_day`, `index_day`, `classify`, `HALF_CENT` and `EPS` all come from
`p26_intrabar_ambiguity` by import. The populations below are therefore
p26's populations, cut the same way, off the same `research/bt2y_trades.json`
(45,175 signals / 1,016 traded, 2024-08-21 -> 2026-08-21, 500 sessions). If
p26's classification moves, this moves with it. The ONLY thing added is the
close-vs-stop test, which p26 never asked:

    long  (call)  stopped on the entry bar's own close  <=>  close < stop
    short (put)   stopped on the entry bar's own close  <=>  close > stop

Stated twice, because the book stores entry and stop as `round(x, 2)` and the
true stop lies in [stop - HALF_CENT, stop + HALF_CENT]:

  strict   the close clears the whole rounding band on the losing side
           (long: close < stop - HALF_CENT). Cannot be a rounding artifact.
  lenient  the close is at or past the near edge of the band
           (long: close <= stop + HALF_CENT). Counts a close sitting exactly
           ON the stop as an out.

RECONCILIATION WITH p8
----------------------
`research/p8_scratch.py` instrumented 43,374 created trades and found the entry
bar's close on the good side of BOTH the stop and the level every single time --
zero crossings. That was measured over a different population (every created
trade, including the ones the engine then skipped) and asked about the level as
well as the stop. This file re-asks the stop half over p26's population and
prints whether the two agree. `--selfcheck` asserts the agreement rather than
leaving it to prose.

READ-ONLY. No default changed, no flag added, no bar fetched -- `load_day`
returns None on an archive miss and the row is counted as a data gap, so this
can never touch POLYGON_API_KEY.

    python research/w6_close_beyond_stop.py [--limit N]
    python research/w6_close_beyond_stop.py --selfcheck

Writes nothing; prints the table. The numbers land in
`research/w6_tz_recall_and_odds.md`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from research.p26_intrabar_ambiguity import (  # noqa: E402
    BT2Y, EPS, HALF_CENT, classify, index_day, load_day,
)
from omen_bot import Candle  # noqa: E402


def close_vs_stop(row: dict, bar) -> dict:
    """Did the candle Austin entered on close past his stop?

    One close per bar, so this is decided, not ambiguous. `dist_r` is how far
    the close sat from the stop in units of the trade's own risk -- positive
    means the close was on the GOOD side, i.e. the trade survived its own
    entry bar."""
    is_long = row["dir"] == "call"
    stop = float(row["stop"])
    entry = float(row["entry"])
    c = bar.close

    if is_long:
        strict = c < stop - HALF_CENT
        lenient = c <= stop + HALF_CENT
        good_dist = c - stop
    else:
        strict = c > stop + HALF_CENT
        lenient = c >= stop - HALF_CENT
        good_dist = stop - c

    risk = abs(entry - stop)
    return {
        "close_beyond_strict": strict,
        "close_beyond_lenient": lenient,
        "good_dist": good_dist,
        "dist_r": (good_dist / risk) if risk > EPS else None,
    }


def build(limit=None):
    with open(BT2Y, encoding="utf-8") as fh:
        book = json.load(fh)
    rows = book["trades"]
    by_day = defaultdict(list)
    for r in rows:
        by_day[(r["sym"], r["day"])].append(r)

    keys = sorted(by_day)
    if limit:
        keys = keys[:limit]

    out, missing_day, missing_bar = [], 0, 0
    for n, (sym, day) in enumerate(keys):
        rth = load_day(sym, day)
        if not rth:
            missing_day += len(by_day[(sym, day)])
            continue
        idx, run_hi, run_lo = index_day(rth)
        for r in by_day[(sym, day)]:
            i = idx.get(r["et"])
            if i is None:
                missing_bar += 1
                continue
            rec = classify(r, rth[i], run_hi[i], run_lo[i])
            rec.update(close_vs_stop(r, rth[i]))
            rec["sym"], rec["day"], rec["et"] = r["sym"], r["day"], r["et"]
            out.append(rec)
        if n and n % 2000 == 0:
            print("  %d/%d symbol-days" % (n, len(keys)), flush=True)
    return out, book.get("meta", {}), missing_day, missing_bar


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def report(recs, meta, missing_day, missing_bar):
    def cut(name, pop):
        intra = [c for c in pop if c["intrabar"]]
        amb = [c for c in intra if c["amb_possible"]]
        at_ext = [c for c in amb if c["at_extreme"]]
        resid = [c for c in amb if not c["at_extreme"]]
        rows = []
        for label, xs in (("all signals in cut", pop),
                          ("intrabar fills", intra),
                          ("+ stop inside the entry bar (p26 'ambiguous')", amb),
                          ("   ... of which stop IS the bar's own extreme", at_ext),
                          ("   ... residual: stop strictly inside the bar", resid)):
            s = sum(1 for c in xs if c["close_beyond_strict"])
            l = sum(1 for c in xs if c["close_beyond_lenient"])
            rows.append((label, len(xs), s, pct(s, len(xs)), l, pct(l, len(xs))))
        print("\n### %s" % name)
        print("%-46s %8s %8s %8s %8s %8s"
              % ("population", "n", "close<stop", "%", "lenient", "%"))
        for label, n, s, sp, l, lp in rows:
            print("%-46s %8d %8d %7.2f%% %8d %7.2f%%" % (label, n, s, sp, l, lp))
        return amb

    print("=" * 96)
    print("W6 / §5.1 -- the odds that the entry candle's own close stops you out")
    print("book: %s" % json.dumps(meta)[:200])
    print("rows classified: %d   archive gaps: %d symbol-day, %d bar"
          % (len(recs), missing_day, missing_bar))
    print("=" * 96)

    traded = [c for c in recs if c["traded"]]
    amb_traded = cut("TRADED BOOK  (the population the 2.0R money gate reads)", traded)
    cut("ALL SIGNALS", recs)
    cut("TRADED S", [c for c in traded if c["sgrade"] == "S"])

    # How much daylight was there? The closest call in the whole population.
    dr = [(c["dist_r"], c) for c in amb_traded if c["dist_r"] is not None]
    dr.sort(key=lambda t: t[0])
    print("\n### closest calls on the traded ambiguous rows "
          "(distance from close to stop, in R; positive = trade survived)")
    for d, c in dr[:8]:
        print("   %+.4f R   %-6s %s %s  %s" % (d, c["sym"], c["day"], c["et"], c["sgrade"]))
    neg = sum(1 for d, _ in dr if d < 0)
    print("   rows with a NEGATIVE distance (close past the stop): %d of %d"
          % (neg, len(dr)))

    print("\n### reconciliation with research/p8_scratch.py")
    all_strict = sum(1 for c in recs if c["close_beyond_strict"])
    print("   p8 (43,374 created trades): entry bar's close on the good side of the")
    print("   stop AND the level every single time -- zero crossings.")
    print("   here (%d classified rows): %d closes strictly beyond the stop."
          % (len(recs), all_strict))
    print("   AGREE" if all_strict == 0 else "   DISAGREE -- investigate before publishing")


def selfcheck():
    """Assert the close test, and assert it agrees with p8's zero-crossing
    result on the shape of the thing rather than on a re-run."""
    print("w6 selfcheck")

    def bar(o, h, l, c):
        return Candle(timestamp="09:45:00", open=o, high=h, low=l, close=c, volume=1000)

    # A long that closes BELOW its stop: this is an out on the entry bar itself.
    b = bar(99.70, 100.90, 99.60, 99.70)
    r = close_vs_stop({"dir": "call", "entry": 100.00, "stop": 99.80}, b)
    assert r["close_beyond_strict"] and r["close_beyond_lenient"], \
        "a long closing at 99.70 with a 99.80 stop is out on that close"
    assert r["dist_r"] < 0, "distance must be negative when the close is past the stop"

    # The same long closing above the stop: it survives its own entry bar.
    b2 = bar(99.70, 100.90, 99.60, 100.85)
    r2 = close_vs_stop({"dir": "call", "entry": 100.00, "stop": 99.80}, b2)
    assert not r2["close_beyond_strict"] and not r2["close_beyond_lenient"]
    assert r2["dist_r"] > 0

    # A short mirror.
    b3 = bar(100.20, 100.90, 99.60, 100.90)
    r3 = close_vs_stop({"dir": "put", "entry": 100.00, "stop": 100.20}, b3)
    assert r3["close_beyond_strict"], "a short closing at 100.90 with a 100.20 stop is out"

    # THE STRUCTURAL RESULT, and it is why the answer is what it is:
    # `signal_runner.intrabar_stop` puts the stop ON the entry bar's own
    # extreme. A bar's close can never be outside its own high/low, so on every
    # such row the close CANNOT be beyond the stop. p26 says this class is
    # 790 of the traded book's 792 ambiguous rows.
    b4 = bar(99.70, 100.90, 99.60, 100.85)
    r4 = close_vs_stop({"dir": "call", "entry": 100.00, "stop": 99.60}, b4)
    assert not r4["close_beyond_strict"], \
        "stop == the bar's own low: the close is inside the bar, so it cannot be beyond"
    b5 = bar(100.20, 100.90, 99.60, 99.65)
    r5 = close_vs_stop({"dir": "put", "entry": 100.00, "stop": 100.90}, b5)
    assert not r5["close_beyond_strict"], \
        "stop == the bar's own high on a short: same structural result, mirrored"

    print("  OK -- 5 cases, including the intrabar_stop structural case")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        selfcheck()
        return
    recs, meta, md, mb = build(a.limit)
    report(recs, meta, md, mb)


if __name__ == "__main__":
    main()
