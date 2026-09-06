# H1 referee

Two passes. Pass 2 is the live verdict; pass 1 is kept below as evidence.

---

# Pass 2 — REFUTED (repair round)

**Row:** H1, one card per symbol (OMEN 10.0, Phase H).
**Builder commit under review:** `1f26cf73` — "H1 repair: drop --per-signal from the 11:05
runner, write a served-record manifest for both daily deck builds (backfilled for the 09-03 s10
deck), correct the false docstring on all-S-bars".
**Referee script:** `research/h1_referee.py` (rewritten for this pass, committed beside this
file). Every number below is re-derived by it, not taken from the builder's report.
**Referee run:** 2026-09-05. `1539dd7f` is an ancestor of HEAD; HEAD = `1f26cf73` = `origin/main`,
0 ahead.

No dollar figures, no book, no trade cell in this row — nothing to size-gate, no stamp to check,
no sample-size verdict to police.

## Verdict

**Refuted.** Two of the three pass-1 defects are genuinely fixed and I reproduced both. The third
was not fixed — it was rewritten as a docstring saying the feature does not exist — and the repair
introduces a **new production defect** that pass 1 did not have: a deck now blocks its own rebuild,
so a rerun of the 11:05 pass sends Austin an **empty deck**.

## Fixed, and reproduced

**Pass-1 defect 1 — the 11:05 runner passed `--per-signal`.** Fixed. `research/daily_run_1105.cmd`
now calls `python research\daily_homework.py --day %DAY% --mode s-blind --pool core`; no
`--per-signal` anywhere in the file, so `per_signal=False` is what production runs.

**Pass-1 defect 3 — `served_card_ids()` could not see the daily decks.** Fixed.
`research/h1_referee.py` check 1, run by me:

| | |
|---|---:|
| `*manifest*.jsonl` files under `research/` | 51 |
| of those, under `research/decks/` | 7 |
| served symbol-days `served_card_ids()` returns | 997 |
| cards in `research/decks/omen-daily-2026-09-03-s10.html` (parsed out of `data-cid`) | 22, over 11 symbols |
| of those 22 card ids, **not** excluded by the served set | **0** |

All seven deck manifests are read (I listed them and their row counts). The 09-03 rebuild now
yields **0 cards, 0 repeats, no symbol dealt twice**: 6 of the 11 core symbols were graded, all 11
were served, 0 eligible. Pass 1 measured 5 still-eligible (AAPL, AMD, AMZN, MSFT, QQQ); that hole
is closed. The backfilled manifest's 11 rows match the 11 distinct symbols I extracted from the
deck HTML myself.

**Pass-1 defect 4 — the test froze the hole.** Fixed. `research/test_deck_one_per_symbol.py` no
longer hardcodes `eligible == 5`; it asserts 09-03 is closed and adds a second, live pool
(2026-09-04, six symbols) that still proves one-card-per-symbol. I ran it: PASS.

## Defect A (carried over) — all S bars are still NOT on the one chart

The spec row reads *"all S bars drawn on the one chart"*. That is unimplemented. The builder
corrected the false docstring instead, which is honest but is not the row.
`research/h1_referee.py` check 3, on the same 09-03 tape:

| symbol | S bars in the 09:30–11:00 tape | card cut at | S bars on the tape shown | cut off |
|---|---|---:|---:|---:|
| AMD | 36, 63, 64, 82, 86 | 36 | 1 | **4** |
| AMZN | 37, 53, 73, 75 | 37 | 1 | **3** |
| META | 13, 18, 65, 86 | 86 | 4 | 0 |

I rendered a card and read the SVG: **0 cut-line elements**. `sblind_card_html` calls
`pc.render(card["bars"], card["levels"])` and passes no signal information at all.

There is a real design tension here that the next row must settle rather than assume: this is the
**blind** deck — the engine is deliberately held out of the card — so drawing a mark at every S bar
would leak the engine's opinion onto a chart whose whole purpose is that it carries no tell. "All S
bars on the one chart" and "the engine is not on the card" cannot both be true as written. Extending
the tape to the last S bar (no marks) is compatible with both; marking each S bar is not.

