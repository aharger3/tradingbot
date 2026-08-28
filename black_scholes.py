"""Black-Scholes for the 0DTE ATM contract OMEN actually trades.

Why this module exists
----------------------
`options_sizer.DEFAULT_DELTA = 0.5` was the ENTIRE options model in this repo.
A flat linear delta cannot express the two things Austin's runner thesis rides
on -- convexity (the delta of a winning 0DTE call climbs toward 1.0, so the
runner earns more than the underlying move) and theta (the same contract bleeds
while it waits, so a scratch costs more than the underlying scratch). One
number cannot be both.

Scope, stated up front: this is the textbook Black-Scholes-Merton formula for a
European option on a non-dividend-paying underlying, with analytic greeks. It is
a MODEL. There is no options tape in this repo -- see
`research/t2_options_tape.md` for the full assumption list and the sensitivity
of every published figure to each assumption.

Conventions
-----------
* `T` is in YEARS. The callers here work in 390-minute RTH sessions and 252
  trading days, so one minute is `1 / (390 * 252)`.
* `sigma` is annualised.
* `r` and `q` default to 0.0. Over the 09:30-16:00 life of a 0DTE contract the
  carry term is worth less than a tenth of a cent on a $200 underlying; the
  sensitivity is measured, not assumed, in the report.
* At `T <= 0` or `sigma <= 0` every function degenerates to the intrinsic-value
  limit rather than raising, because the book contains trades that run to the
  closing bell.

No I/O, no globals, no flags. `options_sizer.ENABLE_CONTRACT_R` decides whether
the live sizer calls any of this; that flag is not here.
"""

from __future__ import annotations

import math

SQRT_2PI = math.sqrt(2.0 * math.pi)


