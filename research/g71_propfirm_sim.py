"""G7.1 / propfirm -- what risk-per-trade passes a prop challenge >=90% of the time.

Input   research/g71_propfirm_daily.json, cached from research/bt2y_trades.json
        (the 2-year book, meta.risk_dollars = 1000, 2,437 traded rows).
Model   ONE trade per session = the first traded signal of each day by alert
        time. 496 sessions, mean +0.5809R, 54.4% win, worst day -1.000R -- the
        R1/R2 disaster stop (backtest_week.py:379 `_disaster_hit`) fills on
        TOUCH at exactly -1R, so CLAUDE.md's -1.25R floor is never reached in
        this book. `--floor` re-clips losing days to stress that.
Method  vectorised i.i.d. bootstrap of the daily-R series. Each path walks day
        by day: balance += R*risk (a daily-loss-limit clips the day's loss but
        does NOT fail the account), EOD trailing floor = running EOD peak - maxDD
        clamped at the starting balance, static floor = start - maxDD. Pass =
        balance >= start+target at an EOD before touching the floor, inside the
        day limit.
Note    pass rate is NOT monotone in risk -- too small and the day limit runs
        out, too large and the drawdown gets you -- so this SWEEPS risk and
        reports the whole >=90% band plus the argmax.

Run: python research/g71_propfirm_sim.py [--floor 1.0] [--trials 40000]
"""
import json, os, statistics, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SERIES = "all"
OPP_RATE = 1.0
CONSISTENCY = None  # e.g. 0.30 = best single position <= 30% of total valid profit   # fraction of sessions on which the chosen series fires at all
CACHE = os.path.join(HERE, "g71_propfirm_daily.json")

# name, start, target, daily_loss_limit(None), max_dd, mode, lock, max_days, cost$
FIRMS = [
    # ---- FUTURES prop firms: index futures only. Options NOT tradeable. ----
    ("Topstep 50K Combine",  50000,  3000, 1000, 2000, "eod",    "start", 120, 49),
    ("Topstep 100K Combine", 100000, 6000, 2000, 3000, "eod",    "start", 120, 99),
    ("Topstep 150K Combine", 150000, 9000, 3000, 4500, "eod",    "start", 120, 149),
    ("Apex 50K Eval EOD",    50000,  3000, None, 2500, "eod",    "start", 120, 35),
    ("Apex 100K Eval EOD",   100000, 6000, None, 3000, "eod",    "start", 120, 85),
    ("Apex 150K Eval EOD",   150000, 9000, None, 5000, "eod",    "start", 120, 105),
    ("TPT Test 50K",         50000,  3000, None, 2000, "eod",    "start", 120, 102),
    ("TPT Test 100K",        100000, 6000, None, 3000, "eod",    "start", 120, 150),
    ("TPT Test 150K",        150000, 9000, None, 4500, "eod",    "start", 120, 200),
    ("MFFU Rapid 50K",       50000,  3000, None, 2000, "eod",    "start", 120, 80),
    ("MFFU Rapid 100K",      100000, 6000, None, 3000, "eod",    "start", 120, 150),
    ("Earn2Trade TCP 25K",   25000,  1750, 550,  1500, "eod",    "start", 120, 150),
    ("OneUp 100K",           100000, 6000, None, 3500, "eod",    "start", 120, 105),
    # ---- STOCK prop firms: real US equities/ETFs. Options NOT tradeable. ----
    ("TTP 25K MAX day",      25000,  1500, 250,  750,  "static", None, 60,  97),
    ("TTP 50K MAX day",      50000,  3000, 500,  1500, "static", None, 60,  230),
    ("TTP 100K MAX day",     100000, 6000, 1000, 3000, "static", None, 60,  435),
    ("TTP 200K MAX day",     200000, 12000,2000, 6000, "static", None, 60,  1100),
    ("TTP 25K FLEX day",     25000,  1500, 500,  1000, "static", None, 120, 97),
    ("TTP 50K FLEX day",     50000,  3000, 1000, 2000, "static", None, 120, 230),
    ("TTP 100K FLEX day",    100000, 6000, 2000, 4000, "static", None, 120, 435),
    ("TTP 200K FLEX day",    200000, 12000,4000, 8000, "static", None, 120, 1100),
]

RISK_GRID = list(range(50, 3001, 50))


def daily_r(floor=1.0):
    path = os.path.join(HERE, "g71_propfirm_daily.json" if SERIES == "all"
                        else f"g71_propfirm_daily_{SERIES}.json")
    rs = np.array([o["r"] for o in json.load(open(path))], dtype=float)
    # `floor` here is a STRESS knob, not the engine's stop floor: the 2-year book
    # never books worse than -1.000R because the R1/R2 disaster stop
    # (backtest_week.py:379) fills on TOUCH, so clipping does nothing. Scaling
    # every losing day by `floor` asks the honest question instead -- what if a
    # touch fill slips to -1.25R (CLAUDE.md's own floor) or -2.00R on a gap.
    return np.where(rs < 0, rs * floor, rs)


