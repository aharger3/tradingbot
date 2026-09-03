# G7.1 / `samplesize` — "70% of the time it feels like we're starting from zero"

**Austin's words:** *"understanding my system from 25 card samples is not enough, it hasnt
been enough because 70 percent of the time it feels like we are starting from zero."*

**Scripts (run these, they reproduce every number below):**

| script | what it makes |
|---|---|
| `research/g71_samplesize_power.py` | the power maths → `research/g71_samplesize_power.json` |
| `research/g71_samplesize_corpus_audit.py` | the corpus census → `research/g71_samplesize_corpus.json` |
| `research/g71_samplesize_full_recall.py` | recall over the WHOLE corpus → `research/g71_samplesize_full_recall.json` |

No mark file was written. No engine file was edited. Four `data_archive/` CSVs were pulled
while timing the Polygon fetch (SOFI 2025-06-18, CRM 2025-05-02, DIA 2026-05-07,
UBER 2025-03-12) — cache growth only.

---

## The headline

**He is half right, and the half he is right about is the expensive half.**

34 S cards is *eight times more* than you need to say "we are not at 90% recall"
(p = 7.5 × 10⁻⁸). It is **nowhere near enough to say whether a change helped**: at n_S = 34
a genuine 10-point recall improvement is detected **12.9%** of the time. That is the
"starting from zero" feeling, and it is not a feeling — it is the power curve.

**And the corpus that fixes it already exists and already has bars.** 1,110 of 1,147 judged
symbol-days are replayable today; **278 of the 287 S days** are. I replayed all 1,096
Austin-graded days with bars through the shipped harness in **122 seconds, zero errors**.
Nothing is blocking it but hardcoded file paths.

---

## 1. The power maths (`g71_samplesize_power.py`)

α = 0.05 two-sided throughout. `n_S` = number of **S cards** in the denominator;
"graded cards" converts at the S base rate (34/100 = 0.340 on the blind sweep,
287/1133 = 0.253 across the whole corpus).

### Q1 — distinguish 52.9% recall from the 90% gate

| requirement | n_S | graded cards @0.253 |
|---|---:|---:|
| point estimate alone rejects 0.90 | **6** | 24 |
| 80% power | **11** | 44 |
| 90% power | 15 | 60 |
| 95% power | **17** | 68 |

At the n we actually have (n_S = 34, 18 hits): Wilson 95% CI **36.7–68.6%**,
p vs 0.90 = **7.5e-08**, power **99.9%**.

**Verdict: the gate reading is not sample-starved.** "We are not at 90%" is one of the most
solid numbers in the project. 25 cards would have been enough for *this* question.

### Q2 — detect a 10-point recall change (52.9% → 62.9%), two independent samples

| power | n_S **per arm** | graded cards per arm @0.253 | both arms |
|---|---:|---:|---:|
| 80% | **382** | 1,509 | 3,018 |
| 90% | 511 | 2,018 | 4,036 |

Per-arm n_S at 80% power by effect size: 5pt → **1,551** · 10pt → **382** · 15pt → 166 ·
20pt → 91 · 25pt → 56 · 37pt (52.9→90) → 23.

### Q3 — detect a 10-point change **paired** (McNemar: same cards, two engine configs)

This is the design the repo actually runs and it is far cheaper, because the two arms
disagree on only a handful of cards.

| discordant-pair rate ψ | n_S | graded cards @0.253 |
|---|---:|---:|
| 0.12 | **92** | 364 |
| 0.15 | 116 | 458 |
| 0.20 | 155 | 612 |
| 0.30 | **234** | 924 |
| 0.40 | 312 | 1,232 |
| 0.50 | 391 | 1,544 |

**234 S cards buys 80% power on a 10-point move at realistic discordance. 278 exist.**

### Q4 — the power curve

