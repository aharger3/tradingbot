"""The eval is a RETRYABLE $397 seat, not a one-shot gate (g4_prop_fit.md:16,
:40-45). Price it the way g4 does: expected seat spend per funded account."""
import random, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import g71_rtarget_model as M
SEAT = 397.0
series, _ = M.day_series(ROOT / "research/bt2y_trades.json")
srcs = {"P1": series["P1"]["day_r"], "P1-livecap": series["P1"]["day_r_livecap"],
        "P2": series["P2"]["day_r"], "P4": series["P4"]["day_r"]}
print(f"{'policy':12s} {'best $/R':>9} {'p_pass':>8} {'p_blow':>8} {'p_expire':>9} "
      f"{'E[attempts]':>12} {'E[seat $]':>10}")
for name, dr in srcs.items():
    sc = M.Scenario(name, name, "empirical", day_r=dr)
    rnd = random.Random(84)
    rows = [(r, M.prop_eval(sc, float(r), 20_000, rnd, max_days=M.PROP_EVAL_DAYS))
            for r in range(25, 3001, 25)]
    risk, v = max(rows, key=lambda x: x[1]["p_pass"])
    ea = 1.0 / v["p_pass"]
    print(f"{name:12s} {('$%d'%risk):>9} {v['p_pass']*100:7.2f}% {v['p_blow']*100:7.2f}% "
          f"{v['p_expire']*100:8.2f}% {ea:11.2f}x {'$%.0f'%(ea*SEAT):>10}")
print("g4_prop_fit.md:47 baseline for comparison: eval cost/funded $1,006 at 43.0%W.")
