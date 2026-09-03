"""ADVERSARIAL VERIFY of research/g71_exitfam.md F4 `ride` vs `ride_nodz`.

Independent re-implementation of the two arms straight off stop_rule primitives
(no import of g71_exitfam's ride()), plus three structural checks:

  A. is disaster_stop_price == the trade's ORIGINAL stop level, on every row?
  B. in the disaster=True arm, is the close-triggered LEVEL stop branch ever
     reached?  (if never, "two stops" is one stop with a wick trigger, and the
     -1.25R floor is dead code again -- x2_stop_floor_audit's bug, restored)
  C. reproduce +0.5597 / +0.7727 / delta +0.2130 [+0.1159, +0.3293].
"""
import json, os, random, statistics, sys
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
from research.r9_simple_book import Bars
from stop_rule import (stop_hit_on_close, stop_fill_price, MAX_LOSS_R,
                       DISASTER_STOP_R, disaster_stop_price, disaster_stop_hit)

BOOK = os.path.join(_HERE, "bt2y_trades.json")
EOD = 10**6

def rr(entry, stop, px, side):
    risk = abs(entry-stop)
    if risk <= 0: return 0.0
    return (px-entry)/risk if side=="L" else (entry-px)/risk

def my_ride(bars, ei, entry, stop, side, disaster):
    """my own loop; disaster tested first, then level stop on close floored -1.25R"""
    risk = abs(entry-stop)
    if risk <= 0: return 0.0, "flat", False
    long = side=="L"
    dz = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
    n=len(bars)
    for i in range(ei+1, n):
        b=bars[i]
        if disaster and disaster_stop_hit(b["h"], b["l"], dz, long):
            return rr(entry,stop,dz,side), "disaster", False
        if stop_hit_on_close(b["c"], stop, long):
            fill = stop_fill_price(b["c"], entry, risk, long)
            return rr(entry,stop,fill,side), "stop", (fill != b["c"])
    return rr(entry,stop,bars[n-1]["c"],side), "clock", False

cache = Bars()
blob = json.load(open(BOOK, encoding="utf-8"))
print("book meta:", {k:v for k,v in blob["meta"].items() if k!="symbols"})
rows=[]; gaps={"day":0,"bar":0,"index":0}
for r in blob["trades"]:
    if not r.get("traded"): continue
    got = cache.get(r["sym"], r["day"])
    if got is None: gaps["day"]+=1; continue
    rth, dicts, idx, hi, lo = got
    if idx.get(r["et"]) is None: gaps["bar"]+=1; continue
    if r["entry_i"] >= len(dicts): gaps["index"]+=1; continue
    rows.append(dict(sym=r["sym"], day=r["day"], ym=r["ym"],
                     side=r.get("side") or ("L" if r["dir"]=="call" else "S"),
                     entry_i=r["entry_i"], entry=float(r["entry"]),
                     stop=float(r["stop"]), book_r=float(r["r"]), bars=dicts))
print("replayed rows:", len(rows), "gaps:", gaps)

# --- CHECK A: dz price vs stop level
maxdiff=0.0; nsame=0
for r in rows:
    risk=abs(r["entry"]-r["stop"]); long=r["side"]=="L"
    dz=disaster_stop_price(r["entry"],risk,long,DISASTER_STOP_R)
    d=abs(dz-r["stop"]); maxdiff=max(maxdiff,d)
    if d<1e-12: nsame+=1
print(f"CHECK A: disaster price == original stop on {nsame}/{len(rows)} rows; max |diff| = {maxdiff:.3e}")

# --- run both arms + reason census
whyon={}; whyoff={}; floored_on=0; floored_off=0
for r in rows:
    v,w,fl = my_ride(r["bars"],r["entry_i"],r["entry"],r["stop"],r["side"],True)
    r["ride"]=v; whyon[w]=whyon.get(w,0)+1; floored_on += fl
    v,w,fl = my_ride(r["bars"],r["entry_i"],r["entry"],r["stop"],r["side"],False)
    r["ride_nodz"]=v; whyoff[w]=whyoff.get(w,0)+1; floored_off += fl
print("CHECK B: exit reasons, disaster ON :", whyon, " rows hitting the -1.25R floor:", floored_on)
print("         exit reasons, disaster OFF:", whyoff, " rows hitting the -1.25R floor:", floored_off)

def agg(vals):
    dec=sum(1 for x in vals if x!=0); w=sum(1 for x in vals if x>0)
    return dict(n=len(vals), mean=sum(vals)/len(vals), med=statistics.median(vals),
                wr=100*w/dec if dec else 0, tot=sum(vals), worst=min(vals))
for k in ("ride","ride_nodz","book_r"):
    a=agg([r[k] for r in rows]); print(f"  {k:10s} n={a['n']} win={a['wr']:.1f}% mean={a['mean']:+.4f} med={a['med']:+.4f} tot={a['tot']:+.1f} worst={a['worst']:+.4f}")

d=[r["ride_nodz"]-r["ride"] for r in rows]
obs=sum(d)/len(d); rnd=random.Random(20260829); m=len(d); means=[]
for _ in range(10000):
    s=0.0
    for _ in range(m): s+=d[rnd.randrange(m)]
    means.append(s/m)
means.sort()
print(f"CHECK C: delta nodz-ride = {obs:+.4f} [{means[250]:+.4f}, {means[9749]:+.4f}]")
ndiff=sum(1 for x in d if abs(x)>1e-9)
print(f"         rows where the two arms differ: {ndiff} ({100*ndiff/len(d):.1f}%)")
