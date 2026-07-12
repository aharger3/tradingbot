"""Parameter sweep over 30-day backtest. Fetches yfinance data once (pickle
cache in .cache/), then re-runs the walk-forward sim across configs.

Usage: python backtest_sweep.py [--days 29] [--refresh]
"""

import pickle
import sys
from datetime import date, timedelta
from pathlib import Path

import omen_bot
import signal_runner
from backtest_week import SYMBOLS, fetch_week, htf_bias_for, simulate_day, _stats

CACHE = Path(__file__).parent / ".cache"
CACHE.mkdir(exist_ok=True)


def load_data(days: int, refresh: bool = False) -> dict:
    """{symbol: {"days": {...}, "hourly": [...]}} — cached per (symbol, days, today)."""
    out = {}
    for sym in SYMBOLS:
        p = CACHE / f"{sym}_{days}d_{date.today().isoformat()}_v2.pkl"  # v2: +premarket
        if p.exists() and not refresh:
            out[sym] = pickle.loads(p.read_bytes())
        else:
            print(f"fetching {sym}...")
            out[sym] = fetch_week(sym, days=days)
            p.write_bytes(pickle.dumps(out[sym]))
    return out


def run_config(data: dict, week_start: str, week_end: str) -> list:
    trades = []
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
                trades.extend(simulate_day(sym, dy, candles, pdh, pdl,
                                           htf_bias_for(d["hourly"], dy), pmh, pml))
            prev_day = dy
    return trades


def summarize(name: str, trades: list) -> str:
    counted = [t for t in trades if t.counted]
    n, w, l, s, wr, pnl = _stats(counted)
    ob = [t for t in counted if t.signal_type == "one_candle_rule"]
    on, ow, ol, os_, owr, opnl = _stats(ob)
    return f"{name:38s} | {n:4d} trades {wr:5.1f}% ${pnl:8.2f} | OB: {on:4d} {owr:5.1f}% ${opnl:8.2f}"


CONFIGS = [
    # (name, displacement_mult, retest_types, volume_mult)
    ("baseline (1.5x, wick+partial, no vol)", 1.5, ("wick_only", "partial_body"), 0.0),
    ("displacement 2.0x", 2.0, ("wick_only", "partial_body"), 0.0),
    ("displacement 2.5x", 2.5, ("wick_only", "partial_body"), 0.0),
    ("wick_only retest", 1.5, ("wick_only",), 0.0),
    ("volume 1.3x (SPEC11)", 1.5, ("wick_only", "partial_body"), 1.3),
    ("wick_only + vol 1.3x", 1.5, ("wick_only",), 1.3),
    ("2.0x + wick_only", 2.0, ("wick_only",), 0.0),
    ("2.0x + wick_only + vol 1.3x", 2.0, ("wick_only",), 1.3),
]


def main():
    days = 29
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    week_start = (date.today() - timedelta(days=days)).isoformat()
    week_end = (date.today() - timedelta(days=1)).isoformat()

    data = load_data(days, refresh="--refresh" in sys.argv)
    n_days = len({d for v in data.values() for d in v["days"]
                  if week_start <= d <= week_end})
    print(f"\nSweep over {n_days} sessions, {len(data)} symbols "
          f"({week_start}..{week_end})\n")
    print(f"{'config':38s} | {'ALL: n, win%, P&L':28s} | OB same")
    print("-" * 110)

    out = Path(__file__).parent / "sweep_results.txt"
    out.write_text("", encoding="utf-8")
    for name, disp, retests, vol in CONFIGS:
        omen_bot.DISPLACEMENT_MULT = disp
        signal_runner.OB_RETEST_TYPES = retests
        signal_runner.OB_VOLUME_MULT = vol
        trades = run_config(data, week_start, week_end)
        line = summarize(name, trades)
        print(line, flush=True)
        with out.open("a", encoding="utf-8") as f:  # survive partial runs
            f.write(line + "\n")


if __name__ == "__main__":
    main()
