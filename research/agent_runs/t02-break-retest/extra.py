# Per-instrument cells (21 combos x ES/NQ), family-wise p, and detail + gate for the best NQ cell. Post-hoc: labeled as such.
import json, itertools, numpy as np, bt
from collections import defaultdict
import propfirm_gate as PG, propfirm_luck_check as LC
SESS = {r: bt.sessions(r) for r in ("ES", "NQ")}
SIG = {(r, ls): {D: bt.signals(S, ls) for D, S in SESS[r].items()} for r in SESS for ls in ("ALL", "PRE", "OR")}
grid = list(itertools.product(("ALL", "PRE", "OR"), ("LVL", "WIDE"), (1, 2, 3))) + [(ls, "WICK", 2) for ls in ("ALL", "PRE", "OR")]
def book(r, ls, sm, k):
    bk = {}
    for D, sigs in SIG[(r, ls)].items():
        for s in sigs:
            t = bt.trade(SESS[r][D], s, sm, k, r, True)
            if t: bk[D] = t; break
    return bk
cells = {}; M = []
U = sorted(set(SESS["ES"]) | set(SESS["NQ"]))
for r in ("ES", "NQ"):
    dates = U
    for c in grid:
        bk = book(r, *c); cells[(r,) + c] = bk
        M.append([bk[D]["usd"] if D in bk else 0.0 for D in dates])
M = np.array(M); obs = M.mean(1); best = int(obs.argmax())
rng = np.random.default_rng(11); cnt = 0
for _ in range(2000):
    f = rng.choice([-1, 1], size=M.shape[1]); cnt += (M * f).mean(1).max() >= obs.max()
keys = list(cells)
print("cells", len(keys), "best", keys[best], "familywise_p(42 cells)", cnt / 2000)
rank = sorted(range(len(keys)), key=lambda i: -obs[i])[:6]
for i in rank:
    bk = cells[keys[i]]; R = [t["R"] for t in bk.values()]
    print(keys[i], "n", len(R), "meanR %+.3f" % np.mean(R), "$/d %+.1f" % obs[i])
key = ("NQ", "PRE", "LVL", 3)
bk = cells[key]; dates = sorted(SESS["NQ"])
tr = [bk[D] for D in dates if D in bk]
st = bt.stats({D: t["usd"] for D, t in bk.items()}, dates)
R = np.array([t["R"] for t in tr])
print("DETAIL", key, "n", len(tr), "win %.3f" % (R > 0).mean(), "meanR %+.3f" % R.mean(), "$/d %+.1f" % st["per_day"],
      "green %d/%d" % (st["green"], st["months"]), "H1 %+.1f (%d/%d)" % (st["h1"], st["h1_green"], st["h1_m"]),
      "H2 %+.1f (%d/%d)" % (st["h2"], st["h2_green"], st["h2_m"]), "p %.3f" % st["p"],
      "avg n %.1f" % np.mean([t["n"] for t in tr]), "med stop %.2f" % np.median([t["dist"] for t in tr]))
print("exits", {w: sum(t["why"] == w for t in tr) for w in ("tgt", "stop", "time")})
print("by level", {l: (sum(1 for t in tr if t["lvl"] == l), round(float(np.mean([t["R"] for t in tr if t["lvl"] == l] or [0])), 3)) for l in ("pdh", "pdl", "onh", "onl")})
yr = defaultdict(list)
for D in dates:
    if D in bk: yr[D[:4]].append(bk[D]["R"])
print("by year", {y: (len(v), round(float(np.mean(v)), 3)) for y, v in yr.items()})
print("monthly", {m: round(v) for m, v in st["monthly"].items()})
# cost stress: 2 ticks per side
bt.SLIP = 2 * bt.TICK
for c in [("PRE", "LVL", 3), ("PRE", "WIDE", 2), ("PRE", "LVL", 2)]:
    b2 = book("NQ", *c); R2 = [t["R"] for t in b2.values()]
    print("STRESS 2tick NQ", c, "n", len(R2), "meanR %+.3f" % np.mean(R2), "$/d %+.1f" % (sum(t["usd"] for t in b2.values()) / len(dates)))
bt.SLIP = bt.TICK
# gate on NQ PRE/LVL/3R alone ($200 L1 sizing)
base = dict(PG.FIRM_RULES)
base["LucidFlex 50K"] = dict(account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.04, dd_mode="eod", dd_lock_at_breakeven=False,
                             daily_loss_limit_pct=1.0, min_trading_days=0, consistency_pct=0.50, max_days=None)
base["Apex 50K Eval EOD (u06 fix)"] = dict(PG.FIRM_RULES["Apex 50K Eval EOD"], trailing_dd_pct=0.04, max_days=30)
daily = [(D, bk[D]["usd"]) for D in dates if D in bk]
g = PG.gate_series(daily, base)
for hz in (120, 60):
    luck = LC.compute(daily, base, n_shuffles=300, seed=1337, horizon=hz)
    for f in base:
        L = luck[f]
        print("GATE NQ-PRE/LVL/3R hz=%d %-38s %s allstarts=%s eval_ready=%s h1=%s h2=%s" % (hz, f[:38], "PASS" if g[f]["passed"] else "FAIL", g[f]["all_starts_pass_pct"], L["eval_ready"],
              {k: L["h1"][k] for k in ("real_pass_pct", "shuffled_pass_pct", "zero_edge_pass_pct")}, {k: L["h2"][k] for k in ("real_pass_pct", "shuffled_pass_pct", "zero_edge_pass_pct")}))
print("trade days", len(daily), "H1", sum(1 for D, _ in daily if D < bt.SPLIT), "H2", sum(1 for D, _ in daily if D >= bt.SPLIT))
