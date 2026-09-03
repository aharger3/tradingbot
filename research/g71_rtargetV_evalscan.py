"""ADVERSARIAL VERIFY of research/g71_rtarget.md 4b / model section 5.

Independent re-run of the 30-day Apex eval scan. Reuses the model module's
day_series + prop_eval verbatim (no re-implementation), then reports the FULL
$25 grid rather than only the argmax the solver keeps, and splits p_fail into
its two components (blow vs expire) which section 5 collapses into one number.
"""
import json, random, statistics, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import g71_rtarget_model as M

TRIALS = 20_000
series, meta = M.day_series(ROOT / "research/bt2y_trades.json")
print("book meta:", meta)
for k in ("P1", "P2", "P4"):
    dr = series[k]["day_r"]; tr = series[k]["trade_r"]
    print(f"{k}: days={len(dr)} trades={len(tr)} meanR/day={statistics.mean(dr):+.4f} "
          f"meanR/trade={statistics.mean(tr):+.4f} sd/day={statistics.pstdev(dr):.4f}")

scens = {
    "p1":      M.Scenario("p1", "P1", "empirical", day_r=series["P1"]["day_r"]),
    "p1_live": M.Scenario("p1_live", "P1 live-cap", "empirical", day_r=series["P1"]["day_r_livecap"]),
    "p2":      M.Scenario("p2", "P2", "empirical", day_r=series["P2"]["day_r"]),
    "p4":      M.Scenario("p4", "P4", "empirical", day_r=series["P4"]["day_r"]),
}

out = {}
for name, sc in scens.items():
    print(f"\n=== {name}  (mean {sc.day_mean:+.4f}R/day, sd {sc.day_sd:.4f}) ===")
    print(f"{'risk':>7} {'p_fail':>8} {'p_blow':>8} {'p_expire':>9} {'p_pass':>8}")
    rows = []
    rnd = random.Random(84)
    for risk in range(25, 3001, 25):
        r = M.prop_eval(sc, float(risk), TRIALS, rnd, max_days=M.PROP_EVAL_DAYS)
        rows.append((risk, r))
        if risk % 100 == 0 or risk <= 200:
            print(f"${risk:>6} {r['p_fail']*100:7.2f}% {r['p_blow']*100:7.2f}% "
                  f"{r['p_expire']*100:8.2f}% {r['p_pass']*100:7.2f}%")
    best_fail = min(rows, key=lambda x: x[1]["p_fail"])
    blow_ok = [x for x in rows if x[1]["p_blow"] <= 0.10]
    print(f"  MIN p_fail over grid: ${best_fail[0]} -> {best_fail[1]['p_fail']*100:.2f}% "
          f"(pass {best_fail[1]['p_pass']*100:.2f}%)")
    if blow_ok:
        top = max(blow_ok, key=lambda x: x[0])
        print(f"  LARGEST unit with p_BLOW<=10%: ${top[0]} -> blow {top[1]['p_blow']*100:.2f}% "
              f"pass {top[1]['p_pass']*100:.2f}% expire {top[1]['p_expire']*100:.2f}%")
    out[name] = {"min_pfail_risk": best_fail[0], "min_pfail": best_fail[1]["p_fail"],
                 "pass_at_min": best_fail[1]["p_pass"],
                 "grid": [(r, v["p_fail"], v["p_blow"], v["p_pass"]) for r, v in rows]}
(ROOT / "research/_g71_rtargetV_evalscan.json").write_text(json.dumps(out, indent=1))
print("\nwrote research/_g71_rtargetV_evalscan.json")
