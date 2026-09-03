"""How fragile is the 25/25 -> 22/23 durability verdict?

Three attacks:
  A. tie-break: several candidates share a minute; "first" is then arbitrary.
  B. exposure control: a RANDOM one-per-day policy (the report leaves its
     months_green as -1) and a random sequential policy -- if those also drop
     to ~22/25, the lost gate is bought by exposure, not by Austin's rule.
  C. how many trades separate a red month from green.
"""
import json, random, statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))["trades"]
counted = [r for r in T if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
raw = defaultdict(list)
for r in counted:
    raw[r["day"]].append(r)
days = sorted(raw)
months = sorted({d[:7] for d in days})

def walk(rows, stop):
    out, free, w, l, cum = [], None, 0, 0, 0.0
    for c in rows:
        if stop(len(out), w, l, cum): break
        if free is not None and c["entry_i"] < free: continue
        out.append(c); free = c["entry_i"] + c["bars"]
        if c["out"] == "win": w += 1
        elif c["out"] == "loss": l += 1
        cum += c["r"]
    return out

POL = {"P1": lambda n,w,l,c: n>=1, "P2": lambda n,w,l,c: w>=1 or l>=2,
       "P3": lambda n,w,l,c: c>0,  "P4": lambda n,w,l,c: c>0 or l>=3,
       "P0seq": lambda n,w,l,c: False}

def green(order, pol):
    m = defaultdict(float)
    for d in days:
        for r in walk(order[d], POL[pol]): m[d[:7]] += r["r"]
    return sum(1 for k in months if m.get(k, 0.0) > 0), dict(m)

# ---- A. tie-break sensitivity
orders = {
  "sym asc (report)": {d: sorted(v, key=lambda r:(r["entry_i"], r["et"], r["sym"])) for d,v in raw.items()},
  "sym desc":         {d: sorted(v, key=lambda r:(r["entry_i"], r["et"]), reverse=False) for d,v in raw.items()},
}
orders["sym desc"] = {d: sorted(v, key=lambda r:(r["entry_i"], [-ord(c) for c in r["sym"]])) for d,v in raw.items()}
tie_minutes = sum(1 for d,v in raw.items() for k,c in __import__("collections").Counter(x["entry_i"] for x in v).items() if c>1)
print("day-minutes carrying >1 candidate: %d" % tie_minutes)
for lab, o in orders.items():
    print("  %-16s " % lab + "  ".join("%s %d/25" % (p, green(o, p)[0]) for p in ("P1","P2","P3","P4","P0seq")))
rng = random.Random(7)
tallies = defaultdict(list)
for s in range(40):
    rr = random.Random(s)
    o = {d: sorted(v, key=lambda r:(r["entry_i"], rr.random())) for d, v in raw.items()}
    for p in ("P1","P2","P3","P4"): tallies[p].append(green(o,p)[0])
print("  random tie-break x40: " + "  ".join("%s min=%d max=%d median=%d" %
      (p, min(v), max(v), int(st.median(v))) for p,v in tallies.items()))

# ---- B. exposure control: random one-per-day and random sequential
base = orders["sym asc (report)"]
r1, rseq = [], []
for s in range(200):
    rr = random.Random(1000+s)
    m = defaultdict(float)
    for d in days: m[d[:7]] += rr.choice(raw[d])["r"]
    r1.append(sum(1 for k in months if m.get(k,0.0) > 0))
    # random sequential: shuffle order, take everything one at a time
    o = {d: sorted(raw[d], key=lambda r:(r["entry_i"], rr.random())) for d in days}
    m2 = defaultdict(float)
    for d in days:
        for r in walk(o[d], POL["P0seq"]): m2[d[:7]] += r["r"]
    rseq.append(sum(1 for k in months if m2.get(k,0.0) > 0))
print("RANDOM one-per-day months green x200: mean=%.2f median=%d min=%d max=%d  P(>=25)=%.0f%%"
      % (st.fmean(r1), st.median(r1), min(r1), max(r1), 100*sum(1 for x in r1 if x>=25)/len(r1)))
print("RANDOM-order sequential  months green x200: mean=%.2f min=%d max=%d"
      % (st.fmean(rseq), min(rseq), max(rseq)))

# ---- C. margins
for p in ("P1","P2","P3","P4"):
    g, m = green(base, p)
    red = sorted((v,k) for k,v in m.items() if v <= 0)
    print("%-3s %d/25 red: %s" % (p, g, ", ".join("%s %+.2fR" % (k,v) for v,k in red)))
