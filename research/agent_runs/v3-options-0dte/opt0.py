"""v3 t-options-0dte: real SPY/QQQ 0DTE option 1-min bars vs underlying. Paper research only.
mode 'sig' -> signals.json ; 'fetch' -> cache option bars (5 calls/min) ; 'an' -> tables."""
import sys, os, json, glob
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AR = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(AR, "v3-options")); sys.path.insert(0, os.path.join(AR, "v2-t01-orb-1m")); sys.path.insert(0, os.path.join(AR, "v3-a2-s-detector"))
ARCH = os.path.join(AR, "..", "..", "data_archive")
START = "2024-09-27"; CUTS = {"1030": 60, "1045": 75, "1100": 90}; TK = 0.01; COMM = 0.0065  # $0.65/contract/side
import functools
@functools.lru_cache(maxsize=None)
def load(und, d):
    f = os.path.join(ARCH, und, d + ".csv")
    if not os.path.exists(f): return None
    df = pd.read_csv(f); ts = pd.to_datetime(df["Datetime"].astype(str).str[:19], errors="coerce")
    mm = (ts.dt.hour * 60 + ts.dt.minute - 570).values; ok = (mm >= 0) & (mm < 390)
    A = {}
    for k, c in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")):
        a = np.full(391, np.nan); a[mm[ok]] = df[c].values[ok]; A[k] = a
    return A if np.sum(~np.isnan(A["close"][:90])) > 60 else None
def days(und): return sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(ARCH, und, "*.csv")) if os.path.basename(f)[:-4] >= START)

def make_signals():
    import types; sys.modules.setdefault("omen_data", types.SimpleNamespace(load_fut=None, SPEC={}))
    import orb1m; orb1m.TICK = TK
    S = []
    for und in ("QQQ", "SPY"):
        for d in days(und):
            A = load(und, d)
            if A is None: continue
            A91 = {k: v[:91] for k, v in A.items()}
            for cn, cut in CUTS.items():
                s = orb1m.signal(A91, 5, cut, 1.0, "strong")
                if s: S.append(dict(v="M" + cn, und=und, d=d, i=int(s[0]), side=int(s[1]), stop=float(s[2]), cut=cut))
    # baseline: v2 MNQ OR5 10:30 strong trade list, mapped to QQQ at same minute (dist / 41.32)
    for cn in CUTS:
        for t in json.load(open(os.path.join(AR, "v2-t01-orb-1m", f"trades_MNQ_OR5_{cn}_D1_strong.json"))):
            A = load("QQQ", t["date"])
            if A is None or np.isnan(A["open"][t["i"]]): continue
            e = A["open"][t["i"]] + TK * t["side"]
            S.append(dict(v="B" + cn, und="QQQ", d=t["date"], i=int(t["i"]), side=int(t["side"]), stop=float(e - t["side"] * t["dist"] / 41.32), cut=CUTS[cn]))
    # a2 S-detector fires (best.json params), SPY/QQQ only
    import s_det as SD
    P = json.load(open(os.path.join(SD.OUT, "best.json")))["best"]
    for und in ("QQQ", "SPY"):
        for d in days(und):
            for f in SD.detect(und, d, P):
                b = SD.day_bars(und, d); ei = f["i"] + 1
                if ei >= len(b["m"]): continue
                em = int(b["m"][ei])
                for cn, cut in CUTS.items():
                    if em < cut: S.append(dict(v="A" + cn, und=und, d=d, i=em, side=int(f["side"]), stop=float(f["stop"]), cut=cut))
    json.dump(S, open(os.path.join(HERE, "signals.json"), "w"))
    import collections; print(collections.Counter(s["v"] + s["und"] for s in S))

def contract(s):
    A = load(s["und"], s["d"]); spot = A["close"][s["i"] - 1]
    if np.isnan(spot): spot = A["open"][s["i"]]
    k = int(round(spot)); cp = "C" if s["side"] > 0 else "P"
    return f"O:{s['und']}{s['d'][2:4]}{s['d'][5:7]}{s['d'][8:10]}{cp}{k*1000:08d}"
PRI = ["B1030", "M1030", "B1100", "M1100", "A1100", "B1045", "M1045", "A1030", "A1045"]
def fetch():
    import opt_loader as OL
    S = json.load(open(os.path.join(HERE, "signals.json"))); seen = []
    for v in PRI:
        for s in S:
            if s["v"] != v: continue
            tk = contract(s)
            if (tk, s["d"]) in seen: continue
            seen.append((tk, s["d"]))
            try: OL._get(f"/v2/aggs/ticker/{tk}/range/1/minute/{s['d']}/{s['d']}", adjusted="true", sort="asc", limit=50000)
            except Exception as ex: print("ERR", tk, ex, flush=True)
            print(len(seen), v, tk, flush=True)

def optbars(s):
    import opt_loader as OL
    tk = contract(s); d = s["d"]
    key = OL.find_cached(f"/v2/aggs/ticker/{tk}/range/1/minute/{d}/{d}", adjusted="true", sort="asc", limit=50000)
    if key is None: return None
    b = OL._bars(json.load(open(key)))
    O = {k: np.full(391, np.nan) for k in "ohlc"}
    if not len(b): return O
    mm = (b.index.hour * 60 + b.index.minute - 570).values; ok = (mm >= 0) & (mm < 390)
    for k in "ohlc": O[k][mm[ok]] = b[k].values[ok]
    return O
def opx(O, m, k, lim=2):
    for j in range(m, min(m + lim + 1, 390)):
        if not np.isnan(O[k][j]): return O[k][j]
    return None

