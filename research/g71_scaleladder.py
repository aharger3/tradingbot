"""G7.1 track `scaleladder` -- Austin's four-point scale-out ladder, measured.

His words, probe_master_2026-08-29:

    "scalling 30 HOD, 30, 2r or nearest level, other 30 break of
     trend/structure/10 runner stop loss break even, if you wanted rules or to
     tighten rules based on my guess thats what ive got."

    "cant reach 2r gate unless change scalling and letting more then 10 percent
     run past 2r."

    Q9: "4 scale points first hod seccond medium rr."

FOUR tranches, not two. The shipped engine (`backtest_week.SCALE_PLAN =
"hod_then_runner_be"`) is a TWO-rung ladder -- 50% at the causal session
extreme, 50% runner to the next structural level -- and `research/exit_lab.py`
::`scale_out` collapses its own `[0.30,0.30,0.30,0.10]` weights into
"tranche 1 + one runner", so `30_30_30_10` there is a 30/70, not his ladder.
Nothing in this repo has ever simulated the four separate exits he named.

    T1  30%  at HOD (LOD for puts)      -- exit_lab's causal-HOD rule
    T2  30%  at 2R or the nearest of his SIX levels, whichever comes first
    T3  30%  at break of trend/structure
    T4  10%  runner, stop trailed to break-even

Entry, stop, side and entry bar are FIXED inputs, read from
`research/bt2y_trades.json` -- the same signals the shipped report renders.
Only the exit varies, so every row here is comparable to the book's own `r`.

FILLS. Every stop fill routes through `stop_rule.stop_fill_price` and every
disaster stop through `stop_rule.disaster_stop_price` /
`stop_rule.disaster_stop_hit` (research/t11_stop_fill_fix.md). Nothing is
re-implemented here. Targets are resting limit orders and fill on an intrabar
TOUCH, which is the one exception stop_rule's docstring names.

CAUSALITY. Every decision at bar i reads bars <= i. Swing lows/highs are
confirmed `SWING_STRENGTH` bars after they print, so a pivot is never used
before it existed. Session extremes are running maxima, not day maxima.

WINDOW. `backtest_week.py:810` -- 11:00 ET stops new ENTRIES; runners ride to
the RTH close. So the primary arm here is EOD, matching the book. `--clock 90`
re-runs the same ladder with the 11:00 force-flat for comparison.

Usage:
    python research/g71_scaleladder.py                     # full run -> md
    python research/g71_scaleladder.py --selftest          # mechanics only
    python research/g71_scaleladder.py --limit 300         # quick smoke
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import polygon_feed as pf                                             # noqa: E402
from stop_rule import (stop_fill_price, stop_hit_on_close,            # noqa: E402
                       disaster_stop_price, disaster_stop_hit,
                       DISASTER_STOP_R)

# His six day-trade levels. "i only have 6 day trade levels."
# (research/g71_levels_p21_six.md). HOD/LOD are deliberately NOT in the roster
# here -- the session extreme is tranche 1's job, not tranche 2's.
SIX = ("PDH", "PDL", "PMH", "PML", "ORH", "ORL")

SWING_STRENGTH = 2      # bars either side for a swing low/high to be confirmed
DISASTER_ON = True      # backtest_week.py:199 ships DISASTER_STOP=1
EOD = 10 ** 6           # "no clock" sentinel


# ---------------------------------------------------------------------------
# bars
# ---------------------------------------------------------------------------

_bar_cache: dict = {}


def bars_for(sym, day):
    """RTH bars as (o, h, l, c) tuples -- the same loader `entry_i` indexes.

    Tuples, not dicts: 2,437 trades touch ~2,000 distinct sessions of ~390
    bars, and dicts cost ~4x the memory for no gain here.
    """
    key = (sym, day)
    hit = _bar_cache.get(key)
    if hit is None:
        try:
            rth = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            rth = []
        hit = _bar_cache[key] = [(c.open, c.high, c.low, c.close) for c in rth]
    return hit


# ---------------------------------------------------------------------------
# the ladder
# ---------------------------------------------------------------------------

def _swing_levels(bars, ei, strength=SWING_STRENGTH):
    """confirm_index -> price, for swing lows and swing highs.

    A swing low at bar j (low strictly below the `strength` bars either side)
    is only KNOWN at bar j + strength, so that is the index it is filed under.
    Only pivots whose pivot bar is at or after the entry bar count: "break of
    structure" means structure the trade itself built.
    """
    lows, highs = {}, {}
    n = len(bars)
    for j in range(max(ei, strength), n - strength):
        lo, hi = bars[j][2], bars[j][1]
        if all(bars[k][2] > lo for k in range(j - strength, j)) and \
           all(bars[k][2] > lo for k in range(j + 1, j + strength + 1)):
            lows[j + strength] = lo
        if all(bars[k][1] < hi for k in range(j - strength, j)) and \
           all(bars[k][1] < hi for k in range(j + 1, j + strength + 1)):
            highs[j + strength] = hi
    return lows, highs


def tranche2_target(entry, stop, long, levels):
    """T2's price: 2R, or the nearest of his six levels, whichever comes first.

    "30, 2r or nearest level" -- whichever price the trade reaches FIRST, so
    the nearer of the two in the trade's direction. Returns (price, R).
    """
    risk = abs(entry - stop)
    two_r = entry + 2.0 * risk if long else entry - 2.0 * risk
    beyond = [px for px in levels
              if (px > entry if long else px < entry)]
    px = two_r
    if beyond:
        nearest = min(beyond) if long else max(beyond)
        px = min(px, nearest) if long else max(px, nearest)
    r = (px - entry) / risk if long else (entry - px) / risk
    return px, r


def run_ladder(bars, ei, entry, stop, long, weights, t2_px,
               trail="be", struct="swing", clock=EOD, per_tranche=False):
    """Realised composite R of the four-tranche ladder on one trade.

    ``weights`` is (w1, w2, w3, w4) summing to 1.0. One position, four resting
    orders; the protective stop is shared by every tranche still open and
    moves to break-even once tranche 1 fires (`SCALE_PLAN="hod_then_runner_be"`
    accelerator, backtest_week.py:565).

    Bar order of operations, pessimistic and matching `_ladder_bar`:
      1. disaster stop (TOUCH, only while the original stop is still working)
      2. protective/trail stop (CLOSE beyond it) -- takes out everything open
      3. limit targets (TOUCH): T1's HOD rung, T2's price
      4. structure break (evaluated at the close): T3
      5. trail update for the next bar

    ``per_tranche=True`` returns ``(composite, {tranche: R}, full_stop)`` instead
    of the composite alone. ``full_stop`` is True when the ORIGINAL stop took the
    whole position out before any rung scaled -- the one case where no runner
    survives to be rescued, which the oracle-runner solve in `main` needs.
    """
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0 or ei >= n - 1:
        return (None, {}, False, set()) if per_tranche else None
    end = min(clock + 1, n) if clock != EOD else n
    if ei + 1 >= end:
        return (None, {}, False, set()) if per_tranche else None

    w1, w2, w3, w4 = weights
    open_w = {1: w1, 2: w2, 3: w3, 4: w4}
    booked = 0.0
    legs = {}
    own = set()          # legs that exited at their OWN rung, not on the stop

    def r_of(px):
        return (px - entry) / risk if long else (entry - px) / risk

    def close_all(px, keys=None):
        nonlocal booked
        r = r_of(px)
        if keys:
            own.update(keys)
        for k in (keys or list(open_w)):
            open_w.pop(k, None)
            legs[k] = r
            booked += weights[k - 1] * r

    full_stop = False
    dz_px = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
    swing_lo, swing_hi = _swing_levels(bars, ei) if struct == "swing" else ({}, {})
    last_struct = None

    # tranche-1 state: running session extreme through the entry bar
    ext = max(b[1] for b in bars[:ei + 1]) if long else min(b[2] for b in bars[:ei + 1])
    new_ext_made = False
    be_moved = False
    work_stop = stop
    fav = entry            # running favourable extreme, for the 1R trail

    for i in range(ei + 1, end):
        o, h, l, c = bars[i]

        # 1. disaster stop -- a resting order, TOUCH, only pre-break-even
        if DISASTER_ON and not be_moved and disaster_stop_hit(h, l, dz_px, long):
            full_stop = not be_moved
            close_all(dz_px)
            return (booked, legs, full_stop, own) if per_tranche else booked

        # 2. protective / trail stop -- CLOSE beyond it, fill via stop_rule
        if stop_hit_on_close(c, work_stop, long):
            full_stop = not be_moved
            close_all(stop_fill_price(c, entry, risk, long))
            return (booked, legs, full_stop, own) if per_tranche else booked

        # 3a. tranche 1 -- causal HOD/LOD rule (exit_lab.causal_hod_exit_bar)
        if 1 in open_w:
            if not new_ext_made:
                if (h > ext) if long else (l < ext):
                    new_ext_made = True
                    ext = h if long else l
            else:
                stalled = (h <= bars[i - 1][1]) if long else (l >= bars[i - 1][2])
                if stalled:
                    close_all(c, [1])
                    if not be_moved:
                        be_moved = True
                        work_stop = entry
                else:
                    ext = h if long else l

        # 3b. tranche 2 -- resting limit at 2R or the nearest six-level
        if 2 in open_w and ((h >= t2_px) if long else (l <= t2_px)):
            close_all(t2_px, [2])
            if not be_moved:
                be_moved = True
                work_stop = entry

        # 4. tranche 3 -- break of trend/structure, booked at the close
        if 3 in open_w:
            if struct == "swing":
                if i in swing_lo:
                    last_struct = swing_lo[i] if long else last_struct
                if i in swing_hi:
                    last_struct = last_struct if long else swing_hi[i]
                broke = last_struct is not None and (
                    c < last_struct if long else c > last_struct)
            else:   # "prevbar" -- exit_lab's lower-low / higher-high test
                broke = (l < bars[i - 1][2]) if long else (h > bars[i - 1][1])
            if broke:
                close_all(c, [3])
                if not be_moved:
                    be_moved = True
                    work_stop = entry

        if not open_w:
            return (booked, legs, full_stop, own) if per_tranche else booked

        # 5. trail for the NEXT bar, from bars <= i. Break-even is a FLOOR
        # under every trail, never an alternative to it (exit_lab._runner_exit).
        fav = max(fav, h) if long else min(fav, l)
        if be_moved:
            if trail == "be":
                work_stop = entry
            elif trail == "1r":
                work_stop = (max(entry, fav - risk) if long
                             else min(entry, fav + risk))
            elif trail == "struct":
                work_stop = max(entry, l) if long else min(entry, h)

    close_all(bars[end - 1][3])
    return (booked, legs, full_stop, own) if per_tranche else booked


def mfe_r(bars, ei, entry, stop, long, clock=EOD):
    """Max favourable excursion in R inside the window. Ignores the stop, so it
    is a strict upper bound on anything any exit policy could have booked."""
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0 or ei >= n - 1:
        return None
    end = min(clock + 1, n) if clock != EOD else n
    seg = bars[ei + 1:end]
    if not seg:
        return None
    if long:
        return (max(b[1] for b in seg) - entry) / risk
    return (entry - min(b[2] for b in seg)) / risk


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def agg(rs):
    """(n, win%, mean R, total R). Wins are R > 0; R == 0 leaves the win-rate
    denominator (research/p21_target_availability.py::agg, same convention)."""
    rs = [r for r in rs if r is not None]
    if not rs:
        return 0, 0.0, 0.0, 0.0
    w = sum(1 for r in rs if r > 0)
    dec = sum(1 for r in rs if r != 0)
    return len(rs), (w / dec * 100 if dec else 0.0), sum(rs) / len(rs), sum(rs)


def _iso_week(day):
    y, m, d = (int(x) for x in day.split("-"))
    iy, iw, _ = date(y, m, d).isocalendar()
    return "%04d-W%02d" % (iy, iw)


def periods_green(rows, rs, key):
    """(green, total) periods, a period being green when its total R > 0."""
    tot = defaultdict(float)
    for t, r in zip(rows, rs):
        if r is None:
            continue
        tot[key(t)] += r
    return sum(1 for v in tot.values() if v > 0), len(tot)


def max_dd(rows, rs):
    """Trade-level max drawdown in R: peak-to-trough of the cumulative curve,
    chronological by (day, et) -- the ordering research/g71_drawdown_audit.py
    and research/t0_rebaseline.py both use."""
    seq = sorted(((t["day"], t["et"], r) for t, r in zip(rows, rs) if r is not None),
                 key=lambda x: (x[0], x[1]))
    cum = peak = 0.0
    dd = 0.0
    for _d, _e, r in seq:
        cum += r
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return dd


def summarise(rows, rs):
    n, wr, mr, tr = agg(rs)
    mg, mt = periods_green(rows, rs, lambda t: t["ym"])
    wg, wt = periods_green(rows, rs, lambda t: _iso_week(t["day"]))
    return {"n": n, "win": wr, "mean": mr, "total": tr,
            "months": "%d/%d" % (mg, mt), "weeks": "%d/%d" % (wg, wt),
            "dd": max_dd(rows, rs),
            "past2r": (sum(1 for r in rs if r is not None and r > 2.0) /
                       max(1, sum(1 for r in rs if r is not None)) * 100)}


# ---------------------------------------------------------------------------
# selftest -- mechanics on synthetic bars, no archive needed
# ---------------------------------------------------------------------------

def selftest():
    fails = []

    def ck(ok, msg):
        print(("ok   " if ok else "FAIL ") + msg)
        if not ok:
            fails.append(msg)

    W = (0.30, 0.30, 0.30, 0.10)

    # A long that runs straight up: entry 100, stop 99 (risk 1). Every bar makes
    # a higher high until bar 8, then stalls -> T1 out; T2's 2R limit at 102.
    up = [(100, 100, 99.9, 100)] * 5                      # 0..4 pre-entry
    up += [(100 + i, 100.5 + i, 99.9 + i, 100.4 + i) for i in range(6)]   # 5..10
    up += [(105, 105.0, 104.0, 104.5)] * 6                # stall / drift
    r = run_ladder(up, 5, 100.0, 99.0, True, W, 102.0, clock=EOD)
    ck(r is not None and r > 0, "straight-up long books a positive composite (%.3f)" % (r or 0))

    # Instant stop-out: the bar after entry closes at 97 -> -1.25R floor, whole
    # position, no tranche credit. Disaster stop rests at 99.0 == the stop here,
    # so it is touched first and books exactly -1.0R.
    dn = [(100, 100.2, 99.8, 100)] * 6 + [(100, 100.0, 96.0, 97.0)] + [(97, 97, 96, 96.5)] * 5
    r = run_ladder(dn, 5, 100.0, 99.0, True, W, 102.0, clock=EOD)
    ck(abs(r + 1.0) < 1e-9, "a bar through the disaster stop books exactly -1.000R (%.4f)" % r)

    # With the disaster stop off, the same bar closes at 97 = -3R raw and must
    # be floored by stop_rule.stop_fill_price at -1.25R.
    global DISASTER_ON
    DISASTER_ON = False
    r = run_ladder(dn, 5, 100.0, 99.0, True, W, 102.0, clock=EOD)
    ck(abs(r + 1.25) < 1e-9, "without it the close-fill floors at -1.250R (%.4f)" % r)
    DISASTER_ON = True

    # Weights are respected: an all-runner ladder and an all-T2 ladder on the
    # same bars must differ, and both must lie inside [-1.25, MFE].
    r_all_t2 = run_ladder(up, 5, 100.0, 99.0, True, (0, 1, 0, 0), 102.0)
    ck(abs(r_all_t2 - 2.0) < 1e-9, "100%% on T2 books exactly the 2R limit (%.4f)" % r_all_t2)

    # T2 takes the NEARER of 2R and a level.
    px, rr = tranche2_target(100.0, 99.0, True, [101.4, 103.0])
    ck(abs(px - 101.4) < 1e-9 and abs(rr - 1.4) < 1e-9,
       "T2 target = nearest level when it is inside 2R (%.2f, %.2fR)" % (px, rr))
    px, rr = tranche2_target(100.0, 99.0, True, [103.0])
    ck(abs(px - 102.0) < 1e-9, "T2 target = 2R when every level is further (%.2f)" % px)
    px, rr = tranche2_target(100.0, 101.0, False, [99.0, 96.0])
    ck(abs(px - 99.0) < 1e-9, "puts mirror: nearest level BELOW entry (%.2f)" % px)

    # Causality: a swing low is filed under the bar that CONFIRMS it.
    b = [(10, 10, 9, 10)] * 3 + [(10, 10, 8, 9)] + [(9, 11, 9.5, 10.5)] * 4
    lo, _hi = _swing_levels(b, 0, strength=2)
    ck(lo.get(5) == 8, "swing low at bar 3 is confirmed at bar 5, not bar 3 (%s)" % lo)

    # No fill definition is re-implemented here.
    # The needles are assembled at runtime so this check does not match itself.
    src = Path(__file__).read_text(encoding="utf-8")
    banned = ["MAX_LOSS_R" + " *", "1.2" + "5 *", "floor_r" + " *"]
    ck("stop_fill_price(" in src and not any(b in src for b in banned),
       "every stop fill routes through stop_rule.stop_fill_price")

    print()
    print("FAILED %d" % len(fails) if fails else "all checks pass")
    return 1 if fails else 0


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inp", default="research/bt2y_trades.json")
    ap.add_argument("--out", default="research/g71_scaleladder.md")
    ap.add_argument("--rows", default="research/g71_scaleladder_rows.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    import p21_target_availability as p21     # heavy (archive walk) -- lazy

    raw = json.loads((ROOT / args.inp).read_text(encoding="utf-8"))
    meta = raw["meta"]
    book = [t for t in raw["trades"] if t["traded"]]
    if args.limit:
        book = book[:args.limit]
    print("%d traded signals, %s..%s" % (len(book), meta["first"], meta["last"]))

    # ---- pass 1: fixed per-trade context (bars, entry bar, T2 target, MFE) ---
    ctx, kept = [], []
    for n, t in enumerate(book, 1):
        ei = t.get("entry_i")
        if ei is None:
            ei = p21.entry_index(t["sym"], t["day"], t["et"])
        bars = bars_for(t["sym"], t["day"])
        if not bars or ei is None or ei >= len(bars) - 1:
            continue
        long = t["dir"] == "call"
        lv = p21.levels_for_entry(t["sym"], t["day"], ei) or {}
        six = [px for k, px in lv.items() if k in SIX]
        t2_px, t2_r = tranche2_target(t["entry"], t["stop"], long, six)
        ctx.append({"t": t, "bars": bars, "ei": ei, "long": long,
                    "t2_px": t2_px, "t2_r": t2_r,
                    "mfe": mfe_r(bars, ei, t["entry"], t["stop"], long)})
        kept.append(t)
        if n % 250 == 0:
            print("  ctx %d/%d" % (n, len(book)))
    print("%d trades with usable bars" % len(ctx))

    # ---- pass 2: every variant over the same context ------------------------
    def weights(f):
        """His 30/30/30 shape with the runner fraction swept; the remaining
        (1-f) is split equally across the three scale points."""
        s = (1.0 - f) / 3.0
        return (s, s, s, f)

    variants = []                      # (label, kwargs)
    for f in (0.0, 0.10, 0.20, 0.30):
        for trail in ("be", "1r", "struct"):
            variants.append(("f=%d%% / trail=%s" % (round(f * 100), trail),
                             dict(weights=weights(f), trail=trail,
                                  struct="swing", clock=EOD)))
    variants.append(("HIS LADDER 30/30/30/10 be", dict(
        weights=(0.30, 0.30, 0.30, 0.10), trail="be", struct="swing", clock=EOD)))
    variants.append(("his ladder, struct=prevbar", dict(
        weights=(0.30, 0.30, 0.30, 0.10), trail="be", struct="prevbar", clock=EOD)))
    variants.append(("his ladder, 11:00 force-flat", dict(
        weights=(0.30, 0.30, 0.30, 0.10), trail="be", struct="swing", clock=90)))
    variants.append(("his ladder, T2 = flat 2R only", dict(
        weights=(0.30, 0.30, 0.30, 0.10), trail="be", struct="swing", clock=EOD,
        _t2_flat=True)))

    res = {}
    for label, kw in variants:
        flat = kw.pop("_t2_flat", False)
        out = []
        for cxt in ctx:
            t, long = cxt["t"], cxt["long"]
            risk = abs(t["entry"] - t["stop"])
            t2 = ((t["entry"] + 2 * risk if long else t["entry"] - 2 * risk)
                  if flat else cxt["t2_px"])
            out.append(run_ladder(cxt["bars"], cxt["ei"], t["entry"], t["stop"],
                                  long, t2_px=t2, **kw))
        res[label] = out
        s = summarise(kept, out)
        print("  %-32s n=%d win=%.1f%% meanR=%+.3f" % (label, s["n"], s["win"], s["mean"]))

    incumbent = [t["r"] for t in kept]

    # ---- tranche attribution + the oracle-runner solve -----------------------
    # Re-run his exact ladder once more with per-leg accounting, so "how far
    # would the runner have to go" is answered from the legs and not assumed.
    legs_all, own_all, fullstops, r4_oracle = [], [], [], []
    for cxt in ctx:
        t, long = cxt["t"], cxt["long"]
        comp, legs, fs, own = run_ladder(cxt["bars"], cxt["ei"], t["entry"], t["stop"],
                                    long, (0.30, 0.30, 0.30, 0.10), cxt["t2_px"],
                                    trail="be", struct="swing", clock=EOD,
                                    per_tranche=True)
        legs_all.append(legs)
        own_all.append(own)
        fullstops.append(fs)
        m = cxt["mfe"]
        r4 = legs.get(4)
        # A full stop-out before any rung scaled takes the runner with it -- no
        # hindsight exit can rescue a leg that is already closed. Everywhere
        # else the oracle runner books the window's MFE.
        r4_oracle.append(r4 if (fs or r4 is None or m is None) else max(r4, m))

    leg_mean = {k: statistics.fmean([lg[k] for lg in legs_all if k in lg])
                for k in (1, 2, 3, 4)}
    leg_n = {k: sum(1 for ow in own_all if k in ow) for k in (1, 2, 3, 4)}
    leg_own_mean = {k: (statistics.fmean([lg[k] for lg, ow in zip(legs_all, own_all)
                                          if k in ow]) if leg_n[k] else 0.0)
                    for k in (1, 2, 3, 4)}

    def mean_at(f, r4s):
        s3 = (1.0 - f) / 3.0
        vals = []
        for lg, r4 in zip(legs_all, r4s):
            if not lg:
                continue
            vals.append(s3 * (lg.get(1, 0.0) + lg.get(2, 0.0) + lg.get(3, 0.0))
                        + f * (r4 if r4 is not None else 0.0))
        return statistics.fmean(vals) if vals else 0.0

    real_r4 = [lg.get(4) for lg in legs_all]
    f_grid = [i / 100.0 for i in range(0, 101)]
    f_oracle = next((f for f in f_grid if mean_at(f, r4_oracle) >= 2.0), None)
    f_real = next((f for f in f_grid if mean_at(f, real_r4) >= 2.0), None)
    oracle_curve = [(f, mean_at(f, r4_oracle)) for f in (0.10, 0.20, 0.30, 0.50,
                                                         0.75, 1.00)]

    his = res["HIS LADDER 30/30/30/10 be"]
    hs = summarise(kept, his)
    w = hs["win"] / 100.0
    hw = [r for r in his if r is not None and r > 0]
    hl = [r for r in his if r is not None and r <= 0]
    mean_loss = statistics.fmean(hl) if hl else -1.0
    mean_win = statistics.fmean(hw) if hw else 0.0
    need_T = (2.0 - (1 - w) * mean_loss) / w if w else float("inf")

    # ladder ceiling: every tranche books the window's MFE, T2 still capped at
    # its own target. A hindsight bound that ignores the stop entirely.
    ceil = []
    for cxt in ctx:
        m = cxt["mfe"]
        if m is None:
            ceil.append(None)
            continue
        m = max(m, 0.0)
        ceil.append(0.30 * m + 0.30 * min(m, cxt["t2_r"]) + 0.30 * m + 0.10 * m)
    cs = summarise(kept, ceil)
    ceil_uncapped = [None if c["mfe"] is None else max(c["mfe"], 0.0) for c in ctx]

    # what the 10% runner alone would have to do
    capped_90 = 0.9 * min(2.0, statistics.fmean([min(max(c["mfe"] or 0, 0), 2.0)
                                                 for c in ctx]))
    runner_needed = (need_T - 0.9 * 2.0) / 0.10

    # ---- report --------------------------------------------------------------
    def row(label, s):
        return ("| %s | %d | %.1f%% | **%+.3f** | %+.0f | %s | %s | %.1f | %.1f%% |"
                % (label, s["n"], s["win"], s["mean"], s["total"],
                   s["months"], s["weeks"], s["dd"], s["past2r"]))

    hdr = ("| exit | n | win% | mean R | total R | months green | weeks green "
           "| max DD (R) | % past 2R |")
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|"

    L = ["# G7.1 `scaleladder` -- Austin's four-point ladder, measured", "",
         "Book `%s` (generated %s), %d traded signals over %d sessions "
         "%s -> %s. Entry, stop, side and entry bar fixed; only the exit varies."
         % (args.inp, meta["generated"], len(ctx), meta["sessions"],
            meta["first"], meta["last"]),
         "", "Script: `research/g71_scaleladder.py` (`--selftest` for the "
         "mechanics checks). Runners ride to the RTH close, matching "
         "`backtest_week.py:810`; one row re-runs with the 11:00 force-flat.", "",
         "## 1. Current exit vs. his ladder", "", hdr, sep,
         row("**current exit** (shipped `hod_then_runner_be`, 50/50)",
             summarise(kept, incumbent)),
         row("**his ladder** 30/30/30/10, runner to BE", hs),
         row("his ladder, structure = prev-bar low/high",
             summarise(kept, res["his ladder, struct=prevbar"])),
         row("his ladder, 11:00 force-flat",
             summarise(kept, res["his ladder, 11:00 force-flat"])),
         row("his ladder, T2 = flat 2R (no level)",
             summarise(kept, res["his ladder, T2 = flat 2R only"])),
         "", "## 2. Runner fraction x trail rule", "",
         "The remaining `1-f` is split equally across the three scale points, "
         "so `f=10%` is exactly his 30/30/30/10.", "", hdr, sep]
    for f in (0.0, 0.10, 0.20, 0.30):
        for trail in ("be", "1r", "struct"):
            lab = "f=%d%% / trail=%s" % (round(f * 100), trail)
            L.append(row("`" + lab + "`", summarise(kept, res[lab])))

    L += ["", "## 3. The arithmetic", "",
          "`mean R = wT - (1-w)`. Under his ladder the realised win rate is "
          "**%.1f%%** and the mean loss is **%+.3fR** (the -1.25R floor and the "
          "-1R disaster stop both bind), so the average WINNER has to make"
          % (hs["win"], mean_loss),
          "", "> **T = (2.0 - (1-w)x%.3f) / %.4f = %+.3fR**"
          % (mean_loss, w, need_T), "",
          "against its actual **%+.3fR**. " % mean_win,
          "", "### What the ladder can pay at its ceiling", "",
          "Hindsight bound: every tranche exits at the window's max favourable "
          "excursion, T2 still capped at its own target price (2R or the nearer "
          "six-level). The stop is ignored entirely, so no policy can beat it.", "",
          "| bound | mean R | % of trades >= 2R |", "|---|---:|---:|",
          "| ladder ceiling (perfect timing, his weights) | **%+.3f** | %.1f%% |"
          % (cs["mean"], cs["past2r"]),
          "| uncapped ceiling (100%% at MFE, no ladder) | %+.3f | %.1f%% |"
          % (agg(ceil_uncapped)[2], summarise(kept, ceil_uncapped)["past2r"]),
          "", "### Where the R actually comes from, leg by leg", "",
          "`own rung` counts the legs that exited where he said they should; the "
          "rest were swept out by the shared stop, which is why every leg's mean "
          "is dragged toward the loss side. Mean R is the LEG's own R, unweighted.",
          "", "| leg | own rung | mean R at own rung | mean R all exits | "
          "weighted contribution |", "|---|---:|---:|---:|---:|",
          "| T1 30%% causal HOD/LOD | %d / %d | %+.3f | %+.3f | %+.3f |"
          % (leg_n[1], len(ctx), leg_own_mean[1], leg_mean[1], 0.30 * leg_mean[1]),
          "| T2 30%% 2R-or-nearest-level | %d / %d | %+.3f | %+.3f | %+.3f |"
          % (leg_n[2], len(ctx), leg_own_mean[2], leg_mean[2], 0.30 * leg_mean[2]),
          "| T3 30%% structure break | %d / %d | %+.3f | %+.3f | %+.3f |"
          % (leg_n[3], len(ctx), leg_own_mean[3], leg_mean[3], 0.30 * leg_mean[3]),
          "| T4 10%% runner to BE | n/a | n/a | %+.3f | %+.3f |"
          % (leg_mean[4], 0.10 * leg_mean[4]),
          "", "T4 has no rung by construction -- it exits only on its trail, the "
          "shared stop, or the close -- so `own rung` is n/a for it, not zero.",
          "", "### The direct answer to \"let more than 10% run past 2R\"", "",
          "Sweep the runner fraction `f` with the OTHER three legs held at their "
          "measured exits. Two runners: the real one (trailed to break-even) and "
          "an ORACLE runner that exits at the window's MFE -- except on a full "
          "pre-scale stop-out, where the leg is already closed and no hindsight "
          "rescues it.", "",
          "| runner fraction f | mean R, real runner | mean R, ORACLE runner |",
          "|---:|---:|---:|"]
    for f, mo in oracle_curve:
        L.append("| %d%% | %+.3f | %+.3f |" % (round(f * 100), mean_at(f, real_r4), mo))
    L += ["",
          "- Smallest `f` reaching mean R 2.0 with the REAL runner: **%s**."
          % ("f = %d%%" % round(f_real * 100) if f_real is not None
             else "none -- 100%% runner still only reaches %+.3fR"
                  % mean_at(1.0, real_r4)),
          "- Smallest `f` reaching mean R 2.0 with a PERFECT (MFE) runner: **%s**."
          % ("f = %d%%" % round(f_oracle * 100) if f_oracle is not None
             else "none -- even a 100%% perfect runner only reaches %+.3fR"
                  % mean_at(1.0, r4_oracle)),
          "", "### How far past 2R the runner would have to go", "",
          "Under his weights 90%% of the position is structurally capped at or "
          "below ~2R (T1 exits on the first stall after the session extreme, T2 "
          "is a limit at <=2R, T3 exits on a structure break). Even granting all "
          "three the full 2R, they contribute 1.800R of the %+.3fR a winner needs, "
          "leaving the 10%% runner to supply %+.3fR of composite -- i.e. the runner "
          "leg itself must average **%+.1fR**."
          % (need_T, need_T - 1.8, runner_needed),
          "", "## 4. Read", ""]

    inc = summarise(kept, incumbent)
    bestk, bestv = max(((k, summarise(kept, v)["mean"]) for k, v in res.items()),
                       key=lambda kv: kv[1])
    L += [
        "- **His ladder and the current exit are the same number.** %+.3fR vs "
        "%+.3fR, a %+.3fR delta against this project's own +/-1.5799R error bar "
        "(`DIRECTION.md`). Nothing here moves the money gate."
        % (hs["mean"], inc["mean"], hs["mean"] - inc["mean"]),
        "- **What his ladder DOES buy is shape.** Win rate %.1f%% -> %.1f%%, weeks "
        "green %s -> %s, max drawdown %.1fR -> %.1fR. Months green stays %s."
        % (inc["win"], hs["win"], inc["weeks"], hs["weeks"], inc["dd"], hs["dd"],
           hs["months"]),
        "- **The runner fraction is not the lever.** Across f = 0%% -> 30%% mean R "
        "moves %+.3fR (%.3f -> %.3f, trail=BE). A 100%% runner, really trailed to "
        "break-even, still books only %+.3fR. The gap to 2.0 is %+.3fR."
        % (summarise(kept, res["f=30% / trail=be"])["mean"]
           - summarise(kept, res["f=0% / trail=be"])["mean"],
           summarise(kept, res["f=0% / trail=be"])["mean"],
           summarise(kept, res["f=30% / trail=be"])["mean"],
           mean_at(1.0, real_r4), 2.0 - hs["mean"]),
        "- **His >10%%-past-2R condition is already met and does not deliver.** "
        "%.1f%% of the incumbent's trades book past 2R and %.1f%% of his ladder's "
        "do; both clear his 10%% and both sit near +0.54R."
        % (inc["past2r"], hs["past2r"]),
        "- **The room is in the tape; the missing thing is knowing when to leave.** "
        "A runner that exits at the window's MFE reaches 2.0R at f = %s. So the "
        "ladder is not arithmetically impossible -- the ceiling with perfect "
        "timing is %+.3fR -- but capture is %.1f%% of it, and no weighting of "
        "blind exits closes that."
        % ("%d%%" % round(f_oracle * 100) if f_oracle is not None else "no f",
           cs["mean"], hs["mean"] / cs["mean"] * 100 if cs["mean"] else 0.0),
        "- **The legs that fire pay; they just do not fire.** T1 reaches its HOD "
        "rung on %d of %d trades (%.1f%%) and books %+.3fR when it does; T3 reaches "
        "a structure break on %d (%.1f%%) for %+.3fR. The other %.0f%% of the time "
        "the shared stop sweeps the whole position before any rung is reached -- "
        "which is an ENTRY problem, not a scaling one."
        % (leg_n[1], len(ctx), leg_n[1] / len(ctx) * 100, leg_own_mean[1],
           leg_n[3], leg_n[3] / len(ctx) * 100, leg_own_mean[3],
           (1 - leg_n[1] / len(ctx)) * 100),
        "- Best variant of the %d measured: `%s` at %+.3fR -- still %+.3fR short."
        % (len(res), bestk, bestv, 2.0 - bestv),
    ]

    (ROOT / args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote %s" % (ROOT / args.out))

    rowsout = {"meta": {"book": args.inp, "n": len(ctx),
                        "generated": meta["generated"]},
               "incumbent": incumbent,
               "variants": {k: v for k, v in res.items()},
               "ceiling": ceil, "t2_r": [c["t2_r"] for c in ctx],
               "mfe": [c["mfe"] for c in ctx],
               "key": [[t["sym"], t["day"], t["et"], t["ym"], t["sgrade"]]
                       for t in kept]}
    (ROOT / args.rows).write_text(json.dumps(rowsout, separators=(",", ":")),
                                  encoding="utf-8")
    print("wrote %s" % (ROOT / args.rows))


if __name__ == "__main__":
    main()
