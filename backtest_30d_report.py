"""Full 30-day report + chart dump from the sweep's data cache (no refetch).

Usage: python backtest_30d_report.py [--days 29]
"""

import json
import sys
from datetime import date, timedelta

import backtest_week
from backtest_week import htf_bias_for, simulate_day, write_report, build_notes, REPORT_PATH
from backtest_sweep import load_data


def main():
    days = 29
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    week_start = (date.today() - timedelta(days=days)).isoformat()
    week_end = (date.today() - timedelta(days=1)).isoformat()

    data = load_data(days)
    all_trades, chart_records, seen_days = [], [], set()
    for sym, d in data.items():
        day_keys = sorted(d["days"].keys())
        prev_day = None
        for dy in day_keys:
            candles = d["days"][dy]
            if week_start <= dy <= week_end and len(candles) >= 30:
                if prev_day:
                    pc = d["days"][prev_day]
                    pdh, pdl = max(c.high for c in pc), min(c.low for c in pc)
                else:
                    pdh = pdl = None
                pmh, pml = d.get("premkt", {}).get(dy, (None, None))
                trades = simulate_day(sym, dy, candles, pdh, pdl,
                                      htf_bias_for(d["hourly"], dy), pmh, pml)
                all_trades.extend(trades)
                seen_days.add(dy)
                orh = max(c.high for c in candles[:5])
                orl = min(c.low for c in candles[:5])
                levels = {k: v for k, v in [("PDH", pdh), ("PDL", pdl), ("PMH", pmh),
                                            ("PML", pml), ("ORH", orh), ("ORL", orl)]
                          if v is not None}
                for t in trades:
                    if t.counted or t.is_alert:
                        lo, hi = max(0, t.entry_idx - 25), min(len(candles), t.exit_idx + 11)
                        chart_records.append({
                            "symbol": t.symbol, "day": t.day, "setup": t.signal_type,
                            "direction": t.direction, "grade": t.grade,
                            "alert_only": t.is_alert, "outcome": t.outcome,
                            "entry": t.entry, "stop": t.stop, "target": t.target,
                            "exit_price": t.exit_price, "pnl": t.pnl,
                            "entry_i": t.entry_idx - lo, "exit_i": t.exit_idx - lo,
                            "reason": t.reason, "levels": levels,
                            "candles": [{"t": c.timestamp[:5], "o": c.open, "h": c.high,
                                         "l": c.low, "c": c.close} for c in candles[lo:hi]],
                        })
            prev_day = dy

    notes = build_notes(all_trades)
    write_report(all_trades, sorted(seen_days), notes)
    REPORT_PATH.with_name("backtest_charts.json").write_text(
        json.dumps(chart_records), encoding="utf-8")
    print(f"{len(all_trades)} signals, {len(chart_records)} chart records")
    for n in notes:
        print(f"  * {n}")


if __name__ == "__main__":
    main()
