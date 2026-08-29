"""T7 -- REAL CONTRACTS. R28: "Sim real contracts with alpaca or tasty trade
because we're working to trade with real money."

Every number in `research/t7_real-contracts.md` comes from here.

    python research/t7_real_contracts.py --fetch     # pull Alpaca quotes (slow, cached)
    python research/t7_real_contracts.py              # score from cache, print report
    python research/t7_real_contracts.py --selfcheck  # the checks this file makes

WHY THIS FILE EXISTS, AND WHAT IT REPLACES
-------------------------------------------
`research/t2_options_tape.md` (commit 3bd2ef1a) was REFUTED, fatal: it priced
premium with Parkinson sigma computed from `drange` -- the day's FULL SESSION
high-low range, known only after the close. The premium is the R denominator,
so the size of the day's own eventual move set the unit the day's own result
was scored in. Ninety percent of that headline was the leak.

This file has exactly one volatility input: the PRIOR session's RTH high-low
range, read from `data_archive/<SYM>/<DAY-1>.csv`. There is no same-day range
anywhere in this file -- `--selfcheck` greps the source for the `drange` field
being indexed off a book row and fails the build if it finds one.

WHAT IS REAL AND WHAT IS MODELLED, STATED PER ROW
---------------------------------------------------
Austin's ask (R28) was to "sim real contracts with alpaca". Alpaca's paper
account (ACTIVE, options_trading_level=3) IS reachable from this box, and its
market-data host serves REAL historical 1-minute option bars going back
through the book's full 2024-08-21..2026-08-21 span -- confirmed empirically
below, not assumed. Two things are NOT available, and both are structural,
not a credentials or reachability problem:

  1. Alpaca's `/v2/options/contracts` reference endpoint lists only
     currently-ACTIVE contracts -- a 0DTE contract that expired two years ago
     is gone from it. So there is no lookup for "what strikes existed on
     2024-08-23". This file works around it: it builds candidate OCC symbols
     at every plausible strike increment ($0.50/$1/$2.50/$5/$10, floor and
     ceil of the entry price) and asks the BARS endpoint directly -- an
     unlisted OCC symbol returns an empty bar list with no error, so the
     candidate with real bars AND the strike nearest the entry price is kept.
     Confirmed against NVDA 2024-08-23: real $1 strikes returned data, the
     $0.50 candidates in between came back empty, cleanly.

  2. The RISK DENOMINATOR (1 contract-R) is `entry_premium - stop_premium`,
     where `stop_premium` is the premium the contract would have shown AT
     ENTRY TIME had the underlying already been sitting at the stop price.
     For a trade that is stopped out, the underlying really did reach that
     price -- LATER. For a trade that wins or scratches, it never did. So
     "the premium at entry time, underlying at the stop level" is a
     counterfactual by construction on every row, real quotes or not: no
     tape, however complete, contains a price for a level the stock was not
     at, at a time that has already passed. This is priced by Black-Scholes
     (S=stop, T=T0, sigma=prior-session Parkinson) FOR EVERY ROW, real-quote
     rows included. Reporting it as "real" would be dishonest; it is
     labelled `denom_model=True` unconditionally and the .md says so once,
     not per row.

So the per-row REAL/MODELLED split that matters is on the two prices that
DO have a real tape: entry premium and exit premium.

    quote_source = "alpaca_real"   entry AND exit premium are real Alpaca
                                    1-min option bars, nearest strike found.
                    "bs_model"     no candidate strike returned bars (thin
                                    0DTE names, or Alpaca's OPRA history does
                                    not reach that day for that name), OR the
                                    prior session has no archive file (first
                                    day on file for that symbol) so even the
                                    volatility input is unavailable and the
                                    row is dropped from every table.

CACHING
-------
`research/t7_alpaca_cache.json` holds one entry per traded row (keyed by
sym|day|et|dir|entry) so a re-run never re-fetches. Delete it to force a
fresh pull. `--fetch` is the only mode that touches the network; the default
mode reads the cache and is deterministic offline.
"""

from __future__ import annotations

