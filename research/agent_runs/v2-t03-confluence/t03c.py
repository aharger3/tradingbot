# v2-t03-confluence: ORB+OCR confluence vs ORB alone vs OCR alone, + 84% re-entry, ES/NQ 1m sized MES/MNQ.
# Honest fills via t02 bt conventions: entry next 1m open +1 tick, stop-market -1 tick (gap->open), target trade-through 1 tick,
# stop-first on same bar, flat 11:00 open -1 tick, $1.24 RT/micro, $200 risk, cap 50.
import sys, math, json
from pathlib import Path
import numpy as np
T02 = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t02-break-retest")
sys.path.insert(0, str(T02))
import bt
from bt import TICK, V, COMM, RISK, MAXN, SLIP, FLOOR_PCT, SPLIT
HERE = Path(__file__).parent
K = 2.0

def avg_rng(h, l, i):
    w0 = max(0, i - 9); return float(np.mean(h[w0:i + 1] - l[w0:i + 1])) or TICK

def ema(x, n):
    a = 2 / (n + 1); out = np.empty(len(x)); out[0] = x[0]
    for i in range(1, len(x)): out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out

def orb_sigs(S, cut):
    """t02 bt.signals('OR') logic with a signal-time cutoff param. returns (i,d,L,ri,far) ; far = level (for LVL stop)"""
    tod, o, h, l, c = S["tod"], S["o"], S["h"], S["l"], S["c"]
    last = int(np.searchsorted(tod, cut, side="right")); out = []
    for L, d in ((h[:5].max(), 1), (l[:5].min(), -1)):
        st, bi, ri = "break", None, None
        for i in range(5, last):
            pc = c[i - 1]; avg = avg_rng(h, l, i); eps = 0.10 * avg; rtol = 0.25 * (h[i - 1] - l[i - 1])
            ci, li, oi = c[i] * d, (l[i] if d == 1 else -h[i]), o[i] * d; Ld = L * d
            if st == "break":
                if pc * d <= Ld and ci > Ld + eps: st, bi = "leave", i
            elif st == "leave":
                if li > Ld + eps: st = "retest"
                elif ci <= Ld + eps: st = "break"
                if st == "leave" and i - bi > 10: st = "break"
            elif st in ("retest", "hold"):
                if st == "retest" and i - bi > 10: st = "break"; continue
                if li <= Ld + rtol: ri, st = i, "hold"
                if st == "hold":
                    if ci < Ld or i - ri > 3: st = "break"; continue
                    body = abs(c[i] - o[i]); adv = (h[i] - max(o[i], c[i])) if d == 1 else (min(o[i], c[i]) - l[i])
                    if ci > Ld and ci > oi and adv <= 1.5 * body:
                        out.append(dict(i=i, d=d, L=L, far=L, bi=bi, ri=ri, kind="ORB")); break
    return sorted(out, key=lambda s: s["i"])

