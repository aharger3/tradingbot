"""ADVERSARIAL: do the SURVIVING T1 level_in_context values sit inside the day's RTH range?
Read-only. Replaces the dead g71_scarface_validate.py (KeyError levels_text)."""
import json,sys
from pathlib import Path
ROOT=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot"); sys.path.insert(0,str(ROOT))
import polygon_feed as pf
rs=[json.loads(l) for l in open(ROOT/"research"/"g71_scarface_candidates.jsonl",encoding='utf-8')]
t1=[r for r in rs if r['tier']=='T1' and r['in_backtest_universe']]
pure=[r for r in t1 if r['level_in_context'] and set(r['level_in_context'])<=set(r['option_strikes'])]
def run(rows,label,cap=40):
    ok=bad=nb=0; ex=[]
    for r in rows[:cap]:
        try: bars=pf.rth(pf.fetch_day(r['symbol'],r['day']))
        except Exception: nb+=1; continue
        if not bars: nb+=1; continue
        lo,hi=min(b.low for b in bars),max(b.high for b in bars)
        h=[L for L in r['level_in_context'] if lo<=L<=hi]
        if h: ok+=1
        else:
            bad+=1; ex.append((r['card_id'],r['level_in_context'],round(lo,2),round(hi,2)))
    n=ok+bad
    print(f"{label}: checked={n} inrange={ok} ({ok/max(1,n)*100:.0f}%) MISS={bad} nobars={nb}")
    for e in ex[:15]: print("   MISS",e)
run(pure,"T1 pure-strike-as-level")
print()
mixed=[r for r in t1 if r not in pure]
run(mixed,"T1 rest")
