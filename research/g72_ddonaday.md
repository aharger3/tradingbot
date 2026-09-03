# The disaster stop, measured under one trade a day

*Measure only. Nothing was changed. `research/g72_ddonaday.py`, run 2026-08-29.*

---

## The answer in one line

**Deleting the resting disaster order is worth about **+$150 a day, +$3,100 a month**
under either of the two sequencing rules you are choosing between — and unlike almost
everything else this project has ever tested, it clears its own error bar.**

The board only ever priced this across all 2,437 trades. Here it is priced on the policy you
are actually going to run.

| your rule | keep the order (what you ratified) | delete it | difference |
|---|---:|---:|---:|
| **(a)** first; a win ends the day; 2 losses end the day | **$806 a day** | **$960 a day** | **+$154 a day** |
| **(b)** keep going until green, 3-loss cap | **$897 a day** | **$1,046 a day** | **+$149 a day** |
| **(b+)** same, plus your −$2,000 day floor | **$863 a day** | **$1,012 a day** | **+$149 a day** |

Per month, at 21 trading days: **(a) $16,900 → $20,200. (b) $18,800 → $22,000.**

Across two years: **(a) +$76,700. (b) +$74,100.**

---

## The full board

496 trading days, 25 months, 105 weeks. 1R = $1,000. Every row runs one position at a time
and cannot open the next trade before the last one closed.

### (a) your sentence — first trade, a win ends the day, two losses end the day

| | trades | win rate | $/day | $/month | months green | weeks green | green days | worst drawdown | worst day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Keep the order at −$1,000 | 705 | 52.5% | $806 | $16,918 | 22/25 | 83/105 | 68.8% | −$16,340 | −$2,000 |
| **Delete it** | 680 | **57.8%** | **$960** | **$20,164** | **23/25** | 84/105 | **71.8%** | **−$14,330** | −$2,500 |
| Push it out to −$1,250 | 692 | 55.8% | $830 | $17,422 | 23/25 | 84/105 | 70.2% | −$17,210 | −$2,500 |

### (b) keep going until the day is green, 3-loss cap

| | trades | win rate | $/day | $/month | months green | weeks green | green days | worst drawdown | worst day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Keep the order at −$1,000 | 861 | 50.4% | $897 | $18,833 | 23/25 | 85/105 | 76.4% | **−$12,930** | −$3,000 |
| **Delete it** | 818 | **55.2%** | **$1,046** | **$21,970** | **24/25** | **88/105** | **78.8%** | −$14,620 | −$3,750 |
| Push it out to −$1,250 | 845 | 53.0% | $856 | $17,970 | 23/25 | 80/105 | 76.2% | −$16,470 | −$3,750 |

### (b+) the same, with your −$2,000 daily floor switched on

| | trades | win rate | $/day | $/month | months green | weeks green | green days | worst drawdown | worst day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Keep the order at −$1,000 | 749 | 52.2% | $863 | $18,119 | 23/25 | 84/105 | 72.6% | **−$10,240** | −$2,838 |
| **Delete it** | 726 | **57.3%** | **$1,012** | **$21,246** | **24/25** | **90/105** | 75.4% | **−$10,520** | −$2,967 |
| Push it out to −$1,250 | 740 | 54.9% | $843 | $17,699 | 23/25 | 86/105 | 73.2% | −$14,850 | −$3,112 |

### For reference — one trade a day flat, and the whole book

| | trades | win rate | $/day | $/month | months green | weeks green | green days | worst drawdown | worst day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| First trade only, keep the order | 496 | 54.9% | $612 | $12,842 | 22/25 | 77/105 | 55.0% | −$20,140 | −$1,000 |
| First trade only, **delete it** | 496 | **60.1%** | **$748** | **$15,718** | **23/25** | **82/105** | **60.3%** | **−$14,170** | −$1,250 |
| Whole book, all signals at once, keep the order | 2,436 | 49.5% | $2,697 | $56,639 | 25/25 | 91/105 | 58.1% | −$14,710 | −$5,784 |
| Whole book, **delete it** | 2,598 | 55.0% | $3,527 | $74,061 | 25/25 | 94/105 | 64.5% | −$11,910 | −$7,182 |

