"""Is the tier inversion real, or is it n?

Two things in the T8 run looked wrong to Austin: S+ grading out BELOW S and A,
and OTHER_POOL beating MAJOR_15. Both could be composition rather than skill --
the tier buckets are tiny (S+ 63, S 39, A 15 against C's 1,313) and the pools
hold different kinds of stock. This asks, for each claim, whether the gap
survives resampling, and how much of it rides on one or two symbols.

Method, all non-parametric because the R distribution is a long right tail with
a hard -1R floor:
  * bootstrap 95% CI on EV per bucket (20k resamples of the bucket's own trades)
  * two-sided permutation test on each contrast (20k shuffles of the labels)
  * per-symbol EV and leave-one-symbol-out, to find concentration
  * minimum detectable difference at this n, so "not significant" can be read
    as "underpowered" where that is what it means
"""
import json, os, sys, random, statistics as st

random.seed(20260811)  # fixed so the numbers are reproducible run to run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "research" \
    else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from universe import MAJOR_15, INDEX_POOL, OTHER_POOL

ROWS = json.load(open(os.path.join(ROOT, "research", "t8_rows.json")))
OUT = os.path.join(ROOT, "research", "t8_significance.md")
B = 20000

fired = [r for r in ROWS if r["status"] == "fired"]
traded = [r for r in ROWS if r["counted"]]


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def boot_ci(xs, b=B, lo=2.5, hi=97.5):
    if len(xs) < 2:
        return (float("nan"), float("nan"))
    n = len(xs)
    means = []
    for _ in range(b):
        means.append(mean([xs[random.randrange(n)] for _ in range(n)]))
    means.sort()
    return means[int(b * lo / 100)], means[int(b * hi / 100)]


def perm_p(a, b_, n=B):
    """Two-sided permutation test on the difference of means."""
    obs = abs(mean(a) - mean(b_))
    pool = a + b_
    na = len(a)
    hits = 0
    for _ in range(n):
        random.shuffle(pool)
        if abs(mean(pool[:na]) - mean(pool[na:])) >= obs:
            hits += 1
    return (hits + 1) / (n + 1)


