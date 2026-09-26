import json, urllib.request, urllib.error, time
from pathlib import Path
key=None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key=l.split("=",1)[1].strip().strip('"')
def get(u):
    u=u+("&" if "?" in u else "?")+"apiKey="+key
    try:
        with urllib.request.urlopen(u,timeout=60) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300].replace(key,"***")
s,d=get("https://api.massive.com/futures/v1/aggs/ESZ5?resolution=1min&window_start.gte=2025-10-01&window_start.lt=2025-11-01&limit=50000")
print(s)
if isinstance(d,dict):
    print({k:(v if k!="results" else len(v)) for k,v in d.items() if k!="next_url"}, "next_url" in d and bool(d["next_url"]))
    r=d.get("results") or []
    print(r[:2]); print(r[-1:])
else: print(d)
