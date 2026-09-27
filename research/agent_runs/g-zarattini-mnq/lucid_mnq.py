# g-zarattini-mnq: Zarattini NQ925 (research/zarattini, unchanged) mapped to integer MNQ sizing and LucidFlex 50K rules.
# 1 per-trade book (15:59 exit = original; 11:00 exit = Austin's window), asserted == robust.book at 15:59
# 2 quarterly walk-forward of the fixed rule + anchored gate   3 permutation p (random direction, sign-flip)
# 4 LucidFlex eval + funded first payout: history (circular starts), block bootstrap, zero-edge null.
# Lucid (u06/t08, aggregator-sourced): $3K target, $2K EOD trail locks at +$100 (breach checked on intraday MAE),
#   no DLL, 50% consistency in eval, 40 micro cap, $146; funded: 5 days >= $150, payout min(50%, $2K) x 0.9.
import sys, json, math
from pathlib import Path
from collections import defaultdict
import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "zarattini"))
import robust as RB
Z = RB.Z; bt = Z.bt
MV, CM, TK = bt.V["NQ"], bt.COMM, bt.TICK
FEE, TGT, TRAIL, LOCK, CAP = 146.0, 3000.0, 2000.0, 100.0, 40


def trade(S, d, slip=1, cut=960, T=10):
    """Zarattini trade in direction d, flat at the close of the last bar with tod < cut. pts/mae in NQ points."""
    tod = S["tod"]
    if list(tod[:6]) != list(range(570, 576)):
        return None
    o, h, l, c = S["o"], S["h"], S["l"], S["c"]
    se = slip * TK; ss = 2 * se
    fill = o[5] + d * se
    ext = l[:5].min() if d == 1 else h[:5].max()
    dist = (fill - ext) * d
    if dist <= 0:
        return None
    stop = fill - d * dist; tgt = fill + d * T * dist
    ex = None; mae = 0.0; last = 5
    for b in range(5, len(o)):
        if tod[b] >= cut:
            break
        last = b
        lo, hi = (l[b], h[b]) if d == 1 else (-h[b], -l[b])
        if lo <= stop * d:
            ex = d * min(stop * d, o[b] * d) - d * ss; why = "stop"; break
        mae = max(mae, fill * d - lo)
        if hi >= tgt * d + TK:
            ex = d * max(tgt * d, o[b] * d); why = "tgt"; break
    if ex is None:
        ex = c[last] - d * se; why = "close"
    pts = (ex - fill) * d
    return dict(d=d, dist=dist, pts=pts, mae=max(mae, -pts), why=why, R=(pts * MV - CM) / (dist * MV))


def books(SESS, PRE, cut):
    """{date: {'sig': trade in the opening-bar direction, 'alt': opposite-direction trade}} on NQ925 days."""
    out = {}
    for D, S in SESS["NQ"].items():
        if list(S["tod"][:6]) != list(range(570, 576)):
            continue
        d = int(np.sign(S["c"][4] - S["o"][0]))
        if d == 0 or PRE["NQ", 5].get((S["tk"], D)) != d:
            continue
        a, b = trade(S, d, cut=cut), trade(S, -d, cut=cut)
        if a:
            out[D] = dict(sig=a, alt=b)
    return out


def perm(bk, rng, N=20000):
    sig = np.array([v["sig"]["R"] for v in bk.values()])
    alt = np.array([v["alt"]["R"] if v["alt"] else 0.0 for v in bk.values()])
    flip = rng.random((N, len(sig))) < 0.5
    rd = np.where(flip, alt, sig).mean(1)
    sf = (sig * np.where(rng.random((N, len(sig))) < 0.5, -1, 1)).mean(1)
    return dict(n=len(sig), R_trade=round(float(sig.mean()), 3), p_randdir=float((rd >= sig.mean()).mean()),
                p_signflip=float((sf >= sig.mean()).mean()))


