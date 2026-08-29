"""T18 -- corpus-scaling: the query set behind research/t18_corpus-scaling.md.

Austin: "scaling and letting runners run needs to come from corpus or watch
your own scrape content if you can." This script runs a fixed set of queries
against research/corpus_index.jsonl via research/corpus_query.py and prints
the raw output that the report's quotes are drawn from -- nothing here is
typed by hand into the report; every quote in the .md traces to a query run
below.

Usage:
    python research/t18_corpus_scaling_queries.py > research/t18_corpus_scaling_queries.out
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

ROOT = Path(__file__).resolve().parent.parent
CORPUS_QUERY = ROOT / "research" / "corpus_query.py"

QUERIES = [
    "scale out",
    "let winners run",
    "breakeven stop",
    "high of day scale",
    "runner key level",
    "50 percent scale",
    "half position out",
    "full position at hod range market",
    "trailer trending market",
    "choppy market take off all",
    "add to winner",
]


def main() -> None:
    for q in QUERIES:
        print(f"\n{'=' * 80}\nQUERY: {q}\n{'=' * 80}")
        result = subprocess.run(
            [sys.executable, str(CORPUS_QUERY), q, "--top", "8"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        sys.stdout.write(result.stdout)
        if result.returncode != 0:
            sys.stderr.write(result.stderr)


if __name__ == "__main__":
    main()
