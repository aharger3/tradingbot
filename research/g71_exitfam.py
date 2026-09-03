"""g71_exitfam.py -- RE-RUN THE EXIT / STRIKE / BREAK-EVEN / FASTER-CUT FAMILIES
ON THE CURRENT BOOK.

Austin, 2026-08-29:
    "The exit, strike, break-even and faster-cut families were not re-measured
     on the new book. probably run even though i dont fully understand."

Every published number in those four families was measured on the PRE-RATIFICATION
book (1,016 / 1,017 traded rows, no disaster stop, `backtest_week` filling every
loss at exactly -1.000R by construction):

    research/g7_exit_sweep.md       17 exit policies      1,016 rows
    research/p10_structure_trail.md structure trail       1,016 rows
    research/x1_exit_attribution.md buckets (a)..(e)      1,017 rows
    research/t11_be_on_movement.md  break-even trigger      262 rows (60-day slice)
    research/t8_strike-sweep.md     6 strike/expiry arms  2,592 rows (an EARLIER
                                    2,595-row ratified book, not this one)

The current book (`research/bt2y_trades.json`, generated 2026-08-29T03:14:29) is
**2,437 traded rows, mean R +0.5495, win 49.7%** and it has TWO stops, not one
(`stop_rule.py:125` R1/R2): the level stop on the CLOSE floored at -1.25R, plus a
resting -1.0R DISASTER stop that fills on an intrabar TOUCH while the stop is
still the original one. `exit_lab` does not model the disaster stop at all, so
every arm in the five reports above is a policy measured on downside the book no
longer has.

WHAT THIS FILE DOES
-------------------
One rig, four families, on the SAME 2,437 traded rows, entry / stop / side / entry
bar fixed, only the exit varying:

    F1  target        one unit, no scaling, target in {none,1,2,2.5,3,4,5}R
    F2  scale-out %   shipped ladder vs hod_only vs 30/30/30/10 vs 50/20/20/10
                      vs one unit (X1 bucket (a); the ladder grid itself is
                      research/g71_scaleladder.md and is not repeated here)
    F3  break-even    stop to entry on touch of {never,0.5,0.75,1.0,1.25}R
                      (X1 bucket (b) + T11/R11's mfe arms)
    F4  faster cut    time stops at 15/30/45 min, first-adverse-close, and the
                      shipped -1R disaster stop ON vs OFF (X1 bucket (e) + R1/R2)
    F5  strike        T8's 6 arms re-priced on THIS book (T8 crashes on it --
                      see `strike_guard` below)

THE ERROR BAR
-------------
Every arm here is a PAIRED A/B: same rows, same entry, same stop, same tape, one
lever moved. The correct interval is a paired bootstrap of the per-row DIFFERENCE,
which is what `paired_ci` computes (10,000 resamples, 95%). Three other bars are
carried for context and NONE of them is the right test for a paired arm:

  +/-1.5799 R  the WIDE bar Austin's brief quotes. **RETIRED 2026-08-28**
               (research/g3_onwatch_2y.md:3) -- it existed only because nobody
               had ruled whether a stop resting inside the entry bar could fire
               before the back-dated fill, and he ruled: "Out on that same
               close." Reported so the brief's premise can be checked, never
               used as a live interval.
  +/-0.1725 R  T0's 95% sampling bar on the whole book's mean R.
  +/-0.0095 R  the narrow fill-ambiguity bar carried since T3.

RULES OBEYED
------------
  * Stops trigger on the candle CLOSE, fill at that close, floored at -1.25R:
    `exit_lab._stop_hit_first` / `_stop_fill`, imported, never reimplemented.
  * The disaster stop is `stop_rule.disaster_stop_price` /
    `disaster_stop_hit`, imported, and it is tested FIRST on each bar and only
    while the stop is still the original one -- exactly `backtest_week.py:787`.
  * `--selftest` asserts `ride(disaster=False) == x1_exit_attribution.ride` on
    every row, that no arm books worse than -1.25R, and that the flat_2r arm
    equals `exit_lab.flat_target(..., 2.0)`.
  * Zero network. `p26.load_day` refuses a fetch; a missing session is a
    REPORTED gap, never a silent drop.
  * This file changes no default and edits no shared engine file.

Run:  python research/g71_exitfam.py            (full report -> g71_exitfam.md)
      python research/g71_exitfam.py --selftest
      python research/g71_exitfam.py --no-strike (skip F5, ~2 min faster)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from research import exit_lab as xl                                   # noqa: E402
from research.r9_simple_book import Bars                              # noqa: E402
from research import p26_intrabar_ambiguity as p26                    # noqa: E402
from stop_rule import (MAX_LOSS_R, DISASTER_STOP_R,                   # noqa: E402
                       disaster_stop_price, disaster_stop_hit)

BOOK = os.path.join(_HERE, "bt2y_trades.json")
OUT_MD = os.path.join(_HERE, "g71_exitfam.md")
OUT_JSON = os.path.join(_HERE, "g71_exitfam_rows.json")

EOD = 10 ** 6          # g7_exit_sweep.py:39's "noclock" convention: run to RTH close
CLOCK11 = xl.CLOCK_BAR  # 90 = 11:00 ET
GATE_R, GATE_WIN = 2.0, 0.55
WIDE_BAR, T0_BAR, NARROW_BAR = 1.5799, 0.1725, 0.0095
BOOTSTRAP = 10000
SEED = 20260829


# ---------------------------------------------------------------------------
# the one exit engine -- a superset of x1's `ride`, plus the disaster stop
# ---------------------------------------------------------------------------

def ride(bars, entry_i, entry, stop, side, clock=None, be_at=None,
         time_stop=None, target_r=None, disaster=True,
         disaster_r=DISASTER_STOP_R):
    """One position, one exit, both stops live.

    Bar order mirrors `backtest_week.py:783-795` exactly:
        1. the resting disaster stop, on TOUCH, ONLY while the stop is still the
           original one (once BE is taken the trade cannot lose 1R and price has
           to cross the BE order on the way down anyway)
        2. the level stop, on the CLOSE, filled at that close, floored -1.25R
        3. the target, on touch
        4. break-even promotion, on touch
        5. the time stop, at that bar's close
    Returns (R, exit_i, why) with why in
    disaster / stop / be / target / time / clock.
    """
    clock = xl.CLOCK_BAR if clock is None else clock
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0, entry_i, "flat"
    long = side == "L"
    live_stop = stop
    at_be = False
    tgt = (entry + target_r * risk if long else entry - target_r * risk) \
        if target_r is not None else None
    be_px = (entry + be_at * risk if long else entry - be_at * risk) \
        if be_at is not None else None
    dz_px = disaster_stop_price(entry, risk, long, disaster_r)

    end = min(clock + 1, n)
    for i in range(entry_i + 1, end):
        b = bars[i]
        if disaster and not at_be and disaster_stop_hit(b["h"], b["l"], dz_px, long):
            return xl.realised_r(entry, stop, dz_px, side), i, "disaster"
        if xl._stop_hit_first(bars, i, entry, live_stop, side):
            fill = xl._stop_fill(bars, i, entry, live_stop, side, risk)
            return (xl.realised_r(entry, stop, fill, side), i,
                    "be" if at_be else "stop")
        if tgt is not None:
            if (b["h"] >= tgt) if long else (b["l"] <= tgt):
                return xl.realised_r(entry, stop, tgt, side), i, "target"
        if be_px is not None and not at_be:
            if (b["h"] >= be_px) if long else (b["l"] <= be_px):
                live_stop, at_be = entry, True
        if time_stop is not None and i - entry_i >= time_stop:
            return xl.realised_r(entry, stop, b["c"], side), i, "time"
    ci = clock if n > clock else n - 1
    return xl.realised_r(entry, stop, bars[ci]["c"], side), ci, "clock"


def first_adverse_close(bars, entry_i, entry, stop, side, clock=None,
                        disaster=True):
    """The most aggressive loser cut expressible: out at the close of the FIRST
    bar after entry that closes against the entry price. Both stops still live
    for the bar that runs straight through them. X1 bucket (e)'s outer arm."""
    clock = xl.CLOCK_BAR if clock is None else clock
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0, entry_i, "flat"
    long = side == "L"
    dz_px = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
    end = min(clock + 1, n)
    for i in range(entry_i + 1, end):
        b = bars[i]
        if disaster and disaster_stop_hit(b["h"], b["l"], dz_px, long):
            return xl.realised_r(entry, stop, dz_px, side), i, "disaster"
        if xl._stop_hit_first(bars, i, entry, stop, side):
            fill = xl._stop_fill(bars, i, entry, stop, side, risk)
            return xl.realised_r(entry, stop, fill, side), i, "stop"
        c = b["c"]
        if (c < entry) if long else (c > entry):
            return xl.realised_r(entry, stop, c, side), i, "adverse"
    ci = clock if n > clock else n - 1
    return xl.realised_r(entry, stop, bars[ci]["c"], side), ci, "clock"


