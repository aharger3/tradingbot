# Fixing the deck builder that showed the wrong chart

*2026-08-30. Follow-up to `research/g77_wrongchart.md`. No deck was built or served —
this fixes the instrument and proves the fix with a test.*

## 1. The finding, checked again independently

Re-ran `research/g77_wrongchart_counterfactual.py` cold, against the same 30 served cards
and the same two-year book. It reproduced, unchanged:

| | |
|---|---:|
| Cards that were a trade the engine actually took | **5 of 30** (4 of those 5 got a yes) |
| Cards where the engine traded something else on that same chart | **10 of 30** — but the *counterfactual* re-pick (which also drops thin/short-session days) counts it as **14 of 30** "same chart, different signal" |
| Cards where the engine refused the whole chart all morning | **15 of 30** |
| Book-wide: the engine's own first trade of the day is not an S on Austin's ladder | **3,228 of 3,740 symbol-days = 86%** |

(The 5/10/15 in the original write-up and the 5/14/15 the counterfactual script prints are
the same underlying finding counted two slightly different ways — the doc's "10" excludes
one case the script folds into "different signal." Both numbers are real and both survive
re-running.) I did not need to change or re-derive the script — it already existed and is
read-only against the book. Confirmed loudly reproducible, not a one-off.

## 2. What was actually broken

`research/g71_homework_build.py::load_s_days` picked its one representative signal per
symbol-day by **belief alone**: Austin-ladder S grade, fewest downgrades, earliest minute.
It never read the `traded` field. So on any day the engine's real trade wasn't the strongest
S-graded signal — which is 86% of the time, book-wide — the card could not show the real
trade even by accident.

A guard (`g77_realtrade_pick.guard`) had already been added that refuses to publish a deck
unless every card is a booked trade. That is not the right fix on its own: run as-is, it
would delete the 15-of-30 engine-silent-day cards entirely, and those are the most valuable
cards in the deck — a yes on a silent day is a pure miss, proof the engine should have fired
and didn't. The task was to build a *deliberate mix*, not to throw away half the deck.

## 3. The fix

`load_s_days` now assigns every symbol-day one of exactly two roles, decided before belief
strength ever enters the picture:

- **role "traded"** — the engine's own first booked trade of the session
  (`g77_realtrade_pick.day_trade`) is itself the S-graded signal. The chart's bucket
  (84%-rule / one-candle-rule / break-and-retest) is that trade's own setup, not a guess.
- **role "silent"** — the engine booked nothing on that chart, all session. The strongest
  eligible S signal stands in, same selection as before (fewest downgrades, earliest
  minute), but now labelled honestly as a refusal, not passed off as a trade.

A third case — the engine booked a trade, but not the S signal a bucket would otherwise show
— is dropped outright. That is the wrong-chart bug itself (14 of the original 30 cards), and
showing that signal at all reproduces the exact defect this rebuild exists to fix.

**The quota, stated in code:** `TRADED_QUOTA_FRAC = 0.5` in `g71_homework_build.py` — half
of each bucket's cards should be role "traded," the rest role "silent." That matches
`build_deck.py`'s own long-standing "half fires, half silent" standard for the main 60-card
deck, so it isn't a new number invented for this page. `pick()` fills traded candidates
first, up to the target, then backfills with silent; if a bucket can't supply enough traded
candidates it says so explicitly (`** QUOTA SHORT **`) instead of padding.

Run against the live book at `--slates 10` (dry run, nothing written):

```
  84  eligible after no-repeat: traded 0, silent 2
  OCR eligible after no-repeat: traded 3, silent 44
  BR  eligible after no-repeat: traded 111, silent 868
stated quota: 5/10 traded per bucket (50%), rest silent
  84  picked 2/10 (traded 0, silent 2)   ** SHORT **  ** QUOTA SHORT: 0/5 traded **
  OCR picked 10/10 (traded 3, silent 7)  ** QUOTA SHORT: 3/5 traded **
  BR  picked 10/10 (traded 5, silent 5)
```

**84% almost never has a "traded" candidate to offer**, book-wide: only **4 raw symbol-days
in two years** have the engine's own booked first trade land as an S-graded 84%-rule signal
(against 398 for break-and-retest and 110 for one-candle-rule). That lines up with the
original finding that 84% is the arm that loses money — it rarely becomes the day's actual
trade even when the engine believes it's an S. The fixed builder reports that shortfall
loudly (`QUOTA SHORT`) rather than quietly filling the 84% bucket with a signal that isn't
honest about what the engine did.

