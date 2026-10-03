"""E9 pass-test band: 5th/95th percentile of summed net_R over 17 sessions, bootstrapped by day from the
frozen in-sample replay (frozen orb1m / paper_replay on the paid archive, MNQ, Mon-Thu sessions only).

Day pool = every Mon-Thu archive session in the fit window (no-signal days count as 0R). Net R = the
clock's own formula: gross_R - 1.24 / (stop_R_pts * 2). Window A is never touched (archive starts 2024-09-26).

    python e9_band.py            # prints the band and writes prereg-E9-is-days.csv next to prereg-E9.md
"""
import csv
import sys
from pathlib import Path

import numpy as np

import forward_clock as fc

N_SESSIONS = 17
DRAWS = 100_000
SEED = 20261003
PCTS = (5, 95)
DAYS_CSV = fc.OUT_DIR / "prereg-E9-is-days.csv"


def is_day_table():
    """[(date_str, net_R)] for every Mon-Thu archive session; 0.0 where the frozen engine gives no trade."""
    fc.assert_frozen()
    orb1m, pr = fc.load_engine()
    from omen_data import load_fut
    days = pr.build_is_days(load_fut, orb1m)
    sha = fc.engine_sha()
    rows = {r["date"]: r for r in pr._one_cell(days, sha, orb1m)}
    out = []
    import datetime as dt
    for d, _ in days:
        if dt.date.fromisoformat(d).weekday() > 3:
            continue
        r = rows.get(d)
        net = 0.0 if r is None else r["gross_R"] - fc.COMM_USD / (r["stop_R_pts"] * fc.USD_PT)
        out.append((d, round(net, 4)))
    return out


def bootstrap_band(day_r, n=N_SESSIONS, draws=DRAWS, seed=SEED, pcts=PCTS):
    r = np.asarray(day_r, dtype=float)
    rng = np.random.default_rng(seed)
    sums = r[rng.integers(0, len(r), size=(draws, n))].sum(axis=1)
    return tuple(float(np.percentile(sums, p)) for p in pcts), float(sums.mean())


if __name__ == "__main__":
    tab = is_day_table()
    with DAYS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "net_R"])
        w.writerows(tab)
    R = [x for _, x in tab]
    (lo, hi), mean = bootstrap_band(R)
    trades = sum(1 for x in R if x != 0.0)
    print(f"days={len(tab)} first={tab[0][0]} last={tab[-1][0]} trade_days={trades} mean_per_day={np.mean(R):+.4f}R "
          f"sum_all={sum(R):+.2f}R")
    print(f"band17 p5={lo:.4f} p95={hi:.4f} boot_mean={mean:.4f} (seed={SEED}, draws={DRAWS})")
