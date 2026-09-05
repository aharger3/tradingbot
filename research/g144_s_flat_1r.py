#!/usr/bin/env python3
"""OMEN 9.0 L5: before/after live-sizing table for the S-flat-1R fix.

Prints, and the .md report freezes, what `live_scanner._emit_signal` would
have budgeted for each S promotion in the current-default 2-year book
(`research/bt2y_trades_retest_on.json`, RETEST_REQUIRED=1) under the OLD
branch (`GRADE_SIZE_PCT[grade]`, the retired A+/A/B/C/X ladder) versus the
NEW one (his S/A/C ladder: S -> 1.0, everything else -> 0.0).

The book itself does not carry a live `sac_grade`/`austin_tier` field --
`research/downgrade.py`'s S/A/C ladder is measured-only and stored per row
as `sgrade` (see CLAUDE.md "Two grade ladders"). `sgrade` IS his ladder
letter, so it stands in here for the `sac_grade` field `live_scanner.py`
reads at runtime. This script computes the DOLLAR BUDGET
(`DEFAULT_MAX_LOSS * size_pct`) each row would have been handed, not a
live contracts count -- the book carries no options premium, so the "±
contract rounding" the row names is real but not reproducible from this
book; it is bounded by one contract's worth of premium (a few dollars),
which is negligible against an $800 -> $1,000 (+25%) sizing error.

Run: python research/g144_s_flat_1r.py
"""
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"

DEFAULT_MAX_LOSS = 1000.0
# The exact retired mapping live_scanner.py read before this fix.
OLD_GRADE_SIZE_PCT = {"A+": 1.0, "A": 0.8, "B": 0.6, "C": 0.4, "X": 0.0, "D": 0.0}


def load_book():
    if BOOK.exists():
        return json.load(open(BOOK))
    gz = BOOK.with_suffix(BOOK.suffix + ".gz")
    if gz.exists():
        return json.loads(gzip.open(gz, "rt").read())
    raise FileNotFoundError(f"{BOOK} (or its .gz) not found")


def old_budget(row):
    return DEFAULT_MAX_LOSS * OLD_GRADE_SIZE_PCT.get(row.get("grade", "?"), 0.6)


def new_budget(row):
    return DEFAULT_MAX_LOSS if row.get("sgrade") == "S" else 0.0


def main():
    book = load_book()
    all_rows = book["trades"]
    # Only PROMOTED rows -- `traded: true` is the book's own "this fired and
    # was actually sized/booked" flag. The other ~123k rows are candidates
    # that never promoted (skipped, halted, or WATCH-tier alerts with a
    # research-only what-if pnl) -- live sizing never touches them.
    trades = [r for r in all_rows if r.get("traded")]
    s_rows = [r for r in trades if r.get("sgrade") == "S"]
    ac_rows = [r for r in trades if r.get("sgrade") in ("A", "C")]

    print(f"book: {BOOK.name}  sessions={book['meta']['sessions']}  "
          f"first={book['meta']['first']}  last={book['meta']['last']}")
    print(f"total candidate rows: {len(all_rows)}  traded (promoted) rows: {len(trades)}")
    print(f"his-S rows (sgrade == 'S'): {len(s_rows)}")
    print(f"his-A/C rows (sgrade in A,C): {len(ac_rows)}")
    print()

    print("--- S rows: old sizing (engine-grade-keyed) vs new (S -> flat 1R) ---")
    print(f"{'engine grade':<14}{'n':>6}{'old $/trade':>14}{'new $/trade':>14}{'delta':>10}")
    by_grade = {}
    for r in s_rows:
        by_grade.setdefault(r.get("grade", "?"), []).append(r)
    total_old = total_new = 0.0
    for g in sorted(by_grade):
        rows = by_grade[g]
        old = old_budget(rows[0])
        new = new_budget(rows[0])
        total_old += old * len(rows)
        total_new += new * len(rows)
        print(f"{g:<14}{len(rows):>6}{old:>14.0f}{new:>14.0f}{new - old:>+10.0f}")
    n = len(s_rows) or 1
    print(f"{'mean/trade':<14}{len(s_rows):>6}{total_old / n:>14.1f}{total_new / n:>14.1f}"
          f"{(total_new - total_old) / n:>+10.1f}")
    print(f"{'total':<14}{'':>6}{total_old:>14.0f}{total_new:>14.0f}{total_new - total_old:>+10.0f}")
    print()
    every_flat = all(new_budget(r) == DEFAULT_MAX_LOSS for r in s_rows)
    print(f"every S row now sizes to exactly ${DEFAULT_MAX_LOSS:.0f}: {every_flat}")

    print()
    print("--- A/C rows: old sizing vs new (A and C do not trade live -> $0) ---")
    total_old_ac = sum(old_budget(r) for r in ac_rows)
    total_new_ac = sum(new_budget(r) for r in ac_rows)
    n_ac = len(ac_rows) or 1
    print(f"n={len(ac_rows)}  old total=${total_old_ac:,.0f} (mean ${total_old_ac/n_ac:.0f}/row)  "
          f"new total=${total_new_ac:,.0f} (mean ${total_new_ac/n_ac:.0f}/row)")


if __name__ == "__main__":
    main()
