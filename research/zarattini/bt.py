# t02 break-and-retest on real ES/NQ 1-min front-month bars, sized as MES/MNQ.
# Honest: signal on 1m close, entry next 1m open +1 tick, hard stop-market (-1 tick, gap -> open),
# target limit needs trade-through by 1 tick, stop checked first when both in one bar, flat 11:00 open -1 tick,
# $1.25 RT commission per micro. Grid = 3 level sets x {LVL,WIDE} x {1,2,3}R + WICK@2R x 3 = 21.
import gzip, json, glob, sys, os, math, random, itertools
from pathlib import Path
from collections import defaultdict
import numpy as np, pandas as pd

HERE = Path(__file__).parent
RESEARCH = HERE.parents[1]
sys.path.insert(0, str(RESEARCH)); sys.path.insert(0, str(RESEARCH.parent))
TICK = 0.25
V = {"ES": 5.0, "NQ": 2.0}          # MES $5/pt, MNQ $2/pt
COMM = 1.24                          # $ round trip per micro (same as t01)
RISK = 200.0                         # $ per trade (10% of $2k DD)
MAXRISK1 = 250.0                     # skip if 1 micro risks more than this
MAXN = 50
FLOOR_PCT = 0.0004                   # min stop distance = 0.04% of price
SPLIT = "2025-09-01"
SLIP = TICK                          # per-side slippage on market entry / stop / time exit
ROOTS = tuple(os.environ.get("ROOTS", "ES,NQ").split(","))

def load(root):
    fr = []
    for fn in glob.glob(str(HERE / "bars" / f"{root}_*.json.gz")):
        d = json.load(gzip.open(fn, "rt"))
        if not d["rows"]: continue
        df = pd.DataFrame(d["rows"], columns=["ts", "o", "h", "l", "c", "v"]); df["tk"] = d["ticker"]; fr.append(df)
    df = pd.concat(fr).drop_duplicates(["tk", "ts"]).sort_values(["tk", "ts"])
    dt = pd.to_datetime(df.ts, unit="ns", utc=True).dt.tz_convert("America/New_York")
    df["dt"] = dt.dt.tz_localize(None); df["date"] = dt.dt.strftime("%Y-%m-%d"); df["tod"] = dt.dt.hour * 60 + dt.dt.minute
    return df.reset_index(drop=True)

def sessions(root):
    df = load(root)
    rth = df[(df.tod >= 570) & (df.tod < 960)]
    vol = rth.groupby(["date", "tk"]).v.sum().reset_index()
    front = vol.sort_values("v").groupby("date").tail(1).set_index("date").tk.to_dict()
    out = {}
    by_tk = {tk: g.reset_index(drop=True) for tk, g in df.groupby("tk")}
    rth_dates = {tk: sorted(g[(g.tod >= 570) & (g.tod < 960)].date.unique()) for tk, g in by_tk.items()}
    for D, tk in sorted(front.items()):
        g = by_tk[tk]
        day = g[(g.date == D) & (g.tod >= 570) & (g.tod < 960)]
        if len(day) < 300 or day.tod.iloc[0] != 570 or day.tod.max() < 661: continue
        ds = rth_dates[tk]; k = ds.index(D)
        pdh = pdl = None
        if k > 0:
            p = g[(g.date == ds[k - 1]) & (g.tod >= 570) & (g.tod < 960)]
            if len(p) >= 300: pdh, pdl = p.h.max(), p.l.min()
        start = pd.Timestamp(ds[k - 1]) + pd.Timedelta(hours=18) if k > 0 else pd.Timestamp(D) - pd.Timedelta(hours=6)
        on = g[(g.dt >= start) & (g.dt < pd.Timestamp(D) + pd.Timedelta(hours=9, minutes=30))]
        onh, onl = (on.h.max(), on.l.min()) if len(on) >= 60 else (None, None)
        prevc = on.c.iloc[-1] if len(on) else day.o.iloc[0]
        day = day.set_index("tod")
        out[D] = dict(tk=tk, tod=day.index.values, o=day.o.values, h=day.h.values, l=day.l.values, c=day.c.values,
                      pdh=pdh, pdl=pdl, onh=onh, onl=onl, prevc=prevc)
    return out

