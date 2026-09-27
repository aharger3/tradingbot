import json,re,datetime,collections,csv,sys,os
from zoneinfo import ZoneInfo
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
B=r'C:\Users\aharg\Desktop\Projects\tradingbot\discord_data\\'
OUT=r'C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v3-a3-pro-calls\\'
os.makedirs(OUT,exist_ok=True)
ET=ZoneInfo('America/New_York')
def t(i): return datetime.datetime.fromtimestamp(((int(i)>>22)+1420070400000)/1000,ET)
TK=set('TSLA NVDA AAPL AMD QQQ SPY GOOGL GOOG META MSFT AMZN PLTR NFLX COIN INTC AVGO MSTR SMCI UBER BA DIS HOOD SHOP ARM MU ORCL CRM IWM SNOW JPM LLY UNH ROKU BABA RIVN SOFI MARA PYPL ADBE TSM ES NQ MES MNQ'.split())
TKRE=re.compile(r'\b(GOOOGL|'+'|'.join(sorted(TK,key=len,reverse=True))+r')\b',re.I)
ENT=re.compile(r'\b(took|taking|entered|entering|bought|buying|added)\b|\bi.?m in\b|\bin at\b|\bgot in\b',re.I)
OPT=re.compile(r'(\d+(?:\.\d+)?)\s*(calls?|puts?|c\b|p\b)',re.I)
FUT=re.compile(r'\b(long|short)\b',re.I)
NOT=re.compile(r'took\s+(off|profit|partial|my\s+first|first|some|half|\d+%|a\s+scale|scale|the\s+l|another\s+scale|more\s+off|most)|\bif\b|watching|looking|keep\s+(a|an)\s+(close\s+)?eye|potential|would|could|\bwhen\b|\bpatient\b|\bwait|interested|in play|will be',re.I)
SWING=re.compile(r'swing|exp\b|expiry|next\s+week|\bjan|\bfeb|\bmar\b|\bapr|\bmay\s+\d|\bjun|\bjul|\baug|\bsep|\boct|\bnov|\bdec',re.I)
rows=[]
for src,f in [('scarface','scarface-alerts'),('jdub','jdub-alerts')]:
    msgs=json.load(open(B+f+'.json',encoding='utf-8'))
    msgs=[m for m in msgs if m['content']]
    msgs.sort(key=lambda m:int(m['id']))
    last_tk=None;last_tk_t=None
    for k,m in enumerate(msgs):
        c=m['content'];ts=t(m['id'])
        tks=TKRE.findall(c)
        if tks: last_tk=tks[0].upper();last_tk_t=ts
        if not ENT.search(c) or NOT.search(c): continue
        o=OPT.search(c)
        if not o: continue
        tk=tks[0].upper() if tks else (last_tk if last_tk_t and (ts-last_tk_t).total_seconds()<1200 else None)
        if tk in('GOOG','GOOOGL'): tk='GOOGL'
        if not tk: continue
        d='long' if o.group(2).lower().startswith('c') else 'short'
        # stop/target from same msg + follow-ups within 45 min
        stop=None;tgt=None
        for mm in [m]+[x for x in msgs[k+1:k+12] if (t(x['id'])-ts).total_seconds()<2700]:
            cc=mm['content']
            s=re.search(r'stop[^\d\n]{0,40}?(\d{2,4}(?:\.\d+)?)',cc,re.I)
            if s and stop is None: stop=float(s.group(1))
            g=re.search(r'target[^\d\n]{0,25}?(\d{2,4}(?:\.\d+)?)',cc,re.I)
            if g and tgt is None: tgt=g.group(1)
            if tgt is None:
                h=re.search(r'\b(HOD|LOD|PDH|PDL|PM ?HIGH|PM ?LOW|ATH)\b',cc,re.I)
                if h and mm is m: tgt=h.group(1).upper()
        rows.append(dict(source=src,time=ts.strftime('%Y-%m-%d %H:%M'),instrument=tk,direction=d,strike=o.group(1),
            entry='',stop=stop if stop else '',target=tgt or '',swing=int(bool(SWING.search(c))),msg_id=m['id'],text=c.replace('\n',' / ')[:200]))
print(collections.Counter(r['source'] for r in rows))
print(collections.Counter((r['source'],r['instrument']) for r in rows).most_common(20))
w=csv.DictWriter(open(OUT+'pro_calls_raw.csv','w',newline='',encoding='utf-8'),fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
for r in rows[::max(1,len(rows)//45)]: print(r['source'][:2],r['time'],r['instrument'],r['direction'],r['stop'],r['target'],r['swing'],'|',r['text'][:110])
