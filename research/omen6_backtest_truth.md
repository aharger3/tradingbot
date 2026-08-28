# OMEN 6 — the backtest, true

**The book is +0.9551 R against a 2.0 R money gate. It FAILS, by 1.0449 R, and that number is a
ceiling rather than a midpoint. Durability FAILS too: 23 of 25 months green, and the gate is
every month. On 100 held-out cards the engine fires on 3 of Austin's 15 S days and on 12 of the
42 days he refused — it is more likely to fire on a day he said no to than on a day he said S.**

This document **supersedes `backtest_report.md` as the quotable number.** That file publishes
dollars and no R, off a rig that is not cache-first: its last re-run lost **458 of ~6,249
day-fetches** to HTTP 429 under concurrent load, and two re-runs inside one session produced
**574** and **824** traded signals from the same code (`research/a2_figure_refresh.md`,
`d4cf3710`). It is not reproducible on demand. Everything below comes from the 2-year archive
replay, which is 100% cache-first with zero fetch errors.

**Every figure below names the script and the commit that produced it.** This file runs no rig
of its own and re-measures nothing; it is the synthesis of fourteen reports written 2026-08-27.
Where a number is not published by any committed script, this file says so instead of computing
one.

Repo HEAD at writing: `ed09f53c`.

---

## 1. The number

The gate, from `CLAUDE.md`: **mean R = 2.0**, win rate a secondary read, **durability = every
month green**. 1R = $1,000 and the instrument is options.

### Whole book

2024-08-21 → 2026-08-21, 500 sessions, 28 symbols, `data_archive/` replay.

| metric | value | verdict | script + commit |
|---|---:|---|---|
| signals | 45,193 | — | `research/g13_floor_fix_ab.py` `off` arm, `6d89513d` |
| **n traded** | **1,017** | — | same |
| **mean R, as booked** | **+0.9551** | **FAIL** — 1.0449 R short of 2.0 | same |
| **mean R, takeable only** (n=995) | **+0.9716** | **FAIL** — 1.0284 R short | `research/r3_downgrade_grader_ab.py`, `ed09f53c` |
| median R | +0.5660 | — | `research/g13_floor_fix_ab.py`, `6d89513d` |
| win rate (of decided) | 53.2% | FAIL vs `t60_baseline`'s secondary 55% leg | same |
| **months green** | **23 / 25** | **FAIL** — the gate is 25/25 | same |
| worst month | 2025-06, −5.6 R | — | `research/r9_simple_book.py`, `e4de7858` |
| total R | +971.4 | — | `research/g13_floor_fix_ab.py`, `6d89513d` |
| quarters green | 9 / 9 | — | `research/a2_bt2y_summary.py`, `d4cf3710` |
| annualised $ | +$589,848 | PASS vs `t60_baseline`'s $100k leg | same |

**Both gates fail. Two of three of `t60_baseline`'s legs fail.** The dollar leg passes and should
not be read as an independent result: it is `mean_r × $1000 × n × 252 / trading_days`, so it is
mean R multiplied by trade frequency. A book half the required edge clears $100k by trading a
lot.

**And +0.9551 R is a ceiling, not a midpoint.** Every back-dated fill assumes the entry trigger
beat the stop inside a minute nobody can see; the ambiguity is one-directional, so resolving it
can only move the number down (`research/p26_intrabar_ambiguity.py`, `8bb78c77`). See §4.

**Two canonical books exist and they are not the same file.** The committed corpus
`research/bt2y_trades.json` (2026-08-26) reads **1,016 traded / +0.9571 R**; the replay at HEAD
reads **1,017 / +0.9551 R**. One trade and 0.0020 R apart — the same drift `research/a2_figure_refresh.md`
found against the vault's "that has not moved today" caption a few hours after it was written.
Quote the HEAD replay; know the other exists.

### Per pool

`universe.pool_for`. `index` = QQQ/SPY/IWM, `equity` = `MAJOR_15`, `other` = the rest of the
28-symbol replay. **Rows under `universe.MIN_SAMPLE_N` (=20) are marked thin — marked, not
dropped, and still inside the whole-book totals above.** Shipped-ladder columns from
`research/r9_simple_book.py`, `e4de7858`.

| pool | n | mean R (shipped ladder) | vs 2.0 gate | win rate | months green |
|---|---:|---:|---|---|---|
| `index` _(thin, n<20)_ | 18 | +0.7393 | FAIL | not published | not published |
| `equity` | 624 | +0.9000 | **FAIL** | not published | not published |
| `other` | 375 | +1.0572 | **FAIL** | not published | not published |

**No pool passes.** The best of the three, `other`, is still 0.94 R short.

**Per-pool win rate and months-green for the shipped ladder are published by no committed
script.** `research/r9_simple_book.py`'s per-pool table carries those two columns for the
`flat_2r` exit arm, not the incumbent ladder (`r9_simple_book.py:565-576` — `months(rs,
"flat2r_r")`, `f["wr"]` off the flat book). Rather than quote a number from the wrong arm, this
file leaves the cells empty. It is a real gap, listed in §6.

