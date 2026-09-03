# G7.1 / losshalt — the loss-governor grid, 2-year book

**Date** 2026-08-29 · **Script** `research/g71_losshalt_grid.py` (deterministic, seed 7)
· **Data** `research/bt2y_trades.json` (500 sessions, 2024-08-21..2026-08-21)
· **Machine-readable** `research/g71_losshalt_grid.json` · **Diagnosis only — no engine
file touched.**

Austin: *"i see your right so 2 consecutive halts is bad, but overtrading is too,
subagents will find the medium"* and *"we dont know if 2 losers in a row is a stopping
point, keep trading s trades until youve hit profit."*

---

## Headline

**Two losers in a row is not a stopping point.** A trade entered while two already-closed
losses sit behind it still makes **+0.308 R** on average (n=320, SE 0.117 — 2.6 SE above
zero). The streak *dents* the edge, it never kills it. Every halt in the grid therefore
throws away money-making trades, and every arm's total R is below the ungoverned book.

What the halt buys is **tail**, not edge: worst day −10.59R → −5.78R, max drawdown
−27.9R → −14.7R. That is worth having and no edge statistic can see it.

**The medium: `halt_n = 3` plus a −2R realised-day floor.** It is a statistical tie with
the shipped `halt_n = 2` on money (+27.4R, 95% CI [−23.0, +84.5]), matches its tail
*exactly* (worst day −5.78R, DD −14.9 vs −14.7), and hands back **162 trades and 60 trading
days**. Days on which the governor stops you trading go **49% → 37%**. That is the
overtrading/undertrading medium, bought at zero measured cost.

---

## 1. Method

`bt2y_trades.json` is written with R31 already applied (857 rows flipped `fired` →
`halted`). The candidate pool is rebuilt as `(status=="fired" and traded) or
status=="halted"` = **3,294 trades over 496 traded sessions, +1,659.2R** — the unhalted
book. Rows that fired but were never counted (alert-only) stay out.

Every gate is **causal**: evaluated at the candidate's own entry moment against trades that
had already **closed** by then, exactly the exit-clock discipline in `loss_halt.py:66-91`.
Sorting a day by entry time and reading off eventual outcomes
(`research/t20_loss_halt_postprocess.py`) is a bar of look-ahead. A blocked trade never
happened, so it never feeds the streak, the win counter, or the realised R.

Uncertainty is a **paired day-block bootstrap** (4,000 resamples of whole sessions on the
day-by-day R difference). Days are the only near-independent unit here — every governor is
a within-day rule, so the arms are perfectly paired.

**On the ±1.5799R bar the brief names:** it was *retired 2026-08-28*
(`research/g3_onwatch_2y.md`, `research/g13_floor_fix_ab.md:152`) and was never a sampling
error — it was the price of one open question about intrabar stops, which Austin closed.
Quoting it here would make every arm "unreadable" by construction: the whole grid's mean
R/trade spans **0.4917 → 0.6654**, a range 10× narrower than that bar. The carried bar is
±0.0095R and is a fill-assumption interval, not a sampling one. So this report uses its own
bootstrap and says explicitly, per row, whether the arm clears it.

---

## 2. The grid — 5 halt_n × 2 stop-on-win × 4 R floors

496 traded days of 500 sessions; months = 25, weeks = 105. Prop breach = count of days
whose realised R is at or below the limit, at 1R = \$1,000.