*(the last two rows reproduce the board's all-trades claim: 49.5% → 55.0% win rate, and the
drawdown falling. Under one-a-day the win-rate lift is bigger, not smaller.)*

---

## Four things you should know before you decide

**1. It is the same trade, just filled differently.** On all 496 days, both books take the
*identical* first signal — same ticker, same minute, same entry. 213 of those 496 first trades
end on a different number, and **26 of them flip from a loss to a win** purely because a wick
no longer ends the trade. This is not a different strategy; it is your close-only rule being
honoured.

**2. It clears its own error bar, which almost nothing here does.** The standing finding in
this project is that every A/B moves less than its own noise. This one does not: the per-day
improvement runs **2.2 to 3.0 standard errors** above zero on all four policies. It is the
first exit-side change since the far-away target to survive that test.

**3. It costs you on the worst single day, and under one rule it costs drawdown too.**
A loss can now book −$1,250 instead of exactly −$1,000, so the worst day gets worse in every
row (−$2,000 → −$2,500 under (a); −$3,000 → −$3,750 under (b)). Under **(a)** the total
drawdown still *improves* by $2,010. Under **(b)** the total drawdown gets **$1,690 worse**
— that is the one place deleting the order is not free. **Switching on your −$2,000 daily
floor removes that cost entirely**: −$10,240 with the order kept, −$10,520 without. Same
drawdown, +$149 a day.

**4. The middle option — pushing the order out to −$1,250 — is the worst of both.** It buys
you +$8 to −$41 a day, all inside the noise, and it makes the drawdown *worse* on every single
policy (−$16,340 → −$17,210 under (a); −$12,930 → −$16,470 under (b)). If you want the −$1,250
number, delete the order and let the close-only clamp give it to you.

---

## So, if you want it as one recommendation

**Delete the resting order and turn on the −$2,000 day floor.** That combination is
**$1,012 a day / $21,200 a month, 57.3% win rate, 24 of 25 months green, 90 of 105 weeks
green, 75% green days, and the second-smallest drawdown on the whole board at −$10,520** —
and its drawdown is within $280 of the best row anywhere in this study.

The straight comparison of your two sequencing candidates does not change with the disaster
stop: **(b) still beats (a)** on money and green days under both settings, and **(a) still
wins on the worst single day**.

---

## How this was measured, and the one thing to watch

Three complete two-year replays that differ *only* in the resting order —
`research/_g71s_S0_shipped.json`, `_g71s_D_off.json`, `_g71s_D_125.json`, all produced by
`research/g71_stops.py` within seven minutes of each other on 2026-08-29. Nothing was
re-simulated for this study; every stop fill in those books came from the one fill definition,
`stop_rule.stop_fill_price()`. The day-policy walk, the candidate stream and the scoring are
imported from `research/g71_firsts_policy.py` rather than rewritten, and the "keep the order"
column reproduces the board's §4 table to the dollar (496 trades / 54.9% / $612 / 22-of-25 /
77-of-105 / 55.0% green days).

**The watch-out:** `research/bt2y_trades.json` on disk is no longer the book the board
describes. The board's book was 76,019 setups and 2,437 trades; another track rebuilt the file
at 17:06 today and it now reads 134,012 setups and 4,508 trades. That is why this study reads
the three `g71_stops` arms — they are the same engine state as the board, and they are the only
disaster-stop-on book that has a disaster-stop-off twin. **Anything on the board that quotes
`bt2y_trades.json` needs re-checking against the new file.**

Recall gate: **PASS** (`python research/regression_gate.py`, no baseline-fired mark went
silent). No engine file, default or setting was touched.
