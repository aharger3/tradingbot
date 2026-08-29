# T21 — card selection: stop spending his attention on cards that don't fit

Run 2026-08-29 on the ratified engine (T0, `9edd2ba7`).
Script `research/t21_card_filter.py` · test `research/test_t21_card_filter.py` ·
wired into `research/build_deck.py::pick()`.

```
python research/t21_card_filter.py --auc --sweep --cv --pool 400
python research/t21_card_filter.py --ssweep      # the held-out S-day cost
python research/t21_card_filter.py --tradeoff    # the frontier that chose the config
python research/test_t21_card_filter.py
```

---

## Headline

**The deck pre-filter is one rule: reject a card whose furthest watched level ahead is more
than 8R away.** It cuts the share of a deck Austin refuses from **71.1% to 63.5%** — an effect
of **+25.4 points, 95% CI [+5.3, +39.7], Fisher p = 0.0211** — while keeping **88.5%** of the
cards he graded and **94.4% (17 of 18)** of the engine's own cards on the held-out S days it
fires on. **On the held-out `rare`+`index` lanes the same lift is NULL** (+11.1 points, CI
[−22.1, +28.1], p = 1.0), so read the direction as established and the size as not.

Four things worth stopping for:

1. **Four of the five criteria the spec named do not exist in his labels.** In-window, not
   chop, clean level and real displacement are all switched **off in the shipped config**, and
   three of them rank at chance across nine separate definitions.
2. **The one that survives is the inverse of the one the spec asked for.** "Plausible RR"
   becomes "reject implausible RR": the cards he refuses have their next structure a median
   **7.24R** away, the cards he grades **2.66R**.
3. **The best-fitting filter is the wrong filter.** A four-check version fitted to his
   refusals scores +41.1 points (p = 0.000037) — and throws away **8 of the 18** engine cards
   on his held-out S days. Method rule 2 says held-out recall governs, so it is not shipped.
   The trade-off curve that made that call is below.
4. **The silent half of a deck is not filtered at all**, also by measurement: chop-filtering
   whole-session cards is null on the 100-card S sweep (+3.6 points, p = 0.82) and costs 9 of
   his 34 S days. Pure cost.

---

## What he said

`research/marks/probe_master_2026-08-29.jsonl`, 123 rows, 90 of them cards:

> "Sometimes in certain categories I had to give u the same answer over and over, you know
> better not to give me old trades that don't fit my system."

> "The chop is really really bad" · "too choppy" · "Later in the day lower probability" ·
> "you know better" · "what am I looking at you know this is wrong easilly"

## The label set — 26 graded, 64 refused

| lane | n | KEEP | REJECT | what KEEP means |
|---|---:|---:|---:|---|
| `vetoes` | 40 | 13 | 27 | he gave the card a grade s/a/c |
| `runner` | 15 | 10 | 5 | he gave the card an exit plan |
| `rare` | 20 | 0 | 20 | 17 "not this setup at all" + 3 "real but not tradeable" |
| `index` | 15 | 3 | 12 | he called the day an S |
| **total** | **90** | **26** | **64** | **he refuses 71.1% of what he is handed** |

`vetoes`+`runner` (55) is the **fit set** — the two lanes that literally asked "would you
trade this card". `rare`+`index` (35) is held out.

A **second, fully independent corpus** governs the cost side:
`research/marks/probe_s_sweep_2026-08-28.jsonl`, 100 cards, 34 S / 66 no. It shares no card
with `probe_master` and was never fitted on.

All 90 cards have archive bars. Three (`INTC_2026-08-17`, `AVGO_2026-07-23`,
`IREN_2026-08-03`) existed only in the working tree and are `git add -f`'d with this report so
the numbers reproduce from a clean checkout.

---

## Four of the five spec criteria are at chance

Ranking AUC over the 75 entry-anchored cards, 23 graded vs 52 refused. 0.5 = a coin.
Reproduce with `--auc`.