### Per grade (Austin's ladder, attached after the fact by `backtest_2y.py`)

`research/r9_simple_book.py`, `e4de7858`. All three clear `MIN_SAMPLE_N`.

| grade | n | mean R | vs 2.0 gate |
|---|---:|---:|---|
| S | 128 | +1.2829 | **FAIL** — 0.7171 R short |
| A | 251 | +0.9956 | FAIL |
| C | 638 | +0.8735 | FAIL |

**The S subset is the best population in the book and it still fails by 0.72 R.** The whole
S-over-C span is **+0.4035 R** (`research/p26_intrabar_ambiguity.py`, `8bb78c77`) — which clears
the carried error bar by 42×, see §4. (Until 2026-08-28 this line said the span was smaller than
the bar it was measured inside; that was true only of the retired wide bar.) The S subset's durability is
also 23/25 (`research/g13_floor_fix_ab.py`, `6d89513d`).

---

## 2. Recall, held out

`research/marks/probe_omen_test1_2026-08-27.jsonl` — **100 symbol-days Austin graded
2026-08-27**, 15 S / 27 A / 16 C / 42 X. No rule was fitted on them and no threshold tuned to
them. **This is the project's only clean held-out recall sample.** Scored by
`research/t70_test1_score.py`, `30fbc3f8`.

Three symbols are held out separately because the engine is configured never to trade them —
SPY by decision (`INCLUDE_SPY_IN_BACKTEST = False`), IWM and ACHR in no backtest tier. That
leaves **84 in-universe cards**: 12 S, 21 A, 14 C, 37 X.

| metric | all 100 | in-universe 84 |
|---|---:|---:|
| **S recall** — fires at all on an S day | **3/15 = 20%** | **2/12 = 17%** |
| **false fire** on refused (X) days | **12/42 = 29%** | **11/37 = 30%** |
| **entry match ±2 bars** (of the 58 graded S/A/C) | **4/58 = 7%** | 3/47 = 6% |
| tradeable-day recall (S/A/C) | 15/58 = 26% | 14/47 = 30% |
| day precision | 15/27 = 56% | 14/25 = 56% |
| grade agreement (the diagonal) | 5/58 = 9% | — |

**The signal is inverted on unseen days: 29% of his X days against 20% of his S days.** And the
day-level 26% overstates the agreement — the bar-level number is **7%**. Of the 12 S days the
engine is silent on, 4 produce no signal of any grade at all; on the other 8 it saw something
and threw it away. `t4_engine_recall`'s in-sample verdict survives the holdout: **this is a
detection problem, not a filter problem.** No gate on the trades it already takes recovers
setups it never sees.

### Every in-sample recall figure measured today failed to reproduce held out

This is the general finding, and it is what makes the 3/15 above the honest number rather than
one reading among several. The 120 graded day-cards are the corpus the rules were built from.
Two flags were implemented and A/B'd today; both bought in-sample S recall, both bought exactly
**zero** held-out S recall, and both bought false fires.

| arm | in-sample `regression_gate` `s_grade` | held-out S recall | held-out false fires | script + commit |
|---|---|---|---|---|
| `ENABLE_STRUCTURAL_RISK_FLOOR` | 5 → **11** (+6) | 3/15 → **3/15** (+0) | 12/42 → **19/42** (+7) | `research/g13_floor_fix_ab.py`, `6d89513d` |
| `ENABLE_DOWNGRADE_GRADER` | 5 → **6** (+1) | 3/15 → **3/15** (+0) | 12/42 → **14/42** (+2) | `research/r3_downgrade_grader_ab.py`, `ed09f53c` |

Same shape a third time on the grader's calibration: `research/p2_threshold_sweep.py` (`99bead1c`)
measures the committed grader's S/A/C mix at distance **0.086** from Austin on the 120 cards it
was effectively tuned against and **0.282** on the held-out 100 — **a card it has never seen
disagrees with him roughly 3× more than a card it has.** S-day recall over the same two rigs:
12/28 = 43% in sample, 5/15 = 33% held out.

Not one of the 12 held-out days the structural-risk floor newly lit up was a day he graded S:
3 A, 2 C, 7 X, and one A day lost its fire.

**Read every in-sample recall number in this repo as an upper bound until it has been shown on
the 100.** The held-out sample is itself only 100 cards and 15 S days — a 3/15 → 3/15 read rules
out a LARGE out-of-sample gain, not a small one — but the direction of the failure has now
repeated three times.

---

## 3. The fill

### What the rig actually does

`signal_runner.fill_price` returns the broken **level**, clamped into the entry bar's range,
instead of the bar's close, whenever the close is judged a bad fill. This is Austin's own rule,
quoted in the function's docstring: *"those candles that move fast and close at high of day or
low of day, i just want to try to not miss out."* Two predicates can trigger it, and only one is
a flag.

