"""ADVERSARIAL VERIFY -- g71_stops.md sec.3, the D_off ("delete the disaster
stop") claim.

The arm keeps `stop_rule.stop_fill_price`'s -1.25R clamp while removing the
only order that could deliver -1.25R. With no resting order the exit is a
market exit on the bar that closed beyond the level stop, i.e. that bar's
CLOSE. This script re-prices D_off's clamped rows at that close and re-runs
the whole money read.
"""
import json, math, os, statistics as st, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import polygon_feed as pf

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOOR = 1.25

def load(a):
    with open(os.path.join(R, "research", "_g71s_%s.json" % a)) as f:
        return [r for r in json.load(f)["trades"] if r["traded"]]

_b = {}
def rth(s, d):
    k = (s, d)
    if k not in _b:
        try: _b[k] = pf.rth(pf.fetch_day(s, d))
        except Exception: _b[k] = []
    return _b[k]

def honest(rows):
    """rows -> {row id: true close-based R} for every clamped row."""
    out, near = {}, 0
    for r in rows:
        if r["r"] > -1.2499:
            continue
        risk = abs(r["entry"] - r["stop"])
        if risk <= 0:
            continue
        long = r["side"] == "L"
        cl = r["entry"] - FLOOR * risk if long else r["entry"] + FLOOR * risk
        if abs(r["exit"] - cl) <= 0.02:
            near += 1
        b = rth(r["sym"], r["day"])
        i = r["entry_i"] + r["bars"]
        if i >= len(b):
            continue
        c = b[i].close
        out[id(r)] = (c - r["entry"]) / risk if long else (r["entry"] - c) / risk
    return out, near

def iso_week(d):
    y, w, _ = date.fromisoformat(d).isocalendar()
    return "%d-W%02d" % (y, w)

def dd(rs):
    peak = cum = 0.0; worst = 0.0
    for x in rs:
        cum += x; peak = max(peak, cum); worst = min(worst, cum - peak)
    return worst

def book(rows, override=None):
    override = override or {}
    rr = [override.get(id(r), r["r"]) for r in rows]
    mo, wk = {}, {}
    for r, x in zip(rows, rr):
        mo[r["ym"]] = mo.get(r["ym"], 0.0) + x
        w = iso_week(r["day"]); wk[w] = wk.get(w, 0.0) + x
    wins = sum(1 for r, x in zip(rows, rr) if x > 0)
    return dict(n=len(rr), mean=round(st.fmean(rr), 4), med=round(st.median(rr), 4),
                win=round(100.0 * wins / len(rr), 1),
                months="%d/%d" % (sum(1 for v in mo.values() if v > 0), len(mo)),
                weeks="%d/%d" % (sum(1 for v in wk.values() if v > 0), len(wk)),
                maxdd=round(dd(rr), 1), worst=round(min(rr), 3))

def paired(a_rows, b_rows, b_over=None, cap=1e9):
    b_over = b_over or {}
    k = lambda r: (r["sym"], r["day"], r["et"], r["setup"], r["dir"])
    A = {k(r): r["r"] for r in a_rows}
    B = {k(r): b_over.get(id(r), r["r"]) for r in b_rows}
    both = set(A) & set(B)
    d = [min(B[x], cap) - min(A[x], cap) for x in both]
    m = st.fmean(d); se = st.stdev(d) / math.sqrt(len(d))
    return dict(n=len(d), delta=round(m, 4), se=round(se, 4), t=round(m / se, 2))

def main():
    base = load("S0_shipped")
    off = load("D_off")
    ov, near = honest(off)
    print("D_off clamped rows: %d  (exit price within $0.02 of the clamp: %d)"
          % (len(ov), near))
    bad = [v for v in ov.values() if v < -1.2501]
    print("  of those, the exit bar's CLOSE was already beyond -1.25R on %d"
          "  (mean %.4f, med %.4f, worst %.4f)"
          % (len(bad), st.fmean(bad), st.median(bad), min(bad)))
    print("\nS0_shipped        ", book(base))
    print("D_off  published  ", book(off))
    print("D_off  honest fill", book(off, ov))
    print("\npaired vs S0_shipped")
    print("  D_off published   raw", paired(base, off))
    print("  D_off published   c10", paired(base, off, cap=10.0))
    print("  D_off honest fill raw", paired(base, off, ov))
    print("  D_off honest fill c10", paired(base, off, ov, cap=10.0))
    d125 = load("D_125")
    print("\n  D_125 (real order at -1.25) raw", paired(base, d125))

main()
