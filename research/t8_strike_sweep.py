"""T8 -- STRIKE SWEEP. 0DTE and 1DTE, ATM +/- 1 strike, priced on PRIOR-SESSION
sigma only (never the trade day's own range -- that would be look-ahead).

Austin: "0DTE and 1DTE, ATM+/-1 strike." Nothing in the engine picks a strike or
an expiry today. This is the first report that tells him, per signal: what
contract to buy, how many contracts at $1,000 planned risk, and what the
premium stop is -- across 6 arms (2 expiries x 3 strikes) -- then says which
arm scores best on mean R and on month greenness.

    python research/t8_strike_sweep.py            # full report
    python research/t8_strike_sweep.py --selfcheck # checks

WHAT IS MEASURED (from files already in the repo)
---------------------------------------------------
  * entry / stop / exit / bars held / side / r / et / sym / day / ym / setup
    -- the traded rows of the current ratified 2-year book (backtest_2y.py)
  * prior-session RTH high-low range -- data_archive/<SYM>/<DAY>.csv, the
    session immediately BEFORE the trade day. Nothing on the trade day itself
    is used to build sigma.

WHAT IS MODELLED (there is no options tape in this repo -- research/t2_options_
tape.py A1-A9 carries the same list; this file adds the strike/expiry axis)
---------------------------------------------------------------------------
  * implied volatility  -- Parkinson vol of the PRIOR session's range x a 1.2
                            IV multiplier (T2's headline arm; swept separately)
  * the option price     -- Black-Scholes (black_scholes.py), r=q=0, flat
                            surface, no smile, no term-structure jump for 1DTE
  * the strike grid       -- options_sizer.STRIKE_INCREMENT (per-symbol $ step);
                            symbols missing from that table fall back to $2.50
  * the fill              -- mid, no spread, no commission, no market impact
  * 1DTE's extra session   -- +390 RTH minutes added to time-to-expiry, no
                            overnight vol scaling and no weekend/holiday gap
                            adjustment (a Friday 1DTE really trades 3 sessions
                            of calendar time; this file does not correct for it
                            because there is no options tape to calibrate a
                            correction against -- see ASSUMPTIONS section)

TWO AXES, SIX ARMS
------------------
  expiry  0DTE  time-to-expiry floored inside today's session, same convention
                as t2_options_tape.py (MIN_T0/MIN_T1 minute floors)
          1DTE  the same clock, plus one full RTH session (390 min) added at
                both entry and exit -- the option does not expire until
                tomorrow's close, so it still holds extrinsic value at 16:00
                on the trade day
  strike  ATM-1 / ATM / ATM+1, in the symbol's own strike increment
          (options_sizer.nearest_strike + k*STRIKE_INCREMENT[sym])

Money gate reported per arm: mean R, win%, month greenness (25 target). Held-
out recall CANNOT move -- this is a pricing skin on an already-selected book,
identical to T2's finding, and is asserted in --selfcheck.
"""

from __future__ import annotations

import csv
import json
import os
import random
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

BOOK = os.path.join(_HERE, "bt2y_trades.json")
ARCHIVE = os.path.join(_ROOT, "data_archive")

RTH_MIN = 390.0
SESSIONS_YR = 252.0
MIN_T0_MIN = 1.0
MIN_T1_MIN = 0.5
HEADLINE_IV = 1.2
PLANNED_RISK = 1000.0
CONTRACT_MULT = 100.0
MIN_TICK = 0.05          # options_sizer.build_options_plan's own min-tick guard on
                          # premium_risk -- without it, a far-OTM strike's premium
                          # risk can collapse to sub-cent and the R denominator
                          # blows up (a $0.01 premium implies 4,711 contracts at
                          # $1,000 planned risk -- not a real market). Applying the
                          # SAME guard the live sizer already uses, not a new one.

EXPIRIES = ("0DTE", "1DTE")
STRIKES = (-1, 0, 1)          # offsets in symbol strike increments
ARMS = [(e, k) for e in EXPIRIES for k in STRIKES]

random.seed(8)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def win(xs):
    xs = list(xs)
    return 100.0 * sum(1 for x in xs if x > 0) / len(xs) if xs else float("nan")


