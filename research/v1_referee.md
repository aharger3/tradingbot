# V1 referee — upheld on substance, one reporting defect

**Row:** V1 (omen-10.0, Phase V) — Monday's push carries the pre-reconcile line, and a
09:25 premarket list goes to ntfy for the core 11.

**Builder's commit, as reported:** `3c8e586df098862d13df1a28285ec5b6042c2d72`
**Builder's commit, as it actually is:** `c59abe88dd5d2ca58773550f08680cce9d9dbabb`

**Referee:** a different model, instructed to refute. Every check below was re-derived here,
not read out of the builder's report. Reproduce with `python research/v1_referee.py`
(14 checks, 13 pass, 1 fails — the reported hash).

**Verdict: upheld.** The code does what the row asked, on the base it claims. One defect,
and it is in the report, not the code.

## Base

`git fetch origin`; HEAD = `origin/main` = `3c8e586d`; `1539dd7f` is an ancestor of HEAD.
Base check passes.

## Row-specific checks

| check | result |
|---|---|
| dry-run lists 11 core symbols with PDH/PDL/PMH/PML | pass — TSLA NVDA AAPL AMD META GOOGL AMZN MSFT PLTR QQQ SPY, 11 rows, none missing |
| dry-run raises no traceback, exits 0 | pass — Polygon returned 403 on 5 symbols and 429 on 6, all fell through to yfinance as designed |
| the API key never appears | pass — `research/premarket_list.py::_scrub` is a real `apiKey=[^&\s]+` substitution, not luck; fed a synthetic URL carrying `apiKey=SENTINELKEY`, the sentinel does not survive |
| pushed text is plain English | pass — the body is the level block only (`TSLA  PDH 364.69  PDL 351.32  PMH 376.37  PML 361.65`, ×11). The Polygon/yfinance diagnostics print to stdout and the log file, never into the push. No flag names, no ticket ids. PDH/PDL/PMH/PML are Austin's own shorthand |
| scheduled task fires weekdays 09:25 ET | pass — `OmenPremarketList`, State Ready, trigger enabled, `StartBoundary 2026-09-05T09:25:00`, `DaysOfWeek 62` = Mon+Tue+Wed+Thu+Fri (Sun=1 … Sat=64). Machine local time is ET (`wmic` reports UTC offset −240 = EDT), so 09:25 local is 09:25 ET |
| task command path exists and is tracked | pass — Execute = `…\research\premarket_list_run.cmd`, file on disk, `git ls-files` returns both it and `research/premarket_list.py` |
| `c59abe88`'s `live_scanner.py` diff is ntfy text only | pass — 8 added lines, **0 removed**. Five are the `PUSH_TAG_PRERECONCILE` env flag and its comment; three append the pre-reconcile sentence to `_push_s_signal`'s body. No added line contains `place_order`, `submit_order`, `_alpaca_submit` or `broker.`. The Alpaca paper block (`live_scanner.py` ~1140–1216, the only caller of `broker.place_order`) is untouched |

`_push_s_signal` is the only S-signal push path in the file, so the tag reaches every S push.

## Standard checks

- **Sample size.** V1 produced no trade cells. Nothing to gate. n/a.
- **Dollar figures.** V1 publishes none. Its own report says "n/a — this row verifies infra".
  Correct; no unlabelled money number was introduced.
- **Stamped books.** V1 wrote no book. Nothing to stamp. n/a.
- **One change per row.** `git show --stat c59abe88` = 2 files, 281 insertions:
  `live_scanner.py` (+8) and the new `research/premarket_list.py` (+273). Two artefacts, but
  the spec row itself names both halves ("every S push carries the line … *and* a 09:25
  premarket list goes to ntfy"), and neither is a measured change — no book moved for two
  reasons. Not a violation.
- **No mark file changed.** `git show --stat` on both `c59abe88` and `3c8e586d` lists no path
  under `research/marks/`, no `*marks*.jsonl`, no `mark_batch_*`, no `recovered_reviews.jsonl`,
  no `marks_clean.jsonl`, no `derived_marks_v*`, no `rule_ballot_*`, no `austin_verdicts.json`,
  no deck manifest. `git status` shows none either.
- **Verify gate green at HEAD.** Run here, at `3c8e586d`:
  `regression_gate.py` → PASS (no baseline-fired mark went silent; any_signal 75→80,
  s_grade 5→25, all new fires); `test_runner_stop.py` → ok, 70 checks across 3 sections;
  `test_universe_single_source.py` → ok, 29 symbols, 25 backtested, no private lists.
- **Plain English.** The ntfy body and the premarket message both read as plain English.

## The defect

**The builder reported the wrong commit hash.** It named
`3c8e586df098862d13df1a28285ec5b6042c2d72` and said "no new commit made". That hash is
*Austin's* `wip: auto-commit Sat 09/05/2026 16:23` — a 21-file sweep carrying another agent's
`g210_fill_arms_v2`, `g215_precision`, `daily_homework.py`, a `CLAUDE.md` edit and the
fill-arms tape. V1's own code landed six minutes earlier in `c59abe88`
("V1: pre-reconcile push tag + 09:25 premarket list to ntfy", `live_scanner.py` +
`research/premarket_list.py`).

Two consequences worth naming:

1. The dispatcher would attribute V1 to a commit that contains none of V1's code, and would
   attribute four other agents' work to V1.
2. `research/premarket_list_run.cmd` — the launcher the scheduled task actually runs — was
   never committed by the V1 builder at all. It was swept into that unrelated auto-commit.
   It is tracked, so nothing is lost, but its provenance is an auto-commit rather than the
   row that created it. The builder's phrase "already tracked … nothing left for V1 to
   commit" is true as a fact about the tree and misleading as a claim about the row.

Neither consequence changes what the code does. The row's deliverables work, the schedule is
right, the key does not leak, and the Alpaca path is untouched — so the verdict is upheld,
with the hash corrected to `c59abe88` for the record.

## Not checked

The `.cmd` was not executed end to end, because it calls `premarket_list.py` without
`--dry-run` and would send Austin a real ntfy message on a Saturday. Its date-stamp block is
character-for-character the pattern already in the working `research/daily_run.cmd`, and
`wmic os get localdatetime` was confirmed present and returning on this box
(`C:\WINDOWS\System32\Wbem\WMIC.exe`), so the log filename will resolve. The first live
09:25 push on Monday is the real test of that path.
