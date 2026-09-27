import json,glob,numpy as np
for f in sorted(glob.glob("trades_*.json")):
    T=json.load(open(f)); R=np.array([t["R"] for t in T])
    if not len(R): continue
    t=R.mean()/(R.std(ddof=1)/np.sqrt(len(R)))
    rng=np.random.default_rng(1); bs=[rng.choice(R,len(R)).mean() for _ in range(2000)]
    mo={}
    for x in T: mo[x["date"][:7]]=mo.get(x["date"][:7],0)+x["R"]
    g=sum(v>0 for v in mo.values())
    print(f[7:-5], len(R), round(t,2), np.round(np.percentile(bs,[2.5,97.5]),3), f"{g}/{len(mo)}", round(R.sum()*200/501,1))