| feature | AUC (all) | AUC (fit) | verdict |
|---|---:|---:|---|
| **reach** — R to the *furthest* watched level ahead, **lower better** | **0.762** | **0.750** | **SHIPPED** |
| entry minute, earlier better | 0.717 | 0.671 | real, but see R13 |
| chop — Kaufman ER over 09:30–11:00 | 0.666 | 0.711 | real, and **off** — costs S days |
| displacement — best 3-bar close move in the prior 10, ATR | 0.619 | 0.607 | weak, and **off** |
| SPEC clean-level: nearest-level distance | 0.515 | 0.522 | **chance** |
| SPEC clean-level: touch count | 0.550 | 0.486 | **chance** |
| SPEC clean-level: levels within 1 ATR | 0.440 | 0.429 | **inverted** |
| SPEC displacement: break-bar range / prior 10 | 0.453 | 0.436 | **inverted** |
| SPEC displacement: break-bar **body** / prior 10 | 0.515 | 0.421 | **chance/inverted** |
| SPEC displacement: widest of the last 5 bars | 0.424 | 0.428 | **inverted** |
| SPEC displacement: 5-bar close move / ATR | 0.481 | 0.492 | **chance** |
| SPEC plausible-RR: RR to the *nearest* level | 0.480 | 0.481 | **chance** |
| alt chop: ER over the prior 15 bars | 0.472 | 0.458 | chance |
| alt chop: ER over the prior 30 bars | 0.666 | 0.651 | ≈ session ER |
| volume on the entry bar / prior 10 | 0.411 | 0.447 | inverted |
| risk in ATR | 0.579 | 0.549 | chance |

**Nine definitions were tried across the spec's three failing criteria — three for "clean
level", four for "real displacement", two for RR — and not one separates.** All are computed
as `dx_*` fields in `features()` and printed by `--auc`, so this is reproducible rather than
asserted. Several point the *wrong way*: on the fit set the cards he graded have a **smaller**
break bar than the ones he refused.

### The surprise: big RR is a symptom of a bad card

`reach` = distance to the **furthest** of the six watched levels in the entry's direction,
over the stop distance.

| | median `reach` |
|---|---:|
| cards he graded | **2.66 R** |
| cards he refused | **7.24 R** |

A level 8R away is not a target. It means price is in no-man's-land with no structure near
it — which is exactly the "what am I looking at" card. The naive reading of "filter for
plausible RR" would have kept the big ones and made the deck **worse**.

### One feature was deliberately thrown away

The strongest single feature found (AUC 0.675) was **how far price travelled after the
proposed entry**. It is excluded and must stay excluded: selecting on it would stack every
future deck with winners and corrupt the grading the filter exists to protect. Nothing in
`features()` reads a post-entry bar except the session-level chop measure, which describes the
chart he is shown — and that one is switched off anyway.

---

## The decision: the frontier, not the best fit

Two axes at once, over all 540 grid points (`--tradeoff`):

* **x** — how much of his attention the filter saves on `probe_master`
* **y** — how many of the engine's own cards it keeps on the **18** held-out S days the engine
  fires on (it fires on 18 of his 34; that 52.9% is the same recall `DIRECTION.md` carries)

| config | cards passed | he grades them | lift | p | **S-day cards kept** |
|---|---:|---:|---:|---:|---:|
| no filter | 90 | 28.9% | — | — | 18/18 = 100% |
| **reach ≤ 8R  ← SHIPPED** | **63** | **36.5%** | **+25.4** | **0.0211** | **17/18 = 94.4%** |
| reach ≤ 6R | 56 | 39.3% | +27.5 | 0.0076 | 16/18 = 88.9% |
| reach ≤ 5R  ← `AGGRESSIVE` | 53 | 41.5% | +30.7 | 0.0019 | 15/18 = 83.3% |
| reach ≤ 5R + chop ≥ 0.05 | 45 | 44.4% | +31.1 | 0.0021 | 10/18 = 55.6% |
| **the best-F1 four-check fit** | 38 | 52.6% | +41.1 | 0.000037 | **10/18 = 55.6%** |
| chop ≥ 0.07, reach ≤ 3R, disp ≥ 2.1 | 17 | 23.5% | −6.6 | 0.77 | 0/18 = 0% |

