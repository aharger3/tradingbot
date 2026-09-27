# J-Dub pre-market gameplan mentions of the marked ticker (no entries exist; gameplan = his only "call")
import json,pandas as pd,numpy as np,re
from datetime import datetime,timezone,timedelta
rng=np.random.default_rng(7)
B=r'C:\Users\aharg\Desktop\Projects\tradingbot'
m=pd.read_csv(B+r'\research\agent_runs\eye1\s_trades.csv'); m['S']=(m.grade=='S').astype(int)
d=json.load(open(B+r'\discord_data\jdub-alerts.json',encoding='utf-8'))
msgs=d if isinstance(d,list) else d.get('messages',d)
rows=[]
for x in msgs:
    t=datetime.fromtimestamp(((int(x['id'])>>22)+1420070400000)/1000,tz=timezone.utc)-timedelta(hours=4)
    txt=(x.get('content') or '')
    rows.append((t.strftime('%Y-%m-%d'),t.strftime('%H:%M'),txt.upper()))
j=pd.DataFrame(rows,columns=['date','hm','txt']); j=j[j.hm<'09:30']
print('jdub pre-open msgs',len(j),'days',j.date.nunique())
def ment(r):
    tx=' '.join(j[j.date==r.date].txt); 
    if not tx: return 'noday'
    if not re.search(r'\b'+re.escape(r.sym)+r'\b',tx): return 'day_no_sym'
    seg=' '.join(re.findall(r'[^\n]*\b'+re.escape(r.sym)+r'\b[^\n]*',tx))
    bull=bool(re.search(r'ABOVE|CALLS|LONG|BULL',seg)); bear=bool(re.search(r'BELOW|PUTS|SHORT|BEAR',seg))
    if bull and not bear: return 'sym_bull'
    if bear and not bull: return 'sym_bear'
    return 'sym_both'
m['jd']=m.apply(ment,axis=1)
print(m.groupby('jd').agg(n=('S','size'),S=('S','mean'),R=('R2_eng','mean')).round(2))
m['jd_sym']=m.jd.str.startswith('sym')
m['jd_dir']=((m.jd=='sym_bull')&(m.side=='L'))|((m.jd=='sym_bear')&(m.side=='S'))
for c in ['jd_sym','jd_dir']:
  for nm,s in [('all',m),('S',m[m.S==1])]:
    s=s.dropna(subset=['R2_eng']); g=s[c].values; y=s.R2_eng.values
    if g.sum()==0: continue
    dd=y[g].mean()-y[~g].mean(); p=(1+sum(abs(y[q].mean()-y[~q].mean())>=abs(dd) for q in (rng.permutation(g) for _ in range(5000))))/5001
    print(f'{c} {nm}: n={g.sum()}/{len(g)} ({g.mean():.0%}) S-rate {s[g].S.mean():.2f} vs {s[~g].S.mean():.2f}  R {y[g].mean():+.2f} vs {y[~g].mean():+.2f} p={p:.3f}')
