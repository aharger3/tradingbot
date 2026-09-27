# v3-t-ym-rty: mantra(=orb1m OR5 D1 strong) + a2 S-detector on MYM/M2K, flat 2R vs 4-tier 30/30/30/10+BE. Paper only.
import sys, json, math
from pathlib import Path
import numpy as np, pandas as pd
RUNS = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs")
sys.path.insert(0, str(RUNS / "v2-signal")); sys.path.insert(0, str(RUNS / "v2-t01-orb-1m")); sys.path.insert(0, str(RUNS / "v2-t10-other-indices"))
sys.path.insert(0, str(RUNS.parent))
import orb1m, t10
SPEC = t10.SPEC; COMM = 1.24; RNG = np.random.default_rng(3); NSH = 100
OUT = {}
# ---- part A: v2-t10 trade files (full 501 sessions, bars no longer on disk) ----
res10 = {(r["sym"], r["cut"]): r for r in json.load(open(RUNS / "v2-t10-other-indices" / "results.json"))}
def stats(T, sess, split="2025-09-26"):
    R = np.array([t["R"] for t in T]); n = len(R)
    yr = {y: (round(float(R[[t["date"][:4] == y for t in T]].mean()), 3) if any(t["date"][:4] == y for t in T) else None, sum(t["date"][:4] == y for t in T)) for y in ("2024", "2025", "2026")}
    isr = [t["R"] for t in T if t["date"] < split]; oos = [t["R"] for t in T if t["date"] >= split]
    return dict(n=n, win=round(float((R > 0).mean()), 3), R=round(float(R.mean()), 3), IS=(round(float(np.mean(isr)), 3), len(isr)), OOS=(round(float(np.mean(oos)), 3) if oos else None, len(oos)), yr=yr, day200=round(float(R.sum() * 200 / sess), 2))
for s in ("MNQ", "MYM", "M2K"):
    for c in ("1030", "1045", "1100"):
        T = json.load(open(RUNS / "v2-t10-other-indices" / f"trades_{s}_{c}.json"))
        r10 = res10[(s, c[:2] + ":" + c[2:])]; st = stats(T, r10["sessions"]); st.update(h1=r10["h1"], h2=r10["h2"], p=r10["p"])
        OUT[f"A|{s}|mantra|{c}|2R"] = st; print(f"A|{s}|{c}", json.dumps(st), flush=True)
# ---- part B: bars still on disk (YM/RTY partial) ----
def load(root):
    d = t10.load_root(root)
    return [(dt, orb1m.day_arrays(g)) for dt, g in d.groupby("date")]
def a2sig(A, cut, tick):
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    if np.isnan(H[:5]).all(): return []
    lv = {1: np.nanmax(H[:5]), -1: np.nanmin(L[:5])}; rngs = H - L; st = {1: None, -1: None}; out = []; done = set()
    for j in range(5, cut - 1):
        if np.isnan(C[j]): continue
        prev = rngs[max(0, j - 14):j]; atr = np.nanmean(prev) if np.sum(~np.isnan(prev)) >= 3 else np.nan
        for sd in (1, -1):
            if sd in done: continue
            l = lv[sd]; s = st[sd]
            if s is None:
                if (C[j] - l) * sd > 0: st[sd] = [j, (H[j] - l) if sd > 0 else (l - L[j])]
                continue
            if (C[j] - l) * sd <= 0: st[sd] = None; continue
            touch = (L[j] <= l) if sd > 0 else (H[j] >= l)
            if touch and j > s[0] and not np.isnan(atr) and s[1] >= 0.5 * atr and not np.isnan(O[j + 1]):
                stop = (L[j] - tick) if sd > 0 else (H[j] + tick); out.append((j + 1, sd, stop)); done.add(sd); continue
            s[1] = max(s[1], (H[j] - l) if sd > 0 else (l - L[j]))
    return out
