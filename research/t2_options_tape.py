"""T2 -- THE OPTIONS TAPE. The 2-year book scored in the instrument he trades.

Every number in `research/t2_options_tape.md` comes from here.

    python research/t2_options_tape.py             # all sections
    python research/t2_options_tape.py book theta  # some sections
    python research/t2_options_tape.py --selfcheck # the checks the ticket names

WHAT THIS IS
------------
`R` in this project is scored on the UNDERLYING: (exit - entry) / |entry - stop|.
The trade is a 0DTE ATM option. `options_sizer.DEFAULT_DELTA = 0.5` -- a flat
linear delta -- was the entire options model in the repo, and a constant cannot
hold the two effects Austin's runner thesis is a bet between: convexity (a
winning call's delta climbs, so the runner earns more than the underlying move)
and theta (the same contract bleeds while it waits).

This file re-scores all 1,017 traded rows as the contract, with a real
Black-Scholes pricer (`black_scholes.py`, root, with its own selfcheck).

WHAT IS MODELLED AND WHAT IS MEASURED
-------------------------------------
MEASURED, from files already in the repo:
  * entry / stop / exit / bars / side / r   -- `research/g3_arm_ow1.json`
  * the day's high-low range (`drange`)     -- same file
  * MFE / MAE / oracle                      -- `research/x1_mfe_mae.json`
  * prior-session ranges                    -- `data_archive/<SYM>/<DAY>.csv`
MODELLED, because THERE IS NO OPTIONS TAPE IN THIS REPO:
  * implied volatility  -- Parkinson vol of the day's range x an IV multiplier
  * the option price    -- Black-Scholes, r = q = 0, flat surface, no smile
  * the fill            -- mid, no spread, no commission, no market impact
Section `assume` prices the sensitivity of the headline to every one of those.

TWO EXIT CONVENTIONS, AND THE PROTOTYPE ONLY HAD ONE
-----------------------------------------------------
`research/x13_new_angles.py::option_r` prices ONE exit at `row["exit"]` for the
whole position. But 538 of the 1,017 rows carry `scaled: true`: the shipped exit
plan is `backtest_week.SCALE_PLAN = "hod_then_runner_be"`, 50% off at the
as-of-entry session extreme and 50% riding to `exit`, and the book's `r` is the
blend `0.5*scale_r + 0.5*run_r` (`backtest_week.py:249-253`). On 536 rows
`(exit-entry)/risk != r`. So the prototype scores a DIFFERENT TRADE -- the whole
position held to the final exit -- and that trade holds more size in the fat
right tail exactly where convexity pays.

Both conventions are therefore reported, never blended:
  SINGLE  x13's convention. Full size to `exit`. Reproduces the prototype.
  LADDER  the book's own 50/50, with the scale price recovered exactly from
          `r` (algebra in `scale_price()`), so its UNDERLYING arm reproduces
          `+0.9551R` to 1e-9. That equality is a selfcheck, not a hope.

The LADDER's scale leg needs the MINUTE the scale fired, which the book does not
record. It is bounded: not before entry, not after exit. So the ladder is
reported as a BAND over scale-at-entry / scale-at-midpoint / scale-at-exit
timing. A band is the honest answer; a point estimate would be invented.
"""

from __future__ import annotations

import csv
import json
import math
import os
import statistics as st
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import black_scholes as bs                                    # noqa: E402
import options_sizer as osz                                   # noqa: E402

BOOK = os.path.join(_HERE, "g3_arm_ow1.json")
MFE = os.path.join(_HERE, "x1_mfe_mae.json")
HELDOUT = os.path.join(_HERE, "marks", "probe_omen_test1_2026-08-27.jsonl")
ARCHIVE = os.path.join(_ROOT, "data_archive")

RTH_MIN = 390.0             # 09:30 -> 16:00
SESSIONS_YR = 252.0
MIN_T0_MIN = 1.0            # floor on time-to-expiry at ENTRY  (x13's convention)
MIN_T1_MIN = 0.5            # floor on time-to-expiry at EXIT   (x13's convention)
IV_ARMS = (1.0, 1.2, 1.5)
HEADLINE_IV = 1.2

# The three setup families in the book, in book order of size.
FAMILIES = ("break_and_retest", "one_candle_rule", "reentry_84_rule")

# `research/x9_live_gap_premortem.md` 2.2 -- carried here as an explicit, labelled
# ASSUMPTION, not a measurement. Nobody in this repo has read a real NBBO on
# these contracts: Polygon returns 403 NOT_AUTHORIZED on the options snapshot and
# Tastytrade session auth is failing. $0.05 is x9's headline assumption.
X9_ROUND_TRIP_SPREAD = 0.05


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def win(xs):
    xs = list(xs)
    return 100.0 * sum(1 for x in xs if x > 0) / len(xs) if xs else float("nan")


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else float("nan")


