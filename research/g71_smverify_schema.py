"""ADVERSARIAL VERIFY of track `smeasure`. Part 3: is the `traded` arm a
measure of the engine's EYE, or of a portfolio-level halt?

Checks
  1. the trade-record schema and every value of `status` / `traded`
  2. how many symbol-days the book covers at all (is `saw` a null arm?)
  3. among S days that ROUTED but did not TRADE, why -- and specifically how
     many were killed by the R31 daily loss halt, which is not a detection
     decision and applies to the whole portfolio, not the symbol
  4. key-format agreement between build_deck._judgement_key and the book keys

Read-only.
"""
from __future__ import annotations
import os, sys, json
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import research.build_deck as bd
import research.g71_smeasure_pools as pools_mod

BOOK = os.path.join(HERE, "bt2y_trades.json")
d = json.load(open(BOOK, encoding="utf-8"))
meta = d["meta"]; trades = d["trades"]
print("records", len(trades))
print("keys of a record:", sorted(trades[0].keys()))
print("status values:", Counter(t.get("status") for t in trades).most_common())
print("traded values:", Counter(t.get("traded") for t in trades).most_common())
for f in ("halt", "halted", "reason", "skip", "skip_reason", "block",
          "blocked", "veto", "grade", "pa_grade"):
    vals = Counter(t.get(f) for t in trades if f in t)
    if vals:
        print("field %-12s %s" % (f, vals.most_common(8)))

days = {(t["sym"], t["day"]) for t in trades}
print("\ndistinct symbol-days in book:", len(days))
print("universe cells 500 x %d = %d" % (len(meta["symbols"]),
                                        500 * len(meta["symbols"])))
print("=> `saw` is emitted on %.1f%% of ALL cells: a near-constant arm"
      % (100.0 * len(days) / (500 * len(meta["symbols"]))))

# traded-vs-fired: is `traded` ever true when status != fired?
odd = sum(1 for t in trades if t.get("traded") and t.get("status") != "fired")
print("traded==True with status != 'fired':", odd)

# key format agreement
sample = []
for path in bd.mark_sources():
    for r in bd._rows(path):
        k = bd._judgement_key(r)
        if k:
            sample.append(k)
        if len(sample) > 5:
            break
    if len(sample) > 5:
        break
print("\n_judgement_key samples:", sample[:6])
bad = [k for k in sample if k.count("_") != 1]
print("keys whose rsplit('_',1) is ambiguous:", bad[:5], "count", len(bad))

# ---- routed-but-not-traded on his S days ---------------------------------
pools, _, _ = pools_mod.collect()
lo_d, hi_d = meta["first"], meta["last"]
syms = set(meta["symbols"])
S = []
for key, byc in pools.items():
    sym, day = key.rsplit("_", 1)
    if sym in syms and lo_d <= day <= hi_d and any(t[True] for t in byc.values()):
        S.append((sym, day))

by = defaultdict(list)
for t in trades:
    by[(t["sym"], t["day"])].append(t)

rt_not_traded = [c for c in S
                 if any(x.get("status") == "fired" for x in by.get(c, []))
                 and not any(x.get("traded") for x in by.get(c, []))]
print("\nS days that ROUTED but did not TRADE: %d" % len(rt_not_traded))
r = Counter()
for c in rt_not_traded:
    for x in by[c]:
        if x.get("status") == "fired" and not x.get("traded"):
            for f in ("skip_reason", "reason", "why", "halt", "note"):
                if x.get(f):
                    r[f + "=" + str(x[f])[:40]] += 1
print("  reasons carried on the record:", r.most_common(10) or "NONE RECORDED")

# how much of the book's non-trading is the daily loss halt
print("\nmeta.loss_halt=%s  meta.halted=%s of %s traded"
      % (meta.get("loss_halt"), meta.get("halted"), meta.get("traded")))
print("  the halt removes %s would-be trades; that is %.0f%% of the "
      "%s that would otherwise be in the book"
      % (meta.get("halted"), 100.0 * meta["halted"] / (meta["traded"] + meta["halted"]),
         meta["traded"] + meta["halted"]))
