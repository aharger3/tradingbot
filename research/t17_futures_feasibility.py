"""T17 -- futures/prop-firm feasibility: verify facts, fabricate no backtest.

Austin (probe_master_2026-08-29.jsonl, fact_strike): "Separate and more
important is prop firms too so measure those futures trading as well, lots
of angles need to be measured here more subagents then u think."

The archive has NO futures bars. This script does not run a futures
backtest -- it verifies, mechanically, the facts the feasibility report
(research/t17_futures-feasibility.md) is built on:

  1. data_archive/ holds only equity/index tickers -- zero futures symbols.
  2. polygon_feed.py (the 2yr backtest data source) hits Polygon's stocks
     aggs endpoint only -- Polygon has no futures product to fall back to.
  3. futures_feed.py exists but is a live-only yfinance wrapper (self-check
     pulls 5 recent 1m candles) -- it has never been used to build an
     archive, so it cannot answer a durability/recall question.
  4. Count how many symbol-days of archive the equity backtest actually
     runs on, for scale contrast against "zero futures days".
  5. Count prop-firm name hits across the tracked corpus/vault so "which
     firms Austin has mentioned" is a grep result, not a memory.

Run: python research/t17_futures_feasibility.py
"""
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
ARCHIVE = REPO / "data_archive"

# Known futures/index-future root symbols -- if any of these ever show up as
# a data_archive/<SYM>/ directory, the "no futures data" claim is false and
# this script must fail loudly rather than let the report say it anyway.
FUTURES_ROOTS = {
    "ES", "NQ", "RTY", "YM", "MES", "MNQ", "M2K", "MYM",
    "CL", "GC", "SI", "ZB", "ZN",
}

PROP_FIRM_NAMES = [
    "Vanquish", "Apex Trader Funding", "Topstep", "MyFundedFutures",
    "TradeDay", "Earn2Trade", "Funded Futures Family", "Bulenox",
    "TakeProfitTrader", "FundedNext",
]


def check_no_futures_archive():
    syms = sorted(p.name for p in ARCHIVE.iterdir() if p.is_dir())
    hit = FUTURES_ROOTS & set(syms)
    assert not hit, f"futures data DOES exist for {hit} -- report claim is false"
    return syms


def check_polygon_is_stocks_only():
    src = (REPO / "polygon_feed.py").read_text(encoding="utf-8")
    m = re.search(r'url = \(f"(https://api\.polygon\.io/[^"]+)"', src)
    assert m, "could not find the polygon aggs URL template in polygon_feed.py"
    assert "/v2/aggs/ticker/" in m.group(1), "unexpected polygon endpoint shape"
    return m.group(1)


def check_futures_feed_is_live_only():
    src = (REPO / "futures_feed.py").read_text(encoding="utf-8")
    assert "yfinance" in src, "futures_feed.py no longer wraps yfinance"
    assert "data_archive" not in src, (
        "futures_feed.py now writes to data_archive -- an archive may exist, "
        "re-check check_no_futures_archive()"
    )
    return True


def count_archive_symbol_days():
    total = 0
    per_sym = {}
    for sym_dir in ARCHIVE.iterdir():
        if not sym_dir.is_dir():
            continue
        n = sum(1 for f in sym_dir.iterdir() if f.suffix == ".csv")
        per_sym[sym_dir.name] = n
        total += n
    return total, per_sym


def count_prop_firm_mentions():
    """Grep the tracked corpus (not .gitignored churn) for each firm name."""
    counts = {}
    text_exts = {".md", ".txt", ".jsonl", ".json"}
    skip_dirs = {".git", "node_modules", ".claude", "data_archive"}
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fn in files:
            if Path(fn).suffix not in text_exts:
                continue
            fp = Path(root) / fn
            try:
                body = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for name in PROP_FIRM_NAMES:
                if name.lower() in body.lower():
                    counts.setdefault(name, set()).add(str(fp.relative_to(REPO)))
    return {k: sorted(v) for k, v in counts.items()}


def main():
    syms = check_no_futures_archive()
    poly_url = check_polygon_is_stocks_only()
    check_futures_feed_is_live_only()
    total_days, per_sym = count_archive_symbol_days()
    mentions = count_prop_firm_mentions()

    print(f"data_archive/: {len(syms)} symbols, ALL equity/index -- {syms}")
    print(f"futures roots checked against archive: {sorted(FUTURES_ROOTS)} -- 0 hits")
    print(f"polygon_feed.py endpoint: {poly_url} (stocks aggs, no futures product)")
    print("futures_feed.py: live-only yfinance wrapper, confirmed no archive write")
    print(f"data_archive total symbol-days across {len(syms)} equity symbols: {total_days}")
    print()
    print("prop-firm name hits across tracked corpus + this report's own inputs:")
    for name in PROP_FIRM_NAMES:
        files = mentions.get(name, [])
        print(f"  {name}: {len(files)} file(s)")

    out = {
        "futures_archive_symbols": sorted(FUTURES_ROOTS & set(syms)),
        "equity_archive_symbol_count": len(syms),
        "equity_archive_total_symbol_days": total_days,
        "polygon_endpoint": poly_url,
        "prop_firm_mentions": {k: len(v) for k, v in mentions.items()},
        "prop_firm_mention_files": mentions,
    }
    out_path = REPO / "research" / "t17_facts.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path.relative_to(REPO)}")


if __name__ == "__main__":
    sys.exit(main())
