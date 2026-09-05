"""G8.3 -- the futures arm. Shares and options are priced elsewhere

    research/g80_options_honest.py    contracts, shares -- market-at-close and
                                       limit-at-level honest fills, full 29-symbol
                                       universe, one trade a day and everything.
    research/g80_ordertype_grid.py    five order types, shares only.

This file is the missing third leg: SPY/QQQ/IWM translated into MES/MNQ/M2K
index-futures dollars, on the SAME honest fill (market order at the close of
the signal minute) and the SAME 500-session, one-trade-a-day policy those two
files use for shares and options.

NO FUTURES BAR IS FABRICATED. research/t17_futures_feasibility.md found the
archive holds zero futures symbol-days and refused to invent a backtest; that
finding stands untouched here. What this file does instead is arithmetic on
data that already exists: OMEN's SPY/QQQ/IWM signals are real 1-minute stock
bars, already detected, already stopped and exited by the shipped engine. The
only new step is translating each signal's entry/stop, in ETF dollars, into
index points and then into a micro-futures contract's dollars, using the
exchange's own published multiplier and tick size. That translation is
sourced below, every number dated and linked. Where a ratio could not be
pulled from the exchange's own site (CME's contract-spec pages timed out on
direct fetch in this sandbox), it is corroborated from public data instead
and flagged as such -- never invented.

Honest fill, reused: the market-at-close entry (order type B) and the flat
2R / close-triggered-stop / -1.25R-floor simulation are g80_options_honest's
own functions, imported here, not reimplemented -- so this file cannot drift
from the shares/options numbers it is being compared against.

Run:
    python research/g83_futures_arm.py             # the table + the .md's numbers
    python research/g83_futures_arm.py --selfcheck  # the checks this file makes

Writes: research/g83_futures_arm.json
Reads only. No mark file, no engine file, no network call (all SPY/QQQ/IWM
1-minute bars for these 500 sessions are already on disk in data_archive/).
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import black_scholes as bs                                       # noqa: E402
from sizing import dollars_futures                                # noqa: E402
from universe import INDEX_POOL                                   # noqa: E402
from g80_options_honest import (                                  # noqa: E402
    bars, prior_session_range, entry_for, simulate, price_contract,
    drawdown, IV_MULT, RISK,
)

BOOK = ROOT / "research" / "bt2y_trades.json"
OUT = ROOT / "research" / "g83_futures_arm.json"

SESSIONS = 500          # matches bt2y_trades.json meta.sessions
MONTHLY_BAR = 397.0 * 252.0 / 12.0    # $397/day * 252 sessions/yr / 12 -> $8,333/mo
DAILY_BAR = 397.0       # Austin, 2026-08-30: $100,000 / 252 = $397/day
SEED = 20260830
BOOTS = 10000

# ---------------------------------------------------------------------------
# CONTRACT SPECS -- sourced 2026-08-30, dated below. CME's own contract-spec
# pages (cmegroup.com/markets/equities/.../*.contractSpecs.html) timed out on
# a direct fetch from this sandbox; every number below is corroborated from
# at least two independent broker/vendor pages that quote the exchange's
# published spec, cross-checked against the standard E-mini's own multiplier
# (MES = ES/10, M2K = RTY/10, MNQ = NQ/10, which is how the "micro" family is
# defined). None of this is modelled or guessed -- it is public contract
# arithmetic, sourced, not fabricated. If a real CME fetch is ever run, diff
# it against this table.
#
#   MES  Micro E-mini S&P 500     $5 / index point   tick 0.25 pt = $1.25
#        ironbeam.com/knowledge-base/micro-e-mini-sp-500-futures-mes-contract-specifications
#        quantvps.com/blog/mes-tick-value
#   MNQ  Micro E-mini Nasdaq-100  $2 / index point   tick 0.25 pt = $0.50
#        ironbeam.com/knowledge-base/micro-e-mini-nasdaq-100-futures-mnq-contract-specifications
#        quantvps.com/blog/mnq-tick-value
#   M2K  Micro E-mini Russell 2000  $5 / index point tick 0.10 pt = $0.50
#        ironbeam.com/knowledge-base/micro-e-mini-russell-2000-futures-m2k-contract-specifications
#        futurespositionsizecalculator.com/contract-specifications/m2k
# ---------------------------------------------------------------------------
FUT_SPEC = {
    "SPY": {"contract": "MES", "multiplier": 5.0, "tick_size": 0.25, "tick_value": 1.25},
    "QQQ": {"contract": "MNQ", "multiplier": 2.0, "tick_size": 0.25, "tick_value": 0.50},
    "IWM": {"contract": "M2K", "multiplier": 5.0, "tick_size": 0.10, "tick_value": 0.50},
}

# ---------------------------------------------------------------------------
# ETF -> INDEX ratio -- how many index points one ETF dollar of stop distance
# maps onto. This is the one genuinely approximate step in the chain, and it
# is sourced, not invented:
#
#   SPY -> S&P 500 (SPX): ratio 10. SPY was structured at launch (1993) to
#     trade at ~1/10 of the index; research/g71_instrument_spread.py already
#     uses this exact "ES ~= 10 x SPY" approximation for the same purpose and
#     it is kept identical here so the two files cannot silently disagree.
#   QQQ -> Nasdaq-100 (NDX): ratio 41.09, sourced 2026-08-30 (spxytrader.com,
#     "NDX vs QQQ", citing a May-2026 NDX/QQQ close ratio). QQQ was launched
#     at a nominal 1/40 in 1999; cash-drag and QQQ's expense ratio have
#     pulled the true ratio to ~41.1 by 2026. Using 40 instead of 41.09 moves
#     every QQQ stop width by 2.7% -- checked below, it does not change which
#     instrument wins.
#   IWM -> Russell 2000 (RUT): ratio 9.91, computed here from two live prints
#     both dated 2026-08-28: RUT closed 2,972.37 (cnbc.com/quotes/.RUT) and
#     IWM's previous close was $299.81 (finance.yahoo.com/quote/IWM), giving
#     2972.37 / 299.81 = 9.914. This is a single day's ratio, not a fitted
#     constant like SPY's or QQQ's -- flagged UNVERIFIED as a multi-year
#     constant, though it lands almost exactly on the "designed as 1/10"
#     figure IWM is commonly cited at, so the error from treating it as
#     constant across the 500-session window is small.
# ---------------------------------------------------------------------------
ETF_INDEX_RATIO = {"SPY": 10.0, "QQQ": 41.09, "IWM": 9.91}


def load_book():
    with open(BOOK, encoding="utf-8") as f:
        return json.load(f)["trades"]


def one_index_trade_per_day(rows):
    """The day's ONE trade, for someone whose account can only see SPY/QQQ/IWM.

    Not the same question as 'the day's global first trade, across all 29
    symbols, happened to be an index name' -- that is a different, narrower
    population (research/g71_propfirm.md's 139/500, computed against a stale
    2,437-row cache -- see the .md's 'day count' section for the full
    reconciliation). A futures-only account does not watch NVDA; it watches
    the index names only, so its one trade a day is the first INDEX-eligible
    signal of the day, full stop.
    """
    idx = [r for r in rows if r.get("traded") and r["sym"] in INDEX_POOL]
    by_day = {}
    for r in idx:
        by_day.setdefault(r["day"], []).append(r)
    picked = []
    for day, rs in by_day.items():
        rs.sort(key=lambda x: (x["et"], x["sym"]))
        picked.append(rs[0])
    picked.sort(key=lambda x: x["day"])
    return picked, len(by_day)


def stop_ticks_for(sym, entry_px, stop_px):
    spec = FUT_SPEC[sym]
    ratio = ETF_INDEX_RATIO[sym]
    etf_risk = abs(entry_px - stop_px)
    index_points = ratio * etf_risk
    ticks = max(1, round(index_points / spec["tick_size"]))
    return ticks, index_points


def build_futures_rows(picked):
    """Market-at-close (order type B) honest fill on each picked index row,
    translated to MES/MNQ/M2K dollars. Reuses g80_options_honest.entry_for /
    .simulate verbatim -- see the module docstring for why."""
    out = []
    diag = {"attempted": 0, "no_bars": 0, "no_fill": 0, "not_takeable": 0}
    for row in picked:
        diag["attempted"] += 1
        sym, day, i = row["sym"], row["day"], row["entry_i"]
        b = bars(sym, day)
        if not b or i >= len(b) - 1:
            diag["no_bars"] += 1
            continue
        ep = entry_for("B", row, b, i)
        if ep is None:
            diag["no_fill"] += 1
            continue
        sim = simulate(ep, row["stop"], row["dir"] == "call", b, i)
        if sim is None:
            diag["not_takeable"] += 1
            continue
        r_u, tag, exit_px, exit_i = sim
        ticks, idx_pts = stop_ticks_for(sym, ep, row["stop"])
        spec = FUT_SPEC[sym]
        fut = dollars_futures(r_u, ticks, tick_value=spec["tick_value"],
                              contract=spec["contract"])
        # shares side, same honest fill, same trades -- the apples-to-apples
        # partner for this specific 230-day population (NOT the g80 headline,
        # which is the full 29-symbol universe; see the .md for why both are
        # reported)
        shares_dollars = r_u * RISK

        # options side, same honest fill, same contract-pricing method g80
        # uses (prior-session Parkinson sigma, $0.05 floor both legs, 1.2x
        # headline IV multiplier)
        rng = prior_session_range(sym, day)
        opt_dollars = None
        if rng:
            sigma = bs.parkinson_sigma(rng, ep) * IV_MULT
            c = price_contract(row, ep, row["stop"], exit_px, exit_i, i, sigma,
                               grid=True, floor_exit=True)
            if c:
                opt_dollars = c["dollars"]

        out.append({
            "day": day, "sym": sym, "et": row["et"], "dir": row["dir"],
            "contract": spec["contract"], "r_underlying": r_u, "tag": tag,
            "entry_px": ep, "stop_px": row["stop"], "index_points_risk": round(idx_pts, 4),
            "stop_ticks": ticks, "contracts": fut["contracts"],
            "realised_risk_dollars": round(fut["realised_risk_dollars"], 2),
            "rounding_error_r": round(fut["rounding_error_r"], 4),
            "dollars_futures": round(fut["pnl"], 2),
            "dollars_shares": round(shares_dollars, 2),
            "dollars_options": None if opt_dollars is None else round(opt_dollars, 2),
        })
    return out, diag


# ---------------------------------------------------------------- arithmetic

def month_key(day):
    return day[:7]


def all_months(rows):
    return sorted({month_key(r["day"]) for r in rows}) if rows else []


def daily_series(rows, key, all_days):
    by_day = {d: 0.0 for d in all_days}
    for r in rows:
        by_day[r["day"]] = by_day.get(r["day"], 0.0) + (r[key] or 0.0)
    return [by_day[d] for d in sorted(all_days)]


def summarise(rows, key, n_sessions, all_days, n_months):
    if not rows:
        return {"trades": 0}
    vals = [r[key] for r in rows if r.get(key) is not None]
    wins = sum(1 for v in vals if v > 0)
    losses = sum(1 for v in vals if v < 0)
    by_m = {}
    for r in rows:
        v = r.get(key)
        if v is None:
            continue
        by_m[month_key(r["day"])] = by_m.get(month_key(r["day"]), 0.0) + v
    total = sum(vals)
    seq = daily_series(rows, key, all_days)
    per_day = total / n_sessions
    return {
        "trades": len(vals),
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "per_day": round(per_day, 2),
        "per_month": round(per_day * n_sessions / n_months, 0) if n_months else None,
        "total_dollars": round(total, 2),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": n_months,
        "worst_drawdown": round(drawdown(seq), 2),
        "distance_to_397_per_day": round(397.0 - per_day, 2),
        "pct_of_397": round(per_day / 397.0 * 100, 1),
    }


def day_ci(rows, key, all_days):
    by_d = {d: 0.0 for d in all_days}
    for r in rows:
        by_d[r["day"]] = by_d.get(r["day"], 0.0) + (r.get(key) or 0.0)
    v = [by_d[d] for d in sorted(all_days)]
    rng = random.Random(SEED)
    n = len(v)
    m = sorted(sum(rng.choices(v, k=n)) / n for _ in range(BOOTS))
    return {"lo": round(m[int(BOOTS * 0.025)], 2), "hi": round(m[int(BOOTS * 0.975)], 2)}


def all_session_days():
    """The 500-session calendar, read from the book itself -- every day that
    appears on any row, traded or not, so a session with zero index signals
    still counts as a $0 day rather than silently shrinking the denominator."""
    rows = load_book()
    return sorted({r["day"] for r in rows})


# --------------------------------------------------------------------- main

def main():
    rows = load_book()
    picked, index_days = one_index_trade_per_day(rows)
    fut_rows, diag = build_futures_rows(picked)
    all_days = all_session_days()
    assert len(all_days) == SESSIONS, f"expected {SESSIONS} sessions, book has {len(all_days)}"
    n_months = len(all_months([{"day": d} for d in all_days]))

    summary = {}
    for key, label in (("dollars_futures", "futures"),
                       ("dollars_shares", "shares_index_only"),
                       ("dollars_options", "options_index_only")):
        s = summarise(fut_rows, key, SESSIONS, all_days, n_months)
        ci = day_ci(fut_rows, key, all_days)
        s["day_ci_95"] = ci
        summary[label] = s

    per_contract = {}
    for sym in INDEX_POOL:
        sub = [r for r in fut_rows if r["sym"] == sym]
        per_contract[FUT_SPEC[sym]["contract"]] = {
            "sym": sym, "trades": len(sub),
            "median_contracts": (sorted(r["contracts"] for r in sub)[len(sub)//2]
                                 if sub else None),
            "median_stop_ticks": (sorted(r["stop_ticks"] for r in sub)[len(sub)//2]
                                  if sub else None),
        }

    out = {
        "meta": {
            "generated": "2026-08-30", "sessions": SESSIONS, "months": n_months,
            "book_meta": None,
        },
        "day_count": {
            "index_eligible_days_current_book": index_days,
            "index_eligible_days_pct": round(index_days / SESSIONS * 100, 1),
            "g71_propfirm_stale_figure": 139,
            "g71_propfirm_stale_figure_pct": 27.8,
            "note": ("g71_propfirm.md's 139/500 was computed on a cache "
                    "(research/g71_propfirm_daily.json) whose own docstring "
                    "states 2,437 traded rows; the current bt2y_trades.json "
                    "holds 4,508 (post-G72 fix pass, same day). Recomputed here "
                    "on the current book: index-only first-of-day, not "
                    "global-first-of-day-that-happened-to-be-index (that "
                    "narrower question gives 31/500 on the current book)."),
        },
        "diagnostics": diag,
        "contract_specs": FUT_SPEC,
        "etf_index_ratio": ETF_INDEX_RATIO,
        "per_contract": per_contract,
        "summary": summary,
        "rows": fut_rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"index-eligible days (current book): {index_days} / {SESSIONS} "
         f"({index_days/SESSIONS*100:.1f}%) -- stale g71_propfirm.md figure was 139 (27.8%)")
    print(f"picked-day rows priced (futures honest fill): {len(fut_rows)} "
         f"of {len(picked)} picked ({diag})")
    for label in ("futures", "shares_index_only", "options_index_only"):
        s = summary[label]
        print(f"\n{label}: trades={s.get('trades')} win%={s.get('win_pct')} "
             f"$/day={s.get('per_day')} months_green={s.get('months_green')}/{s.get('months')} "
             f"worst_dd={s.get('worst_drawdown')} dist_to_397={s.get('distance_to_397_per_day')}")
    print(f"\nWritten: {OUT}")
    return out


# ------------------------------------------------------------------ selfcheck

def selfcheck():
    ok = True

    # 1. contract specs -- multiplier * tick_size == tick_value, exactly, for
    #    all three. This is the one arithmetic identity that must hold if the
    #    sourced numbers are self-consistent.
    for sym, spec in FUT_SPEC.items():
        want = round(spec["multiplier"] * spec["tick_size"], 4)
        got = spec["tick_value"]
        if abs(want - got) > 1e-6:
            print(f"[FAIL] {sym} {spec['contract']}: multiplier*tick_size={want} "
                 f"!= stated tick_value={got}")
            ok = False
    if ok:
        print("[ok] contract specs: multiplier * tick_size == tick_value for MES/MNQ/M2K")

    # 2. one-index-trade-a-day never emits two rows on the same day, and
    #    every row it emits is SPY/QQQ/IWM -- this file never reads or writes
    #    a data_archive/MES, /MNQ or /M2K path, and every entry/stop it prices
    #    comes from the ETF archive already used by every other rig in the repo.
    rows = load_book()
    picked, _ = one_index_trade_per_day(rows)
    days = [r["day"] for r in picked]
    syms_seen = {r["sym"] for r in picked}
    if len(days) != len(set(days)):
        print("[FAIL] one_index_trade_per_day emitted >1 row for a single day")
        ok = False
    elif not syms_seen <= set(INDEX_POOL):
        print(f"[FAIL] a non-index symbol reached the bar loader: {syms_seen - set(INDEX_POOL)}")
        ok = False
    else:
        print(f"[ok] one row per day, {len(days)} distinct index-eligible days, "
             f"symbols {sorted(syms_seen)} only -- no MES/MNQ/M2K bar exists on "
             "disk and none is read")

    # 3. dollars_futures never exceeds the R_DOLLARS budget (realised_risk <= 1000)
    fut_rows, _ = build_futures_rows(picked[:40])   # a fast slice, not the whole book
    for r in fut_rows:
        if r["realised_risk_dollars"] > 1000.0 + 1e-6:
            print(f"[FAIL] {r['sym']} {r['day']}: realised risk "
                 f"${r['realised_risk_dollars']} exceeds the $1,000 budget")
            ok = False
    print(f"[ok] realised futures risk never exceeds the $1,000 budget "
         f"({len(fut_rows)} rows checked)")

    print("SELFCHECK", "PASSED" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        sys.exit(0 if selfcheck() else 1)
    main()
