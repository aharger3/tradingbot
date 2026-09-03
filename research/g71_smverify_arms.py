"""ADVERSARIAL VERIFY of track `smeasure`. Part 4: are the ARMS what they say
they are?

Two defects in research/g71_smeasure_test.py:200-213 (`book_index`):

  (a) `routed` is defined as `status == "fired"`.  But loss_halt.py:110
      REWRITES `status` from "fired" to "halted" for the 857 signals the R31
      daily loss halt blocked -- AFTER they cleared `_route`
      (backtest_2y.py:213 runs `apply_to_book` on the finished rows).  So the
      arm the report calls "cleared `_route`" silently drops every signal the
      router passed and a portfolio-level risk rule then killed.

  (b) `saw` is defined as "any record exists for that symbol-day".  91.6% of
      the 76,019 records carry legacy grade X, and CLAUDE.md is explicit:
      "X is not a grade, it means the engine should not have fired."  A `saw`
      arm built on X records measures "the scanner produced a row", not "the
      engine saw the setup".

This recomputes every arm with those two corrected and reports the effect on
the headline discrimination number.  Read-only.
"""
from __future__ import annotations
import os, sys, json, math
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import research.build_deck as bd
import research.g71_smeasure_pools as pools_mod
from research.g71_smverify_ladder import collect_ladder, wilson, zt

BOOK = os.path.join(HERE, "bt2y_trades.json")
d = json.load(open(BOOK, encoding="utf-8"))
meta = d["meta"]; trades = d["trades"]
lo_d, hi_d = meta["first"], meta["last"]; syms = set(meta["symbols"])

by = defaultdict(list)
for t in trades:
    by[(t["sym"], t["day"])].append(t)


def key2(k):
    s, dd = k.rsplit("_", 1)
    return (s, dd)


ARMS = {
    "saw_any_record        (smeasure)": lambda rs: len(rs) > 0,
    "saw_non_X             (corrected)": lambda rs: any(r["grade"] != "X" for r in rs),
    "routed_fired_only     (smeasure)": lambda rs: any(r["status"] == "fired" for r in rs),
    "routed_fired_or_halted(corrected)": lambda rs: any(
        r["status"] in ("fired", "halted") for r in rs),
    "traded                (both)": lambda rs: any(r["traded"] for r in rs),
}

# pools
pools, _, _ = pools_mod.collect()
S_sm, N_sm = [], []
for k, byc in pools.items():
    s, dd = key2(k)
    if s not in syms or not (lo_d <= dd <= hi_d):
        continue
    (S_sm if any(t[True] for t in byc.values()) else
     N_sm if any(t[False] for t in byc.values()) else []).append(k)

lad = collect_ladder()
elig = {k: v for k, v in lad.items()
        if key2(k)[0] in syms and lo_d <= key2(k)[1] <= hi_d}
S_l = [k for k, v in elig.items() if v["best"] == "S"]
REF = [k for k, v in elig.items() if v["best"] == "REFUSED"]

print("BOOK %d signals / %d traded / %d halted; grade mix: %s"
      % (meta["signals"], meta["traded"], meta["halted"],
         Counter(t["grade"] for t in trades).most_common()))

for label, fn in ARMS.items():
    hs = lambda ks: sum(1 for k in ks if fn(by.get(key2(k), [])))
    k1, n1 = hs(S_sm), len(S_sm)
    k2, n2 = hs(N_sm), len(N_sm)
    k3, n3 = hs(REF), len(REF)
    p1 = wilson(k1, n1); p2 = wilson(k2, n2); p3 = wilson(k3, n3)
    dd1, z1, pv1 = zt(k1, n1, k2, n2)
    dd2, z2, pv2 = zt(k1, n1, k3, n3)
    print("\n%s" % label)
    print("  S           %4d/%4d = %5.1f%% [%.1f, %.1f]"
          % (k1, n1, p1[0] * 100, p1[1] * 100, p1[2] * 100))
    print("  not-S (sm)  %4d/%4d = %5.1f%%   -> diff %+.1f  z=%.3f  p=%.4f"
          % (k2, n2, p2[0] * 100, dd1, z1, pv1))
    print("  REFUSED     %4d/%4d = %5.1f%%   -> diff %+.1f  z=%.3f  p=%.4f"
          % (k3, n3, p3[0] * 100, dd2, z2, pv2))

# the claimed 68.7-point attribution
saw = sum(1 for k in S_sm if by.get(key2(k)))
sawx = sum(1 for k in S_sm if any(r["grade"] != "X" for r in by.get(key2(k), [])))
rf = sum(1 for k in S_sm if any(r["status"] == "fired" for r in by.get(key2(k), [])))
rh = sum(1 for k in S_sm if any(r["status"] in ("fired", "halted")
                                for r in by.get(key2(k), [])))
n = len(S_sm)
print("\nATTRIBUTION of the claimed '68.7 points destroyed by _route'")
print("  saw  (any record, 91.6%% of them X)     %5.1f%%" % (100.0 * saw / n))
print("  saw  (non-X records only)              %5.1f%%" % (100.0 * sawx / n))
print("  routed incl. halted                    %5.1f%%" % (100.0 * rh / n))
print("  routed excl. halted (smeasure)         %5.1f%%" % (100.0 * rf / n))
print("  -> _grade_pa X-skip accounts for %.1f pts of the %.1f-pt fall;"
      % (100.0 * (saw - sawx) / n, 100.0 * (saw - rf) / n))
print("     the R31 loss halt for %.1f pts; _route's own gates for %.1f pts."
      % (100.0 * (rh - rf) / n, 100.0 * (sawx - rh) / n))

# base rate: what does an UNGRADED symbol-day do?
allcells = 500 * len(syms)
tr_days = sum(1 for c, rs in by.items() if any(r["traded"] for r in rs))
print("\nBASE RATE  traded on %d of %d book symbol-days = %.1f%% "
      "(%.1f%% of all %d universe cells)"
      % (tr_days, len(by), 100.0 * tr_days / len(by),
         100.0 * tr_days / allcells, allcells))
print("  his S days trade at 22.7%%, his refused at 28.8%%, an UNSELECTED "
      "book day at %.1f%%." % (100.0 * tr_days / len(by)))
