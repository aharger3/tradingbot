"""OMEN 6 -- venue sizing layer.

The backtest and every measurement rig in this repo (t60_baseline.py,
exit_lab.py, ...) report results as R-multiples. R is venue-free: it is the
trade's outcome as a fraction of what was risked, and it does not know or
care whether that risk sat in a shares account, a futures margin account, or
an options premium. Dollars are a skin applied on top, after the fact, for
one specific venue.

Sizing settled 2026-08-23 (Austin): 1R = $1,000. Max loss on a stop is
-1.25R = $1,250 -- see exit_lab.py's MAX_LOSS_R and the ballot q1 quote
there. That is the ONLY hard floor in the system. Austin was explicit that
nothing else should be hard-floored:

    "not every trade is going to lose exactly 1000, unless we set that as a
    hard floor per trade"

So every function below multiplies the ACTUAL r_multiple from the backtest
by a venue's dollar-per-R. None of them assume a flat -1R loss on a stop-out;
the loss distribution passes through from the R-multiples, unmodified. The
only place a number gets clamped is where the venue's own mechanics force it
(futures: integer contracts round risk down, never up or to zero-silently).

Austin trades options, not shares, and also wants prop-firm futures/indices
modelled. Three venues:

    shares    exact passthrough, r_multiple * R_DOLLARS. The reference case:
              if this venue's numbers look wrong, the bug is upstream of
              this file, not in it.

    futures   prop-firm contract sizing (MNQ / MES micros). Contracts are
              integers, so the dollar amount actually at risk on a given stop
              is never exactly R_DOLLARS -- it is rounded DOWN to the nearest
              whole contract, and the leftover margin is reported, not hidden.

    options   premium-based. This repo has 1-minute underlying bars and no
              options chain, so there is no way to reconstruct an actual
              option fill from the archive. This is NOT a measurement -- it
              is a named, documented approximation (delta-scaled passthrough)
              and every number it returns is tagged confidence: "low". See
              its docstring below before trusting a single figure out of it.

Run the selftest with:

    python research/test_sizing.py
"""

from __future__ import annotations
import math
import statistics

# Settled 2026-08-23. See exit_lab.py MAX_LOSS_R for the -1.25R floor this
# scales -- that floor lives in R-space (the backtest), not here. This file
# only converts whatever R the backtest already produced into dollars.
R_DOLLARS = 1_000.0

# Micro futures presets. Tick size is 0.25 index points for both; what
# differs is the dollar value of that tick. Source: exchange contract specs
# (CME Micro E-mini Nasdaq-100 / Micro E-mini S&P 500), not re-derived here.
FUTURES_PRESETS = {
    "MNQ": {"tick_value": 0.50},  # Micro E-mini Nasdaq-100, $0.50 / 0.25-pt tick
    "MES": {"tick_value": 1.25},  # Micro E-mini S&P 500,    $1.25 / 0.25-pt tick
}

# Options approximation default. 0.5 delta = roughly at-the-money. This is a
# placeholder Austin can override per-trade; it is not fit to anything.
OPTIONS_DEFAULT_DELTA = 0.5


def dollars_shares(r_multiple):
    """Trivial passthrough: 1R = R_DOLLARS, no venue mechanics in the way."""
    return r_multiple * R_DOLLARS


def dollars_futures(r_multiple, stop_ticks, contract="MNQ", tick_value=None):
    """Prop-firm futures sizing: contracts = floor(R_DOLLARS / (stop_ticks * tick_value)).

    Shares and options can size to fractional risk; a futures contract
    cannot. Given a stop distance in ticks, the risk of ONE contract is
    ``stop_ticks * tick_value`` dollars, and the position is sized to the
    largest whole number of contracts that does not exceed the R_DOLLARS
    budget. Because that number is an integer, realised risk is almost never
    exactly R_DOLLARS -- it undershoots by whatever margin doesn't divide
    evenly, and that undershoot (``rounding_error_r``) is returned rather
    than papered over. The dollar P&L for the trade is r_multiple applied to
    the REALISED risk, not the nominal R_DOLLARS budget, because the realised
    risk is what was actually on the table.

    Raises ValueError if the stop is so wide that even one contract's risk
    exceeds the R_DOLLARS budget -- that is a trade this sizing cannot take
    at this stop width, not a trade worth 0 contracts / $0 P&L. Silently
    returning zero would look like a flat trade that happened to break even;
    it is actually a trade that could not be sized at all.
    """
    if stop_ticks <= 0:
        raise ValueError(f"stop_ticks must be positive, got {stop_ticks!r}")
    if tick_value is None:
        if contract not in FUTURES_PRESETS:
            raise ValueError(
                f"unknown futures contract {contract!r}; "
                f"known presets are {sorted(FUTURES_PRESETS)}"
            )
        tick_value = FUTURES_PRESETS[contract]["tick_value"]
    if tick_value <= 0:
        raise ValueError(f"tick_value must be positive, got {tick_value!r}")

    risk_per_contract = stop_ticks * tick_value
    contracts = math.floor(R_DOLLARS / risk_per_contract)
    if contracts <= 0:
        raise ValueError(
            f"{contract} stop of {stop_ticks} ticks (${risk_per_contract:.2f}/contract) "
            f"exceeds the ${R_DOLLARS:.0f} risk budget for even one contract -- "
            "this trade cannot be sized on this venue at this stop width"
        )

    realised_risk = contracts * risk_per_contract  # always <= R_DOLLARS
    rounding_error_r = (R_DOLLARS - realised_risk) / R_DOLLARS  # unused margin, in R, always >= 0
    return {
        "venue": "futures",
        "contract": contract,
        "contracts": contracts,
        "tick_value": tick_value,
        "stop_ticks": stop_ticks,
        "realised_risk_dollars": realised_risk,
        "rounding_error_r": rounding_error_r,
        "pnl": r_multiple * realised_risk,
    }


