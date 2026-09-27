"""rule-backtests-2: four more Scarface / J-Dub rules on the frozen MNQ cell (mf.py / orb1m.py, unchanged).
Paper research only, in-sample 2024-09 -> 2026-09, no cell promotion. Honest fills as orb1m.sim.
 R1 84% rule   : after a stop-out, a close back beyond the OR level (5m close, pre-reg; 1m variant) within 60 min
                 and before 10:30 -> re-enter next open +1 tick, SAME stop price, SAME target price, $200 risk.
 R2 index gate : Scarface "no trade until SPY breaks out of its 5-min range" -> ES must be beyond its own 5m OR
                 in the trade direction (a) at the trigger close, (b) at any close <= trigger.
 R3 window     : J-Dub 09:30-11:00 vs Scarface 10:30 cutoff: (a) same entries, flat 11:00 (runway),
                 (b) entries + flat to 11:00.
 R4 target     : Scarface "min 2R, HOD/LOD first; if HOD < 2R use next level": target = max(2R, HOD/LOD so far).
Usage: python rb2.py  |  python rb2.py test"""
import sys, os, glob, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mf
from mf import signal, ex_trade, halves, TICK, RISK, USD, COMM, MAXN, CUT, NPERM, HOL, FUT, arr91
from orb1m import sim

RNG = np.random.default_rng(11)
NSH = 200


def load_es():
    parts = []
    for f in sorted(glob.glob(FUT + r"\ES*.csv")):
        d = pd.read_csv(f)
        if d.empty: continue
        d.columns = [c.lower() for c in d.columns]
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York")
        d["k"] = os.path.basename(f).split("_")[0]; parts.append(d[["ts", "open", "high", "low", "close", "volume", "k"]])
    df = pd.concat(parts).set_index("ts").sort_index(); t = df.index.hour * 60 + df.index.minute
    rth = df[(t >= 570) & (t < 960)].copy(); rth["date"] = rth.index.strftime("%Y-%m-%d")
    front = rth.groupby(["date", "k"])["volume"].sum().reset_index().sort_values("volume").groupby("date").last()["k"]
    return {D: arr91(rth[(rth.date == D) & (rth.k == k)]) for D, k in front.items() if D not in HOL}


