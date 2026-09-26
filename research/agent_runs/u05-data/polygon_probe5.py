import os, json, urllib.request, urllib.error
from pathlib import Path
key=None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key=l.split("=",1)[1].strip().strip('"')
def get(path):
    sep="&" if "?" in path else "?"
    u="https://api.massive.com"+path+sep+"apiKey="+key
    try:
        with urllib.request.urlopen(u,timeout=30) as r: d=json.load(r); return r.status, len(d.get("results") or []), str(d.get("results",""))[:90]+" .. "+str((d.get("results") or [{}])[-1])[:90]
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode()[:160].replace(key,"***")
import time
for t in ["/futures/v1/aggs/ESZ4?resolution=1min&window_start.gte=2024-10-01&window_start.lt=2024-10-02&limit=2000",
          "/futures/v1/aggs/ESU4?resolution=1min&window_start.gte=2024-06-03&window_start.lt=2024-06-04&limit=2000",
          "/futures/v1/aggs/NQZ5?resolution=1min&window_start.gte=2025-10-01&window_start.lt=2025-10-02&limit=2000",
          "/futures/v1/aggs/MNQZ5?resolution=1min&window_start.gte=2025-10-01&window_start.lt=2025-10-02&limit=2000",
          "/futures/v1/aggs/ESZ6?resolution=1min&window_start.gte=2026-09-26&limit=5"]:
    print(t.split("&limit")[0], get(t), flush=True); time.sleep(13)
