# T1 referee — REFUTED

**Row:** T1 — `research/build_tape.py` → `research/tape/omen-tape.html`
**Builder commit:** `a94948d93c0ce06d389b620830185a2099979448`
**Referee base:** HEAD = `a94948d9`, `1539dd7f` is an ancestor, HEAD == `origin/main`. Base check passes.
**Referee scripts (committed beside this note):** `research/t1_referee.py`, `research/t1_referee_pagejs.js`
**Referee model:** told to refute; every number below was re-derived from the stamped
`.json.gz` books in `research/tape/` and from the JSON physically embedded in the shipped
HTML, not read out of the builder's report.

## Verdict in one line

The page does not run. All seven facets T1 exists to add are declared in the payload but
never encoded, so the page's own `defaultSel()` throws a `TypeError` on load and **nothing
renders** — no rail, no scoreboard, no equity curve, no trade table, no fill-mode table.
The `-$52/day` headline is real and reproduces, but it is produced by a Python function in
the builder, not by the artifact the row was supposed to deliver.

---

## Defect 1 (fatal) — the seven new facets are never encoded

`research/build_tape.py:406`

    dicts, cols = base_encode(rows)

`base_encode` is `build_bt2y_report.encode`, and its first line is
`fields = [f for f, _ in FACETS] + STRS` — where `FACETS` resolves in **its own module's**
globals, i.e. the original 26-facet list. `build_tape.py:87` builds a *new* list
(`FACETS = BASE_FACETS + EXTRA_FACETS`) and never rebinds `build_bt2y_report.FACETS`, so the
encoder has no idea the extra fields exist. Same for `MULTI` vs `MULTI_FIELDS` (`:88`).

Measured on the committed artifact (`research/t1_referee.py`, check A):

| | |
|---|---|
| facets declared in the payload | 33 |
| present in `dicts` / `cols` | 26 |
| **missing** | `source`, `fillmode`, `lane`, `policy`, `wk`, `exitmodel`, `instrument` — all seven of T1's additions |

## Defect 2 (fatal, consequence of 1) — the page throws on load

`research/build_tape.py:333-343` replaces `defaultSel()` with four `pick()` calls on exactly
those missing fields, and `defaultSel()` is called at top level of the page IIFE. Running the
page's own script under a DOM shim (`node research/t1_referee_pagejs.js`):

    PAGE_JS_RESULT: THREW TypeError: Cannot read properties of undefined (reading 'indexOf')
      at pick (<anonymous>:33:26) → defaultSel (<anonymous>:36:3) → eval (<anonymous>:41:1)

`defaultSel()` is the third statement executed. Everything after it — `buildRail`,
`renderKPIs`, `drawEquity`, the breakdown, the trade table and the appended fill-mode table —
is dead. The 9.14 MB file is a blank shell with 9 MB of unreachable JSON in it.

This is not a stale artifact: rebuilding from the committed script
(`python research/build_tape.py --out <scratch>`) produces the identical missing-facet set.

## Defect 3 — the row's own test cannot catch either of the above

`research/test_tape.py` calls `load_rich_sources()` / `compute_default_selection_stats()` —
builder-side Python — then greps the HTML for `<canvas>` and `<script src=`. It never opens
the embedded payload, never checks that a declared facet has data, and never executes a line
of the page's JS. It printed `ALL PASS` against a page that cannot render. The row's stated
verify ("totals for the unfiltered honest selection equal R3's baseline to the dollar")
was checked against a list of dicts in memory, not against the deliverable.

## Defect 4 — "duplicate count 0" holds only under a redefined key

The row's verify is *"one row per (symbol, day, entry minute); a self-check counts duplicates
and fails the build above zero."* `research/build_tape.py:294-297` keys on eleven fields
(`source, fillmode, sym, day, et, dir, entry, stop, pnl, status, level_name`). Counted on the
spec's three-field key, traded rows only (`research/t1_referee.py`, check D):

