import sys, pandas as pd
from pathlib import Path
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
import omen_data as od
H = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s11-other-indices")
m = pd.read_csv(H/"fut"/"snap_MYMZ6.csv"); m["ts"]=pd.to_datetime(m.ts_ns,unit="ns",utc=True).dt.tz_convert("America/New_York")
t=m.ts.dt.strftime("%H:%M"); w=m[(t>="09:30")&(t<"11:00")]
print("MYM 9/24 0930-1100 vol", int(w.volume.sum()), "bars", len(w), "zero-vol bars", int((w.volume==0).sum()), "med/min", int(w.volume.median()))
for s in ("MES","MNQ"):
    d=od.load_fut(s,"09:30","11:00"); x=d[d.date.astype(str)=="2026-09-24"]
    print(s[1:], "9/24 0930-1100 vol", int(x.volume.sum()), "med/min", int(x.volume.median()))
    g=d.groupby("date"); print(s[1:], "median 0930-1100 vol (all sessions)", int(g.volume.sum().median()))
ARC=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\data_archive")
for e in ("SPY","QQQ","IWM"):
    ps=[pd.read_csv(f) for f in sorted((ARC/e).glob("2025-*.csv"))+sorted((ARC/e).glob("2026-*.csv"))]
    d=pd.concat([p for p in ps if not p.empty]); d["ts"]=pd.to_datetime(d.Datetime,utc=True,format="ISO8601").dt.tz_convert("America/New_York")
    d["date"]=d.ts.dt.date; t=d.ts.dt.strftime("%H:%M"); w=d[(t>="09:30")&(t<"11:00")]; o=w[w.ts.dt.strftime("%H:%M")<"09:35"]
    a=o.groupby("date").agg(H=("High","max"),L=("Low","min"),O=("Open","first")); b=w.groupby("date").agg(H=("High","max"),L=("Low","min"),O=("Open","first"))
    orb=((a.H-a.L)/a.O*100); rng=((b.H-b.L)/b.O*100)
    # share of days price breaks OR5 before 10:30 and trades back to the level within 10 bars (retest opportunity)
    print(e, "days", len(a), "OR5 %med", round(orb.median(),3), "0930-1100 range %med", round(rng.median(),3), "range/OR5", round((rng/orb).median(),2))
