import sys,datetime as d
sys.path.insert(0,r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
from omen_data import load_fut
f=load_fut("MES");print("2025-01-09 in:",d.date(2025,1,9) in set(f.date), "n", f.date.nunique())
