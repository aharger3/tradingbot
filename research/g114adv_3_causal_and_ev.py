"""ADVERSARIAL part 2:
 (a) build a CAUSAL day-range (09:30..entry bar only) to replace the look-ahead
     drange/rangeb, and re-test it;
 (b) redefine 'runner' in PRICE terms (MFE % of entry) at matched prevalence to
     strip the R-normalisation confound out of stop_pct/chase;
 (c) year split on every surviving candidate;
 (d) EV PER TRADE IN R -- Austin's ruling metric -- for each arm, on the book's
     own realised R and on a bar-ordered 3R-target counterfactual."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
from research import g80_ordertype_grid as G

POP = json.load(open(os.path.join(HERE, "_adv_g114_pop.json"), encoding="utf-8"))
kept = POP["rows"]; n = len(kept)

# --- (a) causal pre-entry range, from the archive -------------------------
for r in kept:
    bars, *_ = G.day_pack(r["sym"], r["day"])
    i = r["entry_i"]
    seg = bars[:i+1]
    o = seg[0].open
    hi = max(c.high for c in seg); lo = min(c.low for c in seg)
    r["_prerange"] = 100.0*(hi-lo)/o if o else 0.0
    r["_preret"]   = 100.0*(seg[-1].close-o)/o if o else 0.0

runner = np.array([1 if r["_mfe_alive"] >= 3.0 else 0 for r in kept])
mfe_pct = np.array([r["_mfe_alive_pct"] for r in kept])
# price-based runner at MATCHED prevalence (same 103 count)
thr = np.sort(mfe_pct)[::-1][runner.sum()-1]
runner_px = (mfe_pct >= thr).astype(int)
print("price-runner threshold: MFE >= %.3f%% of entry -> %d rows (overlap with R-runner: %d)"
      % (thr, runner_px.sum(), int((runner & runner_px).sum())))

TRIALS = 20000
rng = np.random.default_rng(7)
def perm_num(lab, val, trials=TRIALS):
    good = ~np.isnan(val); v = val[good]; l = lab[good]; N=len(v); k=l.sum()
    obs = v[l==1].mean() - v[l==0].mean()
    idx = np.argsort(rng.random((trials,N)),axis=1)
    P = l[idx].astype(float)
    s = P.dot(v); dp = s/k - (v.sum()-s)/(N-k)
    return obs, (np.sum(np.abs(dp)>=abs(obs))+1)/(trials+1)
def perm_cat(lab, mask, trials=TRIALS):
    N=len(lab); k=lab.sum(); nm=mask.sum()
    obs = lab[mask].mean() - lab[~mask].mean()
    idx = np.argsort(rng.random((trials,N)),axis=1)
    P = lab[idx].astype(float); s = P.dot(mask.astype(float))
    dp = s/nm - (k-s)/(N-nm)
    return obs, (np.sum(np.abs(dp)>=abs(obs))+1)/(trials+1)

print("\n=== (a) LOOK-AHEAD day-range vs its CAUSAL replacement ===")
for name, arr in [("drange (FULL session -- LOOKAHEAD)", np.array([r["drange"] for r in kept])),
                  ("_prerange (09:30..entry -- causal)", np.array([r["_prerange"] for r in kept])),
                  ("dret (FULL session -- LOOKAHEAD)", np.array([r["dret"] for r in kept])),
                  ("_preret (09:30..entry -- causal)", np.array([r["_preret"] for r in kept]))]:
    o,p = perm_num(runner, arr)
    print("  %-38s mean|run %7.3f  mean|non %7.3f  diff %+7.3f  p=%.4f"
          % (name, arr[runner==1].mean(), arr[runner==0].mean(), o, p))
# causal rangeb, same tercile-style buckets refit on the causal variable
pr = np.array([r["_prerange"] for r in kept])
q1,q2 = np.quantile(pr,[1/3,2/3])
for lab_,m in [("pre-range LOW tercile", pr<=q1), ("pre-range HIGH tercile", pr>q2)]:
    o,p = perm_cat(runner, m)
    print("  %-38s n=%3d  runner%% in %.1f vs out %.1f  diff %+.1fpp  p=%.4f"
          % (lab_, m.sum(), 100*runner[m].mean(), 100*runner[~m].mean(), 100*o, p))

print("\n=== (b) stop_pct / chase under a PRICE-based runner label ===")
sp = np.array([r["stop_pct"] for r in kept], dtype=float)
chase = np.array([("chase" in (r.get("tags") or [])) for r in kept])
for lab_name, lab in [("R-runner (>=3R)", runner), ("price-runner (matched n)", runner_px)]:
    o,p = perm_num(lab, sp); print("  stop_pct  | %-24s diff %+7.4f  p=%.4f  (mean %.4f vs %.4f)"
        % (lab_name, o, p, sp[lab==1].mean(), sp[lab==0].mean()))
    o,p = perm_cat(lab, chase); print("  tag=chase | %-24s diff %+6.1fpp p=%.4f  (%.1f%% vs %.1f%%)"
        % (lab_name, 100*o, p, 100*lab[chase].mean(), 100*lab[~chase].mean()))
print("  corr(stop_pct, chase-flag) = %.3f   [chase IS a threshold on stop_pct]"
      % np.corrcoef(sp, chase.astype(float))[0,1])

print("\n=== (c) year split (Y1 = 2024-09..2025-08, Y2 = 2025-09..2026-09) ===")
y1 = np.array([r["day"] < "2025-09-01" for r in kept])
arms = {"level_tf=1D": np.array([r.get("level_tf")=="1D" for r in kept]),
        "dow=Tue": np.array([r.get("dow")=="Tue" for r in kept]),
        "rangeb=big range [LOOKAHEAD]": np.array([r.get("rangeb")=="big range" for r in kept]),
        "tag=chase": chase,
        "pre-range HIGH tercile [causal]": pr>q2}
print("  n Y1=%d  Y2=%d" % (y1.sum(), (~y1).sum()))
for nm, m in arms.items():
    line=["  %-32s" % nm]
    for tag, sub in [("Y1", y1), ("Y2", ~y1)]:
        mm = m & sub; oo = (~m) & sub
        line.append("%s: n=%3d %5.1f%% vs %5.1f%% (%+5.1fpp)" % (tag, mm.sum(),
            100*runner[mm].mean() if mm.sum() else 0, 100*runner[oo].mean() if oo.sum() else 0,
            100*(runner[mm].mean()-runner[oo].mean()) if mm.sum() and oo.sum() else 0))
    print("  ".join(line))
print("\n=== numeric arms, year split (diff of means) ===")
for nm, arr in [("stop_pct",sp),("minutes_since_open",np.array([ (int((r.get('et') or '09:30')[:2])*60+int((r.get('et') or '09:30')[3:5]))-570 for r in kept],dtype=float)),
                ("drange [LOOKAHEAD]",np.array([r['drange'] for r in kept])),("_prerange [causal]",pr)]:
    parts=[]
    for tag, sub in [("Y1",y1),("Y2",~y1)]:
        a=arr[sub][runner[sub]==1]; b=arr[sub][runner[sub]==0]
        parts.append("%s diff %+7.4f" % (tag, a.mean()-b.mean()))
    print("  %-24s %s" % (nm, "   ".join(parts)))

print("\n=== (d) EV PER TRADE IN R (the ruling metric) ===")
bookr = np.array([r["r"] for r in kept]); t3 = np.array([r["_t3.0"] for r in kept])
t2 = np.array([r["_t2.0"] for r in kept])
def ev(x):
    w=x>0; l=x<0
    return ("EV %+.3fR  win %4.1f%%  avgW %+.3f  avgL %+.3f  n=%d"
      % (x.mean(),100*w.mean(),x[w].mean() if w.any() else 0,x[l].mean() if l.any() else 0,len(x)))
print("  ALL 444 | book realised   %s" % ev(bookr))
print("  ALL 444 | flat 2R target  %s" % ev(t2))
print("  ALL 444 | flat 3R target  %s" % ev(t3))
for nm, m in list(arms.items()) + [("runner label itself (>=3R)", runner.astype(bool))]:
    for tag, mm in [("IN ",m),("OUT",~m)]:
        print("  %-32s %s | book %+.3fR | 2R %+.3fR | 3R %+.3fR | n=%d"
              % (nm if tag=="IN " else "", tag, bookr[mm].mean(), t2[mm].mean(), t3[mm].mean(), mm.sum()))
json.dump({"thr_pct":float(thr)}, open(os.path.join(HERE,"_adv_g114_causal.json"),"w"))
