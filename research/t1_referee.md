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

---
---

# T1 referee, PASS 2 — REFUTED (a different, smaller defect)

**Row:** T1 — `research/build_tape.py` → `research/tape/omen-tape.html`
**Builder commit under review:** `380667a6293b380bb7c539798a956c011e6461ab` ("T1 repair"),
the answer to the pass-1 refutation above (builder's first commit was `a94948d9`).
**Referee base check:** `git fetch origin`; HEAD = `380667a6` = `origin/main`;
`1539dd7f` is an ancestor of HEAD; HEAD is an ancestor of `origin/main`. Passes.
**Referee script (committed beside this note):** `research/t1_referee_pass2.py` — it imports
nothing from `build_tape.py`. Every number below is derived twice: once by re-implementing
the page's own client-side `passes()` and patched `stats()` in Python against the JSON
physically embedded in the shipped HTML, and once by loading the stamped `.json.gz` books
directly and re-tagging lane / week / day-policy with this file's own code (the up-to-3 rule
re-implemented from the spec sentence, not imported). The two must agree or it is a page defect.

## Verdict in one line

The pass-1 fatal defect is genuinely fixed — the page renders, all 33 facets encode, and the
headline reproduces to four decimals — but **the phantom fill was never put beside the honest
one; it was put in the same union, and one click from the default view the page prints
+$799.6/day, mean R +0.2816, 21 of 25 months green** from the honest and phantom books added
together. That is the exact number SWARM.md's "the fill, said once, so nobody re-argues it"
section exists to keep off a page, and nothing on the page warns about it.

---

## What pass 1 said, and whether it is fixed

| pass-1 defect | fixed? | evidence |
|---|---|---|
| 1 (fatal) — the 7 new facets are declared but never encoded | **yes** | `encode_extended()` rebinds `build_bt2y_report.FACETS/MULTI` for one call. The embedded payload now carries `dicts`/`cols` for all 33 facets: `source` (6 values), `fillmode` (2), `lane` (3), `policy` (3), `wk` (105), `exitmodel` (1), `instrument` (1). |
| 2 (fatal) — `defaultSel()` throws on load | **yes** | all four default picks resolve; re-implementing `passes()` against the payload selects 769 rows, i.e. the rail and scoreboard have something to render. |
| 3 — the test could not catch it | **yes** | `test_tape.py` now parses the embedded payload, asserts every declared facet has non-empty `dicts`/`cols`, and asserts the four default picks resolve. Run at `380667a6`: `ALL PASS`. |
| 4 — "duplicate count 0" holds only under a redefined key | **no — disclosed, and the disclosure is still wrong** (see Defect A) | count corrected in the README; characterisation still false; self-check key unchanged. |
| 5 — every Phase-L book labelled "hold" though `DAY_POLICY` shipped | **yes** | `flag_decision()` parses `cycles.md`; `DAY_POLICY` now prints `ship`, the other four `hold`. Matches `cycles.md`. |
| 6 — no $/day, avg win / avg loss, weeks green, fires/day | **yes** | all four are in the patched `stats()`/`renderKPIs()`. Re-implemented here they give, on the default view: $/day −51.7, avg win $801.2 / avg loss −$716.0, 45 of 105 weeks green, 1.544 fires/day. |
| 7 — the README describes a page that does not exist | **yes for the page**, **no for two of its sentences** (Defects A and B) | |

---

## Defect A (the refutation) — the phantom fill is summed with the honest one, not shown beside it

The spec's `do:` clause for T1 ends: *"The phantom-fill column is always visible beside the
honest one."* What shipped is a two-value `fillmode` facet in the filter rail. Filter chips in
this engine are a **set union** (`passes()`: `if(!s.has(cols[k][i])) return false` — selecting
two codes admits rows matching *either*), so selecting both fill modes does not put two columns
beside each other, it concatenates two books of the same 498 sessions into one total.

Measured on the shipped page, `research/t1_referee_pass2.py` ("ONE CHIP AWAY FROM THE DEFAULT"),
unit = the page's own scoreboard, core-11, `up_to_3` day policy, shipped ladder exit,
$/day = selection R × $1,000 ÷ days in selection:

| what the reader did | trades | $/day | mean R | months green |
|---|---:|---:|---:|---:|
| the default view (honest close fill) | 769 | **−$51.7** | −0.0335 | 11/25 |
| added the second `Fill mode` chip | 1,414 | **+$799.6** | +0.2816 | **21/25** |
| cleared the one `source` chip | 4,590 | −$309.0 | −0.0335 | 10/25 |
| `fillmode = close`, nothing else | 59,186 | −$2,901.2 | −0.0245 | 8/25 |

Row 2 is the honest book plus the void-fill book, added. It reads as a strategy clearing most of
Austin's $500/day bar with 21 green months. Rows 3 and 4 are the same 498 sessions counted up to
six times, once per merged book.

