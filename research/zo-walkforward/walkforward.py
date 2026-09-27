# zo-book-walkforward: slice g-portfolio's Z+O book by calendar quarter / year with FIXED params
# (no re-tuning), measure tail concentration, paper-month drawdown band, and prop pass odds when
# the future is assumed to look like one held-out quarter at a time.
# Streams are built exactly as research/g-portfolio/portfolio.py builds them (same code, same files).
# Pre-declared bar: >= 6/9 quarters positive AND top-5-trade tail share < 50%.
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
WT = Path(os.environ.get("ZO_WT") or HERE.parents[1])
PROD = WT.parent / "tradingbot" / "research" / "agent_runs"
sys.path[:0] = [str(WT / "research" / "zarattini"), str(WT / "research")]
import zarattini as Zm, bt
import propfirm_gate as PG

RNG = np.random.default_rng(11)
SESS = {r: bt.sessions(r) for r in ("NQ", "ES")}
PRE = {r: Zm.pre_bars(r) for r in ("NQ", "ES")}
zb = Zm.book(SESS, PRE, "NQ925", 1)
Z = {D: t["R"] for D, t in zb.items()}
orb = json.load(open(PROD / "v2-t01-orb-1m" / "trades_MNQ_OR5_1030_D1_strong.json"))
O = {t["date"]: t["R"] for t in orb}
DATES = sorted(set(SESS["NQ"]) | set(O))
DATES = [d for d in DATES if "2024-09-26" <= d <= "2026-09-25"]
M = pd.DataFrame({k: [v.get(d, 0.0) for d in DATES] for k, v in {"Z": Z, "O": O}.items()}, index=DATES)
M["ZO"] = M.Z + M.O
qkey = lambda d: f"{d[2:4]}Q{(int(d[5:7]) - 1) // 3 + 1}"
M["q"] = [qkey(d) for d in DATES]; M["y"] = [d[:4] for d in DATES]
out = {"days": len(DATES), "first": DATES[0], "last": DATES[-1], "bar": ">=6/9 quarters positive and top-5 tail share < 50%"}

# sanity: must reproduce portfolio.json's Z+O +0.241 R/day
out["R_day"] = {k: float(M[k].mean()) for k in ("Z", "O", "ZO")}

