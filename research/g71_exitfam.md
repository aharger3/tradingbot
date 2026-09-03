# G7.1 `exitfam` — the exit / strike / break-even / faster-cut families, re-run on the current book

Book `research/bt2y_trades.json` (generated 2026-08-29T03:14:29), **2437 traded rows** replayed from `data_archive/`, 500 sessions 2024-08-21 → 2026-08-21. Gaps: {'day': 0, 'bar': 0, 'index': 0}. Entry, stop, side and entry bar fixed; only the exit varies. Script `research/g71_exitfam.py` (`--selftest`).

Book as booked: **n=2437, 49.7% win, +0.5495R mean, +1339.1R total, 25/25 months green.**

Every arm below runs to the RTH close (the book's own horizon, `backtest_week.py:810`) unless the label says 11:00, and carries BOTH shipped stops: the level stop on the close floored at −1.25R, and the resting −1.0R disaster stop on touch (`stop_rule.py:125`, R1/R2). **No published exit number predating 2026-08-29 carries the disaster stop**, which is why the before/after columns move as much as they do.

## The table

No jargon. "Effect in R" is how much the change moves the average trade, with the range it could really be. **"Is it real" means the range does not include zero** — if it does, the change is indistinguishable from luck on 2,437 trades. The gap to the money gate is **1.45 R**, so read every number below against that.

| family | what it changes | effect in R | is it real? | keep or kill |
|---|---|---|---|---|
| **Exit target** | Aim for 5R instead of 2R | +0.085 R [+0.002, +0.165] | **Yes** | **Keep, but it is 6% of the gap** — and it drops a green month (24/25) and wins only 28.5% of the time. |
| **Exit target** | Aim for 2.5R instead of 2R | +0.040 R [+0.008, +0.071] | **Yes** | **Keep** — real, and free. It is +0.04 R. |
| **Scale-out %** | Stop splitting the position — one unit, one exit | +0.010 R [-0.139, +0.165] | No | **Kill.** X1 said this was worth +0.061 R on the old book. On this one it is inside the noise. |
| **Scale-out %** | Scale 30/30/30 and leave a 10% runner (what Austin actually does) | +0.044 R [+0.005, +0.084] | **Yes** | **Keep** — but it is +0.04 R, and `g71_scaleladder.md`'s engine-native rig reads it at −0.010 R. Match his behaviour because it is his behaviour, not for the number. |
| **Break-even** | Move the stop to break-even once the trade is up 1R | +0.056 R [-0.025, +0.132] | No | **Kill.** Four triggers tested (0.5R / 0.75R / 1R / 1.25R), none survives. R11's own answer — wait for the first target — stands, and now on 2,437 rows instead of 262. |
| **Faster cut** | Give up on a trade after 15 / 30 / 45 minutes | +0.011 R [-0.133, +0.147] | No | **Kill.** Every horizon is inside its own range. Cutting losers on a clock does nothing. |
| **Faster cut** | Get out on the first candle that closes against you | -0.038 R [-0.134, +0.052] | No | **Kill.** The most aggressive cut expressible, and it is still noise. |
| **Faster cut** | Remove the −1R disaster stop that shipped on 2026-08-29 | +0.213 R [+0.116, +0.329] | **Yes** | **Real, and it is the only exit lever on this page that moves more than a rounding error.** Turning the disaster stop ON cost the book about −0.21 R per trade. It bought 25/25 green months and a worst trade of −1.00 R. That is a risk decision, not a money one — Austin's call. |
| **Strike / expiry** | 0DTE vs 1DTE, ATM−1 / ATM / ATM+1 | every arm −0.03 R or smaller vs 0DTE ATM (F5) | No, except 1DTE ATM−1 at −0.032 R | **Kill the search.** No strike or expiry beats 0DTE ATM, and the one arm that clears its bar clears it in the WRONG direction. T8's null result survives the new book. |
| **Clock** | Hold past 11:00 instead of flattening | -0.007 R [-0.144, +0.123] | No | **Kill.** X1 measured this at −0.171 R on the old book. On this one it is −0.007 R and inside the noise. |

**One sentence:** on the current book the exit, strike, break-even and faster-cut families are all dead ends — the two survivors are worth +0.04 R and +0.08 R against a 1.45 R gap — and the only thing in any of them that moves real money is the disaster stop that already shipped, which costs 0.21 R per trade to buy 25 green months.

## F1 — the target

X1 bucket (d) and G7's `flat_*` arms. Baseline is `flat_2r`: every row in the book plans exactly 2.000 R:R.

| arm | n | win% | mean R | median R | total R | months green | delta vs baseline [95% paired] | real? | note |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| `flat_2r` (the shipped plan) | 2437 | 50.4% | +0.5090 | +1.4004 | +1240.4 | 25/25 | baseline | — |  |
| `flat_1r` | 2437 | 69.8% | +0.3962 | +1.0000 | +965.6 | 25/25 | -0.1128 [-0.1561, -0.0674] | **yes** |  |
| `flat_2.5r` | 2437 | 44.6% | +0.5492 | -1.0000 | +1338.4 | 25/25 | +0.0402 [+0.0080, +0.0712] | **yes** |  |
| `flat_3r` | 2437 | 38.9% | +0.5372 | -1.0000 | +1309.2 | 25/25 | +0.0282 [-0.0195, +0.0745] | no |  |
| `flat_4r` | 2437 | 32.4% | +0.5729 | -1.0000 | +1396.2 | 23/25 | +0.0639 [-0.0030, +0.1306] | no |  |
| `flat_5r` | 2437 | 28.5% | +0.5937 | -1.0000 | +1446.9 | 24/25 | +0.0847 [+0.0020, +0.1647] | **yes** |  |
| `ride` — no target at all, run to the close | 2437 | 18.0% | +0.5597 | -1.0000 | +1364.0 | 23/25 | +0.0507 [-0.1198, +0.2304] | no |  |

## F2 — the scale-out percentages

X1 bucket (a). The full ladder grid on this book is `research/g71_scaleladder.md` and is not repeated; what is here is the question X1 asked — is the scaling itself worth anything against one undivided unit. Baseline is the book as booked.

**Two physics, and mixing them is how this family gets misread.** `exit_lab`'s policies predate R1/R2 and know only one stop, so an `exit_lab` arm scored against the book is holding a free +0.21R of downside the book does not have (F4's `ride_nodz` row prices it). The `+dz` rows are the same shipped policy with the resting −1R order laid over it — never re-implemented, see `with_disaster`.

