# G71 / OMEN 7.1 blocker 1 — where the stop goes, and what to risk on it

Austin, 2026-08-29:

> "stops go where they make sense. you know what makes sense from my marks, the rules. from my head right now the answer is **level, bottom of candle entered on, pivot structure**, and you decide which one based on the **best risk to reward tradable**. you pick a **disaster stop**. if im not trading fixed 2:1 on every single trade, then maybe i have the wrong idea **risking 1k everytime or 1.25k**."

Script: `research/g71_stops.py` (`--selfcheck` green, 8 cases). Book: 10 full 2-year replays of `backtest_2y.py`, 2024-08-21..2026-08-21, 496 sessions, 28 symbols, ~76,000 signals each, engine at `a0997963` after T0's ratification. Baseline `S0_shipped` reproduces the canonical book: 2,436 traded, +0.5492 R, 49.5% win, 25/25 months.

Nothing in the shipped engine was edited. `S1`/`S2` are `signal_runner.STOP_PLACEMENT` (T24, already there, default `entry_bar`); `S3`/`S4` are new and are installed by monkeypatching `signal_runner.placed_stop` inside a child process. Every exit still books through `stop_rule.stop_fill_price()` / `stop_rule.disaster_stop_price()` — no fill is reimplemented anywhere in this track.

---

## The four lines

1. **The one thing worth changing is not a placement — it is the disaster stop, and it should be DELETED as a resting order.** `DISASTER_STOP=0` (keep the close-triggered level stop, keep the −1.25R clamp, remove the intrabar resting order at −1R) is **+0.1204 R paired, SE 0.0210, t = +5.74**, robust to a +10R cap (+0.1192, t = +5.77). Win rate **49.5% → 55.0%** — the win-rate half of the money gate, met. Max drawdown **−17.1R → −13.7R**. Weeks green 91/105 → 94/105. This *reverses* R1/R2 (`fact_two_stops`, ratified this morning: *"Level stop on the close, disaster stop on touch"*), so it is an **amber** finding, not a change to make unattended.
2. **None of the three placements he named beats what is shipped, once the tight-stop artefact is removed.** Paired and capped at +10R: `S1_level` **−0.1327 (t −5.46)**, `S3_pivot` **−0.1448 (t −4.11)**, `S4_bestrr` **−0.1197 (t −4.10)**. Only `S2_candle` is positive (**+0.1378, t +4.15**) — and `S2` is 84.8% of what the shipped engine already does via `intrabar_stop`.
3. **"Best RR tradable" is arithmetically a stop-tightening rule, and it is the worst arm on the board.** With a target fixed at a real level, maximising `(target − entry)/(entry − stop)` *is* minimising `entry − stop`. `S4_bestrr` therefore walks straight into the tightest candidate every time: **269 of 2,402 traded rows (11.2%) end with zero risk**, 14.3% sit inside the tolerance unit, months green fall to 22/25, weeks to 73/105, max drawdown to −32.1R. The selector he described, implemented literally, is a machine for producing untradeable stops.
4. **Fixed $1,000 is right, and the reason is one number: `corr(R, |entry − stop|) = −0.013`.** Stop width carries no information about outcome, so varying risk with it adds leverage and nothing else. Over-risking the tight stops ("inverse") lifts return on risk 54.9% → 66.5% but **doubles max drawdown, −$17,132 → −$32,611**. His "1k or 1.25k" is not a sizing question at all — it is the disaster-stop question in dollars, and finding 1 says **−$1,250**.

---

## What his own marks say

114 marked symbol-days carry both an entry bar and a stop **price** (the rest carry a typed note — "931" meaning the 9:31 wick — and `p25.clean_stop` refuses them). Corpora, loader and the note test are `research.p25_midcandle_entry`, imported not reimplemented, so this is the same population T24 measured. A stop "matches" a family when it sits within **one tolerance unit — `BAR_EXTREME_FRAC` (25%) of the entry bar's own range** — of that family's price. Categories overlap on purpose: a level and a candle wick are often the same price.

