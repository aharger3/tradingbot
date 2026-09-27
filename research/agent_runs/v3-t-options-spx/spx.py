"""v3 t-options-spx: SPXW 0DTE real 1-min bars. Paper research only. sig|fetch|an. Reuses v3-options-0dte/opt0.py."""
import sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); AR = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(AR, "v3-options-0dte")); sys.path.insert(0, os.path.join(AR, "v3-options"))
import opt0 as O0
from opt0 import load, legs, opx, st, CUTS, TK
OTK = 0.10; OCOMM = 0.0125   # SPXW: 1 tick 0.10 slip/side, $1.25/contract/side (comm+fees)
SIG = os.path.join(HERE, "signals.json")
def make_signals():
    S0 = json.load(open(os.path.join(AR, "v3-options-0dte", "signals.json")))
    S = [s for s in S0 if s["und"] == "SPY" and s["v"][0] in "MA"]
    for cn in CUTS:  # v2 MNQ baseline -> SPY proxy, stop matched in % (NQ ~= QQQ*41.32)
        for t in json.load(open(os.path.join(AR, "v2-t01-orb-1m", f"trades_MNQ_OR5_{cn}_D1_strong.json"))):
            A = load("SPY", t["date"]); Q = load("QQQ", t["date"])
            if A is None or Q is None or np.isnan(A["open"][t["i"]]) or np.isnan(Q["open"][t["i"]]): continue
            e = A["open"][t["i"]] + TK * t["side"]; dspy = t["dist"] / 41.32 * A["open"][t["i"]] / Q["open"][t["i"]]
            S.append(dict(v="B" + cn, und="SPY", d=t["date"], i=int(t["i"]), side=int(t["side"]), stop=float(e - t["side"] * dspy), cut=CUTS[cn]))
    json.dump(S, open(SIG, "w")); import collections; print(collections.Counter(s["v"] for s in S))
def contract(s):
    A = load("SPY", s["d"]); spot = A["close"][s["i"] - 1]
    if np.isnan(spot): spot = A["open"][s["i"]]
    k = int(round(spot * 10 / 5) * 5); cp = "C" if s["side"] > 0 else "P"
    return f"O:SPXW{s['d'][2:4]}{s['d'][5:7]}{s['d'][8:10]}{cp}{k*1000:08d}"
PRI = ["B1030", "B1100", "B1045", "M1030", "M1100", "A1030", "A1100"]
def fetch():
    import opt_loader as OL
    S = json.load(open(SIG)); rng = np.random.default_rng(11); seen = set()
    for v in PRI:
        ss = [s for s in S if s["v"] == v]; rng.shuffle(ss)
        for s in ss:
            tk = contract(s)
            if (tk, s["d"]) in seen: continue
            seen.add((tk, s["d"]))
            try: OL._get(f"/v2/aggs/ticker/{tk}/range/1/minute/{s['d']}/{s['d']}", adjusted="true", sort="asc", limit=50000)
            except Exception as ex: print("ERR", tk, repr(ex)[:120], flush=True)
            print(len(seen), v, tk, flush=True)
def optbars(s):
    import opt_loader as OL
    tk = contract(s); d = s["d"]
    key = OL.find_cached(f"/v2/aggs/ticker/{tk}/range/1/minute/{d}/{d}", adjusted="true", sort="asc", limit=50000)
    if key is None: return None
    b = OL._bars(json.load(open(key))); Ob = {k: np.full(391, np.nan) for k in "ohlc"}
    if not len(b): return Ob
    mm = (b.index.hour * 60 + b.index.minute - 570).values; ok = (mm >= 0) & (mm < 390)
    for k in "ohlc": Ob[k][mm[ok]] = b[k].values[ok]
    return Ob
