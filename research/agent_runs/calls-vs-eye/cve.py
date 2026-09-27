# calls-vs-eye: mentor calls (Scarface/J-Dub Discord entries) vs Austin's S marks
import pandas as pd, numpy as np, json, re, sys
rng=np.random.default_rng(7)
B=r'C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs'
m=pd.read_csv(B+r'\eye1\s_trades.csv')
raw=pd.read_csv(B+r'\v3-a3-pro-calls\pro_calls_raw.csv')
bt=pd.read_csv(B+r'\v3-a3-pro-calls\pro_calls_bt.csv')
print('marks',len(m),m.grade.value_counts().to_dict(),m.side.value_counts().to_dict())
print('marks date',m.date.min(),m.date.max(),'syms',m.sym.value_counts().head(8).to_dict())
raw['date']=raw.time.str[:10]; raw['hm']=raw.time.str[11:16]
raw['side']=raw.direction.map({'long':'L','short':'S'})
raw['sym']=raw.instrument.replace({'GOOG':'GOOGL'})
print('calls',len(raw),raw.source.value_counts().to_dict(),'swing',raw.swing.sum())
bt['date']=bt.time.str[:10]; bt['side']=bt.direction.map({'long':'L','short':'S'}); bt['sym']=bt.instrument.replace({'GOOG':'GOOGL'})
m['S']=(m.grade=='S').astype(int)
m['test']=m.date>='2026-03-04'
def mins(t): h,mm=str(t).split(':')[:2]; return int(h)*60+int(mm)
m['tm']=m.mark_t.fillna(m.sig_t).map(mins)
raw['tm']=raw.hm.map(mins)
intra=raw[raw.swing==0]
# period overlap: only marks inside call-coverage window count
lo,hi=intra.date.min(),intra.date.max(); print('call span',lo,hi)
mw=m[(m.date>=lo)&(m.date<=hi)].copy(); print('marks in span',len(mw),'S',mw.S.sum())
cd=set(intra.date); csd=set(zip(intra.sym,intra.date)); csdd=set(zip(intra.sym,intra.date,intra.side))
cdd=intra.groupby('date').side.agg(lambda s:set(s)).to_dict()
mw['call_day']=mw.date.isin(cd)
mw['same_sym_day']=[(a,b) in csd for a,b in zip(mw.sym,mw.date)]
mw['same_sym_dir']=[(a,b,c) in csdd for a,b,c in zip(mw.sym,mw.date,mw.side)]
def t15(r):
    x=intra[(intra.sym==r.sym)&(intra.date==r.date)&(intra.side==r.side)]
    return bool(len(x)) and (abs(x.tm-r.tm)<=15).any()
mw['same_sym_dir_15']=mw.apply(t15,axis=1)
# any mentor call same day same direction (any ticker) / opposite
mw['day_dir_agree']=[d in cd and s in cdd[d] for d,s in zip(mw.date,mw.side)]
mw['day_dir_only_opp']=[d in cd and s not in cdd[d] for d,s in zip(mw.date,mw.side)]
for c in ['call_day','same_sym_day','same_sym_dir','same_sym_dir_15','day_dir_agree','day_dir_only_opp']:
    print(f'{c}: n={mw[c].sum()} ({mw[c].mean():.0%}) S={mw[mw[c]].S.sum()} ({mw[mw[c]].S.mean() if mw[c].sum() else 0:.0%})')
print('same_sym_day rows:\n',mw[mw.same_sym_day][['sym','date','side','mark_t','grade','his_setup','R2_eng']].to_string())
print(intra[[ (a,b) in set(zip(mw.sym,mw.date)) for a,b in zip(intra.sym,intra.date)]][['source','sym','time','side','text']].to_string())
def perm(y,g,k=5000):
    y=np.asarray(y,float); g=np.asarray(g,bool)
    if g.sum()==0 or (~g).sum()==0: return np.nan,np.nan,np.nan
    d=y[g].mean()-y[~g].mean(); c=0
    for _ in range(k):
        p=rng.permutation(g); c+=abs(y[p].mean()-y[~p].mean())>=abs(d)
    return y[g].mean(),y[~g].mean(),(c+1)/(k+1)
print('\n== agreement -> R (marks in call span) ==')
for R in ['R2_eng','R2_wick']:
  for sub,nm in [(mw,'all'),(mw[mw.S==1],'S'),(mw[mw.S==0],'nonS'),(mw[mw.test],'test'),(mw[mw.test&(mw.S==1)],'testS')]:
    for c in ['day_dir_agree','call_day']:
        sub2=sub.dropna(subset=[R]); a,b,p=perm(sub2[R],sub2[c])
        print(f'{R} {nm:5} {c:14} n_agree={int(sub2[c].sum()):3} n_not={int((~sub2[c]).sum()):3} R {a:+.2f} vs {b:+.2f} p={p:.3f}')
# eye on agree vs not
for c in ['day_dir_agree']:
  for flag in [True,False]:
    s=mw[mw[c]==flag].dropna(subset=['R2_eng']); a,b,p=perm(s.R2_eng,s.S==1)
    print(f'eye(S-nonS) when {c}={flag}: S {a:+.2f} nonS {b:+.2f} n={len(s)} p={p:.3f}')
# reverse: calls with Austin S-mark same day same dir -> call R
bt['mark_day']=bt.date.isin(set(m.date))
sd=m[m.S==1].groupby('date').side.agg(lambda s:set(s)).to_dict()
bt['S_agree']=[d in sd and s in sd[d] for d,s in zip(bt.date,bt.side)]
bt['S_opp']=[d in sd and s not in sd[d] for d,s in zip(bt.date,bt.side)]
bts=bt[(bt.date>=m.date.min())]
print('\ncalls in mark span',len(bts),'on mark days',bts.mark_day.sum(),'S agree',bts.S_agree.sum(),'S opp',bts.S_opp.sum())
for c in ['mark_day','S_agree']:
    a,b,p=perm(bts.R,bts[c]); print(f'call R by {c}: {a:+.2f} vs {b:+.2f} p={p:.3f}')
# setup agreement: calls' orb_retest vs marks' setup
print('\ncall setup share: orb_retest',bt.orb_retest.mean().round(2),'S_match',bt.S_match.mean().round(2))
print('mark his_setup:',m.his_setup.value_counts(normalize=True).round(2).head(6).to_dict())
print('mark eng_setup:',m.eng_setup.value_counts(normalize=True).round(2).head(6).to_dict())
# time distributions
print('\ncall median time',intra.hm.median() if False else sorted(intra.hm)[len(intra)//2],'mark median',m.mark_t.dropna().sort_values().iloc[len(m.mark_t.dropna())//2])
bins=[0,9*60+40,9*60+50,10*60,10*60+30,24*60]; lab=['<09:40','09:40-49','09:50-59','10:00-29','10:30+']
print('calls',pd.cut(intra.tm,bins,labels=lab,right=False).value_counts(normalize=True).round(2).reindex(lab).to_dict())
print('S marks',pd.cut(m[m.S==1].tm,bins,labels=lab,right=False).value_counts(normalize=True).round(2).reindex(lab).to_dict())
print('nonS',pd.cut(m[m.S==0].tm,bins,labels=lab,right=False).value_counts(normalize=True).round(2).reindex(lab).to_dict())
print('dir: calls long%',(intra.side=='L').mean().round(2),'S marks long%',(m[m.S==1].side=='L').mean().round(2))
mw.to_csv('calls_vs_eye_marks.csv',index=False); bt.to_csv('calls_vs_eye_calls.csv',index=False)
