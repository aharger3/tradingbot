"""v2-t09 decomposition: QQQ/SPY 10:30 strong, rv IV. Costs off / theta off (T frozen) to attribute the R gap."""
import numpy as np, opt_proxy as P
from orb1m import signal, CUTS, TICK
from omen_data import load_fut
from orb1m import day_arrays
for sym in ("MNQ", "MES"):
    D = [(str(d), day_arrays(g)) for d, g in load_fut(sym, "09:30", "11:01").groupby("date")]
    cut = CUTS["10:30"]; sigs = []
    for d, A in D:
        s = signal(A, 5, cut, 1.0, "strong")
        if not s: continue
        i, side, stop = s; e = A["open"][i] + TICK * side; dist = (e - stop) * side
        if dist >= 2 * TICK: sigs.append((A, i, side, dist))
    name, ratio, hs, sl = P.ETF[sym]; comm0 = P.COMM; bs0 = P.bs
    def run(tag):
        r = [P.one(sym, A, i, side, dist, cut, "rv", 0) for A, i, side, dist in sigs]
        print(name, tag, "n", len(r), "futR %.3f optR %.3f" % (np.mean([x[0] for x in r]), np.mean([x[1] for x in r])),
              "med stop $/sh %.3f" % np.median([dist / ratio for _, _, _, dist in sigs]), "med hold min", flush=True)
    run("base")
    P.ETF[sym] = (name, ratio, 0.0, 0.0); P.COMM = 0.0; run("no-cost")
    T = {}
    def bs_frozen(S, K, Tt, iv, cp):  # theta off: price every point at entry-time T of the trade (max T seen)
        return bs0(S, K, max(Tt, T.get("t", Tt)), iv, cp)
    orig = P.one
    def one2(sym_, A, i, side, dist, cut_, ivm, otm):
        T["t"] = (390 - i) / P.YR_MIN; return orig(sym_, A, i, side, dist, cut_, ivm, otm)
    P.bs = bs_frozen; P.one = one2; run("no-cost,no-theta"); P.one = orig
    P.ETF[sym] = (name, ratio, hs, sl); P.COMM = comm0; P.bs = bs_frozen; P.one = one2; run("cost,no-theta"); P.one = orig; P.bs = bs0
    holds = [P.sim_t(A, side, i, A["open"][i]+TICK*side - side*dist, A["open"][i]+TICK*side + 2*side*dist, cut)[1] - i for A, i, side, dist in sigs]
    print(name, "hold minutes median", np.median(holds), "mean", np.mean(holds))
