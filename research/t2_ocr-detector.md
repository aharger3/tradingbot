# T2 — the one-candle rule is a detection problem, and the entry candle is the whole of it

**Null result: on the two numbers that decide, this does nothing.** Whole-book mean R moves
**+0.5481 → +0.5576, that is +0.0095 R against a ±0.1314 R 95% bar**, and held-out S recall
is **18 of 34 = 52.9% with the detector on and off, the identical 16 misses card for card**.

**What is not null is the detector itself.** Austin's own sentence, turned into a predicate
and run over the book's **5,394 one-candle-rule detections, keeps 141 of them — 2.7%** — and
**rejects 19 of the 20 killed OCR setups he graded "not this setup at all" / "real but not
tradeable"** (17 of 17 on the hard "no"s). The single clause doing 96% of the work is
*"strong PA entry"*: **only 36.0% of today's OCR entry candles even close in the trade's
direction**, and the median OCR entry body is **0.62× the average body of the ten bars
before it**. The engine is buying the retest on a small candle pointing the wrong way
roughly two times in three.

Turning it on takes the book from 2,595 trades to 1,971, **win rate 43.35% → 45.41%**,
**max drawdown 32.43 R → 23.81 R (−26.6%)**, months green 25/25 either way, and total R
+1,422 → +1,099. **It is a precision change, not a mean-R change.** Read it as *what belongs
behind the lifted demote (R3)*, not as a lever that reaches the money gate.

---

## What was asked and what it turned into

R3 is ratified: *"Ther is no B"* — the OCR B→C demote comes off, and T0 has already taken
it off. But in the same 123-card session he graded 20 OCR/84% setups the engine had
detected and then killed, and returned **17 "not this setup at all", 3 "real but not
tradeable", ZERO real** (`research/marks/probe_master_2026-08-29.jsonl`, lane `rare`). All
20 are `one_candle_rule` detections, matched to the book by symbol, day and minute.

So lifting the demote alone promotes garbage — and it measurably already has. **Two of his
20 refusals are TRADED in the shipped post-R3 book**: `AMZN_2024-11-29 10:32` (his verdict:
*no*) and `AAPL_2026-04-10 10:26` (his verdict: *weak*). Before R3 both were `X / skipped_d`.

The question this track answers is therefore not "should the demote come off" (settled) but
**"what is a one-candle rule"**. His answer, in the same session:

> *"s trades are all about being early and the most important thing is that clear break
> retest with displacement that happens quick and strong PA entry"*

---

## The definition, clause by clause

`omen_bot.ocr_quality` is the one implementation; the engine gates on it under `OCR_STRICT`
and `research/t2_ocr_detector.py` measures the same function, so the number and the ship
cannot drift apart.

| his clause | predicate | where the number came from | pass rate over 5,304 detections |
|---|---|---|---:|
| **clear break** | after the break, some bar's low is fully above the block (long) — price actually *left* | the LEAVE step `detect_break_retest` already enforces; the OCR path never had it. No new constant | **78.5%** |
| **retest** | `OB_RETEST_TYPES` | already `("wick_only",)`, unchanged | 100% |
| **with displacement** | `_has_displacement` ≥ `DISPLACEMENT_MULT` | already 1.5×, unchanged | 100% |
| **that happens quick** | ≤ 6 bars block→break, ≤ 10 bars break→entry | **the only new numbers**, and the sweep below shows they are not load-bearing | **88.9%** |
| **strong PA entry** | entry candle closes in the trade's direction AND body ≥ `STRONG_PA_MULT` × avg body of the prior 10 | `STRONG_PA_MULT` is the engine's **own** definition of strong price action — the 84% rule's reclaim gate. Reused, not invented; `research/test_t2_ocr.py` asserts the two constants are the same number | **4.3%** |
| | **ALL FIVE** | | **2.7% (141)** |

Retest and displacement pass at 100% because `detect_order_block_setup` already enforces
them upstream — they are in the table to show his sentence is fully accounted for, not
because they filter anything.

**"being early"** is measured and reported but deliberately **not gated**: chase is already
its own downgrade variable under R22, and gating it twice would turn a detector change into
a grader change. For the record: 891 of 5,304 detections are in the 09:xx hour and 4,413 in
the 10:xx hour, and the median entry closes 0.0513% beyond the retested level.