def signals(S, levelset):
    """All B&R signals for a session: list of (i_signal, dir, level, retest_bar_i). His rules, fixed."""
    tod, o, h, l, c = S["tod"], S["o"], S["h"], S["l"], S["c"]
    lv = []
    if levelset in ("ALL", "PRE"):
        for k in ("pdh", "pdl", "onh", "onl"):
            if S[k] is not None: lv.append((k, S[k], 0))
    if levelset in ("ALL", "OR"):
        lv.append(("orh", h[:5].max(), 5)); lv.append(("orl", l[:5].min(), 5))
    last = int(np.searchsorted(tod, 630, side="right"))   # signal bars 09:30..10:30
    out = []
    for name, L, i0 in lv:
        for d in ((1,) if name.endswith("h") else (-1,)):   # engine: long on highs, short on lows
            st, bi, ri = "break", None, None
            for i in range(max(i0, 0), last):
                pc = S["prevc"] if i == 0 else c[i - 1]
                w0 = max(0, i - 9); avg = float(np.mean(h[w0:i + 1] - l[w0:i + 1])) or TICK
                eps = 0.10 * avg
                prng = (h[i - 1] - l[i - 1]) if i > 0 else avg
                rtol = 0.25 * prng
                ci, hi, li, oi = c[i] * d, (h[i] if d == 1 else -l[i]), (l[i] if d == 1 else -h[i]), o[i] * d
                Ld = L * d; pcd = pc * d
                if st == "break":
                    if pcd <= Ld and ci > Ld + eps: st, bi = "leave", i
                elif st == "leave":
                    if li > Ld + eps: st = "retest"
                    elif ci <= Ld + eps: st = "break"
                    if st == "leave" and i - bi > 10: st = "break"
                elif st in ("retest", "hold"):
                    if st == "retest" and i - bi > 10: st = "break"; continue
                    if li <= Ld + rtol: ri, st = i, "hold"
                    if st == "hold":
                        if ci < Ld: st = "break"; continue          # close through = invalid
                        if i - ri > 3: st = "break"; continue       # stale
                        body = abs(c[i] - o[i]); adverse = (h[i] - max(o[i], c[i])) if d == 1 else (min(o[i], c[i]) - l[i])
                        if ci > Ld and ci > oi and adverse <= 1.5 * body:
                            out.append((i, d, L, ri, name)); st = "done"; break
            # one signal per (level, dir) per day
    out.sort()
    return out