import csv
import json
import math
import os
import statistics as st
import sys
import time
from collections import defaultdict
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import black_scholes as bs                                    # noqa: E402

BOOK = os.path.join(_HERE, "bt2y_trades.json")
ARCHIVE = os.path.join(_ROOT, "data_archive")
CACHE = os.path.join(_HERE, "t7_alpaca_cache.json")
ENV_FILE = os.path.join(_ROOT, ".env")
if not os.path.exists(ENV_FILE):
    ENV_FILE = os.path.join(_HERE, "..", ".env")

RTH_MIN = 390.0
SESSIONS_YR = 252.0
MIN_T0_MIN = 1.0
MIN_T1_MIN = 0.5
HEADLINE_IV = 1.2          # same Parkinson-to-IV multiplier T2 used; unretracted
IV_ARMS = (1.0, 1.2, 1.5)
ET = ZoneInfo("America/New_York")

# `options_sizer.build_options_plan` floors `premium_risk` (its R denominator)
# at $0.05/share -- "min tick guard" -- because a contract whose modelled
# premium barely moves for a real stop distance is not a denominator any
# sizer would actually use; it is a strike/tenor combination where the
# option is nearly insensitive to the underlying, and dividing by that
# near-zero number manufactures triple-digit R out of noise. Same floor,
# same reason, applied here to `Contract.risk` for consistency with the one
# sizer this repo actually ships. Empirically: 15-24 of ~850-900 scoreable
# rows hit this floor depending on IV arm; unfloored, they alone move the
# book mean by roughly +0.6R while the MEDIAN barely moves -- see A3 in the
# retracted T2 tape for the same finding on a different book.
MIN_PREMIUM_RISK = 0.05

# Pinned to the book this file's numbers were measured against. Recompute
# with `python -c "..."` (see the .md) if bt2y_trades.json legitimately moves;
# do not edit this constant to make a stale report look current.
BOOK_SHA = "8cd574c3b8d2de27504f97b327734045e894244220c2c1b7a176c868a07ddbe4"
BOOK_N = 1016


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


def book_fingerprint(path=BOOK):
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
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m - 570


def sign_of(row):
    return 1 if row["dir"] == "call" else -1


def scale_price(row):
    """The price the 50% scale filled at, recovered exactly from the book.
    Same algebra as the retracted T2 tape (backtest_week.py:251-253 unchanged
    since). Returns None for an unscaled row."""
    if not row.get("scaled"):
        return None
    s, risk = sign_of(row), abs(row["entry"] - row["stop"])
    run_r = s * (row["exit"] - row["entry"]) / risk
    scale_r = 2.0 * row["r"] - run_r
    return row["entry"] + s * scale_r * risk


# ---------------------------------------------------------------------------
# prior-session sigma -- the ONLY volatility input in this file
# ---------------------------------------------------------------------------

_prior_cache = {}


def prior_session_range(sym, day):
    """RTH high-low of the most recent session BEFORE `day` in data_archive.
    Ex-ante by construction: only bars that closed before the trade's own
    session opened. Returns None when there is no earlier file on disk."""
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


# ---------------------------------------------------------------------------
# Alpaca -- real historical option bars
# ---------------------------------------------------------------------------

def load_alpaca_creds():
    env = {}
    with open(ENV_FILE) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    key = env.get("ALPACA_API_KEY_ID") or env.get("ALPACA_PAPER_KEY")
    secret = env.get("ALPACA_API_SECRET") or env.get("ALPACA_PAPER_SECRET")
    if not key or not secret:
        raise RuntimeError("no Alpaca key/secret in %s" % ENV_FILE)
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def occ_symbol(sym, day, call, strike):
    yymmdd = day[2:4] + day[5:7] + day[8:10]
    cp = "C" if call else "P"
    return "%s%s%s%08d" % (sym.upper(), yymmdd, cp, int(round(strike * 1000)))


