"""Same replay, but bit-for-bit the DEFAULT live exit path.

paper_trader.py:39 RULE6_ENABLED = False, so exit_for() is literally
    self._check_stop(close) or self._check_target(high, low)
i.e. STOP FIRST on the same bar (docstring: "assume the worst case (stop)"),
close-triggered, floored -1.25R by _stop_fill_premium; TARGET second, wick touch.
No disaster-zone check exists on that path.  Three orderings priced.
"""
import json, statistics, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research"))
import polygon_feed as pf
from stop_rule import (stop_hit_on_close, stop_fill_price, disaster_stop_price,
                       disaster_stop_hit)
import g71_firsts_policy as F

bk = json.loads((ROOT/"research"/"bt2y_trades.json").read_text(encoding="utf-8"))
counted=[r for r in bk["trades"] if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
by=defaultdict(list)
for r in counted: by[r["day"]].append(r)
for d in by: by[d].sort(key=F.ekey)
picked=[]
for d in sorted(by): picked.extend(F.walk(by[d], F.P_FIRST))

cache={}
def rth(s,d):
    if (s,d) not in cache:
        try: cache[(s,d)]=pf.rth(pf.fetch_day(s,d))
        except Exception: cache[(s,d)]=[]
    return cache[(s,d)]

def sim(mode):
    out=[]
    for r in picked:
        bars=rth(r["sym"], r["day"]); i0=r.get("entry_i")
        if not bars or i0 is None or i0>=len(bars): continue
        e,s=r["entry"],r["stop"]; long=r["dir"]=="call"; risk=abs(e-s)
        if risk<=0: continue
        tgt=e+2*risk if long else e-2*risk
        dz=disaster_stop_price(e,risk,long)
        px=bars[-1].close
        for i in range(i0+1,len(bars)):
            c=bars[i]
            tgt_hit=(c.high>=tgt) if long else (c.low<=tgt)
            stp_hit=stop_hit_on_close(c.close,s,long)
            dz_hit=disaster_stop_hit(c.high,c.low,dz,long)
            if mode=="paper":            # paper_trader.exit_for default order
                if stp_hit: px=stop_fill_price(c.close,e,risk,long); break
                if tgt_hit: px=tgt; break
            elif mode=="limit_first":    # a resting limit really does fill first
                if tgt_hit: px=tgt; break
                if dz_hit:  px=dz; break
                if stp_hit: px=stop_fill_price(c.close,e,risk,long); break
            else:                        # paper order + disaster floor
                if dz_hit and not tgt_hit: px=dz; break
                if stp_hit: px=stop_fill_price(c.close,e,risk,long); break
                if tgt_hit: px=tgt; break
        out.append(((px-e) if long else (e-px))/risk)
    return out

bkd=[r["r"] for r in picked]
clip=[min(x,2.0) for x in bkd]
print("A. shipped backtest exit        mean %+0.4fR  total %+7.2fR  E$/day $%d"%(statistics.fmean(bkd),sum(bkd),round(statistics.fmean(bkd)*1000)))
print("B. CLAIM min(r,2.0)             mean %+0.4fR  total %+7.2fR  E$/day $%d"%(statistics.fmean(clip),sum(clip),round(statistics.fmean(clip)*1000)))
for m,lbl in (("paper","C. paper_trader order (stop 1st)"),
              ("limit_first","D. limit fills first + dz floor"),
              ("dz","E. paper order + disaster floor ")):
    v=sim(m)
    print("%-32s mean %+0.4fR  total %+7.2fR  E$/day $%d  win %5.2f%%  n=%d"
          %(lbl,statistics.fmean(v),sum(v),round(statistics.fmean(v)*1000),
            100*sum(1 for x in v if x>0)/len(v),len(v)))