His median stop: **$0.645**, **0.197% of entry**, **0.901 of the entry bar's own range**.

| family | matches within one tolerance unit | nearest of the three |
|---|--:|--:|
| S1 broken level | 33/114 | 32 |
| S2 candle entered on | **80/114** | **77** |
| S3 pivot structure | 7/114 | 5 |
| none of the three | 25/114 | — |

**The bottom of the candle entered on is his stop, 70% of the time.** Pivot structure — the family he named third — matches **7 of 114**, and is the nearest of the three on only 5. His free-text `stop_src` box says `swing high 09:44` fifteen times, so pivots are clearly *in his head*; they are almost never where the price he typed actually landed. Twenty-five stops match none of the three: those are named levels he did not break that day (`PDH`, `ORL`, `PML`) sitting further away than the tolerance unit.

By setup, `nearest` family: **B&R** — candle 35, level 19, pivot 2. **OCR** — candle 27, level 3, pivot 0. **BR+OCR** — candle 12, level 7, pivot 1.

---

## 1. The four families, on the two-year book

`mean R` is the raw book number every other OMEN report prints. It is **not** the number to act on for an arm that moves the stop: `R = |entry − stop|` is the denominator, so a tighter stop inflates R by construction — `signal_runner.py:889-892` names this failure mode verbatim. `med R` and `mean R capped at +10` are the honest reads. *(A 0DTE option cannot return 192x its risk on a 90-minute move; the cap prices that.)*

| arm | traded | mean R | med R | mean R capped at +10 | win% | months | weeks | maxDD | mean stop $ | med stop % | too tight (noise) | too tight (opt $0.05) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `S0_shipped` | 2436 | +0.5492 | -0.1265 | +0.5346 | 49.5% | 25/25 | 91/105 | -17.1R | 0.679 | 0.230% | 1.44% | 42.08% |
| `S1_level` | 2434 | +0.4062 | +0.0000 | +0.4015 | 49.7% | 24/25 | 85/105 | -17.6R | 0.602 | 0.211% | 16.06% | 49.14% |
| `S2_candle` | 2273 | +1.5571 | -1.0000 | +0.6576 | 40.9% | 25/25 | 88/105 | -25.0R | 0.556 | 0.198% | 10.12% | 54.20% |
| `S3_pivot` | 11102 | +0.2836 | +0.2860 | +0.2273 | 64.6% | 25/25 | 100/105 | -22.1R | 1.247 | 0.496% | 0.59% | 19.56% |
| `S4_bestrr` | 2402 | +0.4042 | +0.0000 | +0.3659 | 44.9% | 22/25 | 73/105 | -32.1R | 0.532 | 0.209% | 14.32% | 53.96% |

Read the `S2_candle` row carefully, because it is the trap. Its headline **+1.5571 R** is **the top 10 trades out of 2,273 carrying 35.7% of the entire book**, max R **+192.0**, and a **median R of −1.0000** — more than half of its trades are full losers. Capped at +10R it is +0.6576; on the rows whose stop clears the tolerance unit it is +0.503, *below* the shipped +0.514. Its win rate, 40.9%, is the worst on the board.

`S3_pivot` is a different animal: it trades **11,102 rows — 4.6x the book, 22 a day** — at a **64.6% win rate** and a *positive* median R. That is not a live configuration (he takes 1-3 a day), but it is the only arm that goes the right way on the gate that governs. See §4.

### Stop distance, and how often it is too tight to trade

Austin's "too tight rr" worry, priced three ways. **Noise** is the repo's own tolerance unit — a stop inside `BAR_EXTREME_FRAC` (25%) of the entry bar's range is inside the band this engine already treats as "the same price". **Mech** is one average spread plus one tick, the spread measured per symbol off the archive with the Corwin-Schultz (2012) high-low estimator on consecutive 1-minute RTH bars (median **$0.1185, 6.7 bp**, range $0.0067 ACHR – $1.0937 MU). **Opt $s** is the options reading: an option quoted $s wide at delta 0.50 needs `2 × s/0.50` of underlying to cover the round trip.

