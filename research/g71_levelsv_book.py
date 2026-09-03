"""G7.1 track `levels` -- restrict level selection to Austin's SIX.

Austin: "i only have 6 day trade levels ... if some htf corpus was collected,
its interfering with the 6 levels and were we are at with RR to determine how
to scale."

His six (the roster every deck builder, `research/downgrade.py::CONFLUENCE_LEVELS`
and `research/t21_card_filter.py::_levels` already agree on):

    PDH  PDL   prior regular session high / low
    PMH  PML   PREMARKET high / low (04:00-09:30 the same morning)
    ORH  ORL   5-minute opening range, 09:30-09:34

Two places in the shipped engine reach outside that roster:

 1. `backtest_week.simulate_day:848-859` picks the RUNNER TARGET -- the price
    the second half of every scaled trade is working toward, i.e. the number
    that sets realised RR -- from `(pdh, pmh)` plus an unconditional
    `math.floor(scale_level) + 1.0`, "next psych whole $". The whole dollar is
    never more than $1.00 beyond the scale point, so `min(cands)` takes it
    almost every time. ORH/ORL are not candidates at all.

 2. `signal_runner.py:2692-2710` (`PIVOT_LEVELS`, default ON) feeds T10 3-bar
    swing pivots into `level_pairs` exactly as a named level, so they generate
    ENTRIES and, because a B&R stop is the broken level, STOPS.

Arms (each writes a full `backtest_2y` book):

    base        shipped engine, unchanged
    six_target  runner target from the six only; 2R target when none qualifies
    no_pivot    PIVOT_LEVELS=0
    both        six_target + no_pivot

Every arm also records, per traded row, which candidate WOULD have won under
each rule, so the "how often does the whole dollar beat a real level" number is
measured on the same replay that produces the book.

Usage:
    python research/g71_levels_book.py --arm base --out research/g71_book_base.json
"""
from __future__ import annotations
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

ap = argparse.ArgumentParser()
ap.add_argument("--arm", required=True,
                choices=["base", "six_target", "no_pivot", "both"])
ap.add_argument("--out", required=True)
ap.add_argument("--days", type=int, default=730)
ap.add_argument("--probe", default="")
ARGS = ap.parse_args()

# PIVOT_LEVELS is read at signal_runner import time -- set it BEFORE the import.
if ARGS.arm in ("no_pivot", "both"):
    os.environ["PIVOT_LEVELS"] = "0"

import math  # noqa: E402
import backtest_week as bw  # noqa: E402
import backtest_2y as b2  # noqa: E402

SIX_TARGET = ARGS.arm in ("six_target", "both")

_ctx: dict = {}
_probe: list = []
_orig_sim = b2.simulate_day
_OrigTrade = bw.SimTrade


def _sim(symbol, day_iso, candles, pdh, pdl, bias, pmh=None, pml=None,
         pdo=None, pdc=None, qqq=None, min_risk_dollars=None):
    """Same call, but stash the day's SIX levels where the SimTrade patch can
    see them. ORH/ORL are the first five RTH bars -- `candles` is already
    pf.rth(day), the same slice research/t21_card_filter._levels uses."""
    _ctx.clear()
    _ctx.update(sym=symbol, day=day_iso, pdh=pdh, pdl=pdl, pmh=pmh, pml=pml,
                orh=max(c.high for c in candles[:5]) if len(candles) >= 5 else None,
                orl=min(c.low for c in candles[:5]) if len(candles) >= 5 else None)
    # backtest_week binds SimTrade through its own module globals, so the patch
    # below is live for this call.
    return _orig_sim(symbol, day_iso, candles, pdh, pdl, bias, pmh, pml,
                     pdo, pdc, qqq, min_risk_dollars)


def _six_runner_target(t):
    """First of Austin's SIX beyond the scale point, in the trade's direction.
    None when the day offers none -- the caller then falls back to the trade's
    original 2R target, which is what backtest_week's own F1 docstring says the
    fallback is ("fallback = original 2R target", backtest_week.py:113) and
    which the shipped code never actually reaches because it always appends the
    whole dollar."""
    long = t.direction == "call"
    six = [_ctx.get(k) for k in ("pdh", "pdl", "pmh", "pml", "orh", "orl")]
    beyond = [x for x in six if x is not None
              and (x > t.scale_level if long else x < t.scale_level)]
    if not beyond:
        return None
    return min(beyond) if long else max(beyond)


def _Trade(**kw):
    t = _OrigTrade(**kw)
    if t.scale_level:
        long = t.direction == "call"
        shipped = t.runner_target
        whole = (math.floor(t.scale_level) + 1.0) if long else (math.ceil(t.scale_level) - 1.0)
        six = _six_runner_target(t)
        risk = abs(t.entry - t.stop)
        _probe.append({
            "sym": kw.get("symbol"), "day": kw.get("day"), "et": t.entry_time[:5], "stop": round(t.stop,6), "setup": kw.get("signal_type"), "status": kw.get("status"), "grade": kw.get("grade"),
            "dir": t.direction, "entry": round(t.entry, 4),
            "scale": round(t.scale_level, 4),
            "shipped": round(shipped, 4),
            "shipped_is_whole": abs(shipped - whole) < 1e-9,
            "six": None if six is None else round(six, 4),
            "six_is_none": six is None,
            # RR of the runner leg, off the ORIGINAL risk
            "rr_shipped": None if risk <= 0 else
                round(((shipped - t.entry) if long else (t.entry - shipped)) / risk, 4),
            "rr_six": None if (risk <= 0 or six is None) else
                round(((six - t.entry) if long else (t.entry - six)) / risk, 4),
            "rr_2r": 2.0,
        })
        if SIX_TARGET:
            t.runner_target = six if six is not None else t.target
    return t


bw.SimTrade = _Trade
b2.simulate_day = _sim

sys.argv = ["backtest_2y.py", "--days", str(ARGS.days), "--out", ARGS.out]
b2.main()

if ARGS.probe:
    with open(ARGS.probe, "w", encoding="utf-8") as fh:
        json.dump(_probe, fh, separators=(",", ":"))
    print("wrote probe %s (%d rows)" % (ARGS.probe, len(_probe)))
