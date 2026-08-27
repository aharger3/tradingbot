"""p26_intrabar_ambiguity.py -- T2/R8: the honest error bar on every intrabar
number, counted and PRICED for the first time.

THE QUESTION
------------
The backtest fills at the entry bar's CLOSE. Austin does not: "most of the time
the candle closes near/above HOD/LOD and the RR is shot." `signal_runner.fill_price`
is the engine's model of that -- when the close is a bad fill it back-dates the
FILL to the level, clamped into the bar's own range. That fill happens at an
unknown moment INSIDE bar i.

With 1-minute bars, the fill price and the trade's stop can BOTH sit inside that
one bar's high/low range, and no OHLC field says which came first. That is the
error bar on every intrabar backtest number, and until this file nobody had
counted it.

WHICH OF THE TWO PRICES IS INTRABAR -- READ THIS BEFORE READING A NUMBER
-----------------------------------------------------------------------
This is NOT a wick stop-out and it does not re-open that question. The settled
rule stands untouched: **stops trigger on the candle CLOSE, fill at that close,
floored at -1.25R; wicks stop nothing out.** `research/test_runner_stop.py`
guards it and this script changes nothing about it.

The asymmetry is the entire point:

  * The FILL is intrabar. `fill_price()` returns the LEVEL, a price the bar
    traded at some unknowable moment between its open and its close.
  * The STOP is a CLOSE rule. The engine only ever tests it on the closes of
    bars i+1, i+2, ... It never looks inside bar i at all.

So the ambiguity is one-sided and it lives entirely in the FILL. When the entry
bar's range also contains the stop, the sequence inside that one minute was
either

  level touched -> stop touched   (Austin is filled, then the price he would
                                   exit at trades; on a close-driven engine the
                                   bar still closes on the good side of the
                                   level and the trade LIVES), or
  stop touched  -> level touched  (the price that would have taken him out
                                   traded BEFORE he was ever in -- on a live
                                   ticket that is a fill straight into an
                                   already-violated stop),

and OHLCV cannot distinguish them. The engine silently assumes the first every
time. This file measures how often that assumption is load-bearing and what it
is worth in R.

WHAT COUNTS AS "THE TRIGGER FIRED INSIDE BAR i"
-----------------------------------------------
`backtest_week.py:393` already names it, in the engine's own words:

    # fill_price() returned the LEVEL, not the close -- the engine's only
    # model of "taken intrabar" (bar_extreme_veto or ON WATCH tripped).
    "intrabar_fill": abs(t.entry - c.close) > 1e-9,

That marker is reused verbatim here, with ONE correction: `backtest_2y.py:169`
writes `round(t.entry, 2)` into the book, so the raw comparison flags a
sub-penny rounding gap as an intrabar fill. Comparing against `round(close, 2)`
removes it (measured: 78.8% -> 68.0% on a 400-symbol-day probe, i.e. the naive
test over-reports by ~11 points). The corrected marker can only UNDER-count --
if the clamped level rounds into the same cent as the close, the fill is
recorded as a close fill -- so every count below is a floor.

`BAR_EXTREME_FRAC` is IMPORTED from `signal_runner`, never retyped, and so is
`MAX_LOSS_R` from `research/exit_lab.py`. Two triggers can back-date the fill and
this script separates them, reconstructing both predicates from the archived bars:

  bar-extreme   `bar_extreme_veto` -- the close sits in the top/bottom
                BAR_EXTREME_FRAC of the SIGNAL BAR's own range. Fires on every
                setup except the 84% re-entry (where an extreme close IS the
                signal).
  ON WATCH      `near_session_extreme` -- the close sits within
                BAR_EXTREME_FRAC of the SESSION's own range from the day's high
                (long) or low (short). Wired into the two break-and-retest fill
                sites ONLY (`signal_runner.py:1639`, `:1879`); every other setup
                calls `fill_price` without session extremes, so ON WATCH cannot
                fire there.

Note for anyone reading CLAUDE.md alongside this: the one tolerance unit is
described there as "25% of the previous candle's range". In the code the same
constant is applied to the SIGNAL BAR's own range (`bar_extreme_veto`) and to
the SESSION's range (`near_session_extreme`). No previous-bar reading exists at
the fill site. This script measures what the code does, and says so rather than
quietly reconciling the two.

The reconstruction is self-validating: `--selfcheck` reports how often
`bar_extreme OR on_watch` reproduces the engine's own intrabar marker over a
sample. It agrees on 99.65% of a 400-symbol-day probe and every residual is the
known clamp-rounding collision above.

HOW THE UNKNOWN IS PRICED
-------------------------
Optimistic  the book as written: the trigger came first, the trade lives, R is
            whatever `bt2y_trades.json` recorded.
Pessimistic the stop came first, the trade dies on entry at the stop: R = -1.0.
            The book's own minimum is exactly -1.0 (stop-outs exit AT the stop),
            so this can never be an improvement on any row. A second column
            prices it at the worst the stop rule allows, -MAX_LOSS_R = -1.25R.

R IS AVERAGED OVER THE TRADED BOOK ONLY, AND HERE IS WHY. Across all 45,175
signals the recorded `r` runs to +67,169 -- the skipped-tight-stop population
carries sub-cent risk denominators, so a mean over it is arithmetic, not a
result. Mean R over the traded 1,016 is +0.957 and that is the number the 2.0R
money gate reads. Counts are reported over both populations; R is not.

    python research/p26_intrabar_ambiguity.py [--limit N]
    python research/p26_intrabar_ambiguity.py --selfcheck

READ-ONLY. No default changes, no flags added to the engine, no bar fetched:
symbol-days missing from `data_archive/` are counted and skipped, never pulled,
so this can never touch POLYGON_API_KEY.

Writes research/p26_intrabar_ambiguity.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import polygon_feed as pf                                              # noqa: E402
import signal_runner as sr                                             # noqa: E402
from omen_bot import Candle                                            # noqa: E402
from research.exit_lab import MAX_LOSS_R                               # noqa: E402

OUT = os.path.join(HERE, "p26_intrabar_ambiguity.md")
BT2Y = os.path.join(HERE, "bt2y_trades.json")

# Read from the source of truth, never retyped. If Austin moves the tolerance
# unit, every number in this report moves with it.
FRAC = sr.BAR_EXTREME_FRAC

# `backtest_2y.py:169` stores entry and stop as round(x, 2), so the true price
# behind a stored stop lies in [stop - HALF_CENT, stop + HALF_CENT]. Every
# containment test below is stated at both edges of that band rather than
# pretending the stored cent is exact.
HALF_CENT = 0.005
EPS = 1e-9

# The 84% re-entry never fills intrabar: `bar_extreme_veto` returns False for it
# by construction, and its fill site passes no session extremes.
SETUP_84 = "reentry_84_rule"
SETUP_BNR = "break_and_retest"


# ---------------------------------------------------------------------------
# bars -- cache only, never a fetch
# ---------------------------------------------------------------------------

def load_day(sym: str, day: str):
    """RTH candles for one symbol-day, or None if it is not already archived.

    `pf.fetch_day` is cache-first but WILL call Polygon on a miss. The guard
    makes that impossible: this is a measurement rig over a book that has
    already been replayed, and a cache miss is a data gap to report, not a
    reason to hit the network."""
    if not (pf.ARCHIVE / sym / f"{day}.csv").exists():
        return None
    return pf.rth(pf.fetch_day(sym, day))


def index_day(rth):
    """(minute -> bar index, running session high, running session low).

    The running extremes reproduce `signal_runner.SignalRunner._session_extremes`
    on the entry bar: every RTH bar from the open up to AND INCLUDING bar i, no
    future bars, because that is the answer Austin could have seen."""
    idx, run_hi, run_lo = {}, [], []
    hi = lo = None
    for i, c in enumerate(rth):
        hi = c.high if hi is None else max(hi, c.high)
        lo = c.low if lo is None else min(lo, c.low)
        run_hi.append(hi)
        run_lo.append(lo)
        idx.setdefault(c.timestamp[:5], i)
    return idx, run_hi, run_lo


# ---------------------------------------------------------------------------
# the two predicates, reconstructed from bars
# ---------------------------------------------------------------------------

def bar_extreme_fires(bar, is_long: bool, setup: str) -> bool:
    """`signal_runner.bar_extreme_veto` with the probe `fill_price` builds --
    entry = the bar's own close. Never fires on the 84% re-entry; a zero-range
    bar cannot say where in its range the close sits."""
    if setup == SETUP_84:
        return False
    rng = bar.high - bar.low
    if rng <= 0:
        return False
    return (bar.close >= bar.high - FRAC * rng) if is_long \
        else (bar.close <= bar.low + FRAC * rng)


def on_watch_fires(bar, is_long: bool, setup: str, s_hi: float, s_lo: float) -> bool:
    """`signal_runner.near_session_extreme`, reachable only from the two
    break-and-retest fill sites -- every other setup calls `fill_price` with no
    session extremes, so the rule returns False there by construction."""
    if setup != SETUP_BNR:
        return False
    rng = s_hi - s_lo
    if rng <= 0:
        return False
    return (bar.close >= s_hi - FRAC * rng) if is_long \
        else (bar.close <= s_lo + FRAC * rng)


# ---------------------------------------------------------------------------
# classification of one signal
# ---------------------------------------------------------------------------

def classify(row: dict, bar, s_hi: float, s_lo: float) -> dict:
    """Everything this report needs about one signal, from its entry bar.

    `intrabar` is the engine's own marker (backtest_week.py:393), corrected for
    the book's 2dp rounding. `amb_*` ask whether the stored stop lies inside the
    SAME bar's range, at both edges of the half-cent rounding band."""
    is_long = row["dir"] == "call"
    stop = float(row["stop"])
    lo, hi = bar.low, bar.high

    intrabar = abs(float(row["entry"]) - round(bar.close, 2)) > EPS

    # Certain: the stop clears the rounding band on both sides, so the bar's
    # range contains it whatever the un-rounded stop actually was.
    amb_certain = (lo <= stop - HALF_CENT) and (stop + HALF_CENT <= hi)
    # Possible: containment survives the rounding band. This is the ticket's
    # literal test ("the stop price within their high/low range") read honestly
    # against a stored cent, and it is the headline count.
    amb_possible = (lo <= stop + HALF_CENT) and (stop - HALF_CENT <= hi)
    # The stop sits ON the entry bar's own extreme. `signal_runner.intrabar_stop`
    # puts it there: when the back-dated fill lands at or through the level-stop
    # the trade has no risk to size, so the stop moves to the bar Austin entered
    # on ("stop loss at the bottom of the wick you entered"). Order is still
    # unknowable -- the extreme may fall either side of the fill -- but this
    # class is MANUFACTURED by the stop rule, not found in the tape, so it is
    # reported apart from the rest.
    edge = round(lo, 2) if is_long else round(hi, 2)
    at_extreme = amb_possible and abs(stop - edge) < EPS

    return {
        "intrabar": intrabar,
        "bar_extreme": bar_extreme_fires(bar, is_long, row["setup"]),
        "on_watch": on_watch_fires(bar, is_long, row["setup"], s_hi, s_lo),
        "amb_possible": amb_possible,
        "amb_certain": amb_certain,
        "at_extreme": at_extreme,
        "traded": bool(row["traded"]),
        "sgrade": row["sgrade"],
        "r": float(row["r"]),
    }