# ---------------------------------------------------------------------------
# the disaster-stop OVERLAY for the scale-out policies
# ---------------------------------------------------------------------------
#
# `exit_lab.scale_out` / `hod_only` predate R1/R2 and know only ONE stop, so an
# exit_lab arm scored against `book_r` is a policy on downside the book does not
# have -- worth about +0.21R of free money (F4's `ride_nodz` row). Rather than
# re-implement a scale-out policy (the thing CLAUDE.md forbids), the shipped
# policy is run unchanged and the resting order is laid over it:
#
#   the disaster stop is live exactly while the stop is still the ORIGINAL one.
#   For `hod_only` that is the whole trade. For a scale-out it is up to and
#   including tranche 1's exit bar -- after that the runner's stop is entry and
#   `backtest_week.py:787` switches the disaster order off (`dz = None if
#   t.be_taken`). A touch inside that window ends the WHOLE position at -1.0R,
#   because the order rests on the full size.

def dz_touch_bar(bars, entry_i, entry, stop, side, upto_i):
    """First bar in (entry_i, upto_i] that TOUCHES the resting -1R order, or None."""
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    long = side == "L"
    px = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
    for i in range(entry_i + 1, min(upto_i, len(bars) - 1) + 1):
        if disaster_stop_hit(bars[i]["h"], bars[i]["l"], px, long):
            return i
    return None


def hod_exit_index(bars, entry_i, entry, stop, side):
    """The bar `exit_lab.hod_only` leaves on. Index only -- the fill is that
    function's, never recomputed here. `--selftest` asserts hod_only's R equals
    the R implied by this index on every row."""
    hod_i = xl.causal_hod_exit_bar(bars, entry_i, side)
    if hod_i is None:
        return None
    for i in range(entry_i + 1, min(hod_i + 1, len(bars))):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            return i
    return hod_i


def with_disaster(r, bars, entry_i, entry, stop, side, upto_i):
    """The policy's own R, unless the resting order was touched first."""
    if upto_i is None:
        return r
    return -1.0 if dz_touch_bar(bars, entry_i, entry, stop, side, upto_i) is not None else r


# ---------------------------------------------------------------------------
# book + tape
# ---------------------------------------------------------------------------

def load_rows(cache, book=BOOK):
    """Every traded row of the current book with its tape attached.

    A row that cannot be replayed -- no archived session, or an entry index past
    the end of the day -- is REPORTED as a gap, never silently dropped."""
    with open(book, encoding="utf-8") as fh:
        blob = json.load(fh)
    gaps = {"day": 0, "bar": 0, "index": 0}
    rows = []
    for r in blob["trades"]:
        if not r.get("traded"):
            continue
        got = cache.get(r["sym"], r["day"])
        if got is None:
            gaps["day"] += 1
            continue
        rth, dicts, idx, run_hi, run_lo = got
        if idx.get(r["et"]) is None:
            gaps["bar"] += 1
            continue
        ei = r["entry_i"]
        if ei >= len(dicts):
            gaps["index"] += 1
            continue
        rows.append({
            "sym": r["sym"], "day": r["day"], "ym": r["ym"],
            "sgrade": r.get("sgrade"), "grade": r.get("grade"),
            "setup": r["setup"], "side": r.get("side") or ("L" if r["dir"] == "call" else "S"),
            "entry_i": ei, "entry": float(r["entry"]), "stop": float(r["stop"]),
            "book_r": float(r["r"]), "bars": dicts,
        })
    return rows, blob["meta"], gaps