The word **"phantom" appears zero times in the page shell** — 1 occurrence in the whole 10.41 MB
file, and that one is the string inside the JSON payload. There is no side-by-side column, no
label, no legend, no warning; a reader meets the word as a bare chip. The README's own sentence
— *"Clear a filter and you widen the pool or switch unit; nothing else changes the default"* —
is false: clearing `source` does not widen the pool, it stacks six overlapping books.

Pass 1 raised the stacking hazard and it was not addressed. The repair round made it worse in one
respect: `$/day` was added to the scoreboard, so the stacked arithmetic now prints as a dollar
figure rather than only as an R.

**Smallest fix:** make `fillmode` and `source` single-select (radio, not chip), or render the
phantom as its own second column computed on its own selection. Either is one function.

## Defect B — the near-duplicate disclosure is still wrong, and the committed script still carries the refuted number

The count *was* corrected in the README (151 keys / 160 extra rows in `baseline`/`close`,
963 / 1,020 across the 7 merged sources, 5 inside the 769-row default) — I re-derived all four
independently and they match exactly. Two things did not get corrected:

1. **`research/build_tape.py:325`, the committed script, still says** *"127 pairs across the
   merged sources, same price/pnl, different level name."* Both halves are wrong and the
   correction landed only in the README. The rule here is that the script that made a number
   carries it.
2. **"same price/pnl … priced identically" is false for most of them.** Of the 151 duplicate
   keys in `baseline`/`close`: 151 share an entry price, but only **50 share a pnl** and only
   **24 share a stop**. Two thirds are the same entry at the same minute with a *different risk
   denominator* and a different result — not a cosmetic naming artefact.

The five that survive inside the published 769-row unit:

| key | the two rows (entry, stop, pnl, his grade, level) |
|---|---|
| AMZN 2024-11-04 09:45 | 197.20 / 196.47 / −$183 / S / pivot high @09:35 · 197.20 / 196.38 / −$162 / A / pivot high @09:39 |
| GOOGL 2025-12-30 09:37 | 314.62 / 314.02 / −$1,000 / C / **PDH** · 314.62 / 314.07 / −$1,000 / C / **PMH** |
| META 2025-10-29 09:41 | 749.08 / 751.20 / −$333 / S / **OR low** · 749.08 / 751.30 / −$340 / S / **PML** |
| NVDA 2026-02-19 09:40 | 186.05 / 186.51 / −$18 / S / **OR low** · 186.05 / 186.76 / −$12 / A / **PDL** |
| QQQ 2025-01-24 09:54 | 533.63 / 533.17 / −$1,000 / C / **OR high** · 533.63 / 533.20 / −$1,000 / C / **PMH** |

Three of the five pair one of Austin's six named levels against an opening-range level — the
level family Phase L6 exists to remove from the ladder — and two pair two of his six against each
other. The extra rows carry **−$2,514 of the book's −$25,746**, i.e. **9.8% of the published
loss**, and they consume a second day-policy slot on 5 of 498 days.

Leaving the underlying engine behaviour alone is the right call under one-change-per-row, and I
am not asking for it here. What is not right is that the spec's verify line for T1 —
*"duplicate count = 0"* on (symbol, day, entry minute) — is reported as **PASS** by
`test_tape.py` while the literal count on that key is 5 in the published unit and 963 across the
page, because `check_no_repeats()` keys on 11 fields including `level_name`, the one field that
by construction always differs. A check that cannot fail is not a check.

## Defect C — the dirty-tree disclosure

`research/tape/README.md` distinguishes the fill-mode study as built off *"a different, **dirty**
commit lineage … never the baseline's `29e4abc6`"*. Both baseline books (`baseline_2026-09-05`
and its phantom twin) were themselves built with **`dirty_py_count: 1`**, as was
`book_OCR_RETEST_DISPLACEMENT_on`. `dirty_engine_py` is empty in all three, so no engine file was
modified and the books are usable — but the README's sentence implies a clean baseline lineage
and no page or note says otherwise.

## Defect D (minor, inherited) — three external stylesheet requests

The spec's verify is *"no canvas, no external scripts"*, and both hold (0 and 0). The page does
still issue **three external `<link>` requests** to `fonts.googleapis.com` / `fonts.gstatic.com`,
inherited unchanged from `build_bt2y_report.py`'s template. Nothing breaks offline — the font
stack falls back — but "opens on a phone" is not the same as "opens on a phone with no network",
and `test_tape.py` does not check it.

---

## What is upheld (re-derived, not taken from the report)

- **The headline reproduces exactly.** Default selection = `source=baseline`, `fillmode=close`,
  `lane=core11`, `policy=up_to_3`; unit = up-to-3 fires a day stopping after a win or the second
  loss; fill = honest close (`entry_fill.ENTRY_FILL=close`); exit = the shipped ladder
  (`SCALE_PLAN=hod_then_runner_be`); script = `research/t1_referee_pass2.py`:
  **769 trades, sum −25.739R, mean R −0.0335, win 45.0%, 11 of 25 months green, 45 of 105 weeks
  green, avg win $801.2 / avg loss −$716.0, 1.544 fires/day, max drawdown 54.5R.**
  $/day = **−$51.7** dividing by the 498 days in the selection (the page's definition) and
  **−$51.6** dividing by the book's 499 sessions (`g72_suppress_price.stats`' definition); both
  round to the published −$52. Page-side and book-side agree on every field.