# ---------------------------------------------------------------------------
# the book
# ---------------------------------------------------------------------------

def build(limit=None):
    with open(BT2Y, encoding="utf-8") as fh:
        book = json.load(fh)
    rows = book["trades"]
    by_day = defaultdict(list)
    for r in rows:
        by_day[(r["sym"], r["day"])].append(r)

    keys = sorted(by_day)
    if limit:
        keys = keys[:limit]

    out, missing_day, missing_bar = [], 0, 0
    for n, (sym, day) in enumerate(keys):
        rth = load_day(sym, day)
        if not rth:
            missing_day += len(by_day[(sym, day)])
            continue
        idx, run_hi, run_lo = index_day(rth)
        for r in by_day[(sym, day)]:
            i = idx.get(r["et"])
            if i is None:
                missing_bar += 1
                continue
            out.append(classify(r, rth[i], run_hi[i], run_lo[i]))
        if n and n % 2000 == 0:
            print("  %d/%d symbol-days" % (n, len(keys)), flush=True)
    return out, book["meta"], missing_day, missing_bar


# ---------------------------------------------------------------------------
# the three numbers, per population
# ---------------------------------------------------------------------------

def measure(recs, priced: bool):
    """The ticket's three numbers over one population.

    `priced` gates the R columns. Over the whole 45,175-signal book the recorded
    `r` reaches +67,169 (sub-cent risk denominators on the skipped-tight-stop
    rows), so a mean over it would be arithmetic rather than a result; only the
    traded populations get an R read."""
    n = len(recs)
    intra = [c for c in recs if c["intrabar"]]
    amb = [c for c in intra if c["amb_possible"]]
    m = {
        "n": n,
        "intrabar": len(intra),
        "intrabar_pct": pct(len(intra), n),
        "amb": len(amb),
        "amb_pct_intrabar": pct(len(amb), len(intra)),
        "amb_pct_all": pct(len(amb), n),
        "amb_certain": sum(1 for c in intra if c["amb_certain"]),
        "at_extreme": sum(1 for c in intra if c["at_extreme"]),
        "amb_certain_pct_intrabar": pct(sum(1 for c in intra if c["amb_certain"]),
                                        len(intra)),
        "ow_only": sum(1 for c in intra if c["on_watch"] and not c["bar_extreme"]),
        "be_only": sum(1 for c in intra if c["bar_extreme"] and not c["on_watch"]),
        "both": sum(1 for c in intra if c["bar_extreme"] and c["on_watch"]),
        "neither": sum(1 for c in intra if not c["bar_extreme"] and not c["on_watch"]),
    }
    if not priced or not n:
        return m

    opt = [c["r"] for c in recs]
    pess = [(-1.0 if (c["intrabar"] and c["amb_possible"]) else c["r"]) for c in recs]
    floor = [(-MAX_LOSS_R if (c["intrabar"] and c["amb_possible"]) else c["r"]) for c in recs]
    m.update({
        "priced": True,
        "r_opt": mean(opt),
        "r_pess": mean(pess),
        "r_floor": mean(floor),
        "spread": mean(opt) - mean(pess),
        "spread_floor": mean(opt) - mean(floor),
    })
    # The same spread confined to the population where the ambiguity actually
    # lives -- averaging it over rows that were never intrabar dilutes it.
    sub = [c for c in recs if c["intrabar"] and c["amb_possible"]]
    if sub:
        m["sub_n"] = len(sub)
        m["sub_opt"] = mean([c["r"] for c in sub])
        m["sub_spread"] = m["sub_opt"] - (-1.0)
    return m


