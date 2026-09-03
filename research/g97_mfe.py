"""g97 -- how far did price run in our favour BEFORE it could stop us out?

g96 found the average winner is +0.949R against an average loser of -0.753R, and
that only 295 of 5,906 first-of-day trades reach 2R. Austin's read, from the
anatomy cards: "RUNNER PLAN - way too tight, if we know our mean RR is 2.5 we
shouldnt be targeting .41, this one ran."

He may be right, and it may equally be that the setups do not travel. One
measurement separates those and this repo has never made it on the honest book.

TWO EARLIER VERSIONS OF THIS SCRIPT WERE WRONG. Both errors are worth keeping
written down, because both produced confident numbers.

  1. **Ungated denominator.** It reported mean MFE +4.679R and mean MAE +4.301R.
     An MAE above 4R is impossible against a -1.25R floor; the tell was that both
     arms were huge and nearly equal. 254 of the 4,022 traded rows have
     |entry - stop| under $0.10 and the smallest is $0.02. Dividing by those
     manufactures R out of nothing -- CLAUDE.md's size gate exactly. Rows below
     `signal_runner.min_risk_floor(entry)` are now dropped and counted.

  2. **Unordered excursion.** It measured MFE and MAE independently over the whole
     window, so a trade that ran +2R and then reversed after 11:00 counted BOTH.
     Worse, the flat-target counterfactual stopped out any trade whose full-day
     MAE reached 1R even when the target had already been hit hours earlier. That
     is not a backtest, it is two unrelated maxima.

What it measures now is bar-ordered and causal: walk forward from the entry bar
and record which happens FIRST, the target or the stop.

  mfe_alive   the best price offered while the trade was still alive -- the max
              favourable excursion strictly before adverse movement reaches 1R.
              This is the ceiling any target could actually have captured.
  outcome[T]  for each candidate flat target T: +T if T is reached before the
              stop, -1.0 if the stop comes first, else marked to the 11:00 close.

If mfe_alive clusters near 1R, the targets are not the problem and no ladder
saves this. If it clusters at 2R+, the exits are leaving the trade on the table.

    python research/g97_mfe.py
    python research/g97_mfe.py --lane index

Honest book (`bt2y_trades_retest_on.json`), first-of-day, 1R = |entry - stop|,
window ends 11:00. Applies nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g91_lane_slice as g91                      # noqa: E402
import signal_runner as sr                        # noqa: E402
from research import g80_ordertype_grid as G      # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g97_mfe.json")
OUT_MD = os.path.join(HERE, "g97_mfe.md")
WIN_END = "11:00:00"
TARGETS = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)


def load(p):
    b = json.load(open(p, encoding="utf-8"))
    return b["trades"] if isinstance(b, dict) else b


def walk(row, bars):
    """Bar-ordered excursion. None if the row fails the size gate.

    Returns (mfe_alive, stopped, outcomes) where `outcomes` maps each candidate
    target to the R that target would have produced.

    THE WALK STARTS AT i+1, NOT i. The fill is bar i's CLOSE, so bar i's own
    high and low already happened before we were in. Including bar i made every
    entry whose stop is that bar's own extreme stop out instantly at 0.000R --
    which is exactly what g98's first run printed, 46 pairs of zeros.

    WITHIN-BAR ORDERING IS UNKNOWABLE on 1-minute OHLC: if a bar's high reaches
    the target and its low reaches the stop, we cannot tell which came first.
    That ambiguity is resolved PESSIMISTICALLY -- the stop wins the bar -- which
    is the same convention `stop_rule` uses and the only one that cannot flatter
    a wider target.
    """
    entry, stop = row["entry"], row["stop"]
    risk = abs(entry - stop)
    if risk < sr.min_risk_floor(entry):
        return None
    i = row.get("entry_i")
    if i is None or i >= len(bars):
        return None
    long = row["dir"] == "call"

    mfe_alive = 0.0
    stopped = False
    hit = {}
    last_close = entry
    for b in bars[i + 1:]:
        if b.timestamp > WIN_END:
            break
        last_close = b.close
        fav = ((b.high - entry) if long else (entry - b.low)) / risk
        adv = ((entry - b.low) if long else (b.high - entry)) / risk
        if adv >= 1.0:
            # Pessimistic: the stop takes this bar. Any target not already hit
            # on an EARLIER bar is lost.
            stopped = True
            break
        mfe_alive = max(mfe_alive, fav)
        for t in TARGETS:
            if t not in hit and fav >= t:
                hit[t] = True
        # a bar that reaches neither keeps the trade alive
    mark = ((last_close - entry) if long else (entry - last_close)) / risk
    outcomes = {}
    for t in TARGETS:
        if t in hit:
            outcomes[t] = t
        elif stopped:
            outcomes[t] = -1.0
        else:
            outcomes[t] = mark
    return mfe_alive, stopped, outcomes


def band(r):
    for lo in (5, 4, 3, 2.5, 2, 1.5, 1, 0.5):
        if r >= lo:
            return ">=%.1fR" % lo
    return "<0.5R"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", choices=("full", "index"), default="full")
    a = ap.parse_args()

    rows = load(BOOK)
    if a.lane == "index":
        rows = [r for r in rows if r["sym"] in g91.INDEX]
    byday = g86.candidates(rows)
    firsts = [byday[d][0] for d in sorted(byday) if byday[d]]
    print("%s lane: %d first-of-day trades" % (a.lane, len(firsts)))

    mfe, realised, stops = [], [], 0
    per_target = {t: [] for t in TARGETS}
    no_bars = gated = 0
    for k, r in enumerate(firsts, 1):
        bars, *_ = G.day_pack(r["sym"], r["day"])
        if not bars:
            no_bars += 1
            continue
        w = walk(r, bars)
        if w is None:
            gated += 1
            continue
        m, stopped, outc = w
        mfe.append(m)
        realised.append(r["r"])
        stops += 1 if stopped else 0
        for t in TARGETS:
            per_target[t].append(outc[t])
        if k % 150 == 0:
            print("  ... %d/%d" % (k, len(firsts)))

    n = len(mfe)
    if not n:
        raise SystemExit("nothing measurable")
    print("\nmeasured %d  (%d no bars, %d below min_risk_floor -- dropped)"
          % (n, no_bars, gated))
    print("\n  realised R (book)   mean %+.3f   median %+.3f"
          % (statistics.mean(realised), statistics.median(realised)))
    print("  MFE while ALIVE     mean %+.3f   median %+.3f"
          % (statistics.mean(mfe), statistics.median(mfe)))
    print("  stopped before 11:00: %.1f%%" % (100 * stops / n))
    print("\n  LEFT ON THE TABLE: %+.3fR per trade"
          % (statistics.mean(mfe) - statistics.mean(realised)))

    print("\n  how far it ran while alive:")
    c = Counter(band(v) for v in mfe)
    for k2 in (">=5.0R", ">=4.0R", ">=3.0R", ">=2.5R", ">=2.0R", ">=1.5R",
               ">=1.0R", ">=0.5R", "<0.5R"):
        if c.get(k2):
            print("    %-8s %5d  %5.1f%%" % (k2, c[k2], 100 * c[k2] / n))
    for t in (1.0, 2.0, 3.0):
        r = sum(1 for v in mfe if v >= t)
        print("  reached >=%.0fR before any stop: %d/%d = %.1f%%"
              % (t, r, n, 100 * r / n))

    print("\n  flat-target counterfactual (bar-ordered, stop wins a tied bar):")
    best = None
    for t in TARGETS:
        got = per_target[t]
        mu = statistics.mean(got)
        hitpct = 100 * sum(1 for g in got if g >= t) / len(got)
        print("    target %.1fR -> mean %+.4fR  ($%+.0f/trade)  hit %.1f%%"
              % (t, mu, mu * 1000, hitpct))
        if best is None or mu > best[1]:
            best = (t, mu)
    print("    best flat target: %.1fR at %+.4fR/trade ($%+.0f)"
          % (best[0], best[1], best[1] * 1000))
    print("    book's own realised: %+.4fR/trade ($%+.0f)"
          % (statistics.mean(realised), statistics.mean(realised) * 1000))

    out = {"lane": a.lane, "n": n, "no_bars": no_bars, "gated": gated,
           "realised_mean": round(statistics.mean(realised), 4),
           "mfe_alive_mean": round(statistics.mean(mfe), 4),
           "mfe_alive_median": round(statistics.median(mfe), 4),
           "stopped_pct": round(100 * stops / n, 1),
           "left_on_table_r": round(statistics.mean(mfe) - statistics.mean(realised), 4),
           "bands": dict(c),
           "targets": {str(t): round(statistics.mean(per_target[t]), 4)
                       for t in TARGETS},
           "best_flat_target": best[0],
           "best_flat_target_mean_r": round(best[1], 4)}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g97 -- maximum favourable excursion, bar-ordered", "",
          "%s lane, %d first-of-day trades (%d dropped below "
          "`min_risk_floor`), 1R = |entry - stop|, window to 11:00. A bar that "
          "touches both target and stop is given to the stop."
          % (a.lane, n, gated), "",
          "| measure | mean | median |", "|---|---:|---:|",
          "| realised R (book) | %+.3f | %+.3f |"
          % (statistics.mean(realised), statistics.median(realised)),
          "| **MFE while alive** | **%+.3f** | **%+.3f** |"
          % (statistics.mean(mfe), statistics.median(mfe)), "",
          "Reached >=1R before any stop: **%.1f%%**. >=2R: **%.1f%%**. Stopped "
          "before 11:00: %.1f%%."
          % (100 * sum(1 for v in mfe if v >= 1) / n,
             100 * sum(1 for v in mfe if v >= 2) / n, 100 * stops / n), "",
          "| flat target | mean R | $/trade |", "|---|---:|---:|"]
    for t in TARGETS:
        mu = statistics.mean(per_target[t])
        md.append("| %.1fR | %+.4f | $%+.0f |" % (t, mu, mu * 1000))
    md += ["", "Best flat target **%.1fR** at %+.4fR/trade against the book's "
           "own %+.4fR." % (best[0], best[1], statistics.mean(realised))]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
