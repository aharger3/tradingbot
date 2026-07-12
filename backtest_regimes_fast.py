"""24-month regime backtest — SMA directional 5% vs directional P&L kill switch.

Lean: only the 3 most promising modes. Saves ~5x by not repeating full runs.
"""
import sys
sys.path.insert(0, ".")
from collections import defaultdict, OrderedDict
from datetime import date, datetime, timedelta

import polygon_feed as pf
from backtest_week import CORE_SYMBOLS, simulate_day, htf_bias_for
from market_data import fetch_spy_daily_closes, fetch_vix_daily
from regime_detector import (
    RegimeDetector, RegimeConfig,
    MODE_NONE, MODE_SMA, MODE_PNL_DIRECTIONAL,
    ACTION_NORMAL, ACTION_STOP, ACTION_STOP_LONG, ACTION_STOP_SHORT,
)


def trading_days(n_back):
    out, d = [], date.today() - timedelta(days=1)
    start = date.today() - timedelta(days=n_back)
    while d >= start:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return sorted(out)


def hourly_from_1m(day_iso, bars):
    y, m, dd = map(int, day_iso.split("-"))
    by_hour = {}
    for c in bars:
        h = int(c.timestamp[:2])
        by_hour[h] = c.close
    return [(datetime(y, m, dd, h), close) for h, close in sorted(by_hour.items())]


def run_symbol_first(cfg, days, spy_closes, spy_dates, vix_closes, vix_dates, label=""):
    """Symbol-first backtest."""
    detector = RegimeDetector(cfg)
    detector.feed_daily_closes(spy_dates, spy_closes)
    detector.feed_vix_closes(vix_dates, vix_closes)

    all_trades = []
    seen_days = set()
    stopped_days = 0

    for sym in CORE_SYMBOLS:
        day_bars, hourly = {}, []
        for d in days:
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            rth = pf.rth(bars)
            if len(rth) < 30:
                continue
            day_bars[d] = (bars, rth)
            hourly += hourly_from_1m(d, rth)

        day_keys = sorted(day_bars)
        prev = None
        for d in day_keys:
            regime, action = detector.get_action(d)
            if action == ACTION_STOP:
                stopped_days += 1
                prev = d
                continue

            bars, rth = day_bars[d]
            pdh = pdl = None
            if prev and prev in day_bars:
                _, prth = day_bars[prev]
                pdh = max(c.high for c in prth) if prth else None
                pdl = min(c.low for c in prth) if prth else None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml)

            if action == ACTION_STOP_LONG:
                trades = [t for t in trades if t.direction != "call"]
            elif action == ACTION_STOP_SHORT:
                trades = [t for t in trades if t.direction != "put"]

            # Feed directional P&L for the kill switch mode
            if cfg.mode == MODE_PNL_DIRECTIONAL:
                day_calls = sum(t.pnl for t in trades if t.counted and t.direction == "call")
                day_puts = sum(t.pnl for t in trades if t.counted and t.direction == "put")
                detector.record_daily_directional_pnl(d, day_calls, day_puts)

            all_trades.extend(trades)
            seen_days.add(d)
            prev = d
        print(f"  [{label}] {sym}: {len(day_keys)}d", file=sys.stderr)

    fired = [t for t in all_trades if t.counted]
    calls = [t for t in fired if t.direction == "call"]
    puts = [t for t in fired if t.direction == "put"]

    return {
        "pnl": round(sum(t.pnl for t in fired), 2),
        "n_fired": len(fired),
        "stopped_days": stopped_days,
        "call_pnl": round(sum(t.pnl for t in calls), 2),
        "put_pnl": round(sum(t.pnl for t in puts), 2),
        "call_n": len(calls),
        "put_n": len(puts),
    }


def main():
    n_back = 730
    days = trading_days(n_back)
    mid = days[len(days) // 2]
    y1 = [d for d in days if d < mid]
    y2 = [d for d in days if d >= mid]

    print(f"24mo: {len(days)}d ({days[0]} to {days[-1]})")

    # Fetch data
    print("Fetching SPY/VIX...")
    spy_raw = fetch_spy_daily_closes(days_back=n_back + 60)
    spy_dates = sorted(d for d in spy_raw)
    spy_closes = [spy_raw[d] for d in spy_dates if d in spy_raw]
    vix_raw = fetch_vix_daily(days_back=n_back + 60)
    vix_dates = sorted(d for d in vix_raw)
    vix_closes = [vix_raw[d] for d in vix_dates if d in vix_raw]

    # 3 modes
    configs = OrderedDict([
        ("baseline", RegimeConfig(mode=MODE_NONE)),
        ("SMA directional 5%", RegimeConfig(mode=MODE_SMA, directional=True, melt_up_threshold=0.05, melt_down_threshold=-0.05)),
        ("directional P&L 5d", RegimeConfig(mode=MODE_PNL_DIRECTIONAL, pnl_window=5, pnl_threshold=0)),
    ])

    results = {}
    for key, cfg in configs.items():
        print(f"\n=== {key} (24mo) ===")
        r = run_symbol_first(cfg, days, spy_closes, spy_dates, vix_closes, vix_dates, key)
        results[key] = r
        print(f"  Total: ${r['pnl']:>8,.2f} | Calls: ${r['call_pnl']:>8,.2f} ({r['call_n']}) | Puts: ${r['put_pnl']:>8,.2f} ({r['put_n']}) | {r['n_fired']} trades, {r['stopped_days']} stopped")

    print("\n" + "=" * 70)
    print("SUMMARY (24mo)")
    base = results["baseline"]["pnl"]
    for key, r in results.items():
        delta = r["pnl"] - base
        print(f"  {key:<30s} ${r['pnl']:>8,.2f}  Δ ${delta:>+8,.2f}")

    print("\n\n=== YEAR-BY-YEAR ===")
    for key, cfg in configs.items():
        print(f"\n--- {key} ---")
        for label, dset in [("Year 1", y1), ("Year 2", y2)]:
            r = run_symbol_first(cfg, dset, spy_closes, spy_dates, vix_closes, vix_dates, f"{key}/{label}")
            base_r = run_symbol_first(RegimeConfig(mode=MODE_NONE), dset, spy_closes, spy_dates, vix_closes, vix_dates, f"baseline/{label}")
            delta = r["pnl"] - base_r["pnl"]
            print(f"  {label}: Total ${r['pnl']:>8,.2f} (base ${base_r['pnl']:>8,.2f}, Δ ${delta:+,.2f}) | "
                  f"Calls ${r['call_pnl']:>8,.2f} Puts ${r['put_pnl']:>8,.2f}")


if __name__ == "__main__":
    main()