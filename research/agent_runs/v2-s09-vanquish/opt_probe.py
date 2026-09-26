# v2-s09: probe 0DTE index-ETF option 1-min bars on the existing Polygon/Massive key. Paper research only. Key never printed.
import json, time, urllib.request, urllib.error, statistics as st
from pathlib import Path
from datetime import datetime, timezone, timedelta
key=None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key=l.split("=",1)[1].strip().strip('"')
def get(path):
    sep="&" if "?" in path else "?"
    u="https://api.polygon.io"+path+sep+"apiKey="+key
    time.sleep(13)
    try:
        with urllib.request.urlopen(u,timeout=30) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, {"err": e.read().decode()[:160].replace(key,"***")}
D="2026-09-24"; ymd="260924"
ET=timezone(timedelta(hours=-4))
def win(res):  # 9:30-11:00 ET bars, keyed by minute
    out={}
    for b in res or []:
        t=datetime.fromtimestamp(b["t"]/1000,ET)
        if (t.hour,t.minute)>=(9,30) and (t.hour,t.minute)<(11,0): out[t.strftime("%H:%M")]=b
    return out
def under(sym):
    s,d=get(f"/v2/aggs/ticker/{sym}/range/1/minute/{D}/{D}?limit=50000")
    return s, win(d.get("results"))
def occ(root,cp,k): return f"O:{root}{ymd}{cp}{int(round(k*1000)):08d}"
rows=[]
for sym,step,offs in (("SPY",1,(0,2)),("QQQ",1,(0,))):
    s,u=under(sym); print(sym,"underlying",s,len(u),"bars")
    if not u: continue
    p0=u["09:30"]["o"]; atm=round(p0/step)*step
    for cp,sign in (("C",1),("P",-1)):
        for o in offs:
            k=atm+sign*o*step; tk=occ(sym,cp,k)
            s,d=get(f"/v2/aggs/ticker/{tk}/range/1/minute/{D}/{D}?limit=50000")
            w=win(d.get("results")) if s==200 else {}
            mins=sorted(set(w)&set(u))
            dop=[w[m]["c"]-w[m]["o"] for m in mins]; dun=[u[m]["c"]-u[m]["o"] for m in mins]
            num=sum(a*b for a,b in zip(dop,dun)); den=sum(b*b for b in dun) or 1
            rng=[(w[m]["h"]-w[m]["l"])/w[m]["c"] for m in mins if w[m]["c"]>0]
            rows.append(dict(tk=tk,status=s,bars=len(w),vol=int(sum(b["v"] for b in w.values())),
                prem_open=w.get("09:30",w[min(w)] if w else {}).get("o"),
                emp_delta=round(num/den,3) if mins else None,
                med_bar_range_pct=round(100*st.median(rng),1) if rng else None, under_open=p0, strike=k))
s,d=get(f"/v3/reference/options/contracts?underlying_ticker=SPX&expiration_date={D}&limit=3")
print("SPX contracts ref",s,[r.get("ticker") for r in d.get("results",[])] if s==200 else d)
spxw = (d.get("results") or [{}])[0].get("ticker") if s==200 else None
if spxw:
    s2,d2=get(f"/v2/aggs/ticker/{spxw}/range/1/minute/{D}/{D}?limit=50000"); print("SPXW aggs",spxw,s2,len(d2.get("results") or []))
if rows:
    s,d=get(f"/v3/quotes/{rows[0]['tk']}?limit=1&timestamp.gte={D}"); print("option quotes",s,str(d)[:120] if s!=200 else "ok")
for r in rows: print(json.dumps(r))