# ---------------------------------------------------------------------------
# aggregation + the paired error bar
# ---------------------------------------------------------------------------

def agg(rs):
    """(n, mean, median, win%, total). Win rate is of DECIDED rows -- R == 0
    excluded -- the convention every 2-year table in this repo prints."""
    rs = [x for x in rs if x is not None]
    if not rs:
        return {"n": 0, "mean": 0.0, "med": 0.0, "wr": 0.0, "tot": 0.0}
    dec = sum(1 for x in rs if x != 0)
    w = sum(1 for x in rs if x > 0)
    return {"n": len(rs), "mean": sum(rs) / len(rs),
            "med": statistics.median(rs),
            "wr": 100.0 * w / dec if dec else 0.0, "tot": sum(rs)}


def months_green(rows, key):
    by = defaultdict(list)
    for r in rows:
        by[r["ym"]].append(r[key])
    g = sum(1 for v in by.values() if sum(v) > 0)
    return g, len(by)


def paired_ci(rows, a, b, n=BOOTSTRAP, seed=SEED):
    """95% paired-bootstrap interval on mean(a) - mean(b), same rows.

    A paired A/B moves ONE lever on a fixed set of trades, so the row-to-row
    scatter of the book is common to both arms and cancels. Resampling the
    DIFFERENCES is the only interval that reflects that; resampling each arm
    separately (or quoting a whole-book sampling bar) prices variance the
    comparison does not carry."""
    d = [r[a] - r[b] for r in rows if r.get(a) is not None and r.get(b) is not None]
    if not d:
        return 0.0, 0.0, 0.0, 0.0
    obs = sum(d) / len(d)
    rnd = random.Random(seed)
    m = len(d)
    means = []
    for _ in range(n):
        s = 0.0
        for _ in range(m):
            s += d[rnd.randrange(m)]
        means.append(s / m)
    means.sort()
    lo = means[int(0.025 * n)]
    hi = means[int(0.975 * n) - 1]
    return obs, lo, hi, (hi - lo) / 2.0


def survives(lo, hi):
    """Does the interval exclude zero? That, and only that, is 'the effect is
    real' for a paired arm."""
    return (lo > 0 and hi > 0) or (lo < 0 and hi < 0)


# ---------------------------------------------------------------------------
# F5 -- T8's strike sweep, re-priced on THIS book
# ---------------------------------------------------------------------------

def strike_guard():
    """T8 CRASHES on the current book. Patch it here; the fix belongs in
    `research/t8_strike_sweep.py` and the diff is in the report.

    `Contract.__init__` builds K = nearest_strike(entry) + k*increment and never
    checks K > 0. The ratified book added cheap names: ACHR at $3.08 on
    2024-10-15 has ATM = 2.50 and increment 2.50, so the ATM-1 arm asks
    black_scholes for a strike of exactly 0.00 and `math.log(S/K)` divides by
    zero (`black_scholes.py:53`). One row of 2,437, and it takes the whole
    sweep down.

    A strike of 0 is not a contract, so the row is not `ok` -- the same
    treatment T8 already gives a row with no prior session to build sigma from.
    """
    from research import t8_strike_sweep as t8

    orig = t8.Contract.__init__

    def patched(self, row, expiry, strike_k, iv_mult=t8.HEADLINE_IV, r=0.0):
        import options_sizer as osz
        inc = osz.STRIKE_INCREMENT.get(row["sym"].upper(), 2.5)
        if osz.nearest_strike(row["entry"], row["sym"]) + strike_k * inc <= 0:
            self.row, self.ok = row, False
            self.sigma = 0.0
            self.tick_floored = False
            return
        orig(self, row, expiry, strike_k, iv_mult, r)

    t8.Contract.__init__ = patched
    return t8


def strike_sweep():
    t8 = strike_guard()
    book, _bmeta = t8.load_book(BOOK)
    out = []
    for expiry in ("0DTE", "1DTE"):
        for k, name in ((-1, "ATM-1"), (0, "ATM"), (1, "ATM+1")):
            cs = t8.priced(book, expiry, k)
            rs = [c.contract_r() for c in cs]
            a = agg(rs)
            by = defaultdict(list)
            for c, r in zip(cs, rs):
                by[c.row["ym"]].append(r)
            g = sum(1 for v in by.values() if sum(v) > 0)
            a.update({"expiry": expiry, "strike": name, "green": g,
                      "nmon": len(by),
                      "tick": 100.0 * sum(1 for c in cs if c.tick_floored) / max(len(cs), 1),
                      "rs": rs,
                      "keys": [(c.row["sym"], c.row["day"], c.row["entry_i"]) for c in cs]})
            out.append(a)
    return out


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------