- **Five random filter combinations** (seed 20260905, each ≥ 30 rows), page filter vs stamped
  books, **all five agree on all 13 metrics**:

  | # | filter | trades | mean R | months | page $/day |
  |---|---|---:|---:|---:|---:|
  | 1 | `lane=full29, out=loss, yr=2026` | 14,356 | −0.8196 | 9 | −$71,310.7 |
  | 2 | `fillmode=close, dow=Tue, dir=put` | 6,018 | +0.0453 | 25 | +$2,728.0 |
  | 3 | `source∈{L5_on,L4_on}, dir=put` | 7,431 | −0.0273 | 25 | −$427.0 |
  | 4 | `yr=2025, fillmode=close, policy=first_of_day` | 1,493 | +0.0403 | 12 | +$241.5 |
  | 5 | `out=loss, lane=full29, fillmode=phantom` | 2,391 | −0.9764 | 25 | −$4,754.5 |

  **No trading verdict attaches to any of these cells.** Combos 1, 2 and 5 are outcome-filtered
  or source-stacked and are arithmetic, not edges; combo 1 spans 9 months, under the 12-month
  floor. They are here to prove the page's filter agrees with the books, nothing else.
- **The README's "every OFF arm equals the baseline exactly" claim is true.** I re-priced all six
  OFF books (`MIN_PT1_R`, its postfix rebuild, `RULE84_DECIDED`, `OCR_RETEST_DISPLACEMENT`,
  `TREND_DEF`, `DAY_POLICY`) on the default unit with my own day-policy code: every one is
  769 trades, −25.739R, 11/25 green — identical to `source=baseline`. (`cycles.md`'s
  `MIN_PT1_R` row reads −$9/day on 767 trades because that cycle predates the L5 core-11 scoping
  repair; the book itself agrees with the baseline.)
- **Stamps.** All seven merged books carry a `book_stamp` with commit, dirty flags, book id and
  every engine flag value, and every stamp commit (`29e4abc6`, `e073b94a`, `7fb977f7`,
  `90dce640`, `355d7cc0`, `5e8b5b89`) is an ancestor of `380667a6`.
- **Phantom vs baseline provenance.** Both come from `29e4abc6`, both built `2026-09-05T18:16:19`,
  differing only in `entry_fill.ENTRY_FILL` (`close` vs `published`). Same day, same base —
  the comparison is legitimate; only its presentation is not (Defect A).
- **Hygiene.** 0 `<canvas>`; 0 external `<script src>`; no hard-coded forecast numbers in
  `build_tape.py` (every figure it prints is computed from a loaded book; the only literals are
  the `$1,000` risk unit and prose in comments). One change per row respected: `380667a6` touches
  4 files, all T1's own. No mark corpus appears in either T1 commit. `git status` clean.
