import sys; sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
import pandas as pd, numpy as np
from omen_data import load_fut, load_proxy, SPEC
for s in ("MES","MNQ"):
    f=load_fut(s,"09:30","11:00"); p=load_proxy(s,"09:30","11:00")
    print(s,"proxy sessions",p["date"].nunique(),p["date"].min(),p["date"].max())
    # fitted ratio
    fo=f[f.ts.dt.strftime("%H:%M")=="09:30"].set_index("date")["open"]
    raw=load_proxy(s,"09:30","09:31",ratio=1.0).set_index("date")["open"]
    r=(fo/raw).dropna(); print(s,"ratio fut/etf n",len(r),"min %.3f med %.3f max %.3f"%(r.min(),r.median(),r.max()))
    m=f.merge(p,on="ts",suffixes=("_f","_p"))
    for c in ("close",):
        rf=m.groupby("date_f")[c+"_f"].diff(); rp=m.groupby("date_f")[c+"_p"].diff()
        ok=rf.notna()&rp.notna()
        print(s,"1m pt-chg corr %.3f"%np.corrcoef(rf[ok],rp[ok])[0,1],"mean|diff| pts %.2f"%(rf[ok]-rp[ok]).abs().mean(),"mean|fut chg| %.2f"%rf[ok].abs().mean(), "bars",int(ok.sum()))
    def orr(d,n):
        g=d[d.ts.dt.strftime("%H:%M")<"09:%02d"%(30+n)].groupby("date"); return (g.high.max()-g.low.min())
    for n in (5,15):
        a=orr(f,n); b=orr(p,n); j=a.index.intersection(b.index)
        print(s,f"OR{n} range pts fut med %.2f proxy med %.2f  |diff| med %.2f  n {len(j)}"%(a[j].median(),b[j].median(),(a[j]-b[j]).abs().median()))
    # break-direction agreement of 9:30-9:35 OR break by 11:00 (first break side)
    def first_break(d):
        out={}
        for dt_,g in d.groupby("date"):
            o=g[g.ts.dt.strftime("%H:%M")<"09:35"]; hi,lo=o.high.max(),o.low.min(); r=g[g.ts.dt.strftime("%H:%M")>="09:35"]
            side=None
            for _,b in r.iterrows():
                if b.close>hi: side="L";break
                if b.close<lo: side="S";break
            out[dt_]=side
        return pd.Series(out)
    a=first_break(f); b=first_break(p); j=a.index.intersection(b.index)
    print(s,"OR5 first-close-break side agree %.1f%%"%(100*(a[j]==b[j]).mean()),"n",len(j))