| arm | n | win% | mean R | median R | total R | months green | delta vs book [95% paired] | real? |
|---|---:|---:|---:|---:|---:|---:|---|---|
| book as booked (shipped `hod_then_runner_be`, both stops) | 2437 | 49.7% | +0.5495 | -0.1200 | +1339.1 | 25/25 | baseline | baseline |
| `hod_only` **+dz** | 2437 | 46.6% | +0.5914 | -1.0000 | +1441.2 | 25/25 | +0.0419 [+0.0047, +0.0802] | **yes** |
| `30_30_30_10` **+dz** (his 10% runner) | 2437 | 45.8% | +0.5933 | -1.0000 | +1446.0 | 25/25 | +0.0439 [+0.0054, +0.0844] | **yes** |
| `50_20_20_10` **+dz** | 2437 | 46.5% | +0.5928 | -1.0000 | +1444.6 | 25/25 | +0.0433 [+0.0065, +0.0818] | **yes** |
| one unit, no scaling (`ride`, both stops) | 2437 | 18.0% | +0.5597 | -1.0000 | +1364.0 | 23/25 | +0.0102 [-0.1394, +0.1646] | no |
| `hod_only` — no disaster stop (G7 physics) | 2437 | 51.8% | +0.7129 | +0.2261 | +1737.3 | 25/25 | +0.1634 [+0.1097, +0.2199] | **yes** |
| `30_30_30_10` — no disaster stop (G7 physics) | 2437 | 50.9% | +0.7207 | +0.1067 | +1756.3 | 25/25 | +0.1712 [+0.1145, +0.2296] | **yes** |
| `50_20_20_10` — no disaster stop (G7 physics) | 2437 | 51.6% | +0.7185 | +0.1480 | +1750.9 | 25/25 | +0.1690 [+0.1141, +0.2260] | **yes** |
| one unit — no disaster stop | 2437 | 21.8% | +0.7727 | -1.1613 | +1883.0 | 23/25 | +0.2232 [+0.0458, +0.4121] | **yes** |