**Every point past 8R buys lift by throwing away his S days.** The four-check fit that scores
+41.1 points drops 8 of 18: `MSTR_2025-01-27`, `BABA_2025-02-05`, `AVGO_2025-05-02`,
`SPCX_2026-06-25`, `AVGO_2025-10-10`, `MU_2025-06-25`, `MSTR_2026-03-13`, `MARA_2025-07-18`.
Five of the eight die on `chop`. `reach ≤ 8R` is the only point on the frontier that clears
**90% S-day retention**, so it ships; the single card it costs is `SPCX_2026-06-25`.

This is the whole reason chop and displacement are off. They are real signals about what he
refuses and they are also signals about his best days. Filtering on them is not free.

---

## The shipped filter

```python
DEFAULT = {
    "late_window":     "11:00",   # 09:30-11:00, the deck standard's own bound
    "min_er_session":  0.0,       # chop check OFF -- costs S days
    "max_reach_r":     8.0,       # THE filter
    "min_impulse_atr": 0.0,       # displacement check OFF -- costs S days
}
AGGRESSIVE = dict(DEFAULT, max_reach_r=5.0)   # Austin's dial, see below
```

**A whole-session card — the silent half of a mixed deck — passes untouched.** That is also a
measurement, not laziness: on the 100-card S sweep, chop-filtering session cards is **null**
(+3.6 points, 95% CI [−17.6, +22.0], p = 0.8170) and drops **9 of his 34 S days**. Pure cost
on the exact sample the recall gate uses. `FILTER_SESSION_CARDS = True` reproduces the
rejected arm.

### Against his 90 verdicts

| | n | pass | he grades passing | he grades dropped | effect | 95% CI | Fisher p | recall |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| **all 90** | 90 | 63 | **36.5%** (23/63) | 11.1% (3/27) | **+25.4** | [+5.3, +39.7] | **0.0211** | 23/26 = **88.5%** |
| fit (vetoes+runner) | 55 | 36 | 55.6% (20/36) | 15.8% (3/19) | +39.8 | [+12.8, +57.9] | 0.0087 | 20/23 = 87.0% |
| **held-out (rare+index)** | 35 | 27 | 11.1% (3/27) | 0.0% (0/8) | +11.1 | **[−22.1, +28.1]** | **1.0000** | 3/3 = 100% |

As a deck: **he refuses 71.1% of an unfiltered deck and 63.5% of a filtered one**, and still
sees 23 of the 26 cards he would have engaged with.

**The held-out lanes are a NULL result** — p = 1.0, with only 3 positives and only 8 cards
dropped there. Low power, but it is what it is: the lift does not reproduce off the corpus
the thresholds were chosen on. That is the caveat that governs how hard anyone should lean on
this.

### Nested cross-validation

Thresholds refit inside every fold, 5 folds × 20 seeds over all 90 cards:

| | value |
|---|---|
| out-of-fold keep-rate of passing cards | **35.9% ± 2.7** (min 31.8, max 41.5) |
| out-of-fold recall of his graded cards | 60.2% ± 5.6 |
| base rate | 28.9% |

+7.0 points out of sample, ~2.6 sd clear of the base rate. **Caveat: the CV refits over the
whole grid, including the S-day-costly configs the frontier rejects**, so it estimates the
procedure, not the shipped config. Read it as a lower bound on generalisation, not as the
shipped number.

### The three cards he graded that the filter drops

| card | lane | his grade / note |
|---|---|---|
| `QQQ_2026-05-07` | vetoes | C — "Earlier entries" |
| `BABA_2025-07-23` | vetoes | A |
| `GOOGL_2025-04-17` | vetoes | C |

Two of three are C-grades and one says the good trade was elsewhere on the chart. One clean A
is lost: `BABA_2025-07-23`.

### What still slips through

