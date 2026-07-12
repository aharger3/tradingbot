"""24-month regime backtest — run all modes and compare Y1 vs Y2 P&L.

Usage: python backtest_regimes_24mo.py
"""

import sys
sys.path.insert(0, ".")
from collections import defaultdict, OrderedDict
from datetime import date, datetime, timedelta
from typing import Optional

import polygon_feed as pf
from backtest_week import CORE_SYMBOLS, simulate_day, build_notes, htf_bias_for
from market_data import fetch_spy_daily_closes, fetch_vix_daily
from regime_detector import (
    RegimeDetector, RegimeConfig,
    MODE_NONE, MODE_SMA, MODE_VIX, MODE_PNL,
    ACTION_NORMAL, ACTION_CAUTION, ACTION_STOP,
    ACTION_STOP_LONG, ACTION_STOP_SHORT,
)


def trading_days(n_back: int):
    out, d = [], date.today() - timedelta(days=1)
    start = date.today() - timedelta(days=n_back)
    while d >= start:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return sorted(out)


def hourly_from_1m(day_iso: str, bars) -> list:
    y, m, dd = map(int, day_iso.split("-"))
    by_hour = {}
    for c in bars:
        h = int(c.timestamp[:2])
        by_hour[h] = c.close
    return [(datetime(y, m, dd, h), close) for h, close in sorted(by_hour.items())]


def run_symbol_first(cfg: RegimeConfig, days, spy_closes, spy_dates,
                     vix_closes, vix_dates, label=""):
    """Symbol-first backtest (fast). Used for SMA and VIX modes."""
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

            all_trades.extend(trades)
            seen_days.add(d)
            prev = d
        print(f"  [{label}] {sym}: done", file=sys.stderr)

    fired = [t for t in all_trades if t.counted]
    pnl_total = round(sum(t.pnl for t in fired), 2)
    calls = [t for t in fired if t.direction == "call"]
    puts = [t for t in fired if t.direction == "put"]

    return {
        "trades": all_trades,
        "days_traded": sorted(seen_days),
        "pnl": pnl_total,
        "n_fired": len(fired),
        "stopped_days": stopped_days,
        "call_pnl": round(sum(t.pnl for t in calls), 2),
        "put_pnl": round(sum(t.pnl for t in puts), 2),
        "call_n": len(calls),
        "put_n": len(puts),
    }


def run_baseline(days, spy_closes, spy_dates, vix_closes, vix_dates):
    return run_symbol_first(RegimeConfig(mode=MODE_NONE), days,
                            spy_closes, spy_dates, vix_closes, vix_dates, "baseline")


# ---- mode configs ----

MODES = OrderedDict([
    ("none", ("No Filter (Baseline)", RegimeConfig(mode=MODE_NONE))),
    ("sma_directional_5", ("SMA Directional (5%)",
        RegimeConfig(mode=MODE_SMA, directional=True, melt_up_threshold=0.05, melt_down_threshold=-0.05))),
    ("sma_directional_4", ("SMA Directional (4%)",
        RegimeConfig(mode=MODE_SMA, directional=True, melt_up_threshold=0.04, melt_down_threshold=-0.04))),
    ("sma_directional_3", ("SMA Directional (3%)",
        RegimeConfig(mode=MODE_SMA, directional=True, melt_up_threshold=0.03, melt_down_threshold=-0.03))),
    ("sma_aggressive_7", ("SMA Aggressive (7%, both sides)",
        RegimeConfig(mode=MODE_SMA, directional=False, melt_up_threshold=0.07, melt_down_threshold=-0.07))),
    ("vix", ("VIX Regime",
        RegimeConfig(mode=MODE_VIX, vix_low=14, vix_high=25, vix_panic=35))),
    ("vix_low_only", ("VIX Low-Vol Only (STOP long when VIX<14)",
        RegimeConfig(mode=MODE_VIX, vix_low=14, vix_high=99, vix_panic=99))),
])


