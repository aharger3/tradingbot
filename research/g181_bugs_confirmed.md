# g181 — the bug swarm, verified

**What is different now:** of the 71 findings the eight B1 finders filed, **15 survive a
refutation attempt with a concrete failing input you can re-run**; the other 56 are refuted,
and the single largest refuted class is "dead code behind a hardcoded `False`" — every one of
those flags is a *deliberately retired experiment with the measurement in its own comment*,
not a rule that went unreachable by accident.

Base `f8740f80`; run at HEAD `6d1acf85`, working tree clean of `.py` edits.
No dollar or R figure below is new — the only book read is
`research/bt2y_trades_retest_on.json` (built 2026-09-02 at `a89e90e2`, signal-bar CLOSE entry,
`stop_rule.stop_fill_price` stops, 1R = $1,000, 498 sessions, 4,022 traded rows).

Method: default **refuted**. A finding is CONFIRMED only if a command in this file reproduces
the defect. Claims quoted from a commit message or a vault note without re-derivation were
re-derived or dropped.

---

## CONFIRMED

### B-01 — his `S` is unrecoverable from the engine tier: the S/A round trip is broken
`signal_runner.py` `SAC_TIER` · high · **code, live gate**

`394bcfe0` ("Retire A+ and route the live path on his S grade instead") changed
`SAC_TIER['S']` from `'A+'` to `'A'`. `research/t70_test1_score.py:78` still reads
`LADDER = {"A+": "S", "A": "A", "B": "A", "C": "C", None: "X"}`. So his **S** and his **A**
now both map to engine `'A'`, and the held-out scorer maps `'A'` back to `'A'`.

```
$ python -c "import signal_runner as sr; print(sr.SAC_TIER)"
{'S': 'A', 'A': 'A', 'C': 'C', 'X': 'X'}

his 'S' -> engine 'A' -> back 'A'   BREAKS   (expected 'S')
his 'A' -> engine 'A' -> back 'A'   ok
his 'C' -> engine 'C' -> back 'C'   ok
```

This is the exact failure `CLAUDE.md` names — *"Two grade ladders exist and must never be
mixed"* — and it means the A/B arm and `t70_test1_score.py` are counting different things:
**every S he marked scores as an A**. Two committed tests already assert the round trip and
both fail; neither is in the verify gate, so `394bcfe0` landed it silently.

| reproduce | result |
|---|---|
| `python research/test_sac_ladder.py` | rc=1, `AssertionError: ('S', 'A', 'A')` at line 81 |
| `python research/test_downgrade_grader.py` | rc=1, `AssertionError: DOWNGRADE_TIER must be the inverse of t70_test1_score.LADDER` at line 133 |

### B-02 — two ladders inside one module, disagreeing on his `A`
`signal_runner.py` · high · code

```
SAC_TIER       = {'S': 'A', 'A': 'A', 'C': 'C', 'X': 'X'}
DOWNGRADE_TIER = {'S': 'A', 'A': 'B', 'C': 'C'}
```

His **A** maps to engine `'A'` in one and `'B'` in the other, in the same file, both live.
`research/r3_downgrade_grader_ab.py:462` documents a third version (`S -> A+`), which no
longer exists. Whichever is right, three cannot be.

### B-03 — `HTF_BIAS_VETO` gates 42.2% of the backtest and 0% of live
`omen_bot.py:29`, `omen_bot.py:257`, `live_scanner.py:79-91` · high · **live/backtest divergence**

The veto returns `D` only when `htf_bias in ("bullish","bearish")`. On the book that is almost
always true; live it is never true.

| path | rows with a directional bias | vetoed |
|---|---:|---:|
| `bt2y_trades_retest_on.json`, traded rows | 3,795 / 4,022 (94.4%) | **1,699 `aligned=="against"` — 42.2%** |
| live scanner, 2026-09-01 | 0 | **0** |

Live evidence (`journal/scanner-2026-09-01.log`, UTF-16): **4,954** `HTF unknown` lines,
**5,050** `invalid_credentials`, **5,051** `401`. Still 3,551 `401`s on 2026-09-04. The
yfinance fallback (`_yf_daily_context`) returns `bias=None` unconditionally, so the grader
that produced every committed number is not the grader running live.