def strike_candidates(entry, n=10):
    cands = set()
    for inc in (0.5, 1.0, 2.5, 5.0, 10.0):
        cands.add(math.floor(entry / inc) * inc)
        cands.add(math.ceil(entry / inc) * inc)
    cands.discard(0.0)
    return sorted(cands, key=lambda k: abs(k - entry))[:n]


def et_to_utc_iso(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    y, mo, d = map(int, day.split("-"))
    dt = datetime(y, mo, d, h, m, tzinfo=ET)
    return dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


def exit_hhmm(row):
    t0 = et_min(row["et"])
    t1 = min(RTH_MIN, t0 + max(1, row["bars"]))
    total_min = 570 + int(round(t1))
    h, m = divmod(total_min, 60)
    return "%02d:%02d" % (h, m)


def cache_key(row):
    return "|".join([row["sym"], row["day"], row["et"], row["dir"], str(row["entry"])])


def fetch_real_quote(row, headers, session, retries=4):
    """One Alpaca call: candidate strikes x [entry, exit] time window.
    Returns dict(strike, entry_premium, exit_premium, occ) or None."""
    cands = strike_candidates(row["entry"])
    call = row["dir"] == "call"
    syms = [occ_symbol(row["sym"], row["day"], call, k) for k in cands]
    sym_to_strike = dict(zip(syms, cands))

    xh = exit_hhmm(row)
    start = et_to_utc_iso(row["day"], row["et"])
    end_h, end_m = map(int, xh.split(":"))
    end_dt = datetime(*map(int, row["day"].split("-")), end_h, end_m, tzinfo=ET) \
        + timedelta(minutes=1)
    end = end_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    start_dt = datetime(*map(int, row["day"].split("-")), *map(int, row["et"].split(":")),
                         tzinfo=ET) - timedelta(minutes=1)
    start = start_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {"symbols": ",".join(syms), "timeframe": "1Min",
              "start": start, "end": end, "limit": 2000}
    for attempt in range(retries):
        try:
            r = session.get("https://data.alpaca.markets/v1beta1/options/bars",
                             headers=headers, params=params, timeout=15)
        except requests.RequestException:
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code == 429:
            time.sleep(2.0 * (attempt + 1))
            continue
        if r.status_code != 200:
            return None
        data = r.json().get("bars", {}) or {}
        break
    else:
        return None

    best = None
    for occ, bars in data.items():
        if not bars:
            continue
        strike = sym_to_strike.get(occ)
        if strike is None:
            continue
        if best is None or abs(strike - row["entry"]) < abs(best[0] - row["entry"]):
            best = (strike, occ, bars)
    if best is None:
        return None
    strike, occ, bars = best
    bars = sorted(bars, key=lambda b: b["t"])
    entry_prem = bars[0]["o"]
    exit_prem = bars[-1]["c"]
    return {"strike": strike, "occ": occ, "entry_premium": entry_prem,
            "exit_premium": exit_prem, "n_bars": len(bars)}


def run_fetch():
    book = load_book()
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE) as fh:
            cache = json.load(fh)
    headers = load_alpaca_creds()
    session = requests.Session()
    todo = [r for r in book if cache_key(r) not in cache]
    print("fetching Alpaca quotes: %d cached, %d to fetch" % (len(cache), len(todo)))
    t0 = time.time()
    for i, row in enumerate(todo):
        q = fetch_real_quote(row, headers, session)
        cache[cache_key(row)] = q
        if (i + 1) % 25 == 0 or (i + 1) == len(todo):
            elapsed = time.time() - t0
            print("  %d/%d  (%.0fs elapsed, %.2fs/row)" % (i + 1, len(todo), elapsed,
                                                             elapsed / (i + 1)))
            with open(CACHE, "w") as fh:
                json.dump(cache, fh)
    with open(CACHE, "w") as fh:
        json.dump(cache, fh)
    found = sum(1 for v in cache.values() if v)
    print("done: %d/%d rows have a real Alpaca quote (%.1f%%)"
          % (found, len(cache), 100.0 * found / len(cache) if cache else 0))


# ---------------------------------------------------------------------------
# the contract model
# ---------------------------------------------------------------------------

