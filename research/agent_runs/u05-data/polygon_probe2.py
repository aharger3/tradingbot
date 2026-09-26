import os, json, urllib.request, urllib.error
from pathlib import Path
key=None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key=l.split("=",1)[1].strip().strip('"')
def get(path):
    sep="&" if "?" in path else "?"
    u=(path.startswith("M")and"https://api.massive.com"+path[1:] or "https://api.polygon.io"+path)+sep+"apiKey="+key
    try:
        with urllib.request.urlopen(u,timeout=30) as r: d=json.load(r); return r.status, d.get("resultsCount", d.get("count")), str(d.get("results",""))[:120]
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode()[:160].replace(key,"***")
tests=[f"/v2/aggs/ticker/SPY/range/1/minute/{d}/{d}" for d in ["2023-09-26","2023-12-01","2024-01-02","2024-06-03","2024-09-26","2024-09-27","2024-10-01"]]+[
"M/futures/vX/aggs/ESZ6?resolution=1min&limit=3",
"M/futures/vX/aggs/ESZ5?resolution=1min&limit=3",
"M/futures/vX/products?limit=2",
"/v2/aggs/ticker/I:SPX/range/1/day/2026-09-24/2026-09-24",
"/v2/aggs/ticker/I:NDX/range/1/minute/2024-01-02/2024-01-02",
"/v2/aggs/ticker/SPY/range/1/day/2016-10-03/2016-10-03",
]
for t in tests: print(t.split("?")[0], get(t))
