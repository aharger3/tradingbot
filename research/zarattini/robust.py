# Robustness of the Zarattini NQ 09:25-filter port (zarattini.py), no new data.
# 1 quarterly walk-forward  2 +-20% parameter neighborhood  3 MNQ integer sizing (bt L1 rule)
# 4 cost stress (slip x commission)  5 prop-firm gate from every start day  6 luck checks.
# zarattini.py and bt.py are imported unchanged; defaults are asserted to reproduce Z.book exactly.
import sys, json, math, itertools
from pathlib import Path
from collections import defaultdict
import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import zarattini as Z
bt = Z.bt

DEF = dict(m=5, p=5, T=10, k=1.0)                  # OR minutes, pre-window minutes, target R, stop-distance mult
NBR = dict(m=(4, 5, 6), p=(4, 5, 6), T=(8, 10, 12), k=(0.8, 1.0, 1.2))
PROP = dict(target=3000.0, trail=2000.0, dll=1000.0)   # 50K-combine style [unverified vs current firm rules]


def pre_dirs(root, p):
    """{(tk, date): sign of the p-minute pre-open bar ending 09:30}; needs >= p-2 one-minute bars."""
    df = bt.load(root)
    w = df[(df.tod >= 570 - p) & (df.tod < 570)]
    return {(tk, D): int(np.sign(g.c.iloc[-1] - g.o.iloc[0])) for (tk, D), g in w.groupby(["tk", "date"]) if len(g) >= max(2, p - 2)}


def trade(S, m, T, k, slip, comm=bt.COMM, net=True):
    """Zarattini trade with an m-minute OR, entry at bar m, stop k x OR-extreme distance, T-R target.
    Returns dict(R, d, dist, pts, why) per MNQ contract, or None."""
    tod = list(S["tod"][:m + 1])
    if tod != list(range(570, 571 + m)):
        return None
    o, h, l, c = S["o"], S["h"], S["l"], S["c"]
    d = int(np.sign(c[m - 1] - o[0]))
    if d == 0:
        return None
    se = slip * bt.TICK; ss = 2 * se
    fill = o[m] + d * se
    ext = l[:m].min() if d == 1 else h[:m].max()
    dist = (fill - ext) * d * k
    if dist <= 0:
        return None
    stop = fill - d * dist; tgt = fill + d * T * dist
    ex = None
    for b in range(m, len(o)):
        lo, hi = (l[b], h[b]) if d == 1 else (-h[b], -l[b])
        if lo <= stop * d:
            ex = d * min(stop * d, o[b] * d) - d * ss; why = "stop"; break
        if hi >= tgt * d + bt.TICK:
            ex = d * max(tgt * d, o[b] * d); why = "tgt"; break
    if ex is None:
        ex = c[-1] - d * se; why = "close"
    pts = (ex - fill) * d
    cm = comm if net else 0.0
    return dict(R=(pts * bt.V["NQ"] - cm) / (dist * bt.V["NQ"]), d=d, dist=dist, pts=pts, why=why)


def book(SESS, PRE, flt, m=5, p=5, T=10, k=1.0, slip=1, comm=bt.COMM):
    out = {}
    for D, S in SESS["NQ"].items():
        t = trade(S, m, T, k, slip, comm)
        if t is None:
            continue
        if flt == "NQ925" and PRE["NQ", p].get((S["tk"], D)) != t["d"]:
            continue
        if flt == "ES925":
            E = SESS["ES"].get(D)
            if E is None or PRE["ES", p].get((E["tk"], D)) != t["d"]:
                continue
        out[D] = t
    return out


