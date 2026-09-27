# g-portfolio: combine the surviving OMEN leads into one daily book and run prop-firm pass odds.
# Streams (all in R, paper, honest fills as produced by their own frozen code):
#   Z = Zarattini 5-min ORB on NQ traded as MNQ, NQ 09:25 filter, 1 tick slip (research/zarattini, PR #44)
#   O = MNQ ORB5 mantra cell, trades_MNQ_OR5_1030_D1_strong.json (v2-t01, frozen orb1m.py)
#   S = Austin's S-graded marks, first S per day, R2_eng (v3-s-dataset). HINDSIGHT grades, stocks/ETFs.
# Prop rules reused from research/propfirm_gate.py (Topstep row) + a LucidFlex 50K row (u06 numbers).
import sys, json, random
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
WT = HERE.parents[1]
PROD = WT.parent / "tradingbot" / "research" / "agent_runs"
sys.path[:0] = [str(WT / "research" / "zarattini"), str(WT / "research")]
import zarattini as Zm, bt
import propfirm_gate as PG

RNG = np.random.default_rng(7); random.seed(7)
SESS = {r: bt.sessions(r) for r in ("NQ", "ES")}
PRE = {r: Zm.pre_bars(r) for r in ("NQ", "ES")}
DATES = sorted(SESS["NQ"])
zb = Zm.book(SESS, PRE, "NQ925", 1)
Z = {D: t["R"] for D, t in zb.items()}
Zside = {D: t["d"] for D, t in zb.items()}
orb = json.load(open(PROD / "v2-t01-orb-1m" / "trades_MNQ_OR5_1030_D1_strong.json"))
O = {t["date"]: t["R"] for t in orb}; Oside = {t["date"]: t["side"] for t in orb}
st = pd.read_csv(PROD / "v3-s-dataset" / "s_trades.csv")
st = st[(st.grade == "S") & st.R2_eng.notna()].sort_values(["date", "sig_t"]).groupby("date").first()
S = st.R2_eng.to_dict()
DATES = sorted(set(DATES) | set(O) | set(S))
DATES = [d for d in DATES if "2024-09-26" <= d <= "2026-09-25"]
STREAMS = {"Z": Z, "O": O, "S": S}
M = pd.DataFrame({k: [v.get(d, 0.0) for d in DATES] for k, v in STREAMS.items()}, index=DATES)
out = {"days": len(DATES), "first": DATES[0], "last": DATES[-1], "streams": {}, "corr": {}, "books": {}, "prop": {}}

def mdd(x):
    eq = np.cumsum(x); return float((np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max())

def signflip_p(cols, n=5000):
    obs = M[cols].sum(1).mean(); A = M[cols].values; hits = 0
    for _ in range(n):
        hits += (A * RNG.choice([-1, 1], size=A.shape)).sum(1).mean() >= obs
    return (hits + 1) / (n + 1)

for k, v in STREAMS.items():
    r = np.array([v[d] for d in DATES if d in v])
    out["streams"][k] = dict(n=len(r), R_trade=r.mean(), win=(r > 0).mean(), R_day=M[k].mean(), maxDD_R=mdd(M[k].values))
for a, b in (("Z", "O"), ("Z", "S"), ("O", "S")):
    both = M[(M[a] != 0) & (M[b] != 0)]
    out["corr"][a + b] = dict(all_days=float(M[a].corr(M[b])), overlap_n=len(both),
                             overlap=float(both[a].corr(both[b])) if len(both) > 3 else None)
opp = [d for d in O if d in Zside and Zside[d] != Oside[d]]
out["corr"]["ZO_same_day"] = sum(d in Z for d in O); out["corr"]["ZO_opposite_side"] = len(opp)

LUCID = dict(account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.04, dd_mode="eod",
             dd_lock_at_breakeven=True, daily_loss_limit_pct=1.0, min_trading_days=2, consistency_pct=0.50, max_days=None)
FIRMS = {"LucidFlex 50K": LUCID, "Topstep 50K": PG.FIRM_RULES["Topstep 50K Combine"]}
KW = lambda r: PG._challenge_kwargs(r)

def boot(daily, rule, n=1000, horizon=120, block=5):
    x = np.asarray(daily); L = len(x); P = []; days = []
    for _ in range(n):
        idx = np.concatenate([np.arange(s, s + block) % L for s in RNG.integers(0, L, horizon // block + 1)])[:horizon]
        res = PG.evaluate_prop_challenge([(i, float(x[j])) for i, j in enumerate(idx)], **KW(rule))
        P.append(res["passed"])
        if res["passed"]: days.append(res["days_traded"])
    return float(np.mean(P)), (float(np.median(days)) if days else None)

BOOKS = {"Z": ["Z"], "O": ["O"], "Z+O": ["Z", "O"], "Z+O+S": ["Z", "O", "S"]}
H = len(DATES) // 2
for name, cols in BOOKS.items():
    d = M[cols].sum(1)
    out["books"][name] = dict(R_day=d.mean(), total_R=d.sum(), maxDD_R=mdd(d.values), sharpe=d.mean() / d.std() * np.sqrt(252),
                              h1=d.iloc[:H].mean(), h2=d.iloc[H:].mean(), green_days=float((d > 0).mean()),
                              p_signflip=signflip_p(cols), monthly=d.groupby(d.index.str[:7]).sum().round(2).to_dict())
    for per_R in (100, 200):
        usd = (d * per_R).values; z = usd - usd.mean()
        for fn, rule in FIRMS.items():
            key = f"{name}|${per_R}/R|{fn}"
            r1 = dict(rule, max_days=rule.get("max_days") or 120)
            allp, nst = PG.all_starts_pass_rate([(D, float(u)) for D, u in zip(DATES, usd)], r1)
            bp, bd = boot(usd, rule); zp, _ = boot(z, rule)
            out["prop"][key] = dict(all_starts_pct=allp, boot_pass=bp, boot_med_days=bd, zero_edge_pass=zp)
            print(key, out["prop"][key], flush=True)
    print(name, {k: v for k, v in out["books"][name].items() if k != "monthly"}, flush=True)
print(json.dumps({k: out[k] for k in ("streams", "corr")}, default=float, indent=1))
print("keys", list(PG.evaluate_prop_challenge([(0, 3500.0), (1, 10.0)], **KW(LUCID)).keys()))
json.dump(out, open(HERE / "portfolio.json", "w"), default=float, indent=1)
