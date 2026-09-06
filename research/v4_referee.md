# V4 referee — refuted

**Builder commit:** `79d6f57f` ("V4: live lane follows the loop -- 5 flags mirrored")
**Referee script:** `research/v4_referee.py` (committed beside this file)
**Base:** `git merge-base --is-ancestor 1539dd7f HEAD` OK; HEAD == origin/main == `79d6f57f`.

**Verdict: refuted.** The flag *parity* the row claims is real and I reproduced it. What is
not real is the *guard* — the row's headline deliverable, the test that is supposed to make a
future drift fail. It cannot fail for the two drifts most likely to happen next. Two defects,
both in `research/test_live_follows_loop.py`, both demonstrated by
`research/v4_referee.py`.

---

## What holds up

| claim | how I checked it | result |
|---|---|---|
| The 5 live flag values equal the loop's shipped set in `research/tape/cycles.md` | ran `research/test_live_follows_loop.py`; separately grepped the five definitions in `signal_runner.py` (lines 72, 258, 496, 535, 855) and diffed them against the tape by eye | holds — `MIN_PT1_R=0`, `RULE84_DECIDED=0`, `OCR_RETEST_DISPLACEMENT=0`, `TREND_DEF=off`, `DAY_POLICY=3fires_stop_win_or_2loss` |
| `.env` really is read by the live lane | `signal_runner.py:18-32` `_load_env_file`, re-called at `live_scanner.py:142-143` | holds |
| Alpaca is paper-only, no live key | `broker/alpaca.py:96` — `TradingClient(..., paper=True)` is a hard-coded literal, not an env var; the only credentials read are `ALPACA_PAPER_KEY` / `ALPACA_PAPER_SECRET` (lines 56-57, 89-90) | holds |
| Replay never submits | `live_scanner.py:1531-1534` sets `runner.replay = True` and never constructs a broker; `_alpaca_submit_entry` asserts `not runner.replay` at line 1175 | holds |
| The morning report survives a missing ledger | `journal/alpaca-paper.jsonl` does not exist on this box. `python research/morning_report.py` and `--ledger journal/__nope__.jsonl` both print `No paper trades logged for 2026-09-04. Nothing to report.` and exit 0 | holds |
| Verify gate green at `79d6f57f` | ran all three myself | `regression_gate.py` PASS (any_signal 75→80, s_grade 5→25, 0 baseline-fired marks silent); `test_runner_stop.py` 70 checks ok; `test_universe_single_source.py` ok, 29 symbols |
| One change per row, no mark file touched | `git show --stat 79d6f57f` = 2 files, both new, both under `research/`; `git status -sb` clean | holds |
| Stamped books | the row wrote no book | n/a |
| Dollar figures | the row publishes none | n/a — nothing to size-gate |

---

## Defect 1 — the test cannot see a newly shipped flag, which is the drift it exists to catch

`research/test_live_follows_loop.py`, docstring:

> *"a future cycle that ships a new flag fails this test until `live_scanner.py` /
> `signal_runner.py` are updated to match -- the live lane can never silently drift from the
> loop."*

`parse_cycles_md` (line 51) keeps a row only `if flag in FLAG_ENV`, and `FLAG_ENV` is a
hard-coded five-key dict at line 25. A sixth flag shipped into the tape is dropped on the
floor and the test stays green.

Reproduced (`v4_referee.py::b_new_shipped_flag`): append a `BRAND_NEW_FLAG | ship` row to a
copy of `cycles.md`, and `parse_cycles_md` returns the same five flags —
`['DAY_POLICY','MIN_PT1_R','OCR_RETEST_DISPLACEMENT','RULE84_DECIDED','TREND_DEF']`. No
mismatch, no failure.

So the test is a *value* check on five flags someone remembered to list, not the
drift alarm the row reports it as. The exact scenario it names — a new cycle ships something
and nobody mirrors it into live — passes silently.

## Defect 2 — the DAY_POLICY expectation is inverted, and the tape it reads is already disputed

`expected_env_value` (line 57) branches on `flag == "DAY_POLICY"` **before** it looks at the
decision, and `OFF_VALUES` has no `DAY_POLICY` key at all. So for *any* decision — `ship`,
`hold`, anything — the test demands `3fires_stop_win_or_2loss`.

Reproduced (`v4_referee.py::c_day_policy_unships`):
`expected_env_value('DAY_POLICY','hold')` returns `'3fires_stop_win_or_2loss'`. If the tape
flips that row to `hold`, this test fails the *correct* live configuration and passes the
wrong one — backwards.

