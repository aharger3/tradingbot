"""Regime-filter backtest: run OMEN's 12mo backtest through 4 regime variants and compare.

Usage:
    python backtest_regimes.py                    # full 12mo, all 4 regime modes
    python backtest_regimes.py --days 60          # shorter run for quick iteration
    python backtest_regimes.py --modes sma,vix    # specific modes only

Output: backtest_regime_report.md
"""

import sys
import json
from collections import defaultdict, OrderedDict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import polygon_feed as pf
from backtest_week import (CORE_SYMBOLS, simulate_day, build_notes, write_report,
                           htf_bias_for)
from market_data import fetch_spy_daily_closes, fetch_vix_daily
from regime_detector import (
    RegimeDetector, RegimeConfig,
    MODE_NONE, MODE_SMA, MODE_VIX, MODE_PNL,
    sma_config, vix_config, pnl_config,
    ACTION_NORMAL, ACTION_CAUTION, ACTION_STOP,
    ACTION_STOP_LONG, ACTION_STOP_SHORT,
)


# --- helpers ---

def _trading_days(n_back: int):
    out, d = [], date.today() - timedelta(days=1)
    start = date.today() - timedelta(days=n_back)
    while d >= start:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return sorted(out)


def _hourly_from_1m(day_iso: str, bars) -> list:
    """(datetime, close) per hour bucket — last close wins."""
    y, m, dd = map(int, day_iso.split("-"))
    by_hour = {}
    for c in bars:
        h = int(c.timestamp[:2])
        by_hour[h] = c.close
    return [(datetime(y, m, dd, h), close) for h, close in sorted(by_hour.items())]


# --- day-first P&L-aware backtest ---

def _run_pnl_mode(days: List[str], spy_closes: list, spy_dates: list,
                  vix_closes: list, vix_dates: list) -> dict:
    """P&L kill switch mode: day-first iteration with proper PDH/PDL tracking.

    Fetches all symbol data into a preload dict first, then iterates day-by-day
    so we can feed cumulative P&L back into the kill switch.
    """
    # Preload all data: {sym: {day_iso: (bars, rth)}}
    preload = {}
    for sym in CORE_SYMBOLS:
        sym_data = {}
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
            sym_data[d] = (bars, rth)
        if sym_data:
            preload[sym] = sym_data
        print(f"  Preloaded {sym}: {len(sym_data)} days", file=sys.stderr)

    detector = RegimeDetector(pnl_config())
    detector.feed_daily_closes(spy_dates, spy_closes)
    detector.feed_vix_closes(vix_dates, vix_closes)

    all_trades = []
    seen_days = set()
    stopped_days = 0
    pnl_per_day = {}  # day -> cumulative P&L across all symbols

    # Track prior-day levels per symbol
    prev_day_per_sym = {}

    for d in days:
        regime, action = detector.get_action(d)
        if action == ACTION_STOP:
            stopped_days += 1
            detector.record_daily_pnl(d, 0.0)
            continue

        day_pnl = 0.0
        day_has_data = False

        for sym in CORE_SYMBOLS:
            sym_data = preload.get(sym, {})
            if d not in sym_data:
                continue
            bars, rth = sym_data[d]
            day_has_data = True

            # PDH/PDL from previous trading day
            prev = prev_day_per_sym.get(sym)
            if prev:
                pdh = max(c.high for c in prev)
                pdl = min(c.low for c in prev)
            else:
                pdh = pdl = None

            pmh, pml = pf.premarket_hi_lo(bars)
            hourly = _hourly_from_1m(d, rth)
            bias = htf_bias_for(hourly, d)

            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml)

            # Directional filtering
            if action == ACTION_STOP_LONG:
                trades = [t for t in trades if t.direction != "call"]
            elif action == ACTION_STOP_SHORT:
                trades = [t for t in trades if t.direction != "put"]

            for t in trades:
                if t.counted:
                    day_pnl += t.pnl
            all_trades.extend(trades)
            seen_days.add(d)
            prev_day_per_sym[sym] = rth

        if day_has_data:
            detector.record_daily_pnl(d, day_pnl)
        else:
            detector.record_daily_pnl(d, 0.0)

    fired = [t for t in all_trades if t.counted]
    pnl_total = round(sum(t.pnl for t in fired), 2)
    notes = build_notes(all_trades)

    return {
        "trades": all_trades,
        "days_traded": sorted(seen_days),
        "notes": notes,
        "pnl": pnl_total,
        "n_fired": len(fired),
        "stopped_days": stopped_days,
    }


