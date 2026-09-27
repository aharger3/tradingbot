"""Prop gate + luck check on the best IS NQ/ES cell (2R or 4T). Daily $ scaled x0.5 -> ~$500/R (1 NQ ~ 21pt)."""
import sys, json
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
import propfirm_gate as PG, propfirm_luck_check as LC
from omen_data import load_fut
g = json.load(open("grid.json")); T = json.load(open("trades.json"))
cand = [(k, v) for k, v in g.items() if k.endswith("|IS") and not k.startswith("CHECK") and v["n"] >= 30 and (v["h1"] or -1) > 0 and (v["h2"] or -1) > 0]
cand.sort(key=lambda kv: -kv[1]["usd_day"])
FIRMS = {"Topstep 50K": dict(PG.FIRM_RULES["Topstep 50K Combine"], consistency_pct=0.50, min_trading_days=2),
         "LucidFlex 50K": PG.FIRM_RULES["LucidFlex 50K"]}
sym = None
for k, v in cand[:3]:
    s = k.split("|")[0]
    dates = sorted(set(str(d) for d in load_fut(s, "09:30", "09:31")["date"]))
    tr = {d: u * 0.5 for d, u in T[k]}
    daily = [(d, tr.get(d, 0.0)) for d in dates]
    gg = PG.gate_series(daily, FIRMS); lk = LC.compute(daily, FIRMS, n_shuffles=300, seed=1337)
    row = {f: dict(all_starts=gg[f]["all_starts_pass_pct"], eval_ready=lk[f].get("eval_ready"),
                   h1=(lk[f].get("h1") or {}).get("real_pass_pct"), h2=(lk[f].get("h2") or {}).get("real_pass_pct"),
                   h2shuf=(lk[f].get("h2") or {}).get("shuffled_pass_pct"), err=lk[f].get("error")) for f in FIRMS}
    print("GATE", k, json.dumps(v["usd_day"]), json.dumps(row, default=str), flush=True)
if not cand: print("GATE none: no IS cell with n>=30 and both halves >0")
