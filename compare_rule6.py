"""Compare baseline vs Rule 6 backtest results.

Usage: python compare_rule6.py [--days 8]

Runs the backtest twice: once with RULE6_ENABLED=False (baseline),
once with RULE6_ENABLED=True (Rule 6 scaling), then writes a
comparison report to backtest_rule6_comparison.md.
"""

import sys
import re
from pathlib import Path


REPORT = Path(__file__).parent / "backtest_report.md"
COMPARISON = Path(__file__).parent / "backtest_rule6_comparison.md"


def _parse_pnl(text: str) -> float:
    """Extract simulated P&L from backtest report."""
    m = re.search(r'Simulated P&L.*?\$\(?\s*[-+]?\d+[\d,.]*\)?', text)
    if not m:
        return 0.0
    num_str = re.sub(r'[^\d.-]', '', m.group().split('$')[-1])
    try:
        return float(num_str)
    except ValueError:
        return 0.0


def _parse_wr(text: str) -> float:
    """Extract overall win rate from backtest report."""
    m = re.search(r'win rate (\d+[\d.]*)%', text)
    if m:
        return float(m.group(1))
    return 0.0


def _parse_trade_count(text: str) -> int:
    """Extract total traded signals count."""
    m = re.search(r'Traded signals.*?\*\*(\d+)\*\*', text)
    if m:
        return int(m.group(1))
    return 0.0


def run_with_flag(enable: bool):
    """Toggle RULE6_ENABLED and run backtest_week."""
    # Read current state
    bw_path = Path(__file__).parent / "backtest_week.py"
    code = bw_path.read_text()

    # Replace RULE6_ENABLED = True/False
    key = "RULE6_ENABLED = " + ("True" if enable else "False")
    if enable:
        code = code.replace("RULE6_ENABLED = False", key)
    else:
        code = code.replace("RULE6_ENABLED = True", key)
    bw_path.write_text(code)

    # Run backtest by importing and calling main directly
    # Clear any cached import
    for mod_name in list(sys.modules.keys()):
        if 'backtest_week' in mod_name:
            del sys.modules[mod_name]

    import importlib.util
    spec = importlib.util.spec_from_file_location("bw_module", bw_path)
    bw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bw)

    # Call main
    old_argv = sys.argv
    sys.argv = ["backtest_week.py", "--days", "8"]
    try:
        bw.main()
    except SystemExit:
        pass
    sys.argv = old_argv

    # Read result
    report = REPORT.read_text()
    pnl = _parse_pnl(report)
    wr = _parse_wr(report)
    n = _parse_trade_count(report)
    return n, wr, pnl, report


def main():
    print("=== Rule 6 Comparison ===")
    print()

    # Run baseline
    print("Running baseline (no Rule 6)...")
    n1, wr1, pnl1, report1 = run_with_flag(False)

    # Run with Rule 6
    print("Running with Rule 6...")
    n2, wr2, pnl2, report2 = run_with_flag(True)

    # Write comparison
    diff_n = n2 - n1
    diff_wr = round(wr2 - wr1, 1)
    diff_pnl = round(pnl2 - pnl1, 2)

    lines = [
        "# Rule 6 Comparison Report",
        "",
        f"Generated: {__import__('datetime').date.today()}",
        "",
        "## Summary",
        "",
        "| Metric | Baseline (no BE) | Rule 6 (50% BE scale) | Delta |",
        "|--------|-----------------|----------------------|-------|",
        f"| Trades | {n1} | {n2} | {diff_n:+d} |",
        f"| Win Rate | {wr1:.1f}% | {wr2:.1f}% | {diff_wr:+.1f}% |",
        f"| P&L | ${pnl1:.2f} | ${pnl2:.2f} | ${diff_pnl:+.2f} |",
        "",
        "## Interpretation",
        "",
    ]

    if diff_pnl > 0:
        lines.append(f"Rule 6 improved P&L by ${diff_pnl:.2f} ({diff_pnl/pnl1*100:+.1f}% vs baseline).")
    elif diff_pnl < 0:
        lines.append(f"Rule 6 reduced P&L by ${abs(diff_pnl):.2f} - breakeven scaling may cost too many runners that would have hit 2R anyway.")
    else:
        lines.append("Rule 6 had neutral P&L impact - no meaningful difference.")

    lines += [
        "",
        "Rule 6 mechanics:",
        "- Scale 50% of position at breakeven (entry + 1R for calls, entry - 1R for puts)",
        "- Move runner stop to entry (breakeven)",
        "- Runner continues to original 2R target",
        "- P&L on BE-scale trades: 0.5 x 1R + 0.5 x outcome (2R = 1.5R, stop = 0.5R)",
        "",
        "The key trade-off: locking partial profit reduces max win ($2000 -> $1500)",
        "but eliminates the full loss on trades that did touch breakeven first. Whether",
        "this helps depends on how often price reaches 1R without ever touching 2R.",
        "",
        "## Baseline Report",
        "",
        report1,
        "",
        "## Rule 6 Report",
        "",
        report2,
    ]

    text = chr(10).join(lines)
    COMPARISON.write_text(text, encoding="utf-8")
    print(f"Comparison written to {COMPARISON}")
    print(f"Baseline: {n1} trades, {wr1:.1f}% WR, ${pnl1:.2f}")
    print(f"Rule 6:   {n2} trades, {wr2:.1f}% WR, ${pnl2:.2f}")
    print(f"Delta:    {diff_n:+d} trades, {diff_wr:+.1f}% WR, ${diff_pnl:+.2f}")


if __name__ == "__main__":
    main()
