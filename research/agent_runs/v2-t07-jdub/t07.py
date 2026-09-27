"""t07: J-Dub's 3 most concrete rules (s03) on real ES/NQ 1-min, honest fills. Paper research only."""
import sys, random, math
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-t06-scarface")
from t06 import prep, sim, levels_orb, stats, TICK
from omen_data import SPEC
import numpy as np, pandas as pd

def tol_of(H, L): return 2 * TICK if H - L < 40 else 8 * TICK

def orb_break(D, cut, disp):
    """first 1m close beyond 5m OR; displacement = break-bar body >= disp * mean OR bar range. No disp -> no-trade day."""
    lv = levels_orb(D)
    if not lv: return None
    H, L, s = lv
    o, h, l, c, m = D["o"], D["h"], D["l"], D["c"], D["m"]
    f = m < 5; atr = (h[f] - l[f]).mean()
    for k in range(s, len(c) - 1):
        if m[k] >= cut: return None
        side = 1 if c[k] > H else (-1 if c[k] < L else 0)
        if side:
            if abs(c[k] - o[k]) < disp * atr or (c[k] - o[k]) * side <= 0: return None
            return H, L, k, side, (H if side == 1 else L)

def j1(D, cut, disp=1.0, win=20):
    """J1 ORB B&R: displacement break -> wick retest within tol, no close through (close through = chop, day off)
    -> confirmation candle (closes in trade direction at/after touch) -> next open; stop 1 tick beyond conf candle; 2R."""
    b = orb_break(D, cut, disp)
    if not b: return None
    H, L, bk, side, lev = b
    o, h, l, c, m = D["o"], D["h"], D["l"], D["c"], D["m"]; tol = tol_of(H, L)
    touched = False
    for k in range(bk + 1, min(len(c) - 1, bk + 1 + win)):
        if m[k] >= cut: return None
        if (c[k] - lev) * side < 0: return None
        if side == 1 and l[k] <= lev + tol or side == -1 and h[k] >= lev - tol: touched = True
        if touched and (c[k] - o[k]) * side > 0:
            return k, side, (l[k] - TICK if side == 1 else h[k] + TICK), lev
    return None

def sim_limit(D, j0, side, entry, stop, tgt_R=2.0, cut=None):
    """limit entry: fills only on 1-tick trade-through of `entry` from bar j0 on, filled at entry + 1 tick adverse.
    Same-bar stop counted; target not on fill bar. Invalid if price closes beyond stop before fill."""
    o, h, l, c, m = D["o"], D["h"], D["l"], D["c"], D["m"]
    for j in range(j0, len(o)):
        if m[j] >= cut: return None
        if (side == 1 and l[j] <= entry - TICK) or (side == -1 and h[j] >= entry + TICK):
            e = entry + side * TICK; risk = (e - stop) * side
            if risk <= 0: return None
            t = e + side * tgt_R * risk
            if (side == 1 and l[j] <= stop) or (side == -1 and h[j] >= stop):
                return j, e, stop - side * TICK, risk
            for k in range(j + 1, len(o)):
                if side == 1:
                    if l[k] <= stop: return j, e, min(stop, o[k]) - TICK, risk
                    if h[k] >= t + TICK: return j, e, t, risk
                else:
                    if h[k] >= stop: return j, e, max(stop, o[k]) + TICK, risk
                    if l[k] <= t - TICK: return j, e, t, risk
            return j, e, c[-1] - side * TICK, risk
        if (c[j] - stop) * side < 0: return None
    return None

def ob_of(D, bk, side, look=15):
    """last opposite-close candle before/at the displacement leg (J-Dub continuation OB), zone = wick -> body."""
    o, h, l, c = D["o"], D["h"], D["l"], D["c"]
    for k in range(bk - 1, max(-1, bk - 1 - look), -1):
        if (c[k] - o[k]) * side < 0:
            if side == 1: return k, max(o[k], c[k]), l[k]      # top = body top, bottom = low wick
            return k, min(o[k], c[k]), h[k]
    return None

def j2(D, cut, disp=1.0, conf=True, fill="top"):
    """J2 order block B&R after displacement ORB break: limit at OB top (or mid), stop 1 tick beyond far end, 2R.
    conf=True -> OB zone must contain/touch the ORB level (+tol) = ORB+OCR confluence (S)."""
    b = orb_break(D, cut, disp)
    if not b: return None
    H, L, bk, side, lev = b
    ob = ob_of(D, bk, side)
    if not ob: return None
    k, top, bot = ob; tol = tol_of(H, L)
    lo, hi = min(top, bot), max(top, bot)
    if conf and not (lo - tol <= lev <= hi + tol): return None
    if abs(top - bot) < TICK: return None
    entry = top if fill == "top" else (top + bot) / 2
    stop = bot - side * TICK
    return bk + 1, side, entry, stop

def run_j1(days, sym, cut, disp=1.0, rule84=None):
    sp = SPEC[sym]; out = []
    for d in sorted(days):
        D = days[d]; s = j1(D, cut, disp)
        if not s: continue
        k, side, stop, lev = s
        r = sim(D, k, side, stop)
        if not r: continue
        e, x, risk = r
        R = ((x - e) * side * sp["usd_pt"] - sp["rt_comm"]) / (risk * sp["usd_pt"])
        out.append(dict(date=d, side=side, k=int(D["m"][k]), riskpt=risk, R=R, usd=R * risk * sp["usd_pt"],
                        gR=(x - e) * side / risk, kind="orig"))
        if rule84 is not None and (x - e) * side < 0 and (x - stop) * side <= 0:   # stopped out
            re = reentry(D, k, side, e, stop, e + side * 2 * risk, lev, cut, rule84)
            if re:
                e2, x2, r2, k2, hit = re
                R2 = ((x2 - e2) * side * sp["usd_pt"] - sp["rt_comm"]) / (r2 * sp["usd_pt"])
                out.append(dict(date=d, side=side, k=int(D["m"][k2]), riskpt=r2, R=R2, usd=R2 * r2 * sp["usd_pt"],
                                gR=(x2 - e2) * side / r2, kind="re84", hit=hit, R1=R))
    return pd.DataFrame(out)

