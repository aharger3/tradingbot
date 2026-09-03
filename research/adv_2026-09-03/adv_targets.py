"""Independent adversarial recompute of research/sweep_targets_flat.py.
Nothing imported from sweep_targets_flat. Only polygon_feed (bars) and the
book json. min_risk_floor re-derived from signal_runner AND cross-checked
against the literal formula.
"""
import json, os, sys, statistics
from collections import defaultdict
ROOT = r"C:\Users\aharg\Desktop\Projects\tradingbot"
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT,"research"))
import polygon_feed as pf

BOOK = os.path.join(ROOT,"research","bt2y_trades_retest_on.json")
CUT = "11:00:00"

try:
    from signal_runner import min_risk_floor as MRF
    SRC = "signal_runner.min_risk_floor"
except Exception as e:
    MRF = None; SRC = "IMPORT FAILED: %r" % (e,)
def floor_formula(close): return max(0.10, 0.0015*close)

blob = json.load(open(BOOK, encoding="utf-8"))
rows = blob["trades"]; sessions = blob["meta"]["sessions"]

def first_of_day(rows):
    by = defaultdict(list)
    for r in rows:
        if (r["status"]=="fired" and r.get("traded")) or r["status"]=="halted":
            by[r["day"]].append(r)
    out=[]
    for d in sorted(by):
        out.append(sorted(by[d], key=lambda r:(r["day"],r["et"],r["sym"]))[0])
    return out

firsts = first_of_day(rows)
print("firsts:", len(firsts), "sessions:", sessions)

_c={}
def bars_of(s,d):
    k=(s,d)
    if k not in _c:
        try: _c[k]=pf.rth(pf.fetch_day(s,d))
        except Exception: _c[k]=[]
    return _c[k]

# ---- integrity checks on the population -------------------------------
bad_et=0; bad_close=0; missing=0; sign_bad=0; risk0=0
floor_mismatch=0
gate_keep=[]; gate_drop=[]
for r in firsts:
    b=bars_of(r["sym"],r["day"])
    if not b or r["entry_i"] is None or r["entry_i"]>=len(b):
        missing+=1; continue
    c=b[r["entry_i"]]
    if c.timestamp[:5]!=r["et"]: bad_et+=1
    if abs(c.close-r["entry"])>1e-9: bad_close+=1
    risk=abs(r["entry"]-r["stop"])
    if risk<=0: risk0+=1
    if r["side"]=="L" and r["stop"]>=r["entry"]: sign_bad+=1
    if r["side"]=="S" and r["stop"]<=r["entry"]: sign_bad+=1
    f_sr = MRF(r["entry"]) if MRF else None
    f_ff = floor_formula(r["entry"])
    if f_sr is not None and abs(f_sr-f_ff)>1e-12: floor_mismatch+=1
    (gate_keep if risk>=f_ff else gate_drop).append(r)
print("floor source:", SRC, " sr-vs-formula mismatches:", floor_mismatch)
print("missing bars:", missing, "| entry_i timestamp != et:", bad_et,
      "| entry_bar.close != row.entry:", bad_close,
      "| stop on wrong side of entry:", sign_bad, "| zero risk:", risk0)
print("size gate: keep", len(gate_keep), "drop", len(gate_drop))

def cutidx(b):
    for j,c in enumerate(b):
        if c.timestamp>=CUT: return j
    return len(b)

def resim(r, b, n, stop_mode):
    ei=r["entry_i"]
    if ei is None or ei>=len(b): return None,"no_entry_bar"
    e=r["entry"]; s=r["stop"]; risk=abs(e-s)
    if risk<=0: return None,"zero_risk"
    L = r["side"]=="L"
    t = e + n*risk if L else e - n*risk
    cut=min(cutidx(b), len(b)); start=ei+1
    if start>=cut: return 0.0,"no_bars_after_entry"
    last=b[cut-1].close
    for j in range(start,cut):
        c=b[j]
        if stop_mode=="touch":
            hs = (c.low<=s) if L else (c.high>=s)
        else:  # close-triggered, CLAUDE.md law
            hs = (c.close<=s) if L else (c.close>=s)
        ht = (c.high>=t) if L else (c.low<=t)
        if hs:
            if stop_mode=="touch": return -1.0,"stop"
            rr = (c.close-e)/risk if L else (e-c.close)/risk
            return max(rr,-1.0),"stop"     # R1: -1R hard floor
        if ht: return float(n),"target"
        last=c.close
    return ((last-e)/risk if L else (e-last)/risk),"eod_flat"

def score(rs):
    n=len(rs); w=[x for x in rs if x>0]; l=[x for x in rs if x<0]
    wr=len(w)/n; lr=len(l)/n
    aw=statistics.fmean(w) if w else 0.0
    al=statistics.fmean([-x for x in l]) if l else 0.0
    tot=sum(rs)
    peak=cum=worst=0.0
    for x in rs:
        cum+=x; peak=max(peak,cum); worst=min(worst,cum-peak)
    pf_=sum(w)/sum(-x for x in l) if l else float('inf')
    return dict(ev=wr*aw-lr*al, n=n, win=wr, aw=aw, al=al, tot=tot, dd=worst, pf=pf_)

def prop(daily, acct=50000.0, tgt=0.08, tdd=0.04, dll=0.02, mind=5, cons=0.30):
    """returns (passed, reason, day, days_traded, equity_at_decision, worst_dd)"""
    eq=peak=worst=0.0; dt=0; profits=[]; reached=False
    for day,p in daily:
        if p==0: continue
        dt+=1; profits.append(p)
        if p <= -dll*acct: return (False,"daily_loss_limit",day,dt,eq,worst)
        eq+=p; peak=max(peak,eq); worst=min(worst,eq-peak)
        if eq < peak - tdd*acct: return (False,"trailing_drawdown",day,dt,eq,worst)
        if eq>=tgt*acct and dt>=mind:
            reached=True
            if max(profits)/eq <= cons: return (True,None,day,dt,eq,worst)
    return (False,("min_trading_days" if dt<mind else "consistency" if reached
                   else "profit_target_not_reached"), daily[-1][0] if daily else None,
            dt,eq,worst)

TARGETS=[round(1.0+0.25*i,2) for i in range(21)]
for mode in ("touch","close"):
    print("\n=== STOP MODE: %s ===" % mode)
    print("%5s %8s %5s %6s %7s %7s %8s %8s  %-11s %s"%("N","ev_r","n","win","avgW","totR","maxDD","PF","pass@100","passday"))
    res={}
    for n in TARGETS:
        rs=[]; days=[]
        for r in gate_keep:
            b=bars_of(r["sym"],r["day"])
            v,why=resim(r,b,n,mode)
            if v is None: continue
            rs.append(v); days.append(r["day"])
        sc=score(rs); res[n]=(sc,rs,days)
        p=prop([(d,x*100) for d,x in zip(days,rs)])
        print("%5.2f %+8.4f %5d %6.3f %7.3f %7.2f %8.2f %8.4f  %-11s %s (day#%d, eq=$%.0f)"%(
            n,sc['ev'],sc['n'],sc['win'],sc['aw'],sc['tot'],sc['dd'],sc['pf'],
            "PASS" if p[0] else p[1], p[2], p[3], p[4]))
    json.dump({str(k):(v[0],v[1],v[2]) for k,v in res.items()},
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"adv_%s.json"%mode),"w"))
