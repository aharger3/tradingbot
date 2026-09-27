"""v2-t05: S-filter on ES/NQ ORB(+OCR) retest candidates. Paper research only."""
import sys, json, random, math, collections as C
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
from omen_data import load_fut, sessions, SPEC
random.seed(7)
TK = 0.25; SPLIT = "2025-09-26"
OUT = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-t05-s-filter"

def mins(ts): return ts.hour*60+ts.minute-570  # minutes after 09:30

def sim(b, i, side, entry_i, stop, tgt_R, usd, comm):
    """entry at open of bar entry_i +1 tick adverse; stop-market; 2R limit needs 1 tick through; flat 11:00 open."""
    n = len(b)
    if entry_i >= n: return None
    e = b.open[entry_i] + side*TK
    risk = (e - stop)*side
    if risk <= 0: return None
    tgt = e + side*tgt_R*risk
    for j in range(entry_i, n):
        if mins(b.ts[j]) >= 90:
            x = b.open[j] - side*TK; break
        hi, lo, op = b.high[j], b.low[j], b.open[j]
        if (side == 1 and lo <= stop) or (side == -1 and hi >= stop):
            x = (min(stop, op) if side == 1 else max(stop, op)) - side*TK; break
        if (side == 1 and hi >= tgt + TK) or (side == -1 and lo <= tgt - TK):
            x = tgt; break
    else:
        x = b.close[n-1] - side*TK
    pts = (x - e)*side
    return (pts*usd - comm)/(risk*usd), risk, (x - e)*side/risk

def cands(sym, cutoff):
    sp = SPEC[sym]; usd, comm = sp["usd_pt"], sp["rt_comm"]
    df = load_fut(sym, "09:30", "11:01")
    out = []
    for d, g in sessions(df).items():
        b = g; n = len(b)
        b = b.assign(ts=b.ts)  # keep

        if n < 30: continue
        orb = b[b.ts.dt.strftime("%H:%M") < "09:35"]
        if len(orb) < 4: continue
        ORH, ORL = orb.high.max(), orb.low.min()
        start = len(orb)
        rng = (b.high - b.low).tolist()
        for side, L in ((1, ORH), (-1, ORL)):
            first_brk = None; brk = None; closed_thru = False; fired = False; left = False
            for i in range(start, n):
                t = mins(b.ts[i])
                if t >= cutoff: break
                atr = sum(rng[max(0, i-14):i])/max(1, len(rng[max(0, i-14):i]))
                c, o, h, l = b.close[i], b.open[i], b.high[i], b.low[i]
                beyond = (c - L)*side > 0
                if brk is None:
                    if beyond:
                        brk = i; left = False
                        if first_brk is None: first_brk = i
                    continue
                if not beyond:  # close back through: reset break
                    closed_thru = True; brk = None; continue
                if i == brk: continue
                ext = (l - L) if side == 1 else (L - h)   # how far the retest wick stays beyond level
                if ext > 0.25*atr:
                    left = True; continue              # price has left the level
                if not left: continue                  # still hugging the level: not a retest
                # candidate: bar i retested (wick within 0.25 ATR or through) and closed beyond level
                seg = b.iloc[brk:i]
                disp = ((seg.high.max() - L) if side == 1 else (L - seg.low.min()))/atr if atr > 0 else 0
                touch = ext <= TK   # wick touched/pierced (within 1 tick)
                r = h - l; body = abs(c - o)
                wick = (min(o, c) - l) if side == 1 else (h - max(o, c))
                cpos = ((c - l)/r if side == 1 else (h - c)/r) if r > 0 else 0
                if r > 0 and wick >= 0.5*r and cpos >= 0.6: trig = "hammer/pin"
                elif r > 0 and body >= 0.6*r and (c - o)*side > 0: trig = "strong-body"
                elif (c - o)*side < 0: trig = "against"
                else: trig = "normal"
                # OCR block: last opposite-colour candle before the break bar (within 10 bars)
                ocr = None
                for k in range(brk, max(-1, brk-11), -1):
                    if (b.close[k] - b.open[k])*side < 0: ocr = k; break
                ocr_hit = False; ocr_depth = None
                if ocr is not None:
                    bh, bl = b.high[ocr], b.low[ocr]
                    top, bot = (bh, bl) if side == 1 else (bl, bh)
                    wk = l if side == 1 else h
                    inside = (wk - top)*side <= 0 and (c - bot)*side > 0
                    if inside and abs(top - bot) > 0:
                        ocr_hit = True; ocr_depth = (top - wk)*side/abs(top - bot)  # 0 = top of block
                stop = (l if side == 1 else h) - side*TK
                minstop = max(4*TK, 0.0004*c)
                e0 = b.open[i+1] + side*TK if i+1 < n else None
                if e0 is None: break
                if (e0 - stop)*side < minstop: stop = e0 - side*minstop
                res = sim(b, i, side, i+1, stop, 2.0, usd, comm)
                if res is None: break
                R, risk, G = res
                out.append(dict(sym=sym, day=str(d), t=t, side=side, disp=round(float(disp), 3), touch=bool(touch),
                                ct=bool(closed_thru), trig=trig, ocr=bool(ocr_hit), ocr_depth=None if ocr_depth is None else float(ocr_depth),
                                R=round(float(R), 4), G=round(float(G), 4), risk=float(risk), sig=int(t)))
                fired = True; break
    return out

