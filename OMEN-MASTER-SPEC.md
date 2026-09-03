# OMEN — THE MASTER SPEC

**2026-09-02.** Supersedes `research/g92_master_spec.md`. Every number below names its
fill and its denominator. Every number below comes out of a committed script in this
repo; run it rather than quoting it.

**The book everything is measured on:** `research/bt2y_trades_retest_on.json` — built
2026-09-02 19:49 at commit `a89e90e2`, 498 sessions (2024-09-03 → 2026-09-02), 28
symbols, 127,152 signal rows, 10,830 fired, 4,022 fired-and-traded, 4,205 halted.
Entry fills at the bar **close** (honest). Targets fill on **touch**. Stops trigger on
the **close** and fill through `stop_rule.stop_fill_price()`, floored at −1.25R. A bar
that touches a target and closes past the stop goes to the **stop**. 1R = $1,000.
Every row is size-gated on `signal_runner.min_risk_floor`.

**The unit:** one trade a day — the first size-gated candidate of the session. 498 of
498 sessions have one. `$/day` always divides by all 498 sessions, so a day you sit out
earns $0 and never flatters the average.

**New scripts committed with this spec:**
`research/g101_open_and_ladder.py` (the open read + the ladder sweep),
`research/g102_wait_for_the_open.py` (arrival timing),
`research/g103_what_its_worth.py` (what his label is worth, with permutation tests),
`research/g104_gate_value.py` (what each gate the engine already has is worth).

---

## 1. THE ASK

Austin sees one to three setups a day that he would take every time, and he wants the
engine to find those and only those, hold the ones that run, and scale out of the rest.
He is not asking for a ranker and he is not asking for more signals — the engine already
surfaces 6,889 size-gated candidates across 498 sessions and he takes 1–3. He is asking
for a **classifier that fires 1–3 times a day and is right**, an **entry that is not a
few candles behind the setup**, and an **exit ladder whose last piece has no ceiling**,
because — his words, 2026-09-02 — *"Always scale, but we just want to identify winners
that can run. Scouts are good, but runners that can run is where the money's at."* The
bar is $397/day with every month green. The engine's first-of-day book is $34/day.

---

## 2. THE S-ROUTE AS IT RUNS TODAY

Bar to trade, every gate, marked. Line references are the working copy at commit
`08118e3e`.

| # | step | where | verdict |
|---|---|---|---|
| 1 | scheduled task → `run_daily.ps1` → `python live_scanner.py --paper` | `run_daily.ps1:29` | **suspect** |
| 2 | fetch 1m bars — Tastytrade, yfinance fallback | `live_scanner.py:378-386` | **broken** |
| 3 | mark open paper positions against the fresh bar; a stop-out arms the 84% re-entry | `live_scanner.py:396-420` | correct |
| 4 | daily context PDH/PDL/HTF bias/PMH/PML | `live_scanner.py:424-437` | **broken** |
| 5 | `detect_signals()` — 5 setup families defined, 3 live-active | `signal_runner.py:2782` | **suspect** |
| 6 | base grade `_grade_pa` → A/B/C/D | `omen_bot.py:265-300` | **suspect** |
| 7 | **`ENABLE_SAC_LADDER` forced on, live process only** — his S/A/C/X overwrites the engine letter | `live_scanner.py:30`, `signal_runner.py:2212` | **broken** |
| 8 | `_route()` C-caps and vetoes: `RETEST_REQUIRED` on, `X_LIFT=clean` on, `MIN_STOP_PCT=0.08` on; `S_GATE`, `RULE_710`, `ENFORCE_NO_REPEAT`, `NO_REPEAT_ENTRIES`, `LEVEL_RETIRE_TOUCHES` all off | `signal_runner.py:2629-2780` | correct |
| 9 | TRADE iff `sac_grade == "S"`, else WATCH | `live_scanner.py:572-594` | **broken** |
| 10 | size off `GRADE_SIZE_PCT` — 5 keys, live can only ever reach 2 | `options_sizer.py:212` | **suspect** |
| 11 | exit: `OMEN_LIVE_LADDER` defaults **off** → one flat 2R target, no scale | `options_sizer.py:81` | **broken** |
| 12 | `paper.open_from_plan()` → `journal/paper-trades.jsonl` | `paper_trader.py:404-422` | correct |