### Cumulative funnel, in the order he says the clauses

```
after clear_break    4165   78.5%
after retest         4165   78.5%
after displacement   4165   78.5%
after quick          3580   67.5%
after strong_pa       141    2.7%
```

---

## Reachability, before any tuning (method rule 3)

The composite **rejects 97.3%** of current OCR detections. By the letter of the rule that is
past the 85% line, and the rule is right about what it means: **this is not a threshold
finding, it is a redefinition** — which is exactly what a 17-of-20 "not this setup at all"
verdict predicts. Stated plainly so nobody reads 2.7% as a tuned number.

**The binding clause is strong PA, and its two halves are worth separating:**

- **entry candle in the trade's direction: 1,909 of 5,304 = 36.0%.** Nearly two OCR entries
  in three are a candle closing *against* the trade being taken.
- **entry body ÷ avg body of the prior 10**, deciles:
  `0.11 · 0.21 · 0.33 · 0.47 · 0.62 · 0.78 · 0.99 · 1.26 · 1.75`.
  The median OCR entry candle is **0.62×** the recent average body. His word for the entry
  is *strong*; the median one is two-thirds of ordinary.

### Sweeps — none of the three thresholds is load-bearing in the direction that matters

`quick` (bars block→break / break→entry), holding everything else at the shipped value:

| qb | qe | pass | pass% | his refusals kept | traded | mean R |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 5 | 73 | 1.4% | 0 of 20 | 16 | +2.6299 |
| 4 | 10 | 129 | 2.4% | 1 of 20 | 21 | +2.9431 |
| **6** | **10** | **141** | **2.7%** | **1 of 20** | **25** | **+2.4623** |
| 8 | 20 | 173 | 3.3% | 1 of 20 | 29 | +2.6029 |
| 999 | 999 | 177 | 3.3% | 1 of 20 | 29 | +2.6029 |

Removing the clause entirely (999/999) changes the pass count by 36 and the refusal
rejection by nothing. **6/10 is a documented convenience, not a fitted parameter.**

`displacement` multiple (shipped 1.5×): 1.5× → 141 pass; 2.0× → 89; 2.5× → 50; 3.0× → 31;
4.0× → 7. Tightening past 2.5× drops below the 1% reachability floor. Left at 1.5×.

`strong PA` multiple (shipped 1.5×, = `STRONG_PA_MULT`):

| mult | pass | pass% | refusals kept | traded | mean R | win% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 1,220 | 23.0% | 1 of 20 | 374 | +0.7088 | 36.9% |
| 0.50 | 611 | 11.5% | 1 of 20 | 125 | +1.3626 | 51.2% |
| 1.00 | 318 | 6.0% | 1 of 20 | 56 | +1.5049 | 55.4% |
| **1.50** | **141** | **2.7%** | **1 of 20** | **25** | **+2.4623** | **64.0%** |
| 2.00 | 70 | 1.3% | 0 of 20 | 10 | +2.9427 | 70.0% |
| 3.00 | 18 | 0.3% | 0 of 20 | 2 | +0.3905 | 50.0% |

Note the first row: **`mult = 0` — direction only, no body requirement at all — already
takes the slice from +0.5915 R to +0.7088 R and cuts it to 23% of its size.** Most of the
value in this clause is the sign of the candle, not its size.

---

## Validation on his 20 refusals

A definition of his setup should reject setups he says are not his setup. Each card is
matched to the exact detection minute his chart was drawn on (`sym_day_ET`), not just the
symbol-day — a symbol-day can carry several OCR detections and scoring the wrong one is
silently wrong.

