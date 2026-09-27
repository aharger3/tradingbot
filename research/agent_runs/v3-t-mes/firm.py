"""v3-t-mes firm gate: Lucid Flex 50K (EOD $2K trail, locks +$100, $3K target, 50% consistency), best MES cell.
Size $200/R: n=min(40, floor(200/(stop$)), floor((cushion-50)/(stop$+1.24+1.25))). Paths: every start (wrap) + 1000 day-bootstraps, H=200.
Luck check: same paths, trades de-meaned to 0R (zero-edge control); bootstrap CI of mean R."""
import json, sys, numpy as np
sys.path.insert(0, "."); from mes import load_fut
rng = np.random.default_rng(8)
res = json.load(open("results.json")); T = json.load(open("trades.json"))
cells = {k: v for k, v in res.items() if k.startswith("MES|")}
score = lambda v: min(x for x in (v["h1"], v["h2"], v["oos_proxy"]["R"]) if x is not None)
best = max(cells, key=lambda k: score(cells[k])); print("best", best, json.dumps(cells[best]))
days = [d for d, _ in load_fut("MES")]; idx = {d: i for i, d in enumerate(days)}; ND = len(days)
tr = T[best]; R = np.array([t["R"] for t in tr]); mR = R.mean()
bs = [rng.choice(R, len(R)).mean() for _ in range(2000)]; print("meanR", round(mR, 3), "CI95", np.round(np.percentile(bs, [2.5, 97.5]), 3))
def daytab(demean):
    risk = np.zeros(ND); rr = np.zeros(ND); v = np.zeros(ND, bool)
    for t in tr:
        i = idx[t["date"]]; risk[i] = t["dist"] * 5; rr[i] = t["R"] - (mR if demean else 0); v[i] = True
    return risk, rr, v
def sim(P, demean):
    risk, rr, v = daytab(demean); passed = 0; bust = 0; dl = []
    for p in P:
        bal = 0.0; floor = -2000.0; best = 0.0; ok = False
        for t, d in enumerate(p):
            if not v[d]: continue
            n = min(40, int(200 // risk[d]), int((bal - floor - 50) // (risk[d] + 1.24 + 1.25)))
            if n < 1: continue
            pnl = n * rr[d] * risk[d]  # R is net of commission+ticks per contract
            bal += pnl; best = max(best, pnl)
            if bal < floor: bust += 1; break
            floor = min(max(floor, bal - 2000), 100)
            if bal >= 3000 and best <= 0.5 * bal: passed += 1; dl.append(t + 1); ok = True; break
    return passed / len(P), bust / len(P), (float(np.median(dl)) if dl else None)
H = 200
st = np.array([[(s + t) % ND for t in range(H)] for s in range(ND)]); sh = rng.integers(0, ND, size=(1000, H))
for nm, P in (("start", st), ("boot", sh)):
    for dm in (False, True):
        pr, bu, md = sim(P, dm); print(f"{nm} {'zero-edge' if dm else 'real'} pass={pr:.3f} bust={bu:.3f} med_days={md}")
