# g155 — refuter #1 (leakage / lookahead lens): `ambiguous-stop-candidates` is REFUTED

**What is different now, in one sentence:** the F5 script reproduces byte-for-byte and
contains **no lookahead**, but its "survivor" verdict rests on a rule that changes the
day's pick on **6 of 498 days** and buys its entire precision gain by swapping one
ungraded +$38 winner for one S-graded **−$1,000 loser** — an outcome a random relabel of
the same flags reproduces **64.8%** of the time.

Fill for every figure below: signal-bar **CLOSE** entry (`meta.entry_fill == "close"`),
`stop_rule.stop_fill_price` stops as booked in `research/bt2y_trades_retest_on.json`,
size-gated on `signal_runner.min_risk_floor` via `omen_metrics._row_is_sizeable`,
1R = $1,000. One-trade-a-day unit = `omen_metrics.first_of_day_arm` semantics as
re-implemented in `pick_first_of_day`. H1/H2 split 2025-09-01.

Scripts: `research/g154_rule_ambiguous-stop-candidates.py` (re-run as committed);
refutation work in scratchpad (`r1_amb_align.py`, `r1_amb_null.py`, `r1_amb_days.py`),
all numbers below reproducible from the book + that script's own `is_ambiguous`.

---

## 1. Reproduction: exact

Re-ran `python research/g154_rule_ambiguous-stop-candidates.py` on base `f8740f80`.
`git status --porcelain` on both output files is **empty** — the regenerated `.md` and
`.json` are byte-identical to commit `c9fb9042`.

| figure | claimed | reproduced |
|---|---:|---:|
| baseline $/day | $33.93 | $33.93 |
| arm $/day | $29.94 | $29.94 |
| H1 delta | −4.36 | −4.36 |
| H2 delta | −3.62 | −3.62 |
| precision | 30.5 → 31.7 | 30.5 → 31.7 |
| recall_100 | 5.9 → 5.9 | 5.9 → 5.9 |

**Reproduction is not the failure point.**

## 2. Lookahead lens: CLEAN

I could not find a read past the entry bar.

| surface | check | result |
|---|---|---|
| `entry_i` → bar index | 1,500-row sample: `bars[entry_i].timestamp` vs `row['et']` | **1,500/1,500 exact** (bar[0] = 09:30, so index i = 09:30+i min) |
| entry price | `bars[entry_i].close` vs `row['entry']` | matches to the book's 2-dp rounding on all 1,500 (the 610 "mismatches" are rounding only, max diff < $0.005; no other bar in the day matches better) |
| `ocr_wick` | `detect_order_block_setup(candles[:i+1])` | `omen_bot.py:418-447` reads only the passed list; `check_retest_type(block, candles[-1], …)` uses the **signal bar** as "now". No future bar reachable. |
| `broken_level` | `row['level_px']` | from the book row, set at signal time |
| `entry_bar` | `bars[i].low` / `.high` | the signal bar's own extreme — fully printed at the CLOSE fill. Not lookahead. |
| `avg_rng` | `bars[i-10:i]` | strictly prior |

Leakage is not the reason to refute this. It is refuted anyway, on what follows.

## 3. The arm barely exists: 6 of 498 days

`drop_ambiguous=True` changes the first-of-day pick on **6 days (1.2%)**. Every headline
number is those six rows.

| day | baseline pick | arm pick |
|---|---|---|
| 2024-09-18 | IWM 09:39 **+$274** (grade none) | AVGO 09:42 **−$1,000** (none) |
| 2024-09-23 | HOOD 09:37 −$9 (ungraded) | PLTR 09:43 −$310 (ungraded) |
| 2025-05-16 | COIN 09:41 **+$368** (ungraded) | NVDA 09:41 −$59 (ungraded) |
| 2025-06-17 | PLTR 09:44 −$1,000 (ungraded) | AMD 09:46 **+$953** (ungraded) |
| 2025-06-26 | NFLX 09:44 **+$38** (ungraded) | COIN 09:49 **−$1,000** (**grade S**) |
| 2026-08-04 | PLTR 09:39 **+$760** (ungraded) | INTC 09:41 −$142 (ungraded) |

Total P&L delta **−$1,990** over two years. Four of six swaps lose money.

**The precision gain is one row.** Baseline 18/59 → arm 19/60: the arm added exactly one
graded day, `COIN_2025-06-26`, which Austin graded **S** — and which **lost the full
−$1,000**. Precision rose 30.5% → 31.7% by buying an S-graded loser and dropping a small
winner. That is the entire case for "survivor".

## 4. Placebo: the survivor gate is satisfied by noise 65% of the time

Shuffled the 642 ambiguous labels at random across the 6,889 size-gated candidates
(exact count preserved), 3,000 draws, re-ran selection and the F5 survivor test:

| | value |
|---|---:|
| P(precision improves) under random relabel | **0.642** |
| P(**survivor gate passes**) under random relabel | **0.648** |
| placebo precision-delta, 5th / 50th / 95th pctile | −2.92 / **+1.07** / +5.08 pp |
| observed precision delta | **+1.16 pp** |
| percentile rank of the observed delta | **0.505** |

The observed effect sits at the **median of the null**. A random rule of the same
intensity does this well or better half the time. Single-arm p ≈ 0.50.

## 5. Multiplicity: FWER ≈ 1

The claim itself states **25 candidates were tried**. With per-arm null pass rate 0.648,
the expected number of pure-noise "survivors" is **25 × 0.648 ≈ 16**, and
P(at least one survivor under a complete null) = 1 − 0.352^25 ≈ **1.000**. No Bonferroni
or Holm correction can rescue an arm whose uncorrected p is 0.50.

## 6. Money is negative in both halves, and the CI straddles zero

Paired-by-day bootstrap (5,000 resamples) of the arm-minus-baseline daily P&L:

| | value |
|---|---:|
| mean $/day delta | **−$4.00** |
| 95% CI | **[−$14.63, +$7.36]** |
| H1 delta | −$4.36 |
| H2 delta | −$3.62 |

Point estimate negative in H1 **and** H2. The rule does not make money; it is only
"not-significantly-losing".

## 7. The predicate points the wrong way against his own grades

A refusal-indicator should flag his **`none`** days more than his **S** days. It does the
opposite:

| grade | n | ambiguous | pct |
|---|---:|---:|---:|
| A | 205 | 25 | **12.2%** |
| S | 295 | 31 | **10.5%** |
| none | 405 | 38 | 9.4% |
| C | 54 | 2 | 3.7% |

S vs none two-proportion z = **+0.49 (p = 0.62)** — indistinguishable, and what signal
there is runs backwards. Realized R: ambiguous −0.057 vs clean −0.023, a 0.034R gap
against this book's ±1.58R error bar.

The corpus was already **SILENT** on this rule
(`research/g153_corpus_confirm_ambiguous-stop-candidates.md`), so the predicate is a
construction, not a mined regularity — and the construction does not separate his grades.

## 8. Verdict

**REFUTED.** Lookahead: none found. Reproduction: exact. But the survivor label is a
median draw from a 65%-pass null gate, applied to a 6-day arm, carried by one S-graded
−$1,000 loss, over a 25-arm family with FWER ≈ 1, while $/day falls in both halves.
Do not carry `ambiguous-stop-candidates` into the F7 S-classifier.
