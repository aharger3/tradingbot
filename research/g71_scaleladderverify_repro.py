"""ADVERSARIAL re-implementation of the g71_scaleladder four-tranche ladder.

Written from the SPEC (Austin's words + CLAUDE.md fill rules), not by importing
research/g71_scaleladder.py's run_ladder. Only stop_rule (the one fill
definition) and p21_target_availability.levels_for_entry (the level roster) are
shared. Compares per-trade composite R against the committed rows file.

Usage: python research/g71_scaleladderverify_repro.py [--limit N]
"""
from __future__ import annotations
import argparse, json, os, statistics, sys
from pathlib import Path
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(HERE))
for p in (str(ROOT), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import polygon_feed as pf
from stop_rule import (stop_fill_price, stop_hit_on_close,
                       disaster_stop_price, disaster_stop_hit, DISASTER_STOP_R)
import p21_target_availability as p21

SIX = ("PDH", "PDL", "PMH", "PML", "ORH", "ORL")
S = 2
_bc = {}

def bars_for(sym, day):
    k = (sym, day)
    if k not in _bc:
        try:
            r = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            r = []
        _bc[k] = [(c.open, c.high, c.low, c.close) for c in r]
    return _bc[k]

def swings(bars, ei):
    lo, hi = {}, {}
    n = len(bars)
    for j in range(max(ei, S), n - S):
        L, H = bars[j][2], bars[j][1]
        if all(bars[k][2] > L for k in range(j - S, j)) and all(bars[k][2] > L for k in range(j + 1, j + S + 1)):
            lo[j + S] = L
        if all(bars[k][1] < H for k in range(j - S, j)) and all(bars[k][1] < H for k in range(j + 1, j + S + 1)):
            hi[j + S] = H
    return lo, hi

def ladder(bars, ei, entry, stop, long, w, t2px, trail="be"):
    """Independent implementation. Returns (composite, legs dict)."""
    n = len(bars); risk = abs(entry - stop)
    if risk <= 0 or ei >= n - 1: return None, {}
    R = lambda px: (px - entry) / risk if long else (entry - px) / risk
    openk = {1, 2, 3, 4}
    legs = {}
    dz = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
    slo, shi = swings(bars, ei)
    last = None
    ext = max(b[1] for b in bars[:ei + 1]) if long else min(b[2] for b in bars[:ei + 1])
    made = False; be = False; ws = stop; fav = entry
    def shut(px, keys):
        r = R(px)
        for k in list(keys):
            if k in openk:
                openk.discard(k); legs[k] = r
    for i in range(ei + 1, n):
        o, h, l, c = bars[i]
        if not be and disaster_stop_hit(h, l, dz, long):
            shut(dz, list(openk)); break
        if stop_hit_on_close(c, ws, long):
            shut(stop_fill_price(c, entry, risk, long), list(openk)); break
        if 1 in openk:
            if not made:
                if (h > ext) if long else (l < ext):
                    made = True; ext = h if long else l
            else:
                if (h <= bars[i - 1][1]) if long else (l >= bars[i - 1][2]):
                    shut(c, [1])
                    if not be: be = True; ws = entry
                else:
                    ext = h if long else l
        if 2 in openk and ((h >= t2px) if long else (l <= t2px)):
            shut(t2px, [2])
            if not be: be = True; ws = entry
        if 3 in openk:
            if i in slo and long: last = slo[i]
            if i in shi and not long: last = shi[i]
            if last is not None and ((c < last) if long else (c > last)):
                shut(c, [3])
                if not be: be = True; ws = entry
        if not openk: break
        fav = max(fav, h) if long else min(fav, l)
        if be:
            if trail == "be": ws = entry
            elif trail == "1r": ws = max(entry, fav - risk) if long else min(entry, fav + risk)
            elif trail == "struct": ws = max(entry, l) if long else min(entry, h)
    if openk:
        shut(bars[n - 1][3], list(openk))
    comp = sum(w[k - 1] * legs[k] for k in (1, 2, 3, 4))
    return comp, legs

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    book = json.load(open(ROOT / "research/bt2y_trades.json"))
    rows = [t for t in book["trades"] if t.get("traded")]
    ref = json.load(open(ROOT / "research/g71_scaleladder_rows.json"))
    V = ref["variants"]
    print("book traded=%d  meta=%s" % (len(rows), json.dumps(book["meta"])[:120]))
    print("rows meta=%s" % json.dumps(ref["meta"]))
    W = {0.0: (1/3, 1/3, 1/3, 0.0), 0.10: (0.30, 0.30, 0.30, 0.10),
         0.20: (0.8/3, 0.8/3, 0.8/3, 0.20), 0.30: (0.7/3, 0.7/3, 0.7/3, 0.30)}
    if a.limit: rows = rows[:a.limit]
    out = {}
    idx = 0
    early_or = 0
    t2_bound_by_level = 0
    kept_keys = []
    for t in rows:
        ei = t.get("entry_i")
        bars = bars_for(t["sym"], t["day"])
        if ei is None or not bars or ei >= len(bars) - 1:
            continue
        long = t["dir"] == "call"
        if ei < 4: early_or += 1
        lv = p21.levels_for_entry(t["sym"], t["day"], ei) or {}
        six = [px for k, px in lv.items() if k in SIX]
        risk = abs(t["entry"] - t["stop"])
        two = t["entry"] + 2 * risk if long else t["entry"] - 2 * risk
        beyond = [px for px in six if (px > t["entry"] if long else px < t["entry"])]
        t2 = two
        if beyond:
            nr = min(beyond) if long else max(beyond)
            t2 = min(two, nr) if long else max(two, nr)
        if abs(t2 - two) > 1e-12: t2_bound_by_level += 1
        kept_keys.append(idx)
        for f, ww in W.items():
            for tr in ("be", "1r", "struct"):
                c, _ = ladder(bars, ei, t["entry"], t["stop"], long, ww, t2, tr)
                out.setdefault((f, tr), []).append(c)
        idx += 1
    print("kept=%d  entry_i<4 (ORH/ORL look-ahead risk)=%d  T2 bound by a level=%d"
          % (idx, early_or, t2_bound_by_level))
    print()
    print("%-22s %8s %8s %10s %10s %10s" % ("cell", "n", "win%", "mine", "theirs", "delta"))
    for f in (0.0, 0.10, 0.20, 0.30):
        for tr in ("be", "1r", "struct"):
            mine = [x for x in out[(f, tr)] if x is not None]
            lab = "f=%d%% / trail=%s" % (round(f * 100), tr)
            th = [x for x in V[lab][:len(out[(f, tr)])] if x is not None] if not a.limit else None
            mm = sum(mine) / len(mine)
            tt = (sum(th) / len(th)) if th else float("nan")
            w = 100 * sum(1 for r in mine if r > 0) / sum(1 for r in mine if r != 0)
            print("%-22s %8d %8.1f %+10.4f %+10.4f %+10.4f" % (lab, len(mine), w, mm, tt, mm - tt))
    if not a.limit:
        # per-trade max abs deviation on his ladder
        mine = out[(0.10, "be")]; th = V["f=10% / trail=be"]
        d = [abs(x - y) for x, y in zip(mine, th) if x is not None and y is not None]
        print("\nper-trade |mine-theirs| on f=10%%/be: max=%.6f  n_over_1e-6=%d"
              % (max(d), sum(1 for x in d if x > 1e-6)))

main()