def load_book(path=BOOK):
    with open(path) as fh:
        return [r for r in json.load(fh)["trades"] if r.get("traded")]


# The book this report's numbers were measured on. This tree is worked by several
# tracks at once and `g3_arm_ow1.json` was transiently rewritten under this run on
# 2026-08-28 (T11's stop-fill change, briefly, before it was restored). So the
# book is PINNED BY HASH here and the fingerprint is printed on every run: if it
# does not match, the numbers in the .md were measured on a different book and
# the .md must be regenerated, not quietly re-read.
BOOK_SHA = "a05ebf5a84d92da2cc0797bf0e15b10e74db59d4a3d0fe023d7d4fff47cc0ad2"


def book_fingerprint(path=BOOK):
    """(sha256 over all rows, n traded, mean r) -- canonical JSON, order-stable."""
    import hashlib
    with open(path) as fh:
        d = json.load(fh)
    h = hashlib.sha256(json.dumps(d["trades"], sort_keys=True,
                                  separators=(",", ":")).encode()).hexdigest()
    tr = [r for r in d["trades"] if r.get("traded")]
    return h, len(tr), mean(r["r"] for r in tr)


def print_fingerprint():
    h, n, m = book_fingerprint()
    print("   book %s  n=%d  mean r %+.4f  %s"
          % (h[:16], n, m, "PINNED" if h == BOOK_SHA else "*** NOT THE PINNED BOOK ***"))


def et_min(hhmm):
    """Minutes since 09:30 from an 'HH:MM' ET stamp."""
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m - 570


def sign_of(row):
    return 1 if row["side"] == "L" else -1


def scale_price(row):
    """The price the 50% scale filled at, recovered EXACTLY from the book.

    `backtest_week.Trade.pnl` books a scaled trade as
        r = 0.5 * scale_r + 0.5 * run_r,     run_r = sign*(exit-entry)/risk
    so  scale_r = 2r - run_r, and the scale price follows. The book does not
    store `scale_level`; this is algebra on fields it does store, not a guess.
    Returns None for an unscaled row (there is no scale leg).
    """
    if not row.get("scaled"):
        return None
    s, risk = sign_of(row), abs(row["entry"] - row["stop"])
    run_r = s * (row["exit"] - row["entry"]) / risk
    scale_r = 2.0 * row["r"] - run_r
    return row["entry"] + s * scale_r * risk


# ---------------------------------------------------------------------------
# the contract model
# ---------------------------------------------------------------------------

class Contract:
    """One row priced as a 0DTE ATM contract. All prices are PER SHARE."""

    def __init__(self, row, iv_mult=HEADLINE_IV, r=0.0, sigma=None,
                 strike_on_grid=False):
        self.row = row
        self.call = row["side"] == "L"
        self.S0 = row["entry"]
        self.K = (osz.nearest_strike(self.S0, row["sym"]) if strike_on_grid
                  else self.S0)
        self.stop = row["stop"]
        self.r = r
        self.risk_u = abs(row["entry"] - row["stop"])         # underlying 1R, $/share

        rng = row.get("drange") or 0.0
        self.sigma = (sigma if sigma is not None
                      else bs.parkinson_sigma(rng, self.S0) * iv_mult)

        t0 = et_min(row["et"])
        t1 = min(RTH_MIN, t0 + max(1, row["bars"]))
        self.min0 = max(RTH_MIN - t0, MIN_T0_MIN)
        self.min1 = max(RTH_MIN - t1, MIN_T1_MIN)
        self.T0 = self.min0 / (RTH_MIN * SESSIONS_YR)
        self.T1 = self.min1 / (RTH_MIN * SESSIONS_YR)

        self.p0 = self.px(self.S0, self.T0)
        self.pstop = self.px(self.stop, self.T0)
        # 1R ON THE CONTRACT = the premium lost when the underlying reaches the
        # stop RIGHT NOW. Defined at T0 because it must be knowable at entry --
        # the exit minute is not. A stop-out is therefore exactly -1R *by
        # construction* at frozen time; anything worse is decay, and that is the
        # point of the `theta` section.
        self.risk = self.p0 - self.pstop
        self.ok = self.risk_u > 0 and rng > 0 and self.risk > 1e-9

    def px(self, S, T):
        return bs.price(S, self.K, T, self.sigma, call=self.call, r=self.r)

    def dlt(self, S, T):
        return bs.delta(S, self.K, T, self.sigma, call=self.call, r=self.r)

    # -- the two exit conventions ------------------------------------------
    def cr_single(self):
        """x13's convention: the whole position exits once, at `row['exit']`."""
        return (self.px(self.row["exit"], self.T1) - self.p0) / self.risk

    def cr_ladder(self, when="mid"):
        """The BOOK's convention: 50% at the recovered scale price, 50% at exit.

        `when` times the scale leg -- 'entry' | 'mid' | 'exit' -- because the
        book does not record the scale bar. Unscaled rows ignore it.
        """
        run = (self.px(self.row["exit"], self.T1) - self.p0) / self.risk
        sp = scale_price(self.row)
        if sp is None:
            return run
        Ts = {"entry": self.T0,
              "mid": 0.5 * (self.T0 + self.T1),
              "exit": self.T1}[when]
        scl = (self.px(sp, Ts) - self.p0) / self.risk
        return 0.5 * scl + 0.5 * run

    def ur_single(self):
        return sign_of(self.row) * (self.row["exit"] - self.S0) / self.risk_u

    def ur_ladder(self):
        """The book's own r, rebuilt from the same algebra. Selfcheck target."""
        run = sign_of(self.row) * (self.row["exit"] - self.S0) / self.risk_u
        sp = scale_price(self.row)
        if sp is None:
            return run
        return 0.5 * (sign_of(self.row) * (sp - self.S0) / self.risk_u) + 0.5 * run

    # -- the exact three-way decomposition ---------------------------------
    def legs(self):
        """delta + convexity + theta == cr_single(), EXACTLY. Not a Taylor series.

            delta leg  d0*(Sx-S0)/risk                      the linear part
            gamma leg  [P(Sx,T0) - P0 - d0*(Sx-S0)]/risk    curvature, time frozen
            theta leg  [P(Sx,T1) - P(Sx,T0)]/risk           decay, price frozen

        The three sum to [P(Sx,T1) - P0]/risk by cancellation, so this is an
        identity over the two variables that moved, not an approximation.
        """
        Sx = self.row["exit"]
        d0 = self.dlt(self.S0, self.T0)
        dS = Sx - self.S0
        px_t0 = self.px(Sx, self.T0)
        px_t1 = self.px(Sx, self.T1)
        dleg = d0 * dS / self.risk
        gleg = (px_t0 - self.p0 - d0 * dS) / self.risk
        tleg = (px_t1 - px_t0) / self.risk
        return dleg, gleg, tleg


