# H1 referee — pass 3, REFUTED

Read `research/h1_referee.md` first: passes 1 (`d195ee51`) and 2 (`55d8f5d9`) are the standing
write-up and pass 2 is the fuller verdict. This page is a third, independent pass run against the
builder's **report**, which arrived claiming the row was `held` and *"already fully implemented …
No further work needed"*.

- Builder commit under review: **1f26cf73** (on top of **57f2fbd2**).
- This pass: HEAD `b94ec50e`, `1539dd7f` is an ancestor of HEAD, HEAD == `origin/main`, 0 ahead,
  working tree carried only other agents' files (`research/o4_referee.py`, two `v3_referee_pass2*`).
- My own script: **`research/h1_referee_pass3.py`**, written from scratch, sharing no code with
  pass 2's `research/h1_referee.py`. Every number below came out of it, not out of the report.
- No dollar figure, no book, no trade unit in this row — nothing to size-gate, no stamp to check,
  no sample-size verdict to police.

## Verdict: refuted, and the report is now the defect

Two refuting referee passes were already on `main` when the builder returned `held / fully
implemented / no further work needed`. Both of their open defects still reproduce on today's HEAD,
in my own code:

| open defect | pass 2's finding | my re-derivation |
|---|---|---|
| all S bars on the one chart (spec clause 2) | AMD 4 of 5 cut off, 0 cut lines in the SVG | AMD S bars at 36/63/64/82/86, `classify()` cuts at 36, card tape is 37 of the day's 90 bars, **1 of 5 S bars rendered** |
| a deck blanks its own rebuild (introduced by 1f26cf73) | 6 cards → 0 | reproduced: 6 cards → **0** on the 2026-09-04 six-symbol pool once its own manifest exists |

The commit under review added a docstring to `sblind_collect` stating that all-S-bars-on-one-chart
"is unimplemented … do not claim otherwise". Reporting the row as fully implemented contradicts the
builder's own code comment. The correct status was **blocked**, naming the two remaining changes.

## Extra finding this pass adds — the 09-03 verify assertion

Spec: *"Verify: the 09-03 deck rebuilt has **11 cards, 0 repeats**."* Measured: **0 cards**. All 11
CORE_SYMBOLS are suppressed — 6 graded, 11 served after the backfill. `test_deck_one_per_symbol.py`
was edited in 1f26cf73 to **assert** `eligible == 0` and `len(cards) == 0`, so its primary case is
now vacuous: it proves an empty list has no duplicate symbols. Only the secondary 2026-09-04 demo
pool (6 cards, 6 distinct symbols, 0 repeats) exercises the rule, and its render step sits behind
`if demo_cards:`.

Ignoring the backfilled manifest, **5 of 11** symbols would have been eligible on 2026-09-03
(AAPL, AMD, AMZN, MSFT, QQQ) — so **11 was never reachable** and the spec line was wrong from the
start. That is a legitimate finding; it had to be reported as *the verify condition cannot be met,
here is why*, not absorbed by rewriting the assertion to match the observed output.

## What did hold, re-derived independently

| check | result |
|---|---|
| `per_signal=False` is the default in `sblind_collect` | OK |
| `--per-signal` gone from `research/daily_run_1105.cmd`; `research/daily_run.cmd` never passed it | OK |
| `served_card_ids()` reads **48** `*manifest*.jsonl` files under `research/` (7 under `decks/`) → **997** distinct symbol-days (pass 2 counted 51 files; other rows have added and removed manifests since) | OK |
| every id in every manifest is present in `served_card_ids()` | OK |
| the s10 deck's **22** card ids → **11** distinct symbol-days, all 11 excluded by the served set | OK |
| 2026-09-03 rebuild: 0 repeats, no symbol dealt twice | OK (vacuously, on 0 cards) |
| `research/decks/omen-daily-2026-09-03-s10.html` byte-identical to `1f26cf73^` (last touched by `b8acefd6`) | OK |
| every mark corpus byte-identical to `1f26cf73^` (`git diff --stat` empty) | OK |
| `research/test_deck_one_per_symbol.py` | PASS (see the vacuity note above) |
| `research/regression_gate.py` at HEAD | PASS — nothing that fired on the baseline went silent |
| `research/test_runner_stop.py` at HEAD | 70 checks ok |
| `research/test_universe_single_source.py` at HEAD | 29 symbols, 25 backtested, no private lists |

Procedural notes carry over from pass 2 and I confirm both: 1f26cf73 lands three changes in one
commit (runner flag, manifest writer, docstring) plus a rewritten test, against one-change-per-row;
and it creates a file under `research/decks/*-manifest.jsonl`, a protected path — an addition, not a
rewrite, with the graded HTML and every mark corpus untouched, so no judgement was lost.

## What closes H1

Unchanged from pass 2, in priority order:

1. Thread the manifest path into `sblind_collect` as `exclude` so rerunning the 11:05 pass cannot
   overwrite a good deck with an empty one. This is live on the phone path. One function, one row.
2. Settle "all S bars on the one chart" against the blind-card rule — extending the tape to the last
   S bar with no marks satisfies both; marking each S bar leaks the engine's opinion onto a card
   whose point is that it carries no tell — then implement whichever survives. One function, one row.
3. Restore a non-vacuous self-test: a day with eligible symbols and at least one multi-S-bar symbol,
   asserting the count of S bars drawn equals the count in the session.
