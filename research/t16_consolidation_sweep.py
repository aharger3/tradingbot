"""T16 - Consolidation sweep: sweep 0.5% consolidation threshold (0.2 / 0.3 / 0.5 / 0.75 / 1.0 / 1.5%)
and report trip rate, mean R of skipped days, and held-out recall at each.

Consolidation check: skip a day if PDH/PDL/ORH/ORL all sit within threshold % of each other.

Usage:  python research/t16_consolidation_sweep.py
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf
from universe import ALL_SYMS, has_archive

# Mark files for held-out recall scoring
S_SWEEP = ROOT / "research" / "marks" / "probe_s_sweep_2026-08-28.jsonl"
MASTER_PROBE = ROOT / "research" / "marks" / "probe_master_2026-08-29.jsonl"


def load_marks(path):
    """Load marks from jsonl file: symbol_day -> {grade, ...}"""
    if not path.exists():
        return {}
    marks = {}
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            key = f"{row.get('symbol')}_{row.get('day')}"
            marks[key] = row
    return marks


def is_consolidation(pdh, pdl, orh, orl, threshold_pct):
    """Check if PDH/PDL/ORH/ORL are all within threshold % of each other.

    Consolidation index: (max - min) / mid, where mid = (min + max) / 2
    Returns True if the index is <= threshold_pct (1.0 = 1%)
    """
    levels = [x for x in [pdh, pdl, orh, orl] if x is not None]
    if len(levels) < 2:
        return False  # Can't determine consolidation with < 2 levels

    min_lv = min(levels)
    max_lv = max(levels)
    if max_lv == 0:
        return False

    mid = (min_lv + max_lv) / 2.0
    if mid == 0:
        return False

    spread_pct = ((max_lv - min_lv) / mid) * 100.0
    return spread_pct <= threshold_pct


def archive_days(sym):
    """List archived trading days for a symbol."""
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def get_day_levels(sym, day):
    """Extract PDH/PDL and OR high/low for a day.
    Returns (pdh, pdl, orh, orl) or (None, None, None, None) if not available."""
    try:
        bars = pf.fetch_day(sym, day)
        if not bars:
            return None, None, None, None
        rth = pf.rth(bars)
        if len(rth) < 30:
            return None, None, None, None

        orh = max(c.high for c in rth[:1000])  # OR is first 1m candle(s)
        orl = min(c.low for c in rth[:1000])
        # ORH/ORL is typically the first 30 min, but we'll use all available
        orh = max(c.high for c in rth[:30]) if len(rth) >= 30 else orh
        orl = min(c.low for c in rth[:30]) if len(rth) >= 30 else orl

        return None, None, orh, orl  # PDH/PDL would come from previous day
    except Exception:
        return None, None, None, None


def main():
    print("Loading backtest data...")
    backtest_path = ROOT / "research" / "bt2y_trades.json"
    if not backtest_path.exists():
        print(f"ERROR: {backtest_path} not found")
        return

    with open(backtest_path) as f:
        data = json.load(f)

    trades = data.get("trades", [])
    print(f"Loaded {len(trades)} trades")

    # Group trades by day
    days_data = defaultdict(lambda: {"trades": [], "pdh": None, "pdl": None, "orh": None, "orl": None})
    for t in trades:
        day = t["day"]
        days_data[day]["trades"].append(t)

    # Load mark files
    s_marks = load_marks(S_SWEEP)
    master_marks = load_marks(MASTER_PROBE)

    # Compute levels for each day from first symbol that has data
    print("Computing levels for each day (using QQQ as reference)...")
    level_days = 0
    prev_day_high = None
    prev_day_low = None
    sorted_days = sorted(days_data.keys())

    for day in sorted_days:
        # Try to get levels from QQQ
        try:
            bars = pf.fetch_day("QQQ", day)
            if bars:
                rth = pf.rth(bars)
                if len(rth) >= 30:
                    # Current day: ORH/ORL are first 30 minutes
                    orh = max(c.high for c in rth[:30])
                    orl = min(c.low for c in rth[:30])
                    # Previous day: PDH/PDL come from yesterday
                    pdh = prev_day_high
                    pdl = prev_day_low

                    if pdh is not None and pdl is not None:
                        days_data[day]["pdh"] = pdh
                        days_data[day]["pdl"] = pdl
                    days_data[day]["orh"] = orh
                    days_data[day]["orl"] = orl

                    # Update prev_day for next iteration
                    prev_day_high = max(c.high for c in rth)
                    prev_day_low = min(c.low for c in rth)
                    level_days += 1
        except Exception:
            pass

    print(f"Got levels for {level_days} days")

    # Thresholds to sweep
    thresholds = [0.2, 0.3, 0.5, 0.75, 1.0, 1.5]

    # Run sweep
    results = {}
    for threshold in thresholds:
        days_skipped = 0
        trades_on_skipped = []
        s_trades_skipped = 0
        marks_seen = set()

        for day in sorted(days_data.keys()):
            pdh = days_data[day]["pdh"]
            pdl = days_data[day]["pdl"]
            orh = days_data[day]["orh"]
            orl = days_data[day]["orl"]

            # Skip if PDH/PDL/ORH/ORL all sit within threshold of each other
            if pdh and pdl and orh and orl and is_consolidation(pdh, pdl, orh, orl, threshold):
                days_skipped += 1
                for t in days_data[day]["trades"]:
                    if t["traded"]:
                        trades_on_skipped.append(t)
                        if t["sgrade"] == "S":
                            s_trades_skipped += 1
                    # Track marks we would miss
                    key = f"{t['sym']}_{t['day']}"
                    if key in s_marks:
                        marks_seen.add(key)

        trip_rate = (days_skipped / len(days_data) * 100) if days_data else 0.0
        mean_r = statistics.mean([t["r"] for t in trades_on_skipped]) if trades_on_skipped else 0.0

        results[threshold] = {
            "threshold_pct": threshold,
            "days_total": len(days_data),
            "days_skipped": days_skipped,
            "trip_rate_pct": trip_rate,
            "trades_on_skipped": len(trades_on_skipped),
            "mean_r_of_skipped": mean_r,
            "s_trades_skipped": s_trades_skipped,
            "s_marks_in_skipped": len(marks_seen),
        }

    # Write report
    print("\n\n# T16 — Consolidation Sweep Results")
    print("\n## Summary")
    print("Swept consolidation threshold (PDH/PDL/ORH/ORL spread) from 0.2% to 1.5%")
    print("A day is skipped if all four levels sit within the threshold of each other.")
    print("\n| Threshold % | Days Skipped | Trip Rate | Trades Skipped | Mean R | S Trades Skipped |")
    print("|---|---|---|---|---|---|")
    for threshold in thresholds:
        r = results[threshold]
        print(f"| {r['threshold_pct']} | {r['days_skipped']} | {r['trip_rate_pct']:.1f}% | {r['trades_on_skipped']} | {r['mean_r_of_skipped']:+.4f} | {r['s_trades_skipped']} |")

    print("\n## Reachability Check")
    print("Trip rates: 0.2% -> ", results[0.2]["trip_rate_pct"], "%, 1.5% -> ", results[1.5]["trip_rate_pct"], "%")
    if results[0.2]["trip_rate_pct"] < 1.0 or results[1.5]["trip_rate_pct"] > 85.0:
        print("WARNING: Rule is unreachable — trips on <1% or >85% of days.")


if __name__ == "__main__":
    main()
