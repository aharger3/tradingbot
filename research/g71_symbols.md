# G71 / symbols — which two stocks join SPY

Austin: *"for next test, we should focus on 3 stocks, spy since indecies is big, and pick 2
others. nvda and tsla is where i lean but i have graded a bujnch of those but they are always
top options volitility."*

**Answer: SPY + TSLA + AAPL. TSLA survives the data. NVDA does not — but not for the reason
he gave.** His grading-bias worry is aimed at the wrong symbol (he has over-graded TSLA, not
NVDA) and his options-volatility worry is measurably false for both (NVDA is 15th of 28 on
implied vol, TSLA 11th). What kills NVDA is redundancy: it is the most SPY-correlated single
name in the universe (0.62 to SPY, 0.73 to QQQ), so as SPY's companion it adds the least new
information of any candidate.

Scripts, all read-only, all in this directory:

```
python research/g71_symbols_census.py --json research/g71_symbols_census.json   # the ranked table
python research/g71_symbols_options.py     # contract R vs share R, per symbol, paired CI
python research/g71_symbols_money.py       # per-symbol mean R with a bootstrap bar
python research/g71_symbols_corr.py        # 09:30-11:00 return correlation matrix
python research/g71_symbols_trio.py        # every SPY + 2 trio scored
```

Book: `research/bt2y_trades.json`, generated 2026-08-29T03:14:29, 2024-08-21..2026-08-21,
500 sessions, 76,019 signals, **2,437 traded**, whole-book mean R **+0.5495 [+0.465,+0.632]**,
**25/25 green months**. Marks: every corpus `research/build_deck.py::mark_sources()` reads —
**1,147 distinct judged symbol-days**, 811 more served-but-not-graded, 1,548 seen in total.

---

## 1. The ranked table

`sig` = engine signals · `trd` = trades taken · `stop%` = median risk as % of entry ·
`rng%` = median 09:30–11:00 high-low as % of price, last 120 sessions ·
`$vol` = median 09:30–11:00 dollar volume, last 120 sessions ·
`Srec` = engine graded non-X / engine fired at all / his S days inside the book window ·
`fresh` = archived days never judged **and** never served.

