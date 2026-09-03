"""ADVERSARIAL: how much of the T1 level error is symbol CARRYOVER, not strike-vs-level?
g71_scarface_candidates.py:82-84  sym = hit[0] if hit else last.get(day)  -- a ticker-less
message inherits the day's LAST seen ticker, across the whole day, no time limit."""
import json,sys
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0,str(ROOT/"research")); sys.path.insert(0,str(ROOT))
import importlib; m=importlib.import_module("g71_scarface_candidates")
d=json.load(open(ROOT/"discord_data"/"scarface-alerts.json",encoding='utf-8'))
d=[x for x in d if "TonyMontana" in (x.get("author") or "")]
seqs,last=defaultdict(list),{}
carry=Counter(); tot=Counter(); distinct=defaultdict(set)
for msg in sorted(d,key=lambda x:x.get("ts","")):
    ts=msg.get("ts") or ""
    if not ts: continue
    c=msg.get("content") or ""; day=ts[:10]
    hit=m.TICK.findall(c); sym=hit[0].upper() if hit else last.get(day)
    if hit: last[day]=sym
    if not sym: continue
    if m.in_window(ts):
        tot[(day,sym)]+=1
        if not hit: carry[(day,sym)]+=1
    if hit: distinct[day].add(sym)
units=[k for k in tot]
print("scarface in-window units:",len(units))
print("units with >=1 carried (ticker-less) message:",sum(1 for k in units if carry[k]))
print("in-window messages total:",sum(tot.values())," carried:",sum(carry.values()),
      f"({sum(carry.values())/sum(tot.values())*100:.0f}%)")
multi=[dd for dd,s in distinct.items() if len(s)>1]
print("days where >1 distinct ticker was named (carryover can cross symbols):",len(multi),"of",len(distinct))
# which T1 pure/miss rows are carryover-contaminated
rs=[json.loads(l) for l in open(ROOT/"research"/"g71_scarface_candidates.jsonl",encoding='utf-8')]
t1=[r for r in rs if r['tier']=='T1' and r['source']=='Scarface']
c=sum(1 for r in t1 if carry.get((r['day'],r['symbol']),0))
print(f"Scarface T1 rows={len(t1)}  with >=1 carried message={c} ({c/max(1,len(t1))*100:.0f}%)")
