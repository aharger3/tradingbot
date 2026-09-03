"""Adversarial recompute of g113 ladder_shapes. Independent bar-walk."""
import json, os, sys, statistics
ROOT = r"C:\Users\aharg\Desktop\Projects\tradingbot"
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT,"research"))
import g86_honest_ceiling as g86
import g97_mfe as g97
import g101_open_and_ladder as g101
import signal_runner as sr
from research import g80_ordertype_grid as G
import omen_metrics as om

BOOK = os.path.join(ROOT,"research","bt2y_trades_retest_on.json")
WIN_END = "11:00:00"

SHAPES = {
 "one_target": ((1.0,), 0.0),
 "50/50": ((.5,.5), 0.0),
 "30/30/30/10": ((.3,.3,.3,.1), 0.0),
 "50/20/20/10": ((.5,.2,.2,.1), 0.0),
 "25/25/25/25": ((.25,)*4, 0.0),
 "20/20/20/40P": ((.2,.2,.2,.4), 0.0),
 "20/20/20+40run": ((1/3,1/3,1/3), 0.40),
}

def my_walk(entry, stop, long, i, bars, rungs, runner_w):
    """Independent re-implementation of the documented rules:
       - walk bars i+1.. up to 11:00
       - before any scale-out: level stop rests at `stop`, fills on intrabar TOUCH at `stop` (-1R)
       - a bar that touches a rung AND touches the stop -> STOP (house rule)
       - after first fill: stop moves to entry (breakeven), triggers on CLOSE through entry,
         fills at that close clamped to entry-1.25R
       - leftover at 11:00 exits at last close
    """
    risk = abs(entry-stop); sign = 1.0 if long else -1.0
    scale = 1.0 - runner_w
    rem = 1.0; fills=[]; filled=set(); be=False; last_close=entry
    for c in bars[i+1:]:
        if c.timestamp > WIN_END: break
        last_close = c.close
        if not be:
            # level stop, touch
            if (c.low <= stop) if long else (c.high >= stop):
                fills.append((rem, stop)); rem=0.0; break
        touched = [k for k,r in enumerate(rungs) if k not in filled and
                   ((c.high >= r.price) if long else (c.low <= r.price))]
        if be:
            if (c.close <= entry) if long else (c.close >= entry):
                px = max(c.close, entry-1.25*risk) if long else min(c.close, entry+1.25*risk)
                if touched: px = min(px, entry) if long else max(px, entry)
                fills.append((rem, px)); rem=0.0; break
        if touched:
            for k in sorted(touched, key=lambda j: rungs[j].price if long else -rungs[j].price):
                r = rungs[k]; filled.add(k)
                fills.append((r.weight*scale, r.price)); rem -= r.weight*scale
            be = True
            if len(filled)==len(rungs) and rem <= 1e-9:
                rem = 0.0; break
    if rem > 1e-9: fills.append((rem, last_close))
    return sum(w*sign*(px-entry)/risk for w,px in fills)

def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    rows_all = b["trades"] if isinstance(b, dict) else b
    byday = g86.candidates(rows_all)
    firsts = [byday[d][0] for d in sorted(byday) if byday[d]]
    out = {"shipped": []}
    for k in SHAPES: out[k]=[]
    out2 = {k+"_mine": [] for k in SHAPES}
    rungcount = []
    days=[]
    ngate=0; nobars=0
    for r in firsts:
        entry, stop = r["entry"], r["stop"]; risk=abs(entry-stop)
        if risk < sr.min_risk_floor(entry): ngate+=1; continue
        bars,pdh,pdl,pmh,pml = G.day_pack(r["sym"], r["day"])
        i = r.get("entry_i")
        if not bars or i is None or i>=len(bars): nobars+=1; continue
        long = r["dir"]=="call"
        if g97.walk(r,bars) is None: ngate+=1; continue
        extreme = (max(c.high for c in bars[:i+1]) if long else min(c.low for c in bars[:i+1]))
        named = ({"PDH":pdh,"PMH":pmh} if long else {"PDL":pdl,"PML":pml})
        days.append(r["day"])
        out["shipped"].append(r["r"])
        full = g101.build_rungs(entry,stop,long,extreme,named,(.25,.25,.25,.25),"4")
        rungcount.append((len(full), [x.name for x in full]))
        for lbl,(w,rw) in SHAPES.items():
            rungs = g101.build_rungs(entry,stop,long,extreme,named,w,"4")
            fills = g101.walk_ladder(r,bars,rungs,trail="be",runner_w=rw)
            out[lbl].append(g101.r_of(fills,entry,stop,long))
            out2[lbl+"_mine"].append(my_walk(entry,stop,long,i,bars,rungs,rw))
    n=len(days)
    print("n=%d gated=%d nobars=%d" % (n,ngate,nobars))
    from collections import Counter
    print("rung-count distribution:", Counter(c for c,_ in rungcount))
    print("nearest-rung name when 1 rung used:", Counter(nm[0] for _,nm in rungcount if nm))
    print()
    print("%-18s %9s %9s %9s %8s" % ("arm","EV/R g113","EV/R mine","maxDD_R","totR"))
    for lbl in SHAPES:
        a = out[lbl]; m = out2[lbl+"_mine"]
        ev = lambda v: om.ev_r_scoreboard(v, size_gate=False)["ev_r"]
        dd = om.ev_r_scoreboard(a, size_gate=False)["max_drawdown_R"]
        maxdiff = max(abs(x-y) for x,y in zip(a,m))
        print("%-18s %+9.4f %+9.4f %9.3f %8.2f  maxrowdiff=%.6f" % (lbl, ev(a), ev(m), dd, sum(a), maxdiff))
    print("shipped EV/R", om.ev_r_scoreboard(out["shipped"], size_gate=False)["ev_r"])
    # year split
    print("\n--- year split (H1 = first 222 sessions, H2 = rest) ---")
    cut = n//2
    print("H1 days %s..%s ; H2 %s..%s" % (days[0],days[cut-1],days[cut],days[-1]))
    print("%-18s %9s %9s %9s" % ("arm","EV/R H1","EV/R H2","totR H2"))
    for lbl in list(SHAPES)+["shipped"]:
        a = out[lbl]
        e1 = om.ev_r_scoreboard(a[:cut], size_gate=False)["ev_r"]
        e2 = om.ev_r_scoreboard(a[cut:], size_gate=False)["ev_r"]
        print("%-18s %+9.4f %+9.4f %+9.2f" % (lbl,e1,e2,sum(a[cut:])))
    # calendar year
    print("\n--- by calendar year ---")
    for lbl in list(SHAPES)+["shipped"]:
        a=out[lbl]
        per={}
        for d,v in zip(days,a): per.setdefault(d[:4],[]).append(v)
        print("%-18s %s" % (lbl, "  ".join("%s: n=%d EV=%+.4f sum=%+.1fR"%(y,len(v),statistics.fmean(v),sum(v)) for y,v in sorted(per.items()))))
    json.dump({"days":days, **{k:out[k] for k in out}}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"adv113_rows.json"),"w"))
    print("\nwrote adv113_rows.json")

main()
