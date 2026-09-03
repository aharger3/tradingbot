"""G7.1 / losshaltverify — adversarial re-run of the conditional-edge tables.

Question under test (prior agent, track `losshalt`):
  "The only day governor is the consecutive-loss streak, which the
   conditional-edge table shows is the WEAKER of the two variables."

The two variables are (a) closed-loss streak at entry, (b) realised day R at
entry. This script rebuilds both conditionals from scratch on the ungoverned
candidate pool of `research/bt2y_trades.json` and asks which one actually
discriminates. Causal only: a candidate at entry moment `at` sees only trades
that had already CLOSED at or before `at` (same exit-clock as loss_halt.py:74-83).

No engine file is touched. Diagnosis only.
"""
from __future__ import annotations

import json
import math
import random
import statistics
from collections import defaultdict

BOOK = "research/bt2y_trades.json"
random.seed(7)


def load_pool():
    d = json.load(open(BOOK))
    t = d["trades"]
    # The book on disk already has R31 applied (857 rows flipped to "halted").
    # The ungoverned pool is everything that WOULD have traded.
    pool = [r for r in t
            if (r.get("status") == "fired" and r.get("traded"))
            or r.get("status") == "halted"]
    return d["meta"], pool


def entry_key(x):
    return (x.get("entry_i", 0), x.get("et", ""), x.get("sym", ""))


def exit_key(x):
    return (x.get("entry_i", 0) + x.get("bars", 0), x.get("et", ""), x.get("sym", ""))


def annotate(pool):
    """Attach, per trade, the streak and realised day R visible at its entry."""
    by_day = defaultdict(list)
    for r in pool:
        by_day[r["day"]].append(r)
    out = []
    for day, rows in by_day.items():
        rows = sorted(rows, key=entry_key)
        pending, streak, realised = [], 0, 0.0
        for row in rows:
            at = entry_key(row)
            while pending and pending[0][0] <= at:
                _x, lost, rr = pending.pop(0)
                streak = streak + 1 if lost else 0
                realised += rr
            out.append((streak, realised, float(row.get("r", 0.0)),
                        row.get("out"), day))
            pending.append((exit_key(row), row.get("out") == "loss",
                            float(row.get("r", 0.0))))
            pending.sort(key=lambda p: p[0])
    return out


def stats(rs):
    n = len(rs)
    if n == 0:
        return 0, 0.0, 0.0, 0.0
    m = statistics.fmean(rs)
    se = statistics.stdev(rs) / math.sqrt(n) if n > 1 else 0.0
    return n, m, se, 0.0


def table(rows, keyfn, order):
    buckets = defaultdict(list)
    for streak, realised, r, out, day in rows:
        buckets[keyfn(streak, realised)].append((r, out))
    print("%-14s %6s %10s %8s %7s" % ("bucket", "n", "mean R", "SE", "win%"))
    means = []
    for k in order:
        v = buckets.get(k, [])
        rs = [x[0] for x in v]
        n, m, se, _ = stats(rs)
        w = 100.0 * sum(1 for x in v if x[1] == "win") / n if n else 0.0
        print("%-14s %6d %10.4f %8.4f %7.1f" % (k, n, m, se, w))
        if n:
            means.append((k, n, m, se))
    return means


def streak_bucket(s, _r):
    return "0" if s == 0 else ("1" if s == 1 else ("2" if s == 2 else
                               ("3" if s == 3 else "4+")))


def dayr_bucket(_s, r):
    if r > 0:
        return "green"
    if r <= -3:
        return "<=-3R"
    if r <= -2:
        return "-3..-2R"
    if r <= -1:
        return "-2..-1R"
    return "-1..0R"


def spread_test(rows, keyfn, lo, hi, label):
    """Two-sample difference between the extreme buckets, with its own SE."""
    a = [r for s, rr, r, o, d in rows if keyfn(s, rr) == lo]
    b = [r for s, rr, r, o, d in rows if keyfn(s, rr) == hi]
    na, ma, sa, _ = stats(a)
    nb, mb, sb, _ = stats(b)
    diff = ma - mb
    se = math.sqrt(sa * sa + sb * sb)
    print("%-40s %+.4fR  SE %.4f  = %.2f SE  (n %d vs %d)"
          % (label, diff, se, abs(diff) / se if se else 0.0, na, nb))
    return abs(diff) / se if se else 0.0


