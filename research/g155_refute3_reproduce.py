import json, os, sys, collections
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot")
import importlib.util
spec = importlib.util.spec_from_file_location("g154", r"C:\Users\aharg\Desktop\Projects\tradingbot\research\g154_rule_scale-before-the-level.py")
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
import stop_rule as sru
from research import omen_metrics as om

blob=json.load(open(g.BOOK,encoding="utf-8")); rows=blob["trades"]; n_days=blob["meta"]["sessions"]
picks=om.first_of_day_arm(rows,size_gate=True); pbd={r["day"]:r for r in picks}
RISK=1000.0

def sim(r,tgt,eps):
    """eps = required trade-THROUGH past the resting limit before it fills."""
    entry,stop=r["entry"],r["stop"]; long=r["dir"]=="call"; risk=abs(entry-stop)
    if risk<=0: return r["pnl"],r["r"],"no_bars"
    bars=g.bars_for(r["sym"],r["day"]); ei=r.get("entry_i")
    if not bars or ei is None or ei>=len(bars): return r["pnl"],r["r"],"no_bars"
    dp=sru.disaster_stop_price(entry,risk,long)
    for j in range(ei+1,len(bars)):
        c=bars[j]
        if sru.disaster_stop_hit(c.high,c.low,dp,long): return -sru.DISASTER_STOP_R*RISK,-sru.DISASTER_STOP_R,"disaster"
        hit=(c.high>=tgt+eps) if long else (c.low<=tgt-eps)
        if hit:
            fill=(c.open if c.open>=tgt else tgt) if long else (c.open if c.open<=tgt else tgt)
            rm=(fill-entry)/risk if long else (entry-fill)/risk
            return rm*RISK,rm,"target"
        if sru.stop_hit_on_close(c.close,stop,long):
            fill=sru.stop_fill_price(c.close,entry,risk,long)
            rm=(fill-entry)/risk if long else (entry-fill)/risk
            return rm*RISK,rm,"stop_close"
    last=bars[-1]; rm=(last.close-entry)/risk if long else (entry-last.close)/risk
    return rm*RISK,rm,"eod"

def run(b,eps):
    tr=[]
    for day,r in sorted(pbd.items()):
        tgt=g.shifted_target(r,b) if b>0 else r["target"]
        pnl,rm,reason=sim(r,tgt,eps)
        tr.append({"day":day,"pnl":pnl,"r":rm,"reason":reason})
    f=g.price_stats(tr,n_days)
    h1=g.price_stats(g.half(tr,hi=g.H_SPLIT),g.n_days_in(tr,hi=g.H_SPLIT))
    h2=g.price_stats(g.half(tr,lo=g.H_SPLIT),g.n_days_in(tr,lo=g.H_SPLIT))
    return f,h1,h2

print("fill rule                base $/day (H1/H2)      cents_005 $/day (H1/H2)     dH1     dH2   survives?")
for eps,lab in [(0.0,"touch fills (as shipped)"),(0.01,"must trade through 1c"),(0.02,"must trade through 2c")]:
    b0=run(0.0,eps); b5=run(0.05,eps)
    dh1=b5[1]["per_day"]-b0[1]["per_day"]; dh2=b5[2]["per_day"]-b0[2]["per_day"]
    print("%-24s $%4d (%4d/%4d)        $%4d (%4d/%4d)     %+6.1f %+7.1f   %s"
          %(lab,b0[0]["per_day"],b0[1]["per_day"],b0[2]["per_day"],
            b5[0]["per_day"],b5[1]["per_day"],b5[2]["per_day"],dh1,dh2,
            "YES" if (dh1>0 and dh2>0) else "NO"))

# concentration: how much of the H2 delta is the single best day?
base=[];cand=[]
for day,r in sorted(pbd.items()):
    base.append((day,sim(r,r["target"],0.0)[0])); cand.append((day,sim(r,g.shifted_target(r,0.05),0.0)[0]))
d={a[0]:b[1]-a[1] for a,b in zip(base,cand)}
nz=sorted(((v,k) for k,v in d.items() if abs(v)>1e-6),reverse=True)
h2days=len({k for k in d if k>=g.H_SPLIT})
h2tot=sum(v for k,v in d.items() if k>=g.H_SPLIT)
print("\nDays where cents_005 differs from baseline at all: %d of 498"%len(nz))
print("H2 total delta $%.0f over %d H2 days = $%.1f/day; top 3 days = $%.0f (%.0f%% of it)"
      %(h2tot,h2days,h2tot/h2days,sum(v for v,k in nz if k>=g.H_SPLIT)and sum(sorted((v for v,k in nz if k>=g.H_SPLIT),reverse=True)[:3]),
        100*sum(sorted((v for v,k in nz if k>=g.H_SPLIT),reverse=True)[:3])/h2tot))
print("the differing days:", [(k,round(v)) for v,k in nz])