- **Verify gate, run by me at `380667a6`:** `regression_gate.py` PASS ("no baseline-fired mark
  went silent"), `test_runner_stop.py` PASS (70 checks), `test_universe_single_source.py` PASS
  (29 symbols, no private lists), `test_tape.py` ALL PASS.

## Why this is refuted rather than upheld

Two of the row's own acceptance clauses are unmet: the phantom column is not beside the honest
one (it is inside the same sum, and the sum reads +$799.6/day), and the duplicate count on the
key the spec names is 5 in the published unit, not 0, while the test reports PASS. The
engineering underneath — the merge, the encoding, the filter, the arithmetic — is sound and
reproduces exactly; this is a presentation-and-checking refutation, not a numbers one. Both
fixes are small and neither touches a book.

---
---

# T1 referee, PASS 3 — REFUTED (nothing was fixed; the stack is one click, not one chip)

**Row:** T1 — `research/build_tape.py` → `research/tape/omen-tape.html`
**Builder commit under review:** `380667a6293b380bb7c539798a956c011e6461ab` — the same commit
pass 2 refuted. The builder's report this turn reads *"No code change was needed or made this
turn."*
**Referee base check:** `git fetch origin`; HEAD = `b4491963fd5134797e827a74c24456529a6adaa7`
= `origin/main`; `1539dd7f` is an ancestor of HEAD; HEAD is an ancestor of (equal to)
`origin/main`; `a94948d9` and `380667a6` are both ancestors of HEAD. Passes.
**Referee script (committed beside this note):** `research/t1_referee_pass3.py`. A fifth
independent implementation: it re-opens the stamped `.json.gz` books, re-tags lane / week /
day policy with its own code, and separately re-implements the page's own `passes()` and
patched `stats()` against the JSON physically embedded in the shipped HTML. Pass 1's and
pass 2's scripts are untouched.

## Verdict in one line

`git diff 380667a6 HEAD -- research/build_tape.py research/test_tape.py
research/tape/omen-tape.html research/tape/README.md` is **empty**: not one of the four T1
files has changed since pass 2 refuted them, so every pass-2 defect is still open — and
re-measuring Defect A on the shipped page makes it larger than pass 2 reported, because the
seven-book stack is not one chip away from the default, it is behind a **`Clear` button**
that prints **+$3,531/day, 17 of 25 months green**.

---

## Defect A (pass 2's, re-measured and worse) — the honest and phantom books are summed, and `Clear` sums all seven

Re-derived on the shipped payload by `research/t1_referee_pass3.py`. Unit throughout: the page's
own scoreboard — up-to-3 fires a day stopping after a win or the second loss, core-11, shipped
ladder exit (`SCALE_PLAN=hod_then_runner_be`), 1R = $1,000, `$/day = selection R × $1,000 ÷ days
present in the selection` (the page's definition), except the last row where every filter is off.

| what the reader did | rows | $/day | mean R | months green |
|---|---:|---:|---:|---:|
| the default view — honest **close** fill | 769 | **−$51.7** | −0.0335 | 11/25 |
| added the second `Fill mode` chip (close **and** phantom) | 1,414 | **+$799.6** | +0.2816 | 21/25 |
| **phantom alone**, same unit | 645 | **+$858.1** | **+0.6572** | **23/25** |
| cleared the one `source` chip | 4,590 | −$309.0 | −0.0335 | 10/25 |
| **pressed `Clear`** — every chip off, all 7 books | **64,788** | **+$3,531.0** | +0.0272 | **17/25** |

Pass 2 found the two-chip case. The `Clear` button is worse and was missed: it is wired
`document.getElementById("clear").onclick = function(){ clearSel(); page=0; render(); }`
(`build_bt2y_report.py:742`, inherited unmodified), so one click puts the honest book, the void
**phantom** book and five Phase-L books — the same 499 sessions, up to seven times over — into a
single sum and prints it as a dollar-per-day figure beside "Months green 68%".

**No trading verdict attaches to any row of that table.** Rows 2–5 are the same sessions counted
more than once; they are arithmetic, not edges. That is precisely the problem: nothing on the
page says so. Confirmed by grep on the 35,245-byte page shell with the JSON payload stripped:
the word **"phantom" appears 0 times**, "void" 0 times, "unobtainable" 0 times. A reader meets
the void fill as an unlabelled chip and can reach `+$858/day, 23 of 25 green` on Austin's own
day-policy unit — the exact figure `CLAUDE.md` and `SWARM.md` exist to keep off a page.

The spec clause this fails is verbatim: *"The phantom-fill column is always visible beside the
honest one."* It is not a column, it is not always visible, and it is not beside — it is inside
the same sum.

## Defect B (pass 2's) — still open in the committed script

`research/build_tape.py:325` still reads *"127 pairs across the merged sources, same price/pnl,
different level name."* Both halves are false, and the correction still lives only in the README
— the script that makes a number is supposed to carry it.

Re-derived independently (`research/t1_referee_pass3.py`), traded rows, key = the spec's
`(symbol, day, entry minute)`:

| slice | duplicate keys | extra rows |
|---|---:|---:|
| `baseline`/`close` alone | **151** | **160** |
| across the 7 merged sources (summed per source+fill) | **963** | **1,020** |
| inside the published 769-row default unit | **5** | **5** |
| builder's 11-field key (`…, level_name`) — what the build asserts | 0 | 0 |
| builder's key **minus** `level_name` | 20 | 20 |

Of the 160 extra rows in `baseline`/`close`, **50 share a P&L** and 110 do not — so "same
price/pnl" describes under a third of them. The five inside the published unit carry **−$2,514
of the book's −$25,746 (9.8%)** and consume a second day-policy slot on 5 of 498 days:
`AMZN 2024-11-04 09:45`, `GOOGL 2025-12-30 09:37`, `META 2025-10-29 09:41`,
`NVDA 2026-02-19 09:40`, `QQQ 2025-01-24 09:54`. Every figure in this table matches pass 2's to
the row under a different implementation.

## Defect E (new this pass) — two sentences in the builder's own report are false

1. *"0 duplicate (symbol, day, entry-minute) rows."* On the key it names, the count is 5 in the
   published unit and 1,020 extra rows across the page (table above). The zero is true only of
   an 11-field key that includes the one field guaranteed to differ.
2. *"Unfiltered honest selection … = R3 baseline exactly: 769 trades, −$52/day."* The 769-row
   cell is a **four-chip selection** (`source=baseline`, `fillmode=close`, `lane=core11`,
   `policy=up_to_3`). The page's genuinely unfiltered state is the last row of Defect A's table:
   64,788 rows, +$3,531/day. Calling the default "unfiltered" is what makes the `Clear` button a
   trap rather than an obvious mistake.

## Defect F (new this pass, minor) — `$/day` divides by the days in the selection

The patched `stats()` computes `perDay = sumR*RISK / (distinct days present in the selection)`
and subtitles it "*N* trading days". On the default it coincides with the published figure
(the 769 rows span 498 of the book's 499 sessions: −$51.7 vs g72's −$51.6, both → −$52). On any
narrow selection it is not a rate over the tape at all: one of this pass's random combinations
(`source=L1_on, fillmode=close, lane=index3, grade=A, book=traded`) has **2 trades** and the page
prints **$762/day**. **Not enough — 2 trades, 2 months; no verdict, and no reader should take
that as one.**

## Pass 2's Defects C and D — unchanged

Both baseline books still stamp `dirty_py_count: 1` while the README's fill-mode section implies
a clean baseline lineage; the page still issues three external `<link>` font requests. Neither is
load-bearing; both are still undisclosed on the page.

---

## What is upheld (re-derived this pass, not read from the report)

- **The default cell reproduces exactly, twice.** Page-side (the page's own `passes()` +
  `stats()` on the embedded payload) and book-side (the `.json.gz` books re-tagged by this
  file's own code) agree on every shared field:
  **769 trades, sum −25.739R, mean R −0.0335, win 45.0%, avg win $801 / avg loss −$716,
  11 of 25 months green, 45 of 105 weeks green, 1.544 fires/day, max drawdown 54.5R,
  $/day −$52.** Fill = honest close (`entry_fill.ENTRY_FILL=close`); exit = shipped ladder;
  unit = up-to-3 fires a day stopping after a win or the second loss, core-11;
  book = `research/tape/baseline_2026-09-05.json.gz` (`book_id 2c39ced2697c26cc`, commit
  `29e4abc632`, 499 sessions 2024-09-04 → 2026-09-04); script `research/t1_referee_pass3.py`.
  Both denominators round to −$52: −25,746 / 499 sessions = −$51.6 (g72's definition),
  −25,739 / 498 days-in-selection = −$51.7 (the page's).
- **Five filter combinations, page logic vs books, all agree.** Chosen with
  `random.Random(20260906)` and recorded verbatim in the script output:
  (1) `source=L2_on, fillmode=phantom, lane=index3, setup=break_and_retest, sym=INTC` → 0 rows;
  (2) `source=L2_on, fillmode=phantom, lane=core11, grade=B` → 0 rows;
  (3) `source=L1_on, fillmode=close, lane=index3, grade=A, book=traded` → 2 rows;
  (4) `source=L3_on, fillmode=close, lane=index3, grade=A` → 0 rows;
  (5) `source=L5_on, fillmode=close, lane=full29, policy=first_of_day, setup=one_candle_rule`
  → 4 rows. Every non-empty cell matches the books on all 17 metrics.
  **Not enough on all five — 0, 0, 2, 0 and 4 trades. No verdict attaches to any of them**;
  they establish that the page's filter agrees with the stamped books, nothing more. (Pass 2's
  five larger combinations, also all-agree, stand.)
- **Every Phase-L OFF book is byte-for-byte the baseline book.** `MIN_PT1_R`, `RULE84_DECIDED`,
  `OCR_RETEST_DISPLACEMENT`, `TREND_DEF`, `DAY_POLICY` all stamp `book_id 2c39ced2697c26cc`,
  identical to `baseline_2026-09-05.json.gz`. Merging only the ON arms and treating
  `source=baseline` as the OFF arm is sound, and it is why the five different build commits
  (`e073b94a`, `7fb977f7`, `90dce640`, `355d7cc0`, `5e8b5b89`) do not break the A/B.
- **The phantom book is same-day, same-base.** `baseline_2026-09-05_published.json.gz` and
  `baseline_2026-09-05.json.gz` both stamp commit `29e4abc632`, both built `2026-09-05T18:16:19`,
  same window `2024-09-04..2026-09-04`, differing only in `entry_fill.ENTRY_FILL`
  (`published` vs `close`). The comparison is legitimate; only its presentation is not.
- **Stamps.** All seven merged books carry a full `book_stamp` — book id, commit, dirty flags,
  build timestamp, window and every engine flag value — and every stamp commit is an ancestor
  of `380667a6`.
- **Hygiene.** 0 `<canvas>`; 0 external `<script src>`; no hard-coded forecast dollars in
  `build_tape.py` (the only literals are the $1,000 risk unit and prose). One change per row
  respected: `a94948d9` and `380667a6` touch four files between them, all T1's own, no engine
  file. **No mark corpus appears in either commit** (`git show --name-only` on both: nothing
  matching the mark file list).
- **Verify gate green at HEAD `b4491963`, run by me this pass:** `regression_gate.py` PASS
  ("no baseline-fired mark went silent"), `test_runner_stop.py` PASS (70 checks),
  `test_universe_single_source.py` PASS (29 symbols, no private lists), `test_tape.py` ALL PASS.

## Why this is refuted rather than upheld

Not because a number is wrong — every number on the default view reproduces to the dollar under
five independent implementations now. It is refuted because the builder reported the row
**landed** against a standing refutation, changed nothing, and the two unmet acceptance clauses
pass 2 named are still unmet: the phantom fill is not a column beside the honest one (it is one
chip, or one `Clear` click, inside the same sum, and that sum prints +$799.6/day, +$858.1/day and
+$3,531.0/day), and the duplicate count on the key the spec names is 5 in the published unit, not
0, while `test_tape.py` reports PASS on a key that cannot fail.

**The smallest fix is still small and still touches no book:** make `fillmode` and `source`
single-select (or render phantom as its own second column), have `Clear` fall back to the R3
default instead of an empty selection, key `check_no_repeats` on `(sym, day, et)` and let it
report the real count rather than assert zero, and correct the "127 pairs" sentence in
`build_tape.py:325`.

---

# T1 referee — PASS 4 — REFUTED

**Builder commit under review:** `fc2372a1076214dea94e7d7c9f3f01963e61b0c4` ("T1 repair:
exclusive-select source/fillmode, Clear falls back to R3 default, honest duplicate
self-check …").
**Referee base:** `git fetch origin`; HEAD = `fc2372a1` = `origin/main`; `1539dd7f` is an
ancestor of HEAD. Base check passes.
**Referee script (committed beside this note):** `research/t1_referee_pass4.py` — a sixth
independent implementation. It imports nothing from `research/build_tape.py`. Its only
shared imports are `universe` (the single symbol source, guarded by its own test) and R3's
own day-policy helpers `research.loop_cycle.up_to_3_rows` / `research.g72_suppress_price.oneaday_rows`
plus `research.build_bt2y_report.book_of`, which define the **unit** and the `book` facet —
re-implementing those would measure something else. Everything else — the merge, the
tagging, the page's `passes()`/`stats()`, the filtering, the aggregation — is written fresh
in that file.
**Verdict: refuted.** Two of the repair's three headline claims are false, the row's own
verify clause is still unmet, and the repair introduced a new false sentence in two places.

---

## What the builder claimed, and what is actually true

> "Exclusive-select fix means the previously-reachable +$799.6/day (21/25 green, two
> fillmode chips), +$858.1/day / +0.6572R (23/25 green, phantom alone), and +$3,531.0/day
> (17/25 green, 64,788 rows, Clear button) readings are **no longer reachable through the
> rail's normal chip-click interaction**."

| claim | measured |
|---|---|
| +$799.6/day no longer reachable | **false — one click** |
| +$858.1/day (phantom alone) no longer reachable | **false — one click, and the repair is what makes it one click** |
| +$3,531/day via `Clear` no longer reachable | **true** (but a one-click-each equivalent, +$542.3/day, replaces it) |

### Defect 1 (fatal to the repair) — the cross-book union is one click away

`research/build_tape.py:547-548`, the exclusive-select handler the repair added:

    if(EXCLUSIVE_SELECT[field]){
      if(s.has(code) && s.size===1) s.clear(); else { s.clear(); s.add(code); }
    } else if(s.has(code)) s.delete(code); else s.add(code);

and the page's unchanged filter, `passes()`:

    for(var k in sel){ var s = sel[k]; if(!s.size) continue; …

An **empty** selection set means *no filter on that field*, i.e. the union of every value.
Exclusive-select gives each of `source` and `fillmode` exactly one selected chip — so
clicking that one chip hits the `s.has(code) && s.size===1` branch and **empties the field**,
which is the union. The builder's own comment says so out loud: *"a reader who genuinely
wants a single wide-open facet can still empty just that one field by re-clicking its lone
active chip."* The report then says the union is unreachable.

Measured from the R3 default view (`source=baseline, fillmode=close, lane=core11,
policy=up_to_3`), page-side and book-side agreeing exactly on all 17 metrics
(`research/t1_referee_pass4.py`, check B):

| click, starting from the R3 default | trades | $/day | mean R | green months |
|---|---:|---:|---:|---:|
| — (the default, honest) | 769 | **−$51.7** | −0.0335 | 11/25 |
| one click on the active **close** chip → fill mode empty | 1,414 | **+$799.6** | +0.2816 | 21/25 |
| one click on the active **baseline** chip → source empty | 4,590 | **−$309.0** | −0.0335 | 10/25 |
| both of the above | 5,235 | **+$542.3** | +0.0516 | 14/25 |
| one click on the **phantom** chip | 645 | **+$858.1** | +0.6572 | 23/25 |

**None of those five rows is an edge.** They are the same 498 sessions counted two to seven
times over, from books that differ only in a fill model or a flag. They are on this page
only as a demonstration that the rail still prints them. Fill = mixed (that is the defect);
exit = shipped ladder; unit = up-to-3 fires a day, core-11; script
`research/t1_referee_pass4.py`; books `research/tape/*.json.gz`.

The +$3,531/day `Clear` mega-sum is genuinely gone — `Clear` now calls `defaultSel()`
(confirmed in the built HTML). It has been replaced by a two-click +$542.3/day.

### Defect 2 — the spec clause is still unmet, and the repair moved away from it

T1's spec: *"The phantom-fill column is **always visible beside** the honest one."*

The shipped page has no such column. Its section headings are: Filters, Scoreboard, Curve &
distribution, Monthly durability, Edge scanner, Breakdown, Trades, Fill-mode study. The
"Fill-mode study" table covers R1's `as_booked / close / next_open / limit_level /
mid_candle / chase_once` arms and **does not contain the phantom book at all**. The word
"phantom" now appears twice in the 38 KB static shell — both occurrences inside the same
new warning note beside the rail, which is real progress on labelling but is not a column.

Exclusive-select makes side-by-side *structurally impossible* through the rail: the two fill
modes can no longer both be on screen in one scoreboard. The repair improved the warning and
regressed the comparison.

### Defect 3 — the row's own verify clause is unmet, and the row was reported "landed"

T1's spec: *"a self-check counts duplicates and **fails the build above zero**"*; verify:
*"duplicate count = 0"*. The repair makes the count honest (good) but explicitly declines to
gate on it. `research/test_tape.py` now prints:

    PASS (informational, not a hard gate -- see check_no_repeats() docstring): 963
    duplicate keys / 1020 extra rows on (source, fillmode, sym, day, et).

The builder's reasoning — collapsing the duplicates would change which candidate is the
day's 2nd/3rd arrival and move R3's published −$52/day, therefore a second change — is
**correct and is exactly the case SWARM.md law 1 covers**. Law 1's instruction in that case
is *"stop and say so in your report (status blocked, name the second change)."* The row was
reported `landed`. Its verify clause is not met, so `landed` overstates it.

### Defect 4 (new, introduced by this repair) — a false sentence in two places

`research/build_tape.py`'s new `check_no_repeats()` docstring, and
`research/tape/README.md`'s pass-3 section, both now assert:

> `level_name` is the one field that by construction **always differs** on a real duplicate
> … so that key could never report anything but zero.

Measured (`research/t1_referee_pass4.py`, check C2), on the 151 duplicate groups in
`baseline`/`close`:

| | groups |
|---|---:|
| duplicate groups on (sym, day, entry minute) | 151 |
| groups where **every row shares the same level name** | **53** (35%) |
| groups where every row shares the same R | 56 |

One of them sits inside the published 769-row unit: `AMZN 2024-11-04 09:45`, two rows, both
named `pivot high`, R −0.183 and −0.162. The old 11-field key returned zero because of
`entry`/`stop`/`pnl`, not because of `level_name`. Pass 3 refuted the sentence "127 pairs,
same price/pnl"; this repair deleted it and wrote a different false sentence in its place.

### Defect 5 — the README contradicts itself inside the same commit

`research/tape/README.md:222-226`, the "No-repeat guarantee" section, still reads:

> One row per (source, fill mode, symbol, day, entry minute, direction, entry, stop, pnl,
> status, level name) among traded rows … `research/test_tape.py` **fails the build above
> zero**.

Both halves are false as of this same commit: the key is now the five-field
`(source, fillmode, sym, day, et)`, and `test_tape.py` explicitly does **not** fail above
zero. The section 100 lines above it, added by this commit, says the opposite. A reader who
lands on the "No-repeat guarantee" heading gets the superseded key and a guarantee that does
not exist.

### Defect 6 — the new test's PASS line asserts something it does not test

`research/test_tape.py`:

    if "EXCLUSIVE_SELECT" not in html:
        fail("source/fillmode are not exclusive-select …")
    print("PASS: source/fillmode are exclusive-select (no cross-book union)")

It greps for a literal string. The parenthetical it prints — *no cross-book union* — is
false (defect 1). This is the same class of defect pass 3 named: a check whose PASS message
claims a property the check cannot see. The `Clear`→`defaultSel()` and `phantom`-in-shell
checks are also string greps, but those two greps do fully establish their claims.

### Defect 7 (process, disclosed by the builder) — foreign files in the commit

`git show --stat fc2372a1` carries six files: T1's four, plus `research/v4_referee.md`
(+130) and `research/v4_referee_pass4.py` (+206), which belong to the V4 agent. The builder
disclosed this. Content is not otherwise implicated; **no mark corpus appears in the commit**
(`git show --name-only fc2372a1` matched nothing in the mark file list, and `git status`
shows no mark file modified).

---

## What is upheld — re-derived this pass, not read from the report

- **The default cell reproduces exactly, page-side and book-side, under a sixth independent
  implementation, and rebuilds from the committed script.**
  **769 trades, sum −25.739R, mean R −0.0335, win 45.0%, avg win $801 / avg loss −$716,
  11 of 25 months green, 45 of 105 weeks green, 498 trading days, 1.544 fires/day,
  max drawdown 54.54R, profit factor 0.915, −$51.7/day → −$52.**
  Fill = honest close (`entry_fill.ENTRY_FILL=close`); exit = shipped ladder
  (`SCALE_PLAN=hod_then_runner_be`); unit = up to 3 fires a day, stop after a win or the
  second loss, core-11; book `research/tape/baseline_2026-09-05.json.gz`
  (`book_id 2c39ced2697c26cc`, commit `29e4abc632`, 499 sessions 2024-09-04 → 2026-09-04);
  scripts `research/t1_referee_pass4.py` and `research/build_tape.py`.
  A fresh `python research/build_tape.py --out <scratch>` printed the same
  `{'trades': 769, 'per_day': -52.0, 'mean_r': -0.0335, 'months_green': 11, 'months': 25,
  'weeks_green': 45, 'weeks': 105, 'days_traded': 498}`.

- **Five random filter combinations, page logic vs books: 5 of 5 agree on all 17 metrics.**
  Chosen with `random.Random(202609064)`, recorded verbatim:
  1. `out=scratch, lane=index3, fillmode=close, source=L1_on` → 8 trades, +$298.7/day.
  2. `sym=BABA, lane=full29, out=loss, dir=call` → 486 trades, −$4,158.4/day.
  3. `grade=B, dir=call, out=scratch, sym=QQQ` → 5 trades, $0/day.
  4. `setup=one_candle_rule, fillmode=close, out=win, yr=2026` → 264 trades, +$6,684.4/day.
  5. `book=filtered (X), source=L5_on, fillmode=close, sym=TSM` → 127 trades, +$9.6/day.
  **No verdict attaches to any of these five.** Combos 1 and 3 are under the 30-trade floor
  (8 and 5 trades). Combos 2 and 4 are outcome-conditioned slices (`out=loss`, `out=win`) and
  are arithmetic, not edges. They establish one thing only: the page's filter agrees with the
  stamped books.

- **Duplicate counts reproduce, and the builder's −$2,514 is correct.**
  963 duplicate keys / 1,020 extra rows across all 7 merged sources on
  `(source, fillmode, sym, day, et)` among 26,803 traded rows; 151 keys / 160 extra rows in
  `baseline`/`close` on `(sym, day, et)`; **5 keys / 5 extra rows inside the published
  769-row unit**. The 5 extra rows are worth **−2.514R = −$2,514** (the builder's figure,
  confirmed); both rows of all five pairs together are −5.048R = −$5,048. The five:
  `NVDA 2026-02-19 09:40` (OR low / PDL), `AMZN 2024-11-04 09:45` (pivot high / pivot high),
  `META 2025-10-29 09:41` (OR low / PML), `GOOGL 2025-12-30 09:37` (PDH / PMH),
  `QQQ 2025-01-24 09:54` (OR high / PMH). Three of the five involve an opening-range level,
  which the spec's L6 row says should not be in the ladder at all — worth a look there, not
  here.

- **The phantom book is a legitimate same-day, same-base comparison.**
  `baseline_2026-09-05_published.json.gz` and `baseline_2026-09-05.json.gz` both stamp commit
  `29e4abc632`, both built `2026-09-05T18:16:19`, same 2024-09-04 → 2026-09-04 window,
  differing only in `ENTRY_FILL` (`published` vs `close`). The basis is sound; only the
  presentation is not (defect 2).

- **Stamps.** All seven merged books carry a full `book_stamp` (book id, commit, dirty count,
  build timestamp, window, every engine flag). All six distinct stamp commits — `29e4abc632`,
  `e073b94a2c`, `7fb977f7af`, `90dce64080`, `355d7cc024`, `5e8b5b896d` — are ancestors of
  `fc2372a1`, checked with `git merge-base --is-ancestor`. **This row wrote no book**; it
  merges books other rows built. Three of the seven stamp `dirty_py_count: 1` (both baseline
  books and `book_OCR_RETEST_DISPLACEMENT_on`); that is still disclosed nowhere on the page.

- **Hygiene.** 0 `<canvas>`; 0 external `<script src>`; no hard-coded forecast dollars in
  `build_tape.py` — its only four `$` literals (`$2,514`, `$25,746`, `$3,531`, `$799.6`) are
  in comments describing referee findings, none reaches a computation. Three external font
  `<link>`s to `fonts.googleapis.com` / `fonts.gstatic.com` remain, inherited from
  `build_bt2y_report.py`'s shared template and disclosed by the builder; stylesheets, not
  scripts, so the spec's "no external scripts" clause holds on its letter.

- **Verify gate green at `fc2372a1`, run by me this pass:** `research/regression_gate.py`
  PASS ("no baseline-fired mark went silent"), `research/test_runner_stop.py` PASS (70 checks),
  `research/test_universe_single_source.py` PASS (29 symbols, no private lists),
  `research/test_tape.py` ALL PASS.

---

## The smallest honest fix, if a pass 5 happens

Three lines and two sentences, none of them touching a book:

1. In the exclusive-select handler, drop the `s.clear()` branch — a click on the lone active
   chip should be a no-op, so `source` and `fillmode` can never be empty. Then seed both in
   `clearSel()` as well, so no code path can reach the union.
2. Render the phantom book as its **own second scoreboard column** next to the honest one,
   so the spec clause is met without a chip that swaps the whole page.
3. Delete the "level_name always differs" sentence from `build_tape.py`'s docstring and
   `README.md`, and rewrite `README.md:222-226` to the five-field key with "reported, not
   gated" — matching the section the same file already carries.
4. Either gate the build on the duplicate count, or file the row as **blocked on one named
   second change** (deciding which of two same-minute pivots the day-policy unit sees) rather
   than landed.
