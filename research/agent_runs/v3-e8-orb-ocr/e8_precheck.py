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
  COINCIDE    = CAUSAL (referee fix 2026-10-03): same day, same side, OCR entry bar e with lag = e - i in
                [-NEAR, 0], i = ORB entry index (mnq.signal returns trigger bar + 1). An OCR that forms
                AFTER the ORB entry could not have been known at the ORB entry, so it never counts.   [primary]
  Causal level-based sensitivity rows (reported, not the decision count):
                (a) OCR entry <= ORB entry, any lag;
                (b) OCR break bar j < ORB entry;
                (c) OCR block bar i < ORB entry, same side, block straddles OR5 (orb=True geometry).
  Legacy rows (NOT causal, reported for the audit trail): abs(i - e) <= NEAR, and same day + side any time.
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
    """All OCR-at-OR5-level events for one side as 91-slot indices (entry e, block bar i, break bar j).
    side=-1 mirrors by negation (as v2-t02)."""
    o, c = a["o"] * side, a["c"] * side
    hh, ll = (a["h"], a["l"]) if side == 1 else (-a["l"], -a["h"])
    sig = detect_ij(ocr, o, hh, ll, c, a["m"], "any", "touch", True, cutoff_min)
    m = a["m"]
    return [(int(m[e]) - 570, int(m[bi]) - 570, int(m[bj]) - 570) for e, _st, _R, bi, bj in sig]


def detect_ij(ocr, o, h, l, c, m, zone, confirm, orb, cutoff):
    """Verbatim copy of frozen ocr1m.detect (v2-t02) that also returns the block bar i and break bar j.
    Returns [(ent, st, R, i, j)]. Entries must equal ocr.detect (parity test). Uses ocr.ema / ocr.TICK."""
    TK = ocr.TICK
    n = len(o); e9 = ocr.ema(c, 9); e20 = ocr.ema(c, 20)
    rng = h - l
    atr = np.array([rng[max(0, i - 10):i].mean() if i > 0 else rng[0] for i in range(n)])
    i930 = np.where(m >= 570)[0][0]
    orw = [k for k in range(i930, n) if m[k] < 575]
    if len(orw) < 3: return []
    orh = max(h[k] for k in orw); orr = orh - min(l[k] for k in orw); tol = max(2 * TK, 0.1 * orr)
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
        e = o[ent] + TK; st = bl - TK; R = e - st
        if R < 1.0: continue
        out.append((ent, st, R, i, j))
    return out


def precheck(days, mnq, ocr, near=NEAR):
    """days: {date: v2-t02 day dict}. Returns dict of counts (+ the dates for the primary count)."""
    assert all(in_fit(d) for d in days), "window A leak: a date outside the fit window"
    keys = ("sessions", "orb_primary", "orb_L2", "ocr_alone_events_days",
            "coinc_primary", "coinc_L2",                                   # causal lag in [-NEAR, 0]
            "causal_a_entry_le_orb", "causal_b_break_lt_orb", "causal_c_block_lt_orb",
            "legacy_abs_primary", "legacy_abs_L2", "legacy_loose_primary", "legacy_loose_L2")
    res = {k: 0 for k in keys}
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
            ev = oc[s]
            if any(-near <= e - i <= 0 for e, _bi, _bj in ev):
                res["coinc_" + tag] += 1
                if tag == "primary": prim.append(d)
            if any(abs(i - e) <= near for e, _bi, _bj in ev): res["legacy_abs_" + tag] += 1
            if ev: res["legacy_loose_" + tag] += 1
            if tag == "primary":
                res["causal_a_entry_le_orb"] += int(any(e <= i for e, _bi, _bj in ev))
                res["causal_b_break_lt_orb"] += int(any(bj < i for _e, _bi, bj in ev))
                res["causal_c_block_lt_orb"] += int(any(bi < i for _e, bi, _bj in ev))
    res["primary_dates"] = prim
    return res


def parity(days, ocr):
    """detect_ij entries must equal the frozen ocr.detect entries on every day/side (guards the copy)."""
    bad = 0
    for a in days.values():
        for side in (1, -1):
            o, c = a["o"] * side, a["c"] * side
            hh, ll = (a["h"], a["l"]) if side == 1 else (-a["l"], -a["h"])
            f = [(e, st, R) for e, st, R in ocr.detect(o, hh, ll, c, a["m"], "any", "touch", True, 660)]
            g = [(e, st, R) for e, st, R, _i, _j in detect_ij(ocr, o, hh, ll, c, a["m"], "any", "touch", True, 660)]
            bad += int(f != g)
    return bad


def main():
    import mnq, ocr1m
    days = {d: a for d, a in ocr1m.prep("MNQ").items() if in_fit(d)}
    assert parity(days, ocr1m) == 0, "detect_ij diverged from frozen ocr1m.detect"
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
