import json,os,sys,statistics
from collections import defaultdict
from datetime import date
ROOT=r"C:\Users\aharg\Desktop\Projects\tradingbot"
sys.path.insert(0,ROOT); sys.path.insert(0,os.path.join(ROOT,"research"))
import polygon_feed as pf
from signal_runner import min_risk_floor as MRF
rows=json.load(open(os.path.join(ROOT,"research","bt2y_trades_retest_on.json"),encoding="utf-8"))["trades"]
by=defaultdict(list)
for r in rows:
    if (r["status"]=="fired" and r.get("traded")) or r["status"]=="halted": by[r["day"]].append(r)
firsts=[sorted(by[d],key=lambda r:(r["day"],r["et"],r["sym"]))[0] for d in sorted(by)]
keep=[r for r in firsts if abs(r["entry"]-r["stop"])>=MRF(r["entry"])]
mid=len(keep)//2; START=keep[0]["day"]
_c={}
def Bd(s,d):
    k=(s,d)
    if k not in _c: _c[k]=pf.rth(pf.fetch_day(s,d))
    return _c[k]
def cutidx(b):
    for j,c in enumerate(b):
        if c.timestamp>="11:00:00": return j
    return len(b)
def raw(r,n):
    b=Bd(r["sym"],r["day"]);ei=r["entry_i"];e=r["entry"];s=r["stop"]
    risk=abs(e-s);L=r["side"]=="L";t=e+n*risk if L else e-n*risk
    cut=min(cutidx(b),len(b));start=ei+1
    if start>=cut: return 0.0
    last=b[cut-1].close
    for j in range(start,cut):
        c=b[j]
        if (c.close<=s) if L else (c.close>=s):
            return (c.close-e)/risk if L else (e-c.close)/risk
        if (c.high>=t) if L else (c.low<=t): return float(n)
        last=c.close
    return (last-e)/risk if L else (e-last)/risk
def sc(rs):
    w=[x for x in rs if x>0]; l=[x for x in rs if x<0]
    aw=statistics.fmean(w) if w else 0.; al=statistics.fmean([-x for x in l]) if l else 0.
    return (len(w)/len(rs))*aw-(len(l)/len(rs))*al
def prop(daily,acct=50000.,tgt=.08,tdd=.04,dll=.02,mind=5,cons=.30):
    eq=peak=0.;dt=0;pr=[];reach=False
    for day,p in daily:
        if p==0: continue
        dt+=1;pr.append(p)
        if p<=-dll*acct: return (False,"daily_loss_limit",day)
        eq+=p;peak=max(peak,eq)
        if eq<peak-tdd*acct: return (False,"trailing_drawdown",day)
        if eq>=tgt*acct and dt>=mind:
            reach=True
            if max(pr)/eq<=cons: return (True,None,day)
    return (False,("min_trading_days" if dt<mind else "consistency" if reach else "no_target"),daily[-1][0])
print("close-FILL stop, no -1R clamp (internally consistent close reading), n=%d"%len(keep))
print("%5s | %8s %8s %8s | %-18s %-11s %s"%("N","ev_all","ev_H1","ev_H2","pass@100","day","mos"))
for i in range(21):
    n=round(1.0+.25*i,2)
    rs=[raw(r,n) for r in keep]
    p=prop([(r["day"],x*100) for r,x in zip(keep,rs)])
    mo=(date.fromisoformat(p[2])-date.fromisoformat(START)).days/30.4375
    print("%5.2f | %+8.4f %+8.4f %+8.4f | %-18s %-11s %.1f"%(n,sc(rs),sc(rs[:mid]),sc(rs[mid:]),
        "PASS" if p[0] else p[1],p[2],mo))
