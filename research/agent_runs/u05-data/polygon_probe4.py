import os, json, urllib.request, urllib.error
from pathlib import Path
key=None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key=l.split("=",1)[1].strip().strip('"')
def get(path):
    sep="&" if "?" in path else "?"
    u="https://api.massive.com"+path+sep+"apiKey="+key
    try:
        with urllib.request.urlopen(u,timeout=30) as r: d=json.load(r); return r.status, d.get("resultsCount", d.get("count")), str(d.get("results",""))[:120]
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode()[:160].replace(key,"***")
import time
for t in ["/futures/v1/aggs/ESZ6?resolution=1min&limit=3","/futures/v1/aggs/MESZ6?resolution=1min&window_start.gte=2025-01-02&limit=3","/futures/v1/aggs/ESH5?resolution=1min&window_start=2024-10-01&limit=3"]:
    print(t, get(t), flush=True); time.sleep(13)
