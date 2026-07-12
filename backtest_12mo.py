"""Real 12-month unfiltered backtest on Polygon 1m data.

Reuses backtest_week's simulation engine verbatim (simulate_day = same signal
detection, grading, 2R sim, dedupe, 84% wiring) — only the data source swaps:
Polygon fetch_day (cache-first, Starter = unlimited) instead of yfinance.

hourly HTF bias is resampled from the 1m bars (last close per hour), so bias
matches fetch_htf_bias's SMA20-of-hourly logic without a second data pull.

Usage:
  python backtest_12mo.py [DAYS]              (default 365; core watchlist)
  python backtest_12mo.py --snapshot          (also copy charts/report to *_12mo)
  python backtest_12mo.py 365 --snapshot
"""
import argparse, shutil
from pathlib import Path
from collections import defaultdict
from datetime import date, datetime, timedelta

import polygon_feed as pf
from backtest_week import (SYMBOLS, simulate_day, write_report,
                           build_notes, htf_bias_for)

ROOT = Path(__file__).parent


def trading_days(n_back: int):
    out, d = [], date.today() - timedelta(days=1)
    start = date.today() - timedelta(days=n_back)
    while d >= start:
        if d.weekday() < 5:  # Mon-Fri (holidays fetch empty, skipped later)
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return sorted(out)


def hourly_from_1m(day_iso: str, bars) -> list:
    """(datetime, close) per hour bucket — last close wins. Matches htf_bias_for."""
    y, m, dd = map(int, day_iso.split("-"))
    by_hour = {}
    for c in bars:  # bars are RTH-order; last write per hour = hour's close
        h = int(c.timestamp[:2])
        by_hour[h] = c.close
    return [(datetime(y, m, dd, h), close) for h, close in sorted(by_hour.items())]


def qqq_level_breaks(days):
    """F4 Rule 4 input: {day: {"up": first RTH close above QQQ PDH/PMH,
    "dn": first below PDL/PML}} — times as HH:MM:SS, None if never broke."""
    day_bars = {}
    for d in days:
        try:
            bars = pf.fetch_day("QQQ", d)
        except Exception:
            continue
        if not bars:
            continue
        rth = pf.rth(bars)
        if len(rth) >= 30:
            day_bars[d] = (bars, rth)
    keys = sorted(day_bars)
    out = {}
    for prev, d in zip(keys, keys[1:]):
        _, prth = day_bars[prev]
        pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
        bars, rth = day_bars[d]
        pmh, pml = pf.premarket_hi_lo(bars)
        ups = [l for l in (pdh, pmh) if l is not None]
        dns = [l for l in (pdl, pml) if l is not None]
        out[d] = {
            "up": next((c.timestamp for c in rth if any(c.close > l for l in ups)), None),
            "dn": next((c.timestamp for c in rth if any(c.close < l for l in dns)), None),
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("days", nargs="?", type=int, default=365,
                    help="lookback days (default 365)")
    ap.add_argument("--snapshot", action="store_true",
                    help="copy backtest_charts.json -> _12mo.json and "
                         "backtest_report.md -> _12mo.md on completion")
    ap.add_argument("--entry-cutoff", default=None, metavar="HH:MM",
                    help="override entry cutoff time (default 11:00)")
    ap.add_argument("--skip-news", action="store_true",
                    help="exclude dates listed in news_days.json")
    args = ap.parse_args()

    # Override ENTRY_CUTOFF in backtest_week before the day loop — simulate_day
    # reads it as a module global there. Spec: module-level assignment is fine.
    if args.entry_cutoff:
        import backtest_week
        backtest_week.ENTRY_CUTOFF = f"{args.entry_cutoff}:00"

    news_days = set()
    if args.skip_news:
        import json
        try:
            nd = json.loads((ROOT / "news_days.json").read_text())
            news_days = set(nd.get("news_days", []))
        except (OSError, ValueError):
            pass

    n_back = args.days
    days = trading_days(n_back)
    if news_days:
        days = [d for d in days if d not in news_days]
    all_trades, seen_days, chart_records = [], set(), []
    qqq_brk = qqq_level_breaks(days)  # F4 [qqqA]/[qqqX] tag input
    print(f"QQQ key-level break times: {len(qqq_brk)} days")

    for sym in SYMBOLS:  # full 28-symbol watchlist 2026-07-11 (was CORE only)
        day_bars, hourly = {}, []
        for d in days:
            try:
                bars = pf.fetch_day(sym, d)  # premkt + RTH, cache-first
            except Exception as e:
                print(f"[{sym}] {d} fetch failed: {str(e)[:60]}")
                continue
            if not bars:
                continue  # holiday / no data
            rth = pf.rth(bars)
            if len(rth) < 30:
                continue
            day_bars[d] = (bars, rth)
            hourly += hourly_from_1m(d, rth)

        day_keys = sorted(day_bars)
        prev = None
        for d in day_keys:
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                  qqq=qqq_brk.get(d))
            all_trades.extend(trades)
            orh, orl = max(c.high for c in rth[:5]), min(c.low for c in rth[:5])
            levels = {k: v for k, v in [("PDH", pdh), ("PDL", pdl), ("PMH", pmh),
                                        ("PML", pml), ("ORH", orh), ("ORL", orl)]
                      if v is not None}
            for t in trades:
                if t.counted or t.is_alert:
                    lo, hi = max(0, t.entry_idx - 25), min(len(rth), t.exit_idx + 11)
                    chart_records.append({
                        "symbol": t.symbol, "day": t.day, "setup": t.signal_type,
                        "direction": t.direction, "grade": t.grade,
                        "alert_only": t.is_alert, "outcome": t.outcome,
                        "htf_bias": bias,
                        "entry": t.entry, "stop": t.stop, "target": t.target,
                        "exit_price": t.exit_price, "pnl": t.pnl,
                        "scaled": t.scaled,
                        "scale_level": t.scale_level, "runner_target": t.runner_target,
                        "entry_i": t.entry_idx - lo, "exit_i": t.exit_idx - lo,
                        "reason": t.reason, "levels": levels,
                        "candles": [{"t": c.timestamp[:5], "o": c.open, "h": c.high,
                                     "l": c.low, "c": c.close} for c in rth[lo:hi]],
                    })
            seen_days.add(d)
            prev = d
        fired = sum(1 for t in all_trades if t.counted and t.day in day_keys)
        print(f"[{sym}] {len(day_keys)} days, "
              f"{sum(1 for t in all_trades if t.symbol == sym)} signals")

    days_sorted = sorted(seen_days)
    notes = build_notes(all_trades)
    write_report(all_trades, days_sorted, notes)
    import json
    charts_path = ROOT / "backtest_charts.json"
    charts_path.write_text(json.dumps(chart_records), encoding="utf-8")
    if args.snapshot:
        shutil.copy2(charts_path, ROOT / "backtest_charts_12mo.json")
        shutil.copy2(ROOT / "backtest_report.md", ROOT / "backtest_report_12mo.md")
        print("  snapshot: backtest_charts_12mo.json + backtest_report_12mo.md written")
    print(f"\n{len(days_sorted)} sessions, {len(all_trades)} total signals, "
          f"{len(chart_records)} charted")
    for n_ in notes:
        print(f"  * {n_}")


if __name__ == "__main__":
    main()
