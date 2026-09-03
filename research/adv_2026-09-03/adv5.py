import json, collections, numpy as np
B='C:/Users/aharg/Desktop/Projects/tradingbot/research/bt2y_trades_retest_on.json'
b=json.load(open(B,encoding='utf-8')); rows=b['trades']
def floor(c): return max(0.10,0.0015*c)
def sz(r):
    e,s=r.get('entry'),r.get('stop')
    return None if e is None or s is None else abs(e-s)>=floor(r.get('close',e))
by_day=collections.defaultdict(list)
for r in rows:
    if (r['status']=='fired' and r.get('traded')) or r['status']=='halted': by_day[r['day']].append(r)
ek=lambda r:(r['day'],r['et'],r['sym'])
SUB=[]
for d,v in sorted(by_day.items()):
    for r in sorted(v,key=ek):
        if sz(r) is not False and r.get('r') is not None: SUB.append(r); break
POWER=[r for r in rows if r['status']=='fired' and r.get('traded') and sz(r) is not False and r.get('r') is not None]
days=sorted({r['day'] for r in rows}); cut=days[len(days)//2]
rng=np.random.default_rng(99)
def lvlp(rs,mask,nperm=50000):
    mask=np.asarray(mask,bool); n=len(rs); obs=abs(rs[mask].mean()-rs[~mask].mean()); c=0
    for _ in range(nperm):
        m=mask[rng.permutation(n)]
        if abs(rs[m].mean()-rs[~m].mean())>=obs: c+=1
    return (c+1)/(nperm+1)
def blk(tag,arm,pred,npm=50000):
    rs=np.array([r['r'] for r in arm]); m=np.array([pred(r) for r in arm])
    if m.sum()<5 or m.sum()==len(rs): print('  %-34s n=%d SKIP'%(tag,m.sum())); return
    g=rs[m]; o=rs[~m]; w=g[g>0]
    print('  %-34s n=%4d ev=%+.4f win=%.1f%% | rest n=%4d ev=%+.4f | p=%.5f'%(
        tag,len(g),g.mean(),100*len(w)/len(g),len(o),o.mean(),lvlp(rs,m,npm)))

print('== level_tf on the SHIPPABLE SUB arm (n=%d, ev=%.4f) =='%(len(SUB),np.mean([r['r'] for r in SUB])))
print(collections.Counter(r.get('level_tf') for r in SUB))
for lv in sorted({r.get('level_tf') for r in SUB}):
    blk('level_tf=%s'%lv, SUB, lambda r,lv=lv: r.get('level_tf')==lv)
print('\n== POWER replication ==')
for lv in sorted({r.get('level_tf') for r in POWER}):
    blk('level_tf=%s'%lv, POWER, lambda r,lv=lv: r.get('level_tf')==lv, 6000)

print('\n== HOLDOUT: first half vs second half of the book, SUB arm ==')
for half,pred in (('FIRST',lambda r:r['day']<cut),('SECOND',lambda r:r['day']>=cut)):
    a=[r for r in SUB if pred(r)]
    print(' %s n=%d ev=%.4f'%(half,len(a),np.mean([r['r'] for r in a])))
    for lv in ('1D','1m premarket','5m opening range'):
        blk('   level_tf=%s'%lv, a, lambda r,lv=lv: r.get('level_tf')==lv, 20000)
    blk('   dow=Thu', a, lambda r: r.get('dow')=='Thu', 20000)
    blk('   rangeb=quiet (LOOKAHEAD)', a, lambda r: r.get('rangeb')=='quiet', 20000)
    blk('   month=02', a, lambda r: r['ym'][5:7]=='02', 20000)

print('\n== economics: drop level_tf==1D from SUB arm ==')
rs=np.array([r['r'] for r in SUB])
keep=[r for r in SUB if r.get('level_tf')!='1D']
k=np.array([r['r'] for r in keep])
print('  base   n=%d ev=%.4f totalR=%.2f $/day(498)=%.0f'%(len(rs),rs.mean(),rs.sum(),rs.sum()*1000/498))
print('  no-1D  n=%d ev=%.4f totalR=%.2f $/day(498)=%.0f'%(len(k),k.mean(),k.sum(),k.sum()*1000/498))
mg=collections.defaultdict(float)
for r in keep: mg[r['ym']]+=r['r']
print('  no-1D months green %d/%d'%(sum(1 for v in mg.values() if v>0),len(mg)))
mg2=collections.defaultdict(float)
for r in SUB: mg2[r['ym']]+=r['r']
print('  base  months green %d/%d'%(sum(1 for v in mg2.values() if v>0),len(mg2)))
