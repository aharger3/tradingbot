import csv,json,os,urllib.request,datetime,time
D=r'C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v3-a3-pro-calls\\'
os.makedirs(D+'bars',exist_ok=True)
K=os.environ['POLYGON_API_KEY']
rows=list(csv.DictReader(open(D+'pro_calls_raw.csv',encoding='utf-8')))
need=set()
for r in rows:
    d=r['time'][:10]; need.add((r['instrument'],d)); need.add(('SPY',d))
ok=0;fail=[]
for tk,d in sorted(need):
    fn=D+f'bars\\{tk}_{d}.json'
    if os.path.exists(fn): ok+=1; continue
    d0=(datetime.date.fromisoformat(d)-datetime.timedelta(days=6)).isoformat()
    u=f'https://api.polygon.io/v2/aggs/ticker/{tk}/range/1/minute/{d0}/{d}?adjusted=false&sort=asc&limit=50000&apiKey={K}'
    try:
        j=json.load(urllib.request.urlopen(u,timeout=30))
        if j.get('results'): json.dump(j['results'],open(fn,'w')); ok+=1
        else: fail.append((tk,d,j.get('status')))
    except Exception as e: fail.append((tk,d,str(e)[:60].replace(K,'***')))
print('ok',ok,'fail',len(fail),fail[:8])