class Contract:
    """One row priced as a 0DTE ATM(ish) contract. All prices PER SHARE.

    entry/exit premium: REAL Alpaca quote when `quote` is not None, else
    Black-Scholes. The RISK DENOMINATOR (`self.risk`) is ALWAYS
    Black-Scholes at (S=stop, T=T0) -- see module docstring for why this is
    not optional, real quotes or not.
    """

    def __init__(self, row, quote, iv_mult=HEADLINE_IV, r=0.0):
        self.row = row
        self.call = row["dir"] == "call"
        self.S0 = row["entry"]
        self.K = quote["strike"] if quote else self.S0
        self.stop = row["stop"]
        self.r = r
        self.risk_u = abs(row["entry"] - row["stop"])

        prior_rng = prior_session_range(row["sym"], row["day"])
        self.have_sigma = prior_rng is not None and prior_rng > 0
        self.sigma = (bs.parkinson_sigma(prior_rng, self.S0) * iv_mult
                      if self.have_sigma else 0.0)

        t0 = et_min(row["et"])
        t1 = min(RTH_MIN, t0 + max(1, row["bars"]))
        self.min0 = max(RTH_MIN - t0, MIN_T0_MIN)
        self.min1 = max(RTH_MIN - t1, MIN_T1_MIN)
        self.T0 = self.min0 / (RTH_MIN * SESSIONS_YR)
        self.T1 = self.min1 / (RTH_MIN * SESSIONS_YR)

        self.quote = quote
        self.real = quote is not None
        self.p0 = quote["entry_premium"] if quote else self.px(self.S0, self.T0)
        self.p_exit_raw = quote["exit_premium"] if quote else None

        self.pstop = self.px(self.stop, self.T0)   # ALWAYS modelled; see docstring
        raw_risk = self.p0 - self.pstop
        self.risk_floored = 0.0 < raw_risk < MIN_PREMIUM_RISK
        self.risk = max(raw_risk, MIN_PREMIUM_RISK) if raw_risk > 0 else raw_risk
        self.ok = self.have_sigma and self.risk_u > 0 and raw_risk > 1e-9

    def px(self, S, T):
        return bs.price(S, self.K, T, self.sigma, call=self.call, r=self.r)

    def cr_single(self):
        """Full size to `row['exit']`. Real exit premium when we have one,
        else Black-Scholes at the underlying exit price."""
        px_exit = self.p_exit_raw if self.p_exit_raw is not None \
            else self.px(self.row["exit"], self.T1)
        return (px_exit - self.p0) / self.risk

    def cr_ladder(self):
        """Book's 50/50 scale plan. The scale leg has no real quote (we do
        not know the scale MINUTE), so it is always modelled at T=mid."""
        px_exit = self.p_exit_raw if self.p_exit_raw is not None \
            else self.px(self.row["exit"], self.T1)
        run = (px_exit - self.p0) / self.risk
        sp = scale_price(self.row)
        if sp is None:
            return run
        Tmid = 0.5 * (self.T0 + self.T1)
        scl = (self.px(sp, Tmid) - self.p0) / self.risk
        return 0.5 * scl + 0.5 * run

    def ur_single(self):
        return sign_of(self.row) * (self.row["exit"] - self.S0) / self.risk_u

    def ur_ladder(self):
        run = sign_of(self.row) * (self.row["exit"] - self.S0) / self.risk_u
        sp = scale_price(self.row)
        if sp is None:
            return run
        return 0.5 * (sign_of(self.row) * (sp - self.S0) / self.risk_u) + 0.5 * run


def priced(book, cache, iv_mult=HEADLINE_IV):
    out = []
    for row in book:
        q = cache.get(cache_key(row)) if cache is not None else None
        c = Contract(row, q, iv_mult)
        if c.ok:
            out.append(c)
    return out


def load_cache():
    if not os.path.exists(CACHE):
        return {}
    with open(CACHE) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# report sections
# ---------------------------------------------------------------------------

