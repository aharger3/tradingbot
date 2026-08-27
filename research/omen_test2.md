# OMEN Test 2 — the 12-symbol roster deck

`python research/build_omen_test1.py` (with `OMEN_DECK=omen-test-2`, its default) builds
this. Numbers below came from that run, `_this commit_`.

## The roster

Austin, 2026-08-27: "core symbols and indices in prop firms." That is
`universe.CORE_SYMBOLS` union `universe.INDEX_POOL`, imported in
`research/build_omen_test1.py` — never retyped, so `research/test_universe_single_source.py`
stays clean:

```
AAPL AMD AMZN GOOGL IWM META MSFT NVDA PLTR QQQ SPY TSLA
```

12 distinct symbols. `CORE_SYMBOLS` is 10 (it does not carry SPY —
`INCLUDE_SPY_IN_BACKTEST=False` governs the *backtest* roster, not this deck, and this
build does not flip it). `INDEX_POOL` adds SPY and IWM; QQQ sits in both, hence the set
union rather than a concatenation.

## The pool, measured

Restricting `build_deck.universe()` to the roster, from `2025-01-01`, minus every symbol-day
already in `build_deck.marked_card_ids()`, leaves **4439 candidate symbol-days**. Per
engine-side stratum (`stratum_of()`, no bar reads needed — this is the number the build now
prints on every run):

| stratum | pool | quota | quota/pool |
|---|---:|---:|---:|
| s_traded | 145 | 12 | 8% |
| s_dropped | 1698 | 28 | 2% |
| silent | 106 | 15 | 14% |
| low | 1021 | 25 | 2% |
| mid (off-roster-only, best sgrade A) | 1469 | — | — |

None of those four are close to their ceiling. Off-roster is the one that is: of the 4128
pool days eligible for it (engine never traded that day), classifying all of them
(`classify()` in `research/build_omen_test1.py`) found:

| pattern | classifiable candidates | drawn |
|---|---:|---:|
| gap_fill | 874 | 5 |
| or_reversal | 938 | 5 |
| no_retest | 315 | 5 |
| double_tap | 203 | 5 |
| range_fade | **0** | 0 |

`range_fade` — "contained inside the premarket range, both ends worked twice" — never
matches on this roster. That is not new to the 12-symbol cut: the pre-roster-filter build
(28 symbols, the same `bt2y_trades.json` book) failed with the identical shape, `stratum
offroster short: 20 of 25 (probed 9372 days)` — 4 patterns of 5, one pattern of 0, on the
full universe too. Restricting to 12 symbols did not create this gap; it was already there.

## The quotas, and why

`OFFROSTER_EACH=5` × 4 living patterns caps off-roster at 20, not 25, regardless of roster
size — raising the per-pattern cap wasn't needed or touched, since the four live patterns
have 200-940 candidates apiece against a draw of 5 each. `QUOTAS` moved the 5 cards
`range_fade` cannot supply into `low`, the stratum with the deepest bench (1021 candidates
against the draw):

| stratum | old | new |
|---|---:|---:|
| s_traded | 12 | 12 |
| s_dropped | 28 | 28 |
| silent | 15 | 15 |
| offroster | 25 | **20** |
| low | 20 | **25** |
| **total** | **100** | **100** |

**100 cards was reachable on the 12-symbol roster** — the shrink from 29→12 symbols never
bound anything except off-roster, and off-roster's real ceiling (20) was already true before
the roster changed at all. `s_traded`/`s_dropped` (the 40-card S-denominator the module
docstring sizes the whole instrument around) are untouched. The `select()` assert
(`stratum %s short: %d of %d`) still runs after the draw — it did not fire this build,
and stays in place to fail loudly if a future roster or judged-day count ever pushes a
stratum past its pool again.

`MAX_PER_SYMBOL` raised from 8 to **9** — the minimum arithmetic allows: 12 symbols × 8 =
96 < 100, 12 × 9 = 108 ≥ 100. No further than forced.

## Cards per symbol (this draw, seed=1)

| symbol | cards |
|---|---:|
| NVDA | 9 |
| PLTR | 9 |
| META | 9 |
| TSLA | 9 |
| MSFT | 9 |
| GOOGL | 9 |
| AAPL | 9 |
| SPY | 9 |
| QQQ | 8 |
| AMD | 8 |
| AMZN | 7 |
| IWM | 5 |
| **total** | **100** |

Eight symbols hit the new `MAX_PER_SYMBOL=9` cap; none were starved (IWM, the lowest, still
landed 5 — no symbol failed to place a single card).

## Repeat guard

`marked_card_ids()` excluded **758** already-judged symbol-days from the pool before the
draw — every corpus in `research/marks/LEDGER.md` plus `LEGACY_MARK_FILES`, `grade:"none"`
included. The draw then probed 119 of the remaining 4439 candidates to fill 100 cards (far
fewer than the pre-roster-filter build's 9372, since the pool is now tightly scoped to 12
symbols). `verify()` re-checks zero repeats within the document and zero overlap with
`judged` before the page is written — both passed.

## S-denominator (informational)

45 of the 100 cards carry an engine `best_sgrade` of S (the 40 direct
`s_traded`+`s_dropped` cards plus 5 more that landed in `low`/`offroster` on this draw and
happened to also carry an S grade) — one disagreement against Austin's 95% target now costs
2.2 points.

## Gates

`python research/build_omen_test1.py`, `python research/test_omen_test1_page.py` and
`python research/test_universe_single_source.py` all pass. The last one required one
unrelated fix: `research/test_universe_single_source.py`'s directory walk had no skip rule
for `.claude/`, and a stray git worktree at `.claude/worktrees/kind-dewdney-5d7d3c/`
(pre-dating this build, `.git/info/exclude`d, unrelated to OMEN Test 2) carries its own copy
of `universe.py`. Added `.claude` to `SKIP_DIRS` — same treatment `.git` already gets, and
no source under `.claude` was ever meant to be scanned.
