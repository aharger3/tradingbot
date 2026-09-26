import os,sys,json,gzip,collections as C
ROOT=r"C:\Users\aharg\Desktop\Projects\tradingbot"; os.chdir(ROOT); sys.path.insert(0,"research")
import marks_pool as mp, build_deck as bd
B=json.load(gzip.open("research/tape/baseline_2026-09-13.json.gz"))
print(B.keys() if isinstance(B,dict) else type(B))
T=B["trades"]; print(len(T)); print(json.dumps(T[0],default=str)[:1500])
print(C.Counter(t.get("setup") for t in T).most_common(20))
n=0; fc=C.Counter(); gs=C.Counter(); syms=C.Counter()
for p in bd.mark_sources():
    for r in bd._rows(p):
        g=mp.row_grade(r); k=mp._judgement_key(r)
        if g is None or not k: continue
        gs[str(g)]+=1; fc.update(r.keys()); syms[k.split("_")[0]]+=1
        if str(g)=="S" and n<4: print(mp._relname(p), json.dumps(r,default=str)[:900]); n+=1
print(gs); print(syms.most_common(25)); print(fc.most_common(80))
