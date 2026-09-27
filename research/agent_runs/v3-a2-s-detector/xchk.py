import sys, os, json, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s_det as S
P=json.load(open(os.path.join(S.OUT,"best.json")))["best"]; SPLIT=json.load(open(os.path.join(S.OUT,"marks.json")))["split"]
df=pd.read_csv(os.path.join(S.OUT,"..","v3-s-dataset","s_trades.csv"))
for part,sub in (("train",df[df.date<SPLIT]),("held-out",df[df.date>=SPLIT])):
  for g in ("S","one-off","two-off"):
    x=sub[sub.grade==g]; hit=0; n=0
    for _,r in x.iterrows():
        m=int(r.sig_t[:2])*60+int(r.sig_t[3:5])-570; sd=1 if str(r.side).upper().startswith("L") else -1
        fs=S.detect(r.sym,r.date,P); 
        if S.day_bars(r.sym,r.date) is None: continue
        n+=1; hit+= any(abs(f["m"]-m)<=3 and f["side"]==sd for f in fs)
    print(part,g,"n",n,"caught",hit,round(hit/max(n,1),3))
