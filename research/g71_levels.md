# G7.1 — track `levels`: every price level the code computes, against Austin's six

> *"i only have 6 day trade levels."*
> *"if some htf corpus was collected, its interfering with the 6 levels and were we are at with RR to determine how to scale."*
> *"you know the 6 levels i watch thats it."* — Austin, 2026-08-29

Diagnosis only. No shipped file was edited; the diffs are in §6.

Scripts committed with this report:
`research/g71_levels_book.py` (the four-arm 2-year rig),
`research/g71_levels_compare.py` (arm comparison),
`research/g71_levels_p21_six.py` (P21 re-run on his roster),
`research/g71_levels_pmh_collision.py` (the PMH name collision, measured).

---

## 1. His six, stated

**PDH · PDL · PMH · PML · ORH · ORL** — prior regular-session high/low, **premarket**
high/low (04:00–09:30 the same morning), and the 5-minute opening range (09:30–09:34).

This is not inferred. It is written down in five independent places, and he ratified the
premarket pair himself:

| source | evidence |
|---|---|
| his ballot | `research/rule_ballot_batch02.jsonl` b5: *"lets count bull/bear PA and below/above at least 5/6 levels i watch a +1"* |
| his mark | `research/marks/probe_master_2026-08-29.jsonl:23` `fact_pm_levels` → `trade`: *"THIS IS ONE OF THE 6 LEVELS WE WATCH, SO YES ITS TRADEABLE SUOULD HAVE ALWAYS BEEN"* |
| code | `research/downgrade.py:89` `CONFLUENCE_LEVELS = ("PDH","PDL","PMH","PML","ORH","ORL")` |
| code | `signal_runner.py:2665` `_active_levels = [pdh, pdl, pmh, pml, or_high, or_low]` |
| code | `research/build_levels.py`, `research/t21_card_filter.py:159`, `research/build_s_cards.py:42`, `research/build_master_homework.py:56`, `research/build_x_veto_deck.py:56`, `research/deck_ui.py:219` — the same six, six times |

Why exactly these six and not more is already argued in
`research/p18_p19_new_variables.md` §"The six levels, and why these six": they are fixed
before (PDH/PDL/PMH/PML) or shortly after (ORH/ORL, locked 09:34) the open.

---

## 2. Every price level the code computes

### 2a. In the shipped trading path

| level family | where | in his six? | live? |
|---|---|---|---|
| ORH / ORL | `signal_runner.py:2648` `OpeningRangeAnalyzer.get_opening_range` | **yes** | on |
| PDH / PDL | `signal_runner.py:1803-4`, fed by `live_scanner.py:182` / `backtest_2y.py:120` | **yes** | on |
| PMH / PML (premarket) | `signal_runner.py:1809-10`, `polygon_feed.premarket_hi_lo` | **yes** | on |
| session HOD / LOD as a B&R level | `signal_runner.py:2679-2690`, gated by `HODLOD_PAIR` | **no** | **off** (`HODLOD_PAIR = False`, `:148`) |
| session HOD / LOD as the **scale rung** (PT1) | `backtest_week.py:851/856` `scale_level` | **no** | **on** — every scaled trade |
| T10 swing pivots (strength 2, lookback 30) | `signal_runner.py:1359 pivot_levels`, wired `:2698-2710` | **no** | **on** (`PIVOT_LEVELS` default `"1"`, `:1162`) |
| **next whole psychological dollar** | `backtest_week.py:853/858` `math.floor(scale_level)+1.0` | **no** | **on** — this is the runner target |
| order-block candle (OCR) | `omen_bot.py:318 get_valid_order_blocks` | n/a — Austin: the OCR candle *"is a level generator"* (`omen-rulebook.md:356`) | on |
| Rule-10 left-side pivots | `signal_runner.py:1734 rule10_left_pivots` | no | off (`RULE_710_ENABLED` default off) |
| QQQ's own PD/PM level break | `live_scanner.py:224 compute_qqq_breaks` | it is *QQQ's* copy of his six, used as a market-wide tag | on |

