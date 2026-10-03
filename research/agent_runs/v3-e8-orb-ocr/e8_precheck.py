"""E8 PRE-CHECK (OMEN canon section 5, row E8). Paper research only. Not investment advice.

Question: on the FIT window 2024-09-26 -> 2026-09-25 (real NQ 1-min, 502 sessions), how many ORB
break-and-retest trades coincide with a one-candle-rule (OCR) block at the OR5 level?
n < 30 -> NO-TEST (stop, no variants run). n >= 30 -> the 2 declared variants may run.

Declared BEFORE looking at any count (definitions, in order of strictness):
  ORB signal  = frozen mantra `mnq.signal()` (OR5 break, displacement >= 1 ATR, wick retest, strong trigger)
                with cut 11:00 (the loosest of the 10:30/10:45/11:00 cuts).      [primary]
                Loosened:  D0.5 / any trigger / tol 0 (the a2-detector shape).    [L2]
  OCR event   = frozen v2-t02 `detect(orb=True)` geometry: opposite-colour bar in an EMA9>EMA20 trend,
                block high..low, break WITH displacement, retest inside the block, block straddles the OR5 level.
                zone=any, confirm=touch (loosest), cutoff 11:00.
  COINCIDE    = same day, same side, ORB entry bar and OCR entry bar within +-5 one-minute bars.   [primary]
                [loose]  same day, same side, any time before 11:00.
Decision count = primary. The other rows are reported so nothing is hidden.
Window A (2019-09-26 -> 2024-09-25) is never loaded: dates are asserted inside the fit window.
"""
import sys, json
import numpy as np

AR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs"
for p in (AR + r"\v2-signal", AR + r"\v2-t01-orb-1m", AR + r"\v3-t-mnq", AR + r"\v2-t02-ocr-1m", AR + r"\v2-s07-data",
          r"C:\Users\aharg\Desktop\Projects\tradingbot\research"):
    if p not in sys.path: sys.path.insert(0, p)

FIT_START, FIT_END = "2024-09-26", "2026-09-25"
NEAR = 5          # bars, COINCIDE proximity
MIN_N = 30        # canon pre-check floor
TICK = 0.25


def in_fit(d):
    return FIT_START <= str(d) <= FIT_END


def to_A(a):
    """v2-t02 day dict (minute-of-day arrays from 09:00) -> mnq 91-slot arrays (09:30..11:00)."""
    m = a["m"] - 570; ok = (m >= 0) & (m <= 90); A = {}
    for k, s in (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c")):
        x = np.full(91, np.nan); x[m[ok]] = a[s][ok]; A[k] = x
    return A


def orb_entries(A, cut, dk, trig, tol, jmax, mnq):
    """ORB break-and-retest entry (index in 91-slot space, side) or None. Wraps frozen mnq.signal."""
    s = mnq.signal(A, cut, dk, trig, tol, jmax)
    return None if s is None else (s[0], s[1])


def ocr_entries(a, side, cutoff_min, ocr):
    """All OCR-at-OR5-level entries for one side as 91-slot indices. side=-1 mirrors by negation (as v2-t02)."""
    o, c = a["o"] * side, a["c"] * side
    hh, ll = (a["h"], a["l"]) if side == 1 else (-a["l"], -a["h"])
    sig = ocr.detect(o, hh, ll, c, a["m"], "any", "touch", True, cutoff_min)
    return [int(a["m"][e]) - 570 for e, _st, _R in sig]


def precheck(days, mnq, ocr, near=NEAR):
    """days: {date: v2-t02 day dict}. Returns dict of counts (+ the dates for the primary count)."""
    assert all(in_fit(d) for d in days), "window A leak: a date outside the fit window"
    res = {k: 0 for k in ("sessions", "orb_primary", "orb_L2", "ocr_alone_events_days",
                          "coinc_primary", "coinc_L2", "coinc_loose_primary", "coinc_loose_L2")}
    res["sessions"] = len(days); prim = []
    for d, a in days.items():
        A = to_A(a)
        o1 = orb_entries(A, 90, 1.0, "strong", TICK, 99, mnq)
        o2 = orb_entries(A, 90, 0.5, "any", 0.0, 99, mnq)
        oc = {s: ocr_entries(a, s, 660, ocr) for s in (1, -1)}
        res["ocr_alone_events_days"] += int(bool(oc[1] or oc[-1]))
        for tag, o in (("primary", o1), ("L2", o2)):
            if o is None: continue
            res["orb_" + tag] += 1
            i, s = o
            if oc[s] and any(abs(i - e) <= near for e in oc[s]): res["coinc_" + tag] += 1; (prim.append(d) if tag == "primary" else None)
            if oc[s]: res["coinc_loose_" + tag] += 1
    res["primary_dates"] = prim
    return res


def main():
    import mnq, ocr1m
    days = {d: a for d, a in ocr1m.prep("MNQ").items() if in_fit(d)}
    res = precheck(days, mnq, ocr1m)
    # diff vs v2-t02: same detector, orb=True, MNQ only, same window (reproduces t02's MNQ share)
    t02 = {}
    for cut in (630, 645, 660):
        tr = ocr1m.trades_for(days, "MNQ", "any", "strong", True, cut)
        t02[f"strong_{cut}"] = dict(n=len(tr), net=round(float(np.mean([t["net"] for t in tr])), 3) if tr else None)
    res["t02_mnq_orb_any_strong"] = t02
    res["decision_n"] = res["coinc_primary"]; res["verdict"] = "NO-TEST: n too small" if res["decision_n"] < MIN_N else "RUN VARIANTS"
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    main()
