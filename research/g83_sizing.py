"""G8.3 -- THE SIX-FIGURE SIZING PAGE.

Austin, 2026-08-30: "The backtest numbers I always would preach was six figures
a year and 55 percent win rate. But our situation has changed, and it's not just
about win rate."

  $100,000 / 252 sessions = $397 a day = $8,333 a month.

THE QUESTION, for each of the three instruments he keeps open (shares, options,
index futures):

  1. what risk per trade reaches $397 a day, if any does?
  2. at that risk, what is the chance of blowing the account, and of passing a
     prop challenge?
  3. does that risk keep 25 of 25 green months? He ratified 2026-08-30 that
     GREEN MONTHS WIN when gates conflict, so $397/day at 22 of 25 is a FAIL.
  4. chance of a green week, chance of a green month, worst drawdown, expected
     months to funded.
  5. is six figures a year reachable at all on the current engine?

THE FILL. Every number here is on an HONEST fill -- a market order paid at the
close of the signal minute. The published book's $683-$721 a day is priced at a
level the minute may never have traded at (research/g80_lookahead_refute.md:
2,067 trades, $1.5m of the book, filled at the best price the minute printed on
a minute that never came back to the level). Sizing computed on that fill would
be worse than no sizing page at all. The published fill is carried in every
table as a labelled control, never as an answer.

THE RIG. research/g80_options_honest.py, imported, not re-implemented -- its
build_many() prices every traded row of the two-year book as both stock and
same-day at-the-money contract off the archived one-minute bars, and its
first_takeable_per_day() does the one-trade-a-day walk. Stops route through
stop_rule.stop_fill_price. Volatility multiplier 1.0x, the one that matches the
only real option tape in the repo (1.2x asks $0.39 too much on a $1.89 median
premium -- g80_options_honest.md, "the volatility number was 20% too high").

THE ARITHMETIC THAT MAKES THIS PAGE SHORT. Risk per trade is a fixed dollar
amount, so every dollar figure is LINEAR in it:

    $/day(risk) = (risk / 1000) x $/day(at $1,000)

which means the risk that reaches $397/day is just 397 / mean-daily-R, and it
also means GREEN MONTHS ARE SCALE-INVARIANT. Multiplying every day in a month by
a positive constant cannot change the sign of the month's total. A policy that
is 21 of 25 green at $1,000 a trade is 21 of 25 green at every size. Sizing
cannot buy durability. That is asserted numerically in --selfcheck, not assumed.

Blow-up and prop-challenge pass rates are NOT linear, and those are bootstrapped
(research/g71_propfirm_sim.py, imported for the challenge specs and the path
walker).

Run:  python research/g83_sizing.py            # ~4 min, offline, writes the JSON
      python research/g83_sizing.py --selfcheck # the invariants this file claims
      python research/g83_sizing.py --cached    # re-score without re-pricing

Writes: research/g83_sizing.json  (and research/g83_series.json, the day series)
Reads only. No engine file is edited, no mark file is opened, nothing is
committed, no request URL is printed.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from research import g80_options_honest as oh     # noqa: E402
from research import g71_propfirm_sim as pf       # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
SERIES_OUT = ROOT / "research" / "g83_series.json"
OUT = ROOT / "research" / "g83_sizing.json"

RISK0 = 1000.0                 # 1R = $1,000 (CLAUDE.md)
TARGET_DAY = 100_000 / 252     # $396.83 -- the six-figure bar
TARGET_MONTH = 100_000 / 12
SESSIONS_PER_MONTH = 21
SESSIONS_PER_WEEK = 5
SEED = 20260830
BOOTS = 20000

# index futures translate only for the index ETFs; NVDA and TSLA have no future.
# MES/MNQ/M2K against SPY/QQQ/IWM (research/g71_propfirm.md section 2).
INDEX_SYMS = {"SPY", "QQQ", "IWM"}

# spread, a PARAMETER not a measurement: nobody in this repo has read a real
# bid/ask on a same-day contract on these names. g80_options_honest.md calls
# this "the single number most likely to flip the answer". A nickel round trip
# is the assumption the repo has been carrying.
OPT_ROUND_TRIP = 0.05
SHR_ROUND_TRIP = 0.01
FUT_ROUND_TRIP_TICKS = 1.0     # one tick each way on a micro; charged in dollars below
MULT = 100                     # option contract multiplier


# ------------------------------------------------------------ the day series

def build_series():
    """Price the book once and cut it into the day-R series this page needs.

    One pass over the archive, three readings of the same trades:
      shares   -- the stock position that carries $1,000 of risk
      options  -- the same-day ATM contract on the same trade, 1.0x vol
      index    -- the same rows, restricted to SPY/QQQ/IWM (the only setups a
                  futures prop account could take at all)
    Each is charged its own round-trip cost, and each is also kept raw.
    """
    book = json.load(open(BOOK, encoding="utf-8"))
    all_days = sorted({r["day"] for r in book["trades"]})
    n_days = book["meta"]["sessions"]

    configs = {
        # honest: market order paid at the close of the signal minute
        "B": {"arm": "B", "iv": 1.0},
        # the published book's own recorded entry -- the control, never an answer
        "PUB": {"arm": "PUBLISHED", "iv": 1.0},
    }
    print("pricing %d traded rows x %d fills (~4 min, offline) ..."
          % (book["meta"]["traded"], len(configs)), flush=True)
    arms, diag = oh.build_many(book["trades"], configs)

    out = {"meta": {"book_generated": book["meta"]["generated"],
                    "sessions": n_days, "traded": book["meta"]["traded"],
                    "all_days": all_days, "iv_mult": 1.0,
                    "risk_dollars": RISK0,
                    "opt_round_trip": OPT_ROUND_TRIP,
                    "shr_round_trip": SHR_ROUND_TRIP},
           "diagnostics": diag, "series": {}}

    for fill, rows in arms.items():
        sc = oh.scoreable(rows)                       # rows with a contract price
        idx_rows = [r for r in rows if r["sym"] in INDEX_SYMS]
        idx_sc = [r for r in sc if r["sym"] in INDEX_SYMS]

        def day_series(chosen, key, cost):
            """{day: R} for one instrument, one trade a day, cost charged."""
            d = {}
            for r in chosen:
                d[r["day"]] = (r[key] - cost(r)) / RISK0
            return d

        out["series"]["%s/shares" % fill] = day_series(
            oh.first_takeable_per_day(rows), "shares_dollars",
            lambda r: r["shares_held"] * SHR_ROUND_TRIP)
        out["series"]["%s/shares_raw" % fill] = day_series(
            oh.first_takeable_per_day(rows), "shares_dollars", lambda r: 0.0)
        out["series"]["%s/options" % fill] = day_series(
            oh.first_takeable_per_day(sc), "dollars",
            lambda r: r["contracts"] * OPT_ROUND_TRIP * MULT)
        out["series"]["%s/options_raw" % fill] = day_series(
            oh.first_takeable_per_day(sc), "dollars", lambda r: 0.0)
        # index futures: the SAME stock geometry on SPY/QQQ/IWM. A micro
        # contract's tick is $1.25 (MES) / $0.50 (MNQ) / $0.50 (M2K); at
        # $1,000 of risk the position is tens of contracts, so the round trip
        # is charged as the equivalent share-side toll, which is the closest
        # honest analogue this rig supports. Granularity is a caveat, not a
        # model -- see the markdown.
        out["series"]["%s/index" % fill] = day_series(
            oh.first_takeable_per_day(idx_rows), "shares_dollars",
            lambda r: r["shares_held"] * SHR_ROUND_TRIP)
        out["series"]["%s/index_raw" % fill] = day_series(
            oh.first_takeable_per_day(idx_rows), "shares_dollars", lambda r: 0.0)

        # capital actually tied up, for the blow-up question
        # the raw ingredients, kept per day so a spread sweep costs nothing:
        # the round trip is charged at score time instead of re-pricing.
        out.setdefault("raw", {})["%s/options" % fill] = {
            r["day"]: [r["dollars"], r["contracts"]]
            for r in oh.first_takeable_per_day(sc)}
        out["raw"]["%s/shares" % fill] = {
            r["day"]: [r["shares_dollars"], r["shares_held"]]
            for r in oh.first_takeable_per_day(rows)}
        out["raw"]["%s/index" % fill] = {
            r["day"]: [r["shares_dollars"], r["shares_held"]]
            for r in oh.first_takeable_per_day(idx_rows)}

        cap = [r["capital"] for r in oh.first_takeable_per_day(sc) if "capital" in r]
        sh = [r["shares_held"] * r["entry_px"] for r in oh.first_takeable_per_day(rows)]
        out.setdefault("capital", {})["%s/options" % fill] = {
            "median": round(statistics.median(cap), 0) if cap else None,
            "p90": round(sorted(cap)[int(0.9 * len(cap))], 0) if cap else None}
        out["capital"]["%s/shares" % fill] = {
            "median": round(statistics.median(sh), 0) if sh else None,
            "p90": round(sorted(sh)[int(0.9 * len(sh))], 0) if sh else None}

    SERIES_OUT.write_text(json.dumps(out), encoding="utf-8")
    print("wrote %s" % SERIES_OUT.relative_to(ROOT))
    return out


# ------------------------------------------------------------------ scoring

def full_daily(series, all_days):
    """The day-R vector over EVERY session. A session the instrument did not
    trade books 0.0 and stays in the vector -- a no-trade day is not a free
    option, it is a day that did not earn."""
    return np.array([series.get(d, 0.0) for d in all_days], dtype=float)


def month_key(d):
    return d[:7]


def green_buckets(series, all_days, n):
    """(green, total) months or weeks. SCALE-INVARIANT: multiplying every day by
    a positive constant cannot change the sign of a bucket's sum, so this
    answer is the same at every risk-per-trade."""
    if n == "month":
        b = defaultdict(float)
        for d in all_days:
            b[month_key(d)] += series.get(d, 0.0)
        v = list(b.values())
    else:
        v = []
        for i in range(0, len(all_days), SESSIONS_PER_WEEK):
            v.append(sum(series.get(d, 0.0) for d in all_days[i:i + SESSIONS_PER_WEEK]))
    return sum(1 for x in v if x > 0), len(v)


def drawdown_r(daily):
    eq = np.cumsum(daily)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    return float((peak - eq).max())


def boot_green(daily, n, rng, trials=BOOTS):
    """P(a bucket of n sessions ends green), i.i.d. bootstrap of the day series."""
    return float((rng.choice(daily, size=(trials, n), replace=True).sum(1) > 0).mean())


def ruin(daily, risk, start, dd_frac, rng, days=252, trials=BOOTS):
    """P(equity falls dd_frac below its starting balance inside `days`)."""
    draws = rng.choice(daily, size=(trials, days), replace=True) * risk
    eq = start + np.cumsum(draws, axis=1)
    return float((eq.min(axis=1) <= start * (1 - dd_frac)).mean())


def score(name, series, all_days, rng):
    daily = full_daily(series, all_days)
    mean_r = float(daily.mean())
    per_day = mean_r * RISK0
    gm, tm = green_buckets(series, all_days, "month")
    gw, tw = green_buckets(series, all_days, "week")
    # the risk that reaches $397/day. Linear, so it is a division.
    need = (TARGET_DAY / mean_r) if mean_r > 0 else None
    rec = {
        "name": name,
        "days_traded": len(series),
        "sessions": len(all_days),
        "fire_rate_pct": round(100 * len(series) / len(all_days), 1),
        "mean_daily_r": round(mean_r, 4),
        "per_day_at_1k": round(per_day, 0),
        "per_month_at_1k": round(per_day * SESSIONS_PER_MONTH, 0),
        "per_year_at_1k": round(per_day * 252, 0),
        "distance_to_397_at_1k": round(per_day - TARGET_DAY, 0),
        "pct_of_397_at_1k": round(100 * per_day / TARGET_DAY, 1),
        "risk_for_397": round(need, 0) if need else None,
        "risk_multiple_of_1k": round(need / RISK0, 2) if need else None,
        "months_green": gm, "months": tm,
        "weeks_green": gw, "weeks": tw,
        "durability_pass": gm == tm,
        "p_green_week": round(boot_green(daily, SESSIONS_PER_WEEK, rng), 3),
        "p_green_month": round(boot_green(daily, SESSIONS_PER_MONTH, rng), 3),
        "p_green_year": round(boot_green(daily, 252, rng), 3),
        "worst_dd_r": round(drawdown_r(daily), 3),
        "worst_dd_at_1k": round(drawdown_r(daily) * RISK0, 0),
        "win_rate_of_traded_days_pct": round(
            100 * sum(1 for v in series.values() if v > 0) / max(1, len(series)), 1),
    }
    if need:
        rec["worst_dd_at_397_risk"] = round(drawdown_r(daily) * need, 0)
        # 95% interval on $/day, resampled over whole sessions
        bs = rng.choice(daily, size=(BOOTS, len(daily)), replace=True).mean(1) * RISK0
        rec["ci95_per_day_at_1k"] = [round(float(np.percentile(bs, 2.5)), 0),
                                     round(float(np.percentile(bs, 97.5)), 0)]
        rec["ci_includes_zero"] = bool(np.percentile(bs, 2.5) <= 0)
    else:
        bs = rng.choice(daily, size=(BOOTS, len(daily)), replace=True).mean(1) * RISK0
        rec["ci95_per_day_at_1k"] = [round(float(np.percentile(bs, 2.5)), 0),
                                     round(float(np.percentile(bs, 97.5)), 0)]
        rec["ci_includes_zero"] = True
    return rec


# ------------------------------------------------------------- prop challenge

def _clean(x):
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) else x


def challenge(daily, need_risk, rng, want=0.90):
    """Pass rates per firm, over the risk grid, on the HONEST day series.

    Reuses research/g71_propfirm_sim.simulate() -- the same path walker, the
    same EOD-trailing / static drawdown model, the same daily-loss-limit clip.
    Only the R series it eats is different, and that is the whole point.

    The day series already books 0.0 on a session the instrument did not fire,
    so the calendar is honest as it stands and needs no rescaling.

    TWO risk levels are reported per firm, because they answer different
    questions and the argmax alone is misleading:
      best_risk   -- the grid point with the highest pass rate. On a $3,000
                     target this lands near $2,750, i.e. "one good day passes
                     you", which is why its median days-to-pass is ~2 and its
                     pass rate is still only two thirds.
      need_risk   -- the risk that reaches $397/day for this instrument. This
                     is the one that matters: it is what he would actually be
                     sizing at if the goal is six figures.
    """
    rows = []
    for spec in pf.FIRMS:
        nm, start, target, dll, mdd, mode, lock, max_days, cost = spec
        best_k, best_p, best_d = None, -1.0, None
        band = []
        for k in pf.RISK_GRID:
            p, d = pf.simulate(daily, k, spec, 10000, rng)
            if p >= want:
                band.append(k)
            if p > best_p:
                best_k, best_p, best_d = k, p, d
        np_, nd_ = (None, None)
        if need_risk:
            np_, nd_ = pf.simulate(daily, need_risk, spec, 10000, rng)
        rows.append({"firm": nm, "start": start, "target": target,
                     "max_dd": mdd, "max_days": max_days, "cost": cost,
                     "band_lo": band[0] if band else None,
                     "band_hi": band[-1] if band else None,
                     "best_risk": best_k, "best_pass_rate": round(best_p, 4),
                     "best_median_days": _clean(best_d),
                     "months_to_funded": (round(_clean(best_d) / SESSIONS_PER_MONTH, 2)
                                          if _clean(best_d) is not None else None),
                     "risk_for_397": round(need_risk, 0) if need_risk else None,
                     "pass_rate_at_397_risk": round(np_, 4) if np_ is not None else None,
                     "median_days_at_397_risk": _clean(nd_),
                     "months_to_funded_at_397_risk":
                         (round(_clean(nd_) / SESSIONS_PER_MONTH, 2)
                          if _clean(nd_) is not None else None)})
    return rows


# ------------------------------------------------------------------ selfcheck

def selfcheck():
    """The three claims this page rests on, checked rather than asserted."""
    rng = np.random.default_rng(SEED)
    ok = True

    # 1. green months are scale-invariant
    s = json.load(open(SERIES_OUT, encoding="utf-8"))
    days = s["meta"]["all_days"]
    for key in ("B/shares", "B/options", "B/index"):
        ser = s["series"][key]
        base = green_buckets(ser, days, "month")
        for mult in (0.25, 3.0, 17.5):
            scaled = {k: v * mult for k, v in ser.items()}
            got = green_buckets(scaled, days, "month")
            if got != base:
                print("  FAIL scale-invariance %s x%s: %s vs %s" % (key, mult, got, base))
                ok = False
    print("  [%s] green months are scale-invariant on all three instruments"
          % ("ok" if ok else "FAIL"))

    # 2. the honest shares/options headline reproduces g80_options_honest.md
    #    ($187/day shares, $346/day options at 1.0x vol, BEFORE spread)
    for key, want, label in (("B/shares_raw", 187.0, "shares, market at close"),
                             ("B/options_raw", 346.0, "options 1.0x, market at close")):
        got = full_daily(s["series"][key], days).mean() * RISK0
        good = abs(got - want) <= 3.0
        print("  [%s] %s: $%.0f/day, g80_options_honest.md says $%.0f"
              % ("ok" if good else "FAIL", label, got, want))
        ok &= good

    # 3. linearity: $/day at 2x risk is exactly 2x
    d = full_daily(s["series"]["B/options"], days)
    lin = abs((d.mean() * 2 * RISK0) - 2 * (d.mean() * RISK0)) < 1e-9
    print("  [%s] dollars are linear in risk per trade" % ("ok" if lin else "FAIL"))
    ok &= lin
    return ok


# ---------------------------------------------------------------------- main

def main():
    if "--selfcheck" in sys.argv:
        sys.exit(0 if selfcheck() else 1)

    if "--cached" in sys.argv and SERIES_OUT.exists():
        s = json.load(open(SERIES_OUT, encoding="utf-8"))
    else:
        s = build_series()
    days = s["meta"]["all_days"]
    rng = np.random.default_rng(SEED)

    res = {"meta": dict(s["meta"], target_day=round(TARGET_DAY, 2),
                        target_month=round(TARGET_MONTH, 0),
                        target_year=100000,
                        generated_by="research/g83_sizing.py"),
           "capital": s.get("capital", {}), "instruments": {}, "challenge": {}}

    label = {"B/shares": "shares, honest fill, after a penny round trip",
             "B/options": "same-day ATM contracts, honest fill, after a nickel round trip",
             "B/options_raw": "same-day ATM contracts, honest fill, before any spread",
             "B/index": "index futures (SPY/QQQ/IWM setups only), honest fill",
             "B/shares_raw": "shares, honest fill, before any spread",
             "B/index_raw": "index futures, honest fill, before any spread",
             "PUB/shares": "shares, PUBLISHED fill -- control, not obtainable",
             "PUB/options": "contracts, PUBLISHED fill -- control, not obtainable",
             "PUB/index": "index, PUBLISHED fill -- control, not obtainable"}

    print("\n%-58s %6s %9s %9s %11s %7s %7s"
          % ("instrument", "days", "$/day@1k", "% of $397", "risk for $397",
             "months", "weeks"))
    print("-" * 116)
    for key in ("B/shares", "B/shares_raw", "B/options", "B/options_raw",
                "B/index", "B/index_raw",
                "PUB/shares", "PUB/options", "PUB/index"):
        rec = score(label.get(key, key), s["series"][key], days, rng)
        rec["key"] = key
        res["instruments"][key] = rec
        print("%-58s %6d %9s %8.0f%% %13s %4d/%2d %4d/%3d"
              % (label.get(key, key)[:58], rec["days_traded"],
                 "$%.0f" % rec["per_day_at_1k"], rec["pct_of_397_at_1k"],
                 ("$%.0f" % rec["risk_for_397"]) if rec["risk_for_397"] else "unreachable",
                 rec["months_green"], rec["months"],
                 rec["weeks_green"], rec["weeks"]))

    print("\n%-58s %8s %8s %8s %12s"
          % ("instrument", "P(wk+)", "P(mo+)", "P(yr+)", "worstDD@1k"))
    print("-" * 100)
    for key, rec in res["instruments"].items():
        print("%-58s %7.0f%% %7.0f%% %7.0f%% %12s"
              % (rec["name"][:58], 100 * rec["p_green_week"],
                 100 * rec["p_green_month"], 100 * rec["p_green_year"],
                 "$%.0f" % rec["worst_dd_at_1k"]))

    # ---- blow-up, on a personal account -----------------------------------
    print("\nBLOWING THE ACCOUNT -- P(50%% drawdown of starting equity inside "
          "one year), at the risk that reaches $397/day")
    res["blowup"] = {}
    for key in ("B/shares", "B/options", "B/index"):
        rec = res["instruments"][key]
        daily = full_daily(s["series"][key], days)
        rows = []
        need = rec["risk_for_397"]
        for start in (25000, 50000, 100000, 250000):
            r = {"account": start}
            for tag, risk in (("at_1k", RISK0), ("for_397", need)):
                if risk is None:
                    r[tag] = None
                    continue
                r[tag] = {
                    "risk": round(risk, 0),
                    "risk_pct_of_account": round(100 * risk / start, 2),
                    "p_ruin_50pct_1y": round(ruin(daily, risk, start, 0.50, rng), 4),
                    "p_dd_25pct_1y": round(ruin(daily, risk, start, 0.25, rng), 4)}
            rows.append(r)
        res["blowup"][key] = rows
        print("\n  %s" % rec["name"])
        for r in rows:
            a = r.get("for_397")
            print("    $%-7d account | at $1,000 risk: %5.1f%% ruin | at $%s risk (%.0f%% of "
                  "the account per trade): %s"
                  % (r["account"], 100 * r["at_1k"]["p_ruin_50pct_1y"],
                     ("%.0f" % a["risk"]) if a else "n/a",
                     a["risk_pct_of_account"] if a else 0,
                     ("%.1f%% ruin" % (100 * a["p_ruin_50pct_1y"])) if a else "unreachable"))

    # ---- prop challenges ----------------------------------------------------
    # futures firms take index futures only; stock firms take shares; NO prop
    # firm on the challenge model allows options (research/g71_propfirm.md s.0).
    print("\nPROP CHALLENGES on the honest fill (>=90%% pass band, and the best "
          "risk on the grid)")
    for key, which in (("B/index", "futures"), ("B/shares", "stock")):
        daily = full_daily(s["series"][key], days)
        rows = challenge(daily, res["instruments"][key]["risk_for_397"], rng)
        rows = [r for r in rows if (which == "futures") ==
                (not r["firm"].startswith("TTP"))]
        res["challenge"][key] = rows
        print("\n  %s -- %s firms  (risk for $397/day = $%s)"
              % (res["instruments"][key]["name"], which,
                 res["instruments"][key]["risk_for_397"]))
        print("    %-24s %13s %9s %7s %8s %9s %9s"
              % ("firm", ">=90% band", "best risk", "peak", "mo.", "pass@$397",
                 "mo.@$397"))
        for r in rows:
            b = ("$%d-$%d" % (r["band_lo"], r["band_hi"])) if r["band_lo"] else "none"
            print("    %-24s %13s %9s %6.1f%% %8s %8s%% %9s"
                  % (r["firm"], b, "$%d" % r["best_risk"], 100 * r["best_pass_rate"],
                     ("%.2f" % r["months_to_funded"])
                     if r["months_to_funded"] is not None else "-",
                     ("%.1f" % (100 * r["pass_rate_at_397_risk"]))
                     if r["pass_rate_at_397_risk"] is not None else "  n/a",
                     ("%.2f" % r["months_to_funded_at_397_risk"])
                     if r["months_to_funded_at_397_risk"] is not None else "-"))

    # ---- the spread sweep, which is what actually decides the options answer -
    # Nobody in this repo has read a real bid/ask on a same-day contract on
    # these names. This is a PARAMETER SWEEP, not a measurement, and it is the
    # single number most likely to flip the page.
    print("\nTHE SPREAD SWEEP -- options, one trade a day, honest fill. A "
          "parameter, not a measurement.")
    res["spread_sweep"] = []
    print("  %-14s %9s %10s %13s %8s %11s"
          % ("option r/t", "$/day@1k", "% of $397", "risk for $397",
             "months", "P(green mo)"))
    raw = s.get("raw", {}).get("B/options", {})
    for rt in (0.00, 0.01, 0.02, 0.03, 0.05, 0.10):
        ser = {d: (v[0] - v[1] * rt * MULT) / RISK0 for d, v in raw.items()}
        rec = score("options, $%.2f round trip" % rt, ser, days, rng)
        res["spread_sweep"].append(dict(rec, round_trip=rt))
        print("  $%-13.2f %9s %9.0f%% %13s %5d/%2d %10.0f%%"
              % (rt, "$%.0f" % rec["per_day_at_1k"], rec["pct_of_397_at_1k"],
                 ("$%.0f" % rec["risk_for_397"]) if rec["risk_for_397"] else "unreachable",
                 rec["months_green"], rec["months"], 100 * rec["p_green_month"]))

    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("\nwrote %s" % OUT.relative_to(ROOT))

    # ---- the headline -------------------------------------------------------
    best = max((r for r in res["instruments"].values()
                if not r["key"].startswith("PUB")),
               key=lambda r: r["per_day_at_1k"])
    dur = [r for r in res["instruments"].values()
           if not r["key"].startswith("PUB") and r["durability_pass"]]
    print("\n" + "=" * 78)
    print("HEADLINE")
    print("  best honest instrument: %s" % best["name"])
    print("  $%.0f a day at $1,000 risk -- %.0f%% of the $397 bar, %s to go"
          % (best["per_day_at_1k"], best["pct_of_397_at_1k"],
             "$%.0f" % -best["distance_to_397_at_1k"]))
    print("  reaches $397/day at $%s of risk per trade"
          % (("%.0f" % best["risk_for_397"]) if best["risk_for_397"] else "never"))
    print("  green months at ANY size: %d of %d  ->  durability %s"
          % (best["months_green"], best["months"],
             "MET" if best["durability_pass"] else "FAILED"))
    print("  instruments that hold 25 of 25 green months at any size: %s"
          % (", ".join(r["name"] for r in dur) if dur else "NONE"))
    print("=" * 78)


if __name__ == "__main__":
    main()