def section_coverage(book, cache):
    print("=== 0. COVERAGE -- real vs modelled, row by row")
    print_fingerprint()
    n_no_sigma = sum(1 for r in book if prior_session_range(r["sym"], r["day"]) is None)
    n_real = sum(1 for r in book if cache.get(cache_key(r)))
    n_cached_miss = sum(1 for r in book if cache_key(r) in cache and not cache.get(cache_key(r)))
    n_not_fetched = sum(1 for r in book if cache_key(r) not in cache)
    print("   traded rows                         : %d" % len(book))
    print("   no prior-session archive (dropped)   : %d" % n_no_sigma)
    print("   Alpaca real quote found (entry+exit)  : %d (%.1f%%)"
          % (n_real, 100.0 * n_real / len(book)))
    print("   Alpaca queried, no listed strike found: %d" % n_cached_miss)
    print("   never queried (cache miss)            : %d" % n_not_fetched)
    cs = priced(book, cache)
    real_n = sum(1 for c in cs if c.real)
    print("   scoreable rows (sigma available)      : %d, of which real-quoted %d (%.1f%%)"
          % (len(cs), real_n, 100.0 * real_n / len(cs) if cs else 0))


def section_book(book, cache):
    print("=== 1. THE BOOK -- contract R (real-where-available) vs underlying R")
    print_fingerprint()
    print()
    print("   -- SINGLE convention: full size to exit -- (risk denom floored at $%.2f/sh)"
          % MIN_PREMIUM_RISK)
    print("   %-8s %-8s %9s %8s | %9s %8s   %8s" %
          ("IV", "n", "CONTRACT", "win%", "UNDERLYING", "win%", "flr#"))
    for iv in IV_ARMS:
        cs = priced(book, cache, iv)
        co = [c.cr_single() for c in cs]
        uo = [c.ur_single() for c in cs]
        nflr = sum(1 for c in cs if c.risk_floored)
        print("   %-8s %-8d %+9.4f %7.1f%% | %+9.4f %7.1f%%   %8d"
              % ("%.1fx" % iv, len(cs), mean(co), win(co), mean(uo), win(uo), nflr))
        print("        contract R  p10 %+.2f  p50 %+.2f  p90 %+.2f  max %+.2f  (READ p50: "
              "the mean is pulled by a fat right tail, this is expected -- see calibration"
              " section for why)" % (pct(co, .10), pct(co, .50), pct(co, .90), max(co)))
    print()
    print("   -- LADDER convention: book's own 50/50 scale plan --")
    print("   %-8s %-8s %9s %8s | %9s %8s" %
          ("IV", "n", "CONTRACT", "win%", "UNDERLYING", "win%"))
    for iv in IV_ARMS:
        cs = priced(book, cache, iv)
        co = [c.cr_ladder() for c in cs]
        uo = [c.ur_ladder() for c in cs]
        print("   %-8s %-8d %+9.4f %7.1f%% | %+9.4f %7.1f%%"
              % ("%.1fx" % iv, len(cs), mean(co), win(co), mean(uo), win(uo)))
    print()
    cs = priced(book, cache, HEADLINE_IV)
    print("   -- split by real vs modelled entry/exit premium, LADDER, IV %.1fx --" % HEADLINE_IV)
    for lbl, pred in (("real Alpaca quote", lambda c: c.real),
                      ("BS model (no real quote)", lambda c: not c.real)):
        sub = [c for c in cs if pred(c)]
        if not sub:
            continue
        co = [c.cr_ladder() for c in sub]
        uo = [c.ur_ladder() for c in sub]
        print("   %-28s n=%-5d CONTRACT %+9.4f %6.1f%% | UNDERLYING %+9.4f %6.1f%%"
              % (lbl, len(sub), mean(co), win(co), mean(uo), win(uo)))


