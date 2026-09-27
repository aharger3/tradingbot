import sys, json
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
import propfirm_gate as PG, propfirm_luck_check as LC
cell = sys.argv[1]
tr = json.load(open("trades.json"))
T = sorted(tr[cell + "|OOS"] + tr[cell + "|IS"], key=lambda t: t["date"])
FIRMS = {"Topstep 50K": dict(PG.FIRM_RULES["Topstep 50K Combine"], consistency_pct=0.50, min_trading_days=2),
         "LucidFlex 50K": dict(account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.04, dd_mode="eod",
                               dd_lock_at_breakeven=False, daily_loss_limit_pct=1.0, min_trading_days=0, consistency_pct=0.50, max_days=None)}
for nm, TT in (("IS", tr[cell + "|IS"]), ("IS+OOS", T)):
    daily = [(t["date"], t["usd"]) for t in TT]
    g = PG.gate_series(daily, FIRMS); lk = LC.compute(daily, FIRMS, n_shuffles=300, seed=1337)
    for f in FIRMS:
        print(nm, f, "allstarts", g[f]["all_starts_pass_pct"], "eval_ready", lk[f].get("eval_ready"),
              "h2 real/shuf", lk[f]["h2"]["real_pass_pct"], lk[f]["h2"]["shuffled_pass_pct"], flush=True)