**Reachability, counted on the 127,152-row book rather than asserted.** Of every signal
the engine ever considered: `skipped_d` 105,876 (83.3%) — killed as D/X before any other
gate; `fired` 10,830 (8.5%); `skipped_tight_stop` 6,241 (4.9%); `halted` 4,205 (3.3%).
Of the 4,022 traded rows the legacy grade is **B on 3,959 (98.4%) and A on 63 (1.6%)** —
zero A+, zero C. A five-letter ladder that emits one letter.

**What the live gate actually does, priced for the first time** (`g104`, 498 sessions,
honest fill, ladder exit):

| slice | days traded | trades/day | book $/day | ladder $/day | months green | max DD |
|---|---:|---:|---:|---:|---:|---:|
| everything the backtest trades | 498 | 1.00 | $34 | **$101** | 12/25 | −$20,438 |
| **`sgrade == S` — the live gate** | 88 | **0.18** | $27 | **$14** | 12/25 | −$7,274 |
| `sgrade` S or A | 218 | 0.44 | $41 | $78 | 13/25 | −$11,090 |
| `sgrade == C` | 280 | 0.56 | −$7 | $23 | 13/24 | −$19,730 |

The gate live runs on fires **0.18 times a day**, not the 1–3 he asked for, and costs
$87/day of ladder value. It is also barely a classifier: against his own labels, on the
683 judged symbol-days the engine had a candidate on, `sgrade == S` is **35.0% precise
against a 29.4% base rate** and catches **20.9%** of the S days it saw.

**The paper book is one trade.** `journal/paper-trades.jsonl` holds a single round trip —
TSLA 2026-09-01, put, grade A, stopped, −$783, `scaled: false`. Today's
`journal/scanner_status.json` (13:24 ET) reads `bars_fetched: 0`, `signals_fired_today:
0`, `last_error: rate limited`. The live route has not yet been observed working.

---

## 3. THE S-ROUTE AS IT SHOULD RUN

He said fix the entry first. So: entry, then the ladder. Every change names its evidence
and its denominator, and nothing here is asserted from a handful of cards.

### 3.1 Entry — what the evidence actually says

**E1. Do not wait for the open to behave. Arrival order is the edge, and it points
earlier, not later.** (`g102`, 498 sessions, both fills, same one-a-day rule, only the
arrival filter differs.)

| arm | days traded | book $/day | ladder $/day | months green | runner rate |
|---|---:|---:|---:|---:|---:|
| **first of day (shipped)** | 498 | **$34** | **$101** | 12/25 | **23.5%** |
| first at/after 09:45 | 498 | −$51 | −$19 | 10/25 | 21.9% |
| first at/after 09:50 | 498 | −$49 | −$35 | 11/25 | 20.1% |
| first at/after 10:00 | 493 | −$109 | −$131 | 9/25 | 17.4% |

Runner rate decays monotonically with arrival: 23.5% first-of-day, 21.6% for candidates
arriving 09:45–09:59 (n=1,964), 18.0% for 10:00–10:29 (n=2,450), 9.5% for 10:30+
(n=1,241). Every minute of patience costs money and costs runners.

**E2. "How the open behaved" is right, and unavailable.** Implemented causally in
`g101.open_state` — opening range = high/low of 09:30–09:44; then read the closes from
09:45 to `min(entry bar, 09:59)`; *trend* if the majority close outside on one side, the
last close is outside, and the boundary was crossed at most once; *chop* at two or more
crossings; *inside* if it never closed out. Needs no other symbol and no lookahead. On
the 444-row first-of-day population it produces a read on **42 of 444 rows (9.5%)**,
because **402 of 444 (90.5%) of first-of-day entries land before 09:45** — the engine is
already filled before the open has behaved. Only 8 rows carry a full trend read. **Stamp
the field on every trade starting now; gate on nothing until there are hundreds of rows
where the read exists.** It is not a failed idea, it is an unmeasurable one on this book.

