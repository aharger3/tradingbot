"""s-matcher: decision-time features + honest 1-min sim. Pure numpy, no I/O, no future bars.

A "day" is a dict of 1440-long minute-of-day arrays (O,H,L,C,V), NaN where no bar. Minute index m is the bar OPEN
time (m = 60*hh+mm, ET). A signal at bar m has its bar CLOSED; entry is the open of bar m+1. Every feature below reads
only indexes <= m on the signal day, plus the previous session and the 04:00-09:29 pre-market of the same day.
"""
import numpy as np

RTH0, RTH1 = 570, 960          # 09:30 .. 15:59 (bar open minutes)
PRE0 = 240                     # 04:00
FLAT = 660                     # 11:00
FEATURES = ["is_long", "tod", "or5_range_atr", "or5_range_pdr", "or_break_dist_atr", "bars_since_or_break",
            "vwap_dist_atr", "room_pd_atr", "pd_pos_dir", "dist_pdc_atr", "on_range_pdr", "on_pos_dir",
            "gap_dir_pdr", "mom5_atr", "mom15_atr", "vol_ratio_sig", "relvol_cum", "body_frac", "rej_wick",
            "far_wick", "close_pos_dir", "range_atr", "stop_atr"]
NQ_CTX = ["nq_mom15_atr", "nq_vwap_dist_atr", "nq_gap_dir_pdr"]


def empty_day():
    return {k: np.full(1440, np.nan) for k in "OHLCV"}


def day_from_rows(minutes, o, h, l, c, v):
    d = empty_day()
    m = np.asarray(minutes, dtype=int)
    ok = (m >= 0) & (m < 1440)
    for k, a in zip("OHLCV", (o, h, l, c, v)):
        d[k][m[ok]] = np.asarray(a, dtype=float)[ok]
    return d


def prior_levels(prev):
    """RTH high/low/close + cumulative RTH volume array of the previous session (or all NaN)."""
    nanres = dict(pdh=np.nan, pdl=np.nan, pdc=np.nan, cumv=None)
    if prev is None:
        return nanres
    H, L, C, V = (prev[k][RTH0:RTH1] for k in "HLCV")
    if np.isnan(H).all():
        return nanres
    cl = C[~np.isnan(C)]
    return dict(pdh=np.nanmax(H), pdl=np.nanmin(L), pdc=cl[-1] if len(cl) else np.nan,
                cumv=np.cumsum(np.nan_to_num(V)))


def _ref_close(day, m, back):
    j = m - back
    if j >= RTH0 and np.isfinite(day["C"][j]):
        return day["C"][j]
    return day["O"][RTH0] if np.isfinite(day["O"][RTH0]) else np.nan