def dollars_options(r_multiple, delta=OPTIONS_DEFAULT_DELTA):
    """Options premium sizing -- APPROXIMATION, NOT A MEASUREMENT.

    This repo has no options chain, only 1-minute underlying bars, so there
    is no way to replay what an actual option contract would have filled
    for on any of these trades. What follows is a single documented
    assumption standing in for that missing data: an option's premium moves
    roughly ``delta`` dollars per dollar the underlying moves, so its R-scaled
    P&L is approximated as the shares-equivalent P&L scaled by delta:

        pnl = r_multiple * R_DOLLARS * delta

    This is a first-order, near-the-money, small-move approximation and it is
    KNOWN WRONG in specific, real ways this file does not correct for:
      - delta itself moves as the underlying moves (gamma) -- a real option's
        payoff is convex, not linear, so this understates winners and
        (for long premium) overstates the pain of losers;
      - theta decay is not modelled at all -- every day held bleeds premium
        that this number does not subtract;
      - implied-vol change and bid-ask spread on entry/exit are not modelled.

    Every dict this returns carries ``confidence: "low"`` for that reason --
    treat these numbers as a rough directional sizing guide, not a P&L record.
    """
    if not (0.0 < delta <= 1.0):
        raise ValueError(f"delta must be in (0, 1], got {delta!r}")
    return {
        "venue": "options",
        "delta": delta,
        "pnl": r_multiple * R_DOLLARS * delta,
        "confidence": "low",
    }


def dollars(r_multiple, venue, **kwargs):
    """Dispatch to the venue-specific sizer. Always returns a dict with a 'pnl' key.

    ``venue`` is one of "shares", "futures", "options". Extra kwargs pass
    straight through to that venue's function (e.g. stop_ticks/contract for
    futures, delta for options) -- see their docstrings for what each expects.
    """
    if venue == "shares":
        return {"venue": "shares", "pnl": dollars_shares(r_multiple)}
    if venue == "futures":
        return dollars_futures(r_multiple, **kwargs)
    if venue == "options":
        return dollars_options(r_multiple, **kwargs)
    raise ValueError(f"unknown venue {venue!r}; expected shares, futures, or options")


def summarise(r_multiples, venue, **kwargs):
    """Total / mean / worst dollar P&L over a list of R-multiples, at one venue.

    For "futures" also reports the mean ABSOLUTE rounding error in R (see
    dollars_futures) so the leftover-margin cost of integer contract sizing
    is visible, not averaged away by signed errors that happen to cancel --
    every futures rounding error has the same sign (undershoot), so mean and
    mean-abs are the same number here, but this stays explicit rather than
    relying on that.
    """
    results = [dollars(r, venue, **kwargs) for r in r_multiples]
    pnls = [row["pnl"] for row in results]
    out = {
        "venue": venue,
        "n": len(r_multiples),
        "total_dollars": sum(pnls),
        "mean_dollars": statistics.mean(pnls) if pnls else 0.0,
        "worst_dollars": min(pnls) if pnls else 0.0,
    }
    if venue == "futures":
        errs = [row["rounding_error_r"] for row in results]
        out["mean_abs_rounding_error_r"] = (
            statistics.mean(abs(e) for e in errs) if errs else 0.0
        )
    if venue == "options":
        out["confidence"] = "low"
    return out