**HTF is a bias, not a level set.** `htf_bias_for` (`backtest_week.py:713`) and
`daily_trend_bias` are close-vs-SMA20 on hourly/daily closes. Nothing anywhere in the
shipped path derives a *price* from a higher timeframe. So the literal reading of
Austin's worry — an HTF level set injecting targets — is **not** what is happening.
Something else is, and it is worse (§4).

### 2b. Research-only level sets (never reach detection)

`research/levels.py` builds a **nine-family** node set for the target autopsy:
psych $50/$10/$5/$1/$0.50 grid (`:93`), HOD/LOD (`:143`), 3-bar swing pivots (`:218`),
PDH/PDL **plus classic floor pivots PP/R1/S1/R2/S2** (`:168`), and
**prior-calendar-month high/low** (`:196`). Imported only by `mark_features.py`,
`h3_veto.py`, `h5_frontrun.py`, `rule7_rule10.py`, `exit_lab.py`,
`build_mark_batch_02.py`, `omen6_forward.py` — none of which is in the trading path.

`research/build_h2_deck.py:258` offers Austin **VWAP** as a level chip on a homework
deck. VWAP is not one of his six and is computed nowhere in the engine.

---

## 3. (a) Which computed levels are NOT in his six

Three, all live:

1. **T10 swing pivots** — `PIVOT_LEVELS` default ON.
2. **The next whole psychological dollar** — the runner target.
3. **Session HOD/LOD** — as the PT1 scale rung (as a B&R *entry* level it is off).

Measured share of the 2-year book (`research/g71_arm_base.json`, 76,019 signals /
2,437 traded, 2024-08-21…2026-08-21):

| level named in the signal | all signals | traded |
|---|---:|---:|
| pivot high / pivot low | **42,706 (56.2%)** | **691 (28.4%)** |
| his six (ORH/ORL/PDH/PDL/PMH/PML) | 27,531 (36.2%) | 1,244 (51.0%) |
| other (84%-rule re-entry / OCR, no level name) | 5,782 (7.6%) | 502 (20.6%) |

Per-trade money by level family is flat — pivot high **+0.588R** (n=372), pivot low
**+0.558R** (n=319) against OR high +0.589R, PMH +0.635R, PDH +0.626R, PDL +0.468R,
PML +0.391R. **The off-roster entries are not the losing half of the book.**

---

## 4. (b)+(c) Do the extras feed entry, stop, target — and is a corpus set setting RR?

**Entry: yes.** Pivots enter `level_pairs` (`signal_runner.py:2708-2710`) on exactly the
same footing as a named level, and `:3283-3288` ranks a pivot B&R *above* a named one on
the same bar.

**Stop: yes, by construction.** A break-and-retest stop is the broken level, so a pivot
level is a pivot stop. 691 traded rows.

**Target: yes — and this is the finding.**

`backtest_week.py:848-859` picks the runner target — the price the second half of every
scaled trade works toward, i.e. the number that sets realised RR and therefore the
scaling:

```python
cands = [x for x in (pdh, pmh) if x is not None and x > scale_level]
cands.append(math.floor(scale_level) + 1.0)  # next psych whole $
runner_tgt = min(cands)
```

Three things are wrong with that against "I only have 6 levels":

1. **ORH / ORL are not candidates at all.** Two of his six cannot be a target.
2. **The whole-dollar candidate is appended unconditionally and is never more than
   $1.00 beyond the scale point**, so `min()` takes it almost every time.
   Measured on the traded book (`research/g71_runner_probe.json`, 2,540 matched rows):
   **87.6% of traded runner targets are the next whole dollar, not one of his levels.**
3. **The whole dollar's provenance is the video corpus, not Austin.** It traces to
   `research/scarface-rules-accelerator.md:13` and
   `research/fable-spec-2026-07-12.md:25` — *"next draw of liquidity (PDH/PDL, psych
   whole numbers, gap fill)"*, Scarface/jdub. **This is Austin's "some htf corpus was
   collected, its interfering with the 6 levels and were we are at with RR."** He is
   right about the mechanism; the corpus is the video corpus, not an HTF one.
   DIRECTION.md's standing rule — *"the corpus validates rules Austin states, it never
   invents them"* — was broken here.

Size of the RR distortion, traded rows only:

| | shipped (whole-dollar) | his six only |
|---|---:|---:|
| median runner-leg RR | **3.275 R** | **5.758 R** |
| mean | 4.624 R | 8.051 R |
| runner target below 2.0R | **24.1%** | 1.4% |
| rows where none of his six lies beyond the scale point | — | **48.1%** |

Median paired lift from using his six instead: **+1.691 R of headroom**.

**A second, smaller defect — the PMH name collision.** `research/levels.py:196`
`prior_month_nodes` emits nodes typed `"PMH"`/`"PML"` holding the **prior calendar
month's** high/low. Everywhere else in the repo PMH/PML is the **premarket** pair — one
of his six. Measured over 960 archived symbol-days
(`research/g71_levels_pmh_collision.py`): the two prices differ by a **median 6.83%
(PMH) / 7.74% (PML)**, and match exactly on **1 of 960**. `h3_veto.py:20` and
`h5_frontrun.py:47` both describe those nodes in print as if they were the premarket
levels. Research-only, so no booked trade is wrong — but every mark-feature and veto
number computed off a `"PMH"` node from that module is describing a level Austin does not
watch, under the name of one he does.

---

## 5. What restricting to his six actually costs

Four arms, one rig (`backtest_2y.py`), 500 sessions, 2024-08-21…2026-08-21.
`base` reproduces the shipped book byte-for-byte (2,437 traded, identical R vector).

| arm | traded | win% | mean R | total R | months green | paired ΔR vs base (95%) |
|---|---:|---:|---:|---:|---:|---|
| **base** (shipped) | 2,437 | 49.5 | **+0.5495** | +1,339.1 | **25/25** | — |
| **six_target** — runner target from his six, 2R fallback | 2,430 | 48.0 | +0.4630 | +1,125.0 | 23/25 | **−0.0620 ± 0.0387** |
| **no_pivot** — `PIVOT_LEVELS=0` | 1,879 | 48.5 | +0.5476 | +1,028.9 | 24/25 | 0.0000 (0 of 1,669 shared trades moved) |
| **both** | 1,869 | 48.0 | +0.4737 | +885.3 | 24/25 | −0.0656 ± 0.0468 |

Held-out S recall, 100 blind cards (`research/t0_heldout_recall.py`, 34 S):

| arm | recall | precision |
|---|---|---|
| base | **23/34 = 67.6%** | 39.7% |
| `PIVOT_LEVELS=0` | **18/34 = 52.9%** | 47.4% |

(`six_target` cannot move recall — it is an exit-side change only.)

### Read

- **Restricting the runner target to his six loses money, and the loss is real.**
  −0.0620R paired, CI **excludes zero** — rare in this project, where every A/B on record
  moves less than its ±1.5799R error bar. Durability breaks: 25/25 → 23/25 green (the two
  red months are shallow, −0.8R and −3.5R). The mechanism is plain from §4 — his levels
  sit a median 1.7R further away, so the runner reaches them less often.
  **"Shoot higher" is measurably the wrong trade on this exit.** On Austin's own S rows it
  goes the other way (+0.3759R vs +0.3547R, n≈297), so the cost is carried by the non-S
  bulk of the book.
- **Turning pivots off costs a quarter of the book and a third of the recall for nothing.**
  −558 trades (−22.9%), −310R total, mean R unchanged (−0.0019R), and **S recall falls
  14.7 points, 23/34 → 18/34**. Zero shared trades move: pivots only ever *add* signals.
  Precision rises 39.7% → 47.4%, so this is a recall-for-precision trade, and recall is
  the gate DIRECTION.md names.
