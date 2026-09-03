# OMEN — the book, as of 2026-08-29

Every trade the engine would have taken over 500 market days, 2024-08-21 to 2026-08-21, across 28 symbols. Risk on every trade is $1,000. "R" is that $1,000: +2R is +$2,000.

It looked at **76,019** setups and took **2,437** of them.

## 1. Did it make money?

| | this run | needs to be | there yet? | moved |
|---|---:|---:|:--:|---:|
| Money made | **$1,339,071** | — | — | — |
| Average made per trade | **+0.55R** ($550) | +2.00R | no | — |
| Win rate | **49.5%** | 55.0% | no | — |

1,198 winners, 1,222 losers, 17 closed flat. Best trade +24.35R, worst -1.00R. It makes $2.11 for every $1.00 it loses.

## 2. Did it hold up?

| | this run | needs to be | there yet? | moved |
|---|---:|---:|:--:|---:|
| Months in profit | **25 of 25** | all 25 | YES | — |
| Weeks in profit | **91 of 105** (87%) | — | — | — |
| Worst run of losses | **17.1R** (-$17,132) | smaller is better | — | — |

Worst month was 2025-09 at +3.92R ($3,920). "Worst run of losses" is how far the account fell from its own high point before making a new one.

## 3. Did it find his trades?

| | this run | needs to be | there yet? | moved |
|---|---:|---:|:--:|---:|
| Fires on the days he graded best | **18 of 34 (52.9%)** | 90% | no | — |
| Also fires on days he refused | 33 of 66 (50.0%) | fewer is better | — | — |
| Of the setups it saw and threw away, how many he wanted | 0 of 9 | all of them | no | — |

Measured on days the engine has never been tuned on (`research/t0_heldout_recall.json`, probe_s_sweep_2026-08-28 (100 blind cards)).

## 4. How busy is it?

| | this run | moved |
|---|---:|---:|
| Trades per market day | **4.87** | — |
| Trades in total | 2,437 | — |
| Setups looked at | 76,019 | — |

## The scoreboard

**1 of 3 finished.** OMEN is done when all three are true at once: it averages +2R a trade at a 55% win rate, every month is green, and it fires on 90% of the days he grades best.

## Month by month

| month | R | dollars |
|---|---:|---:|
| 2024-08 | +21.90 | $21,900 |
| 2024-09 | +9.79 | $9,790 |
| 2024-10 | +71.18 | $71,180 |
| 2024-11 | +42.99 | $42,990 |
| 2024-12 | +11.32 | $11,320 |
| 2025-01 | +28.10 | $28,100 |
| 2025-02 | +56.59 | $56,590 |
| 2025-03 | +61.35 | $61,350 |
| 2025-04 | +110.86 | $110,860 |
| 2025-05 | +31.72 | $31,720 |
| 2025-06 | +22.29 | $22,290 |
| 2025-07 | +44.19 | $44,190 |
| 2025-08 | +74.54 | $74,540 |
| 2025-09 | +3.92 | $3,920 |
| 2025-10 | +42.58 | $42,580 |
| 2025-11 | +36.06 | $36,060 |
| 2025-12 | +71.14 | $71,140 |
| 2026-01 | +59.27 | $59,270 |
| 2026-02 | +41.66 | $41,660 |
| 2026-03 | +91.65 | $91,650 |
| 2026-04 | +61.72 | $61,720 |
| 2026-05 | +63.41 | $63,410 |
| 2026-06 | +98.81 | $98,810 |
| 2026-07 | +114.20 | $114,200 |
| 2026-08 | +67.83 | $67,830 |

---

Book: `research/bt2y_trades.json` (built 2026-08-29T03:14:29). Page: `research/g71_standard_report.py`. Numbers: `research/omen_report.json`.