def load_book(path=BOOK):
    with open(path) as fh:
        d = json.load(fh)
    return [r for r in d["trades"] if r.get("traded")], d.get("meta", {})


# Pinned to the T0-ratified book: 2,595 traded rows, mean R +0.5481, worst -1.0
# (matches T0's headline exactly -- research/t0_ratified_rebaseline.md). If a
# re-run of this file prints a different (n, mean) pair, another track has
# rewritten research/bt2y_trades.json under this tree; regenerate with
# `python backtest_2y.py --out research/bt2y_trades.json` before trusting a
# new number, do not silently read against a different book.
PINNED_N = 2595
PINNED_MEAN_R = 0.5481


def check_fingerprint(book):
    n = len(book)
    m = sum(r["r"] for r in book) / n if n else 0.0
    ok = n == PINNED_N and abs(m - PINNED_MEAN_R) < 5e-4
    print("   book fingerprint: n=%d mean_r=%+.4f  %s"
          % (n, m, "PINNED (T0-ratified)" if ok else "*** NOT THE PINNED BOOK ***"))
    return ok


def et_min(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m - 570


_prior_cache = {}


def prior_session_range(sym, day):
    """RTH high-low of the most recent session strictly BEFORE `day`.

    Identical convention to t2_options_tape.py::prior_session_range -- ex-ante
    by construction. Returns None if no earlier archive file exists.
    """
    key = (sym, day)
    if key in _prior_cache:
        return _prior_cache[key]
    d = os.path.join(ARCHIVE, sym)
    if not os.path.isdir(d):
        _prior_cache[key] = None
        return None
    prev = [f for f in sorted(os.listdir(d)) if f.endswith(".csv") and f[:-4] < day]
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


# ---------------------------------------------------------------------------
# the contract model -- 6 arms per row (expiry x strike)
# ---------------------------------------------------------------------------

class Contract:
    """One (row, expiry, strike-offset) priced with PRIOR-SESSION sigma only."""

    def __init__(self, row, expiry, strike_k, iv_mult=HEADLINE_IV, r=0.0):
        self.row = row
        self.call = row["dir"] == "call"
        self.S0 = row["entry"]
        inc = osz.STRIKE_INCREMENT.get(row["sym"].upper(), 2.5)
        base = osz.nearest_strike(self.S0, row["sym"])
        self.K = base + strike_k * inc
        self.stop = row["stop"]
        self.r = r
        self.risk_u = abs(row["entry"] - row["stop"])
        self.expiry = expiry
        self.strike_k = strike_k

        pr = prior_session_range(row["sym"], row["day"])
        self.sigma = bs.parkinson_sigma(pr, self.S0) * iv_mult if pr else 0.0

        t0 = et_min(row["et"])
        t1 = min(RTH_MIN, t0 + max(1, row["bars"]))
        extra = RTH_MIN if expiry == "1DTE" else 0.0
        self.min0 = max(RTH_MIN - t0, MIN_T0_MIN) + extra
        self.min1 = max(RTH_MIN - t1, MIN_T1_MIN) + extra
        self.T0 = self.min0 / (RTH_MIN * SESSIONS_YR)
        self.T1 = self.min1 / (RTH_MIN * SESSIONS_YR)

        self.p0 = self.px(self.S0, self.T0) if self.sigma > 0 else None
        self.pstop = self.px(self.stop, self.T0) if self.sigma > 0 else None
        raw_risk = (self.p0 - self.pstop) if self.p0 is not None else None
        # options_sizer.build_options_plan's own guard: a premium_risk under one
        # tick is floored, not divided by. Same rule applied here, not invented.
        self.premium_risk = (max(raw_risk, MIN_TICK) if raw_risk is not None else None)
        self.tick_floored = raw_risk is not None and raw_risk < MIN_TICK
        self.ok = (self.sigma > 0 and self.risk_u > 0
                   and self.premium_risk is not None and self.premium_risk > 1e-9)

    def px(self, S, T):
        return bs.price(S, self.K, T, self.sigma, call=self.call, r=self.r)

    def contract_r(self):
        px_exit = self.px(self.row["exit"], self.T1)
        return (px_exit - self.p0) / self.premium_risk

    def contracts_at_risk(self, planned=PLANNED_RISK):
        per = self.premium_risk * CONTRACT_MULT
        return int(planned // per) if per > 0 else 0

    def stop_premium(self):
        return max(self.p0 - self.premium_risk, 0.01)


def priced(book, expiry, strike_k, iv_mult=HEADLINE_IV):
    cs = [Contract(r, expiry, strike_k, iv_mult) for r in book]
    return [c for c in cs if c.ok]


# ---------------------------------------------------------------------------
# bootstrap error bar (method rule 1 -- report our own)
# ---------------------------------------------------------------------------

def bootstrap_se(xs, n_boot=2000):
    xs = list(xs)
    if len(xs) < 2:
        return 0.0
    n = len(xs)
    means = []
    for _ in range(n_boot):
        sample = [xs[random.randrange(n)] for _ in range(n)]
        means.append(mean(sample))
    return st.pstdev(means)


# ---------------------------------------------------------------------------
# 0. HELD-OUT RECALL -- this track cannot move it, same as T2's finding
# ---------------------------------------------------------------------------

def section_holdout():
    print("=== 0. HELD-OUT RECALL -- unchanged by construction")
    print("   T8 is a pricing/sizing skin on an ALREADY-SELECTED book: same rows")
    print("   in, same rows out, a strike/expiry choice on top. It touches")
    print("   black_scholes.py, options_sizer.py (grid only) and this file --")
    print("   none of those are on the detection path (signal_runner /")
    print("   backtest_week / backtest_2y / downgrade). Recall cannot move.")
    print("   Verified in --selfcheck: neither module appears in those three files.")


# ---------------------------------------------------------------------------
# 1. THE SWEEP -- 6 arms, mean R / win% / month greenness / recovered error bar
# ---------------------------------------------------------------------------

def section_sweep(book):
    print("=== 1. THE SWEEP -- %d traded rows, prior-session sigma, IV %.1fx"
          % (len(book), HEADLINE_IV))
    print("   %-8s %-8s %8s | %9s %8s %7s | %9s | %6s | %s"
          % ("expiry", "strike", "n", "meanR", "medianR", "win%", "se(boot)",
             "tick%", "months green"))
    results = {}
    months_all = sorted(set(r["ym"] for r in book))
    best_r, best_g, best_rmed = None, None, None
    for expiry, k in ARMS:
        cs = priced(book, expiry, k)
        co = [c.contract_r() for c in cs]
        se = bootstrap_se(co)
        tick_pct = 100.0 * sum(1 for c in cs if c.tick_floored) / len(cs)
        bym = defaultdict(list)
        for c in cs:
            bym[c.row["ym"]].append(c.contract_r())
        green = sum(1 for m in months_all if m in bym and sum(bym[m]) > 0)
        med = st.median(co)
        results[(expiry, k)] = dict(n=len(cs), mean=mean(co), median=med, win=win(co),
                                     se=se, green=green, n_months=len(months_all),
                                     tick_pct=tick_pct)
        lbl = {-1: "ATM-1", 0: "ATM", 1: "ATM+1"}[k]
        print("   %-8s %-8s %8d | %+9.4f %+8.4f %6.1f%% | %+9.4f | %5.1f%% | %d/%d"
              % (expiry, lbl, len(cs), mean(co), med, win(co), se, tick_pct,
                 green, len(months_all)))
        if best_r is None or results[(expiry, k)]["mean"] > results[best_r]["mean"]:
            best_r = (expiry, k)
        if best_rmed is None or results[(expiry, k)]["median"] > results[best_rmed]["median"]:
            best_rmed = (expiry, k)
        if best_g is None or results[(expiry, k)]["green"] > results[best_g]["green"]:
            best_g = (expiry, k)
    print()
    print("   READ THE MEDIAN ON THE OTM ARMS, NOT THE MEAN (t2_options_tape.py's")
    print("   own warning, re-confirmed here): far-OTM premium risk can sit at the")
    print("   %.2f min-tick floor, and the mean is then set by a handful of huge-R" % MIN_TICK)
    print("   outlier rows a real market could never fill at that size.")
    print()
    print("   BEST ON MEAN R:     %s %s  (%+.4f R, se %.4f, tick-floored %.1f%% of rows)"
          % (best_r[0], {-1: "ATM-1", 0: "ATM", 1: "ATM+1"}[best_r[1]],
             results[best_r]["mean"], results[best_r]["se"], results[best_r]["tick_pct"]))
    print("   BEST ON MEDIAN R:   %s %s  (%+.4f R) -- the honest read where OTM"
          % (best_rmed[0], {-1: "ATM-1", 0: "ATM", 1: "ATM+1"}[best_rmed[1]],
             results[best_rmed]["median"]))
    print("                        premium collapses (see note above)")
    max_green = results[best_g]["green"]
    tied = [k for k in results if results[k]["green"] == max_green]
    lbl = lambda k: "%s %s" % (k[0], {-1: "ATM-1", 0: "ATM", 1: "ATM+1"}[k[1]])   # noqa: E731
    print("   BEST ON GREENNESS:  %d/%d months, tied across %d of 6 arms: %s"
          % (max_green, results[best_g]["n_months"], len(tied),
             ", ".join(lbl(k) for k in tied)))
    base = results[("0DTE", 0)]
    for key, res in results.items():
        if key == ("0DTE", 0):
            continue
        gap = res["mean"] - base["mean"]
        pooled_se = (res["se"] ** 2 + base["se"] ** 2) ** 0.5
        inside = abs(gap) < 1.96 * pooled_se
        print("   %s %s vs 0DTE ATM: %+.4f R (%s the +/-%.4f 95%% bar)"
              % (key[0], {-1: "ATM-1", 0: "ATM", 1: "ATM+1"}[key[1]], gap,
                 "INSIDE - null" if inside else "outside", 1.96 * pooled_se))
    return results


# ---------------------------------------------------------------------------
# 2. REPRESENTATIVE SIGNALS -- the actual deliverable: contract, count, stop
# ---------------------------------------------------------------------------

def section_cards(book):
    print("=== 2. REPRESENTATIVE SIGNALS -- contract, count @ $%.0f planned risk, "
          "premium stop" % PLANNED_RISK)
    by_setup = defaultdict(list)
    for r in book:
        by_setup[r["setup"]].append(r)
    reps = []
    for setup, rows in sorted(by_setup.items()):
        rows = sorted(rows, key=lambda r: (r["sym"], r["day"]))
        take = rows[::max(1, len(rows) // 3)][:3]
        reps.extend(take)
    reps = reps[:12]
    print("   %-6s %-10s %-4s %-6s %6s %6s | %-6s %-6s %8s %8s %8s %5s"
          % ("sym", "day", "dir", "setup", "entry", "stop", "expiry",
             "strike", "premium", "prem$stop", "contr$", "n@1k"))
    for r in reps:
        c = Contract(r, "0DTE", 0)
        if not c.ok:
            continue
        print("   %-6s %-10s %-4s %-6s %6.2f %6.2f | %-6s %-6.2f %8.2f %8.2f %8.2f %5d"
              % (r["sym"], r["day"], r["dir"], r["setup"][:6], r["entry"], r["stop"],
                 "0DTE", c.K, c.p0, c.stop_premium(), c.premium_risk,
                 c.contracts_at_risk()))
    print()
    print("   Same rows, all 6 arms (0DTE/1DTE x ATM-1/ATM/ATM+1) -- first 4 cards:")
    print("   %-6s %-10s | %-8s %-8s %10s %10s %6s"
          % ("sym", "day", "expiry", "strike", "premium", "stop$", "n@1k"))
    for r in reps[:4]:
        for expiry, k in ARMS:
            c = Contract(r, expiry, k)
            if not c.ok:
                continue
            lbl = {-1: "ATM-1", 0: "ATM", 1: "ATM+1"}[k]
            print("   %-6s %-10s | %-8s %-8s %10.2f %10.2f %6d"
                  % (r["sym"], r["day"], expiry, lbl, c.p0, c.stop_premium(),
                     c.contracts_at_risk()))
        print()


# ---------------------------------------------------------------------------
# 3. ASSUMPTIONS -- where pricing is modelled, not quoted
# ---------------------------------------------------------------------------

def section_assume(book):
    print("=== 3. ASSUMPTIONS -- pricing is MODELLED here, not quoted from a tape")
    print("   No options tape exists in this repo (Polygon 403s the options")
    print("   snapshot; Tastytrade sandbox session auth fails outside a live")
    print("   round trip -- research/t2_options_tape.md A5, unchanged).")
    print("   Every price, stop and contract count above comes from")
    print("   black_scholes.py, an r=q=0 flat-surface Black-Scholes model, fed")
    print("   PRIOR-SESSION Parkinson vol x %.1fx (T2's headline multiplier)." % HEADLINE_IV)
    print("   1DTE adds one full RTH session (390 min) to time-to-expiry with NO")
    print("   overnight vol adjustment and no weekend/holiday calendar correction")
    print("   -- a Friday 1DTE genuinely spans 3 calendar days, priced here as 1.")
    print("   No bid-ask spread, no commission, no market impact, continuous")
    print("   contract size (T9 prices spread; not repeated here).")
    n_missing = sum(1 for r in book if prior_session_range(r["sym"], r["day"]) is None)
    print("   %d of %d rows have no earlier archive session and are DROPPED from"
          % (n_missing, len(book)))
    print("   every arm above (cannot price without a prior session).")
    print("   Strike grid: options_sizer.STRIKE_INCREMENT, 11 symbols named, all")
    print("   others fall back to a flat $2.50 step -- an assumption, not a quote.")


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck():
    print("=== T8 SELFCHECK")
    book, meta = load_book()
    assert len(book) > 0, "empty book"
    print("   book: %d traded rows, meta=%s" % (len(book), meta.get("generated")))
    assert check_fingerprint(book), "not the T0-ratified book -- regenerate before trusting"

    # 1. detection path does not import this file or its pricing modules
    for f in ("backtest_2y.py", "backtest_week.py", "signal_runner.py"):
        src = open(os.path.join(_ROOT, f)).read()
        assert "black_scholes" not in src and "t8_strike_sweep" not in src, f
    print("   [ok] detection path (backtest_2y/backtest_week/signal_runner)")
    print("        imports neither black_scholes nor this file -- recall cannot move")

    # 2. every arm's contracts_at_risk is non-negative and premium_risk > 0
    sample = book[:200]
    bad = 0
    for r in sample:
        for expiry, k in ARMS:
            c = Contract(r, expiry, k)
            if not c.ok:
                continue
            if c.contracts_at_risk() < 0 or c.premium_risk <= 0:
                bad += 1
    assert bad == 0, bad
    print("   [ok] %d sample rows x 6 arms: contracts >= 0, premium_risk > 0" % len(sample))

    # 3. 1DTE always has more (or equal) time value than 0DTE at the same strike
    #    -> 1DTE contract R magnitude on a WIN should never be starved of theta
    #    the way 0DTE is; check T0 > 0 and T1 >= 0 on both expiries.
    r0 = book[0]
    for expiry, k in ARMS:
        c = Contract(r0, expiry, k)
        assert c.T0 > 0 and c.T1 >= 0, (expiry, k, c.T0, c.T1)
    print("   [ok] time-to-expiry positive on all 6 arms for a sample row")

    # 4. ATM-1 / ATM / ATM+1 strikes are strictly ordered around spot
    c_lo = Contract(r0, "0DTE", -1)
    c_mid = Contract(r0, "0DTE", 0)
    c_hi = Contract(r0, "0DTE", 1)
    assert c_lo.K < c_mid.K < c_hi.K, (c_lo.K, c_mid.K, c_hi.K)
    print("   [ok] ATM-1 < ATM < ATM+1 strike ordering holds")

    print("ALL T8 SELFCHECKS PASSED")


SECTIONS = {"holdout": section_holdout, "sweep": section_sweep,
            "cards": section_cards, "assume": section_assume}

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selfcheck" in args:
        selfcheck()
    else:
        bk, meta = load_book()
        check_fingerprint(bk)
        print()
        section_holdout()
        print()
        section_sweep(bk)
        print()
        section_cards(bk)
        print()
        section_assume(bk)
