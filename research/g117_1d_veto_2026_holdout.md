# g117 — the 1D veto on 2026 only, and the pick-then-gate fix

**2026-09-03.** Script: `research/g117_1d_veto_2026_holdout.py`. Book:
`research/bt2y_trades_retest_on.json` (127,152 rows, 498 sessions, every row carrying
`level_tf`). Unit: one trade a day, first size-gated candidate, honest close entry fill,
$1,000 per R. Nothing here is fitted — the veto is one boolean applied as-is.

---

## (a) Pick-then-gate: the selection rule was losing one day in nine

`omen_metrics.first_of_day_arm` returned the day's **first** candidate and let
`ev_r_scoreboard`'s size gate drop it afterwards. So a day whose first setup was too
tight to size did not fall through to the next tradeable candidate — **the whole day
left the arm.**

| first-of-day arm | days scored | ev/R | total R | $/day | win | months green | max DD (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| before — pick, then gate | 444 | +0.0377 | 16.73 | $34 | 46.0% | 12/25 | −20.41 |
| after — gate inside the pick | **498** | +0.0339 | 16.90 | $34 | 46.4% | **13/25** | −21.40 |

**54 of 498 sessions (10.8%) were being silently discarded.** The headline ev/R goes
*down* slightly (−0.0038) and that is the point: the old number was flattered by dropping
days rather than trading them. Total R and months green both improve, because the
recovered days are real trades, not a resampling. One decision now has one owner — the
gate runs inside selection, through the same `_row_is_sizeable` predicate the scoreboard
uses, not a second copy.

## The 1D veto, measured on an arm that no longer loses days

Veto = skip the day when the first size-gated candidate retested a **prior-day high or
low**. 104 of 498 arm days (20.9%) are 1D.

| full book | days | ev/R | total R | $/day | win | months green | max DD (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| no veto | 498 | +0.0339 | 16.90 | $34 | 46.4% | 13/25 | −21.40 |
| **1D veto ON** | 394 | **+0.1359** | 53.54 | **$108** | 50.8% | **16/25** | **−13.91** |

## (d) 2026 holdout — the year the rule was not chosen on

164 sessions, 39 of them vetoed.

| 2026 only | days | ev/R | total R | $/day | win | months green | max DD (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| no veto | 164 | **−0.0679** | −11.13 | **−$68** | 44.5% | 2/9 | −21.40 |
| 1D veto ON | 125 | +0.0247 | 3.08 | +$19 | 47.2% | 4/9 | −13.91 |

Delta: **+0.0926 ev/R, +$87/day, on 39 vetoed days.** The direction holds out of sample,
and the more interesting half of the table is the top row: **without the veto, 2026 is a
losing year** on this unit.

## What this does and does not establish

- **It is a direction check, not a decision.** 164 arm days is a few hundred trades; the
  error bar on any single arm in this repo has exceeded ±1.5R, and 39 vetoed days cannot
  separate a real effect from noise. It is not on its own a reason to ship the veto.
- **It is in-sample for the veto's discovery**, only out-of-sample for the *year*. The
  rule came off the full book, which contains 2026.
- **The live gate is unaffected and stays OFF.** Austin, 2026-09-03: *"PDH/PDL are good
  levels in my eyes."* `live_scanner.OMEN_LIVE_1D_VETO` defaults off, the phone push goes
  to the first size-gated S regardless of level, and the 11:00 summary reports both arms
  every day — so this comparison keeps accruing on live data without asking him again.
- **The pick-then-gate fix is not optional and is not an arm.** It was a bug in the
  selection rule; every `$/day` figure measured on `first_of_day_arm` before this commit
  was computed on 444 days while claiming 498.
