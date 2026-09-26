# v2-s05: 84% rule (Scarface reclaim re-entry) on ES/NQ 1m, ORB break-retest base, vs ORB+OCR confluence.
# Reuses t02 bt.py (honest fills: next open +1 tick, stop-market -1 tick, target trade-through, $1.24 RT/micro).
import sys, math, json
from pathlib import Path
import numpy as np
T02 = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t02-break-retest")
sys.path.insert(0, str(T02))
import bt
from bt import TICK, V, COMM, RISK, MAXN, SLIP, FLOOR_PCT, SPLIT

def run_fixed(S, j, d, stop, tgt, root, cut=660):
    tod, o, h, l = S["tod"], S["o"], S["h"], S["l"]
    if j >= len(o) or tod[j] >= cut: return None
    fill = o[j] + d * SLIP
    dist = (fill - stop) * d
    if dist <= 0 or (tgt - fill) * d <= 0: return None
    n = min(MAXN, int(RISK // (dist * V[root] + COMM)))
    if n == 0: return None
    for b in range(j, len(o)):
        if tod[b] >= 660: ex = o[b] - d * SLIP; why = "time"; break
        lo, hi = (l[b], h[b]) if d == 1 else (-h[b], -l[b])
        if lo <= stop * d: ex = d * min(stop * d, o[b] * d) - d * SLIP; why = "stop"; break
        if hi >= tgt * d + TICK: ex = d * max(tgt * d, o[b] * d); why = "tgt"; break
    else: return None
    usd = n * ((ex - fill) * d * V[root] - COMM)
    return dict(fill=fill, stop=stop, tgt=tgt, dist=dist, n=n, usd=usd, R=usd / (n * dist * V[root]), why=why, xb=b, j=j)

def ocr_conf(S, sig):
    i, d, L, ri, name = sig
    o, h, l, c = S["o"], S["h"], S["l"], S["c"]
    # break bar = first bar in [0,i] closing through L; OCR = last opposite-colour candle in 10 bars before break
    bi = next((k for k in range(5, i + 1) if c[k] * d > L * d), None)
    if bi is None: return False
    for k in range(bi - 1, max(-1, bi - 11), -1):
        if (c[k] - o[k]) * d < 0:   # down-close in up-move (long) / up-close (short)
            tol = 0.25 * (h[k] - l[k])
            return (h[k] + tol >= L >= l[k] - tol)
    return False

def book(SESS, root, K=2.0, cut_sig=630, arm="trend", rcut=660, tolf=0.25):
    rows = []
    for D, S in SESS[root].items():
        sigs = [s for s in bt.signals(S, "OR") if S["tod"][s[0]] <= cut_sig]
        if not sigs: continue
        sig = sigs[0]; i, d, L, ri, name = sig
        t = bt.trade(S, sig, "LVL", K, root)
        if t is None: continue
        j = i + 1; fill = S["o"][j] + d * SLIP
        dist = t["dist"]; stop = fill - d * dist; tgt = fill + d * K * dist
        conf = ocr_conf(S, sig)
        rows.append(dict(D=D, kind="orig", conf=conf, R=t["R"], usd=t["usd"], why=t["why"], t=int(S["tod"][i])))
        if t["why"] != "stop": continue
        # 84% arm: stopped out. Find exit bar, then reclaim close at original entry within tolf*prev range, <= 2 attempts
        tod, o, h, l, c = S["tod"], S["o"], S["h"], S["l"], S["c"]
        xb = next(b for b in range(j, len(o)) if ((l[b] if d == 1 else -h[b]) <= stop * d))
        att = 0; b = xb + 1
        while att < 2 and b < len(o) - 1 and tod[b] < rcut:
            prng = h[b - 1] - l[b - 1]
            ok = c[b] * d >= fill * d - 0 and abs(c[b] - fill) <= tolf * prng
            if arm == "trend": ok = ok and (c[b] - o[b]) * d > 0
            if ok:
                r = run_fixed(S, b + 1, d, stop, tgt, root, cut=rcut)
                if r is None: break
                att += 1
                rows.append(dict(D=D, kind="r84", conf=conf, R=r["R"], usd=r["usd"], why=r["why"], t=int(tod[b])))
                if r["why"] != "stop": break
                b = r["xb"] + 1; continue
            b += 1
    return rows

def summ(rows, dates, sel):
    rs = [r for r in rows if sel(r)]
    if not rs: return dict(n=0)
    daily = {}
    for r in rs: daily[r["D"]] = daily.get(r["D"], 0) + r["usd"]
    st = bt.stats(daily, dates)
    R = np.array([r["R"] for r in rs])
    h1 = [r["R"] for r in rs if r["D"] < SPLIT]; h2 = [r["R"] for r in rs if r["D"] >= SPLIT]
    return dict(n=len(rs), win=round(float((R > 0).mean()), 3), R=round(float(R.mean()), 3), h1R=round(float(np.mean(h1 or [0])), 3),
                h2R=round(float(np.mean(h2 or [0])), 3), n1=len(h1), n2=len(h2), usd_day=round(st["per_day"], 2), green=f'{st["green"]}/{st["months"]}', p=round(st["p"], 3))

SESS = {r: bt.sessions(r) for r in ("ES", "NQ")}
out = {}
for root in ("ES", "NQ"):
    dates = sorted(SESS[root])
    for cut in (630, 645, 660):
        for arm in ("trend", "any"):
            rows = book(SESS, root, cut_sig=cut, arm=arm, rcut=cut)
            key = f"{root}|cut{cut}|{arm}"
            out[key] = {
              "orig": summ(rows, dates, lambda r: r["kind"] == "orig"),
              "r84": summ(rows, dates, lambda r: r["kind"] == "r84"),
              "orig+r84": summ(rows, dates, lambda r: True),
              "orig_conf": summ(rows, dates, lambda r: r["kind"] == "orig" and r["conf"]),
              "orig_noconf": summ(rows, dates, lambda r: r["kind"] == "orig" and not r["conf"]),
              "r84_conf": summ(rows, dates, lambda r: r["kind"] == "r84" and r["conf"]),
            }
            print(key, json.dumps(out[key]), flush=True)
json.dump(out, open(Path(__file__).parent / "results.json", "w"), indent=1)