**The new part:** `live_scanner.py:84-86`'s own blocker note names the *wrong flag* —

> "`HTF_BIAS_GATE` defaults OFF in both paths, so today this changes nothing on its own"

`HTF_BIAS_GATE` is indeed OFF, but the flag that gates the `D` return is `HTF_BIAS_VETO`, and
it is **ON**. The note's conclusion is false by 1,699 traded rows.

### B-04 — ticket 23: the true `HTF_BIAS_VETO` / `HTF_GRADE_VETO` timeline
`omen_bot.py:29`, `spec0b_levels_check.py:60`, `omen-rulebook.md:851-881` · high · **documentation**

`spec0b_levels_check.py` **crashes today** because it asserts a default the code does not have:

```
$ python spec0b_levels_check.py
AssertionError: TradeGrade.X          # line 60: assert g_opp == TradeGrade.A_PLUS
                                      # "veto OFF by default: graded on PA alone"
```

The reconstructed timeline, from `git log -p -- omen_bot.py`:

| when | commit | what the flag actually did |
|---|---|---|
| before 2026-08-27 | — | the opposed-bias `D` return was **unconditional and unflagged** |
| 2026-08-27 | `fdc8e090` | `HTF_BIAS_VETO` introduced, default **`"0"` (OFF)** |
| 2026-08-27 | `71f39851` | default flipped **`"0"` → `"1"` (ON)**; "lifting it buys 1.7%, not 3,525" |
| 2026-08-28 | `f959cff5` | docstring corrected to "which is the SHIPPED DEFAULT" |
| 2026-08-28 | — | `omen-rulebook.md:855` records **"Deleted 2026-08-28"** — the name was never deleted |
| 2026-09-03 | `d0a38dc9` | adds `HTF_GRADE_VETO` (default **OFF**) to `omen_bot.py`, `signal_runner.py`, `test_htf_grade_veto_default.py` |
| **now** | `6d1acf85` | `grep -c HTF_GRADE_VETO omen_bot.py` = **0**. `d0a38dc9` *is* an ancestor of HEAD, but its `omen_bot.py` and `signal_runner.py` hunks are **not in the tree** — the 2026-09-03 history rewrite dropped them. `test_htf_grade_veto_default.py` is gone; `test_htf_bias_veto_default.py` (which asserts the ON default) is what survives, and it passes. |

So the rulebook's R4 entry describes a state that existed for part of one day and no longer
exists. The shipped flag is `HTF_BIAS_VETO`, default **ON**, and `spec0b_levels_check.py` is
the last artifact still asserting otherwise.

### B-05 — ticket 19: the two −1R counts measure two different columns, and neither doc says which
`stop_rule.py` docstring, `CLAUDE.md:185`, `backtest_week.py:773` · high · **documentation**

Both commits were right. They were never comparable.

| claim | commit | column | number |
|---|---|---|---:|
| "70 of 4,022 traded rows fill worse than −1.000R" | `bbcfd5cf` 2026-09-03 02:04 | **per fill, against original risk** | 70 (53 after the size gate; 6 on the −1.25R clamp; worst −1.3333R, MARA 2025-12-15 put) |
| "0 rows worse than −1.000R" | `ece08845` 2026-09-03 14:22 | **blended `r`** (nets the first scale-out's profit against the runner's loss) | 0 |

Re-derived here from `research/bt2y_trades_retest_on.json`:

```
traded rows        4,022
r < -1.0               0
r == -1.0          1,448
r < -1.25              0     worst traded row: NVDA 2024-09-03, r = -1.0
losses (r < 0)     2,216     <- CLAUDE.md:185's "0 of 2,216" checks out exactly
scaled rows        2,572     scaled rows with r < -1.0: 0
```

The book has **no per-fill column**, so `bbcfd5cf`'s 70 cannot be re-derived from it at all —
it needs a re-run with per-fill accounting. And this book was built **2026-09-02**, *before*
`ece08845`, so its zero is the blended column of the *pre-fix* engine, not proof of the fix.
After `ece08845`, `backtest_week.py:773` reads
`floor_r = _STOP_FILL_FLOOR_R or (DISASTER_R if DISASTER_STOP else MAX_LOSS_R)` with
`DISASTER_R = 1.0`, so per-fill worst is −1.000R by construction.