def ocr_sigs(S, cut):
    """One-candle rule: long = down-close candle while EMA9>EMA20; close above its high by >10% avg (break), price leaves,
    retest into block (low <= top + tol) within 10 bars, no close below block low, confirm bar <=3 bars: up candle closing above top."""
    tod, o, h, l, c = S["tod"], S["o"], S["h"], S["l"], S["c"]
    e9, e20 = ema(c, 9), ema(c, 20)
    last = int(np.searchsorted(tod, cut, side="right")); out = []
    for d in (1, -1):
        st = "idle"; top = bot = None; bi = ri = None; dep = 0.0
        for i in range(1, last):
            avg = avg_rng(h, l, i); eps = 0.10 * avg; rtol = 0.25 * (h[i - 1] - l[i - 1])
            ci, li, oi = c[i] * d, (l[i] if d == 1 else -h[i]), o[i] * d
            if st in ("idle", "wait"):
                if st == "wait" and ci > top + eps: st, bi = "leave", i; continue
                if st == "wait" and i - kb > 30: st = "idle"
                if (c[i] - o[i]) * d < 0 and (e9[i] - e20[i]) * d > 0 and h[i] > l[i]:
                    st = "wait"; top, bot = (h[i], l[i]) if d == 1 else (-l[i], -h[i]); kb = i
                continue
            if st == "leave":
                if li > top + eps: st = "retest"
                elif ci <= top + eps: st = "wait"
                if st == "leave" and i - bi > 10: st = "idle"
                continue
            if st in ("retest", "hold"):
                if st == "retest" and i - bi > 10: st = "idle"; continue
                if li <= top + rtol:
                    if st == "retest": dep = 0.0
                    st = "hold"; ri = i
                    dep = max(dep, (top - li) / max(top - bot, TICK))
                if st == "hold":
                    if ci < bot: st = "idle"; continue
                    if i - ri > 3: st = "idle"; continue
                    body = abs(c[i] - o[i]); adv = (h[i] - max(o[i], c[i])) if d == 1 else (min(o[i], c[i]) - l[i])
                    if ci > top and ci > oi and adv <= 1.5 * body:
                        out.append(dict(i=i, d=d, L=top * d, far=bot * d, bi=bi, ri=ri, kind="OCR", depth=dep, kb=kb)); break
    return sorted(out, key=lambda s: s["i"])

def ocr_proxy(S, sig):   # s05 proxy: last opposite-colour candle in 10 bars before break spans the level +-25%
    o, h, l, c = S["o"], S["h"], S["l"], S["c"]; d, L, bi = sig["d"], sig["L"], sig["bi"]
    for k in range(bi - 1, max(-1, bi - 11), -1):
        if (c[k] - o[k]) * d < 0:
            tol = 0.25 * (h[k] - l[k]); return bool(h[k] + tol >= L >= l[k] - tol)
    return False