**E3. His minute beats the engine's, directionally only.** `g98`: on 46 same-tape pairs
his entry offers +2.795R against the engine's +2.312R, p=0.137. Say "directional, not
proven" every time this is cited. Do not build on it.

**E4. The thing that separates trades is his label, and what it separates is runners.**
(`g103`, unit = judged symbol-day, first size-gated candidate, 592 priced.)

| | n | book $/trade | ladder $/trade | ladder win | **runner rate** |
|---|---:|---:|---:|---:|---:|
| he graded S | 169 | $36 | **$297** | 50.9% | **29.0%** |
| he did not | 423 | −$171 | −$170 | 33.6% | 16.3% |

Gap: **+0.2065R** on the book fill (label-shuffle p=0.0142), **+0.4665R** on the ladder
fill (p<0.0001), and **+12.7 percentage points of runner rate (p=0.0003)**. His eye
selects the trades that run, and the ladder is the only structure that pays for that.
Neither works alone. *(Denominator warning, inherited from `g96`: judged symbol-days are
not a random sample of sessions — deck cards were often chosen because the engine fired.
This is a within-judged-pool comparison and an upper bound, not a forecast.)*

**E5. The engine's own eight-variable grade carries almost none of that information.**
Precision against his S on the 683 overlapping symbol-days: `sgrade S` 35.0%,
`sgrade A` 28.7%, `sgrade C` 28.0%, base rate 29.4%. The whole ladder is worth +5.6
percentage points and throws away 79% of his S days.

**E6. Three of the eight downgrade variables are wrong-signed on the honest book.**
(`g104`, 498 first-of-day rows, ladder R.)

| variable | trips | R when tripped | R when clean | verdict |
|---|---:|---:|---:|---|
| `chase` | 165 (33.1%) | −0.0412 | +0.1709 | right-signed, strongest |
| `level_not_respected` | 312 (62.7%) | +0.0550 | +0.1772 | right-signed here |
| `no_displacement` | 300 (60.2%) | +0.0514 | +0.1752 | right-signed |
| `counter_trend_not_respected` | **317 (63.7%)** | **+0.1926** | **−0.0604** | **WRONG-SIGNED** |
| `no_retest` | 35 (7.0%) | +0.1738 | +0.0951 | wrong-signed, small n |
| `ocr_not_respected` | 34 (6.8%) | +0.2184 | +0.0920 | wrong-signed, small n |

A variable that trips on two thirds of the book and grades backwards is inside the grade
the live process trades on. That is why the live S gate is worth $14/day.

**E7. The shippable entry gate is the chase veto.** (`g104`, 498 sessions.)

| slice | days traded | trades/day | book $/day | ladder $/day | win | months green | max DD | runner |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| everything | 498 | 1.00 | $34 | $101 | 39.8% | 12/25 | −$20,438 | 23.5% |
| **minus chase** | 333 | **0.67** | **$63** | **$114** | 41.4% | **13/25** | **−$15,736** | **26.7%** |
| minus chase, minus `nodisp` | 51 | 0.10 | $28 | $52 | 54.9% | 13/22 | −$7,206 | 31.4% |
| minus chase, `sgrade` S or A | 166 | 0.33 | $52 | $79 | 41.6% | **16/25** | −$8,748 | 28.9% |

Dropping chased entries is better on every axis at once: more money, fewer trades, higher
win rate, one more green month, 23% less drawdown, and more runners. It is also his own
word for the mistake.

### 3.2 The build order

1. **Ship the chase veto** behind `CHASE_VETO`, default off, with a test that counts how
   often it trips (must be 165/498 on this book, or the gate has drifted).
2. **Ship the ladder live.** `OMEN_LIVE_LADDER=1` and the plan in §4. He has now answered
   the question that flag was waiting on.
