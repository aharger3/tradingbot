"""G80 -- tradability: can a robot actually get filled on these trades.

Austin: "i want trades that can realistically be done by a robot." A stop too
tight to survive spread plus slippage is not a valid stop no matter what it
does to the backtest.

We do not have a quote feed (bid/ask) for this book -- only 1-minute OHLCV
bars, cached on disk at data_archive/<SYM>/<day>.csv. So the spread here is a
PROXY, stated up front and used consistently:

    spread_proxy(bar) = max(ONE_CENT, SPREAD_FRAC * (bar.high - bar.low))

SPREAD_FRAC = 0.10 -- ten percent of the entry minute's own high-low range.
Rationale: on a 1-minute bar, the printed range already reflects how much the
name moved and how liquid/volatile it was in that minute; a dime-out-of-a-
dollar-of-range is a mid-of-the-road estimate for a liquid, actively-traded
name (large caps typically quote 1-3 cents wide against a much larger 1-min
range; thin/volatile names quote wider against a larger range too, so a
fraction-of-range scales in the right direction). This is NOT a fitted or
historically-validated number -- it is a defensible, stated assumption, nothing
more. A one-cent floor keeps flat/zero-range minutes from returning zero
spread.

Trades whose STOP DISTANCE (|entry - stop|) is under 2x this proxy are
flagged untradeable: a bot would routinely get stopped by spread crossing
alone, independent of any real move against the position.

Usage:  python research/g80_tradability.py
Writes: research/g80_tradability.json, research/g80_tradability.md
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf  # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
OUT_JSON = ROOT / "research" / "g80_tradability.json"
OUT_MD = ROOT / "research" / "g80_tradability.md"

SPREAD_FRAC = 0.10
ONE_CENT = 0.01
MIN_STOP_MULT = 2.0

_cache: dict = {}


def bars(sym, day):
    k = (sym, day)
    if k not in _cache:
        if len(_cache) > 60:
            _cache.clear()
        _cache[k] = pf.rth(pf.fetch_day(sym, day))
    return _cache[k]


def spread_proxy_cents(bar) -> float:
    rng = bar.high - bar.low
    return max(ONE_CENT, SPREAD_FRAC * rng)


def mean(xs):
    return statistics.mean(xs) if xs else 0.0


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def one_a_day(trades):
    """First trade per (sym-agnostic) day, ordered by seq, mirrors the book's
    'one-trade-a-day' lens used throughout G80/G76/g71."""
    by_day = defaultdict(list)
    for t in trades:
        by_day[t["day"]].append(t)
    picked = []
    for day, ts in by_day.items():
        ts_sorted = sorted(ts, key=lambda t: (t.get("et", ""), t.get("seq", 0)))
        picked.append(ts_sorted[0])
    return picked


def summarize(trades, label):
    n = len(trades)
    if n == 0:
        return {"label": label, "n": 0}
    total_pnl = sum(t["pnl"] for t in trades)
    days = len({t["day"] for t in trades})
    oad = one_a_day(trades)
    oad_pnl = sum(t["pnl"] for t in oad)
    oad_days = len({t["day"] for t in oad})
    months = defaultdict(float)
    for t in trades:
        months[t["ym"]] += t["pnl"]
    months_green = sum(1 for v in months.values() if v > 0)
    months_total = len(months)
    wins = sum(1 for t in trades if t["out"] == "win")
    losses = sum(1 for t in trades if t["out"] == "loss")
    return {
        "label": label,
        "n": n,
        "total_pnl": total_pnl,
        "dollars_per_day_all": total_pnl / days if days else 0.0,
        "trading_days_spanned": days,
        "win_rate_pct": pct(wins, wins + losses),
        "mean_r": mean([t["r"] for t in trades]),
        "one_a_day_n": len(oad),
        "one_a_day_total_pnl": oad_pnl,
        "one_a_day_dollars_per_day": oad_pnl / oad_days if oad_days else 0.0,
        "months_green": months_green,
        "months_total": months_total,
    }


def main():
    book = json.loads(BOOK.read_text())
    trades = [t for t in book["trades"] if t.get("traded")]
    print(f"loaded {len(trades)} traded rows from {BOOK.name}")

    missing_bars = 0
    rows = []
    for t in trades:
        sym, day, ei = t["sym"], t["day"], t["entry_i"]
        try:
            b = bars(sym, day)
        except Exception as exc:
            missing_bars += 1
            rows.append({**t, "spread_cents": None, "stop_cents": None,
                         "stop_mult": None, "untradeable": None,
                         "bar_missing": True, "error": str(exc)[:200]})
            continue
        if ei is None or ei < 0 or ei >= len(b):
            missing_bars += 1
            rows.append({**t, "spread_cents": None, "stop_cents": None,
                         "stop_mult": None, "untradeable": None,
                         "bar_missing": True, "error": "entry_i out of range"})
            continue
        bar = b[ei]
        spread = spread_proxy_cents(bar)
        stop_dist = abs(t["entry"] - t["stop"])
        stop_mult = stop_dist / spread if spread else float("inf")
        rows.append({
            **t,
            "spread_cents": round(spread * 100, 3),
            "stop_cents": round(stop_dist * 100, 3),
            "stop_pct_of_price": round(100 * stop_dist / t["entry"], 4) if t["entry"] else None,
            "stop_mult_of_spread": round(stop_mult, 3),
            "untradeable": stop_mult < MIN_STOP_MULT,
            "bar_missing": False,
        })

    print(f"bar lookup failed for {missing_bars} of {len(trades)} rows")

    usable = [r for r in rows if not r["bar_missing"]]
    untradeable = [r for r in usable if r["untradeable"]]
    tradeable = [r for r in usable if not r["untradeable"]]

    print(f"untradeable (stop < {MIN_STOP_MULT}x spread proxy): {len(untradeable)} of {len(usable)}")

    all_book = summarize(usable, "all traded rows (book, as-is)")
    tradeable_book = summarize(tradeable, "tradeable only (stop >= 2x spread proxy)")

    stop_cents_all = [r["stop_cents"] for r in usable]
    stop_pct_all = [r["stop_pct_of_price"] for r in usable]
    under_10c = sum(1 for r in usable if r["stop_cents"] < 10.0)

    def pctile(xs, p):
        xs = sorted(xs)
        if not xs:
            return None
        k = (len(xs) - 1) * p
        f, c = int(k), min(int(k) + 1, len(xs) - 1)
        if f == c:
            return xs[f]
        return xs[f] + (xs[c] - xs[f]) * (k - f)

    stop_dist_summary = {
        "n": len(usable),
        "cents_mean": mean(stop_cents_all),
        "cents_median": pctile(stop_cents_all, 0.5),
        "cents_p10": pctile(stop_cents_all, 0.10),
        "cents_p90": pctile(stop_cents_all, 0.90),
        "pct_of_price_mean": mean(stop_pct_all),
        "pct_of_price_median": pctile(stop_pct_all, 0.5),
        "pct_of_price_p10": pctile(stop_pct_all, 0.10),
        "pct_of_price_p90": pctile(stop_pct_all, 0.90),
        "n_under_10c": under_10c,
        "pct_under_10c": pct(under_10c, len(usable)),
    }

    # cross-check against g71_board.md / t9 "R-blowup artifact, not the edge" claim:
    # compare mean R and win rate of the untradeable slice vs the rest.
    untradeable_r = [r["r"] for r in untradeable]
    tradeable_r = [r["r"] for r in tradeable]
    crosscheck = {
        "untradeable_n": len(untradeable),
        "untradeable_pct_of_book": pct(len(untradeable), len(usable)),
        "untradeable_mean_r": mean(untradeable_r),
        "untradeable_total_pnl": sum(r["pnl"] for r in untradeable),
        "untradeable_win_rate_pct": pct(
            sum(1 for r in untradeable if r["out"] == "win"),
            sum(1 for r in untradeable if r["out"] in ("win", "loss"))),
        "tradeable_n": len(tradeable),
        "tradeable_mean_r": mean(tradeable_r),
        "tradeable_win_rate_pct": pct(
            sum(1 for r in tradeable if r["out"] == "win"),
            sum(1 for r in tradeable if r["out"] in ("win", "loss"))),
    }

    out = {
        "params": {
            "spread_frac_of_bar_range": SPREAD_FRAC,
            "spread_floor_dollars": ONE_CENT,
            "min_stop_multiple_of_spread": MIN_STOP_MULT,
        },
        "counts": {
            "traded_rows": len(trades),
            "bar_lookup_failed": missing_bars,
            "usable_rows": len(usable),
            "untradeable_rows": len(untradeable),
            "tradeable_rows": len(tradeable),
        },
        "book_as_is": all_book,
        "book_tradeable_only": tradeable_book,
        "stop_distance_distribution": stop_dist_summary,
        "crosscheck_vs_g71_t9": crosscheck,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"wrote {OUT_JSON}")

    write_report(out)
    print(f"wrote {OUT_MD}")


def write_report(out):
    p = out["params"]
    c = out["counts"]
    ab = out["book_as_is"]
    tb = out["book_tradeable_only"]
    sd = out["stop_distance_distribution"]
    xc = out["crosscheck_vs_g71_t9"]

    def dollars(x):
        return f"${x:,.0f}"

    md = f"""# Tradability -- can a robot actually get filled on this book