40 of his 64 refusals still pass. 24 of those 40 are the two lanes the filter is not built
for — `rare` (setups he says are not setups at all; that is **T2**'s detector problem) and
`index` (session cards, passed by design). Of the vetoes that slip through, several carry a
note saying the good trade is a candle or two away — `BABA_2026-02-17` "Few candles later good
trade", `MU_2026-01-09` "2 candles earlier s". Those are not bad cards, they are cards with
the wrong minute, which is **T12**'s deliverable. A card-selection filter cannot fix a
timestamp.

---

## Pool survival

Random sample of 400 of the 16,820 archived symbol-days, seed 21. The engine fires on 138 of
them (34.5%) and is silent on 262.

| card kind | survives | 95% CI |
|---|---:|---|
| whole-session (the silent half) | **390 / 390 = 100%** | [99.0%, 100%] — passed by design |
| entry-anchored (the fire half) | **123 / 138 = 89.1%** | [82.8%, 93.3%] |

Every one of the 15 fire-half rejections is `reach`; `window`, `chop` and `displacement` fire
zero times, exactly as the config says they should.

**No deck is starved.** The no-repeat guard leaves 15,326 unjudged archived days; at 89.1% and
100% survival that is ~4,700 eligible fire cards and ~10,000 eligible session cards against
the 30 + 30 a deck needs. A live build confirms it: `pick(4, seed=21, max_probe=30)` filled
its four cards immediately.

For contrast, the rejected four-check fit survived on only **51.4%** of fire days and **70.0%**
of session days — three times the rejection rate, for the S-day cost documented above.

---

## Wired in

`research/build_deck.py::pick()` runs every candidate through the filter before it can enter a
deck; `--no-prefilter` reproduces a pre-T21 deck and prints a warning saying so. Each card's
manifest row carries `prefilter: {er_session, reach_r, impulse_atr, et}` — the reason it was
allowed in front of him.

`research/test_t21_card_filter.py` asserts:

1. His 90 verdicts still read 26 graded / 64 refused, per lane.
2. `window`, `chop` and `displacement` are **off** at the shipped config (0 trips) — pinned so
   nobody "fixes" a branch that was switched off on purpose — **and** that each still fires
   when switched on, so the switch is not a lie.
3. `reach` is the only live check and is reachable (30.0%).
4. The published numbers reproduce: 63 pass, 23 tp, 40 fp, +25.4 points, p = 0.0211.
5. The held-out lift is null, and the report says so.
6. Session cards pass unconditionally, and the rejected chop arm still works when enabled.
7. **The engine fires on 18 of his 34 held-out S days and the shipped config keeps ≥90% of
   those cards** — with the rejected four-check fit pinned at 10/18 so the reason it is not
   shipped stays in the repo.
8. **`build_deck.pick()` actually calls it** — a deck built through `pick()` contains no card
   the filter would drop. The filter is worthless if the deck generator forgets to call it,
   which is exactly the failure mode `omen-no-repeat-guarantee` hit three times.

---

## Caveats

1. **The held-out lift is NULL.** +11.1 points, CI [−22.1, +28.1], p = 1.0 on `rare`+`index`.
   3 positives, 8 dropped cards. The direction is right on every cut; the size is not
   established off the fit corpus.
2. **The main effect is real but modest and near its bar.** +25.4 points with a lower bound of
   +5.3. Do not quote it as if it were the +41.1 the best-fitting version scores — that
   version is rejected for costing S days.
3. **n = 26 positives.** Everything rests on 26 cards he engaged with.
4. **Four of five spec criteria are off, not implemented.** Clean level, break-bar
   displacement and nearest-level RR are at chance across nine definitions. That is a finding
   about those nine definitions, not proof the concepts are empty. Chop and displacement are
   *real* and still switched off, because on this evidence they cost more S days than they buy
   attention.
5. **`window` is dead by construction** — the engine's own 11:00 cutoff enforces it upstream,
   so it can never fire on an engine-proposed card. Fifth instance of this repo's
   unreachable-rule bug class; shipped dead with a test pinning it.
6. **Card selection only — never wire this into detection.** `features()` reads the whole
   09:30–11:00 session for its chop measure. In `backtest_week` or `live_scanner` that is
   look-ahead.
7. **No money number moves.** T21 touches no engine code. `python research/regression_gate.py`
   is unchanged: any_signal 80, s_grade 5, PASS.
8. **`rare` is out of scope by construction.** Those are setups he says are not setups; only
   T2 reaches that.
9. **Not run:** whether filtering changes what he *grades* rather than what he refuses. That
   needs a fresh deck built through the filter and a grading session — his time, not an
   agent's.