| sym | pool | tier | graded | S | S% | sig | trd | meanR | win% | stop% | rng% | $vol 09:30–11:00 | Srec nonX/fire/n | arch | seen | fresh |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:--:|---:|---:|---:|
| TSLA | MAJOR_15 | core | **127** | **24** | 19% | 3395 | 170 | +0.5388 | 48.8 | 0.251 | 2.52 | $6.6B | 9/20/20 | 658 | 147 | 511 |
| QQQ | INDEX | core | 98 | **36** | 37% | 2578 | 69 | +0.5484 | 65.2 | 0.117 | 0.95 | $8.6B | 8/30/31 | 660 | 116 | 544 |
| SPY | INDEX | *excluded* | 70 | 16 | 23% | 2397 | 55 | +1.3253 | 65.5 | 0.095 | 0.61 | $8.9B | 5/14/14 | 654 | 87 | 567 |
| PLTR | MAJOR_15 | core | 55 | 14 | 25% | 3299 | 134 | +0.5259 | 47.8 | 0.273 | 3.33 | $1.9B | 2/12/12 | 657 | 73 | 584 |
| MSFT | MAJOR_15 | core | 47 | 10 | 21% | 2780 | 94 | +0.1900 | 42.6 | 0.153 | 1.77 | $3.5B | 4/10/10 | 658 | 64 | 594 |
| **NVDA** | MAJOR_15 | core | 47 | **8** | 17% | 3189 | 103 | +0.4352 | 49.5 | 0.235 | 2.08 | **$8.8B** | 4/7/7 | 658 | 64 | 594 |
| **AAPL** | MAJOR_15 | core | 46 | 13 | **28%** | 2944 | 81 | +0.6642 | **56.8** | 0.174 | 1.51 | $3.0B | 3/11/12 | 658 | 69 | 589 |
| AVGO | OTHER | exp | 43 | 7 | 16% | 3290 | 125 | +0.2783 | 40.8 | 0.220 | 2.50 | $2.1B | 2/6/6 | 506 | 54 | 452 |
| COIN | OTHER | exp | 40 | 8 | 20% | 3702 | 203 | +0.2381 | 41.4 | 0.270 | 4.23 | $0.5B | 4/8/8 | 621 | 56 | 565 |
| MU | MAJOR_15 | exp | 40 | 10 | 25% | 3311 | 147 | +0.6717 | 46.9 | 0.266 | 4.56 | **$11.0B** | 5/10/10 | 657 | 47 | 610 |
| HOOD | OTHER | exp | 37 | 9 | 24% | 3445 | 133 | +0.7452 | 45.9 | 0.283 | 3.93 | $0.7B | 4/9/9 | 530 | 47 | 483 |
| AMD | MAJOR_15 | core | 36 | 8 | 22% | 3164 | 127 | +0.6820 | 52.8 | 0.248 | 3.72 | $4.2B | **6/8/8** | 654 | 55 | 599 |
| IWM | INDEX | other | 36 | 15 | 42% | 2740 | 40 | +0.2683 | 50.0 | 0.118 | 1.11 | $2.3B | 1/13/13 | 653 | 56 | 597 |
| META | MAJOR_15 | core | 35 | 8 | 23% | 3074 | 123 | +0.5152 | 54.5 | 0.188 | 1.96 | $2.4B | 2/8/8 | 655 | 52 | 603 |
| AMZN | MAJOR_15 | core | 33 | 8 | 24% | 2926 | 79 | +0.4674 | 51.9 | 0.181 | 1.80 | $2.9B | 3/7/8 | 655 | 53 | 602 |
| BABA | OTHER | exp | 31 | 9 | 29% | 2650 | 62 | +0.5789 | 48.4 | 0.206 | 1.64 | $0.4B | 2/9/9 | 437 | 40 | 397 |
| NFLX | MAJOR_15 | exp | 31 | 4 | 13% | 3167 | 73 | +0.5182 | 46.6 | 0.183 | 2.08 | $0.9B | 0/3/3 | 529 | 40 | 489 |
| MARA | OTHER | exp | 30 | 8 | 27% | 2042 | 29 | +0.9481 | 72.4 | 0.732 | 5.33 | $0.1B | 2/6/7 | **278** | 34 | 244 |
| ORCL | MAJOR_15 | exp | 30 | 6 | 20% | 3197 | 105 | +0.4557 | 47.6 | 0.228 | 3.56 | $1.3B | 5/6/6 | 654 | 40 | 614 |
| INTC | MAJOR_15 | exp | 29 | 6 | 21% | 3086 | 69 | +0.6682 | 49.3 | 0.366 | 4.59 | $3.5B | 3/6/6 | 655 | 42 | 613 |
| CRM | OTHER | exp | 27 | 4 | 15% | 1717 | 65 | +1.3151 | 61.5 | 0.206 | 2.81 | $0.6B | 1/4/4 | **275** | 24 | 251 |
| GOOGL | MAJOR_15 | core | 27 | 6 | 22% | 2953 | 73 | +0.8695 | 58.9 | 0.191 | 1.76 | $2.5B | 2/5/6 | 654 | 46 | 608 |
| MSTR | retired | — | 24 | 5 | 21% | 0 | 0 | — | — | — | 4.04 | $0.7B | 0/0/5 | 654 | 39 | 615 |
| UBER | OTHER | exp | 23 | 6 | 26% | 1813 | 45 | +0.8801 | 51.1 | 0.210 | 2.32 | $0.3B | 2/4/6 | **274** | 26 | 248 |
| IREN | OTHER | exp | 21 | 3 | 14% | 2108 | 90 | +0.2406 | 35.6 | 0.439 | 6.24 | $0.6B | 3/3/3 | **273** | 25 | 248 |
| SOFI | OTHER | exp | 21 | 8 | 38% | 1849 | 19 | +0.1209 | 52.6 | 0.553 | 3.45 | $0.3B | 1/5/7 | **281** | 21 | 260 |
| TSM | OTHER | exp | 15 | 6 | 40% | 1733 | 61 | +0.3584 | 52.5 | 0.213 | 2.37 | $1.7B | 2/6/6 | **297** | 22 | 275 |
| SPCX | MAJOR_15 | other | 12 | 2 | 17% | 284 | 22 | +0.7845 | 50.0 | 0.430 | 1.95 | $0.0B | 1/2/2 | 531 | 13 | 518 |
| ACHR | MAJOR_15 | other | 11 | 3 | 27% | 3186 | 41 | +0.5940 | 65.9 | 0.711 | 4.36 | $0.0B | 0/3/3 | 653 | 28 | 625 |
| GOOG | OTHER | other | 10 | 0 | 0% | 0 | 0 | — | — | — | 2.47 | $1.9B | 0/0/0 | **4** | 4 | 0 |
| DIA / ARM / SMCI / RIVN / QCOM | not in book | | 8/4/2/1/0 | 3/2/1/0/0 | | 0 | 0 | — | — | — | | | 0/582/280/261/21 | | |

