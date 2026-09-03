"""Decompose the six_target paired loss, joining book->probe on the key the
book actually rounds to (2dp entry/stop) and refusing ambiguous keys."""
from __future__ import annotations
import json, math, statistics as st
from collections import defaultdict, Counter

b = [t for t in json.load(open("research/_v/v_base2.json", encoding="utf-8"))["trades"] if t["traded"]]
a = [t for t in json.load(open("research/_v/v_six.json", encoding="utf-8"))["trades"] if t["traded"]]
pb = json.load(open("research/_v/v_base2_probe.json", encoding="utf-8"))

def pk(r): return (r["sym"], r["day"], r["et"], r["dir"], round(r["entry"], 2), round(r["stop"], 2))
def bk(t): return (t["sym"], t["day"], t["et"], t["dir"], round(t["entry"], 2), round(t["stop"], 2))

idx = defaultdict(list)
for r in pb: idx[pk(r)].append(r)
def key(t): return (t["sym"], t["day"], t["et"], t["setup"], t["dir"], t["entry"], t["stop"])
bm = {key(t): t for t in b}; am = {key(t): t for t in a}
shared = sorted(set(bm) & set(am))
print("base n=%d arm n=%d shared=%d" % (len(b), len(a), len(shared)))

g = defaultdict(list)
for k in shared:
    rows = idx.get(bk(bm[k]), [])
    d = am[k]["r"] - bm[k]["r"]
    if not rows:
        g["NO PROBE ROW"].append(d); continue
    flags = {r["six_is_none"] for r in rows}
    sames = {(not r["six_is_none"]) and abs(r["six"] - r["shipped"]) < 1e-9 for r in rows}
    if len(flags) > 1 or len(sames) > 1:
        g["AMBIGUOUS"].append(d); continue
    if flags == {True}: g["B. fallback: no six beyond scale -> t.target"].append(d)
    elif sames == {True}: g["C. six == shipped (inert)"].append(d)
    else: g["A. six really supplied the target"].append(d)

tot = sum(len(v) for v in g.values())
for name in sorted(g):
    d = g[name]; m = st.fmean(d); se = st.pstdev(d) / math.sqrt(len(d))
    print("%-42s n=%-5d moved=%-4d dR=%+.4f +/-%.4f  share of total dR=%+.4f"
          % (name, len(d), sum(1 for x in d if abs(x) > 1e-9), m, 1.96 * se, sum(d) / tot))
allд = [x for v in g.values() for x in v]
print("overall paired dR=%+.4f (n=%d)" % (st.fmean(allд), len(allд)))
