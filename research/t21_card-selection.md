# T21 — card selection: stop spending his attention on cards that don't fit

Run 2026-08-29 on the ratified engine (T0, `9edd2ba7`).
Script: `research/t21_card_filter.py` · Test: `research/test_t21_card_filter.py`
Wired into: `research/build_deck.py::pick()`

Reproduce every number below with:

```
python research/t21_card_filter.py --auc --cv --sweep --pool 400
python research/test_t21_card_filter.py
```

---

## Headline

**A pre-filter cuts the share of a deck Austin refuses from 71.1% to 47.4% while keeping
76.9% of the cards he engages with — an effect of +41.1 points against a ±19 point 95% bar
(Fisher p = 0.000037). It is not null.** Under nested cross-validation, with the thresholds
refit inside every fold, the out-of-sample keep-rate is **47.1% ± 2.8** against a 28.9% base
rate, so the effect survives the fit.

**But three of the five criteria the spec named do not exist in his labels.** "Clean level",
"real displacement" as break-bar size, and "plausible RR" all rank at chance (AUC 0.48–0.52).
What replaces them is the opposite of one of them: the cards he refuses have their next
structure **eight R away**, the cards he grades have it at **two-and-a-half R**. A big paper
RR is a symptom of a bad card, not a good one.

---

## What he actually said

`research/marks/probe_master_2026-08-29.jsonl`, 123 rows, 90 of them cards:

> "Sometimes in certain categories I had to give u the same answer over and over, you know
> better not to give me old trades that don't fit my system."

> "The chop is really really bad" · "too choppy" · "Later in the day lower probability" ·
> "you know better" · "what am I looking at you know this is wrong easilly"

## The label set — 26 graded, 64 refused

| lane | n | KEEP (he engaged) | REJECT (he refused) | what KEEP means |
|---|---:|---:|---:|---|
| `vetoes` | 40 | 13 | 27 | he gave the card a grade s/a/c |
| `runner` | 15 | 10 | 5 | he gave the card an exit plan |
| `rare` | 20 | 0 | 20 | 17 "not this setup at all" + 3 "real but not tradeable" |
| `index` | 15 | 3 | 12 | he called the day an S |
| **total** | **90** | **26** | **64** | **he refused 71.1% of what he was handed** |

`vetoes` + `runner` (55 cards) is the **fit set** — those are the two lanes where the
question asked was literally "would you trade this card". `rare` + `index` (35 cards) is
**held out** and the thresholds never saw it.

All 90 cards have archive bars. Three (`INTC_2026-08-17`, `AVGO_2026-07-23`,
`IREN_2026-08-03`) existed only in the working tree and are committed with this report so the
numbers reproduce from a clean checkout.

---

## Reachability first (method rule 3)

Trip rates on all 90 cards, measured **before** any threshold was chosen:

| check | trips | rate | verdict |
|---|---:|---:|---|
| `window` | 0 / 90 | **0.0%** | **DEAD by construction** — see below |
| `chop` | 26 / 90 | 28.9% | reachable |
| `reach` | 27 / 90 | 30.0% | reachable |
| `displacement` | 15 / 90 | 16.7% | reachable |

**`window` is the fifth instance of this project's unreachable-rule bug class.** The spec
asks for an "in-window" check, and it can never fire on a card the engine proposed: the
engine's own 11:00 entry cutoff (`t4_engine_recall.ENTRY_CUTOFF`) already enforces it
upstream. Every one of his 90 cards is in-window. The check stays in the code as a structural
assertion for hand-added cards and `test_t21_card_filter.py` **pins it as dead**, so nobody
tunes a threshold that cannot fire.

A tighter version — banning 10:45–11:00 entries — *is* reachable, and the sweep rejects it:
it costs more graded cards than it saves refusals (F1 0.613 vs 0.625). That agrees with R13,
which is explicit that 10:45–11:00 is "a bad **entry** window, noted not banned".

---

