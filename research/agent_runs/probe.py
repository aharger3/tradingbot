import os, time, json, requests
K=os.environ["POLYGON_API_KEY"]; B="https://api.polygon.io"
S=requests.Session()
def g(path, **p):
    p["apiKey"]=K
    t=time.time(); r=S.get(B+path, params=p, timeout=30)
    try: j=r.json()
    except Exception: j={}
    return r.status_code, j, round(time.time()-t,2)
def contracts(u, exp, ctype=None):
    p=dict(underlying_ticker=u, expiration_date=exp, limit=1000, expired="true")
    if ctype: p["contract_type"]=ctype
    c,j,_=g("/v3/reference/options/contracts", **p)
    return c, j.get("results",[]) if isinstance(j,dict) else []
print("== contracts by underlying/expiry ==")
for u in ["SPY","QQQ","SPX","SPXW","I:SPX"]:
    for exp in ["2026-09-24","2024-09-24","2023-09-22","2022-09-23","2021-09-24","2019-09-20"]:
        c,res=contracts(u,exp)
        roots=sorted(set(x["ticker"][2:].rstrip("0123456789CP")[:-6] for x in res))[:4] if res else []
        print(u,exp,c,len(res),roots)
print("== minute aggs depth ==")
tests=[("O:SPY260924C00764000","2026-09-24"),("O:SPY240924C00570000","2024-09-24"),("O:SPY230922C00435000","2023-09-22"),
       ("O:SPY220923C00370000","2022-09-23"),("O:SPY210924C00445000","2021-09-24"),("O:SPY200918C00335000","2020-09-18"),
       ("O:SPY190920C00300000","2019-09-20"),("O:SPXW260924C06620000","2026-09-24"),("O:SPX260918C06600000","2026-09-18")]
for t,d in tests:
    c,j,s=g(f"/v2/aggs/ticker/{t}/range/1/minute/{d}/{d}", adjusted="true", sort="asc", limit=50000)
    print(t,d,c,j.get("resultsCount"),j.get("status"),j.get("message","")[:90] if isinstance(j.get("message"),str) else "",s)
print("== underlying minute ==")
for t in ["SPY","QQQ","I:SPX"]:
    c,j,s=g(f"/v2/aggs/ticker/{t}/range/1/minute/2024-09-24/2024-09-24", limit=50000)
    print(t,c,j.get("resultsCount"),str(j.get("message",""))[:90])
print("== snapshot/greeks/quotes/trades ==")
c,j,s=g("/v3/snapshot/options/SPY", limit=5)
r0=(j.get("results") or [{}])[0]
print("snapshot",c,str(j.get("message",""))[:90],list(r0.keys()),r0.get("greeks"),r0.get("implied_volatility"))
for path in ["/v3/quotes/O:SPY240924C00570000","/v3/trades/O:SPY240924C00570000","/v2/last/trade/O:SPY260924C00764000"]:
    c,j,s=g(path, limit=2); print(path,c,str(j.get("message",""))[:100])
print("== rate test: 30 back-to-back ==")
codes={}; t0=time.time()
for i in range(30):
    c,_,_=g("/v2/aggs/ticker/O:SPY240924C00570000/range/1/minute/2024-09-24/2024-09-24", limit=10)
    codes[c]=codes.get(c,0)+1
print(codes, round(time.time()-t0,1),"s")