def legs(A, s, scale):
    """underlying events -> list of (weight, exit_min_react, und_exit_px, kind). stop wins ties."""
    sd, i, cut = s["side"], s["i"], s["cut"]; H, L, Op = A["high"], A["low"], A["open"]
    e = Op[i] + TK * sd; dist = (e - s["stop"]) * sd
    if not dist >= 2 * TK: return None, e, dist
    stop = s["stop"]
    if not scale: tg = [(1.0, e + sd * 2 * dist)]
    else:
        ex = np.nanmax(H[:i]) if sd > 0 else np.nanmin(L[:i]); t = []
        if (ex - e) * sd >= 0.2 * dist and (ex - e) * sd < 2 * dist: t.append(ex)
        t += [e + sd * 2 * dist, e + sd * 4 * dist]
        w = [.3, .3, .1] if len(t) == 3 else [.3, .1]; w = [x / sum(w) for x in w]; tg = list(zip(w, t))
    out = []; open_ = list(tg); first = True
    for j in range(i, cut):
        if np.isnan(Op[j]) or not open_: continue
        if (L[j] <= stop if sd > 0 else H[j] >= stop):
            px = (min(stop, Op[j]) if sd > 0 else max(stop, Op[j])) - TK * sd
            out += [(w, j, px, "stop") for w, _ in open_]; open_ = []; break
        hit = [(w, p) for w, p in open_ if (H[j] >= p + TK if sd > 0 else L[j] <= p - TK)]
        for w, p in hit: out.append((w, j, p, "tgt"))
        open_ = [x for x in open_ if x not in hit]
        if hit and scale and first: stop = e; first = False   # BE after PT1
    if open_:
        px = (Op[cut] if not np.isnan(Op[cut]) else A["close"][cut - 1]) - TK * sd
        out += [(w, cut, px, "flat") for w, _ in open_]
    return out, e, dist

def trade(s, scale, stress=False):
    A = load(s["und"], s["d"]); L_, e, dist = legs(A, s, scale)
    if L_ is None: return None
    sd = s["side"]; uR = sum(w * ((px - e) * sd - 0.01) for w, _, px, _ in L_) / dist
    O = optbars(s)
    if O is None: return dict(uR=uR, oR=None, d=s["d"], dist=dist)
    oe = opx(O, s["i"], "h" if stress else "o")
    if oe is None: return dict(uR=uR, oR=None, miss=1, d=s["d"], dist=dist)
    oe += TK + COMM; pnl = 0
    for w, x, _, kind in L_:
        m = x + (0 if (kind == "flat" or stress) else 1)   # react next bar open after a stop/target print
        px = opx(O, m, "l" if stress else "o", 3) if m < 390 else None
        if px is None: px = opx(O, x, "c", 0) or 0.0
        pnl += w * (px - TK - COMM - oe)
    risk = 0.5 * dist + 2 * TK + 2 * COMM   # planned risk proxy: delta 0.5 x und stop + slip + comm
    return dict(uR=uR, oR=pnl / risk, usd=pnl * 100, riskusd=risk * 100, prem=oe, d=s["d"], dist=dist)

def st(x):
    x = np.asarray(x, float); n = len(x)
    if n < 2: return dict(n=n)
    return dict(n=n, mean=round(x.mean(), 3), win=round((x > 0).mean(), 3), t=round(x.mean() / x.std(ddof=1) * n ** .5, 2))
def an():
    S = json.load(open(os.path.join(HERE, "signals.json"))); rng = np.random.default_rng(7); res = {}
    mid = "2025-09-26"
    for v in sorted({s["v"] for s in S}):
        for und in ("QQQ", "SPY"):
            ss = [s for s in S if s["v"] == v and s["und"] == und]
            if not ss: continue
            for scale in (0, 1):
                for stress in ((0, 1) if not scale else (0,)):
                    T = [t for t in (trade(s, scale, stress) for s in ss) if t]
                    U = [t["uR"] for t in T]; Tt = [t for t in T if t.get("oR") is not None]
                    oR = np.array([t["oR"] for t in Tt]); uR2 = np.array([t["uR"] for t in Tt]); dd = np.array([t["d"] for t in Tt])
                    r = dict(und_all=st(U), und_on_opt=st(uR2), opt=st(oR), cover=f"{len(Tt)}/{len(T)}")
                    if len(oR) >= 4:
                        r["H1"] = st(oR[dd < mid]); r["H2"] = st(oR[dd >= mid])
                        r["yr"] = {y: st(oR[np.char.startswith(dd.astype(str), y)])for y in ("2024", "2025", "2026")}
                        bs = [rng.choice(oR, len(oR)).mean() for _ in range(2000)]; r["boot_p_le0"] = round(float(np.mean(np.array(bs) <= 0)), 3)
                        r["usd_ct_mean"] = round(float(np.mean([t["usd"] for t in Tt])), 1); r["med_risk_ct"] = round(float(np.median([t["riskusd"] for t in Tt])), 1)
                        r["med_prem"] = round(float(np.median([t["prem"] for t in Tt])), 2)
                        r["Rlist"] = [round(float(x), 3) for x in oR]; r["dlist"] = list(dd)
                    res[f"{v}|{und}|{'scale' if scale else 'flat2R'}|{'stress' if stress else 'base'}"] = r
    json.dump(res, open(os.path.join(HERE, "an.json"), "w"))
    for k, r in res.items(): print(k, r["cover"], "und", r["und_all"], "undOnOpt", r["und_on_opt"], "opt", r["opt"], "H1", r.get("H1"), "H2", r.get("H2"), "p", r.get("boot_p_le0"), "$ct", r.get("usd_ct_mean"), "risk", r.get("med_risk_ct"))
if __name__ == "__main__": {"sig": make_signals, "fetch": fetch, "an": an}[sys.argv[1]]()