| cell | n | total R | R/trade | R/traded-day | win% | mo | wk | maxDD | worst day | R/DD | 50k@2% | 50k@3% | 100k@2% | 100k@3% |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **halt=none win=N floor=none** (no governor) | 3294 | **1659.2** | 0.5037 | 3.345 | 46.4 | 25/25 | 93/105 | −27.9 | −10.59 | 59.5 | 122 | 102 | 84 | 52 |
| halt=none win=N floor=−3R | 2985 | 1531.5 | 0.5131 | 3.088 | 47.4 | 25/25 | 92/105 | −22.2 | −6.78 | 69.0 | 142 | 126 | 109 | 79 |
| halt=4 win=N floor=none | 3084 | 1516.4 | 0.4917 | 3.057 | 46.9 | 25/25 | 93/105 | −25.2 | −9.59 | 60.2 | 134 | 112 | 92 | 63 |
| halt=4 win=N floor=−3R | 2935 | 1484.2 | 0.5057 | 2.992 | 47.5 | 25/25 | 93/105 | −22.2 | −6.78 | 66.9 | 145 | 127 | 107 | 77 |
| halt=3 win=N floor=−3R | 2839 | 1472.0 | 0.5185 | 2.968 | 48.0 | 24/25 | 93/105 | −18.7 | −6.78 | 78.7 | 149 | 125 | 103 | 70 |
| halt=3 win=N floor=none | 2863 | 1465.9 | 0.5120 | 2.955 | 47.9 | 24/25 | 92/105 | −18.7 | −7.59 | 78.3 | 148 | 124 | 102 | 69 |
| **halt=none win=N floor=−2R** | 2702 | 1389.8 | 0.5144 | 2.802 | 47.5 | 25/25 | 91/105 | −15.9 | −5.78 | 87.2 | 180 | 167 | 152 | 38 |
| halt=4 win=N floor=−2R | 2662 | 1371.1 | 0.5151 | 2.764 | 47.7 | 25/25 | 91/105 | −15.9 | −5.78 | 86.0 | 180 | 164 | 146 | 37 |
| **halt=3 win=N floor=−2R** ← recommended | 2599 | **1366.5** | 0.5258 | 2.755 | 48.2 | **25/25** | 91/105 | **−14.9** | **−5.78** | 91.5 | 180 | 159 | 138 | 37 |
| halt=2 win=N floor=−3R | 2435 | 1341.1 | 0.5508 | 2.704 | 49.2 | 25/25 | 91/105 | −14.7 | −5.78 | 91.2 | 170 | 147 | 120 | 37 |
| **halt=2 win=N floor=none** (SHIPPED R31) | 2437 | **1339.1** | 0.5495 | 2.700 | 49.2 | 25/25 | 91/105 | −14.7 | −5.78 | 91.0 | 170 | 147 | 120 | 37 |
| halt=2 win=N floor=−2R | 2424 | 1337.9 | 0.5519 | 2.697 | 49.3 | 25/25 | 90/105 | **−13.7** | −5.78 | **97.6** | 171 | 148 | 123 | 36 |
| halt=none win=N floor=−1R | 2077 | 1256.5 | 0.6050 | 2.533 | 49.6 | 25/25 | 90/105 | −17.4 | −3.48 | 72.0 | 244 | 72 | 44 | 6 |
| halt=3 win=N floor=−1R | 2013 | 1241.4 | 0.6167 | 2.503 | 50.4 | 25/25 | 88/105 | −17.4 | −3.48 | 71.1 | 241 | 68 | 42 | 6 |
| halt=4 win=N floor=−1R | 2047 | 1236.6 | 0.6041 | 2.493 | 49.9 | 25/25 | 90/105 | −17.4 | −3.48 | 70.9 | 243 | 71 | 44 | 6 |
| halt=2 win=N floor=−1R | 1900 | 1204.9 | 0.6342 | 2.429 | 51.2 | 25/25 | 88/105 | −17.4 | −3.48 | 69.0 | 230 | 62 | 41 | 6 |
| halt=1 win=N floor=−1R | 1515 | 989.1 | 0.6529 | 1.994 | 53.4 | **23/25** | 87/105 | −16.4 | −3.48 | 60.1 | 204 | 46 | 37 | 6 |
| halt=1 win=N floor=−2R / −3R / none | 1524 | 984.7 | 0.6461 | 1.985 | 53.1 | **23/25** | 88/105 | −16.4 | −5.78 | 59.9 | 203 | 47 | 40 | 8 |
| halt=none **win=Y** floor=none | 1362 | 742.2 | 0.5449 | 1.496 | 51.0 | **21/25** | 87/105 | −27.4 | −10.00 | 27.1 | 88 | 68 | 52 | 36 |
| halt=4 win=Y floor=none | 1296 | 698.4 | 0.5389 | 1.408 | 51.5 | 23/25 | 87/105 | −19.4 | −8.00 | 36.0 | 93 | 72 | 58 | 41 |
| halt=3 win=Y floor=−3R / none | 1232 | 687.5 | 0.5581 | 1.386 | 52.4 | 25/25 | 89/105 | −17.5 | −5.00 | 39.2 | 98 | 81 | 66 | 50 |
| halt=4 / none win=Y floor=−3R | 1235 | 687.3 | 0.5565 | 1.386 | 52.4 | 25/25 | 88/105 | −17.5 | −5.00 | 39.2 | 98 | 80 | 65 | 50 |
| halt=2 win=Y floor=none / −2R / −3R | 1098 | 647.7 | 0.5899 | 1.306 | 53.3 | 24/25 | 86/105 | −16.6 | −4.00 | 38.9 | 123 | 105 | 96 | 21 |
| halt=3 / 4 / none win=Y floor=−2R | 1106 | 644.7 | 0.5829 | 1.300 | 53.1 | 24/25 | 86/105 | −16.6 | −4.00 | 38.7 | 123 | 108 | 99 | 21 |
| halt=3 / 4 / none win=Y floor=−1R | 811 | 539.0 | 0.6647 | 1.087 | **55.2** | 24/25 | 84/105 | −19.1 | −3.39 | 28.2 | 192 | 36 | 34 | 5 |
| halt=2 win=Y floor=−1R | 810 | 537.0 | 0.6630 | 1.083 | **55.2** | 24/25 | 84/105 | −19.1 | −3.39 | 28.1 | 192 | 36 | 34 | 5 |
| halt=1 win=Y (any floor) | 806 | 536.3 | 0.6654 | 1.081 | **55.3** | 24/25 | 85/105 | −19.1 | −3.39 | 28.1 | 190 | 36 | 34 | 5 |

