"""Split the six_target paired loss into (i) rows where one of Austin's SIX
actually supplied the runner target and (ii) rows where the day offered none
and the arm silently fell back to `t.target` (2R / the 84% original).

The claim is about "restricting the target to his six". If the damage lives in
the fallback, the claim is measuring the fallback, not the six.
"""
from __future__ import annotations
import json, math, random, statistics as st, sys
from collections import defaultdict

b = json.load(open("research/_v/v_base.json", encoding="utf-8"))["trades"]
a = json.load(open("research/_v/v_six.json", encoding="utf-8"))["trades"]
b = [t for t in b if t["traded"]]; a = [t for t in a if t["traded"]]
pb = json.load(open("research/_v/v_base_probe.json", encoding="utf-8"))

# probe key: sym/day/et/dir/entry  (probe et is HH:MM, book et is HH:MM)
pk = {}
for r in pb:
    pk[(r["sym"], r["day"], r["et"], r["dir"], round(r["entry"], 4))] = r

def key(t):
    return (t["sym"], t["day"], t["et"], t["setup"], t["dir"], t["entry"], t["stop"])
def pkey(t):
    return (t["sym"], t["day"], t["et"], t["dir"], round(t["entry"], 4))

bm = {key(t): t for t in b}; am = {key(t): t for t in a}
shared = sorted(set(bm) & set(am))

def ci(d):
    if not d: return (0.0, 0.0, 0)
    m = st.fmean(d); se = st.pstdev(d) / math.sqrt(len(d))
    return (m, 1.96 * se, len(d))

groups = defaultdict(list)
unmatched = 0
for k in shared:
    p = pk.get(pkey(bm[k]))
    d = am[k]["r"] - bm[k]["r"]
    if p is None:
        unmatched += 1; groups["UNMATCHED"].append(d); continue
    if p["six_is_none"]:
        groups["fallback (no six beyond scale)"].append(d)
    elif abs(p["six"] - p["shipped"]) < 1e-9:
        groups["six == shipped (no change)"].append(d)
    else:
        groups["six supplied a different target"].append(d)

print("shared=%d  probe-unmatched=%d" % (len(shared), unmatched))
tot = 0.0
for g, d in sorted(groups.items()):
    m, e, n = ci(d)
    moved = sum(1 for x in d if abs(x) > 1e-9)
    print("%-34s n=%-5d moved=%-4d dR=%+.4f +/-%.4f  contrib to overall dR=%+.4f"
          % (g, n, moved, m, e, sum(d) / len(shared)))
    tot += sum(d) / len(shared)
print("sum of contributions = %+.4f" % tot)

# scale-armed only (the only rows the change can touch)
armed = [d for g, d in groups.items() if g != "UNMATCHED" for d in d]
