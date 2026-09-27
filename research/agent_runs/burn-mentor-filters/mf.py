"""burn-mentor-filters: Scarface / J-Dub rules as filters and exits on the frozen MNQ cell
(OR5, disp>=1 ATR, wick retest +-1 tick, strong/pin trigger, 2R, 10:30 last entry+flat, 1/day).
Paper research only, exploratory, no cell promotion. Honest fills as orb1m.py: entry next open +1 tick,
stop min(stop,open)-1 tick, target needs 1 tick through, same bar = stop, flat at cutoff open -1 tick,
$1.24 RT/micro, $200/trade risk sizing (as v3-t-mnq/mnq.py).
Usage: python mf.py        -> baseline check (n=105, +0.309R) + rule table -> mf_res.json, mf_trades.json
       python mf.py test   -> synthetic unit tests for the exit simulators"""
import sys, os, glob, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import orb1m  # frozen copy, byte-identical to v2-t01-orb-1m/orb1m.py (untracked)
from orb1m import pin, strong, sim, TICK

FUT = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t01-orb5\fut"
USD, COMM, RISK, MAXN, CUT = 2.0, 1.24, 200.0, 50, 60
HOL = set("2024-11-28 2024-12-25 2025-01-01 2025-01-09 2025-01-20 2025-02-17 2025-04-18 2025-05-26 2025-06-19 2025-07-04 2025-09-01 2025-11-27 2025-12-25 2026-01-01 2026-01-19 2026-02-16 2026-04-03 2026-05-25 2026-06-19 2026-07-03 2026-09-07".split())
NSH, NPERM = 200, 5000
RNG = np.random.default_rng(7)


def arr91(g):
    m = (g.index.hour * 60 + g.index.minute - 570).to_numpy(); ok = (m >= 0) & (m <= 90); A = {}
    for k in ("open", "high", "low", "close"):
        a = np.full(91, np.nan); a[m[ok]] = g[k].to_numpy()[ok]; A[k] = a
    return A


def load_real():
    """Same loader as v3-t-mnq/mnq.py::load_real (front-month NQ by RTH volume)."""
    parts = []
    for f in sorted(glob.glob(FUT + r"\NQ*.csv")):
        d = pd.read_csv(f)
        if d.empty: continue
        d.columns = [c.lower() for c in d.columns]
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York")
        d["k"] = os.path.basename(f).split("_")[0]; parts.append(d[["ts", "open", "high", "low", "close", "volume", "k"]])
    df = pd.concat(parts).set_index("ts").sort_index(); t = df.index.hour * 60 + df.index.minute
    rth = df[(t >= 570) & (t < 960)].copy(); rth["date"] = rth.index.strftime("%Y-%m-%d")
    front = rth.groupby(["date", "k"])["volume"].sum().reset_index().sort_values("volume").groupby("date").last()["k"]
    days = []; prev = None
    for D, k in front.items():
        if D in HOL: continue
        c = df[df.k == k]; g = rth[(rth.date == D) & (rth.k == k)]; A = arr91(g)
        if np.isnan(A["open"][:5]).all(): continue
        on = c[(c.index > pd.Timestamp(D + " 09:29", tz="America/New_York") - pd.Timedelta(hours=15, minutes=29)) & (c.index < pd.Timestamp(D + " 09:30", tz="America/New_York"))]
        pr = rth[(rth.date == prev) & (rth.k == k)] if prev else None
        A.update(date=D, onh=on.high.max() if len(on) else None, onl=on.low.min() if len(on) else None,
                 pdh=pr.high.max() if pr is not None and len(pr) else None, pdl=pr.low.min() if pr is not None and len(pr) else None)
        days.append(A); prev = D
    return days


def atr_at(rngs, j):
    p = rngs[max(0, j - 14):j]
    return np.nanmean(p) if np.sum(~np.isnan(p)) >= 3 else np.nan


