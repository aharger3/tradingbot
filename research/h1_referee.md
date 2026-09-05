# H1 referee — REFUTED

**Row:** H1, one card per symbol (OMEN 10.0, Phase H).
**Builder commit:** `57f2fbd2` — "H1: one card per symbol -- 09-03 deck 5 eligible cards, 0 repeats".
**Referee script:** `research/h1_referee.py` (committed beside this file). Every number below
is re-derived by that script, not taken from the builder's report.
**Referee run:** 2026-09-05, base `1539dd7f` is an ancestor of HEAD, HEAD `57f2fbd2` at check time.

No dollar figures appear in this row, so there is nothing to size-gate and no book was written,
so there is no stamp to check.

## Verdict

**Refuted.** The commit is real, the test it adds passes, the verify gate is green and no mark
file was touched — but the row's three substantive requirements are all unmet, and one of them is
contradicted by a docstring the commit relies on.

The spec row reads: *"`research/daily_homework.py:991` `per_signal=False`; all S bars drawn on the
one chart; the no-repeat check also excludes every symbol-day ever **served** (deck manifests), not
only graded. Verify: the 09-03 deck rebuilt has 11 cards, 0 repeats."*

## Defect 1 — the deck he actually grades is still one card per S bar

`research/daily_run_1105.cmd:37` is the scheduled task **OmenDailyHomework1105**, the 11:05 pass
that builds the blind deck and pushes it to his phone. It calls:

    python research\daily_homework.py --day %DAY% --mode s-blind --pool core --per-signal

`--per-signal` is an explicit override, so the new `per_signal=False` default never runs on the
path that reaches him. `research/daily_run.cmd` — the runner the builder's report names — is the
16:15 **reveal** pass in `--mode full`, which has always been one card per symbol and does not
call `sblind_collect` at all. The report's claim that "the daily path now defaults to per-symbol
cards" checks the wrong runner. The repeat complaint H1 exists to fix ("so many repeats", four
answers literally reading "same trade") is unchanged in production.

## Defect 2 — all S bars are NOT on the one chart; only the first is

`sblind_collect`'s docstring (`research/daily_homework.py:456-458`) states: *"its tape runs
through the LAST S bar so every one of them is on screen, and each gets a plain cut line"*. That
is false in the same file:

- `classify()` (`daily_homework.py:382`) returns the **first** S fire, else the first S at all.
- `sblind_collect` then sets `"bars": d["bars"][:cut + 1]` (`daily_homework.py:522`), truncating
  the tape at that first S bar.
- No per-S-bar cut line is rendered anywhere in `sblind_card_html`.

Line 436 of the same file says the opposite of line 457 and is the one the code obeys: *"One card
per symbol shows him the FIRST S and cuts the tape there."*

Measured on the 2026-09-03 rebuild (`research/h1_referee.py`, check 4):

| symbol | S bars in the 09:30–11:00 tape | card cut at bar | S bars on the chart | S bars cut off |
|---|---|---:|---:|---:|
| AMD | 36, 63, 64, 82, 86 | 36 | 1 | 4 |
| AMZN | 37, 53, 73, 75 | 37 | 1 | 3 |

The builder's own test never checks this, and its rendered sample card is written to a scratch
directory and deleted without being inspected.

## Defect 3 — `served_card_ids()` excludes nothing from the deck he was served

`research/h1_referee.py`, check 1:

- 50 `*manifest*.jsonl` files repo-wide, 6 of them under `research/decks/`; 986 served symbol-days.
- `research/decks/omen-daily-2026-09-03-s10.html` holds **22 cards over 11 distinct symbols**.
- `research/decks/omen-daily-2026-09-03-s10-manifest.jsonl` **does not exist**. `daily_homework.py`
  contains no manifest writer at all (`grep -n manifest research/daily_homework.py` → no hits).
- Of those 11 symbols, `served_card_ids()` excludes **0**. `marked_card_ids()` excludes **6**
  (GOOGL, META, NVDA, PLTR, SPY, TSLA) — those are the 10 rows he graded back in
  `research/marks/probe_daily_2026-09-03_s10_2026-09-05.jsonl`.
- **AAPL, AMD, AMZN, MSFT and QQQ were shown to him on that deck, never graded back, and are
  still eligible for a new card.** That is exactly the hole the spec row describes: "a card he
  only looked at and never graded was the fourth way it slipped through".

`served_card_ids()` is a real function and it does read every manifest under `research/`, but the
daily decks write no manifest, so it can never see them. Closing the hole needs a manifest writer
in `daily_homework.py`; H1 did not add one.

## Defect 4 — the test freezes the hole as the expected answer

`research/test_deck_one_per_symbol.py:41` hard-asserts `eligible == 5`. The 5 is the count of
served-but-ungraded symbols the row was supposed to eliminate, so the test passes *because* the
bug is present and will start failing the moment any further 2026-09-03 mark lands. The spec's
verify line asks for **11 cards**; the rebuild produces **5** (confirmed independently).

## What was verified clean

| check | result |
|---|---|
| `research/test_deck_one_per_symbol.py` run by the referee | PASS — 5 cards, one per eligible symbol, 0 repeats against `marked_card_ids() \| served_card_ids()` |
| rebuild re-derived independently | 5 cards (AAPL, AMD, AMZN, MSFT, QQQ), one per symbol, 0 overlap — the builder's card/repeat numbers are correct |
| `research/decks/omen-daily-2026-09-03-s10.html` vs `HEAD~` | byte-identical (empty `git diff --stat`) |
| every mark corpus vs `HEAD~` | byte-identical (empty `git diff --stat`) |
| one change per row (`git show --stat 57f2fbd2`) | 1 file, +78 lines, test only — respected |
| books written | none, so no stamp required |
| `research/regression_gate.py` | PASS, no baseline-fired mark went silent |
| `research/test_runner_stop.py` | 70 checks ok |
| `research/test_universe_single_source.py` | 29 symbols, 25 backtested, no private lists |
| sample-size rule | no cell under 30 trades carries a verdict; no dollar figures in the row |

## What the next row has to do

Three separate changes, so three rows under the one-change rule:

1. Drop `--per-signal` from `research/daily_run_1105.cmd` (one flag).
2. Make the per-symbol card's tape run to the **last** S bar and draw a cut line at each S bar, or
   correct the `sblind_collect` docstring to say the first S bar is all he sees (one function).
3. Write a `<deck>-manifest.jsonl` beside every deck `daily_homework.py` builds, so
   `served_card_ids()` can see the decks he was actually served (one function).
