"""G7.1 losshalt VERIFY part 2 — day-block bootstrap of the conditional-edge
buckets (the report's OWN stated uncertainty method, which the CONDITIONAL EDGE
block did not use), plus the halted-vs-traded composition decomposition and a
within-day permutation null for the streak gradient.
Read-only. Usage: python research/g71_losshaltverify_boot.py
"""
import json, statistics, random
from collections import defaultdict

d = json.load(open("research/bt2y_trades.json", encoding="utf-8"))
rows = d["trades"]
cand = [r for r in rows if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
ekey = lambda r: (r["entry_i"], r["et"], r["sym"])
xkey = lambda r: (r["entry_i"]+r["bars"], r["et"], r["sym"])

by_day = defaultdict(list)
for r in cand: by_day[r["day"]].append(r)
days = sorted(by_day)

def annotate(order):
    pending, streak = [], 0
    out = []
    for i, row in enumerate(order):
        at = ekey(row)
        while pending and pending[0][0] <= at:
            _x, lost = pending.pop(0)
            streak = streak+1 if lost else 0
        out.append((row, min(streak,4), i))
        pending.append((xkey(row), row["out"]=="loss"))
        pending.sort(key=lambda p: p[0])
    return out

ann = {dy: annotate(sorted(by_day[dy], key=ekey)) for dy in days}

# ---- 1. composition of each streak bucket ----
print("bucket composition (status) and day count")
comp = defaultdict(lambda: defaultdict(int)); dcount = defaultdict(set); vals = defaultdict(list)
for dy in days:
    for row, s, i in ann[dy]:
        comp[s][row["status"]] += 1; dcount[s].add(dy); vals[s].append(row["r"])
for s in sorted(comp):
    print("  streak %d  n=%4d  halted=%4d traded=%4d  days=%3d  mean=%+.4f"
          % (s, sum(comp[s].values()), comp[s].get("halted",0), comp[s].get("fired",0),
             len(dcount[s]), statistics.fmean(vals[s])))

# ---- 2. day-block bootstrap of each bucket mean and of the 0-vs-2 gap ----
def boot(fn, nb=4000, seed=7):
    rnd = random.Random(seed); k = len(days); out = []
    per = {dy: fn(ann[dy]) for dy in days}
    for _ in range(nb):
        num = defaultdict(float); den = defaultdict(int)
        for _i in range(k):
            dy = days[rnd.randrange(k)]
            for key,(sr,cn) in per[dy].items():
                num[key]+=sr; den[key]+=cn
        out.append({key:(num[key]/den[key] if den[key] else None) for key in per[days[0]] | set(num)})
    return out

def per_day_streak(a):
    agg = defaultdict(lambda: [0.0,0])
    for row,s,i in a:
        agg[s][0]+=row["r"]; agg[s][1]+=1
    return {k:(v[0],v[1]) for k,v in agg.items()}

rnd = random.Random(7); k=len(days)
per = {dy: per_day_streak(ann[dy]) for dy in days}
NB=4000
draws = {s: [] for s in range(5)}; gaps02=[]; gaps01=[]
for _ in range(NB):
    num=defaultdict(float); den=defaultdict(int)
    for _i in range(k):
        dy=days[rnd.randrange(k)]
        for s,(sr,cn) in per[dy].items():
            num[s]+=sr; den[s]+=cn
    m={s:(num[s]/den[s] if den.get(s) else None) for s in range(5)}
    for s in range(5):
        if m[s] is not None: draws[s].append(m[s])
    if m[0] is not None and m[2] is not None: gaps02.append(m[0]-m[2])
    if m[0] is not None and m[1] is not None: gaps01.append(m[0]-m[1])

def ci(v):
    v=sorted(v); return v[int(.025*len(v))], v[int(.975*len(v))-1]
print("\nday-block bootstrap (4000 resamples of whole sessions), mean R by streak")
for s in range(5):
    lo,hi = ci(draws[s])
    print("  streak %d  mean %+.4f  95%% [%+.4f, %+.4f]  %s"
          % (s, statistics.fmean(vals[s]), lo, hi, "excludes 0" if lo*hi>0 else "SPANS 0"))
lo,hi = ci(gaps02); print("  gap 0-2   %+.4f  95%% [%+.4f, %+.4f]  %s"
      % (statistics.fmean(vals[0])-statistics.fmean(vals[2]), lo, hi, "excludes 0" if lo*hi>0 else "SPANS 0"))
lo,hi = ci(gaps01); print("  gap 0-1   %+.4f  95%% [%+.4f, %+.4f]  %s"
      % (statistics.fmean(vals[0])-statistics.fmean(vals[1]), lo, hi, "excludes 0" if lo*hi>0 else "SPANS 0"))

# ---- 3. within-day permutation null: is the gradient more than day-composition? ----
# Shuffle the r/out assignment among a day's trades, recompute streaks, re-bucket.
# Preserves each day's multiset of outcomes and its entry schedule; destroys only
# the pairing between a trade's position and its own outcome.
def grad_once(rndp):
    v = defaultdict(list)
    for dy in days:
        base = sorted(by_day[dy], key=ekey)
        pay = [(r["r"], r["out"]=="loss", r["bars"]) for r in base]
        rndp.shuffle(pay)
        pending, streak = [], 0
        for j,(row,(rr,lost,bars)) in enumerate(zip(base,pay)):
            at = ekey(row)
            while pending and pending[0][0] <= at:
                _x, l2 = pending.pop(0); streak = streak+1 if l2 else 0
            v[min(streak,4)].append(rr)
            pending.append(((row["entry_i"]+bars, row["et"], row["sym"]), lost))
            pending.sort(key=lambda p:p[0])
    return v
rndp = random.Random(11)
obs = statistics.fmean(vals[0]) - statistics.fmean(vals[2])
null=[]
for _ in range(2000):
    v = grad_once(rndp)
    if v.get(2): null.append(statistics.fmean(v[0])-statistics.fmean(v[2]))
null.sort()
p = sum(1 for x in null if x >= obs)/len(null)
print("\nwithin-day outcome permutation (2000 draws): observed 0-2 gap %+.4f, "
      "null mean %+.4f, p(one-sided) = %.4f" % (obs, statistics.fmean(null), p))
print("  null 95%% range [%+.4f, %+.4f]" % (null[int(.025*len(null))], null[int(.975*len(null))-1]))