| predicate | measures | gated by `ON_WATCH`? | reachable from |
|---|---|---|---|
| `bar_extreme_veto` | close sits in the top/bottom `BAR_EXTREME_FRAC` (0.25) of the SIGNAL BAR's own range | **no — always live** | all 10 `fill_price` call sites |
| `near_session_extreme` | close sits within `BAR_EXTREME_FRAC` of the SESSION range from the day's high (long) / low (short) | **yes — this is the whole flag** | **2 of 10**: B&R long `signal_runner.py:1638`, B&R short `:1878` |

### What `ON_WATCH` really controls

`research/g3_onwatch_2y.py`, `47e60796`, both arms replayed at commit against the same archive:

| arm | signals | traded | mean R | months green | intrabar fills | of traded |
|---|---:|---:|---:|---:|---:|---:|
| `ON_WATCH=0` | 45,193 | 1,091 | +0.8416 | 24 / 25 | 815 | **74.7%** |
| `ON_WATCH=1` (shipped) | 45,193 | 1,017 | +0.9551 | 23 / 25 | 913 | 89.8% |

- **It moves 0 of 45,193 signals.** It is a price rule, not a detector. This is why
  `research/t61_onwatch_ab.py` measured +0 on every recall metric over the 120 day-cards and was
  right to.
- **`ON_WATCH=0` still leaves 74.7% of traded fills intrabar.** The flag's own reach is 175 rows
  on the off arm / 90 on the on arm — the signals where `near_session_extreme` is the only
  predicate that could have moved the price.
- **No close-fill arm is expressible.** Turning the flag off is *less* intrabar fill, never
  *no* intrabar fill. A genuine close-fill arm needs `fill_price` itself changed, which no
  ticket today does.
- **T3's delta: +0.1135 R on the whole book, +0.2023 R on S** — and it costs a green month
  (24/25 → 23/25) and 74 trades. Neither arm passes either gate. See §4 for whether the delta
  is readable.

### The mechanism that ties the day together

**The intrabar fill back-dates the entry to the level, which collapses `|entry − stop|`.** For
break-and-retest the structural stop *is* the broken level, so a fill at the level is a fill at
the stop. One mechanism, two symptoms, measured by two different rigs today.

**Symptom 1 — it suppresses trades.** `research/g12_recall_regression.md`, `df8e1c89`: the
collapsed `stock_risk` falls under the pre-existing minimum-risk floor at `signal_runner.py:1657`
(long) / `:1892` (short), `max(0.10, 0.0015 × close)`, which forces `TradeGrade.D` — an alias of
`X` — so the signal is skipped and never becomes an entry. Six of Austin's marked S entries went
silent this way; all six are `risk_after < floor ≤ risk_before`, same bar, same level, same
grader. The commit's own guard, `intrabar_stop`, fires only on full collapse (`entry <= stop`),
so the four *squeeze* cases — where the clamp lands the fill exactly on the bar's own extreme
without reaching the stop — are invisible to it. Its docstring measures the population-wide cost
at **30% of B&R signals**.

**Symptom 2 — it inflates the survivors.** `research/r9_simple_book.py`, `e4de7858`: R is
denominated in `|entry − stop|`, and on the 39 surviving moved pairs arm B's risk unit is a
**median 63% of arm A's** (mean 69%, smaller in 33 of 39). So the same trade's "2R" sits about
**37% nearer in price**. Held to a fixed denominator of the 175 candidates the extra fill class
can reach, P(2R) goes **36.00% → 14.29%** — the earlier fill more than halves it. The 62.50%
you get by scoring only the 40 survivors is survivorship: **135 of 175 (77%) never reach the
traded book at all**, and under the close fill those 135 book a mean −0.0058 R, roughly flat. The
fill does not cut a tail off the book; it converts 77% of a break-even population into
no-trades.

**Suppression and inflation are the same arithmetic seen from two sides.** Trades whose risk
collapses far enough leave the book (G12); trades whose risk collapses less stay in it with a
smaller denominator and look better than they are (T10). Any read of this book's mean R that
does not hold that in mind is reading a survivor's average against a shrunk unit.

And the fill is where the ambiguity lives: **86.8% of traded intrabar fills sit on a bar whose
range also contains the trade's stop**, and **790 of those 792 rows are the stop sitting on the
entry bar's own extreme**, put there by `intrabar_stop` (`research/p26_intrabar_ambiguity.py`,
`8bb78c77`). The engine assumes fill-then-stop every single time.

---

## 4. Error bars — the narrow one, since 2026-08-28

`research/p26_intrabar_ambiguity.py` (`8bb78c77`) and `research/g3_onwatch_2y.py` (`47e60796`)
built two bars. Both are **one-directional** — repricing can only make R worse, so the booked
mean is a ceiling. Which of the two the repo carried was never a measurement question; it was a
rules question, and **Austin answered it on 2026-08-28**:

> Q: *"Entry is mid-candle at the level. That SAME candle then closes beyond your stop. Are you
> out on that close, or does the stop only go live from the next candle?"*
> A: **"Out on that same close."**

A stop is triggered by a candle CLOSE and by nothing else, and the entry candle's own close
counts. **There is exactly one close per bar, so a stop cannot fire inside the entry bar ahead of
the back-dated fill.** The 790-of-792 `intrabar_stop` class is not ambiguous — it is decided.

| bar | which ambiguous rows get repriced to −1.0R | whole book, shipped arm | status |
|---|---|---:|---|
| **narrow — CARRIED** | only rows whose stop is NOT the entry bar's own extreme | **±0.0095 R** | **the bar every number in this repo carries** |
| wide — RETIRED 2026-08-28 | all of them, the `intrabar_stop` class included | ±1.5799 R | history; do not quote as a live interval |

**Why the wide bar was carried, and what retired it.** It was carried in good faith: while the
ordering question was open, excluding the `intrabar_stop` class would have been assuming Austin's
answer, so the honest move was to price both and quote the pessimistic one. His sentence — not a
new rig, not new data — retired it. The residual genuine ambiguity is the **2 rows of 913** the
narrow bar prices, 0.2% of intrabar fills. The ON-WATCH-off arm's pair is the same story:
±0.0088 R carried, ±1.3388 R retired.

### Every A/B measured 2026-08-27 CLEARS the carried bar

| A/B | delta | vs ±0.0095 R, carried | vs ±1.5799 R, retired | script + commit |
|---|---:|---|---|---|
| `ON_WATCH` on − off, whole book | **+0.1135 R** | **CLEARS — 12×** | *(was: inside, 14× smaller)* | `research/g3_onwatch_2y.py`, `47e60796` |
| `ENABLE_STRUCTURAL_RISK_FLOOR`, 429 matched trades | **+0.1898 R** | **CLEARS — 20×** | *(was: inside, 8× smaller)* | `research/g13_floor_fix_ab.py`, `6d89513d` |
| `ENABLE_DOWNGRADE_GRADER`, takeable-only | **−0.1289 R** | **CLEARS — 14×** | *(was: inside, 12× smaller)* | `research/r3_downgrade_grader_ab.py`, `ed09f53c` |
| the whole S-over-C span | **+0.4035 R** | **CLEARS — 42×** | *(was: inside, 3.9× smaller)* | `research/p26_intrabar_ambiguity.py`, `8bb78c77` |

**That is the section's real point, and it is a statement about the method, not about the three
flags.** This section used to say the opposite: that every effect measured on 2026-08-27 was
8–14× smaller than the doubt the fill assumption carried, and that a mean-R ranking under about
one full R could not be read here in either direction. **That is no longer true and must not be
repeated.** The three flag deltas and the S-over-C span all clear the carried bar by 12× to 42×.
The signs are readable.

What the correction does **not** buy:

- **It does not make any of these deltas large.** +0.1135 R and +0.1898 R are still small next to
  the 1.0449 R the book is short of the money gate. Clearing an error bar makes a sign readable;
  it does not make an effect worth shipping.
- **It does not make them out-of-sample.** Every one is in-sample over the same 500 sessions, and
  §2's held-out numbers govern (`CLAUDE.md`: held-out beats in-sample, always). Each of these
  three arms bought **zero** held-out S recall regardless of what its mean R did.
- **It does not touch the gate.** The ambiguity was always one-directional and the book always
  failed at 2.0 R optimistically, pessimistically, and everywhere between.

The tick-data purchase this section used to list as the other way out
(`research/p25_midcandle_entry.md`, `9d0c2206`) is **no longer needed for this question**. The
free lever was pulled.

---

## 5. Flags

**Every flag in this table is at its committed default. Nothing was flipped, and no engine
default moved in any ticket reported here.** Flipping one changes what trades, which is Austin's
call, and re-freezing the engine **VOIDS** the forward book (`research/omen6_forward.py`).

### Added by this effort — both OFF

| flag | site | default | measured delta of flipping it | script + commit |
|---|---|---|---|---|
| `ENABLE_STRUCTURAL_RISK_FLOOR` | `signal_runner.py:391` | **OFF** (`"0"`) | in-sample `s_grade` **5 → 11**; held-out S recall **3/15 → 3/15**, false fires **12/42 → 19/42**. As-booked mean R +0.9551 → **+14.72** is arithmetic, not money: **73.3% of the resulting book (1,139 of 1,553) is untakeable**, 79 rows with `entry == stop` exactly. The defensible delta is the 429 matched trades: **+0.1898 R**, which clears the carried narrow bar by 20× (the wide bar it was once judged inside was retired 2026-08-28 — §4) | `research/g13_floor_fix_ab.py`, `6d89513d` |
| `ENABLE_DOWNGRADE_GRADER` | `signal_runner.py:415` | **OFF** (`"0"`) | held-out S recall **3/15 → 3/15**, false fires **12/42 → 14/42**, grade agreement 5/58 → 6/58. Book 1,017 → 1,310 traded; takeable-only mean R +0.9716 → +0.8427 = **−0.1289 R**, which clears the carried narrow bar by 14× (wide bar retired 2026-08-28 — §4). 22 of 27 symbols move down | `research/r3_downgrade_grader_ab.py`, `ed09f53c` |

