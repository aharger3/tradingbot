"""C9 - 84% rule strict-spec A/B (SIM cross-check on research/c1_off_charts.json).

Three arms measured on the frozen 12mo baseline population (671 traded / 78 tier,
same charts json as C3/C5/C8 prior art):

  1. current de-martingaled 84%  = baseline, all trades as-is.
  2. strict-spec                 = re-entry fires ONLY when the ORIGINAL stopped-out
                                   entry was graded A+ (or A) AND same thesis/level/
                                   direction. Same-thesis (BNR) + same-level (reclaim
                                   of the original entry price) + same-direction are
                                   ALREADY enforced by the current arming
                                   (RULE84_ARM_BNR_ONLY + entry_price/direction gate);
                                   strict adds the A+/A original-grade requirement.
                                   Faithful on the json: strict's fired re-entries are
                                   a subset of baseline's (arming only ever narrows).
  3. detector OFF                = drop every reentry_84_rule trade.

84% re-entries carry NO S-score, so they never enter the S>=4+[hammer] tier
(B3 sec5, B4 "tier bit-for-bit identical"). Tier is therefore identical across all
three arms; this sim confirms it and reports full-pop deltas.
"""
import json, re
from collections import defaultdict, Counter

CHARTS = "research/c1_off_charts.json"
PRIOR = re.compile(r"prior entry \$([0-9.]+)")


def prior_entry(rec):
    m = PRIOR.search(rec["reason"])
    return float(m.group(1)) if m else None


def s_score(rec):
    m = re.search(r" S(\d+)", rec["reason"])
    return int(m.group(1)) if m else None


def is_hammer(rec):
    c = rec["candles"][rec["entry_i"]]
    body = abs(c["c"] - c["o"]); rng = c["h"] - c["l"]
    if rng == 0:
        return False
    if rec["direction"] == "call":
        return min(c["o"], c["c"]) - c["l"] >= body and c["c"] >= c["l"] + 0.5 * rng
    return c["h"] - max(c["o"], c["c"]) >= body and c["c"] <= c["h"] - 0.5 * rng


def link_strict(re84, bnr):
    """Return the re84 subset whose originating B&R entry graded A+/A."""
    idx = defaultdict(list)
    for r in bnr:
        idx[(r["symbol"], r["day"], r["direction"])].append(r)
    keep, origin = [], Counter()
    for r in re84:
        pe = prior_entry(r)
        cands = idx.get((r["symbol"], r["day"], r["direction"]), [])
        best, bd = None, 1e9
        for o in cands:
            diff = abs(o["entry"] - pe) if pe else 1e9
            if diff < bd:
                bd, best = diff, o
        g = best["grade"] if (best and bd <= 0.02) else "?"
        origin[g] += 1
        if g in ("A+", "A"):
            keep.append(r)
    return keep, origin


def stats(rs):
    n = len(rs)
    w = sum(1 for r in rs if r["outcome"] == "win")
    pnl = sum(r["pnl"] for r in rs)
    return n, (w / n * 100 if n else 0.0), pnl


def tier(recs, min_s=4, max_n=2):
    recs = [r for r in recs if not r["alert_only"]]
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    out = []
    for day, rs in byday.items():
        rs.sort(key=lambda r: r["candles"][r["entry_i"]]["t"])
        taken = pnl_day = 0
        for r in rs:
            if taken >= max_n or pnl_day > 0:
                break
            s = s_score(r)
            if s is None or s < min_s or not is_hammer(r):
                continue
            taken += 1; pnl_day += r["pnl"]; out.append(r)
    return out


def main():
    d = json.load(open(CHARTS))
    traded = [r for r in d if not r["alert_only"]]
    re84 = [r for r in traded if r["setup"] == "reentry_84_rule"]
    bnr = [r for r in traded if r["setup"] == "break_and_retest"]
    non84 = [r for r in traded if r["setup"] != "reentry_84_rule"]

    keep, origin = link_strict(re84, bnr)
    dropped = [r for r in re84 if r not in keep]

    print("# C9 84% strict-spec sim (research/c1_off_charts.json)\n")
    print(f"re84 population: {len(re84)}  origin-grade dist: {dict(origin)}")
    print(f"  ALL re84       : n={len(re84):>2}  W%={stats(re84)[1]:4.1f}  P&L=${stats(re84)[2]:>8,.0f}")
    print(f"  STRICT (A/A+)  : n={len(keep):>2}  W%={stats(keep)[1]:4.1f}  P&L=${stats(keep)[2]:>8,.0f}")
    print(f"  dropped (B/?)  : n={len(dropped):>2}  W%={stats(dropped)[1]:4.1f}  P&L=${stats(dropped)[2]:>8,.0f}\n")

    arms = {
        "current de-martingaled": non84 + re84,
        "strict-spec":            non84 + keep,
        "detector OFF":           non84,
    }
    print("## Full-pop (all A+/A/B trades)")
    print(f"{'arm':24} {'tr':>4} {'win%':>6} {'P&L/yr':>11}  {'d vs OFF':>9}")
    off_pnl = stats(non84)[2]
    for name, pop in arms.items():
        n, wr, pnl = stats(pop)
        print(f"{name:24} {n:>4} {wr:>5.1f}% ${pnl:>10,.0f}  ${pnl-off_pnl:>+8,.0f}")

    print("\n## Tier (S>=4 + hammer, max 2/day, stop-when-green)")
    print(f"{'arm':24} {'tr':>4} {'win%':>6} {'P&L/yr':>11}")
    for name, pop in arms.items():
        tr = tier(pop)
        n, wr, pnl = stats(tr)
        print(f"{name:24} {n:>4} {wr:>5.1f}% ${pnl:>10,.0f}")
    print("\n(84% re-entries carry no S-score => never in tier => tier identical, as predicted.)")

    # detector contribution
    print("\n## Detector contribution (current vs OFF, strict vs OFF)")
    cur = stats(non84 + re84)[2]
    strict = stats(non84 + keep)[2]
    print(f"current 84% adds ${cur-off_pnl:+,.0f}/yr over OFF ({len(re84)} re-entries)")
    print(f"strict  84% adds ${strict-off_pnl:+,.0f}/yr over OFF ({len(keep)} re-entries)")


if __name__ == "__main__":
    main()
