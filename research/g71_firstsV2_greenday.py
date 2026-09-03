"""G7.1 adversarial verify of track `firsts` green-day claim.

Reproduces P3/P4/P0seq/P0 green-day share off research/bt2y_trades.json, then
runs three controls the original did not:
  A. within-day order shuffle  -- does green share survive destroying order?
  B. R-permutation null book   -- reassign every row's r from a global shuffle,
                                 destroying all signal identity. If P3 still
                                 beats P0seq on green days, the gap is the
                                 arithmetic of the stopping rule, not an edge.
  C. matched-count control     -- take exactly len(P3_taken[d]) trades per day,
                                 first-k, non-adaptive. Isolates "fewer trades"
                                 from "stop when green".
Plus risk-normalised drawdown (return over max DD) for every arm.
"""
import json, random, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ekey = lambda r: (r["entry_i"], r["et"], r["sym"])
xkey = lambda r: (r["entry_i"] + r["bars"], r["et"], r["sym"])

def walk(cands, decide):
    taken, free = [], None
    w = l = s = 0; cum = 0.0
    for c in cands:
        if decide((len(taken), w, l, s, cum)): break
        if free is not None and ekey(c) < free: continue
        taken.append(c); free = xkey(c)
        o = c["out"]
        if o == "win": w += 1
        elif o == "loss": l += 1
        else: s += 1
        cum += c["r"]
    return taken

P_GREEN  = lambda s: s[4] > 0
P_GREEN3 = lambda s: s[4] > 0 or s[2] >= 3
P_NONE   = lambda s: False

