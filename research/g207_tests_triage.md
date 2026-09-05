# W7/g207 — the 14 failing tests, triaged

**One sentence:** all 14 of B-08's failing tests were checking real invariants against
stale assumptions — three shipped-default changes (the 2026-08-30 entry-fill refactor,
2026-09-02's `RETEST_REQUIRED`, 2026-09-03's -1R hard floor) each silently broke several
tests at once — 11 are fixed, 2 are retired with the empirical claim they depended on
now gone, 1 was already fixed by an earlier commit tonight; `research/run_tests.py` now
runs the canonical set (66/67 passing) and is wired into `daily_run.cmd`, log-only.

No production module was edited. `CLAUDE.md`'s `verify:` line is unchanged.

## Disposition

| test | verdict | root cause |
|---|---|---|
| `test_austin_tier.py` | **fix** | bar-extreme clamp checks called `fill_price` in its default mode, which has always booked the CLOSE since the 2026-08-30 entry-fill refactor and never reads the clamp; rewritten to exercise `entry_fill.entry_fill_price(..., mode="published")`, the one path that still implements it |
| `test_rule_710.py` | **fix** | `RETEST_REQUIRED` (default ON since 2026-09-02, unrelated to this flag) also caps the SLOW fixture to C, since it's built to fail a retest-timing check too; isolated it for the duration of the OFF-arm assertion |
| `test_detect_wide.py` | **fix** | `Path.read_text()` with no `encoding=` used the Windows default codepage, mis-decoding `signal_runner.py`'s em dash and breaking a substring match; pinned `encoding="utf-8"` |
| `research/test_downgrade_grader.py` | none needed | already fixed by an earlier commit tonight (B-01/B-02 lineage); confirmed passing |
| `research/test_sac_ladder.py` | **fix** | its round-trip check literally composed `SAC_TIER` (his grade → the legacy engine grade) with `LADDER` (the engine grade → his grade, from a different, independently-evolved module) as an identity — exactly the "two grade ladders must never be mixed" CLAUDE.md warns about, and it does not hold by design (`SAC_TIER` never emits "B"; `LADDER["A"] == "S"`). Replaced with the one pair (C, and the skip grade) both ladders actually agree on |
| `research/test_entry_scratch.py` | **retire** | built on the pre-2026-09-03 `-1.25R` stop floor; the 2026-09-03 ruling made the disaster stop a resting order at exactly 1R that fills on a TOUCH, so nothing books worse than `-1.000R` any more — most of its money assertions compare a scratch against a stop-out that no longer floors worse, and its "OFF: the trade survives the bar" fixture no longer survives under the touch-based disaster stop. Needs fixture redesign against current stop mechanics, not a numeric patch |
| `research/test_onwatch_fill.py` | **fix** | same clamp-is-dead-under-default-close-mode issue as `test_austin_tier.py`; rewritten the same way |
| `research/test_paper_trader_stop.py` | **fix** | the test computed its expected floored premium off `stop_rule.MAX_LOSS_R` (1.25, now a lab-only constant per the 2026-09-03 ruling — `research/exit_lab.py` only); `paper_trader._stop_fill_premium` already passes the correct `DISASTER_STOP_R` (1.0) to the shared `stop_fill_price` clamp — the test was checking its numbers against the wrong constant, not a paper_trader bug |
| `research/test_published_numbers.py` | **fix** | the allowlist's watermark was stale at 2026-08-28; 169 files had accumulated since (this row's own g181/g182 included). Extended the watermark to 2026-09-05. **Still racing**: 2–3 more wave-2 report files (`g201_refute1.md`, `g203_alpaca_referee.md`, `g201_mid_candle_referee.md`) appeared *after* this fix from other agents' rows still running concurrently — left off the allowlist on purpose, since they are not this row's backlog and may get their own scripts before wave 2 closes |
| `research/test_rule84_source.py` | **fix** | two issues: (1) same `RETEST_REQUIRED`-contamination pattern as `test_rule_710.py`, cascading into the C-grade tight-stop skip and killing the signal outright; (2) the `MIN_STOP_PCT` fixture assumed the pre-2026-08-30 fill (entry at the LEVEL on a near-own-high close) — rebuilt using the ORIGINAL-stop fallback path instead, which is compatible with the shipped always-close fill |
| `research/test_structural_floor.py` | **retire** | `ENABLE_STRUCTURAL_RISK_FLOOR`'s entire empirical case (`research/g12_recall_regression.md`'s "six dropped marks") depends on `fill_price`'s pre-2026-08-30 bar-extreme clamp squeezing the post-fill risk under the floor. That clamp is dead under the shipped close-only fill, so the flag's off/on arms are now IDENTICAL on every one of its six documented examples (confirmed: `GOOGL\|2024-10-15\|32` now fires with the flag off, where it used to be silently dropped). This needs an engineering decision — new dropped-mark examples that don't depend on the retired clamp, or retiring the flag itself — not a test patch |
| `research/test_universe_single_source.py` | none needed | already fixed by an earlier commit tonight; confirmed passing |
| `research/test_master_homework_page.py` | **retire** | drives `research/probes/omen-master-homework.html`, which `research/probes/README.md`'s ARCHIVED table lists as closed and exported (`marks/probe_master_homework_2026-08-26.jsonl`, `marks/probe_master_2026-08-29.jsonl`); the page no longer exists at that path. No subject left to test — if a master homework page is rebuilt, bring this test back pointed at the new path |
| `research/test_omen_test1_page.py` | **fix** | `OMEN_DECK`'s default moved from `omen-test-1` (100 cards) to `omen-test-2` (97, the ACTIVE deck) without the hardcoded `100`/`20` counts moving with it; made the assertions read the card total off the page itself |