| key | dupe keys | extra rows |
|---|---:|---:|
| spec key `(sym, day, et)`, inside `baseline`/`close` alone | **151** | **160** |
| spec key `(sym, day, et)`, per source+fill across all 7 merged books | **963** | **1,020** |
| builder's 11-field key | 0 | 0 |
| spec key, inside the published 769-row default selection | **5** | 5 |

All 151 baseline collisions carry the **identical entry price** and differ only in
`level_name` — so the phenomenon the builder describes is real, and the decision not to
collapse them (it would move R3's published number) is defensible. What is not defensible is
reporting "duplicate count: 0" against a verify line that names a different key, and
disclosing the size as "127 pairs across the merged books" when the baseline book alone holds
151 and the merged set holds 963. Examples inside the published unit:
`AMZN 2024-11-04 09:45`, `QQQ 2025-01-24 09:54`, `META 2025-10-29 09:41`,
`GOOGL 2025-12-30 09:37`, `NVDA 2026-02-19 09:40`.

Related: `check_no_repeats` skips rows where `traded` is false, so the 149 `halted` rows that
sit inside the 769-row default selection are outside the duplicate check entirely.

## Defect 5 — every Phase-L book is labelled "hold"; one of them shipped

`research/build_tape.py:218` hardcodes the string `"all held --> hold (cycles.md)"` into the
provenance note for all five L sources. `research/tape/cycles.md` records `DAY_POLICY` as
**ship** (row: "up to three trades a day … | ship"). Build-time output only — it is not in the
page — but it is a wrong statement about a settled decision, printed by the committed script.

## Defect 6 — metrics the row asked for are not on the scoreboard

The row lists: *$/day, total, mean R, **avg win / avg loss**, win rate, profit factor, months
green, **weeks green**, max drawdown, **fires/day**, trades.* The scoreboard
(`renderKPIs`, inherited unchanged from `build_bt2y_report.py`) shows Signals, Win rate, Mean
R, Total R, Profit factor, Max drawdown (in R), Worst losing run, Months green, Avg hold.

Absent: **$/day**, **avg win / avg loss** (the "2:1" half of his target), **weeks green**,
**fires/day**. The equity curve and drawdown are in R only; there is no dollar curve. Per-symbol
comes free from the inherited Breakdown tabs. None of these were added, and none would appear
even after Defect 1 is fixed.

## Defect 7 — the README describes a page that does not exist

`research/tape/README.md`'s "What every filter reads" table documents the source, fillmode,
lane, policy, week, exit-model and instrument filters, and states the page "opens on" the R3
default. None of those filters are in the shipped page, and it opens on a JavaScript error.

---

## What is upheld

**The headline number reproduces.** Re-derived by `research/t1_referee.py` check C, with my
own re-implementation of the day policy (not the builder's import):

> Unit: **up to 3 fires a day, stop after the first win or the second loss**, core-11
> (`tier == "core"`, verified to be exactly `universe.CORE_SYMBOLS`), **honest close fill**,
> shipped ladder exit (`SCALE_PLAN=hod_then_runner_be`, 1R hard stop on the intrabar touch),
> 1R = $1,000, book `research/tape/baseline_2026-09-05.json.gz` (`book_id 2c39ced2697c26cc`,
> commit `29e4abc632`, 499 sessions 2024-09-04 → 2026-09-04), script `research/t1_referee.py`.

| | referee | `loop.json` baseline_figures.whole |
|---|---:|---:|
| trades | 769 | 769 |
| $/day | −$52 | −$52 |
| mean R | −0.0335 | −0.0335 |
| win rate | 45.0% | 45.0% |
| avg win / avg loss | $801 / $716 = 1.119 | $801 / $716 = 1.119 |
| months green | 11 / 25 | 11 / 25 |
| weeks green | 45 / 105 | — |

(Max drawdown differs by ordering convention — $51.1k sorting on `(day, et)`, $54.5k in the
builder's `(day, et, sym)` row order. Drawdown is order-sensitive inside a day; neither is
wrong, but the page would need to say which it uses.)

**Other builder claims that check out.**
- 149 of the 769 rows are `status == "halted"`, `traded == False`, summing −$5,925. The
  "undercount by 149 of 769" fix is real.
- `skipped_d` = 106,217 of 127,513 baseline signals. Correct.
- Baseline and phantom books share commit `29e4abc632` **and** build timestamp
  `2026-09-05T18:16:19` — same day, same base, A/B-legal. (They are still not *shown* side by
  side, because the `fillmode` facet is missing.)
- All five Phase-L **OFF** books carry `book_id 2c39ced2697c26cc`, identical to the baseline,
  so merging only the ON arms and treating `source=baseline` as the OFF arm is sound.
- No `<canvas>`, no external `<script src>`. There is one external stylesheet
  (`fonts.googleapis.com`, inherited from `build_bt2y_report.py`) — not a script, but it means
  the page is not fully offline on a phone.
- No hard-coded forecast dollars in `research/build_tape.py`. The only hard-coded figures are
  `test_tape.py`'s `R3_BASELINE`, quoted from `research/tape/loop.json`.
- One change per row respected: 4 files, all owned by the row, no engine file touched.
- **No mark file touched** (`git show --name-only a94948d9`: `research/build_tape.py`,
  `research/test_tape.py`, `research/tape/README.md`, `research/tape/omen-tape.html`).
- **Verify gate green at `a94948d9`**, run by me: `regression_gate.py` PASS,
  `test_runner_stop.py` 70 checks ok, `test_universe_single_source.py` ok.

## The five filter combinations (row-specific check)

Chosen with `random.Random(20260905)` over the facets that actually exist, evaluated by
transcribing the page's own `passes()` into Python and running it on the embedded columns,
then recomputed from the books. Recorded in full in `research/t1_referee.py` check E.

| # | combination | page (7 books merged) | `baseline`/`close` alone | trade inflation |
|---|---|---:|---:|---:|
| 1 | `out=loss`, `level=PDL` | 1,517 trades, −$2,339/day | 501 trades, −$821/day | 3.03× |
| 2 | `slot=10:00`, `yr=2026` | 9,028 trades, −$1,067/day | 3,195 trades, −$920/day | 2.83× |
| 3 | `status=skipped_tight_stop`, `grade=B` | 143 trades, +$13/day | 143, +$13/day | 1.00× |
| 4 | `grade=C`, `dir=put` | 6,185 trades, −$87/day | 6,185, −$87/day | 1.00× |
| 5 | `sym=NVDA`, `status=skipped_tight_stop` | 374 trades, +$70/day | 374, +$70/day | 1.00× |

**No trading verdict is attached to any cell above** — combo 2 spans 9 months, under the
12-month floor, and every cell here is a diagnostic of a construction bug, not a measured
edge. What they show: combos 1 and 2 select rows the comparison books also contain, so the
page sums the same 499 sessions up to three times over and there is no `source` facet left to
separate them. Combos 3–5 match 1.00× only because those filters happen to select rows the
trimmed comparison books never kept. A reader cannot tell which case they are in.

The two combinations the row's verify actually demands are unrunnable:

- `source=baseline, fillmode=close, lane=core11, policy=up_to_3` — all four fields absent.
- `source=L3_on, fillmode=close, lane=index3` — three of three absent.

## Smallest fix that would make this row true

One line: give `encode()` the extended field list — either rebind
`build_bt2y_report.FACETS`/`MULTI` before calling it, or (cleaner) add a `fields=` /
`multi=` parameter to `encode()` and pass `FACETS` / `MULTI_FIELDS`. Then add to
`test_tape.py` an assertion that every facet in the payload has a `dicts`/`cols` entry and
that the four default picks resolve to a code, and re-measure. Defects 4–7 stand on their own
after that.