def monotone(means):
    """Fraction of adjacent pairs that move the right way (edge decays)."""
    ok = sum(1 for i in range(len(means) - 1) if means[i][2] >= means[i + 1][2])
    return ok, len(means) - 1


def variance_explained(rows, keyfn):
    """Between-bucket variance of mean R, weighted by n / total variance.
    A crude eta^2: how much of trade-level R variance the variable explains."""
    allr = [r for s, rr, r, o, d in rows]
    gm = statticmean = statistics.fmean(allr)
    tot = sum((r - gm) ** 2 for r in allr)
    buckets = defaultdict(list)
    for s, rr, r, o, d in rows:
        buckets[keyfn(s, rr)].append(r)
    between = sum(len(v) * (statistics.fmean(v) - gm) ** 2 for v in buckets.values())
    return between / tot if tot else 0.0


def perm_eta(rows, keyfn, iters=2000):
    """Permutation null for eta^2: shuffle the bucket labels."""
    obs = variance_explained(rows, keyfn)
    labels = [keyfn(s, rr) for s, rr, r, o, d in rows]
    rs = [r for s, rr, r, o, d in rows]
    gm = statistics.fmean(rs)
    tot = sum((r - gm) ** 2 for r in rs)
    hits = 0
    for _ in range(iters):
        random.shuffle(labels)
        b = defaultdict(list)
        for lab, r in zip(labels, rs):
            b[lab].append(r)
        e = sum(len(v) * (statistics.fmean(v) - gm) ** 2 for v in b.values()) / tot
        if e >= obs:
            hits += 1
    return obs, (hits + 1) / (iters + 1)


def main():
    meta, pool = load_pool()
    print("book %s  sessions=%s traded=%s halted=%s" %
          (meta["last"], meta["sessions"], meta["traded"], meta["halted"]))
    print("ungoverned candidate pool = %d trades, total R = %.1f"
          % (len(pool), sum(float(r.get("r", 0.0)) for r in pool)))
    rows = annotate(pool)
    assert len(rows) == len(pool)

    print("\n--- A. streak at entry ---")
    ms = table(rows, streak_bucket, ["0", "1", "2", "3", "4+"])
    print("monotone adjacent pairs: %d/%d" % monotone(ms))
    z_streak = spread_test(rows, streak_bucket, "0", "2", "streak 0 vs 2:")
    spread_test(rows, streak_bucket, "0", "3", "streak 0 vs 3:")

    print("\n--- B. realised day R at entry ---")
    md = table(rows, dayr_bucket, ["<=-3R", "-3..-2R", "-2..-1R", "-1..0R", "green"])
    # order the day-R table worst-hole -> best so "monotone" means the same thing
    print("monotone adjacent pairs (deep hole -> green, edge should RISE): %d/%d"
          % (sum(1 for i in range(len(md) - 1) if md[i][2] <= md[i + 1][2]), len(md) - 1))
    z_dayr = spread_test(rows, dayr_bucket, "green", "<=-3R", "day R green vs <=-3R:")
    spread_test(rows, dayr_bucket, "-1..0R", "<=-3R", "day R -1..0 vs <=-3R:")

    print("\n--- C. which variable discriminates? (eta^2 + permutation null) ---")
    for name, fn in (("streak", streak_bucket), ("day R", dayr_bucket)):
        e, p = perm_eta(rows, fn)
        print("%-8s eta^2 = %.5f   permutation p = %.4f" % (name, e, p))

    print("\n--- D. the -2R floor bucket, which is what the floor actually gates ---")
    below = [r for s, rr, r, o, d in rows if rr <= -2.0]
    at2 = [r for s, rr, r, o, d in rows if s >= 2]
    n1, m1, s1, _ = stats(below)
    n2, m2, s2, _ = stats(at2)
    print("trades entered with day R <= -2R : n=%d mean %+.4fR SE %.4f (%.2f SE from 0)"
          % (n1, m1, s1, abs(m1) / s1 if s1 else 0))
    print("trades entered with streak >= 2  : n=%d mean %+.4fR SE %.4f (%.2f SE from 0)"
          % (n2, m2, s2, abs(m2) / s2 if s2 else 0))


if __name__ == "__main__":
    main()