3. **Kill the live/backtest grading divergence.** One ladder, one process. Either the
   2-year book is rebuilt with `ENABLE_SAC_LADDER=1` or live stops forcing it. Until then
   no live number can be compared to any backtest number.
4. **Fix `counter_trend_not_respected`'s sign**, or drop it from the varset, and re-price
   `sgrade` — it is inside the gate that decides live trades.
5. **Then, and only then, rebuild the classifier — against the runner target, not the
   grade.** §5 says why.

---

## 4. THE LADDER, DERIVED

### 4.1 PT1 is his and it is confirmed — and it is a scout, not a target

113 statements across 1,263 judged symbol-days name HOD/LOD as the thing to target or
scale at. Measured on the book (`g99_rung_recon`, 444 first-of-day rows): the session
extreme as of the entry bar sits a **median of 0.495R** from entry (mean 0.797R). It is
2R or further on **41 of 444 (9.2%)** and is **already at or behind entry on 14 (3.2%)** —
a target that has been passed before the trade starts. PT1 pays fast and pays small.
That is exactly what a first scale should do; it is not where the money is.

### 4.2 PT2 exists half the time, and when it exists it is a long way out

PT2 = the nearest named level (PDH/PDL/PMH/PML) strictly beyond PT1 — the option he
accepted. Measured: **available on 220 of 444 rows (49.5%), missing on 224 (50.5%)**.
Where it exists it sits at a **median 3.148R** (mean 4.175R). Sources: PDL 82, PDH 72,
PMH 42, PML 24. The opening-range extremes never win, because the session extreme
subsumes them by construction. So PT2 is not one step past PT1 — it skips clean over 2R
half the time and does not exist the other half. **A 2R rung has to sit between them**,
and that is what makes the ladder four rungs rather than a neat ascending list.

The level the setup broke is **not** a candidate: it is behind price in the trade's
direction on **0 of 444 rows**. "PT2 = the level" was an arithmetic impossibility.

### 4.3 The survival curve is the ladder's only real input

Bar-ordered, size-gated, MFE while still alive, n=444 (`g97`):

| reaches | before any stop | share |
|---|---:|---:|
| 0.5R | 277 | 62.4% |
| 1.0R | 223 | 50.2% |
| 2.0R | 147 | 33.1% |
| 3.0R | 103 | **23.2%** |
| 4.0R | 79 | 17.8% |
| 5.0R | 49 | **11.0%** |

Conditional on reaching 2R the mean MFE is 5.23R; conditional on 3R it is 6.40R. **The
tail is fat and it is where the money lives.** 73.9% of trades stop out before 11:00.

### 4.4 Every ladder shape, priced on the same 444 rows

(`g101`. Identical population, identical fills. The 30/30/30/10 row reproduces the
committed `g99_ladder_ab.json` exactly — $92, 40.8% win, 12/25, −$16,980 — which is the
proof the replica has not drifted.)

| arm | $/day | win | months green | max DD | mean R |
|---|---:|---:|---:|---:|---:|
| book today (shipped exit) | $38 | 46.0% | 12/25 | −$20,416 | +0.038 |
| flat 2.5R | $98 | 32.7% | 14/25 | −$25,583 | +0.098 |
| 4-rung 30/30/30/10 *(g99 control)* | $92 | 40.8% | 12/25 | −$16,980 | +0.092 |
| 4-rung + ratchet trail | $91 | 40.8% | 12/25 | −$16,618 | +0.091 |
| **5-rung 30/25/20/15/10** | **$88** | 40.5% | 12/25 | −$17,841 | +0.088 |
| 5-rung 20/20/20/20/20 | $98 | 39.2% | 12/25 | −$18,542 | +0.098 |
| 5-rung 40/20/20/10/10 | $79 | 43.7% | 12/25 | −$18,152 | +0.079 |
| 4 priced + 10% free runner | $100 | 40.3% | 12/25 | −$16,795 | +0.100 |
| **4 priced + 20% free runner** | **$109** | 39.4% | 12/25 | −$16,972 | +0.109 |
| 4 priced + 20% runner, BE trail | $115 | 39.4% | **13/25** | −$17,884 | +0.115 |
| 4 priced + 30% free runner | $117 | 38.3% | 12/25 | −$17,272 | +0.117 |
| 4 priced + 40% free runner | $126 | 37.4% | 12/25 | −$17,641 | +0.126 |
| 4 priced + 60% free runner | $143 | 34.9% | 11/25 | −$18,377 | +0.143 |