**The reconciled number for `stop_rule.py` and `CLAUDE.md`:** *per fill against original risk,
the floor is −1.000R and 0 rows breach it; on the pre-`ece08845` engine 70 of 4,022 traded rows
did (53 after the size gate, worst −1.3333R). On the blended column, 0 of 2,216 losses breach
−1.000R and 1,448 sit exactly on it.* `CLAUDE.md:185` is arithmetically correct and silent
about which column it means, which is how the same book supported both claims for twelve hours.

### B-06 — the live options sizer under-sizes every trade by 16%
`position_sizer.py:48` vs `options_sizer.py:62` · medium · code

`options_sizer.py:55-62` measured the delta and wrote the consequence down: a position sized at
delta 0.5 against a true 0.42 realizes **$840 of a $1,000 budget** (the ratio is exactly
0.42/0.5, independent of stock risk). `DEFAULT_DELTA` was set to 0.42 there. `position_sizer.py`
was not — and it is the one `signal_runner.py:3476` calls, with no delta argument.

```
$ python -c "import position_sizer as p; \
  print(p.compute_plan(stock_entry=100.0, stock_stop=99.58, direction='call').contracts_estimated, \
        p.compute_plan(stock_entry=100.0, stock_stop=99.58, direction='call', assumed_delta=0.42).contracts_estimated)"
47 56
```

### B-07 — the viability gate admits signals it is written to reject
`signal_runner.py:2057` · medium · **code, fire path**

`_min_viable_stop` is a hard gate on the fire path (`signal_runner.py:2623`, `:2747`). Its
docstring: *"Skip only when BOTH stock risk < 0.5% of entry AND estimated premium risk < $0.20."*
It estimates premium risk with a hardcoded `* 0.5`.

Failing input — entry 100.00, stop 99.58:

| delta | `risk_pct` | `premium_risk` | verdict |
|---|---:|---:|---|
| 0.5 (shipped hardcode) | 0.0042 | **$0.21** | **viable — fires** |
| 0.42 (`options_sizer.DEFAULT_DELTA`, measured) | 0.0042 | $0.1764 | rejected |

The gate passes a signal whose real premium risk is $0.176/share, below the $0.20 the gate
exists to enforce.

### B-08 — 14 committed tests fail, and no gate runs any of them
`CLAUDE.md:9`, `research/daily_run.cmd` · high · process

The gate is `python research/regression_gate.py && python research/test_runner_stop.py`. Both
pass (rc=0). The repo tracks **59** `test_*.py` files. The daily pass (`research/daily_run.cmd`)
adds nothing — it runs `daily_fetch`, `daily_homework` and `regression_gate` only.

Fourteen fail right now, every one outside the gate:

| test | rc | last line |
|---|---:|---|
| `test_austin_tier.py` | 1 | `(b) a level above the bar is clamped to its high` |
| `test_rule_710.py` | 1 | `flag OFF: a rule-7-failing signal is untouched` |
| `test_detect_wide.py` | 1 | `the FVG long branch routes to SignalType.FAIR_VALUE_GAP` |
| `research/test_downgrade_grader.py` | 1 | ladder inverse assertion — **B-01** |
| `research/test_sac_ladder.py` | 1 | `AssertionError: ('S','A','A')` — **B-01** |
| `research/test_entry_scratch.py` | 1 | `8 checks failed` |
| `research/test_onwatch_fill.py` | 1 | `short: a close on the session low moves the fill` |
| `research/test_paper_trader_stop.py` | 1 | `put: bar straddles both, closes above the stop: filled at 2.5` |
| `research/test_published_numbers.py` | 1 | `research\top_options_volume_2026-09.md` |
| `research/test_rule84_source.py` | 1 | `2 check(s) FAILED` |
| `research/test_structural_floor.py` | 1 | `GOOGL 2024-10-15 bar 32 should be SILENT with the flag` |
| `research/test_universe_single_source.py` | 1 | `research\g83_verify_2.py:43 INDEX_POOL -- import it from universe.py` |
| `research/test_master_homework_page.py` | 1 | (no message) |
| `research/test_omen_test1_page.py` | 1 | `FAILED: 100 cards, static SVG, no canvas, progress counts X` |

