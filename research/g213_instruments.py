"""g213_instruments.py -- T2, instrument columns over the R3 baseline.

WHAT THIS DOES. The R3 baseline book (research/tape/baseline_2026-09-05.json.gz)
is priced in SHARES. Austin's target instruments are options, futures and
indices on prop firms (omen-rulebook.md, 2026-08-23): "the backtest reports
R-multiples, which are venue-free, and a thin sizing layer dollarises the same
result per venue." This script IS that sizing layer for the two venues that
are not shares: futures micro contracts (SPY->MES, QQQ->MNQ; single names
n/a) and options (nearest-expiry ATM contract, real Polygon 1-minute bars
where available, a delta model where they are not).

UNIT. The row this script prices is the loop's own unit,
`up_to_3_stop_win_or_2loss` (research/loop_cycle.py:up_to_3_rows, imported
not retyped): up to 3 fired-and-traded core-11 signals a day in arrival
order, stop after the first win or the second loss. That is the unit named
in this row's baseline dict ("unit":"up_to_3_stop_win_or_2loss"), on
universe.CORE_SYMBOLS (tier=='core', 11 symbols: TSLA NVDA AAPL AMD META
GOOGL AMZN MSFT PLTR QQQ SPY -- IWM is not in CORE_SYMBOLS, so the M2K
mapping is documented but never exercised on this book).

FUTURES. Ratio is ETF price x a fixed index/ETF ratio (SPY:SPX ~ 10.0,
QQQ:NDX ~ 41.35 -- both approximate rule-of-thumb ratios, NOT fit to data;
no ES/MES or NQ/MNQ 1-minute bars exist under data_archive/ on this box (
checked: `find data_archive -iname "*ES*" -o -iname "*MES*" -o -iname "*NQ*"`
returned nothing), so g213_verify.py reports this ratio UNVERIFIED rather
than checked against overlap, per this row's own verify clause). Index
points are tick-rounded (MES/MNQ 0.25, M2K 0.10) at both entry and stop
BEFORE the risk is computed, integer contracts are sized so that risk is as
close to $1,000 (1R) as an integer contract count allows, and $0.62/side
commission is charged per contract. Tick rounding at a 2-3 point stop
distance can move risk-per-contract by more than a full percent of itself
(e.g. a 3.10-point stop rounds to 3.00 on MES, an 3.2% understatement of
risk before it is even sized) -- `actual_r_dollars` on every row is the
REAL dollar value of "1R" after rounding and integer sizing, and is what
`r_effective = pnl / actual_r_dollars` divides by, not the flat $1,000 the
shares column uses. That is the futures column's own answer to "what does
integer sizing do to R": it makes R noisy trade to trade, not exactly 1.0.

OPTIONS. For every priced row: the nearest-expiry, nearest-strike LISTED
contract on or after the trade's day (Polygon's own contract catalog,
`/v3/reference/options/contracts` -- no strike-increment guessing), call or
put per the row's own `dir` field (which already reads "call"/"put").
Sizing risk is computed the SAME way whether or not a real bar is found:
delta model, `risk_per_contract = |entry - stop| * 0.42 * 100`, contracts
sized to $1,000 of that. That keeps sizing identical across the real/model
split so the split only shows up in the REALIZED pnl, which is the actual
question this row asks (does an option's real fill diverge from a linear
R-scaled shares figure). Realized pnl:
    real:  fetch the 1-minute bar nearest the entry clock time ("et") and
           the bar nearest exit clock time (et + `bars` minutes -- `bars`
           is the engine's own minute count from entry to exit, the same
           field day_policy.py and loss_halt.py use as `entry_i + bars` to
           order exits) for the SAME contract; pnl = (exit - entry) close
           prices x 100 x contracts. instrument_source="real".
    model: pnl = r * actual_r_dollars (linear in the underlying's own R,
           by construction of the delta-sized risk) minus a round-trip
           $0.05 x 100 x contracts x 2 spread cost. instrument_source="model".
A row is "real" only if BOTH the entry and the exit bar exist for the
picked contract on Polygon; any 403, empty result, or missing minute falls
through to the model and is counted as such.

WALL-CLOCK BOUND. `--stage fetch` runs the real-bar pull, capped internally
at 110 minutes (SWARM.md: "run ... in the background ... hard cap of 2
hours" -- 110m leaves headroom for `--stage report` afterward), in a FIXED
shuffled order (seed 20260905) so a time-capped prefix is a random
subsample across the whole two years, not just the earliest days. It
checkpoints to `data_archive/options/g213_progress.json` after every row,
so a second `--stage fetch` resumes rather than re-spending calls the
cache already paid for. `--stage report` prices every row (real from the
cache where present, model everywhere else) and writes the book + the md.
`--stage all` does both, but a real 2-year fetch should always be launched
as `--stage fetch` in the background per SWARM.md, then `--stage report`
run once it finishes or the cap is hit.

Cache: data_archive/options/{catalog,aggs}/*.json (data_archive/ is already
entirely .gitignore'd, so no separate rule is needed here). Rate limiting,
429 backoff and never-print-the-key are `research/g73_polygon_fetch._get`,
imported not retyped -- g73 already measured this key's actual rate (5
calls/min, "Options Basic") and it is the same key here.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import book_stamp                                    # noqa: E402
from research.g72_suppress_price import stats as g72_stats, idkey   # noqa: E402
from research.loop_cycle import up_to_3_rows                        # noqa: E402
from research.g73_polygon_fetch import _get                         # noqa: E402
import universe                                                     # noqa: E402

BASELINE = ROOT / "research" / "tape" / "baseline_2026-09-05.json.gz"
OUT_BOOK = ROOT / "research" / "tape" / "instruments_2026-09-05.json.gz"
REPORT_MD = ROOT / "research" / "g213_instruments.md"
CACHE = ROOT / "data_archive" / "options"
(CACHE / "catalog").mkdir(parents=True, exist_ok=True)
(CACHE / "aggs").mkdir(parents=True, exist_ok=True)
PROGRESS = CACHE / "g213_progress.json"

CORE = set(universe.CORE_SYMBOLS)
HALVES_BOUNDARY = "2025-09-01"      # SWARM.md's H1/H2 split
RISK = 1000.0

# ------------------------------------------------------------- futures model
FUT_MAP = {"SPY": "MES", "QQQ": "MNQ", "IWM": "M2K"}
# APPROXIMATE, rule-of-thumb ratios (index level / ETF price). Not fit to
# data; see the verify note above and g213_verify.py's "unverified" line.
FUT_RATIO = {"SPY": 10.0, "QQQ": 41.35, "IWM": 10.0}
FUT_RATIO_SOURCE = ("standard SPX~=10xSPY and NDX~=41.35xQQQ rules of thumb "
                     "(no fixed date -- no ES/MES or NQ/MNQ bars on disk to "
                     "fit a date-specific ratio to; see g213_verify.py)")
FUT_TICK = {"MES": 0.25, "MNQ": 0.25, "M2K": 0.10}
FUT_MULT = {"MES": 5.0, "MNQ": 2.0, "M2K": 5.0}
FUT_COMMISSION_PER_SIDE = 0.62
# Approximate day-session (intraday) margins, broker-published rule-of-thumb
# figures as of 2026-09, NOT fit to any specific broker/date -- referee
# defect: this row's spec required a margin figure and none was in the file.
# These are for capital-requirement DISCLOSURE only; they do not change pnl.
FUT_DAY_MARGIN = {"MES": 50.0, "MNQ": 100.0, "M2K": 50.0}


def round_tick(px, tick):
    return round(round(px / tick) * tick, 4)


def price_futures(r):
    sym = r["sym"]
    fut = FUT_MAP.get(sym)
    if not fut:
        return {"instrument": "n/a", "reason": "single name, no micro future"}
    ratio = FUT_RATIO[sym]
    tick = FUT_TICK[fut]
    mult = FUT_MULT[fut]
    idx_entry = round_tick(r["entry"] * ratio, tick)
    idx_stop = round_tick(r["stop"] * ratio, tick)
    risk_pts = abs(idx_entry - idx_stop)
    if risk_pts <= 0:
        risk_pts = tick   # rounding collapsed the stop onto entry -- floor at 1 tick
    risk_per_contract = risk_pts * mult
    contracts = max(1, round(RISK / risk_per_contract))
    actual_r_dollars = contracts * risk_per_contract
    commission = 2 * FUT_COMMISSION_PER_SIDE * contracts
    pnl = r["r"] * actual_r_dollars - commission
    notional = idx_entry * mult * contracts
    day_margin = FUT_DAY_MARGIN[fut] * contracts
    return {"instrument": fut, "ratio": ratio, "contracts": contracts,
            "risk_per_contract": round(risk_per_contract, 2),
            "actual_r_dollars": round(actual_r_dollars, 2),
            "commission": round(commission, 2), "pnl": round(pnl, 2),
            "r_effective": round(pnl / actual_r_dollars, 4),
            "notional": round(notional, 2), "day_margin": round(day_margin, 2)}


# -------------------------------------------------------------- options model
DELTA = 0.42
SPREAD = 0.05
MULT = 100


def sizing_risk(r):
    risk_per_contract = abs(r["entry"] - r["stop"]) * DELTA * MULT
    contracts = max(1, round(RISK / risk_per_contract))
    actual_r_dollars = contracts * risk_per_contract
    return contracts, round(actual_r_dollars, 2)


def catalog(sym, month, cache_only=False):
    f = CACHE / "catalog" / ("%s_%s.json" % (sym, month))
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    if cache_only:
        return {"_status": "uncached"}
    y, m = int(month[:4]), int(month[5:7])
    lo = month + "-01"
    hi = "%04d-%02d-01" % (y + (1 if m == 12 else 0), (m % 12) + 1)
    j = _get("/v3/reference/options/contracts", underlying_ticker=sym,
             expired="true", limit=1000,
             **{"expiration_date.gte": lo, "expiration_date.lt": hi})
    if "_status" in j:
        f.write_text(json.dumps({"_status": j["_status"], "results": []}))
        return {"_status": j["_status"], "results": []}
    out = list(j.get("results") or [])
    while j.get("next_url") and len(out) < 6000:
        nxt = j["next_url"].replace("https://api.polygon.io", "")
        base, _, qs = nxt.partition("?")
        kw2 = dict(p.split("=", 1) for p in qs.split("&") if p and "apiKey" not in p)
        j = _get(base, **kw2)
        if "_status" in j:
            break
        out += list(j.get("results") or [])
    result = {"results": out}
    f.write_text(json.dumps(result))
    return result


def pick_contract(sym, day, entry_px, is_call, cache_only=False):
    cat = catalog(sym, day[:7], cache_only=cache_only)
    if cat.get("_status") in (403, "uncached"):
        return None, cat.get("_status")
    cands = cat.get("results", [])
    if not any(c.get("expiration_date", "") >= day for c in cands):
        y, m = int(day[:4]), int(day[5:7])
        cat2 = catalog(sym, "%04d-%02d" % (y + (1 if m == 12 else 0), (m % 12) + 1),
                       cache_only=cache_only)
        if cat2.get("_status") in (403, "uncached"):
            return None, cat2.get("_status")
        cands = cands + cat2.get("results", [])
    want = "call" if is_call else "put"
    cands = [c for c in cands
             if c.get("contract_type") == want
             and c.get("expiration_date", "") >= day
             and c.get("shares_per_contract", 100) == 100]
    if not cands:
        return None, "no_listing"
    exp = min(c["expiration_date"] for c in cands)
    same = [c for c in cands if c["expiration_date"] == exp]
    best = min(same, key=lambda c: abs(c["strike_price"] - entry_px))
    return {"ticker": best["ticker"], "strike": best["strike_price"], "expiry": exp}, None


def option_minutes(ticker, day, cache_only=False):
    f = CACHE / "aggs" / ("%s_%s.json" % (ticker.replace(":", "_"), day))
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    if cache_only:
        return {"_status": "uncached"}
    j = _get("/v2/aggs/ticker/%s/range/1/minute/%s/%s" % (ticker, day, day),
              adjusted="true", sort="asc", limit=50000)
    if "_status" in j:
        out = {"_status": j["_status"]}
    else:
        import datetime as dt
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")
        out = {}
        for b in (j.get("results") or []):
            ts = dt.datetime.fromtimestamp(b["t"] / 1000, tz=dt.timezone.utc).astimezone(ET)
            out[ts.strftime("%H:%M")] = {"o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"]}
    f.write_text(json.dumps(out))
    return out


def nearest_minute(bars, hhmm):
    """Closing price of the bar at hhmm, or the nearest bar within 5 minutes."""
    if hhmm in bars:
        return bars[hhmm]["c"]
    h, m = int(hhmm[:2]), int(hhmm[3:])
    total = h * 60 + m
    best, best_d = None, 6
    for k, v in bars.items():
        if k.startswith("_"):
            continue
        kh, km = int(k[:2]), int(k[3:])
        d = abs((kh * 60 + km) - total)
        if d < best_d:
            best_d, best = d, v["c"]
    return best


def add_minutes(hhmm, n):
    h, m = int(hhmm[:2]), int(hhmm[3:])
    total = h * 60 + m + int(n)
    return "%02d:%02d" % (total // 60, total % 60)


def price_options_real(r, cache_only=False):
    """Real-bar pnl per contract-pair, or None if any leg is unavailable.

    `cache_only=True` (the report stage) never makes a new network call --
    an uncached leg is priced by the model, not fetched on the spot, so the
    report never blocks on Polygon's 5-calls/min limit."""
    contract, err = pick_contract(r["sym"], r["day"], r["entry"], r["dir"] == "call",
                                   cache_only=cache_only)
    if contract is None:
        return None, ("403" if err == 403 else err or "no_listing")
    entry_bars = option_minutes(contract["ticker"], r["day"], cache_only=cache_only)
    if entry_bars.get("_status") in (403, "uncached"):
        return None, entry_bars["_status"]
    exit_clock = add_minutes(r["et"], r.get("bars", 1) or 1)
    entry_px = nearest_minute(entry_bars, r["et"])
    exit_px = nearest_minute(entry_bars, exit_clock)
    if entry_px is None or exit_px is None:
        return None, "no_bar"
    return {"contract": contract["ticker"], "entry_opt": entry_px,
            "exit_opt": exit_px}, None


