"""Is the 30-day arm's 10% gate reachable BY ANY scenario, including the
money gate itself (55% win / +2.0R mean, one trade a day)? If the system's own
success condition also returns NONE, the arm measures the 21-day horizon, not
the one-trade-a-day policy."""
import random, sys, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import g71_rtarget_model as M

series, meta = M.day_series(ROOT / "research/bt2y_trades.json")
scens = [
    M.Scenario("gate", "money gate 55%/2.0R 1/day", "parametric", w=0.55, mean_r=2.0, trades_per_day=1.0),
    M.Scenario("mid", "55%/1.20R 1/day", "parametric", w=0.55, mean_r=1.20, trades_per_day=1.0),
    M.Scenario("today_book", "today headline 4.91 trades/day", "parametric", w=0.431, mean_r=0.5481, trades_per_day=4.91),
    M.Scenario("p1", "P1 measured", "empirical", day_r=series["P1"]["day_r"]),
]
for sc in scens:
    rnd = random.Random(84)
    best = None; rows = []
    for risk in range(25, 3001, 25):
        r = M.prop_eval(sc, float(risk), 20_000, rnd, max_days=M.PROP_EVAL_DAYS)
        rows.append((risk, r))
    mn = min(rows, key=lambda x: x[1]["p_fail"])
    clears = [x for x in rows if x[1]["p_fail"] <= 0.10]
    print(f"{sc.label:34s} meanR/day={sc.day_mean:+.3f}  "
          f"min p_fail ${mn[0]} = {mn[1]['p_fail']*100:.2f}%  "
          f"clears10%={'YES @$'+str(max(c[0] for c in clears)) if clears else 'NONE'}")