Both were verified byte-identical to unmodified HEAD with the flag off — same 45,193 signals,
same 1,017 traded, same sha256 over the `trades` array. The flag-off engine is the flag-less
engine.

### Pre-existing `ENABLE_*` in `research/downgrade.py` — all `False`

| flag | site | default | measured delta | script |
|---|---|---|---|---|
| `ENABLE_SEQUENCE_GATE` | `downgrade.py:112` | `False` | all-signal reading trips 73.9% of the book; tripped **+0.767 R** (n=422) vs clean **+1.092 R** (n=594) = **−0.325 R**, right-signed. Card gate: S recall 12/28 → 8/28, false fire 30/61 → 9/61. P23 measured it best-of-five on both rigs (S mean R **+1.572 R**, n=77) | `research/p20_sequence_gate.py`, `research/p23_combined_arms.py` |
| `ENABLE_LARGE_COUNTER_BODY` | `downgrade.py:83` | `False` | trips **57.2%** of the book; tripped +0.968 R (n=622) vs clean +0.939 R (n=394) = **+0.029 R** — near zero and **wrong-signed for a downgrade** | `research/p18_p19_new_variables.py` |
| `ENABLE_MULTI_LEVEL_CONFLUENCE` | `downgrade.py:91` | `False` | trips 23.9% of covered; tripped +1.064 R (n=582) vs clean +0.814 R (n=434) = **+0.250 R**, right-signed — but **zero marginal effect on the card gate** (S recall 12/28, false fire 30/61, agreement 20/58 all unchanged) | `research/p18_p19_new_variables.py` |

### Pre-existing env flags — all ON

| flag | site | default | measured delta of flipping it | script + commit |
|---|---|---|---|---|
| `ON_WATCH` | `signal_runner.py:369` | **ON** (`"1"`) | 0 of 45,193 signals move; traded 1,091 → 1,017; mean R +0.8416 → +0.9551 = **+0.1135 R**, and a green month lost. Controls 1 of 2 predicates at 2 of 10 `fill_price` call sites | `research/g3_onwatch_2y.py`, `47e60796` |
| `HTF_BIAS_VETO` | `omen_bot.py:29` | **ON** (`"1"`) — see §6, two committed artefacts say OFF | of the 3,525 dropped S signals the veto is blamed for, lifting it frees only **60 (1.7%)**, at +1.012 R (n=60, thin) | `research/p16_htf_bias.md` |
| `RULE84_STRICT` | `signal_runner.py:215` | **ON** (`"1"`) | loose arm fires **116** re-entries vs 3; that arm's own re-entry book is **+0.792 R** (n=79) and the whole book goes +0.957 → +0.942. Of the 318 armings that die past ARMED, **92 (28.9%) die on `rr15` alone**, worth **+0.617 R** (n=92) if that one gate were lifted | `research/g10_arming_funnel.py`, `66557d12` |

**No flag in this table is what stands between this book and the money gate.** Every arm above,
on or off, lands between +0.83 R and +0.99 R on a gate of 2.0.

---

## 6. Still wrong, named

**1. The recall regression gate is RED at HEAD and is staying red by decision.**
`python research/regression_gate.py` drops **6 `s_grade` marks** — `GOOGL|2024-10-15|32`,
`IWM|2025-04-10|16`, `IWM|2025-12-01|11`, `IWM|2025-12-04|56`, `QQQ|2025-02-25|16`,
`UBER|2025-09-11|15`. Culprit bisected to **`5e3677ea`** (2026-08-11); red for 16 days and 112
commits before anyone ran the gate. It is wired into no CI and no `verify:` line. The fix is not
being applied because the only version that recovers marks
(`ENABLE_STRUCTURAL_RISK_FLOOR`) makes 73% of the book untakeable, and shipping any of it
requires re-freezing the engine, which **VOIDS the forward book**. That is Austin's call.
`research/g12_recall_regression.md` `df8e1c89`, `research/g13_floor_fix_ab.md` `6d89513d`,
confirmed still 6-and-only-6 at HEAD by `research/r3_downgrade_grader_ab.py` `ed09f53c`.