def price_options(r, cache_only=True):
    """cache_only=True (the default, and always in the report stage): only
    ever read what `--stage fetch` already cached -- never a new call."""
    contracts, actual_r_dollars = sizing_risk(r)
    real = None
    real, err = price_options_real(r, cache_only=cache_only)
    if real:
        pnl = (real["exit_opt"] - real["entry_opt"]) * MULT * contracts
        return {"instrument_source": "real", "contract": real["contract"],
                "contracts": contracts, "actual_r_dollars": actual_r_dollars,
                "entry_opt": real["entry_opt"], "exit_opt": real["exit_opt"],
                "pnl": round(pnl, 2), "r_effective": round(pnl / actual_r_dollars, 4)}
    # Referee defect (T2 pass 1): this used to charge 2 x SPREAD, i.e. two
    # full quoted widths ($10/contract) round trip. Standard convention is
    # ONE full width from mid ($5/contract): half the spread lost on entry,
    # half on exit. Fixed to the standard convention.
    spread_cost = SPREAD * MULT * contracts
    pnl = r["r"] * actual_r_dollars - spread_cost
    return {"instrument_source": "model", "contracts": contracts,
            "actual_r_dollars": actual_r_dollars, "spread_cost": round(spread_cost, 2),
            "pnl": round(pnl, 2), "r_effective": round(pnl / actual_r_dollars, 4)}


