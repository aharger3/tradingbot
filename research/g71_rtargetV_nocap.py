"""No-time-cap arm: is p_fail monotone in risk? solve_risk_for_fail breaks on
the first failing unit AFTER a success, so a non-monotone curve returns a LOCAL
ceiling. Full grid, no early break."""
import random, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import g71_rtarget_model as M
series, _ = M.day_series(ROOT / "research/bt2y_trades.json")
for key, dr in (("p1", series["P1"]["day_r"]), ("p1_live", series["P1"]["day_r_livecap"]),
                ("p2", series["P2"]["day_r"]), ("p4", series["P4"]["day_r"])):
    sc = M.Scenario(key, key, "empirical", day_r=dr)
    rnd = random.Random(84)
    rows = []
    for risk in range(25, 1501, 25):
        r = M.prop_eval(sc, float(risk), 20_000, rnd, max_days=None)
        rows.append((risk, r["p_fail"]))
    clears = [r for r, f in rows if f <= 0.10]
    # what the model's early-break solver would return
    best = None
    for r, f in rows:
        if f <= 0.10: best = r
        elif best is not None: break
    print(f"{key:8s} solver(local)=${best}  global max clearing=${max(clears) if clears else None}  "
          f"all clearing units: {clears}")
