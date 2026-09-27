import sys; sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
import pandas as pd
from omen_data import load_fut
f=load_fut("MES"); n=f.groupby("date").size()
d=pd.to_datetime(pd.Series(n.index))
print("weekend",int((d.dt.weekday>=5).sum()))
low=n[n<380]; print("RTH<380:",", ".join(f"{k}:{v}" for k,v in low.items()))
print("contracts:", f.groupby("contract").date.agg(["min","max","count"]).to_string())
