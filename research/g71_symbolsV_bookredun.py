"""Return correlation is not the redundancy a stop-based directional book
experiences. Measure the redundancy that actually costs money: correlation of
per-day realised R between SPY and each companion, on the traded book."""
import json, os, statistics, collections
HERE=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(os.path.join(HERE,'bt2y_trades.json')))
tr=[t for t in d['trades'] if t.get('traded')]
print('traded rows in book:', len(tr), ' meta.traded=', d['meta']['traded'])
by=collections.defaultdict(lambda: collections.defaultdict(float))
cnt=collections.Counter()
for t in tr:
    by[t['sym']][t['day']] += t['r']; cnt[t['sym']]+=1
def pear(xs,ys):
    mx,my=statistics.fmean(xs),statistics.fmean(ys)
    n=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    dx=sum((x-mx)**2 for x in xs)**.5; dy=sum((y-my)**2 for y in ys)**.5
    return n/(dx*dy) if dx and dy else None
spy=by['SPY']
print('\nSPY traded days: %d  (SPY book trades %d)' % (len(spy), cnt['SPY']))
rows=[]
for s in sorted(by):
    if s=='SPY': continue
    days=sorted(set(spy)&set(by[s]))
    if len(days)<5: continue
    r=pear([spy[d] for d in days],[by[s][d] for d in days])
    rows.append((s,r,len(days),cnt[s]))
rows.sort(key=lambda t:-(t[1] or -9))
print('%-6s %7s %6s %6s'%('sym','r(dayR)','codays','trades'))
for s,r,n,c in rows: print('%-6s %+7.3f %6d %6d'%(s,r,n,c))
