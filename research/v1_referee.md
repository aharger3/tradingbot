# V1 referee

**Pass 1 (below, kept verbatim): upheld, one reporting defect.**
**Pass 2 (a second referee, different model, at the end of this page): REFUTED —
the premarket half of the row silently publishes the previous session's numbers
under today's date, and its first scheduled fire is on a market holiday.**
The standing verdict for the row is **pass 2's: refuted.**

---

## Pass 1 — upheld on substance, one reporting defect

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

---

# Pass 2 — REFUTED

**Referee:** a second, different model, instructed to refute. Nothing below is taken from
the builder's report or from pass 1; every claim was re-derived here. Reproduce with
`python research/v1_referee_pass2.py` (4 checks, **0 pass, 4 fail**).

**Builder's commit, as reported:** `3c8e586df098862d13df1a28285ec5b6042c2d72`
(pass 1 already established this is Austin's `wip: auto-commit Sat 09/05/2026 16:23`, not
V1's code). **V1's actual code commit:** `c59abe88dd5d2ca58773550f08680cce9d9dbabb`.

**Base.** `git fetch origin`; HEAD = `origin/main` = `ccd7fa06`; `1539dd7f` is an ancestor
of HEAD; HEAD equals `origin/main`. Base check passes.

## What pass 1 confirmed and pass 2 re-confirmed

| check | result |
|---|---|
| dry-run lists the 11 core symbols, each with all four levels | pass — TSLA NVDA AAPL AMD META GOOGL AMZN MSFT PLTR QQQ SPY, 11 rows, no `n/a` |
| dry-run exits 0, no traceback | pass — Polygon 403 on 5 symbols, 429 on 6, all fell through to yfinance |
| the API key never appears in the output | pass — `_scrub`'s `apiKey=[^&\s]+` substitution fires on every printed error; the 11 diagnostic lines show truncated URLs with no key |
| the pushed body is plain English | pass — the body is the level block only; the fetch diagnostics go to stdout and the log, never into the push |
| scheduled task, weekdays 09:25 | pass — `\OmenPremarketList`, Schedule Type Weekly, Days `MON, TUE, WED, THU, FRI`, Start Time 9:25:00 AM, Status Ready |
| task command path exists and is tracked | pass — Task To Run = `…\research\premarket_list_run.cmd`; `git ls-files` returns it and `research/premarket_list.py` |
| `c59abe88`'s `live_scanner.py` diff is ntfy text only, Alpaca untouched | pass — +8 lines, 0 removed: the `PUSH_TAG_PRERECONCILE` env flag plus three lines appending the sentence to `_push_s_signal`'s body. No `place_order`, no `submit_order`, no broker call added or moved |
| verify gate green at HEAD (`ccd7fa06`) | pass — `regression_gate.py` PASS (no baseline-fired mark went silent); `test_runner_stop.py` ok, 70 checks; `test_universe_single_source.py` ok, 29 symbols, no private lists |
| no mark file changed | pass — `git show --stat` on `c59abe88` and `3c8e586d` and `git status` list nothing under `research/marks/`, no `*marks*.jsonl`, no `mark_batch_*`, no `recovered_reviews.jsonl`, no `marks_clean.jsonl`, no `derived_marks_v*`, no `rule_ballot_*`, no `austin_verdicts.json`, no deck manifest |
| sample size / dollar figures / stamped books | n/a — V1 produced no trade cells, no dollar figure and no book. Nothing to gate, nothing to stamp |

## The defect pass 1 missed

Pass 1 checked that the dry-run *printed eleven rows of numbers*. It did not check whether
those numbers are **today's**. They are not.

`research/premarket_list.py::_yf_batch_premarket_today` downloads with
`yf.download(symbols, period="1d", interval="1m", prepost=True, …)` and then selects
premarket bars with a single line:

    pm = df[df.index.time < dt.time(9, 30)]

That is a **clock filter with no date filter**. `period="1d"` returns the most recent
session that *has* data, which is not necessarily today. Nothing downstream re-checks it:
`fetch_levels` assigns `yf_pm.get(s, …)` straight into the message, and `format_message`
prints `n/a` only when a value is `None` — a stale-but-present number is printed exactly
like a fresh one.

**Demonstrated, not argued.** The dry-run I ran on 2026-09-06 printed the title
`OMEN premarket 2026-09-06` and, for TSLA, `PMH 376.37  PML 361.65`. Fetching the same
frame directly, `yf.download(period="1d", prepost=True)` returned bars spanning
**2026-09-04 04:00 → 19:59 ET**, 330 of them premarket, **every one dated 2026-09-04**.
`max(High) = 376.365`, `min(Low) = 361.65` — the printed numbers, two sessions stale, with
nothing on the card saying so. `research/v1_referee_pass2.py` reproduces the same
substitution offline against a synthetic frame that contains only the prior session: the
selector returns real numbers where it should return `None`.

**It fires in production on the first run.** `schtasks` reports Next Run Time
**2026-09-07 09:25**. 2026-09-07 is the first Monday of September 2026 — **Labor Day**, US
markets closed. There is no premarket session that morning, so the first live push of this
row will carry Friday's premarket range labelled as Monday's, and nothing in the message
distinguishes it. The task is a plain weekly Mon–Fri trigger with no holiday calendar, so
this recurs on every weekday holiday.

**Why it matters for this row specifically.** The 2026-09-05 call gave Austin exactly one
job in the reconcile era: HTF levels premarket. This push is the input to that job. A stale
premarket range that looks fresh is worse than a missing one — he would pencil levels off a
range that never happened, and `PMH`/`PML` are two of the six levels the spec locks as the
scale-point ladder.

## Scope of the refutation

The **push-tag half of V1 is clean** and stands: 8 lines, ntfy text only, Alpaca paper path
untouched, flag defaults ON, plain English. The refutation is confined to the **premarket
list half**.

## The one change that fixes it

Filter the premarket frame by date as well as clock — `pm = df[(df.index.date == today) &
(df.index.time < dt.time(9, 30))]` — and let the existing `None` path print `n/a`, so a
holiday or a not-yet-populated feed shows `PMH n/a  PML n/a` instead of last session's
range. That is one function, one line, and it needs its own row: pass 2 changed no
production code.

## Not checked in pass 2 either

The `.cmd` was still not executed end to end, for pass 1's reason — without `--dry-run` it
sends Austin a real push. Whether yfinance reliably serves the *current* partial session at
09:25 on an ordinary trading day was not established; the defect above does not depend on
it, because the holiday case alone is deterministic.
