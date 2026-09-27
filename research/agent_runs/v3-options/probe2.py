import os, time, requests
K=os.environ["POLYGON_API_KEY"]; B="https://api.polygon.io"
def g(path, **p):
    time.sleep(13); p["apiKey"]=K; r=requests.get(B+path, params=p, timeout=30)
    try: j=r.json()
    except Exception: j={}
    return r.status_code, j
for path, p in [("/v2/aggs/ticker/O:SPY240927C00572000/range/1/minute/2024-09-27/2024-09-27", {}),
                ("/v2/aggs/ticker/O:SPY241001C00570000/range/1/minute/2024-10-01/2024-10-01", {}),
                ("/v2/aggs/ticker/SPY/range/1/minute/2024-09-27/2024-09-27", {}),
                ("/v3/snapshot/options/SPY/O:SPY260925C00765000", {}),
                ("/v2/aggs/ticker/I:SPX/range/1/minute/2026-09-24/2026-09-24", {}),
                ("/v2/aggs/ticker/O:SPY260925C00765000/range/1/minute/2026-09-25/2026-09-25", {}),
                ("/v2/aggs/ticker/O:SPY260925C00765000/range/1/second/2026-09-25/2026-09-25", {"limit":10})]:
    c,j=g(path, **p); print(path.split("?")[0], c, j.get("resultsCount"), str(j.get("message",""))[:100], flush=True)