## Three of the five spec criteria are at chance

Ranking AUC over the 75 entry-anchored cards, 23 he graded vs 52 he refused. 0.5 = a coin.

| feature | AUC (all) | AUC (fit) | reading |
|---|---:|---:|---|
| **reach** — R to the *furthest* watched level ahead, **lower better** | **0.762** | **0.750** | strongest, and inverted |
| **entry minute**, earlier better | 0.717 | 0.671 | real |
| **chop** — Kaufman ER over 09:30–11:00 | 0.666 | 0.711 | real |
| **displacement** — best 3-bar close move in the prior 10, in ATR | 0.619 | 0.607 | weak but real |
| SPEC clean-level: nearest-level distance, lower better | 0.515 | 0.522 | **chance** |
| SPEC clean-level: touch count, lower better | 0.550 | 0.486 | **chance** |
| SPEC clean-level: levels within 1 ATR, lower better | 0.440 | 0.429 | **inverted** |
| SPEC displacement: break-bar range / prior 10 | 0.453 | 0.436 | **inverted** |
| SPEC displacement: break-bar **body** / prior 10 | 0.515 | 0.421 | **chance/inverted** |
| SPEC displacement: widest of the last 5 bars | 0.424 | 0.428 | **inverted** |
| SPEC displacement: 5-bar close move / ATR | 0.481 | 0.492 | **chance** |
| SPEC plausible-RR: RR to the *nearest* level | 0.480 | 0.481 | **chance** |
| alt chop: ER over the prior 15 bars | 0.472 | 0.458 | **chance** |
| alt chop: ER over the prior 30 bars | 0.666 | 0.651 | real, ≈ session ER |
| volume on the entry bar / prior 10 | 0.411 | 0.447 | inverted |
| risk in ATR | 0.579 | 0.549 | chance |

**Nine definitions were tried for the spec's three failing criteria — three for "clean level",
four for "real displacement", two for RR — and not one separates his labels.** All are
computed by `features()` as `dx_*` diagnostic fields and printed by `--auc`, so the claim is
reproducible rather than asserted. Several point the *wrong way*: on the fit set the cards he
graded have a **smaller** break bar than the ones he refused.

### The surprise: big RR is a symptom of a bad card

`reach` is the distance to the **furthest** of the six watched levels in the entry's
direction, divided by the stop distance.

| | median `reach` |
|---|---:|
| cards he graded | **2.66 R** |
| cards he refused | **7.24 R** |

A level 8R away is not a target. It means price is in no-man's-land with no structure near
it, which is exactly the "what am I looking at" card. The naive reading — "filter for
plausible RR, keep the big ones" — would have made the deck **worse**.

### One feature was deliberately thrown away

The single strongest thing found (AUC 0.675) was **how far price travelled after the proposed
entry**. It is excluded and must stay excluded: selecting cards on it would stack every future
deck with winners and corrupt the grading the filter exists to protect. Nothing in
`features()` reads a bar after the entry except the session-level chop measure, which
describes the chart he is shown.

---

## The filter

```python
DEFAULT = {
    "late_window":     "11:00",   # dead on engine-proposed cards; kept for hand-added ones
    "min_er_session":  0.05,      # Kaufman efficiency ratio 09:30-11:00
    "max_reach_r":     8.0,       # R to the furthest watched level ahead
    "min_impulse_atr": 1.2,       # best 3-bar close move in the prior 10, in ATR
}
```

A card with **no proposed entry** — the silent half of a mixed deck — is judged on `chop`
alone. The entry-anchored checks are *skipped*, not failed. If they were applied, every silent
day would be dropped and the deck would lose its recall half entirely; that is asserted in the
test.

### Against his 90 verdicts