def wilson(w, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return 100 * (c - m), 100 * (c + m)


def wr(rows):
    dec = [r for r in rows if r["outcome"] in ("win", "loss")]
    w = sum(1 for r in dec if r["outcome"] == "win")
    return (100.0 * w / len(dec) if dec else float("nan")), w, len(dec)


def mdd(a, b_):
    """Roughly the smallest true EV gap detectable at this n (80% power, a=.05)."""
    if len(a) < 2 or len(b_) < 2:
        return float("nan")
    va, vb = st.pvariance(a), st.pvariance(b_)
    return 2.8 * ((va / len(a) + vb / len(b_)) ** 0.5)


R = lambda rows: [r["r"] for r in rows]
L = ["# T8 -- is the tier inversion real, or is it n?\n"]
L.append("Bootstrap 95% CIs (20,000 resamples) and two-sided permutation tests "
         "(20,000 shuffles) on the two results Austin did not expect: S+ below S and A, "
         "and OTHER_POOL above MAJOR_15. Everything is R per trade at $1,000 risk. "
         "Seeded, so these numbers reproduce.\n")

L.append("## Every bucket with its uncertainty\n")
L.append("| bucket | trades | EV | 95% CI | width | win rate | 95% CI |")
L.append("|---|---|---|---|---|---|---|")
BUCKETS = [("S+", [r for r in fired if r["tier"] == "S+"]),
           ("S", [r for r in fired if r["tier"] == "S"]),
           ("A", [r for r in fired if r["tier"] == "A"]),
           ("C", [r for r in fired if r["tier"] == "C"]),
           ("MAJOR_15", [r for r in traded if r["symbol"] in set(MAJOR_15)]),
           ("INDEX_POOL", [r for r in traded if r["symbol"] in set(INDEX_POOL)]),
           ("OTHER_POOL", [r for r in traded if r["symbol"] in set(OTHER_POOL)])]
for name, rows in BUCKETS:
    xs = R(rows)
    lo, hi = boot_ci(xs)
    w, wn, dn = wr(rows)
    wl, wh = wilson(wn, dn)
    L.append(f"| **{name}** | {len(xs)} | {mean(xs):+.3f}R | [{lo:+.3f}, {hi:+.3f}] | "
             f"{hi - lo:.3f}R | {w:.1f}% | [{wl:.1f}%, {wh:.1f}%] |")
L.append("")
L.append("A CI that straddles the other bucket's point estimate means the two are not "
         "separated by this data. Width is the honest measure of how little the small "
         "buckets say.\n")

L.append("## The contrasts Austin asked about\n")
L.append("| contrast | n | n | EV gap | p (permutation) | smallest gap detectable at this n |")
L.append("|---|---|---|---|---|---|")
S_plus = [r for r in fired if r["tier"] == "S+"]
S_ = [r for r in fired if r["tier"] == "S"]
A_ = [r for r in fired if r["tier"] == "A"]
C_ = [r for r in fired if r["tier"] == "C"]
MAJ = [r for r in traded if r["symbol"] in set(MAJOR_15)]
OTH = [r for r in traded if r["symbol"] in set(OTHER_POOL)]
CONTRASTS = [("S+ vs S (the ranking rule itself)", S_plus, S_),
             ("S+ vs A", S_plus, A_),
             ("S+ vs C", S_plus, C_),
             ("S vs C", S_, C_),
             ("A vs C", A_, C_),
             ("all S-family (S+/S/A) vs C", S_plus + S_ + A_, C_),
             ("MAJOR_15 vs OTHER_POOL", MAJ, OTH)]
for name, a, b_ in CONTRASTS:
    ra, rb = R(a), R(b_)
    L.append(f"| {name} | {len(ra)} | {len(rb)} | {mean(ra) - mean(rb):+.3f}R | "
             f"{perm_p(list(ra), list(rb)):.3f} | {mdd(ra, rb):.3f}R |")
L.append("")

L.append("## How much rides on single symbols\n")
L.append("Leave-one-symbol-out: the pool's EV recomputed with that symbol removed. A pool "
         "whose edge is one name is not a pool result.\n")
for pname, pool in (("MAJOR_15", MAJ), ("OTHER_POOL", OTH)):
    base = mean(R(pool))
    deltas = []
    for sym in sorted({r["symbol"] for r in pool}):
        rest = [r for r in pool if r["symbol"] != sym]
        deltas.append((mean(R(rest)) - base, sym, len([r for r in pool if r["symbol"] == sym])))
    deltas.sort()
    L.append(f"**{pname}** (EV {base:+.3f}R) -- biggest movers when dropped:\n")
    L.append("| symbol | trades | pool EV without it | change |")
    L.append("|---|---|---|---|")
    for d, sym, n in (deltas[:3] + deltas[-3:]):
        L.append(f"| {sym} | {n} | {base + d:+.3f}R | {d:+.3f}R |")
    L.append("")

L.append("## Per-symbol EV (traded)\n")
L.append("| symbol | pool | trades | EV | win rate |")
L.append("|---|---|---|---|---|")
POOL_OF = {}
for n_, p_ in (("MAJOR_15", MAJOR_15), ("INDEX_POOL", INDEX_POOL), ("OTHER_POOL", OTHER_POOL)):
    for s_ in p_:
        POOL_OF[s_] = n_
per = []
for sym in sorted({r["symbol"] for r in traded}):
    rows = [r for r in traded if r["symbol"] == sym]
    per.append((mean(R(rows)), sym, len(rows), wr(rows)[0]))
for evv, sym, n, w in sorted(per, reverse=True):
    L.append(f"| {sym} | {POOL_OF.get(sym, '?')} | {n} | {evv:+.3f}R | {w:.1f}% |")
L.append("")

L.append("## Does the S+ rule pick worse trades, or just earlier ones?\n")
L.append("S+ is the earliest 3 S of each day; S is what is left over. Same pool of "
         "candidates, split only by time of day -- so this is a clean read on the ranking "
         "rule with no grade confound.\n")
xs, ys = R(S_plus), R(S_)
lo1, hi1 = boot_ci(xs)
lo2, hi2 = boot_ci(ys)
L.append(f"- S+ (earliest 3/day): n={len(xs)}, EV {mean(xs):+.3f}R, CI [{lo1:+.3f}, {hi1:+.3f}]")
L.append(f"- S (the rest of the day): n={len(ys)}, EV {mean(ys):+.3f}R, CI [{lo2:+.3f}, {hi2:+.3f}]")
L.append(f"- permutation p = {perm_p(list(xs), list(ys)):.3f}, "
         f"smallest gap this n could detect = {mdd(xs, ys):.3f}R\n")

open(OUT, "w").write("\n".join(L))
print("\n".join(L))
print("wrote", OUT)
