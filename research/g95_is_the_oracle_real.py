"""g95 -- is the oracle real edge, or is it max-of-N arithmetic?

CLAUDE.md rests the whole project on one row:

    "The oracle row is **not a plan** -- it is proof the setups are there, every
     month, in the book we already have."

That claim has never been tested, and it is load-bearing. If picking the best of
~18 candidates a day is worth $2,948/day only because you are taking the maximum
of 18 draws from a fat-tailed distribution, then the "setups are there" reading
is false, no classifier can approach it, and selection is not the lane.

Three questions, in order of how much they change the plan:

  Q1  ORACLE vs NULL. Compare the real per-day max against the max of the same
      number of R-multiples drawn at random from the book's own pooled outcome
      distribution. If the two are close, the oracle is arithmetic.

  Q2  DOES ANY RECORDED FEATURE SELECT? For every feature the book already
      stamps -- grade, sgrade, setup, level, tags, downgrades, tier, hour --
      take the day's first candidate carrying it and price that policy. If none
      beats first-of-day, the engine cannot see what separates a winner from a
      loser, and more gates will not help.

  Q3  HOW ACCURATE MUST A CLASSIFIER BE? A picker that finds the day's best with
      probability p and otherwise picks at random earns
      p * oracle + (1 - p) * coinflip. Solve for the p that clears his $397/day
      bar. That number is the actual specification for the thing we are building,
      and nobody has ever written it down.

    python research/g95_is_the_oracle_real.py
    python research/g95_is_the_oracle_real.py --lane index --trials 400

Honest book, one trade a day, 1R = $1,000. Applies nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g91_lane_slice as g91                      # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
BAR = 397.0
OUT_JSON = os.path.join(HERE, "g95_is_the_oracle_real.json")
OUT_MD = os.path.join(HERE, "g95_is_the_oracle_real.md")


def load(p):
    b = json.load(open(p, encoding="utf-8"))
    return b["trades"] if isinstance(b, dict) else b


def per_day(byday, pick):
    d = {}
    for day, v in byday.items():
        if v:
            r = pick(v)
            if r is not None:
                d[day] = r["pnl"]
    return d


def money(daily, n_days):
    return round(sum(daily.values()) / n_days, 2) if n_days else 0.0


def features(r):
    """Every label the book already stamps, as (name, value) pairs."""
    out = [("grade", r.get("grade")), ("sgrade", r.get("sgrade")),
           ("setup", r.get("setup")), ("setup_label", r.get("setup_label")),
           ("level", r.get("level_name")), ("tier", r.get("tier")),
           ("pool", r.get("pool")), ("side", r.get("side")),
           ("confluence", r.get("confluence")), ("stopb", r.get("stopb")),
           ("bias", r.get("bias")), ("aligned", r.get("aligned")),
           ("vol_regime", r.get("vol_regime")), ("rangeb", r.get("rangeb")),
           ("gapb", r.get("gapb")), ("dow", r.get("dow")),
           ("hour", (r.get("et") or "")[:2]),
           ("tripped", str(r.get("tripped"))),
           ("seq", "seq%s" % r.get("seq"))]
    for t in (r.get("tags") or ()):
        out.append(("tag", t))
    for d in (r.get("downgrades") or ()):
        out.append(("downgrade", d))
    return [(k, v) for k, v in out if v not in (None, "", "None")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", choices=("full", "index"), default="full")
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--min-days", type=int, default=60,
                    help="a feature policy must cover at least this many days")
    a = ap.parse_args()

    rows = load(BOOK)
    if a.lane == "index":
        rows = [r for r in rows if r["sym"] in g91.INDEX]
    byday = g86.candidates(rows)
    byday = {d: v for d, v in byday.items() if v}
    n_days = len(byday)
    counts = [len(v) for v in byday.values()]
    print("%s lane: %d days, %d candidates, %.1f/day (median %d, max %d)"
          % (a.lane, n_days, sum(counts), sum(counts) / n_days,
             statistics.median(counts), max(counts)))

    first = per_day(byday, lambda v: v[0])
    best = per_day(byday, lambda v: max(v, key=lambda r: r["pnl"]))
    worst = per_day(byday, lambda v: min(v, key=lambda r: r["pnl"]))
    pool = [r["pnl"] for v in byday.values() for r in v]
    coin = round(statistics.mean(pool), 2)

    f_pd, b_pd, w_pd = money(first, n_days), money(best, n_days), money(worst, n_days)
    print("\n  first of day   $%7.0f/day" % f_pd)
    print("  coin flip      $%7.0f/day" % coin)
    print("  ORACLE (best)  $%7.0f/day" % b_pd)
    print("  anti-oracle    $%7.0f/day" % w_pd)

    # ---- Q1: oracle vs a null that knows nothing -------------------------
    rng = random.Random(20260902)
    null_best, null_worst = [], []
    for _ in range(a.trials):
        tot_b = tot_w = 0.0
        for k in counts:
            draw = [pool[rng.randrange(len(pool))] for _ in range(k)]
            tot_b += max(draw)
            tot_w += min(draw)
        null_best.append(tot_b / n_days)
        null_worst.append(tot_w / n_days)
    nb, nw = statistics.mean(null_best), statistics.mean(null_worst)
    lo, hi = min(null_best), max(null_best)
    print("\n=== Q1: is the oracle real, or max-of-N? ===")
    print("  real oracle           $%7.0f/day" % b_pd)
    print("  NULL oracle (%d sims) $%7.0f/day   [range $%.0f..$%.0f]"
          % (a.trials, nb, lo, hi))
    print("  real anti-oracle      $%7.0f/day   NULL $%7.0f/day" % (w_pd, nw))
    share = (b_pd / nb * 100) if nb else 0
    if b_pd <= hi:
        q1 = ("THE ORACLE IS ARITHMETIC. Taking the max of the same number of "
              "random draws from the book's own outcome pool reaches the same "
              "place (real is %.0f%% of null, inside the null's own range). It "
              "is NOT proof the setups are there -- it is proof that 18 draws "
              "have a big maximum. No classifier can chase it." % share)
    elif b_pd > nb * 1.15:
        q1 = ("THE ORACLE CARRIES REAL STRUCTURE. The real per-day max beats the "
              "null by %.0f%%, so good candidates cluster on days and are not "
              "spread at random. Selection has something to find." % (share - 100))
    else:
        q1 = ("MOSTLY ARITHMETIC. Real beats null by only %.0f%%; most of the "
              "oracle is max-of-N, and the residual is thin." % (share - 100))
    print("\n  %s" % q1)

    # ---- Q2: does any recorded feature select? ---------------------------
    print("\n=== Q2: can any label the book already stamps beat first-of-day? ===")
    bucket = defaultdict(dict)     # (k,v) -> {day: pnl of first carrying it}
    for day, v in byday.items():
        for r in v:
            for kv in features(r):
                bucket[kv].setdefault(day, r["pnl"])
    scored = []
    for kv, daily in bucket.items():
        if len(daily) < a.min_days:
            continue
        # Priced over the days it covers, and over ALL days (silent days pay $0)
        scored.append((money(daily, len(daily)), money(daily, n_days),
                       len(daily), kv))
    scored.sort(reverse=True)
    print("  %-28s %10s %10s %7s" % ("feature = value", "$/covered", "$/all-day", "days"))
    for cov, alld, nd, (k, v) in scored[:12]:
        print("  %-28s %10.0f %10.0f %7d" % ("%s = %s" % (k, v), cov, alld, nd))
    print("  ... %d features scored; first-of-day is $%.0f/day for reference"
          % (len(scored), f_pd))
    beats = [s for s in scored if s[1] > f_pd]
    print("  features beating first-of-day on an all-day basis: %d" % len(beats))

    # ---- Q3: the classifier's actual spec --------------------------------
    print("\n=== Q3: how good must the picker be? ===")
    print("  a picker that finds the day's best with probability p and otherwise")
    print("  picks at random earns  p*oracle + (1-p)*coinflip")
    chance = round(sum(1.0 / k for k in counts) / n_days * 100, 1)
    need = (BAR - coin) / (b_pd - coin) if b_pd != coin else None
    print("  chance rate (1/N averaged)     %.1f%%" % chance)
    if need is not None:
        print("  p needed for $%.0f/day          %.1f%%" % (BAR, need * 100))
        print("  ...that is %.1fx better than chance" % (need * 100 / chance))
    for p in (0.10, 0.20, 0.30, 0.50):
        print("     p=%3.0f%%  ->  $%6.0f/day" % (p * 100, p * b_pd + (1 - p) * coin))

    out = {"lane": a.lane, "days": n_days, "cands_per_day": sum(counts) / n_days,
           "first_per_day": f_pd, "coinflip_per_day": coin, "oracle_per_day": b_pd,
           "anti_oracle_per_day": w_pd, "null_oracle_per_day": round(nb, 2),
           "null_range": [round(lo, 2), round(hi, 2)],
           "oracle_vs_null_pct": round(share, 1), "q1": q1,
           "chance_pct": chance,
           "p_needed_for_bar": round(need * 100, 1) if need else None,
           "features_beating_first": len(beats),
           "top_features": [{"feature": "%s=%s" % kv, "per_covered_day": cov,
                             "per_all_day": alld, "days": nd}
                            for cov, alld, nd, kv in scored[:12]]}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g95 -- is the oracle real edge, or max-of-N?", "",
          "Book `research/bt2y_trades_retest_on.json` (RETEST_REQUIRED on), "
          "%s lane, one trade a day, 1R = $1,000, honest close fill." % a.lane, "",
          "| policy | $/day |", "|---|---:|",
          "| first of day | $%.0f |" % f_pd,
          "| coin flip among the day's candidates | $%.0f |" % coin,
          "| **oracle** (best of day, hindsight) | **$%.0f** |" % b_pd,
          "| null oracle (max of the same N random draws) | $%.0f |" % nb,
          "| anti-oracle (worst of day) | $%.0f |" % w_pd, "",
          "## Q1", "", q1, "",
          "## Q2 -- features that beat first-of-day", "",
          "%d of %d stamped feature-values beat first-of-day on an all-day basis."
          % (len(beats), len(scored)), "",
          "| feature | $/covered day | $/all day | days |", "|---|---:|---:|---:|"]
    for cov, alld, nd, (k, v) in scored[:12]:
        md.append("| %s = %s | $%.0f | $%.0f | %d |" % (k, v, cov, alld, nd))
    md += ["", "## Q3 -- the classifier's specification", "",
           "Chance rate is **%.1f%%**. To clear the $%.0f/day bar a picker must "
           "find the day's best **%.1f%%** of the time -- %.1fx better than "
           "chance." % (chance, BAR, (need or 0) * 100,
                        (need or 0) * 100 / chance if chance else 0), ""]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
