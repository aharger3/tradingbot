import json, urllib.request, urllib.error
from pathlib import Path
key=None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key=l.split("=",1)[1].strip().strip('"')
u="https://api.massive.com/futures/v1/aggs/ESZ5?resolution=1min&window_start.gte=2025-09-10&window_start.lt=2025-12-20&limit=50000&apiKey="+key
try:
    with urllib.request.urlopen(u,timeout=60) as r: d=json.load(r)
    res=d.get("results") or []
    print(r.status,len(res),{k:(v if k!="results" else None) for k,v in d.items() if k!="next_url"}, "next_url" in d)
    print(res[0]); print(res[-1])
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode()[:200].replace(key,"***"))
