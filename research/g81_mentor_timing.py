"""g81_mentor_timing.py -- when a mentor traded a symbol-day, what did OMEN do
on that same symbol-day, and how did the two entry TIMES compare?

Austin, 2026-08-29: "We need to use Scarface and J Dub because you said one
candle rule is not firing as the earliest best possible entry."

INPUT (already built, not re-mined here):
  research/corpus_sf/pooled_trades.jsonl -- 3,547 deduplicated mentor trade
  instances (symbol, direction, trade_date, a Discord post timestamp, and
  where stated an entry price / outcome / R / dollar P&L), pooled from 6,318
  trade-shaped rows across Scarface alerts, jdub alerts, futures alerts,
  written reviews and posted gains. See research/corpus_sf/pool_report.md for
  exactly how it was built and its two documented limits (8.7% outcome
  conflicts on multi-row instances, 79 weekend dates).

THE ROUTER MUST BE THE REAL ONE. This script reuses research/t4_engine_recall
and backtest_week exactly as research/g81_marks30_score.py does, and refuses
to run unless CaptureRunner._route still delegates to the shipped router
(SignalRunner._route) -- see assert_real_router().

WHAT "OMEN traded" MEANS: a signal the shipped router accepted (`fired`) AND
booked through the shipped fill simulation (`backtest_week.simulate_day`,
`SimTrade.counted` -- fired and not grade C, since C is alert-only in the live
scanner). "OMEN fired" is looser: the router accepted a signal, whether or not
it survived to a booked/counted trade.

A DISCORD POST TIME IS A LAGGING, NOISY PROXY FOR AN ENTRY. A trader posts
after clicking buy, after typing a paragraph, sometimes in a recap hours
later. Section 6 below quantifies that lag directly, on the handful of rows
where a review states the actual fill price: it locates the RTH minute whose
close is nearest that stated price and reports how far the post minute sits
from it. Every other timing number in this file compares AGAINST THE POST
MINUTE because it is the only timestamp this corpus has -- not because it is
assumed to be the entry.

This is EVIDENCE ABOUT AUSTIN'S RULES. Scarface's and jdub's judgements are
mentor data, never Austin's, and nothing here is merged into any Austin mark
corpus. No file under research/marks/, research/austin_marks_v7.jsonl,
research/blind_marks_all.jsonl, or any other named mark corpus is opened for
writing.

    python research/g81_mentor_timing.py [--out research/g81_mentor_timing.json]
"""
from __future__ import annotations

import argparse
import datetime
import inspect
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as t4            # noqa: E402
import backtest_week as bw               # noqa: E402
import levels                            # noqa: E402
from universe import ALL_SYMS            # noqa: E402

POOL = os.path.join(HERE, "corpus_sf", "pooled_trades.jsonl")
WINDOW_LO, WINDOW_HI = 570, 660  # 09:30-11:00 ET, minutes since midnight

DIR_OF = {"long": "call", "short": "put"}   # mentor spelling -> engine spelling


# --------------------------------------------------------------------------
# guard: are we on the fixed router? (same check as g81_marks30_score.py)
# --------------------------------------------------------------------------

def assert_real_router():
    src = inspect.getsource(t4.CaptureRunner._route)
    if "super()._route(" not in src:
        raise SystemExit(
            "ABORT: t4_engine_recall.CaptureRunner._route does not call super(). "
            "That is the hand-rolled copy that flattered recall. Refusing to "
            "publish a number measured on it.")
    return {"delegates_to_super": True,
            "base_router": "%s.%s" % (t4.SignalRunner.__module__, "SignalRunner._route")}


def is_weekday(iso_date: str) -> bool:
    y, m, d = (int(x) for x in iso_date.split("-"))
    return datetime.date(y, m, d).weekday() < 5


