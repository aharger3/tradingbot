"""T20 — loss-halt A/B using existing backtest data.

Process research/bt2y_trades.json to simulate loss-halt impact without re-running
the full 2-year backtest. Much faster than the full backtest.

Usage: python research/t20_loss_halt_postprocess.py
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent

def load_trades():
    """Load the pre-computed 2-year backtest data."""
    # Main repo path: go from worktree/research up to main tradingbot/
    # worktree/research -> worktree -> .claude -> tradingbot
    main_repo = Path(__file__).parent.parent.parent.parent.parent  # .\.claude\worktrees\wf_...\research -> tradingbot
    path = main_repo / "research" / "bt2y_trades.json"
    if not path.exists():
        raise FileNotFoundError(f"bt2y_trades.json not found at {path}")
    data = json.load(path.open())
    return data["trades"], data["meta"]

def apply_loss_halt(day_trades, halt_on_n_losses=2):
    """Apply loss halt: stop accepting new signals after N consecutive losses on a day.

    day_trades: list of trades for a single day (in chronological order by entry time)
    halt_on_n_losses: threshold (2 = stop after 2 consecutive losses)

    Returns: filtered list of trades
    """
    if halt_on_n_losses == 0:
        return day_trades

    result = []
    consecutive_losses = 0

    for t in day_trades:
        # Only look at fired trades (not skipped)
        if t["status"] == "fired" and t["traded"]:
            if consecutive_losses >= halt_on_n_losses:
                # Halt reached; stop accepting new signals
                continue
            result.append(t)
            # Update consecutive loss counter
            if t["out"] == "loss":
                consecutive_losses += 1
            else:
                consecutive_losses = 0
        else:
            # Skipped signals and non-traded alerts are included regardless
            result.append(t)

    return result

def compute_stats(trades):
    """Compute stats: (n, wins, losses, scratches, win_rate%, mean_r, total_pnl)"""
    fired = [t for t in trades if t["status"] == "fired" and t["traded"] and t["grade"] != "C"]
    n = len(fired)
    if n == 0:
        return 0, 0, 0, 0, 0.0, 0.0, 0.0

    wins = sum(1 for t in fired if t["out"] == "win")
    losses = sum(1 for t in fired if t["out"] == "loss")
    scratches = n - wins - losses
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
    total_pnl = sum(t["pnl"] for t in fired)
    mean_r = sum(t["r"] for t in fired) / n if n > 0 else 0.0
    return n, wins, losses, scratches, win_rate, mean_r, total_pnl

def compute_durability(trades):
    """Compute months_green and total_months."""
    fired = [t for t in trades if t["status"] == "fired" and t["traded"] and t["grade"] != "C"]

    by_month = defaultdict(list)
    for t in fired:
        month = t["day"][:7]
        by_month[month].append(t)

    green = 0
    for month_trades in by_month.values():
        if sum(t["pnl"] for t in month_trades) > 0:
            green += 1

    return green, len(by_month)

def analyze_halt_events(day_trades_before, day_trades_after, day):
    """Analyze what trades were halted on a day."""
    fired_before = [t for t in day_trades_before if t["status"] == "fired" and t["traded"]]
    fired_after = [t for t in day_trades_after if t["status"] == "fired" and t["traded"]]

    if len(fired_after) >= len(fired_before):
        return None  # No halt

    halted = fired_before[len(fired_after):]
    return {
        "day": day,
        "traded_before_halt": len(fired_after),
        "halted_count": len(halted),
        "halted_pnl": sum(t["pnl"] for t in halted),
        "halted_wins": sum(1 for t in halted if t["out"] == "win"),
        "halted_losses": sum(1 for t in halted if t["out"] == "loss"),
        "halted_trades": [
            {"time": t["et"], "setup": t["setup"], "outcome": t["out"], "pnl": t["pnl"]}
            for t in halted[:5]  # First 5 halted trades
        ]
    }

def main():
    print("Loading 2-year backtest data...")
    trades, meta = load_trades()
    print(f"Loaded {len(trades)} signals from {meta['sessions']} sessions")

    # Group trades by day
    by_day = defaultdict(list)
    for t in trades:
        day = t["day"]
        by_day[day].append(t)

    # Sort each day by entry time
    for day in by_day:
        by_day[day].sort(key=lambda t: t["et"])

    # Run A/B: with and without halt
    all_trades_no_halt = []
    all_trades_with_halt = []
    halt_events = []

    for day in sorted(by_day.keys()):
        day_trades = by_day[day]
        all_trades_no_halt.extend(day_trades)

        day_trades_halted = apply_loss_halt(day_trades, halt_on_n_losses=2)
        all_trades_with_halt.extend(day_trades_halted)

        # Check if halt triggered
        event = analyze_halt_events(day_trades, day_trades_halted, day)
        if event:
            halt_events.append(event)

    # Compute stats
    n_no, w_no, l_no, s_no, wr_no, mr_no, pnl_no = compute_stats(all_trades_no_halt)
    gm_no, tm_no = compute_durability(all_trades_no_halt)

    n_yes, w_yes, l_yes, s_yes, wr_yes, mr_yes, pnl_yes = compute_stats(all_trades_with_halt)
    gm_yes, tm_yes = compute_durability(all_trades_with_halt)

    # Report
    report = {
        "track": "T20 — loss-halt",
        "method": "post-process existing backtest data",
        "sessions": len(by_day),
        "halt_events": len(halt_events),
        "stats_no_halt": {
            "traded": n_no,
            "wins": w_no,
            "losses": l_no,
            "scratches": s_no,
            "win_rate": round(wr_no, 1),
            "mean_r": round(mr_no, 4),
            "total_pnl": round(pnl_no, 0),
            "months_green": f"{gm_no}/{tm_no}",
        },
        "stats_with_halt": {
            "traded": n_yes,
            "wins": w_yes,
            "losses": l_yes,
            "scratches": s_yes,
            "win_rate": round(wr_yes, 1),
            "mean_r": round(mr_yes, 4),
            "total_pnl": round(pnl_yes, 0),
            "months_green": f"{gm_yes}/{tm_yes}",
        },
        "impact": {
            "traded_delta": n_yes - n_no,
            "traded_pct": round((n_yes - n_no) / n_no * 100, 1) if n_no else 0,
            "mean_r_delta": round(mr_yes - mr_no, 4),
            "mean_r_pct": round((mr_yes - mr_no) / mr_no * 100, 1) if mr_no else 0,
            "win_rate_delta": round(wr_yes - wr_no, 1),
            "pnl_delta": round(pnl_yes - pnl_no, 0),
            "months_green_delta": gm_yes - gm_no,
        },
        "halt_event_summary": {
            "days_halted": len(halt_events),
            "total_halted_trades": sum(e["halted_count"] for e in halt_events),
            "total_halted_pnl": round(sum(e["halted_pnl"] for e in halt_events), 0),
            "halted_wins": sum(e["halted_wins"] for e in halt_events),
            "halted_losses": sum(e["halted_losses"] for e in halt_events),
            "halted_win_rate": round(
                sum(e["halted_wins"] for e in halt_events) / max(
                    sum(e["halted_wins"] + e["halted_losses"] for e in halt_events), 1
                ) * 100, 1
            )
        },
        "sample_halt_events": halt_events[:10]
    }

    # Write report
    out = ROOT / "research" / "t20_loss_halt.json"
    out.write_text(json.dumps(report, indent=2))

    print("\n" + "=" * 70)
    print("T20 LOSS-HALT A/B RESULTS")
    print("=" * 70)
    print(f"\nBaseline: {n_no} traded | Win rate: {wr_no:.1f}% | Mean R: {mr_no:.4f} | Months green: {gm_no}/{tm_no}")
    print(f"With halt: {n_yes} traded | Win rate: {wr_yes:.1f}% | Mean R: {mr_yes:.4f} | Months green: {gm_yes}/{tm_yes}")
    print(f"\nImpact:")
    print(f"  Traded: {n_yes - n_no:+d} ({(n_yes - n_no) / n_no * 100:+.1f}%)")
    print(f"  Mean R: {mr_yes - mr_no:+.4f}")
    print(f"  Win rate: {wr_yes - wr_no:+.1f}%")
    print(f"  PnL: ${pnl_yes - pnl_no:+,.0f}")
    print(f"  Months green: {gm_yes - gm_no:+d}")
    print(f"\nHalt Events: {len(halt_events)} days")
    if halt_events:
        print(f"  Halted trades: {sum(e['halted_count'] for e in halt_events)}")
        print(f"  Halted PnL: ${sum(e['halted_pnl'] for e in halt_events):,.0f}")
        print(f"  Halted win rate: {report['halt_event_summary']['halted_win_rate']:.1f}%")

    print(f"\nReport: {out}")

if __name__ == "__main__":
    main()