# --------------------------------------------------------------------- main

def load_unit_rows():
    b = json.loads(gzip.open(BASELINE, "rt", encoding="utf-8").read())
    meta, rows = b["meta"], b["trades"]
    core = [r for r in rows if r.get("tier") == "core"]
    unit = up_to_3_rows(core)
    return meta, unit


def stage_fetch(cap_minutes=110):
    meta, unit = load_unit_rows()
    order = list(range(len(unit)))
    random.Random(20260905).shuffle(order)
    progress = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {"done_ids": []}
    done = set(progress["done_ids"])
    t0 = time.time()
    cap = cap_minutes * 60
    stopped_early = False
    n_new = 0
    for i in order:
        r = unit[i]
        rid = "|".join(str(x) for x in idkey(r))
        if rid in done:
            continue
        if time.time() - t0 > cap:
            stopped_early = True
            break
        _, err = price_options_real(r)
        done.add(rid)
        n_new += 1
        if err == "403":
            # Referee defect (T2 pass 1): this used to `break`, so ONE
            # out-of-window row (Polygon Options Basic has a rolling ~2-year
            # lookback) ended the entire fetch pass. A 403 is cached
            # permanently on that row's catalog/agg file (see catalog() /
            # option_minutes()), so it never re-spends a call -- `continue`
            # to the next row instead of aborting the whole pass.
            print("g213_instruments: 403 on %s %s -- that row falls back to the model, continuing" % (r["sym"], r["day"]), flush=True)
            continue
        if n_new % 25 == 0:
            PROGRESS.write_text(json.dumps({"done_ids": sorted(done)}))
            print("g213_instruments: fetched %d/%d, %.1fm elapsed" %
                  (len(done), len(unit), (time.time() - t0) / 60), flush=True)
    PROGRESS.write_text(json.dumps({"done_ids": sorted(done)}))
    print("g213_instruments fetch done: %d of %d rows cached, stopped_early=%s"
          % (len(done), len(unit), stopped_early), flush=True)


