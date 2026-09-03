"""G7.1 adversarial verify of track `scaleladder`.

Independent re-implementation of the four-tranche ladder + the CONTROL ARM the
original report never ran: the SHIPPED 50/50 `hod_then_runner_be` plan pushed
through the SAME rig, to test whether the rig reproduces the book's own +0.549R.
If it does not, the report's "-0.010R delta" is rig noise, not a policy delta.

Read-only. Writes nothing but its own stdout.
"""
from __future__ import annotations
import json, os, statistics, sys
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(HERE))
for p in (str(ROOT), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import polygon_feed as pf
from stop_rule import (stop_fill_price, stop_hit_on_close,
                       disaster_stop_price, disaster_stop_hit, DISASTER_STOP_R)

SIX = ("PDH", "PDL", "PMH", "PML", "ORH", "ORL")
STRENGTH = 2
EOD = 10 ** 6

_bc = {}


def bars_for(sym, day):
    k = (sym, day)
    v = _bc.get(k)
    if v is None:
        try:
            v = [(c.open, c.high, c.low, c.close) for c in pf.rth(pf.fetch_day(sym, day))]
        except Exception:
            v = []
        _bc[k] = v
    return v


def swings(bars, ei, strength=STRENGTH):
    """confirm_index -> price."""
    lo, hi = {}, {}
    n = len(bars)
    for j in range(max(ei, strength), n - strength):
        L, H = bars[j][2], bars[j][1]
        if all(bars[k][2] > L for k in range(j - strength, j)) and \
           all(bars[k][2] > L for k in range(j + 1, j + strength + 1)):
            lo[j + strength] = L
        if all(bars[k][1] < H for k in range(j - strength, j)) and \
           all(bars[k][1] < H for k in range(j + 1, j + strength + 1)):
            hi[j + strength] = H
    return lo, hi


def t2_target(entry, stop, long, levels):
    risk = abs(entry - stop)
    two = entry + 2 * risk if long else entry - 2 * risk
    beyond = [p for p in levels if (p > entry if long else p < entry)]
    px = two
    if beyond:
        nr = min(beyond) if long else max(beyond)
        px = min(px, nr) if long else max(px, nr)
    return px, ((px - entry) / risk if long else (entry - px) / risk)


def ladder(bars, ei, entry, stop, long, w, t2px, trail="be", struct="swing",
           clock=EOD, disaster=True, runner_target=None):
    """Independent re-implementation. w = (w1,w2,w3,w4).

    runner_target: if given, T4 also exits on an intrabar TOUCH of this price
    (the SHIPPED runner behaviour). None = ride to the close (report's arm).
    """
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0 or ei >= n - 1:
        return None, {}, set()
    end = min(clock + 1, n) if clock != EOD else n
    if ei + 1 >= end:
        return None, {}, set()
    openw = {i + 1: w[i] for i in range(4) if w[i] > 0}
    booked = 0.0
    legs = {}
    own = set()

    def rof(px):
        return (px - entry) / risk if long else (entry - px) / risk

    def close(px, keys=None):
        nonlocal booked
        r = rof(px)
        if keys:
            own.update(keys)
        for k in (keys or list(openw)):
            if k in openw:
                openw.pop(k)
                legs[k] = r
                booked += w[k - 1] * r

    dz = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
    slo, shi = swings(bars, ei) if struct == "swing" else ({}, {})
    last = None
    ext = max(b[1] for b in bars[:ei + 1]) if long else min(b[2] for b in bars[:ei + 1])
    made = False
    be = False
    ws = stop
    fav = entry

    for i in range(ei + 1, end):
        o, h, l, c = bars[i]
        if disaster and not be and disaster_stop_hit(h, l, dz, long):
            close(dz)
            return booked, legs, own
        if stop_hit_on_close(c, ws, long):
            close(stop_fill_price(c, entry, risk, long))
            return booked, legs, own
        if 1 in openw:
            if not made:
                if (h > ext) if long else (l < ext):
                    made = True
                    ext = h if long else l
            else:
                if (h <= bars[i - 1][1]) if long else (l >= bars[i - 1][2]):
                    close(c, [1])
                    if not be:
                        be = True
                        ws = entry
                else:
                    ext = h if long else l
        if 2 in openw and ((h >= t2px) if long else (l <= t2px)):
            close(t2px, [2])
            if not be:
                be = True
                ws = entry
        if 3 in openw:
            if struct == "swing":
                if i in slo and long:
                    last = slo[i]
                if i in shi and not long:
                    last = shi[i]
                broke = last is not None and (c < last if long else c > last)
            else:
                broke = (l < bars[i - 1][2]) if long else (h > bars[i - 1][1])
            if broke:
                close(c, [3])
                if not be:
                    be = True
                    ws = entry
        if 4 in openw and runner_target is not None and \
           ((h >= runner_target) if long else (l <= runner_target)):
            close(runner_target, [4])
        if not openw:
            return booked, legs, own
        fav = max(fav, h) if long else min(fav, l)
        if be:
            if trail == "be":
                ws = entry
            elif trail == "1r":
                ws = max(entry, fav - risk) if long else min(entry, fav + risk)
            elif trail == "struct":
                ws = max(entry, l) if long else min(entry, h)
    close(bars[end - 1][3])
    return booked, legs, own


def agg(rs):
    rs = [r for r in rs if r is not None]
    if not rs:
        return 0, 0.0, 0.0, 0.0
    w = sum(1 for r in rs if r > 0)
    d = sum(1 for r in rs if r != 0)
    return len(rs), (w / d * 100 if d else 0), sum(rs) / len(rs), sum(rs)


def green(rows, rs, key):
    t = defaultdict(float)
    for r0, r in zip(rows, rs):
        if r is not None:
            t[key(r0)] += r
    return sum(1 for v in t.values() if v > 0), len(t)


def show(label, kept, rs):
    n, wr, m, tot = agg(rs)
    mg, mt = green(kept, rs, lambda x: x["ym"])
    print("%-46s n=%d win=%.2f%% meanR=%+.4f tot=%+.0f months=%d/%d"
          % (label, n, wr, m, tot, mg, mt), flush=True)
    return m


def paired(label, a_list, b_list):
    d = [b - a for a, b in zip(a_list, b_list) if b is not None and a is not None]
    if not d:
        return
    sd = statistics.pstdev(d)
    se = sd / len(d) ** 0.5
    print("PAIRED %-40s mean=%+.4f sd=%.4f se=%.4f 95%%CI=[%+.4f,%+.4f] n=%d"
          % (label, statistics.fmean(d), sd, se,
             statistics.fmean(d) - 1.96 * se, statistics.fmean(d) + 1.96 * se, len(d)))


def main():
    import p21_target_availability as p21
    raw = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
    book = [t for t in raw["trades"] if t["traded"]]
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if lim:
        book = book[:lim]
    print("book traded=%d meta.traded=%d" % (len(book), raw["meta"]["traded"]))

    ctx, kept = [], []
    for k, t in enumerate(book, 1):
        ei = t.get("entry_i")
        bars = bars_for(t["sym"], t["day"])
        if not bars or ei is None or ei >= len(bars) - 1:
            continue
        long = t["dir"] == "call"
        lv = p21.levels_for_entry(t["sym"], t["day"], ei) or {}
        six = [p for kk, p in lv.items() if kk in SIX]
        px, rr = t2_target(t["entry"], t["stop"], long, six)
        ctx.append((t, bars, ei, long, px, rr))
        kept.append(t)
        if k % 500 == 0:
            print("  ctx %d/%d" % (k, len(book)), flush=True)
    print("usable ctx=%d  dropped=%d" % (len(ctx), len(book) - len(ctx)))

    W = (0.30, 0.30, 0.30, 0.10)

    def run(w, trail="be", struct="swing", clock=EOD, use_book_rt=False, flat2r=False):
        rs = []
        for (t, bars, ei, long, px, rr) in ctx:
            risk = abs(t["entry"] - t["stop"])
            tp = ((t["entry"] + 2 * risk) if long else (t["entry"] - 2 * risk)) if flat2r else px
            rt = (t.get("runner_target") or t.get("target")) if use_book_rt else None
            r, _lg, _ow = ladder(bars, ei, t["entry"], t["stop"], long, w, tp,
                                 trail=trail, struct=struct, clock=clock,
                                 runner_target=rt)
            rs.append(r)
        return rs

    inc = [t["r"] for t in kept]
    show("BOOK stored r (shipped hod_then_runner_be)", kept, inc)

    his = run(W, "be")
    show("MY his ladder 30/30/30/10 trail=be", kept, his)

    ctrl_close = run((0.5, 0, 0, 0.5), "be")
    show("CTRL rig 50/50 T1 + runner-to-CLOSE", kept, ctrl_close)

    ctrl_tgt = run((0.5, 0, 0, 0.5), "be", use_book_rt=True)
    show("CTRL rig 50/50 T1 + runner-to-book-target", kept, ctrl_tgt)

    print()
    paired("his-ladder minus BOOK r", inc, his)
    paired("CTRL(rig 50/50 close) minus BOOK r", inc, ctrl_close)
    paired("CTRL(rig 50/50 tgt) minus BOOK r", inc, ctrl_tgt)
    paired("his-ladder minus CTRL(rig 50/50 close)", ctrl_close, his)
    paired("his-ladder minus CTRL(rig 50/50 tgt)", ctrl_tgt, his)

    rp = ROOT / "research/g71_scaleladder_rows.json"
    if rp.exists() and not lim:
        pr = json.loads(rp.read_text(encoding="utf-8"))
        theirs = pr["variants"]["HIS LADDER 30/30/30/10 be"]
        if len(theirs) == len(his):
            diff = [i for i, (a, b) in enumerate(zip(theirs, his))
                    if (a is None) != (b is None) or (a is not None and abs(a - b) > 1e-6)]
            print("\nper-trade agreement vs their rows: %d/%d identical, %d differ"
                  % (len(his) - len(diff), len(his), len(diff)))
            if diff:
                print("  first 5 diffs:", [(i, theirs[i], his[i]) for i in diff[:5]])
        else:
            print("\nrow-count mismatch: theirs=%d mine=%d" % (len(theirs), len(his)))


if __name__ == "__main__":
    main()
