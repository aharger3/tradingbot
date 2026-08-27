"""Single source of truth for symbol pools.

Every module that names a set of symbols imports it FROM HERE. Nothing defines
its own list. `research/test_universe_single_source.py` enforces that.

Two different partitions of the same 29 symbols coexist on purpose, because they
answer different questions:

  * POOLS (2026-08-11) -- MAJOR_15 / INDEX_POOL / OTHER_POOL. Used for per-pool
    reporting: "how does the engine do on indices vs equities."
  * BACKTEST TIERS (2026-07-11) -- CORE_SYMBOLS / EXPERIMENTAL_SYMBOLS. Austin's
    own watchlist split, used by backtest_week and its six dependents to label a
    trade core vs experimental.

They are NOT the same cut and neither is wrong. What was wrong, until 2026-08-22,
was that six modules each kept a private copy and they had drifted apart -- see
OMEN 6 ticket 14.

Usage:
  from universe import MAJOR_15, INDEX_POOL, OTHER_POOL, ALL_SYMS, POOL_OF
  from universe import CORE_SYMBOLS, EXPERIMENTAL_SYMBOLS, BACKTEST_SYMBOLS
  from universe import EQUITY_POOL, pool_for, has_archive, archived_symbols
"""

import os

MAJOR_15 = [
    "NVDA","TSLA","AAPL","SPCX","MSFT","MU","INTC","PLTR",
    "AMZN","META","AMD","GOOGL","ACHR","NFLX","ORCL",
]

INDEX_POOL = ["QQQ","SPY","IWM"]

# Everything in live_scanner DEFAULT_SYMBOLS minus MAJOR_15 and INDEX_POOL.
OTHER_POOL = [
    "GOOG","SOFI","COIN","HOOD","IREN","AVGO","UBER","BABA","CRM","TSM","MARA",
]

ALL_SYMS = MAJOR_15 + INDEX_POOL + OTHER_POOL  # 15 + 3 + 11 = 29 symbols

# Reverse lookup: symbol -> pool name (used for per-pool reporting).
POOL_OF = {}
for _name, _pool in [
    ("MAJOR_15", MAJOR_15),
    ("INDEX_POOL", INDEX_POOL),
    ("OTHER_POOL", OTHER_POOL),
]:
    for _sym in _pool:
        POOL_OF[_sym] = _name


# ---------------------------------------------------------------------------
# Backtest tiers -- Austin's watchlist split, moved here from backtest_week.py
# ---------------------------------------------------------------------------
# Austin's watchlist 2026-07-11: all stocks with ~200k+ daily options volume
# (his rule -- high options volume = cleaner moves, easier fills). SPY/QQQ are
# trend reference and are rarely traded by hand.

# SPY's exclusion is a DECISION, not an accident. Recorded here so it stops
# being a comment nobody can find:
#
#   2026-07-11 (A3): SPY removed from CORE_SYMBOLS, rationale "0-for-5".
#   2026-08-22 (OMEN 6 ticket 04): flagged as questionable -- five trades is not
#     a sample, SPY is fully archived, it IS in INDEX_POOL, and it is 30 of the
#     120 symbol-days Austin has ever graded (25% of his whole graded set).
#     Any recall number computed over CORE_SYMBOLS therefore ignores a quarter
#     of his own judgements.
#
# NOT flipped unilaterally: six backtest modules import CORE_SYMBOLS and every
# published number would move. Ratification is Q12 in
# .scratch/omen-6/qa-queue.md. Flip this one flag to include SPY everywhere.
INCLUDE_SPY_IN_BACKTEST = False

CORE_SYMBOLS = ["TSLA", "NVDA", "AAPL", "AMD", "META",
                "GOOGL", "AMZN", "MSFT", "PLTR", "QQQ"]
if INCLUDE_SPY_IN_BACKTEST:
    CORE_SYMBOLS = CORE_SYMBOLS + ["SPY"]

# 2026-07-11 (A3): SMCI / MSTR / RIVN removed, rationale "-$22k/12mo".
EXPERIMENTAL_SYMBOLS = ["SOFI", "ORCL", "COIN", "HOOD", "IREN", "INTC",
                        "NFLX", "AVGO", "MU", "UBER", "BABA", "CRM",
                        "TSM", "MARA"]

BACKTEST_SYMBOLS = CORE_SYMBOLS + EXPERIMENTAL_SYMBOLS

# Retired from every pool, with the reason and the date.
RETIRED = {
    "SMCI": "2026-07-11 (A3): -$22k/12mo across the tier",
    "MSTR": "2026-07-11 (A3): -$22k/12mo across the tier",
    "RIVN": "2026-07-11 (A3): -$22k/12mo across the tier",
    "HTZ":  "no data_archive at all, and in no pool (OMEN 6 ticket 04)",
}


# ---------------------------------------------------------------------------
# Pool lookup for reporting -- moved here from research/t4_engine_recall.py
# ---------------------------------------------------------------------------
# t4 kept its own EQUITY_POOL that still carried MSTR and HTZ (both retired) and
# omitted ACHR, NFLX and ORCL. The equity pool IS MAJOR_15; there is no second
# definition of it.
EQUITY_POOL = frozenset(MAJOR_15)
INDEX_POOL_SET = frozenset(INDEX_POOL)


def pool_for(symbol: str) -> str:
    """'index' | 'equity' | 'other' -- for per-pool aggregation in reports."""
    if symbol in INDEX_POOL_SET:
        return "index"
    if symbol in EQUITY_POOL:
        return "equity"
    return "other"


# ---------------------------------------------------------------------------
# Sample floor for per-symbol / per-pool reporting (G6/T5)
# ---------------------------------------------------------------------------
# 20 trades. Settled in research/p12_sample_floor.md, read before this constant
# was added: it reused SCAN_MIN, the floor research/build_bt2y_report.py's edge
# scanner already enforced, rather than inventing a second number. That doc's
# arithmetic: a slice's mean R carries a standard error of roughly
# sd/sqrt(n); below n=20 that error is large enough for one more trade to
# swing the mean by several tenths of an R -- the same order of magnitude as
# the money gate itself (mean R >= 2.0, research/t60_baseline.py). Above ~20
# the swing per additional trade is small enough for the number to mean
# something. research/t70_metric_sweep.py had independently landed on the same
# 20 under its own name (THIN_N) for the same reason -- a second confirmation,
# not a second number.
#
# Every per-symbol/per-pool reporting path imports this ONE constant and marks
# -- never drops, never excludes from whole-book totals -- rows under it.
MIN_SAMPLE_N = 20


# ---------------------------------------------------------------------------
# Archive coverage -- derived from disk, never hardcoded
# ---------------------------------------------------------------------------
ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_archive")


def has_archive(symbol: str, min_days: int = 1) -> bool:
    """Does this symbol have at least ``min_days`` archived sessions on disk?"""
    d = os.path.join(ARCHIVE_DIR, symbol)
    if not os.path.isdir(d):
        return False
    return sum(1 for f in os.listdir(d) if f.endswith(".csv")) >= min_days


def archived_symbols(symbols=None, min_days: int = 1) -> list:
    """The subset of ``symbols`` (default ALL_SYMS) that is actually replayable.

    Research rows that need "every symbol we can measure" should call this
    rather than pasting a list, so a backfill is picked up automatically instead
    of silently missing from a headline. Replaces t8_verdict_measure's
    hand-maintained WINDOW_SYMBOLS, which was stale: it still carried MSTR and
    omitted ACHR, which has been fully archived since 2026-08-10.
    """
    return [s for s in (symbols or ALL_SYMS) if has_archive(s, min_days)]
