import pickle, numpy as np, statistics
d=pickle.load(open("zz_tl.pkl","rb")); store=d["store"]; base=d["base"]; days=[m[0] for m in d["meta"]]
rng=np.random.default_rng(7)
print("%-5s %9s %9s %8s %8s   %s"%("tol","d_vs_2R","bootP","permP","Y1/Y2 sign","note"))
for tol in [round(0.05*k,2) for k in range(1,11)]:
    lv=np.array(store[tol][0]); df=lv-np.array(base)
    obs=df.mean()
    # bootstrap two-sided p
    m=rng.integers(0,len(df),size=(20000,len(df))); bm=df[m].mean(axis=1)
    bp=2*min((bm<=0).mean(),(bm>=0).mean())
    # sign-flip permutation (paired)
    s=rng.choice([-1.0,1.0],size=(20000,len(df))); pm=(df*s).mean(axis=1)
    pp=(np.abs(pm)>=abs(obs)).mean()
    y1=df[[i for i,a in enumerate(days) if a<"2025-09-01"]].mean()
    y2=df[[i for i,a in enumerate(days) if a>="2025-09-01"]].mean()
    print("%-5.2f %+9.4f %9.3f %8.3f  %+.4f/%+.4f  %s"%(tol,obs,bp,pp,y1,y2,
      "both-year positive" if y1>0 and y2>0 else "sign flips across years"))