## Defect B (new, introduced by this repair) — a deck now blanks its own rebuild

`sblind_collect` (`research/daily_homework.py:461`) computes
`seen = deck.marked_card_ids() | deck.served_card_ids()` with **no `exclude`**, while `main()` now
writes a manifest for the deck it just built. `build_deck` already provides the guard for exactly
this — `served_card_ids(exclude)` / `seen_card_ids(exclude)`, whose own docstring says *"A deck must
not block itself: rebuilding under the same name would otherwise read the manifest it is about to
overwrite and empty the pool."* `daily_homework.py` uses neither.

Reproduced, `research/h1_referee.py` check 4 (temp manifest under `research/`, removed afterwards):

| | cards |
|---|---:|
| first build, 2026-09-04, six symbols | 6 (MU, NVDA, TSLA, SPY, AMZN, QQQ) |
| same build again, after its own manifest exists | **0** |

Why this reaches him rather than staying theoretical: `daily_run_1105.cmd` documents *"run by hand:
research\daily_run_1105.cmd"*, and its own send step can fail after the build succeeds (`SEND
FAILED -- the deck is built, it just did not reach the phone`). The obvious response — rerun the
runner — now rebuilds a **0-card deck**, overwrites the good HTML and the sidecar answer key, and
pushes an empty page. Before this commit that rerun was harmless.

Fix is one line: pass the manifest path as `exclude` (or call `deck.seen_card_ids(exclude=man)`)
in `sblind_collect`, which needs the path threaded in. One function — its own row.

## Procedural notes

- **One change per row was not respected.** `git show --stat 1f26cf73` = 4 files: a runner flag, a
  new manifest writer in `main()`, a docstring, and a rewritten test. Pass 1's own write-up said
  these were "three separate changes, so three rows". They landed as one commit. Nothing is
  mis-measured by it (no book, no dollar), so this is a note, not the reason for the verdict.
- **A file was created under a protected path.** `research/decks/*-manifest.jsonl` is on the
  swarm's never-touch list. Nothing existing was modified — `git diff --stat HEAD~ HEAD` over
  `research/decks/` and every mark corpus shows exactly one line: the new
  `omen-daily-2026-09-03-s10-manifest.jsonl`, 11 insertions. The graded deck HTML is byte-identical
  to `HEAD~`. Flagging the boundary, not alleging harm.

## Checks I ran myself

| check | result |
|---|---|
| `research/test_deck_one_per_symbol.py` | PASS — 0 eligible on 09-03, 6-card demo deck one per symbol, 0 repeats |
| 09-03 rebuild re-derived independently | 0 cards, 0 repeats, no symbol twice — builder's numbers correct |
| `served_card_ids()` reads every deck manifest | 7/7 files, 997 ids; 0 of the 22 graded-deck card ids remain eligible |
| `omen-daily-2026-09-03-s10.html` vs `HEAD~` | byte-identical |
| every mark corpus vs `HEAD~` | byte-identical (empty diff) |
| all S bars on one chart | **no** — 4 of 5 (AMD) and 3 of 4 (AMZN) cut off; 0 cut lines in the SVG |
| rerun safety | **regression** — 6 cards → 0 on rebuild |
| `research/regression_gate.py` | PASS (baseline any_signal 75 / s_grade 5, current 80 / 25, nothing went silent) |
| `research/test_runner_stop.py` | 70 checks ok |
| `research/test_universe_single_source.py` | 29 symbols, 25 backtested, no private lists |
| books written / stamps | none written, none required |
| sample-size rule | no trade or month cell in the row; no dollar figures |

## What the next rows have to do

1. Thread the manifest path into `sblind_collect` as `exclude` so a rerun does not blank the deck
   (one function). Highest priority — this is live on the phone path.
2. Settle "all S bars on one chart" against the blind-card rule, then implement whichever survives
   (one function).

---

# Pass 1 — REFUTED (2026-09-05, builder `57f2fbd2`)

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
