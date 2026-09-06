"""L2 referee pass 4 -- the reclaim-tolerance semantics, checked against raw bars.

For every 84%-rule row that FIRED in the ON arm, re-derive the settled test from
data_archive alone:

    |reclaim candle's close - the original entry price| <= 0.25 * (previous
    candle's high - previous candle's low)

"previous candle" = the bar immediately before the reclaim bar (signal_runner
passes `self.candles[-2]` while `current` is `self.candles[-1]`; verified at
signal_runner.py:3095).  Also checks the off-by-one alternative (two bars back)
so a wrong-candle implementation would show up as the better fit, and checks the
OFF-arm fires the flag REMOVED to confirm they fail the same test.

Run:  python research/l2_referee4_bars.py
"""
from __future__ import annotations

import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAPE = ROOT / "research" / "tape"
ARCH = ROOT / "data_archive"
FRAC = 0.25


def load(name):
    with gzip.open(TAPE / name, "rt", encoding="utf-8") as f:
        return json.load(f)["trades"]


_cache = {}


def bars(sym, day):
    k = (sym, day)
    if k in _cache:
        return _cache[k]
    p = ARCH / sym / ("%s.csv" % day)
    out = {}
    if p.exists():
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                hhmm = row["Datetime"][11:16]
                out[hhmm] = (float(row["High"]), float(row["Low"]),
                             float(row["Close"]))
    _cache[k] = out
    return out


def minus1(hhmm):
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    m -= 1
    if m < 0:
        h, m = h - 1, 59
    return "%02d:%02d" % (h, m)


def check(rows, label):
    fires = [r for r in rows
             if r.get("setup") == "reentry_84_rule" and r.get("status") == "fired"]
    ok = off_by_one_only = miss = nobars = 0
    worst = []
    for r in fires:
        b = bars(r["sym"], r["day"])
        et = r.get("et")
        p1, p2 = minus1(et), minus1(minus1(et))
        if et not in b or p1 not in b:
            nobars += 1
            continue
        close = b[et][2]
        orig = r.get("level_px")
        gap = abs(close - orig)
        tol1 = FRAC * (b[p1][0] - b[p1][1])
        tol2 = FRAC * (b[p2][0] - b[p2][1]) if p2 in b else None
        if gap <= tol1 + 1e-9:
            ok += 1
        elif tol2 is not None and gap <= tol2 + 1e-9:
            off_by_one_only += 1
            worst.append((r["sym"], r["day"], et, round(gap, 4), round(tol1, 4),
                          round(tol2, 4), "PASSES ONLY on the bar-2 reading"))
        else:
            miss += 1
            worst.append((r["sym"], r["day"], et, round(gap, 4), round(tol1, 4),
                          round(tol2, 4) if tol2 is not None else None, "fails both"))
    print("%s: %d fires | tolerance holds on the PREVIOUS bar %d | only on two-bars-back %d "
          "| fails both %d | no archived bars %d" % (label, len(fires), ok, off_by_one_only, miss, nobars))
    for w in worst:
        print("    ", w)
    return fires


def removed_check(off_rows, on_rows):
    """The 84% fires the flag removed: do they fail the settled tolerance?
    (Some are removed by the S/A arm gate instead -- those may still pass the
    tolerance, which is expected, so this only reports the split.)"""
    def k(r):
        return (r["sym"], r["day"], r.get("et"), round(r.get("entry") or 0, 4))
    on_k = {k(r) for r in on_rows
            if r.get("setup") == "reentry_84_rule" and r.get("status") == "fired"}
    gone = [r for r in off_rows
            if r.get("setup") == "reentry_84_rule" and r.get("status") == "fired"
            and k(r) not in on_k]
    pass_tol = fail_tol = nobars = 0
    for r in gone:
        b = bars(r["sym"], r["day"])
        et, p1 = r.get("et"), minus1(r.get("et"))
        if et not in b or p1 not in b:
            nobars += 1
            continue
        gap = abs(b[et][2] - r.get("level_px"))
        if gap <= FRAC * (b[p1][0] - b[p1][1]) + 1e-9:
            pass_tol += 1
        else:
            fail_tol += 1
    print("OFF-arm 84%% fires the flag removed: %d | still inside the 25%%-of-previous-candle "
          "tolerance (so removed by the S/A arm gate, not the tolerance): %d | outside it: %d "
          "| no archived bars: %d" % (len(gone), pass_tol, fail_tol, nobars))


def main():
    off = load("book_RULE84_DECIDED_off.json.gz")
    on = load("book_RULE84_DECIDED_on.json.gz")
    check(on, "ON  arm")
    check(off, "OFF arm")
    removed_check(off, on)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