def trade(S, sig, stopmode, k, root, net=True):
    i, d, L, ri, name = sig
    tod, o, h, l, c = S["tod"], S["o"], S["h"], S["l"], S["c"]
    j = i + 1
    if j >= len(o) or tod[j] >= 660: return None
    sl = SLIP if net else 0.0
    fill = o[j] + d * sl
    w0 = max(0, i - 9); avg = float(np.mean(h[w0:i + 1] - l[w0:i + 1]))
    if stopmode in ("LVL", "WIDE"):
        buf = max(TICK, math.ceil((0.25 if stopmode == "LVL" else 1.0) * avg / TICK) * TICK)
        stop = L - d * buf
    else:
        stop = (l[ri] - TICK) if d == 1 else (h[ri] + TICK)
    dist = (fill - stop) * d
    if dist <= 0: return None
    floor = math.ceil(FLOOR_PCT * fill / TICK) * TICK
    if dist < floor: dist = floor; stop = fill - d * dist
    n = min(MAXN, int(RISK // (dist * V[root] + COMM)))   # u07 L1 sizing, same as t01
    if n == 0: return None
    tgt = fill + d * k * dist
    ex = None
    for b in range(j, len(o)):
        if tod[b] >= 660: ex = o[b] - d * sl; why = "time"; break
        lo, hi = (l[b], h[b]) if d == 1 else (-h[b], -l[b])
        if lo <= stop * d: ex = d * min(stop * d, o[b] * d) - d * sl; why = "stop"; break
        if hi >= tgt * d + (TICK if net else 0): ex = d * max(tgt * d, o[b] * d); why = "tgt"; break
    if ex is None: return None
    pts = (ex - fill) * d
    comm = COMM if net else 0.0
    usd = n * (pts * V[root] - comm)
    R = usd / (n * dist * V[root])
    return dict(i=i, t=int(tod[i]), d=d, lvl=name, n=n, dist=dist, R=R, usd=usd, why=why)

def stats(daily, dates):
    """daily: {date: usd}; dates: all sessions in window."""
    arr = np.array([daily.get(D, 0.0) for D in dates])
    mon = defaultdict(float)
    for D in dates: mon[D[:7]] += daily.get(D, 0.0)
    h1 = np.array([daily.get(D, 0.0) for D in dates if D < SPLIT]); h2 = np.array([daily.get(D, 0.0) for D in dates if D >= SPLIT])
    rng = np.random.default_rng(7)
    obs = arr.mean()
    flips = rng.choice([-1, 1], size=(2000, len(arr)))
    p = float(((flips * arr).mean(1) >= obs).mean())
    return dict(per_day=obs, green=sum(v > 0 for v in mon.values()), months=len(mon), h1=h1.mean(), h2=h2.mean(), p=p,
                h1_green=sum(v > 0 for m, v in mon.items() if m < SPLIT[:7]), h1_m=sum(1 for m in mon if m < SPLIT[:7]),
                h2_green=sum(v > 0 for m, v in mon.items() if m >= SPLIT[:7]), h2_m=sum(1 for m in mon if m >= SPLIT[:7]), monthly=dict(mon))

def per_inst(bk):
    tr = list(bk.values())
    if not tr: return dict(n=0, R=0.0, win=0.0, med_stop=0.0, h1R=0.0, h2R=0.0)
    return dict(n=len(tr), R=float(np.mean([t["R"] for t in tr])), win=float(np.mean([t["R"] > 0 for t in tr])),
                med_stop=float(np.median([t["dist"] for t in tr])),
                h1R=float(np.mean([t["R"] for D, t in bk.items() if D < SPLIT] or [0])),
                h2R=float(np.mean([t["R"] for D, t in bk.items() if D >= SPLIT] or [0])))

def main():
    SESS = {r: sessions(r) for r in ROOTS}
    dates = sorted(set().union(*[set(SESS[r]) for r in ROOTS]))
    print("sessions", {r: len(SESS[r]) for r in ROOTS}, "union", len(dates), dates[0], dates[-1], flush=True)
    SIG = {(r, ls): {D: signals(S, ls) for D, S in SESS[r].items()} for r in SESS for ls in ("ALL", "PRE", "OR")}
    grid = list(itertools.product(("ALL", "PRE", "OR"), ("LVL", "WIDE"), (1, 2, 3))) + [(ls, "WICK", 2) for ls in ("ALL", "PRE", "OR")]
    res = []; mats = []
    for ls, sm, k in grid:
        books = {}
        for r in ROOTS:
            for net in (True, False):
                bk = {}
                for D, sigs in SIG[(r, ls)].items():
                    for s in sigs:     # first signal that yields a sizable trade
                        t = trade(SESS[r][D], s, sm, k, r, net)
                        if t: t["root"] = r; bk[D] = t; break
                books[(r, net)] = bk
        comb = {}; combg = {}
        for D in dates:
            cands = [books[(r, True)][D] for r in ROOTS if D in books[(r, True)]]
            if cands:
                t = min(cands, key=lambda x: (x["t"], x["root"] != "ES")); comb[D] = t
                combg[D] = books[(t["root"], False)].get(D)
        tr = list(comb.values())
        st = stats({D: t["usd"] for D, t in comb.items()}, dates)
        row = dict(levels=ls, stop=sm, tgt=k, n=len(tr), win=np.mean([t["R"] > 0 for t in tr]) if tr else 0,
                   R_net=np.mean([t["R"] for t in tr]) if tr else 0,
                   R_gross=np.mean([t["R"] for t in combg.values() if t]) if tr else 0,
                   **{f"{k}_{r.lower()}": v for r in ("ES", "NQ") for k, v in per_inst(books.get((r, True), {})).items()},
                   avg_n=np.mean([t["n"] for t in tr]) if tr else 0, **st)
        row["daily"] = [(D, comb[D]["usd"], comb[D]["R"]) for D in dates if D in comb]
        res.append(row); mats.append([comb[D]["usd"] if D in comb else 0.0 for D in dates])
        print(f"{ls:4}{sm:5}{k}R n={row['n']:3} win={row['win']:.2f} Rn={row['R_net']:+.3f} Rg={row['R_gross']:+.3f} "
              f"$/d={row['per_day']:+7.1f} H1={row['h1']:+6.1f} H2={row['h2']:+6.1f} green={row['green']}/{row['months']} p={row['p']:.3f} "
              f"ES {row['n_es']}:{row['R_es']:+.3f} NQ {row['n_nq']}:{row['R_nq']:+.3f} stop {row['med_stop_es']}/{row['med_stop_nq']} h1R {row['h1R_es']:+.3f}/{row['h1R_nq']:+.3f} h2R {row['h2R_es']:+.3f}/{row['h2R_nq']:+.3f}", flush=True)
    # family-wise: joint sign-flip, max mean over combos
    M = np.array(mats); obs = M.mean(1).max()
    rng = np.random.default_rng(11); cnt = 0
    for _ in range(2000):
        f = rng.choice([-1, 1], size=M.shape[1]); cnt += (M * f).mean(1).max() >= obs
    fw = cnt / 2000
    # split-half pick
    di = [D < SPLIT for D in dates]
    h1m = M[:, np.array(di)].mean(1); best1 = int(h1m.argmax())
    # day-shuffle (block) null: shuffle ES/NQ session order vs signals is not meaningful; use luck check on top3
    import propfirm_gate as PG, propfirm_luck_check as LC
    base = {k: dict(v) for k, v in PG.FIRM_RULES.items()}
    fix = dict([("Topstep 50K Combine", dict(consistency_pct=0.50, min_trading_days=2)),
               ("Apex 50K Eval EOD", dict(trailing_dd_pct=0.04, max_days=30)),
               ("MyFundedFutures Rapid 50K", dict(consistency_pct=0.50, min_trading_days=2)),
               ("Alpha Futures 50K Standard", dict(daily_loss_limit_pct=1.0, min_trading_days=2)),
               ("Take Profit Trader 50K Test", dict(trailing_dd_pct=0.04, min_trading_days=3))])
    for k, upd in fix.items():
        base[k + " (u06 fix)"] = dict(PG.FIRM_RULES[k], **upd)
    base["LucidFlex 50K"] = dict(account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.04, dd_mode="eod",
                                 dd_lock_at_breakeven=False, daily_loss_limit_pct=1.0, min_trading_days=0, consistency_pct=0.50, max_days=None)
    base["Tradeify Select 50K"] = dict(account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.04, dd_mode="eod",
                                       dd_lock_at_breakeven=False, daily_loss_limit_pct=1.0, min_trading_days=3, consistency_pct=0.40, max_days=None)
    top = sorted(range(len(res)), key=lambda x: -res[x]["per_day"])[:3]
    gates = {}
    for ti in top:
        r = res[ti]; daily = [(D, u) for D, u, _ in r["daily"]]
        g = PG.gate_series(daily, base)
        luck = LC.compute(daily, base, n_shuffles=300, seed=1337)
        name = f"{r['levels']}/{r['stop']}/{r['tgt']}R"
        gates[name] = {f: dict(passed=g[f]["passed"], fail=g[f].get("fail_reason"), all_starts=g[f]["all_starts_pass_pct"],
                               eval_ready=luck[f].get("eval_ready"),
                               luck={kk: vv for kk, vv in luck[f].items() if kk != "eval_ready"}) for f in base}
        print("GATE", name, flush=True)
        for f, v in gates[name].items():
            L = v["luck"]
            print(f"  {f:32} {'PASS' if v['passed'] else 'FAIL'} {str(v['fail']):18} allstarts={v['all_starts']} eval_ready={v['eval_ready']} "
                  + json.dumps(L, default=str)[:500], flush=True)
    out = dict(sessions=len(dates), first=dates[0], last=dates[-1], n_sess={r: len(SESS[r]) for r in ROOTS},
               familywise_p=fw, best_h1=f"{res[best1]['levels']}/{res[best1]['stop']}/{res[best1]['tgt']}R",
               best_h1_h1=float(h1m[best1]), best_h1_h2=res[best1]["h2"],
               grid=[{k: v for k, v in r.items() if k != "daily"} for r in res], gates=gates,
               top3_daily={f"{res[t]['levels']}/{res[t]['stop']}/{res[t]['tgt']}R": res[t]["daily"] for t in top})
    json.dump(out, open(HERE / "results.json", "w"), default=float, indent=1)
    print("familywise_p", fw, "best_on_H1", out["best_h1"], "H1", round(out["best_h1_h1"], 1), "H2", round(out["best_h1_h2"], 1))

if __name__ == "__main__":
    main()
