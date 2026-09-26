import json,os,sys,collections as C
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0,"research")
import build_deck as bd, marks_pool as mp
srcs=bd.mark_sources(); print(len(srcs))
fc=C.Counter()
for p in srcs:
    p=str(p)
    try:
        if p.endswith(".jsonl"): rows=[json.loads(l) for l in open(p,encoding="utf-8") if l.strip()]
        else:
            d=json.load(open(p,encoding="utf-8")); rows=d if isinstance(d,list) else (list(d.values()) if isinstance(d,dict) else [])
    except Exception as e: print("ERR",p,e); continue
    ks=C.Counter()
    for r in rows:
        if isinstance(r,dict):
            for k in r: ks[k]+=1
            if isinstance(r.get("answers"),dict):
                for k in r["answers"]: ks["answers."+k]+=1
    print(os.path.basename(p), len(rows), [k for k,_ in ks.most_common(40)])