def size(dist):
    return min(MAXN, int(RISK // (dist * USD + COMM))) or 1


def trade_px(A, d, i, stop, tgt, cut=CUT):
    """orb1m.sim fill logic, returns (R on own risk, usd, exit bar, how). fill = open[i] +1 tick."""
    O, H, L = A["open"], A["high"], A["low"]
    fill = O[i] + TICK * d; dist = (fill - stop) * d; n = size(dist)
    px, b, how = None, cut, "flat"
    for j in range(i, cut):
        if np.isnan(O[j]): continue
        if (L[j] <= stop) if d > 0 else (H[j] >= stop):
            px = (min(stop, O[j]) - TICK) if d > 0 else (max(stop, O[j]) + TICK); b, how = j, "stop"; break
        if (H[j] >= tgt + TICK) if d > 0 else (L[j] <= tgt - TICK):
            px, b, how = tgt, j, "tgt"; break
    if px is None: px = mf.flat_px(A, cut) - d * TICK
    usd = (px - fill) * d * n * USD - n * COMM
    return usd / (n * dist * USD), usd, b, how


def reclaim(A, t, tf, win=60, cut=CUT):
    """First close back beyond lvl (side dir) after the stop bar; tf=1 (1m) or 5 (5m bars aligned to 09:30)."""
    C, d, lvl = A["close"], t["side"], t["lvl"]
    for b in range(t["xb"] + 1, min(t["xb"] + win, cut - 1)):
        if tf == 5 and b % 5 != 4: continue
        if np.isnan(C[b]) or np.isnan(A["open"][b + 1]): continue
        if (C[b] - lvl) * d > 0: return b + 1
    return None


def perm_subset(R0, r, k, base):
    sub = np.array([R0[RNG.choice(len(R0), k, replace=False)].mean() for _ in range(NPERM)])
    return float((np.abs(sub - base) >= abs(r - base) - 1e-12).mean())


def signflip(dl):
    pm = (RNG.choice([-1.0, 1.0], size=(NPERM, len(dl))) * dl).mean(1)
    return float((np.abs(pm) >= abs(dl.mean()) - 1e-12).mean())


def shuffle_fixed(T, days, cut=CUT):
    """Same minute, side, stop and target distances on another session (entry-price-relative)."""
    out = []
    for _ in range(NSH):
        rr = []
        for t in T:
            while True:
                k = int(RNG.integers(len(days)))
                if k != t["k"] and not np.isnan(days[k]["open"][t["i"]]): break
            A = days[k]; f = A["open"][t["i"]] + TICK * t["side"]
            rr.append(trade_px(A, t["side"], t["i"], f - t["side"] * t["dist"], f + t["side"] * t["tdist"], cut)[0])
        out.append(np.mean(rr))
    return np.array(out)


def row(name, K, mid, extra=None):
    a, b = halves(K, mid); R = np.array([t["R"] for t in K])
    r = dict(rule=name, n=len(K), R=float(R.mean()) if len(K) else None, h1=a, h2=b, win=float((R > 0).mean()) if len(K) else None)
    r.update(extra or {}); print(json.dumps(r), flush=True); return r


def main():
    days = mf.load_real(); es = load_es(); mid = days[len(days) // 2]["date"]; rows = []
    print("days", len(days), "es", len(es), "mid", mid, flush=True)
    T = []
    for k, A in enumerate(days):
        s = signal(A)
        if not s: continue
        d = s["side"]; fill = A["open"][s["i"]] + TICK * d; dist = (fill - s["stop"]) * d
        if dist < 2 * TICK: continue
        tgt = fill + d * 2 * dist
        r, u, xb, how = trade_px(A, d, s["i"], s["stop"], tgt)
        assert abs(r - ex_trade(A, s["i"], d, dist)[0]) < 1e-9
        T.append(dict(date=A["date"], k=k, i=s["i"], j=s["j"], side=d, dist=float(dist), tdist=float(2 * dist), R=r, usd=u,
                      xb=xb, how=how, lvl_off=0.0, lvl=float(s["lvl"]), stop=float(s["stop"]), tgt=float(tgt)))
    R0 = np.array([t["R"] for t in T]); base = float(R0.mean())
    rows.append(row("unfiltered frozen cell", T, mid))

    # R1 84% re-entry
    stopped = [t for t in T if t["how"] == "stop"]
    for tf in (5, 1):
        RE = []
        for t in stopped:
            A = days[t["k"]]; i = reclaim(A, t, tf)
            if i is None: continue
            f = A["open"][i] + TICK * t["side"]
            if (f - t["stop"]) * t["side"] < 2 * TICK or (t["tgt"] - f) * t["side"] <= 0: continue
            r, u, xb, how = trade_px(A, t["side"], i, t["stop"], t["tgt"])
            RE.append(dict(date=t["date"], k=t["k"], i=i, side=t["side"], dist=float((f - t["stop"]) * t["side"]),
                           tdist=float((t["tgt"] - f) * t["side"]), R=r, usd=u, how=how, pair=(t["usd"] + u) / RISK))
        if not RE: rows.append(dict(rule=f"84% re-entry ({tf}m close)", n=0)); continue
        hit = np.mean([x["how"] == "tgt" for x in RE]); n = len(RE); z = 1.96
        lo = (hit + z * z / (2 * n) - z * np.sqrt(hit * (1 - hit) / n + z * z / (4 * n * n))) / (1 + z * z / n)
        hi = (hit + z * z / (2 * n) + z * np.sqrt(hit * (1 - hit) / n + z * z / (4 * n * n))) / (1 + z * z / n)
        sh = shuffle_fixed(RE, days); rr = float(np.mean([x["R"] for x in RE]))
        rows.append(row(f"84% re-entry ({tf}m close, 60 min)", RE, mid, dict(
            stopped=len(stopped), tgt_hit=float(hit), ci=[float(lo), float(hi)], p_shuf=float((sh >= rr).mean()),
            pair_R=float(np.mean([x["pair"] for x in RE])), tot_R_added=float(sum(x["usd"] for x in RE) / RISK))))

    # R2 ES index gate
    def es_ok(t, anytime):
        E = es.get(t["date"])
        if E is None or np.isnan(E["high"][:5]).all(): return None
        orh, orl = np.nanmax(E["high"][:5]), np.nanmin(E["low"][:5]); C = E["close"][5:t["j"] + 1]
        beyond = (C > orh) if t["side"] > 0 else (C < orl)
        return bool(beyond.any()) if anytime else bool(beyond[-1]) if len(beyond) and not np.isnan(C[-1]) else False
    for anytime in (False, True):
        m = [es_ok(t, anytime) for t in T]; K = [t for t, x in zip(T, m) if x]; X = [t for t, x in zip(T, m) if x is False]
        r = float(np.mean([t["R"] for t in K]))
        rows.append(row(f"ES beyond own 5m OR ({'any close <= trigger' if anytime else 'at trigger close'})", K, mid, dict(
            p_vs=perm_subset(R0, r, len(K), base), p_shuf=float((mf.day_shuffle(K, days, "base") >= r).mean()),
            fail_n=len(X), fail_R=float(np.mean([t["R"] for t in X])) if X else None, es_missing=sum(x is None for x in m))))

    # R3 window
    Rr = np.array([trade_px(days[t["k"]], t["side"], t["i"], t["stop"], t["tgt"], 90)[0] for t in T])
    K = [dict(t, R=float(x)) for t, x in zip(T, Rr)]
    rows.append(row("same entries, flat 11:00 (runway)", K, mid, dict(dR=float((Rr - R0).mean()), p_vs=signflip(Rr - R0),
                changed=int((np.abs(Rr - R0) > 1e-9).sum()))))
    W = []
    for k, A in enumerate(days):
        s = signal(A, cut=90)
        if not s: continue
        d = s["side"]; fill = A["open"][s["i"]] + TICK * d; dist = (fill - s["stop"]) * d
        if dist < 2 * TICK: continue
        r, u, xb, how = trade_px(A, d, s["i"], s["stop"], fill + d * 2 * dist, 90)
        W.append(dict(date=A["date"], k=k, i=s["i"], side=d, dist=float(dist), tdist=float(2 * dist), R=r, usd=u, late=s["i"] > CUT))
    L = [w for w in W if w["late"]]
    rows.append(row("entries + flat to 11:00 (J-Dub window)", W, mid, dict(tot_R=float(sum(w["R"] for w in W)), base_tot_R=float(R0.sum()))))
    if L:
        r = float(np.mean([w["R"] for w in L]))
        rows.append(row("  of which new 10:30-11:00 entries", L, mid, dict(p_shuf=float((shuffle_fixed(L, days, 90) >= r).mean()))))

    # R4 target max(2R, HOD/LOD so far)
    R4 = []; far = 0
    for t in T:
        A = days[t["k"]]; d = t["side"]; f = A["open"][t["i"]] + TICK * d
        ext = np.nanmax(A["high"][:t["i"]]) if d > 0 else np.nanmin(A["low"][:t["i"]])
        tg = t["tgt"]
        if (ext - tg) * d > 0: tg = float(ext); far += 1
        R4.append(trade_px(A, d, t["i"], t["stop"], tg)[0])
    R4 = np.array(R4); K = [dict(t, R=float(x)) for t, x in zip(T, R4)]
    rows.append(row("target = max(2R, HOD/LOD so far)", K, mid, dict(dR=float((R4 - R0).mean()), p_vs=signflip(R4 - R0), hod_beyond_2R=far)))
    json.dump(rows, open(os.path.join(HERE, "rb2_res.json"), "w"), indent=1, default=float)
    print("DONE")


def test():
    ok = lambda r, e: abs(r - e) < 1e-9 or (_ for _ in ()).throw(AssertionError((r, e)))
    fl = {m: (100, 100.5, 99.5, 100) for m in range(0, 91)}
    A = mf._day({**fl, 12: (100, 102.5, 100, 102.4)})
    r, u, b, how = trade_px(A, 1, 10, 99.25, 102.25); ok(r, ex_trade(A, 10, 1, 1.0)[0]); assert how == "tgt" and b == 12
    A = mf._day({**fl, 11: (100, 100.3, 99.0, 100.1)})
    r, u, b, how = trade_px(A, 1, 10, 99.25, 102.25); ok(r, ex_trade(A, 10, 1, 1.0)[0]); assert how == "stop" and b == 11
    # reclaim: level 100.2, stop bar 11; 1m close above at bar 13; 5m close only at bar 14
    A = mf._day({**fl, 13: (100, 100.4, 99.9, 100.3), 14: (100.3, 100.4, 100.1, 100.35)})
    t = dict(side=1, lvl=100.2, xb=11); assert reclaim(A, t, 1) == 14 and reclaim(A, t, 5) == 15
    As = mf._day({**fl, 13: (100, 100.4, 99.9, 99.8)}); ts = dict(side=-1, lvl=99.9, xb=11)
    assert reclaim(As, ts, 1) == 14
    print("TESTS OK")


if __name__ == "__main__":
    test() if len(sys.argv) > 1 and sys.argv[1] == "test" else main()