- **And he already ratified keeping them.** `probe_master_2026-08-29`
  `fact_pivot_levels` → `keep`: *"They can still be a if clean and RR good."* Pivots are
  not an unauthorised level family; they came out of his own marks (*"pivot structure
  break > level break"*, AMZN_2025-07-17_34, quoted at `signal_runner.py:1151`).
  What is **not** implemented is the *"can still be **a**"* half — a pivot-keyed setup can
  currently reach **S**; `compute_austin_tier` (`signal_runner.py:1655`) never reads
  `level_kind`.

### Bonus: P21's negative result was measured on the wrong roster

`research/p21_target_availability.md` tested his ballot b4 (*"if there are no other levels
to target … harder to trade"*) against a **nine**-family roster — his six plus HOD, LOD
and every T10 pivot, a mean of **12.95 levels per signal** against his 6.00
(`research/g71_levels_p21_six.md`). Re-run on his six:

| roster | mean levels/signal | no-target share of losers | of winners | gap |
|---|---:|---:|---:|---:|
| his six | 6.00 | 33.6% | 46.1% | **−12.5 pts** |
| six + HOD/LOD | 8.00 | 17.1% | 34.5% | −17.4 pts |
| nine (what P21 ran) | 12.95 | 17.1% | 34.5% | −17.4 pts |

His rule still runs backwards on his own roster, so the negative result stands — but it is
**28% less extreme**, and the T10 pivots contributed *literally nothing* to it (nine and
six+HOD/LOD are identical: a pivot inside a 30-bar lookback is never beyond 2R).

---

## 6. The diffs

### D1 — runner target: his six, level-first, 2R fallback (his ratified `fact_blind_2r`)

`fact_blind_2r` → `take`: *"Pick a level first if no level then default 2r."*
This is that sentence, implemented on his six. **Measured at −0.0620 ± 0.0387 R and
25/25 → 23/25 green — do not ship it without him seeing that number.**

```diff
--- a/backtest_week.py
+++ b/backtest_week.py
@@ -748,6 +748,11 @@ def simulate_day(symbol: str, day_iso: str, candles: List[Candle],
     trades: List[SimTrade] = []
     open_trades: List[SimTrade] = []
     probe: List[tuple] = []   # P8/G2, only under SCRATCH_PROBE=1
     seen = {}  # dedupe key -> last bar index it appeared
 
+    # Austin's six, assembled once. ORH/ORL are the first five RTH bars --
+    # the same slice research/t21_card_filter._levels and
+    # research/p21_target_availability.levels_for_entry use.
+    orh = max(c.high for c in candles[:5]) if len(candles) >= 5 else None
+    orl = min(c.low for c in candles[:5]) if len(candles) >= 5 else None
+
     for i in range(5, len(candles)):
@@ -845,17 +850,25 @@ def simulate_day(symbol: str, day_iso: str, candles: List[Candle],
             # F1 ladder: scale trigger = session extreme as-of entry bar (no
             # lookahead); runner target = first key level beyond the scale point
             scale_level = runner_tgt = 0.0
             if SCALE_PLAN and risk > 0:
+                # R9 / `fact_blind_2r` -> `take`: "Pick a level first if no
+                # level then default 2r", and the levels are Austin's SIX --
+                # "i only have 6 day trade levels". The "next psych whole $"
+                # candidate this replaces came from the Scarface video corpus
+                # (research/scarface-rules-accelerator.md:13,
+                # research/fable-spec-2026-07-12.md:25), never from him; it
+                # sits at most $1.00 beyond the scale point, so it won min()
+                # on 87.6% of traded rows and set the runner's RR -- and
+                # therefore the scaling -- from a level he does not watch.
+                # ORH/ORL were never candidates at all. Measured in
+                # research/g71_levels.md: -0.0620 +/- 0.0387 R paired.
+                six = (pdh, pdl, pmh, pml, orh, orl)
                 if sig["direction"] == "call":
                     scale_level = max(cd.high for cd in candles[:i + 1])
-                    cands = [x for x in (pdh, pmh) if x is not None and x > scale_level]
-                    cands.append(math.floor(scale_level) + 1.0)  # next psych whole $
-                    runner_tgt = min(cands)
+                    cands = [x for x in six if x is not None and x > scale_level]
+                    runner_tgt = min(cands) if cands else target
                 else:
                     scale_level = min(cd.low for cd in candles[:i + 1])
-                    cands = [x for x in (pdl, pml) if x is not None and x < scale_level]
-                    cands.append(math.ceil(scale_level) - 1.0)
-                    runner_tgt = max(cands)
+                    cands = [x for x in six if x is not None and x < scale_level]
+                    runner_tgt = max(cands) if cands else target
```

A flag-gated form is safer and is what the method rules want — `RUNNER_TARGET_LEVELS`
(`"six"` / `"corpus"`), default `"corpus"` until he rules.

### D2 — the pivot-keyed setup caps at A, not S (his `fact_pivot_levels` → `keep`, *"can still be a"*)

This is the restriction his sentence actually asks for. It keeps the recall the six-only
roster throws away (`no_pivot` costs 5 of 23 S cards) while stopping a level outside his
six from producing his top grade.

```diff
--- a/signal_runner.py
+++ b/signal_runner.py
@@ -1655,6 +1655,14 @@ def compute_austin_tier(sig: dict, candles, fired_ideas, htf_bias) -> str:
     if not setup_is_s_eligible(sig):
         return "C"
     if _targets_session_extreme(sig):
         return "C"
+    # `fact_pivot_levels` -> `keep`: "They can still be a if clean and RR
+    # good." A T10 swing pivot is NOT one of the six levels he watches ("i only
+    # have 6 day trade levels"), so a pivot-keyed setup tops out at A. Deleting
+    # the family instead costs 5 of 23 held-out S cards and 558 trades for no
+    # change in mean R (research/g71_levels.md §5).
+    if PIVOT_TIER_CAP_A and sig.get("level_kind") == "pivot":
+        return "A"
```

with, beside `PIVOT_LEVELS` at `signal_runner.py:1162`:

```diff
+# A pivot is not one of Austin's six. `fact_pivot_levels` -> `keep`, "They can
+# still be a if clean and RR good" -- so cap a pivot-keyed setup at A. OFF by
+# default until measured against held-out recall (method rule 6, measure then
+# wire).
+PIVOT_TIER_CAP_A = os.getenv("PIVOT_TIER_CAP_A", "0").strip().lower() in ("1", "true", "yes", "on")
```

### D3 — kill the PMH/PML name collision (pure defect, no book effect)

```diff
--- a/research/levels.py
+++ b/research/levels.py
@@ -196,7 +196,13 @@
 def prior_month_nodes(symbol: str, day: str):
-    """PMH/PML across the prior calendar month archived for the symbol."""
+    """Prior-calendar-month high/low, typed PRMH/PRML.
+
+    NOT "PMH/PML": everywhere else in this repo -- signal_runner.py:1809,
+    backtest_week.py:734, research/downgrade.py:89, research/build_levels.py,
+    research/t21_card_filter.py:159 -- PMH/PML is the PREMARKET high/low, one
+    of Austin's six. The two prices differ by a median 6.83% / 7.74% over 960
+    archived symbol-days and coincide once (research/g71_levels_pmh_collision.py).
+    """
@@ -210,8 +216,8 @@
-    return [{"price": round(hi, 4), "type": "PMH", "weight": 2.5},
-            {"price": round(lo, 4), "type": "PML", "weight": 2.5}]
+    return [{"price": round(hi, 4), "type": "PRMH", "weight": 2.5},
+            {"price": round(lo, 4), "type": "PRML", "weight": 2.5}]
@@ -258,8 +264,8 @@ SOURCE_FAMILY = {
-    "PMH": {"PMH"},
-    "PML": {"PML"},
+    "PRMH": {"PRMH"},
+    "PRML": {"PRML"},
```

`research/h3_veto.py:20/377` and `research/h5_frontrun.py:47/477` state in prose that
these are the premarket levels and must be corrected in the same commit.

### D4 — take VWAP off the homework deck

`research/build_h2_deck.py:258` offers `("VWAP", "VWAP")` as a level chip. VWAP is not
one of his six and the engine does not compute it; a deck answer of "VWAP" cannot be
routed anywhere. Drop the chip or replace it with `("pivot", "Pivot")`.

---

## 7. Answer to the question he asked

He has six levels; the engine watches those six **plus** swing pivots, session HOD/LOD
and whole-dollar round numbers. The one that touches RR is the whole dollar: it is the
runner target on **87.6%** of traded rows, it came out of the mined Scarface video corpus
rather than out of him, and it truncates the runner's headroom from a median **5.76R** to
**3.28R**. So yes — a corpus level set is setting the number the scaling is computed
against. But when the runner target is restricted to his six the book gets **worse**
(−0.0620 ± 0.0387 R, 25/25 → 23/25 green), because his levels sit further away and the
runner reaches them less often. **The corpus level was doing work, it just was not his.**
The open question is whether he wants the honest number or his rule.