def section_month(book, cache):
    print("=== 2. PER MONTH -- IV %.1fx, LADDER convention" % HEADLINE_IV)
    cs = priced(book, cache, HEADLINE_IV)
    bym = defaultdict(list)
    for c in cs:
        bym[c.row["ym"]].append(c)
    print("   %-9s %5s %6s | %9s %7s | %9s %7s | %s"
          % ("month", "n", "real%", "CONTRACT", "win%", "UNDERLY", "win%", "green"))
    gc = gu = 0
    for m in sorted(bym):
        v = bym[m]
        co = [c.cr_ladder() for c in v]
        uo = [c.ur_ladder() for c in v]
        real_pct = 100.0 * sum(1 for c in v if c.real) / len(v)
        c_ok, u_ok = sum(co) > 0, sum(uo) > 0
        gc += c_ok
        gu += u_ok
        print("   %-9s %5d %5.0f%% | %+9.4f %6.1f%% | %+9.4f %6.1f%% | C:%s U:%s"
              % (m, len(v), real_pct, mean(co), win(co), mean(uo), win(uo),
                 "Y" if c_ok else "n", "Y" if u_ok else "n"))
    print("   DURABILITY: green months  CONTRACT %d/%d   UNDERLYING %d/%d"
          % (gc, len(bym), gu, len(bym)))


def section_family(book, cache):
    print("=== 3. PER SETUP FAMILY -- LADDER, IV %.1fx" % HEADLINE_IV)
    cs = priced(book, cache, HEADLINE_IV)
    byf = defaultdict(list)
    for c in cs:
        byf[c.row["setup"]].append(c)
    print("   %-18s %5s %6s | %9s %7s | %9s %7s"
          % ("family", "n", "real%", "CONTRACT", "win%", "UNDERLY", "win%"))
    for f in sorted(byf, key=lambda k: -len(byf[k])):
        v = byf[f]
        co = [c.cr_ladder() for c in v]
        uo = [c.ur_ladder() for c in v]
        real_pct = 100.0 * sum(1 for c in v if c.real) / len(v)
        print("   %-18s %5d %5.0f%% | %+9.4f %6.1f%% | %+9.4f %6.1f%%"
              % (f, len(v), real_pct, mean(co), win(co), mean(uo), win(uo)))


def section_symbol(book, cache):
    print("=== 4. PER SYMBOL -- LADDER, IV %.1fx, symbols with n>=15" % HEADLINE_IV)
    cs = priced(book, cache, HEADLINE_IV)
    bys = defaultdict(list)
    for c in cs:
        bys[c.row["sym"]].append(c)
    print("   %-8s %5s %6s | %9s %7s | %9s %7s"
          % ("sym", "n", "real%", "CONTRACT", "win%", "UNDERLY", "win%"))
    for s in sorted(bys, key=lambda k: -len(bys[k])):
        v = bys[s]
        if len(v) < 15:
            continue
        co = [c.cr_ladder() for c in v]
        uo = [c.ur_ladder() for c in v]
        real_pct = 100.0 * sum(1 for c in v if c.real) / len(v)
        print("   %-8s %5d %5.0f%% | %+9.4f %6.1f%% | %+9.4f %6.1f%%"
              % (s, len(v), real_pct, mean(co), win(co), mean(uo), win(uo)))


