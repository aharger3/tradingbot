#!/usr/bin/env python3
"""backtest_churn.py -- diff two backtest trade sets by trade identity.

Trade identity = symbol + day + entry bar (entry_i) + direction.
A trade present in both sets is either `unchanged` (same grade) or
`regraded` (grade changed, named from->to).

Usage:
    python research/backtest_churn.py            # diff current vs stored baseline
    python research/backtest_churn.py --selftest # baseline vs itself, must be all-unchanged

Artifacts written from a run:
    research/churn_baseline_v40.json  -- normalized snapshot of the current trade set
    research/t7_churn.md              -- the four counts + per-pool split
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESEARCH = REPO_ROOT / "research"

CURRENT_BACKTEST = REPO_ROOT / "backtest_charts.json"
BASELINE_PATH = RESEARCH / "churn_baseline_v40.json"
REPORT_PATH = RESEARCH / "t7_churn.md"
PRIORITY_POOL = RESEARCH / "priority_pool.json"

IDENTITY_FIELDS = ("symbol", "day", "entry_i", "direction")


def load_pool_map():
    """Return symbol -> pool name from priority_pool.json (best effort)."""
    pools = {}
    try:
        spec = json.loads(PRIORITY_POOL.read_text())
    except (OSError, ValueError):
        return pools, {"equity": [], "index": []}
    equity = spec.get("equity_pool_14", [])
    index = spec.get("index_pool", [])
    for s in equity:
        pools[s] = "equity"
    for s in index:
        pools[s] = "index"
    return pools, {"equity": equity, "index": index}


def identity_key(t):
    return (t["symbol"], t["day"], t["entry_i"], t["direction"])


def normalize_trade(t, pool_map):
    return {
        "symbol": t["symbol"],
        "day": t["day"],
        "entry_i": t["entry_i"],
        "direction": t["direction"],
        "grade": t.get("grade"),
        "pool": pool_map.get(t["symbol"], "other"),
    }


def load_current_trades():
    """Load the live backtest trade set (backtest_charts.json at repo root)."""
    data = json.loads(CURRENT_BACKTEST.read_text())
    pool_map, _ = load_pool_map()
    return [normalize_trade(t, pool_map) for t in data]


def load_baseline():
    return json.loads(BASELINE_PATH.read_text())


def write_baseline(trades):
    BASELINE_PATH.write_text(json.dumps(trades, indent=2) + "\n")


def diff_sets(current, previous):
    """Return dict of the four buckets plus per-pool splits."""
    prev_by_id = {identity_key(t): t for t in previous}
    curr_by_id = {identity_key(t): t for t in current}

    added = []
    dropped = []
    unchanged = []
    regraded = []

    for key, t in curr_by_id.items():
        if key not in prev_by_id:
            added.append(t)
        else:
            pg = prev_by_id[key].get("grade")
            cg = t.get("grade")
            if pg == cg:
                unchanged.append(t)
            else:
                regraded.append({**t, "from": pg, "to": cg})

    for key, t in prev_by_id.items():
        if key not in curr_by_id:
            dropped.append(t)

    def pool_of(trade):
        return trade.get("pool", "other")

    def per_pool(bucket):
        counts = defaultdict(int)
        for t in bucket:
            counts[pool_of(t)] += 1
        return dict(counts)

    return {
        "trades_added": added,
        "trades_dropped": dropped,
        "trades_unchanged": unchanged,
        "trades_regraded": regraded,
        "per_pool": {
            "added": per_pool(added),
            "dropped": per_pool(dropped),
            "unchanged": per_pool(unchanged),
            "regraded": per_pool(regraded),
        },
    }


def render_report(result, current_count, previous_count, selftest=False):
    lines = []
    lines.append("# T7 -- backtest churn report")
    lines.append("")
    if selftest:
        lines.append("_self-test: current baseline diffed against itself_")
        lines.append("")
    lines.append(f"current_trades: {current_count}")
    lines.append(f"previous_trades: {previous_count}")
    lines.append("")
    lines.append(f"trades_added: {len(result['trades_added'])}")
    lines.append(f"trades_dropped: {len(result['trades_dropped'])}")
    lines.append(f"trades_unchanged: {len(result['trades_unchanged'])}")
    lines.append(f"trades_regraded: {len(result['trades_regraded'])}")
    lines.append("")
    lines.append("## per-pool split")
    lines.append("")
    pp = result["per_pool"]
    lines.append("| pool | added | dropped | unchanged | regraded |")
    lines.append("|---|---|---|---|---|")
    pools = sorted(
        set(pp["added"]) | set(pp["dropped"]) | set(pp["unchanged"]) | set(pp["regraded"])
    )
    for p in pools:
        lines.append(
            f"| {p} | {pp['added'].get(p,0)} | {pp['dropped'].get(p,0)} | "
            f"{pp['unchanged'].get(p,0)} | {pp['regraded'].get(p,0)} |"
        )
    lines.append("")
    if result["trades_regraded"]:
        lines.append("## regrades")
        lines.append("")
        for t in result["trades_regraded"]:
            lines.append(
                f"- {t['symbol']} {t['day']} bar={t['entry_i']} {t['direction']}: "
                f"{t['from']} -> {t['to']}"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def run_selftest():
    """Diff the current trade set against itself; snapshot + report; exit 0 iff clean."""
    current = load_current_trades()
    if not current:
        print("selftest: no current trades found in backtest_charts.json", file=sys.stderr)
        return 1
    write_baseline(current)
    result = diff_sets(current, current)
    report = render_report(result, len(current), len(current), selftest=True)
    REPORT_PATH.write_text(report)

    n_add = len(result["trades_added"])
    n_drop = len(result["trades_dropped"])
    n_unch = len(result["trades_unchanged"])
    n_reg = len(result["trades_regraded"])
    # identity is symbol+day+entry_i+direction; duplicate keys collapse, so
    # unchanged must equal the number of *unique* identities, not raw trade count.
    n_unique = len({identity_key(t) for t in current})
    ok = (n_add == 0 and n_drop == 0 and n_reg == 0 and n_unch == n_unique)
    print(
        f"selftest: added={n_add} dropped={n_drop} unchanged={n_unch} "
        f"regraded={n_reg} -> {'OK' if ok else 'FAIL'}"
    )
    return 0 if ok else 1


def run_diff():
    """Diff current trades against the stored baseline; refresh baseline + report."""
    if not BASELINE_PATH.exists():
        print(
            f"no baseline at {BASELINE_PATH}; run with --selftest first to seed it.",
            file=sys.stderr,
        )
        return 1
    current = load_current_trades()
    previous = load_baseline()
    write_baseline(current)
    result = diff_sets(current, previous)
    report = render_report(result, len(current), len(previous))
    REPORT_PATH.write_text(report)
    print(report)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selftest", action="store_true", help="diff baseline against itself")
    args = p.parse_args(argv)
    if args.selftest:
        return run_selftest()
    return run_diff()


if __name__ == "__main__":
    sys.exit(main())