def mnq_usd(t, comm=bt.COMM):
    """bt L1 sizing: n = min(50, RISK // (1-contract risk + comm)); 0 -> skip. Returns (usd, n)."""
    n = min(bt.MAXN, int(bt.RISK // (t["dist"] * bt.V["NQ"] + comm)))
    return (n * (t["pts"] * bt.V["NQ"] - comm), n) if n else (0.0, 0)


def prop_gate(usd_days, target, trail, dll):
    """usd_days: list of daily $ (0 = no trade). EOD trailing DD, daily loss limit.
    Returns ('pass'|'bust'|'open', trading days used)."""
    eq = peak = 0.0; n = 0
    for x in usd_days:
        if x == 0:
            continue
        n += 1
        if x <= -dll:
            return "bust", n
        eq += x; peak = max(peak, eq)
        if eq <= peak - trail:
            return "bust", n
        if eq >= target:
            return "pass", n
    return "open", n


def rstats(bk, dates):
    R = np.array([t["R"] for t in bk.values()]); n = len(R)
    return dict(n=n, R_trade=float(R.mean()) if n else 0.0, R_day=float(R.sum() / len(dates)),
                t=float(R.mean() / (R.std(ddof=1) / math.sqrt(n))) if n > 1 else 0.0)


def quarter(D):
    return f"{D[:4]}Q{(int(D[5:7]) - 1) // 3 + 1}"


def main():
    rng = np.random.default_rng(11)
    SESS = {r: bt.sessions(r) for r in ("NQ", "ES")}
    PRE = {(r, p): pre_dirs(r, p) for r in ("NQ", "ES") for p in NBR["p"]}
    dates = sorted(SESS["NQ"])
    out = dict(sessions=len(dates), first=dates[0], last=dates[-1])
    # 0. defaults reproduce zarattini.book exactly
    ZPRE = {r: Z.pre_bars(r) for r in ("NQ", "ES")}
    for f in Z.FILTERS:
        a, b = book(SESS, PRE, f), Z.book(SESS, ZPRE, f, 1)
        assert a.keys() == b.keys() and all(abs(a[D]["R"] - b[D]["R"]) < 1e-9 for D in a), f
    print("defaults == zarattini.book: OK", flush=True)
    base = {f: book(SESS, PRE, f) for f in Z.FILTERS}
    out["base"] = {f: rstats(base[f], dates) for f in Z.FILTERS}

    # 1. quarterly table + anchored walk-forward (pick best filter x params on all prior quarters, trade next)
    qs = sorted({quarter(D) for D in dates}); qd = defaultdict(list)
    for D in dates: qd[quarter(D)].append(D)
    out["quarters"] = {q: {f: round(sum(t["R"] for D, t in base[f].items() if quarter(D) == q), 2) for f in Z.FILTERS} for q in qs}
    combos = [dict(zip(NBR, v)) for v in itertools.product(*NBR.values())]
    BK = {(f, tuple(c.values())): book(SESS, PRE, f, **c) for f in Z.FILTERS for c in combos}
    print("books", len(BK), flush=True)
    qR = {key: defaultdict(float, {}) for key in BK}
    for key, bk in BK.items():
        for D, t in bk.items(): qR[key][quarter(D)] += t["R"]
    wf = []
    for i, q in enumerate(qs):
        if i < 2: continue
        prior = qs[:i]
        pick = max(BK, key=lambda kk: sum(qR[kk][x] for x in prior))
        wf.append(dict(q=q, pick=f"{pick[0]} m{pick[1][0]} p{pick[1][1]} T{pick[1][2]} k{pick[1][3]}", oos_R=round(qR[pick][q], 2),
                       fixed_NQ925=round(qR[("NQ925", tuple(DEF.values()))][q], 2), days=len(qd[q])))
    out["walk_forward"] = wf
    out["wf_total"] = dict(picked=round(sum(w["oos_R"] for w in wf), 2), fixed=round(sum(w["fixed_NQ925"] for w in wf), 2),
                           days=sum(w["days"] for w in wf))

    # 2. neighborhood (NQ925, 81 combos): distribution + one-at-a-time
    nb = {c: rstats(BK[("NQ925", c)], dates) for (f, c) in BK if f == "NQ925"}
    rt = np.array([v["R_trade"] for v in nb.values()]); rd = np.array([v["R_day"] for v in nb.values()])
    out["neighborhood"] = dict(n=len(nb), pos_R_trade=int((rt > 0).sum()), pct_R_trade=np.percentile(rt, [0, 10, 50, 90, 100]).round(3).tolist(),
                               pct_R_day=np.percentile(rd, [0, 10, 50, 90, 100]).round(4).tolist(),
                               t_ge_2=int(sum(v["t"] >= 2 for v in nb.values())),
                               nq925_minus_none=float(np.median([nb[c]["R_day"] - rstats(BK[("NONE", c)], dates)["R_day"] for c in nb])))
    oat = {}
    for p, vals in NBR.items():
        for v in vals:
            c = dict(DEF); c[p] = v
            oat[f"{p}={v}"] = {k2: round(x, 4) for k2, x in nb[tuple(c.values())].items()}
    out["one_at_a_time"] = oat

    # 3+4. MNQ integer sizing and cost stress, $ per session day
    cs = {}
    for f in ("NONE", "NQ925"):
        for slip, cm in itertools.product((1, 2, 4), (1.0, 2.0, 3.0)):
            bk = book(SESS, PRE, f, slip=slip, comm=bt.COMM * cm)
            usd = [mnq_usd(t, bt.COMM * cm) for t in bk.values()]
            took = [u for u, n in usd if n]
            cs[f"{f} s{slip} c{cm:g}x"] = dict(trades=len(took), skipped_wide=len(usd) - len(took),
                                              usd_day=round(sum(took) / len(dates), 1), usd_trade=round(float(np.mean(took)), 1),
                                              med_contracts=float(np.median([n for _, n in usd if n])))
    out["mnq_cost"] = cs

    # 5. prop gate from every start day (MNQ, slip 1, 1x comm)
    pg = {}
    for f in ("NONE", "NQ925"):
        daily = {D: mnq_usd(t)[0] for D, t in base[f].items()}
        seq = [daily.get(D, 0.0) for D in dates]
        res = [prop_gate(seq[i:], **PROP) for i in range(len(seq))]
        done = [r for r in res if r[0] != "open"]
        pg[f] = dict(starts=len(res), resolved=len(done), pass_rate=round(sum(r[0] == "pass" for r in done) / max(1, len(done)), 3),
                     med_days_to_pass=float(np.median([n for s, n in done if s == "pass"])) if any(s == "pass" for s, _ in done) else None,
                     worst_eod_dd=round(float(min(np.cumsum(seq) - np.maximum.accumulate(np.cumsum(seq)))), 0))
    out["prop"] = pg

    # 6. luck: (a) random same-size subsets of the unfiltered book (b) bootstrap CI (c) drop best 5 trades
    rn = np.array([t["R"] for t in base["NONE"].values()]); rq = np.array([t["R"] for t in base["NQ925"].values()])
    draws = np.array([rng.choice(rn, len(rq), replace=False).mean() for _ in range(20000)])
    boot = np.array([rng.choice(rq, len(rq)).mean() for _ in range(20000)])
    out["luck"] = dict(subset_p=float((draws >= rq.mean()).mean()), boot_ci90=np.percentile(boot, [5, 95]).round(3).tolist(),
                       boot_p_le0=float((boot <= 0).mean()), drop_top5_R_trade=round(float(np.sort(rq)[:-5].mean()), 3),
                       top5_share=round(float(np.sort(rq)[-5:].sum() / rq.sum()), 2))
    json.dump(out, open(HERE / "robust.json", "w"), indent=1, default=float)
    print(json.dumps({k: out[k] for k in ("base", "wf_total", "neighborhood", "prop", "luck")}, default=float), flush=True)


if __name__ == "__main__":
    main()