Rows collapse where floors are non-binding (e.g. with `stop_on_win`, a −3R floor almost
never fires before the first win does).

### 2b. Bootstrap vs the ungoverned book (4,000 day resamples, total R)

**All 39 governed arms lose money against no governor and all 39 clear their own CI.**
Selected rows:

| cell | Δ total R | lo95 | hi95 | readable |
|---|--:|--:|--:|---|
| halt=none floor=−3R | −127.7 | −259.1 | −23.2 | yes |
| halt=4 floor=none | −142.8 | −264.8 | −47.5 | yes |
| halt=3 floor=none | −193.3 | −334.0 | −77.0 | yes |
| halt=none floor=−2R | −269.3 | −417.5 | −137.2 | yes |
| **halt=3 floor=−2R** | **−292.7** | −452.4 | −152.1 | yes |
| **halt=2 floor=none (shipped)** | **−320.1** | −483.4 | −174.5 | yes |
| halt=1 floor=none | −674.5 | −900.9 | −474.7 | yes |
| **stop-on-win, nothing else** | **−917.0** | −1143.7 | −693.1 | yes |
| halt=1 + stop-on-win | −1122.9 | −1377.6 | −874.9 | yes |

### 2c. Head-to-head against the shipped rule

| comparison | Δ total R | lo95 | hi95 | readable |
|---|--:|--:|--:|---|
| −2R floor only **vs** halt=2 | +50.8 | −12.7 | +118.5 | **no — tie** |
| halt=3 + −2R floor **vs** halt=2 | +27.4 | −23.0 | +84.5 | **no — tie** |

