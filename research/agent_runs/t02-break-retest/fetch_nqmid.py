# Fetch ES/NQ 1-min bars per contract per month from Massive futures aggs. Key never printed.
import json, urllib.request, urllib.error, time, gzip, os, sys
from pathlib import Path
from datetime import date
OUT=Path(__file__).parent/"bars"; OUT.mkdir(exist_ok=True)
key=None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key=l.split("=",1)[1].strip().strip('"')
Q={3:"H",6:"M",9:"U",12:"Z"}
def contracts_for(y,m):
    # front quarterly contract for month (y,m); in a quarter month also the next one
    qm=next(q for q in (3,6,9,12) if q>=m) if m<=12 else None
    cs=[(y,qm)]
    if m in Q:
        ny,nm=(y,m+3) if m<12 else (y+1,3)
        cs.append((ny,nm))
    return cs
def get(u):
    u=u+"&apiKey="+key
    for attempt in range(8):
        try:
            with urllib.request.urlopen(u,timeout=90) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(30); continue
            return {"error":e.code}
        except Exception as e:
            time.sleep(15)
    return {"error":"retries"}
months=[]
y,m=2024,9
while (y,m)<=(2026,9):
    months.append((y,m)); m+=1
    if m==13: y,m=y+1,1
for root in ("NQ",):
    for (y,m) in [x for x in months if x>=(2025,6)]:
        for (cy,cm) in contracts_for(y,m):
            tk=f"{root}{Q[cm]}{str(cy)[-1]}"
            fn=OUT/f"{root}_{tk}_{y}-{m:02d}.json.gz"
            if fn.exists(): continue
            s=date(y,m,1); e=date(y+(m==12), (m%12)+1, 1)
            d=get(f"https://api.massive.com/futures/v1/aggs/{tk}?resolution=1min&window_start.gte={s}&window_start.lt={e}&limit=50000")
            n=len(d.get("results") or [])
            print(root,tk,y,m,n,d.get("error",""),("NEXT" if d.get("next_url") else ""),flush=True)
            if "error" not in d:
                rows=[[r["window_start"],r["open"],r["high"],r["low"],r["close"],r["volume"]] for r in d.get("results") or []]
                with gzip.open(fn,"wt") as f: json.dump({"ticker":tk,"rows":rows},f)
            time.sleep(12.5)
print("DONE")
