"""t06: Scarface's 3 most concrete rules (s02) on real ES/NQ 1-min, honest fills. Paper research only."""
import sys, random, math
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
from omen_data import load_fut, SPEC
import numpy as np, pandas as pd

def prep(sym):
    rth = load_fut(sym, "09:30", "16:00")
    pd_hl = rth.groupby("date").agg(h=("high", "max"), l=("low", "min")).shift(1)
    w = load_fut(sym, "09:30", "11:00")
    days = {}
    for d, g in w.groupby("date"):
        g = g.reset_index(drop=True)
        mins = (g.ts.dt.hour * 60 + g.ts.dt.minute - 570).values
        days[d] = dict(o=g.open.values, h=g.high.values, l=g.low.values, c=g.close.values, m=mins,
                       pdh=pd_hl.h.get(d, np.nan), pdl=pd_hl.l.get(d, np.nan))
    return days

TICK = 0.25

def sim(D, i, side, stop, tgt_R=2.0, cut=None):
    """enter next bar open (+1 tick adverse); hard intrabar stop (-1 tick slip, gap -> open);
    target limit needs trade-through by 1 tick; stop checked first on same bar; flat at 10:59 close -1 tick."""
    o, h, l, c = D["o"], D["h"], D["l"], D["c"]
    j = i + 1
    if j >= len(o):
        return None
    e = o[j] + side * TICK
    risk = (e - stop) * side
    if risk <= 0:
        return None
    t = e + side * tgt_R * risk
    for k in range(j, len(o)):
        if side == 1:
            if l[k] <= stop:
                return e, min(stop, o[k]) - TICK, risk
            if h[k] >= t + TICK:
                return e, t, risk
        else:
            if h[k] >= stop:
                return e, max(stop, o[k]) + TICK, risk
            if l[k] <= t - TICK:
                return e, t, risk
    return e, c[-1] - side * TICK, risk

def strong(o, h, l, c, k, side, frac=0.4):
    rng = h[k] - l[k]
    if rng <= 0:
        return False
    if side == 1:
        return c[k] > o[k] and (min(o[k], c[k]) - l[k]) >= frac * rng
    return c[k] < o[k] and (h[k] - max(o[k], c[k])) >= frac * rng

def levels_orb(D):
    m = D["m"]; f = m < 5
    if f.sum() < 4:
        return None
    return D["h"][f].max(), D["l"][f].min(), int(np.argmax(m >= 5))

def rule_raw(D, cut):
    lv = levels_orb(D)
    if not lv: return None
    H, L, s = lv
    o, h, l, c, m = D["o"], D["h"], D["l"], D["c"], D["m"]
    for k in range(s, len(c) - 1):
        if m[k] >= cut: return None
        if c[k] > H: return k, 1, l[k] - TICK
        if c[k] < L: return k, -1, h[k] + TICK
    return None

def rule_retest(D, cut, lvfn):
    r = lvfn(D)
    if not r: return None
    H, L, s = r
    o, h, l, c, m = D["o"], D["h"], D["l"], D["c"], D["m"]
    tol = 2 * TICK if H - L < 40 else 8 * TICK   # ES ~0.5pt, NQ ~2pt
    side = 0
    for k in range(s, len(c) - 1):
        if m[k] >= cut: return None
        if side == 0:
            if c[k] > H: side, lev, bk = 1, H, k
            elif c[k] < L: side, lev, bk = -1, L, k
            continue
        if k == bk: continue
        if side == 1:
            if c[k] < lev:          # close through -> invalid, reset (can re-break)
                side = 0; continue
            if l[k] <= lev + tol and strong(o, h, l, c, k, 1):
                return k, 1, l[k] - TICK
        else:
            if c[k] > lev:
                side = 0; continue
            if h[k] >= lev - tol and strong(o, h, l, c, k, -1):
                return k, -1, h[k] + TICK
    return None