def priced(book, iv_mult=HEADLINE_IV, **kw):
    cs = [Contract(r, iv_mult, **kw) for r in book]
    return [c for c in cs if c.ok]


# ---------------------------------------------------------------------------
# 0. HELD-OUT S RECALL -- printed before any in-sample number
# ---------------------------------------------------------------------------

def section_holdout(book):
    print("=== 0. HELD-OUT S RECALL -- reported BEFORE any in-sample number")
    print_fingerprint()
    census = defaultdict(int)
    with open(HELDOUT, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                g = json.loads(line).get("grade_std")
                census["X" if g == "none" else g] += 1
    print("   %s  n=%d" % (os.path.relpath(HELDOUT, _ROOT), sum(census.values())))
    print("   census  S %d / A %d / C %d / X %d"
          % (census["S"], census["A"], census["C"], census["X"]))
    print("   held-out S recall BEFORE T2 : 3/15 = 20.0%   (in-universe 2/12 = 17%)")
    print("   held-out S recall AFTER  T2 : 3/15 = 20.0%   -- UNCHANGED, +0.0 points")
    print("   provenance: `python research/t70_test1_score.py`, re-run for T2,")
    print("               research/t70_test1_score.md regenerated byte-identical.")
    print("   T2 changes NO detection code. It is a SCORING skin on an already-")
    print("   selected book: same rows in, same rows out, a different unit on the")
    print("   P&L. Recall cannot move and it did not. The files T2 touches are")
    print("   black_scholes.py (new), options_sizer.py (sizing only, flag OFF),")
    print("   research/t2_options_tape.{py,md} (new) -- none is on the detection")
    print("   path (signal_runner / backtest_week / backtest_2y / downgrade).")
    assert (census["S"], census["A"], census["C"], census["X"]) == (15, 27, 16, 42), census
    print("   the recall gate is NOT moved by this track. It stays the wound.")


# ---------------------------------------------------------------------------
# 1. THE BOOK -- contract R and underlying R, side by side, three IV arms
# ---------------------------------------------------------------------------

def section_book(book):
    print("=== 1. THE BOOK -- %d traded rows, 2024-08-21..2026-08-21" % len(book))
    print_fingerprint()
    print("   MONEY GATE: mean R >= 2.0 (the gate) and win rate (Austin accepts <55%")
    print("   under the runner system). BOTH halves printed on every line.")
    print()
    print("   -- convention SINGLE: full size to `exit` (x13's prototype) --")
    print("   %-8s %-10s %9s %8s | %9s %8s" %
          ("IV", "n", "CONTRACT", "win%", "UNDERLYING", "win%"))
    for iv in IV_ARMS:
        cs = priced(book, iv)
        co = [c.cr_single() for c in cs]
        uo = [c.ur_single() for c in cs]
        print("   %-8s %-10d %+9.4f %7.1f%% | %+9.4f %7.1f%%"
              % ("%.1fx" % iv, len(cs), mean(co), win(co), mean(uo), win(uo)))
        print("        contract R  p10 %+.2f  p50 %+.2f  p90 %+.2f  max %+.2f"
              % (pct(co, .10), pct(co, .50), pct(co, .90), max(co)))
    print()
    print("   -- convention LADDER: the BOOK's 50/50 scale plan (538 of %d rows scaled) --"
          % len(book))
    print("   %-8s %-10s %9s %8s | %9s %8s" %
          ("IV", "scale@", "CONTRACT", "win%", "UNDERLYING", "win%"))
    for iv in IV_ARMS:
        cs = priced(book, iv)
        uo = [c.ur_ladder() for c in cs]
        for when in ("entry", "mid", "exit"):
            co = [c.cr_ladder(when) for c in cs]
            print("   %-8s %-10s %+9.4f %7.1f%% | %+9.4f %7.1f%%"
                  % ("%.1fx" % iv if when == "entry" else "", when,
                     mean(co), win(co), mean(uo), win(uo)))
    print()
    cs = priced(book, HEADLINE_IV)
    print("   the book's own mean r = %+.4f ; LADDER underlying arm = %+.4f (must match)"
          % (mean(r["r"] for r in book), mean(c.ur_ladder() for c in cs)))
    k = [abs(c.dlt(c.S0, c.T0)) * c.risk_u / c.risk for c in cs]
    print("   linear-scale factor k = |delta0|*risk_u/premium_risk : mean %.4f median %.4f"
          % (mean(k), st.median(k)))
    print("   (k > 1 because premium risk is CONVEX-shrunk: the loss decelerates")
    print("    into the stop, so the contract's 1R buys more underlying than 0.5*d)")


# ---------------------------------------------------------------------------
# 2. PER MONTH  and  3. PER SETUP FAMILY
# ---------------------------------------------------------------------------

def _pair(cs, conv):
    if conv == "single":
        return [c.cr_single() for c in cs], [c.ur_single() for c in cs]
    return [c.cr_ladder("mid") for c in cs], [c.ur_ladder() for c in cs]


def section_month(book):
    print("=== 2. PER MONTH -- IV %.1fx, LADDER convention (the book's own exit plan)"
          % HEADLINE_IV)
    cs = priced(book, HEADLINE_IV)
    bym = defaultdict(list)
    for c in cs:
        bym[c.row["ym"]].append(c)
    print("   %-9s %5s | %9s %7s | %9s %7s | %s"
          % ("month", "n", "CONTRACT", "win%", "UNDERLY", "win%", "green"))
    gc = gu = 0
    for m in sorted(bym):
        co, uo = _pair(bym[m], "ladder")
        c_ok, u_ok = sum(co) > 0, sum(uo) > 0
        gc += c_ok
        gu += u_ok
        print("   %-9s %5d | %+9.4f %6.1f%% | %+9.4f %6.1f%% | C:%s U:%s"
              % (m, len(co), mean(co), win(co), mean(uo), win(uo),
                 "Y" if c_ok else "n", "Y" if u_ok else "n"))
    print("   DURABILITY: green months  CONTRACT %d/%d   UNDERLYING %d/%d"
          % (gc, len(bym), gu, len(bym)))
    print("   (a red month is a month whose SUMMED R is <= 0)")


def section_family(book):
    print("=== 3. PER SETUP FAMILY -- IV %.1fx" % HEADLINE_IV)
    cs = priced(book, HEADLINE_IV)
    byf = defaultdict(list)
    for c in cs:
        byf[c.row["setup"]].append(c)
    for conv in ("single", "ladder"):
        print("   -- %s --" % conv.upper())
        print("   %-18s %5s | %9s %7s | %9s %7s | %8s"
              % ("family", "n", "CONTRACT", "win%", "UNDERLY", "win%", "p90 C"))
        for f in FAMILIES:
            if f not in byf:
                continue
            co, uo = _pair(byf[f], conv)
            print("   %-18s %5d | %+9.4f %6.1f%% | %+9.4f %6.1f%% | %+8.2f"
                  % (f, len(co), mean(co), win(co), mean(uo), win(uo), pct(co, .90)))
    print("   -- WHY the families differ: the legs, SINGLE, IV %.1fx --" % HEADLINE_IV)
    print("   %-18s %5s %9s %9s %9s %9s %9s"
          % ("family", "n", "delta", "convex", "theta", "held med", "prem risk"))
    for f in FAMILIES:
        v = byf.get(f) or []
        if not v:
            continue
        print("   %-18s %5d %+9.4f %+9.4f %+9.4f %9.0f %9.3f"
              % (f, len(v), mean(c.legs()[0] for c in v), mean(c.legs()[1] for c in v),
                 mean(c.legs()[2] for c in v),
                 st.median([c.min0 - c.min1 for c in v]),
                 st.median([c.risk for c in v])))
    print("   -- by outcome label, LADDER, IV %.1fx --" % HEADLINE_IV)
    byo = defaultdict(list)
    for c in cs:
        byo[c.row["out"]].append(c)
    for o in ("win", "loss", "scratch"):
        if o not in byo:
            continue
        co, uo = _pair(byo[o], "ladder")
        print("   %-18s %5d | %+9.4f %6.1f%% | %+9.4f %6.1f%%"
              % (o, len(co), mean(co), win(co), mean(uo), win(uo)))


# ---------------------------------------------------------------------------
# 4. THETA vs CONVEXITY -- the decomposition Austin's runner thesis is a bet on
# ---------------------------------------------------------------------------

def section_theta(book):
    print("=== 4. THETA vs CONVEXITY -- decomposed, SINGLE convention, IV %.1fx"
          % HEADLINE_IV)
    cs = priced(book, HEADLINE_IV)
    rows = [(c, c.legs()) for c in cs]
    d = [l[0] for _, l in rows]
    g = [l[1] for _, l in rows]
    t = [l[2] for _, l in rows]
    tot = [c.cr_single() for c in cs]
    resid = max(abs(a + b + e - x) for (a, b, e), x in zip((l for _, l in rows), tot))
    print("   identity  delta + convexity + theta == contract R   max residual %.2e" % resid)
    print("   %-14s %+9s %+9s %+9s %+9s" % ("", "mean", "median", "p10", "p90"))
    for lbl, v in (("delta leg", d), ("convexity leg", g), ("theta leg", t),
                   ("= contract R", tot)):
        print("   %-14s %+9.4f %+9.4f %+9.4f %+9.4f"
              % (lbl, mean(v), st.median(v), pct(v, .10), pct(v, .90)))
    print("   underlying R (same rows, SINGLE) %+9.4f" % mean(c.ur_single() for c in cs))
    print()
    print("   convexity beats theta by %+.4f R per trade on the whole book."
          % (mean(g) + mean(t)))
    print("   holding minutes: median %d  p90 %d  max %d"
          % (st.median([c.min0 - c.min1 for c in cs]),
             pct([c.min0 - c.min1 for c in cs], .90),
             max(c.min0 - c.min1 for c in cs)))
    print()
    print("   -- split by outcome: where each leg is actually earned or paid --")
    print("   %-10s %5s %9s %9s %9s %9s" %
          ("out", "n", "delta", "convex", "theta", "contract"))
    byo = defaultdict(list)
    for c, l in rows:
        byo[c.row["out"]].append((c, l))
    for o in ("win", "loss", "scratch"):
        v = byo.get(o) or []
        if not v:
            continue
        print("   %-10s %5d %+9.4f %+9.4f %+9.4f %+9.4f"
              % (o, len(v), mean(l[0] for _, l in v), mean(l[1] for _, l in v),
                 mean(l[2] for _, l in v), mean(c.cr_single() for c, _ in v)))
    print()
    print("   -- by HOLDING TIME: where convexity stops beating theta --")
    print("   %-14s %5s %9s %9s %9s %9s" %
          ("held (min)", "n", "convex", "theta", "net", "contract"))
    buckets = [(0, 5), (5, 15), (15, 30), (30, 60), (60, 120), (120, 10 ** 9)]
    for lo_, hi_ in buckets:
        v = [(c, l) for c, l in rows if lo_ <= (c.min0 - c.min1) < hi_]
        if not v:
            continue
        g_ = mean(l[1] for _, l in v)
        t_ = mean(l[2] for _, l in v)
        print("   %-14s %5d %+9.4f %+9.4f %+9.4f %+9.4f"
              % ("%d-%d" % (lo_, hi_) if hi_ < 10 ** 8 else "%d+" % lo_,
                 len(v), g_, t_, g_ + t_, mean(c.cr_single() for c, _ in v)))
    print("   Austin's runner thesis is exactly this table: convexity has to")
    print("   out-earn decay for as long as he holds. Where the net column goes")
    print("   negative, the 0DTE contract is the WRONG instrument for that hold.")
    print()
    print("   THE STOP-OUT ARM, stated exactly:")
    lo = byo.get("loss") or []
    print("     a stop-out is -1.0000 R by construction at FROZEN time (selfcheck).")
    print("     realised, the same %d rows book %+.4f R, because %.1f minutes of"
          % (len(lo), mean(c.cr_single() for c, _ in lo),
             mean(c.min0 - c.min1 for c, _ in lo)))
    print("     decay ran before the stop closed. The gap IS the theta leg: %+.4f R."
          % mean(l[2] for _, l in lo))
    print("     Underlying scores those rows a flat -1.0000. The contract does not.")
    print()
    print("   THE -1.25R FLOOR, WHICH HAS NEVER BOUND ON A SINGLE UNDERLYING ROW:")
    co = [c.cr_single() for c in cs]
    cl = [c.cr_ladder("mid") for c in cs]
    print("     underlying rows worse than -1.25R : %d of %d"
          % (sum(1 for r in book if r["r"] < -1.25), len(book)))
    for nm, v in (("contract SINGLE", co), ("contract LADDER", cl)):
        print("     %-16s worse than -1.25R : %d of %d (%.1f%%)  min %+.3f R"
              % (nm, sum(1 for x in v if x < -1.25), len(v),
                 100.0 * sum(1 for x in v if x < -1.25) / len(v), min(v)))
    cap = [-c.p0 / c.risk for c in cs]
    print("     WHY: a stop that triggers on the UNDERLYING does not cap the")
    print("     CONTRACT's loss. Max loss is the whole premium, -p0/risk:")
    print("     median %+.2f R  p10 %+.2f R  worst %+.2f R -- so 'flat on the stock'"
          % (st.median(cap), pct(cap, .10), min(cap)))
    print("     can be several R on the option, paid entirely in decay.")
    print("     This is the single largest thing DEFAULT_DELTA = 0.5 hides.")


# ---------------------------------------------------------------------------
# 5. ASSUMPTIONS AND THEIR SENSITIVITY
# ---------------------------------------------------------------------------

_prior_cache = {}


def prior_session_range(sym, day):
    """RTH high-low of the most recent session BEFORE `day` in data_archive.

    Ex-ante by construction: it uses only bars that closed before the trade's
    session opened. Returns None when there is no earlier file on disk.
    """
    key = (sym, day)
    if key in _prior_cache:
        return _prior_cache[key]
    d = os.path.join(ARCHIVE, sym)
    if not os.path.isdir(d):
        _prior_cache[key] = None
        return None
    prev = [f for f in sorted(os.listdir(d))
            if f.endswith(".csv") and f[:-4] < day]
    out = None
    if prev:
        hi, lo = -1e18, 1e18
        with open(os.path.join(d, prev[-1]), newline="") as fh:
            for row in csv.DictReader(fh):
                hhmm = row["Datetime"][11:16]
                if "09:30" <= hhmm <= "15:59":
                    hi = max(hi, float(row["High"]))
                    lo = min(lo, float(row["Low"]))
        if hi > lo:
            out = hi - lo
    _prior_cache[key] = out
    return out


def section_assume(book):
    print("=== 5. ASSUMPTIONS -- every one, and what the headline does without it")
    base_cs = priced(book, HEADLINE_IV)
    base_single = mean(c.cr_single() for c in base_cs)
    base_ladder = mean(c.cr_ladder("mid") for c in base_cs)
    ur = mean(r["r"] for r in book)
    print("   HEADLINE  SINGLE %+0.4f | LADDER(mid) %+0.4f | underlying %+0.4f  (IV %.1fx)"
          % (base_single, base_ladder, ur, HEADLINE_IV))
    print("   error bar on an A/B of this book: +/-0.0095 R. Anything under that is noise.")
    print()

    def show(lbl, cs, note=""):
        sv = [c.cr_single() for c in cs]
        lv = [c.cr_ladder("mid") for c in cs]
        s, l = mean(sv), mean(lv)
        print("   %-40s SINGLE %+0.4f (%+0.4f) med %+0.4f | LADDER %+0.4f (%+0.4f) %s"
              % (lbl, s, s - base_single, st.median(sv), l, l - base_ladder, note))

    print("   A1 IV LEVEL -- modelled, no options tape exists.")
    for iv in IV_ARMS:
        show("   IV = %.1fx realised Parkinson" % iv, priced(book, iv))

    print("   A2 IV IS LOOK-AHEAD -- `drange` is the FULL SESSION range, unknown")
    print("      at 09:42. Re-priced on the PRIOR session's RTH range instead:")
    ex = []
    missing = 0
    for r in book:
        pr = prior_session_range(r["sym"], r["day"])
        if pr is None:
            missing += 1
            continue
        c = Contract(r, sigma=bs.parkinson_sigma(pr, r["entry"]) * HEADLINE_IV)
        if c.ok:
            ex.append(c)
    same = [c for c in base_cs
            if (c.row["sym"], c.row["day"]) in {(x.row["sym"], x.row["day"]) for x in ex}]
    print("      n=%d (%d rows have no earlier session on disk)" % (len(ex), missing))
    show("   ex-ante IV (prior session Parkinson)", ex,
         "vs same-rows realised %+0.4f" % mean(c.cr_single() for c in same))

    print("   A3 STRIKE IS PERFECTLY ATM (K = entry). Real strikes sit on a")
    print("      $1-$5 grid (`options_sizer.STRIKE_INCREMENT`):")
    grid = priced(book, HEADLINE_IV, strike_on_grid=True)
    show("   K rounded to the symbol's strike grid", grid)
    blow = [c for c in grid if abs(c.cr_single()) > 25.0]
    print("      READ THE MEDIAN, NOT THE MEAN, ON THIS ROW. Off ATM the premium")
    print("      risk -- the R DENOMINATOR -- can collapse: min $%.4f here against"
          % min(c.risk for c in grid))
    print("      $%.4f at the money, and %d rows blow past |25 R| (max %+.1f R)."
          % (min(c.risk for c in base_cs), len(blow),
             max(c.cr_single() for c in grid)))
    print("      The median barely moves. So the ATM assumption is load-bearing")
    print("      for the UNIT, not for the centre -- a real strike grid needs a")
    print("      minimum-premium guard before contract R is quotable per trade.")

    print("   A4 CARRY r = q = 0 over a 0DTE contract:")
    show("   r = 5% annual", priced(book, HEADLINE_IV, r=0.05))

    print("   A5 FILL AT MID, ZERO SPREAD. Nobody in this repo has read a real")
    print("      NBBO on these contracts (x9 2.2: Polygon 403, Tastytrade auth).")
    print("      A round-trip spread costs `spread / premium_risk` in CONTRACT R:")
    print("      %-10s %8s %8s %10s %10s" %
          ("spread", "medianR", "meanR", "SINGLE", "LADDER"))
    for sp in (0.01, 0.02, X9_ROUND_TRIP_SPREAD, 0.10, 0.15):
        cost = [sp / c.risk for c in base_cs]
        print("      $%-9.2f %8.4f %8.4f %+10.4f %+10.4f"
              % (sp, st.median(cost), mean(cost),
                 base_single - mean(cost), base_ladder - mean(cost)))
    breakeven = base_ladder / mean(1.0 / c.risk for c in base_cs)
    print("      the LADDER contract edge dies at a $%.3f round-trip spread." % breakeven)
    prem = [c.risk for c in base_cs]
    print("      modelled premium risk per share: median $%.2f  p10 $%.2f  p90 $%.2f"
          % (st.median(prem), pct(prem, .10), pct(prem, .90)))
    print("      x9 carried $%.2f as its assumption and charged the UNDERLYING book"
          % X9_ROUND_TRIP_SPREAD)
    print("      -0.2042R for it. On the CONTRACT the same nickel costs %.4fR --"
          % mean(X9_ROUND_TRIP_SPREAD / c.risk for c in base_cs))
    print("      the contract's 1R is a THINNER unit, so the same cents hurt more.")

    print("   A6 ENTRY AND EXIT PRICES ARE THE BOOK'S. x9 2.1 measured that 961 of")
    print("      1,017 book a price the bar traded before it closed (-0.6653R if")
    print("      you pay the close). Contract R INHERITS that optimism whole; it")
    print("      is not re-litigated here and it is not additive with A5 by hand.")
    print("   A7 FLAT VOL SURFACE: one sigma, entry to exit, no smile, no term")
    print("      structure, no IV crush on the news-day setups. Unmeasurable here.")
    print("   A8 EXPIRY = the 16:00 close; time floored at %.1f min at entry and"
          % MIN_T0_MIN)
    print("      %.1f min at exit so a run-to-the-bell prices instead of dividing" % MIN_T1_MIN)
    print("      by zero. %d of %d rows exit inside the last 5 minutes."
          % (sum(1 for c in base_cs if c.min1 <= 5.0), len(base_cs)))
    print("   A9 NO COMMISSION, NO MARKET IMPACT, CONTINUOUS SIZE. x9 2.2: the")
    print("      sizer wants a median 47 and up to 200 contracts of a 0DTE ATM")
    print("      option filled at the mid. Not modelled anywhere, including here.")


# ---------------------------------------------------------------------------
# 6. SELFCHECK
# ---------------------------------------------------------------------------

def selfcheck():
    print("=== T2 SELFCHECK")
    print_fingerprint()
    h, _, _ = book_fingerprint()
    assert h == BOOK_SHA, (
        "g3_arm_ow1.json is not the book research/t2_options_tape.md was measured "
        "on (%s != %s). Another track has moved it. Regenerate the .md; do not "
        "read its numbers against this book." % (h[:16], BOOK_SHA[:16]))
    book = load_book()
    assert len(book) == 1017, len(book)

    # ---- 1. a stop-out is EXACTLY -1R by construction --------------------
    worst = 0.0
    for r in book:
        c = Contract(r, HEADLINE_IV)
        if not c.ok:
            continue
        worst = max(worst, abs((c.px(c.stop, c.T0) - c.p0) / c.risk + 1.0))
    assert worst < 1e-12, worst
    print("  [ok] stop-out == -1R by construction on all %d rows (max dev %.2e)"
          % (len(book), worst))

    # ---- 2. the LADDER underlying arm reproduces the book exactly ---------
    cs = priced(book, HEADLINE_IV)
    devs = [(abs(c.ur_ladder() - c.row["r"]), c.row["out"]) for c in cs]
    exact = sum(1 for d, _ in devs if d < 1e-9)
    rest = [(d, o) for d, o in devs if d >= 1e-9]
    # The only rows that are not exact are the 5 EOD scratches, where the book
    # writer rounds `r` to 3dp and the algebra cannot recover the lost digits.
    # Max 0.0016 R on 5 of 1,017 rows -- 5e-6 R on the book mean, three orders
    # below the +/-0.0095 R error bar.
    assert exact == len(cs) - 5, exact
    assert all(o == "scratch" for _, o in rest), rest
    assert max(d for d, _ in rest) < 2e-3, rest
    dmean = abs(mean(c.ur_ladder() for c in cs) - mean(r["r"] for r in book))
    assert dmean < 1e-5, dmean
    print("  [ok] recovered 50/50 ladder reproduces %d/%d book r exactly; the 5"
          % (exact, len(cs)))
    print("       EOD scratches differ by <=%.4f R (book rounds r to 3dp), and"
          % max(d for d, _ in rest))
    print("       the book mean moves %.2e R -- under the +/-0.0095 error bar" % dmean)

    # ---- 3. the decomposition is an identity, not an approximation --------
    worst = 0.0
    for c in cs:
        d, g, t = c.legs()
        worst = max(worst, abs(d + g + t - c.cr_single()))
    assert worst < 1e-9, worst
    print("  [ok] delta + convexity + theta == contract R (max residual %.2e)" % worst)

    # ---- 4. signs: long options are convex, and they decay ---------------
    g_neg = sum(1 for c in cs if c.legs()[1] < -1e-12)
    t_pos = sum(1 for c in cs if c.legs()[2] > 1e-12)
    assert g_neg == 0 and t_pos == 0, (g_neg, t_pos)
    print("  [ok] convexity leg >= 0 and theta leg <= 0 on all %d rows" % len(cs))

    # ---- 5. the x13 prototype's figures are reproduced --------------------
    want = {1.0: 1.4988, 1.2: 1.3551, 1.5: 1.1941}
    for iv, target in want.items():
        got = mean(c.cr_single() for c in priced(book, iv))
        assert abs(got - target) < 5e-4, (iv, got, target)
        print("  [ok] IV %.1fx SINGLE = %+.4f  (x13 prototype %+.4f)" % (iv, got, target))
    w = win([c.cr_single() for c in priced(book, HEADLINE_IV)])
    assert abs(w - 38.5) < 0.1, w
    print("  [ok] contract win rate %.1f%% (x13 38.5%%) vs underlying %.1f%%"
          % (w, win(r["r"] for r in book)))

    # ---- 6. ENABLE_CONTRACT_R ships OFF and changes nothing off -----------
    assert osz.ENABLE_CONTRACT_R is False, "ENABLE_CONTRACT_R must default OFF"
    assert osz.atm_delta("call", 100.0, 100.0, 0.5, 300.0) == osz.DEFAULT_DELTA
    a = osz.build_options_plan("NVDA", "call", 128.00, 127.89)
    b = osz.build_options_plan("NVDA", "call", 128.00, 127.89,
                               iv=0.55, minutes_to_expiry=348)
    assert (a.entry_premium, a.stop_premium, a.target_premium, a.contracts) == \
           (b.entry_premium, b.stop_premium, b.target_premium, b.contracts), (a, b)
    print("  [ok] ENABLE_CONTRACT_R defaults OFF; iv/minutes are inert while it is")

    # ---- 7. the 2-year book cannot see this flag at all -------------------
    src = open(os.path.join(_ROOT, "backtest_2y.py")).read()
    src += open(os.path.join(_ROOT, "backtest_week.py")).read()
    src += open(os.path.join(_ROOT, "signal_runner.py")).read()
    assert "options_sizer" not in src and "black_scholes" not in src
    print("  [ok] backtest_2y / backtest_week / signal_runner import neither")
    print("       options_sizer nor black_scholes -- the book is structurally")
    print("       unreachable from this flag. Empirically re-proved in the .md.")

    print("ALL T2 SELFCHECKS PASSED")


SECTIONS = {"holdout": section_holdout, "book": section_book,
            "month": section_month, "family": section_family,
            "theta": section_theta, "assume": section_assume}

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selfcheck" in args:
        selfcheck()
    else:
        bk = load_book()
        for nm in ([a for a in args if not a.startswith("-")] or list(SECTIONS)):
            SECTIONS[nm](bk)
            print()
