"""v2-t02: one-candle rule (OCR) per Austin spec 0926 on 1-min MES/MNQ (real ES/NQ bars). Paper research only.
Long rule (shorts = mirror via price negation):
  uptrend EMA9>EMA20 (EMAs from 09:00), OCR = down-close bar right after an up-close bar, bar open >= 09:31.
  Block = OCR high..low. Break: within 10 bars a close > block high WITH displacement
  (break body >= ATR10, or 2 up-closes whose combined body >= 1.5*ATR10); no close < block low before it.
  Retest: within 15 bars a bar's low enters the block; no close < block low (no close through).
  zone=any: anywhere in block; zone=upper: low must stay >= block mid ("higher in block"), deeper = dead.
  confirm=touch: enter next open after retest bar. confirm=strong: retest bar or one of next 3 is a hammer/pin
  (lower wick>=50% range, close top third) or strong up bar (body>=60% range, close > block high) -> next open.
  orb: OCR bar >= 09:35 and block straddles OR5 high (tol max(2 ticks, 0.1*OR range)).
Fills: entry next-bar open +1 tick; stop = block low -1 tick, fills stop-1tick (or open-1tick on gap);
  target 2R limit, fills only if high >= tgt+1 tick; stop wins same-bar ties; flat 11:00 at 10:59 close -1 tick.
  $1.24 RT/micro. R<1pt skipped. One trade/instrument/day (earliest entry). Entry bar open < cutoff.
"""
import sys, json, math, random
import numpy as np
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
from omen_data import load_fut, SPEC

TICK = 0.25; RISK = 200.0; TGT = 2.0; SPLIT = "2025-09-01"
random.seed(7); np.random.seed(7)

def ema(x, n):
    a = 2 / (n + 1); out = np.empty_like(x); out[0] = x[0]
    for i in range(1, len(x)): out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out

def prep(sym):
    df = load_fut(sym, "09:00", "11:00")
    days = {}
    for d, g in df.groupby("date"):
        mins = (g["ts"].dt.hour * 60 + g["ts"].dt.minute).to_numpy()
        if (mins == 570).sum() == 0: continue
        days[str(d)] = dict(m=mins, o=g.open.to_numpy(float), h=g.high.to_numpy(float),
                            l=g.low.to_numpy(float), c=g.close.to_numpy(float))
    return days

def sim(o, h, l, c, m, ei, stop, tgt):
    """long in transformed space. entry at o[ei]+tick. returns exit price."""
    for k in range(ei, len(o)):
        if m[k] >= 660: return c[k - 1] - TICK
        if o[k] <= stop: return o[k] - TICK
        if l[k] <= stop: return stop - TICK
        if h[k] >= tgt + TICK: return tgt
    return c[-1] - TICK

def detect(o, h, l, c, m, zone, confirm, orb, cutoff):
    n = len(o); e9 = ema(c, 9); e20 = ema(c, 20)
    rng = h - l
    atr = np.array([rng[max(0, i - 10):i].mean() if i > 0 else rng[0] for i in range(n)])
    i930 = np.where(m >= 570)[0][0]
    orw = [k for k in range(i930, n) if m[k] < 575]
    if len(orw) < 3: return []
    orh = max(h[k] for k in orw); orr = orh - min(l[k] for k in orw); tol = max(2 * TICK, 0.1 * orr)
    out = []
    for i in range(max(i930 + 1, 1), n):
        if m[i] < (575 if orb else 571) or m[i] >= cutoff: continue
        if not (c[i] < o[i] and c[i - 1] > o[i - 1] and e9[i] > e20[i]): continue
        bh, bl = h[i], l[i]; bmid = (bh + bl) / 2
        if orb and not (bl - tol <= orh <= bh + tol): continue
        j = None
        for jj in range(i + 1, min(n, i + 11)):
            if c[jj] < bl: break
            if c[jj] > bh:
                d1 = c[jj] - o[jj] >= atr[jj]
                d2 = c[jj] > o[jj] and c[jj - 1] > o[jj - 1] and jj - 1 > i and (c[jj] - o[jj - 1]) >= 1.5 * atr[jj]
                if d1 or d2: j = jj
                break
        if j is None: continue
        ent = None
        for k in range(j + 1, min(n, j + 16)):
            if c[k] < bl: break
            if zone == "upper" and l[k] < bmid: break
            if l[k] <= bh:
                if confirm == "touch":
                    ent = k + 1
                else:
                    for mm in range(k, min(n, k + 4)):
                        if c[mm] < bl or (zone == "upper" and l[mm] < bmid): break
                        r = h[mm] - l[mm]
                        if r <= 0: continue
                        lw = min(o[mm], c[mm]) - l[mm]
                        pin = lw >= 0.5 * r and c[mm] >= l[mm] + 2 * r / 3
                        strong = c[mm] > o[mm] and (c[mm] - o[mm]) >= 0.6 * r and c[mm] > bh
                        if pin or strong: ent = mm + 1; break
                break
        if ent is None or ent >= n or m[ent] >= cutoff: continue
        e = o[ent] + TICK; st = bl - TICK; R = e - st
        if R < 1.0: continue
        out.append((ent, st, R))
    return out

