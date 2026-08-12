"""How long until the tier question can actually be answered?

The T8 contrasts all came back non-significant, but "non-significant" splits two
ways: the effect isn't there, or the sample can't see it. This computes the
second -- how many trades each bucket needs to resolve a gap the size of the one
observed, and, at the rate that bucket actually fires, how many trading days and
calendar years that is.

n per group for 80% power at a=.05, two-sided: n = 2*var*(2.8/gap)^2
"""
import json, os, sys, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "research" \
    else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from universe import MAJOR_15, OTHER_POOL

ROWS = json.load(open(os.path.join(ROOT, "research", "t8_rows.json")))
OUT = os.path.join(ROOT, "research", "t8_power.md")
DAYS = len({r["day"] for r in ROWS})

fired = [r for r in ROWS if r["status"] == "fired"]
traded = [r for r in ROWS if r["counted"]]
R = lambda rows: [r["r"] for r in rows]


def need(a, b, gap):
    v = (st.pvariance(a) + st.pvariance(b)) / 2
    return int(2 * v * (2.8 / abs(gap)) ** 2) + 1


BUCK = {
    "S+": [r for r in fired if r["tier"] == "S+"],
    "S": [r for r in fired if r["tier"] == "S"],
    "A": [r for r in fired if r["tier"] == "A"],
    "C": [r for r in fired if r["tier"] == "C"],
    "MAJOR_15": [r for r in traded if r["symbol"] in set(MAJOR_15)],
    "OTHER_POOL": [r for r in traded if r["symbol"] in set(OTHER_POOL)],
}
RATE = {k: len(v) / DAYS for k, v in BUCK.items()}

L = ["# T8 -- what it would take to answer the tier question\n"]
L.append(f"Over {DAYS} trading days. n is per group for 80% power at a=.05 against the "
         "gap actually observed; years assumes the bucket keeps firing at its current "
         "rate and 252 trading days a year.\n")
L.append("| contrast | observed gap | n needed per side | have | slower side fires | years to reach it |")
L.append("|---|---|---|---|---|---|")
for name, x, y in [("S+ vs S", "S+", "S"), ("S+ vs A", "S+", "A"), ("S vs C", "S", "C"),
                   ("A vs C", "A", "C"), ("MAJOR_15 vs OTHER_POOL", "MAJOR_15", "OTHER_POOL")]:
    a, b = R(BUCK[x]), R(BUCK[y])
    gap = sum(a) / len(a) - sum(b) / len(b)
    n = need(a, b, gap)
    slow = x if RATE[x] < RATE[y] else y
    yrs = n / RATE[slow] / 252
    L.append(f"| {name} | {gap:+.3f}R | {n:,} | {len(a)} / {len(b)} | "
             f"{slow} at {RATE[slow]:.2f}/day | **{yrs:,.0f}** |")
L.append("")
L.append("Reading it: the S-tier contrasts are not close to answerable on P&L. The "
         "variance of a ladder-B R distribution is large enough that separating two "
         "buckets whose true gap is a few tenths of an R takes thousands of trades per "
         "side, and the S tiers fire well under one a day between them. **Tier quality "
         "has to be judged on agreement with Austin's own grades (T9's eye-match), not "
         "on backtest P&L** -- P&L will not resolve it this decade.\n")
L.append("The pool contrast is the one that is merely slow rather than hopeless: both "
         "pools fire often, so it is a matter of more history rather than a different "
         "kind of measurement.\n")

open(OUT, "w").write("\n".join(L))
print("\n".join(L))
print("wrote", OUT)
