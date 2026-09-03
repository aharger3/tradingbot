"""G7.1 weeks -- adversarial part 2: decompose the 1.244 'corr_drag' and test
the variable-sizing escape the claim rules out. Read-only."""
import json,math,statistics,collections,random,datetime
from pathlib import Path
R=Path(__file__).resolve().parent.parent
def phi(x): return .5*(1+math.erf(x/math.sqrt(2)))
b=json.loads((R/"research/bt2y_trades.json").read_text())
rows=[r for r in b["trades"] if r["status"]=="fired" and r["traded"]]
def iw(s):
    y,w,_=datetime.date.fromisoformat(s).isocalendar(); return "%d-W%02d"%(y,w)
wk=collections.defaultdict(list)
for r in rows: wk[iw(r["day"])].append(r)
weeks=sorted(wk); ser=[sum(x["r"] for x in wk[w]) for w in weeks]
cnt=[len(wk[w]) for w in weeks]
mu=statistics.fmean(r["r"] for r in rows); sg=statistics.pstdev([r["r"] for r in rows])
sdw=statistics.pstdev(ser); En=statistics.fmean(cnt); Vn=statistics.pstdev(cnt)**2
# compound model: Var(week) = E[n]*sg^2 + Var(n)*mu^2   (random n, iid r)
v_compound=En*sg*sg+Vn*mu*mu
print(json.dumps({"E_n":round(En,2),"Var_n":round(Vn,2),"sd_n":round(math.sqrt(Vn),2),
 "sd_week_obs":round(sdw,3),"sd_week_iid_fixed_n":round(sg*math.sqrt(En),3),
 "sd_week_compound_random_n":round(math.sqrt(v_compound),3),
 "drag_vs_fixed_n":round(sdw/(sg*math.sqrt(En)),3),
 "drag_vs_compound":round(sdw/math.sqrt(v_compound),3),
 "share_of_excess_var_from_count_dispersion":round((Vn*mu*mu)/(sdw**2-En*sg*sg),3)},indent=1))
# permutation: shuffle trades across weeks keeping the week counts -> kills any
# real intra-week correlation, keeps count dispersion. If drag survives, drag is
# a count artefact, not correlation.
allr=[r["r"] for r in rows]; random.seed(11); ds=[]
for _ in range(2000):
    random.shuffle(allr); i=0; s=[]
    for c in cnt: s.append(sum(allr[i:i+c])); i+=c
    ds.append(statistics.pstdev(s))
print("permuted sd_week (correlation destroyed, counts kept): mean=%.3f p95=%.3f  obs=%.3f"
      %(statistics.fmean(ds),sorted(ds)[int(.95*len(ds))],sdw))
print("permuted drag vs sg*sqrt(E_n): %.3f   obs drag %.3f"%(statistics.fmean(ds)/(sg*math.sqrt(En)),sdw/(sg*math.sqrt(En))))
gp=[sum(1 for v in [sum(allr[i:i+c]) for i,c in [(0,0)]] ) for _ in [0]]
# variable sizing test: the claim says P(green week) is scale-invariant.
# TRUE for a uniform multiplier. FALSE for per-trade weights. Demonstrate with a
# causal, no-look-ahead weight: half size on the 2nd+ trade of the same day.
byday=collections.defaultdict(list)
for r in rows: byday[r["day"]].append(r)
for d in byday: byday[d].sort(key=lambda r:(r["entry_i"],r["seq"]))
for half in (1.0,0.5,0.25):
    w2=collections.defaultdict(float)
    for d,rs in byday.items():
        for i,r in enumerate(rs): w2[iw(d)]+=r["r"]*(1.0 if i==0 else half)
    s=[w2[w] for w in weeks]; g=sum(1 for v in s if v>0)
    print("uniform=%.2f on 2nd+ trade/day: green %d/105 = %.1f%%  mean %.2fR sharpe %.3f"
          %(half,g,g/105*100,statistics.fmean(s),statistics.fmean(s)/statistics.pstdev(s)))
print("baseline green 91/105 = 86.67%")
