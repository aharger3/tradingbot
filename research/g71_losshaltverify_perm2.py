"""VERIFY part 3 — the within-day permutation null for EACH streak bucket mean.
Answers: with the trade->outcome pairing destroyed (day outcome-multiset and
entry schedule preserved), what would E[R | streak=k] be anyway?
Read-only. Usage: python research/g71_losshaltverify_perm2.py"""
import json, statistics, random
from collections import defaultdict
d = json.load(open("research/bt2y_trades.json", encoding="utf-8"))
rows = d["trades"]
cand = [r for r in rows if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
ek = lambda r: (r["entry_i"], r["et"], r["sym"])
by = defaultdict(list)
for r in cand: by[r["day"]].append(r)
days = sorted(by)
rnd = random.Random(11)
acc = defaultdict(list)
for _ in range(2000):
    v = defaultdict(list)
    for dy in days:
        base = sorted(by[dy], key=ek)
        pay = [(r["r"], r["out"]=="loss", r["bars"]) for r in base]
        rnd.shuffle(pay)
        pend, s = [], 0
        for row,(rr,lost,bars) in zip(base, pay):
            at = ek(row)
            while pend and pend[0][0] <= at:
                _x,l2 = pend.pop(0); s = s+1 if l2 else 0
            v[min(s,4)].append(rr)
            pend.append(((row["entry_i"]+bars,row["et"],row["sym"]), lost))
            pend.sort(key=lambda p:p[0])
    for k in range(5):
        if v.get(k): acc[k].append(statistics.fmean(v[k]))
obs = defaultdict(list)
pend, s = [], 0
for dy in days:
    base = sorted(by[dy], key=ek); pend, s = [], 0
    for row in base:
        at = ek(row)
        while pend and pend[0][0] <= at:
            _x,l2 = pend.pop(0); s = s+1 if l2 else 0
        obs[min(s,4)].append(row["r"])
        pend.append(((row["entry_i"]+row["bars"],row["et"],row["sym"]), row["out"]=="loss"))
        pend.sort(key=lambda p:p[0])
print("%-8s %8s %10s %10s %s" % ("streak","n","observed","null mean","null 95%"))
for k in range(5):
    a = sorted(acc[k]); m = statistics.fmean(obs[k])
    print("%-8d %8d %+10.4f %+10.4f  [%+.4f, %+.4f]"
          % (k, len(obs[k]), m, statistics.fmean(a), a[int(.025*len(a))], a[int(.975*len(a))-1]))