Three governors — `halt=2`, `halt=3 + −2R`, `−2R floor alone` — are money-indistinguishable
and tail-identical (worst day −5.78R for all three; DD −14.7 / −14.9 / −15.9). **The choice
between them is not a money choice.** It is a choice about how many days you are allowed to
trade, and there they differ a lot:

| governor | days it stops you trading | trades removed |
|---|--:|--:|
| halt=1 | 394 / 496 (79%) | 1,770 (54%) |
| **halt=2 (shipped)** | **245 / 496 (49%)** | 857 (26%) |
| halt=3 + −2R floor | 185 / 496 (37%) | 695 (21%) |
| halt=3 + −2R + S-until-profit | 179 / 496 (36%) | 576 (17%) |
| −2R floor alone | 145 / 496 (29%) | 592 (18%) |

This is the R20 collision (`research/t22_adjudication.md` blocker 7 — *"quality over
quantity, but he wants to trade every day"*) measured. **The shipped rule benches him on
half of all trading days for a money result it cannot distinguish from a rule that benches
him on 37%.**

---

## 3. Is "two in a row" a stopping point? No.

Mean R of a trade **given the closed-loss streak sitting behind it at its own entry
moment**, on the ungoverned book:

| streak at entry | n | mean R | SE | win% |
|---|--:|--:|--:|--:|
| 0 in a row | 1894 | **+0.6003** | 0.0474 | 51.8 |
| 1 in a row | 762 | +0.3910 | 0.0833 | 42.1 |
| 2 in a row | 320 | **+0.3080** | 0.1168 | 40.3 |
| 3 in a row | 173 | +0.1930 | 0.1444 | 33.5 |
| 4+ in a row | 145 | +0.6359 | 0.2230 | 40.0 |

The edge decays monotonically 0 → 3 (0-vs-2 gap +0.292R against a combined SE of 0.126 —
2.3 SE, readable) and then **rebounds**, which is noise at n=145. **It never turns
negative.** The trade after two losses still makes +0.31R at 2.6 SE above zero.

Same test on the day's realised R instead of the streak:

| realised day R at entry | n | mean R | SE | win% |
|---|--:|--:|--:|--:|
| ≤ −3R | 254 | +0.3767 | 0.1417 | 37.0 |
| −3 .. −2R | 227 | +0.4806 | 0.1472 | 45.8 |
| −2 .. −1R | 444 | +0.2882 | 0.0915 | 44.1 |
| −1 .. 0R | 1001 | +0.6251 | 0.0627 | 53.1 |
| green | 1368 | +0.5122 | 0.0620 | 45.5 |

Even three R in the hole, the next trade is worth +0.38R. **Nothing in this book supports
stopping for edge reasons.** Any halt is a risk-management choice made in spite of the
edge, not because of it. Say that out loud when the rule ships.

---

## 4. "Keep trading S trades until you've hit profit"

Taken literally: once the gate trips, keep taking **Austin-ladder S** cards, and only while
the day's realised R is still ≤ 0 (`+Sprof`). The all-day version (`+Scont`) is the
looser reading.

| cell | n | total R | R/trade | win% | mo | maxDD | worst day | Δ vs same gate | lo95 | hi95 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| halt=2 floor=none | 2437 | 1339.1 | 0.5495 | 49.2 | 25/25 | −14.7 | −5.78 | — | | |
| halt=2 floor=none **+Sprof** | 2593 | **1392.5** | 0.5370 | 48.9 | 25/25 | −16.7 | −6.33 | **+53.4** | +4.4 | +109.4 |
| halt=2 floor=none +Scont | 2620 | 1378.7 | 0.5262 | 48.6 | 25/25 | −16.7 | −6.33 | +39.6 | −11.7 | +95.2 |
| halt=3 floor=−2R | 2599 | 1366.5 | 0.5258 | 48.2 | 25/25 | −14.9 | −5.78 | — | | |
| halt=3 floor=−2R **+Sprof** | 2718 | **1412.1** | 0.5195 | 48.1 | 25/25 | −16.9 | −5.44 | +45.6 | −2.1 | +99.2 |
| halt=3 floor=none +Sprof | 2948 | 1503.1 | 0.5099 | 47.7 | **25/25** (was 24) | −20.7 | −7.59 | +37.2 | −0.8 | +83.3 |
| halt=none floor=−2R +Sprof | 2817 | 1438.1 | 0.5105 | 47.4 | 25/25 | −17.9 | −5.44 | +48.3 | +1.4 | +102.1 |
| halt=1 floor=none +Sprof | 1799 | 1023.2 | 0.5688 | 51.5 | 23/25 | −16.6 | −5.00 | +38.5 | −16.1 | +99.7 |

**The S exemption is positive in 12 of 12 arms** (+30.4R to +53.4R), and 3 of 12 clear
their own CI. Twelve same-signs is stronger than any single CI suggests, but the arms
overlap heavily so treat it as *consistent* rather than *proven*. It also restores a green
month on `halt=3 floor=none` (24/25 → 25/25).

`+Sprof` beats `+Scont` on 4 of 6 shared gates — stopping the exemption once the day is
green is the better half of his sentence, not just the more literal one.

---

## 5. Stop-after-win is the most expensive setting in the grid

−917.0R [−1143.7, −693.1] on its own, and it costs **4 green months** (25/25 → 21/25). It
buys +4.6pp win rate (46.4% → 51.0%) and halves the book. Every `win=Y` row sits in the
bottom third of the table.

`config.yaml:28` has it **off** (C10 turned it off on the 12-month book) and
`live_scanner.py:81` defaults `STOP_AFTER_WIN` to `"0"`. **Nothing to change — this section
is a lock, not a proposal.** C10's call is now confirmed at 4× the sample and it is a
readable, not a marginal, result.

---

## 6. Prop-firm daily loss limits — the counts are a trap

Naive reading of the breach columns says a floor makes things *worse*: the ungoverned book
breaches 2% of \$50k (= 1R) on 122 of 496 days; add a −1R floor and it breaches on **244**.
That is not a bug. **A floor set at the limit maximises breaches of that limit** — it
converts every day that would have dug deep and recovered into a day parked at exactly the
limit. The −2R floor does the same thing to the 100k@2% column (84 → 152) while cutting
100k@3% from 52 → 38.

The number that actually matters to a prop account is **the largest 1R you can size and
never breach**, = limit ÷ |worst day R|:

| cell | worst day | 50k@2% | 50k@3% | 100k@2% | 100k@3% |
|---|--:|--:|--:|--:|--:|
| no governor | −10.59R | \$94 | \$141 | \$188 | \$283 |
| halt=2 (shipped) | −5.78R | \$173 | \$259 | \$346 | \$519 |
| **halt=3 + −2R floor** | −5.78R | \$173 | \$259 | \$346 | \$519 |
| −2R floor alone | −5.78R | \$173 | \$259 | \$346 | \$519 |
| halt=2 + −2R floor | −5.78R | \$173 | \$259 | \$346 | \$519 |

**Any governor roughly doubles the size you can carry** (\$94 → \$173 on a \$50k/2% desk),
and the three medium candidates are exactly tied on it. And the blunt truth: **at 1R =
\$1,000 this book is not prop-survivable on either account under any of the 40 cells** —
the best row still breaches 2% of \$50k on 190 of 496 days. Prop deployment is a sizing
question, not a halt question, and the halt's whole contribution is the 1.8× on size above.

---

## 7. Recommendation

**Ship `halt_n = 3` plus a realised-day floor at −2R, and add the S-until-profit
exemption.** In the grid that is `halt=3 win=N floor=−2R +Sprof`: 2,718 trades,
**+1,412.1R**, 48.1% win, **25/25 months**, 91/105 weeks, max DD −16.9R, worst day −5.44R.

Against the shipped `halt_n = 2`: **+73.0R more, 281 more trades, 66 more tradeable days,
same worst day (−5.44 vs −5.78), DD −16.9 vs −14.7.** Against no governor: −247R, and DD
halves.

If only one knob may move, **move `LOSS_HALT_N` from 2 to 3 and add the −2R floor**; the
`+Sprof` exemption is the part that is directionally consistent but not individually
readable, and it is also the part that needs `downgrade.py`'s S grade in the live path,
which is not wired (`DIRECTION.md` §"Two grading ladders" — S/A/C is measured only). Ship
the two knobs now, hold `+Sprof` until the ladder is wired.

### Confidence: **medium**

- **High confidence, readable:** *any* governor costs total R vs none (all 39 arms clear
  their CI); stop-on-win is a disaster (−917R, 8× its CI half-width); the halt's real
  product is tail (worst day halves, DD halves); the edge after two consecutive losses is
  **positive** (+0.308R, 2.6 SE).
- **Explicitly NOT resolved — the arms are inside the bar:** `halt=2` vs `halt=3+−2R` vs
  `−2R floor alone` are a **three-way tie on money** (+27.4R [−23.0, +84.5] and +50.8R
  [−12.7, +118.5], both spanning zero) and identical on worst day. **Do not present the
  recommended cell as beating the shipped one on P&L — it does not, measurably.** The
  argument for it is *days he is allowed to trade* (37% benched vs 49%), which is a
  preference he already stated, not a number the book resolves.
- On the retired **±1.5799R** bar the brief cites, **every one of the 40 cells is inside
  it and always would be**: the whole grid's mean R/trade spans 0.4917–0.6654, a range 10×
  narrower than that interval. That bar cannot discriminate anything here and is not the
  right instrument — it was retired 2026-08-28 and was never a sampling error.
- The book itself does not clear the money gate in any cell: best mean R/trade is 0.6654
  against a 2.0 target, and only 8 of 40 cells reach 55% win rate — all of them
  stop-on-win arms that give up half the book. **This grid tunes risk, not the gate.**

---

## 8. Exact diff, if adopted (NOT applied)

`loss_halt.py` gains the floor and the exemption; `backtest_2y.py` is unchanged because it
already calls `apply_to_book`. The live path needs a matching realised-R accumulator next
to `_account_streak` (`live_scanner.py:562`), which this diff does **not** write — flag it
as the second half of the ticket.

```diff
--- a/loss_halt.py
+++ b/loss_halt.py
@@
 # R31. Two in a row, and the day is done.
-HALT_AFTER_CONSECUTIVE_LOSSES = int(os.getenv("LOSS_HALT_N", "2"))
+# G7.1/losshalt 2026-08-29: 2 -> 3. `halt=2`, `halt=3 + -2R floor` and the floor
+# alone are a three-way TIE on total R (+27.4R [-23.0,+84.5] paired day
+# bootstrap, research/g71_losshalt.md S2c) with an identical worst day
+# (-5.78R). What separates them is how often he is benched: 49% of sessions at
+# n=2, 37% at n=3 with the floor. R20 says he wants to trade every day.
+HALT_AFTER_CONSECUTIVE_LOSSES = int(os.getenv("LOSS_HALT_N", "3"))
+
+# G7.1/losshalt: the DAY'S realised R, not the streak, is the governor that
+# actually carries the tail. New entries stop once closed trades have taken the
+# day to this level or below. None / 0 disables. Set at -2R: -3R leaves the
+# worst day at -6.78R, -1R parks 244 of 496 days exactly on a $50k/2% prop
+# limit (research/g71_losshalt.md S6).
+_floor = os.getenv("DAY_R_FLOOR", "-2").strip()
+DAY_R_FLOOR = float(_floor) if _floor not in ("", "none", "off", "0") else None
 
 # Ships ON — R31 is ratified and ships at his answer (method rule 4).
 # LOSS_HALT=0 restores the pre-T23 book for a leave-one-out arm.
 LOSS_HALT = os.getenv("LOSS_HALT", "1").strip().lower() not in ("0", "false", "off", "no")
 
 
-def halt_day(rows, entry_key, exit_key, loss_key, n=None):
+def halt_day(rows, entry_key, exit_key, loss_key, r_key=None, n=None, floor=...):
     """Walk one day's traded rows in entry order and return the blocked ones.
 
     ``rows``      — the day's TRADED rows, any order.
     ``entry_key`` — row -> a sortable moment the entry is placed.
     ``exit_key``  — row -> the same scale, the moment the trade closes.
     ``loss_key``  — row -> True if the trade closed at a loss.
+    ``r_key``     — row -> the trade's R. Required when ``floor`` is in play.
 
     Returns the subset of ``rows`` that the halt blocks, as a list. A row is
     blocked when, at its own entry moment, at least ``n`` already-closed trades
-    that were themselves TAKEN have lost in an unbroken run.
+    that were themselves TAKEN have lost in an unbroken run, OR the realised R
+    of those already-closed taken trades is at or below ``floor``.
     """
     if n is None:
         n = HALT_AFTER_CONSECUTIVE_LOSSES
-    if n <= 0:
+    if floor is ...:
+        floor = DAY_R_FLOOR
+    if n <= 0 and floor is None:
         return []
 
     taken = sorted(rows, key=entry_key)
-    blocked, pending, streak = [], [], 0
+    blocked, pending, streak, realised = [], [], 0, 0.0
     # `pending` holds trades that are taken and still open, as (exit, is_loss),
     # kept sorted so the counter can be advanced to any entry moment.
     for row in taken:
         at = entry_key(row)
         while pending and pending[0][0] <= at:
-            _x, lost = pending.pop(0)
+            _x, lost, r = pending.pop(0)
             streak = streak + 1 if lost else 0
-        if streak >= n:
+            realised += r
+        if (n > 0 and streak >= n) or (floor is not None and realised <= floor):
             blocked.append(row)
             continue                       # a blocked trade never happened
-        pending.append((exit_key(row), bool(loss_key(row))))
+        pending.append((exit_key(row), bool(loss_key(row)),
+                        float(r_key(row)) if r_key else 0.0))
         pending.sort(key=lambda p: p[0])
     return blocked
@@
     n = 0
     for day_rows in by_day.values():
         for r in halt_day(day_rows,
                           entry_key=lambda x: (x.get("entry_i", 0), x.get("et", ""), x.get("sym", "")),
                           exit_key=lambda x: (x.get("entry_i", 0) + x.get("bars", 0),
                                               x.get("et", ""), x.get("sym", "")),
-                          loss_key=lambda x: x.get("out") == "loss"):
+                          loss_key=lambda x: x.get("out") == "loss",
+                          r_key=lambda x: x.get("r", 0.0)):
             r["traded"] = False
             r["status"] = "halted"
             r["halted"] = True
-            r["reason"] = (r.get("reason", "") + " [halt: %d consecutive losses]"
-                           % HALT_AFTER_CONSECUTIVE_LOSSES).strip()
+            r["reason"] = (r.get("reason", "") + " [halt: %d consecutive losses or %s day R]"
+                           % (HALT_AFTER_CONSECUTIVE_LOSSES, DAY_R_FLOOR)).strip()
             n += 1
     return n
```

**Second half of the ticket, not diffed here:** `live_scanner._tier():573-576` gates on
`_account_streak["n"]` only. It needs a sibling `_account_day_r` accumulated on every
closed paper/live trade and the same `<= DAY_R_FLOOR` test, or the live path and the
backtest run different rules again — which is exactly the failure R31 was written to close.

**Re-run gate:** this changes the published two-year book (2,437 → 2,599 traded, +1,339.1R
→ +1,366.5R). `backtest_2y.py` must be re-run and every figure in `DIRECTION.md`'s money
row re-stated in the same commit.