# --- standard symbol-first backtest (no P&L feedback) ---

def _run_sma_mode(days: List[str], spy_closes: list, spy_dates: list,
                  vix_closes: list, vix_dates: list) -> dict:
    """SMA crossover mode: standard symbol-first backtest."""
    return _run_symbol_first(MODE_SMA, sma_config(), days, spy_closes, spy_dates,
                             vix_closes, vix_dates)


def _run_sma_directional(days, spy_closes, spy_dates, vix_closes, vix_dates):
    """SMA directional: melt-up stops only longs, melt-down stops only shorts."""
    cfg = RegimeConfig(mode=MODE_SMA, directional=True,
                       melt_up_threshold=0.05, melt_down_threshold=-0.05)
    return _run_symbol_first(MODE_SMA, cfg, days, spy_closes, spy_dates,
                             vix_closes, vix_dates)


def _run_sma_tight(days, spy_closes, spy_dates, vix_closes, vix_dates):
    """SMA tight directional: 3% threshold, directional."""
    cfg = RegimeConfig(mode=MODE_SMA, directional=True,
                       melt_up_threshold=0.03, melt_down_threshold=-0.03)
    return _run_symbol_first(MODE_SMA, cfg, days, spy_closes, spy_dates,
                             vix_closes, vix_dates)


def _run_sma_moderate(days, spy_closes, spy_dates, vix_closes, vix_dates):
    """SMA moderate: 4% threshold, directional."""
    cfg = RegimeConfig(mode=MODE_SMA, directional=True,
                       melt_up_threshold=0.04, melt_down_threshold=-0.04)
    return _run_symbol_first(MODE_SMA, cfg, days, spy_closes, spy_dates,
                             vix_closes, vix_dates)


def _run_sma_aggressive(days, spy_closes, spy_dates, vix_closes, vix_dates):
    """SMA aggressive: 7% threshold, non-directional (stops both sides)."""
    cfg = RegimeConfig(mode=MODE_SMA, directional=False,
                       melt_up_threshold=0.07, melt_down_threshold=-0.07)
    return _run_symbol_first(MODE_SMA, cfg, days, spy_closes, spy_dates,
                             vix_closes, vix_dates)


def _run_vix_mode(days: List[str], spy_closes: list, spy_dates: list,
                  vix_closes: list, vix_dates: list) -> dict:
    """VIX regime mode: standard symbol-first backtest."""
    return _run_symbol_first(MODE_VIX, vix_config(), days, spy_closes, spy_dates,
                             vix_closes, vix_dates)


def _run_symbol_first(mode: str, cfg: RegimeConfig, days: List[str],
                      spy_closes: list, spy_dates: list,
                      vix_closes: list, vix_dates: list) -> dict:
    """Standard symbol-first iteration (no P&L feedback). Used for SMA and VIX modes."""
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
            hourly += _hourly_from_1m(d, rth)

        day_keys = sorted(day_bars)
        prev = None
        for d in day_keys:
            regime, action = detector.get_action(d)
            if action == ACTION_STOP:
                stopped_days += 1
                prev = d  # still advance PDH/PDL
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

            # Directional filtering: filter trades by regime action
            if action == ACTION_STOP_LONG:
                trades = [t for t in trades if t.direction != "call"]
            elif action == ACTION_STOP_SHORT:
                trades = [t for t in trades if t.direction != "put"]

            all_trades.extend(trades)
            seen_days.add(d)
            prev = d

    fired = [t for t in all_trades if t.counted]
    pnl_total = round(sum(t.pnl for t in fired), 2)
    notes = build_notes(all_trades)

    return {
        "trades": all_trades,
        "days_traded": sorted(seen_days),
        "notes": notes,
        "pnl": pnl_total,
        "n_fired": len(fired),
        "stopped_days": stopped_days,
    }


# --- mode registry ---