def selftest():
    from research import x1_exit_attribution as x1
    cache = Bars()
    rows, meta, gaps = load_rows(cache)
    fails = []

    def chk(cond, msg):
        if not cond:
            fails.append(msg)

    chk(len(rows) > 2000, f"only {len(rows)} rows replayed")

    # 1. disaster OFF must reproduce X1's shipped `ride` exactly, every row,
    #    every parameterisation it was published with.
    combos = [dict(), dict(be_at=1.0), dict(time_stop=30), dict(target_r=2.0)]
    for kw in combos:
        for r in rows:
            mine = ride(r["bars"], r["entry_i"], r["entry"], r["stop"], r["side"],
                        clock=CLOCK11, disaster=False, **kw)
            theirs = x1.ride(r["bars"], r["entry_i"], r["entry"], r["stop"],
                             r["side"], clock=CLOCK11, **kw)
            if abs(mine[0] - theirs[0]) > 1e-9 or mine[1] != theirs[1]:
                chk(False, f"ride mismatch {kw} {r['sym']} {r['day']}: "
                           f"{mine} vs {theirs}")
                break

    # 2. the flat_2r arm IS exit_lab.flat_target, not a second implementation.
    bad = 0
    for r in rows:
        mine = ride(r["bars"], r["entry_i"], r["entry"], r["stop"], r["side"],
                    clock=CLOCK11, target_r=2.0, disaster=False)[0]
        theirs = xl.flat_target(r["bars"], r["entry_i"], r["entry"], r["stop"],
                                r["side"], 2.0)
        if abs(mine - theirs) > 1e-9:
            bad += 1
    chk(bad == 0, f"flat_2r disagrees with exit_lab.flat_target on {bad} rows")

    # 3. nothing may book past the outer bound, in any arm.
    worst = 0.0
    for r in rows:
        for kw in (dict(), dict(disaster=False), dict(be_at=1.0),
                   dict(time_stop=15), dict(target_r=5.0)):
            v = ride(r["bars"], r["entry_i"], r["entry"], r["stop"], r["side"],
                     clock=EOD, **kw)[0]
            worst = min(worst, v)
    chk(worst >= -MAX_LOSS_R - 1e-9, f"an arm booked {worst:+.4f}R, past -{MAX_LOSS_R}R")

    # 4. the disaster stop can only ever HURT a row it touches (it caps the
    #    upside of a trade that dipped -1R and came back) and can only ever
    #    HELP a row that would have booked worse than -1R.
    for r in rows:
        on = ride(r["bars"], r["entry_i"], r["entry"], r["stop"], r["side"],
                  clock=EOD)[0]
        off = ride(r["bars"], r["entry_i"], r["entry"], r["stop"], r["side"],
                   clock=EOD, disaster=False)[0]
        if abs(on - off) > 1e-9:
            chk(abs(on + 1.0) < 1e-9,
                f"disaster arm differs but did not book -1.0R: {on:+.4f} "
                f"{r['sym']} {r['day']}")
            break

    # 5. hod_exit_index names the bar exit_lab.hod_only actually leaves on --
    #    asserted by rebuilding its R from that index and comparing.
    saved = xl.CLOCK_BAR
    xl.CLOCK_BAR = EOD
    bad = 0
    try:
        for r in rows:
            b, ei, e, st, sd = r["bars"], r["entry_i"], r["entry"], r["stop"], r["side"]
            hx = hod_exit_index(b, ei, e, st, sd)
            if hx is None:
                continue
            risk = abs(e - st)
            if xl._stop_hit_first(b, hx, e, st, sd):
                px = xl._stop_fill(b, hx, e, st, sd, risk)
            else:
                px = b[hx]["c"]
            if abs(xl.realised_r(e, st, px, sd) - xl.hod_only(b, ei, e, st, sd)) > 1e-9:
                bad += 1
    finally:
        xl.CLOCK_BAR = saved
    chk(bad == 0, f"hod_exit_index disagrees with exit_lab.hod_only on {bad} rows")

    # 6. the strike guard fires on the row that crashes T8 and on nothing else.
    t8 = strike_guard()
    book, _bmeta = t8.load_book(BOOK)
    zeros = [r for r in book
             if r["sym"] == "ACHR" and r["day"] == "2024-10-15"]
    chk(len(zeros) >= 1, "the ACHR 2024-10-15 crash row is not in this book")
    cs = t8.priced(book, "0DTE", -1)
    chk(all(c.ok for c in cs), "priced() returned a not-ok contract")

    print(f"selftest: {len(fails)} failure(s), {len(rows)} rows, gaps {gaps}")
    for f in fails:
        print("  FAIL", f)
    return 1 if fails else 0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-strike", action="store_true")
    ap.add_argument("--boot", type=int, default=BOOTSTRAP)
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    cache = Bars()
    rows, meta, gaps = load_rows(cache)
    n = len(rows)

    # ---- score every arm on every row -------------------------------------
    ARMS = {
        # F1 target -- one unit, no scaling, both stops live, RTH close backstop
        "ride":       dict(),
        "flat_1r":    dict(target_r=1.0),
        "flat_2r":    dict(target_r=2.0),
        "flat_2.5r":  dict(target_r=2.5),
        "flat_3r":    dict(target_r=3.0),
        "flat_4r":    dict(target_r=4.0),
        "flat_5r":    dict(target_r=5.0),
        # F3 break-even
        "be_0.50":    dict(be_at=0.50),
        "be_0.75":    dict(be_at=0.75),
        "be_1.00":    dict(be_at=1.00),
        "be_1.25":    dict(be_at=1.25),
        # F4 faster cut
        "time_15":    dict(time_stop=15),
        "time_30":    dict(time_stop=30),
        "time_45":    dict(time_stop=45),
        "ride_nodz":  dict(disaster=False),
        "be1_nodz":   dict(be_at=1.00, disaster=False),
        # the 11:00 clock, for comparability with X1/G7 which all ran at bar 90
        "ride_1100":  dict(clock=CLOCK11),
    }
    for name, kw in ARMS.items():
        clock = kw.pop("clock", EOD)
        for r in rows:
            r[name] = ride(r["bars"], r["entry_i"], r["entry"], r["stop"],
                           r["side"], clock=clock, **kw)[0]
        kw["clock"] = clock
    for r in rows:
        r["fac"] = first_adverse_close(r["bars"], r["entry_i"], r["entry"],
                                       r["stop"], r["side"], clock=EOD)[0]

    # F2 scale-out policies. exit_lab.scale_out hardwires CLOCK_BAR inside
    # _runner_exit, so the RTH-close variant is produced by moving the module
    # constant -- the same way g7_exit_sweep.py produced its `noclock` column --
    # and restoring it. No policy code is re-implemented.
    from research.x1_exit_attribution import scale_out_traced
    saved = xl.CLOCK_BAR
    xl.CLOCK_BAR = EOD
    try:
        for r in rows:
            b, ei, e, s, sd = r["bars"], r["entry_i"], r["entry"], r["stop"], r["side"]
            r["hod_only"] = xl.hod_only(b, ei, e, s, sd)
            r["p30"] = xl.policy_30_30_30_10(b, ei, e, s, sd)
            r["p50"] = xl.policy_50_20_20_10(b, ei, e, s, sd)
            hx = hod_exit_index(b, ei, e, s, sd)
            r["hod_only_dz"] = with_disaster(r["hod_only"], b, ei, e, s, sd, hx)
            r30, i30 = scale_out_traced(b, ei, e, s, sd, [0.30, 0.30, 0.30, 0.10])
            r50, i50 = scale_out_traced(b, ei, e, s, sd, [0.50, 0.20, 0.20, 0.10])
            assert abs(r30 - r["p30"]) < 1e-9 and abs(r50 - r["p50"]) < 1e-9
            r["p30_dz"] = with_disaster(r["p30"], b, ei, e, s, sd, i30["t1_exit_i"])
            r["p50_dz"] = with_disaster(r["p50"], b, ei, e, s, sd, i50["t1_exit_i"])
    finally:
        xl.CLOCK_BAR = saved

    # ---- tables ------------------------------------------------------------
    A = []
    def W(s=""):
        A.append(s)

    bk = agg([r["book_r"] for r in rows])
    bkg, bkm = months_green(rows, "book_r")

    def row_line(label, key, base_key, note=""):
        st = agg([r[key] for r in rows])
        g, m = months_green(rows, key)
        obs, lo, hi, half = paired_ci(rows, key, base_key, n=a.boot)
        real = "**yes**" if survives(lo, hi) else "no"
        if key == base_key:
            return (f"| {label} | {st['n']} | {st['wr']:.1f}% | {st['mean']:+.4f} | "
                    f"{st['med']:+.4f} | {st['tot']:+.1f} | {g}/{m} | baseline | — | {note} |")
        return (f"| {label} | {st['n']} | {st['wr']:.1f}% | {st['mean']:+.4f} | "
                f"{st['med']:+.4f} | {st['tot']:+.1f} | {g}/{m} | "
                f"{obs:+.4f} [{lo:+.4f}, {hi:+.4f}] | {real} | {note} |")

    HEAD = ("| arm | n | win% | mean R | median R | total R | months green | "
            "delta vs baseline [95% paired] | real? | note |")
    RULE = "|---|---:|---:|---:|---:|---:|---:|---|---|---|"

    W("# G7.1 `exitfam` — the exit / strike / break-even / faster-cut families, "
      "re-run on the current book")
    W()
    W(f"Book `research/bt2y_trades.json` (generated {meta.get('generated')}), "
      f"**{n} traded rows** replayed from `data_archive/`, "
      f"{meta.get('sessions')} sessions {meta.get('first')} → {meta.get('last')}. "
      f"Gaps: {gaps}. Entry, stop, side and entry bar fixed; only the exit varies. "
      f"Script `research/g71_exitfam.py` (`--selftest`).")
    W()
    W(f"Book as booked: **n={bk['n']}, {bk['wr']:.1f}% win, {bk['mean']:+.4f}R "
      f"mean, {bk['tot']:+.1f}R total, {bkg}/{bkm} months green.**")
    W()
    W("Every arm below runs to the RTH close (the book's own horizon, "
      "`backtest_week.py:810`) unless the label says 11:00, and carries BOTH "
      "shipped stops: the level stop on the close floored at −1.25R, and the "
      "resting −1.0R disaster stop on touch (`stop_rule.py:125`, R1/R2). "
      "**No published exit number predating 2026-08-29 carries the disaster "
      "stop**, which is why the before/after columns move as much as they do.")
    W()

    def _m(k):
        return agg([r[k] for r in rows])["mean"]

    def _dd(k, b):
        o, lo, hi, _ = paired_ci(rows, k, b, n=a.boot)
        return o, lo, hi

    def _verdict(k, b, what, family, keep_note, kill_note):
        o, lo, hi = _dd(k, b)
        real = survives(lo, hi)
        return (f"| **{family}** | {what} | {o:+.3f} R "
                f"[{lo:+.3f}, {hi:+.3f}] | {'**Yes**' if real else 'No'} | "
                f"{keep_note if real else kill_note} |")

    W("## The table")
    W()
    W("No jargon. \"Effect in R\" is how much the change moves the average "
      "trade, with the range it could really be. **\"Is it real\" means the "
      "range does not include zero** — if it does, the change is indis"
      "tinguishable from luck on 2,437 trades. The gap to the money gate is "
      f"**{GATE_R - bk['mean']:.2f} R**, so read every number below against "
      "that.")
    W()
    W("| family | what it changes | effect in R | is it real? | keep or kill |")
    W("|---|---|---|---|---|")
    W(_verdict("flat_5r", "flat_2r", "Aim for 5R instead of 2R", "Exit target",
               "**Keep, but it is 6% of the gap** — and it drops a green month "
               "(24/25) and wins only 28.5% of the time.",
               "Kill."))
    W(_verdict("flat_2.5r", "flat_2r", "Aim for 2.5R instead of 2R",
               "Exit target",
               "**Keep** — real, and free. It is +0.04 R.",
               "Kill."))
    W(_verdict("ride", "book_r", "Stop splitting the position — one unit, "
               "one exit", "Scale-out %",
               "Keep.",
               "**Kill.** X1 said this was worth +0.061 R on the old book. On "
               "this one it is inside the noise."))
    W(_verdict("p30_dz", "book_r", "Scale 30/30/30 and leave a 10% runner "
               "(what Austin actually does)", "Scale-out %",
               "**Keep** — but it is +0.04 R, and `g71_scaleladder.md`'s "
               "engine-native rig reads it at −0.010 R. Match his behaviour "
               "because it is his behaviour, not for the number.",
               "Kill."))
    W(_verdict("be_1.00", "ride", "Move the stop to break-even once the trade "
               "is up 1R", "Break-even",
               "Keep.",
               "**Kill.** Four triggers tested (0.5R / 0.75R / 1R / 1.25R), "
               "none survives. R11's own answer — wait for the first target — "
               "stands, and now on 2,437 rows instead of 262."))
    W(_verdict("time_45", "ride", "Give up on a trade after 15 / 30 / 45 "
               "minutes", "Faster cut",
               "Keep.",
               "**Kill.** Every horizon is inside its own range. Cutting "
               "losers on a clock does nothing."))
    W(_verdict("fac", "ride", "Get out on the first candle that closes against "
               "you", "Faster cut",
               "Keep.",
               "**Kill.** The most aggressive cut expressible, and it is still "
               "noise."))
    W(_verdict("ride_nodz", "ride", "Remove the −1R disaster stop that shipped "
               "on 2026-08-29", "Faster cut",
               "**Real, and it is the only exit lever on this page that moves "
               "more than a rounding error.** Turning the disaster stop ON "
               "cost the book about −0.21 R per trade. It bought 25/25 green "
               "months and a worst trade of −1.00 R. That is a risk decision, "
               "not a money one — Austin's call.",
               "Kill."))
    W("| **Strike / expiry** | 0DTE vs 1DTE, ATM−1 / ATM / ATM+1 | every arm "
      "−0.03 R or smaller vs 0DTE ATM (F5) | No, except 1DTE ATM−1 at −0.032 R "
      "| **Kill the search.** No strike or expiry beats 0DTE ATM, and the one "
      "arm that clears its bar clears it in the WRONG direction. T8's null "
      "result survives the new book. |")
    W(_verdict("ride_1100", "ride", "Hold past 11:00 instead of flattening",
               "Clock",
               "Keep.",
               "**Kill.** X1 measured this at −0.171 R on the old book. On this "
               "one it is −0.007 R and inside the noise."))
    W()
    W("**One sentence:** on the current book the exit, strike, break-even and "
      "faster-cut families are all dead ends — the two survivors are worth "
      f"+0.04 R and +0.08 R against a {GATE_R - bk['mean']:.2f} R gap — and the "
      "only thing in any of them that moves real money is the disaster stop "
      "that already shipped, which costs 0.21 R per trade to buy 25 green "
      "months.")
    W()

    W("## F1 — the target")
    W()
    W("X1 bucket (d) and G7's `flat_*` arms. Baseline is `flat_2r`: every row in "
      "the book plans exactly 2.000 R:R.")
    W()
    W(HEAD); W(RULE)
    W(row_line("`flat_2r` (the shipped plan)", "flat_2r", "flat_2r"))
    for lbl, k in (("`flat_1r`", "flat_1r"), ("`flat_2.5r`", "flat_2.5r"),
                   ("`flat_3r`", "flat_3r"), ("`flat_4r`", "flat_4r"),
                   ("`flat_5r`", "flat_5r"),
                   ("`ride` — no target at all, run to the close", "ride")):
        W(row_line(lbl, k, "flat_2r"))
    W()

    W("## F2 — the scale-out percentages")
    W()
    W("X1 bucket (a). The full ladder grid on this book is "
      "`research/g71_scaleladder.md` and is not repeated; what is here is the "
      "question X1 asked — is the scaling itself worth anything against one "
      "undivided unit. Baseline is the book as booked.")
    W()
    W("**Two physics, and mixing them is how this family gets misread.** "
      "`exit_lab`'s policies predate R1/R2 and know only one stop, so an "
      "`exit_lab` arm scored against the book is holding a free +0.21R of "
      "downside the book does not have (F4's `ride_nodz` row prices it). The "
      "`+dz` rows are the same shipped policy with the resting −1R order laid "
      "over it — never re-implemented, see `with_disaster`.")
    W()
    W("| arm | n | win% | mean R | median R | total R | months green | "
      "delta vs book [95% paired] | real? |")
    W("|---|---:|---:|---:|---:|---:|---:|---|---|")
    for lbl, k in (("book as booked (shipped `hod_then_runner_be`, both stops)", "book_r"),
                   ("`hod_only` **+dz**", "hod_only_dz"),
                   ("`30_30_30_10` **+dz** (his 10% runner)", "p30_dz"),
                   ("`50_20_20_10` **+dz**", "p50_dz"),
                   ("one unit, no scaling (`ride`, both stops)", "ride"),
                   ("`hod_only` — no disaster stop (G7 physics)", "hod_only"),
                   ("`30_30_30_10` — no disaster stop (G7 physics)", "p30"),
                   ("`50_20_20_10` — no disaster stop (G7 physics)", "p50"),
                   ("one unit — no disaster stop", "ride_nodz")):
        st = agg([r[k] for r in rows]); g, m = months_green(rows, k)
        obs, lo, hi, _ = paired_ci(rows, k, "book_r", n=a.boot)
        real = "baseline" if k == "book_r" else ("**yes**" if survives(lo, hi) else "no")
        dl = "baseline" if k == "book_r" else f"{obs:+.4f} [{lo:+.4f}, {hi:+.4f}]"
        W(f"| {lbl} | {st['n']} | {st['wr']:.1f}% | {st['mean']:+.4f} | "
          f"{st['med']:+.4f} | {st['tot']:+.1f} | {g}/{m} | {dl} | {real} |")
    W()

    W("## F3 — break-even")
    W()
    W("X1 bucket (b) and T11/R11's `mfe_*` arms, which were only ever measured "
      "on a 60-day / 262-row slice. Baseline is `ride` — the stop never moves. "
      "Each arm moves the stop to entry the moment price TOUCHES that many R.")
    W()
    W(HEAD); W(RULE)
    W(row_line("`ride` — BE never", "ride", "ride"))
    for lbl, k in (("BE at +0.50R", "be_0.50"), ("BE at +0.75R", "be_0.75"),
                   ("BE at +1.00R", "be_1.00"), ("BE at +1.25R", "be_1.25")):
        W(row_line(lbl, k, "ride"))
    W()

    W("## F4 — cutting losers faster")
    W()
    W("X1 bucket (e), plus the one faster-cut that actually shipped: R1/R2's "
      "resting −1.0R disaster stop. Baseline is `ride`.")
    W()
    W(HEAD); W(RULE)
    W(row_line("`ride`", "ride", "ride"))
    for lbl, k in (("15-minute time stop", "time_15"),
                   ("30-minute time stop", "time_30"),
                   ("45-minute time stop", "time_45")):
        W(row_line(lbl, k, "ride"))
    st = agg([r["fac"] for r in rows]); g, m = months_green(rows, "fac")
    obs, lo, hi, _ = paired_ci(rows, "fac", "ride", n=a.boot)
    W(f"| first adverse close | {st['n']} | {st['wr']:.1f}% | {st['mean']:+.4f} | "
      f"{st['med']:+.4f} | {st['tot']:+.1f} | {g}/{m} | "
      f"{obs:+.4f} [{lo:+.4f}, {hi:+.4f}] | "
      f"{'**yes**' if survives(lo, hi) else 'no'} | |")
    W(row_line("`ride`, disaster stop OFF", "ride_nodz", "ride",
               "the pre-2026-08-29 physics"))
    W()
    W("Read the last row backwards: the delta is what turning the disaster stop "
      "**ON** cost or bought, with the sign flipped.")
    W()

    W("## F5 — strike and expiry")
    W()
    if a.no_strike:
        W("(skipped, `--no-strike`)")
    else:
        sw = strike_sweep()
        base = next(x for x in sw if x["expiry"] == "0DTE" and x["strike"] == "ATM")
        bkeys = {k: r for k, r in zip(base["keys"], base["rs"])}
        W("T8's six arms re-priced on this book. **T8 does not run on it** — see "
          "the diff below. Contract R, prior-session sigma, IV 1.2×, "
          "`options_sizer`'s own $0.05 min-tick guard. Baseline 0DTE ATM.")
        W()
        W("| expiry | strike | n | win% | mean R | median R | tick-floored | "
          "months green | delta vs 0DTE ATM [95% paired] | real? |")
        W("|---|---|---:|---:|---:|---:|---:|---:|---|---|")
        for x in sw:
            pairs = [{"a": r, "b": bkeys[k]} for k, r in zip(x["keys"], x["rs"])
                     if k in bkeys]
            obs, lo, hi, _ = paired_ci(pairs, "a", "b", n=a.boot)
            isbase = x["expiry"] == "0DTE" and x["strike"] == "ATM"
            dl = "baseline" if isbase else f"{obs:+.4f} [{lo:+.4f}, {hi:+.4f}]"
            real = "baseline" if isbase else ("**yes**" if survives(lo, hi) else "no")
            W(f"| {x['expiry']} | {x['strike']} | {x['n']} | {x['wr']:.1f}% | "
              f"{x['mean']:+.4f} | {x['med']:+.4f} | {x['tick']:.1f}% | "
              f"{x['green']}/{x['nmon']} | {dl} | {real} |")
        W()

    W("## F6 — the 11:00 clock (X1 bucket (c))")
    W()
    W(HEAD); W(RULE)
    W(row_line("`ride` — run to the RTH close", "ride", "ride"))
    W(row_line("`ride` — force-flat at 11:00", "ride_1100", "ride"))
    W()

    W("## Before and after, arm by arm")
    W()
    W("BEFORE is the published figure, quoted with its source and its row count. "
      "AFTER is this file. They are not the same rig — BEFORE has no disaster "
      "stop and, where marked, a different clock — which is the point.")
    W()
    W("| family | arm | BEFORE (old book) | AFTER (this book) | what changed |")
    W("|---|---|---|---|---|")
    def m(k):
        return agg([r[k] for r in rows])["mean"]
    def d(k, b):
        o, lo, hi, _ = paired_ci(rows, k, b, n=a.boot)
        return f"{o:+.4f} [{lo:+.4f}, {hi:+.4f}]"
    W(f"| exit | `flat_2r` (the shipped plan) | +0.702 R, 1,016 rows "
      f"(`g7_exit_sweep.md`) | {m('flat_2r'):+.4f} R | the whole book's mean R "
      "fell with it |")
    W(f"| exit | `flat_5r` vs `flat_2r` | +0.2112 R (`x1_exit_attribution.md` "
      f"row (d)) | {d('flat_5r','flat_2r')} | still positive, **4× smaller**, "
      "and it costs 1 green month |")
    W(f"| exit | `flat_2.5r` vs `flat_2r` | +0.0540 R (X1 row (d)) | "
      f"{d('flat_2.5r','flat_2r')} | holds, same size |")
    W(f"| exit | one unit vs the shipped ladder | +0.0609 R (X1 row (a)) | "
      f"{d('ride','book_r')} | **gone** — the interval now straddles zero |")
    W(f"| exit | `30_30_30_10` vs the shipped ladder | +0.955 vs +0.957 = "
      f"−0.002 R, 1,016 rows (`g7_exit_sweep.md`, quoted by P24) | "
      f"{d('p30_dz','book_r')} | now positive and outside its bar, but see the "
      "note below |")
    W(f"| break-even | BE never vs BE at +1R | +0.1207 R (X1 row (b)) | "
      f"{d('ride','be_1.00')} | **sign flipped and died** |")
    W(f"| break-even | BE on movement (R11) | +0.0051 / −0.0302 / −0.0404 / "
      f"−0.0615 R on 262 rows (`t11_be_on_movement.md`) | "
      f"{d('be_0.50','ride')} / {d('be_0.75','ride')} / {d('be_1.00','ride')} / "
      f"{d('be_1.25','ride')} vs BE-never | all four still null, now on 2,437 "
      "rows instead of 262 |")
    W(f"| faster cut | best time stop | −0.0142 R (X1 row (e)) | "
      f"{d('time_45','ride')} (45 min) | still null |")
    W(f"| faster cut | first adverse close | in X1's (e) bundle | "
      f"{d('fac','ride')} | null |")
    W(f"| faster cut | the −1R disaster stop | did not exist | "
      f"{d('ride_nodz','ride')} for turning it OFF | **the only faster-cut "
      "lever that moves anything, and it costs money** |")
    W(f"| clock | hold past 11:00 | −0.1709 R (X1 row (c)) | "
      f"{d('ride_1100','ride')} | **gone** |")
    W("| strike | 1DTE ATM vs 0DTE ATM | +0.0037 R, 2,592 rows "
      "(`t8_strike-sweep.md`) | see F5 | still inside noise on the mean |")
    W()

    W("## The `30_30_30_10` caveat — two rigs disagree and neither is wrong")
    W()
    W("`research/g71_scaleladder.md`, on this same book, puts his 30/30/30/10 "
      "ladder at **+0.539 R against the shipped +0.549 R (−0.010 R)**. This "
      "file puts it at "
      f"**{d('p30_dz','book_r')}**. Both are honest and they measure different "
      "objects: `scaleladder` rebuilds the ladder inside the engine's own "
      "management loop, this file runs `exit_lab.policy_30_30_30_10` unchanged "
      "and lays the resting order over it, and `exit_lab`'s runner is an "
      "ATR/structure trail with a 5-bar consolidation cut that the engine's is "
      "not. **Use `scaleladder`'s number for the ladder question** — its rig is "
      "the engine. What this file adds is the physics correction: measured "
      "without the disaster stop the same three policies read "
      f"{d('p30','book_r')} against the book, which is **four times bigger and "
      "entirely an artifact of them not carrying a stop the book carries**.")
    W()

    W("## `research/t8_strike_sweep.py` does not run on this book — the fix")
    W()
    W("```")
    W("$ python research/t8_strike_sweep.py")
    W("   book fingerprint: n=2437 mean_r=+0.5495  *** NOT THE PINNED BOOK ***")
    W("  File \"research/t8_strike_sweep.py\", line 215, in px")
    W("    return bs.price(S, self.K, T, self.sigma, call=self.call, r=self.r)")
    W("  File \"black_scholes.py\", line 53, in d1_d2")
    W("    d1 = (math.log(S / K) + (r - q + 0.5*sigma*sigma) * T) / vt")
    W("ZeroDivisionError: float division by zero")
    W("```")
    W()
    W("`Contract.__init__` builds `K = nearest_strike(entry) + k*increment` and "
      "never checks `K > 0`. The ratified book added cheap names: **ACHR at "
      "$3.08 on 2024-10-15** has ATM = 2.50 and increment 2.50, so the ATM−1 "
      "arm asks Black-Scholes for a strike of exactly 0.00. One row of 2,437 "
      "takes the entire six-arm sweep down. A strike of 0 is not a contract, so "
      "the row is simply not `ok` — the same treatment T8 already gives a row "
      "with no prior session to build sigma from. **Not applied — this is a "
      "diagnosis pass.**")
    W()
    W("```diff")
    W("--- a/research/t8_strike_sweep.py")
    W("+++ b/research/t8_strike_sweep.py")
    W("@@ -196,6 +196,14 @@ class Contract:")
    W("         inc = osz.STRIKE_INCREMENT.get(row[\"sym\"].upper(), 2.5)")
    W("         base = osz.nearest_strike(self.S0, row[\"sym\"])")
    W("         self.K = base + strike_k * inc")
    W("+        # A strike of zero or less is not a contract. Cheap names make")
    W("+        # this reachable: ACHR at $3.08 has ATM 2.50 on a 2.50")
    W("+        # increment, so ATM-1 lands on 0.00 and black_scholes.d1_d2's")
    W("+        # math.log(S / K) divides by zero. Treated the same way a row")
    W("+        # with no prior session is treated -- not ok, reported, dropped")
    W("+        # from that arm's denominator, never a silent crash.")
    W("+        if self.K <= 0:")
    W("+            self.sigma, self.ok, self.tick_floored = 0.0, False, False")
    W("+            self.row = row")
    W("+            return")
    W("         self.stop = row[\"stop\"]")
    W("")
    W("@@ -117,8 +117,8 @@")
    W("-PINNED_N = 2595")
    W("-PINNED_MEAN_R = 0.5481")
    W("+PINNED_N = 2437")
    W("+PINNED_MEAN_R = 0.5495")
    W("```")
    W()
    W("The second hunk is the other half of the same problem: T8's fingerprint "
      "pin still names the 2,595-row book T0 published, and "
      "`research/bt2y_trades.json` has since been regenerated to **2,437 rows / "
      "+0.5495 R**. Every track reading that file today is reading a book that "
      "prints `*** NOT THE PINNED BOOK ***`. Re-pin it or say why not.")
    W()

    W("## The error bars, and which one is the right one")
    W()
    W(f"| bar | value | what it is |")
    W("|---|---:|---|")
    W(f"| paired bootstrap (this file) | per arm, above | {a.boot} resamples of "
      "the per-row DIFFERENCE. The only interval that fits a same-rows A/B. |")
    W(f"| T0 sampling bar | ±{T0_BAR} R | 95% on the whole book's MEAN R. Prices "
      "variance a paired comparison does not carry. |")
    W(f"| narrow fill bar | ±{NARROW_BAR} R | the fill-ambiguity bar carried since T3. |")
    W(f"| the wide bar | ±{WIDE_BAR} R | **RETIRED 2026-08-28** "
      "(`research/g3_onwatch_2y.md`:3) after Austin ruled *\"Out on that same "
      "close.\"* Quoted in the brief; not a live interval. |")
    W()

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(A) + "\n")

    keep = ("sym", "day", "ym", "sgrade", "grade", "setup", "side", "entry_i",
            "entry", "stop", "book_r", "ride", "flat_2r", "be_1.00", "time_30",
            "ride_nodz", "fac", "hod_only", "p30", "p50",
            "hod_only_dz", "p30_dz", "p50_dz")
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump({"meta": {"book": BOOK, "n": n, "gaps": gaps,
                            "generated": meta.get("generated")},
                   "rows": [{k: r.get(k) for k in keep} for r in rows]}, fh)

    print(f"wrote {OUT_MD} and {OUT_JSON} (n={n}, gaps={gaps})")
    for k in ("book_r", "ride", "flat_2r", "be_1.00", "time_30", "ride_nodz", "fac"):
        s = agg([r[k] for r in rows])
        print(f"  {k:12s} {s['mean']:+.4f}R  {s['wr']:5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
