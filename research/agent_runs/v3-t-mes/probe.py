import os, json, urllib.request
k=os.environ.get("POLYGON_API_KEY") or os.environ.get("MASSIVE_API_KEY")
print("key?", bool(k))
for d in ("2019-09-03","2021-03-01"):
    u=f"https://api.polygon.io/v2/aggs/ticker/SPY/range/1/minute/{d}/{d}?adjusted=false&sort=asc&limit=50000&apiKey={k}"
    try:
        j=json.load(urllib.request.urlopen(u,timeout=30)); print(d, j.get("status"), j.get("resultsCount"), (j.get("results") or [{}])[0])
    except Exception as e: print(d,"ERR",str(e)[:200])