## F3 — break-even

X1 bucket (b) and T11/R11's `mfe_*` arms, which were only ever measured on a 60-day / 262-row slice. Baseline is `ride` — the stop never moves. Each arm moves the stop to entry the moment price TOUCHES that many R.

| arm | n | win% | mean R | median R | total R | months green | delta vs baseline [95% paired] | real? | note |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| `ride` — BE never | 2437 | 18.0% | +0.5597 | -1.0000 | +1364.0 | 23/25 | baseline | — |  |
| BE at +0.50R | 2437 | 12.2% | +0.6024 | -0.3182 | +1467.9 | 23/25 | +0.0426 [-0.0464, +0.1269] | no |  |
| BE at +0.75R | 2437 | 12.9% | +0.6153 | -0.3636 | +1499.4 | 23/25 | +0.0555 [-0.0282, +0.1351] | no |  |
| BE at +1.00R | 2437 | 13.4% | +0.6157 | -0.4200 | +1500.4 | 23/25 | +0.0559 [-0.0247, +0.1322] | no |  |
| BE at +1.25R | 2437 | 14.0% | +0.6184 | -0.5000 | +1507.1 | 24/25 | +0.0587 [-0.0189, +0.1316] | no |  |

## F4 — cutting losers faster

X1 bucket (e), plus the one faster-cut that actually shipped: R1/R2's resting −1.0R disaster stop. Baseline is `ride`.

| arm | n | win% | mean R | median R | total R | months green | delta vs baseline [95% paired] | real? | note |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| `ride` | 2437 | 18.0% | +0.5597 | -1.0000 | +1364.0 | 23/25 | baseline | — |  |
| 15-minute time stop | 2437 | 40.9% | +0.5148 | -1.0000 | +1254.6 | 25/25 | -0.0449 [-0.2051, +0.1114] | no |  |
| 30-minute time stop | 2437 | 34.3% | +0.5449 | -1.0000 | +1327.9 | 24/25 | -0.0148 [-0.1640, +0.1308] | no |  |
| 45-minute time stop | 2437 | 30.1% | +0.5710 | -1.0000 | +1391.5 | 24/25 | +0.0113 [-0.1330, +0.1468] | no |  |
| first adverse close | 2437 | 10.1% | +0.5213 | -0.2879 | +1270.4 | 22/25 | -0.0384 [-0.1340, +0.0525] | no | |
| `ride`, disaster stop OFF | 2437 | 21.8% | +0.7727 | -1.1613 | +1883.0 | 23/25 | +0.2130 [+0.1159, +0.3293] | **yes** | the pre-2026-08-29 physics |

Read the last row backwards: the delta is what turning the disaster stop **ON** cost or bought, with the sign flipped.

## F5 — strike and expiry

T8's six arms re-priced on this book. **T8 does not run on it** — see the diff below. Contract R, prior-session sigma, IV 1.2×, `options_sizer`'s own $0.05 min-tick guard. Baseline 0DTE ATM.

