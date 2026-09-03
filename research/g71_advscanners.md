# G7.1 adversarial verify — track `scanners`, the "two filters kill 92.7% of S" claim

**Verdict: REFUTED.** The raw counts reproduce to the row. Both inferences built on them do not.

Rig: `research/g71_advscanners_funnel.py` (read-only over `research/bt2y_trades.json`,
meta `2026-08-29T03:14:29`, 500 sessions, 76,019 signals, **2,437 traded**).

## 0. What reproduces

`python research/g71_scanners_sfunnel.py` re-run verbatim gives exactly the claimed table:
9,923 sgrade==S; 4,632 (46.7%) HTF veto; 4,562 (46.0%) `_grade_pa`; 298 (3.0%) traded; and
46.1 / 45.4 / 3.2% over all 76,019. Book identity is fine — 2,437 is the current book
(`145d564e`), which supersedes the 2,595-trade T0 book; `DIRECTION.md:20,27` is the stale
line, not the funnel. Two line cites are off by one: the veto is applied at
`omen_bot.py:242` and `signal_runner.py:2365`, not :243 / :2364.

## 1. The 46.7% is a branch-ordering artifact, not a causal number

`omen_bot.py:242` `if opposed and HTF_BIAS_VETO: return TradeGrade.D` **short-circuits
before** `_grade_pa` is called at `omen_bot.py:244`. The funnel's `why()` therefore blames
the veto for every opposed row without ever learning what `_grade_pa` would have said. That
is first-blame, not attribution.

Measured base rate on the rows the veto never touched:

| population | rows the veto skipped (`aligned!=against`) | of those, `grade=="X"` |
|---|---:|---:|
| all 76,019 | 40,391 | 34,549 = **85.5%** |
| sgrade S | 5,230 | 4,562 = **87.2%** |
| (for contrast, `aligned=="against"`) | 35,628 / 4,693 | 98.4% / 98.7% — i.e. the veto, tautologically |

Apply the 87.2% base to the 4,693 vetoed S rows: **~599 (6.0% of S)** would clear `_grade_pa`
if the veto were deleted, not 46.7%. The instrumented replay already in the tree agrees and
is tighter: `research/p16_htf_bias.md` §4 — of 3,525 veto-killed S signals, **60 (1.7%)**
reach a tradeable tier with the veto off, 84 more become alerts, **263 die elsewhere anyway**.

The two filters are ~87% **co-extensive**, not additive. Reversing the two branches in
`why()` would move the veto's share from 46.7% to roughly 6% and `_grade_pa`'s to ~86%.
"92.7%" is the correct *survivor* arithmetic (9,923 − 729 non-D survivors = 9,194) but the
**split between the two, and the framing of them as two independent killers, is wrong**.

## 2. "They kill S at the same rate they kill everything" is a tautology

`research/downgrade.py:532-535` defines `observations` as, in its own words, *"the three
branches of the old `_grade_pa`, demoted from veto to evidence"*: `entry_bar_off_level`,
`entry_bar_counter_coloured`, `htf_opposed`. `net = len(tripped) − confluence`
(`downgrade.py:527`) **excludes all three**. `sgrade` is constructed to be independent of
precisely the two gates the funnel measures against it. Equal kill rates is the **designed
null**, not a finding, and cannot be evidence that the gates "are not selecting."

## 3. "Not Austin's rules" is half false

- HTF veto: supported. `p16_htf_bias.md` §3 has Austin CONTRADICTING any author
  ("we dont have any higher timeframe bias yet"). Fair.
- `_grade_pa`: **not supported.** Its two D branches are candle colour and *never touched the
  level*. `level_not_respected` is one of Austin's own eight `CHECKS`
  (`downgrade.py:67`, `:437`) and carries 49,989 rows in this book. `downgrade.py:481-484`
  calls all three demoted branches *"real entry criteria"* — reported rather than deleted,
  which is not the same as unauthored. Lumping `_grade_pa` in with the veto is the claim's
  own conflation.

## 4. "Deleting the population" implies a loss that is not there

Among rows that actually traded, S is the **worst** bucket:

| sgrade | n | win% | mean R | 95% CI |
|---|---:|---:|---:|---|
| S | 298 | 50.0 | **+0.3547** | [+0.158, +0.551] |
| A | 525 | 50.5 | +0.5298 | [+0.358, +0.701] |
| C | 1,614 | 49.4 | +0.5918 | [+0.484, +0.700] |

All three CIs overlap — consistent with the standing "error bar exceeds the arms" result.
There is no measured edge inside S for the gates to be destroying. And S is not even
disfavoured on pass rate: S traded 298/9,923 = 3.003%, non-S 2,139/66,096 = 3.236%.

## 5. Minor undercount

"only 298 (3.0%) are traded" understates what clears the two filters. **729 S rows (7.3%)
survive both to a non-D grade**: 298 traded + 128 killed later by R31's account-wide halt
(which is downstream, applied after the symbol loop in `backtest_2y.py`) + 291 landing at C
(alert / min-stop). 426 (4.3%) reached a tradeable state.

## 6. Attacks that FAILED (the claim survives these)

- **Look-ahead in `sgrade`:** none. Every forward index in the eight `CHECKS` is bounded at
  `i + 1` (`level_not_respected` `bars[max(0,i-12):i+1]`, `counter_trend_not_respected`
  `range(j+1, min(j+3, i+1))`, `break_then_rejection` and `ocr_not_respected` likewise).
  Ex-ante clean.
- **Wrong book:** no. 2,437 is current; 2,595 is the superseded T0 book.
- **Unreachable branch:** no. `HTF_BIAS_VETO` defaults ON (`omen_bot.py:29`) and the veto
  fires on 35,628 of 76,019 rows (46.9%). It is live and it is real.

## 7. Corrected claim

One unauthored filter (`HTF_BIAS_VETO`) and one partly-authored grader (`_grade_pa`, whose
level-touch branch is Austin's own `level_not_respected`) between them reduce his S rows to
7.3% survivors — but they are ~87% co-extensive, so the veto's marginal contribution is
1.7% (P16's replay) to 6% (base-rate estimate), not 46.7%. They kill S at the population
rate because `downgrade.py` deliberately excludes their inputs from `net`, which makes equal
rates the expected null rather than evidence of anything; and traded S rows are the worst of
the three sgrade buckets (+0.3547R vs +0.5918R for C), so no measured edge is being deleted.