## The pattern worth naming

Three shipped-default changes each broke several tests at once, because the tests
reached past the current public entry point into a mechanism the change retired:

1. **The 2026-08-30 entry-fill refactor** (`fill_price` now always books the signal
   minute's CLOSE) killed the bar/session-extreme clamp for every DEFAULT-mode caller —
   4 of the 14 tests (`test_austin_tier.py`, `test_onwatch_fill.py`,
   `test_rule84_source.py`'s MIN_STOP_PCT fixture, `test_structural_floor.py`) were still
   calling `fill_price` expecting the clamp to fire.
2. **`RETEST_REQUIRED` (2026-09-02, default ON)** caps unrelated flag-OFF fixtures to C
   whenever their bars happen to also fail a retest-timing check — 2 of 14
   (`test_rule_710.py`, `test_rule84_source.py`) needed the flag isolated for the
   duration of an unrelated assertion.
3. **The 2026-09-03 -1R hard floor** (disaster stop fills on TOUCH, not close) retired
   `MAX_LOSS_R=1.25` from every live path — 2 of 14 (`test_paper_trader_stop.py` fixed,
   `test_entry_scratch.py` retired).

None of these three flags are new discoveries — all three are already documented in
CLAUDE.md — but nothing had walked the test suite against them since they shipped. That
is exactly what `research/run_tests.py` is for going forward: it will not predict the
NEXT default change, but it will say, the next morning, which tests it broke.

## `research/run_tests.py`

Runs every `test_*.py` under the repo root and `research/` (excluding
`research/_retired_tests/`) as its own subprocess — deliberately not sharing one
process, since several of these tests flip module-level flags (`RETEST_REQUIRED`,
`ENABLE_SAC_LADDER`, ...) and would otherwise leak state into each other. A short,
named `EXCLUDED` dict holds five tests broken for reasons unrelated to B-08 (a missing
generated artifact, a missing data file, a broken import path, `test_provenance.py`'s
live backlog from other concurrent wave-2 report files, and the already-tracked B-07
partial fix) — never a silent skip, each with its reason inline.

Current run: **66/67 passing** (canonical set; the lone failure,
`test_published_numbers.py`, is the live race described above and is expected to
change by the hour while wave 2 is still writing report files).

Wired into `research/daily_run.cmd`, **log-only, non-fatal**, after the regression
gate — this is a triage instrument, not `CLAUDE.md`'s `verify:` line, which stays
`regression_gate.py && test_runner_stop.py`, unchanged.

## Files touched

- Fixed (test-file-only edits, no production module touched): `test_austin_tier.py`,
  `test_rule_710.py`, `test_detect_wide.py`, `research/test_sac_ladder.py`,
  `research/test_onwatch_fill.py`, `research/test_paper_trader_stop.py`,
  `research/test_published_numbers.py`, `research/test_rule84_source.py`,
  `research/test_omen_test1_page.py`.
- Retired (`git mv` into `research/_retired_tests/`, one line each in its `README.md`):
  `test_entry_scratch.py`, `test_structural_floor.py`, `test_master_homework_page.py`.
- New: `research/run_tests.py`, `research/g207_tests_triage.md`.
- Wired: `research/daily_run.cmd` (new log-only, non-fatal block).