def sim(S, j, d, stop, tgt, root, dist, rcut=660):
    tod, o, h, l = S["tod"], S["o"], S["h"], S["l"]
    fill = o[j] + d * SLIP
    n = min(MAXN, int(RISK // (dist * V[root] + COMM)))
    if n == 0: return None
    for b in range(j, len(o)):
        if tod[b] >= 660: ex = o[b] - d * SLIP; why = "time"; break
        lo, hi = (l[b], h[b]) if d == 1 else (-h[b], -l[b])
        if lo <= stop * d: ex = d * min(stop * d, o[b] * d) - d * SLIP; why = "stop"; break
        if hi >= tgt * d + TICK: ex = d * max(tgt * d, o[b] * d); why = "tgt"; break
    else: return None
    usd = n * ((ex - fill) * d * V[root] - COMM)
    return dict(usd=usd, R=usd / (n * dist * V[root]), why=why, xb=b, fill=fill)

def trade(S, sig, stopmode, root):
    i, d = sig["i"], sig["d"]; j = i + 1
    if j >= len(S["o"]) or S["tod"][j] >= 660: return None
    fill = S["o"][j] + d * SLIP; avg = avg_rng(S["h"], S["l"], i)
    if stopmode == "LVL":
        stop = sig["L"] - d * max(TICK, math.ceil(0.25 * avg / TICK) * TICK)
    else:  # FAR: OCR block far edge (ORB: OR opposite? no -> use the confluence block if present) -1 tick
        stop = sig["far"] - d * TICK
    dist = (fill - stop) * d
    if dist <= 0: return None
    fl = math.ceil(FLOOR_PCT * fill / TICK) * TICK
    if dist < fl: dist = fl; stop = fill - d * dist
    tgt = fill + d * K * dist
    r = sim(S, j, d, stop, tgt, root, dist)
    if r: r.update(stop=stop, tgt=tgt, dist=dist, j=j, d=d, t=int(S["tod"][i]))
    return r

def r84(S, t, root, rcut=660):
    """Scarface/Austin 84%: after a stop-out, a TREND-coloured bar closes at/beyond original fill within 0.25x prev range -> re-enter
    next open +1 tick, same stop/target, <=2 attempts, reclaim before rcut."""
    tod, o, h, l, c = S["tod"], S["o"], S["h"], S["l"], S["c"]; d = t["d"]; fill = t["fill"]
    out = []; b = t["xb"] + 1; att = 0
    while att < 2 and b < len(o) - 1 and tod[b] < rcut:
        ok = c[b] * d >= fill * d and abs(c[b] - fill) <= 0.25 * (h[b - 1] - l[b - 1]) and (c[b] - o[b]) * d > 0
        if ok:
            dist = (o[b + 1] + d * SLIP - t["stop"]) * d
            if dist <= 0 or (t["tgt"] - o[b + 1]) * d <= 0: break
            r = sim(S, b + 1, d, t["stop"], t["tgt"], root, dist)
            if r is None: break
            att += 1; out.append(r)
            if r["why"] != "stop": break
            b = r["xb"] + 1; continue
        b += 1
    return out

def dayshuffle(SESS, rows, nsh=200, seed=3):
    """same root, same entry bar index, side, stop distance & 2R target on a random other session; null mean R."""
    rng = np.random.default_rng(seed); keys = {r: sorted(SESS[r]) for r in SESS}; means = []
    for _ in range(nsh):
        Rs = []
        for x in rows:
            D2 = keys[x["root"]][rng.integers(len(keys[x["root"]]))]; S2 = SESS[x["root"]][D2]
            j = x["j"]
            if j >= len(S2["o"]) - 1: continue
            f = S2["o"][j] + x["d"] * SLIP; st = f - x["d"] * x["dist"]; tg = f + x["d"] * K * x["dist"]
            r = sim(S2, j, x["d"], st, tg, x["root"], x["dist"])
            if r: Rs.append(r["R"])
        means.append(np.mean(Rs))
    return np.array(means)

def summ(rows, dates, SESS=None, null=False):
    if not rows: return dict(n=0)
    daily = {}
    for r in rows: daily[r["D"]] = daily.get(r["D"], 0) + r["usd"]
    st = bt.stats(daily, dates); R = np.array([r["R"] for r in rows])
    h1 = [r["R"] for r in rows if r["D"] < SPLIT]; h2 = [r["R"] for r in rows if r["D"] >= SPLIT]
    o = dict(n=len(rows), win=round(float((R > 0).mean()), 3), R=round(float(R.mean()), 3), t=round(float(R.mean() / (R.std(ddof=1) / math.sqrt(len(R)))), 2) if len(R) > 2 else 0,
             h1R=round(float(np.mean(h1 or [0])), 3), n1=len(h1), h2R=round(float(np.mean(h2 or [0])), 3), n2=len(h2),
             usd_day=round(st["per_day"], 2), green=f'{st["green"]}/{st["months"]}', p=round(st["p"], 3))
    if null and SESS is not None:
        base = [r for r in rows if r.get("j") is not None]
        m = dayshuffle(SESS, base); o["null_mean"] = round(float(m.mean()), 3); o["null_p"] = round(float((m >= R.mean()).mean()), 3)
    return o

def perm_diff(a, b, n=5000, seed=5):
    ra = np.array([x["R"] for x in a]); rb = np.array([x["R"] for x in b])
    if len(ra) < 3 or len(rb) < 3: return None
    obs = ra.mean() - rb.mean(); allr = np.concatenate([ra, rb]); rng = np.random.default_rng(seed); c = 0
    for _ in range(n):
        rng.shuffle(allr); c += (allr[:len(ra)].mean() - allr[len(ra):].mean()) >= obs
    return round(float(obs), 3), round(c / n, 3)

SESS = {r: bt.sessions(r) for r in ("ES", "NQ")}
print("sessions", {r: len(SESS[r]) for r in SESS}, flush=True)
res = {}; ledger = []
for cut in (630, 645, 660):
    B = {}
    for root in ("ES", "NQ"):
        for D, S in SESS[root].items():
            osg = orb_sigs(S, cut); csg = ocr_sigs(S, cut)
            def near(s, pool): return any(p["d"] == s["d"] and abs(p["i"] - s["i"]) <= 3 for p in pool)
            def add(arm, sig, stopmode):
                t = trade(S, sig, stopmode, root)
                if t is None: return
                row = dict(D=D, root=root, arm=arm, stop=stopmode, R=t["R"], usd=t["usd"], why=t["why"], j=t["j"], d=t["d"], dist=t["dist"], t=t["t"], kind="orig")
                B.setdefault((arm, stopmode), []).append(row)
                if t["why"] == "stop":
                    for rr in r84(S, t, root):
                        B.setdefault((arm + "+84re", stopmode), []).append(dict(D=D, root=root, R=rr["R"], usd=rr["usd"], why=rr["why"], kind="r84"))
                if cut == 645 and stopmode == "LVL": ledger.append(dict(cut=cut, **{k: row[k] for k in ("D", "root", "arm", "R", "why", "t", "d")}))
            if osg:
                s = osg[0]; px = ocr_proxy(S, s); st = near(s, csg)
                if st:  # strict confluence: attach OCR block far edge for block stop
                    blk = min((p for p in csg if p["d"] == s["d"] and abs(p["i"] - s["i"]) <= 3), key=lambda p: abs(p["i"] - s["i"]))
                    s = dict(s, far=blk["far"] if (blk["far"] - s["L"]) * s["d"] < 0 else s["L"])
                for sm in ("LVL", "FAR"):
                    add("ORB_all", s, sm)
                    add("ORB+OCRproxy" if px else "ORB_noOCRproxy", s, sm)
                    add("ORB+OCRstrict" if st else "ORB_noOCRstrict", s, sm)
                    if st and px: add("ORB+OCRboth", s, sm)
            if csg:
                s = csg[0]
                for sm in ("LVL", "FAR"):
                    add("OCR_all", s, sm)
                    add("OCR_alone" if not near(s, osg) else "OCR_withORB", s, sm)
                    add("OCR_shallow" if s["depth"] <= 0.5 else "OCR_deep", s, sm)
    for (arm, sm), rows in sorted(B.items()):
        for inst in ("ES", "NQ", "BOTH"):
            rs = [r for r in rows if inst == "BOTH" or r["root"] == inst]
            dates = sorted(set(SESS["ES"]) | set(SESS["NQ"])) if inst == "BOTH" else sorted(SESS[inst])
            key = f"{cut}|{arm}|{sm}|{inst}"
            nul = (cut == 645 and sm == "LVL" and inst != "BOTH" and "84" not in arm and arm in ("ORB_all", "ORB+OCRproxy", "ORB+OCRstrict", "OCR_alone", "OCR_all", "ORB+OCRboth"))
            res[key] = summ(rs, dates, SESS, null=nul)
            print(key, json.dumps(res[key]), flush=True)
    for sm in ("LVL", "FAR"):
        for inst in ("ES", "NQ", "BOTH"):
            f = lambda a: [r for r in B.get((a, sm), []) if inst == "BOTH" or r["root"] == inst]
            for c_, n_ in (("ORB+OCRproxy", "ORB_noOCRproxy"), ("ORB+OCRstrict", "ORB_noOCRstrict"), ("ORB+OCRstrict", "OCR_alone")):
                res[f"{cut}|DIFF {c_} - {n_}|{sm}|{inst}"] = perm_diff(f(c_), f(n_))
                print(f"{cut}|DIFF {c_} - {n_}|{sm}|{inst}", res[f"{cut}|DIFF {c_} - {n_}|{sm}|{inst}"], flush=True)
json.dump(res, open(HERE / "results.json", "w"), indent=1)
import csv
with open(HERE / "ledger_645_LVL.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(ledger[0].keys())); w.writeheader(); w.writerows(ledger)
print("DONE")
