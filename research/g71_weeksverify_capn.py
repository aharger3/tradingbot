"""G7.1 / track `weeksverify` -- adversarial re-check of the `weeks` CAP-N claim.

Tests three things the `weeks` report asserts:
 1. that the CAP-N curve is MONOTONE in trade count (it is not),
 2. that CAP-N holds trade QUALITY fixed (it does not),
 3. that `p_green_model` is a test of P(green)=Phi(sqrt(n)mu/sigma) (it is not --
    it is a normal fit to the REALISED weekly series, and it already absorbs
    the correlation it is supposed to be measuring). The true iid prediction is
    recomputed here, both with the mean weekly count and with the correct
    variance-of-a-random-sum term.
"""
import json, math, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT/"research/_g71_weeks_verify.json").read_text())

def phi(x): return 0.5*(1+math.erf(x/math.sqrt(2)))

rows = d["capn_curve"] + [r for r in d["policies"] if r["policy"].split()[0] in ("P0","P0u","P0seq")]
print("%-12s %7s %7s %7s %8s %8s %8s %8s %8s %8s" % (
    "arm","t/wk","muR","sdR","obs%grn","iid_meanN","iid_randN","realsd","iidsd","drag"))
for r in rows:
    n = r["trades_per_week"]; mu=r["mean_r_trade"]; sg=r["sd_r_trade"]
    cnt = [c for _w,_v,c in r["weekly_series"]]
    En = statistics.fmean(cnt); Vn = statistics.pvariance(cnt)
    # iid with FIXED n = mean count (what the report's sd_week_iid_pred uses)
    sd_fixed = sg*math.sqrt(En)
    # iid with RANDOM weekly count (Wald): Var = E[n]sg^2 + Var(n)mu^2
    sd_rand = math.sqrt(En*sg*sg + Vn*mu*mu)
    mw = r["mean_week_r"]
    print("%-12s %7.2f %7.4f %7.4f %7.1f%% %8.1f%% %8.1f%% %8.3f %8.3f %8.3f" % (
        r["policy"].split()[0], n, mu, sg, r["green_week_pct"],
        phi(mw/sd_fixed)*100, phi(mw/sd_rand)*100,
        r["sd_week_r"], sd_fixed, r["sd_week_r"]/sd_fixed))

print()
# monotonicity of the OBSERVED curve
c = [(r["trades_per_week"], r["green_week_pct"], r["policy"].split()[0]) for r in d["capn_curve"]]
c += [(r["trades_per_week"], r["green_week_pct"], r["policy"].split()[0])
      for r in d["policies"] if r["policy"].split()[0] in ("P0","P0u")]
c.sort()
viol = [(a,b) for a,b in zip(c,c[1:]) if b[1] < a[1]]
print("observed count-sorted curve:", [(round(x,2),y,z) for x,y,z in c])
print("MONOTONE VIOLATIONS (%d):" % len(viol), [(a[2],a[1],'->',b[2],b[1]) for a,b in viol])
best = max(c, key=lambda x: x[1])
print("argmax of the curve: %s at %.2f trades/wk = %.1f%%" % (best[2], best[0], best[1]))