| n_S | Wilson 95% CI on 52.9% | ± pts | power vs the 90% gate | power, 10pt unpaired | power, 10pt paired ψ=.30 |
|---:|---|---:|---:|---:|---:|
| 17 | 31.0–73.8 | 21.4 | 0.958 | **0.084** | 0.110 |
| **25** | 33.5–70.0 | 18.2 | 0.984 | **0.106** | 0.143 |
| **34** (today) | 36.7–68.5 | **15.9** | 0.999 | **0.129** | **0.181** |
| 50 | 38.5–65.2 | 13.3 | 1.000 | 0.171 | 0.248 |
| 100 | 43.3–62.5 | 9.6 | 1.000 | 0.298 | 0.446 |
| 150 | 44.7–60.5 | 7.9 | 1.000 | 0.418 | 0.611 |
| 200 | 46.1–59.8 | 6.9 | 1.000 | 0.526 | 0.737 |
| **278** (available) | 47.0–58.7 | **5.8** | 1.000 | 0.666 | **0.865** |
| 400 | 48.1–57.8 | 4.9 | 1.000 | 0.818 | 0.957 |

Read the "10pt paired" column top to bottom. **At 25 cards, 86% of real 10-point wins are
invisible. At 34, 82%. At 278, 13%.** Austin's "70% of the time" is, if anything, generous.

This is the same wall as the standing method finding *"every A/B moves less than its own
±1.5799R error bar"* — same disease, different metric.

---

## 2. The corpus census (`g71_samplesize_corpus_audit.py`)

Walked with `build_deck.mark_sources()` / `build_deck._judgement_key()` — called, not
reimplemented — across all 19 corpora.

| | count |
|---|---:|
| distinct judged symbol-days | **1,147** |
| …carrying an Austin-ladder grade | 1,133 |
| …with archived bars | **1,110 (96.8%)** |
| **without** archived bars | **37 (3.2%)** |
| **S days** | **287** |
| **S days with bars** | **278 (96.9%)** |
| A / C / none days | 236 / 57 / 553 |
| S base rate among graded days | **0.253** |

`CLAUDE.md`'s figure of **1,057 is stale by 90 days** — `probe_master_2026-08-29.jsonl`
and the 2026-08-28 files landed after it was written.

**Ladder note:** `X` in `austin_tier` / `tier` / `verdict` inside a *human* mark file is
Austin's old fourth button — "I would not take this", the label that became `none`. It is
**not** the engine's `X`. Merging it into the engine ladder mis-sorts 300 rows and drops
"Austin-graded days" from 1,133 to 941; the audit script names this at
`g71_samplesize_corpus_audit.py:31-40`. (17 stray `B` rows — 3 in `austin_marks_v7`, 14 in
`recovered_reviews` — are genuine legacy-ladder leakage and are excluded.)

---

## 3. Why measurement runs on 25/34/100 instead of 1,147 — the reason, with lines

**It is not bar coverage, and it is not a considered held-out discipline. It is ~15 rigs
that each hardcode one file path, and nothing that aggregates.**

| file:line | constant | n | n_S |
|---|---|---:|---:|
| `research/t0_heldout_recall.py:38` | `SWEEP = marks/probe_s_sweep_2026-08-28.jsonl` | 100 | **34** |
| `research/t4_engine_recall.py:37` | `MARKS = austin_marks_v2.jsonl` | 159 rows / 151 days | 77 rows |
| `research/t70_test1_score.py:46` | `MARKS = marks/probe_omen_test1_2026-08-27.jsonl` | 100 | 15 |
| `research/t3_selection_ranker.py:60` | same test1 file | 100 | 15 |
| `research/t2_ocr_detector.py:51` | `marks/probe_master_2026-08-29.jsonl` | 90 | — |
| `research/t61_onwatch_ab.py:5` | "his 120 graded day-cards" | 120 | 28 |
| `research/t21_card_filter.py:442`, `t14_arrival_ladder.py:72`, `t16_consolidation_sweep.py:21`, `t23_stack.py:65`, `g71_router_recall.py:51`, `t12_earlier_entry_gap.py:826`, `t1_entry_minute_autopsy.py:38`, `t9_spread_tight_rr.py:47`, `t6_losers_quick.py:94`, `g71_capture_heldout_ab.py:32` | all → the **same** 100-card sweep | 100 | 34 |
| `research/mark_features.py:45`, `miss_autopsy.py:81`, `rule7_rule10.py:57`, `t6_count_arming.py:44`, `regression_gate.py` (via `t4.MARKS`) | all → `austin_marks_v2.jsonl` | 159 | 77 |

