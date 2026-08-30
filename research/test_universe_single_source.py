"""No module may define its own symbol list (OMEN 6 ticket 14).

Until 2026-08-22 six modules each kept a private copy of the traded universe and
they had drifted: check_24mo included SPY where backtest_week dropped it,
backtest_window carried GOOG where the universe carries GOOGL, t4_engine_recall's
equity pool still held MSTR and HTZ (retired 2026-07-11) while omitting ACHR,
NFLX and ORCL, and t8_verdict_measure's hand-maintained window silently missed a
backfill.

The failure mode is quiet: two scripts measure "the engine" over different
symbol sets and their numbers are compared as if they were the same measurement.

This test greps the tree for list literals of ticker-shaped strings assigned to a
symbol-ish name, and fails on any found outside universe.py.

    python research/test_universe_single_source.py
"""

from __future__ import annotations
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import universe  # noqa: E402

# Names that mean "a set of symbols". Anything assigned a ticker-list literal
# under one of these names is a private universe copy.
NAME_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*(?:SYMBOLS|SYMS|POOL|TICKERS|WATCHLIST))\s*=\s*[\[({]",
    re.M,
)
# A ticker literal: 1-5 uppercase letters in quotes. Require >= 3 in the literal
# so single-symbol constants and control groups are not flagged.
TICKER_RE = re.compile(r"['\"][A-Z]{1,5}['\"]")

# Files allowed to hold a literal, with why.
ALLOWED = {
    "universe.py": "the single source of truth",
    os.path.join("research", "test_universe_single_source.py"): "this test",
    "futures_feed.py": "futures contracts (ES/NQ/RTY), not the equity universe",
    # Discord chat-mining vocabulary (research/corpus_sf/chat_vocab.py): real
    # tickers OMEN never trades that appear in raw chat text, and uppercase
    # tokens that look like tickers but are jargon/prose (a stop-word list --
    # the inverse of a universe). Never fed into a backtest, the signal
    # engine, or a symbol pool -- see the file's own docstring. This is a
    # recognition dictionary for text parsing, not a private copy of the
    # traded universe, so it is exempted rather than forced into universe.py.
    os.path.join("research", "corpus_sf", "chat_vocab.py"): "chat-mining vocabulary, not a trading universe",
}

SKIP_DIRS = {".git", "__pycache__", "node_modules", "circle_data", "circle_videos",
             "circle_audio", "discord_data", "data_archive", "venv", ".venv",
             # session/tooling scratch, not source -- .git/info/exclude already
             # treats .claude/worktrees/ as ephemeral and untracked.
             ".claude"}


def offenders():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT)
            if rel in ALLOWED:
                continue
            try:
                src = open(path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            for m in NAME_RE.finditer(src):
                # take the literal that follows, up to its closing bracket
                tail = src[m.end() - 1: m.end() + 600]
                depth, end = 0, len(tail)
                for i, ch in enumerate(tail):
                    if ch in "[({":
                        depth += 1
                    elif ch in "])}":
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                literal = tail[:end + 1]
                if len(TICKER_RE.findall(literal)) >= 3:
                    line = src[: m.start()].count("\n") + 1
                    out.append((rel, line, m.group(1)))
    return out


def main():
    # the source of truth itself must still be sane
    assert len(universe.ALL_SYMS) == len(set(universe.ALL_SYMS)), \
        "duplicate symbol in universe.ALL_SYMS"
    for sym in universe.RETIRED:
        assert sym not in universe.ALL_SYMS, \
            "%s is retired but still in ALL_SYMS" % sym
        assert sym not in universe.BACKTEST_SYMBOLS, \
            "%s is retired but still in BACKTEST_SYMBOLS" % sym
    for sym in universe.BACKTEST_SYMBOLS:
        assert sym in universe.ALL_SYMS, \
            "%s is backtested but is in no pool" % sym
    assert ("SPY" in universe.CORE_SYMBOLS) == universe.INCLUDE_SPY_IN_BACKTEST, \
        "SPY membership does not match INCLUDE_SPY_IN_BACKTEST"

    bad = offenders()
    if bad:
        print("UNIVERSE SINGLE-SOURCE TEST FAILED: %d private symbol list(s)" % len(bad))
        for rel, line, name in bad:
            print("  %s:%d  %s -- import it from universe.py instead" % (rel, line, name))
        sys.exit(1)

    print("universe single-source ok: %d symbols, %d backtested, no private lists"
          % (len(universe.ALL_SYMS), len(universe.BACKTEST_SYMBOLS)))


if __name__ == "__main__":
    main()
