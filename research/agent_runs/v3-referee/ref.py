"""v3-referee: re-run headline MNQ cell (v2 baseline OR5 D1 strong, 10:30, 2R) from v3-t-mnq/mnq.py."""
import sys, os, json, glob, hashlib
import numpy as np
AR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs"
sys.path.insert(0, AR + r"\v3-t-mnq")
import mnq
print("orb1m sha", hashlib.sha256(open(AR + r"\v2-t01-orb-1m\orb1m.py", "rb").read()).hexdigest()[:12])
S = "v2 baseline (OR5 D1.0 strong)"
prox = mnq.load_proxy()
print("proxy days", len(prox), prox[0]["date"], prox[-1]["date"])
T, sh = mnq.run_cell(prox, S, "10:30", "2R", nshuf=200)
print("OOS", json.dumps(mnq.summ(T, sh, prox)))
nq = glob.glob(AR + r"\t01-orb5\fut\NQ*.csv")
print("NQ csv on disk", len(nq))
if nq:
    real = mnq.load_real(); T, sh = mnq.run_cell(real, S, "10:30", "2R", nshuf=200)
    print("IS", json.dumps(mnq.summ(T, sh, real)))
# IS from the frozen v2 trade list
f = AR + r"\v2-t01-orb-1m\trades_MNQ_OR5_1030_D1_strong.json"
d = json.load(open(f)); tl = d if isinstance(d, list) else d.get("trades", d)
print("v2 trade list type", type(d).__name__, "len", len(tl))
if isinstance(tl, list) and tl and isinstance(tl[0], dict):
    print("keys", list(tl[0].keys()))
    k = "R" if "R" in tl[0] else ("r" if "r" in tl[0] else None)
    if k:
        R = np.array([t[k] for t in tl]); n = len(R); h = n // 2
        print("v2 list n", n, "R", round(R.mean(), 3), "win", round((R > 0).mean(), 3), "h1", round(R[:h].mean(), 3), "h2", round(R[h:].mean(), 3))
# res.json stored
r = json.load(open(AR + r"\v3-t-mnq\res.json"))[S + "|10:30|2R"]
print("res.json", json.dumps({k: {x: r[k].get(x) for x in ("n", "R", "h1", "h2", "p")} for k in r}))
