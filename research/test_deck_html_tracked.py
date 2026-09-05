"""No homework deck under research/decks/ may be silently gitignored (bug B-14).

.gitignore:83 ignores research/decks/**/*.html so the tens of thousands of
regenerable deck rebuilds don't get committed by accident. But that rule is
wider than it looks: it also swallowed real, already-built homework
instruments with no warning -- omen-5.2-index-day-deck.html,
omen-5.2-tsla-day-deck.html, omen-5.3-mixed.html,
omen-daily-2026-09-03-s10.html and omen-s-accuracy-100.html were all built,
ignored, and never committed, while three sibling decks in the same directory
(omen-5.1-index-day-deck.html, omen-5.1-tsla-day-deck.html,
omen-trade-anatomy.html) sit right next to them, tracked. This is the same
class of loss CLAUDE.md already names for 5.2's T6 decks: the HTML is the
instrument (answers live in localStorage/.jsonl), so the loss is the ability
to re-serve the same cards and audit what he was shown.

The root cause is the single ignore rule at .gitignore:83. This test walks
every existing research/decks/*.html file and fails if `git check-ignore`
matches any of them -- i.e. it fails before the un-ignore rule is added and
passes after.

    python research/test_deck_html_tracked.py
"""

from __future__ import annotations
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def deck_html_files() -> list[str]:
    return sorted(glob.glob(os.path.join(ROOT, "research", "decks", "*.html")))


def ignored_files(paths: list[str]) -> list[str]:
    if not paths:
        return []
    result = subprocess.run(
        ["git", "check-ignore", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    # git check-ignore prints matched paths on stdout, one per line, and
    # exits 0 if at least one path matched.
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    decks = deck_html_files()
    if not decks:
        print("BLOCKED: no research/decks/*.html files found to check")
        return 1

    ignored = ignored_files(decks)
    if ignored:
        print(f"FAIL: {len(ignored)} of {len(decks)} deck HTML files are gitignored:")
        for path in ignored:
            print(f"  {os.path.relpath(path, ROOT)}")
        return 1

    print(f"PASS: all {len(decks)} research/decks/*.html files are trackable (none gitignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