def price(s, Ob, scale, stress=False, i=None):
    s2 = dict(s)
    if i is not None:  # shuffle: same day/side/stop distance, random entry minute
        A = load("SPY", s["d"]); e0 = A["open"][s["i"]] + TK * s["side"]; dist0 = (e0 - s["stop"]) * s["side"]
        if np.isnan(A["open"][i]): return None
        s2["i"] = i; s2["stop"] = A["open"][i] + TK * s["side"] - s["side"] * dist0
    A = load("SPY", s["d"]); L_, e, dist = legs(A, s2, scale)
    if L_ is None: return None
    sd = s["side"]; uR = sum(w * ((px - e) * sd - 0.01) for w, _, px, _ in L_) / dist
    oe = opx(Ob, s2["i"], "h" if stress else "o")
    if oe is None: return None
    oe += OTK + OCOMM; pnl = 0
    for w, x, _, kind in L_:
        m = x + (0 if (kind == "flat" or stress) else 1)
        px = opx(Ob, m, "l" if stress else "o", 3) if m < 390 else None
        if px is None: px = opx(Ob, x, "c", 0) or 0.0
        pnl += w * (px - OTK - OCOMM - oe)
    risk = 0.5 * dist * 10 + 2 * OTK + 2 * OCOMM
    return dict(uR=uR, oR=pnl / risk, usd=pnl * 100, riskusd=risk * 100, prem=oe, d=s["d"])
def an():
    S = json.load(open(SIG)); rng = np.random.default_rng(7); res = {}; mid = "2025-09-26"
    for v in sorted({s["v"] for s in S}):
        ss = [s for s in S if s["v"] == v]
        for scale in (0, 1):
            for stress in ((0, 1) if not scale else (0,)):
                U = []; T = []; UD = []
                for s in ss:
                    A = load("SPY", s["d"]); L_, e, dist = legs(A, s, scale)
                    if L_ is None: continue
                    U.append(sum(w * ((px - e) * s["side"] - 0.01) for w, _, px, _ in L_) / dist); UD.append(s["d"])
                    Ob = optbars(s)
                    if Ob is None: continue
                    t = price(s, Ob, scale, stress)
                    if t: t["s"] = s; t["Ob"] = Ob; T.append(t)
                Ua = np.array(U); Ud = np.array(UD)
                r = dict(und=st(U), undH1=st(Ua[Ud < mid]), undH2=st(Ua[Ud >= mid]), undYr={y: st(Ua[np.char.startswith(Ud.astype(str), y)]) for y in ("2024", "2025", "2026")}, cover=f"{len(T)}/{len(U)}")
                if len(T) >= 4:
                    oR = np.array([t["oR"] for t in T]); dd = np.array([t["d"] for t in T])
                    r.update(undOnOpt=st([t["uR"] for t in T]), opt=st(oR), H1=st(oR[dd < mid]), H2=st(oR[dd >= mid]),
                             yr={y: st(oR[np.char.startswith(dd.astype(str), y)]) for y in ("2024", "2025", "2026")},
                             usd_ct=round(float(np.mean([t["usd"] for t in T])), 1), med_risk_ct=round(float(np.median([t["riskusd"] for t in T])), 1),
                             med_prem=round(float(np.median([t["prem"] for t in T])), 2))
                    if not stress:
                        nm = []
                        for _ in range(200):
                            x = []
                            for t in T:
                                s = t["s"]; i = int(rng.integers(35, s["cut"] - 5)); q = price(s, t["Ob"], scale, False, i)
                                if q: x.append(q["oR"])
                            nm.append(np.mean(x))
                        r["shuf_p"] = round(float(np.mean(np.array(nm) >= oR.mean())), 3); r["shuf_mean"] = round(float(np.mean(nm)), 3)
                        # prop-style luck: bootstrap 20-trade runs, P(sum R >= +6R before <= -4R)
                        ok = 0
                        for _ in range(2000):
                            c = np.cumsum(rng.choice(oR, 40)); hit = np.where((c >= 6) | (c <= -4))[0]
                            ok += int(len(hit) and c[hit[0]] >= 6)
                        r["pass6R_before_-4R"] = round(ok / 2000, 3)
                res[f"{v}|{'scale' if scale else 'flat2R'}|{'stress' if stress else 'base'}"] = r
    json.dump(res, open(os.path.join(HERE, "an.json"), "w"), default=str)
    for k, r in res.items(): print(k, json.dumps(r, default=str))
if __name__ == "__main__": {"sig": make_signals, "fetch": fetch, "an": an}[sys.argv[1]]()
