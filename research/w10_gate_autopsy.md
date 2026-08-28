# W10 — the gate autopsy: the days Austin traded and the engine refused

Produced by `research/w10_gate_autopsy.py`. Every number below names the command that made it, and the reproduce block at the bottom runs all of them. Nothing here changes a default, adds a flag, or re-freezes the forward book.

Carry the **narrow error bar, ±0.0095 R**. The wide ±1.5799 R bar was retired 2026-08-28 when Austin ruled that a stop needs a close and the entry candle's own close counts.

---

## 0. What this is measured against, and what it is not

`data/tradezella_trades.csv`: **350 rows, all of them tagged `Account Name = "Backtesting"`.** This is Austin replaying the tape by hand and logging what he would have taken. It is **not** a broker fill record and it is **not** non-hindsight — he could see the day when he logged it. It is held out from the *engine*, which no rule was ever fitted to, and that is the whole of its value. Every recall number in this file is recall against a hand-replay book, never against execution ground truth.

| | |
|---|---|
| rows | 350 over **271 symbol-days** |
| symbols | 2 — NVDA 186, TSLA 164 |
| playbook | 1 — "Break and Retest , One Candle Rule" on all 350 |
| span | 2024-01-03 → 2025-01-30 |
| archive coverage | NVDA and TSLA each hold 658 archived sessions from 2024-01-02; **0 of his 271 symbol-days are missing bars** |

`python research/w10_gate_autopsy.py coverage` prints that check. No denominator below is discounted for a missing session, and no bar was fetched — `data_archive/` only.

**Two populations, never merged.** His book is 2024-01 → 2025-01 on two symbols. The 2-year money book (`backtest_2y.py --days 730`) is 2024-08-21 → 2026-08-21 on 28. Section 3 measures his days; section 4 prices gates on the 2-year book. They are stated side by side and are never averaged.

## 1. The join reproduces W6 exactly, and that is the licence for the rest

`w10_gate_autopsy.py` invents no second definition of "match". `parse_rows` / `derive_stop` come from `research/w6_tz_recall.py`; `run_day`, `rth_candles` and `TOL` (= **±2 bars**) from `research/t4_engine_recall.py`, the same convention `research/t70_test1_score.py` uses.

The autopsy replays each day through `_ProbeRunner`, a subclass of `t4_engine_recall.CaptureRunner` whose accept logic is byte-identical to the one W6 measured `fired` with; everything added is a read. `python research/w10_gate_autopsy.py funnel` **asserts** that the instrumented engine reproduces W6's published counts and refuses to write its output otherwise:

| | W6 (`26ba3f48`) | this replay |
|---|---|---|
| symbol-days scored | 271 | 271 |
| engine **fired** | 129 / 271 | **129/271 = 48%** |
| engine **saw a signal** | 261 / 271 | **261/271 = 96%** |
| his rows on a day it fired | 173 / 350 | 173/350 = 49% |

So the gap W6 named is real and this file is measuring the same gap: **132 symbol-days where the engine found the setup and then threw it away**, plus **10** where nothing reached routing at all.

## 2. The 132 refused days: what the engine actually did

On those 132 days the engine routed **495 distinct setup-ideas** (median 3.5 per day, max 10) and accepted none of them:

| terminal status | signals | share |
|---|---:|---:|
| `skipped_d` | 486 | 98.2% |
| `skipped_tight` | 9 | 1.8% |
| **total** | **495** | |

**98.2% of the refusals are `skipped_d`** — the signal was graded `X` (`TradeGrade.D`, `omen_bot.py:33` aliases the two) before routing could consider it. So this is not a routing problem, a dedupe problem or a no-repeat problem. It is a **grading** problem, and the grade is being forced by geometry, not by price action.

Two engine gates that could have killed a signal before it ever reached routing were instrumented and killed **nothing** on this set: `session_extreme_veto` (`signal_runner.py:1562`) is inert because `SESSION_EXTREME_FRAC` ships at **0.0**, and the retired-setup veto (`signal_runner.py:1698`) removed no signal from a day that had no other. `--selfcheck` asserts both defaults.

### And the refusal is blind to his outcome

| his rows | n | mean R | **median R** | win rate |
|---|---:|---:|---:|---:|
| on days the engine FIRED | 173 | +0.5838 | **+1.3503** | 51% |
| on days the engine REFUSED | 176 | +0.5936 | **+1.7089** | 51% |

**The half of his book the engine throws away has a HIGHER median R than the half it keeps.** The gate is not filtering his losers out; it is cutting his book roughly in half at random with respect to the result. Goal 0 of the master spec is the median R, so this is the worst possible shape for the error to have.

## 3. Which gate kills — ranked

Each refused signal is charged to the **proximate** killer: the last thing in the engine's own evaluation order that had to be true for the signal to be refused. `attribute()` is unit-tested in `--selfcheck` on the ordering that matters (the risk floor is evaluated *after* the pattern grader's D, so a row failing both is charged to the floor).

`days` is non-exclusive: a day is counted for a gate when that gate kills at least one of the day's signals. A day usually has several.

**One caveat on this table and it is why the replay below is the authoritative column.** The signal list is deduped the way `t4_engine_recall` / W6 dedupe it — one row per (setup, direction, level) per 30 bars, keeping the FIRST occurrence. So a setup-idea that was killed by the risk floor at 09:41 and by the tight-stop skip at 10:12 is charged once, to the floor. The counts below are therefore *first-sighting* counts, not total kills, and they under-count the gates that act late. The `alone` replay does not have that problem: it re-runs the engine.

| gate | source | signals | **his days killed** | share of the 132 |
|---|---|---:|---:|---:|
| `min_risk_floor` | `signal_runner.py:1963/:2201` | 401 | **127** | 96% |
| `htf_bias_veto` | `omen_bot.py:210` | 49 | **38** | 29% |
| `hard_risk_50c` | `signal_runner.py:2041/:2065/:2096/:2264/:2287/:2313` | 25 | **22** | 17% |
| `min_viable_stop` | `signal_runner.py:1299` | 9 | **8** | 6% |
| `wide_stop_0p4` | `signal_runner.py:2072/:2292` | 9 | **8** | 6% |
| `pa_grade_D` | `omen_bot.py:218` | 2 | **2** | 2% |

### The `alone` column is a replay, not an inference

Each gate is lifted **one at a time** — every other gate, upstream and downstream, still in force — and the 271 days are replayed. `recovered` counts days that go from refused to fired. Each arm is its own child process, so no arm inherits another's patch.

| arm | what is lifted | fired days | **recovered** | his rows on a fired day |
|---|---|---:|---:|---:|
| `none` | control -- HEAD, nothing lifted | 129/271 = 48% | — | 173/350 = 49% |
| `floor` | min_risk_floor: `max(0.10, 0.0015*close)` never fires | 164/271 = 61% | **+35** | 216/350 = 62% |
| `htf_veto` | HTF_BIAS_VETO=0 (omen_bot.py:200) -- an opposed daily bias no longer forces D | 169/271 = 62% | **+40** | 226/350 = 65% |
| `pa_d` | _grade_pa's D becomes C (alert tier), the HTF veto untouched | 140/271 = 52% | **+11** | 186/350 = 53% |
| `mvs` | _min_viable_stop always True -- the whole tight-stop skip lifted | 151/271 = 56% | **+22** | 199/350 = 57% |
| `stop_range` | STOP_RANGE_MULT 0.75 -> 0.0; the 0.5%/$0.20 clause of _min_viable_stop stays | 131/271 = 48% | **+2** | 176/350 = 50% |
| `level_cap` | LEVEL_BLOCK_CAP=False -- a level in the 2R path no longer caps to C | 129/271 = 48% | — | 173/350 = 49% |
| `counter_trend` | the counter-day-trend cap to C in _calibration_grade lifted, B floor kept | 129/271 = 48% | — | 173/350 = 49% |
| `retired` | TRADE_RETIRED_SETUPS=1 -- FVG and FLAG signals reach routing | 129/271 = 48% | — | 173/350 = 49% |