`test_universe_single_source.py` is the one `CLAUDE.md` says *"fails the build if a new one
appears"*. It is failing, so a module **has** appeared with a private ticker list
(`research/g83_verify_2.py:43`), and nothing caught it.

### B-09 — `archive_1m.py` is called the one way its own docstring says never to call it
`run_daily.ps1:32` · high · ops

`archive_1m.py:28-30`: *"Polygon returns 403 for the CURRENT day on this plan … so an
unattended job must ask for completed sessions — see `--back`."* `run_daily.ps1:32` runs it with
no `--back`, and `archive_1m.py:57` defaults `end = date.today()`, so the only day it ever
requests is the 403 day.

```
$ python -c "import polygon_feed; print(len(polygon_feed.fetch_day('AAPL','2026-09-04')))"
959
$ python -c "import polygon_feed; polygon_feed.fetch_day('AAPL','2026-09-05')"
HTTPError: 403 Client Error: Forbidden
```

`data_archive/` reaching 2026-09-04 is `research/daily_fetch.py` (yfinance) doing the work;
`archive_1m.py` has contributed nothing since the plan changed. Fix is `--back 1`.

### B-10 — the daily run pulls before it scans, and one bad pull killed the whole live path
`run_daily.ps1:26` · high · ops

`git pull --rebase --autostash` runs at line 26; `live_scanner.py` at line 29. On 2026-09-03 the
pull brought in an `omen_bot.py` that did not parse, and the entire day died — scanner and
archiver both (`journal/scanner-2026-09-03.log`, 80 lines against ~8,000 on a normal day):

```
File "…\omen_bot.py", line 219
    opposed trend = D when HTF_BIAS_VETO=1 (default 0 — P16/W3, the veto
SyntaxError: invalid character '—' (U+2014)
```

An unattended job that self-updates from `main` with no syntax check between the pull and the
run has no floor under it. A `python -c "import live_scanner"` smoke test between lines 26 and
29 would have skipped the pull and scanned on yesterday's code.

### B-11 — `OmenWeeklyDigest` is enabled and its script does not exist
high · ops

```
OmenWeeklyDigest | Ready | 8/30/2026 6:00 PM | LastTaskResult 4294770688
$ ls run_weekly_digest.ps1  ->  No such file or directory
```

Enabled, scheduled, failing every week since 2026-08-30.

### B-12 — `a6_dispatch.ps1` points at the junction tree dissolved 2026-08-06
`a6_dispatch.ps1:5,9,10` · medium · ops

All three lines use `C:\Users\aharg\aharg\Desktop\projects\tradingbot` (doubled `aharg`,
lowercase `projects`). That path does not exist. `OmenA6PaperLog`'s last run returned
`2147942402` = `0x80070002` ERROR_FILE_NOT_FOUND. The task is already **Disabled**, so this is
a latent trap rather than a live outage — but the script is committed and wrong.

### B-13 — `market_open_healthcheck.py` checks three paths, two of which cannot exist
`market_open_healthcheck.py:98,99,115` · medium · ops