Three specific facts fall out of that table:

1. **`build_deck.marked_card_ids()` already reads all 19 corpora** — but only to *exclude*
   days from new decks (`build_deck.py:169-186`). **No measurement rig calls it.** The
   union of Austin's judgements is computed on every deck build and thrown away.

2. **The `verify:` gate runs on a two-generations-stale file.** `regression_gate.py:4`
   locks against `t4_engine_recall.MARKS` = `austin_marks_v2.jsonl`, **159 rows / 151
   distinct days**. `austin_marks_v7.jsonl` is the terminal file with **479 rows, every one
   carrying `entry_i`** — 3.0x the marks, same schema except the tier field is named
   `austin_tier` instead of `tier`. The recall regression gate is watching a third of the
   marks it could watch.

3. **Held-out discipline is real but explains only the sweep.** The rationale is written
   down once, at `research/t21_card_filter.py:444-450`: *"This corpus was NOT used to build
   or fit the filter … It is the governing held-out sample under method rule 2."* That
   justifies keeping the 100-card sweep clean. It does **not** justify discarding the other
   ~1,000 days, because:
   - **No train/test manifest exists anywhere in the repo.** Nothing records which days any
     flag was fitted on, so every pre-2026-08-27 mark is treated as contaminated *by
     default* rather than by evidence.
   - The comparison that matters is **paired** — the same days replayed under two engine
     configs. In-sample contamination shifts both arms identically; the *delta* survives it.
     Using 278 S days for the A/B and reserving the 34 for the absolute gate reading costs
     nothing and is strictly more information.

---

## 4. What running the whole corpus actually gives (`g71_samplesize_full_recall.py`)

Scored exactly as `t0_heldout_recall.py::score_sweep` scores its 100 — replay with
`t4_engine_recall.run_day` (shipped harness, untouched), card is a hit if the engine takes
**any** entry that day.

**1,096 days replayed · 121.7 s · 0.111 s/day · 0 errors.**

| Austin grade | n | fired | **recall** | detected (any signal) |
|---|---:|---:|---:|---:|
| **S** | **278** | 166 | **59.7%** | 97.1% |
| A | 227 | 113 | 49.8% | 97.8% |
| C | 57 | 39 | 68.4% | 93.0% |
| none | 534 | 274 | 51.3% | 97.6% |

**Calibration** — the same process, restricted to the 100-card blind sweep: 23/34 =
**67.6%** recall, 39.7% precision. That reproduces the current published held-out number
(`g71_router_recall.py:24`, the `hand_rolled` arm), so the corpus-wide figure is on the
same footing.

### The finding that only exists at the larger n

Does the engine fire more often on his S days than on the days he refused?

| sample | S recall | `none` fire rate | gap | z | **p** |
|---|---:|---:|---:|---:|---:|
| 34-card sweep | 67.6% (23/34) | 53.0% (35/66) | 14.6 pt | 1.40 | **0.161 — invisible** |
| whole corpus | 59.7% (166/278) | 51.3% (274/534) | 8.4 pt | 2.28 | **0.023 — real** |

The 34-card sample cannot tell you whether the engine discriminates his S days from his
refusals **at all**. The 278-day sample can, and the answer is "barely, but yes" — which
is the same conclusion `x6_recall_n.md` reached from the detection side (a 2.3-point
separation on S *detections*), now confirmed on *fires* at 8x the sample.

