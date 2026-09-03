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
rs=np.array([r['r'] for r in SUB]); is1d=np.array([r.get('level_tf')=='1D' for r in SUB])
print('1D vs rest confounds on SUB arm:')
for f in ('dow','rangeb','vol_regime','spy_trend','gapb','yr','stopb','tier','cls','dir','tripped','confluence','sgrade','slot','setup'):
    a=collections.Counter(str(r.get(f)) for r,m in zip(SUB,is1d) if m)
    c=collections.Counter(str(r.get(f)) for r,m in zip(SUB,is1d) if not m)
    ka=set(a)|set(c)
    line=' '.join('%s:%.0f%%/%.0f%%'%(k,100*a[k]/is1d.sum(),100*c[k]/(~is1d).sum()) for k in sorted(ka))
    print('  %-11s %s'%(f,line))
print()
mins=np.array([int(r['et'][:2])*60+int(r['et'][3:]) for r in SUB])
print('median entry minute 1D=%d rest=%d'%(np.median(mins[is1d]),np.median(mins[~is1d])))
sp=np.array([r.get('stop_pct',0) for r in SUB])
print('mean stop_pct 1D=%.3f rest=%.3f'%(sp[is1d].mean(),sp[~is1d].mean()))
# 1D effect WITHIN each rangeb bucket (does it survive conditioning on the lookahead regime?)
rng=np.random.default_rng(5)
def p(rs_,m,n=20000):
    m=np.asarray(m,bool); o=abs(rs_[m].mean()-rs_[~m].mean()); c=0
    for _ in range(n):
        mm=m[rng.permutation(len(rs_))]
        if abs(rs_[mm].mean()-rs_[~mm].mean())>=o: c+=1
    return (c+1)/(n+1)
print('\n1D effect conditioned:')
for f,vals in (('rangeb',['big range','normal','quiet']),('dow',['Mon','Tue','Wed','Thu','Fri']),('yr',['2024','2025','2026'])):
    for v in vals:
        idx=np.array([str(r.get(f))==v for r in SUB])
        sub=rs[idx]; m=is1d[idx]
        if m.sum()<8 or (~m).sum()<8: continue
        print('  %s=%-10s 1D n=%3d ev=%+.4f | rest n=%3d ev=%+.4f  p=%.4f'%(f,v,m.sum(),sub[m].mean(),(~m).sum(),sub[~m].mean(),p(sub,m)))
# Thu after removing 1D
keep=[r for r in SUB if r.get('level_tf')!='1D']
k=np.array([r['r'] for r in keep]); thu=np.array([r['dow']=='Thu' for r in keep])
print('\nThursday AFTER dropping 1D: n=%d ev=%+.4f | rest n=%d ev=%+.4f p=%.4f'%(thu.sum(),k[thu].mean(),(~thu).sum(),k[~thu].mean(),p(k,thu)))

def dd(a):
    p=c=w=0.0
    for r in a: c+=r; p=max(p,c); w=min(w,c-p)
    return w
for tag,arm in (('base SUB',SUB),('no-1D',[r for r in SUB if r.get('level_tf')!='1D']),
                ('no-1D no-Thu',[r for r in SUB if r.get('level_tf')!='1D' and r['dow']!='Thu'])):
    a=[r['r'] for r in arm]; a_=np.array(a); w=a_[a_>0]; l=a_[a_<0]
    print('%-14s n=%3d ev_r=%+.4f win=%.1f%% aw=%.3f al=%.3f PF=%.2f maxDD_R=%.2f totalR=%.1f $/day=%.0f trades/day=%.2f'%(
        tag,len(a),a_.mean(),100*len(w)/len(a),w.mean(),-l.mean(),w.sum()/-l.sum(),dd(a),a_.sum(),a_.sum()*1000/498,len(a)/498))