def features_at(day, prev, m, side, stop):
    """Feature dict for a signal on bar m (bar closed), trade side +1/-1, structural stop price.
    Uses day[:m+1], the day's pre-market, and `prev` only."""
    O, H, L, C, V = (day[k] for k in "OHLCV")
    f = {k: np.nan for k in FEATURES}
    f["is_long"] = 1.0 if side > 0 else 0.0
    f["tod"] = float(m - RTH0)
    if not (m > RTH0 and np.isfinite(C[m])):
        return f
    rng = H[RTH0:m + 1] - L[RTH0:m + 1]
    last14 = rng[-14:]
    last14 = last14[np.isfinite(last14)]
    if len(last14) < 3:
        return f
    atr = float(last14.mean())
    if atr <= 0:
        return f
    c, o, h, l = C[m], O[m], H[m], L[m]
    pl = prior_levels(prev)
    pdh, pdl, pdc = pl["pdh"], pl["pdl"], pl["pdc"]
    pdr = pdh - pdl if np.isfinite(pdh) and np.isfinite(pdl) else np.nan
    pdr = pdr if (np.isfinite(pdr) and pdr > 0) else np.nan
    # opening range 09:30-09:34 (needs 5 complete bars: m >= 574)
    if m >= RTH0 + 4:
        ors = slice(RTH0, RTH0 + 5)
        if np.isfinite(H[ors]).any():
            orh, orl = np.nanmax(H[ors]), np.nanmin(L[ors])
            f["or5_range_atr"] = (orh - orl) / atr
            f["or5_range_pdr"] = (orh - orl) / pdr if np.isfinite(pdr) else np.nan
            f["or_break_dist_atr"] = ((c - orh) if side > 0 else (orl - c)) / atr
            cc = C[RTH0 + 5:m + 1]
            beyond = np.where((cc > orh) if side > 0 else (cc < orl))[0]
            f["bars_since_or_break"] = float(len(cc) - beyond[0]) if len(beyond) else np.nan
    # vwap from 09:30
    tp = (H[RTH0:m + 1] + L[RTH0:m + 1] + C[RTH0:m + 1]) / 3.0
    vv = V[RTH0:m + 1]
    ok = np.isfinite(tp) & np.isfinite(vv)
    if ok.any() and vv[ok].sum() > 0:
        vwap = float((tp[ok] * vv[ok]).sum() / vv[ok].sum())
        f["vwap_dist_atr"] = (c - vwap) * side / atr
    if np.isfinite(pdr):
        f["room_pd_atr"] = ((pdh - c) if side > 0 else (c - pdl)) / atr
        pos = (c - pdl) / pdr
        f["pd_pos_dir"] = pos if side > 0 else 1.0 - pos
        f["dist_pdc_atr"] = (c - pdc) * side / atr
    # overnight / pre-market 04:00-09:29
    pre_h, pre_l = H[PRE0:RTH0], L[PRE0:RTH0]
    if np.isfinite(pre_h).any() and np.isfinite(pdr):
        onh, onl = np.nanmax(pre_h), np.nanmin(pre_l)
        f["on_range_pdr"] = (onh - onl) / pdr
        if onh > onl:
            p = (c - onl) / (onh - onl)
            p = min(max(p, -1.0), 2.0)
            f["on_pos_dir"] = p if side > 0 else 1.0 - p
    if np.isfinite(pdr) and np.isfinite(O[RTH0]) and np.isfinite(pdc):
        f["gap_dir_pdr"] = (O[RTH0] - pdc) * side / pdr
    f["mom5_atr"] = (c - _ref_close(day, m, 5)) * side / atr
    f["mom15_atr"] = (c - _ref_close(day, m, 15)) * side / atr
    pv = V[max(RTH0, m - 14):m]
    pv = pv[np.isfinite(pv)]
    if len(pv) >= 3 and pv.mean() > 0 and np.isfinite(V[m]):
        f["vol_ratio_sig"] = float(V[m] / pv.mean())
    if pl["cumv"] is not None:
        cum_today = np.nansum(V[RTH0:m + 1])
        cum_prev = pl["cumv"][m - RTH0]
        if cum_prev > 0:
            f["relvol_cum"] = float(cum_today / cum_prev)
    bar = h - l
    if bar > 0:
        f["body_frac"] = (c - o) * side / bar
        if side > 0:
            f["rej_wick"] = (min(o, c) - l) / bar
            f["far_wick"] = (h - max(o, c)) / bar
            f["close_pos_dir"] = (c - l) / bar
        else:
            f["rej_wick"] = (h - max(o, c)) / bar
            f["far_wick"] = (min(o, c) - l) / bar
            f["close_pos_dir"] = (h - c) / bar
        f["range_atr"] = bar / atr
    if np.isfinite(stop):
        f["stop_atr"] = (c - stop) * side / atr
    return f


def nq_context(nq_day, nq_prev, m, side):
    """Same definitions on the NQ tape at the same minute (market context for a labeled stock signal)."""
    if nq_day is None:
        return {k: np.nan for k in NQ_CTX}
    f = features_at(nq_day, nq_prev, m, side, np.nan)
    return {"nq_mom15_atr": f["mom15_atr"], "nq_vwap_dist_atr": f["vwap_dist_atr"],
            "nq_gap_dir_pdr": f["gap_dir_pdr"]}


def simulate(day, m, side, stop, flat_m=FLAT, slip=0.01, comm_side=0.005, min_risk_frac=0.0005, tgt_extra=0.0):
    """Entry at open of bar m+1 (+slip adverse), stop touch (gap -> open), stop checked before target, 2R limit needs
    price through (tgt_extra = extra distance, e.g. 1 tick), flat at the flat_m bar open (-slip). Net R after commission (comm_side per unit, both sides).
    Returns (R, how) or None. Mirrors t04 eye_test.sim."""
    O, H, L, C = (day[k] for k in "OHLC")
    if m + 1 >= flat_m or not np.isfinite(O[m + 1]):
        return None
    fill = O[m + 1] + slip * side
    risk = (fill - stop) * side
    if not np.isfinite(risk) or risk <= 0 or risk < min_risk_frac * fill:
        return None
    tgt = fill + 2 * risk * side
    ex = how = None
    for k in range(m + 1, flat_m):
        if not np.isfinite(O[k]):
            continue
        first = k == m + 1
        if side > 0:
            if not first and O[k] <= stop:
                ex, how = O[k] - slip, "gap"; break
            if L[k] <= stop:
                ex, how = stop - slip, "stop"; break
            if H[k] > tgt + tgt_extra - (1e-9 if tgt_extra else 0.0):
                ex, how = tgt, "tgt"; break
        else:
            if not first and O[k] >= stop:
                ex, how = O[k] + slip, "gap"; break
            if H[k] >= stop:
                ex, how = stop + slip, "stop"; break
            if L[k] < tgt - tgt_extra + (1e-9 if tgt_extra else 0.0):
                ex, how = tgt, "tgt"; break
    if ex is None:
        later = [k for k in range(flat_m, RTH1) if np.isfinite(O[k])]
        if later:
            ex = O[later[0]] - slip * side
        else:
            cl = C[RTH0:RTH1]
            cl = cl[np.isfinite(cl)]
            ex = (cl[-1] if len(cl) else fill) - slip * side
        how = "time"
    pps = (ex - fill) * side
    return (pps - 2 * comm_side) / risk, how