| card | his verdict | strict verdict | clause(s) that killed it |
|---|---|---|---|
| COIN 2026-06-17 09:50 | no | rejected | strong_pa |
| UBER 2026-07-09 10:28 | no | rejected | clear_break, strong_pa |
| BABA 2026-01-06 10:46 | no | rejected | clear_break, strong_pa |
| MU 2025-04-30 09:55 | no | rejected | quick, strong_pa |
| AAPL 2025-01-28 09:52 | no | rejected | strong_pa |
| PLTR 2024-09-04 10:47 | no | rejected | clear_break, strong_pa |
| PLTR 2024-11-25 10:20 | no | rejected | strong_pa |
| CRM 2026-06-24 10:27 | no | rejected | clear_break, strong_pa |
| PLTR 2026-07-15 10:44 | no | rejected | strong_pa |
| NFLX 2024-08-22 10:12 | no | rejected | clear_break, strong_pa |
| NFLX 2025-03-25 10:40 | weak | rejected | strong_pa |
| **AAPL 2026-04-10 10:26** | **weak** | **SURVIVES** | — *(traded in the shipped book)* |
| META 2025-12-03 10:20 | no | rejected | strong_pa |
| GOOGL 2025-07-18 10:05 | weak | rejected | clear_break, strong_pa |
| NVDA 2025-09-18 09:57 | no | rejected | strong_pa |
| NVDA 2026-04-10 09:55 | no | rejected | clear_break, strong_pa |
| **AMZN 2024-11-29 10:32** | **no** | **rejected** | clear_break, strong_pa *(traded in the shipped book)* |
| AMD 2026-04-08 10:46 | no | rejected | clear_break, strong_pa |
| ACHR 2026-07-28 10:44 | no | rejected | clear_break, strong_pa |
| HOOD 2025-04-29 10:20 | no | rejected | quick, strong_pa |

**19 of 20 rejected (95%).** The one survivor is `AAPL_2026-04-10`, and it is one of his
three **"weak"** answers — *real but not tradeable* — not one of his 17 hard "no"s. On the
17 hard refusals the definition is **17 of 17**.

**The two refusals R3 promoted into real trades:** the strict detector removes the one he
called *no* (`AMZN_2024-11-29`) and keeps the one he called *weak* (`AAPL_2026-04-10`).

---

## What it costs and what it buys

### Inside the OCR slice (from the shipped book, no re-run needed)

| slice | n detections | traded | mean R | win rate |
|---|---:|---:|---:|---:|
| all OCR detections | 5,304 | 564 | +0.5915 | 37.94% |
| **passing his definition** | **141** | **25** | **+2.4623** | **64.0%** |
| failing his definition | 5,163 | 539 | +0.5047 | 36.73% |

pass − fail = **+1.9576 R against a ±1.7116 R 95% bar** — outside its bar, but by 14%, on
**n = 25**. Read the sign as established and the size as not. This is the same warning T0
gave about the disaster stop and it applies harder here: 25 trades over two years is about
one a month.

### Whole book, `OCR_STRICT` off vs on

Two full 730-day replays, both produced by `backtest_2y.py` and compared by
`research/t2_ocr_detector.py --compare`.

| figure | OFF (shipped) | ON (`OCR_STRICT=1`) | move |
|---|---:|---:|---:|
| signals detected | 75,953 | 69,316 | −6,637 |
| — `one_candle_rule` | **5,394** | **236** | **−5,158** |
| — `reentry_84_rule` | 322 | 248 | −74 |
| — `break_and_retest` | 70,237 | 68,832 | −1,405 |
| **traded** | 2,595 | **1,971** | −624 |
| — OCR traded | 572 | **54** | −518 |
| — 84% traded | 319 | 245 | −74 |
| — B&R traded | 1,704 | 1,672 | −32 |
| **mean R** | +0.5481 | **+0.5576** | **+0.0095** |
| **win rate** | 43.35% | **45.41%** | **+2.06 pts** |
| total R | +1,422.33 | +1,099.02 | −323.31 |
| profit factor | 1.9732 | 2.0248 | +0.052 |
| **max drawdown** | 32.43 R | **23.81 R** | **−8.62 R (−26.6%)** |
| months green | 25/25 | 25/25 | 0 |
| worst month | +6.01 R | +5.21 R | −0.80 R |
| traded, his ladder S | 348 | 201 | −147 |
| traded, his ladder A | 570 | 409 | −161 |
| traded, his ladder C | 1,677 | 1,361 | −316 |
| sessions with a signal | 500 | 499 | −1 |