**A grade-extraction hole was fixed to build this table.** `probe_s_sweep_2026-08-28.jsonl`
writes `grade:"none"` on all 100 rows; the judgement lives in `answers.s == ["s"|"no"]`.
Reading the `grade` field in `_GRADE_KEYS` order scores the entire held-out S sweep as a
refusal and loses all 34 S days. `g71_symbols_census.grade_of()` (`research/g71_symbols_census.py:44`)
makes the `answers` dict outrank the `grade` field. `build_deck.marked_card_ids()` is **not**
affected — it only asks *was this judged*, and `answered` already catches it — but any future
per-grade read of that file must use the answers dict.

---

## 2. What actually separates symbols, and what does not

### Money does not separate them. At all.

`research/g71_symbols_money.py`. Every one of the 28 symbols' 95% bootstrap CI on mean R
**overlaps the whole book's [+0.465, +0.632]**. SPY's headline +1.3253 carries the bar
[+0.570, +2.229] on 55 trades; MSFT's +0.1900 carries [−0.154, +0.582] on 94. There is no
symbol in this universe that is measurably better or worse than the book average.

**Do not pick companions on mean R.** "SPY does +1.33R" is 55 trades and a bar three times
the effect — the same error `omen-error-bar-exceeds-arms` already records.

### Redundancy does separate them, decisively.

`research/g71_symbols_corr.py`, 09:30–11:00 return correlation over 654+ overlapping sessions:

| | SPY | QQQ | TSLA | NVDA | AAPL | MU | AMD | sd of window return |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY | 1.00 | 0.91 | 0.48 | **0.62** | **0.39** | 0.49 | 0.51 | 0.43% |
| QQQ | 0.91 | 1.00 | 0.51 | **0.73** | 0.40 | 0.60 | 0.61 | 0.64% |
| TSLA | 0.48 | 0.51 | 1.00 | 0.37 | **0.17** | 0.22 | 0.29 | 2.04% |
| NVDA | 0.62 | 0.73 | 0.37 | 1.00 | 0.19 | 0.49 | 0.55 | 1.71% |
| AAPL | 0.39 | 0.40 | 0.17 | 0.19 | 1.00 | 0.10 | 0.15 | 1.04% |
| MU | 0.49 | 0.60 | 0.22 | 0.49 | 0.10 | 1.00 | 0.51 | 2.23% |

**NVDA is a levered SPY in this window** (0.62 to SPY, 0.73 to QQQ — the highest of any
single name tested). **AAPL is the most orthogonal thing available** (0.39 to SPY, 0.17 to
TSLA). And the three volatility bands come out clean: SPY 0.43% / AAPL 1.04% / TSLA 2.04%.
Swap AAPL for NVDA and you get 0.43 / 1.71 / 2.04 with a 0.62 correlation between two of the
three — one band covered twice and the low band shadowed.

### S-day inventory separates them; S *rate* does not.