That is not hypothetical. Commit `34c1546e`, the L5 pass-2 referee, **refuted** the DAY_POLICY
ship on the grounds that flipping the default makes `backtest_2y`'s default book the ON book
and blocks `loop_cycle`'s OFF==baseline guard. `research/tape/cycles.md` still carries the row
as `ship`, so V4 correctly mirrored what the tape says — but it hard-wired the disputed value
into the one place that is supposed to notice when the tape changes its mind.

## Defect 3 (minor) — "can never silently drift" overstates what `.env` does

`_load_env_file` (`signal_runner.py:28`) writes a key **only if it is not already in
`os.environ`**. An exported environment variable, or the harness `env` block, still beats the
`.env` pin. `.env` is also gitignored and untracked, so nothing about the pin travels to
another box or a fresh clone; the five values match the loop today because
`signal_runner.py`'s own defaults already match, not because of `.env`. The pin is a comment
with a file extension. Harmless, but it is not the guarantee the report states.

---

## What would make this row upheld

One change, in `research/test_live_follows_loop.py` only:

1. `parse_cycles_md` returns **every** flag in the table, and the test **fails** on a flag it
   has no `FLAG_ENV` entry for, naming it ("cycles.md gates `X`; this test does not know how
   to read it in the live lane"). That is the alarm the docstring promises.
2. `expected_env_value` reads the decision for `DAY_POLICY` too: `ship` →
   `3fires_stop_win_or_2loss`, anything else → whatever the pre-L5 default was, recorded in
   `OFF_VALUES` like the other four.

Neither touches engine code. The parity itself does not need re-measuring — it is correct
today.

---
---

# V4 referee, pass 2 — upheld, with one finding logged

**Builder commit under review:** `76d6e4ad` ("V4 repair: parse_cycles_md no longer silently
drops flags outside FLAG_ENV …"), the repair of `79d6f57f`.
**Referee script (pass 2):** `research/v4_referee_pass2.py`. Pass 1's `research/v4_referee.py`
is untouched and still runs — I re-ran it against the repaired test as an independent second
opinion.
**Base check:** `git fetch origin`; `git merge-base --is-ancestor 1539dd7f HEAD` OK;
HEAD == origin/main == `76d6e4ad`.

**Verdict: upheld.** Both pass-1 defects are genuinely fixed, and I proved each one with my
own code rather than reading the diff. Twelve checks, eleven pass. The twelfth is not a
defect in what the builder wrote — it is a gap between the *label* this row certifies and
the *behaviour* the live session runs, and closing it needs a second change, so it is logged
below as a follow-up rather than counted against the row.

No dollar figure appears anywhere in this row. It is a plumbing/parity row: there is nothing
to size-gate, no book was written, no stamp is owed.

## Pass-1 defect 1 — a newly shipped flag could not fail the test. FIXED.

`parse_cycles_md` used to filter rows to the hardcoded five `FLAG_ENV` keys *while parsing*,
so a sixth shipped flag vanished before the test body ever saw it. It now returns every flag
row the table contains, and the test body asserts `unknown_flags` is empty, naming the
offender.

Re-derived (check 1 and check 2, `research/v4_referee_pass2.py`): appending a synthetic
`BRAND_NEW_FLAG | ship` row to the tape's text now parses to six flags
(`BRAND_NEW_FLAG, DAY_POLICY, MIN_PT1_R, OCR_RETEST_DISPLACEMENT, RULE84_DECIDED, TREND_DEF`),
and pointing the test at that tape raises, with the message naming `BRAND_NEW_FLAG`. Before
the repair it parsed to five and passed green.

## Pass-1 defect 2 — DAY_POLICY demanded its shipped value even on a hold. FIXED.

`expected_env_value` checked `flag == "DAY_POLICY"` before it looked at the decision, so it
returned the shipped string unconditionally. It now branches on the decision like every other
flag, with `first3` — the documented prior default, per `signal_runner.py`'s own comment
block above the `DAY_POLICY` assignment — added to `OFF_VALUES`.

Re-derived (checks 3 and 4): `expected_env_value("DAY_POLICY", "hold") == "first3"` and
`("DAY_POLICY", "ship") == "3fires_stop_win_or_2loss"`. Rewriting the tape's DAY_POLICY row to
`hold` now makes the whole test fail on DAY_POLICY, where before it passed.

Pass 1's own script agrees: `python research/v4_referee.py` against the repaired test prints
`all three caught` (A value-drift, B new shipped flag, C DAY_POLICY un-ships).

## The parity itself, re-derived (check 5)

`research/tape/cycles.md` decisions vs the value a fresh `import live_scanner` actually
carries, read by me, not quoted from the report — five flags, five matches:

| flag | tape says | expected | live runtime |
|---|---|---|---|
| MIN_PT1_R | hold | 0 | 0.0 |
| RULE84_DECIDED | hold | 0 | False |
| OCR_RETEST_DISPLACEMENT | hold | 0 | False |
| TREND_DEF | hold | off | off |
| DAY_POLICY | ship | 3fires_stop_win_or_2loss | 3fires_stop_win_or_2loss |

`.env` (gitignored, this box only) also pins all five to exactly these values, and
`signal_runner._load_env_file` runs at import, so the pin is live-effective here. Pass 1's
point stands that the pin does not travel to a fresh clone; the code defaults match anyway.

## Alpaca, replay, morning report (checks 6–11)

- `broker/alpaca.py` constructs `TradingClient(..., paper=True)` with `paper=True` as a
  literal; there is no other `paper=` assignment in the file, so no env var or caller can
  point it at the live endpoint.
- The only credentials the file reads are `ALPACA_PAPER_KEY` and `ALPACA_PAPER_SECRET`. No
  live key name appears in it. (`.env` does hold a separate non-paper Alpaca key pair, but no
  code path in `broker/` or `live_scanner.py` reads those names — grepped.)
- No live-trading host literal in the file; the only Alpaca hostname text is the paper one.
- Replay still cannot submit: both `_alpaca_submit_entry` and `_alpaca_submit_exit` open with
  `assert not getattr(runner, "replay", False)`, and `run_replay` sets `runner.replay = True`
  and is never handed a broker.
- `journal/alpaca-paper.jsonl` does not exist today (nothing has paper-traded yet).
  `research/morning_report.py` pointed at a missing ledger prints
  `No paper trades logged for 2026-09-04. Nothing to report.` and exits cleanly — no crash.

## Finding, logged not charged: the live day policy carries the label, not the whole rule

The shipped `DAY_POLICY = 3fires_stop_win_or_2loss` means, in `signal_runner.py`'s own words,
"up to 3 fires a day, the day ends the moment a taken trade CLOSES a winner, or on the second
closed loss". `live_scanner.py` sets the session's limits from `MAX_TRADES_PER_DAY` (3) and
`CONSECUTIVE_LOSS_HALT` (2) and special-cases only `one_and_done`; the day-ends-on-a-win half
is governed by a different switch, `STOP_AFTER_WIN`, whose live default is **off** and which
`.env` does not pin. So the live session's actual behaviour today is the three-fires /
two-losses rule — i.e. the `first3` behaviour — while the string it carries and stamps into
`scanner_status.json` is the shipped one. `signal_runner.select_day_trades` (which does
implement the full rule) is documented as "not called anywhere in the live entry path".

This is not something `76d6e4ad` broke, and it is not fixable inside this row: turning
`STOP_AFTER_WIN` on is a second change, and it collides with a settled verdict (C10,
2026-07-13, stop-after-win default OFF, measured cost at the v2 tier). The honest statement
is narrower than the test's docstring: **the test guarantees the live lane's flag *values*
match the tape; it does not guarantee the live session *enforces* what a string-valued flag
names.** A follow-up row should either wire the live session to the policy or write the
divergence into the tape.

## Standard checks

- **Sample size.** No cell, no trade count, no month count, no verdict on one. N/A.
- **Dollars name their fill/exit/unit/script.** No dollar figure in the row. N/A.
- **Stamped books.** The row wrote no book. N/A.
- **One change per row.** `git show --stat 76d6e4ad` = 1 file, `research/test_live_follows_loop.py`,
  +27/−7. The original `79d6f57f` = 2 new files, `research/morning_report.py` and the test.
  No engine file touched by either.
- **Mark files.** Neither commit touches any mark corpus; `git status` shows none modified.
- **Verify gate at `76d6e4ad`.** Run by me, exit 0: `regression_gate.py` PASS,
  `test_runner_stop.py` 70 checks across 3 sections, `test_universe_single_source.py` ok
  (29 symbols, 25 backtested, no private lists).
- **Plain English.** `research/morning_report.py` is the only thing here Austin reads. Its
  output is plain English ("bought a call, 2 contracts", "Still open at end of day") — no
  ticket ids, no flag names.