The `traded`/`sgrade`/`downgrades`/`outcome` fields stay exactly where they were — written to
the manifest, deliberately never rendered on the page. The new `role` field is derived
directly from `traded` and is exactly as sensitive, so it gets the same treatment: recorded
in the manifest (along with `traded_quota_frac` and the per-bucket `bucket_target_traded`),
never in the HTML. Confirmed by rendering one card of each role and checking the HTML and the
card's own export blob for every answer-key term — see the test below.

## 4. The self-check: `research/test_deck_selection.py`

Calls `pick()` directly — read-only against the two-year book and the local price archive,
never `main()`, never writes to the real `OUT_HTML`/`OUT_MANIFEST` paths — and asserts:

1. `TRADED_QUOTA_FRAC` is a real, stated fraction, and every bucket's actual traded count is
   **capped** by it, not just influenced by it (a regression that reverts to "grab every
   traded candidate available" would blow past the 5/10 target for break-and-retest, where
   traded candidates are plentiful — the test catches that, not just an empty-quota case).
2. Every served card's role is **independently re-derived from the book** (not trusted from
   the label the builder attached) and matches `g77_realtrade_pick.day_trade` exactly —
   including that a "traded" card's setup and minute match the engine's real first trade, not
   merely that *some* trade happened that day.
3. No card survives selection where the engine traded something else on the same chart — the
   specific 14-of-30 defect.
4. The rendered HTML and the card's own export blob for a traded-role card AND a silent-role
   card carry none of `traded` / `role` / `sgrade` / `downgrade` / `outcome`.
5. The manifest actually records `role` and the quota fields on every row.

Ran green:

```
PASS  TRADED_QUOTA_FRAC is stated: 0.50
PASS  every bucket's traded count is <= the stated per-bucket quota
PASS  every card's role independently matches g77_realtrade_pick.day_trade (8 cards, 4 traded / 4 silent)
PASS  no card was built from a signal the engine set aside for a different trade
PASS  rendered HTML carries no answer-key term, for a traded-role and a silent-role card
PASS  the manifest records role and the stated quota for every card
OK
```

**Proved the check has teeth**, not just a pass on trivial input: fed `g77_realtrade_pick.role_guard`
two synthetic cards reproducing the exact old bug pattern (a card labelled role="traded" whose
book row was never booked; a card labelled role="silent" whose book row WAS booked) and both
correctly raised `AssertionError`.

Also re-ran the two protected gates and the existing g77 guard test — all still green and
untouched by this change: `research/regression_gate.py` (PASS, 83 fires against baseline 75,
none silent), `research/test_runner_stop.py` (18 laddered results, floored at −1.25R), and
`research/g77_realtrade_pick_test.py` (still catches 25 of 30 refusals in the old served
deck; still passes the 39-card g75 deck at 0 refusals).

## 5. What this does not do

- **No deck was built or served.** `main()` in `g71_homework_build.py` was edited (new
  `--traded-quota` flag replacing the old `--allow-untraded` escape hatch, and the guard call
  swapped for `role_guard`) but never executed to completion in this session. `research/g71_homework.html`
  and `research/decks/g71-homework-s3-manifest.jsonl` are untouched — the manifest still holds
  the 30-card deck Austin already graded, which the no-repeat guard still needs intact.
- **It does not move a dollar.** This is an instrument-correctness fix, not a backtest
  result. Nothing here changes the book, the recall gate, or a mean-R number.
- It does not solve 84%'s scarcity of real traded days — that's a fact about the arm (it
  rarely becomes the actual trade), now surfaced loudly instead of hidden by a builder that
  never looked.

## Files touched

- `research/g71_homework_build.py` — `load_s_days` now assigns role "traded"/"silent"/dropped
  before picking a representative row; `pick()` fills each bucket to a stated per-bucket
  quota (`TRADED_QUOTA_FRAC = 0.5`, traded capped and backfilled with silent); `write_manifest`
  records `role`, `traded_quota_frac`, `bucket_target_traded`; `main()` calls
  `realtrade.role_guard` and takes `--traded-quota` in place of the old `--allow-untraded`.
- `research/g77_realtrade_pick.py` — added `role_guard`, alongside the existing `guard` (still
  used by its own test, untouched).
- `research/test_deck_selection.py` — new, the self-check above.
