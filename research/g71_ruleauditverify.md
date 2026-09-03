# G7.1 / ruleauditverify — adversarial check of the "flat 2R target" claim (S11)

**Claim under test** (`research/g71_ruleaudit.md` §1a row S11): *"Every non-84% row still
plans a flat 2.000 R:R target, which makes the mean-R 2.0 money gate arithmetically
unreachable."* Evidence offered: `backtest_week.py:836-837`, the planned-R:R histogram in
`research/g71_ruleaudit_counts.py` §3, and `mean R = wT−(1−w)`.

**Verdict: REFUTED.** The cited line writes a field the shipped engine never reads, the
histogram's shape is an export-rounding artefact, and the book it was taken from already
books 463 trades above +2.0R with a max of +24.35R.

Reproduce: `python research/g71_ruleauditverify_rr.py` (read-only, over
`research/bt2y_trades.json`, 2026-08-29 03:14, 76,019 signals / 2,437 traded / 500 sessions).

---

## 1. The branch is dead on the shipped config

`backtest_week.py:144` — `SCALE_PLAN = "hod_then_runner_be"` by default (via the
`OMEN_LADDER_MODE` default `"B"` at `:141`). Confirmed at import:
`backtest_week.SCALE_PLAN == 'hod_then_runner_be'`.

`backtest_week.py:770-772`:

```python
if SCALE_PLAN:
    _ladder_bar(t, c, i, open_trades, runner)
    continue
```

Every read of `t.target` that can decide an exit sits **below that `continue`**:

| line | code | reachable at default? |
|---|---|---|
| `backtest_week.py:789` | `targeted = c.high >= t.target …` | **no** |
| `backtest_week.py:806` | `t.outcome, t.exit_price = "win", t.target` | **no** |
| `backtest_week.py:469` | `runner.session.entry_target = t.target` (84% arming) | yes, not an exit |
| `backtest_week.py:1197` | report field | yes, not an exit |

The 2R number written at `:836-837` is therefore a **vestigial plan field**, exported to
the book and never consulted. The claim reads a dead branch as the shipped exit policy —
which is precisely the bug class `research/g71_ruleaudit.md` itself names ("branches that
can never evaluate true"), applied in reverse.

**Measured:** traded rows whose exit price equals their planned 2R target: **2 of 2,437**
(0.08%) — and both are coincidental collisions with a ladder level, not target fills.

## 2. What actually sets the exit is a structural-level ladder

`_ladder_bar` (`backtest_week.py:560-607`) exits on:

- **rung 1** — `t.scale_level` = the causal session extreme as of the entry bar
  (`:851`, `:856`), 50%; then `t.runner_stop = t.entry` (`:565`).
- **rung 2** — `t.runner_target` = `min/max` over `{PDH, PMH, next psych whole $}`
  beyond the scale point (`:852-854`, `:857-859`), 50% (`:579`, `:604`).

That *is* rulebook b4 / S11 — "the target is the next structural level, not 2× risk" —
already shipped. It is an **incomplete** implementation of that rule (the level set is only
PDH/PMH/whole-dollar, not the full level book, and the psych-whole-$ fallback is mechanical,
not structural), which is a legitimate open ticket. It is **not** "target = 2R".

## 3. The 2.0R ceiling the arithmetic assumes does not exist in the book

Over the same 2,437 traded rows the claim counted:

| quantity | value |
|---|---:|
| realized mean R | **+0.5495** |
| realized **max** R | **+24.3480** |
| traded rows with R > 2.0 | **463 (19.00%)** |
| winning rows, n / mean R | 1,198 / **+2.0892** |
| winners booking > 2.0R | **454 of 1,198 (37.9%)** |
| scaled rows | 1,217 of 2,437 |
| realized mean **loss**-leg R | **−0.9393** (not −1.0) |

`mean R = wT − (1−w)` requires *both* that every win books exactly `T` and every loss
exactly `−1R`. Neither holds: 37.9% of winners exceed T, and the loss leg averages −0.9393
because scratches and BE-stop exits sit in it. The correct decomposition,
`0.4916 × 2.0892 + 0.5084 × (−0.9393) = +0.5495`, reproduces the book exactly. Mean R 2.0
is **far away** — the shipped engine is at +0.55R — but it is not *arithmetically barred*.
The claim's stated mechanism for the miss is wrong, and pointing P21/P32 at `:836-837`
would change nothing in the shipped book.

## 4. The histogram is an export-rounding artefact

`backtest_2y.py:170-171` rounds `entry`, `stop` and `target` to **2 decimal places** before
writing the book. `research/g71_ruleaudit_counts.py:60-64` then divides those rounded
numbers. The tidy-looking `{1.0, 1.5, 3.0, 2.5, 1.667, 1.75}` buckets are what
`round(x,2)/round(y,2)` quantizes to when `y` is a couple of cents — not alternative plans:

| |entry−stop| after rounding | n | ratio exactly 2.0 | within 0.05 | far |
|---|---:|---:|---:|---:|
| < 0.05 | 22,023 | 14,834 | 0 | **7,189** |
| 0.05–0.20 | 27,253 | 20,215 | 43 | 6,995 |
| 0.20–1.00 | 20,194 | 15,587 | 4,159 | 448 |
| ≥ 1.00 | 2,040 | 1,603 | 420 | **17** |

The deviation vanishes as risk grows — 17 "far" rows out of 2,040 at risk ≥ $1.00. The
claim also asserts the non-2.0 rows are the 84% re-entries; they are not: of the 19,271
non-2.0 rows, **17,353 are `break_and_retest` and 1,733 are `one_candle_rule`**, against
only 388 `reentry_84_rule` signals in the entire book.

## 5. What does survive

- The **book was the right one**. `research/bt2y_trades.json` (2,437 traded, 2026-08-29
  03:14) is the current shipped book; the 1,017-trade book is the superseded
  `research/a2_bt2y_rerun.json` (2026-08-27), and no 2,595-trade book exists in the repo.
  The prior agent did not count the stale book.
- **No look-ahead** in the target computation: `scale_level` uses `candles[:i+1]` (`:851`),
  and PDH/PMH are prior-session levels. Clean.
- The *underlying* rule gap is real but narrower than stated: the runner target's level set
  is thin (PDH/PMH/whole-$ only). That is the P21/P32 ticket. It should be written against
  `backtest_week.py:852-859` (`_ladder_bar`'s level set), **not** against `:836-837`.

## 6. Correction to apply to `research/g71_ruleaudit.md`

No code change. Row S11 should read:

| # | impl | file:line | reachable? | divergence |
|---|---|---|---|---|
| S11 | **partial** | `backtest_week.py:852-859` `runner_tgt` | 1,217 scaled rows; 463 rows > +2.0R, max +24.35R | the structural target exists (PDH/PMH/psych-$) but the level set is thin. `:836-837`'s 2R plan is **dead code** under the default `SCALE_PLAN` and gates nothing. `mean R = wT−(1−w)` does not apply — 37.9% of winners exceed T |
