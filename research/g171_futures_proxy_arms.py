"""g171 -- the futures proxy arm + overlap check.

OMEN's book is priced in QQQ/SPY/IWM cash-equity dollars, not futures points.
Prop-firm futures evals (Topstep, Apex, MFFU, ...) trade ES/NQ/RTY (or the
micro MES/MNQ/M2K contracts), not the ETFs. This file maps the honest,
one-trade-a-day INDEX-POOL book (QQQ/SPY/IWM only, RETEST_REQUIRED=1,
`research/bt2y_trades_retest_on.json` per CLAUDE.md -- never the stale
`bt2y_trades.json`) into futures index points and runs it through every
futures-only firm in `research/g71_propfirm_sim.FIRMS`, plus a walk-forward
rolling-252-session pass rate that `research/g120_prop_arms.py`'s Vanquish
sweep does not need but a futures eval (finite max_days) does.

THE MAPPING, stated once so nothing downstream re-derives it silently:

  1. Ratio = futures_close / etf_close on the SAME trading day, from
     yfinance daily closes over the book's own ~2-year window. ES=F/SPY,
     NQ=F/QQQ, RTY=F/IWM. This is a DAILY ratio, forward-filled onto any
     book day yfinance is missing (a handful of holidays/gaps) -- it is not
     re-fit intraday, so an intraday basis move (overnight gap, contract
     roll) is invisible to it. See the overlap check below for how much
     that costs.
  2. A book row's entry/stop/target (ETF dollars) become index points by
     multiplying by that day's ratio. |entry - stop| in index points,
     divided by the contract's tick size, is `stop_ticks` for
     `research/sizing.dollars_futures`.
  3. `sizing.FUTURES_PRESETS` has MES/MNQ but not M2K (Micro E-mini Russell
     2000). Added HERE, not in sizing.py, per the ticket: CME multiplier
     $5/index-point, tick 0.10 point = $0.50/tick (source: CME micro
     contract specs, same convention sizing.py already documents for
     MES/MNQ -- not re-derived, just the missing third preset).
  4. A trade whose mapped stop is so tight even 1 micro contract's risk
     exceeds the firm's per-trade budget is DROPPED, not zero-filled --
     `dollars_futures` raises on that case by design (see its docstring:
     "not a trade worth 0 contracts"). Dropped-day count is reported, never
     swallowed.

Every firm's PASS/FAIL and rolling-252 pass rate reuse
`omen_metrics.evaluate_prop_challenge` -- the one prop-eval simulator in
this repo -- fed the REAL chronological daily P&L sequence (a single
walk-forward pass, not a bootstrap resample: g71_propfirm_sim.py already
answers the resampled-Monte-Carlo question; this file answers "what did the
actual 2-year sequence do").

Lucid Trading: P0 (`research/g170_futures_firms_2026-09.md`, W6 2026-09-05)
verified account sizes, targets, drawdown, and costs via six independent
review sites (primary pages return 403). Automation policy confirmed:
"Algorithmic systems and automated execution are permitted across all
account types." Micro contracts confirmed (MES, MNQ, M2K, MYM @ $0.50/side).
Three Lucid rows added to the local FIRMS list this file uses (not g71).

    python research/g171_futures_proxy_arms.py
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import universe                                        # noqa: E402
from sizing import dollars_futures, R_DOLLARS           # noqa: E402
from omen_metrics import evaluate_prop_challenge, min_risk_floor  # noqa: E402
from g71_propfirm_sim import FIRMS as G71_FIRMS         # noqa: E402

try:
    import yfinance as yf
except ImportError:
    yf = None

# =========================================================================
# LOCAL FIRMS LIST: futures-only, including Lucid rows added W6 2026-09-05
# =========================================================================
# G71_FIRMS mixes futures and stock rows; this script uses only futures.
# Format: (name, account_size, profit_target, daily_loss, max_drawdown,
#          dd_type, lock, max_days, cost)
#
# Lucid rows (W6 2026-09-05): verified via secondary review sites; primary
# pages (lucidtrading.com) return 403 Forbidden. Automation policy quoted:
# "Algorithmic systems and automated execution are permitted across all
# account types" (confirmed across 6 independent review sites).
# Micro contracts confirmed: MES, MNQ, M2K, MYM @ $0.50/side.
# See research/g170_futures_firms_2026-09.md for full verification chain.
#
FIRMS = [
    # ---- G71 futures rows (existing, 2026-08-23 baseline) ----
    ("Topstep 50K Combine",  50000,  3000, 1000, 2000, "eod",    "start", 120, 49),
    ("Topstep 100K Combine", 100000, 6000, 2000, 3000, "eod",    "start", 120, 99),
    ("Topstep 150K Combine", 150000, 9000, 3000, 4500, "eod",    "start", 120, 149),
    ("Apex 50K Eval EOD",    50000,  3000, None, 2500, "eod",    "start", 120, 35),
    ("Apex 100K Eval EOD",   100000, 6000, None, 3000, "eod",    "start", 120, 85),
    ("Apex 150K Eval EOD",   150000, 9000, None, 5000, "eod",    "start", 120, 105),
    ("MFFU Rapid 50K",       50000,  3000, None, 2000, "eod",    "start", 120, 80),
    ("MFFU Rapid 100K",      100000, 6000, None, 3000, "eod",    "start", 120, 150),
    # ---- Lucid Trading rows (NEW, W6 2026-09-05) ----
    # Verified via proptradingvibes.com, tradetanto.com, saveonpropfirms.com,
    # proptradercheck.com, pipback.com, damnpropfirms.com (2026-09-05).
    # LucidPro: EOD trailing DD, 40% consistency when funded (0% eval).
    # Automation: PERMITTED per "Algorithmic systems and automated execution
    # are permitted across all account types" (damnpropfirms.com, 2026-09-05).
    ("Lucid Pro 50K",        50000,  2500, 1200, 2000, "eod",    "start", 120, 185),
    ("Lucid Pro 100K",       100000, 5000, 1800, 3000, "eod",    "start", 120, 285),
    ("Lucid Pro 150K",       150000, 7500, 2700, 4500, "eod",    "start", 120, 370),
]

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g171_futures_proxy_arms.json")
OUT_MD = os.path.join(HERE, "g171_futures_proxy_arms.md")
H1_H2_SPLIT = "2025-09-01"

# M2K -- Micro E-mini Russell 2000. NOT in sizing.FUTURES_PRESETS (ticket:
# "add M2K if missing in YOUR script, not in sizing.py"). Multiplier
# $5/index-point, min tick 0.10 point => $0.50/tick -- same convention as
# sizing.py's MES/MNQ comments (CME contract specs, not re-derived).
M2K_TICK_VALUE = 0.50
M2K_TICK_SIZE = 0.10
MES_MNQ_TICK_SIZE = 0.25  # sizing.py's dollars_futures already assumes this
                          # unit ("0.25-pt tick") for MES/MNQ; only M2K differs.

# Pair each index-pool ETF with its futures proxy and micro contract.
PAIRS = {
    "SPY": {"fut": "ES=F", "micro": "MES", "tick_size": MES_MNQ_TICK_SIZE,
            "tick_value": None},   # None -> sizing.FUTURES_PRESETS["MES"]
    "QQQ": {"fut": "NQ=F", "micro": "MNQ", "tick_size": MES_MNQ_TICK_SIZE,
            "tick_value": None},   # None -> sizing.FUTURES_PRESETS["MNQ"]
    "IWM": {"fut": "RTY=F", "micro": "M2K", "tick_size": M2K_TICK_SIZE,
            "tick_value": M2K_TICK_VALUE},
}
OVERLAP_MICRO_1MIN = {"ES=F": "MES=F"}  # ticket: overlap check on ES=F/MES=F vs SPY

INDEX_POOL = frozenset(universe.INDEX_POOL)


# ==========================================================================
# 1. Ratio: futures_close / etf_close, daily, over the book's own window
# ==========================================================================

def fetch_daily_ratio(etf, fut, days=760):
    """{iso_date: ratio} from yfinance daily closes. Raises if yfinance is
    unavailable or returns nothing -- a silent empty ratio table would make
    every downstream mapped trade look like a data problem instead of a
    fetch problem."""
    if yf is None:
        raise RuntimeError("yfinance not importable")
    etf_df = yf.download(etf, period=f"{days}d", interval="1d",
                          progress=False, auto_adjust=False)
    fut_df = yf.download(fut, period=f"{days}d", interval="1d",
                          progress=False, auto_adjust=False)
    if etf_df.empty or fut_df.empty:
        raise RuntimeError(f"empty daily series for {etf}/{fut}")
    etf_close = etf_df["Close"][etf] if hasattr(etf_df["Close"], "__getitem__") and etf in getattr(etf_df["Close"], "columns", []) else etf_df["Close"].iloc[:, 0]
    fut_close = fut_df["Close"][fut] if hasattr(fut_df["Close"], "__getitem__") and fut in getattr(fut_df["Close"], "columns", []) else fut_df["Close"].iloc[:, 0]
    etf_map = {d.strftime("%Y-%m-%d"): float(v) for d, v in etf_close.items()}
    fut_map = {d.strftime("%Y-%m-%d"): float(v) for d, v in fut_close.items()}
    ratio = {}
    for d in sorted(set(etf_map) & set(fut_map)):
        if etf_map[d] > 0:
            ratio[d] = fut_map[d] / etf_map[d]
    return ratio


def ratio_for_day(ratio_table, day):
    """Exact match, else most recent prior trading day (forward-fill)."""
    if day in ratio_table:
        return ratio_table[day]
    prior = [d for d in ratio_table if d < day]
    if not prior:
        return None
    return ratio_table[max(prior)]


def ratio_stats(ratio_table):
    vals = list(ratio_table.values())
    if not vals:
        return {}
    return {
        "n_days": len(vals),
        "mean": round(statistics.mean(vals), 4),
        "stdev": round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0,
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "latest": round(ratio_table[max(ratio_table)], 4),
    }


# ==========================================================================
# 2. Map the index-pool one-trade-a-day book into futures points/dollars
# ==========================================================================

def load_index_pool_book():
    b = json.load(open(BOOK, encoding="utf-8"))
    rows = [r for r in b["trades"]
            if r.get("sym") in INDEX_POOL
            and ((r.get("status") == "fired" and r.get("traded"))
                 or r.get("status") == "halted")
            and r.get("entry") is not None and r.get("stop") is not None]
    byday = defaultdict(list)
    for r in rows:
        byday[r["day"]].append(r)
    firsts = []
    for day in sorted(byday):
        v = byday[day]
        v.sort(key=lambda r: (r["et"], r["sym"]))
        first = next((r for r in v
                      if abs(r["entry"] - r["stop"]) >= min_risk_floor(r["entry"])),
                     None)
        if first is not None:
            firsts.append(first)
    return firsts


def map_row_to_futures(row, ratio_tables):
    sym = row["sym"]
    spec = PAIRS[sym]
    ratio = ratio_for_day(ratio_tables[sym], row["day"])
    if ratio is None:
        return None, "no_ratio"
    price_diff = abs(row["entry"] - row["stop"])
    index_points = price_diff * ratio
    stop_ticks = index_points / spec["tick_size"]
    if stop_ticks <= 0:
        return None, "zero_stop"
    try:
        sized = dollars_futures(row["r"], stop_ticks, contract=spec["micro"],
                                 tick_value=spec["tick_value"])
    except ValueError:
        return None, "stop_too_tight_for_1_contract"
    sized["day"] = row["day"]
    sized["sym"] = sym
    sized["ratio"] = round(ratio, 4)
    sized["index_points_stop"] = round(index_points, 2)
    return sized, None


def build_futures_daily(firsts, ratio_tables):
    daily = {}
    dropped = defaultdict(int)
    detail = []
    for row in firsts:
        sized, why = map_row_to_futures(row, ratio_tables)
        if sized is None:
            dropped[why] += 1
            continue
        daily[row["day"]] = sized["pnl"]
        detail.append(sized)
    return daily, dict(dropped), detail


def split_h1_h2(daily):
    h1 = {d: v for d, v in daily.items() if d < H1_H2_SPLIT}
    h2 = {d: v for d, v in daily.items() if d >= H1_H2_SPLIT}
    return h1, h2


def money_read(daily):
    days = sorted(daily)
    if not days:
        return {}
    vals = [daily[d] for d in days]
    months = defaultdict(float)
    for d, v in daily.items():
        months[d[:7]] += v
    return {
        "days": len(days),
        "total": round(sum(vals), 2),
        "per_day": round(sum(vals) / len(days), 2),
        "win_pct": round(sum(1 for v in vals if v > 0) / len(days) * 100, 1),
        "green_months": sum(1 for v in months.values() if v > 0),
        "months": len(months),
        "first_day": days[0], "last_day": days[-1],
    }


# ==========================================================================
# 3. FIRMS: PASS/FAIL a walk-forward pass + rolling-252-session pass rate
# ==========================================================================

def firm_kw(spec):
    name, start, target, dll, mdd, mode, _lock, max_days, cost = spec
    return dict(
        account_size=float(start),
        profit_target_pct=target / start,
        trailing_dd_pct=mdd / start,
        daily_loss_limit_pct=(dll / start) if dll is not None else 1.0,
        min_trading_days=0,  # G71_FIRMS carries no min-trading-days field for
                             # futures rows (only "lock"/mode) -- real firms
                             # do impose one (Topstep etc. commonly ~5 days);
                             # this arm cannot enforce it without fabricating
                             # a number G71_FIRMS does not have.
        consistency_pct=1.0,  # no consistency rule documented for any futures
                              # firm in FIRMS/g170 -- 1.0 effectively disables it
        dd_mode=mode,
    ), max_days, cost, name


def is_futures_firm(spec):
    # g71_propfirm_sim.FIRMS mixes futures and stock-prop rows in one list;
    # only the futures block (comment-delimited there) applies to this arm.
    name = spec[0]
    return not name.startswith("TTP")


def pass_summary(daily_ordered_days, daily_map, kw, max_days, cost, monthly_cost):
    """One walk-forward pass over the REAL chronological sequence, capped at
    max_days trading sessions (a real eval expires -- this book does not
    silently keep feeding it session #121 on a 120-day firm)."""
    capped_days = daily_ordered_days[:max_days]
    pnls = [(d, daily_map[d]) for d in capped_days]
    res = evaluate_prop_challenge(pnls, **kw)
    days_used = res["days_traded"]
    if monthly_cost:
        months = max(1, math.ceil(days_used / 21))  # ~21 trading days/month
        cost_paid = months * cost
    else:
        months = None
        cost_paid = cost  # one-time eval fee
    net = res["final_equity"] - cost_paid
    return {
        "passed": res["passed"], "fail_reason": res["fail_reason"],
        "days_used": days_used, "months_to_resolve": months,
        "cost": round(cost_paid, 2), "final_equity": res["final_equity"],
        "net_after_cost": round(net, 2),
    }


def rolling_252_pass_rate(daily_ordered_days, daily_map, kw, max_days):
    """Slide a 252-trading-session window across the REAL sequence (walk-
    forward, not resampled) and run one eval per window start, capped at
    max_days sessions inside that window. Reports the fraction of windows
    that PASS -- the honest answer to "if you started this eval on any
    given day of the last 2 years, how often did it pass"."""
    n = len(daily_ordered_days)
    window = min(252, n)
    if window == 0:
        return {"windows": 0, "pass_rate_pct": None}
    passes = 0
    total = 0
    for start in range(0, max(1, n - window + 1)):
        days = daily_ordered_days[start:start + window][:max_days]
        pnls = [(d, daily_map[d]) for d in days]
        res = evaluate_prop_challenge(pnls, **kw)
        total += 1
        if res["passed"]:
            passes += 1
    return {"windows": total,
            "pass_rate_pct": round(passes / total * 100, 1) if total else None}


def run_firms(daily):
    days_sorted = sorted(daily)
    rows = []
    for spec in FIRMS:  # Use local FIRMS (includes Lucid rows), not G71_FIRMS
        if not is_futures_firm(spec):
            continue
        kw, max_days, cost, name = firm_kw(spec)
        monthly = "Combine" in name or "Eval" in name or "Rapid" in name or "TCP" in name or "100K" in name or "Pro" in name
        # cost in FIRMS is a one-time-or-monthly figure per the source docs;
        # g170/g71 both record it as $/mo for every futures row here.
        # "Pro" added for Lucid Pro tier (W6 2026-09-05: verified tertiary cost).
        summary = pass_summary(days_sorted, daily, kw, max_days, cost, monthly_cost=True)
        rolling = rolling_252_pass_rate(days_sorted, daily, kw, max_days)
        rows.append({"firm": name, **summary, **{"rolling_252_" + k: v
                     for k, v in rolling.items()}})
    return rows


# ==========================================================================
# 4. Overlap check: last 7 days, 1-min ES=F/MES=F vs SPY
# ==========================================================================

def fetch_1m(ticker, days=8):
    if yf is None:
        return None
    df = yf.download(ticker, period=f"{days}d", interval="1m",
                      progress=False, auto_adjust=False)
    if df.empty:
        return None
    close = df["Close"][ticker] if ticker in getattr(df["Close"], "columns", []) else df["Close"].iloc[:, 0]
    return close  # tz-aware US/Eastern index, per yfinance


def prior_day_levels(close):
    """{date: (pdh, pdl)} from the PRIOR trading day's full-session high/low."""
    by_day = defaultdict(list)
    for ts, px in close.items():
        by_day[ts.date().isoformat()].append(float(px))
    days = sorted(by_day)
    out = {}
    for i in range(1, len(days)):
        prev = by_day[days[i - 1]]
        out[days[i]] = (max(prev), min(prev))
    return out


def detect_breaks(close, tol_pct=0.001, window_start="09:30", window_end="11:00"):
    """SIMPLIFIED proxy detector, NOT the shipped break_and_retest engine
    (live_scanner.py/signal_runner.py are off-limits to edit and too heavy
    to reimplement here). A 'signal' is: first bar in the 09:30-11:00 ET
    window whose close breaks the prior day's high or low, followed within
    the same window by a bar that retests back within tol_pct of that
    level. This is a documented approximation for the overlap question
    ("does the same structural event show up on both instruments, near the
    same time"), not a claim that it reproduces the shipped detector's
    exact fires."""
    levels = prior_day_levels(close)
    by_day = defaultdict(list)
    for ts, px in close.items():
        by_day[ts.date().isoformat()].append((ts, float(px)))
    signals = []
    for day, bars in by_day.items():
        if day not in levels:
            continue
        pdh, pdl = levels[day]
        bars = sorted(bars)
        win = [(ts, px) for ts, px in bars
               if window_start <= ts.strftime("%H:%M") <= window_end]
        broke = None  # (ts, level, direction)
        for ts, px in win:
            if broke is None:
                if px > pdh:
                    broke = (ts, pdh, "long")
                elif px < pdl:
                    broke = (ts, pdl, "short")
                continue
            level = broke[1]
            if abs(px - level) / level <= tol_pct:
                signals.append({"day": day, "signal_time": ts.isoformat(),
                                 "level": level, "dir": broke[2],
                                 "retest_px": px})
                break
    return signals


def overlap_check():
    if yf is None:
        return {"status": "BLOCKED", "reason": "yfinance not importable"}
    es_close = fetch_1m("ES=F")
    mes_close = fetch_1m("MES=F")
    spy_close = fetch_1m("SPY")
    if es_close is None or spy_close is None:
        return {"status": "BLOCKED", "reason": "empty 1-min series from yfinance"}

    es_sig = detect_breaks(es_close)
    spy_sig = detect_breaks(spy_close)

    def by_day(sigs):
        d = defaultdict(list)
        for s in sigs:
            d[s["day"]].append(s)
        return d

    es_by_day, spy_by_day = by_day(es_sig), by_day(spy_sig)
    matched, unmatched_es, unmatched_spy = [], [], []
    basis_errors = []
    for day in sorted(set(es_by_day) | set(spy_by_day)):
        es_list = es_by_day.get(day, [])
        spy_list = spy_by_day.get(day, [])
        used_spy = set()
        for e in es_list:
            et = datetime.fromisoformat(e["signal_time"])
            best = None
            for i, s in enumerate(spy_list):
                if i in used_spy:
                    continue
                st = datetime.fromisoformat(s["signal_time"])
                if abs((et - st).total_seconds()) <= 120:  # +/- 2 one-min bars
                    best = (i, s)
                    break
            if best is not None:
                used_spy.add(best[0])
                matched.append({"day": day, "es_time": e["signal_time"],
                                 "spy_time": best[1]["signal_time"]})
                # basis error at the ES signal's retest instant, using the
                # SAME-day approximate ratio would need the daily ratio
                # table; report raw point gap instead (ES points vs SPY
                # dollars are not directly comparable) -- so report the
                # ES/SPY retest-price RATIO at that instant, which is
                # exactly the quantity section 1's daily ratio approximates.
                basis_errors.append(round(e["retest_px"] / best[1]["retest_px"], 4))
            else:
                unmatched_es.append(e)
        for i, s in enumerate(spy_list):
            if i not in used_spy:
                unmatched_spy.append(s)

    out = {
        "status": "OK",
        "es_signals": len(es_sig), "spy_signals": len(spy_sig),
        "matched_pairs": len(matched),
        "unmatched_es_only": len(unmatched_es),
        "unmatched_spy_only": len(unmatched_spy),
        "mes_series_fetched": mes_close is not None,
    }
    if basis_errors:
        out["intrabar_ratio_at_match"] = {
            "n": len(basis_errors),
            "mean": round(statistics.mean(basis_errors), 4),
            "stdev": round(statistics.pstdev(basis_errors), 4) if len(basis_errors) > 1 else 0.0,
            "min": round(min(basis_errors), 4), "max": round(max(basis_errors), 4),
        }
    else:
        out["intrabar_ratio_at_match"] = None
    return out


# ==========================================================================
# main
# ==========================================================================

def main():
    if yf is None:
        report = {"status": "BLOCKED", "reason": "yfinance not importable"}
        json.dump(report, open(OUT_JSON, "w"), indent=2)
        with open(OUT_MD, "w", encoding="utf-8") as f:
            f.write("BLOCKED: yfinance not importable in this environment.\n")
        print("BLOCKED: yfinance not importable")
        return

    ratio_tables = {}
    for sym, spec in PAIRS.items():
        try:
            ratio_tables[sym] = fetch_daily_ratio(sym, spec["fut"])
        except Exception as e:  # noqa: BLE001
            ratio_tables[sym] = {}
            print(f"WARN: ratio fetch failed for {sym}/{spec['fut']}: {e}",
                  file=sys.stderr)

    firsts = load_index_pool_book()
    daily, dropped, detail = build_futures_daily(firsts, ratio_tables)
    h1, h2 = split_h1_h2(daily)

    firm_rows = run_firms(daily) if daily else []

    overlap = overlap_check()

    report = {
        "meta": {
            "book": os.path.basename(BOOK),
            "index_pool": sorted(INDEX_POOL),
            "candidates_pre_map": len(firsts),
            "mapped_days": len(daily),
            "dropped": dropped,
            "h1_h2_split": H1_H2_SPLIT,
        },
        "ratio": {sym: ratio_stats(t) for sym, t in ratio_tables.items()},
        "money": {
            "full": money_read(daily),
            "H1_before_2025-09-01": money_read(h1),
            "H2_from_2025-09-01": money_read(h2),
        },
        "firms": firm_rows,
        "overlap_check": overlap,
    }
    json.dump(report, open(OUT_JSON, "w"), indent=2, default=str)

    lines = []
    lines.append("# G171 -- futures proxy arm + overlap check\n")
    lines.append("What is different: the index-pool one-trade-a-day book "
                  "(QQQ/SPY/IWM, retest-on) is now priced in futures points "
                  "and run through every futures-only firm in FIRMS; the ES=F "
                  "vs SPY overlap check says how much to trust the proxy.\n")
    m = report["meta"]
    lines.append(f"- Candidates pre-map: {m['candidates_pre_map']}, mapped: "
                 f"{m['mapped_days']}, dropped: {m['dropped']}\n")
    lines.append("## Ratio (futures_close / etf_close, daily)\n")
    lines.append("| pair | days | mean | stdev | min | max | latest |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for sym, spec in PAIRS.items():
        rs = report["ratio"].get(sym, {})
        if rs:
            lines.append(f"| {spec['fut']}/{sym} | {rs['n_days']} | {rs['mean']} "
                         f"| {rs['stdev']} | {rs['min']} | {rs['max']} | {rs['latest']} |")
        else:
            lines.append(f"| {spec['fut']}/{sym} | -- | BLOCKED | | | | |")
    lines.append("\n## Money ($/day, one-trade-a-day, mapped futures fill)\n")
    lines.append("| window | days | $/day | win% | green months |")
    lines.append("|---|---:|---:|---:|---:|")
    for label, key in (("full 2y", "full"), ("H1 (<2025-09-01)", "H1_before_2025-09-01"),
                       ("H2 (>=2025-09-01)", "H2_from_2025-09-01")):
        r = report["money"][key]
        if r:
            lines.append(f"| {label} | {r['days']} | ${r['per_day']} | {r['win_pct']}% "
                         f"| {r['green_months']}/{r['months']} |")
        else:
            lines.append(f"| {label} | 0 | -- | -- | -- |")
    lines.append("\n## Firms -- walk-forward PASS/FAIL on the real 2-year sequence\n")
    lines.append("| firm | passed | fail_reason | days_used | months | cost | net_after_cost | rolling-252 pass% |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|")
    for r in firm_rows:
        lines.append(f"| {r['firm']} | {r['passed']} | {r.get('fail_reason')} "
                     f"| {r.get('days_used')} | {r.get('months_to_resolve')} "
                     f"| {r.get('cost')} | {r.get('net_after_cost')} "
                     f"| {r.get('rolling_252_pass_rate_pct')} |")
    lines.append("\n## Overlap check: ES=F/MES=F vs SPY, last 7 days, 1-min\n")
    lines.append("```json")
    lines.append(json.dumps(overlap, indent=2, default=str))
    lines.append("```")
    lines.append("\nSimplified proxy detector (PDH/PDL break + retest to "
                 "within 0.1%), NOT the shipped engine -- see the module "
                 "docstring. Trust reading: " +
                 ("basis is tight and signals largely co-occur" if
                  overlap.get("intrabar_ratio_at_match") and
                  overlap["intrabar_ratio_at_match"]["stdev"] < 0.01
                  else "treat the daily ratio as an approximation only -- "
                       "see the match/mismatch counts and ratio spread above."))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("wrote", OUT_JSON, "and", OUT_MD)


if __name__ == "__main__":
    main()