| | n | pass | he grades the passing | he grades the dropped | effect | 95% CI | Fisher p | recall |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| **all 90** | 90 | 38 | **52.6%** (20/38) | 11.5% (6/52) | **+41.1 pts** | [+21.9, +57.2] | 0.000037 | 20/26 = **76.9%** |
| fit (vetoes+runner) | 55 | 24 | 70.8% (17/24) | 19.4% (6/31) | +51.5 pts | [+25.3, +69.0] | 0.0002 | 17/23 = 73.9% |
| **held-out (rare+index)** | 35 | 14 | 21.4% (3/14) | **0.0%** (0/21) | +21.4 pts | [+0.7, +47.6] | **0.0556** | 3/3 = **100%** |

Read as a deck: **he refuses 71.1% of an unfiltered deck and 47.4% of a filtered one**, and
he still sees 20 of the 26 cards he would have engaged with.

On the held-out lanes the filter drops **21 of 32 refusals and loses none of his 3 keeps** —
but with only 3 positives the Fisher p is **0.0556**, i.e. *at the edge*. The held-out lift is
directionally right and statistically marginal. Say so.

### Nested cross-validation — the honest out-of-sample number

Thresholds refit inside every fold, 5 folds × 20 seeds, over all 90 cards:

| | value |
|---|---|
| out-of-fold keep-rate of passing cards | **47.1% ± 2.8** (min 40.0, max 51.4) |
| out-of-fold recall of his graded cards | 62.9% ± 6.8 |
| base rate to beat | 28.9% |
| cards passing per fold-set | 34.6 of 90 |

The out-of-sample lift is **+18.2 points, 6.5 standard deviations clear of the base rate**.
Recall falls from 76.9% (fitted) to 62.9% (out-of-fold), which is the honest cost of the fit.

### The threshold surface is a plateau, not a knife edge

Of 540 grid points, the top ten span F1 0.610–0.625 across three different `late_window`
values, two `max_reach_r` values and both `min_impulse_atr` values. Only `min_er_session =
0.05` is common to all of them — the chop floor is the load-bearing number and the rest are
nearly free.

### Ablation

| filter | pass | graded-rate of passing | recall |
|---|---:|---:|---:|
| all four checks | 38 | 52.6% | 76.9% |
| − window | 38 | 52.6% | 76.9% | (identical — the check is dead) |
| − chop | 57 | 38.6% | 84.6% |
| − reach | 53 | 39.6% | 80.8% |
| − displacement | 43 | 48.8% | 80.8% |

`chop` and `reach` each carry ~13 points of graded-rate. `displacement` carries ~4.

---

## What it costs — the six cards he graded that it drops

| card | lane | dropped for | his note |
|---|---|---|---|
| `AAPL_2026-05-08` | vetoes | displacement | (graded A) |
| `QQQ_2026-05-07` | vetoes | reach | "Earlier entries" |
| `BABA_2025-07-23` | vetoes | reach, displacement | (graded A) |
| `GOOGL_2025-04-17` | vetoes | reach, displacement | (graded C) |
| `COIN_2025-03-31` | runner | chop | "LODD AND HTF LEVELS IF THEY EXIST" |
| `TSLA_2025-08-13` | runner | chop | (gave a level exit) |

Two of the six are C-grades and two carry notes saying the *good* trade was elsewhere on the
chart. Only `AAPL_2026-05-08` and `BABA_2025-07-23` are clean A-grades lost outright.

## What still slips through — his refusals the filter keeps

13 of the 18 false fires are the two lanes the filter was **not** built for: 6 `rare` cards
(setups he says are not setups at all — that is T2's detector problem, not a card-selection
problem) and 5 `index` cards (judged on chop alone because they carry no proposed entry).

Of the 5 vetoes that slip through, **three carry a note saying the good trade is a candle or
two away**: `BABA_2026-02-17` "Few candles later good trade", `MU_2026-01-09` "2 candles
earlier s". Those are not bad cards — they are cards with the wrong minute on them, which is
**T12's** deliverable, not T21's. The filter cannot fix a card whose only fault is its
timestamp.

---

## Pool survival — what fraction of the sampling pool gets through

