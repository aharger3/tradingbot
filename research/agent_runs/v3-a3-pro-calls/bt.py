import csv,os,json,random,statistics as st,datetime,collections,sys
import pandas as pd, numpy as np
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
D=r'C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v3-a3-pro-calls\\'
A=r'C:\Users\aharg\Desktop\Projects\tradingbot\data_archive\\'
rows=list(csv.DictReader(open(D+'pro_calls_raw.csv',encoding='utf-8')))
_c={}
def day(tk,d):
    k=(tk,d)
    if k in _c: return _c[k]
    f=A+f'{tk}\\{d}.csv'
    if not os.path.exists(f): _c[k]=None; return None
    x=pd.read_csv(f); x['t']=pd.to_datetime(x['Datetime'],utc=True).dt.tz_convert('America/New_York')
    x=x.set_index('t')[['Open','High','Low','Close']]; _c[k]=x; return x
def prevday(tk,d):
    dd=datetime.date.fromisoformat(d)
    for i in range(1,6):
        p=(dd-datetime.timedelta(days=i)).isoformat(); x=day(tk,p)
        if x is not None:
            r=x.between_time('09:30','15:59'); 
            if len(r): return r
    return None
SLIP=0.01; COM=0.005
def sim(b,ei,side,stop,cut):
    """b: rth frame; ei: index of entry bar; returns R"""
    e=b.Open.iloc[ei]+side*SLIP; risk=(e-stop)*side
    if risk<=0.02: return None
    tgt=e+side*2*risk
    for j in range(ei,len(b)):
        if b.index[j].strftime('%H:%M')>=cut:
            x=b.Open.iloc[j]-side*SLIP; return ((x-e)*side-2*COM)/risk
        h,l=b.High.iloc[j],b.Low.iloc[j]
        if (l<=stop if side>0 else h>=stop): return ((stop-side*SLIP-e)*side-2*COM)/risk
        if (h>=tgt if side>0 else l<=tgt): return (2*risk-2*COM)/risk
    x=b.Close.iloc[-1]; return ((x-e)*side-2*COM)/risk
def feats(b,ei,side):
    o=b.between_time('09:30','09:34'); orh,orl=o.High.max(),o.Low.min()
    lvl=orh if side>0 else orl
    rng=(b.High-b.Low)
    f=dict(orb_break=0,disp_atr=np.nan,strong_break=0,retest=0,closed_thru=0,trig='none',ext_atr=np.nan,in_range=0)
    pre=b.iloc[:ei]
    if len(pre)<6: return f,lvl
    atr=rng.iloc[max(0,ei-14):ei].mean()
    cl=pre.Close; 
    brk=[i for i in range(5,ei) if (cl.iloc[i]-lvl)*side>0]
    e=b.Open.iloc[ei]
    f['ext_atr']=round((e-lvl)*side/atr,2); f['in_range']=int(orl<=e<=orh)
    if brk:
        i0=brk[0]; f['orb_break']=1
        seg=b.iloc[i0:ei]
        ext=(seg.High.max()-lvl) if side>0 else (lvl-seg.Low.min())
        f['disp_atr']=round(ext/atr,2)
        bb=b.iloc[i0]; body=abs(bb.Close-bb.Open); r=bb.High-bb.Low
        f['strong_break']=int(r>0 and body/r>=0.6 and r>=1.2*atr)
        post=b.iloc[i0+1:ei]
        if len(post):
            f['retest']=int(((post.Low-lvl) if side>0 else (lvl-post.High)).min()<=0.25*atr)
            f['closed_thru']=int(((post.Close-lvl)*side<0).any())
    cb=b.iloc[ei-1]; r=cb.High-cb.Low
    if r>0:
        lw=(min(cb.Open,cb.Close)-cb.Low)/r; uw=(cb.High-max(cb.Open,cb.Close))/r; body=abs(cb.Close-cb.Open)/r
        pos=(cb.Close-cb.Low)/r
        if side>0 and lw>=0.5 and pos>=0.6 or side<0 and uw>=0.5 and pos<=0.4: f['trig']='hammer'
        elif body>=0.6 and (cb.Close-cb.Open)*side>0: f['trig']='strong'
        elif (cb.Close-cb.Open)*side<0: f['trig']='against'
        else: f['trig']='weak'
    return f,lvl