def ladder_means(recs):
    """Traded mean R per S/A/C. Not a result of this ticket — the yardstick the
    spread is measured against, so that "big enough to matter" is a comparison
    against a real effect size rather than an adjective."""
    out = {}
    for g in ("S", "A", "C"):
        xs = [c["r"] for c in recs if c["traded"] and c["sgrade"] == g]
        out[g] = mean(xs)
        out["n_" + g] = len(xs)
    return out


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def pct(a, b):
    return 100.0 * a / b if b else 0.0


# ---------------------------------------------------------------------------
# selfcheck -- assert-based, no framework
# ---------------------------------------------------------------------------

def _bar(o, h, l, c):
    return Candle(timestamp="09:45:00", open=o, high=h, low=l, close=c, volume=1000)


def selfcheck(sample_days=400):
    print("p26 selfcheck -- BAR_EXTREME_FRAC = %r (from signal_runner)" % FRAC)
    assert FRAC is sr.BAR_EXTREME_FRAC, "the tolerance unit must come from the source"
    assert MAX_LOSS_R == 1.25, "exit_lab.MAX_LOSS_R moved; the pessimistic floor moved with it"

    # ---- CASE A: trigger fires AND the stop is inside the same bar's range ---
    # A long break-and-retest of a level at 100.00. The bar runs 99.60 -> 100.90
    # and closes at 100.85, inside the top FRAC of its own range, so `fill_price`
    # back-dates the fill to the level. The stop at 99.80 also lies inside the
    # bar: price was at the stop and at the fill within the same minute.
    a = _bar(99.70, 100.90, 99.60, 100.85)
    lvl, stop = 100.00, 99.80
    assert a.close >= a.high - FRAC * (a.high - a.low), "case A must trip bar_extreme"
    assert sr.fill_price(lvl, a, is_long=True) == lvl, \
        "case A must fill at the LEVEL -- that is what 'taken intrabar' means"
    row = {"dir": "call", "entry": round(lvl, 2), "stop": stop, "setup": SETUP_BNR,
           "traded": True, "sgrade": "S", "r": 3.0}
    ca = classify(row, a, s_hi=100.90, s_lo=99.60)
    assert ca["intrabar"], "case A: fill != close, so it is an intrabar fill"
    assert ca["bar_extreme"], "case A: the bar-extreme trigger fired"
    assert ca["amb_possible"] and ca["amb_certain"], \
        "case A: 99.60 <= 99.80 <= 100.90 -- the stop is inside the entry bar"
    assert not ca["at_extreme"], "case A: the stop is not sitting on the bar's low"

    # ---- CASE B: trigger fires, the stop is NOT inside the bar's range -------
    # Same bar and same fill, stop moved to 99.40 -- below the bar's low. Nothing
    # inside this minute could have taken him out. Unambiguous.
    b_stop = 99.40
    row_b = dict(row, stop=b_stop)
    cb = classify(row_b, a, s_hi=100.90, s_lo=99.60)
    assert cb["intrabar"], "case B is still an intrabar fill"
    assert not cb["amb_possible"], \
        "case B: 99.40 < the bar's low 99.60 -- the stop was never reachable"
    assert not cb["amb_certain"] and not cb["at_extreme"], "case B: no ambiguity of any kind"

    # ---- CASE C: no trigger, so no intrabar fill at all ---------------------
    # The close sits mid-range: `fill_price` returns the CLOSE and the book's
    # entry equals it, so there is nothing to be ambiguous about even though the
    # stop is well inside the bar.
    c = _bar(99.70, 100.90, 99.60, 100.20)
    assert sr.fill_price(lvl, c, is_long=True) == c.close, "case C must fill at the close"
    cc = classify({"dir": "call", "entry": round(c.close, 2), "stop": 99.80,
                   "setup": SETUP_BNR, "traded": True, "sgrade": "S", "r": 3.0},
                  c, s_hi=100.90, s_lo=99.60)
    assert not cc["intrabar"], "case C: the fill IS the close"
    assert cc["amb_possible"], "case C: the stop is in range -- but the fill is not intrabar"

    # ---- CASE D: the stop sitting ON the entry bar's low --------------------
    # What `signal_runner.intrabar_stop` produces. Still ambiguous, reported apart.
    cd = classify(dict(row, stop=round(a.low, 2)), a, s_hi=100.90, s_lo=99.60)
    assert cd["at_extreme"], "case D: the stop is the bar's own low"
    assert cd["amb_possible"], "case D is ambiguous"
    assert not cd["amb_certain"], "case D sits inside the rounding band, not clear of it"

    # ---- CASE E: ON WATCH, the short side, session extreme ------------------
    # A short whose bar closes jammed on the low of the day. `bar_extreme_veto`
    # does NOT fire (the close sits mid-range on its own bar), ON WATCH does.
    e = _bar(50.30, 50.40, 50.00, 50.20)
    assert not bar_extreme_fires(e, False, SETUP_BNR), "case E must not trip bar_extreme"
    assert on_watch_fires(e, False, SETUP_BNR, s_hi=51.00, s_lo=50.00), \
        "case E must trip ON WATCH -- the close is inside FRAC of the session low"
    assert not on_watch_fires(e, False, "one_candle_rule", s_hi=51.00, s_lo=50.00), \
        "ON WATCH is wired into the break-and-retest fill sites only"
    assert sr.fill_price(50.25, e, is_long=False, session_hi=51.00, session_lo=50.00) == 50.25, \
        "case E must fill at the LEVEL via near_session_extreme"

    # ---- CASE F: the pricing arithmetic -------------------------------------
    recs = [
        {"intrabar": True, "amb_possible": True, "r": 3.0, "bar_extreme": True,
         "on_watch": False, "amb_certain": True, "at_extreme": False,
         "traded": True, "sgrade": "S"},
        {"intrabar": True, "amb_possible": False, "r": 1.0, "bar_extreme": True,
         "on_watch": False, "amb_certain": False, "at_extreme": False,
         "traded": True, "sgrade": "S"},
    ]
    m = measure(recs, priced=True)
    assert m["intrabar"] == 2 and m["amb"] == 1
    assert abs(m["amb_pct_intrabar"] - 50.0) < EPS
    assert abs(m["r_opt"] - 2.0) < EPS, "optimistic = the book: (3.0 + 1.0)/2"
    assert abs(m["r_pess"] - 0.0) < EPS, "pessimistic = (-1.0 + 1.0)/2"
    assert abs(m["spread"] - 2.0) < EPS, "the spread is what the unknown is worth"
    assert abs(m["r_floor"] - (-0.125)) < EPS, "at the -1.25R floor: (-1.25 + 1.0)/2"
    assert abs(m["amb_certain_pct_intrabar"] - 50.0) < EPS
    lad = ladder_means(recs)
    assert lad["n_S"] == 2 and abs(lad["S"] - 2.0) < EPS, "the yardstick is the traded mean"

    # ---- CASE G: the reconstruction IS the engine's marker ------------------
    # Not a hand-built bar: over real archived days, does
    # `bar_extreme OR on_watch` reproduce the engine's own intrabar flag?
    agree = dis = 0
    residual_shape = True
    with open(BT2Y, encoding="utf-8") as fh:
        rows = json.load(fh)["trades"]
    by_day = defaultdict(list)
    for r in rows:
        by_day[(r["sym"], r["day"])].append(r)
    for sym, day in sorted(by_day)[:sample_days]:
        rth = load_day(sym, day)
        if not rth:
            continue
        idx, run_hi, run_lo = index_day(rth)
        for r in by_day[(sym, day)]:
            i = idx.get(r["et"])
            if i is None:
                continue
            c = classify(r, rth[i], run_hi[i], run_lo[i])
            pred = c["bar_extreme"] or c["on_watch"]
            if pred == c["intrabar"]:
                agree += 1
            else:
                dis += 1
                # The only permitted residual: a trigger fired but the clamped
                # level rounded into the same cent as the close, so the book
                # cannot show it. The reverse -- an intrabar fill with neither
                # trigger -- would mean the reconstruction is wrong.
                if not (pred and not c["intrabar"]):
                    residual_shape = False
    rate = pct(agree, agree + dis)
    print("  case G: reconstruction agrees with the engine's marker on "
          "%d/%d = %.2f%% of %d symbol-days" % (agree, agree + dis, rate, sample_days))
    assert rate > 99.0, "the reconstruction of fill_price must track the engine"
    assert residual_shape, \
        "every disagreement must be a trigger the rounding hid, never a fill with no trigger"

    print("  cases A-G pass. No engine default was read from an env var or written.")
    return 0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def row_counts(name, m):
    return ("| %s | %s | %s | %.1f%% | %s | %.1f%% | %.1f%% |"
            % (name, f"{m['n']:,}", f"{m['intrabar']:,}", m["intrabar_pct"],
               f"{m['amb']:,}", m["amb_pct_intrabar"], m["amb_pct_all"]))