MODE_LABELS = OrderedDict([
    (MODE_NONE, "No Filter (Baseline)"),
    (MODE_SMA, "SPY SMA50/200 Crossover (5%, non-directional)"),
    ("sma_directional", "SMA Directional (5%, stop only wrong side)"),
    ("sma_tight_directional", "SMA Directional (3%, stop only wrong side)"),
    ("sma_moderate_directional", "SMA Directional (4%, stop only wrong side)"),
    ("sma_aggressive", "SMA Aggressive (7%, non-directional, both sides)"),
    (MODE_VIX, "VIX Regime (low<14, high>25, panic>35)"),
    (MODE_PNL, "Rolling 5-day P&L Kill Switch"),
])

MODE_DESCRIPTIONS = {
    MODE_NONE: "OMEN as-is. All A+/A/B trades execute regardless of market regime.",
    MODE_SMA: "STOP trading when SPY price >5% above SMA50 (melt-up) or >5% below (melt-down). Stops all trades regardless of direction.",
    "sma_directional": "Same as SMA, but melt-up only stops CALL (long) trades; melt-down only stops PUT (short) trades.",
    "sma_tight_directional": "Directional SMA at 3% threshold. Stops the wrong-direction trades sooner.",
    "sma_moderate_directional": "Directional SMA at 4% threshold. Balanced between tight and standard.",
    "sma_aggressive": "Non-directional SMA at 7% threshold. Only stops on extreme conditions.",
    MODE_VIX: "STOP all trades when VIX >35 (panic). CAUTION when VIX >25 (high vol) or VIX <14 (melt-up / complacency).",
    MODE_PNL: "STOP trading when trailing 5-day aggregate P&L is negative. Resume when it turns positive again.",
}

RUNNERS = {
    MODE_NONE: None,
    MODE_SMA: _run_sma_mode,
    "sma_directional": _run_sma_directional,
    "sma_tight_directional": _run_sma_tight,
    "sma_moderate_directional": _run_sma_moderate,
    "sma_aggressive": _run_sma_aggressive,
    MODE_VIX: _run_vix_mode,
    MODE_PNL: _run_pnl_mode,
}


# --- baseline (no filter) ---

def _run_baseline(days: List[str], spy_closes, spy_dates, vix_closes, vix_dates):
    """Baseline: symbol-first, no regime filter."""
    return _run_symbol_first(MODE_NONE, RegimeConfig(mode=MODE_NONE), days,
                             spy_closes, spy_dates, vix_closes, vix_dates)


# --- main ---