def main():
    n_back = 730
    days = trading_days(n_back)
    mid = days[len(days) // 2]
    y1 = [d for d in days if d < mid]
    y2 = [d for d in days if d >= mid]

    print(f"24mo: {len(days)} trading days ({days[0]} to {days[-1]})")
    print(f"Year 1: {len(y1)} days ({days[0]} to {y1[-1]})")
    print(f"Year 2: {len(y2)} days ({y2[0]} to {days[-1]})")

    # Fetch SPY daily closes
    print("\nFetching SPY daily closes...")
    spy_raw = fetch_spy_daily_closes(days_back=n_back + 60)
    spy_dates = sorted(d for d in spy_raw)
    spy_closes = [spy_raw[d] for d in spy_dates if d in spy_raw]
    print(f"  SPY: {len(spy_dates)} daily closes (${spy_closes[0]:.2f} to ${spy_closes[-1]:.2f})")

    # Fetch VIX daily closes
    print("Fetching VIX daily closes...")
    vix_raw = fetch_vix_daily(days_back=n_back + 60)
    vix_dates = sorted(d for d in vix_raw)
    vix_closes = [vix_raw[d] for d in vix_dates if d in vix_raw]
    if vix_closes:
        print(f"  VIX: {len(vix_dates)} daily closes ({min(vix_closes):.1f} to {max(vix_closes):.1f})")

    # Run baseline
    print("\n=== BASELINE ===")
    base = run_baseline(days, spy_closes, spy_dates, vix_closes, vix_dates)
    base_pnl = base["pnl"]
    print(f"  Total: ${base_pnl:,.2f} ({base['n_fired']} trades)")
    print(f"  Calls: ${base['call_pnl']:,.2f} ({base['call_n']}) | Puts: ${base['put_pnl']:,.2f} ({base['put_n']})")

    # Run each mode for full 24mo
    results = {"none": base}
    for mode_key, (label, cfg) in MODES.items():
        if mode_key == "none":
            continue
        print(f"\n=== {label} ===")
        result = run_symbol_first(cfg, days, spy_closes, spy_dates,
                                  vix_closes, vix_dates, label)
        results[mode_key] = result
        delta = result["pnl"] - base_pnl
        pct = round(delta / abs(base_pnl) * 100, 1) if base_pnl else 0
        print(f"  Total: ${result['pnl']:,.2f} (Δ ${delta:+,.2f}, {pct:+.1f}%)")
        print(f"  Calls: ${result['call_pnl']:,.2f} ({result['call_n']}) | Puts: ${result['put_pnl']:,.2f} ({result['put_n']})")
        print(f"  {result['n_fired']} trades, {result['stopped_days']} days stopped")

    # Print summary
    print("\n" + "=" * 70)
    print("24-MONTH REGIME COMPARISON:")
    print(f"{'Mode':<40s} {'Total P&L':>10s}  {'Δ vs Base':>10s}  {'Calls':>10s}  {'Puts':>10s}")
    print("-" * 70)
    ranked = sorted([(k, results[k]) for k in results],
                    key=lambda x: x[1]["pnl"], reverse=True)
    for k, r in ranked:
        label = MODES[k][0] if k in MODES else "???"
        delta = r["pnl"] - base_pnl
        print(f"{label:<40s} ${r['pnl']:>8,.2f}  ${delta:>+8,.2f}  ${r['call_pnl']:>8,.2f}  ${r['put_pnl']:>8,.2f}")
    print("=" * 70)

    # Year-by-year for the best mode
    print("\n\n=== YEAR-BY-YEAR (top 3 modes) ===")
    top3 = [k for k, _ in ranked[:4] if k != "none"]
    for mode_key in top3:
        cfg = MODES[mode_key][1]
        print(f"\n--- {MODES[mode_key][0]} ---")
        for label, dset in [("Year 1 (oldest)", y1), ("Year 2 (recent)", y2)]:
            r = run_symbol_first(cfg, dset, spy_closes, spy_dates,
                                 vix_closes, vix_dates, f"{mode_key}/{label}")
            base_r = run_baseline(dset, spy_closes, spy_dates, vix_closes, vix_dates)
            delta = r["pnl"] - base_r["pnl"]
            print(f"  {label}: Total ${r['pnl']:>8,.2f} (base ${base_r['pnl']:>8,.2f}, Δ ${delta:+,.2f})")


if __name__ == "__main__":
    main()