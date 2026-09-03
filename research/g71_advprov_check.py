"""ADVERSARIAL VERIFY of research/g71_smeasure.md's provenance claim.

Recomputes the 196/54/13/0 split day-by-day, tests whether the buckets
partition the 255, attributes each bucket to its source corpora, and asks the
empirical question the label never asks: does the engine actually score
DIFFERENTLY on the days it is claimed to have been fitted to?  Read-only.
"""
import json, os, sys, math
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import research.g71_smeasure_test as T   # noqa: E402

spool, per_source, pools = T.s_pool()
neg = T.neg_pool(pools)
by_day, meta = T.book_index()
SYMS = set(meta["symbols"])
LO, HI = meta["first"], meta["last"]


def elig_key(key):
    s, d = T.split(key)
    return (s in SYMS) and (LO <= d <= HI)


elig = [k for k in sorted(spool) if elig_key(k)]
elig_neg = [k for k in sorted(neg) if elig_key(k)]
print("BOOK", meta["generated"], meta["signals"], "signals", meta["traded"], "traded")
print("eligible S", len(elig), " eligible refused", len(elig_neg))

uses = {k: set(spool[k]["uses"]) for k in elig}
cnt = Counter()
for k in elig:
    for u in uses[k]:
        cnt[u] += 1
print("bucket counts (overlapping):", dict(cnt), "sum", sum(cnt.values()))
excl = Counter(tuple(sorted(uses[k])) for k in elig)
print("exclusive combinations:")
for combo, n in excl.most_common():
    print("   ", combo, n)

for tag in ("fit", "selection"):
    src = Counter()
    for k in elig:
        if tag in uses[k]:
            for c in spool[k]["S_in"]:
                if T.PROVENANCE.get(c, ("", ""))[1] == tag:
                    src[c] += 1
    print(tag, "day sources:", dict(src))


def rate(keys, arm):
    hit = sum(1 for k in keys if by_day.get(T.split(k), {}).get(arm, 0))
    n = len(keys)
    return hit, n, (100.0 * hit / n if n else 0.0)


print("\ntraded-arm recall by provenance bucket")
for tag in ("in_sample", "selection", "fit"):
    ks = [k for k in elig if tag in uses[k]]
    h, n, p = rate(ks, "traded")
    print("  %-22s %3d/%3d = %5.1f%%" % (tag, h, n, p))
pure_in = [k for k in elig if uses[k] == {"in_sample"}]
never_in = [k for k in elig if "in_sample" not in uses[k]]
for lbl, ks in (("in_sample ONLY", pure_in), ("never in_sample", never_in)):
    h, n, p = rate(ks, "traded")
    print("  %-22s %3d/%3d = %5.1f%%" % (lbl, h, n, p))
h, n, p = rate(elig_neg, "traded")
print("  %-22s %3d/%3d = %5.1f%%" % ("refused days", h, n, p))
a = rate(pure_in, "traded")
b = rate(never_in, "traded")
print("  in_sample-only vs never-in_sample:", T.two_prop_z(a[0], a[1], b[0], b[1]))
for arm in ("sigs", "routed"):
    x, y = rate(pure_in, arm), rate(never_in, arm)
    print("  %-7s in_only %5.1f%%  never %5.1f%%  %s"
          % (arm, x[2], y[2], T.two_prop_z(x[0], x[1], y[0], y[1])))

cand = defaultdict(list)
for k in elig:
    if uses[k] == {"in_sample"}:
        for c in spool[k]["S_in"]:
            cand[c].append(k)
print("\ncorpora contributing in_sample-ONLY days (clean candidates):")
for c, ks in sorted(cand.items(), key=lambda x: -len(x[1])):
    print("   %-46s %3d" % (c, len(ks)))