def main():
    n_back = 365
    modes_to_run = list(RUNNERS.keys())
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg.startswith("--modes="):
            modes_to_run = [m.strip() for m in arg.split("=", 1)[1].split(",")]
        elif arg == "--days" and i < len(sys.argv):
            n_back = int(sys.argv[i + 1])

    # Default: run SMA variants + baseline only (VIX and P&L take much longer)
    if len(sys.argv) == 1:
        modes_to_run = [MODE_NONE, MODE_SMA, "sma_directional",
                        "sma_tight_directional", "sma_moderate_directional",
                        "sma_aggressive"]

    days = _trading_days(n_back)
    print(f"Regime backtest: {len(days)} trading days ({days[0]} to {days[-1]})")
    print(f"Modes: {', '.join(modes_to_run)}")

    # 1. Fetch SPY daily data from cached Polygon
    print("\nFetching SPY daily closes from Polygon cache...")
    spy_raw = fetch_spy_daily_closes(days_back=n_back + 60)
    spy_dates = sorted(d for d in spy_raw if d <= days[-1])
    spy_closes = [spy_raw[d] for d in spy_dates if d in spy_raw]
    print(f"  SPY: {len(spy_dates)} daily closes")
    if spy_closes:
        print(f"  Range: ${spy_closes[0]:.2f} to ${spy_closes[-1]:.2f}")

    # 2. Fetch VIX daily data from Polygon cache
    print("Fetching VIX daily closes from Polygon cache...")
    vix_raw = fetch_vix_daily(days_back=n_back + 60)
    vix_dates = sorted(d for d in vix_raw if d <= days[-1])
    vix_closes = [vix_raw[d] for d in vix_dates if d in vix_raw]
    print(f"  VIX: {len(vix_dates)} daily closes")
    if vix_closes:
        print(f"  Range: {min(vix_closes):.1f} to {max(vix_closes):.1f}")

    # 3. Run baseline
    print("\n--- BASELINE: No regime filter ---")
    baseline = _run_baseline(days, spy_closes, spy_dates, vix_closes, vix_dates)
    base_pnl = baseline["pnl"]
    base_fired = baseline["n_fired"]
    base_days = len(baseline["days_traded"])
    base_w = sum(1 for t in baseline["trades"] if t.counted and t.outcome == "win")
    base_l = sum(1 for t in baseline["trades"] if t.counted and t.outcome == "loss")
    base_wr = round(base_w / (base_w + base_l) * 100, 1) if (base_w + base_l) else 0
    print(f"  P&L: ${base_pnl:,.2f} ({base_fired} trades, {base_wr}% WR, {base_days} days traded)")

    # 4. Run each regime mode
    results = {MODE_NONE: baseline}
    for mode in [m for m in modes_to_run if m != MODE_NONE]:
        label = MODE_LABELS.get(mode, mode)
        print(f"\n--- {label} ---")
        runner_fn = RUNNERS[mode]
        if runner_fn is None:
            continue
        result = runner_fn(days, spy_closes, spy_dates, vix_closes, vix_dates)
        results[mode] = result

        r_pnl = result["pnl"]
        r_fired = result["n_fired"]
        r_days = len(result["days_traded"])
        r_w = sum(1 for t in result["trades"] if t.counted and t.outcome == "win")
        r_l = sum(1 for t in result["trades"] if t.counted and t.outcome == "loss")
        r_wr = round(r_w / (r_w + r_l) * 100, 1) if (r_w + r_l) else 0
        delta = r_pnl - base_pnl
        pct_improve = round(delta / abs(base_pnl) * 100, 1) if base_pnl != 0 else 0
        print(f"  P&L: ${r_pnl:,.2f} (vs baseline ${base_pnl:,.2f} = ${delta:+,.2f}, {pct_improve:+.1f}%)")
        print(f"  {r_fired} trades ({r_wr}% WR), {r_days} days traded, {result['stopped_days']} days stopped")

    # 5. Generate comparison report
    _write_report(results, days, spy_closes, spy_dates, vix_closes, vix_dates)

    # Print summary line
    print("\n" + "=" * 70)
    print("ORDERED BY IMPROVEMENT:")
    ranked = sorted(
        [(m, results[m]) for m in results if m in MODE_LABELS],
        key=lambda x: x[1]["pnl"], reverse=True
    )
    for mode, res in ranked:
        delta = res["pnl"] - base_pnl
        print(f"  {MODE_LABELS[mode]:40s} ${res['pnl']:>8,.2f}  (${delta:+,.2f})")
    print("=" * 70)


