import sys, json, numpy as np
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
import propfirm_gate as PG, propfirm_luck_check as LC
B = json.load(open("books.json"))
# walk-forward: choose best cell by mean R on train years, report next year
def yr(k, ys):
    t = [x["R"] for x in B[k] if x["date"][:4] in ys]; return (np.mean(t) if t else -9, len(t))
for tr, te in ((("2024",), "2026x"), (("2024",), "2025"), (("2024", "2025"), "2026")):
    if te == "2026x": continue
    best = max(B, key=lambda k: yr(k, tr)[0]); print("WF train", tr, "pick", best, "trainR %.3f" % yr(best, tr)[0], "test", te, "R %.3f n %d" % yr(best, (te,)))
FIRMS = {"Topstep 50K": dict(PG.FIRM_RULES["Topstep 50K Combine"], consistency_pct=0.50, min_trading_days=2),
         "LucidFlex 50K": dict(account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.04, dd_mode="eod", dd_lock_at_breakeven=False,
                               daily_loss_limit_pct=1.0, min_trading_days=0, consistency_pct=0.50, max_days=None)}
for k in ("QQQ|mantra|10:30|4tier", "QQQ|mantra|10:30|2R"):
    daily = [(t["date"], t["usd"]) for t in B[k]]
    g = PG.gate_series(daily, FIRMS); lk = LC.compute(daily, FIRMS, n_shuffles=300, seed=1337)
    for f in FIRMS:
        print(k, f, "allstarts", g[f]["all_starts_pass_pct"], "eval_ready", lk[f].get("eval_ready"), "h2 real", lk[f]["h2"]["real_pass_pct"], "h2 shuf", lk[f]["h2"]["shuffled_pass_pct"])
