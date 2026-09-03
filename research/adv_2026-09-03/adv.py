"""Independent adversarial recompute of the stop_placement sweep.
Reads bars straight off data_archive CSVs (no engine import), reimplements
the resim from the described rules, and cross-checks the claimed numbers.
"""
import csv, json, os, sys, statistics
from collections import defaultdict

ROOT = r"C:\Users\aharg\Desktop\Projects\tradingbot"
BOOK = os.path.join(ROOT, "research", "bt2y_trades_retest_on.json")

def floor_(c):  # signal_runner.min_risk_floor
    return max(0.10, 0.0015 * c)

_bars = {}
def bars_for(sym, day):
    k = (sym, day)
    if k in _bars:
        return _bars[k]
    p = os.path.join(ROOT, "data_archive", sym, day + ".csv")
    out = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                t = r["Datetime"][11:19]
                if "09:30:00" <= t < "16:00:00":
                    out.append((t, float(r["Open"]), float(r["High"]),
                                float(r["Low"]), float(r["Close"])))
    if len(_bars) > 600: _bars.clear()
    _bars[k] = out
    return out

ATR_LB = 14
def atr(bars, i):
    lo = max(0, i - ATR_LB + 1)
    w = bars[lo:i+1]
    if not w: return None
    return sum(b[2]-b[3] for b in w)/len(w)

def v_shipped(row,bars,i,e,lng): return row["level_px"], None
def v_bookstop(row,bars,i,e,lng): return row["stop"], None
def v_entry(row,bars,i,e,lng): return (bars[i][3] if lng else bars[i][2]), None
def v_prior(row,bars,i,e,lng):
    if i<1: return None,"no_prior_bar"
    return (bars[i-1][3] if lng else bars[i-1][2]), None
def mk_atr(m):
    def f(row,bars,i,e,lng):
        a=atr(bars,i)
        if not a or a<=0: return None,"no_atr"
        return (e-m*a) if lng else (e+m*a), None
    return f
def mk_pct(p):
    def f(row,bars,i,e,lng):
        return (e*(1-p)) if lng else (e*(1+p)), None
    return f

VARIANTS=[("shipped_level",v_shipped),("book_stop",v_bookstop),
          ("entry_candle_extreme",v_entry),("prior_candle_extreme",v_prior)]
VARIANTS+=[("atr_%sx"%m,mk_atr(m)) for m in (0.5,1.0,1.5,2.0)]
VARIANTS+=[("fixed_pct_%.2f"%(p*100),mk_pct(p)) for p in (0.0010,0.0025,0.0050,0.0100)]

def resim(row,bars,fn,cap=True):
    i=row["entry_i"]
    if i>=len(bars): return None,"entry_i_out_of_range"
    e=row["entry"]; lng=row["dir"]=="call"; tgt=row["target"]
    stop,reason=fn(row,bars,i,e,lng)
    if stop is None: return None,reason
    risk=abs(e-stop)
    if risk<=1e-9: return None,"zero_risk"
    if lng and stop>=e: return None,"stop_wrong_side"
    if (not lng) and stop<=e: return None,"stop_wrong_side"
    if risk<floor_(e): return None,"below_min_risk_floor"
    out=None; px=None; j_hit=None
    for j in range(i+1,len(bars)):
        _,o,h,l,c=bars[j]
        sh=(c<=stop) if lng else (c>=stop)
        th=(h>=tgt) if lng else (l<=tgt)
        if sh: out,px,j_hit="stop",stop,j; break
        if th: out,px,j_hit="target",tgt,j; break
    if out is None:
        out,px,j_hit="scratch",bars[-1][4],len(bars)-1
    if out=="stop":
        r=-1.0
        # uncapped: real fill is the CLOSE of the stopping bar
        rc=((bars[j_hit][4]-e)/risk) if lng else ((e-bars[j_hit][4])/risk)
    else:
        r=((px-e)/risk) if lng else ((e-px)/risk); rc=r
    return {"day":row["day"],"sym":row["sym"],"et":row["et"],"key":(row["day"],row["et"],row["sym"],i),
            "entry":e,"stop":stop,"risk":risk,"out":out,"r":r,"r_uncapped":rc,
            "bars_held":j_hit-i},None

def sb(trs, key="r"):
    rs=[t[key] for t in trs]
    n=len(rs)
    if not n: return dict(n=0,ev_r=None,win=None,aw=None,al=None,pf=None,tot=0.0)
    w=[r for r in rs if r>0]; l=[r for r in rs if r<0]
    wr=len(w)/n; lr=len(l)/n
    aw=statistics.fmean(w) if w else 0.0
    al=statistics.fmean([-x for x in l]) if l else 0.0
    sl=sum(-x for x in l)
    return dict(n=n,ev_r=wr*aw-lr*al,win=wr,aw=aw,al=al,
                pf=(sum(w)/sl if sl>0 else None),tot=sum(rs))

blob=json.load(open(BOOK,encoding="utf-8"))
rows=blob["trades"]; meta=blob["meta"]
sessions=meta["sessions"]
traded=[r for r in rows if r["status"]=="fired" and r.get("traded")]
print("traded rows:",len(traded),"sessions:",sessions)

res={n:{"t":[],"reasons":defaultdict(int)} for n,_ in VARIANTS}
nbad=0
for row in traded:
    b=bars_for(row["sym"],row["day"])
    if not b:
        nbad+=1
        for n,_ in VARIANTS: res[n]["reasons"]["bad_bars"]+=1
        continue
    for n,fn in VARIANTS:
        rec,rsn=resim(row,b,fn)
        if rec is None: res[n]["reasons"][rsn]+=1
        else: res[n]["t"].append(rec)
print("bad_bars days:",nbad)
print()
hdr="%-22s %6s %6s %8s %7s %8s %8s %7s %7s"%("variant","n","drop","ev_r","win%","avg_win","avg_loss","stop%","yrR")
print(hdr)
for n,_ in VARIANTS:
    trs=res[n]["t"]; s=sb(trs)
    if not s["n"]:
        print("%-22s %6d %6d  ALL DROPPED"%(n,0,sum(res[n]["reasons"].values()))); continue
    st=100*sum(1 for t in trs if t["out"]=="stop")/s["n"]
    print("%-22s %6d %6d %8.4f %7.1f %8.4f %8.4f %7.1f %7.1f"%(
        n,s["n"],sum(res[n]["reasons"].values()),s["ev_r"],100*s["win"],s["aw"],s["al"],st,
        s["tot"]/sessions*252))
print()
for n,_ in VARIANTS:
    r=res[n]["reasons"]
    if r: print("  %-22s %s"%(n,", ".join("%s=%d"%(k,v) for k,v in sorted(r.items(),key=lambda kv:-kv[1]))))

json.dump({n:{"t":[{k:v for k,v in t.items() if k!="key"} for t in res[n]["t"]],
              "keys":[list(map(str,t["key"])) for t in res[n]["t"]]} for n,_ in VARIANTS},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"adv_out.json"),"w"))
print("\nwrote adv_out.json")