def size(t, B):
    return min(CAP, int(B // (t["dist"] * MV + CM)))


def day_seq(bk, dates, B, shift_R=0.0, monthu=False):
    """per session: (pnl $, intraday worst $). shift_R subtracts R*1-contract-risk per contract (zero-edge null)."""
    pnl = np.zeros(len(dates)); worst = np.zeros(len(dates))
    for i, D in enumerate(dates):
        v = bk.get(D)
        if v is None or (monthu and __import__("datetime").date.fromisoformat(D).weekday() == 4):
            continue
        t = v["sig"]; n = size(t, B)
        if n == 0:
            continue
        pnl[i] = n * (t["pts"] * MV - CM - shift_R * (t["dist"] * MV + CM))
        worst[i] = min(pnl[i], -n * (t["mae"] * MV + CM))
    return pnl, worst


def lucid(pnl, worst, H_eval=200, H_fund=120):
    """eval then funded on the continuing path. Returns (status, sessions, payout)."""
    bal = peak = best = 0.0; fl = -TRAIL
    for i in range(min(H_eval, len(pnl))):
        if pnl[i] == 0 and worst[i] == 0:
            continue
        if bal + worst[i] <= fl:
            return "bust", i + 1, 0.0
        bal += pnl[i]; best = max(best, pnl[i]); peak = max(peak, bal); fl = min(max(fl, peak - TRAIL), LOCK)
        if bal <= fl:
            return "bust", i + 1, 0.0
        if bal >= TGT and best <= 0.5 * bal:
            j0 = i + 1; fb = fpk = 0.0; ff = -TRAIL; good = 0
            for j in range(j0, min(j0 + H_fund, len(pnl))):
                if pnl[j] == 0 and worst[j] == 0:
                    continue
                if fb + worst[j] <= ff:
                    return "pass", i + 1, 0.0
                fb += pnl[j]; fpk = max(fpk, fb); ff = min(max(ff, fpk - TRAIL), LOCK)
                if fb <= ff:
                    return "pass", i + 1, 0.0
                good += pnl[j] >= 150
                if good >= 5 and fb > 0:
                    return "pass", i + 1, min(0.5 * fb, 2000.0) * 0.9
            return "pass", i + 1, 0.0
    return "timeout", H_eval, 0.0


def summarize(res):
    st = np.array([r[0] for r in res]); ss = np.array([r[1] for r in res]); pay = np.array([r[2] for r in res])
    ps = st == "pass"
    return dict(pass_=round(float(ps.mean()), 3), bust=round(float((st == "bust").mean()), 3),
                med_sess=float(np.median(ss[ps])) if ps.any() else None, payout_rate=round(float((pay > 0).mean()), 3),
                EV=round(float(pay.mean() - FEE), 0))


def boot_paths(n, rng, P=2000, L=300, blk=20):
    """stationary block bootstrap index paths (circular)."""
    out = np.empty((P, L), dtype=int)
    for p in range(P):
        i = 0
        while i < L:
            s = rng.integers(n); k = max(1, rng.geometric(1 / blk))
            idx = (s + np.arange(k)) % n; take = min(k, L - i)
            out[p, i:i + take] = idx[:take]; i += take
    return out


def main():
    rng = np.random.default_rng(7)
    SESS = {r: bt.sessions(r) for r in ("NQ", "ES")}
    PRE = {("NQ", 5): RB.pre_dirs("NQ", 5)}
    dates = sorted(SESS["NQ"])
    ref = RB.book(SESS, {("NQ", 5): PRE["NQ", 5], ("ES", 5): {}}, "NQ925")
    B = {c: books(SESS, PRE, c) for c in (960, 660)}
    assert ref.keys() == B[960].keys() and all(abs(ref[D]["R"] - B[960][D]["sig"]["R"]) < 1e-9 for D in ref)
    print("15:59 book == robust.book NQ925: OK", len(ref), flush=True)
    out = dict(sessions=len(dates), first=dates[0], last=dates[-1])
    out["perm"] = {("1559" if c == 960 else "1100"): perm(B[c], rng) for c in B}
    print(out["perm"], flush=True)

    # quarterly walk-forward: fixed rule, plus anchored gate (trade q only if prior-quarter cumulative R > 0)
    q = defaultdict(list)
    for D, v in B[960].items():
        q[RB.quarter(D)].append(v)
    qs = sorted({RB.quarter(D) for D in dates}); wf = []; cum = 0.0
    for i, k in enumerate(qs):
        R = [v["sig"]["R"] for v in q[k]]; usd = [size(v["sig"], 400) * (v["sig"]["pts"] * MV - CM) for v in q[k]]
        R11 = [v["sig"]["R"] for D, v in B[660].items() if RB.quarter(D) == k]
        wf.append(dict(q=k, n=len(R), R=round(sum(R), 2), R_trade=round(float(np.mean(R)), 3) if R else 0.0,
                       usd_B400=round(sum(usd), 0), R_1100=round(sum(R11), 2), gated=bool(i >= 1 and cum > 0)))
        cum += sum(R)
    out["quarters"] = wf
    out["q_pos"] = f"{sum(w['R'] > 0 for w in wf)}/{len(wf)}"
    out["gated_R"] = round(sum(w["R"] for w in wf if w["gated"]), 2)

    # LucidFlex: history (every circular start), bootstrap, zero-edge null; budgets x exit
    n = len(dates); idx = boot_paths(n, rng); lu = {}
    hist_idx = np.array([(s + np.arange(300)) % n for s in range(n)])
    for c in (960, 660):
        bk = B[c]; muR = float(np.mean([v["sig"]["R"] for v in bk.values()]))
        for Bd in (200, 400, 800):
            for tag, shift, mt in (("hist", 0.0, False), ("boot", 0.0, False), ("null", muR, False), ("boot_MonThu", 0.0, True)):
                pnl, worst = day_seq(bk, dates, Bd, shift, mt)
                P = hist_idx if tag == "hist" else idx
                res = [lucid(pnl[p], worst[p]) for p in P]
                lu[f"{'1559' if c == 960 else '1100'} B{Bd} {tag}"] = s = summarize(res)
            pnl, _ = day_seq(bk, dates, Bd)
            lu[f"{'1559' if c == 960 else '1100'} B{Bd} usd_day"] = round(float(pnl.sum() / n), 1)
            lu[f"{'1559' if c == 960 else '1100'} B{Bd} traded"] = int((pnl != 0).sum())
            print(c, Bd, {k.split()[-1]: lu[k] for k in lu if k.startswith(f"{'1559' if c == 960 else '1100'} B{Bd} ")}, flush=True)
    out["lucid"] = lu
    json.dump(out, open(HERE / "lucid_mnq.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
