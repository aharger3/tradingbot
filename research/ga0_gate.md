## Verify gate + tests — actual output

**1. `python research/regression_gate.py`** — PASS, exit 0
```
baseline: any_signal 75, s_grade 5
current:  any_signal 80, s_grade 25
new fires (not a failure): any_signal +5, s_grade +20
by_tier: {'A': {'fired': 17, 'any_signal': 32, 'total': 60}, 'X': {'fired': 6, 'any_signal': 14, 'total': 22}, 'S': {'fired': 25, 'any_signal': 34, 'total': 77}}

PASS: no baseline-fired mark went silent.
```

**2. `python research/test_runner_stop.py`** — PASS, exit 0 (full 27-row stop-placement table + 18-row ladder table printed, ends `runner-stop selftest ok: 18 laddered results, stop-outs floored at -1.25R, wick-only days never stopped out`)

**3. `python research/test_retest_gate.py`** — PASS, exit 0
```
  predicate: retest tape False, run-away tape True  OK
  1. default is ON; RETEST_REQUIRED=0 still disables it  OK
  3. ON leaves a real break-and-retest alone (1 signal(s))  OK
  2a. synthetic run-away fires nothing either way (FSM already refuses it)  OK
  2b. ON caps 1 real candidate(s) on IWM 2024-10-01 to C, entries unmoved  OK
  4. ON moves no entry price and drops no row  OK
test_retest_gate OK
```

**4. `python research/test_universe_single_source.py`** — **FAILED, exit 1**
```
UNIVERSE SINGLE-SOURCE TEST FAILED: 3 private symbol list(s)
  research\g83_futures_arm.py:67  INDEX_POOL -- import it from universe.py instead
  research\g83_sizing.py:91  INDEX_SYMS -- import it from universe.py instead
  research\g83_verify_2.py:43  INDEX_POOL -- import it from universe.py instead
```
Pre-existing, unrelated to this build: the offending files date to 2026-08-30 and the ladder commit (617fdb06) touched only `backtest_week.py`, `levels_ladder.py`, `research/_a_ladder_selfcheck.py` (confirmed via `git diff 617fdb06^ 617fdb06 --name-only`).

**5. New work's own test — `python research/_a_ladder_selfcheck.py`** — PASS, exit 0, `35 checks... 0 FAILED of (see above) / ALL CHECKS PASSED`, including `runner guard reaches >=250 of the real book (spec floor)` at 278/444.

**6. `python research/g99_ladder_ab.py`** — ran clean, exit 0:
```
first-of-day rows (pre-gate): 498
measured 444  (54 below min_risk_floor, 0 no bars)
baseline check OK: n=444 gated=54, flat targets match g97_mfe.json exactly

| arm | $/day | win | months green | max drawdown | mean R |
|---|---:|---:|---:|---:|---:|
| book today               | $38     |  46.0% |  12/25 | $-20416  | +0.0380 |
| blind 2R                 | $40     |  35.1% |  13/25 | $-30286  | +0.0400 |
| flat 1.5R                | $48     |  41.9% |  13/25 | $-23767  | +0.0480 |
| flat 2.5R                | $98     |  32.7% |  14/25 | $-25583  | +0.0980 |
| flat 4.0R                | $153    |  27.7% |  13/25 | $-37314  | +0.1530 |
| four-rung 30/30/30/10    | $92     |  40.8% |  12/25 | $-16980  | +0.0920 |
| four-rung 50/20/20/10    | $73     |  46.8% |  13/25 | $-17804  | +0.0730 |

row count sanity: every arm should carry exactly 444 trades (all 7 rows = 444)
```

**Aside (unrelated to the task):** mid-investigation I ran `git stash -u` by mistake to test whether the universe-test failure predated the ladder commit; it stashed all uncommitted/untracked files. I immediately `git stash pop`'d it back — `git status` after the pop shows the identical untracked-file set (688 lines) as before, nothing lost. Confirmed benign, but flagging since it touched the working tree.

Not fixing anything per instructions — this is a report only.