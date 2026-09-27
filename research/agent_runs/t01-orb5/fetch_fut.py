"""Fetch ES/NQ quarterly contracts 1-min bars from Massive (key from .env, never printed)."""
import json, time, urllib.request, urllib.error, csv, datetime as dt
from pathlib import Path
OUT=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t01-orb5\fut")
OUT.mkdir(exist_ok=True)
key=None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key=l.split("=",1)[1].strip().strip('"')
def third_friday(y,m):
    d=dt.date(y,m,15)
    while d.weekday()!=4: d+=dt.timedelta(1)
    return d
codes={3:"H",6:"M",9:"U",12:"Z"}
qs=[(2024,9),(2024,12)]+[(y,m) for y in (2025,2026) for m in (3,6,9,12)]
def get(u):
    for attempt in range(6):
        try:
            with urllib.request.urlopen(u,timeout=90) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(30); continue
            print("HTTP",e.code,flush=True); return None
        except Exception as e:
            print("err",type(e).__name__,flush=True); time.sleep(20)
    return None
for root in ("ES","NQ"):
    for i,(y,m) in enumerate(qs):
        tk=f"{root}{codes[m]}{y%10}"
        f=OUT/f"{tk}_{y}.csv"
        if f.exists(): continue
        exp=third_friday(y,m)
        pm = m-3 if m>3 else 12; py = y if m>3 else y-1
        start=third_friday(py,pm)-dt.timedelta(21)
        u=f"https://api.massive.com/futures/v1/aggs/{tk}?resolution=1min&window_start.gte={start}&window_start.lt={exp+dt.timedelta(1)}&limit=50000&apiKey={key}"
        rows=[]
        while u:
            d=get(u); time.sleep(13)
            if not d: break
            rows+=d.get("results") or []
            nu=d.get("next_url")
            u=(nu+("&" if "?" in nu else "?")+"apiKey="+key) if nu else None
        with open(f,"w",newline="") as fh:
            w=csv.writer(fh); w.writerow(["ts_ns","open","high","low","close","volume"])
            for r in sorted(rows,key=lambda r:r["window_start"]):
                w.writerow([r["window_start"],r["open"],r["high"],r["low"],r["close"],r["volume"]])
        print(tk,y,start,exp,len(rows),flush=True)
print("DONE",flush=True)