| arm | mean stop $ | med stop % | inside noise band | < spread+tick | < $0.10 (opt $0.05) | < $0.20 (opt $0.10) | < $0.30 (opt $0.15) | zero-risk rows |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `S0_shipped` | 0.679 | 0.230% | 1.44% | 10.06% | 17.53% | 42.08% | 64.12% | 0 |
| `S1_level` | 0.602 | 0.211% | **16.06%** | 24.16% | 29.54% | 49.14% | 67.95% | **324 (13.3%)** |
| `S2_candle` | 0.556 | 0.198% | 10.12% | 22.22% | 29.74% | 54.20% | 72.24% | 38 |
| `S3_pivot` | 1.247 | 0.496% | 0.59% | 4.46% | 10.56% | 19.56% | 35.43% | 4 |
| `S4_bestrr` | 0.532 | 0.209% | **14.32%** | 23.77% | 33.97% | 53.96% | 72.40% | **269 (11.2%)** |

**He is right to worry, and the shipped book is already exposed.** On `S0_shipped`, **42.1% of traded rows have a stop narrower than the round trip on a $0.05-wide option at 0.50 delta**. In R-dollars: mean stop $0.679 at $1,000 risk is **1,473 shares, or ~29 contracts at 0.50 delta**; on `S3_pivot`'s $1.247 stop it is 802 shares / ~16 contracts.

**His `level` stop is unsizeable 13% of the time.** This is T24's finding re-measured on the post-T0 book: a resting limit at the broken level fills *at* the level, and for a break-and-retest the level **is** the stop, so `|entry − stop|` collapses to zero. `intrabar_stop` exists to rescue exactly those rows onto the candle entered on — which is why the shipped engine is already 84.8% `S2` in practice, and why `S1` as a *uniform* rule books 324 zero-risk rows.

---

## 2. The selector — "best risk to reward tradable"