**mean R moves +0.0095 R against a ±0.1314 R 95% bar. That is INSIDE the bar — a null
result**, and it is the headline number for the whole-book arm.

What is *not* null:

| slice | move | 95% bar | verdict |
|---|---:|---:|---|
| OCR slice mean R (n 572 → 54) | **+1.3764 R** | ±0.9463 | outside |
| B&R slice mean R (n 1,704 → 1,672) | −0.0354 R | ±0.1436 | **inside — the knock-on is null** |

**Why 236 detections and not 141.** The funnel above says 141 of the *recorded* detections
pass. The book records signals **after** the 30-bar dedupe, and 5,158 fewer fires means far
fewer are swallowed as repeats: of the 236 OCR detections in the ON book, **141 are exactly
the funnel's 141, and 95 are detections the OFF book never recorded at all** because a
now-rejected earlier fire was suppressing them. Both numbers are correct; they count
different things.

**The 84% rule moves without being touched.** `_arm_84` arms off stop-outs, and 518 fewer
OCR trades means 74 fewer 84% signals (322 → 248). Its mean R is unchanged (+0.1804 →
+0.1823). Anyone reading the 84% slice after this flag lands should know it shrank for this
reason and not because T3 changed anything.



### Held-out recall — the gate that governs (method rule 2)

Both arms re-run in this worktree so the comparison is apples-to-apples
(`research/t0_heldout_recall.py`, unmodified; 2 of the 100 sweep days have no archived bars
in this checkout and are excluded from **both** arms).

| set | OFF | ON |
|---|---|---|
| `probe_s_sweep_2026-08-28` S recall | **18 / 34 = 52.9%** | **18 / 34 = 52.9%** |
| — the missed 16 | identical, card for card | identical |
| precision on the 100 blind cards | 36.0% (32 false fires of 66) | 36.7% (31 of 66) |
| `probe_master_2026-08-29` lane=vetoes, his 5 S | 0 of 5 | 0 of 5 |
| his 4 A | 0 of 4 | 0 of 4 |
| false fires on his 27 "no" | 2 (7.4%) | 2 (7.4%) |

**Recall does not move. One false fire of 66 is removed.** By method rule 2 this is the
number that decides, and on it **this is a null result**.

`python research/regression_gate.py` is **PASS and byte-identical with the flag on and off**
(`any_signal 80, s_grade 5, +5 new fires, nothing went silent`) — the detections the strict
definition removes were never the ones producing the gate's fires.

---

## What this means

1. **His verdict was right and it is now quantified.** 17 of 20 "not this setup at all" maps
   onto a definition that rejects 17 of 17 of those cards, and the reason is nearly always
   the same one: the entry candle. Two-thirds of OCR entries close against the trade.
2. **R3 alone does promote garbage, and it has.** Two of his own refusals became trades.
   `OCR_STRICT` removes the one he called *no*.
3. **This is not a money-gate lever, and it costs 624 trades.** Whole-book mean R is inside
   its bar. What it actually buys is +2.06 points of win rate and a **26.6% smaller max
   drawdown**; what it costs is −323 R of total return and **147 fewer trades he would grade
   S** (348 → 201). Anyone stacking it in T22/T23 should stack it as a **precision /
   drawdown** change, and should notice that on a mean-R gate it is free but not helpful.
4. **The unreachable-rule bug class did not fire here, but it nearly did in reverse.**
   `clear_break` — the LEAVE step — has existed in `detect_break_retest` since the ordered
   B&R FSM landed and was simply never applied to the OCR path. 21.5% of OCR detections are
   chop on the level that the B&R detector would have refused on the same bars.

## Ship

`OCR_STRICT`, **default OFF** (method rule 4: R3 ships ON because it is ratified; this is
the new lever and it ships behind a flag).

**Recommendation: ship it, default OFF, and let T22 decide.** The case FOR turning it on is
his own verdict (19 of 20 refusals rejected), 26.6% less drawdown, and +2 points of win
rate. The case AGAINST is that it deletes 147 trades he would grade S, gives up 323 R of
total return, and moves neither of the two gates that govern. That trade is a judgement
about book size versus book cleanliness, which is an adjudication call over the whole stack,
not a call this track can make alone — and see the Austin blocker below.