`C:\Users\aharg\projects\tradingbot\` does not exist. Two of the three `CRED_FILES` entries can
never match, and the refresh-token format check at line 115 opens the same dead path, so it is
skipped unconditionally. The healthcheck reports on Tastytrade credentials it never reads —
while Tastytrade is in fact 401ing 3,551 times a day (B-03).

### B-14 — five homework decks are ignored and untracked, two of them from this week
`.gitignore:83` · high · **THE ONE RULE**

`git check-ignore -v` on `research/decks/*.html`:

| deck | tracked | ignored |
|---|---|---|
| `omen-5.1-index-day-deck.html` | **YES** | no |
| `omen-5.1-tsla-day-deck.html` | **YES** | no |
| `omen-trade-anatomy.html` | **YES** | no |
| `omen-5.2-index-day-deck.html` | NO | `.gitignore:83` |
| `omen-5.2-tsla-day-deck.html` | NO | `.gitignore:83` |
| `omen-5.3-mixed.html` | NO | `.gitignore:83` |
| `omen-daily-2026-09-03-s10.html` | NO | `.gitignore:83` |
| `omen-s-accuracy-100.html` | NO | `.gitignore:83` |

The three tracked ones prove the intent. `research/decks/**/*.html` swallows the rest and no
un-ignore rule covers them — this is the 5.2 T6 loss described in `CLAUDE.md`, still open, and
it has now taken two decks from the last three days.

**Scope, stated honestly:** the HTML file is the *instrument*, not the marks. Answers live in
localStorage and in the exported `.jsonl`. Losing these files loses the ability to re-serve the
same cards and to audit what he was shown — not the judgements themselves. Real, and smaller
than "13 files of judgement data".

### B-15 — three more scheduled tasks are enabled and returning failure
high · ops · *found while verifying B-11/B-12, not filed by a B1 finder*

```
omen-corpus-harvest | Ready | 9/4 2:00 AM  | 4294967295 (0xFFFFFFFF)
OmenDailyHomework   | Ready | 9/4 4:15 PM  | 1
OmenSignalBot       | Ready | 9/4 9:25 AM  | 267014
```

`OmenDailyHomework` is the deck pass `CLAUDE.md` describes as the daily instrument. It returned
1 on its most recent run.

---

## REFUTED — 56 findings, one line each

**Dead code behind a hardcoded flag (11 findings, lens 1).** Every one is real dead code and
none is a bug: each flag is a retired experiment whose own comment carries the measurement that
retired it. The bug class in `omen-rules-unreachable-in-code` is a *ratified* rule that became
unreachable; none of these is ratified.

| # | claim | why refuted |
|---|---|---|
| 1 | `RULE84_ARM_BNR_ONLY` always False, unreferenced | true and harmless — an unused derived boolean, no behaviour depends on it |
| 2 | `HODLOD_PAIR` block unreachable | `HODLOD_PAIR = False` is deliberate; comment carries F3's measurement (19 tr/yr, 33.3%W, −$228) |
| 3 | `BNR_STOP_MODE == "retest"` unreachable (long) | deliberate; F2 A/B 2026-07-11 measured both alternatives losing |
| 4 | `FVG_RETEST` block unreachable (long) | deliberate; 07-05 A/B (FVG dilutes B&R) named in the comment |
| 5 | `FLAG_ENABLED` block unreachable (long) | deliberate; T5 comment says the change was a *label* fix on a dormant setup |
| 6 | `BNR_STOP_MODE == "retest"` unreachable (short) | same as #3, mirror |
| 7 | `FVG_RETEST` block unreachable (short) | same as #4, mirror |
| 8 | `FLAG_ENABLED` block unreachable (short) | same as #5, mirror |
| 9 | `LEVEL_BLOCK_CAP` block unreachable | deliberate; comment records the cap was replaced by scale targets |
| 10 | `RULE_710_ENABLED` block unreachable | deliberate; DEFAULT OFF pending A/B, stated across lines 467-510 |
| 11 | `AUSTIN_TIER_ENABLED` else-branch unreachable | true; `setdefault(..., None)` on a dead branch changes nothing |

**Flag defaults vs the vault (3 of 5, lens 2).**

| claim | why refuted |
|---|---|
| `RETEST_REQUIRED=1` not ratified in the rulebook | it is ratified in `CLAUDE.md` with a matched book pair; "not in the rulebook" is a filing question, not a defect |
| `ON_WATCH=1` default unstated in the vault | absence of a vault line is not a code defect; the flag's own comment states the A/B contract |
| `HTF_BIAS_GATE` (OFF) vs `HTF_BIAS_VETO` (ON) are two switches on one concept | they gate different things — `_GATE` caps counter-trend to C, `_VETO` returns D. Folded into **B-03**, which is the real defect |

**Constants that "disagree" (6 of 9, lens 3).** Six are the *same value* in two places —
duplication, not disagreement, and no input distinguishes them:
`RISK_DOLLARS 1000.0` ×3 (`a2_bt2y_summary.py:32`, `g71_instrument_spread.py:85`,
`g71_standard_report.py:48`) all equal `backtest_week.py:64`;
`EPS_FRAC 0.25` = `BAR_EXTREME_FRAC 0.25`;
`CHASE_PCT 0.005` = `signal_runner.CHASE_PCT`;
`0.005` at `signal_runner.py:2058` = `MIN_VIABLE_STOP_PCT`.
`research/sizing.OPTIONS_DEFAULT_DELTA = 0.5` is refuted separately: it is labelled a
placeholder, and its only consumer `dollars_options` is called from one research arm
(`g83_futures_arm.py`) that reports it beside a shares figure, never as a shipped number.

**Swallowed exceptions (9 of 9, lens 4).** All nine `except Exception:` clauses are real, and
all nine claims of *invisibility* are false — the outcome is logged one level up. The daily
log prints `Tastytrade: session auth failed: HTTP 401 …` once and
`[SYM] tasty fetch failed (…), trying yfinance` per symbol (`live_scanner.py:582`), and
`HTF {bias or 'unknown'}` per symbol (`live_scanner.py:647`). The 2026-09-01 log carries 5,050
of the first pair and 4,954 of the second — the loudest possible failure. `dxlink.py:65,196`
and `live_scanner.py:1224,1256` are `break` / `return []` on a socket read whose empty result is
checked by the caller. The *substantive* problem behind this lens is that nothing acts on the
log, which is **B-03**, not the `except` clauses.

**Tests that "hang" (6 of 8, lens 5).** The finder used a 5-second timeout. At 120 s:
`test_build_s_sweep.py`, `test_deck_selection.py`, `test_field_distinctness.py`,
`test_live_batch_fetch.py`, `test_t14_arrival_ladder.py`, `test_t21_card_filter.py` all pass
(rc=0). The two that genuinely fail are folded into **B-08**.

**The −1R mechanism claim (lens 6).** "floor_r computed with wrong condition" is refuted —
`backtest_week.py:773` is correct and its `MAX_LOSS_R` fallback is guarded by `DISASTER_STOP`,
exactly as the surrounding comment describes. The *documentation* gap is real and is **B-05**.

**Scheduled tasks and scripts (2 of 10, lens 7).**

| claim | why refuted |
|---|---|
| `OmenForwardClock` is Ready and should be Disabled | it **is** Disabled — `Get-ScheduledTask` says so |
| `OmenA6PaperLog` is Ready | it **is** Disabled; the bad paths are still real and are **B-12** |

**`.gitignore` (4 of 5, lens 8).**

| claim | why refuted |
|---|---|
| `research/*.html` swallows 6 files "with judgement data" | all six are generated report/homework *pages*; they are regenerable from committed scripts and hold no answers. `research/decks/` is the case that matters — **B-14** |
| a future `scored_days.jsonl` would slip the un-ignore rules | true and hypothetical: no such file exists. The 20 ignored+untracked `research/*.jsonl` with a `grade` key are all `corpus_engine_*` **engine output**, which is what the rule is for |
| a future `derived_tiers_v3.jsonl` would slip | same — speculative, no failing input |
| `research/*.jsonl` does not cover subdirectories | correct by design; `research/marks/**` is separately un-ignored, and the finder's own evidence says current directories are safe |

---

## For B3, in fix order

1. **B-01 / B-02** — the ladders. Nothing downstream of a grade can be trusted until his `S`
   round-trips. Fix `SAC_TIER`/`LADDER`/`DOWNGRADE_TIER` as one change with the two existing
   tests as the gate.
2. **B-03** — decide whether the veto is live behaviour or backtest-only, then make both paths
   agree. Correct `live_scanner.py:84-86` either way.
3. **B-04 / B-05** — the two documentation fixes named in the spec.
4. **B-06 / B-07** — one delta constant, imported, not three.
5. **B-08** — put the failing tests in a gate, or delete the ones that measure retired arms.
   Do not leave 14 red tests un-run.
6. **B-09 / B-10 / B-11 / B-12 / B-13 / B-15** — ops hygiene; B-10 is the one that can take
   a whole trading day again.
7. **B-14** — un-ignore `research/decks/**/*.html`, `git add -f` the five, verify by eye.
