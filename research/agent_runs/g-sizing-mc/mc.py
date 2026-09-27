# Monte Carlo: LucidFlex 50K eval pass prob / time-to-pass across MNQ contract ladders
# outcome shape = empirical S trades (s_trades.csv R2_eng), edge level per scenario + parameter uncertainty
import numpy as np, pandas as pd, itertools, json, sys
rng=np.random.default_rng(7)
d=pd.read_csv('s_trades.csv'); s=d[d.grade=='S'].dropna(subset=['R2_eng'])
R=s.R2_eng.values; ex=s.exit2_eng.values
flatR=R[ex=='flat']; thruR=R[ex=='stop_thru_fill']
sh_flat=len(flatR)/len(R); sh_thru=len(thruR)/len(R)
WIN=R[ex=='tgt'].mean(); LOSS=R[ex=='stop'].mean()
print('emp S mean',round(R.mean(),3),'win',round(WIN,3),'loss',round(LOSS,3),'flat',round(sh_flat,3),'thru',round(sh_thru,3),'n',len(R))
def p_for(mu):  # win prob (of total) giving E[R]=mu with flat/thru shares fixed
    rest=1-sh_flat-sh_thru; base=sh_flat*flatR.mean()+sh_thru*thruR.mean()
    return (mu-base-rest*LOSS)/(WIN-LOSS)
TIERS=[2,3,4,6,8,10,12,15,20]
LAD=np.array(list(itertools.product(TIERS,repeat=3)))  # (L,3) cts at profit <1k / 1-2k / >=2k
L=len(LAD); P=int(sys.argv[1]) if len(sys.argv)>1 else 3000
H_EVAL=200; H_FUND=120; COMM=1.24; PT=2.0; CAP=40
def run(mu,se,freq,P=P):
    # per-path edge draw (parameter uncertainty)
    mu_p=mu+rng.normal(0,se,P)
    pw=np.clip(p_for(mu_p),0.02,1-sh_flat-sh_thru-0.02)
    NT=int((H_EVAL+H_FUND)*freq*2)+20
    gaps=rng.geometric(freq,(NT,P)); sess=np.cumsum(gaps,0)  # session index of each trade
    u=rng.random((NT,P)); rest=1-sh_flat-sh_thru
    r=np.where(u<sh_flat, rng.choice(flatR,(NT,P)),
      np.where(u<sh_flat+sh_thru, rng.choice(thruR,(NT,P)),
      np.where(u<sh_flat+sh_thru+pw*1, WIN, LOSS)))
    # u in [sh_flat+sh_thru, 1): win if below +pw (pw is share of total)
    stop=np.clip(np.exp(rng.normal(np.log(21),0.45,(NT,P))),6,70)
    Lx=LAD[:,:,None]
    bal=np.full((L,P),50000.); hi=bal.copy(); floor=np.full((L,P),48000.)
    best=np.zeros((L,P)); phase=np.zeros((L,P),np.int8)  # 0 eval 1 funded 2 bust-eval 3 timeout 4 paid 5 bust-funded
    pass_s=np.full((L,P),np.nan); fstart=np.zeros((L,P)); fbal0=np.zeros((L,P)); pdays=np.zeros((L,P)); payout=np.zeros((L,P))
    for k in range(NT):
        sk=sess[k][None,:]; act0=(phase==0)&(sk<=H_EVAL); act1=(phase==1)&(sk-fstart<=H_FUND)
        phase[(phase==0)&(sk>H_EVAL)]=3
        act=act0|act1
        if not act.any(): break
        prof=np.where(phase==1,bal-fbal0,bal-50000)
        tier=np.where(prof<1000,Lx[:,0],np.where(prof<2000,Lx[:,1],Lx[:,2]))
        per=stop[k][None,:]*PT+COMM+0.5
        n=np.minimum(np.minimum(tier,CAP),np.floor((bal-floor-50)/per)).clip(0)
        pnl=n*(r[k][None,:]*stop[k][None,:]*PT-COMM)
        pnl=np.where(act,pnl,0.)
        # intraday breach: loss beyond cushion
        busted=act&(bal+pnl<=floor)
        bal=bal+pnl
        best=np.where(act0,np.maximum(best,pnl),best)
        hi=np.maximum(hi,bal)
        lockv=np.where(phase==1,fbal0+100,50100.)
        floor=np.where(act,np.maximum(floor,np.minimum(hi-2000,lockv)),floor)
        phase[busted&(phase==0)]=2; phase[busted&(phase==1)]=5
        tp=np.where(act0&~busted,bal-50000,0)
        passed=act0&~busted&(tp>=3000)&(best<=0.5*tp)
        pass_s[passed]=np.broadcast_to(sk,(L,P))[passed]; phase[passed]=1
        fstart[passed]=np.broadcast_to(sk,(L,P))[passed]; fbal0[passed]=50000.; bal[passed]=50000.; hi[passed]=50000.; floor[passed]=48000.
        # funded: count profitable days >=150; first payout at 5 such days with profit>0
        good=act1&~busted&(pnl>=150); pdays+=good
        pay=act1&~busted&(pdays>=5)&(bal-fbal0>0)
        payout[pay]=np.minimum(0.5*(bal-fbal0)[pay],2000)*0.9; phase[pay]=4
    ps=~np.isnan(pass_s)
    out=pd.DataFrame({'lad':['/'.join(map(str,x)) for x in LAD],
        'pass':ps.mean(1),'bust':(phase==2).mean(1),
        'pass60':(pass_s<=60).mean(1),
        'med':np.nanmedian(np.where(ps,pass_s,np.nan),1),
        'p75':np.nanpercentile(np.where(ps,pass_s,np.nan),75,axis=1),
        'payP':(phase==4).mean(1),'EV':(payout.sum(1)/P)-146})
    return out
if __name__=='__main__':
    SC={'A_o2test':(0.49,0.225),'B_allS':(0.38,0.127),'C_half':(0.19,0.127),'D_zero':(0.0,0.127)}
    FR={'f12':0.12,'f25':0.25,'f50':0.50}
    res={}
    for sn,(mu,se) in SC.items():
        for fn,f in FR.items():
            o=run(mu,se,f); o['sc']=sn; o['fr']=fn; res[(sn,fn)]=o
            b=o.sort_values('EV',ascending=False).iloc[0]; b2=o.sort_values('pass',ascending=False).iloc[0]
            print(sn,fn,'bestEV',b.lad,round(b['pass'],3),round(b.pass60,3),b.med,round(b.EV),'| bestPass',b2.lad,round(b2['pass'],3),b2.med,flush=True)
    allr=pd.concat(res.values()); allr.to_csv('mc_all.csv',index=False)