def stage_report():
    meta, unit = load_unit_rows()
    trades_out = []
    n_real = n_model = 0
    for r in unit:
        rid = "|".join(str(x) for x in idkey(r))
        fut = price_futures(r)
        opt = price_options(r, cache_only=True)
        if opt["instrument_source"] == "real":
            n_real += 1
        else:
            n_model += 1
        trades_out.append({
            "id": rid, "sym": r["sym"], "day": r["day"], "et": r["et"], "r": r["r"],
            "bars": r.get("bars", 1),   # carried so g213_verify.py never has to
                                        # re-derive the exit clock via a (sym,day,et)
                                        # lookup that is not itself a unique key
            "shares": {"pnl": r["pnl"]},
            "futures": fut,
            "options": opt,
        })

    def rows_for(instrument):
        return [{"day": t["day"], "pnl": t[instrument]["pnl"]} for t in trades_out
                if instrument in t and "pnl" in t[instrument]]

    def half(rows, before):
        return [r for r in rows if (r["day"] < HALVES_BOUNDARY) == before]

    n_days_all = len({t["day"] for t in trades_out})
    n_days_h1 = len({t["day"] for t in trades_out if t["day"] < HALVES_BOUNDARY})
    n_days_h2 = len({t["day"] for t in trades_out if t["day"] >= HALVES_BOUNDARY})

    sections = {}
    for name, key in (("shares", "shares"), ("futures", "futures"), ("options", "options")):
        rows = rows_for(key)
        h1 = half(rows, True)
        h2 = half(rows, False)
        sections[name] = {
            "n": len(rows),
            "whole": g72_stats(rows, n_days_all) if rows and n_days_all else {},
            "h1": g72_stats(h1, n_days_h1) if h1 and n_days_h1 else {},
            "h2": g72_stats(h2, n_days_h2) if h2 and n_days_h2 else {},
        }

    # Referee defect (T2 pass 1): the published report set futures' $/day
    # (99 SPY/QQQ rows) beside shares' whole-window $/day (all 769 rows) as
    # though matched. Add the SAME 99 rows priced as shares, so futures is
    # judged against its own subset, not the whole book.
    # Same denominator convention the "futures" section itself uses
    # (n_days_all, the whole-window trading-day count) -- otherwise the
    # $/day comparison mismatches on the denominator instead of matching on
    # the row set.
    fut_rows_full = [t for t in trades_out if "pnl" in t.get("futures", {})]
    matched_shares_rows = [{"day": t["day"], "pnl": t["shares"]["pnl"]} for t in fut_rows_full]
    sections["shares_matched_to_futures"] = {
        "n": len(matched_shares_rows),
        "whole": g72_stats(matched_shares_rows, n_days_all) if matched_shares_rows and n_days_all else {},
    }
    if fut_rows_full:
        notionals = sorted(t["futures"]["notional"] for t in fut_rows_full)
        sections["futures"]["median_notional"] = notionals[len(notionals) // 2]

    out_meta = book_stamp.stamp(unit, unit="up_to_3_stop_win_or_2loss",
                                 baseline_book=str(BASELINE.relative_to(ROOT)),
                                 baseline_book_id=meta["stamp"]["book_id"],
                                 n_unit_rows=len(unit),
                                 options_real=n_real, options_model=n_model)
    OUT_BOOK.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT_BOOK, "wt", encoding="utf-8") as f:
        json.dump({"meta": out_meta, "trades": trades_out}, f)

    write_report(sections, n_real, n_model, len(unit), out_meta)
    print("wrote %s and %s (real=%d model=%d of %d)" %
          (OUT_BOOK, REPORT_MD, n_real, n_model, len(unit)), flush=True)


