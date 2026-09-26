import json,gzip,os,sys,inspect
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0,"research"); sys.path.insert(0,".")
import marks_pool as mp
print(inspect.signature(mp.canonical_pool)); 
src=inspect.getsource(mp.canonical_pool); print(src[:1500])
pool=mp.canonical_pool()
print(type(pool), len(pool))
it=list(pool.items())[:3] if isinstance(pool,dict) else pool[:3]
print(it)
for f in ["research/tape/r2ref_simd_next_open_blind2r_real_engine.json.gz","research/tape/baseline_2026-09-13.json.gz"]:
    d=json.load(gzip.open(f))
    print(f,type(d), list(d.keys())[:20] if isinstance(d,dict) else len(d))
    tr=d.get("trades",d) if isinstance(d,dict) else d
    if isinstance(tr,dict): print(list(tr.keys())[:10]); 
    else:
        print(len(tr)); print(json.dumps(tr[0],default=str)[:2500])
