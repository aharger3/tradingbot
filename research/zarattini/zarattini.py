# Zarattini & Aziz (2023) 5-min ORB, ported onto t02 bt.py's loaders/costs (bt.py byte-identical, not edited).
# Method follows giovannibrusco/zarattini-2023-orb-qqq, traded as MNQ on real NQ 1-min front-month bars:
#   09:30-09:35 bar bullish -> long at 09:35 open, bearish -> short, doji -> no trade.
#   stop = opening-bar low (long) / high (short); target +10R; else flat at the 15:59 bar close.
#   NQ filter: the 09:25-09:30 NQ bar must agree with the opening bar. ES925 = same test on ES (cross-market).
#   Slippage stress: entry s ticks/side, stop 2s ticks (repo convention: stop slip = 2x entry), close exit s ticks.
# R is per contract, net of bt.COMM; $/day is R x $200 (bt.RISK). Bars = BARS_ROOT env, else t02-break-retest (read-only).
import os, sys, json, math
from pathlib import Path
from collections import defaultdict
import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import bt

_T02 = Path("research") / "agent_runs" / "t02-break-retest"   # untracked data; a worktree reads the production copy
bt.HERE = Path(os.environ.get("BARS_ROOT") or next(
    (p for p in (HERE.parents[1] / _T02, HERE.parents[2] / "tradingbot" / _T02) if (p / "bars").is_dir()), HERE))
TGT_R = 10
SLIPS = (0, 1, 2, 4, 8, 12, 16, 24, 32)        # entry ticks per side
FILTERS = ("NONE", "NQ925", "ES925")


def or_bar(S):
    """Opening 5-min bar from 1-min bars 09:30..09:34 -> (o, h, l, c) or None if incomplete."""
    tod = list(S["tod"])
    if tod[:5] != [570, 571, 572, 573, 574] or len(tod) < 6 or tod[5] != 575:
        return None
    return S["o"][0], S["h"][:5].max(), S["l"][:5].min(), S["c"][4]


def pre_bars(root):
    """{(tk, date): direction of the 09:25-09:30 bar} from bt.load (Globex pre-open minutes 565..569)."""
    df = bt.load(root)
    p = df[(df.tod >= 565) & (df.tod < 570)]
    out = {}
    for (tk, D), g in p.groupby(["tk", "date"]):
        if len(g) >= 3:
            out[(tk, D)] = int(np.sign(g.c.iloc[-1] - g.o.iloc[0]))
    return out


def trade(S, d, entry_slip_ticks, net=True, root="NQ"):
    """One Zarattini trade from bar index 5 (09:35). Returns dict(R, why) or None."""
    ob = or_bar(S)
    if ob is None:
        return None
    _, h5, l5, _ = ob
    o, h, l, c = S["o"], S["h"], S["l"], S["c"]
    se = entry_slip_ticks * bt.TICK
    ss = 2 * se
    fill = o[5] + d * se
    stop = l5 if d == 1 else h5
    dist = (fill - stop) * d
    if dist <= 0:
        return None
    tgt = fill + d * TGT_R * dist
    ex = why = None
    for b in range(5, len(o)):
        lo, hi = (l[b], h[b]) if d == 1 else (-h[b], -l[b])
        if lo <= stop * d:
            ex = d * min(stop * d, o[b] * d) - d * ss; why = "stop"; break
        if hi >= tgt * d + bt.TICK:
            ex = d * max(tgt * d, o[b] * d); why = "tgt"; break
    if ex is None:
        ex = c[-1] - d * se; why = "close"
    pts = (ex - fill) * d
    comm = bt.COMM if net else 0.0
    return dict(R=(pts * bt.V[root] - comm) / (dist * bt.V[root]), why=why, dist=dist)


def book(SESS, PRE, flt, slip, net=True):
    """{date: trade} for NQ under a filter."""
    out = {}
    for D, S in SESS["NQ"].items():
        ob = or_bar(S)
        if ob is None:
            continue
        d = int(np.sign(ob[3] - ob[0]))
        if d == 0:
            continue
        if flt == "NQ925" and PRE["NQ"].get((S["tk"], D)) != d:
            continue
        if flt == "ES925":
            E = SESS["ES"].get(D)
            if E is None or PRE["ES"].get((E["tk"], D)) != d:
                continue
        t = trade(S, d, slip, net)
        if t:
            t["d"] = d; out[D] = t
    return out


def summarize(bk, dates):
    R = np.array([t["R"] for t in bk.values()])
    daily = {D: t["R"] for D, t in bk.items()}
    st = bt.stats(daily, dates)
    yr = defaultdict(float)
    for D, t in bk.items():
        yr[D[:4]] += t["R"]
    tot = sum(yr.values())
    why = defaultdict(int)
    for t in bk.values():
        why[t["why"]] += 1
    n = len(R)
    return dict(n=n, R_trade=float(R.mean()) if n else 0.0, R_day=float(st["per_day"]),
                usd_day=float(st["per_day"]) * bt.RISK, med_stop_pts=float(np.median([t["dist"] for t in bk.values()])) if n else 0.0, win=float((R > 0).mean()) if n else 0.0,
                t=float(R.mean() / (R.std(ddof=1) / math.sqrt(n))) if n > 1 else 0.0,
                h1_R_day=float(st["h1"]), h2_R_day=float(st["h2"]), p=st["p"],
                green=f"{st['green']}/{st['months']}", years={k: round(float(v), 2) for k, v in sorted(yr.items())},
                best_year_share=float(max(yr.values()) / tot) if tot > 0 else None,
                exits={k: round(v / n, 3) for k, v in why.items()} if n else {})


def breakeven(xs, ys):
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if y0 > 0 >= y1:
            return round(x0 + (x1 - x0) * y0 / (y0 - y1), 2)
    return None if ys[0] <= 0 else f">{xs[-1]}"


def main():
    SESS = {r: bt.sessions(r) for r in ("NQ", "ES")}
    PRE = {r: pre_bars(r) for r in ("NQ", "ES")}
    dates = sorted(SESS["NQ"])
    print("NQ sessions", len(dates), dates[0], dates[-1], flush=True)
    out = dict(sessions=len(dates), first=dates[0], last=dates[-1], split=bt.SPLIT, rows={}, sweep={}, breakeven_ticks={})
    for f in FILTERS:
        g = summarize(book(SESS, PRE, f, 0, net=False), dates)
        out["rows"][f"{f}/gross"] = g
        ys = []
        for s in SLIPS:
            r = summarize(book(SESS, PRE, f, s), dates)
            out["rows"][f"{f}/slip{s}"] = r; ys.append(r["R_day"])
            print(f"{f:6} slip={s} n={r['n']:3} R/tr={r['R_trade']:+.3f} R/day={r['R_day']:+.4f} $/d={r['usd_day']:+6.1f} "
                  f"stop={r['med_stop_pts']:.1f}pt t={r['t']:+.2f} p={r['p']:.3f} H1={r['h1_R_day']:+.3f} H2={r['h2_R_day']:+.3f} green={r['green']} "
                  f"yrs={r['years']} exits={r['exits']}", flush=True)
        out["sweep"][f] = dict(zip(SLIPS, ys))
        out["breakeven_ticks"][f] = breakeven(list(SLIPS), ys)
        print(f"{f:6} gross R/day={g['R_day']:+.4f} breakeven entry ticks={out['breakeven_ticks'][f]}", flush=True)
    json.dump(out, open(HERE / "results.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