def mdd(x):
    eq = np.cumsum(x); return float((np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max()) if len(x) else 0.0

def slice_stats(g):
    return dict(days=len(g), n_Z=int((g.Z != 0).sum()), n_O=int((g.O != 0).sum()),
                Z=round(float(g.Z.sum()), 2), O=round(float(g.O.sum()), 2), ZO=round(float(g.ZO.sum()), 2),
                ZO_R_day=round(float(g.ZO.mean()), 3), maxDD=round(mdd(g.ZO.values), 2))

out["quarters"] = {q: slice_stats(g) for q, g in M.groupby("q")}
out["years"] = {y: slice_stats(g) for y, g in M.groupby("y")}
Q = out["quarters"]
out["q_positive"] = {k: f"{sum(v[k] > 0 for v in Q.values())}/{len(Q)}" for k in ("Z", "O", "ZO")}
wq = min(Q, key=lambda q: Q[q]["ZO"]); out["worst_quarter"] = dict(q=wq, R=Q[wq]["ZO"])
tot = float(M.ZO.sum()); qs = sorted((v["ZO"] for v in Q.values()), reverse=True)
out["best2_quarter_share"] = round(sum(qs[:2]) / tot, 3)

# tail share: top-5 individual trades' R / total R
trades = {"Z": list(Z[d] for d in DATES if d in Z), "O": list(O[d] for d in DATES if d in O)}
trades["ZO"] = trades["Z"] + trades["O"]
out["tail5_share"] = {k: round(sum(sorted(v, reverse=True)[:5]) / sum(v), 3) for k, v in trades.items()}
out["tail5_share_days"] = round(float(M.ZO.sort_values(ascending=False).iloc[:5].sum()) / tot, 3)
out["ZO_ex_top5_R_day"] = round((tot - sum(sorted(trades["ZO"], reverse=True)[:5])) / len(DATES), 3)

# paper month (21 sessions): rolling all-starts + block bootstrap
W = 21; x = M.ZO.values
roll = [(x[s:s + W].sum(), mdd(x[s:s + W])) for s in range(len(x) - W + 1)]
def blk(xx, n, block=5):
    L = len(xx); idx = np.concatenate([np.arange(s, s + block) % L for s in RNG.integers(0, L, n // block + 1)])[:n]
    return xx[idx]
bs = [(p.sum(), mdd(p)) for p in (blk(x, W) for _ in range(5000))]
def band(rows):
    a = np.array(rows)
    return dict(month_R_p5=round(float(np.percentile(a[:, 0], 5)), 2), month_R_p50=round(float(np.median(a[:, 0])), 2),
                month_R_p95=round(float(np.percentile(a[:, 0], 95)), 2), maxDD_p90=round(float(np.percentile(a[:, 1], 90)), 2),
                p_month_negative=round(float((a[:, 0] < 0).mean()), 3))
out["paper_month"] = {"rolling": band(roll), "bootstrap": band(bs)}

# prop odds under each held-out quarter's distribution ($200/R, 120-day horizon, 5-day blocks)
LUCID = dict(account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.04, dd_mode="eod",
             dd_lock_at_breakeven=True, daily_loss_limit_pct=1.0, min_trading_days=2, consistency_pct=0.50, max_days=None)
FIRMS = {"Lucid": LUCID, "Topstep": PG.FIRM_RULES["Topstep 50K Combine"]}
def boot(daily, rule, n=600, horizon=120):
    P = [PG.evaluate_prop_challenge([(i, float(v)) for i, v in enumerate(blk(daily, horizon))], **PG._challenge_kwargs(rule))["passed"] for _ in range(n)]
    return round(float(np.mean(P)), 3)
PER_R = 200
out["prop_by_quarter"] = {}
for q, g in M.groupby("q"):
    if len(g) < 20: continue  # 24Q3 = 3 sessions, too short to resample
    usd = g.ZO.values * PER_R
    out["prop_by_quarter"][q] = {fn: boot(usd, r) for fn, r in FIRMS.items()}
    print(q, out["prop_by_quarter"][q], flush=True)
pq = out["prop_by_quarter"]
full = M.ZO.values * PER_R
out["prop_summary"] = {fn: dict(
    median_q=float(np.median([v[fn] for v in pq.values()])), min_q=float(min(v[fn] for v in pq.values())),
    max_q=float(max(v[fn] for v in pq.values())),
    quarter_block_boot=None, full_boot=boot(full, r, 1000), zero_edge=boot(full - full.mean(), r, 1000)) for fn, r in FIRMS.items()}
# whole-quarter block bootstrap: stitch random quarters (each ~63 sessions) into 120-day paths
qarr = [g.ZO.values * PER_R for q, g in M.groupby("q") if len(g) >= 20]
for fn, r in FIRMS.items():
    P = []
    for _ in range(1000):
        path = np.concatenate([qarr[i] for i in RNG.integers(0, len(qarr), 3)])[:120]
        P.append(PG.evaluate_prop_challenge([(i, float(v)) for i, v in enumerate(path)], **PG._challenge_kwargs(r))["passed"])
    out["prop_summary"][fn]["quarter_block_boot"] = round(float(np.mean(P)), 3)
# ex-best-2-quarters bootstrap (what if 25Q3/25Q4 never repeat)
top2 = sorted(Q, key=lambda q: Q[q]["ZO"], reverse=True)[:2]
ex = M[~M.q.isin(top2)].ZO.values * PER_R
out["prop_ex_best2"] = dict(dropped=top2, R_day=round(float(ex.mean() / PER_R), 3), **{fn: boot(ex, r, 1000) for fn, r in FIRMS.items()})

qp = sum(v["ZO"] > 0 for v in Q.values())
out["verdict"] = dict(quarters_positive=qp, n_quarters=len(Q), tail5=out["tail5_share"]["ZO"],
                      passes_bar=bool(qp >= 6 and len(Q) == 9 and out["tail5_share"]["ZO"] < 0.50))
print(json.dumps({k: v for k, v in out.items()}, default=float, indent=1))
json.dump(out, open(HERE / "walkforward.json", "w"), default=float, indent=1)