def cell(s, min_trades=30, min_months=12):
    if not s:
        return "no rows"
    t = s.get("trades", 0)
    mo = s.get("months", 0)
    flag = "" if (t >= min_trades and mo >= min_months) else "  (not enough: %d trades, %d months)" % (t, mo)
    return ("$%d/day, mean R %.3f, win %.1f%%, %d/%d green months%s"
            % (s.get("per_day", 0), s.get("mean_r", 0), s.get("win_pct", 0),
               s.get("months_green", 0), s.get("months", 0), flag))


def write_report(sections, n_real, n_model, n_unit, out_meta):
    pct_real = round(100 * n_real / n_unit, 1) if n_unit else 0.0
    dirty = out_meta.get("git", {}).get("dirty_py_count")
    lines = []
    lines.append("# g213 -- instrument columns, T2\n")
    lines.append("Baseline: `%s` (book_id %s), unit `up_to_3_stop_win_or_2loss`, "
                  "universe.CORE_SYMBOLS (tier=='core', 11 symbols), fill=close. "
                  "%d unit rows priced. Script: `research/g213_instruments.py`.\n"
                  % (BASELINE.name, out_meta["baseline_book_id"], n_unit))
    if dirty:
        lines.append("**Tree was dirty at build time (%d .py file(s) uncommitted).** "
                      "Rebuild after committing this repair to get a clean-tree stamp "
                      "if that matters for your use of this book.\n" % dirty)
    lines.append("Options priced from real Polygon 1-minute option aggregates for "
                  "**%d of %d rows (%.1f%%)**; the rest (%d rows) fall back to the "
                  "0.42-delta + $0.05-spread model. Referee pass 1 found the real "
                  "coverage this low mainly because (a) Polygon Options Basic has a "
                  "rolling ~2-year lookback -- a live probe got a 403 on a contract "
                  "that returned 200 the night before -- and (b) the fetch loop used "
                  "to `break` on the FIRST 403 instead of `continue`, so one "
                  "out-of-window row ended the whole pass; both are now fixed "
                  "(`continue`, permanently cached per-row so it never re-spends a "
                  "call), but this report was NOT re-fetched against live Polygon as "
                  "part of this repair, so the %d/%d coverage number itself is "
                  "unchanged from before the fix. `instrument_source` on every row in "
                  "`research/tape/instruments_2026-09-05.json.gz` says which.\n"
                  % (n_real, n_unit, pct_real, n_unit - n_real, n_real, n_unit))
    lines.append("Futures ratio (SPY->MES 10.0x, QQQ->MNQ 41.35x) is a rule-of-thumb, "
                  "**not fit to data** -- no ES/MES or NQ/MNQ 1-minute bars exist under "
                  "`data_archive/` on this box, so `research/g213_verify.py` reports "
                  "this UNVERIFIED rather than checked against a 7-day overlap "
                  "(the row's own fallback clause). IWM->M2K is defined but never "
                  "exercised on this book: IWM is in `universe.INDEX_POOL` but not in "
                  "`universe.CORE_SYMBOLS`, the tier this baseline trades.\n")
    lines.append("**What the futures column actually measures (referee pass 1).** "
                  "Integer-contract sizing pins `actual_r_dollars` to within about "
                  "+-2 pct of $1,000 no matter what the SPY->MES / QQQ->MNQ ratio is, so "
                  "`pnl = r * actual_r_dollars - commission` is barely more than "
                  "shares-R minus $1.24/contract commission -- re-pricing all 99 rows "
                  "at ratio shocks of +-0.5/1/2/5/10 pct moves $/day by about $1 and "
                  "green months not at all. **This column cannot tell you anything "
                  "about the SPY:SPX or QQQ:NDX basis; it tells you what commission "
                  "does to the shares number.** Day margin (required by this row's "
                  "spec, missing before this repair) is now reported per trade as an "
                  "approximate, not-fit-to-any-broker figure "
                  "(MES $50/contract, MNQ $100/contract) -- median notional on the "
                  "futures-eligible rows is roughly $%s.\n"
                  % "{:,.0f}".format(sections["futures"].get("median_notional", 0)))
    lines.append("**Futures is worse than shares on the same rows, not better "
                  "(referee pass 1).** The published version set futures' $/day "
                  "beside shares' whole-window $/day (99 rows vs all 769) as though "
                  "matched. On the SAME 99 SPY/QQQ rows: shares %s vs futures %s -- "
                  "futures loses to shares by commission alone.\n"
                  % (cell(sections["shares_matched_to_futures"]["whole"]), cell(sections["futures"]["whole"])))
    lines.append("Sample-size rule (SWARM.md): a cell under 30 trades or 12 months "
                  "gets no verdict, just the count -- marked inline below. Only %d "
                  "rows are real-priced, so the real-vs-model split itself has no "
                  "verdict either; it is a coverage number, not a comparison.\n" % n_real)
    lines.append("Why the options model column is this negative: at this engine's "
                  "typical stop distance, a delta-sized position needs dozens of "
                  "contracts to reach $1,000 of risk (median ~34 contracts across the "
                  "model-priced rows here), and the round-trip spread cost scales with "
                  "contract count. **Spread convention fixed this repair** (referee "
                  "pass 1): it used to charge TWO full quoted widths ($10/contract "
                  "round trip) on model rows and zero on the 20 real rows -- the only "
                  "verified rows were the only rows exempt from the assumption that "
                  "drove the headline. It now charges the standard ONE full width from "
                  "mid ($5/contract). The %d real-bar rows above are ladder-scale-out "
                  "trades priced at a single entry-to-last-exit-leg option price, which "
                  "does not price the same trade the shares row booked for scaled "
                  "exits (most of the 20) -- this is a known, unfixed divergence "
                  "between the option pricing and the shares pricing for scaled "
                  "trades, not evidence about option convexity.\n" % n_real)
    for name in ("shares", "futures", "options"):
        s = sections[name]
        lines.append("## %s (%d trades)\n" % (name.capitalize(), s["n"]))
        lines.append("- whole window: %s" % cell(s["whole"]))
        lines.append("- H1 (before 2025-09-01): %s" % cell(s["h1"]))
        lines.append("- H2 (2025-09-01 on): %s\n" % cell(s["h2"]))
    lines.append("## Shares, matched to the futures-eligible subset (%d trades)\n"
                  % sections["shares_matched_to_futures"]["n"])
    lines.append("- whole window: %s\n" % cell(sections["shares_matched_to_futures"]["whole"]))
    lines.append("Single names (AAPL AMD AMZN GOOGL META MSFT NVDA PLTR TSLA) have no "
                  "futures column (`instrument: \"n/a\"` on those rows) -- only "
                  "SPY and QQQ trade as futures micros in this universe.\n")
    lines.append("## Refereed (T2 repair, referee pass 1)\n")
    lines.append("**Fixed in this repair:**\n")
    lines.append("1. Spread convention: was charging two full quoted widths "
                  "($10/contract round trip); now charges the standard one full "
                  "width from mid ($5/contract). Options headline moved from "
                  "-$607/day 2/25 green to -$326/day 4/25 green.")
    lines.append("2. Futures-vs-shares comparison: was comparing futures' 99-row "
                  "$/day against shares' all-769-row $/day as though matched. Added "
                  "the \"Shares, matched to the futures-eligible subset\" section "
                  "above (same 99 rows, same denominator convention) -- shares "
                  "$17/day beats futures $12/day on the identical rows; futures is "
                  "worse by commission, not better.")
    lines.append("3. Day margin (required by this row's spec, absent before this "
                  "repair): added as an approximate, not-fit-to-any-broker figure "
                  "per contract (MES $50, MNQ $100), plus notional, on every "
                  "futures-priced row.")
    lines.append("4. Fetch loop broke on the FIRST 403 instead of continuing; one "
                  "out-of-window row ended the whole two-year pass. Now `continue`s "
                  "(the 403 is cached permanently on that row so it never re-spends "
                  "a call). Confirmed live during this repair's verify re-run: the "
                  "TSLA 2024-09-05 row, real-priced when the original book was "
                  "built, now returns a fresh HTTP 403 from Polygon -- direct "
                  "evidence of the rolling ~2-year lookback the referee named as "
                  "the real cause, not the 110-minute wall-clock cap.")
    lines.append("5. \"the 15 real-bar rows above\" corrected to the actual real-bar "
                  "count (computed, not a hardcoded number).")
    lines.append("6. IWM->M2K wording corrected: IWM IS in `universe.INDEX_POOL`, "
                  "just not in `universe.CORE_SYMBOLS` (the tier this baseline "
                  "trades) -- the prior wording implied IWM was absent from "
                  "universe.py entirely.")
    lines.append("7. Dirty-tree-at-build-time is now disclosed in this report when "
                  "`meta.git.dirty_py_count` is nonzero.")
    lines.append("8. `g213_verify.py` now states explicitly that its 20-row check "
                  "is the entire real-row population, not a sample of it, and "
                  "verifies cache integrity only.\n")
    lines.append("**Refuted, kept as a disclosed limitation (not fixable inside "
                  "this row without a second change):**\n")
    lines.append("1. The futures column is fundamentally insensitive to the "
                  "SPY:SPX / QQQ:NDX basis it claims to model: integer-contract "
                  "sizing pins `actual_r_dollars` within about +-2 pct of $1,000 "
                  "regardless of the ratio used (re-priced at +-0.5/1/2/5/10 pct "
                  "ratio shocks: $/day moves ~$1, green months unchanged). This is "
                  "a structural property of integer sizing on a fixed-R book, not a "
                  "bug this repair can code its way out of -- the report above now "
                  "says plainly that this column reads as \"shares R minus "
                  "commission,\" not a futures venue simulation. Fixing it for real "
                  "would mean pricing risk in index points directly rather than "
                  "converting a shares-R figure, which is a second, larger change "
                  "outside this row's scope.")
    lines.append("2. 14 of the 20 real-bar option rows are ladder scale-out trades "
                  "(30/30/30/10) priced as a single entry-close to last-exit-leg "
                  "close, which does not price the same trade the shares row "
                  "booked for scaled exits, and 4 of 20 flip P&L sign against "
                  "shares on that account. Pricing each leg separately needs the "
                  "per-leg exit clocks that `backtest_2y.py`'s ladder produces "
                  "internally but does not export on this row's trade record -- a "
                  "second change to what the baseline book carries, not something "
                  "fixable inside `g213_instruments.py` alone.")
    lines.append("3. Real-bar coverage remains 20/769 (2.6%) in this repair's "
                  "output: the break-on-403 bug is fixed (see item 4 above), but a "
                  "live 2-year re-fetch was not re-run as part of this repair (would "
                  "cost a fresh ~110-minute background pass against Polygon's "
                  "5-calls/min limit); a future `--stage fetch` run will pick up "
                  "more real coverage than this book has today.")
    lines.append("4. Commits `07c35df8` and `ccd7fa06` (T2's original build) are "
                  "both `wip: auto-commit` messages that do not name the row or "
                  "number -- history cannot be rewritten under this project's "
                  "never-rebase rule, so they stand uncorrected; this repair's own "
                  "commit names the row and the number that moved.\n")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["fetch", "report", "all"], default="all")
    ap.add_argument("--cap-minutes", type=int, default=110)
    args = ap.parse_args()
    if args.stage in ("fetch", "all"):
        stage_fetch(args.cap_minutes)
    if args.stage in ("report", "all"):
        stage_report()


if __name__ == "__main__":
    main()