### 4.5 The answer: four priced rungs and one that has no price

**He asked for five. The evidence supports four priced rungs plus an unpriced runner
tranche — five pieces, four targets.** Adding a fifth *price* at 6R makes the ladder
*worse* ($88 against $92) for a reason that is not noise: a price caps the tail, and
11.0% of trades run past 5R with a conditional mean of 6.40R. Every dollar the ladder
gains over `flat 2.5R` comes out of that tail, and a ceiling on it is a tax.

**The shipped default:**

| rung | price | size | why, with its denominator |
|---|---|---:|---|
| PT1 | session HOD/LOD at the entry bar | 24% | median 0.495R, hit fast; his rule, 113/1,263 corpus statements |
| PT2 | nearest PDH/PDL/PMH/PML beyond PT1 | 24% | exists on 220/444; median 3.148R when it does |
| PT3 | 2R, snapped to a whole dollar or named level within 0.25R | 24% | 147/444 reach it (33.1%) |
| PT4 | the further of 4R and the next named level beyond PT3 | 8% | 79/444 reach 4R (17.8%) |
| **PT5** | **no price — trailing stop, marked at 11:00** | **20%** | 49/444 run past 5R (11.0%); conditional mean MFE 6.40R |

(PT1–PT4 weights are 30/30/30/10 of the 80% that is priced.) Rungs are built causally,
sorted ascending in R, and coalesced at a 0.20R minimum gap; a rung that lands behind
price is dropped and its weight redistributed. **$109/day, 39.4% win, 12/25 green,
−$16,972 max drawdown**, against the shipped exit's $38/day.

**The runner weight is a dial, and it is monotonic.** Each 10 percentage points added to
the runner tranche is worth roughly **+$8/day** and costs roughly **−1 point of win rate**
and one green month at the extremes. 20% is the point where money improves and durability
does not degrade. If he wants durability over dollars, the breakeven-trail variant is
$115/day at 13/25 green. If he wants dollars, 40% is $126/day at 12/25. **Do not go past
60%** — that is 11/25 green and is just `flat 4R` wearing a ladder.

### 4.6 The trending test, defined

Ships as a stamped field, `open_state ∈ {trend_up, trend_dn, chop, inside, no_read}`,
computed by `g101.open_state` and written on every signal. Causal, own tape only. Its
first job is to accumulate rows: **today it is readable on 9.5% of first-of-day trades.**
It becomes a gate the day the entry moves late enough that the read exists — and §3.1 E1
says that day is not near, because every arm that waits loses money.

---

## 5. RUNNERS

A runner is a trade whose MFE while still alive reaches **3R before any stop**. There are
**103 of them in 444 first-of-day trades (23.2%)**, and they are where the money is: the
book realises +0.038R per trade while +2.141R was available while the trade was alive.

**What was tested at entry time, causally, and what it found** (17 stamped fields,
`_g100_runner_summary.json`, plus the tag cross-tab in `g104`):

| feature | runner rate | vs | n | p |
|---|---:|---|---:|---:|
| big daily range | 28.0% | 16.1% | 264 | 0.0035 |
| `dow = Tue` | 33.0% | 20.6% | 94 | 0.0114 |
| mid-placed stop | 27.7% | 19.7% | 195 | 0.0471 |
| pivot-high level | 57.1% | 22.7% | **7** | 0.032 |
| `disp` tag | 28.8% | — | 73 | — |
| `chase` tag | **17.0%** | — | 165 | — |
| setup, setup_label, level_name, tripped, confluence, bias, aligned, tier, seq, gap, pool, vol_regime, hour | *no separation* | | 444 | all ≥0.05 |