book = json.loads((ROOT/"research/bt2y_trades.json").read_text(encoding="utf-8"))
trades = book["trades"]; meta = book["meta"]
counted = [r for r in trades if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
shipped = [r for r in trades if r["traded"]]
by_day = defaultdict(list)
for r in counted: by_day[r["day"]].append(r)
for d in by_day: by_day[d].sort(key=ekey)
all_days = sorted(by_day)

def dd(day_r):
    cum=peak=mx=0.0
    for d in all_days:
        cum += day_r.get(d,0.0); peak=max(peak,cum); mx=max(mx,peak-cum)
    return mx

def rep(name, taken):
    day_r = {d: sum(x["r"] for x in rs) for d,rs in taken.items() if rs}
    n = sum(len(v) for v in taken.values())
    tot = sum(day_r.values()); D = dd(day_r)
    g = sum(1 for v in day_r.values() if v>0)
    mon=defaultdict(float)
    for d,v in day_r.items(): mon[d[:7]]+=v
    months=sorted({d[:7] for d in all_days})
    return dict(arm=name, trades=n, days=len(day_r), green=g,
                green_pct=round(100*g/len(day_r),1),
                tpd=round(n/len(day_r),2), totalR=round(tot,1),
                meanR=round(tot/n,4) if n else 0, maxDD=round(D,2),
                RoMaD=round(tot/D,1) if D else 0,
                DD_pct_of_total=round(100*D/tot,2) if tot else 0,
                months_green=sum(1 for m in months if mon.get(m,0.0)>0),
                months=len(months))

grp = lambda rows: {d:[r for r in rows if r["day"]==d] for d in {x["day"] for x in rows}}
sh = defaultdict(list)
for r in shipped: sh[r["day"]].append(r)

base = {}
base["P0 shipped"]  = rep("P0 shipped", dict(sh))
base["P0seq ctrl"]  = rep("P0seq ctrl", {d: walk(rs, P_NONE) for d,rs in by_day.items()})
p3 = {d: walk(rs, P_GREEN) for d,rs in by_day.items()}
base["P3 green"]    = rep("P3 green", p3)
base["P4 green/3L"] = rep("P4 green/3L", {d: walk(rs, P_GREEN3) for d,rs in by_day.items()})

print("=== REPRODUCTION + risk-normalised DD ===")
hdr = "%-13s %6s %5s %6s %7s %6s %8s %8s %7s %7s %8s %6s"
print(hdr % ("arm","trades","days","green","green%","t/day","totalR","meanR","maxDD","RoMaD","DD%tot","mo"))
for k,v in base.items():
    print("%-13s %6d %5d %6d %6.1f%% %6.2f %8.1f %8.4f %7.2f %7.1f %7.2f%% %2d/%d"
          % (v["arm"],v["trades"],v["days"],v["green"],v["green_pct"],v["tpd"],
             v["totalR"],v["meanR"],v["maxDD"],v["RoMaD"],v["DD_pct_of_total"],
             v["months_green"],v["months"]))

# ---- control C: matched trade count, non-adaptive first-k
mc = {}
for d,rs in by_day.items():
    k = len(p3[d]); taken=[]; free=None
    for c in rs:
        if len(taken)>=k: break
        if free is not None and ekey(c)<free: continue
        taken.append(c); free=xkey(c)
    mc[d]=taken
print("\n=== CONTROL C: matched trades/day, NO green stop rule ===")
v = rep("C matched-k", mc)
print(json.dumps(v))

# ---- control A: within-day order shuffle, P3 re-run
rng = random.Random(7)
def shuffled_run(seed, permute_r=False):
    r2 = random.Random(seed)
    if permute_r:
        pool = [x["r"] for x in counted]; outs=[x["out"] for x in counted]
        r2.shuffle(pool); r2.shuffle(outs)
        i=0; fake={}
        for d in all_days:
            rows=[]
            for c in by_day[d]:
                c2=dict(c); c2["r"]=pool[i]; c2["out"]=outs[i]; i+=1
                rows.append(c2)
            fake[d]=rows
        src=fake
    else:
        src={d: r2.sample(by_day[d], len(by_day[d])) for d in all_days}
        for d in src: src[d].sort(key=lambda r:(r["entry_i"],))  # keep time order legal
        src={d: r2.sample(by_day[d], len(by_day[d])) for d in all_days}
    return src

print("\n=== CONTROL A: within-day ORDER shuffled (30 seeds), P3 ===")
gs=[]
for s in range(30):
    src = shuffled_run(s, permute_r=False)
    t = {d: walk(rs, P_GREEN) for d,rs in src.items()}
    gs.append(rep("x",t)["green_pct"])
print("P3 green%% shuffled: mean %.1f  min %.1f  max %.1f  (actual 78.6)"
      % (statistics.fmean(gs), min(gs), max(gs)))

print("\n=== CONTROL B: R-PERMUTATION NULL BOOK (30 seeds) ===")
p3g=[]; sqg=[]; p3dd=[]; sqdd=[]; p4dd=[]
for s in range(30):
    src = shuffled_run(1000+s, permute_r=True)
    a = rep("x", {d: walk(rs, P_GREEN) for d,rs in src.items()})
    b = rep("x", {d: walk(rs, P_NONE)  for d,rs in src.items()})
    c = rep("x", {d: walk(rs, P_GREEN3) for d,rs in src.items()})
    p3g.append(a["green_pct"]); sqg.append(b["green_pct"])
    p3dd.append(a["maxDD"]); sqdd.append(b["maxDD"]); p4dd.append(c["maxDD"])
print("null-book P3 green%%   mean %.1f (actual 78.6)" % statistics.fmean(p3g))
print("null-book P0seq green%% mean %.1f (actual 63.5)" % statistics.fmean(sqg))
print("null-book gap %.1f pp  (actual gap %.1f pp)"
      % (statistics.fmean(p3g)-statistics.fmean(sqg), 78.6-63.5))
print("null-book maxDD  P3 %.1f  P4 %.1f  P0seq %.1f (actual 15.9/12.9/27.8)"
      % (statistics.fmean(p3dd), statistics.fmean(p4dd), statistics.fmean(sqdd)))

out = {"base": base, "matched_k": v,
       "shuffle_order_p3_green_pct": {"mean": statistics.fmean(gs), "min": min(gs), "max": max(gs)},
       "null_book": {"p3_green_pct": statistics.fmean(p3g), "p0seq_green_pct": statistics.fmean(sqg),
                     "p3_dd": statistics.fmean(p3dd), "p4_dd": statistics.fmean(p4dd),
                     "p0seq_dd": statistics.fmean(sqdd)},
       "book_meta": meta}
(ROOT/"research/g71_firstsV2_greenday.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