TSLA 24 S days · AAPL 13 · MU 10 · MSFT 10 · NVDA 8 · AMD 8. Those are counts, and counts are
what a recall gate spends. The *rates* are not distinguishable — NVDA 8/47 vs AAPL 13/46 is
z = 1.31, NVDA vs TSLA is z = 0.29. Report the inventory, not the rate.

---

## 3. Every SPY trio, scored

`research/g71_symbols_trio.py`. `heldoutS` = how many of the 34 held-out S days in
`probe_s_sweep_2026-08-28.jsonl` the trio contains. `frSILENT` = fresh, never-served days on
which the engine is silent, inside the book window. Top rows by S-days-on-file, plus the
comparisons that matter.

| trio | n | mean R | 95% CI | win% | green | graded | S | heldout S | fr FIRE | fr SILENT | max r |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY+TSLA+QQQ | 294 | +0.6882 | [+0.450,+0.944] | 55.8 | 21/25 | 295 | 76 | 2 | 1145 | 33 | **0.91** |
| **SPY+TSLA+AAPL** | 306 | +0.7134 | [+0.479,+0.973] | 53.9 | 20/25 | 243 | **53** | **0** | 1175 | **38** | **0.48** |
| SPY+TSLA+PLTR | 359 | +0.6545 | [+0.434,+0.894] | 51.0 | 21/25 | 252 | 54 | 4 | 1176 | 34 | 0.49 |
| SPY+TSLA+MU | 372 | +0.7076 | [+0.470,+0.961] | 50.5 | 20/25 | 237 | 50 | 1 | 1201 | 34 | 0.49 |
| **SPY+TSLA+NVDA** | 328 | +0.6382 | [+0.401,+0.891] | 51.8 | **17/25** | 244 | 48 | 1 | 1190 | 32 | **0.62** |
| SPY+TSLA+AMD | 352 | +0.7134 | [+0.491,+0.940] | 52.8 | 20/25 | 233 | 48 | 0 | 1188 | 32 | 0.51 |
| SPY+TSLA+ORCL | 330 | +0.6435 | [+0.408,+0.900] | 51.2 | **22/25** | 227 | 46 | 0 | 1207 | 32 | 0.48 |
| SPY+AAPL+ORCL | 241 | +0.7242 | [+0.437,+1.032] | 54.8 | **24/25** | 146 | 35 | 0 | 1262 | 41 | 0.45 |
| SPY+NVDA+GOOGL | 231 | +0.7844 | [+0.481,+1.100] | 56.3 | **24/25** | 144 | 30 | 1 | 1266 | 37 | 0.62 |

Every CI in that table overlaps every other. The columns that decide are **green**,
**S**, **heldout S**, **fr SILENT** and **max r**.

`SPY+TSLA+NVDA` is the worst TSLA trio on two of them: 17/25 green months (every other TSLA
trio is 19–22) and 0.62 max correlation (every other TSLA trio is 0.48–0.57).

---

## 4. His two worries, measured

### "I have graded a bunch of those"

**Half right, and aimed at the wrong symbol.**

* TSLA: **127** judged symbol-days — 11.1% of the entire 1,147-day corpus, more than any other
  symbol, and it includes a whole 60-card TSLA-only deck
  (`research/marks/deck_marks_tsla_2026-08-20.jsonl`).
* NVDA: **47** — the same as MSFT, fewer than PLTR (55), and less than half QQQ's 98.

**But supply is not the constraint anywhere.** Never-judged, never-served days inside the
book window: TSLA 368, NVDA 441, AAPL 432, SPY 413, MU 454. A 60-card deck needs 60. There
are six-plus decks of fresh TSLA left, and TSLA is the *scarcest* candidate.

The real repeat risk is the **silent half**, not the fire half — see the blocker below.

### "They are always top options volatility"

**False for both, on the repo's own volatility measure.** `research/g71_symbols_options.py`
prices every traded row through `research/t7_real_contracts.py`'s Contract class — prior
session's Parkinson sigma × 1.2, no same-day input (the leak that retracted T2).