## The one thing only Austin can settle

**Put 12 charts in front of him: the 6 OCR entries the strict detector KEEPS and the 6 it
DELETES that he would most plausibly have taken — each drawn on the entry candle, with one
question: "is this candle a strong PA entry?"**

The reason: `strong_pa` is doing 96% of the filtering, and its whole content is one
threshold on one candle. The sweep is monotone — 0.0× keeps 1,220 detections at +0.71 R,
1.5× keeps 141 at +2.46 R, 2.0× keeps 70 at +2.94 R and 3.0× collapses to 18 at +0.39 R —
so the number is not determined by the data, it is determined by what he means by *strong*.
The engine currently answers it with `STRONG_PA_MULT = 1.5`, a constant borrowed from the
84% rule's reclaim gate, and nobody has ever asked him whether that is his answer for the
OCR entry too. **147 of his own S-graded trades hang on it.** Twelve charts, one question,
and the constant stops being a guess.

## Artefacts

| file | what it is |
|---|---|
| `omen_bot.py::ocr_quality` / `ocr_is_his` | the definition, one implementation |
| `signal_runner.py::OCR_STRICT` | the flag, both OCR emit sites |
| `research/t2_ocr_detector.py` | every number in this report |
| `research/test_t2_ocr.py` | 15 checks — one bar sequence per clause, plus the two invariants (`OCR_STRONG_PA_MULT == STRONG_PA_MULT`, `OCR_STRICT` off by default) and a standing assertion that ≥18 of his 20 refusals are rejected |
| `research/_t2_ocr_features.json` | the replayed anatomy of 5,304 detections |
| `research/_t2_heldout_base.json` / `_t2_heldout_strict.json` | held-out recall, both arms |

Reproduce:

```
python research/t2_ocr_detector.py --stage1      # ~7 min, writes _t2_ocr_features.json
python research/t2_ocr_detector.py --report      # stages 2-4
OCR_STRICT=1 python backtest_2y.py --days 730 --out research/_t2_ocr_strict_book.json
python research/t2_ocr_detector.py --compare research/bt2y_trades.json research/_t2_ocr_strict_book.json
python research/t0_heldout_recall.py --out research/_t2_heldout_base.json
OCR_STRICT=1 python research/t0_heldout_recall.py --out research/_t2_heldout_strict.json
```

## Caveats

- **90 of 5,394 detections (1.7%) could not be replayed** — the recomputed structure at that
  bar did not land on the same minute the book recorded. Every rate in this report is over
  the 5,304 that did. All 20 of his refusals replayed.
- **The 25-trade arm.** The OCR slice's mean-R edge clears its bar by 14% on n = 25.
- **2 of 100 sweep days have no archived bars in this checkout**, so held-out precision is
  over 98 cards. Both arms were re-run here, so the OFF/ON comparison is unaffected; the
  36.0% OFF figure is therefore not identical to T0's published 35.3% (which was over 100).
- **`clear_break` and `quick` were not A/B'd on their own** at book level. The three-clause
  composite is what ran. The static funnel and the sweeps above are the only per-clause
  evidence; a per-clause book arm is a full 730-day run each.
- **The strict detector is not confined to the OCR slice.** The B&R slice loses 32 trades
  and 0.0354 R (inside a ±0.1436 R bar, so null) and the 84% slice loses 74 trades, both
  through dedupe and `_arm_84` knock-on. The 236/141 reconciliation above is the same
  effect. Nothing here is a clean single-slice change.
- **Win rate is `r > 0` over all traded rows.** T0 published 43.06% for the same OFF book
  using a different denominator; this report computes both arms with one function
  (`research/t2_ocr_detector.py::_book_stats`) so the OFF/ON comparison is internally
  consistent, and the OFF figure reads 43.35% here for that reason alone.
- **One session disappears** (500 → 499): a day whose only signals were rejected OCR fires.
- **No options, contracts, spreads or futures** — every R here is the underlying.
- **The 84% rule is untouched.** His rare lane mixed OCR and 84% cards; all 20 that came
  back happened to be OCR, so this track says nothing about the 84% detector. That is T3.