def fmt_min(n):
    return "%d:%02d" % (n // 60, n % 60)


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")[:2]
    return int(h) * 60 + int(m)


def dist(vals):
    if not vals:
        return None
    s = sorted(vals)
    return {"n": len(s), "min": s[0], "max": s[-1],
             "median": statistics.median(s), "mean": round(statistics.mean(s), 2),
             "earlier_than_mentor": sum(1 for v in s if v < 0),
             "exact": sum(1 for v in s if v == 0),
             "later_than_mentor": sum(1 for v in s if v > 0),
             "within_5min": sum(1 for v in s if abs(v) <= 5),
             "within_10min": sum(1 for v in s if abs(v) <= 10),
             "values": s}


# --------------------------------------------------------------------------
# 1. join
# --------------------------------------------------------------------------

def build_join(pool_rows):
    """Return (funnel, joined_rows, pair_cache). funnel is the honest yield
    at each filter stage, reported in the order the task asked for."""
    funnel = {"pool_total": len(pool_rows)}

    weekday_rows = [r for r in pool_rows if is_weekday(r["trade_date"])]
    funnel["weekend_dropped"] = len(pool_rows) - len(weekday_rows)
    funnel["after_weekday_filter"] = len(weekday_rows)

    uni_rows = [r for r in weekday_rows if r["symbol"] in ALL_SYMS]
    funnel["not_in_universe_dropped"] = len(weekday_rows) - len(uni_rows)
    funnel["after_universe_filter"] = len(uni_rows)
    funnel["distinct_symbol_days_after_universe_filter"] = len(
        {(r["symbol"], r["trade_date"]) for r in uni_rows})

    pairs = sorted({(r["symbol"], r["trade_date"]) for r in uni_rows})
    has_bars = {}
    for sym, day in pairs:
        p = os.path.join(levels.ARCHIVE, sym, "%s.csv" % day)
        has_bars[(sym, day)] = os.path.exists(p)
    n_pairs_with_bars = sum(1 for v in has_bars.values() if v)
    funnel["distinct_symbol_days_with_archived_bars"] = n_pairs_with_bars
    funnel["distinct_symbol_days_no_archive"] = len(pairs) - n_pairs_with_bars

    joined_rows = [r for r in uni_rows if has_bars.get((r["symbol"], r["trade_date"]))]
    funnel["after_archive_filter_rows"] = len(joined_rows)
    funnel["join_yield_pct_of_pool"] = round(len(joined_rows) / len(pool_rows) * 100, 1)

    in_window = [r for r in joined_rows
                 if r["et_minute"] is not None and WINDOW_LO <= r["et_minute"] <= WINDOW_HI]
    funnel["of_joined_rows_posted_in_0930_1100_window"] = len(in_window)
    funnel["of_joined_rows_posted_outside_window_or_no_time"] = len(joined_rows) - len(in_window)

    return funnel, joined_rows


# --------------------------------------------------------------------------
# 2. run the engine once per unique (symbol, day)
# --------------------------------------------------------------------------

def score_pair(symbol, day):
    candles = t4.rth_candles(symbol, day)
    if not candles:
        return None
    pdh, pdl, pdo, pdc = t4.prior_day_levels(symbol, day)
    pmh, pml = t4.premarket_extremes(symbol, day)
    bias = t4.htf_bias(symbol, day)

    entries, all_sigs, raw_sigs = t4.run_day(symbol, day)
    trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, qqq=None)
    booked = [t for t in trades if t.counted]

    fired_by_dir = defaultdict(list)   # 'call'/'put' -> [minute]
    for e in (entries or []):
        fired_by_dir[e["direction"]].append(to_min(e["timestamp"][:5]))
    booked_by_dir = defaultdict(list)
    booked_price_by_dir = defaultdict(list)  # 'call'/'put' -> [(minute, entry_price)]
    for t in booked:
        m = to_min(t.entry_time[:5])
        booked_by_dir[t.direction].append(m)
        booked_price_by_dir[t.direction].append((m, t.entry))

    return {
        "candles": candles,
        "fired_dirs": set(fired_by_dir),
        "fired_by_dir": dict(fired_by_dir),
        "booked_dirs": set(booked_by_dir),
        "booked_by_dir": dict(booked_by_dir),
        "booked_price_by_dir": dict(booked_price_by_dir),
        "any_fired_minutes": sorted({to_min(e["timestamp"][:5]) for e in (entries or [])}),
        "any_booked_minutes": sorted({to_min(t.entry_time[:5]) for t in booked}),
    }


