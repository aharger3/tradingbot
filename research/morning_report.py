"""OMEN 10.0 V4/V5: the morning report.

Reads journal/alpaca-paper.jsonl and prints yesterday's paper orders in plain
English -- no ticket ids, no flag names, no jargon (Austin reads this).

Run before the market open: it looks back at the previous trading day's
Alpaca PAPER fills (entries and exits) and says, in one line per symbol, what
happened. Paper only -- this script places no orders, it only reads the
ledger live_scanner.py and research/paper_order.py already write.

V5 adds a second block: engine (Arm A) vs Austin's own tap (Arm B), grouped
by the ledger's `arm` field -- trades, wins, mean R and $/day on the honest
unit (1R = $1,000), across the whole ledger, not just yesterday, since the
row asks for a running read once 25 sessions have accumulated.

    python research/morning_report.py            # yesterday (last calendar day with rows)
    python research/morning_report.py --date 2026-09-04
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

LEDGER = Path(__file__).parent.parent / "journal" / "alpaca-paper.jsonl"


def _load_rows(ledger_path: Path) -> list[dict]:
    if not ledger_path.exists():
        return []
    rows = []
    with ledger_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _row_date(row: dict) -> str | None:
    ts = row.get("ts")
    if not ts:
        return None
    return str(ts)[:10]


def _latest_date_with_rows(rows: list[dict]) -> str | None:
    dates = sorted({d for r in rows if (d := _row_date(r))})
    return dates[-1] if dates else None


def build_report_text(rows: list[dict], for_date: str) -> str:
    day_rows = [r for r in rows if _row_date(r) == for_date]
    if not day_rows:
        return f"No paper trades logged for {for_date}. Nothing to report."

    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for r in day_rows:
        by_symbol[r.get("symbol", "?")].append(r)

    lines = [f"Yesterday's paper trades ({for_date}):", ""]
    for symbol in sorted(by_symbol):
        events = by_symbol[symbol]
        entries = [e for e in events if e.get("event") == "entry"]
        exits = [e for e in events if e.get("event") == "exit"]
        skips = [e for e in events if e.get("event") == "entry_skip"]
        errors = [e for e in events if e.get("event") in ("entry_error", "exit_error")]

        if entries:
            e = entries[0]
            direction = "a call" if e.get("direction") == "call" else "a put"
            qty = e.get("quantity", "?")
            line = f"- {symbol}: bought {direction}, {qty} contracts/shares."
            if exits:
                line += f" Closed out {len(exits)} time(s) later that day."
            else:
                line += " Still open at end of day (or exit not logged)."
            lines.append(line)
        elif skips:
            reason = skips[0].get("reason", "sizing came out to zero")
            lines.append(f"- {symbol}: signal fired but no order was placed ({reason}).")
        elif errors:
            lines.append(f"- {symbol}: an order failed to submit to the paper broker.")

    total_entries = sum(1 for r in day_rows if r.get("event") == "entry")
    lines.append("")
    lines.append(f"Total: {total_entries} paper order(s) placed on {for_date}.")
    return "\n".join(lines)


def _arm_stats(rows: list[dict], arm: str) -> dict:
    """trades / wins / mean R / $/day for one arm, on the honest unit: 1R =
    a trade's own `max_loss` (falls back to $1,000 -- V5's stated unit --
    when a row predates the max_loss field). Only exit rows with a `pnl`
    count as closed trades; an arm with entries but no matched exits yet
    reports 0 closed trades rather than guessing."""
    exits = [r for r in rows if r.get("event") == "exit" and r.get("arm") == arm
             and r.get("pnl") is not None]
    entries = [r for r in rows if r.get("event") == "entry" and r.get("arm") == arm]
    if not exits:
        return {"trades": len(entries), "closed": 0, "wins": 0, "mean_r": None, "per_day": None}
    r_values = []
    wins = 0
    for e in exits:
        max_loss = e.get("max_loss") or 1000.0
        r = e["pnl"] / max_loss if max_loss else 0.0
        r_values.append(r)
        # A win is money, not a label: a trade that scaled out green and then
        # stopped the runner at breakeven books outcome="stop" and still nets
        # positive, and an "eod" close can be either sign.
        if e["pnl"] > 0:
            wins += 1
    mean_r = sum(r_values) / len(r_values)
    days = len({_row_date(e) for e in exits if _row_date(e)}) or 1
    per_day = (mean_r * 1000.0 * len(r_values)) / days
    return {"trades": len(entries), "closed": len(exits), "wins": wins,
            "mean_r": mean_r, "per_day": per_day}


def build_arm_summary_text(rows: list[dict]) -> str:
    """V5's two-column read: engine (Arm A) vs Austin's own tap (Arm B),
    trades / wins / mean R / $/day on the honest unit (1R = $1,000)."""
    eng = _arm_stats(rows, "engine")
    aus = _arm_stats(rows, "austin")

    def _fmt(s: dict) -> tuple[str, str, str, str]:
        w = f"{s['wins']}/{s['closed']}" if s["closed"] else "-"
        r = f"{s['mean_r']:+.3f}R" if s["mean_r"] is not None else "-"
        d = f"${s['per_day']:+.0f}/day" if s["per_day"] is not None else "-"
        return str(s["trades"]), w, r, d

    et, ew, er, ed = _fmt(eng)
    at_, aw, ar, ad = _fmt(aus)
    lines = [
        "Engine vs Austin (paper, 1R = $1,000):",
        "",
        f"{'':<10}{'trades':>8}{'wins':>10}{'mean R':>10}{'$/day':>12}",
        f"{'engine':<10}{et:>8}{ew:>10}{er:>10}{ed:>12}",
        f"{'austin':<10}{at_:>8}{aw:>10}{ar:>10}{ad:>12}",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=None,
                         help="YYYY-MM-DD; default is the most recent day with rows "
                              "(falls back to yesterday's calendar date if the "
                              "ledger is empty).")
    parser.add_argument("--ledger", default=str(LEDGER))
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    rows = _load_rows(ledger_path)

    for_date = args.date or _latest_date_with_rows(rows)
    if for_date is None:
        for_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print(build_report_text(rows, for_date))
    print()
    print(build_arm_summary_text(rows))


if __name__ == "__main__":
    main()