**2. 98 grandfathered reports state numbers with no provenance.** `python
research/test_provenance.py` prints `provenance ok (98 reports grandfathered)` — it is green
because 98 filenames are in `KNOWN_UNPROVENANCED`, not because those files name their script and
commit. Among them are documents this project quotes constantly: `t60_baseline.md`,
`p7_84_rule.md`, `p2_threshold_sweep.md`, `t66_downgrade_measure.md`, `g7_exit_sweep.md`,
`p20_sequence_gate.md`, `p23_combined_arms.md`, `hallucination-audit.md`. The list is supposed to
shrink and has not.

**3. 33 constants nobody ever stated.** `research/hallucination-audit.md` (`86d96f99`) checked 50
hardcoded constants in `signal_runner.py` against the trader corpus: **15 CONFIRMED, 2
CONTRADICTED, 33 UNMENTIONED.** Two of the unmentioned are load-bearing for everything in §3:
`B&R_MIN_RISK = 0.0015 × close` (the floor that suppressed the six S marks) and
`STOP_RANGE_MULT = 0.75` (the second gate that killed the seventh). Both are flagged HIGH and
both are ours, not his. The 2 CONTRADICTED are worse than unmentioned: `BNR_STOP_MODE` is coded
at-level where the source teaches a 10-15 cent buffer, and the blind 2R target is coded as an
exit mechanism where the source calls 2:1 a minimum aggregate expectation.

**4. `+0.0787R` and `+0.957R` were never the same measurement, and have been quoted side by
side.** `research/a2_figure_refresh.md` (`d4cf3710`) row 9: `t60_baseline.md`'s published
+0.0787 R is **Corpus B** — the 12-month, live-fetching, 429-degraded `backtest_charts.json`
rig — and +0.9551 R is the 2-year cache-first archive replay. Different corpora, different
windows, different fetch reliability. Re-running Corpus B today gives **+0.1574 R**, not +0.0787
and not +0.955. The published win rates are not comparable either: 30.1% divides by every row
including scratches, 53.2% divides by decided trades; on the same convention the gap is **+1.0
point**, not +23. `t60_baseline.md` calls itself "the baseline every later number is measured
against" and is the most out-of-date number wearing that title.

**5. `HTF_BIAS_VETO`'s documented default is the opposite of its shipped default.**
`omen_bot.py:29` is `os.getenv("HTF_BIAS_VETO", "1")` — **ON**, and the module comment above it
says "DEFAULT ON, deliberately". But `research/p16_htf_bias.md` §5 says "a new `HTF_BIAS_VETO`
env flag, **default OFF**" and reasons at length about what shipping it OFF does to the live
scanner; `omen_bot.py:193`'s own docstring says "(default 0)"; `spec0b_levels_check.py:74` prints
"HTF_BIAS_VETO=0 default"; `TASKS.md` records it as "defaulted it OFF". Four committed artefacts
describe a default the code does not have, on a flag read by all ten detection sites including
the live ones. Whichever way it was meant to land, the record and the code disagree.

**6. `paper_trader.py` stops on wicks.** `PaperPosition._check_stop` tests `low <= stock_stop` /
`high >= stock_stop` and has never received a `close`. The settled rule — *stops trigger on the
candle CLOSE; wicks stop nothing out*, which Austin settled five times in one batch of marks and
which `backtest_week.py`'s `STOP_ON_CLOSE` already implements correctly one file over — is
violated on **every position, every day paper trading has run**, always in the direction of
cutting trades early. `_check_breakeven` has the identical bug, dormant only because
`RULE6_ENABLED = False`. Fix is one file, one call site, one test rewrite. Blocked on nothing.
`research/g11_live_scratch_scope.md`, `00d64ad5`.

**7. Two committed rigs print different win rates for the identical 1,017-row book.**
`research/a2_bt2y_summary.py::book` counts wins off the stored `out` label and prints **53.2%**;
`research/r9_simple_book.py::agg_r` counts wins off the sign of R (`x > 0`, decided = `x != 0`)
and prints **53.4%** — both docstrings claim to follow the same convention. ~2 trades, and it
means "win rate" is not one quantity in this repo.

**8. `research/bt2y_trades.json` is not tracked by git.** The canonical 2-year book behind a
large share of the mean-R figures in this project exists only as a 37 MB local file. It is
deliberate (regenerable, and the finding lives in the tracked report) and it is still a
single-machine dependency for reproducing anything.

**9. Per-pool win rate and months-green for the shipped ladder are published nowhere.** §1's
table has two empty columns for this reason. The only committed per-pool rig carries those
columns for the `flat_2r` exit arm.

