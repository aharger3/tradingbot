# B3 bug fixes — B-14

Five homework decks that had been silently gitignored are now tracked, and the
rule that swallowed them can no longer swallow a sixth.

## B-14 — deck HTML instruments silently gitignored

- **Root cause**: `.gitignore:83` (`research/decks/**/*.html`) ignores every
  deck HTML file with no exception, including built homework instruments.
  Three sibling decks in the same directory were already tracked, proving the
  un-ignore intent existed but was never written down. This is the same loss
  class as 5.2's T6 decks (CLAUDE.md, "never lose a mark").
- **Fix**: added `!research/decks/**/*.html` immediately after the ignore rule
  in `.gitignore`, then `git add -f` on the five affected files:
  `omen-5.2-index-day-deck.html`, `omen-5.2-tsla-day-deck.html`,
  `omen-5.3-mixed.html`, `omen-daily-2026-09-03-s10.html`,
  `omen-s-accuracy-100.html`.
- **Test**: `research/test_deck_html_tracked.py` walks every
  `research/decks/*.html` file and fails if `git check-ignore` matches any of
  them. Failed (5/8 ignored) before the `.gitignore` fix, passes (0/8 ignored)
  after.
- **Verify gate**: `research/regression_gate.py` and
  `research/test_runner_stop.py` both pass unchanged — this fix touches only
  `.gitignore` and adds a new standalone test file, no signal or trade logic.
- **Scope note**: `research/decks/_retired/*.html` (7 files) remain untracked.
  They are outside B-14's failing input (which named the five files above)
  and outside `research/decks/README.md`'s active list — left alone, not part
  of this fix.
- **Commit**: `b8acefd6` — "B3 B-14: un-ignore research/decks/**/*.html and
  recover 5 swallowed homework decks (base f8740f80)"
