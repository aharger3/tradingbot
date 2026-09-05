# g155 refuter#3 — scratch-exit-direction-match is REFUTED

**What is different now:** the g154 numbers reproduce byte for byte, but the arm changes
only **5 days out of 498**, one of those days carries **81% of the whole gain**, and a
random drop of the same 229 candidates passes g154's own survivor test **61% of the time** —
so "survivor" here is a coin flip that landed heads, not an edge.

All figures: honest close fill on the signal bar, `stop_rule.stop_fill_price` stops,
size-gated on `signal_runner.min_risk_floor`, 1R = $1,000, one-trade-a-day unit
(`research/omen_metrics.first_of_day_arm`), book `research/bt2y_trades_retest_on.json`,
498 sessions. Split at 2025-09-01. Produced by
`research/g155_refute3_scratch_dir.py` → `research/g155_refute3_scratch_dir.json`.

---

## 1. Reproduction: clean

Re-ran `research/g154_rule_scratch-exit-direction-match.py` on base f8740f80. The regenerated
`.json` and `.md` are **byte-identical** to the committed ones (`diff` empty). Every headline
number in the claim is real: baseline $33.93/day → arm $35.09/day, H1 delta 1.89, H2 delta 0.42,
precision 30.5 → 30.0, recall_100 5.9 → 5.9. Nothing was mis-stated.

## 2. Lookahead: clean

`direction_match` reads `bars[entry_i]` only — the signal bar itself. Audited all 8,227
candidates against the book's own `entry` price: 4,972 match `bars[entry_i].close` exactly and
the maximum disagreement across the rest is **$0.005** (the book rounds entry to cents). The bar
being read *is* the bar being filled at close, so the candle's color is known at the fill
instant. No read past the entry bar. **This is not the reason to refute.**

## 3. The arm moves 5 days out of 498

| day | baseline pick | arm pick | $ delta |
|---|---|---|---:|
| 2024-12-20 | MSFT 09:36, −$447.13 | INTC 09:37, +$19.23 | **+466.36** |
| 2025-08-13 | AMD 09:49, +$175.77 | GOOGL 09:52, +$480.16 | +304.39 |
| 2024-09-23 | HOOD 09:37, −$8.82 | PLTR 09:43, −$310.18 | −301.36 |
| 2025-11-19 | NFLX 09:41, +$291.56 | QQQ 09:41, +$395.65 | +104.09 |
| 2025-10-16 | ACHR 09:37, −$283.68 | AMZN 09:48, −$283.22 | +0.46 |

Total P&L delta over two years: **+$573.94**. One day (2024-12-20) is **81.3%** of it.

Split the same five days by half and the survivor test dissolves:

- **H1** = 2024-12-20 (+466), 2025-08-13 (+304), 2024-09-23 (−301) → +$469.39 / 249 = **+1.89/day**
- **H2** = 2025-11-19 (+104), 2025-10-16 (+0.46) → +$104.55 / 249 = **+0.42/day**

**The entire H2 half of "survives both halves" is one day.** 2025-11-19 fires NFLX and QQQ in
the *same minute* (09:41); dropping NFLX promotes QQQ purely because same-minute arrival order
is broken alphabetically in `ekey`. The second H2 day contributes 46 cents. Remove 2025-11-19
and H2's delta is +$0.0018/day, and `usd_improves` — the only branch holding the flag up — goes
false.

## 4. A random drop passes the same test 61% of the time

Placebo: drop 229 candidates at random (same count as the 229 mismatches), rebuild first-of-day,
apply g154's survivor test verbatim. 400 trials, seed 20260905:

| null-arm outcome | rate |
|---|---:|
| passes `usd_improves` (both halves > 0) | 21.2% |
| passes `prec_improves` | 51.0% |
| **passes g154's survivor test (`(usd or prec) and recall_ok`)** | **61.0%** |

The arm's own overall delta (+$1.16/day) sits at the **61st percentile** of the placebo
distribution — a middling random draw. Placebo mean delta −$1.78/day, p95 +$15.49/day.
A test a null arm passes 61% of the time is not a test.

## 5. The claim's own numbers already fail two project gates

- **Precision goes DOWN**, 30.5% (18/59) → 30.0% (18/60). The arm added a fired-and-graded day
  and it was not an S. `prec_improves` is False; the flag rides entirely on the `or` branch.
- **Green months go DOWN**, 13/25 → 12/25 overall and 9/12 → 8/12 in H1. CLAUDE.md names
  durability — "every month green" — as the gate. g154's survivor test never looks at green
  months, so the arm regresses the stated gate and is scored a survivor anyway.
- **Recall is unchanged, not preserved by design**: 2/34 both sides, and 18/347 on all
  bar-backed S days. The arm touches no S day at all.

## 6. Confidence interval and multiplicity

Paired per-day bootstrap (4,000 resamples of the 498 days) on the arm-minus-baseline delta:

| | value |
|---|---:|
| paired delta | **+$1.15/day** |
| 95% CI | **[−$1.21, +$3.84]** |
| straddles zero | **yes** |

25 rule candidates were tried. At a 61% null pass rate, roughly **15 of 25 would "survive" on
noise alone**. Seeing this one pass carries essentially zero evidential weight (p ≈ 0.61 for a
single draw), and this is before the four-cell survivor test's own internal multiplicity.

## 7. Verdict

**REFUTED.** The numbers are honest and the code has no lookahead — the *inference* is what
fails. Five changed days, 81% of the gain in one of them, an H2 half made of a single
same-minute alphabetical tiebreak, a CI straddling zero, a null placebo clearing the same bar
61% of the time, and two named project gates (precision, green months) moving the wrong way.

To g154's credit its own notes call the deltas "noise-sized" and say the survivor test "proves
almost nothing on its own." That caveat is correct and this report quantifies it: the flag
should read `survivor = False`.

The descriptive split g154 calls its load-bearing result is a separate question and is untouched
here — but note it too rests on 20 graded rows in the mismatch bucket (10 S of 20), against 952
in the match bucket. A 50%-vs-29.9% S-rate gap on n=20 is a hint, not a finding.
