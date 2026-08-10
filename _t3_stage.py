"""T3: add SPCX + widen data_archive date coverage.

Runs inside the CI runner.  Appends missing 1-min bar CSVs — never rewrites
existing files.  Uses polygon_feed.fetch_day() which caches to the same layout.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import polygon_feed

ARCHIVE = Path(__file__).parent / "data_archive"

# --- config ----------------------------------------------------------------
COMMON_START = date(2024, 2, 20)
LATEST       = date(2026, 8, 7)   # last full trading day before this run

# equity_pool_14 from priority_pool.json minus HTZ (skip per spec)
EQUITY_POOL = [
    "NVDA","TSLA","SPCX","PLTR","AAPL","MU","MSTR",
    "AMZN","MSFT","INTC","AMD","GOOGL","META",
]
INDEX_POOL = ["QQQ","SPY","IWM"]
ALL_SYMS   = EQUITY_POOL + INDEX_POOL

def trading_days_between(start: date, end: date) -> list[date]:
    """Return all weekdays in [start, end]."""
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri
            days.append(d)
        d += timedelta(days=1)
    return days

def compute_coverage(sym: str) -> tuple:
    """Return (earliest_existing, latest_existing, count)."""
    d = ARCHIVE / sym
    if not d.exists():
        return (None, None, 0)
    files = sorted(d.glob("*.csv"))
    if not files:
        return (None, None, 0)
    dates = [f.stem for f in files]
    return (dates[0], dates[-1], len(files))

def main():
    # Part A: SPCX first — fetch all dates from common start to latest
    print("=" * 60)
    print("PART A: Fetching SPCX historical bars")
    print("=" * 60)
    spcx_days = trading_days_between(COMMON_START, LATEST)
    spcx_got = 0
    for d in spcx_days:
        ds = d.isoformat()
        cached = ARCHIVE / "SPCX" / f"{ds}.csv"
        if cached.exists():
            continue
        candles = polygon_feed.fetch_day("SPCX", ds)
        if candles:
            spcx_got += 1
        if spcx_got and spcx_got % 50 == 0:
            print(f"  SPCX: {spcx_got}/{len(spcx_days)} days fetched")
    print(f"  SPCX: done — {spcx_got} new days added")
    first_s, last_s, cnt_s = compute_coverage("SPCX")
    print(f"  SPCX coverage: {first_s} to {last_s} ({cnt_s} days)")

    # Part B: widen all symbols
    print()
    print("=" * 60)
    print("PART B: Widening archive coverage for all pool symbols")
    print("=" * 60)

    total_added = 0
    summary = []

    for sym in ALL_SYMS:
        first, last, cnt = compute_coverage(sym)
        if first is None:
            # New symbol — should only be SPCX which we already did
            print(f"  {sym}: no existing data, skipping widen")
            continue

        old_first = first
        old_last  = last

        # Build missing-date list
        missing = []

        # Backward: from COMMON_START to (first - 1 day)
        bwd_start = max(COMMON_START, date(2020, 1, 1))  # don't go nuts
        bwd_end   = date.fromisoformat(first) - timedelta(days=1)
        if bwd_end >= bwd_start:
            for d in trading_days_between(bwd_start, bwd_end):
                ds = d.isoformat()
                if not (ARCHIVE / sym / f"{ds}.csv").exists():
                    missing.append(d)

        # Forward: from (last + 1 day) to LATEST
        fwd_start = date.fromisoformat(last) + timedelta(days=1)
        if LATEST >= fwd_start:
            for d in trading_days_between(fwd_start, LATEST):
                ds = d.isoformat()
                if not (ARCHIVE / sym / f"{ds}.csv").exists():
                    missing.append(d)

        if not missing:
            print(f"  {sym}: already up to date ({cnt} days)")
            summary.append((sym, old_first, old_last, first, last, 0))
            continue

        print(f"  {sym}: fetching {len(missing)} missing days "
              f"(existing: {cnt} days, {first} to {last})")
        got = 0
        for d in missing:
            ds = d.isoformat()
            candles = polygon_feed.fetch_day(sym, ds)
            if candles:
                got += 1
            if got and got % 50 == 0:
                print(f"    {sym}: {got}/{len(missing)}")

        total_added += got
        new_first, new_last, new_cnt = compute_coverage(sym)
        summary.append((sym, old_first, old_last, new_first, new_last, got))
        print(f"    {sym}: {got} new days → {new_cnt} total")

    # Write coverage report
    print()
    print("=" * 60)
    print("Writing research/t3_archive_coverage.md")
    print("=" * 60)

    lines = [
        "# T3 Archive Coverage — omen-4.0",
        "",
        f"Common start date: {COMMON_START.isoformat()}",
        f"Latest date:       {LATEST.isoformat()}",
        f"Run date:          {date.today().isoformat()}",
        "",
        "| Symbol | Old First | Old Last | New First | New Last | Days Added |",
        "|--------|-----------|----------|-----------|----------|-----------:|",
    ]
    for sym, old_first, old_last, new_first, new_last, added in summary:
        lines.append(
            f"| {sym} | {old_first} | {old_last} | {new_first} | {new_last} | {added} |"
        )
    lines.append("")
    lines.append(f"**symbol_days_added:** {total_added}")
    lines.append("")
    lines.append("### Notes")
    lines.append("- HTZ explicitly skipped per spec (hype-boosted, not expected to hold top-14 options volume).")
    lines.append("- No existing bar files were deleted or rewritten — only appended.")
    lines.append("- SPCX added to data_archive/ for the first time using the same ingestion path (polygon_feed.fetch_day → CSV).")
    lines.append(f"- Archive now spans {COMMON_START.isoformat()} → {LATEST.isoformat()} for all equity_pool and index_pool symbols.")

    report = ARCHIVE.parent / "research" / "t3_archive_coverage.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n")
    print(f"Written to {report}")
    print()
    print(f"Total symbol-days added: {total_added}")
    print("Done.")

if __name__ == "__main__":
    main()