Implemented literally (`_best_rr`, `research/g71_stops.py`): among `S1`, `S2`, `S3`, keep the candidates that are on the losing side of the close, at least **$0.05** away (the tradability floor), and no further than **0.60% of price** (the disaster-stop ceiling — T24 put the shipped book's p90 stop at 0.405% of entry); then take the one maximising `(nearest real level beyond entry − entry) / (entry − stop)`.

**With the target fixed at a real level, the numerator is shared, so RR-maximising and stop-tightening are the same operation.** The selector is a tightening rule wearing a ratio's clothes. What it picked, over 137,600 calls: level 57,437 · candle 54,728 · pivot 12,852 · nothing valid 12,583. What it rejected: **pivot past the ceiling 36,626** (pivot structure is simply wider than 0.60% of price most of the time), **level too tight 31,808**, **candle too tight 23,092**.

Result: the worst arm measured here. −0.1197R paired-and-capped (t −4.10), **22/25 months green** (durability lost — the only arm to lose it), 73/105 weeks, max drawdown −32.1R, 269 zero-risk rows.

**This is the answer to the question he asked.** "Pick the best RR" is not a stop rule — it is an instruction to shrink the denominator, and the denominator is the only thing standing between the book and an arithmetic fiction. What would make an RR selector meaningful is a target that does **not** move with the stop, *and* a floor set to his real execution cost rather than to $0.05. The engine's own target is `entry ± 2 × risk` (`backtest_week.py:836`) — a blind 2R that moves with the stop, so under the shipped exit **every** stop scores exactly 2.00 RR and the phrase has no content. That is his own complaint — *"if im not trading fixed 2:1 on every single trade"* — sitting in the code as a line of arithmetic.

---

## 3. The disaster stop — the one real result

Every arm below is the shipped placement; only the resting order moves. `DISASTER_STOP=0` means no resting intrabar order at all: the level stop still triggers on a **close** and the fill is still clamped at −1.25R by `stop_rule.stop_fill_price`.

| arm | where the order rests | traded | mean R | med R | win% | worst R | months | weeks | maxDD |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `D_off` | no resting order (clamp only, −1.25R) | 2598 | **+0.6733** | +0.3400 | **55.0%** | -1.25 | 25/25 | **94/105** | **-13.7R** |
| `D_075` | resting at −0.75R | 2343 | +0.5506 | -0.7500 | 45.5% | -0.75 | 25/25 | 94/105 | -13.7R |
| `S0_shipped` | resting at −1.00R (shipped) | 2436 | +0.5492 | -0.1265 | 49.5% | -1.00 | 25/25 | 91/105 | -17.1R |
| `D_125` | resting at −1.25R | 2546 | +0.5639 | +0.2500 | 52.8% | -1.25 | 25/25 | 88/105 | -17.1R |
| `D_150` | resting at −1.50R | 2559 | +0.5598 | +0.3020 | 54.1% | -1.50 | 25/25 | 86/105 | -20.8R |
| `D_200` | resting at −2.00R | 2606 | +0.5804 | +0.3280 | 54.7% | -2.00 | 25/25 | 89/105 | -21.4R |

### Paired vs the shipped book

The arms share most of their rows, so the unpaired ±0.17R book bar is the wrong bar — it prices variance the two arms hold in common. Rows are matched on `(symbol, day, entry time, setup, direction)`.

| arm | shared rows | delta mean R | SE | t | delta capped at +10R | SE | t |
|---|--:|--:|--:|--:|--:|--:|--:|
| `S1_level` | 2206 | -0.1437 | 0.0284 | -5.07 | -0.1327 | 0.0243 | -5.46 |
| `S2_candle` | 1591 | +0.8075 | 0.1958 | +4.12 | +0.1378 | 0.0332 | +4.15 |
| `S3_pivot` | 1399 | +0.0575 | 0.1117 | +0.51 | -0.1448 | 0.0352 | -4.11 |
| `S4_bestrr` | 1682 | -0.0912 | 0.0471 | -1.94 | -0.1197 | 0.0292 | -4.10 |
| `D_off` | 2328 | **+0.1204** | 0.0210 | **+5.74** | **+0.1192** | 0.0207 | **+5.77** |
| `D_075` | 2250 | -0.0093 | 0.0166 | -0.56 | -0.0093 | 0.0166 | -0.56 |
| `D_125` | 2354 | +0.0047 | 0.0152 | +0.31 | +0.0045 | 0.0151 | +0.30 |
| `D_150` | 2333 | -0.0019 | 0.0184 | -0.10 | -0.0021 | 0.0183 | -0.12 |
| `D_200` | 2333 | +0.0270 | 0.0213 | +1.27 | +0.0257 | 0.0210 | +1.23 |

**Reading it.** `D_125` rests at −1.25R, which is also where the clamp already sits, and it is a **no-op (+0.0047, t +0.31)**. `D_off` removes the resting order entirely and is **+0.1204, t +5.74**. The only difference between those two arms is *touch versus close* — and that difference is the whole effect. **A bar that wicks to −1.25R and recovers is a loser under every resting-order arm and a survivor under `D_off`.** That is Austin's own settled rule — *"wicks stop nothing"* — showing up as +0.12R and 5.5 points of win rate.

`D_200` looks like it should equal `D_off` (a resting order at −2R rarely triggers) and does not (+0.0270, t +1.27): when it *does* trigger it books −2.0R, bypassing the −1.25R clamp. Its `worst R` column says so.

**The recommendation, and why it is amber.** The measurement says: keep the level stop on the close, keep the −1.25R clamp, **delete the resting intrabar order**. That directly contradicts R2 (`fact_two_stops`, verdict `both`) which Austin ratified on 2026-08-29 — *"Level stop on the close, disaster stop on touch."* He named that rule this morning; a subagent does not delete it on a t-stat. **Take it to him with the number.**

The one-line diff, if he says yes — a default change in `backtest_week.py`, no new code:

```diff
--- a/backtest_week.py
+++ b/backtest_week.py
@@
-DISASTER_STOP = os.getenv("DISASTER_STOP", "1") not in ("0", "false", "off")
+# G71: measured -0.1204R (paired, t = -5.74, n = 2,328) against no resting
+# order at all -- see research/g71_stops.md section 3. The LEVEL stop on the
+# close and the -1.25R clamp both stay; what goes is the intrabar TOUCH, which
+# is the half that contradicts "wicks stop nothing". DISASTER_STOP=1 restores
+# R2's two-stop model for the A/B.
+DISASTER_STOP = os.getenv("DISASTER_STOP", "0") not in ("0", "false", "off")
```

---

## 4. Held-out S recall — the gate that governs

`research/marks/probe_omen_test1_2026-08-27.jsonl`, 15 S / 27 A / 16 C / 42 X, scored by `research.t70_test1_score.score_all` and counted by `t24_stop_taxonomy.test1_counts` — both imported, neither reimplemented, so this table is directly comparable to T24's.

| arm | S recall | false fire | entry match | symbol-days fired on |
|---|--:|--:|--:|--:|
| `S0_shipped` | 4/15 | 16/42 | 6/58 | 34 |
| `S1_level` | 4/15 | 16/42 | 6/58 | 34 |
| `S2_candle` | 3/15 | 12/42 | 3/58 | 25 |
| `S3_pivot` | **7/15** | 31/42 | 13/58 | 67 |
| `S4_bestrr` | 3/15 | 13/42 | 4/58 | 27 |
| `D_off` | 4/15 | 16/42 | 6/58 | 34 |
| `D_075` | 4/15 | 16/42 | 6/58 | 34 |
| `D_125` | 4/15 | 16/42 | 6/58 | 34 |
| `D_150` | 4/15 | 16/42 | 6/58 | 34 |
| `D_200` | 4/15 | 16/42 | 6/58 | 34 |

**Every disaster arm is identical (4/15).** That is a correctness check, not a finding: the disaster stop is an exit, so it cannot move detection. It moving would have meant a bug.

**`S3_pivot` is the only arm that buys recall: 4/15 → 7/15.** It is strictly additive — it gains `IWM 2025-03-14`, `AAPL 2025-09-11`, `PLTR 2025-09-02` and loses nothing. But it also gains **15 false fires and loses none** (16/42 → 31/42), and it fires on **67 symbol-days against 34**. Precision among fired days: 4/34 = 11.8% before, 7/67 = 10.4% after. **The recall gain is volume, not selectivity** — S3 fires on twice as much and hits twice as many S days. McNemar on the S column is 3 gains / 0 losses, one-sided p = 0.125: suggestive, not significant on 15 cards.

Where S3's extra trades come from: the pivot stop is **2.1x wider** ($1.247 vs $0.679), so signals that used to die in `min_risk_floor` now clear it. Those 9,626 new rows book **+0.2309 mean R at 65.0% win, +2,222R total** — a genuinely positive population, just a small-R one. `S3_pivot`'s whole book totals **+3,148.8R against the shipped +1,338.6R**, at 100/105 weeks green (the best durability figure on this board) and only **0.59% of rows inside the noise band** (the best tradability figure).

So pivot structure is not a stop rule — **it is a recall lever that happens to be expressed as a stop**, and it needs a selector on top before it is a live configuration. 22 trades a day is not what he trades.

---

## 5. Sizing — "risking 1k everytime or 1.25k"

`corr(R, |entry − stop|) = −0.0130` over n = 2,436.

| stop-width decile | n | stop $ range | mean R | win% |
|--:|--:|---|--:|--:|
| 1 | 243 | 0.010 - 0.150 | +0.9272 | 49.8% |
| 2 | 244 | 0.150 - 0.220 | +0.7364 | 43.2% |
| 3 | 243 | 0.220 - 0.300 | +0.4697 | 44.8% |
| 4 | 244 | 0.300 - 0.380 | +0.6419 | 41.2% |
| 5 | 244 | 0.380 - 0.450 | +0.2835 | 42.4% |
| 6 | 243 | 0.460 - 0.550 | +0.5263 | 49.2% |
| 7 | 244 | 0.550 - 0.680 | +0.4879 | 48.6% |
| 8 | 243 | 0.680 - 0.870 | +0.3935 | 52.7% |
| 9 | 244 | 0.870 - 1.270 | +0.3456 | 52.9% |
| 10 | 244 | 1.270 - 32.800 | +0.6801 | **70.1%** |

| policy | total $ | $ risked | return on risk | max DD $ | worst trade $ |
|---|--:|--:|--:|--:|--:|
| **fixed** ($1,000 every trade) | +1,337,772 | 2,436,000 | 54.92% | **-17,132** | **-1,000** |
| contracts (one fixed contract count) | +1,097,671 | 2,130,673 | 51.52% | -15,384 | -3,000 |
| inverse (over-risk the tight stops) | +1,439,972 | 2,164,626 | **66.52%** | -32,611 | -3,000 |

**The answer is fixed $1,000, and `corr(R, |entry − stop|) = −0.013` is the reason.** Stop width predicts nothing about the R outcome, so scaling risk by it cannot add information — only leverage. Policies are priced at comparable total dollars risked, with per-trade leverage capped at 3x so a single 2-cent stop cannot own the book:

- **fixed** — 54.92% return on risk, max DD **−$17,132**, worst trade **−$1,000**.
- **contracts** (dollar risk rides the stop width) — 51.52%, DD −$15,384, worst −$3,000. Worse return *and* a worst trade three times the size. This is the failure mode of not resizing.
- **inverse** — 66.52% return on risk but max DD **−$32,611**, worst trade −$3,000. Per dollar of drawdown: fixed returns $78, inverse returns $44. The extra return is the tight-stop artefact levered up.

The decile table carries one real signal, and it is not about sizing: **win rate climbs monotonically with stop width from decile 5 (42.4%) to decile 10 (70.1%)**, while mean R stays flat. Wider stops win more often and pay less per win — the two cancel, which is exactly what a −0.013 correlation looks like when you pull it apart.

**And his actual question has a different answer than he thinks.** `1k` vs `1.25k` is not a position-sizing choice: with the shipped resting disaster stop at −1.00R the worst trade *is* exactly −$1,000 (the book's `worst` column reads −1.0000), and with it removed the worst trade is the −1.25R clamp, −$1,250. So "1k or 1.25k" **is** the disaster-stop question, and §3 says **$1,250** — take the wider max loss, because the trades that wick through −$1,000 and come back are worth more than the ones they cost.

---

## 6. What is still open

- **R2 is contradicted by measurement.** `fact_two_stops` (*"disaster stop on touch"*) is ratified and costs −0.12R at t = 5.74. Needs him, not an agent.
- **The RR selector needs a target that does not move with the stop.** The blind `entry ± 2 × risk` target makes every RR exactly 2.00 by construction. Until P21 ("is there a tracked level ≥2R away at entry?") lands, "best RR" cannot be measured on the exit that ships.
- **The tradability floor is a guess.** $0.05 is set by `G71_MIN_STOP_ABS`, and the Corwin-Schultz spread (median $0.1185) is an *upper* bound on effective cost — it is a high-low estimator running on 1-minute bars, not a quote. **The number he could give in thirty seconds — what an ATM 0DTE on NVDA is actually quoted at — would replace three assumptions in §1's tightness table.**
- **`intrabar_stop` is still the real subject**, exactly as T24 closed. It rewrites 84.8% of B&R stops onto the candle entered on, which is where 70% of his own marks sit, and it is the only reason the level-stop family is sizeable at all.

## Provenance

`research/g71_stops.py`. Ten 2-year replays (`_g71s_{S0_shipped,S1_level,S2_candle,S3_pivot,S4_bestrr,D_off,D_075,D_125,D_150,D_200}.json`, ~68 MB each, one child process per arm with the flags forced in its environment), plus `_g71s_analysis.json`, `_g71s_test1.json`, `_g71s_his.json`, `_g71s_spread.json`. Regenerate every table with `python research/g71_stops.py report`.