Ranked by that IV: IREN 0.98 · SPCX 0.80 · ACHR 0.69 · MARA 0.69 · INTC 0.58 · COIN 0.57 ·
SOFI 0.57 · HOOD 0.52 · MU 0.48 · PLTR 0.47 · **TSLA 0.45** · AMD 0.43 · AVGO 0.42 · ORCL 0.40
· **NVDA 0.34** · UBER 0.32 · CRM 0.31 · TSM 0.30 · BABA 0.28 · GOOGL 0.27 · META 0.27 ·
NFLX 0.26 · AMZN 0.26 · AAPL 0.22 · MSFT 0.20 · IWM 0.17 · QQQ 0.17 · SPY 0.12.

TSLA is 11th of 28. NVDA is 15th — below AMD, AVGO and ORCL. They are top by options
*volume*, which is a liquidity fact and not in this repo; they are mid-pack on *volatility*.

---

## 5. Does R-on-shares misprice NVDA/TSLA? **No — and it is the opposite of what he fears.**

Paired contract-minus-share R, ladder convention, per symbol, 95% bootstrap CI on the paired
difference (`research/g71_symbols_options.py`, 2,309 of 2,437 traded rows priced):

| sym | n | IV | ATM 0DTE premium %spot | contract R | share R | Δ | 95% CI | different? |
|---|---:|---:|---:|---:|---:|---:|---|:--:|
| MU | 136 | 0.48 | 1.17% | +0.9762 | +0.6803 | **+0.2959** | [+0.027,+0.755] | **YES** |
| UBER | 39 | 0.32 | 0.77% | +1.1591 | +0.8217 | **+0.3375** | [+0.007,+0.764] | **YES** |
| GOOGL | 70 | 0.27 | 0.62% | +1.1929 | +0.9497 | **+0.2433** | [+0.104,+0.420] | **YES** |
| MARA | 29 | 0.69 | 1.67% | +0.6319 | +0.9481 | **−0.3162** | [−0.569,−0.081] | **YES** |
| SPCX | 21 | 0.80 | 1.79% | +0.8803 | +0.7495 | +0.1309 | [+0.017,+0.272] | YES |
| **TSLA** | 162 | 0.45 | 1.11% | +0.6180 | +0.5696 | **+0.0485** | [−0.028,+0.125] | **no** |
| **NVDA** | 94 | 0.34 | 0.82% | +0.2839 | +0.3412 | **−0.0573** | [−0.172,+0.046] | **no** |
| SPY | 54 | 0.12 | 0.29% | +1.5033 | +1.3683 | +0.1350 | [−0.132,+0.490] | no |
| AAPL | 78 | 0.22 | 0.54% | +0.7034 | +0.6847 | +0.0187 | [−0.179,+0.234] | no |
| QQQ | 67 | 0.17 | 0.40% | +0.5807 | +0.5153 | +0.0654 | [−0.035,+0.172] | no |

**Share-scored R is a fine unit for NVDA, TSLA, SPY, AAPL and QQQ.** The names where the
contract measurably differs are MU (+0.30R), UBER (+0.34R), GOOGL (+0.24R) and MARA (−0.32R).
The mechanism runs the other way from his intuition: high IV inflates the premium, which
inflates the R *denominator*, which cancels most of the convexity — the highest-IV names are
where the contract helps *least*. The universe-level version of this is T7's null result
(+0.0941R against a ±0.1298R bar, `research/t7_real-contracts.md`).

### One real instrument fact, and it favours SPY only

The t7 Alpaca cache is an accidental census of **which days a 0DTE contract even existed**: a
strike candidate with real bars = a same-day expiry, an empty response = none. By weekday:

| | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|
| SPY + QQQ + IWM | 3/3 | 0/0 | 8/8 | 3/3 | 4/4 |
| TSLA | 2/16 | 0/14 | 3/17 | 1/17 | **11/11** |
| NVDA | 1/6 | 0/7 | 5/9 | 2/16 | **10/10** |
| COIN | 0/22 | 0/21 | 0/19 | 2/21 | **21/21** |
| PLTR / HOOD | 0/32 | 0/28 | 0/36 | 0/26 | **30/30** |

