# g154 -- F5: entry-earlier-satisfiable-bar

**One sentence: the engine's own signal bar is not always the earliest bar that would have satisfied a workable retest -- of the book's 8227 fired-and-traded candidates, 2.1% already had lag_bars<=0 (the signal bar itself was the earliest workable one); the rest had an earlier bar that would have worked, and restricting the one-trade-a-day pick to KEEP lag_bars<=L clears the survivor bar (H1 and H2 both improve, recall_100 not below baseline).**

Every dollar figure: signal-bar CLOSE entry, `stop_rule.stop_fill_price` stops, size-gated on `signal_runner.min_risk_floor`, 1R = $1,000. Book: `research/bt2y_trades_retest_on.json` (498 sessions, 2024-09-03 -> 2026-09-02). Produced by `research/g154_rule_entry-earlier-satisfiable-bar.py`.

## Lag prevalence (raw candidate stream, 8227 rows, 16.52 cand/day)

| lag_bars <= L | %% of raw candidates |
|---:|---:|
| 0 | 2.1% |
| 1 | 7.9% |
| 2 | 15.1% |
| 3 | 23.3% |

## Money and durability, one-trade-a-day

| arm | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| baseline (first_of_day_arm) | $34 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| KEEP lag_bars<=0 | $-36 | -0.181 | 44.4% | 9/25 | $19549 | 0.199 |
| KEEP lag_bars<=1 | $-30 | -0.050 | 45.9% | 9/25 | $15931 | 0.608 |
| KEEP lag_bars<=2 | $-39 | -0.047 | 46.1% | 10/25 | $22493 | 0.817 |
| KEEP lag_bars<=3 | $-51 | -0.055 | 45.0% | 8/25 | $27080 | 0.930 |

## H1 (< 2025-09-01) vs H2 (>= 2025-09-01)

| arm | H1 $/day | H2 $/day | H1 months green | H2 months green |
|---|---:|---:|---:|---:|
| baseline | $136 | $-68 | 9/12 | 4/13 |
| KEEP lag_bars<=0 | $-45 | $-27 | 3/12 | 6/13 |
| KEEP lag_bars<=1 | $-21 | $-40 | 4/12 | 5/13 |
| KEEP lag_bars<=2 | $-10 | $-68 | 5/12 | 5/13 |
| KEEP lag_bars<=3 | $-30 | $-73 | 5/12 | 3/13 |

## Recall and precision

Definitions (stated because the row's wording underdetermines them): the one-trade-a-day arm picks exactly ONE symbol per calendar day across the whole pool. RECALL(100) = of the 34 cards in `probe_s_sweep_2026-08-28.jsonl` graded S (answers.s==['s']), the fraction where that day's arm pick exists and is on that symbol. RECALL(bar-backed) = the same test against all `marks_pool.s_days()` symbol-days that have `data_archive` bars (345 of 347 graded S). PRECISION = of the days the arm fired, restricted to days where that (symbol, day) has ANY `marks_pool.canonical_pool()` grade, the fraction graded S.

| arm | recall(100) | recall(bar-backed) | precision |
|---|---:|---:|---:|
| baseline | 5.9% (2/34) | 5.2% (18/345) | 30.5% (18/59) |
| KEEP lag_bars<=0 | 2.9% (1/34) | 2.6% (9/345) | 60.0% (9/15) |
| KEEP lag_bars<=1 | 2.9% (1/34) | 4.9% (17/345) | 43.6% (17/39) |
| KEEP lag_bars<=2 | 5.9% (2/34) | 7.5% (26/345) | 46.4% (26/56) |
| KEEP lag_bars<=3 | 8.8% (3/34) | 7.8% (27/345) | 45.0% (27/60) |

## Verdict

Survivor test (THE LAW): H1 AND H2 both improve $/day or precision, and recall_100 is not below baseline. **survivor = True**, chosen L = 2.

Chosen arm (KEEP lag_bars<=2) vs baseline: $-39/day vs $34/day (H1 $-10 vs $136, H2 $-68 vs $-68); precision 46.4% vs 30.5%; recall(100) 5.9% vs 5.9%; 10/25 months green vs 13/25.

Small-N caveat: recall(100) denominators are 34 cards; a single card flipping moves the percentage by ~3 points. Read this as a direction, not a diagnosis (CLAUDE.md: never oversell a handful of marks).

**Survivor test is fragile, flag for F6.** The formula as specified -- "H1 and H2 both improve $/day OR precision" -- was implemented literally: precision is a single overall number (the row names no H1/H2-split precision field), so it is checked once and OR'd into BOTH half-conditions. That is what let L=2 pass: H1 $/day COLLAPSED (baseline $136/day -> $-10/day) while H2 $/day barely moved (baseline $-68/day -> $-68/day, still negative) -- neither half's MONEY improved, but overall precision rose (30.5% -> 46.4%) and that alone satisfied both halves. A stricter reading -- both halves' $/day must not get WORSE, with precision only as a tie-breaker -- would flip every tested L to survivor=False, since every arm's full-book $/day is negative against a $34/day positive baseline. Reported as specified; treat 'survivor=True' here as 'passes the letter of the rule', not as a shippable arm.

Nothing here is applied. `signal_runner.py` is unchanged.