def trades_for(days, sym, zone, confirm, orb, cutoff):
    sp = SPEC[sym]; res = []
    for d, a in days.items():
        best = None
        for side in (1, -1):
            s = side
            o, h, l, c = (a["o"] * s, a["h"], a["l"], a["c"] * s)
            if s == 1: hh, ll = a["h"], a["l"]
            else: hh, ll = -a["l"], -a["h"]
            sig = detect(o, hh, ll, c, a["m"], zone, confirm, orb, cutoff)
            if sig:
                ent, st, R = min(sig)
                if best is None or ent < best[0]: best = (ent, st, R, side, o, hh, ll, c)
        if best is None: continue
        ent, st, R, side, o, hh, ll, c = best
        e = o[ent] + TICK; tgt = e + TGT * R
        x = sim(o, hh, ll, c, a["m"], ent, st, tgt)
        gross = (x - e) / R
        net = gross - sp["rt_comm"] / (sp["usd_pt"] * R)
        grossfrict = (x - e + 2 * TICK) / R  # before both slippage ticks
        nct = min(50, math.floor(RISK / (R * sp["usd_pt"] + sp["rt_comm"])))
        usd = nct * ((x - e) * sp["usd_pt"] - sp["rt_comm"])
        res.append(dict(date=d, sym=sym, side=side, min=int(a["m"][ent]), R=R, net=net, gross0=grossfrict, usd=usd, win=gross > 0))
    return res

def shuffle_null(days_by, trades, reps=200):
    means = []
    for _ in range(reps):
        v = []
        for t in trades:
            days = days_by[t["sym"]]; keys = list(days.keys())
            d = random.choice(keys)
            while d == t["date"]: d = random.choice(keys)
            a = days[d]; idx = np.where(a["m"] == t["min"])[0]
            if len(idx) == 0: continue
            ent = idx[0]; s = t["side"]
            o, c = a["o"] * s, a["c"] * s
            hh, ll = (a["h"], a["l"]) if s == 1 else (-a["l"], -a["h"])
            e = o[ent] + TICK; st = e - t["R"]; tgt = e + TGT * t["R"]
            x = sim(o, hh, ll, c, a["m"], ent, st, tgt)
            sp = SPEC[t["sym"]]
            v.append((x - e) / t["R"] - sp["rt_comm"] / (sp["usd_pt"] * t["R"]))
        means.append(np.mean(v))
    return np.array(means)

def stats(tr, nsess):
    if not tr: return dict(n=0)
    net = np.array([t["net"] for t in tr])
    h1 = np.array([t["net"] for t in tr if t["date"] < SPLIT]); h2 = np.array([t["net"] for t in tr if t["date"] >= SPLIT])
    months = {}
    for t in tr: months[t["date"][:7]] = months.get(t["date"][:7], 0) + t["usd"]
    return dict(n=len(tr), win=round(100 * np.mean([t["win"] for t in tr]), 1),
                gross0=round(float(np.mean([t["gross0"] for t in tr])), 3), net=round(float(net.mean()), 3),
                t=round(float(net.mean() / (net.std(ddof=1) / math.sqrt(len(net)))), 2) if len(net) > 2 else None,
                usd_day=round(sum(t["usd"] for t in tr) / nsess, 1),
                green=f"{sum(v > 0 for v in months.values())}/{len(months)}",
                h1=round(float(h1.mean()), 3) if len(h1) else None, n1=len(h1),
                h2=round(float(h2.mean()), 3) if len(h2) else None, n2=len(h2),
                mes=round(float(np.mean([t["net"] for t in tr if t["sym"] == "MES"] or [np.nan])), 3),
                mnq=round(float(np.mean([t["net"] for t in tr if t["sym"] == "MNQ"] or [np.nan])), 3),
                medR_mes=round(float(np.median([t["R"] for t in tr if t["sym"] == "MES"] or [np.nan])), 2),
                medR_mnq=round(float(np.median([t["R"] for t in tr if t["sym"] == "MNQ"] or [np.nan])), 2))

if __name__ == "__main__":
    days_by = {s: prep(s) for s in ("MES", "MNQ")}
    nsess = len(set(days_by["MES"]) | set(days_by["MNQ"]))
    print("sessions", {s: len(v) for s, v in days_by.items()}, "union", nsess, flush=True)
    grid = []
    for zone in ("any", "upper"):
        for confirm in ("touch", "strong"):
            for cut in (630, 645, 660):
                grid.append((zone, confirm, False, cut))
    for zone in ("any", "upper"):
        for cut in (630, 645, 660):
            grid.append((zone, "strong", True, cut))
    out = []; alltr = {}
    for vi, (zone, confirm, orb, cut) in enumerate(grid, 1):
        tr = trades_for(days_by["MES"], "MES", zone, confirm, orb, cut) + trades_for(days_by["MNQ"], "MNQ", zone, confirm, orb, cut)
        st = stats(tr, nsess)
        if tr:
            nl = shuffle_null(days_by, tr, 200)
            st["null_mean"] = round(float(nl.mean()), 3); st["null_p95"] = round(float(np.percentile(nl, 95)), 3)
            st["null_p"] = round(float((nl >= st["net"]).mean()), 3)
        st.update(v=vi, zone=zone, confirm=confirm, orb=orb, cut=f"{cut//60}:{cut%60:02d}")
        out.append(st); alltr[vi] = tr
        print(json.dumps(st), flush=True)
    json.dump(out, open("t02_ocr1m_result.json", "w"), indent=1)
    import csv
    with open("t02_ocr1m_trades.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["v", "date", "sym", "side", "min", "R", "net", "usd"])
        for vi, tr in alltr.items():
            for t in tr: w.writerow([vi, t["date"], t["sym"], t["side"], t["min"], round(t["R"], 2), round(t["net"], 4), round(t["usd"], 2)])
