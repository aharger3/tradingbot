import sys, random, numpy as np, pandas as pd
sys.argv=["x"]
import importlib.util
spec=importlib.util.spec_from_file_location("t",r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t03-one-candle\t03_ocr.py"); t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
days=t.load("ES"); data={d:(lambda p:(p,t.mirror(p)))(t.prep(x)) for d,x in days.items()}
rng=random.Random(1)
for R in (3.0,5.5,10.0):
  for side in (0,1):
    acc=[];kinds={}
    for d,(pL,pS) in data.items():
        p=(pL,pS)[side]
        idx=[i for i,x in enumerate(p["hm"]) if "09:31"<=x<="10:30"]
        for _ in range(3):
            i=rng.choice(idx); ent=p["o"][i+1]+t.TICK
            r=t.simulate(p,i+1,ent-R,3,entry=ent)
            if r is None: continue
            e,x,RR,k=r; kinds[k]=kinds.get(k,0)+1
            acc.append(((x-e)*5-t.COMM)/(RR*5))
    print("R",R,"side","LS"[side],"n",len(acc),"meanR",round(np.mean(acc),3),kinds)
