# H1 referee — REFUTED

Row: **H1 — one card per symbol** (OMEN 10.0, phase H).
Builder commit under review: **1f26cf73** ("H1 repair: drop --per-signal from the 11:05
runner, write a served-record manifest…"), on top of **57f2fbd2** ("H1: one card per symbol").
Builder status: `held` — *"already fully implemented … No further work needed."*
Referee HEAD: `ccd7fa06` (both commits are ancestors; `1539dd7f` is an ancestor of HEAD;
HEAD == origin/main; working tree clean).
Every number below is re-derived by **`research/h1_referee.py`** (committed beside this file),
not taken from the builder's self-test.

**Verdict: refuted.** Two of the three clauses of the row hold. The middle clause — *"all S
bars drawn on the one chart"* — is **not implemented**, and the commit under review says so in
its own new docstring while the report says the row is fully implemented. The row's own verify
condition ("the 09-03 deck rebuilt has 11 cards, 0 repeats") is now unreachable, and the
self-test was rewritten to assert the opposite rather than flagged.

---

## Defect 1 — all S bars are NOT on the one chart (spec clause 2)

`sblind_collect` cuts the tape at the bar `classify()` returns, which is the **first** S bar:

    "bars": d["bars"][:cut + 1],        # research/daily_homework.py

Re-derived on the row's own day, 2026-09-03:

| symbol | S bars in the session | `classify()` cut | S bars drawn on the card |
|---|---|---:|---:|
| AMD | 36, 63, 64, 82, 86 | 36 | **1 of 5** |

The card was rendered (`dh.sblind_card_html`) and the SVG inspected: **37 of the day's 90 bars
on the tape**, S bars 63/64/82/86 are past the end of it, so they are not drawn and carry no
cut line. This is the exact failure the row exists to fix in the other direction — he saw AMD
five times as five cards; he now sees it once, but the four later S bars he complained about
are simply gone from the chart rather than consolidated onto it.

The commit under review **added a docstring saying this is unimplemented**
("Showing every S bar on one chart is unimplemented (H1 referee, OMEN 10.0, defect 2)") and the
report nonetheless returned `held / already fully implemented / no further work needed`. An
honest docstring does not close a spec clause. The correct status was **blocked** or **partial**,
naming the missing work.

## Defect 2 — the row's verify condition was replaced, not met

Spec: *"Verify: the 09-03 deck rebuilt has **11 cards, 0 repeats**."*
Measured now: the 2026-09-03 rebuild with `per_signal=False` deals **0 cards** — all 11
CORE_SYMBOLS are suppressed as already marked or served. `test_deck_one_per_symbol.py` was
edited in 1f26cf73 to **assert** `eligible == 0` and `len(cards) == 0`, so its primary case is
vacuous: it now proves that an empty list contains no duplicate symbols. Only the secondary
2026-09-04 demo pool (6 cards, 6 distinct symbols, 0 repeats) exercises the rule, and its
render step is guarded by `if demo_cards:`.

Removing the backfilled manifest from the served set, **5 of 11** symbols would be eligible on
2026-09-03 (AAPL, AMD, AMZN, MSFT, QQQ); the other 6 were graded. So **11 was never reachable**
— the spec line was wrong, and 57f2fbd2's own message says "5 eligible". That is a defensible
finding, but it had to be reported as *the verify condition cannot be met, here is why*, not
absorbed by rewriting the assertion to match the observed output.

Also noted: 1f26cf73 carries three distinct changes (runner flag, manifest writing, docstring)
in one commit, against the one-change-per-row rule. No number depends on it here.

---

## What does hold (verified independently)

| check | result |
|---|---|
| `per_signal=False` is the default in `sblind_collect` | OK |
| `--per-signal` gone from `research/daily_run_1105.cmd`; `research/daily_run.cmd` never passed it | OK |
| `served_card_ids()` reads **48** `*manifest*.jsonl` files under `research/` (7 under `decks/`), yielding **997** distinct symbol-days | OK |
| every id in every manifest is present in `served_card_ids()` | OK |
| the s10 deck's **22** card ids → **11** distinct symbol-days, all 11 excluded by the served set | OK |
| 2026-09-03 rebuild: 0 repeats, no symbol dealt twice | OK (on 0 cards) |
| `research/decks/omen-daily-2026-09-03-s10.html` byte-identical to `1f26cf73^` | OK (last touched by b8acefd6) |
| every mark corpus byte-identical to `1f26cf73^` (`git diff --stat` empty) | OK |
| verify gate at HEAD: `regression_gate.py` PASS, `test_runner_stop.py` 70 checks ok, `test_universe_single_source.py` 29 symbols ok | OK |

No dollar figure, no book and no trade unit are involved in this row, so the sizing, fill and
stamp rules have nothing to bind to; nothing here carries a sample-size verdict.

## Note on the backfilled manifest

`research/decks/omen-daily-2026-09-03-s10-manifest.jsonl` is new in 1f26cf73 and sits in the
protected deck-manifest namespace. It is an added record of what was served, not a rewrite of a
graded file, and the graded HTML is untouched, so no judgement was lost. Its permanent effect is
that those 11 symbol-days can never be dealt again — correct behaviour, and the reason the
row's own verify line can no longer be run.

## What would close H1

Draw the whole symbol-day. Either extend the tape to the **last** S bar and mark every S bar
with its own cut line, or state on the card that the tape stops at the first one. Then restore a
non-vacuous self-test: a day with eligible symbols and at least one multi-S-bar symbol, asserting
the count of drawn S bars equals the count in the session.