Detection ≥ 97% on **every** grade confirms T1's "the engine is never silent" at 8x its
original n, and re-anchors the wound where T1 put it: not detection, grading.

---

## 5. The bar-pull, quantified

Bar coverage is **not** the blocker — but here is the exact residue.

**33 symbol-days of bars still need pulling** (37 at audit time; 4 were pulled while timing
the fetch). Split:

| bucket | pairs | S | A | none |
|---|---:|---:|---:|---:|
| fetchable (day ≥ 2024-08-29) | **29** | 4 | 9 | 16 |
| **outside Polygon's ~2-year window** — HTTP **403 Forbidden**, verified twice | 4 | **2** | 0 | 2 |

The 2 permanently-unmeasurable S days are **MARA 2024-08-02** and **SOFI 2024-08-05**. The
403 is an entitlement/lookback wall, not a rate limit — retested after a 65-second pause on
`SOFI 2024-08-05` and `BABA 2024-08-01`, both 403 while 2025/2026 dates returned 400-800
bars in 0.23 s. Recovering them needs a Polygon plan change, not a script.

**Time to pull the 29:** a fetch is 0.23 s, but the key rate-limits at ~5 calls/minute — the
5th consecutive call returned **429**, and `polygon_feed.py` has **no backoff, no retry, no
sleep** (grep for `sleep|429|retry|backoff` returns nothing). So: **≈ 6–7 minutes**
wall-clock at a 12-second gap, or seconds on a paid tier. Payoff: S days go **278 → 282 of
287** and the CI half-width moves 5.79 → 5.75 points.

**Do not block on this.** It is 1.4% of the S denominator for 7 minutes of clock and a
plan upgrade.

By symbol: SOFI 8, DIA 8 (DIA is not in `universe.py` — it appears only in old marks;
8 days incl. 3 S), GOOG 6, CRM 5, TSM 4, MARA 2, UBER 2, BABA 1, IREN 1.
Also degraded-but-runnable: 9 days with bars have no prior archived trading day (PDH/PDL
come back `None`) and 38 have fewer than 20 prior days (`htf_bias` returns `None`).
`run_day` degrades rather than fails on both; they are inside the 1,096 above.

---

## 6. What to change

**No engine diff is needed.** The two rigs in this report are the change: they read the
whole corpus through the existing loaders and run in two minutes.

**Do this:**

1. **Run every recall A/B paired, on all 278 S days, and report McNemar** — not two
   independent recall percentages. That takes the power on a 10-point move from **0.18 to
   0.87** for two extra minutes of compute per arm.
2. **Keep the 34-card sweep as the absolute gate read only.** It is well-powered for
   "are we at 90%" and hopeless for "did that help". Say which question each number answers.
3. **Stop reporting a bare recall percentage without its CI.** `18/34` and `23/34` differ by
   14.7 points and their 95% intervals overlap over most of their length.

**Flagged, not done** (it re-locks a baseline, which `CLAUDE.md` forbids doing silently):
`regression_gate.py` / `t4_engine_recall.py:37` should point at `austin_marks_v7.jsonl`
(479 rows) instead of `austin_marks_v2.jsonl` (159). The only schema change is the tier
field name:

```diff
--- a/research/t4_engine_recall.py
+++ b/research/t4_engine_recall.py
@@
-MARKS = os.path.join(HERE, "austin_marks_v2.jsonl")
+# v7 is the terminal mark file -- v2..v6 are fully contained in it (CLAUDE.md).
+# 479 rows / every one carrying entry_i, against v2's 159. The tier field is
+# named austin_tier there, so normalise on load.
+MARKS = os.path.join(HERE, "austin_marks_v7.jsonl")
```

and wherever marks are loaded, `m["tier"]` becomes `m.get("tier") or m["austin_tier"]`.
**This will move the gate's locked key set and `research/baseline_3.8.json` must be
re-locked deliberately, with Austin told which marks entered the baseline.** Do not do it
as a side effect of another ticket.