**10. `before11` in the 84%-rule block is unreachable.** It kills 0 of 318 dead armings and
structurally cannot kill any: `backtest_week.py`'s per-bar loop already skips bars at/after
`ENTRY_CUTOFF`, and `detect_signals()` repeats the check, before the rule's own `bar_time <
SESSION_END` runs. A real rule that has become a branch that can never be false — the same class
as the 84% re-entry rule firing 3 times in two years. `research/g10_arming_funnel.py`,
`66557d12`.

**11. `level_not_respected` is wrong-signed at a 63-68% trip rate.** Its tripped population earns
**+0.996 R** (n=638) against its clean population's **+0.892 R** (n=378) — a downgrade that marks
better trades worse, firing on nearly two thirds of the book. P15 tried three reformulations and
all three failed differently; the standing recommendation is STOP, not a fourth attempt.
`research/p2_threshold_sweep.py`, `99bead1c`.

**12. OMEN Test 1's entry prices are the bar close by construction.**
`research/build_omen_test1.py:696` wrote `out.entry_p = closes[i]` unconditionally, so **every S,
A and C entry in that corpus reads 100% at-close** and the mid-candle question cannot be answered
from it. His prose says otherwise 14 times in 58 graded rows — a **24% floor**, not a rate. Also
6 of the 57 stops he typed are not prices (`931`, `121052`, `957`, `930`, `20`) and are refused
rather than repaired, leaving 51 usable. The instrument is fixed for future decks (`cef00981`);
Test 1's corpus is not. `research/p25_midcandle_entry.py`, `9d0c2206`.

**13. There is a third grade ladder and a second, hardcoded HTF veto, and neither is measured.**
`signal_runner.compute_austin_tier` computes its own S/A/C/X tier — a third ladder alongside
Austin's S/A/C and the legacy A+/A/B/C/X — and its clause 4 votes on `htf_bias` through
`HTF_OPPOSITION_VETO = "hard"` at `signal_runner.py:363`, a **hardcoded constant with no env
flag**, unlike `HTF_BIAS_VETO` one file over. Its own comment calls it *"the one clause Austin
has not settled"* and says *"T8 A/Bs it"* — `research/t8_verdict_measure.md` does not exist. The
field is reported-only today and gates no trade, which is why it has stayed invisible; mixing
ladders is exactly what killed the 84% rule once already.
`research/p16_htf_bias.md`, `fdc8e090`.

---

## 7. What to do next

**The strongest lead on the board is not a grader. It is arrival order.**

`research/g4_dropped_s.md` §6 measured it: **968 of the 1,016 traded signals — 95.3% — carry the
`[floor B: first with-trend signal of the day]` tag.** Only 48 earn `B` or better from their own
price action. On the S book it is 120 of 128. The branch is one `elif` in
`SignalRunner._calibration_grade`:

```
elif (with_trend and self._dir_fired[d] == 0 and 0 <= mins <= 90
      and sig["grade"] == "C" and "capped C" not in sig["reason"]):
    sig["grade"] = TradeGrade.B.value      # first with-trend signal of the day
