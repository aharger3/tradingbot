"""l4_referee2_bars.py -- L4 referee pass 2, the raw-bar semantics check.

Two questions the book alone cannot answer:

 1. Is the 15-candle bucket actually a CLOCK-aligned 15-minute bar?  It is only
    if every archived session's first RTH bar is the 09:30 bar.  Counted here
    over every (symbol, day) the flip set touches, plus a wide sample.
 2. Does the gate remove exactly the rows whose 15-minute structure disagrees
    with the trade direction?  Re-computed from the archived 1-minute bars at
    the signal bar, with the bar list physically truncated at that bar so a
    look-ahead is impossible.

    python research/l4_referee2_bars.py
"""
from __future__ import annotations

import gzip
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import polygon_feed as pf                                    # noqa: E402
from signal_runner import structure15_trend                  # noqa: E402

TAPE = ROOT / "research" / "tape"


def load(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def key(r):
    return (r["day"], r.get("et"), r["sym"], r.get("dir"), r.get("setup"))


def main():
    _, off = load(TAPE / "book_TREND_DEF_off.json.gz")
    _, on = load(TAPE / "book_TREND_DEF_on.json.gz")
    off = [r for r in off if r.get("tier") == "core"]
    on = [r for r in on if r.get("tier") == "core"]
    fo = {key(r): r for r in off if r.get("status") == "fired"}
    fn = {key(r): r for r in on if r.get("status") == "fired"}

    gated = {"one_candle_rule", "reentry_84_rule"}
    lost = [fo[k] for k in (set(fo) - set(fn)) if k[4] in gated]
    kept = [fo[k] for k in (set(fo) & set(fn)) if k[4] in gated]
    print("lost (fired OFF, gone ON) on gated setups: %d" % len(lost))
    print("kept (fired in both)      on gated setups: %d" % len(kept))

    cache = {}

    def bars(sym, day):
        if (sym, day) not in cache:
            try:
                cache[(sym, day)] = pf.rth(pf.fetch_day(sym, day))
            except Exception as e:
                cache[(sym, day)] = []
                print("   fetch failed %s %s: %s" % (sym, day, str(e)[:80]))
        return cache[(sym, day)]

    # ---- 1. bucket alignment -------------------------------------------------
    print("\n--- bucket alignment: first RTH bar of each touched session ---")
    firsts = Counter()
    sessions = sorted({(r["sym"], r["day"]) for r in lost + kept})
    random.seed(4)
    sample = sessions if len(sessions) <= 400 else random.sample(sessions, 400)
    for sym, day in sample:
        b = bars(sym, day)
        firsts[b[0].timestamp if b else "NO BARS"] += 1
    for ts, n in firsts.most_common(10):
        print("   first bar %s : %d sessions" % (ts, n))
    off_grid = sum(n for ts, n in firsts.items() if ts not in ("09:30:00",))
    print("   sessions whose first RTH bar is NOT 09:30:00: %d of %d"
          % (off_grid, sum(firsts.values())))

    # ---- 2. semantics on the flipped rows ------------------------------------
    print("\n--- semantics: the trend read at the signal bar, from raw bars ---")

    def check(rows, label, expect_block):
        agree = disagree = none_read = missing = 0
        bad = []
        for r in rows:
            b = bars(r["sym"], r["day"])
            if not b:
                missing += 1
                continue
            want = (r.get("et") or "") + ":00"
            idx = next((i for i, c in enumerate(b) if c.timestamp == want), None)
            if idx is None:
                missing += 1
                continue
            trend = structure15_trend(b[:idx + 1])          # truncated: no look-ahead
            is_long = r.get("dir") == "call"
            if trend is None:
                none_read += 1
                blocked = False
            else:
                blocked = not ((trend == "bullish") == is_long)
            if blocked == expect_block:
                agree += 1
            else:
                disagree += 1
                if len(bad) < 12:
                    bad.append((r["day"], r["et"], r["sym"], r["dir"], r["setup"],
                                trend, "blocked" if blocked else "allowed"))
        print("   %-28s n=%d  as expected %d  CONTRADICTS %d  (trend None %d, bars missing %d)"
              % (label, len(rows), agree, disagree, none_read, missing))
        for x in bad:
            print("      contradiction:", x)
        return agree, disagree, missing

    check(lost, "removed rows -> must block", True)
    # reach: of every fired gated row in the OFF book, how often can the flag
    # form an opinion at all?
    reach = Counter()
    for r in lost + kept:
        b = bars(r["sym"], r["day"])
        want = (r.get("et") or "") + ":00"
        idx = next((i for i, c in enumerate(b) if c.timestamp == want), None)
        if idx is None:
            reach["no bars"] += 1
            continue
        t = structure15_trend(b[:idx + 1])
        if t is None:
            reach["abstain (None)"] += 1
        elif (t == "bullish") == (r.get("dir") == "call"):
            reach["agrees -> allowed"] += 1
        else:
            reach["disagrees -> blocked"] += 1
    print("   REACH over all %d fired gated rows in the OFF book: %s"
          % (len(lost) + len(kept), dict(reach)))
    keep_sample = kept
    check(keep_sample, "kept rows -> must NOT block", False)

    # ---- 3. how stale is the read at the signal bar --------------------------
    print("\n--- staleness: minutes between the last completed bucket and the signal bar ---")
    lag = Counter()
    for r in (lost + keep_sample):
        b = bars(r["sym"], r["day"])
        want = (r.get("et") or "") + ":00"
        idx = next((i for i, c in enumerate(b) if c.timestamp == want), None)
        if idx is None:
            continue
        n = idx + 1
        lag[n - (n // 15) * 15] += 1
    tot = sum(lag.values())
    print("   bars past the last completed 15-bucket: " +
          ", ".join("%d:%d" % (k, v) for k, v in sorted(lag.items())))
    print("   rows where the read is >=10 minutes stale: %d of %d (%.0f%%)"
          % (sum(v for k, v in lag.items() if k >= 10), tot,
             100.0 * sum(v for k, v in lag.items() if k >= 10) / tot if tot else 0))


if __name__ == "__main__":
    main()
