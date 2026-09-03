"""G7.1/scarface: validate T1 candidates against real bars.
A level parsed from alert text is only usable if it sits inside that day's RTH range.
Read-only. Does not write any corpus."""
import json, sys
from pathlib import Path
ROOT = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0,str(ROOT))
import polygon_feed as pf

recs=[json.loads(l) for l in open(ROOT/"research"/"g71_scarface_candidates.jsonl",encoding='utf-8')]
t1=[r for r in recs if r["tier"]=="T1" and r["in_backtest_universe"]]
print(f"T1 in backtest universe: {len(t1)}")
ok=bad=nobar=0; details=[]
import itertools
for r in t1[:int(sys.argv[1]) if len(sys.argv)>1 else 60]:
    try:
        bars=pf.rth(pf.fetch_day(r["symbol"], r["day"]))
    except Exception as e:
        nobar+=1; continue
    if not bars: nobar+=1; continue
    lo,hi=min(b.low for b in bars),max(b.high for b in bars)
    hits=[L for L in r["levels_text"] if lo<=L<=hi]
    if hits: ok+=1; details.append((r["card_id"],r["direction"],hits[:2],round(lo,2),round(hi,2),"OK"))
    else:    bad+=1; details.append((r["card_id"],r["direction"],r["levels_text"][:3],round(lo,2),round(hi,2),"MISS"))
n=ok+bad
print(f"checked={n}  level-in-range OK={ok} ({ok/max(1,n)*100:.0f}%)  MISS={bad}  nobars={nobar}")
for d in details[:25]: print("  ",d)