def lv_pd(D):
    if np.isnan(D["pdh"]): return None
    return D["pdh"], D["pdl"], 1

RULES = {
    "R1 raw 5m ORB break (enter on break close, stop break-candle, 2R)": lambda D, cut: rule_raw(D, cut),
    "R2 5m ORB break+retest+strong candle (2R)": lambda D, cut: rule_retest(D, cut, levels_orb),
    "R3 PDH/PDL break+retest+strong candle (2R)": lambda D, cut: rule_retest(D, cut, lv_pd),
}

def run(days, sym, fn, cut, tgt=2.0):
    sp = SPEC[sym]; out = []
    for d in sorted(days):
        D = days[d]; s = fn(D, cut)
        if not s: continue
        k, side, stop = s
        r = sim(D, k, side, stop, tgt)
        if not r: continue
        e, x, risk = r
        pnl = (x - e) * side * sp["usd_pt"] - sp["rt_comm"]
        out.append(dict(date=d, side=side, k=int(D["m"][k]), riskpt=risk, R=pnl / (risk * sp["usd_pt"]), usd=pnl,
                        gR=(x - e) * side / risk))
    return pd.DataFrame(out)

def stats(t):
    if len(t) == 0: return dict(n=0)
    w = t.R > 0; gp = t.R[w].sum(); gl = -t.R[~w].sum()
    h = len(t) // 2
    return dict(n=len(t), win=round(100 * w.mean(), 1), avgR=round(t.R.mean(), 3), PF=round(gp / gl, 2) if gl else np.inf,
                usd_day=round(t.usd.sum() / 501, 2), h1=round(t.R.iloc[:h].mean(), 3), h2=round(t.R.iloc[h:].mean(), 3),
                t=round(t.R.mean() / (t.R.std(ddof=1) / math.sqrt(len(t))), 2), med_risk=round(t.riskpt.median(), 2))

def shuffle_p(days, sym, t, reps=300, seed=7):
    """day-shuffle: same entry minute, side, stop distance, applied to a random other day. p = P(null mean >= obs)."""
    rng = random.Random(seed); keys = sorted(days); sp = SPEC[sym]; obs = t.R.mean(); ge = 0
    for _ in range(reps):
        rs = []
        for row in t.itertuples():
            D = days[rng.choice(keys)]
            idx = np.where(D["m"] == row.k)[0]
            if not len(idx): continue
            k = idx[0]
            if k + 1 >= len(D["o"]): continue
            e0 = D["o"][k + 1] + row.side * TICK
            stop = e0 - row.side * (row.riskpt)
            r = sim(D, k, row.side, stop)
            if not r: continue
            e, x, risk = r
            rs.append(((x - e) * row.side * sp["usd_pt"] - sp["rt_comm"]) / (risk * sp["usd_pt"]))
        if np.mean(rs) >= obs: ge += 1
    return round((ge + 1) / (reps + 1), 3)

if __name__ == "__main__":
    for sym in ("MES", "MNQ"):
        days = prep(sym)
        print(sym, "days", len(days))
        for name, fn in RULES.items():
            for cut in (60, 75, 90):
                t = run(days, sym, fn, cut)
                st = stats(t)
                if cut == 60 and st.get("n", 0) > 5:
                    st["p_shuf"] = shuffle_p(days, sym, t)
                    st["gross_avgR"] = round(t.gR.mean(), 3)
                    st["long_avgR"] = round(t[t.side == 1].R.mean(), 3); st["short_avgR"] = round(t[t.side == -1].R.mean(), 3)
                print(sym, "|", name, "| cut", 570 + cut and f"{(570+cut)//60}:{(570+cut)%60:02d}", "|", st, flush=True)
            # ES e-mini cost view at 10:30
        # e-mini version at 10:30 for comparison
        big = "ES" if sym == "MES" else "NQ"
        for name, fn in RULES.items():
            print(big, "|", name, "| cut 10:30 |", stats(run(days, big, fn, 60)), flush=True)
