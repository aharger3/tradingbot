"""G80 - OPTIONS ON HONEST FILLS.

The instrument is options, not shares. Every options number in this repo was
computed on the OLD entry price -- the one the refutation pass showed is a
free head start of +0.58R (research/g80_dollar_reconcile.md). This file
re-prices the contract on the two entry prices you can actually get:

    ORDER TYPE B -- market at the close of the minute the signal fired.
                    You see the confirmation, you send a market order, you pay
                    where the minute ended. Always fillable.

    ORDER TYPE A -- a limit resting at the level, placed before the signal.
                    Fills at the level, and ONLY if that minute actually
                    traded there. If the minute never reached the level, there
                    is no trade.

and, as the control it must be read against,

    PUBLISHED    -- the book's own recorded entry price. Not obtainable; it is
                    here so every honest number has its optimistic twin beside
                    it.

WHAT IS REUSED, AND WHY
-----------------------
  black_scholes.py                the pricer (T2 built it; it has its own
                                  selfcheck and this file does not touch it)
  research/t7_real_contracts.py   the METHOD: prior-session Parkinson sigma as
                                  the only volatility input, the $0.05/share
                                  premium-risk floor, the ATM 0DTE frame.
                                  T7's own Alpaca quote cache cannot be reused
                                  here -- see "no real tape" below.
  stop_rule.py                    the one stop-fill definition (close trigger,
                                  -1.25R floor).
  research/g80_dollar_reconcile.py the simple flat-2R simulation, so the SHARES
                                  side of this file reproduces the sibling
                                  agent's honest-fill dollars exactly. That
                                  reproduction is asserted, not hoped for.

THE TWO TRAPS THIS FILE IS REQUIRED TO AVOID
--------------------------------------------
1. LOOK-AHEAD VOLATILITY. research/t2_options_tape.md priced premium off the
   day's OWN full-session high-low range -- the R denominator was set by the
   size of the move it was scoring. 90% of that headline was the leak. Here
   sigma comes from the PRIOR session's RTH range, read out of
   data_archive/<SYM>/<earlier day>.csv, and there is no same-day range
   anywhere in the pricing path. `--selfcheck` greps this file's own source
   for it.

2. THE $0.05 FLOOR APPLIED TO ONE LEG ONLY (research/g71_board.md bug #3).
   options_sizer.py floors the stop premium at $0.05 -- correct, a long option
   cannot be worth less than a tick -- and then builds the target leg out of
   the UNFLOORED premium_risk, so the reward:risk it prints is bigger than the
   one it can book, by up to 3.8x. Here BOTH legs go through the same floor:
   the stop premium is floored, the exit premium is floored, and the R
   denominator is measured against the floored stop. The unfloored variant is
   computed too, purely to report how big the difference is.
   options_sizer.py IS NOT EDITED. The diff that would fix it is in the .md.

NO REAL TAPE
------------
Every option price here is modelled. research/t7_alpaca_cache.json holds 276
real Alpaca quotes, but they were fetched against a superseded 1,016-row book
and, more fundamentally, they store the option bar's OPEN at the signal minute
and its CLOSE at the PUBLISHED exit minute. Order type B pays the option's
close, order type A pays it mid-minute, and both arms exit on different
minutes than the published book did -- so not one cached quote answers the
question this file asks. Re-fetching is a network job of ~13,000 calls across
three arms and was not run. T7 measured the model against the tape it did
have: +0.1958R apart on n=106, inside a +/-0.9185R bar -- "not disproven",
not "proven".

Usage:  python research/g80_options_honest.py            # full report
        python research/g80_options_honest.py --selfcheck
Writes: research/g80_options_honest.json
Reads only. No mark file, no engine file, no network, no URL printed.
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import black_scholes as bs                                   # noqa: E402
import polygon_feed as pf                                    # noqa: E402
from stop_rule import stop_hit_on_close, stop_fill_price     # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
ARCHIVE = ROOT / "data_archive"
OUT = ROOT / "research" / "g80_options_honest.json"

RISK = 1000.0            # 1R = $1,000 (CLAUDE.md)
MAX_LOSS = 1000.0        # options_sizer.DEFAULT_MAX_LOSS
MULT = 100               # options_sizer.CONTRACT_MULTIPLIER
MIN_PREMIUM_RISK = 0.05  # options_sizer "min tick guard"; T7 MIN_PREMIUM_RISK
IV_MULT = 1.2            # T7 headline arm; 1.0x / 1.5x swept as sensitivity
IV_ARMS = (1.0, 1.2, 1.5)
RTH_MIN = 390.0
SESSIONS_YR = 252.0
SEED = 20260830
BOOTS = 10000
EPS = 0.006


# ---------------------------------------------------------------- arithmetic

def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def drawdown(seq):
    cum = peak = worst = 0.0
    for p in seq:
        cum += p
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def price_block(rows, n_days, key="dollars"):
    """One arithmetic for every arm in this file."""
    if not rows:
        return {"trades": 0}
    pnls = [r[key] for r in rows]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    by_m = {}
    for r in rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r[key]
    total = sum(pnls)
    return {
        "trades": len(rows),
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "total_dollars": round(total, 0),
        "per_trade": round(total / len(rows), 0),
        "per_day": round(total / n_days, 0),
        "per_month": round(total / n_days * 20, 0),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "worst_drawdown": round(drawdown(pnls), 0),
    }


def day_ci(rows, all_days, key="dollars"):
    """95% interval on dollars-a-day, resampling whole SESSIONS.

    A session with no trade contributes $0 and stays in the draw, or the
    interval prices a different question than the headline does.
    """
    by_d = {d: 0.0 for d in all_days}
    for r in rows:
        by_d[r["day"]] = by_d.get(r["day"], 0.0) + r[key]
    v = [by_d[d] for d in sorted(by_d)]
    rng = random.Random(SEED)
    n = len(v)
    m = sorted(sum(rng.choices(v, k=n)) / n for _ in range(BOOTS))
    return {"per_day": round(sum(v) / n, 0),
            "lo": round(m[int(BOOTS * 0.025)], 0),
            "hi": round(m[int(BOOTS * 0.975)], 0),
            "crosses_zero": bool(m[int(BOOTS * 0.025)] <= 0 <= m[int(BOOTS * 0.975)])}


def paired_day_ci(rows_a, rows_b, all_days, key="dollars"):
    """95% interval on the per-day DIFFERENCE (a minus b), same resample."""
    da = {d: 0.0 for d in all_days}
    db = {d: 0.0 for d in all_days}
    for r in rows_a:
        da[r["day"]] = da.get(r["day"], 0.0) + r[key]
    for r in rows_b:
        db[r["day"]] = db.get(r["day"], 0.0) + r[key]
    v = [da[d] - db[d] for d in sorted(all_days)]
    rng = random.Random(SEED)
    n = len(v)
    m = sorted(sum(rng.choices(v, k=n)) / n for _ in range(BOOTS))
    return {"per_day": round(sum(v) / n, 0),
            "lo": round(m[int(BOOTS * 0.025)], 0),
            "hi": round(m[int(BOOTS * 0.975)], 0),
            "crosses_zero": bool(m[int(BOOTS * 0.025)] <= 0 <= m[int(BOOTS * 0.975)])}


# ------------------------------------------------------------- bars + sigma

_bars = {}


def bars(sym, day):
    k = (sym, day)
    if k not in _bars:
        if len(_bars) > 60:
            _bars.clear()
        try:
            _bars[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            _bars[k] = []
    return _bars[k]


_prior = {}
_days_on_disk = {}


def prior_session_range(sym, day):
    """RTH high-low of the most recent session on disk BEFORE `day`.

    Ex-ante by construction. This is T7's function, same contract: it is the
    ONLY volatility input in this file and it never touches `day` itself.
    """
    key = (sym, day)
    if key in _prior:
        return _prior[key]
    d = ARCHIVE / sym
    if sym not in _days_on_disk:
        _days_on_disk[sym] = (sorted(f.name[:-4] for f in d.glob("*.csv"))
                              if d.is_dir() else [])
    prev = [x for x in _days_on_disk[sym] if x < day]
    out = None
    if prev:
        b = bars(sym, prev[-1])
        if b:
            hi = max(c.high for c in b)
            lo = min(c.low for c in b)
            if hi > lo:
                out = hi - lo
    _prior[key] = out
    return out


# --------------------------------------------------------- the flat-2R sim

def simulate(entry_px, stop_px, long, b, i):
    """Flat 2R, close-triggered stop, -1.25R floor, target fills on touch.

    Identical rules to g80_dollar_reconcile.simulate -- that file's shares
    numbers are reproduced by this one and the reproduction is asserted -- with
    the exit PRICE and the exit BAR returned as well, because the option has to
    be priced at the minute the trade actually ended.

    Bar i is the minute the signal fired and the trade is opened on; management
    starts at i+1. Unresolved at 15:59 is marked to the last close.
    """
    risk = (entry_px - stop_px) if long else (stop_px - entry_px)
    if risk <= 0.005:
        return None
    target = entry_px + 2.0 * risk if long else entry_px - 2.0 * risk
    for j in range(i + 1, len(b)):
        c = b[j]
        if stop_hit_on_close(c.close, stop_px, long):
            fill = stop_fill_price(c.close, entry_px, risk, long)
            r = (fill - entry_px) / risk if long else (entry_px - fill) / risk
            return round(r, 4), "stop", fill, j
        if (long and c.high >= target) or ((not long) and c.low <= target):
            return 2.0, "target", target, j
    if len(b) <= i + 1:
        return None
    last = b[-1].close
    r = (last - entry_px) / risk if long else (entry_px - last) / risk
    return round(max(r, -1.25), 4), "eod", last, len(b) - 1


# ---------------------------------------------------------- the entry arms

def entry_for(arm, row, b, i):
    """The price each order type actually pays, or None for no fill.

    PUBLISHED  the book's own recorded entry. The control.
    B          market at the close of the signal minute. Always fillable.
    A          limit resting at the level. Fills at the level only if that
               minute traded there in the right direction (a buy limit fills
               when the bar's LOW reaches it, a sell limit when the HIGH does).
               No touch, no trade.
    """
    long = row["dir"] == "call"
    if arm == "PUBLISHED":
        return row["entry"]
    if arm == "B":
        return b[i].close
    lvl = row.get("level_px")
    if not lvl:
        return None
    if long and b[i].low <= lvl + 1e-9:
        return lvl
    if (not long) and b[i].high >= lvl - 1e-9:
        return lvl
    return None


# ------------------------------------------------------- the contract model

def strike_for(entry_px, grid=True):
    """Nearest listed strike. $1 increments -- every name in this universe has
    $1 strikes at these prices, and $2.50/$5 names would only round FURTHER
    from the money, so this is the friendly end of the assumption. `grid=False`
    is the perfectly-ATM arm T2 used, kept as a sensitivity."""
    if not grid:
        return entry_px
    return max(1.0, round(entry_px))


def mins_left(bar_i, floor_min):
    return max(RTH_MIN - bar_i, floor_min)


def price_contract(row, entry_px, stop_px, exit_px, exit_i, entry_i, sigma,
                   grid=True, floor_exit=True):
    """One trade as a same-day ATM contract. All premiums PER SHARE.

    R denominator = entry premium minus the premium the SAME contract would
    show, at the SAME instant, with the underlying already sitting at the stop.
    That price is a counterfactual on every row -- no tape holds a price for a
    level the stock was not at -- so it is modelled here exactly as T7 models
    it, real quotes or not.

    BOTH legs are floored at $0.05/share. That is the g71 board #3 fix,
    applied here and not in options_sizer.py.
    """
    call = row["dir"] == "call"
    K = strike_for(entry_px, grid)
    T0 = mins_left(entry_i, 1.0) / (RTH_MIN * SESSIONS_YR)
    T1 = mins_left(exit_i, 0.5) / (RTH_MIN * SESSIONS_YR)

    p0 = bs.price(entry_px, K, T0, sigma, call=call)
    p_stop_raw = bs.price(stop_px, K, T0, sigma, call=call)
    p_exit_raw = bs.price(exit_px, K, T1, sigma, call=call)

    p_stop = max(p_stop_raw, MIN_PREMIUM_RISK) if floor_exit else p_stop_raw
    p_exit = max(p_exit_raw, MIN_PREMIUM_RISK) if floor_exit else p_exit_raw

    raw_risk = p0 - p_stop
    if raw_risk <= 1e-9 or p0 <= 0.0:
        return None
    prem_risk = max(raw_risk, MIN_PREMIUM_RISK)
    contracts = int(MAX_LOSS // (prem_risk * MULT))
    if contracts < 1:
        return None
    dollars = contracts * (p_exit - p0) * MULT
    return {
        "K": K, "p0": p0, "p_stop": p_stop, "p_exit": p_exit,
        "prem_risk": prem_risk, "floored": raw_risk < MIN_PREMIUM_RISK,
        "contracts": contracts,
        "dollars": dollars,
        "contract_r": (p_exit - p0) / prem_risk,
        "capital": contracts * p0 * MULT,
    }


# ------------------------------------------------------------------- rows

def ekey(r):
    return (r["day"], r["et"], r["sym"])


def first_takeable_per_day(rows):
    byday = {}
    for r in rows:
        byday.setdefault(r["day"], []).append(r)
    return [sorted(v, key=lambda x: (x["et"], x["sym"]))[0]
            for _, v in sorted(byday.items())]


def build_many(rows, configs):
    """Every traded row, under several (order type, pricing) configs, in ONE
    pass over the archive. Reading 4,508 cached day files once per config
    instead of once per run is the difference between three minutes and half
    an hour; nothing about the arithmetic changes.

    configs: {name: dict(arm=, iv=, grid=, floor_exit=)}
    returns: ({name: rows}, {name: diagnostics})
    """
    out = {k: [] for k in configs}
    diag = {k: {"attempted": 0, "no_bars": 0, "no_fill": 0, "not_takeable": 0,
                "no_sigma": 0, "no_contract": 0} for k in configs}
    # iterate SYMBOL-major so the bar cache and the prior-session lookup walk
    # forward through one symbol's archive instead of thrashing across 28 of
    # them. Output order does not matter: every consumer re-sorts.
    tr = sorted([r for r in rows if r.get("traded")],
                key=lambda r: (r["sym"], r["day"], r["et"]))
    for row in tr:
        b = bars(row["sym"], row["day"])
        i = row["entry_i"]
        rng = prior_session_range(row["sym"], row["day"])
        # one simulation per distinct entry price, shared by every config that
        # asks for the same order type
        sims = {}
        for name, cfg in configs.items():
            d = diag[name]
            d["attempted"] += 1
            if not b or i >= len(b) - 1:
                d["no_bars"] += 1
                continue
            arm = cfg["arm"]
            if arm not in sims:
                ep = entry_for(arm, row, b, i)
                sims[arm] = (ep, None if ep is None
                             else simulate(ep, row["stop"], row["dir"] == "call", b, i))
            ep, sim = sims[arm]
            if ep is None:
                d["no_fill"] += 1
                continue
            if sim is None:
                d["not_takeable"] += 1
                continue
            r_u, tag, exit_px, exit_i = sim
            rec = {"day": row["day"], "sym": row["sym"], "et": row["et"],
                   "setup": row["setup"], "grade": row["grade"],
                   "sgrade": row.get("sgrade"), "tag": tag,
                   "r_underlying": r_u, "shares_dollars": r_u * RISK,
                   "entry_px": ep, "exit_px": exit_px,
                   # shares held for the same $1,000 of risk -- the stock side's
                   # own position size, needed to charge it a spread too
                   "shares_held": RISK / abs(ep - row["stop"])}
            if not rng:
                d["no_sigma"] += 1
                out[name].append(rec)
                continue
            sigma = bs.parkinson_sigma(rng, ep) * cfg.get("iv", IV_MULT)
            c = price_contract(row, ep, row["stop"], exit_px, exit_i, i, sigma,
                               grid=cfg.get("grid", True),
                               floor_exit=cfg.get("floor_exit", True))
            if c is None:
                d["no_contract"] += 1
                out[name].append(rec)
                continue
            rec.update({"dollars": c["dollars"], "contracts": c["contracts"],
                        "contract_r": c["contract_r"], "prem_risk": c["prem_risk"],
                        "p0": c["p0"], "p_exit": c["p_exit"],
                        "capital": c["capital"], "floored": c["floored"]})
            out[name].append(rec)
    return out, diag


def build(rows, arm, iv_mult=IV_MULT, grid=True, floor_exit=True):
    """One config. Thin wrapper on build_many, kept for --selfcheck."""
    o, d = build_many(rows, {"x": {"arm": arm, "iv": iv_mult, "grid": grid,
                                   "floor_exit": floor_exit}})
    return o["x"], d["x"]


def scoreable(rows):
    return [r for r in rows if "dollars" in r]


# ----------------------------------------- the pricer vs the only real tape

T7_CACHE = ROOT / "research" / "t7_alpaca_cache.json"


def calibrate(rows):
    """How far this file's modelled premium sits from a real option print.

    research/t7_alpaca_cache.json holds 276 real Alpaca 1-minute option bars,
    fetched for the superseded 1,016-row book. Its key includes the entry
    price, so only rows that survived into the current book at the SAME
    published entry match -- and the honest-fill arms pay a different price, so
    the tape cannot score them. This is a check on the PRICER, not on any
    headline in this file.

    The cached `entry_premium` is the first bar's OPEN in a window that starts
    one minute before the signal, so it is the option's price at or just before
    the signal minute; the model is asked for the price at the published entry.
    That is a minute of slack and it is part of the error reported here.
    """
    if not T7_CACHE.exists():
        return {"n": 0}
    cache = json.load(open(T7_CACHE, encoding="utf-8"))
    pairs = []
    for row in [r for r in rows if r.get("traded")]:
        k = "|".join([row["sym"], row["day"], row["et"], row["dir"],
                      str(row["entry"])])
        q = cache.get(k)
        if not q or q.get("entry_premium", 0) <= 0:
            continue
        rng = prior_session_range(row["sym"], row["day"])
        if not rng:
            continue
        pairs.append((row, q, rng))
    if not pairs:
        return {"n": 0}

    def errs_at(mult):
        out = []
        for row, q, rng in pairs:
            sigma = bs.parkinson_sigma(rng, row["entry"]) * mult
            T0 = mins_left(row["entry_i"], 1.0) / (RTH_MIN * SESSIONS_YR)
            p = bs.price(row["entry"], q["strike"], T0, sigma,
                         call=row["dir"] == "call")
            out.append((p, q["entry_premium"]))
        return out

    sweep = {}
    for m in (0.8, 0.9, 1.0, 1.1, 1.2, 1.5):
        e = errs_at(m)
        sweep["%.1f" % m] = {
            "mean_err": round(statistics.fmean(p - r for p, r in e), 4),
            "median_err": round(statistics.median(p - r for p, r in e), 4)}

    e12 = errs_at(IV_MULT)
    # T7's own scoreable filter -- Contract.ok -- requires
    # `entry_premium - modelled_stop_premium > 0`. On a real-quoted row the
    # entry premium is the TAPE's and the stop premium is the MODEL's, so that
    # test silently drops exactly the rows where the model prices ABOVE the
    # tape. Counting them is the point of this block.
    dropped = []
    for (p, real), (row, q, rng) in zip(e12, pairs):
        sigma = bs.parkinson_sigma(rng, row["entry"]) * IV_MULT
        T0 = mins_left(row["entry_i"], 1.0) / (RTH_MIN * SESSIONS_YR)
        pstop = bs.price(row["stop"], q["strike"], T0, sigma,
                         call=row["dir"] == "call")
        if real - pstop <= 1e-9:
            dropped.append(p - real)
    return {"n": len(pairs),
            "mean_err": round(statistics.fmean(p - r for p, r in e12), 4),
            "median_err": round(statistics.median(p - r for p, r in e12), 4),
            "median_abs_err": round(statistics.median(abs(p - r) for p, r in e12), 4),
            "median_real": round(statistics.median(r for _, r in e12), 3),
            "median_abs_pct": round(100 * statistics.median(
                abs(p - r) / r for p, r in e12), 1),
            "iv_sweep_vs_tape": sweep,
            "t7_would_drop": len(dropped),
            "t7_dropped_median_err": round(statistics.median(dropped), 4)
            if dropped else None}


# ------------------------------------------------------------------- main

def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    rows, nd = book["trades"], book["meta"]["sessions"]
    sessions = sorted({r["day"] for r in rows})
    res = {"meta": {"book_generated": book["meta"]["generated"],
                    "sessions": nd, "traded": book["meta"]["traded"],
                    "iv_mult": IV_MULT, "risk_dollars": RISK}}

    print("G80 OPTIONS ON HONEST FILLS")
    print("book %s  %d sessions  %d traded rows  IV = prior-session Parkinson x %.1f"
          % (book["meta"]["generated"], nd, book["meta"]["traded"], IV_MULT))
    print("reading ~4.5k cached day files per arm, three arms -- a few minutes\n",
          flush=True)

    configs = {
        "PUBLISHED": {"arm": "PUBLISHED"},
        "B": {"arm": "B"},
        "A": {"arm": "A"},
        "B_nofloor": {"arm": "B", "floor_exit": False},
        "A_nofloor": {"arm": "A", "floor_exit": False},
        "B_iv1.0": {"arm": "B", "iv": 1.0},
        "B_iv1.5": {"arm": "B", "iv": 1.5},
        "B_atm": {"arm": "B", "grid": False},
        "A_iv1.0": {"arm": "A", "iv": 1.0},
    }
    built, diags = build_many(rows, configs)
    arms = built
    res["diagnostics"] = {k: diags[k] for k in ("PUBLISHED", "B", "A")}

    # ---- 1. the headline table -------------------------------------------
    print("\n1. DOLLARS A DAY -- one trade a day, and everything taken")
    print("   %-10s %-9s %7s %7s %10s %22s %7s %11s"
          % ("order", "instr", "trades", "win%", "$/day", "95% interval",
             "green", "worst DD"))
    res["headline"] = {}
    for arm in ("PUBLISHED", "B", "A", "B_iv1.0", "A_iv1.0"):
        sc = scoreable(arms[arm])
        one_o = first_takeable_per_day(sc)
        one_s = first_takeable_per_day(arms[arm])
        for lbl, rws, key in (("options 1/day", one_o, "dollars"),
                              ("shares  1/day", one_s, "shares_dollars"),
                              ("options all", sc, "dollars"),
                              ("shares  all", arms[arm], "shares_dollars")):
            st = price_block(rws, nd, key)
            ci = day_ci(rws, sessions, key)
            res["headline"].setdefault(arm, {})[lbl] = dict(st, ci=ci)
            print("   %-10s %-9s %7d %6.1f%% %10s %22s %5d/%d %11s"
                  % (arm, lbl, st["trades"], st["win_pct"],
                     "$%.0f" % st["per_day"],
                     "[$%.0f, $%.0f]" % (ci["lo"], ci["hi"]),
                     st["months_green"], st["months"],
                     "$%.0f" % st["worst_drawdown"]))

    # ---- 2. options minus shares, paired ----------------------------------
    print("\n2. DO OPTIONS BEAT SHARES? paired per-day difference, same trades")
    res["options_minus_shares"] = {}
    for arm in ("PUBLISHED", "B", "A", "B_iv1.0", "A_iv1.0"):
        sc = scoreable(arms[arm])
        one = first_takeable_per_day(sc)
        for lbl, rws in (("one a day", one), ("everything", sc)):
            a = [dict(r, d=r["dollars"]) for r in rws]
            b = [dict(r, d=r["shares_dollars"]) for r in rws]
            ci = paired_day_ci(a, b, sessions, "d")
            res["options_minus_shares"].setdefault(arm, {})[lbl] = ci
            print("   %-10s %-12s %+10s /day   [%s, %s]  %s"
                  % (arm, lbl, "$%.0f" % ci["per_day"],
                     "$%+.0f" % ci["lo"], "$%+.0f" % ci["hi"],
                     "TIE (crosses zero)" if ci["crosses_zero"] else "separated"))

    # ---- 3. per month, order type B, options vs shares --------------------
    print("\n3. PER MONTH -- order type B, one trade a day")
    sc = first_takeable_per_day(scoreable(arms["B"]))
    bym = {}
    for r in sc:
        m = bym.setdefault(r["day"][:7], {"n": 0, "o": 0.0, "s": 0.0, "ow": 0})
        m["n"] += 1
        m["o"] += r["dollars"]
        m["s"] += r["shares_dollars"]
        m["ow"] += 1 if r["dollars"] > 0 else 0
    res["per_month_B_one_a_day"] = bym
    print("   %-9s %5s %12s %12s  %s" % ("month", "n", "options $", "shares $", "green"))
    for m in sorted(bym):
        v = bym[m]
        g = ("both" if v["o"] > 0 and v["s"] > 0 else
             "options" if v["o"] > 0 else "shares" if v["s"] > 0 else "neither")
        print("   %-9s %5d %12s %12s  %s"
              % (m, v["n"], "$%+.0f" % v["o"], "$%+.0f" % v["s"], g))

    # ---- 4. the -1.25R floor on contracts ---------------------------------
    print("\n4. THE -1.25R FLOOR, ON CONTRACTS")
    res["floor"] = {}
    for arm in ("PUBLISHED", "B", "A"):
        sc = scoreable(arms[arm])
        one = first_takeable_per_day(sc)
        worse = [r for r in sc if r["contract_r"] < -1.25]
        u_worse = [r for r in sc if r["r_underlying"] < -1.2501]
        # dollars if a PREMIUM stop capped every contract loss at -1.25 R,
        # where 1 R is that row's own floored premium risk on the contracts held
        def cap(r):
            worst = -1.25 * r["prem_risk"] * r["contracts"] * MULT
            return max(r["dollars"], worst)
        d_cap = sum(cap(r) for r in sc)
        d_now = sum(r["dollars"] for r in sc)
        o_cap = sum(cap(r) for r in one)
        o_now = sum(r["dollars"] for r in one)
        res["floor"][arm] = {
            "n": len(sc),
            "contract_rows_past_minus_1_25R": len(worse),
            "underlying_rows_past_minus_1_25R": len(u_worse),
            "worst_contract_r": round(min(r["contract_r"] for r in sc), 3) if sc else None,
            "worst_underlying_r": round(min(r["r_underlying"] for r in sc), 3) if sc else None,
            "dollars_now": round(d_now, 0),
            "dollars_if_premium_stop_at_minus_1_25R": round(d_cap, 0),
            "dollars_per_day_delta": round((d_cap - d_now) / nd, 0),
            "one_a_day_dollars_now": round(o_now, 0),
            "one_a_day_dollars_if_capped": round(o_cap, 0),
            "one_a_day_per_day_delta": round((o_cap - o_now) / nd, 0),
            "one_a_day_rows_past_minus_1_25R":
                sum(1 for r in one if r["contract_r"] < -1.25),
        }
        f = res["floor"][arm]
        print("   %-10s contract rows worse than -1.25R: %4d of %4d (%.1f%%)   "
              "worst contract %+.2fR   worst underlying %+.2fR"
              % (arm, f["contract_rows_past_minus_1_25R"], f["n"],
                 100.0 * f["contract_rows_past_minus_1_25R"] / f["n"] if f["n"] else 0,
                 f["worst_contract_r"], f["worst_underlying_r"]))
        print("             a premium stop at -1.25R: %s a day taking everything, "
              "%s a day one-a-day (%d of %d one-a-day rows are past it)" %
              ("$%+.0f" % f["dollars_per_day_delta"],
               "$%+.0f" % f["one_a_day_per_day_delta"],
               f["one_a_day_rows_past_minus_1_25R"], len(one)))
        print("             contracts held: median %d, p90 %d, max %d; capital at risk "
              "median $%.0f, p90 $%.0f"
              % (statistics.median(r["contracts"] for r in sc),
                 sorted(r["contracts"] for r in sc)[int(.9 * len(sc))],
                 max(r["contracts"] for r in sc),
                 statistics.median(r["capital"] for r in sc),
                 sorted(r["capital"] for r in sc)[int(.9 * len(sc))]))

    # ---- 5. the g71 board #3 floor bug, sized ----------------------------
    print("\n5. THE $0.05 FLOOR ON ONE LEG ONLY (g71 board bug #3), sized here")
    res["floor_bug"] = {}
    for arm in ("B", "A"):
        both, one = arms[arm], arms[arm + "_nofloor"]
        b1 = price_block(first_takeable_per_day(scoreable(both)), nd, "dollars")
        o1 = price_block(first_takeable_per_day(scoreable(one)), nd, "dollars")
        ba = price_block(scoreable(both), nd, "dollars")
        oa = price_block(scoreable(one), nd, "dollars")
        nb = sum(1 for r in scoreable(both) if r["p_exit"] <= MIN_PREMIUM_RISK + 1e-9)
        res["floor_bug"][arm] = {"both_legs_floored_per_day": b1["per_day"],
                                 "exit_leg_unfloored_per_day": o1["per_day"],
                                 "both_legs_floored_per_day_all": ba["per_day"],
                                 "exit_leg_unfloored_per_day_all": oa["per_day"],
                                 "rows_where_exit_premium_hits_the_floor": nb}
        print("   %-3s both legs floored: $%.0f/day one-a-day, $%.0f/day all   "
              "exit leg unfloored: $%.0f/day one-a-day, $%.0f/day all   "
              "(%d rows exit at the floor)"
              % (arm, b1["per_day"], ba["per_day"], o1["per_day"], oa["per_day"], nb))

    # ---- 6. sensitivity ---------------------------------------------------
    print("\n6. SENSITIVITY -- order type B, one trade a day, options")
    res["sensitivity"] = {}
    for iv, name in ((1.0, "B_iv1.0"), (1.2, "B"), (1.5, "B_iv1.5")):
        s = price_block(first_takeable_per_day(scoreable(arms[name])), nd, "dollars")
        res["sensitivity"]["iv_%.1f" % iv] = s
        print("   IV %.1fx prior-session Parkinson : %7s /day  %5.1f%% win  %d/%d green"
              % (iv, "$%.0f" % s["per_day"], s["win_pct"], s["months_green"], s["months"]))
    s = price_block(first_takeable_per_day(scoreable(arms["B_atm"])), nd, "dollars")
    res["sensitivity"]["strike_exactly_atm"] = s
    print("   strike exactly ATM (no $1 grid)  : %7s /day  %5.1f%% win  %d/%d green"
          % ("$%.0f" % s["per_day"], s["win_pct"], s["months_green"], s["months"]))

    # ---- 7. arm A's structural ceiling ------------------------------------
    tr = [r for r in rows if r.get("traded")]
    lvl_is_stop = sum(1 for r in tr if abs(r["level_px"] - r["stop"]) < EPS)
    res["arm_A_structure"] = {
        "traded_rows": len(tr),
        "level_is_the_stop": lvl_is_stop,
        "entry_was_at_the_level": sum(1 for r in tr
                                      if abs(r["entry"] - r["level_px"]) < EPS),
        "arm_A_filled": len(arms["A"]),
        "days_with_an_A_fill": len({r["day"] for r in arms["A"]}),
        "days_with_a_B_fill": len({r["day"] for r in arms["B"]}),
    }
    a = res["arm_A_structure"]
    print("\n7. WHY ORDER TYPE A IS SMALLER THAN THE BOOK")
    print("   the level IS the stop on %d of %d traded rows (%.1f%%) -- a limit "
          "resting there is a limit at your own stop, so there is no trade to take"
          % (lvl_is_stop, len(tr), 100.0 * lvl_is_stop / len(tr)))
    print("   arm A fills %d rows on %d of %d sessions; arm B fills %d rows on %d"
          % (a["arm_A_filled"], a["days_with_an_A_fill"], nd,
             len(arms["B"]), a["days_with_a_B_fill"]))

    # ---- 8. exit mix and premium size ------------------------------------
    print("\n8. EXIT MIX AND WHAT A CONTRACT COSTS")
    res["exit_mix"] = {}
    for arm in ("PUBLISHED", "B", "A"):
        sc = scoreable(arms[arm])
        mix = {t: sum(1 for r in sc if r["tag"] == t) for t in ("target", "stop", "eod")}
        p0s = sorted(r["p0"] for r in sc)
        res["exit_mix"][arm] = dict(
            mix, n=len(sc),
            entry_premium_median=round(p0s[len(p0s) // 2], 3),
            entry_premium_p10=round(p0s[int(.10 * len(p0s))], 3),
            entry_premium_p90=round(p0s[int(.90 * len(p0s))], 3),
            premium_risk_median=round(
                statistics.median(r["prem_risk"] for r in sc), 3),
            rows_on_the_premium_risk_floor=sum(1 for r in sc if r["floored"]))
        e = res["exit_mix"][arm]
        print("   %-10s target %4d  stop %4d  end-of-day %3d   entry premium "
              "median $%.2f (p10 $%.2f, p90 $%.2f)   premium risk median $%.2f   "
              "%d rows on the $0.05 risk floor"
              % (arm, e["target"], e["stop"], e["eod"], e["entry_premium_median"],
                 e["entry_premium_p10"], e["entry_premium_p90"],
                 e["premium_risk_median"], e["rows_on_the_premium_risk_floor"]))

    # ---- 9. the pricer against the only real tape this repo has ----------
    print("\n9. THE MODEL AGAINST T7's REAL ALPACA QUOTES")
    res["calibration"] = calibrate(rows)
    c = res["calibration"]
    if c["n"]:
        print("   %d of the book's traded rows have a real Alpaca 1-min option bar in "
              "research/t7_alpaca_cache.json (fetched for the superseded 1,016-row "
              "book; the key is sym|day|time|dir|entry so only PUBLISHED-fill rows "
              "match at all)." % c["n"])
        print("   entry premium, model minus tape: mean $%+.3f  median $%+.3f  "
              "median |error| $%.3f on a median tape premium of $%.2f (%.0f%%)"
              % (c["mean_err"], c["median_err"], c["median_abs_err"],
                 c["median_real"], c["median_abs_pct"]))
        print("   the same error at other IV multipliers (this is how you pick one):")
        for m, v in sorted(c["iv_sweep_vs_tape"].items()):
            print("      %sx  mean $%+.3f  median $%+.3f" % (m, v["mean_err"],
                                                             v["median_err"]))
        print("   T7's scoreable filter would drop %d of these %d rows -- and it "
              "drops them BECAUSE the model prices above the tape there "
              "(median error on the dropped rows $%+.2f)."
              % (c["t7_would_drop"], c["n"], c["t7_dropped_median_err"]))
    else:
        print("   no overlap; skipped.")

    # ---- 10. the spread, on both instruments ------------------------------
    #
    # Nobody in this repo has read a real bid/ask on a 0DTE contract on these
    # names -- the options snapshot is not authorised on the data plan and the
    # broker session has never been logged. So this is a PARAMETER SWEEP, not a
    # measurement, and it is the single number most likely to decide the
    # answer: the option position is ~30 contracts (3,000 shares of exposure)
    # bought at a wide quote, the stock position is ~3,000 shares bought at a
    # penny quote, and the two do not pay the same toll.
    print("\n10. THE SPREAD -- a parameter, not a measurement, and it decides "
          "the answer")
    res["spread"] = {}
    print("   %-8s %-24s %10s %10s %10s"
          % ("order", "round trip", "options", "shares", "options-shares"))
    for arm in ("B", "A", "B_iv1.0", "A_iv1.0"):
        sc = scoreable(arms[arm])
        one = first_takeable_per_day(sc)
        for opt_rt, shr_rt in ((0.02, 0.01), (0.05, 0.01), (0.10, 0.01),
                               (0.05, 0.02)):
            o = sum(r["dollars"] - r["contracts"] * opt_rt * MULT for r in one)
            s = sum(r["shares_dollars"] - r["shares_held"] * shr_rt for r in one)
            res["spread"].setdefault(arm, {})["opt%.2f_shr%.2f" % (opt_rt, shr_rt)] = {
                "options_per_day": round(o / nd, 0), "shares_per_day": round(s / nd, 0),
                "diff_per_day": round((o - s) / nd, 0)}
            print("   %-8s option $%.2f / stock $%.2f  %10s %10s %10s"
                  % (arm, opt_rt, shr_rt, "$%.0f" % (o / nd), "$%.0f" % (s / nd),
                     "$%+.0f" % ((o - s) / nd)))
    med_ct = statistics.median(r["contracts"] for r in
                               first_takeable_per_day(scoreable(arms["B"])))
    med_sh = statistics.median(r["shares_held"] for r in
                               first_takeable_per_day(arms["B"]))
    res["spread"]["position_size"] = {"median_contracts": med_ct,
                                      "median_shares": round(med_sh, 0)}
    print("   position size, order type B one-a-day: median %d contracts "
          "(%d shares of exposure) against %d shares on the stock side"
          % (med_ct, med_ct * MULT, med_sh))

    json.dump(res, open(OUT, "w"), indent=1)
    print("\nwrote %s" % OUT)
    return res


# ---------------------------------------------------------------- selfcheck

def selfcheck():
    ok = True
    # Everything ABOVE `def selfcheck` -- the measurement itself. The checks
    # below must not match their own text.
    src = Path(__file__).read_text(encoding="utf-8").split("def selfcheck(")[0]

    # 1. no same-day volatility anywhere in the pricing path. The look-ahead
    #    that killed research/t2_options_tape.md was `row["drange"]` -- the
    #    day's own full-session range. Any READ of that field fails this check;
    #    prose about it in a comment or docstring does not.
    import re
    bad = [ln for ln in src.splitlines()
           if re.search(r'(\[|\.get\()\s*["\']drange["\']', ln)]
    print("[%s] the day's own range is never read in the pricing path "
          "(%d field accesses found)" % ("ok" if not bad else "FAIL", len(bad)))
    ok &= not bad

    # 1b. and the only volatility input is the PRIOR session
    print("[%s] prior_session_range is the sole sigma source (%d call sites, all "
          "in build_many/calibrate)"
          % ("ok" if src.count("prior_session_range(") >= 3 else "FAIL",
             src.count("prior_session_range(") - 1))

    # 2. both legs floored the same way
    both, _ = build(json.load(open(BOOK, encoding="utf-8"))["trades"], "B")
    sc = scoreable(both)
    viol = [r for r in sc if r["p_exit"] < MIN_PREMIUM_RISK - 1e-9]
    print("[%s] every exit premium >= $%.2f (the same floor the stop leg gets): "
          "%d violations" % ("ok" if not viol else "FAIL", MIN_PREMIUM_RISK, len(viol)))
    ok &= not viol

    # 3. the shares side reproduces the sibling agent's honest-fill figure
    book = json.load(open(BOOK, encoding="utf-8"))
    nd = book["meta"]["sessions"]
    s1 = price_block(first_takeable_per_day(both), nd, "shares_dollars")
    sall = price_block(both, nd, "shares_dollars")
    match = s1["per_day"] == 187 and sall["per_day"] == 650
    print("[%s] shares, order type B: $%.0f/day one-a-day, $%.0f/day everything "
          "-- research/g80_dollar_reconcile.md reports $187 and $650 from an "
          "independently written rig" % ("ok" if match else "FAIL",
                                         s1["per_day"], sall["per_day"]))
    ok &= match

    # 4. this file measures; it does not import or call anything that could
    #    change an engine. Named imports only, asserted from the source.
    forbidden = [m for m in ("import options_sizer", "from options_sizer",
                             "import signal_runner", "import backtest_2y",
                             "import backtest_week") if m in src]
    print("[%s] this file never imports options_sizer / signal_runner / "
          "backtest_2y / backtest_week (%s)"
          % ("ok" if not forbidden else "FAIL",
             "none found" if not forbidden else ", ".join(forbidden)))
    ok &= not forbidden
    writes = [ln.strip() for ln in src.splitlines()
              if 'open(' in ln and '"w"' in ln]
    print("[%s] the only file this run writes is its own .json (%d write sites: %s)"
          % ("ok" if len(writes) == 1 and "OUT" in writes[0] else "FAIL",
             len(writes), "; ".join(writes)))
    ok &= len(writes) == 1 and "OUT" in writes[0]

    # 5. contracts are sized off the FLOORED risk, so max 200 on $1,000
    over = [r for r in sc if r["contracts"] > MAX_LOSS / (MIN_PREMIUM_RISK * MULT)]
    print("[%s] no row holds more than %d contracts on $%.0f of risk: %d violations"
          % ("ok" if not over else "FAIL",
             int(MAX_LOSS / (MIN_PREMIUM_RISK * MULT)), MAX_LOSS, len(over)))
    ok &= not over

    print("SELFCHECK %s" % ("PASSED" if ok else "FAILED"))
    return ok


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        sys.exit(0 if selfcheck() else 1)
    main()
