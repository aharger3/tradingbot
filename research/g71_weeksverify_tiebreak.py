"""Fragility of P1 ('one trade a day') to the arbitrary tie-break in ekey().

ekey = (entry_i, et, sym). When several signals fire on the SAME bar, "the
first signal of the day" is decided by TICKER ALPHABET -- not by anything
causal. This resamples that tie-break at random and asks how much of P1's
77/105 green weeks, and of the 22/8 McNemar split against P0, is an artefact
of alphabetical order.
"""
import json, math, random, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
book = json.loads((ROOT/"research/bt2y_trades.json").read_text(encoding="utf-8"))
trades = book["trades"]
counted = [r for r in trades if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
shipped = [r for r in trades if r["traded"]]

def wk(d):
    y,w,_=date.fromisoformat(d).isocalendar(); return "%04d-W%02d"%(y,w)

by_day=defaultdict(list)
for r in counted: by_day[r["day"]].append(r)
all_days=sorted(by_day); all_weeks=sorted({wk(d) for d in all_days})

# how often is the first bar of the day contested?
ties=0; tsz=[]
for d,rs in by_day.items():
    m=min(r["entry_i"] for r in rs)
    k=sum(1 for r in rs if r["entry_i"]==m)
    if k>1: ties+=1; tsz.append(k)
print("days where >1 counted signal shares the first bar: %d / %d (%.1f%%), mean tie size %.2f, max %d"
      % (ties,len(all_days),ties/len(all_days)*100, statistics.fmean(tsz) if tsz else 0, max(tsz) if tsz else 0))

def greenvec(dayr):
    v=defaultdict(float)
    for d,x in dayr.items(): v[wk(d)]+=x
    return [1 if v.get(w,0.0)>0 else 0 for w in all_weeks]

p0day={}
for r in shipped: p0day[r["day"]]=p0day.get(r["day"],0.0)+r["r"]
g0=greenvec(p0day)

def mcn(ga,gb):
    b10=sum(1 for x,y in zip(ga,gb) if x==1 and y==0)
    b01=sum(1 for x,y in zip(ga,gb) if x==0 and y==1)
    n=b10+b01
    if n==0: return b10,b01,1.0
    k=min(b10,b01)
    return b10,b01,min(1.0, 2*sum(math.comb(n,i) for i in range(k+1))/2**n)

rng=random.Random(20260829)
greens=[]; ps=[]; sig=0
for it in range(2000):
    day={}
    for d,rs in by_day.items():
        m=min(r["entry_i"] for r in rs)
        pick=rng.choice([r for r in rs if r["entry_i"]==m])
        day[d]=pick["r"]
    gv=greenvec(day)
    greens.append(sum(gv))
    a,b,p=mcn(g0,gv); ps.append(p)
    if p<0.05: sig+=1
gs=sorted(greens); pss=sorted(ps)
print("P1 under random same-bar tie-break, 2000 draws:")
print("  green weeks  min=%d p05=%d med=%d p95=%d max=%d   (report's alphabetical P1 = 77)"
      %(gs[0],gs[100],gs[1000],gs[1900],gs[-1]))
print("  McNemar p    min=%.4f p05=%.4f med=%.4f p95=%.4f max=%.4f"%(pss[0],pss[100],pss[1000],pss[1900],pss[-1]))
print("  share of tie-breaks where p<0.05: %.1f%%   (p<0.05/13 Holm-ish: %.1f%%)"
      %(sig/len(ps)*100, sum(1 for p in ps if p<0.05/13)/len(ps)*100))

# and the same for the RANDOM-ONE-PER-DAY control (any signal, not just first bar)
greens2=[]; ps2=[]
for it in range(2000):
    day={d: rng.choice(rs)["r"] for d,rs in by_day.items()}
    gv=greenvec(day); greens2.append(sum(gv)); ps2.append(mcn(g0,gv)[2])
g2=sorted(greens2); p2=sorted(ps2)
print("RANDOM one-per-day (EV control, not 'first'):")
print("  green weeks med=%d [p05 %d, p95 %d]; McNemar p med=%.4f, share p<0.05 = %.1f%%"
      %(g2[1000],g2[100],g2[1900],p2[1000],sum(1 for p in ps2 if p<0.05)/len(ps2)*100))
