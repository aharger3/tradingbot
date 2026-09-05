import json, os, sys, random, statistics
ROOT=r"C:\Users\aharg\Desktop\Projects\tradingbot"
SP=os.path.join(ROOT,"research")   # committed causal SPY field lives beside this script
sys.path.insert(0,ROOT)
import research.g160_tweak_grid as G
from research.omen_metrics import ev_r_scoreboard, first_of_day_arm
from collections import defaultdict

blob=json.load(open(os.path.join(ROOT,'research','bt2y_trades_retest_on.json'),encoding='utf-8'))
rows=blob['trades']; meta=blob['meta']
TOT=meta['sessions']
H='2025-09-01'
elig=G._eligible(rows)
by_day=defaultdict(list)
for r in elig: by_day[r['day']].append(r)
s_h1=len({r['day'] for r in rows if r['day']<H}); s_h2=len({r['day'] for r in rows if r['day']>=H})

caus=json.load(open(os.path.join(SP,'g160_refute2_spy_causal.json')))

def arm(veto_fn, **kw):
    G._veto_1d = veto_fn
    return G.build_arm(by_day, **kw)

def sb(tr,ss): return ev_r_scoreboard(tr, risk_dollars=1000.0, sessions=ss)
def line(tag,tr):
    a=sb(tr,TOT); h1=sb([r for r in tr if r['day']<H],s_h1); h2=sb([r for r in tr if r['day']>=H],s_h2)
    print("%-46s n=%4d ev_r=%+.3f H1=%+.3f H2=%+.3f $/day=%7.1f win=%.1f%% green=%s"%(
        tag,a['n'],a['ev_r'],h1['ev_r'] or 0,h2['ev_r'] or 0,a['expectancy_per_day'],100*a['win_rate'],a['months_green']))
    return a,h1,h2,tr

ORIG=G._veto_1d
def veto_causal(r):
    d=r.get('dir'); t=caus.get(r['day'],'n/a')
    return (d=='call' and t=='bear') or (d=='put' and t=='bull')
def veto_never(r): return False

print("=== A. VETO_1D: as-shipped (today's SPY close) vs causal (prior close) ===")
base=first_of_day_arm(rows); line("BASELINE first_of_day_arm",base)
for pol,win in (("one_and_done","09:45"),("first3_loss_halt","09:45"),("one_and_done","11:00"),("first3_loss_halt","11:00")):
    kw=dict(classifier_on=False,day_policy=pol,window_end=win,fire_a_no_s=False)
    t0,_,_=arm(veto_never,veto1d_on=True,**kw); line("%s %s veto=OFF"%(pol,win),t0)
    G._veto_1d=ORIG
    t1,_,_=arm(ORIG,veto1d_on=True,**kw); line("%s %s veto=ON  (as shipped, LOOKAHEAD)"%(pol,win),t1)
    t2,_,_=arm(veto_causal,veto1d_on=True,**kw); line("%s %s veto=ON  (causal prior-close)"%(pol,win),t2)
    print()
G._veto_1d=ORIG

print("=== B. loss-halt causality: was the prior trade closed when the next was taken? ===")
viol=tot=0
for day,cands in by_day.items():
    cs=sorted(cands,key=lambda r:(r['et'],r['sym']))
    picks=[];cl=0
    for r in cs:
        if r['sgrade']!='S': continue
        picks.append(r); cl=cl+1 if r['r']<0 else 0
        if len(picks)>=3 or cl>=2: break
    for i in range(1,len(picks)):
        tot+=1
        prev=picks[i-1]
        if prev['entry_i']+prev['bars'] > picks[i]['entry_i']: viol+=1
print("first3 s_only full-window: %d of %d follow-on picks were taken while the PRIOR pick was still open (%.1f%%)"%(viol,tot,100*viol/max(tot,1)))

print()
print("=== C. paired session bootstrap: best arm vs baseline, per half ===")
kw=dict(classifier_on=False,day_policy='one_and_done',window_end='09:45',fire_a_no_s=False,veto1d_on=True)
G._veto_1d=ORIG
best,_,_=G.build_arm(by_day,**kw)
def daymap(tr):
    m=defaultdict(float)
    for r in tr: m[r['day']]+=r['r']
    return m
db=daymap(base); dbest=daymap(best)
alldays=sorted({r['day'] for r in rows})
def boot(days,n=20000):
    # paired on sessions: per session, R of arm and R of baseline (0 if no trade)
    a=[dbest.get(d,0.0) for d in days]; b=[db.get(d,0.0) for d in days]
    N=len(days); rng=random.Random(7)
    # observed diff in TOTAL R per session (dollars-comparable) and in ev_r
    obs=(sum(a)-sum(b))/N
    cnt=0; diffs=[]
    for _ in range(n):
        idx=[rng.randrange(N) for _ in range(N)]
        d=sum(a[i]-b[i] for i in idx)/N
        diffs.append(d)
        if d<=0: cnt+=1
    diffs.sort()
    return obs, diffs[int(.025*n)], diffs[int(.975*n)], cnt/n
for name,days in (("ALL",alldays),("H1",[d for d in alldays if d<H]),("H2",[d for d in alldays if d>=H])):
    obs,lo,hi,p=boot(days)
    print("%-4s R/session  arm-minus-baseline = %+.4f  95%% CI [%+.4f, %+.4f]  P(diff<=0)=%.3f"%(name,obs,lo,hi,p))

print()
print("=== D. how often does a RANDOM 16-arm grid contain an arm beating baseline ev_r in BOTH halves? ===")
# null: arms that pick a random eligible candidate per day at the same fire rate
rng=random.Random(11)
def rand_arm(rate):
    tr=[]
    for d,cs in by_day.items():
        if rng.random()>rate: continue
        tr.append(rng.choice(cs))
    return tr
bh1=sb([r for r in base if r['day']<H],s_h1)['ev_r']; bh2=sb([r for r in base if r['day']>=H],s_h2)['ev_r']
print("baseline ev_r H1=%+.3f H2=%+.3f"%(bh1,bh2))
hits=0;T=400
for _ in range(T):
    grid=[rand_arm(0.18) for _ in range(16)]
    ok=False
    for g in grid:
        h1=sb([r for r in g if r['day']<H],s_h1)['ev_r']; h2=sb([r for r in g if r['day']>=H],s_h2)['ev_r']
        if h1 is not None and h2 is not None and h1>bh1 and h2>bh2: ok=True;break
    hits+=ok
print("random 16-arm grids at 0.18 fires/day containing an arm that beats baseline in BOTH halves: %d/%d = %.1f%%"%(hits,T,100*hits/T))
