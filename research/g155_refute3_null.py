import json,os,sys,random,statistics
from collections import defaultdict
HERE=r"C:/Users/aharg/Desktop/Projects/tradingbot/research"
sys.path.insert(0,os.path.dirname(HERE)); sys.path.insert(0,HERE)
import importlib.util
spec=importlib.util.spec_from_file_location("g154",os.path.join(HERE,"g154_rule_displacement-graded-not-boolean.py"))
g=importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
import marks_pool
from omen_metrics import _row_is_sizeable
blob=json.load(open(g.BOOK_PATH,encoding="utf-8")); rows=blob["trades"]
byday=g.by_day_candidates(rows)
pool=marks_pool.canonical_pool()
s100=g.load_sweep_s_days()
BASE_PREC=30.5; BASE_REC=5.9
def pick(keep):
    out=[]
    for day in sorted(byday):
        for r in byday[day]:
            if _row_is_sizeable(r) is False: continue
            if keep is not None and not keep(r): continue
            out.append(r); break
    return out
def stats(f):
    gs=ga=0
    for r in f:
        e=pool.get("%s_%s"%(r["sym"],r["day"]))
        if e is None: continue
        ga+=1
        if e.grade=="S": gs+=1
    p=round(gs/ga*100,1) if ga else 0.0
    fs=defaultdict(set)
    for r in f: fs[r["day"]].add(r["sym"])
    hit=sum(1 for sym,day in s100 if sym in fs.get(day,()))
    return p, round(hit/len(s100)*100,1), sum(r["pnl"] for r in f)/len({r["day"] for r in f})
random.seed(11)
DROP=0.6712
surv=0; N=400; precs=[]; recs=[]; usds=[]
for i in range(N):
    keeps={id(r):(random.random()>DROP) for v in byday.values() for r in v}
    p,rc,u=stats(pick(lambda r: keeps[id(r)]))
    precs.append(p); recs.append(rc); usds.append(u)
    if p>BASE_PREC and rc>=BASE_REC: surv+=1
print("random-drop null, drop=%.2f%%, N=%d"%(DROP*100,N))
print("  P(survivor by this row's rule) = %.1f%%"%(surv/N*100))
print("  P(precision > 30.5) = %.1f%%   P(recall100 >= 5.9) = %.1f%%"%(
    sum(1 for p in precs if p>BASE_PREC)/N*100, sum(1 for r in recs if r>=BASE_REC)/N*100))
print("  precision null: median %.1f  p95 %.1f  ; observed arm 38.3 -> pctile %.1f%%"%(
    statistics.median(precs), sorted(precs)[int(.95*N)], sum(1 for p in precs if p<38.3)/N*100))
print("  recall100 null: median %.1f  p95 %.1f ; observed 14.7 -> pctile %.1f%%"%(
    statistics.median(recs), sorted(recs)[int(.95*N)], sum(1 for r in recs if r<14.7)/N*100))
print("  $/day null: median %.1f  [p5 %.1f, p95 %.1f] ; observed -36.03 -> pctile %.1f%%"%(
    statistics.median(usds), sorted(usds)[int(.05*N)], sorted(usds)[int(.95*N)],
    sum(1 for u in usds if u<-36.03)/N*100))
# family: 4 thresholds per rule -> P(at least one arm survives) under same null
random.seed(23); fam=0; M=400
for i in range(M):
    ok=False
    for _ in range(4):
        keeps={id(r):(random.random()>DROP) for v in byday.values() for r in v}
        p,rc,u=stats(pick(lambda r: keeps[id(r)]))
        if p>BASE_PREC and rc>=BASE_REC: ok=True; break
    fam+=ok
print("  P(at least 1 of 4 swept thresholds survives) = %.1f%%"%(fam/M*100))