| expiry | strike | n | win% | mean R | median R | tick-floored | months green | delta vs 0DTE ATM [95% paired] | real? |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 0DTE | ATM-1 | 2435 | 34.4% | +0.5726 | -0.5893 | 13.3% | 25/25 | -0.0311 [-0.0702, +0.0061] | no |
| 0DTE | ATM | 2436 | 34.3% | +0.6012 | -0.9354 | 6.4% | 25/25 | baseline | baseline |
| 0DTE | ATM+1 | 2436 | 34.2% | +0.5780 | -0.5146 | 17.0% | 25/25 | -0.0255 [-0.0665, +0.0131] | no |
| 1DTE | ATM-1 | 2435 | 34.5% | +0.5714 | -0.7091 | 10.3% | 25/25 | -0.0323 [-0.0629, -0.0028] | **yes** |
| 1DTE | ATM | 2436 | 34.4% | +0.5911 | -0.9676 | 5.4% | 25/25 | -0.0124 [-0.0258, +0.0021] | no |
| 1DTE | ATM+1 | 2436 | 34.4% | +0.5750 | -0.5959 | 12.5% | 25/25 | -0.0285 [-0.0592, +0.0008] | no |

## F6 — the 11:00 clock (X1 bucket (c))

| arm | n | win% | mean R | median R | total R | months green | delta vs baseline [95% paired] | real? | note |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| `ride` — run to the RTH close | 2437 | 18.0% | +0.5597 | -1.0000 | +1364.0 | 23/25 | baseline | — |  |
| `ride` — force-flat at 11:00 | 2437 | 30.4% | +0.5523 | -1.0000 | +1346.0 | 24/25 | -0.0074 [-0.1439, +0.1234] | no |  |

## Before and after, arm by arm

BEFORE is the published figure, quoted with its source and its row count. AFTER is this file. They are not the same rig — BEFORE has no disaster stop and, where marked, a different clock — which is the point.

| family | arm | BEFORE (old book) | AFTER (this book) | what changed |
|---|---|---|---|---|
| exit | `flat_2r` (the shipped plan) | +0.702 R, 1,016 rows (`g7_exit_sweep.md`) | +0.5090 R | the whole book's mean R fell with it |
| exit | `flat_5r` vs `flat_2r` | +0.2112 R (`x1_exit_attribution.md` row (d)) | +0.0847 [+0.0020, +0.1647] | still positive, **4× smaller**, and it costs 1 green month |
| exit | `flat_2.5r` vs `flat_2r` | +0.0540 R (X1 row (d)) | +0.0402 [+0.0080, +0.0712] | holds, same size |
| exit | one unit vs the shipped ladder | +0.0609 R (X1 row (a)) | +0.0102 [-0.1394, +0.1646] | **gone** — the interval now straddles zero |
| exit | `30_30_30_10` vs the shipped ladder | +0.955 vs +0.957 = −0.002 R, 1,016 rows (`g7_exit_sweep.md`, quoted by P24) | +0.0439 [+0.0054, +0.0844] | now positive and outside its bar, but see the note below |
| break-even | BE never vs BE at +1R | +0.1207 R (X1 row (b)) | -0.0559 [-0.1322, +0.0247] | **sign flipped and died** |
| break-even | BE on movement (R11) | +0.0051 / −0.0302 / −0.0404 / −0.0615 R on 262 rows (`t11_be_on_movement.md`) | +0.0426 [-0.0464, +0.1269] / +0.0555 [-0.0282, +0.1351] / +0.0559 [-0.0247, +0.1322] / +0.0587 [-0.0189, +0.1316] vs BE-never | all four still null, now on 2,437 rows instead of 262 |
| faster cut | best time stop | −0.0142 R (X1 row (e)) | +0.0113 [-0.1330, +0.1468] (45 min) | still null |
| faster cut | first adverse close | in X1's (e) bundle | -0.0384 [-0.1340, +0.0525] | null |
| faster cut | the −1R disaster stop | did not exist | +0.2130 [+0.1159, +0.3293] for turning it OFF | **the only faster-cut lever that moves anything, and it costs money** |
| clock | hold past 11:00 | −0.1709 R (X1 row (c)) | -0.0074 [-0.1439, +0.1234] | **gone** |
| strike | 1DTE ATM vs 0DTE ATM | +0.0037 R, 2,592 rows (`t8_strike-sweep.md`) | see F5 | still inside noise on the mean |

## The `30_30_30_10` caveat — two rigs disagree and neither is wrong

