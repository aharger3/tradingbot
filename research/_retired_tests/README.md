# Retired tests

Tests moved here with `git mv`, never deleted. One line each: why it stopped being
answerable as written, and what superseded its premise.

- **`test_structural_floor.py`** (retired W7/g207, 2026-09-05) — all six of
  `research/g12_recall_regression.md`'s "dropped marks" this test is built on depend on
  `fill_price`'s pre-2026-08-30 bar-extreme clamp (a signal bar closing near its own
  high/low used to fill at that extreme, squeezing the post-fill risk under the
  minimum-risk floor). The 2026-08-30 entry-fill refactor made `fill_price`'s default
  mode always book the signal minute's CLOSE, so that squeeze can no longer happen —
  the off/on arms of `ENABLE_STRUCTURAL_RISK_FLOOR` now compute the IDENTICAL risk on
  every documented example (confirmed: `GOOGL|2024-10-15|32` now fires with the flag
  off, where it used to be silently dropped). The flag itself still exists and still
  ships OFF, but the empirical case for it is now moot under the shipped fill mode.
  This needs an engineering decision (new dropped-mark examples that don't depend on
  the retired clamp, or retiring `ENABLE_STRUCTURAL_RISK_FLOOR` itself), not a test
  patch — flagged in `research/g207_tests_triage.md` for follow-up.

- **`test_master_homework_page.py`** (retired W7/g207, 2026-09-05) — drove
  `research/probes/omen-master-homework.html`, which `research/probes/README.md`'s
  ARCHIVED table lists as closed: exported to `marks/probe_master_homework_2026-08-26
  .jsonl` and `marks/probe_master_2026-08-29.jsonl`, moved to `_archived/`. The page
  this test serves at that path no longer exists on the active board -- testing a
  closed homework instrument's live-delivery contract has no subject any more. If a
  master homework page is rebuilt, this test (or a close copy pointed at the new
  path) should come back.

- **`test_entry_scratch.py`** (retired W7/g207, 2026-09-05) — built against the
  pre-2026-09-03 stop-fill floor (`-1.25R` on the stop-out's own close). The
  2026-09-03 ruling made the disaster stop a resting order at exactly 1R that fills on
  an intrabar TOUCH, so nothing books worse than `-1.000R` — most of this file's
  fixtures compared a scratch's payoff against a stop-out that no longer floors any
  worse, and its "OFF: the trade survives the bar and runs on" fixture (`BAND
  ["between"]`) no longer survives the bar at all under the touch-based disaster stop.
  `ENTRY_SCRATCH`'s money case needs re-deriving against the current stop mechanics,
  not a numeric patch — flagged in `research/g207_tests_triage.md` for follow-up.