def _write_report(results: dict, days: list,
                  spy_closes: list, spy_dates: list,
                  vix_closes: list, vix_dates: list):
    base = results.get(MODE_NONE)
    base_pnl = base["pnl"] if base else 0

    lines = [
        f"# Regime Filter Comparison — {len(days)} trading days",
        f"**Period:** {days[0]} to {days[-1]}",
        f"**Symbols:** {', '.join(CORE_SYMBOLS)}",
        f"**Risk per trade:** $1,000, 2R target",
        "",
        "## Overview",
        "OMEN's 12-month backtest shows positive returns in trending markets but bleeds",
        "in melt-ups (sharp rallies with no retracement). This report compares three",
        "regime detection filters against the unfiltered baseline.",
        "",
        "| # | Mode | P&L | Change | Trades | WR | Days Traded | Days Stopped |",
        "|---|------|-----|--------|--------|----|-------------|--------------|",
    ]

    for i, (mode, res) in enumerate(sorted(
        [(m, results[m]) for m in results if m in MODE_LABELS],
        key=lambda x: x[1]["pnl"], reverse=True
    )):
        label = MODE_LABELS.get(mode, mode)
        pnl = res["pnl"]
        delta = pnl - base_pnl
        fired = res["n_fired"]
        dt = len(res["days_traded"])
        sd = res.get("stopped_days", 0)
        w = sum(1 for t in res["trades"] if t.counted and t.outcome == "win")
        l = sum(1 for t in res["trades"] if t.counted and t.outcome == "loss")
        wr = round(w / (w + l) * 100, 1) if (w + l) else 0
        pct = round(delta / abs(base_pnl) * 100, 1) if base_pnl else 0
        lines.append(f"| {i + 1} | {label} | ${pnl:,.2f} | ${delta:+,.2f} ({pct:+.1f}%) | {fired} | {wr}% | {dt} | {sd} |")

    lines += [
        "",
        "## Per-Mode Details",
        "",
    ]

    for mode, res in results.items():
        if mode not in MODE_LABELS:
            continue
        label = MODE_LABELS[mode]
        desc = MODE_DESCRIPTIONS[mode]
        cfg_desc = _cfg_desc(mode)
        lines += [
            f"### {label}",
            f"**Description:** {desc}",
            f"**Configuration:** {cfg_desc}",
            f"**P&L:** ${res['pnl']:,.2f} | **{res['n_fired']} trades** | "
            f"**{res.get('stopped_days', 0)} days halted**",
            "",
        ]
        # By setup breakdown
        fired = [t for t in res["trades"] if t.counted]
        by_setup = defaultdict(list)
        for t in fired:
            by_setup[t.signal_type].append(t)
        lines += ["| Setup | Signals | W | L | Win Rate | P&L |",
                   "|-------|---------|---|---|----------|-----|"]
        for st in sorted(by_setup):
            sts = by_setup[st]
            n = len(sts)
            w = sum(1 for t in sts if t.outcome == "win")
            l = sum(1 for t in sts if t.outcome == "loss")
            wr = round(w / (w + l) * 100, 1) if (w + l) else 0
            pnl = round(sum(t.pnl for t in sts), 2)
            lines.append(f"| {st} | {n} | {w} | {l} | {wr}% | ${pnl} |")
        lines.append("")

    # Market context
    if spy_dates and spy_closes:
        lines += [
            "## Market Context",
            "### SPY Daily Closes",
            "",
            "| Period | SPY Start | SPY End | Change |",
            "|--------|-----------|---------|--------|",
        ]
        if len(spy_closes) >= 2:
            start_p = spy_closes[0]
            end_p = spy_closes[-1]
            chg = (end_p - start_p) / start_p * 100
            lines.append(f"| {spy_dates[0]}–{spy_dates[-1]} | ${start_p:.2f} | ${end_p:.2f} | {chg:+.1f}% |")
        lines.append("")

    if vix_dates and vix_closes:
        vals = [v for v in vix_closes if v is not None]
        if vals:
            lines += [
                "### VIX Statistics",
                "",
                "| Stat | Value |",
                "|------|-------|",
                f"| Min VIX | {min(vals):.1f} |",
                f"| Max VIX | {max(vals):.1f} |",
                f"| Avg VIX | {sum(vals) / len(vals):.1f} |",
                f"| Days VIX < 14 | {sum(1 for v in vals if v < 14)} |",
                f"| Days VIX > 25 | {sum(1 for v in vals if v > 25)} |",
                f"| Days VIX > 35 | {sum(1 for v in vals if v > 35)} |",
                "",
            ]

    text = "\n".join(lines)
    report_path = Path(__file__).parent / "backtest_regime_report.md"
    report_path.write_text(text, encoding="utf-8")
    print(f"\nReport -> {report_path}")


def _cfg_desc(mode: str) -> str:
    from regime_detector import (
        DEFAULT_SMA_FAST, DEFAULT_SMA_SLOW, DEFAULT_MELT_UP_THRESHOLD,
        DEFAULT_MELT_DOWN_THRESHOLD, DEFAULT_CHOP_BAND,
        DEFAULT_VIX_LOW, DEFAULT_VIX_HIGH, DEFAULT_VIX_PANIC,
        DEFAULT_PNL_WINDOW, DEFAULT_PNL_THRESHOLD,
    )
    if mode == MODE_SMA:
        return (f"SMA{DEFAULT_SMA_FAST}/{DEFAULT_SMA_SLOW}, "
                f"melt-up >{DEFAULT_MELT_UP_THRESHOLD*100:.0f}%, "
                f"melt-down <{DEFAULT_MELT_DOWN_THRESHOLD*100:.0f}%, "
                f"chop band ±{DEFAULT_CHOP_BAND*100:.1f}%")
    if mode == MODE_VIX:
        return (f"Low <{DEFAULT_VIX_LOW}, High >{DEFAULT_VIX_HIGH}, "
                f"Panic >{DEFAULT_VIX_PANIC}")
    if mode == MODE_PNL:
        return f"Window {DEFAULT_PNL_WINDOW}d, threshold ${DEFAULT_PNL_THRESHOLD}"
    return "N/A"


if __name__ == "__main__":
    main()
