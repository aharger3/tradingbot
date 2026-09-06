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
