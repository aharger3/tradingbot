"""burn-two-strong: does Austin's "a couple of strong candles" displacement rule hold on MNQ futures?

PRE-REGISTERED (before looking at futures): trades whose break leg has >=2 strong displacement candles
earn HIGHER R2 than trades with exactly 1 (and than <2). One-sided tests in that direction only.

n_disp_candles (a1 definition): bars of the break leg -- break bar (first close past the level) through the
bar of max excursion before the signal bar -- with a with-trend body >= 60% of range and range >= 1 ATR,
ATR = mean 1-min range of the <=14 bars before the break bar.

Samples: (A) the 105 frozen MNQ trades (v3-t-mnq v2 baseline, OR5 D1.0 strong, 10:30, 2R; frozen orb1m.py);
(B) the 40 eye2 replay candidates (v3-eye2-candidates candidates_out.json), R2 via the same mnq.trade(),
flat 11:00. Tag only -- no engine change. Paper research only.
"""
import sys, json
import numpy as np

AR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs"
sys.path.insert(0, AR + r"\v3-t-mnq")
CAND = r"C:\Users\aharg\Desktop\Projects\tradingbot-eye2-candidates\research\agent_runs\v3-eye2-candidates\candidates_out.json"
TICK = 0.25
ORN = 5


def n_disp_candles(A, side, bi, j):
    """Count strong with-trend candles on the break leg bi..extreme (extreme = max excursion in bi..j-1)."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    pre = (H - L)[max(0, bi - 14):bi]
    atr = np.nanmean(pre) if np.sum(~np.isnan(pre)) >= 1 else np.nan
    if np.isnan(atr) or atr <= 0:
        return None
    seg = range(bi, max(bi + 1, j))
    exc = [(H[b] if side > 0 else -L[b]) for b in seg]
    ext = bi + int(np.nanargmax(exc))
    n = 0
    for b in range(bi, ext + 1):
        rng = H[b] - L[b]
        if np.isnan(rng) or rng <= 0:
            continue
        if (C[b] - O[b]) * side >= 0.6 * rng and rng >= atr:
            n += 1
    return n


def break_bar(A, j, side, lvl):
    """Last bar <= j where the close crossed past lvl in trade direction after being not past it (or first after OR)."""
    C = A["close"]
    bi = None
    for b in range(ORN, j):
        past = (C[b] - lvl) * side > 0
        if past and (bi is None):
            bi = b
        elif not past and not np.isnan(C[b]):
            bi = None
    return bi


def shuffle_means(mnq, days, T, cut, rng, nshuf=200):
    """mnq-style day-shuffle: same minute, side, stop pts on a random other day. Returns (nshuf, len(T)) R."""
    out = np.zeros((nshuf, len(T)))
    for s in range(nshuf):
        for q, t in enumerate(T):
            while True:
                k = int(rng.integers(len(days)))
                if k != t["k"] and not np.isnan(days[k]["open"][t["i"]]):
                    break
            out[s, q] = mnq.trade(days[k], t["i"], t["side"], t["dist"], cut, t["j"], "2R")[0]
    return out


def stats(T, SH, mid, perm_rng, nperm=5000):
    R = np.array([t["R"] for t in T]); nd = np.array([t["nd"] for t in T]); h1 = np.array([t["date"] < mid for t in T])
    grp = {"0": nd == 0, "1": nd == 1, ">=2": nd >= 2, "<2": nd < 2}
    rows = {}
    for g, m in grp.items():
        if not m.any():
            rows[g] = dict(n=0); continue
        sm = SH[:, m].mean(1)
        rows[g] = dict(n=int(m.sum()), R=float(R[m].mean()), win=float((R[m] > 0).mean()),
                       H1=float(R[m & h1].mean()) if (m & h1).any() else None, nH1=int((m & h1).sum()),
                       H2=float(R[m & ~h1].mean()) if (m & ~h1).any() else None, nH2=int((m & ~h1).sum()),
                       p_shuffle=float((sm >= R[m].mean()).mean()))
    tests = {}
    for a, b in ((">=2", "1"), (">=2", "<2")):
        ma, mb = grp[a], grp[b]
        if not ma.any() or not mb.any():
            continue
        d = R[ma].mean() - R[mb].mean()
        both = ma | mb; Rb = R[both]; la = ma[both]; c = 0
        for _ in range(nperm):
            p = perm_rng.permutation(la); c += (Rb[p].mean() - Rb[~p].mean()) >= d
        sd = SH[:, ma].mean(1) - SH[:, mb].mean(1)
        tests[f"{a} vs {b}"] = dict(diff=float(d), p_label_perm=float((c + 1) / (nperm + 1)),
                                    p_shuffle=float((sd >= d).mean()),
                                    H1_diff=_d(R, ma, mb, h1), H2_diff=_d(R, ma, mb, ~h1))
    return rows, tests


def _d(R, ma, mb, h):
    if (ma & h).any() and (mb & h).any():
        return float(R[ma & h].mean() - R[mb & h].mean())
    return None


def main():
    import mnq
    rng = np.random.default_rng(11); prng = np.random.default_rng(12)
    days = mnq.load_real(); dates = [A["date"] for A in days]; byd = {A["date"]: (k, A) for k, A in enumerate(days)}
    mid = dates[len(dates) // 2]
    # (A) frozen 105
    T, _ = mnq.run_cell(days, "v2 baseline (OR5 D1.0 strong)", "10:30", "2R", nshuf=0)
    for t in T:
        A = days[t["k"]]; orh, orl = np.nanmax(A["high"][:ORN]), np.nanmin(A["low"][:ORN])
        lvl = orh if t["side"] > 0 else orl
        t["bi"] = break_bar(A, t["j"], t["side"], lvl); t["nd"] = n_disp_candles(A, t["side"], t["bi"], t["j"])
    print("A n", len(T), "R", round(float(np.mean([t["R"] for t in T])), 4), flush=True)
    SH = shuffle_means(mnq, days, T, 60, rng)
    ra, ta = stats(T, SH, mid, prng)
    # (B) eye2 candidates
    C = json.load(open(CAND)); TB = []; miss = 0; dev = []
    for c in C:
        D = c["time"][:10]
        if D not in byd:
            miss += 1; continue
        k, A = byd[D]; side = 1 if c["direction"] == "long" else -1; j = c["features"]["minutes_after_open"]; i = j + 1
        if np.isnan(A["open"][i]):
            miss += 1; continue
        e = A["open"][i] + TICK * side; dist = (e - c["stop"]) * side; dev.append(abs(e - c["entry"]))
        if dist < 2 * TICK:
            miss += 1; continue
        r, u = mnq.trade(A, i, side, dist, 90, j, "2R")
        bi = ORN + c["features"]["bars_to_break"]
        TB.append(dict(date=D, k=k, i=i, j=j, side=side, dist=dist, R=r, bi=bi, nd=n_disp_candles(A, side, bi, j),
                       grade=c["grade_hint"]))
    print("B n", len(TB), "skipped", miss, "max entry dev pts", max(dev) if dev else None, flush=True)
    cd = sorted({t["date"] for t in TB}); midB = cd[len(cd) // 2]
    SHB = shuffle_means(mnq, days, TB, 90, rng)
    rb, tb = stats(TB, SHB, midB, prng)
    out = dict(A_frozen105=dict(groups=ra, tests=ta, split_mid=mid,
                                nd_hist={str(v): int(sum(t["nd"] == v for t in T)) for v in sorted({t["nd"] for t in T})}),
               B_eye2=dict(groups=rb, tests=tb, split_mid=midB, skipped=miss, max_entry_dev=max(dev) if dev else None,
                           nd_hist={str(v): int(sum(t["nd"] == v for t in TB)) for v in sorted({t["nd"] for t in TB})}),
               tags=dict(A=[dict(date=t["date"], side=t["side"], nd=t["nd"], R=round(t["R"], 4)) for t in T],
                         B=[dict(date=t["date"], j=t["j"], side=t["side"], nd=t["nd"], R=round(t["R"], 4), grade=t["grade"]) for t in TB]))
    json.dump(out, open("res.json", "w"), indent=1)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "tags"} for k, v in out.items() if k != "tags"}, indent=1))


if __name__ == "__main__":
    main()
