# V1 referee

**Pass 1 (below, kept verbatim): upheld, one reporting defect.**
**Pass 2 (a second referee, different model, at the end of this page): REFUTED —
the premarket half of the row silently publishes the previous session's numbers
under today's date, and its first scheduled fire is on a market holiday.**
**Pass 3 (a third referee, told to refute the repair): UPHELD with two residuals — the
repair (c84d0bd3) is real, independently re-derived, and does not disable the live path.**
The standing verdict for the row is **pass 3's: upheld**.

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

---

# Pass 3 — the repair, refereed. UPHELD, two residuals.

**Builder's repair commit:** `c84d0bd3135a48d40b6b1abaa505e8530860eca2`
("V1 repair: date-scope yfinance premarket fallback so stale prior-session PMH/PML never
render as today's"). Original row commit `c59abe88`. Referee: a third model, instructed to
refute the repair. Every number below was re-derived here with
`research/v1_referee_pass3.py`; nothing is read out of the builder's report.

**Base:** `1539dd7f` is an ancestor of HEAD; HEAD (`3ace41cb` at referee time) equals
`origin/main`. `research/premarket_list.py` and `live_scanner.py` are byte-identical between
`c84d0bd3` and HEAD, so every check below is a check on the row's own commit.

## Pass 2's defect is real, and it is gone

Pass 2 claimed the premarket mask filtered by clock only, so a prior session's range would
publish under today's title. Re-derived on today's live yfinance frame (2026-09-06, Sunday;
the frame's only session is Friday 2026-09-04):

| symbol | pre-fix mask (clock only) | fixed mask, `today=2026-09-06` | fixed mask, `today=2026-09-04` |
|---|---|---|---|
| TSLA | **376.365 / 361.65** | `None / None` | 376.365 / 361.65 |
| NVDA | **232.49 / 228.45** | `None / None` | 232.49 / 228.45 |
| SPY  | **774.27 / 770.50** | `None / None` | 774.27 / 770.50 |

The middle column is the fix. The right-hand column is the check that separates *fixed* from
*disabled*: a mask that returned nothing on every day would also produce the Sunday `n/a`
the builder verified, so the Sunday run alone proves nothing. With `today` set to the frame's
own session the same function still returns a real range — **the live path is intact**.

The left column is also the size of what pass 2 caught. TSLA's PDH today prints **364.69**;
the stale PMH would have printed **376.37**, ~$11.7 *above* the prior day's high. On Austin's
phone at 09:25 that reads as a large gap-up premarket and is a level he would have drawn.
Not a cosmetic staleness bug.

## Dry-run, re-run here, not quoted

`python research/premarket_list.py --dry-run`, 2026-09-06: 11 symbols
(TSLA NVDA AAPL AMD META GOOGL AMZN MSFT PLTR QQQ SPY), all with PDH/PDL populated and
`PMH n/a  PML n/a`. Polygon returned 403 on 5 symbols and 429 on 6 — every error line is
truncated at 80 chars *after* `_scrub()` has already rewritten `apiKey=…`; **the key does not
appear**, checked with and without a `grep -v apiKey` filter. No traceback. The message body
is plain English plus the four level abbreviations, which are Austin's own names for them
(rulebook, 2026-08-29) — no flag names, no ticket ids.

## Scheduled task

`\OmenPremarketList`: Schedule Type Weekly, Days **MON TUE WED THU FRI**, Start Time
**09:25:00**, State Enabled, next run 2026-09-07 09:25. Task To Run
`C:\Users\aharg\Desktop\Projects\tradingbot\research\premarket_list_run.cmd` — the file
exists and is tracked (`git ls-files` returns it; added in `3c8e586d`, which is a real
commit, contrary to my expectation from pass 1's hash mix-up). Last Result `267011` =
0x41303, "has not yet run".

## The push-tag half, re-checked at c59abe88

The `live_scanner.py` diff is 8 lines: one module constant `PUSH_TAG_PRERECONCILE` and one
`body += …` inside `_push_s_signal`. `_push_s_signal` **places no order** — it reads
`rec.get("alpaca_order_id")` that some earlier caller already set, and returns
`notify_ntfy.push(...)`. Nothing in the diff is upstream of, or conditions, the Alpaca path.
Confirmed: ntfy text only.

## Residual 1 — the same defect class is still live in the sibling leg (not confirmed, dated)

`_yf_batch_prevday` ends with an **unconditional** fallback:

    row = df.iloc[-1]      # last close before today -- holiday-safe

The comment is an assertion, not a check. That line fires only when `prev_iso` is missing
from the daily frame, i.e. when `_prev_trading_day` lands on a market holiday — first
occurrence **Tuesday 2026-09-08**, the session after Labor Day, when Polygon will also miss
09-07 and all 11 symbols fall through to it. If Yahoo has published a partial current-day
daily bar by 09:25 ET, `iloc[-1]` is *today's own* premarket range published as PDH/PDL —
exactly the bug just fixed one leg over. I could **not** confirm this: it needs a live 09:25
run on a trading day, and Sunday's frame ends at Friday either way. Reported as a dated risk,
not a defect. It is a second function and therefore a second row.

## Residual 2 — process

The builder committed `research/v1_referee_pass3.md` as part of `c84d0bd3`. Its content is an
honest repair note, but a builder must not author a file in the referee's namespace
(SWARM.md law 4: a builder never grades its own number). Left in place — nothing is deleted
here — but this page, `research/v1_referee.md`, is the referee record for V1.

## Verify gate, run here at this tree

- `research/regression_gate.py` → PASS, no baseline-fired mark went silent
  (any_signal 75→80, s_grade 5→25, all additions).
- `research/test_runner_stop.py` → ok, 70 checks across 3 sections.
- `research/test_universe_single_source.py` → ok, 29 symbols, 25 backtested, no private lists.

## Standard checks

- **Sample size:** V1 publishes no trade cell and no month cell — nothing to gate.
- **Dollar figures:** V1 publishes none. The prices in the table above are quoted levels from
  a live yfinance 1-minute frame, not P&L, and name their source and session.
- **Books:** V1 wrote no book, so there is no stamp to check.
- **One change per row:** `git show --stat c84d0bd3` = `research/premarket_list.py` (6 lines,
  one function plus its one call site) and one markdown note. Respected.
- **Mark files:** neither `c84d0bd3` nor `c59abe88` touches any mark corpus; `git status`
  shows none modified.

## Verdict

**Upheld.** The repair does what the builder says, the pass-2 defect no longer reproduces,
the live path survives the fix, the task is scheduled correctly at weekdays 09:25 with a
tracked command file, the push-tag diff never reaches the order path, and the gate is green.
Two residuals, both filed above, neither blocking: `_yf_batch_prevday`'s undated `iloc[-1]`
fallback (first exposure 2026-09-08) and the builder authoring a referee-named file.
