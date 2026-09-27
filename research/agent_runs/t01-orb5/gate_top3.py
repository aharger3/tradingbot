"""Run the tradingbot prop-firm gate (propfirm_gate.gate_series + propfirm_luck_check.compute)
on the top-3 ORB-5 combos. Ranking rule fixed before looking: full-sample avg net R on the
proxy grid (longest sample). Sizing: u07 L1, $200 risk/trade in micros, n = floor(200/(risk$+comm)),
cap 50; plus a 1-contract series. LucidFlex 50K row added locally (u06), core FIRM_RULES untouched."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\aharg\Desktop\Projects\tradingbot"
sys.path.insert(0, os.path.join(ROOT, "research")); sys.path.insert(0, ROOT)
from propfirm_gate import FIRM_RULES, gate_series
import propfirm_luck_check

PT = {"MES": 5.0, "MNQ": 2.0}; COMM = 1.24
FIRMS = dict(FIRM_RULES)
FIRMS["LucidFlex 50K (u06, agg-sourced)"] = dict(
    account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.04, dd_mode="eod",
    dd_lock_at_breakeven=False, daily_loss_limit_pct=1.0, min_trading_days=0,
    consistency_pct=0.50, max_days=None, cost_dollars=146.0,
    source="u06-prop-firms.md (proptradingvibes 9/16); target $3,000 assumed", verify="aggregator")

grid = json.load(open(os.path.join(HERE, "grid_proxy.json")))
top = sorted(grid, key=lambda k: -(grid[k].get("avgR") or -9))[:3]
out = {}
for src in ("proxy", "fut"):
    for key in top:
        inst, combo = key.split("|", 1)
        p = os.path.join(HERE, f"trades_{src}_{inst}.json")
        if not os.path.exists(p):
            continue
        tr = json.load(open(p))[combo]
        for sizing in ("1ct", "L1_$200"):
            daily = []
            for x in tr:
                n = 1 if sizing == "1ct" else min(50, int(200 // (x["risk"] * PT[inst] + COMM)))
                if n > 0:
                    daily.append((x["day"], n * x["usd"]))
            res = gate_series(daily, FIRMS)
            luck = propfirm_luck_check.compute(daily, FIRMS, n_shuffles=100)
            row = {}
            for f, r in res.items():
                row[f] = dict(passed=r["passed"], fail_reason=r["fail_reason"], fail_day=r["fail_day"],
                              all_starts_pct=r["all_starts_pass_pct"], eval_ready=luck[f]["eval_ready"],
                              luck={k: v for k, v in luck[f].items() if k != "eval_ready"})
            k = f"{src}|{key}|{sizing}"
            out[k] = dict(n_days=len(daily), total=sum(v for _, v in daily), firms=row)
            print(k, "days", len(daily), "total $%.0f" % out[k]["total"])
            for f, r in row.items():
                print("   %-40s %-5s %-18s all-starts %5s%%  eval_ready %s" % (
                    f[:40], "PASS" if r["passed"] else "FAIL", r["fail_reason"] or "-",
                    r["all_starts_pct"], r["eval_ready"]))
json.dump(dict(top=top, gate=out), open(os.path.join(HERE, "gate_top3.json"), "w"), indent=1, default=str)