def mean(x): return sum(x)/len(x) if x else float("nan")

def stats(rows):
    Rs = [r["R"] for r in rows]
    h1 = [r["R"] for r in rows if r["day"] < SPLIT]; h2 = [r["R"] for r in rows if r["day"] >= SPLIT]
    return len(Rs), (sum(x > 0 for x in Rs)/len(Rs) if Rs else float("nan")), mean(Rs), len(h1), mean(h1), len(h2), mean(h2)

def p_label(rows, f, N=5000):
    """time-matched label permutation: draw same count from same 15-min bucket, same sym; p that null mean >= obs"""
    sel = [r for r in rows if f(r)]
    if not sel: return float("nan"), float("nan")
    pool = C.defaultdict(list)
    for r in rows: pool[(r["sym"], r["t"]//15)].append(r["R"])
    obs = mean([r["R"] for r in sel]); keys = [(r["sym"], r["t"]//15) for r in sel]
    nulls = [mean([random.choice(pool[k]) for k in keys]) for _ in range(N)]
    return mean(nulls), (1 + sum(x >= obs for x in nulls))/(N + 1)

def p_signflip(rows, N=5000):
    """day-level sign flip of summed R: p that mean > 0 by chance"""
    byd = C.defaultdict(float)
    for r in rows: byd[r["day"]] += r["R"]
    v = list(byd.values()); obs = mean(v)
    if not v: return float("nan")
    c = sum(1 for _ in range(N) if mean([x*random.choice((1, -1)) for x in v]) >= obs)
    return (1 + c)/(N + 1)

def p_dayshuffle(rows, f, N=5000):
    """day-shuffle: permute S flag across days (keep each day's candidate set), compare S-minus-rest."""
    sel = [r["R"] for r in rows if f(r)]; rest = [r["R"] for r in rows if not f(r)]
    if not sel or not rest: return float("nan")
    obs = mean(sel) - mean(rest)
    days = sorted({r["day"] for r in rows}); byd = C.defaultdict(list)
    for r in rows: byd[r["day"]].append(r)
    flags = {d: [f(r) for r in byd[d]] for d in days}
    cnt = 0
    for _ in range(N):
        perm = days[:]; random.shuffle(perm)
        s, o = [], []
        for d, d2 in zip(days, perm):
            fl = flags[d2]
            for k, r in enumerate(byd[d]):
                (s if (fl[k % len(fl)] if fl else False) else o).append(r["R"])
        if s and o and mean(s) - mean(o) >= obs: cnt += 1
    return (1 + cnt)/(N + 1)

T = lambda r: r["t"] <= 30
D = lambda r: r["disp"] >= 1.0
W = lambda r: r["touch"] and not r["ct"]
P = lambda r: r["trig"] in ("hammer/pin", "strong-body")
S = lambda r: T(r) and D(r) and W(r) and P(r)
RULES = [("base (all ORB retest candidates)", lambda r: True), ("T <=30 min", T), ("D disp >=1 ATR", D),
         ("W wick-touch, no close thru", W), ("P hammer/pin or strong-body", P), ("OCR confluence", lambda r: r["ocr"]),
         ("S = T+D+W+P", S), ("S minus T", lambda r: D(r) and W(r) and P(r)),
         ("S + OCR", lambda r: S(r) and r["ocr"]), ("S + OCR top half of block", lambda r: S(r) and r["ocr"] and r["ocr_depth"] is not None and r["ocr_depth"] <= 0.5),
         ("not S", lambda r: not S(r))]

if __name__ == "__main__":
    res = {}
    for cutoff, lab in ((60, "10:30"), (75, "10:45"), (90, "11:00")):
        rows = cands("MES", cutoff) + cands("MNQ", cutoff)
        json.dump(rows, open(f"{OUT}\\cands_{lab.replace(':','')}.json", "w"))
        print(f"\n== signal cutoff {lab}, flat 11:00, n candidates {len(rows)} ==")
        print("rule|n|win|meanR|grossR|med risk ES/NQ pts|H1 n|H1 R|H2 n|H2 R|ES n/R|NQ n/R|null R|p_time|p_day|p_signflip")
        for name, f in RULES:
            sel = [r for r in rows if f(r)]
            n, w, m, n1, m1, n2, m2 = stats(sel)
            es = [r["R"] for r in sel if r["sym"] == "MES"]; nq = [r["R"] for r in sel if r["sym"] == "MNQ"]
            if name.startswith("base") or name == "not S":
                nl, pt, pd_ = float("nan"), float("nan"), float("nan")
            else:
                nl, pt = p_label(rows, f, 1000 if cutoff != 75 else 5000); pd_ = p_dayshuffle(rows, f, 300 if cutoff != 75 else 2000)
            ps = p_signflip(sel, 2000)
            import statistics as st
            ge = mean([r["G"] for r in sel]); rke = st.median([r["risk"] for r in sel if r["sym"]=="MES"] or [0]); rkn = st.median([r["risk"] for r in sel if r["sym"]=="MNQ"] or [0])
            print(f"{name}|{n}|{w:.3f}|{m:+.3f}|{ge:+.3f}|{rke:.2f}/{rkn:.2f}|{n1}|{m1:+.3f}|{n2}|{m2:+.3f}|{len(es)}/{mean(es):+.3f}|{len(nq)}/{mean(nq):+.3f}|{nl:+.3f}|{pt:.4f}|{pd_:.4f}|{ps:.4f}")
    # his S marks on SPY->ES, QQQ->NQ: does the futures S filter fire on that day/side?
    M = json.load(open(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s01-s-trades\s_rows.json"))
    rows = json.load(open(f"{OUT}\\cands_1100.json"))
    idx = C.defaultdict(list)
    for r in rows: idx[(r["sym"], r["day"], r["side"])].append(r)
    print("\n== his graded SPY/QQQ marks vs futures candidates (same day, same side, any time <11:00) ==")
    print("g|sym|day|et|side|his setup|his R|fut cand t|fut S?|fut R")
    for m in sorted(M, key=lambda m: (m["g"], m["day"])):
        if m["sym"] not in ("SPY", "QQQ"): continue
        fs = "MES" if m["sym"] == "SPY" else "MNQ"; sd = 1 if m["side"] == "L" else -1
        c = idx.get((fs, m["day"], sd), [])
        if c:
            hm = int(m["et"][:2])*60+int(m["et"][3:])-570
            r = min(c, key=lambda r: abs(r["t"]-hm)); print(f"{m['g']}|{m['sym']}|{m['day']}|{m['et']}|{m['side']}|{m['setup']}|{m.get('R')}|{r['t']}|{S(r)}|{r['R']:+.2f}")
        else:
            print(f"{m['g']}|{m['sym']}|{m['day']}|{m['et']}|{m['side']}|{m['setup']}|{m.get('R')}|none|-|-")
