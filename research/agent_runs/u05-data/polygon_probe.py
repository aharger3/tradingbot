import os, json, urllib.request, urllib.error
from pathlib import Path
key=None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key=l.split("=",1)[1].strip().strip('"')
def get(path):
    sep="&" if "?" in path else "?"
    u="https://api.polygon.io"+path+sep+"apiKey="+key
    try:
        with urllib.request.urlopen(u,timeout=30) as r: d=json.load(r); return r.status, d.get("resultsCount", d.get("count")), str(d.get("results",""))[:120]
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode()[:160].replace(key,"***")
tests=["/v2/aggs/ticker/SPY/range/1/minute/2021-10-01/2021-10-01",
"/v2/aggs/ticker/SPY/range/1/minute/2020-10-01/2020-10-01",
"/v2/aggs/ticker/SPY/range/1/minute/2016-10-03/2016-10-03",
"/v2/aggs/ticker/SPY/range/1/minute/2026-09-25/2026-09-25",
"/v2/aggs/ticker/SPY/range/1/minute/2026-09-26/2026-09-26",
"/v3/trades/SPY?limit=1&timestamp=2026-09-24",
"/futures/vX/aggs/ESZ6?resolution=1min&window_start.gte=2026-09-24&limit=5",
"/futures/vX/contracts?product_code=ES&limit=2",
"/futures/vX/products?limit=2",
"/v2/aggs/ticker/I:SPX/range/1/minute/2026-09-24/2026-09-24",
"/v2/aggs/ticker/I:NDX/range/1/minute/2026-09-24/2026-09-24",
]
for t in tests: print(t.split("?")[0], get(t))