def reentry(D, k, side, e, stop, tgt, lev, cut, win):
    """84%: after the stop bar, first 1m close back beyond the original level within `win` bars -> next open.
    Original stop price and original target price. One re-entry."""
    o, h, l, c, m = D["o"], D["h"], D["l"], D["c"], D["m"]
    sb = None
    for j in range(k + 1, len(o)):
        if (side == 1 and l[j] <= stop) or (side == -1 and h[j] >= stop): sb = j; break
    if sb is None: return None
    for j in range(sb + 1, min(len(o) - 1, sb + 1 + win)):
        if m[j] >= cut: return None
        if (c[j] - lev) * side > 0:
            e2 = o[j + 1] + side * TICK; r2 = (e2 - stop) * side
            if r2 <= 0 or (tgt - e2) * side <= 0: return None
            for q in range(j + 1, len(o)):
                if side == 1:
                    if l[q] <= stop: return e2, min(stop, o[q]) - TICK, r2, j, False
                    if h[q] >= tgt + TICK: return e2, tgt, r2, j, True
                else:
                    if h[q] >= stop: return e2, max(stop, o[q]) + TICK, r2, j, False
                    if l[q] <= tgt - TICK: return e2, tgt, r2, j, True
            return e2, c[-1] - side * TICK, r2, j, False
    return None

def run_j2(days, sym, cut, **kw):
    sp = SPEC[sym]; out = []
    for d in sorted(days):
        D = days[d]; s = j2(D, cut, **kw)
        if not s: continue
        j0, side, entry, stop = s
        r = sim_limit(D, j0, side, entry, stop, cut=cut)
        if not r: continue
        j, e, x, risk = r
        R = ((x - e) * side * sp["usd_pt"] - sp["rt_comm"]) / (risk * sp["usd_pt"])
        out.append(dict(date=d, side=side, k=int(D["m"][j]) - 1, riskpt=risk, R=R, usd=R * risk * sp["usd_pt"],
                        gR=(x - e) * side / risk))
    return pd.DataFrame(out)

def shuffle_p(days, sym, t, reps=300, seed=7):
    rng = random.Random(seed); keys = sorted(days); sp = SPEC[sym]; obs = t.R.mean(); ge = 0
    for _ in range(reps):
        rs = []
        for row in t.itertuples():
            D = days[rng.choice(keys)]
            idx = np.where(D["m"] == row.k)[0]
            if not len(idx) or idx[0] + 1 >= len(D["o"]): continue
            k = idx[0]; e0 = D["o"][k + 1] + row.side * TICK
            r = sim(D, k, row.side, e0 - row.side * row.riskpt)
            if not r: continue
            e, x, risk = r
            rs.append(((x - e) * row.side * sp["usd_pt"] - sp["rt_comm"]) / (risk * sp["usd_pt"]))
        if rs and np.mean(rs) >= obs: ge += 1
    return round((ge + 1) / (reps + 1), 3)

def show(tag, sym, t, days, shuf=False):
    st = stats(t)
    if shuf and st.get("n", 0) > 5:
        st["p_shuf"] = shuffle_p(days, sym, t); st["gross"] = round(t.gR.mean(), 3)
        st["L"] = round(t[t.side == 1].R.mean(), 3); st["S"] = round(t[t.side == -1].R.mean(), 3)
    print(sym, "|", tag, "|", st, flush=True)

if __name__ == "__main__":
    CUTS = {60: "10:30", 75: "10:45", 90: "11:00"}
    for sym in ("MES", "MNQ"):
        days = prep(sym); big = "ES" if sym == "MES" else "NQ"
        print(sym, "days", len(days))
        for cut, cn in CUTS.items():
            for disp in (0.0, 1.0, 1.5):
                show(f"J1 ORB B&R disp{disp} {cn}", sym, run_j1(days, sym, cut, disp), days, shuf=(cut == 90 and disp == 1.0))
            for conf in (False, True):
                for fill in ("top", "mid"):
                    show(f"J2 OB conf{int(conf)} {fill} disp1.0 {cn}", sym, run_j2(days, sym, cut, disp=1.0, conf=conf, fill=fill),
                         days, shuf=(cut == 90 and fill == "top"))
            show(f"J2 OB conf1 top disp0 {cn}", sym, run_j2(days, sym, cut, disp=0.0, conf=True, fill="top"), days)
            for win in (10, 20, 30):
                t = run_j1(days, sym, cut, 1.0, rule84=win)
                re = t[t.kind == "re84"] if len(t) else t
                if len(re):
                    st = stats(re); st["tgt_hit%"] = round(100 * re.hit.mean(), 1)
                    st["day_R(orig+re)"] = round((re.R1 + re.R).mean(), 3)
                    if cut == 90 and win == 20 and len(re) > 5: st["p_shuf"] = shuffle_p(days, sym, re)
                    print(sym, "|", f"J3 84% re-entry win{win} (after J1 disp1.0 stop) {cn}", "|", st, flush=True)
                show(f"J1+J3 book win{win} {cn}", sym, t, days)
        for cut, cn in CUTS.items():
            show(f"J1 disp1.0 {cn} e-mini", big, run_j1(days, big, cut, 1.0), days)
            show(f"J2 conf1 top {cn} e-mini", big, run_j2(days, big, cut, disp=1.0, conf=True, fill="top"), days)
