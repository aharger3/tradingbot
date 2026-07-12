"""Quick check: run baseline over 24mo to see year-1 vs year-2 P&L split."""
import sys
sys.path.insert(0, ".")
from collections import defaultdict
from datetime import date, timedelta
import polygon_feed as pf
from backtest_week import simulate_day, htf_bias_for

CORE_SYMBOLS = ["TSLA", "NVDA", "AAPL", "AMD", "META",
                "GOOGL", "AMZN", "MSFT", "PLTR", "SPY", "QQQ"]


def _hourly_from_1m(day_iso, bars):
    from datetime import datetime
    y, m, dd = map(int, day_iso.split("-"))
    by_hour = {}
    for c in bars:
        h = int(c.timestamp[:2])
        by_hour[h] = c.close
    return [(datetime(y, m, dd, h), close) for h, close in sorted(by_hour.items())]


def trading_days(n_back):
    out, d = [], date.today() - timedelta(days=1)
    start = date.today() - timedelta(days=n_back)
    while d >= start:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return sorted(out)


def main():
    days = trading_days(730)
    print(f"24mo: {len(days)} trading days ({days[0]} to {days[-1]})")

    # Split into two 12-month periods
    mid = days[len(days) // 2]
    y1 = [d for d in days if d < mid]
    y2 = [d for d in days if d >= mid]
    print(f"Year 1: {len(y1)} days ({days[0]} to {y1[-1]})")
    print(f"Year 2: {len(y2)} days ({y2[0]} to {days[-1]})")

    for label, dset in [("Year 1 (oldest)", y1), ("Year 2 (recent)", y2)]:
        all_trades = []
        for sym in CORE_SYMBOLS:
            day_bars, hourly = {}, []
            for d in dset:
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
                bars, rth = day_bars[d]
                pdh = pdl = None
                if prev and prev in day_bars:
                    _, prth = day_bars[prev]
                    pdh = max(c.high for c in prth) if prth else None
                    pdl = min(c.low for c in prth) if prth else None
                pmh, pml = pf.premarket_hi_lo(bars)
                bias = htf_bias_for(hourly, d)
                trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml)
                all_trades.extend(trades)
                prev = d
        fired = [t for t in all_trades if t.counted]
        pnl = round(sum(t.pnl for t in fired), 2)
        w = sum(1 for t in fired if t.outcome == "win")
        l = sum(1 for t in fired if t.outcome == "loss")
        wr = round(w / (w + l) * 100, 1) if (w + l) else 0
        calls = [t for t in fired if t.direction == "call"]
        puts = [t for t in fired if t.direction == "put"]
        call_pnl = round(sum(t.pnl for t in calls), 2)
        put_pnl = round(sum(t.pnl for t in puts), 2)
        call_wr = round(sum(1 for t in calls if t.outcome == "win") / len(calls) * 100, 1) if calls else 0
        put_wr = round(sum(1 for t in puts if t.outcome == "win") / len(puts) * 100, 1) if puts else 0

        print(f"\n  {label}:")
        print(f"    P&L: ${pnl:,.2f} ({len(fired)} trades, {wr}% WR)")
        print(f"    Calls: ${call_pnl:,.2f} ({len(calls)} trades, {call_wr}% WR)")
        print(f"    Puts:  ${put_pnl:,.2f} ({len(puts)} trades, {put_wr}% WR)")

        # By setup
        from collections import defaultdict as dd
        by_st = dd(list)
        for t in fired:
            by_st[t.signal_type].append(t)
        for st in sorted(by_st):
            sts = by_st[st]
            n = len(sts)
            w_ = sum(1 for t in sts if t.outcome == "win")
            l_ = sum(1 for t in sts if t.outcome == "loss")
            wr_ = round(w_ / (w_ + l_) * 100, 1) if (w_ + l_) else 0
            pnl_ = round(sum(t.pnl for t in sts), 2)
            print(f"    {st}: {n} trades, {wr_}% WR, ${pnl_:,.2f}")


if __name__ == "__main__":
    main()