def signal(A, cut=CUT, dk=1.0, tol=TICK):
    """mnq.signal(v2 baseline) logic, unchanged, but also returns level / break bar / ATRs for the filters."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    orh, orl = np.nanmax(H[:5]), np.nanmin(L[:5]); rngs = H - L; state = None
    for j in range(5, cut - 1):
        if np.isnan(C[j]): continue
        atr = atr_at(rngs, j)
        def brk():
            s = [1, orh, j, H[j] - orh, False, atr] if C[j] > orh else ([-1, orl, j, orl - L[j], False, atr] if C[j] < orl else None)
            if s: s[4] = s[3] >= dk * atr
            return s
        if state is None: state = brk(); continue
        side, lvl, bi, exc, disp, atr_b = state
        if (C[j] - lvl) * side <= 0: state = brk(); continue
        touched = (L[j] <= lvl + tol) if side > 0 else (H[j] >= lvl - tol)
        if touched and disp and j > bi and strong(O[j], H[j], L[j], C[j], side) and not np.isnan(O[j + 1]):
            return dict(i=j + 1, side=side, stop=(L[j] - TICK) if side > 0 else (H[j] + TICK), j=j, lvl=lvl, bi=bi, atr=atr, atr_b=atr_b)
        state[3] = max(exc, (H[j] - lvl) if side > 0 else (lvl - L[j]))
        if not disp and not np.isnan(atr) and state[3] >= dk * atr: state[4] = True
        if j - bi > 30: state = None
    return None


def flat_px(A, cut):
    if cut < 91 and not np.isnan(A["open"][cut]): return A["open"][cut]
    v = A["close"][:cut]; return v[~np.isnan(v)][-1]


def ex_trade(A, i, d, dist, mode="base", cut=CUT, lvl_off=None):
    """Returns (R, usd). R = usd / (n * dist * $/pt), as mnq.trade('2R').
    base      : hard intrabar stop, 2R limit (orb1m.sim)
    jdub      : 25% off at HOD/LOD-so-far (limit, 1 tick through), then stop -> breakeven; rest 2R
    closestop : Scarface: no intrabar stop; exit next open -1 tick after a 1-min CLOSE beyond the stop
    lvlclose  : hard stop + exit next open after a close back through the OR level (lvl_off = (lvl-fill)*d)"""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    fill = O[i] + TICK * d; stop = fill - d * dist; tgt = fill + d * 2 * dist
    n = min(MAXN, int(RISK // (dist * USD + COMM))) or 1
    if mode == "base":
        pts = (sim(A, d, i, stop, tgt, cut) - fill) * d * n
    else:
        legs = [n]; pts = 0.0; q1 = 0; t1 = None
        if mode == "jdub":
            ext = (np.nanmax(H[:i]) if d > 0 else np.nanmin(L[:i]))
            if (ext - fill) * d >= TICK and n >= 2: q1 = max(1, int(round(n * 0.25))); t1 = ext
        rem = n; trimmed = False; b = i; pending = False
        while b < cut and rem:
            if np.isnan(O[b]): b += 1; continue
            if pending:  # close-based exit fills at this bar's open -1 tick
                pts += rem * (O[b] - d * TICK - fill) * d; rem = 0; break
            lo_hit = (L[b] <= stop) if d > 0 else (H[b] >= stop)
            if mode != "closestop" and lo_hit:
                px = (min(stop, O[b]) - TICK) if d > 0 else (max(stop, O[b]) + TICK)
                pts += rem * (px - fill) * d; rem = 0; break
            if t1 is not None and not trimmed and ((H[b] >= t1 + TICK) if d > 0 else (L[b] <= t1 - TICK)):
                pts += q1 * (t1 - fill) * d; rem -= q1; trimmed = True; stop = fill  # BE from the next bar
            if (H[b] >= tgt + TICK) if d > 0 else (L[b] <= tgt - TICK):
                pts += rem * (tgt - fill) * d; rem = 0; break
            if mode == "closestop" and (C[b] - stop) * d <= 0: pending = True
            if mode == "lvlclose" and (C[b] - (fill + d * lvl_off)) * d <= 0: pending = True
            b += 1
        if rem:
            pts += rem * (flat_px(A, cut) - d * TICK - fill) * d
    usd = pts * USD - n * COMM
    return usd / (n * dist * USD), usd


FILTERS = {  # name: (mentor tag from mentor-alignment video share, predicate(A, s, fill))
    "candle close >=0.5 ATR past level (trigger)": ("both (SF 55 / JD 72)", lambda A, s, f: (A["close"][s["j"]] - s["lvl"]) * s["side"] >= 0.5 * s["atr"]),
    "candle close >=0.5 ATR past level (break bar)": ("both (SF 55 / JD 72)", lambda A, s, f: (A["close"][s["bi"]] - s["lvl"]) * s["side"] >= 0.5 * s["atr_b"]),
    "hammer/wick trigger only": ("both, JD-lean (SF 61 / JD 80)", lambda A, s, f: pin(A["open"][s["j"]], A["high"][s["j"]], A["low"][s["j"]], A["close"][s["j"]], s["side"])),
    "PDH/PDL confluence (OR lvl within 1 ATR)": ("both, JD-lean (SF 66 / JD 88)", lambda A, s, f: any(x is not None and abs(s["lvl"] - x) <= s["atr"] for x in (A["pdh"], A["pdl"]))),
    "PDH/PDL/ONH/ONL confluence (1 ATR)": ("both, JD-lean (SF 66 / JD 88)", lambda A, s, f: any(x is not None and not pd.isna(x) and abs(s["lvl"] - x) <= s["atr"] for x in (A["pdh"], A["pdl"], A["onh"], A["onl"]))),
    "wait out first 15 min (trigger >= 9:45)": ("Scarface (SF 16 / JD 7)", lambda A, s, f: s["j"] >= 15),
    "don't chase (fill <=4 ATR from 9:30 open)": ("Scarface (SF 24 / JD 13)", lambda A, s, f: abs(f - A["open"][0]) <= 4 * s["atr"]),
}
EXITS = {"J-Dub 25% @ HOD/LOD + BE": ("J-Dub", "jdub"),
         "Scarface close-through stop (close past stop)": ("Scarface", "closestop"),
         "exit on close back through OR level (+hard stop)": ("both (SF 95 / JD 98)", "lvlclose")}


def halves(T, mid):
    a = [t["R"] for t in T if t["date"] < mid]; b = [t["R"] for t in T if t["date"] >= mid]
    return (float(np.mean(a)) if a else None), (float(np.mean(b)) if b else None)


def day_shuffle(T, days, mode):
    out = []
    for _ in range(NSH):
        rr = []
        for t in T:
            while True:
                k = int(RNG.integers(len(days)))
                if k != t["k"] and not np.isnan(days[k]["open"][t["i"]]): break
            rr.append(ex_trade(days[k], t["i"], t["side"], t["dist"], mode, lvl_off=t["lvl_off"])[0])
        out.append(np.mean(rr))
    return np.array(out)


def main():
    days = load_real(); mid = days[len(days) // 2]["date"]
    print("days", len(days), days[0]["date"], days[-1]["date"], "mid", mid, flush=True)
    T = []
    for k, A in enumerate(days):
        s = signal(A)
        if not s: continue
        fill = A["open"][s["i"]] + TICK * s["side"]; dist = (fill - s["stop"]) * s["side"]
        if dist < 2 * TICK: continue
        r, u = ex_trade(A, s["i"], s["side"], dist)
        T.append(dict(date=A["date"], k=k, i=s["i"], j=s["j"], side=s["side"], dist=float(dist), R=r, usd=u,
                      lvl_off=float((s["lvl"] - fill) * s["side"]), sig=s, fill=float(fill)))
    R0 = np.array([t["R"] for t in T]); base = float(R0.mean()); h1, h2 = halves(T, mid)
    sh0 = day_shuffle(T, days, "base"); p0 = float((sh0 >= base).mean())
    print(f"BASE n={len(T)} R={base:+.3f} H1={h1:+.3f} H2={h2:+.3f} win={np.mean(R0 > 0):.3f} p_shuf={p0:.3f}", flush=True)
    rows = [dict(rule="unfiltered (frozen cell)", tag="-", kind="-", n=len(T), R=base, h1=h1, h2=h2, dR=0.0, p_shuf=p0, p_vs=None)]
    for name, (tag, fn) in FILTERS.items():
        keep = np.array([bool(fn(days[t["k"]], t["sig"], t["fill"])) for t in T]); K = [t for t, m in zip(T, keep) if m]
        if len(K) < 3: rows.append(dict(rule=name, tag=tag, kind="filter", n=len(K))); continue
        r = float(np.mean([t["R"] for t in K])); a, b = halves(K, mid)
        sub = np.array([R0[RNG.choice(len(T), len(K), replace=False)].mean() for _ in range(NPERM)])
        p_vs = float((np.abs(sub - base) >= abs(r - base) - 1e-12).mean())  # two-sided: random same-size subset
        p_sh = float((day_shuffle(K, days, "base") >= r).mean())
        rows.append(dict(rule=name, tag=tag, kind="filter", n=len(K), R=r, h1=a, h2=b, dR=r - base, p_shuf=p_sh, p_vs=p_vs))
        print(json.dumps(rows[-1]), flush=True)
    for name, (tag, mode) in EXITS.items():
        Rm = np.array([ex_trade(days[t["k"]], t["i"], t["side"], t["dist"], mode, lvl_off=t["lvl_off"])[0] for t in T])
        K = [dict(t, R=float(x)) for t, x in zip(T, Rm)]; a, b = halves(K, mid); dl = Rm - R0
        flips = RNG.choice([-1.0, 1.0], size=(NPERM, len(dl))); pm = (flips * dl).mean(1)
        p_vs = float((np.abs(pm) >= abs(dl.mean()) - 1e-12).mean())  # paired sign-flip, two-sided
        p_sh = float((day_shuffle(T, days, mode) >= Rm.mean()).mean())
        rows.append(dict(rule=name, tag=tag, kind="exit", n=len(T), R=float(Rm.mean()), h1=a, h2=b, dR=float(dl.mean()),
                         p_shuf=p_sh, p_vs=p_vs, changed=int((np.abs(dl) > 1e-9).sum())))
        print(json.dumps(rows[-1]), flush=True)
    json.dump(rows, open(os.path.join(HERE, "mf_res.json"), "w"), indent=1)
    json.dump([{k: v for k, v in t.items() if k != "sig"} for t in T], open(os.path.join(HERE, "mf_trades.json"), "w"), default=float)
    print("DONE")


def _day(bars):
    A = {k: np.full(91, np.nan) for k in ("open", "high", "low", "close")}
    for m, (o, h, l, c) in bars.items():
        A["open"][m], A["high"][m], A["low"][m], A["close"][m] = o, h, l, c
    return A


def test():
    """dist 1 pt, 50 MNQ: commission = 0.62R. long fill 100.25, stop 99.25, 2R target 102.25."""
    ok = lambda r, e: abs(r - e) < 1e-9 or (_ for _ in ()).throw(AssertionError((r, e)))
    fl = {m: (100, 100.5, 99.5, 100) for m in range(0, 91)}; fl[0] = (100, 101.5, 99, 100)  # HOD 101.5
    A = _day({**fl, 12: (100, 102.5, 100, 102.4)}); ok(ex_trade(A, 10, 1, 1.0, "base")[0], 1.38)
    # wick through stop, close above: base stopped at 99.0, close-stop survives to target
    A = _day({**fl, 11: (100, 100.3, 99.0, 100.1), 12: (100, 102.5, 100, 102.4)})
    ok(ex_trade(A, 10, 1, 1.0, "base")[0], -1.87); ok(ex_trade(A, 10, 1, 1.0, "closestop")[0], 1.38)
    # close below stop: close-stop exits next open 98.0 - 1 tick
    A = _day({**fl, 11: (100, 100.3, 98.5, 98.9), 12: (98.0, 98.2, 97.5, 98.0)}); ok(ex_trade(A, 10, 1, 1.0, "closestop")[0], -3.12)
    # J-Dub: 12 of 50 off at HOD 101.5, BE stop fills 100.0 (1 tick slip): (12*1.25 - 38*.25)*2 - 62 = -51
    A = _day({**fl, 11: (100.5, 101.8, 100.4, 101.6), 12: (101, 101.2, 100.0, 100.1)})
    ok(ex_trade(A, 10, 1, 1.0, "jdub")[0], -0.51); ok(ex_trade(A, 10, 1, 1.0, "base")[0], -1.12)
    # level 99.75: close 99.6 through it -> exit next open 99.9 - 1 tick
    A = _day({**fl, 11: (100, 100.3, 99.5, 99.6), 12: (99.9, 100, 99.8, 99.9)}); ok(ex_trade(A, 10, 1, 1.0, "lvlclose", lvl_off=-0.5)[0], -1.22)
    # short mirror of the wick case
    fs = {m: (100, 100.5, 99.5, 100) for m in range(0, 91)}
    A = _day({**fs, 11: (100, 101.0, 99.7, 99.9), 12: (99.9, 100, 97.5, 97.6)})
    ok(ex_trade(A, 10, -1, 1.0, "base")[0], -1.87); ok(ex_trade(A, 10, -1, 1.0, "closestop")[0], 1.38)
    print("TESTS OK")


if __name__ == "__main__":
    test() if len(sys.argv) > 1 and sys.argv[1] == "test" else main()