def run(r,minute=None,rng_=None):
    tk,d=r['instrument'],r['time'][:10]; x=day(tk,d)
    if x is None: return None
    b=x.between_time('09:30','15:59')
    if len(b)<60: return None
    side=1 if r['direction']=='long' else -1
    hm=minute or r['time'][11:16]
    ts=pd.Timestamp(d+' '+hm,tz='America/New_York')+pd.Timedelta(minutes=1)
    idx=np.where(b.index>=ts)[0]
    if not len(idx): return None
    ei=idx[0]
    if ei<6: return None
    cb=b.iloc[ei-1]; lo2=b.iloc[ei-2:ei]
    stop=(lo2.Low.min()-0.01) if side>0 else (lo2.High.max()+0.01)
    cut='11:00' if hm<'11:00' else '15:55'
    R=sim(b,ei,side,stop,cut)
    stated=None
    try:
        s=float(r['stop']); e=b.Open.iloc[ei]
        if 0<(e-s)*side<0.03*e: stated=sim(b,ei,side,s-0.01*side,cut)
    except: pass
    f,lvl=feats(b,ei,side)
    pd_=prevday(tk,d)
    near=''
    if pd_ is not None:
        atr=(b.High-b.Low).iloc[max(0,ei-14):ei].mean()
        for nm,v in [('PDH',pd_.High.max()),('PDL',pd_.Low.min())]:
            if abs(b.iloc[max(0,ei-5):ei].Low.min()-v)<0.5*atr or abs(b.iloc[max(0,ei-5):ei].High.max()-v)<0.5*atr: near+=nm
    return dict(R=R,R_stated=stated,**f,near_pd=near,entry=round(b.Open.iloc[ei]+side*SLIP,2),stop_used=round(stop,2),ent_hm=b.index[ei].strftime('%H:%M'))
out=[]
for r in rows:
    if r['swing']=='1': continue
    res=run(r)
    if res is None or res['R'] is None: continue
    o={**r,**res}; out.append(o)
df=pd.DataFrame(out)
df['orb_retest']=((df.orb_break==1)&(df.retest==1)&(df.closed_thru==0)).astype(int)
df['S_match']=((df.orb_retest==1)&(df.disp_atr>=1)&(df.trig.isin(['hammer','strong']))&(df.ent_hm<='10:30')).astype(int)
df.to_csv(D+'pro_calls_bt.csv',index=False)
def s(g,col='R'):
    v=g[col].dropna(); return f"n={len(v)} avgR={v.mean():+.2f} win2R={(v>=1.9).mean():.0%} stopped={(v<=-0.9).mean():.0%} sumR={v.sum():+.1f}" if len(v) else 'n=0'
print('ALL',s(df)); print('stated stop',s(df,'R_stated'))
for k,g in df.groupby('source'): print('src',k,s(g))
df['half']=np.where(df.time<df.time.sort_values().iloc[len(df)//2],'H1','H2')
for k,g in df.groupby('half'): print(k,g.time.min()[:10],g.time.max()[:10],s(g))
df['yr']=df.time.str[:4]
for k,g in df.groupby('yr'): print('yr',k,s(g))
for c in ['orb_break','orb_retest','S_match','strong_break','closed_thru','in_range']:
    for k,g in df.groupby(c): print(c,k,s(g))
for k,g in df.groupby('trig'): print('trig',k,s(g))
for k,g in df.groupby(df.near_pd!=''): print('nearPD',k,s(g))
for k,g in df.groupby(df.ent_hm<='10:30'): print('<=10:30',k,s(g))
for k,g in df.groupby(pd.cut(df.ext_atr,[-99,0,1,2,4,99])): print('ext_atr',k,s(g))
for k,g in df.groupby('target'): print('tgt',k,s(g))
print('median entry',df.ent_hm.median() if False else sorted(df.ent_hm)[len(df)//2],'disp med',df.disp_atr.median(),'ext med',df.ext_atr.median())
# shuffle: random minute 09:36-10:30 same day/side, 500 draws
random.seed(7); means=[]
mins=[f'{h:02d}:{m:02d}' for h in (9,10) for m in range(60) if '09:36'<=f'{h:02d}:{m:02d}'<='10:30']
recs=df.to_dict('records')
for it in range(300):
    v=[]
    for r in recs:
        q=run(r,minute=random.choice(mins))
        if q and q['R'] is not None: v.append(q['R'])
    means.append(np.mean(v))
obs=df.R.mean(); print(f'shuffle: obs {obs:+.3f} rand mean {np.mean(means):+.3f} p(rand>=obs)={np.mean(np.array(means)>=obs):.3f}')
# direction flip check