def ladder(A, i, side, dist, cut, tick, usd, n):
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]; e = O[i] + tick * side
    Rp = lambda px: (px - e) * side / dist
    ext = np.nanmax(H[:i]) if side > 0 else np.nanmin(L[:i]); pt1 = Rp(ext)
    named = sorted(Rp(v) for v in (np.nanmax(H[:5]), np.nanmin(L[:5])))
    c = []
    if pt1 >= 0.2: c.append([pt1, .3, "PT1"])
    bey = [x for x in named if x > max(pt1, .2)]
    if bey: c.append([bey[0], .3, "PT2"])
    c.append([2.0, .3, "PT3"]); c.append([4.0, .1, "PT4"]); c.sort(); rs = []
    for x in c:
        if rs and x[0] - rs[-1][0] < .2: continue
        rs.append(x)
    sw = sum(x[1] for x in rs)
    if n >= len(rs):
        raw = [x[1] / sw * n for x in rs]; q = [int(v) for v in raw]
        for k in sorted(range(len(rs)), key=lambda k: -(raw[k] - q[k]))[: n - sum(q)]: q[k] += 1
        for k in range(len(q)):
            if q[k] == 0: b = int(np.argmax(q)); q[b] -= 1; q[k] += 1
        legs = [[e + side * rs[k][0] * dist, q[k]] for k in range(len(rs)) if q[k] > 0]; coll = False
    else:
        pri = {nm: r for r, w, nm in rs}; keep = [pri[p] for p in ("PT3", "PT1", "PT4", "PT2") if p in pri][:n]
        legs = [[e + side * r * dist, 1] for r in keep]; coll = True
    stop = e - side * dist; pnl = 0.0; be = False
    for b in range(i, 91):
        if not legs: break
        rem = sum(q for _, q in legs)
        if b >= cut:
            px = O[b] if not np.isnan(O[b]) else C[:b][~np.isnan(C[:b])][-1]
            pnl += rem * (px - tick * side - e) * side; legs = []; break
        if np.isnan(O[b]): continue
        if (L[b] <= stop) if side > 0 else (H[b] >= stop):
            px = (min(stop, O[b]) - tick) if side > 0 else (max(stop, O[b]) + tick); pnl += rem * (px - e) * side; legs = []; break
        for lg in legs:
            if (H[b] >= lg[0] + tick) if side > 0 else (L[b] <= lg[0] - tick):
                pnl += lg[1] * (lg[0] - e) * side; lg[1] = 0; be = True
        legs = [x for x in legs if x[1] > 0]; rem = sum(q for _, q in legs)
        if rem and be and (C[b] - e) * side <= 0:
            pnl += rem * max((C[b] - e) * side - tick, -dist); legs = []; break
    u = pnl * usd - n * COMM
    return u / (n * dist * usd), u, coll
def trade(A, i, side, dist, cut, sym, ex):
    sp = SPEC[sym]; n = min(50, int(200 // (dist * sp["usd"] + COMM)))
    if n < 1: return None
    if ex == "2R":
        orb1m.TICK = sp["tick"]; r, u1 = orb1m.run_trade(A, i, side, dist, cut, sp["usd"], COMM); return r, u1 * n, False
    return ladder(A, i, side, dist, cut, sp["tick"], sp["usd"], n)
for sym, root in (("MYM", "YM"), ("M2K", "RTY")):
    days = load(root); dates = [str(d) for d, _ in days]; sp = SPEC[sym]
    print(sym, "sessions", len(days), dates[0], dates[-1], flush=True)
    for setup in ("mantra", "a2"):
        for cn in ("10:30", "10:45", "11:00"):
            cut = orb1m.CUTS[cn]; orb1m.TICK = sp["tick"]; sigs = []
            for d, A in days:
                ss = ([orb1m.signal(A, 5, cut, 1.0, "strong")] if setup == "mantra" else a2sig(A, cut, sp["tick"]))
                for s in ss:
                    if not s: continue
                    i, side, stop = s; e = A["open"][i] + sp["tick"] * side; dist = (e - stop) * side
                    if dist >= 2 * sp["tick"]: sigs.append((str(d), A, i, side, dist))
            for ex in ("2R", "4tier"):
                T = []; daily = {}
                for d, A, i, side, dist in sigs:
                    r = trade(A, i, side, dist, cut, sym, ex)
                    if r: T.append(dict(date=d, R=r[0], usd=r[1], coll=r[2], i=i, side=side, dist=dist)); daily[d] = daily.get(d, 0) + r[1]
                if not T: continue
                st = stats(T, len(days)); mid = dates[len(dates) // 2]; R = np.array([t["R"] for t in T])
                st["h1"] = round(float(R[[t["date"] < mid for t in T]].mean()), 3); st["h2"] = round(float(R[[t["date"] >= mid for t in T]].mean()), 3)
                st["usd_day"] = round(sum(daily.values()) / len(days), 2); st["coll"] = round(float(np.mean([t["coll"] for t in T])), 2)
                sh = []
                for _ in range(NSH):
                    rr = []
                    for t in T:
                        for _k in range(50):
                            k = RNG.integers(len(days))
                            if dates[k] != t["date"] and not np.isnan(days[k][1]["open"][t["i"]]): break
                        x = trade(days[k][1], t["i"], t["side"], t["dist"], cut, sym, ex)
                        if x: rr.append(x[0])
                    sh.append(np.mean(rr))
                st["p"] = round(max(float((np.array(sh) >= R.mean()).mean()), 1 / NSH), 3); st["sessions"] = len(days)
                eq = np.cumsum([daily.get(d, 0) for d in dates]); st["maxdd"] = round(float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()), 0)
                key = f"B|{sym}|{setup}|{cn}|{ex}"; OUT[key] = st; OUT[key + "|daily"] = [(d, daily.get(d, 0.0)) for d in dates if d in daily]
                print(key, json.dumps(st), flush=True)
json.dump(OUT, open("out.json", "w"), default=float)
print("DONE", flush=True)