`research/g71_scaleladder.md`, on this same book, puts his 30/30/30/10 ladder at **+0.539 R against the shipped +0.549 R (−0.010 R)**. This file puts it at **+0.0439 [+0.0054, +0.0844]**. Both are honest and they measure different objects: `scaleladder` rebuilds the ladder inside the engine's own management loop, this file runs `exit_lab.policy_30_30_30_10` unchanged and lays the resting order over it, and `exit_lab`'s runner is an ATR/structure trail with a 5-bar consolidation cut that the engine's is not. **Use `scaleladder`'s number for the ladder question** — its rig is the engine. What this file adds is the physics correction: measured without the disaster stop the same three policies read +0.1712 [+0.1145, +0.2296] against the book, which is **four times bigger and entirely an artifact of them not carrying a stop the book carries**.

## `research/t8_strike_sweep.py` does not run on this book — the fix

```
$ python research/t8_strike_sweep.py
   book fingerprint: n=2437 mean_r=+0.5495  *** NOT THE PINNED BOOK ***
  File "research/t8_strike_sweep.py", line 215, in px
    return bs.price(S, self.K, T, self.sigma, call=self.call, r=self.r)
  File "black_scholes.py", line 53, in d1_d2
    d1 = (math.log(S / K) + (r - q + 0.5*sigma*sigma) * T) / vt
ZeroDivisionError: float division by zero
```

`Contract.__init__` builds `K = nearest_strike(entry) + k*increment` and never checks `K > 0`. The ratified book added cheap names: **ACHR at $3.08 on 2024-10-15** has ATM = 2.50 and increment 2.50, so the ATM−1 arm asks Black-Scholes for a strike of exactly 0.00. One row of 2,437 takes the entire six-arm sweep down. A strike of 0 is not a contract, so the row is simply not `ok` — the same treatment T8 already gives a row with no prior session to build sigma from. **Not applied — this is a diagnosis pass.**

```diff
--- a/research/t8_strike_sweep.py
+++ b/research/t8_strike_sweep.py
@@ -196,6 +196,14 @@ class Contract:
         inc = osz.STRIKE_INCREMENT.get(row["sym"].upper(), 2.5)
         base = osz.nearest_strike(self.S0, row["sym"])
         self.K = base + strike_k * inc
+        # A strike of zero or less is not a contract. Cheap names make
+        # this reachable: ACHR at $3.08 has ATM 2.50 on a 2.50
+        # increment, so ATM-1 lands on 0.00 and black_scholes.d1_d2's
+        # math.log(S / K) divides by zero. Treated the same way a row
+        # with no prior session is treated -- not ok, reported, dropped
+        # from that arm's denominator, never a silent crash.
+        if self.K <= 0:
+            self.sigma, self.ok, self.tick_floored = 0.0, False, False
+            self.row = row
+            return
         self.stop = row["stop"]

@@ -117,8 +117,8 @@
-PINNED_N = 2595
-PINNED_MEAN_R = 0.5481
+PINNED_N = 2437
+PINNED_MEAN_R = 0.5495
```

The second hunk is the other half of the same problem: T8's fingerprint pin still names the 2,595-row book T0 published, and `research/bt2y_trades.json` has since been regenerated to **2,437 rows / +0.5495 R**. Every track reading that file today is reading a book that prints `*** NOT THE PINNED BOOK ***`. Re-pin it or say why not.

## The error bars, and which one is the right one

| bar | value | what it is |
|---|---:|---|
| paired bootstrap (this file) | per arm, above | 10000 resamples of the per-row DIFFERENCE. The only interval that fits a same-rows A/B. |
| T0 sampling bar | ±0.1725 R | 95% on the whole book's MEAN R. Prices variance a paired comparison does not carry. |
| narrow fill bar | ±0.0095 R | the fill-ambiguity bar carried since T3. |
| the wide bar | ±1.5799 R | **RETIRED 2026-08-28** (`research/g3_onwatch_2y.md`:3) after Austin ruled *"Out on that same close."* Quoted in the brief; not a live interval. |