**Say this plainly: nothing the engine computes identifies a runner at entry time.** Four
features clear p<0.05 out of seventeen tested; **none clears a Bonferroni threshold of
p<0.003**, and one of the four is a weekday on n=94. The best real one — big range — moves
the rate from 23.2% to 28.0%. That is a nudge, not a classifier.

**One thing does separate runners, and it is his label.** 29.0% against 16.3%, +12.7
percentage points, **p=0.0003**, n=169 versus 423 judged symbol-days. It survives a
label-shuffle test that assumes nothing about the distribution, and it is the largest
effect in this repo.

**So the classifier's target changes.** Not "is this an S" as a grade to be matched, but
**"will this one run"** — with his 347 S symbol-days as the supervision signal, because
his S *is* a runner label wearing a grade's name. That reframing is his own: *"Scouts are
good, but runners that can run is where the money's at."* It is also the only framing the
measurements support.

---

## 6. THE BUG LIST

Ranked by money on the honest book, then by correctness.

| # | bug | evidence | cost |
|---|---|---|---|
| 1 | **Live trades a gate nobody had priced.** `live_scanner._tier` trades only `sac_grade == "S"` | `live_scanner.py:572-594`; `g104`: 88/498 days, 0.18 trades/day, $14/day laddered | **−$87/day** vs taking everything, and it fires at a sixth of the rate he asked for |
| 2 | **Live does not scale.** `OMEN_LIVE_LADDER` defaults off; live takes one flat 2R exit | `options_sizer.py:81`; the live book's one trade has `scaled: false` | **−$67/day** ($101 laddered vs $34 book exit); contradicts his 2026-09-02 answer outright |
| 3 | **Live and every published number grade differently.** `ENABLE_SAC_LADDER=1` is forced in the live process only; the 2-year book's 60-flag stamp does not contain it | `live_scanner.py:30`; `bt2y_trades_retest_on.json` meta.stamp.flags | no live figure is comparable to any backtest figure |
| 4 | **HTF bias is dead live and it is a hardcoded `None`, not a missing value.** Tastytrade 401 → `_yf_daily_context` returns bias `None` on every call | `live_scanner.py:172`; `journal/scanner-2026-09-01.log` logs `HTF unknown` 4,954 times; the backtest has a real bias on 126,314/127,188 rows (99.3%) | the bias demotions at `signal_runner.py:2501-2507` cannot fire — **live grades strictly looser than every number we publish** |
| 5 | **A wrong-signed variable sits inside the live grade.** `counter_trend_not_respected` trips on 317/498 first-of-day rows and marks better trades worse (+0.1926R tripped vs −0.0604R clean) | `g104`; `SAC_LADDER_VARSET` defaults to `shipped`, which also keeps `level_not_respected`, already flagged in CLAUDE.md | this is *why* bug #1 costs what it costs |
| 6 | **The shipped exit's "runner" rung is not a runner.** It lands **inside** its own 2R rung on 303/444 rows (68.2%), median 1.300R, and its source is a whole dollar on 389/444 (87.6%) | `g99_rung_recon`; `backtest_week.py:1032-1043` computes both and never compares them | the ladder in §4 replaces it |
| 7 | **Dedupe units differ.** Backtest suppresses a re-fire of the same *level* (2 contiguous bars); live suppresses any signal on a symbol+direction for a flat 20 minutes | `backtest_week.py:105`; `live_scanner.py:527,597-604` | live runs the arm the backtest retired |
| 8 | **Near-unreachable rules.** `stale_retest` trips 6 times in 4,022 traded rows (0.15%); `break_then_rejection` never trips on a traded row | book `downgrades` counter | the repo's named bug class — a real rule encoded as a branch that cannot be true |
| 9 | **`CONSECUTIVE_LOSS_HALT` is read, passed, printed, and never used.** `TradingSession.day_ended` hardcodes 2 | `omen_bot.py:900-905` vs `live_scanner.py:310,329` | harmless today (default == hardcoded), a trap the moment anyone changes the env var |
| 10 | **Two parallel S definitions live; only one gates.** `compute_austin_tier` (4 clauses) is computed and stamped and branched on by nothing; `rank_s_plus` is called by no shipping module | `signal_runner.py:2676-2686`, `1765`; callers only in `test_austin_tier.py`, `t8`, `t11` | dead weight that reads like a decision |
| 11 | **The live route has never been observed working.** One trade in the paper book's life; today `bars_fetched: 0`, `signals_fired_today: 0`, `last_error: rate limited` | `journal/paper-trades.jsonl`, `journal/scanner_status.json` | every live claim is untested |
| 12 | **An eleventh grade-bearing spelling, unread.** `answers.real` (n=20: 17 `no`, 3 `weak`) and `answers.regrade` (n=5: 2 `to_a`) are in no reader. `answers.wrong` (n=8) is his own per-component diagnosis and is read by nothing | field audit across 30 mark corpora vs `grade_read.ALL_FIELDS` | 25 judgements invisible; `answers.verdict` (36) is a rule ballot, correctly excluded |