def nearest_close_minute(candles, price):
    """The RTH minute (minute-of-day int) whose close is nearest `price`,
    and the abs $ distance. Used only to quantify Discord-post lag against a
    stated fill price (section 6) -- never used as an engine signal."""
    best = None
    for c in candles:
        m = to_min(c.timestamp[:5])
        d = abs(c.close - price)
        if best is None or d < best[1]:
            best = (m, d)
    return best


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g81_mentor_timing.json"))
    args = ap.parse_args()

    router = assert_real_router()
    print("router check: %s" % router)

    pool_rows = [json.loads(l) for l in open(POOL, encoding="utf-8") if l.strip()]
    funnel, joined = build_join(pool_rows)
    print("join funnel: %s" % json.dumps(funnel, indent=2))

    pairs = sorted({(r["symbol"], r["trade_date"]) for r in joined})
    print("scoring %d unique symbol-day pairs against the real router..." % len(pairs))
    cache = {}
    for n, (sym, day) in enumerate(pairs, 1):
        cache[(sym, day)] = score_pair(sym, day)
        if n % 250 == 0:
            print("  ...%d/%d" % (n, len(pairs)))

    # ---------------------------------------------------------------- rows
    scored = []
    for r in joined:
        pair = cache[(r["symbol"], r["trade_date"])]
        sym_dir = DIR_OF.get(r["direction"])
        et = r["et_minute"]
        row = {
            "card_id": r["card_id"],
            "symbol": r["symbol"], "day": r["trade_date"],
            "mentor_direction": r["direction"],
            "engine_direction": sym_dir,
            "post_minute": et,
            "post_time": fmt_min(et) if et is not None else None,
            "in_window": et is not None and WINDOW_LO <= et <= WINDOW_HI,
            "n_authors": r["n_authors"], "confidence": r["confidence"],
            "outcome": r["outcome"], "entry_price": r["entry"],
            "engine_fired_any_minutes": pair["any_fired_minutes"] if pair else [],
            "engine_booked_any_minutes": pair["any_booked_minutes"] if pair else [],
            "engine_fired_dirs": sorted(pair["fired_dirs"]) if pair else [],
            "engine_booked_dirs": sorted(pair["booked_dirs"]) if pair else [],
        }
        if sym_dir and pair:
            row["engine_fired_same_side_minutes"] = pair["fired_by_dir"].get(sym_dir, [])
            row["engine_booked_same_side_minutes"] = pair["booked_by_dir"].get(sym_dir, [])
            opp = "put" if sym_dir == "call" else "call"
            row["engine_fired_opposite_side_minutes"] = pair["fired_by_dir"].get(opp, [])
            row["engine_booked_opposite_side_minutes"] = pair["booked_by_dir"].get(opp, [])
        else:
            row["engine_fired_same_side_minutes"] = []
            row["engine_booked_same_side_minutes"] = []
            row["engine_fired_opposite_side_minutes"] = []
            row["engine_booked_opposite_side_minutes"] = []
        # signed timing: engine minute minus mentor post minute
        if row["in_window"] and row["engine_fired_same_side_minutes"]:
            row["delta_first_fire_vs_post"] = min(row["engine_fired_same_side_minutes"]) - et
        if row["in_window"] and row["engine_booked_same_side_minutes"]:
            row["delta_first_booked_vs_post"] = min(row["engine_booked_same_side_minutes"]) - et
        scored.append(row)

    # ---------------------------------------------------------- 2. fired/traded
    with_dir = [r for r in scored if r["mentor_direction"]]
    q2 = {
        "n_joined_rows": len(scored),
        "n_with_stated_direction": len(with_dir),
        "engine_fired_any_direction": sum(1 for r in scored if r["engine_fired_any_minutes"]),
        "engine_booked_any_direction": sum(1 for r in scored if r["engine_booked_any_minutes"]),
        "of_stated_direction_rows": {
            "engine_fired_same_side": sum(1 for r in with_dir if r["engine_fired_same_side_minutes"]),
            "engine_booked_same_side": sum(1 for r in with_dir if r["engine_booked_same_side_minutes"]),
            "engine_silent_same_side": sum(1 for r in with_dir if not r["engine_fired_same_side_minutes"]),
        },
        "in_window_rows": {
            "n": sum(1 for r in with_dir if r["in_window"]),
            "engine_fired_same_side": sum(1 for r in with_dir if r["in_window"] and r["engine_fired_same_side_minutes"]),
            "engine_booked_same_side": sum(1 for r in with_dir if r["in_window"] and r["engine_booked_same_side_minutes"]),
        },
    }

    # ---------------------------------------------------------- 3. signed timing
    both_fired = [r for r in with_dir if r["in_window"] and "delta_first_fire_vs_post" in r]
    both_booked = [r for r in with_dir if r["in_window"] and "delta_first_booked_vs_post" in r]
    q3 = {
        "note": "engine minute minus mentor's Discord POST minute, signed. Positive = "
                "engine later than the post. Restricted to rows posted 09:30-11:00 (the "
                "engine's own operating window) on the same symbol AND same side.",
        "first_fire_minus_post": dist([r["delta_first_fire_vs_post"] for r in both_fired]),
        "first_booked_minus_post": dist([r["delta_first_booked_vs_post"] for r in both_booked]),
    }

    # ---------------------------------------------------------- 4. entry price
    # entry field mixes underlying-price fills and option-premium fills
    # (e.g. "AMD Puts 870 @2.5" parses entry=2.5, the premium, not the stock
    # price). Filter to rows whose stated entry falls inside a generous band
    # around that day's actual RTH range -- a premium of $0.60-$25 almost
    # never lands inside an equity's own trading range, so this is a cheap,
    # honest filter, not a guess at intent.
    priced = [r for r in with_dir if r["entry_price"] is not None]
    price_rows = []
    for r in priced:
        pair = cache.get((r["symbol"], r["day"]))
        if not pair or not pair["candles"]:
            continue
        lo = min(c.low for c in pair["candles"])
        hi = max(c.high for c in pair["candles"])
        pad = (hi - lo) * 0.5 or hi * 0.05
        if not (lo - pad <= r["entry_price"] <= hi + pad):
            continue  # looks like an option premium/strike, not the underlying
        sym_dir = r["engine_direction"]
        bp = pair["booked_price_by_dir"].get(sym_dir, [])
        if not bp:
            continue
        # nearest booked entry in time to the mentor's post minute, same side
        et = r["post_minute"]
        m_min, m_price = min(bp, key=lambda x: abs(x[0] - et)) if et is not None else bp[0]
        price_rows.append({
            "card_id": r["card_id"], "symbol": r["symbol"], "day": r["day"],
            "direction": r["mentor_direction"],
            "mentor_entry_price": r["entry_price"],
            "omen_entry_price": m_price, "omen_entry_minute": fmt_min(m_min),
            "diff": round(m_price - r["entry_price"], 4),
            "pct_diff": round((m_price - r["entry_price"]) / r["entry_price"] * 100, 2),
        })
    worse_for_calls = sum(1 for p in price_rows if p["direction"] == "long" and p["diff"] > 0)
    worse_for_puts = sum(1 for p in price_rows if p["direction"] == "short" and p["diff"] < 0)
    q4 = {
        "note": "stated 'entry' field is unreliable -- filtered from the "
                "%d rows with any stated price to %d whose value plausibly sits inside "
                "the underlying's own RTH range that day (others are option premiums or "
                "strikes, e.g. an 'AMD Puts 870 @2.5' post parses entry=2.5)."
                % (len(priced), len(price_rows)),
        "n_compared": len(price_rows),
        "omen_price_diff_vs_mentor": dist([p["diff"] for p in price_rows]),
        "omen_pct_diff_vs_mentor": dist([p["pct_diff"] for p in price_rows]),
        "omen_worse_price_count": worse_for_calls + worse_for_puts,
        "omen_worse_price_of_n": len(price_rows),
        "rows": price_rows,
    }

    # ---------------------------------------------------------- 5. directional agreement
    dir_cases = {"same_only": 0, "opposite_only": 0, "both_sides": 0, "engine_silent": 0}
    opposite_examples = []
    for r in with_dir:
        same = bool(r["engine_fired_same_side_minutes"])
        opp = bool(r["engine_fired_opposite_side_minutes"])
        if same and opp:
            dir_cases["both_sides"] += 1
        elif same:
            dir_cases["same_only"] += 1
        elif opp:
            dir_cases["opposite_only"] += 1
            opposite_examples.append(r["card_id"])
        else:
            dir_cases["engine_silent"] += 1
    q5 = {
        "note": "of rows with a stated mentor direction where the engine fired ANYTHING "
                "that symbol-day, how often was the ONLY thing it fired the opposite side.",
        "counts": dir_cases,
        "n_with_any_engine_signal": dir_cases["same_only"] + dir_cases["opposite_only"] + dir_cases["both_sides"],
        "opposite_only_pct_of_any_signal": round(
            dir_cases["opposite_only"] /
            max(1, dir_cases["same_only"] + dir_cases["opposite_only"] + dir_cases["both_sides"]) * 100, 1),
        "opposite_only_examples": opposite_examples[:25],
    }

    # ---------------------------------------------------------- 6. post-time lag
    # For reviews that state an actual fill price, locate the RTH minute whose
    # close is nearest that price, and compare it to the POST minute. That
    # gap is a direct measurement of how much a Discord post lags the real
    # entry -- not an estimate, a lower bound (price can revisit a level more
    # than once; nearest-close only finds the closest visit, not necessarily
    # the one the mentor took).
    lag_rows = []
    for r in price_rows:
        pair = cache.get((r["symbol"], r["day"]))
        candles = pair["candles"] if pair else None
        mentor_row = next((x for x in with_dir if x["card_id"] == r["card_id"]), None)
        if not candles or not mentor_row or mentor_row["post_minute"] is None:
            continue
        nearest = nearest_close_minute(candles, r["mentor_entry_price"])
        if nearest is None:
            continue
        nm, dprice = nearest
        lag_rows.append({
            "card_id": r["card_id"], "symbol": r["symbol"], "day": r["day"],
            "stated_entry_price": r["mentor_entry_price"],
            "post_minute": fmt_min(mentor_row["post_minute"]),
            "nearest_price_match_minute": fmt_min(nm),
            "price_at_match": None,
            "lag_minutes_post_minus_match": mentor_row["post_minute"] - nm,
            "price_gap_at_match": round(dprice, 4),
        })
    q6 = {
        "note": "n is small by construction -- it is the intersection of 'entry price "
                "plausibly the underlying' (q4) and 'post time exists'. Lag is POST minute "
                "minus the minute price was nearest the stated entry; positive = the post "
                "came after the price was actually there (a lagging report). This is a "
                "floor, not an exact fill time: price can revisit a level.",
        "lag_minutes_post_minus_match": dist([r["lag_minutes_post_minus_match"] for r in lag_rows]),
        "rows": lag_rows,
    }

    summary = {
        "router": router,
        "join_funnel": funnel,
        "q2_fired_and_traded": q2,
        "q3_signed_timing_vs_post_minute": q3,
        "q4_entry_price_comparison": q4,
        "q5_directional_agreement": q5,
        "q6_post_time_lag": q6,
    }

    out = {"summary": summary, "rows": scored}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print("wrote %s" % args.out)
    print(json.dumps({k: v for k, v in summary.items() if k != "q4_entry_price_comparison"
                      and k != "q6_post_time_lag"}, indent=2, default=str))


if __name__ == "__main__":
    main()
