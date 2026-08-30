# G82 — cleaning up the OMEN 7.1 verdict sheet

Austin, tonight: *"The artifact that I get, we can keep updating it the same way it
is, but it has a lot of issues -- random repeats, and some metrics that are not
very clean."*

Target: `research/omen-71-verdict.html` (284 lines, committed whole in `a0997963`).

## First finding: there was no generator

I searched the full repo history (`git log --all --diff-filter=A -- "*verdict*.py"
"*verdict*.html"`) and every `research/*.py` file for any script that writes to
`omen-71-verdict.html`. There isn't one. The commit that added the page added only
the HTML — 284 lines, hand-authored, no companion script. That is itself the
"not very clean" problem: `CLAUDE.md` says *"If you publish a number, commit the
script that made it,"* and this page broke that rule from the day it was
committed. It also explains why the two numbers below went wrong and nobody
caught it — nothing regenerates this page from data, so a typo just sits there.

I wrote `research/g82_artifact_cleanup_build.py` to be that script. Running it
reads `research/t23_stack.json` (the file `research/t23_stack.py` already
produces) and reprints the page with the "What moved" table's two error-column
cells re-derived from it instead of hand-typed. Everything else on the page is
unchanged template text — see the diff below.

## Repeats

I read the whole page line by line looking for a duplicated row, paragraph, or
number the way the prompt described (same trade counted twice, a section two
scripts both appended to). **I did not find one.** All 10 rows in the "What
moved" table are distinct metrics, no action item repeats another, and the
"scale-out leg counted as a separate trade" hypothesis does not apply here: the
book this page cites (`research/t23_stack.json` / `research/bt2y_trades.json`,
via `t23_stack.py`) stores one row per signal regardless of how many legs its
exit used — `scaled` is a boolean field on the row, not a reason for more rows.
The recurring phrases across sections (recall mentioned in the headline verdict,
the gate box, and the blocker note) are the same fact stated three times on
purpose, at three levels of detail — that is the page's format, and it is the
format Austin said to keep.

So: zero duplicate rows removed. If the "random repeats" Austin is seeing are on
a *different* page (this repo generates several report/*.md and *.html files
that share sections — `backtest_report.md`, `backtest_report_12mo.md`,
`b4_baseline_report.md` vs `b4_gradefix_report.md` do carry identical trade
tables between files, by design, not by accident of one page), that is worth a
separate pass — flagging it below rather than guessing at a fix on a page he
didn't name.

## Unclean metrics — two wrong numbers, both traced and fixed

I checked every number on the page against its cited source
(`research/t23_stack.json`, `research/t23_stack.md`, `research/t0_ratified_rebaseline.md`,
`research/t0_heldout_recall.json`). Two were wrong, both in the "What moved"
table's AFTER column, both in the same row-family (trailing derived cell typed
by hand instead of computed):

1. **Win rate.** Page said `53.1% -> 49.7%` (move `-3.4`). The shipped book's
   actual win rate is **49.5%** — `research/t23_stack.json`
   `arms.stack.win_rate = 49.5`, and `research/t23_stack.md` line 78 prints
   `49.50%` at the same precision. The correct move against the 53.1% baseline
   is **-3.6**, not -3.4. (Two digits wrong, not a rounding artifact — 49.7
   does not round from 49.50 by any reasonable rule.)

2. **Index trades.** Page said `18 -> 137` (`7.6x`). **137 is the wrong
   book** — it's `arms.t0_base.index_trades` in the same JSON, i.e. the state
   *before* the T23 stack landed (X-lift, the stop floor, the loss halt), while
   every other cell in that row's table (traded, mean R, total R, months green)
   reports the state *after* the stack. The shipped book's index trades is
   **164** — `arms.stack.index_trades = 164`, matching `research/t23_stack.md`'s
   own row (`index (ETF) trades | 137 | 164`). Against the 18-trade baseline
   that's **9.1x**, not 7.6x.

Both are now pulled from `research/t23_stack.json` at generation time instead of
typed by hand, so they can't drift from the underlying number again. Nothing
about the measurement changed — same JSON, same script that produced it
(`research/t23_stack.py`), only which field of it landed on the page.

I checked the rest of the checklist and found nothing else:

- **No denominator stated** — every rate on the page (win rate, recall, months
  green) carries its count either inline (`18 / 34`) or in the adjacent row
  (traded count). None found bare.
- **Two metrics computed over different trade counts** — this *is* what the
  two bugs above were (137 was T0-book, everything beside it was T23-book).
  Fixed. No other cross-row mismatch found.
- **A percentage that can't be reproduced from the counts shown** — the fixed
  49.5% now reproduces (`t23_stack.json`); nothing else failed this check.
- **A figure whose source script no longer exists** — the footer cites
  `research/t23_stack.md`, `research/t0_ratified_rebaseline.md`, and
  `Projects/omen-2y-backtest.md`; all three exist, and both `.md` files name
  their own producing scripts (`t23_stack.py`, `t0_rebaseline.py`), which also
  both exist and both still run.

## What I deliberately left alone

- **The "before" column mixes two different milestones on purpose** (T0's
  pre-ratification book for "before", the T23 stack for "after" — skipping
  past T0's own "after" state in the middle). That's not a bug, it's "how much
  changed since we started tonight" — but it does mean the row is a *chained*
  comparison, not a single A/B, and that's worth knowing if you ever pull a
  number from the middle of that chain by hand again, which is exactly how the
  two bugs above happened.
- **The recall row (18/34 -> 23/34) is the harness number**, already flagged
  in the page's own note 1 as measured on the wrong router (real number on the
  traded book: 1/34). I did not touch this — the page already discloses it, and
  fixing the *measurement* wasn't in scope tonight.
- **I did not touch the measurement anywhere.** Every number that changed,
  changed because it was read from `research/t23_stack.json` instead of
  mistyped from it — the number `t23_stack.py` computed never moved.

## What I did not get to

- I did not audit `backtest_report.md`, `backtest_report_12mo.md`, or the
  `b4_baseline_report.md` / `b4_gradefix_report.md` pair for the repeats
  Austin may actually be seeing — those weren't the file named in this task,
  and `b4_baseline_report.md` vs `b4_gradefix_report.md` sharing rows looked
  intentional (two report variants over the same underlying trades) rather
  than a bug, but I didn't chase it further. If that's what he meant, it's a
  same-shaped follow-up.

## Files

- `research/g82_artifact_cleanup_build.py` — new. The generator. Run
  `python research/g82_artifact_cleanup_build.py` to regenerate
  `research/omen-71-verdict.html`; it is idempotent (reads existing JSON,
  writes the same output every time nothing upstream changes).
- `research/omen-71-verdict.html` — regenerated in place. Diffed against the
  committed version: exactly 2 table cells changed (4 lines touched: win rate
  AFTER + MOVE, index trades AFTER + MOVE). Nothing else in the 284 lines
  moved — checked with `git diff`.