**Single names have a 0DTE only on Fridays; the index ETFs have one every session** — 18/18
across four different weekdays. If the traded instrument really is 0DTE ATM, four fifths of
every single-name signal has no such contract, and the trade is a 1–4 DTE with different
theta. This applies equally to NVDA, TSLA, AAPL and MU, so it does not separate the
companions — but it is a reason the index anchor is doing more work than "indices is big."

---

## 6. Recommendation

**SPY + TSLA + AAPL.**

* **TSLA survives, on inventory.** 24 S days on file (most of any single name), 127 judged
  symbol-days, full 658-session archive, 170 trades, $6.6B in the window, and the **lowest
  SPY correlation of any large single name (0.48)**. His bias worry is real as a fact but is
  an argument *for* TSLA: the recall gate is scored against his S days and TSLA supplies the
  largest single-name pile of them, with 368 fresh in-window days still unserved.
* **AAPL is the second companion.** 13 S days (2nd among the mega-caps), the highest S rate
  of the full-archive names (28%), 0.39 to SPY and **0.17 to TSLA** — the most orthogonal
  pair available — 56.8% win on 81 trades, a full 658-session archive, and it fills the
  volatility band between SPY (0.43%) and TSLA (2.04%) at 1.04%. It also contributes the most
  fresh silent days of any TSLA trio bar INTC.
* **NVDA does not survive.** 8 S days (fewest of the mega-caps), 0.62 to SPY and 0.73 to QQQ
  (a levered index in this window), 15th of 28 on IV, and the SPY+TSLA+NVDA trio posts the
  worst durability of any TSLA trio (17/25 green months vs 20–22).
* **Alternate, if he wants a second high-volatility name rather than band coverage: MU.**
  Highest window dollar volume in the universe ($11–12B), 10 S days, 147 trades, IV 0.48.
  Cost: it duplicates TSLA's volatility band and its contract R is **+0.296R above** its share
  R (CI excludes zero), so MU is the one candidate where R-on-shares *does* misprice the
  trade and every published number for it would need the contract skin.

---

## 7. Four things that break when the universe narrows to three

1. **Durability — the only gate currently MET — breaks.** The whole book is **25/25 green
   months** on 2,437 trades. **No trio reaches 25/25.** Best is 24/25 (SPY+AAPL+ORCL,
   SPY+NVDA+GOOGL); SPY+TSLA+AAPL is 20/25; SPY+TSLA+NVDA is 17/25. This is thinning, not
   decay — 306 trades over 25 months is 12 a month — but the gate as written
   (`DIRECTION.md`, every month green) will read RED for every trio on day one. Decide before
   the test whether durability is measured on the trio or stays on the full universe.

2. **The held-out recall sample does not survive the cut.** `probe_s_sweep_2026-08-28.jsonl`'s
   34 S days are spread across 32 symbols, 1–9 cards each. **SPY+TSLA+AAPL contains 0 of
   them. SPY+TSLA+NVDA contains 1.** The 52.9% (18/34) recall baseline in `DIRECTION.md`
   **cannot be carried into a 3-symbol test** — a fresh held-out deck must be built and
   graded on the chosen trio before any before/after claim is possible. This is the first
   thing to do, not the last.

3. **The mixed-deck silent half runs out after one deck.** The standard is 30 FIRE + 30
   SILENT (`Projects/omen-decks.md`). Fresh, never-served silent days inside the book window:
   SPY 23, AAPL 12, TSLA **3**, NVDA 6, MU 8 — 38 for SPY+TSLA+AAPL, 32 for SPY+TSLA+NVDA.
   That is **one** mixed deck, and then the standard breaks. FIRE cards are not the problem
   (1,175 fresh).

4. **SPY is switched off in the backtest tier.** `universe.py:80` — `INCLUDE_SPY_IN_BACKTEST
   = False`, on a 2026-07-11 "0-for-5" rationale that OMEN 6 ticket 04 already flagged as
   five trades and not a sample. If SPY anchors the next test, this flips, and six modules'
   published numbers move with it. Ratification is Q12 in `.scratch/omen-6/qa-queue.md` — it
   is Austin's call, not an agent's.