**The two rankings disagree, and the disagreement is the finding.** By proximate kills the floor is first by a mile (127 days to 38). By what actually recovers a day when lifted alone, `htf_veto` is first (+40 to +35). Both are true: the floor is evaluated on more signals, but on most of the days it kills, every OTHER signal of the day also fails something, so lifting the floor alone does not open the day. The HTF veto kills fewer signals and opens more days because the signals it kills are ones whose geometry already cleared the floor.

And they are nearly **disjoint**, so they add rather than overlap:

| set of refused days recovered | n | share of the 132 |
|---|---:|---:|
| `floor` | 35 | 27% |
| `htf_veto` | 40 | 30% |
| `mvs` | 22 | 17% |
| `pa_d` | 11 | 8% |
| `floor` ∩ `htf_veto` | **3** | 2% |
| **union of all four** | **84** | **64%** |

Lifting all four together (not measured as one arm — this is the union of four single-gate replays, an upper bound) would take day recall from 129/271 = 48% to 213/271 = 79% of his book.

Three suspected gates recover **nothing** on this set and should stop being suspected: `LEVEL_BLOCK_CAP`, the counter-day-trend cap in `_calibration_grade`, and the retired-setup veto — 0 days each. `STOP_RANGE_MULT` (0.75, another of the audit's unstated constants) recovers **2**; the tight-stop skip that reads it only matters as the whole `_min_viable_stop` (+22), and its other clause — 0.5% of entry or $0.20 of premium — is doing that work, not the 0.75.

### What the failing value actually looks like

Ten of the 132, chosen as the first ten by date, showing the signal closest to his own entry bar:

| symbol | day | his entry | engine's nearest routed signal | killing gate | the value that failed |
|---|---|---|---|---|---|
| NVDA | 2024-01-03 | 09:43 call | break_and_retest call @09:43 (+0 bars) | `min_risk_floor` | risk $0.0100 < floor $0.1000 (close $48.04) |
| NVDA | 2024-01-04 | 09:43 put | break_and_retest put @09:45 (+2 bars) | `min_risk_floor` | risk $0.0042 < floor $0.1000 (close $47.75) |
| NVDA | 2024-01-05 | 09:34 call | break_and_retest call @10:13 (+39 bars) | `min_risk_floor` | risk $0.0070 < floor $0.1000 (close $48.84) |
| NVDA | 2024-01-08 | 09:38 call | break_and_retest call @10:11 (+33 bars) | `min_risk_floor` | risk $0.0420 < floor $0.1000 (close $51.34) |
| NVDA | 2024-01-10 | 10:16 call | break_and_retest call @10:39 (+23 bars) | `min_risk_floor` | risk $0.0300 < floor $0.1000 (close $54.20) |
| NVDA | 2024-01-11 | 09:49 put | break_and_retest call @10:32 (+43 bars) | `min_risk_floor` | risk $0.0047 < floor $0.1000 (close $54.53) |
| NVDA | 2024-01-16 | 09:40 call | break_and_retest call @09:43 (+3 bars) | `min_risk_floor` | risk $0.0890 < floor $0.1000 (close $55.61) |
| NVDA | 2024-02-01 | 10:15 call | break_and_retest call @10:38 (+23 bars) | `min_risk_floor` | risk $0.0060 < floor $0.1000 (close $62.35) |
| NVDA | 2024-02-07 | 10:06 call | one_candle_rule call @09:53 (-13 bars) | `hard_risk_50c` | stock_risk $0.1284 < $0.50 |
| NVDA | 2024-02-09 | 09:54 call | break_and_retest call @10:00 (+6 bars) | `min_risk_floor` | risk $0.0680 < floor $0.1062 (close $70.81) |

### The gate that kills: `max(0.10, 0.0015 × close)`

`signal_runner.py:1963/:2201` — the call block and the put block:

```python
if floor_reference_risk(entry, stop, current.close, structural_stop,
                        True) < max(0.10, 0.0015 * current.close):
    grade = TradeGrade.D
```

| | value |
|---|---|
| signals killed on his days | **401** |
| setups | {'break_and_retest': 401} — **the floor is only evaluated on break-and-retest** |
| measured risk, median | **$0.0600** |
| measured risk, quartiles | $0.0280 / $0.1199 |
| the floor it is tested against, median | $0.1939 |
| measured risk ÷ floor, median | **0.310** |
| rows where `entry == stop` exactly | 9 |
| binding leg: flat `$0.10` / relative `0.0015 × close` | 13 / 388 |

**The engine is measuring a one-to-six-cent stop on a $50–$250 stock.** That is not what the setup's geometry says; it is what `fill_price` leaves behind. `research/g12_recall_regression.md` named the mechanism and it is the same one here: the T3(b) intrabar fill back-dates the entry onto the broken level, and for a break-and-retest **the level IS the stop** (`BNR_STOP_MODE="level"`), so the post-fill `stock_risk` collapses toward zero and then fails a floor that was written for the pre-fill geometry.

**Both constants in that line are ours, not his.** `research/hallucination-audit.md` lists `B&R_MIN_RISK = 0.0015 * close` under UNMENTIONED Constants, importance **HIGH — "gates grade D"**, and the `$0.50` flat floor on the other setups under the same heading with **"NO A/B"**. The relative leg is the one that binds here (388 of 401).

Sensitivity, on his days — how much of the constant is doing the work:

| a flat floor of | signals it still kills | refused days that get a signal past it |
|---|---:|---:|
| $0.01 | 47 of 401 | 121 of 132 |
| $0.02 | 75 of 401 | 120 of 132 |
| $0.03 | 107 of 401 | 116 of 132 |
| $0.05 | 182 of 401 | 101 of 132 |
| $0.10 | 285 of 401 | 68 of 132 |

Even a **one-cent** floor readmits 121 of the 132 days. The constant is not marginally wrong for this population; the quantity it measures is.

## 4. Pricing the top gates — held-out first, then the money book

### 4a. The 100 held-out OMEN Test 1 cards — the only false-fire denominator there is

The TradeZella book cannot price a false fire: every row in it is a trade he took, so it has no X rows and no refusals. `research/marks/probe_omen_test1_2026-08-27.jsonl` does, and `research/t70_test1_score.py::score_all` is the scorer — imported, not reimplemented. Master spec §2: **held out beats in-sample, and is reported first.**

| arm | **held-out S recall** | **false fire on his X days** | entry match | day precision |
|---|---|---|---|---|
| `none` (control) | 3/15 = 20% | 12/42 = 29% | 4/58 = 7% | 15/27 = 56% |
| `floor` | 3/15 = 20% | 25/42 = 60% | 6/58 = 10% | 25/50 = 50% |
| `htf_veto` | 4/15 = 27% | 18/42 = 43% | 4/58 = 7% | 20/38 = 53% |
| `mvs` | 4/15 = 27% | 13/42 = 31% | 5/58 = 9% | 17/30 = 57% |
| `pa_d` | 3/15 = 20% | 14/42 = 33% | 4/58 = 7% | 17/31 = 55% |

Deltas against the control, S recall first because recall governs (ballot q20):

| arm | held-out S recall | false fires | verdict |
|---|---:|---:|---|
| `floor` | +0 | +13 | **false fires bought, no recall** |
| `htf_veto` | +1 | +6 | **recall bought at a false-fire cost** |
| `mvs` | +1 | +1 | **recall bought at a false-fire cost** |
| `pa_d` | +0 | +2 | **false fires bought, no recall** |

This is the number that decides whether any of section 3's recoveries is worth having, and it is measured on cards the engine has never been shown. Every in-sample recall figure measured 2026-08-27 bought exactly zero held-out recall (`research/omen6_backtest_truth.md`); that history is why this table comes before the money table and not after it.

**Read alongside section 3, this is the whole trade-off in one line.** On his own book the four arms recover 35, 40, 22 and 11 of the 132 refused days. On the held-out cards the same four buy 0, 1, 1 and 0 S days, and cost 13, 6, 1 and 2 false fires. **Nothing in this file is a free win**, and the two gates with the largest claim on his days — the risk floor and the HTF veto — are also the two with the worst held-out exchange rate. `mvs` is the only arm whose false fires stay flat, and section 4b shows it takes trades AWAY on the shipped router.

Recall governs (ballot q20), so a +1 S day against +6 false fires is not automatically a loss — but it is a decision, not a measurement, and this file does not make it.

### 4b. The 2-year money book

Control arm: `python backtest_2y.py --days 730`, unmodified HEAD, 2024-08-21 → 2026-08-21, 500 sessions, 28 symbols.

| arm | what is lifted | signals | traded | mean R | **median R** | win | months green | **untakeable rows** |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `none (control)` | — | 45193 | 1017 | +0.9551 | **+0.5660** | 53.4% | 23/25 | 22 (2.2%) |
| `floor` | min_risk_floor: `max(0.10, 0.0015*close)` never fires | 45197 | 4351 | +6.1298 | **+0.0000** | 47.3% | 25/25 | 3522 (80.9%) |
| `htf_veto` | HTF_BIAS_VETO=0 (omen_bot.py:200) -- an opposed daily bias no longer forces D | 45193 | 1978 | +0.8771 | **+0.5105** | 51.9% | 25/25 | 50 (2.5%) |
| `mvs` | _min_viable_stop always True -- the whole tight-stop skip lifted | 45193 | 1005 | +0.9434 | **+0.5510** | 53.1% | 23/25 | 22 (2.2%) |

`untakeable` is g13's proxy, not a new one: the row must clear the engine's OWN floor on the geometry `backtest_week` sizes 1R on (`RISK_DOLLARS / |entry − stop|`). A book that is mostly untakeable has a mean R made of divisions by near-zero, and its **median** is the only column worth reading.

| arm | trades **added** | trades **removed** | the ADDED trades: mean R | **median R** | win | untakeable |
|---|---:|---:|---:|---:|---:|---:|
| `floor` | **3478** | 144 | +7.3107 | **+0.0000** | 45.7% | 3472 (99.8%) |
| `htf_veto` | **961** | 0 | +0.7945 | **+0.3410** | 50.4% | 28 (2.9%) |
| `mvs` | **0** | 12 | — | — | — | — |

- **`floor`**: whole-book mean R +0.9551 → +6.1298 (**+5.1747**, 545× the carried ±0.0095 R bar), median +0.5660 → +0.0000, months green 23/25 → 25/25.
- **`htf_veto`**: whole-book mean R +0.9551 → +0.8771 (**-0.0780**, 8× the carried ±0.0095 R bar), median +0.5660 → +0.5105, months green 23/25 → 25/25.
- **`mvs`**: whole-book mean R +0.9551 → +0.9434 (**-0.0117**, 1× the carried ±0.0095 R bar), median +0.5660 → +0.5510, months green 23/25 → 23/25.

**A note the two populations make necessary.** The section-3 replay routes through `t4_engine_recall.CaptureRunner._route` — the research route W6 measured `fired` with, which has no `NO_REPEAT_ENTRIES` and no level-retire. `backtest_2y.py` routes through the shipped `_route`, which has both. That is why `mvs` recovers 22 of his days in section 3 and REMOVES 12 trades here: with no-repeat on, letting a tight-stop C fire first lets it claim the level (`_fired_levels`) and block the better entry behind it. **The tight-stop skip is load-bearing in the shipped router**, and that is not visible on the research route.

### Why the biggest gate cannot simply be opened

`research/g13_floor_fix_ab.md` (`6d89513d`) already established the mechanism on the smallest possible version of this change — moving the floor onto the pre-fill geometry rather than removing it — and it is worth restating because it applies with more force to a full lift: **`backtest_week` sizes every trade at `RISK_DOLLARS / |entry − stop|`, so a book admitted by relaxing a floor on that same distance is a book dividing by zero.** G13's arm produced mean R +14.72 against median +1.7080 with **1,139 of 1,553 rows (73.3%) untakeable**, and it bought **zero** held-out S recall while adding 7 false fires (`research/omen6_backtest_truth.md` §2).

This autopsy adds the number that was missing: it is not 6 marks. It is **127 of Austin's own 271 trading days**.

So the price, both sides, in one place:

- **What opening it recovers.** `floor` lifted takes the engine from 129/271 = 48% of his days to 164/271 = 61% — **+35 of the 132 refused days**.
- **What it costs.** The 2-year book goes from **1017 trades to 4351** — a 4.3× book. Of the 3478 trades it adds, **3472 (99.8%) cannot be sized**, and the median R of the added trades is **+0.0000**. Whole-book median R falls +0.5660 → **+0.0000**.

**A median of exactly +0.0000 R on 3,478 added trades is not a book that got worse — it is a book with no risk unit.** Goal 0 of the master spec is the median R. Removing this floor does not raise it; it deletes the quantity it is measured in.

### The gate that CAN be opened, and what it costs

`htf_veto` is the one arm in this file that produces a **takeable** book. It recovers **more of his days than the floor does** (+40 against +35), adds 961 trades and removes none, and only 2.9% of what it adds is unsizeable — against the floor's 99.8%.

It is also not free, and the direction is the wrong one for goal 0: it **nearly doubles the book** (1017 → 1978) while mean R falls +0.9551 → +0.8771 and median R falls +0.5660 → +0.5105. Both deltas clear the carried ±0.0095 R narrow bar by 8× and 6× — they are readable, and they are negative. Months green go 23/25 → 25/25, which is a durability gain bought with more trades rather than better ones.

The veto has no author. `omen_bot.py`'s own comment block says so, quoting Austin: *"we dont have any higher timeframe bias yet youll need to tell me what that is then."* `research/p16_htf_bias.md` measured lifting it and found only 60 of 3,525 dropped S signals reach a tradeable tier. This autopsy finds the same rule standing between the engine and **40 of Austin's own trading days** — a much larger claim on the same unowned rule, and the reason it belongs in front of him rather than in a backlog.

## 5. The 14-bar lag is a LEVEL-selection finding, not an entry-trigger finding

W6 reported a **median |bar gap| of 14** between his entry and the engine's nearest fired entry on the 129 days it did trade. The question the spec asks is whether that is the same setup taken late or a different setup. `python research/w10_gate_autopsy.py lag` answers it by comparing the two **stops**, because for a break-and-retest the stop IS the level: if the engine is on his level, its stop is his stop.

| | value |
|---|---|
| matched rows | 173 |
| **signed** gap (engine − him), median | **+3 bars** |
| \|gap\|, median | 14 bars |
| engine later / earlier / same bar | 102 / 61 / 10 |
| direction agrees | 133/173 = 77% |

The engine is **not** systematically a quarter of an hour behind. The median signed gap is +3 bars. The 14 is a median of *absolute* gaps and it is made of two populations:

| | n | \|gap\| median | within ±2 bars | engine risk ÷ his risk |
|---|---:|---:|---:|---:|
| engine is on **his level** (\|stops differ\| ≤ 25% of his risk) | 26 | **1 bar** | 16/26 = 62% | 0.524 |
| engine is on a **different level** | 107 | **11 bars** | 21/107 = 20% | 0.442 |

**When the engine trades his level it is on his bar** — median |gap| 1, 16/26 = 62% inside ±2. When it is fourteen minutes away it is trading something else.

What it is trading instead is mostly an **intraday pivot**, a level family that is not in his one playbook:

| engine's stop level | rows | \|gap\| median |
|---|---:|---:|
| named level (OR / PMH / PML / PDH / PDL / order block) | 98 | 9 bars |
| `pivot high` / `pivot low` (intraday, engine-derived) | 75 | **21 bars** |

### The risk unit, which is the second half of the same mechanism

On the 133 direction-matched rows:

| | median |
|---|---:|
| his 1R (`\|Trade Risk\| / Quantity`, verified against his exits) | $0.8920 |
| engine 1R, **post-fill** (`\|entry − stop\|`, what it sizes on) | **$0.3600** |
| engine 1R, **pre-fill** (`\|bar close − stop\|`) | $0.5462 |

Stated as ratios to his own risk unit: post-fill **0.471**, pre-fill **0.813**. The engine's *structural* read of the trade is within a fifth of his; the fill is what takes it to less than half.

This is the same `fill_price` back-dating that section 3's floor reacts to, seen from the other side. It is also an independent reproduction of the master spec §1.3 figure: post-fill ÷ pre-fill comes out at a median of **0.611** here against the spec's **63%**, measured on a completely different population.

**Verdict on the 14 bars: it is not an entry-trigger finding.** The entry trigger is on time whenever it is aimed at the level Austin was aimed at. The lag is a proxy for the engine picking a different level — most often an intraday pivot he does not trade — and it therefore belongs to the same body of work as section 3, not to a separate entry-timing ticket.

## 6. What this changes

- **`research/omen6_backtest_truth.md` §2's "this is a detection problem, not a filter problem" does not survive this sample.** On the 271 symbol-days of Austin's own book the engine sees 261/271 = 96% and takes 129/271 = 48%. Detection accounts for **10/142 = 7%** of the gap; grading accounts for **132/142 = 93%**. The sentence should be corrected where it is quoted.
- **The single biggest gate in the project is a constant Austin never stated.** `max(0.10, 0.0015 × close)` kills at least one signal on 127/132 = 96% of his refused days.
- **It is a symptom, not the disease.** The floor is measuring a quantity `fill_price` created. Section 5 shows the same fill halving the risk unit on the trades that DO fire. Any fix that moves the floor without moving what the floor measures produces G13's un-sizeable book — and a full lift produces a 4.3× book whose added trades have a median R of exactly **+0.0000**.
- **The gate with the biggest claim on his days is not the gate with the biggest kill count.** `HTF_BIAS_VETO` recovers more of his days when lifted alone (+40) than the floor does (+35), and it is the only arm here that produces a book that can actually be sized. It is also the rule `omen_bot.py`'s own comment says has no author. It is not free: on the held-out cards it buys +1 S day for +6 false fires and on the 2-year book it nearly doubles the book while mean and median R both fall by 6-8x the narrow bar. Sections 4a and 4b price it.
- **The tight-stop skip is protective, not obstructive.** Lifting `_min_viable_stop` opens days on the research route and REMOVES 12 trades on the shipped one, because a tight C that fires claims the level under `NO_REPEAT_ENTRIES` and blocks the entry behind it. `STOP_RANGE_MULT` — the audit's other HIGH-importance unstated constant — is not the gate anyone should be spending time on: it recovers 2 days.
- **The 14-bar lag is not an entry-timing bug.** Section 5: on his level, the engine is on his bar. The lag measures how often it is on a different level, usually an intraday pivot he does not trade.
- **The refusal is outcome-blind and median-negative.** The days it refuses carry a higher median R in his own book than the days it takes.

## 7. What this does NOT do

- **Changes no default and adds no flag.** Every arm above is a monkeypatch confined to this script's own process or to a child process it spawns. `signal_runner.py`, `omen_bot.py` and `backtest_week.py` are untouched.
- **Does not re-freeze.** `research/omen6_forward.py freeze --force` was not run and must not be.
- **Does not decide anything.** This is the input to a detection/grading change, in the same way `research/g10_arming_funnel.md` was for the 84% rule. It does not make one.
- **Cannot measure precision.** Every TradeZella row is a trade he took. There are no X rows and no refusals, so this set scores recall only. A change that fires more scores better here and worse on the 100 held-out Test 1 cards. Read the two together or neither.

## Reproduce

```
git show ce2a98d6:data/tradezella_trades.csv > data/tradezella_trades.csv
python research/w10_gate_autopsy.py --selfcheck
python research/w10_gate_autopsy.py coverage
python research/w10_gate_autopsy.py funnel      # ~5 min, asserts W6's 129/271
python research/w10_gate_autopsy.py lift        # ~35 min, 9 arms x 271 days
python research/w10_gate_autopsy.py lag
python backtest_2y.py --days 730 --out research/_w10_base.json   # control
python research/w10_gate_autopsy.py price --gate floor
python research/w10_gate_autopsy.py price --gate htf_veto
python research/w10_gate_autopsy.py price --gate mvs
python research/w10_gate_autopsy.py test1     # 5 arms x 100 held-out cards
python research/w10_gate_autopsy.py report
```

**Provenance.** `research/w10_gate_autopsy.py`. Bars from `data_archive/` only — nothing here can fetch, so nothing here can touch `POLYGON_API_KEY`.

---

## Appendix — all 132 refused days, one row each

`gate` is the proximate killer of the signal nearest his entry bar; `recovered by` names every single-gate lift that made the day fire. A day with no entry in that column is one no single gate opens.

| # | symbol | day | his entry | his R | engine's nearest signal | gate | the value that failed | recovered by |
|---:|---|---|---|---:|---|---|---|---|
| 1 | NVDA | 2024-01-03 | 09:43 call | -1.00 | break_and_retest call @09:43 (+0) | `min_risk_floor` | risk $0.0100 < floor $0.1000 (close $48.04) | `floor`, `pa_d` |
| 2 | NVDA | 2024-01-04 | 09:43 put | -1.00 | break_and_retest put @09:45 (+2) | `min_risk_floor` | risk $0.0042 < floor $0.1000 (close $47.75) | `floor` |
| 3 | NVDA | 2024-01-05 | 09:34 call | +2.32 | break_and_retest call @10:13 (+39) | `min_risk_floor` | risk $0.0070 < floor $0.1000 (close $48.84) | `floor` |
| 4 | NVDA | 2024-01-08 | 09:38 call | +1.98 | break_and_retest call @10:11 (+33) | `min_risk_floor` | risk $0.0420 < floor $0.1000 (close $51.34) | `floor` |
| 5 | NVDA | 2024-01-10 | 10:16 call | +2.07 | break_and_retest call @10:39 (+23) | `min_risk_floor` | risk $0.0300 < floor $0.1000 (close $54.20) | `floor` |
| 6 | NVDA | 2024-01-11 | 09:49 put | -1.00 | break_and_retest call @10:32 (+43) | `min_risk_floor` | risk $0.0047 < floor $0.1000 (close $54.53) | `floor` |
| 7 | NVDA | 2024-01-16 | 09:40 call | -1.00 | break_and_retest call @09:43 (+3) | `min_risk_floor` | risk $0.0890 < floor $0.1000 (close $55.61) | `floor` |
| 8 | NVDA | 2024-02-01 | 10:15 call | -1.00 | break_and_retest call @10:38 (+23) | `min_risk_floor` | risk $0.0060 < floor $0.1000 (close $62.35) | — |
| 9 | NVDA | 2024-02-07 | 10:06 call | +1.97 | one_candle_rule call @09:53 (-13) | `hard_risk_50c` | stock_risk $0.1284 < $0.50 | `floor` |
| 10 | NVDA | 2024-02-09 | 09:54 call | +2.88 | break_and_retest call @10:00 (+6) | `min_risk_floor` | risk $0.0680 < floor $0.1062 (close $70.81) | `floor` |
| 11 | NVDA | 2024-02-14 | 09:50 call | -1.00 | break_and_retest call @09:50 (+0) | `min_risk_floor` | risk $0.0560 < floor $0.1103 (close $73.51) | `floor` |
| 12 | NVDA | 2024-02-15 | 09:39 put | +1.70 | break_and_retest put @09:38 (-1) | `htf_bias_veto` | htf_bias=bullish, direction=put, _grade_pa would say X | `mvs` |
| 13 | NVDA | 2024-02-16 | 10:00 put | -1.00 | break_and_retest call @09:39 (-21) | `min_risk_floor` | risk $0.0010 < floor $0.1110 (close $73.98) | `htf_veto` |
| 14 | NVDA | 2024-03-07 | 10:15 call | +1.81 | break_and_retest call @10:59 (+44) | `min_risk_floor` | risk $0.0000 < floor $0.1376 (close $91.71) | — |
| 15 | NVDA | 2024-03-12 | 10:47 call | +2.10 | break_and_retest put @10:16 (-31) | `min_risk_floor` | risk $0.1280 < floor $0.1316 (close $87.75) | `htf_veto`, `mvs` |
| 16 | NVDA | 2024-03-13 | 09:57 put | +2.00 | one_candle_rule call @10:09 (+12) | `hard_risk_50c` | stock_risk $0.4700 < $0.50 | — |
| 17 | NVDA | 2024-03-14 | 09:59 put | +2.08 | break_and_retest put @09:57 (-2) | `min_risk_floor` | risk $0.0525 < floor $0.1326 (close $88.38) | `htf_veto` |
| 18 | NVDA | 2024-03-18 | 09:43 call | -1.00 | break_and_retest call @09:44 (+1) | `min_risk_floor` | risk $0.1110 < floor $0.1375 (close $91.67) | `floor` |
| 19 | NVDA | 2024-03-19 | 09:46 put | -1.00 | break_and_retest put @09:48 (+2) | `min_risk_floor` | risk $0.0410 < floor $0.1286 (close $85.76) | `htf_veto`, `mvs` |
| 20 | NVDA | 2024-03-20 | 09:34 call | -1.00 | break_and_retest put @09:48 (+14) | `htf_bias_veto` | htf_bias=bullish, direction=put, _grade_pa would say X | — |
| 21 | NVDA | 2024-03-21 | 09:47 put | +2.00 | break_and_retest put @09:54 (+7) | `min_risk_floor` | risk $0.0335 < floor $0.1366 (close $91.07) | — |
| 22 | NVDA | 2024-03-25 | 09:49 call | +2.03 | break_and_retest call @09:59 (+10) | `min_risk_floor` | risk $0.0750 < floor $0.1433 (close $95.55) | `floor` |
| 23 | NVDA | 2024-03-27 | 09:36 put | +2.10 | break_and_retest put @09:38 (+2) | `min_risk_floor` | risk $0.0100 < floor $0.1372 (close $91.45) | `htf_veto`, `mvs` |
| 24 | NVDA | 2024-03-28 | 09:56 call | -1.00 | break_and_retest put @10:02 (+6) | `htf_bias_veto` | htf_bias=bullish, direction=put, _grade_pa would say C | — |
| 25 | NVDA | 2024-04-01 | 09:35 call | +2.59 | break_and_retest call @10:29 (+54) | `min_risk_floor` | risk $0.0446 < floor $0.1370 (close $91.34) | `floor`, `pa_d` |
| 26 | NVDA | 2024-04-02 | 09:44 put | -1.00 | break_and_retest put @09:44 (+0) | `min_risk_floor` | risk $0.0810 < floor $0.1319 (close $87.94) | — |
| 27 | NVDA | 2024-04-03 | 10:15 call | +2.04 | break_and_retest call @10:00 (-15) | `htf_bias_veto` | htf_bias=bearish, direction=call, _grade_pa would say C | `htf_veto` |
| 28 | NVDA | 2024-04-05 | 09:57 call | -1.00 | break_and_retest call @09:58 (+1) | `min_risk_floor` | risk $0.0020 < floor $0.1311 (close $87.41) | — |
| 29 | NVDA | 2024-04-10 | 09:41 call | +2.00 | break_and_retest call @10:11 (+30) | `min_risk_floor` | risk $0.0210 < floor $0.1297 (close $86.50) | — |
| 30 | NVDA | 2024-04-11 | 09:41 call | -1.00 | break_and_retest call @09:38 (-3) | `htf_bias_veto` | htf_bias=bearish, direction=call, _grade_pa would say X | `mvs` |
| 31 | NVDA | 2024-04-12 | 09:42 put | -1.00 | break_and_retest put @09:45 (+3) | `min_risk_floor` | risk $0.0737 < floor $0.1342 (close $89.48) | — |
| 32 | NVDA | 2024-04-15 | 09:41 call | +1.72 | break_and_retest call @09:55 (+14) | `min_risk_floor` | risk $0.0240 < floor $0.1353 (close $90.18) | — |
| 33 | NVDA | 2024-04-16 | 10:02 call | -1.00 | break_and_retest call @10:51 (+49) | `min_risk_floor` | risk $0.0604 < floor $0.1305 (close $87.02) | — |
| 34 | NVDA | 2024-04-17 | 09:35 call | -1.00 | one_candle_rule put @09:58 (+23) | `hard_risk_50c` | stock_risk $0.2164 < $0.50 | — |
| 35 | NVDA | 2024-04-18 | 09:42 put | -1.00 | break_and_retest put @10:04 (+22) | `min_risk_floor` | risk $0.0600 < floor $0.1264 (close $84.30) | — |
| 36 | NVDA | 2024-04-22 | 10:34 put | -1.00 | break_and_retest call @10:14 (-20) | `min_risk_floor` | risk $0.0600 < floor $0.1178 (close $78.53) | `htf_veto` |
| 37 | NVDA | 2024-04-23 | 10:19 call | +2.06 | break_and_retest call @10:18 (-1) | `min_risk_floor` | risk $0.0290 < floor $0.1221 (close $81.42) | `htf_veto` |
| 38 | NVDA | 2024-04-25 | 09:49 call | +2.00 | break_and_retest call @09:47 (-2) | `min_risk_floor` | risk $0.0920 < floor $0.1208 (close $80.55) | `mvs` |
| 39 | NVDA | 2024-05-08 | 09:43 call | +2.08 | break_and_retest call @09:40 (-3) | `min_risk_floor` | risk $0.0280 < floor $0.1352 (close $90.12) | `floor` |
| 40 | NVDA | 2024-05-13 | 09:44 put | +2.00 | break_and_retest call @10:03 (+19) | `min_risk_floor` | risk $0.0450 < floor $0.1342 (close $89.50) | `mvs` |
| 41 | NVDA | 2024-05-17 | 10:11 put | -1.00 | break_and_retest put @10:00 (-11) | `min_risk_floor` | risk $0.1320 < floor $0.1405 (close $93.70) | — |
| 42 | NVDA | 2024-05-31 | 10:29 put | +2.01 | break_and_retest put @10:12 (-17) | `min_risk_floor` | risk $0.1447 < floor $0.1670 (close $111.36) | — |
| 43 | NVDA | 2024-06-05 | 09:58 call | +2.04 | break_and_retest put @10:54 (+56) | `min_risk_floor` | risk $0.0420 < floor $0.1795 (close $119.65) | — |
| 44 | NVDA | 2024-06-13 | 10:22 put | -1.00 | break_and_retest call @10:04 (-18) | `min_viable_stop` | risk $0.3400 vs 0.75 x avg range $0.2203 | `mvs` |
| 45 | NVDA | 2024-06-17 | 10:01 put | +3.70 | break_and_retest put @09:57 (-4) | `min_risk_floor` | risk $0.0050 < floor $0.1981 (close $132.06) | `htf_veto`, `mvs` |
| 46 | NVDA | 2024-06-25 | 09:55 call | -1.00 | break_and_retest call @09:53 (-2) | `min_risk_floor` | risk $0.0450 < floor $0.1825 (close $121.64) | `floor`, `htf_veto` |
| 47 | NVDA | 2024-06-28 | 09:56 call | +1.93 | one_candle_rule call @09:56 (+0) | `hard_risk_50c` | stock_risk $0.4400 < $0.50 | — |
| 48 | NVDA | 2024-07-01 | 09:44 put | +2.00 | break_and_retest put @10:10 (+26) | `min_risk_floor` | risk $0.0500 < floor $0.1807 (close $120.46) | `floor`, `mvs` |
| 49 | NVDA | 2024-07-02 | 09:49 call | -1.00 | break_and_retest call @09:47 (-2) | `min_risk_floor` | risk $0.0600 < floor $0.1844 (close $122.91) | — |
| 50 | NVDA | 2024-07-03 | 09:34 call | -1.00 | break_and_retest call @09:49 (+15) | `min_risk_floor` | risk $0.0200 < floor $0.1836 (close $122.37) | `mvs` |
| 51 | NVDA | 2024-07-08 | 09:38 call | +2.00 | break_and_retest call @10:29 (+51) | `min_risk_floor` | risk $0.1107 < floor $0.1934 (close $128.96) | `htf_veto` |
| 52 | NVDA | 2024-07-10 | 10:54 call | -1.00 | break_and_retest call @10:53 (-1) | `min_risk_floor` | risk $0.1500 < floor $0.2017 (close $134.45) | `floor` |
| 53 | NVDA | 2024-07-12 | 09:57 call | -1.00 | break_and_retest call @09:56 (-1) | `htf_bias_veto` | htf_bias=bearish, direction=call, _grade_pa would say B | `htf_veto` |
| 54 | NVDA | 2024-07-15 | 09:43 put | +2.00 | break_and_retest put @09:42 (-1) | `min_risk_floor` | risk $0.1500 < floor $0.1951 (close $130.04) | `mvs` |
| 55 | NVDA | 2024-07-16 | 09:47 call | -1.00 | break_and_retest call @09:40 (-7) | `min_risk_floor` | risk $0.0400 < floor $0.1935 (close $129.00) | `floor`, `mvs`, `pa_d` |
| 56 | NVDA | 2024-07-23 | 09:44 call | -1.00 | break_and_retest call @09:44 (+0) | `min_risk_floor` | risk $0.1800 < floor $0.1866 (close $124.42) | — |
| 57 | NVDA | 2024-07-29 | 09:43 call | -1.00 | one_candle_rule call @09:46 (+3) | `wide_stop_0p4` | risk/close 0.5011% > 0.40% | `htf_veto` |
| 58 | NVDA | 2024-07-30 | 10:10 put | -1.00 | break_and_retest put @10:12 (+2) | `min_risk_floor` | risk $0.0900 < floor $0.1627 (close $108.46) | `floor`, `pa_d` |
| 59 | NVDA | 2024-07-31 | 10:00 call | +2.05 | break_and_retest call @10:01 (+1) | `htf_bias_veto` | htf_bias=bearish, direction=call, _grade_pa would say X | `htf_veto`, `mvs` |
| 60 | NVDA | 2024-08-05 | 09:42 call | +1.97 | break_and_retest call @10:55 (+73) | `min_risk_floor` | risk $0.0147 < floor $0.1501 (close $100.08) | — |
| 61 | NVDA | 2024-08-06 | 09:39 put | +1.97 | break_and_retest call @10:12 (+33) | `min_risk_floor` | risk $0.0000 < floor $0.1562 (close $104.13) | `htf_veto` |
| 62 | NVDA | 2024-08-13 | 09:49 call | +1.94 | break_and_retest call @09:55 (+6) | `min_risk_floor` | risk $0.0600 < floor $0.1697 (close $113.12) | — |
| 63 | NVDA | 2024-08-20 | 10:16 put | +2.08 | break_and_retest put @10:14 (-2) | `min_risk_floor` | risk $0.0600 < floor $0.1921 (close $128.05) | — |
| 64 | NVDA | 2024-08-27 | 10:10 call | +2.00 | break_and_retest call @10:01 (-9) | `min_risk_floor` | risk $0.1500 < floor $0.1904 (close $126.96) | `floor`, `pa_d` |
| 65 | NVDA | 2024-08-28 | 10:14 put | -1.00 | break_and_retest call @10:16 (+2) | `min_risk_floor` | risk $0.1455 < floor $0.1907 (close $127.14) | — |
| 66 | NVDA | 2024-09-03 | 09:47 put | -1.00 | break_and_retest put @09:46 (-1) | `htf_bias_veto` | htf_bias=bullish, direction=put, _grade_pa would say C | `htf_veto` |
| 67 | NVDA | 2024-09-11 | 09:49 call | -1.00 | break_and_retest call @09:46 (-3) | `htf_bias_veto` | htf_bias=bearish, direction=call, _grade_pa would say X | `floor` |
| 68 | NVDA | 2024-09-12 | 09:42 call | -1.00 | break_and_retest call @09:42 (+0) | `min_risk_floor` | risk $0.0400 < floor $0.1768 (close $117.89) | `htf_veto` |
| 69 | NVDA | 2024-09-19 | 09:34 call | -1.00 | break_and_retest call @09:37 (+3) | `htf_bias_veto` | htf_bias=bearish, direction=call, _grade_pa would say C | `htf_veto` |
| 70 | NVDA | 2024-09-20 | 09:42 call | -1.00 | break_and_retest call @09:43 (+1) | `min_risk_floor` | risk $0.1600 < floor $0.1774 (close $118.27) | `floor` |
| 71 | NVDA | 2025-01-02 | 09:42 put | -1.00 | break_and_retest call @10:07 (+25) | `min_risk_floor` | risk $0.0700 < floor $0.2070 (close $138.02) | `htf_veto` |
| 72 | NVDA | 2025-01-07 | 09:39 put | +2.06 | break_and_retest put @09:49 (+10) | `htf_bias_veto` | htf_bias=bullish, direction=put, _grade_pa would say C | `htf_veto` |
| 73 | NVDA | 2025-01-10 | 09:50 put | -1.00 | break_and_retest put @09:52 (+2) | `min_risk_floor` | risk $0.2000 < floor $0.2023 (close $134.89) | `htf_veto` |
| 74 | NVDA | 2025-01-13 | 10:00 call | -1.00 | break_and_retest call @10:01 (+1) | `min_risk_floor` | risk $0.0800 < floor $0.1976 (close $131.76) | — |
| 75 | NVDA | 2025-01-15 | 10:31 call | -1.00 | break_and_retest call @10:20 (-11) | `min_risk_floor` | risk $0.0200 < floor $0.2012 (close $134.13) | — |
| 76 | NVDA | 2025-01-17 | 09:56 call | -1.00 | break_and_retest call @09:55 (-1) | `min_risk_floor` | risk $0.0466 < floor $0.2055 (close $137.00) | `htf_veto` |
| 77 | NVDA | 2025-01-22 | 10:01 call | -1.00 | break_and_retest call @10:36 (+35) | `min_risk_floor` | risk $0.0968 < floor $0.2202 (close $146.78) | `floor`, `pa_d` |
| 78 | NVDA | 2025-01-30 | 09:44 put | -1.00 | break_and_retest put @09:43 (-1) | `min_risk_floor` | risk $0.0700 < floor $0.1828 (close $121.84) | `floor` |
| 79 | TSLA | 2024-01-08 | 10:04 call | -1.00 | break_and_retest call @10:07 (+3) | `min_risk_floor` | risk $0.0200 < floor $0.3567 (close $237.82) | — |
| 80 | TSLA | 2024-01-18 | 10:36 put | -1.00 | break_and_retest put @10:54 (+18) | `min_risk_floor` | risk $0.0000 < floor $0.3196 (close $213.09) | `floor`, `pa_d` |
| 81 | TSLA | 2024-01-31 | 09:39 call | +2.39 | break_and_retest call @09:47 (+8) | `min_risk_floor` | risk $0.0100 < floor $0.2849 (close $189.95) | — |
| 82 | TSLA | 2024-02-07 | 09:50 put | +1.96 | break_and_retest put @10:11 (+21) | `min_risk_floor` | risk $0.0800 < floor $0.2766 (close $184.42) | — |
| 83 | TSLA | 2024-02-08 | 09:38 put | -1.00 | break_and_retest call @10:15 (+37) | `min_risk_floor` | risk $0.0200 < floor $0.2834 (close $188.92) | — |
| 84 | TSLA | 2024-02-27 | 09:39 put | -1.00 | break_and_retest put @10:05 (+26) | `min_risk_floor` | risk $0.2950 < floor $0.3042 (close $202.81) | — |
| 85 | TSLA | 2024-03-04 | 09:43 put | +2.21 | break_and_retest put @10:38 (+55) | `min_risk_floor` | risk $0.0599 < floor $0.2885 (close $192.31) | — |
| 86 | TSLA | 2024-03-06 | 09:49 put | +2.17 | break_and_retest put @09:48 (-1) | `min_risk_floor` | risk $0.2000 < floor $0.2661 (close $177.39) | `floor`, `pa_d` |
| 87 | TSLA | 2024-03-12 | 09:37 put | +2.06 | break_and_retest call @10:10 (+33) | `min_risk_floor` | risk $0.1400 < floor $0.2612 (close $174.16) | — |
| 88 | TSLA | 2024-03-21 | 10:05 put | -1.00 | one_candle_rule put @10:02 (-3) | `pa_grade_D` | _grade_pa=X | `pa_d` |
| 89 | TSLA | 2024-03-22 | 10:09 call | +2.54 | break_and_retest call @10:20 (+11) | `min_risk_floor` | risk $0.0100 < floor $0.2545 (close $169.65) | `mvs`, `pa_d` |
| 90 | TSLA | 2024-03-27 | 09:39 put | +2.08 | break_and_retest put @09:38 (-1) | `htf_bias_veto` | htf_bias=bullish, direction=put, _grade_pa would say X | `mvs` |
| 91 | TSLA | 2024-04-04 | 09:39 put | -1.00 | break_and_retest call @10:10 (+31) | `min_risk_floor` | risk $0.0479 < floor $0.2543 (close $169.54) | — |
| 92 | TSLA | 2024-04-15 | 09:48 put | +2.80 | break_and_retest put @10:15 (+27) | `min_risk_floor` | risk $0.0800 < floor $0.2478 (close $165.17) | `floor` |
| 93 | TSLA | 2024-04-22 | 09:40 call | +1.93 | break_and_retest put @10:11 (+31) | `min_risk_floor` | risk $0.0100 < floor $0.2144 (close $142.91) | `floor`, `mvs` |
| 94 | TSLA | 2024-05-01 | 10:18 put | -1.00 | break_and_retest put @10:18 (+0) | `min_risk_floor` | risk $0.0400 < floor $0.2704 (close $180.29) | — |
| 95 | TSLA | 2024-05-02 | 09:44 put | +2.16 | break_and_retest put @10:13 (+29) | `min_risk_floor` | risk $0.1100 < floor $0.2658 (close $177.17) | `htf_veto` |
| 96 | TSLA | 2024-05-06 | 09:34 call | +2.03 | break_and_retest call @10:44 (+70) | `min_risk_floor` | risk $0.0500 < floor $0.2780 (close $185.36) | `floor` |
| 97 | TSLA | 2024-05-07 | 09:53 put | +3.20 | break_and_retest put @10:04 (+11) | `min_risk_floor` | risk $0.0300 < floor $0.2681 (close $178.73) | — |
| 98 | TSLA | 2024-05-09 | 09:38 put | -1.00 | break_and_retest put @09:43 (+5) | `min_risk_floor` | risk $0.1960 < floor $0.2605 (close $173.64) | `htf_veto`, `mvs` |
| 99 | TSLA | 2024-05-16 | 09:38 put | -1.00 | break_and_retest put @10:00 (+22) | `min_risk_floor` | risk $0.0333 < floor $0.2598 (close $173.18) | `mvs` |
| 100 | TSLA | 2024-05-17 | 09:43 call | -1.00 | break_and_retest put @09:52 (+9) | `htf_bias_veto` | htf_bias=bullish, direction=put, _grade_pa would say A+ | `htf_veto` |
| 101 | TSLA | 2024-05-22 | 09:40 put | -1.00 | break_and_retest put @09:39 (-1) | `min_risk_floor` | risk $0.1700 < floor $0.2729 (close $181.94) | `htf_veto` |
| 102 | TSLA | 2024-05-24 | 09:37 call | +0.76 | break_and_retest call @09:41 (+4) | `htf_bias_veto` | htf_bias=bearish, direction=call, _grade_pa would say X | `htf_veto` |
| 103 | TSLA | 2024-05-29 | 09:52 call | -1.00 | break_and_retest put @10:18 (+26) | `min_risk_floor` | risk $0.1899 < floor $0.2632 (close $175.45) | — |
| 104 | TSLA | 2024-05-30 | 09:49 call | +2.06 | break_and_retest call @10:13 (+24) | `min_risk_floor` | risk $0.0508 < floor $0.2717 (close $181.12) | — |
| 105 | TSLA | 2024-06-04 | 10:15 put | -1.00 | break_and_retest put @10:08 (-7) | `min_risk_floor` | risk $0.0043 < floor $0.2622 (close $174.82) | `floor` |
| 106 | TSLA | 2024-06-06 | 09:36 call | -1.00 | break_and_retest call @09:35 (-1) | `htf_bias_veto` | htf_bias=bearish, direction=call, _grade_pa would say B | `floor`, `htf_veto` |
| 107 | TSLA | 2024-06-10 | 09:54 call | -1.00 | break_and_retest call @09:51 (-3) | `min_risk_floor` | risk $0.0994 < floor $0.2667 (close $177.83) | `floor` |
| 108 | TSLA | 2024-06-12 | 09:42 call | +1.89 | break_and_retest call @09:45 (+3) | `min_risk_floor` | risk $0.1000 < floor $0.2596 (close $173.08) | `htf_veto` |
| 109 | TSLA | 2024-06-14 | 09:46 put | -1.00 | break_and_retest put @09:45 (-1) | `min_risk_floor` | risk $0.0300 < floor $0.2735 (close $182.31) | `htf_veto` |
| 110 | TSLA | 2024-06-25 | 09:43 put | -1.00 | break_and_retest put @09:41 (-2) | `min_risk_floor` | risk $0.0901 < floor $0.2748 (close $183.18) | `floor`, `htf_veto` |
| 111 | TSLA | 2024-06-26 | 09:51 call | -1.00 | break_and_retest call @10:14 (+23) | `min_risk_floor` | risk $0.0700 < floor $0.2897 (close $193.13) | `floor` |
| 112 | TSLA | 2024-07-10 | 10:07 put | +2.56 | break_and_retest put @10:04 (-3) | `min_risk_floor` | risk $0.0200 < floor $0.3915 (close $260.99) | `htf_veto` |
| 113 | TSLA | 2024-07-16 | 09:47 put | +2.86 | break_and_retest put @09:42 (-5) | `min_risk_floor` | risk $0.0700 < floor $0.3807 (close $253.83) | `htf_veto`, `pa_d` |
| 114 | TSLA | 2024-07-17 | 09:50 call | -1.00 | one_candle_rule call @09:47 (-3) | `wide_stop_0p4` | risk/close 0.4082% > 0.40% | `htf_veto` |
| 115 | TSLA | 2024-07-19 | 09:43 put | +2.20 | break_and_retest put @09:39 (-4) | `min_risk_floor` | risk $0.0450 < floor $0.3707 (close $247.16) | `htf_veto` |
| 116 | TSLA | 2024-07-23 | 09:57 put | +2.00 | break_and_retest put @09:57 (+0) | `min_risk_floor` | risk $0.1766 < floor $0.3744 (close $249.63) | — |
| 117 | TSLA | 2024-07-25 | 09:33 call | +1.93 | break_and_retest call @09:47 (+14) | `min_risk_floor` | risk $0.2383 < floor $0.3318 (close $221.18) | `htf_veto`, `mvs`, `stop_range` |
| 118 | TSLA | 2024-08-08 | 09:47 put | -1.00 | break_and_retest put @09:45 (-2) | `min_risk_floor` | risk $0.1500 < floor $0.2898 (close $193.19) | `floor` |
| 119 | TSLA | 2024-08-12 | 09:34 put | +1.73 | break_and_retest call @10:28 (+54) | `min_risk_floor` | risk $0.1600 < floor $0.2957 (close $197.13) | — |
| 120 | TSLA | 2024-08-20 | 10:08 put | +2.17 | break_and_retest call @10:23 (+15) | `min_risk_floor` | risk $0.1300 < floor $0.3347 (close $223.11) | — |
| 121 | TSLA | 2024-08-21 | 10:23 put | -1.00 | break_and_retest put @10:21 (-2) | `min_risk_floor` | risk $0.1288 < floor $0.3310 (close $220.68) | — |
| 122 | TSLA | 2024-08-22 | 10:18 put | +2.02 | break_and_retest put @10:35 (+17) | `min_risk_floor` | risk $0.0200 < floor $0.3305 (close $220.34) | `htf_veto` |
| 123 | TSLA | 2024-08-27 | 09:45 put | -1.00 | break_and_retest put @10:11 (+26) | `min_risk_floor` | risk $0.0900 < floor $0.3127 (close $208.49) | `mvs` |
| 124 | TSLA | 2024-09-06 | 09:44 put | +2.37 | break_and_retest put @09:52 (+8) | `min_risk_floor` | risk $0.1400 < floor $0.3363 (close $224.18) | — |
| 125 | TSLA | 2024-09-11 | 10:39 put | +1.74 | break_and_retest put @10:38 (-1) | `min_risk_floor` | risk $0.1600 < floor $0.3283 (close $218.89) | — |
| 126 | TSLA | 2024-09-20 | 09:45 put | +2.04 | break_and_retest put @09:44 (-1) | `min_risk_floor` | risk $0.2963 < floor $0.3606 (close $240.43) | — |
| 127 | TSLA | 2025-01-03 | 09:45 call | -1.00 | break_and_retest call @09:42 (-3) | `min_risk_floor` | risk $0.1800 < floor $0.5800 (close $386.64) | `htf_veto`, `mvs`, `stop_range` |
| 128 | TSLA | 2025-01-07 | 10:04 put | +1.94 | one_candle_rule put @10:06 (+2) | `wide_stop_0p4` | risk/close 0.6152% > 0.40% | — |
| 129 | TSLA | 2025-01-16 | 09:48 put | -1.00 | break_and_retest put @09:47 (-1) | `htf_bias_veto` | htf_bias=bullish, direction=put, _grade_pa would say X | `htf_veto` |
| 130 | TSLA | 2025-01-21 | 09:37 put | +1.99 | break_and_retest put @10:08 (+31) | `min_risk_floor` | risk $0.3700 < floor $0.6160 (close $410.65) | `htf_veto` |
| 131 | TSLA | 2025-01-23 | 09:51 call | -1.00 | break_and_retest call @10:36 (+45) | `min_risk_floor` | risk $0.2463 < floor $0.6221 (close $414.74) | — |
| 132 | TSLA | 2025-01-30 | 09:49 put | +1.98 | break_and_retest call @10:12 (+23) | `htf_bias_veto` | htf_bias=bearish, direction=call, _grade_pa would say C | — |
