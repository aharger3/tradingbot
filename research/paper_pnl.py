"""research/paper_pnl.py -- paper P&L attribution for the V5 Alpaca paper ledger.

Read-only analysis of journal/alpaca-paper.jsonl (PAPER trading only). Never
places, modifies, or cancels an order -- it only reads the ledger
live_scanner.py and research/paper_order.py already write.

Reports, per run:
  - rows / fills / unfilled / $ / mean R, grouped by arm (S-only vs legacy)
  - the same, grouped by entry_rule (e.g. g88, close)
  - the list of unfilled orders

"Arm" here is live_scanner.py's own `legacy` bool (omen-v5-undry,
2026-09-19): "S-only" is the simulated-book paper arm (legacy falsy),
"legacy" is the non-S grade fill-mechanics experiment (legacy=True). This is
a different split than the ledger's separate `arm` field (engine/austin,
i.e. who fired the trade) that research/morning_report.py already reports
on -- both readings coexist, this script answers the S-only-vs-legacy
question specifically.

The ledger carries no explicit entry->exit foreign key (only
live_scanner.py's in-memory `_alpaca_open_orders` dict does at runtime), so
outcomes are reconstructed FIFO per symbol: each `entry` row is paired with
the next unclaimed resolving row for that symbol (an `exit`, or a
`session_end` flatten). Anything else (a `session_end` cancel, an
`entry_cancelled`/`entry_cancel_noop`, or nothing at all before the ledger
ends) leaves the entry "unfilled" -- no pnl was ever logged for it.

Usage:
    python research/paper_pnl.py                  # print report, append to research/tape/paper_pnl.md
    python research/paper_pnl.py --ledger PATH     # use a different ledger file
    python research/paper_pnl.py --no-write        # print only, skip the tape append
    python research/paper_pnl.py --selftest        # synthetic 5-row journal, asserts, no ledger/tape touched
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "journal" / "alpaca-paper.jsonl"
TAPE_MD = ROOT / "research" / "tape" / "paper_pnl.md"

DEFAULT_MAX_LOSS = 1000.0


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def arm_of(entry: dict) -> str:
    return "legacy" if entry.get("legacy") else "S-only"


def match_entries_to_outcomes(rows: list[dict]) -> list[dict]:
    """One dict per `entry` row: the entry's own fields plus `arm`,
    `outcome` ("filled"|"unfilled"), `pnl`, and `r` (pnl / max_loss, using
    the entry's own max_loss, falling back to DEFAULT_MAX_LOSS)."""
    pending: dict[str, list[dict]] = defaultdict(list)
    results: list[dict] = []

    def pop_pending(symbol):
        q = pending.get(symbol)
        return q.pop(0) if q else None

    for row in rows:
        event = row.get("event")
        symbol = row.get("symbol")

        if event == "entry":
            rec = dict(row)
            rec["arm"] = arm_of(row)
            rec["outcome"] = "unfilled"
            rec["pnl"] = None
            rec["r"] = None
            pending[symbol].append(rec)
            results.append(rec)

        elif event == "exit":
            rec = pop_pending(symbol)
            if rec is None:
                continue
            pnl = row.get("pnl")
            max_loss = rec.get("max_loss") or DEFAULT_MAX_LOSS
            rec["pnl"] = pnl
            rec["r"] = (pnl / max_loss) if (pnl is not None and max_loss) else None
            if pnl is not None:
                rec["outcome"] = "filled"

        elif event == "session_end" and row.get("action") == "flatten":
            rec = pop_pending(symbol)
            if rec is None:
                continue
            pnl = row.get("pnl")
            max_loss = rec.get("max_loss") or DEFAULT_MAX_LOSS
            rec["pnl"] = pnl
            rec["r"] = (pnl / max_loss) if (pnl is not None and max_loss) else None
            if pnl is not None:
                rec["outcome"] = "filled"

        elif event == "session_end" and row.get("action") == "cancel":
            pop_pending(symbol)  # stays "unfilled" -- consume so it isn't reused
        elif event in ("entry_cancelled", "entry_cancel_noop"):
            pop_pending(symbol)  # stays "unfilled"
        # entry_skip / entry_error / exit_error / dry_fire / *_error rows
        # never had a resolvable order attached -- nothing to do.

    return results


def _aggregate(results: list[dict], key_fn) -> dict:
    groups: dict[str, dict] = defaultdict(
        lambda: {"rows": 0, "fills": 0, "unfilled": 0, "total_pnl": 0.0, "r_values": []}
    )
    for rec in results:
        g = groups[key_fn(rec)]
        g["rows"] += 1
        if rec["outcome"] == "filled":
            g["fills"] += 1
            g["total_pnl"] += rec["pnl"]
            if rec["r"] is not None:
                g["r_values"].append(rec["r"])
        else:
            g["unfilled"] += 1
    return groups


def _format_table(title: str, groups: dict) -> str:
    lines = [f"### {title}", "", "| key | rows | fills | unfilled | $ | mean R |", "|---|---|---|---|---|---|"]
    for key in sorted(groups):
        g = groups[key]
        mean_r = sum(g["r_values"]) / len(g["r_values"]) if g["r_values"] else None
        lines.append(
            f"| {key} | {g['rows']} | {g['fills']} | {g['unfilled']} | "
            f"{g['total_pnl']:+.2f} | {('%.3f' % mean_r) if mean_r is not None else '-'} |"
        )
    return "\n".join(lines)


def build_report(results: list[dict]) -> str:
    by_arm = _aggregate(results, lambda r: r["arm"])
    by_rule = _aggregate(results, lambda r: r.get("entry_rule") or "close")
    unfilled = [r for r in results if r["outcome"] == "unfilled"]

    lines = [_format_table("By arm (S-only vs legacy)", by_arm), "", _format_table("By entry_rule", by_rule), ""]
    lines.append(f"### Unfilled orders ({len(unfilled)})")
    lines.append("")
    if unfilled:
        lines.append("| symbol | ts | arm | entry_rule |")
        lines.append("|---|---|---|---|")
        for r in unfilled:
            lines.append(f"| {r.get('symbol')} | {r.get('ts')} | {r['arm']} | {r.get('entry_rule') or 'close'} |")
    else:
        lines.append("(none)")
    return "\n".join(lines)


def append_tape(report: str, tape_path: Path = TAPE_MD) -> None:
    """Append-only: one dated block per run, never rewrites earlier blocks."""
    tape_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = f"\n## {stamp}\n\n{report}\n"
    with tape_path.open("a", encoding="utf-8") as f:
        f.write(block)


def run(ledger_path: Path, write: bool, tape_path: Path = TAPE_MD) -> str:
    rows = load_rows(ledger_path)
    results = match_entries_to_outcomes(rows)
    report = build_report(results)
    print(report)
    if write:
        append_tape(report, tape_path)
    return report


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------

def _selftest() -> None:
    synthetic = [
        {"event": "entry", "ts": "2026-09-20T09:31:00", "symbol": "AAPL",
         "arm": "engine", "entry_rule": "g88", "max_loss": 1000.0},
        {"event": "exit", "ts": "2026-09-20T09:45:00", "symbol": "AAPL",
         "pnl": 500.0},
        {"event": "entry", "ts": "2026-09-20T09:32:00", "symbol": "MSFT",
         "arm": "engine", "legacy": True, "entry_rule": "g88", "max_loss": 100.0},
        {"event": "session_end", "action": "flatten", "ts": "2026-09-20T16:00:00",
         "symbol": "MSFT", "pnl": -50.0},
        {"event": "entry", "ts": "2026-09-20T09:33:00", "symbol": "TSLA",
         "arm": "engine", "entry_rule": "close", "max_loss": 1000.0},
    ]

    tmpdir = Path(tempfile.mkdtemp(prefix="paper_pnl_selftest_"))
    ledger_path = tmpdir / "alpaca-paper.jsonl"
    tape_path = tmpdir / "tape" / "paper_pnl.md"
    try:
        with ledger_path.open("w", encoding="utf-8") as f:
            for row in synthetic:
                f.write(json.dumps(row) + "\n")

        rows = load_rows(ledger_path)
        assert len(rows) == 5, f"expected 5 rows, got {len(rows)}"

        results = match_entries_to_outcomes(rows)
        assert len(results) == 3, f"expected 3 entries, got {len(results)}"

        by_arm = _aggregate(results, lambda r: r["arm"])
        assert by_arm["S-only"]["rows"] == 2, by_arm["S-only"]
        assert by_arm["S-only"]["fills"] == 1, by_arm["S-only"]
        assert by_arm["S-only"]["unfilled"] == 1, by_arm["S-only"]
        assert abs(by_arm["S-only"]["total_pnl"] - 500.0) < 1e-9, by_arm["S-only"]
        assert abs(sum(by_arm["S-only"]["r_values"]) / len(by_arm["S-only"]["r_values"]) - 0.5) < 1e-9

        assert by_arm["legacy"]["rows"] == 1, by_arm["legacy"]
        assert by_arm["legacy"]["fills"] == 1, by_arm["legacy"]
        assert abs(by_arm["legacy"]["total_pnl"] - (-50.0)) < 1e-9, by_arm["legacy"]
        assert abs(by_arm["legacy"]["r_values"][0] - (-0.5)) < 1e-9

        by_rule = _aggregate(results, lambda r: r.get("entry_rule") or "close")
        assert by_rule["g88"]["rows"] == 2, by_rule["g88"]
        assert by_rule["g88"]["fills"] == 2, by_rule["g88"]
        assert abs(by_rule["g88"]["total_pnl"] - 450.0) < 1e-9, by_rule["g88"]
        assert abs(sum(by_rule["g88"]["r_values"]) / len(by_rule["g88"]["r_values"]) - 0.0) < 1e-9

        assert by_rule["close"]["rows"] == 1, by_rule["close"]
        assert by_rule["close"]["fills"] == 0, by_rule["close"]
        assert by_rule["close"]["unfilled"] == 1, by_rule["close"]

        unfilled = [r for r in results if r["outcome"] == "unfilled"]
        assert len(unfilled) == 1 and unfilled[0]["symbol"] == "TSLA", unfilled

        # exercise the report/tape-append path end to end (isolated tmp dir)
        report = run(ledger_path, write=True, tape_path=tape_path)
        assert "S-only" in report and "legacy" in report and "Unfilled orders (1)" in report
        assert tape_path.exists() and tape_path.stat().st_size > 0

        print("\nOK: paper_pnl.py --selftest passed (5-row synthetic journal, aggregation verified)")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Also do one real (read-only) run against the actual ledger, so
    # `--selftest` alone leaves research/tape/paper_pnl.md populated --
    # same append-only report a normal run would produce, just triggered
    # here too. Never touches the ledger itself, only reads it.
    run(LEDGER, write=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger", default=str(LEDGER), help="path to the alpaca-paper.jsonl ledger")
    parser.add_argument("--no-write", action="store_true", help="print the report only, skip the tape append")
    parser.add_argument("--selftest", action="store_true", help="run the synthetic-journal selftest and exit")
    args = parser.parse_args()

    if args.selftest:
        _selftest()
        return 0

    run(Path(args.ledger), write=not args.no_write)
    return 0


if __name__ == "__main__":
    sys.exit(main())