### Does his belief hold?

> *"Late entries and hallucinations on candles because the rules make sense, but maybe
> just sometimes the bug is misfire and the engine just panicked and didn't understand."*

**Half right, and the right half is the expensive half.** Bugs #1–#4 are real, they are
mechanical, and between them they are worth on the order of $150/day without touching a
single rule — the engine is trading a gate that fires at 0.18/day, exiting flat when the
book scales, grading on a different ladder than every number we publish, and doing it all
with a hardcoded-null higher-timeframe bias. He is right that the engine is misfiring.

**But the rules as encoded are also not sufficient, and that is not a bug.** The
eight-variable ladder — his own variables, correctly implemented — separates his S label
at **35.0% precision against a 29.4% base rate** on 683 judged symbol-days, and catches
20.9% of the S days it sees. Nothing is panicking there; the model simply does not contain
what his eye contains. Calling that a bug would send us hunting for a fix that does not
exist. **Fix the bugs first because they are cheap and measured. Then accept that the
classifier has to be rebuilt against a target it has never been trained on.**

One correction to his premise, offered because he asked us to think like a trader rather
than agree with him: **the engine is not late.** 402 of 444 first-of-day entries fire
before 09:45, and every arm that waits loses money (§3.1 E1). What his marks actually show
is that on the *specific setup he likes*, his trigger is a few candles ahead of the
engine's — median 1 bar, mean 9.4 bars, on 103 head-to-head pairs, and only 46 of those
are endorsed and testable at p=0.137. That is an entry-*precision* problem inside a single
setup, not a session-wide latency problem, and the two need different fixes.

---

## 7. WHAT IT IS WORTH

All rows: honest close fill on entry, touch on targets, close-triggered stops floored at
−1.25R, 1R = $1,000, size-gated, `bt2y_trades_retest_on.json`, **$/day over all 498
sessions**.

| step | trades/day | $/day | win | months green | max DD |
|---|---:|---:|---:|---:|---:|
| today — first of day, shipped exit | 1.00 | **$34** | 46.5% | 12/25 | −$20,438 |
| + the ladder (§4), nothing else | 1.00 | **$101** | 39.8% | 12/25 | −$20,438 |
| + the chase veto (§3.1 E7) | 0.67 | **$114** | 41.4% | 13/25 | −$15,736 |
| durability variant: + `sgrade` S or A | 0.33 | $79 | 41.6% | **16/25** | −$8,748 |
| **ceiling — a perfect S classifier + the ladder** | 0.28 | **$111** | 56.1% | 17/24 | −$5,501 |
| his bar | — | **$397** | — | 25/25 | — |

**$114/day is what is shippable this week**, and it is 29% of his bar. It comes entirely
from two changes that are already measured: scale out with a runner tranche, and refuse
chased entries.

