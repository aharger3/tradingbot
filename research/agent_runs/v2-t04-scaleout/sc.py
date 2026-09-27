# v2-t04: fixed 1:2 (and 3R) vs 4-tier 30/30/30/10 scale-out w/ BE, SAME entries as t02 (bt.py signals/sessions).
# Honest: entry next 1m open +1 tick; hard stop touch -> min(stop,open)-1 tick; limit targets need 1-tick trade-through;
# stop wins same bar (no rung that bar); BE armed on first rung fill, close-triggered (close-1 tick, floor -1R);
# flat at cutoff open -1 tick; $1.24 RT/micro/contract; $200 risk, n=floor(200/(dist*V+comm)).
import sys, json, math
from pathlib import Path
import numpy as np
T02 = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t02-break-retest")
sys.path.insert(0, str(T02))
import bt
from bt import TICK, V, COMM, RISK, MAXN, FLOOR_PCT, SPLIT, SLIP
HERE = Path(__file__).parent
W4 = [0.30, 0.30, 0.30, 0.10]

def setup(S, sig, stopmode, root, cutoff):
    i, d, L, ri, name = sig
    tod, o, h, l = S["tod"], S["o"], S["h"], S["l"]
    j = i + 1
    if j >= len(o) or tod[j] >= cutoff: return None
    fill = o[j] + d * SLIP
    w0 = max(0, i - 9); avg = float(np.mean(h[w0:i + 1] - l[w0:i + 1]))
    buf = max(TICK, math.ceil((0.25 if stopmode == "LVL" else 1.0) * avg / TICK) * TICK)
    stop = L - d * buf
    dist = (fill - stop) * d
    if dist <= 0: return None
    fl = math.ceil(FLOOR_PCT * fill / TICK) * TICK
    if dist < fl: dist = fl; stop = fill - d * dist
    n = min(MAXN, int(RISK // (dist * V[root] + COMM)))
    if n == 0: return None
    return dict(i=i, j=j, d=d, fill=fill, stop=stop, dist=dist, n=n)

def rungs(S, e, mode, pt1def):
    d, fill, dist, i = e["d"], e["fill"], e["dist"], e["i"]
    R = lambda px: (px - fill) * d / dist
    if mode[0] == "flat": return [(mode[1], 1.0, "T")]
    named = sorted(R(v) for v in [S[k] for k in ("pdh", "pdl", "onh", "onl")] + [S["h"][:5].max(), S["l"][:5].min()] if v is not None)
    ext = S["h"][:i + 1].max() if d == 1 else S["l"][:i + 1].min()
    pt1 = 1.0 if pt1def == "1R" else R(ext)
    c = []
    if pt1 >= 0.20: c.append([pt1, W4[0], "PT1"])
    beyond = [x for x in named if x > max(pt1, 0.20)]
    if beyond: c.append([beyond[0], W4[1], "PT2"])
    p3 = 2.0; near = [x for x in named if abs(x - 2.0) <= 0.25]
    if near: p3 = min(near, key=lambda x: abs(x - 2.0))
    c.append([p3, W4[2], "PT3"])
    nxt = [x for x in named if x > p3 + 0.20]
    c.append([max(4.0, nxt[0]) if nxt else 4.0, W4[3], "PT4"])
    c.sort(key=lambda x: x[0]); out = []
    for x in c:   # coalesce within 0.20R, keep nearer (weight lost -> renormalize)
        if out and x[0] - out[-1][0] < 0.20: continue
        out.append(x)
    s = sum(x[1] for x in out)
    return [(x[0], x[1] / s, x[2]) for x in out]

def alloc(rs, n):
    if n >= len(rs):
        raw = [w * n for _, w, _ in rs]; q = [int(x) for x in raw]
        for k in sorted(range(len(rs)), key=lambda k: (-(raw[k] - q[k]), rs[k][0]))[: n - sum(q)]: q[k] += 1
        # ensure each rung >=1 if possible
        for k in range(len(q)):
            if q[k] == 0:
                big = max(range(len(q)), key=lambda z: q[z]); q[big] -= 1; q[k] += 1
        return [(r, q[k], nm) for k, (r, w, nm) in enumerate(rs) if q[k] > 0], False
    pri = ["PT3", "PT1", "PT4", "PT2"]
    names = {nm: (r, nm) for r, w, nm in rs}
    keep = [names[p] for p in pri if p in names][:n]
    if not any(nm == "PT3" for _, nm in keep) and keep: pass
    return sorted([(r, 1, nm) for r, nm in keep]), True

def run(S, e, mode, root, cutoff, pt1def="HOD"):
    tod, o, h, l, c = S["tod"], S["o"], S["h"], S["l"], S["c"]
    d, fill, dist, n = e["d"], e["fill"], e["dist"], e["n"]
    rs = rungs(S, e, mode, pt1def)
    legs, coll = alloc(rs, n) if mode[0] != "flat" else ([(mode[1], n, "T")], False)
    open_ = [[fill + d * r * dist, q, nm] for r, q, nm in legs]
    pnl = 0.0; be = False; filled = []; hard = e["stop"]; peak_open = 0.0; why = None
    for b in range(e["j"], len(o)):
        rem = sum(q for _, q, _ in open_)
        if rem == 0: break
        if tod[b] >= cutoff:
            pnl += rem * (o[b] - d * SLIP - fill) * d; open_ = []; why = why or "time"; break
        lo, hi = (l[b], h[b]) if d == 1 else (-h[b], -l[b])
        # open-equity peak (intraday trail proxy), before exits this bar
        peak_open = max(peak_open, pnl * V[root] + rem * (hi - fill * d) * V[root])
        if lo <= hard * d:
            px = d * min(hard * d, o[b] * d) - d * SLIP
            pnl += rem * (px - fill) * d; open_ = []; why = why or "stop"; break
        for leg in open_:
            if hi >= leg[0] * d + TICK:
                px = d * max(leg[0] * d, o[b] * d); pnl += leg[1] * (px - fill) * d; filled.append(leg[2]); leg[1] = 0; be = True
        open_ = [x for x in open_ if x[1] > 0]
        rem = sum(q for _, q, _ in open_)
        if rem and be and c[b] * d <= fill * d:
            px = max(c[b] * d - SLIP, fill * d - dist) * d  # floored at -1R
            pnl += rem * (px - fill) * d; open_ = []; why = "be"; break
    if open_:  # ran out of bars
        pnl += sum(q for _, q, _ in open_) * (c[-1] - fill) * d
    usd = pnl * V[root] - n * COMM
    return dict(usd=usd, R=usd / (n * dist * V[root]), filled=filled, coll=coll, nlegs=len(legs), peak=peak_open, why=why)

def maxdd(x):
    eq = np.cumsum(x); return float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())

def main():
    ROOTS = ("ES", "NQ")
    SESS = {r: bt.sessions(r) for r in ROOTS}
    dates = sorted(set().union(*[set(SESS[r]) for r in ROOTS]))
    print("sessions", len(dates), dates[0], dates[-1], flush=True)
    import propfirm_gate as PG, propfirm_luck_check as LC
    FIRMS = {}
    FIRMS["Topstep 50K"] = dict(PG.FIRM_RULES["Topstep 50K Combine"], consistency_pct=0.50, min_trading_days=2)
    FIRMS["LucidFlex 50K"] = dict(account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.04, dd_mode="eod",
                                 dd_lock_at_breakeven=False, daily_loss_limit_pct=1.0, min_trading_days=0, consistency_pct=0.50, max_days=None)
    VARS = [("A ES+NQ PRE/LVL", ("ES", "NQ"), "PRE", "LVL"), ("B ES+NQ PRE/WIDE", ("ES", "NQ"), "PRE", "WIDE"),
            ("C NQ PRE/LVL", ("NQ",), "PRE", "LVL"), ("ref ES+NQ ORB/LVL", ("ES", "NQ"), "OR", "LVL")]
    MODES = [("flat2R", ("flat", 2.0), "HOD"), ("flat3R", ("flat", 3.0), "HOD"),
             ("4tier", ("tier",), "HOD"), ("4tier-PT1=1R", ("tier",), "1R")]
    SIG = {(r, ls): {D: bt.signals(S, ls) for D, S in SESS[r].items()} for r in ROOTS for ls in ("PRE", "OR")}
    rows = []
    for vname, roots, ls, sm in VARS:
        for cutoff in (630, 645, 660):
            # same entries for every mode
            ent = {}
            for D in dates:
                cands = []
                for r in roots:
                    if D not in SESS[r]: continue
                    for s in SIG[(r, ls)][D]:
                        e = setup(SESS[r][D], s, sm, r, cutoff)
                        if e: e["root"] = r; e["t"] = int(SESS[r][D]["tod"][s[0]]); e["sig"] = s; cands.append(e); break
                if cands: ent[D] = min(cands, key=lambda x: (x["t"], x["root"] != "ES"))
            for mname, mode, p1 in MODES:
                tr = {D: run(SESS[e["root"]][D], e, mode, e["root"], cutoff, p1) for D, e in ent.items()}
                arr = np.array([tr[D]["usd"] if D in tr else 0.0 for D in dates])
                Rs = np.array([t["R"] for t in tr.values()])
                h1 = np.array([tr[D]["usd"] if D in tr else 0 for D in dates if D < SPLIT]); h2 = np.array([tr[D]["usd"] if D in tr else 0 for D in dates if D >= SPLIT])
                rng = np.random.default_rng(7); flips = rng.choice([-1, 1], size=(2000, len(arr)))
                p = float(((flips * arr).mean(1) >= arr.mean()).mean())
                mon = {}
                for D in dates: mon[D[:7]] = mon.get(D[:7], 0) + (tr[D]["usd"] if D in tr else 0)
                row = dict(var=vname, cutoff=cutoff, mode=mname, n=len(tr), win=float((Rs > 0).mean()), R=float(Rs.mean()),
                           per_day=float(arr.mean()), h1=float(h1.mean()), h2=float(h2.mean()), p=p, maxdd=maxdd(arr),
                           green=sum(v > 0 for v in mon.values()), months=len(mon),
                           worst_day=float(arr.min()), best_day=float(arr.max()),
                           med_peak=float(np.median([t["peak"] for t in tr.values()])),
                           giveback=float(np.mean([max(0.0, t["peak"] - t["usd"]) for t in tr.values()])))
                if mode[0] == "tier":
                    row["collapse"] = float(np.mean([t["coll"] for t in tr.values()]))
                    row["nlegs"] = float(np.mean([t["nlegs"] for t in tr.values()]))
                    for pt in ("PT1", "PT2", "PT3", "PT4"): row[f"f_{pt}"] = float(np.mean([pt in t["filled"] for t in tr.values()]))
                    row["be_exit"] = float(np.mean([t["why"] == "be" for t in tr.values()]))
                if cutoff == 660:
                    daily = [(D, tr[D]["usd"]) for D in dates if D in tr]
                    g = PG.gate_series(daily, FIRMS); lk = LC.compute(daily, FIRMS, n_shuffles=300, seed=1337)
                    for f in FIRMS:
                        row[f"{f}|allstarts"] = g[f]["all_starts_pass_pct"]; row[f"{f}|eval_ready"] = lk[f].get("eval_ready")
                        row[f"{f}|h2real"] = lk[f]["h2"]["real_pass_pct"]; row[f"{f}|h2shuf"] = lk[f]["h2"]["shuffled_pass_pct"]
                rows.append(row)
                print(json.dumps(row, default=float), flush=True)
    json.dump(rows, open(HERE / "results.json", "w"), default=float, indent=1)

if __name__ == "__main__":
    main()