Random sample of 400 of the 16,820 archived symbol-days, seed 21:

| card kind | survives | 95% CI |
|---|---:|---|
| whole-session (the silent half, `chop` only) | **273 / 390 = 70.0%** | [65.3%, 74.3%] |
| entry-anchored (the fire half, all four checks) | **71 / 138 = 51.4%** | [43.2%, 59.6%] |

Of the 400 sampled days the engine fires on 138 (34.5%) and is silent on 262. On the fire
half the rejections split: `chop` 40 (29.0%), `displacement` 24 (17.4%), `reach` 15 (10.9%);
`window` 0, as predicted.

**No deck is starved.** The no-repeat guard leaves 15,326 unjudged archived days; at 51.4%
and 70.0% survival that is ~2,700 eligible fire cards and ~7,100 eligible session cards —
four orders of magnitude more than the 30 + 30 a deck needs. A live build confirms it: `pick(4,
seed=21, max_probe=30)` filled its 4 cards after dropping 4 of 8 probed days.

---

## Wired in

`research/build_deck.py::pick()` now runs every candidate through the filter before it can
enter a deck. `--no-prefilter` reproduces a pre-T21 deck and prints a warning saying so. Each
card's manifest row records `prefilter: {er_session, reach_r, impulse_atr, et}` — the reason
it was allowed in front of him.

`research/test_t21_card_filter.py` asserts, in order:

1. His 90 verdicts still read 26 graded / 64 refused, per lane. If someone reinterprets a
   lane, the filter is not silently re-scored against a different label set.
2. `window` is still dead at 0/90 and the other three are still reachable.
3. The published numbers reproduce (38 pass, 20 tp, 18 fp, +41.1 pts, p < 0.001).
4. Held-out: 3/3 keeps survive, 21 refusals dropped.
5. A session card with no entry is judged on chop alone.
6. The two chance-level spec criteria are still at chance.
7. **`build_deck.pick()` actually calls it** — a deck built through `pick()` contains no card
   the filter would drop, and every card records why it passed. The filter is worthless if the
   deck generator forgets to call it, and that is precisely the failure mode
   `omen-no-repeat-guarantee` already hit three times.

---

## Caveats

1. **The held-out lift is marginal.** Fisher p = 0.0556 on `rare`+`index` with only 3
   positives. The Newcombe interval excludes zero by 0.7 points. Directionally right,
   statistically at the edge.
2. **Three of the five spec criteria are dropped, not implemented.** Clean level, break-bar
   displacement and nearest-level RR are at chance on his labels. They may be real and merely
   mis-defined here: **nine** definitions across the three were tried and none separated
   (`--auc` prints all nine). That is a finding about these nine definitions, not proof the
   concepts are empty. The one displacement measure that does work — the best 3-bar close
   move in the prior 10 bars — is about the *approach*, not the entry bar.
3. **`window` is dead and shipped dead.** Deliberately, with a test pinning it.
4. **n = 26 positives.** Everything here rests on 26 cards he engaged with. The nested CV is
   the guard against reading too much into that, and it is why the recall figure to quote is
   62.9%, not 76.9%.
5. **This is a card-selection filter over completed sessions and must never be wired into
   detection.** It reads the whole 09:30–11:00 session for its chop measure. In
   `backtest_week` or `live_scanner` that is look-ahead.
6. **No effect on any money number.** Nothing in T21 touches the engine, the book, or the
   backtest. `python research/regression_gate.py` is unchanged: any_signal 80, s_grade 5,
   PASS.
7. **The `rare` lane is out of scope by construction.** 6 of its 20 cards pass. He said those
   setups are not setups at all — fixing that is T2's detector work, and no card-level filter
   reaches it.

## For Austin

The filter drops two cards he graded A (`AAPL_2026-05-08`, `BABA_2025-07-23`) to buy a
24-point cut in refused cards. That trade is a judgement call about his own time and only he
can price it — see the blocker in the track summary.