def section_calibration(book, cache):
    """How well does the BS model's price track the real Alpaca tape, on the
    rows where we have BOTH? -- the direct answer to "how much is the model
    fallback worth trusting on the rows it has to cover"."""
    print("=== 5. MODEL vs TAPE -- on real-quoted rows, BS-model price vs actual")
    cs = [c for c in priced(book, cache, HEADLINE_IV) if c.real]
    if not cs:
        print("   no real-quoted rows -- run --fetch first")
        return
    entry_err = [(c.px(c.S0, c.T0) - c.p0) for c in cs]
    exit_err = [(c.px(c.row["exit"], c.T1) - c.p_exit_raw) for c in cs]
    print("   n=%d rows with a real Alpaca quote" % len(cs))
    print("   entry premium: model - real   mean %+.4f  median %+.4f  |err| p90 %.4f"
          % (mean(entry_err), st.median(entry_err), pct([abs(e) for e in entry_err], .90)))
    print("   exit  premium: model - real   mean %+.4f  median %+.4f  |err| p90 %.4f"
          % (mean(exit_err), st.median(exit_err), pct([abs(e) for e in exit_err], .90)))
    real_r = [c.cr_ladder() for c in cs]
    model_r = []
    for c in cs:
        c2 = Contract(c.row, None, HEADLINE_IV)
        if c2.ok:
            model_r.append(c2.cr_ladder())
    print("   contract R on these rows: REAL tape %+.4f  vs  full BS-model %+.4f  (delta %+.4f)"
          % (mean(real_r), mean(model_r), mean(real_r) - mean(model_r)))
    for iv in IV_ARMS:
        mr = []
        for c in cs:
            c2 = Contract(c.row, None, iv)
            if c2.ok:
                mr.append(c2.cr_ladder())
        print("      IV %.1fx model  : %+.4f  (vs real tape %+.4f, delta %+.4f)"
              % (iv, mean(mr), mean(real_r), mean(mr) - mean(real_r)))


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck():
    print("=== T7 SELFCHECK")
    print_fingerprint()
    h, n, _ = book_fingerprint()
    assert h == BOOK_SHA and n == BOOK_N, (
        "bt2y_trades.json is not the book this report was measured on "
        "(%s n=%d != pinned %s n=%d). Regenerate the report, do not read "
        "stale numbers against a moved book." % (h[:16], n, BOOK_SHA[:16], BOOK_N))
    print("  [ok] book pinned: %s n=%d" % (h[:16], n))

    # no same-day range anywhere in this file's pricing path
    src = open(__file__).read()
    import re
    bad = re.findall(r'row(?:\[|\.get\()["\']drange["\']', src)
    assert not bad, "same-day drange leaked into the pricing path: %r" % bad
    print("  [ok] no same-day 'drange' reference anywhere in this file")

    bs._selfcheck()
    print("  [ok] black_scholes selfcheck passed")

    book = load_book()
    assert len(book) == BOOK_N, len(book)
    cache = load_cache()

    # the risk denominator is ALWAYS Black-Scholes, real quote or not
    cs = priced(book, cache, HEADLINE_IV)
    real_cs = [c for c in cs if c.real]
    if real_cs:
        for c in real_cs[:50]:
            expected = c.px(c.stop, c.T0)
            assert abs(c.pstop - expected) < 1e-9
        print("  [ok] risk denominator is Black-Scholes on real-quoted rows too "
              "(checked %d)" % min(50, len(real_cs)))
    else:
        print("  [--] no real-quoted rows cached yet -- run --fetch to populate "
              "research/t7_alpaca_cache.json before publishing numbers")

    # ladder underlying arm reproduces the book's own r (same algebra as the
    # retracted T2 tape; still an identity because backtest_week's scale math
    # has not changed)
    devs = []
    for c in cs:
        devs.append(abs(c.ur_ladder() - c.row["r"]))
    exact = sum(1 for d in devs if d < 2e-3)
    assert exact >= len(cs) - 5, (exact, len(cs))
    print("  [ok] recovered ladder underlying R reproduces book r on %d/%d rows "
          "(<=2e-3 tolerance for 3dp-rounded book r)" % (exact, len(cs)))

    # every scoreable row used a PRIOR-session sigma, never same-day
    for c in cs[:200]:
        rng = prior_session_range(c.row["sym"], c.row["day"])
        assert rng is not None and rng > 0
        assert abs(c.sigma - bs.parkinson_sigma(rng, c.S0) * HEADLINE_IV) < 1e-12
    print("  [ok] sigma traced to prior-session archive range on sampled rows, "
          "matches Parkinson(prior_range) x IV exactly")

    print("ALL T7 SELFCHECKS PASSED")


SECTIONS = {"coverage": section_coverage, "book": section_book, "month": section_month,
            "family": section_family, "symbol": section_symbol,
            "calibration": section_calibration}

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selfcheck" in args:
        selfcheck()
    elif "--fetch" in args:
        run_fetch()
    else:
        bk = load_book()
        cache = load_cache()
        for nm in ([a for a in args if not a.startswith("-")] or list(SECTIONS)):
            SECTIONS[nm](bk, cache)
            print()