```

So the A+/A/B/C ladder is very nearly decorative. **The engine's actual entry rule is "the first
with-trend signal of the day, in the first 90 minutes, that reached C."** `C` is the real
candidate pool and `X` is the real rejection.

**Why this outranks another grader attempt**, in order of weight:

1. **T6 says so about its own result.** `research/r3_downgrade_grader_ab.md` (`ed09f53c`) swapped
   the grader wholesale — every one of ten detection sites — and its own §6 concludes: *"A
   different grader changes which signal is first; it does not change that first is what gets
   taken."* It bought 0 held-out S recall and 2 more false fires for a takeable-only −0.1289 R.
2. **The grader has now been attacked from both ends and neither end moved.** A1 measured the
   eight variables as committed and found 1 wrong-signed, 6 right-signed, 1 unreachable — with
   the grader's own mix 3× further from Austin on held-out cards than on the cards it was tuned
   against. R3 replaced the grader entirely. Both moved mean R by a readable but tiny amount
   (R3: −0.1289 R, 14× the carried bar since 2026-08-28 — see §4) and **both bought zero held-out
   S recall**, which is the read that governs.
3. **T1 says the problem is upstream of any grade.** 4 of the 12 silent S days produce no signal
   of any grade at all, and the bar-level entry match is 7%. A grader ranks what detection
   hands it; it cannot conjure a setup the detector never saw.
4. **`_calibration_grade`'s floor has never been A/B'd.** Every parameter in it is untested: the
   90-minute window, the `with_trend` condition, the once-per-direction `_dir_fired` counter,
   and the requirement that the signal already reached `C`. That is the branch promoting 95.3%
   of the book. `research/hallucination-audit.md` lists the same rule as unsourced — *"Proxy rule
   from 133 labeled trades; not course-taught."*
5. **It is the lever whose effect is largest, not merely readable.** This item used to rest on
   §4's claim that everything measured was 8-14× smaller than the error bar; since 2026-08-28
   those deltas are readable (12-20× the carried bar) and the argument no longer needs that
   crutch. It stands on its own: changing which signal is *first* replaces trades rather than
   adding them at the margin — G4 §6 says so explicitly — so it moves the whole book, while the
   three flags measured so far move it by roughly a tenth of an R and buy no held-out recall.

**One other thing is blocked on nothing and costs no compute:**

- ~~**Ask Austin one question:** *when your fill is back-dated to the level and the stop goes on
  the entry bar's own wick, could that wick have printed before you were filled?*~~ **Done
  2026-08-28. His answer: "Out on that same close" — a stop needs a close and the entry bar has
  exactly one, so that wick could not have taken him out first.** The bar this repo carries
  collapsed from ±1.5799 R to ±0.0095 R, and every sub-1R ranking in it is readable for the first
  time. The wide bar is retired; §4 carries the corrected verdicts.
- **Fix the `paper_trader.py` wick bug** (§6 item 6). One file, one call site, one test rewrite,
  a working reference implementation already in the repo, and it has been mismarking every live
  paper position every day.

---

## What this document does not say

- **It does not say the book is worthless.** It says the book is +0.9551 R against a 2.0 R gate
  and 23/25 months green against a 25/25 gate, and that both figures are ceilings.
- **It no longer says the three deltas in §4 are unreadable.** Until 2026-08-28 it said each was
  smaller than the error bar on the quantity it is a delta of. Austin's answer that day retired
  the wide bar, and all three clear the carried narrow bar by 12-20×. Their signs are readable;
  what they are not is *large*, and none of them bought a single held-out S day.
- **It changes no code, flips no default, and re-runs nothing** that the fourteen source reports
  already measured. Where those reports disagree with each other (§6 items 7 and the two
  canonical books in §1), both numbers are shown rather than one picked.
- **It does not re-open the stop rule.** Stops trigger on the candle CLOSE, fill at that close,
  floored at −1.25 R; wicks stop nothing out.
- **`research/regression_gate.py` is RED at HEAD and this document does not fix it.**
- Every held-out figure rests on 100 cards and 15 S days. What that sample rules out is a large
  out-of-sample recall gain, not a small one.
- Nothing here is a walk-forward. Every 2-year number is in-sample over the same 500 sessions.

---

## Provenance

Produced by hand at `_this commit_` from the reports below, each of which names its own script.
**This document runs no rig and computes no new number.** `python research/test_provenance.py`
passes at HEAD; `python research/regression_gate.py` is RED at HEAD on the six marks named in §6
and is reported, not fixed.

| ticket | report | script | commit |
|---|---|---|---|
| T1 | `research/t70_test1_score.md` | `research/t70_test1_score.py` | `30fbc3f8` |
| T2 / R8 | `research/p26_intrabar_ambiguity.md` | `research/p26_intrabar_ambiguity.py` | `8bb78c77` |
| T3 / G3 | `research/g3_onwatch_2y.md` | `research/g3_onwatch_2y.py` | `47e60796` |
| A1 / T4 | `research/a1_threshold_sweep.md` | `research/p2_threshold_sweep.py` | `99bead1c` |
| A2 | `research/a2_figure_refresh.md` | `research/a2_bt2y_summary.py` | `d4cf3710` |
| A3 / T11 | `research/a3_s_cap_sweep.md` | `research/a3_s_cap_sweep.py` | `615a0ce3` |
| G10 | `research/g10_arming_funnel.md` | `research/g10_arming_funnel.py` | `66557d12` |
| G11 | `research/g11_live_scratch_scope.md` | (scoping, read-only) | `00d64ad5` |
| G12 | `research/g12_recall_regression.md` | `research/g12_attribute.py` | `df8e1c89` |
| G13 | `research/g13_floor_fix_ab.md` | `research/g13_floor_fix_ab.py` | `6d89513d` |
| R9 / T10 | `research/r9_simple_book.md` | `research/r9_simple_book.py` | `e4de7858` |
| R3 / T6 | `research/r3_downgrade_grader_ab.md` | `research/r3_downgrade_grader_ab.py` | `ed09f53c` |
| P25 | `research/p25_midcandle_entry.md` | `research/p25_midcandle_entry.py` | `9d0c2206` |
| G5 | `research/hallucination-audit.md` | `research/corpus_query.py` | `86d96f99` |
| G4 | `research/g4_dropped_s.md` (§6, arrival order) | `research/g4_dropped_s.py` | `d8b04625` |
| P16 | `research/p16_htf_bias.md` | `research/g4_dropped_s.py`, re-run with the veto off | `fdc8e090` |
| P18/P19 | `research/p18_p19_new_variables.md` | `research/p18_p19_new_variables.py` | `db439106` |
| P20 | `research/p20_sequence_gate.md` | `research/p20_sequence_gate.py` | `73d3c903` |
| P23 | `research/p23_combined_arms.md` | `research/p23_combined_arms.py` | `5e28e96e` |

Sample floor: `universe.MIN_SAMPLE_N` = 20, applied and marked in §1, never used to drop a row
from a total. Pools: `universe.pool_for`. Money gate and durability gate: `CLAUDE.md`.
`POLYGON_API_KEY` was never printed while producing this file.
</content>
</invoke>
