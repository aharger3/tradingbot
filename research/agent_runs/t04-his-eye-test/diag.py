import os,sys,json,re,collections as C
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0,"research")
import marks_pool as mp, build_deck as bd
TK=["entry_t","entry_time","et","eng_et","entry_et","entry_minute","setup_et","tod"]
IK=["entry_i","eng_entry_i"]
cnt=C.Counter(); ex=[]
for p in bd.mark_sources():
    n=mp._relname(p)
    for r in bd._rows(p):
        k=mp._judgement_key(r); g=mp.row_grade(r)
        if not k or g is None: continue
        t={f:r.get(f) for f in TK if r.get(f) not in (None,"")}
        i={f:r.get(f) for f in IK if r.get(f) not in (None,"")}
        cnt[(n, bool(t), bool(i))]+=1
        if t and i and len(ex)<40: ex.append((n,k,t,i))
for x in sorted(cnt.items()): print(x)
for e in ex: print(e)
