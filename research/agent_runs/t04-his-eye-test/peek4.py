import json,gzip,os,sys,collections as C
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0,"research")
import marks_pool as mp
pool=mp.canonical_pool()
r2=json.load(gzip.open("research/tape/r2ref_simd_next_open_blind2r_real_engine.json.gz"))
print(json.dumps(r2["meta"],default=str)[:1500])
T=r2["trades"]
print(C.Counter(t["filled"] for t in T), C.Counter(t["outcome"] for t in T).most_common(8))
days=sorted({t["day"] for t in T}); print(days[0],days[-1],len(days)); syms=sorted({t["sym"] for t in T}); print(len(syms),syms)
pd=sorted(v.date for v in pool.values()); print("marks",pd[0],pd[-1])
psyms=C.Counter(v.symbol for v in pool.values()); print(psyms.most_common(50))
keys={t["sym"]+"_"+t["day"] for t in T}
g=C.Counter(); 
for k,v in pool.items(): g[(v.grade, k in keys, days[0]<=v.date<=days[-1])]+=1
for x in sorted(g.items()): print(x)
b=json.load(gzip.open("research/tape/baseline_2026-09-13.json.gz"))
print(json.dumps(b["meta"],default=str)[:1500])
B=b["trades"]; print(C.Counter(t["status"] for t in B).most_common(), C.Counter(t["traded"] for t in B))
bd=sorted({t["day"] for t in B}); print(bd[0],bd[-1],len(bd), len({t["sym"] for t in B}))
print(C.Counter(t["setup"] for t in B), C.Counter(t["grade"] for t in B))
bk={t["sym"]+"_"+t["day"] for t in B}
g=C.Counter()
for k,v in pool.items(): g[(v.grade, k in bk)]+=1
print(sorted(g.items()))
# join r2 to baseline
bi={(t["sym"],t["day"],t["et"],t["dir"]):t for t in B}
hit=0
for t in T[:2000]:
    hh,mm=map(int,t["entry_time"].split(":")[:2])
    for d in (0,-1,1):
        m=hh*60+mm+d; key=(t["sym"],t["day"],f"{m//60:02d}:{m%60:02d}",t["side"])
        if key in bi: hit+=1;break
print("join",hit,"/2000")
print(C.Counter(t["side"] for t in T), C.Counter(t["setup"] for t in T))
