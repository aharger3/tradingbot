# g/z-regime: does an opening-bar / gap / volatility regime change what Zarattini NQ925 (PR #44) earns?
# zarattini.py and bt.py imported unchanged; NQ925 book at 1 tick is asserted equal to the frozen n=261 book.
# Terciles are cut on TRAIN (dates < bt.SPLIT), tested on TEST, one-sided label-shuffle p in the train-chosen
# direction, BH across all cells. Both halves of TEST reported. Nothing here changes the trade rule.
import sys, json, math
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
ZDIR = next(p for p in (HERE.parents[1] / "zarattini", HERE.parents[3] / "tradingbot-zarattini" / "research" / "zarattini") if (p / "zarattini.py").exists())  # PR #44 dir is untracked
sys.path.insert(0, str(ZDIR))
import zarattini as Z
bt = Z.bt
rng = np.random.default_rng(7)

SESS = {"NQ": bt.sessions("NQ"), "ES": {}}
PRE = {"NQ": Z.pre_bars("NQ"), "ES": {}}
dates = sorted(SESS["NQ"])
bk = Z.book(SESS, PRE, "NQ925", 1)
assert len(bk) == 261, len(bk)

# session features (no look-ahead: only bars <= 09:34 of D plus prior sessions)
sess_rng, sess_close = {}, {}
for D in dates:
    S = SESS["NQ"][D]
    sess_rng[D] = float(S["h"].max() - S["l"].min()); sess_close[D] = float(S["c"][-1])
feat = {}
for i, D in enumerate(dates):
    if D not in bk or i < 5:
        continue
    S = SESS["NQ"][D]; ob = Z.or_bar(S)
    if ob is None:
        continue
    o0, h5, l5, c4 = ob
    atr5 = float(np.mean([sess_rng[dates[j]] for j in range(i - 5, i)]))
    orp = h5 - l5
    feat[D] = dict(or_rel=orp / atr5, or_body=abs(c4 - o0) / orp if orp > 0 else 0.0,
                   gap_rel=abs(o0 - sess_close[dates[i - 1]]) / atr5,
                   gap_with=(o0 - sess_close[dates[i - 1]]) * bk[D]["d"] / atr5,
                   vol_rel=atr5 / float(np.mean(S["c"][:5])) * 100)
R = {D: bk[D]["R"] for D in feat}
train = [D for D in feat if D < bt.SPLIT]; test = [D for D in feat if D >= bt.SPLIT]
th = test[: len(test) // 2]; t2 = test[len(test) // 2:]
print(f"book n={len(bk)} featured n={len(feat)} train {len(train)} test {len(test)} split {bt.SPLIT}", flush=True)


def m(ds):
    return float(np.mean([R[D] for D in ds])) if ds else float("nan")


rows = []
for f in ("or_rel", "or_body", "gap_rel", "gap_with", "vol_rel"):
    x = np.array([feat[D][f] for D in train]); q1, q2 = np.quantile(x, [1 / 3, 2 / 3])
    cut = lambda v: 0 if v < q1 else (1 if v < q2 else 2)
    for tc, name in enumerate(("low", "mid", "high")):
        tr_in = [D for D in train if cut(feat[D][f]) == tc]; tr_out = [D for D in train if cut(feat[D][f]) != tc]
        te_in = [D for D in test if cut(feat[D][f]) == tc]; te_out = [D for D in test if cut(feat[D][f]) != tc]
        d_tr = m(tr_in) - m(tr_out); sgn = 1 if d_tr >= 0 else -1
        d_te = m(te_in) - m(te_out)
        allR = np.array([R[D] for D in test]); k = len(te_in)
        perm = np.array([rng.permutation(allR)[:k].mean() - rng.permutation(allR)[k:].mean() for _ in range(5000)])
        p = float((perm * sgn >= d_te * sgn).mean())
        rows.append(dict(feature=f, tercile=name, cut=(round(float(q1), 3), round(float(q2), 3)), n_train=len(tr_in), R_train_in=m(tr_in),
                         eye_train=d_tr, n_test=k, R_test_in=m(te_in), R_test_out=m(te_out), eye_test=d_te, p_test=p,
                         test_h1=m([D for D in te_in if D in th]), test_h2=m([D for D in te_in if D in t2])))
# BH
ps = sorted((r["p_test"], i) for i, r in enumerate(rows)); nT = len(rows); q = [1.0] * nT; prev = 1.0
for rank, (p, i) in reversed(list(enumerate(ps, 1))):
    prev = min(prev, p * nT / rank); q[i] = prev
for r, qq in zip(rows, q):
    r["q"] = qq
    print(f"{r['feature']:8} {r['tercile']:4} cut={r['cut']} train n={r['n_train']:3} R={r['R_train_in']:+.3f} eye={r['eye_train']:+.3f} | "
          f"test n={r['n_test']:3} R={r['R_test_in']:+.3f} out={r['R_test_out']:+.3f} eye={r['eye_test']:+.3f} p={r['p_test']:.3f} q={qq:.2f} "
          f"H1={r['test_h1']:+.2f} H2={r['test_h2']:+.2f}", flush=True)
base = dict(train=m(train), test=m(test), test_h1=m(th), test_h2=m(t2))
print("base", {k: round(v, 3) for k, v in base.items()})
json.dump(dict(base=base, rows=rows, n_tests=nT), open(HERE / "regime.json", "w"), indent=1, default=float)