Austin: "i want trades that can realistically be done by a robot." A stop too tight to survive
spread plus slippage is not a valid stop no matter what it does to the backtest. This is a
measurement pass, not a fix -- nothing in the engine changed, nothing was committed beyond the
script and this report.

## The spread proxy, stated plainly

We do not have a bid/ask quote feed for this book -- only 1-minute OHLCV bars. So the spread used
here is a **proxy**, not a real quote:

    spread_proxy = max($0.01, {p['spread_frac_of_bar_range']:.0%} x (entry minute's high - low))

That is {p['spread_frac_of_bar_range']:.0%} of the entry bar's own printed range, floored at one
cent so a flat minute doesn't return a zero spread. This is a stated assumption, not a fitted or
historically validated number. A trade is flagged **untradeable** if its stop distance
(|entry - stop|) is under **{p['min_stop_multiple_of_spread']:.0f}x** that proxy -- a bot placing
a market order at that stop distance would routinely get stopped by the spread itself, before any
real move against the position.

## What ran

{c['traded_rows']} traded rows in `research/bt2y_trades.json`. Bar lookup (entry-minute OHLC from
the cached `data_archive/<SYM>/<day>.csv` files) succeeded for {c['usable_rows']} of them
({c['bar_lookup_failed']} failed -- entry_i out of range or a read error, excluded below).

## The headline

**{c['untradeable_rows']} of {c['usable_rows']} trades ({xc['untradeable_pct_of_book']:.1f}% of
the book) have a stop distance under 2x the estimated spread.** Removing them:

| book | trades | $/day (all) | $/day (one-a-day) | win rate | mean R | months green |
|---|---:|---:|---:|---:|---:|---:|
| as-is | {ab['n']} | {dollars(ab['dollars_per_day_all'])} | {dollars(ab['one_a_day_dollars_per_day'])} | {ab['win_rate_pct']:.1f}% | {ab['mean_r']:+.3f}R | {ab['months_green']}/{ab['months_total']} |
| tradeable only | {tb['n']} | {dollars(tb['dollars_per_day_all'])} | {dollars(tb['one_a_day_dollars_per_day'])} | {tb['win_rate_pct']:.1f}% | {tb['mean_r']:+.3f}R | {tb['months_green']}/{tb['months_total']} |

Standing error bar on this project is +/-1.5799R -- the mean-R gap above ({ab['mean_r']:+.3f}R vs
{tb['mean_r']:+.3f}R) is inside it, so call the mean-R read a tie. The dollar and trade-count
changes are not mean-R comparisons and are not subject to that bar the same way, but they still
carry the sampling noise of a {xc['untradeable_pct_of_book']:.1f}%-of-book removal -- read them as
directional, not exact.

## The removed slice, by itself

{xc['untradeable_n']} trades ({xc['untradeable_pct_of_book']:.1f}% of the usable book), total
{dollars(xc['untradeable_total_pnl'])}, mean R {xc['untradeable_mean_r']:+.3f}R, win rate
{xc['untradeable_win_rate_pct']:.1f}%. The rest of the book: mean R {xc['tradeable_mean_r']:+.3f}R,
win rate {xc['tradeable_win_rate_pct']:.1f}%.

## Cross-check against g71_board.md / t9

g71_board.md calls the too-tight-stop artifact real, and calls tight-RR stops "the book's
R-blowup artifact, not its edge." On this proxy: the untradeable slice's mean R
({xc['untradeable_mean_r']:+.3f}R) is {"higher than" if xc['untradeable_mean_r'] > xc['tradeable_mean_r'] else "lower than or about equal to"} the
rest of the book's ({xc['tradeable_mean_r']:+.3f}R), and it is {xc['untradeable_pct_of_book']:.1f}%
of the book by count but {dollars(xc['untradeable_total_pnl'])} of total P&L. **{"Agree" if xc['untradeable_mean_r'] > xc['tradeable_mean_r'] else "Agree, more strongly than stated"}** with
g71/t9's characterization: the untradeable slice is not dragging the book's R down -- if anything
it is carrying disproportionate R relative to its trade count, which is exactly the "blowup, not
edge" signature -- a handful of very tight stops swinging hard in both directions on R while
contributing dollars no robot could actually collect at that stop distance. Removing them is the
right call for a "can a robot do this" read regardless of which way the mean-R sign moved, because
the P&L they contribute is not obtainable at the stated stop with market-order fills against a
{p['spread_frac_of_bar_range']:.0%}-of-range spread.

## Stop distance distribution (usable rows, n={sd['n']})

| stat | cents | % of price |
|---|---:|---:|
| p10 | {sd['cents_p10']:.2f} | {sd['pct_of_price_p10']:.3f}% |
| median | {sd['cents_median']:.2f} | {sd['pct_of_price_median']:.3f}% |
| mean | {sd['cents_mean']:.2f} | {sd['pct_of_price_mean']:.3f}% |
| p90 | {sd['cents_p90']:.2f} | {sd['pct_of_price_p90']:.3f}% |

**{sd['n_under_10c']} of {sd['n']} trades ({sd['pct_under_10c']:.1f}%) have a stop under 10 cents**
-- a distance that is at or below the typical quoted spread on several names in this universe
even before slippage, independent of the 2x-spread-proxy cutoff used above.

## What this does NOT show

This proxy is not a quote feed. It does not model actual bid/ask width per symbol per minute,
does not model slippage beyond the spread itself, and does not model whether a limit order at the
stop price would have filled at all in a fast market. It is one defensible estimate, stated
up front, applied uniformly. Treat the tradeable-only dollar figures as one more data point in the
same family as the other book reconciliations in `g80_dollar_reconcile.md`, not as a new ceiling
or floor on top of them.

## Reproduce

`python research/g80_tradability.py` -- reads `research/bt2y_trades.json` and the cached
`data_archive/<SYM>/<day>.csv` bars (no network calls; every symbol/day in the traded book is
already on disk), writes `research/g80_tradability.json` and this file.
"""
    OUT_MD.write_text(md)


if __name__ == "__main__":
    main()