### Diff for #4, when he ratifies it — NOT applied

```diff
--- a/universe.py
+++ b/universe.py
@@
-# NOT flipped unilaterally: six backtest modules import CORE_SYMBOLS and every
-# published number would move. Ratification is Q12 in
-# .scratch/omen-6/qa-queue.md. Flip this one flag to include SPY everywhere.
-INCLUDE_SPY_IN_BACKTEST = False
+# NOT flipped unilaterally: six backtest modules import CORE_SYMBOLS and every
+# published number would move. Ratification is Q12 in
+# .scratch/omen-6/qa-queue.md. Flip this one flag to include SPY everywhere.
+#
+# 2026-08-29 (G71/symbols): Austin picked SPY as the anchor of the 3-symbol
+# test -- "spy since indecies is big". SPY is 70 of the 1,147 judged
+# symbol-days and 16 of his S days; a recall number computed over
+# CORE_SYMBOLS without it ignores that whole pile. research/g71_symbols.md.
+INCLUDE_SPY_IN_BACKTEST = True
+
+# The 3-symbol focus set for the next test (G71/symbols, research/g71_symbols.md).
+# Chosen on S-day inventory + 09:30-11:00 return orthogonality, NOT on mean R:
+# every symbol's mean-R CI overlaps the whole book's [+0.465,+0.632].
+FOCUS_3 = ["SPY", "TSLA", "AAPL"]
```

---

## 8. Provenance

Judgement rows read, per corpus (`build_deck.mark_sources()` order, counts from
`g71_symbols_census.py`): `austin_marks_v7.jsonl` 478 · `blind_marks_all.jsonl` 260 ·
`recovered_reviews.jsonl` 176 · `austin_verdicts.json` 162 · `marks_clean.jsonl` 117 ·
`marks/probe_omen_test1_2026-08-27.jsonl` 100 · `marks/probe_s_sweep_2026-08-28.jsonl` 100 ·
`marks/probe_master_2026-08-29.jsonl` 90 · `marks/deck_marks_tsla_2026-08-20.jsonl` 60 ·
`mark_batch_02_grades.jsonl` 60 · `marks/deck_marks_h2_3lane_2026-08-28.jsonl` 59 ·
`marks/deck_marks_index_2026-08-19.jsonl` 59 · `marks/probe_master_homework_2026-08-26.jsonl` 51 ·
`mark_batch_04_grades.jsonl` 35 · `mark_batch_03_regrades.jsonl` 29 ·
`derived_marks_v2.jsonl` 18 · `marks/probe_autopsy_2026-08-23.jsonl` 15 ·
`derived_marks_v1.jsonl` 14 · `marks/probe_head2head_2026-08-24.jsonl` 9.

**No mark file was written, moved or modified.** Outputs of this track:
`research/g71_symbols_census.{py,json}`, `research/g71_symbols_options.{py,json}`,
`research/g71_symbols_money.{py,json}`, `research/g71_symbols_corr.py`,
`research/g71_symbols_trio.{py,json}`, this file.

**Known caveat — the book on disk is not the book `DIRECTION.md` quotes.** That file reports
**2,595 traded / 43.1% win / +0.5481R**; `research/bt2y_trades.json` as it stands holds
**2,437 traded**, and on those rows `out == "win"` is **49.2%** (1,198 win / 1,222 loss /
17 scratch) while `r > 0` is **49.7%**, mean R **+0.5495**. `research/t7_real-contracts.md`
pins a third state of the same file (1,016 traded). Tracks have landed since each was
written. Every number in this report is from the 2,437-row file dated 2026-08-29T03:14:29 and
nothing here is comparable to a headline computed on a different one. The per-symbol win
column uses `r > 0` throughout, so it is internally consistent, but it is not the money
gate's statistic.

`python research/regression_gate.py` → **PASS** (any_signal 83 vs baseline 75, s_grade 13 vs
5, no baseline-fired mark went silent). This track added files only; no engine file, no mark
file, and no baseline was touched.
