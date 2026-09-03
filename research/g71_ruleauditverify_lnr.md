# G7.1 — adversarial verify of the `ruleaudit` G3 claim (`level_not_respected`)

Scripts: `research/g71_lnrverify_recompute.py`, `research/g71_lnrverify_sides.py`.
Book: `research/bt2y_trades.json`, meta `2026-08-29T03:14:29`, **76,019 signals / 2,437
traded / 500 sessions / 2024-08-21..2026-08-21**. (The prompt's "2,595-trade post-T0 book"
no longer exists on disk — superseded at `145d564e`; `g71_advcapture.md:80`,
`g71_artifacts.md:27`. The prior agent used the current book: correct.)

## What reproduces exactly

| quantity | claimed | re-run |
|---|---|---|
| `level_not_respected` trips | 49,989 / 76,019 (65.76%) | **identical** |
| traded tripped | n=1,381 meanR +0.6054 | **identical** |
| traded clean | n=1,056 meanR +0.4763 | **identical** |
| delta | +0.1291R | **identical** |
| traded sgrade money | S +0.3547 (298) / A +0.5298 (525) / C +0.5918 (1,614) | **identical** |
| `downgrade.py:218-223` is `abs(b["c"] - level) <= e`, symmetric | yes | **yes** |

No look-ahead: window is `bars[max(0,i-12):i+1]`, `_eps`→`_atr` over `bars[lo:i+1]` (`:130`).
Branch is reachable (65.76%). Sgrade rebuilt from stored `downgrades`+`confluence`
reproduces the book's `sgrade` on **76,019 / 76,019** rows, so the ladder arithmetic is
auditable off the book.

## Where the claim fails

**1. Not the largest input.** `counter_trend_not_respected` trips **69,537 (91.47%)** vs
49,989 (65.76%). By |traded delta| it is 5th of 8 (`no_retest` −0.3677, `exhausted` +0.3986,
`chase` +0.3449 all larger). Second by reach, fifth by effect.

**2. The live path does not route on the S/A/C grade.** `backtest_2y.py:151,196` attaches
`sgrade` *after* the trade is simulated, for report filtering only; `traded` comes from the
legacy `t.grade`. The only code that could route on it is `backtest_week.py:454`
(`grade_ok = _sgrade_84(t, runner) == "S"`), behind `RULE84_ARM_SGRADE`, default **0**
(`signal_runner.py:265`); `ENABLE_SAC_LADDER` default 0 (`:660`, and `g71_scanners.md`
confirms it never ran); `TRADE_S_ONLY` (`:492`) has zero readers. **87.77% of traded rows
are non-S** (traded rate S 298/9,923 = 3.0%, A 525/17,639 = 3.0%, C 1,614/48,457 = 3.3% —
no gradient at all).

**3. The backwards ranking is not caused by this variable.** Delete it and re-grade:

| ladder | traded S | traded A | traded C |
|---|---|---|---|
| as shipped | +0.3547 (298) | +0.5298 (525) | +0.5918 (1,614) |
| `level_not_respected` deleted | **+0.4653 (550)** | **+0.5253 (773)** | **+0.6078 (1,114)** |
| `counter_trend_not_respected` deleted (control) | +0.4275 (727) | +0.5723 (780) | +0.6257 (930) |
| `no_retest` deleted (control) | +0.3653 (327) | +0.4789 (578) | +0.6154 (1,532) |

Still monotonically backwards with the variable gone. The inversion is a property of the
whole ladder, not this input.

**4. The ballot quote is truncated.** a3 in full: *"has to hold the level **or candle
period. chopping around is not respecting.**"* a1, answer `all`: *"all of the above, candles
closing through the level make it less clean, however it happens each instance lowers
probability."* Chop **at** the level is disrespect in Austin's own words — which is what the
committed test computes. a2's *"still wicking around it its fine"* is about **wicks**, and
the committed test already reads closes only. "Only a close THROUGH the level is disrespect"
is not what a2/a3 say.

**5. Side decomposition: "either side" is true, and mostly the correct side.** Replaying all
2,437 traded rows (99.55% agreement with the book's stored flag), the closes the shipped
rule counts split **2,938 on the correct side within ε / 1,782 on the wrong side within ε**,
with a further **5,973 closes THROUGH the level by more than ε that the shipped rule never
counts**. So the mechanical part of the claim holds.

**6. The proposed fix, measured on this book for the first time, does not deliver.**

| reading (traded rows, n=2,437) | trips | tripped | clean | delta |
|---|---:|---:|---:|---:|
| SHIPPED `\|c−level\| ≤ ε` either side, ≥2 | 1,382 (56.7%) | +0.5929 | +0.4927 | **+0.1002** |
| CLAIM: close THROUGH by > ε, ≥2 | 1,364 (56.0%) | +0.5243 | +0.5815 | **−0.0573** |
| HYBRID: any close on the wrong side, ≥2 | 1,656 (68.0%) | +0.5542 | +0.5395 | +0.0147 |
| wrong side **within** ε only, ≥2 | 429 (17.6%) | +0.7387 | +0.5091 | +0.2296 |

The claim's reading turns the sign correct but the magnitude is **0.057R** — far inside the
±1.5799R A/B error bar this project already recorded — and it still trips on 56% of the
book, so the "trips on 65.8%" objection is not remedied. Re-grading under it:
S +0.4809 (179) / A +0.4706 (676) / C +0.5910 (1,582) — **C is still the best bucket**.

**7. Not new.** `research/p15_level_respect.md` (commit `8f5cb36b`) already ran two
close-through readings and stopped; `PHASES.md:57` records P15 green/STOPPED and
`a1_threshold_sweep.md:25` already published 62.8% / +0.104R on the older book. P38
(`PHASES.md:145`) is the open ticket and it asks for a **pre-setup level-history** anchor,
not a fourth post-break side test.

**8. Unstated caveat.** The "level" handed to `level_not_respected` in this book is the
trade's **stop** (`backtest_2y.py:151`, `dg.score(dbars, t.entry_idx, t.stop, ...)`), so
every number above measures closes near the stop, not near the level. `p15_level_respect.md`
flags this; the claim does not.

## Verdict

Numbers: reproduced. Diagnosis: wrong on superlative, wrong on routing, wrong on causation,
wrong on the ballot text, and the proposed fix is a re-run of a rejected P15 attempt that
moves 0.057R. Do not apply Diff 3.