def row_priced(name, m):
    if not m.get("priced"):
        return ""
    return ("| %s | %s | %+.4f | %+.4f | **%.4f** | %+.4f | %.4f |"
            % (name, f"{m['n']:,}", m["r_opt"], m["r_pess"], m["spread"],
               m["r_floor"], m["spread_floor"]))


def report(pops, meta, missing_day, missing_bar, n_class, ladder):
    A, T, AS, TS = pops["all"], pops["traded"], pops["all_S"], pops["traded_S"]
    L = []
    add = L.append

    add("# P26 / R8 — the intrabar ambiguity rate")
    add("")
    add("**%.1f%% of intrabar fills sit on a bar that also contains the trade's stop, "
        "and the unknown is worth %.4f R of mean R on the traded book** — more than "
        "the %.4f R that book is short of the 2.0R money gate, and %.1f× the entire "
        "S-over-C edge the grader is built to produce."
        % (T["amb_pct_intrabar"], T["spread"], 2.0 - T["r_opt"],
           T["spread"] / (ladder["S"] - ladder["C"]) if ladder["S"] > ladder["C"] else 0.0))
    add("")
    add("Two caveats belong in the same breath as that number. It is **one-directional** "
        "— the ambiguity can only make R worse, so the booked %+.4f R is a ceiling, not "
        "a midpoint. And **%s of the %s ambiguous traded bars are the stop sitting on "
        "the entry bar's own extreme**, which `signal_runner.intrabar_stop` put there; "
        "only %d (%.1f%% of intrabar fills) have a stop clear of both edges of the bar."
        % (T["r_opt"], f"{T['at_extreme']:,}", f"{T['amb']:,}", T["amb_certain"],
           T["amb_certain_pct_intrabar"]))
    add("")
    add("Generated by `research/p26_intrabar_ambiguity.py` over "
        "`research/bt2y_trades.json` (%s signals / %s traded, %s → %s, %d sessions). "
        "Read-only: no default changed, no flag added, no bar fetched."
        % (f"{meta['signals']:,}", f"{meta['traded']:,}", meta["first"], meta["last"],
           meta["sessions"]))
    add("")

    add("## Which of the two prices is intrabar")
    add("")
    add("This does not re-open the stop rule and nothing here contradicts it. "
        "**Stops trigger on the candle CLOSE, fill at that close, floored at "
        "−%.2fR; wicks stop nothing out.** That is settled and "
        "`research/test_runner_stop.py` guards it." % MAX_LOSS_R)
    add("")
    add("The ambiguity is one-sided, and the side it sits on is the **fill**:")
    add("")
    add("| price | how the engine gets it | is it intrabar? |")
    add("|---|---|---|")
    add("| the FILL | `signal_runner.fill_price` returns the LEVEL, clamped into bar "
        "*i*'s range, whenever the close is a bad fill | **yes** — the level was traded "
        "at an unknowable moment inside the minute |")
    add("| the STOP | tested on the CLOSE of bars *i+1, i+2, …* | **no** — the engine "
        "never looks inside bar *i*, and a wick has never stopped anything out |")
    add("")
    add("So an ambiguous bar is **not a hidden wick stop-out**. It is a bar in which "
        "the price Austin was filled at and the price his stop order rests at were "
        "*both traded inside the same minute*, in an order OHLCV cannot recover. "
        "The engine assumes fill-then-stop every single time. On a live ticket the "
        "other order means the stop was violated before he was ever in.")
    add("")

    add("## 1 & 2 — the count and the rate")
    add("")
    add("*Ambiguous* = the stored stop lies inside the entry bar's high/low range "
        "(within the half-cent band the book's 2dp rounding leaves).")
    add("")
    add("| population | signals | intrabar fills | of pop. | ambiguous | **of intrabar** | of pop. |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    add(row_counts("all signals", A))
    add(row_counts("traded", T))
    add(row_counts("all S", AS))
    add(row_counts("**traded S**", TS))
    add("")
    add("### The same count, split three ways")
    add("")
    add("Not every ambiguous bar is ambiguous for the same reason, and one class is "
        "manufactured by a stop rule rather than found in the tape.")
    add("")
    add("| population | ambiguous | stop *clear* of both edges | of intrabar | stop **is** the bar's own extreme |")
    add("|---|---:|---:|---:|---:|")
    for nm, m in (("all signals", A), ("traded", T), ("all S", AS), ("traded S", TS)):
        add("| %s | %s | %s | %.1f%% | %s |"
            % (nm, f"{m['amb']:,}", f"{m['amb_certain']:,}",
               m["amb_certain_pct_intrabar"], f"{m['at_extreme']:,}"))
    add("")
    add("**This is the load-bearing split and it should be read before the headline "
        "rate.** The last column is `signal_runner.intrabar_stop` at work: when the "
        "back-dated fill lands at or through the level-stop the trade has no risk "
        "to size, so the stop moves to the entry bar's own wick — Austin's own "
        "answer, written five times in the recovered reviews (\"stop loss at the "
        "bottom of the wick you entered\"). It accounts for %s of the traded book's "
        "%s ambiguous bars." % (f"{T['at_extreme']:,}", f"{T['amb']:,}"))
    add("")
    add("Those rows are genuinely ambiguous — the bar's extreme may fall either side "
        "of the fill, and OHLCV does not say which — but the ambiguity is a "
        "consequence of *where the stop was put*, not of what the tape did. It also "
        "makes the pessimistic arm less of a stretch than it looks: on a long "
        "break-and-retest bar that closes near its high, the bar's low very often "
        "precedes the close, and the low IS the stop on these rows. The residual "
        "class — a stop strictly inside the bar, clear of both wicks — is only "
        "%.1f%% of intrabar fills on the traded book (%d of %s)."
        % (T["amb_certain_pct_intrabar"], T["amb_certain"], f"{T['intrabar']:,}"))
    add("")

    add("### Which trigger back-dated the fill")
    add("")
    add("`BAR_EXTREME_FRAC = %s`, imported from `signal_runner`. Two rules can "
        "back-date a fill and only one of them is ON WATCH." % FRAC)
    add("")
    add("| population | intrabar fills | bar-extreme only | **ON WATCH only** | both | neither |")
    add("|---|---:|---:|---:|---:|---:|")
    for nm, m in (("all signals", A), ("traded", T), ("all S", AS), ("traded S", TS)):
        add("| %s | %s | %s | %s | %s | %s |"
            % (nm, f"{m['intrabar']:,}", f"{m['be_only']:,}", f"{m['ow_only']:,}",
               f"{m['both']:,}", f"{m['neither']:,}"))
    add("")
    add("*neither* is the reconstruction's residual — a trigger fired but the clamped "
        "level rounded into the same cent as the close, so the book cannot show it. "
        "`--selfcheck` asserts that every disagreement has this shape and that the "
        "reconstruction tracks the engine's own marker above 99%.")
    add("")

    add("## 3 — what the unknown is worth")
    add("")
    add("Optimistic = the book as written (trigger first, the trade lives). "
        "Pessimistic = every ambiguous row dies on entry at its stop, −1.0R. "
        "The book's own minimum R is exactly −1.0, so the pessimistic arm can never "
        "flatter a row. The floor column prices the same rows at −%.2fR, the worst "
        "the stop rule allows." % MAX_LOSS_R)
    add("")
    add("| population | n | mean R optimistic | mean R pessimistic | **spread** | at −%.2fR floor | spread |"
        % MAX_LOSS_R)
    add("|---|---:|---:|---:|---:|---:|---:|")
    add(row_priced("traded", T))
    add(row_priced("**traded S**", TS))
    add("")
    add("R is averaged over the traded book only. Across all %s signals the recorded "
        "`r` runs to +67,169 — the skipped-tight-stop rows carry sub-cent risk "
        "denominators — so a mean over that population is arithmetic, not a result. "
        "The traded book is also the population the 2.0R money gate reads."
        % f"{meta['signals']:,}")
    add("")
    add("### The same spread, undiluted")
    add("")
    add("Averaged over the whole traded book the spread is damped by every row the "
        "ambiguity never touched. Confined to the ambiguous rows themselves:")
    add("")
    add("| population | ambiguous & traded | mean R as booked | mean R if the stop came first | spread |")
    add("|---|---:|---:|---:|---:|")
    for nm, m in (("traded", T), ("traded S", TS)):
        if m.get("sub_n"):
            add("| %s | %s | %+.4f | -1.0000 | **%.4f** |"
                % (nm, f"{m['sub_n']:,}", m["sub_opt"], m["sub_spread"]))
    add("")

    add("## Against the money gate — is the spread big enough to matter?")
    add("")
    gap, gap_s = 2.0 - T["r_opt"], 2.0 - TS["r_opt"]
    edge = ladder["S"] - ladder["C"]
    add("The gate is mean R = 2.0. Two questions, and they have different answers.")
    add("")
    add("**Does the gate's verdict flip? No.** The ambiguity is one-directional: "
        "the pessimistic arm is never better than the booked row, so **the booked "
        "%+.4f R is a ceiling, not a midpoint.** That ceiling is already %.4f R below "
        "2.0 (traded S: %+.4f R, %.4f R below). Resolving the ordering with sub-minute "
        "data can only move both arms down. The book fails the money gate optimistically, "
        "pessimistically, and everywhere in between — the gate is not being missed "
        "because of a measurement artifact, and no amount of tick data rescues it."
        % (T["r_opt"], gap, TS["r_opt"], gap_s))
    add("")
    add("**Does the spread dominate the effects being measured? Yes, and this is the "
        "part that bites.** The %.4f R spread is %.1f× the %.4f R gap to the gate and "
        "%.1f× the whole S-over-C mean-R edge on the traded book:"
        % (T["spread"], T["spread"] / gap if gap else 0.0, gap,
           T["spread"] / edge if edge > 0 else 0.0))
    add("")
    add("| traded | n | mean R |")
    add("|---|---:|---:|")
    for g in ("S", "A", "C"):
        add("| %s | %s | %+.4f |" % (g, f"{ladder['n_' + g]:,}", ladder[g]))
    add("| **S − C** | | **%+.4f** |" % edge)
    add("")
    add("An S/A/C ladder whose whole span is %.4f R is being ranked inside an error "
        "bar of %.4f R. Every A/B in the book that turns on a mean-R difference of "
        "under a full R — which is most of them — is reporting a number smaller than "
        "the thing that has never been measured. **That is what this file changes: "
        "not the verdict on the gate, but the credibility interval on every ranking "
        "underneath it.**" % (edge, T["spread"]))
    add("")
    add("The one lever that shrinks it without new data is the split above. Strip out "
        "the `intrabar_stop` class and the residual ambiguity is %.1f%% of intrabar "
        "fills; the open question is whether a stop resting on the entry bar's own "
        "wick should be modelled as reachable inside that bar at all, and that is "
        "Austin's call, not a measurement." % T["amb_certain_pct_intrabar"])
    add("")

    add("## What this does not say")
    add("")
    add("- It does not say the pessimistic arm is what happened. It is the other "
        "half of a coin the data cannot flip; the truth is somewhere between, and "
        "nothing here estimates where.")
    add("- It does not touch the stop rule. Wicks still stop nothing out and stops "
        "still trigger on closes.")
    add("- It measures the code, not the sentence. `CLAUDE.md` describes the "
        "tolerance unit as \"25% of the previous candle's range\"; at the fill site "
        "the same constant is applied to the SIGNAL BAR's own range "
        "(`bar_extreme_veto`) and to the SESSION's range (`near_session_extreme`). "
        "No previous-bar reading exists there. If the sentence is the rule, this "
        "report measures the wrong band and the fix belongs in `fill_price`, not here.")
    add("- The intrabar marker can only under-count. `backtest_2y.py:169` stores "
        "entry at 2dp, so a clamped level that rounds into the close's cent is "
        "recorded as a close fill. Every count above is a floor.")
    add("- %d signals were dropped for a missing archived day and %d for an entry "
        "minute with no bar; %s of %s signals were classified. Cache misses are "
        "never fetched, on purpose."
        % (missing_day, missing_bar, f"{n_class:,}", f"{meta['signals']:,}"))
    add("")
    add("Reproduce: `python research/p26_intrabar_ambiguity.py` · "
        "verify: `python research/p26_intrabar_ambiguity.py --selfcheck`")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="first N symbol-days only (smoke run)")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()

    recs, meta, missing_day, missing_bar = build(a.limit)
    pops = {
        "all": measure(recs, priced=False),
        "traded": measure([c for c in recs if c["traded"]], priced=True),
        "all_S": measure([c for c in recs if c["sgrade"] == "S"], priced=False),
        "traded_S": measure([c for c in recs if c["traded"] and c["sgrade"] == "S"],
                            priced=True),
    }
    md = report(pops, meta, missing_day, missing_bar, len(recs), ladder_means(recs))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(md)

    T, TS = pops["traded"], pops["traded_S"]
    print("classified %d signals (%d day-gaps, %d minute-gaps)"
          % (len(recs), missing_day, missing_bar))
    print("ambiguous / intrabar: all %.1f%%  traded %.1f%%  S %.1f%%  traded-S %.1f%%"
          % (pops["all"]["amb_pct_intrabar"], T["amb_pct_intrabar"],
             pops["all_S"]["amb_pct_intrabar"], TS["amb_pct_intrabar"]))
    print("traded   mean R  opt %+.4f  pess %+.4f  spread %.4f"
          % (T["r_opt"], T["r_pess"], T["spread"]))
    print("traded S mean R  opt %+.4f  pess %+.4f  spread %.4f"
          % (TS["r_opt"], TS["r_pess"], TS["spread"]))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