def norm_cdf(x: float) -> float:
    """Standard normal CDF via erf. Accurate to ~1e-16, no scipy dependency."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def d1_d2(S: float, K: float, T: float, sigma: float, r: float = 0.0, q: float = 0.0):
    """The two Black-Scholes arguments. Caller must guarantee T > 0, sigma > 0."""
    vt = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vt
    return d1, d1 - vt


def _intrinsic(S: float, K: float, call: bool) -> float:
    return max(0.0, (S - K) if call else (K - S))


def price(S: float, K: float, T: float, sigma: float, call: bool = True,
          r: float = 0.0, q: float = 0.0) -> float:
    """Black-Scholes-Merton price. Degenerates to intrinsic at T<=0 or sigma<=0."""
    if T <= 0.0 or sigma <= 0.0:
        return _intrinsic(S, K, call)
    d1, d2 = d1_d2(S, K, T, sigma, r, q)
    df_q = math.exp(-q * T)
    df_r = math.exp(-r * T)
    if call:
        return S * df_q * norm_cdf(d1) - K * df_r * norm_cdf(d2)
    return K * df_r * norm_cdf(-d2) - S * df_q * norm_cdf(-d1)


def delta(S: float, K: float, T: float, sigma: float, call: bool = True,
          r: float = 0.0, q: float = 0.0) -> float:
    """dPrice/dS. Signed: positive for calls, negative for puts."""
    if T <= 0.0 or sigma <= 0.0:
        if call:
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0
    d1, _ = d1_d2(S, K, T, sigma, r, q)
    df_q = math.exp(-q * T)
    return df_q * (norm_cdf(d1) if call else norm_cdf(d1) - 1.0)


def gamma(S: float, K: float, T: float, sigma: float,
          r: float = 0.0, q: float = 0.0) -> float:
    """d2Price/dS2. Same for calls and puts."""
    if T <= 0.0 or sigma <= 0.0:
        return 0.0
    d1, _ = d1_d2(S, K, T, sigma, r, q)
    return math.exp(-q * T) * norm_pdf(d1) / (S * sigma * math.sqrt(T))


def vega(S: float, K: float, T: float, sigma: float,
         r: float = 0.0, q: float = 0.0) -> float:
    """dPrice/dsigma, per 1.00 of annualised vol (NOT per vol point)."""
    if T <= 0.0 or sigma <= 0.0:
        return 0.0
    d1, _ = d1_d2(S, K, T, sigma, r, q)
    return S * math.exp(-q * T) * norm_pdf(d1) * math.sqrt(T)


def theta(S: float, K: float, T: float, sigma: float, call: bool = True,
          r: float = 0.0, q: float = 0.0) -> float:
    """dPrice/dT_elapsed, PER YEAR. Negative for a long option.

    Divide by 252 for per-trading-day, by (252 * 390) for per-RTH-minute. This
    is the instantaneous rate; the report never integrates it by hand -- it
    reprices at the later T, which is exact rather than first-order.
    """
    if T <= 0.0 or sigma <= 0.0:
        return 0.0
    d1, d2 = d1_d2(S, K, T, sigma, r, q)
    df_q = math.exp(-q * T)
    df_r = math.exp(-r * T)
    term = -(S * df_q * norm_pdf(d1) * sigma) / (2.0 * math.sqrt(T))
    if call:
        return term - r * K * df_r * norm_cdf(d2) + q * S * df_q * norm_cdf(d1)
    return term + r * K * df_r * norm_cdf(-d2) - q * S * df_q * norm_cdf(-d1)


def parkinson_sigma(high_low_range: float, reference_price: float,
                    periods_per_year: float = 252.0) -> float:
    """Annualised vol from ONE session's high-low range (Parkinson, 1980).

    sigma = (range / price) / (2 * sqrt(ln 2)) * sqrt(periods_per_year)

    The 1/(2*sqrt(ln2)) factor converts an expected absolute range into the
    standard deviation of a driftless Brownian motion over the same window.
    Returns 0.0 on a degenerate input rather than raising.
    """
    if high_low_range <= 0.0 or reference_price <= 0.0:
        return 0.0
    return ((high_low_range / reference_price) / (2.0 * math.sqrt(math.log(2.0)))
            * math.sqrt(periods_per_year))


def _selfcheck():
    """Textbook identities. `python black_scholes.py` runs these."""
    S, K, T, sig = 100.0, 100.0, 0.25, 0.20

    # put-call parity with carry on, which is where a sign error would hide
    r_, q_ = 0.05, 0.02
    c = price(S, K, T, sig, True, r_, q_)
    p = price(S, K, T, sig, False, r_, q_)
    lhs = c - p
    rhs = S * math.exp(-q_ * T) - K * math.exp(-r_ * T)
    assert abs(lhs - rhs) < 1e-10, (lhs, rhs)

    # ATM zero-carry delta is just above 0.5 (the +0.5*sigma^2*T drift term)
    dc = delta(S, K, T, sig, True)
    dp = delta(S, K, T, sig, False)
    assert 0.50 < dc < 0.55, dc
    assert abs(dc - dp - 1.0) < 1e-12, (dc, dp)     # call delta - put delta = 1

    # analytic greeks match central differences
    h = 1e-4
    fd_d = (price(S + h, K, T, sig) - price(S - h, K, T, sig)) / (2 * h)
    assert abs(fd_d - dc) < 1e-6, (fd_d, dc)
    fd_g = (price(S + h, K, T, sig) - 2 * price(S, K, T, sig)
            + price(S - h, K, T, sig)) / (h * h)
    assert abs(fd_g - gamma(S, K, T, sig)) < 1e-4, (fd_g, gamma(S, K, T, sig))
    fd_v = (price(S, K, T, sig + h) - price(S, K, T, sig - h)) / (2 * h)
    assert abs(fd_v - vega(S, K, T, sig)) < 1e-5, (fd_v, vega(S, K, T, sig))
    fd_t = -(price(S, K, T + h, sig) - price(S, K, T - h, sig)) / (2 * h)
    assert abs(fd_t - theta(S, K, T, sig)) < 1e-4, (fd_t, theta(S, K, T, sig))

    # convexity: a long option is strictly convex in S, so the second-order
    # gain of a symmetric up/down move is positive. This is the whole reason
    # the contract book differs from the underlying book.
    up = price(S + 1.0, K, T, sig) - price(S, K, T, sig)
    dn = price(S, K, T, sig) - price(S - 1.0, K, T, sig)
    assert up > dn > 0, (up, dn)

    # degenerate limits
    assert price(105.0, 100.0, 0.0, sig) == 5.0
    assert price(95.0, 100.0, 0.0, sig) == 0.0
    assert price(100.0, 100.0, 0.25, 0.0) == 0.0

    # Parkinson: a 2% daily range on a $100 stock
    s = parkinson_sigma(2.0, 100.0)
    assert abs(s - (0.02 / (2 * math.sqrt(math.log(2))) * math.sqrt(252))) < 1e-12
    assert parkinson_sigma(0.0, 100.0) == 0.0

    print("black_scholes selfcheck: OK")


if __name__ == "__main__":
    _selfcheck()