def simulate(rs, risk, spec, trials, rng):
    """-> (pass_fraction, median days over passing paths)."""
    _, start, target, dll, mdd, mode, _lock, max_days, _ = spec
    draws = rs[rng.integers(0, len(rs), size=(trials, max_days))] * risk
    if dll is not None:
        np.maximum(draws, -float(dll), out=draws)   # daily pause clips the day
    bal = start + np.cumsum(draws, axis=1)
    if mode == "eod":
        peak = np.maximum.accumulate(np.maximum(bal, start), axis=1)
        floor = np.minimum(peak - mdd, start)       # MLL stops trailing at start
    else:
        floor = np.full_like(bal, start - mdd)
    blown = bal <= floor
    hit = bal >= start + target
    if CONSISTENCY is not None:
        # e.g. TTP eval: "the User's best position cannot be responsible for more
        # than 30% of the total valid profit" (tradethepool.com/program-terms/).
        # One trade a day == one position a day, so the day IS the position.
        pos = np.where(draws > 0, draws, 0.0)
        gross = np.cumsum(pos, axis=1)
        biggest = np.maximum.accumulate(pos, axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(gross > 0, biggest / gross, 1.0)
        hit = hit & (ratio <= CONSISTENCY + 1e-9)
    big = max_days + 1
    d_blow = np.where(blown.any(1), blown.argmax(1), big)
    d_hit = np.where(hit.any(1), hit.argmax(1), big)
    won = d_hit < d_blow
    med = float(np.median(d_hit[won]) + 1) if won.any() else float("nan")
    return won.mean(), med


def band(rs, spec, trials, want=0.90, seed=7):
    rng = np.random.default_rng(seed)
    out = [(k, *simulate(rs, k, spec, trials, rng)) for k in RISK_GRID]
    ok = [(k, p, d) for k, p, d in out if p >= want]
    best = max(out, key=lambda z: z[1])
    return ok, best, out


if __name__ == "__main__":
    floor = 1.0; trials = 10000
    if "--consistency" in sys.argv:
        globals()["CONSISTENCY"] = float(sys.argv[sys.argv.index("--consistency") + 1])
    if "--rate" in sys.argv:
        globals()["OPP_RATE"] = float(sys.argv[sys.argv.index("--rate") + 1])
    if "--series" in sys.argv:
        SERIES = sys.argv[sys.argv.index("--series") + 1]
        globals()["SERIES"] = SERIES
    if "--floor" in sys.argv:  floor  = float(sys.argv[sys.argv.index("--floor") + 1])
    if "--trials" in sys.argv: trials = int(sys.argv[sys.argv.index("--trials") + 1])
    rs = daily_r(floor)
    print(f"# series={SERIES} loss floor {floor:.2f}R | N={len(rs)} mean={rs.mean():+.4f}R "
          f"win={100*(rs>0).mean():.1f}% worst={rs.min():+.2f}R | trials={trials}")
    h = (f"{'firm / account':22s} {'tgt':>6s} {'DLL':>5s} {'maxDD':>6s} {'days':>4s} "
         f"{'>=90% risk band':>17s} {'best risk':>9s} {'peak':>6s} {'medDays':>7s}")
    print(h); print("-" * len(h))
    rows = []
    for spec in FIRMS:
        name, start, target, dll, mdd, mode, lock, max_days, cost = spec
        max_days = max(3, int(round(max_days * OPP_RATE)))
        spec = (name, start, target, dll, mdd, mode, lock, max_days, cost)
        ok, best, curve = band(rs, spec, trials)
        bandtxt = f"${ok[0][0]}-${ok[-1][0]}" if ok else "none"
        rows.append(dict(firm=name, start=start, target=target, dll=dll, maxdd=mdd,
                         mode=mode, max_days=max_days, cost=cost, loss_floor=floor,
                         band_lo=ok[0][0] if ok else None, band_hi=ok[-1][0] if ok else None,
                         best_risk=best[0], best_rate=round(float(best[1]), 4),
                         best_median_days=best[2],
                         curve=[[k, round(float(p), 4)] for k, p, _ in curve]))
        print(f"{name:22s} {target:6d} {str(dll):>5s} {mdd:6d} {max_days:4d} "
              f"{bandtxt:>17s} {'$'+str(best[0]):>9s} {best[1]*100:5.1f}% {best[2]:7.0f}")
    out = os.path.join(HERE, f"g71_propfirm_sim_{SERIES}_floor{floor:.2f}"
                       f"{'_c'+str(CONSISTENCY) if CONSISTENCY else ''}.json")
    json.dump(rows, open(out, "w"), indent=1)
    print("\nwrote", out)
