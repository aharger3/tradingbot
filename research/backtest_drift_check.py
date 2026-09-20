#!/usr/bin/env python
"""OMEN Backtest Drift Watchdog.

Finds the newest backtest metrics file under results/ or research/tape/,
computes daily-avg P&L and win-%, compares against the green baseline
documented in research/omen-why-backtests-regressed.md (or a hardcoded
fallback if that doc is missing), and appends one line to
research/backtest-alerts.md:

    YYYY-MM-DD: ALERT: <reason>
    YYYY-MM-DD: green

Run: python backtest_drift_check.py   (from anywhere; paths are relative
to this file's location, i.e. Desktop/Projects/tradingbot/research/).
"""
import gzip
import json
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../tradingbot/research
PROJECT = HERE.parent                            # .../tradingbot

CANDIDATE_DIRS = [
    PROJECT / "results",
    PROJECT / "tape",
    HERE / "tape",       # research/tape
]

REGRESSION_DOC = HERE / "omen-why-backtests-regressed.md"
ALERTS_FILE = HERE / "backtest-alerts.md"

# Hardcoded fallback baseline, used only if REGRESSION_DOC is missing or
# doesn't contain parseable numbers. Derived from the last known-green
# full backtest run (v2.4-pipeline, overall block).
FALLBACK_BASELINE = {
    "daily_avg": 200.0,   # dollars, net P&L per trading day
    "win_pct": 38.0,      # percent
}

# Drift tolerances.
DAILY_AVG_DROP_FRAC = 0.30   # alert if daily_avg falls more than 30% below baseline
WIN_PCT_DROP_PTS = 5.0       # alert if win_pct falls more than 5 points below baseline


def load_json_any(path: Path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_candidate_files():
    candidates = []
    for d in CANDIDATE_DIRS:
        if not d.is_dir():
            continue
        for p in d.glob("*.json*"):
            if p.suffix not in (".json", ".gz"):
                continue
            candidates.append(p)
    # Newest first. Try "metrics"-named files before anything else, since
    # they're pre-aggregated and cheap to parse; fall back to everything
    # else (e.g. raw baseline_*.json.gz tape dumps) newest-first.
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    metric_first = [p for p in candidates if "metric" in p.name.lower()]
    rest = [p for p in candidates if "metric" not in p.name.lower()]
    return metric_first + rest


def compute_from_aggregate(d):
    """Handle a pre-aggregated metrics json with an 'overall' block."""
    overall = d.get("overall")
    if not overall:
        return None
    win_rate = overall.get("win_rate")
    net_profit = overall.get("net_profit")
    trade_count = overall.get("trade_count")
    prov = d.get("_provenance", {})
    days = prov.get("trading_days")
    if win_rate is None or net_profit is None or not days:
        return None
    return {
        "daily_avg": net_profit / days,
        "win_pct": win_rate * 100.0,
        "source_shape": "aggregate",
    }


def compute_from_raw_trades(d):
    """Handle a raw tape dump: {'meta': {...}, 'trades': [...]}."""
    trades = d.get("trades")
    if trades is None:
        return None
    traded = [t for t in trades if t.get("traded")]
    if not traded:
        return None
    wins = sum(1 for t in traded if t.get("out") == "win")
    losses = sum(1 for t in traded if t.get("out") == "loss")
    decided = wins + losses
    win_pct = (wins / decided * 100.0) if decided else 0.0
    net_pnl = sum(t.get("pnl", 0.0) for t in traded)
    days = len({t.get("day") for t in traded if t.get("day")})
    if not days:
        return None
    return {
        "daily_avg": net_pnl / days,
        "win_pct": win_pct,
        "source_shape": "raw_trades",
    }


def compute_current_metrics(path: Path):
    d = load_json_any(path)
    result = compute_from_aggregate(d) if isinstance(d, dict) else None
    if result is None and isinstance(d, dict):
        result = compute_from_raw_trades(d)
    return result


def load_baseline():
    if REGRESSION_DOC.is_file():
        text = REGRESSION_DOC.read_text(encoding="utf-8", errors="ignore")
        daily_m = re.search(r"daily[-_ ]avg[^0-9\-]*(-?[\d.]+)", text, re.IGNORECASE)
        win_m = re.search(r"win[-_ ]?%?[^0-9]*(-?[\d.]+)\s*%", text, re.IGNORECASE)
        if daily_m and win_m:
            return {
                "daily_avg": float(daily_m.group(1)),
                "win_pct": float(win_m.group(1)),
                "source": str(REGRESSION_DOC.name),
            }
    fb = dict(FALLBACK_BASELINE)
    fb["source"] = "hardcoded fallback"
    return fb


def find_newest_parseable_metrics():
    for p in find_candidate_files():
        try:
            metrics = compute_current_metrics(p)
        except Exception:
            metrics = None
        if metrics is not None:
            return p, metrics
    return None, None


def main():
    today = date.today().isoformat()
    metrics_path, current = find_newest_parseable_metrics()

    if metrics_path is None:
        line = f"{today}: ALERT: no parseable backtest metrics json found under results/ or tape/"
        append_alert(line)
        print(line)
        return

    baseline = load_baseline()

    reasons = []
    daily_floor = baseline["daily_avg"] * (1 - DAILY_AVG_DROP_FRAC)
    if current["daily_avg"] < daily_floor:
        reasons.append(
            f"daily-avg ${current['daily_avg']:.2f} < floor ${daily_floor:.2f} "
            f"(baseline ${baseline['daily_avg']:.2f}, {baseline['source']})"
        )
    win_floor = baseline["win_pct"] - WIN_PCT_DROP_PTS
    if current["win_pct"] < win_floor:
        reasons.append(
            f"win-% {current['win_pct']:.2f}% < floor {win_floor:.2f}% "
            f"(baseline {baseline['win_pct']:.2f}%, {baseline['source']})"
        )

    if reasons:
        line = f"{today}: ALERT: " + "; ".join(reasons) + f" [file: {metrics_path.name}]"
    else:
        line = (
            f"{today}: green (daily-avg ${current['daily_avg']:.2f}, "
            f"win-% {current['win_pct']:.2f}%, file: {metrics_path.name})"
        )
    append_alert(line)
    print(line)


def append_alert(line: str):
    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ALERTS_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


if __name__ == "__main__":
    main()