**The ceiling row needs reading carefully, because it is the honest bad news.** On the 139
days where Austin graded at least one symbol-day S *and* the engine had a size-gated
candidate on it, taking that first S symbol-day and running the ladder pays **$397 per
traded day, 56.1% win, 17/24 months green, max drawdown −$5,501** (n=139). That is his bar
exactly — *per day traded*. Spread across all 498 sessions it is **$111/day**, because
those 139 days are 28% of the calendar. Even generously: 255 of the 486 judged calendar
days (52.5%) carry at least one S, so a perfect classifier **with perfect recall** — the
engine currently sees only 139 of those 255 — projects to roughly **$203/day**.

**So state it without burying it: this design's ceiling is about half his bar.** A perfect
reproduction of his eye, plus a perfect ladder, plus perfect recall, on one trade a day,
lands near $203/day against $397. Taking a second S trade per day does not fix it — the
169 judged S symbol-days pay $297/trade against the first-of-day S's $397, so the second
trade dilutes rather than doubles. Closing the remaining gap requires something not yet on
the table: more R per trade than the ladder extracts, a larger universe of S-quality days
than the current detector surfaces, or accepting that the bar moves.

---

## 8. WHAT WE STILL CANNOT ANSWER

Each item names the exact cards that would answer it. None of these is a re-asked rule
question; all of them buy the one thing only he can give — the eye test on a chart.

1. **Does the S label survive outside the judged pool?** Every number in §3.1 E4 and §7's
   ceiling row is a within-judged-pool comparison, and deck cards were often chosen
   *because* the engine fired. **Cards: 60 symbol-days drawn at random from sessions the
   engine never fired on, S / none, no engine annotation.** That puts a ±12pp band on the
   base rate and tells us whether the label is a property of his eye or of our sampling.

2. **What makes a runner, in his eye, at entry?** Nothing the engine computes does it
   (§5). **Cards: 103 runner symbol-days paired blind with 103 matched non-runners — same
   setup family, same symbol pool, chart cut at the entry bar — one binary each: "would
   you still be in this past 2R?"** That is the training label the classifier actually
   needs, and it does not exist yet.

3. **What is PT2 when there is no named level?** It is missing on **224 of 444 rows
   (50.5%)**, and today the ladder silently redistributes that weight. **Cards: 40 charts
   drawn at the moment price reaches 2R, level map overlaid, one question: where does the
   third piece come off?**

4. **Can the entry move earlier without losing the arrival edge?** g98 is n=46 at p=0.137
   and cannot settle it. **Cards: 150 head-to-head pairs — his minute against the engine's
   on the same tape, same day, entry minute only.** That is the sample size that would
   turn a direction into a decision.

5. **Are the marks fully read?** `answers.real` (20 rows), `answers.regrade` (5) and
   `answers.wrong` (8) are grade- and diagnosis-bearing and no reader parses them. This
   needs no cards — it needs a reader, and an assertion in `marks_pool` that every
   `answers.*` key seen in any corpus is either consumed or explicitly excluded with a
   reason. Note what `answers.wrong` already says about the eight anatomy trades he graded
   on 2026-09-01: **entry named on 4 of 8, runner on 3, breakeven on 3, PT1 on 2,
   scale size on 2, stop on 1.** Eight cards is a hint, not a diagnosis — but it is his own
   ordering, and it is the same ordering this spec builds in.

6. **Does the live route work at all?** Not a card. One trade in the paper book's life and
   zero bars fetched today. Nothing in §3.2 can be verified live until that is fixed, and
   no live number should be quoted until it has run a clean week.

---

*Every figure here is reproducible: `research/g97_mfe.py`, `research/g99_rung_recon.py`,
`research/g99_ladder_ab.py`, `research/g101_open_and_ladder.py`,
`research/g102_wait_for_the_open.py`, `research/g103_what_its_worth.py`,
`research/g104_gate_value.py`. Verify gate green at time of writing:
`research/regression_gate.py` PASS (no baseline-fired mark went silent),
`research/test_runner_stop.py` PASS (18 laddered results, stop-outs floored at −1.25R,
wick-only days never stopped out).*
