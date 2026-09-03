# G7.1 / `smeasure` — how S accuracy is measured, where the pools disagree, and the test that replaces them

**Scripts (both runnable, both read-only):**
`research/g71_smeasure_pools.py` → `research/g71_smeasure_pools.json`
`research/g71_smeasure_test.py` → `research/g71_smeasure_test.json`

Austin, 2026-08-29: *"until we have the best test to determine s trade acuracy, and pooling
those together, then we can determine if the whole system is meeting my eye"* ·
*"s is not pooling as the same"* · *"understanding my system from 25 card samples is not enough."*

---

## The headline

**On the two-year book the engine trades 22.7% of the 255 S days Austin has graded, and
28.9% of the 775 days he looked at and refused. It trades his refusals slightly more often
than his S days.** The gap is −6.2 points, z = −1.91, p = 0.056 — indistinguishable from
zero. The S label carries no measurable information about what the book trades.

The number the repo publishes today (67.6% held-out S recall, `DIRECTION.md:19`
says 52.9% pre-T23) is measured on a replay harness, on 34 cards, through a router that
is not the shipped one. On the same 34 cards the traded book scores **1/34 = 2.9%**.

---

## 1. How S recall and S precision are measured TODAY

| what | answer | file:line |
|---|---|---|
| script | `research/t0_heldout_recall.py` | `:86` `score_sweep()` |
| sample | 34 S cards inside the 100-card `research/marks/probe_s_sweep_2026-08-28.jsonl` | `:38`, `:87-89` |
| S is read from | `r["answers"]["s"] == ["s"]` — **not** the `grade` field | `:88` |
| hit definition | the engine takes **any** entry that day; no minute, no direction, no side match | `:92-97` |
| replay | `research/t4_engine_recall.run_day` | `:36`, `t4_engine_recall.py:164` |
| router | `t4_engine_recall.CaptureRunner._route` — hand-rolled, **never calls `super()`** | `t4_engine_recall.py:141-160` |
| grade ladder | **neither**. The card asks a yes/no "is this an S", so nothing on Austin's S/A/C/none ladder or the engine's A+/A/B/C/X ladder is consulted at scoring time | `:87-89` |
| precision | same 100 cards: `TP / (TP + fired-on-his-66-refused)` | `:104-105` |
| second sample | `probe_master_2026-08-29.jsonl` lane `vetoes`, 40 cards, `answers.grade` | `:111-139` |
| minute tolerance | ±2 bars — applied **only** in the veto lane, never in the sweep | `:45`, `:121` |

Three defects, all measured:

1. **n = 34.** The 95% Wilson interval on 23/34 is **±15.0 points**. The `sr_` lane Austin
   is referring to when he says "25 card samples" (`probe_master_homework_2026-08-26.jsonl`,
   25 cards, 5 S) is **±15.1 points** on 5/25. Neither can see a 90% gate.
2. **Wrong router.** `CaptureRunner._route` re-implements accept/reject instead of
   delegating, so every gate `SignalRunner._route` (`signal_runner.py:2491`) grew after it
   was written is inert in the one rig that scores the governing metric. Identical bug was
   fixed in `backtest_week.BacktestRunner._route` (`backtest_week.py:619`) in omen-5.0.
   Found by T23, `research/t23_stack.md:214-222`. The `router` track of this run is fixing it.
3. **It sees 34 of 288 S days.** Documented in §2.

---

## 2. "s is not pooling as the same" — this is literally true

`research/g71_smeasure_pools.py` enumerates every corpus through
`build_deck.py::marked_card_ids` / `_judgement_key` (`research/build_deck.py:86,162,169`) —
called, never re-implemented — and adds the one thing that enumerator does not have: an
**S extractor**. Five different fields mean "S":

| field | corpora |
|---|---|
| `austin_tier` | `austin_marks_v7`, `derived_marks_v2`, `recovered_reviews` |
| `tier` | `blind_marks_all`, `marks_clean`, `mark_batch_03/04`, `derived_marks_v1` |
| `austin_grade` | `mark_batch_02_grades` |
| `verdict` (lowercase `"s"`) | `austin_verdicts.json` |
| `grade` | the deck files and most probe files |
| `answers.grade` / `answers.your_grade` | probe pages in ladder form |
| **`answers.s` / `answers.s_call`** | **`probe_s_sweep_2026-08-28`, `probe_master_2026-08-29` lane `index`, `probe_master_homework_2026-08-26` lane `sr_`** |

`build_deck._GRADE_KEYS` (`:78`) covers the first five and **not the last two**.

### The trap

`research/marks/probe_s_sweep_2026-08-28.jsonl` carries `"grade": "none"` on **all 100
rows, including the 34 he called S**. Any tool that reads a grade field sees **zero** S days
in the sample the whole project steers by. Same for `probe_master_2026-08-29` (123 rows, all
`grade: "none"`) and the `sr_` lane (`grade: null`).

**48 distinct S symbol-days are invisible to any grade-field reader.**

### Three published S-day counts, all of them from this repo, none of them equal

| number | source | what it counts |
|---:|---|---|
| **154** | `research/marks/LEDGER.md` §"S-grade day count — the number the 90%-recall gate needs" | `austin_marks_v7` + the two canon decks only |
| **207** | `research/x6_recall_n.md` (`x6_recall_n.py::norm_tier`) | scalar grade fields only, at its run date |
| **240** | x6's method re-run today | scalar grade fields only, corpus has since grown |
| **288** | `g71_smeasure_pools.py` today | **all five field families, all 19 corpora** |

### Distinct S symbol-days per corpus

| corpus | distinct S days |
|---|---:|
| `austin_marks_v7.jsonl` | 127 |
| `austin_verdicts.json` | 74 |
| `recovered_reviews.jsonl` | 57 |
| `blind_marks_all.jsonl` | 50 |
| `marks_clean.jsonl` | 50 |
| `mark_batch_02_grades.jsonl` | 35 |
| `marks/probe_s_sweep_2026-08-28.jsonl` | **34** ← the whole published metric |
| `marks/deck_marks_index_2026-08-19.jsonl` | 19 |
| `marks/probe_autopsy_2026-08-23.jsonl` | 15 |
| `marks/probe_omen_test1_2026-08-27.jsonl` | 15 |
| `marks/probe_master_homework_2026-08-26.jsonl` | 14 |
| `mark_batch_03_regrades.jsonl` | 12 |
| `marks/deck_marks_tsla_2026-08-20.jsonl` | 9 |
| `derived_marks_v2.jsonl` | 9 |
| `marks/probe_master_2026-08-29.jsonl` | 8 |
| `marks/deck_marks_h2_3lane_2026-08-28.jsonl` | 5 |
| `derived_marks_v1.jsonl` | 5 |
| `mark_batch_04_grades.jsonl` | 4 |
| **distinct union** | **288** |

### The disagreement he can feel

Of **1,147** judged symbol-days, **357 appear in more than one corpus**. Scoring each corpus
at day level (a corpus that called any bar of the day S votes S — the grain the recall metric
actually uses):

- **35 symbol-days carry an S in one corpus and a NOT-S in another** — 9.8% of the days
  graded twice, and **30 of them sit inside the 255-day test pool**.
- 3 more are contested only *inside* one corpus (bar-level granularity, not a real conflict).
- 3 rows contradict themselves field-to-field within a single row.

Three fault lines, and they need three different fixes:

| cluster | n | what it is | fix |
|---|---:|---|---|
| `austin_verdicts.json` vs `austin_marks_v7.jsonl` | **20** (18 one way, 2 the other) | `LEDGER.md`: verdicts → v2 → v3 ("+batch02, 25 new and **7 overwrites**") → v4 ("overwrite-only" 29-regrade merge). Every overwrite leaves the source file still saying S and the terminal file saying otherwise, **and the pooler still reads both** | precedence: v7 supersedes verdicts, per `LEDGER.md`'s own "only v7's 479 rows should count" |
| a regrade batch dissenting from v7 + verdicts | **11** | `mark_batch_03_regrades` / `mark_batch_04_grades` are *deliberate regrade passes* — he changed his mind | precedence: latest grading session wins. This is not an error, it is temporal supersession that nothing encodes |
| day-card vs day-card, and grain mismatch | **4** | `recovered_reviews`'s coarse `(symbol, day, setup, direction)` grain colliding with day cards (`IREN_2026-05-21`, `PLTR_2025-12-10`, `QQQ_2026-07-24`, `TSLA_2026-07-09`) | needs a rule, possibly needs him |

Plus one that belongs to neither and is the sharpest of all: **`QQQ_2026-07-31` is S in
`probe_master_homework_2026-08-26` and not-S in `deck_marks_index_2026-08-19`** — two of his
own day-card sessions, seven days apart, on the same chart, with opposite answers. That one is
a genuine Austin-vs-Austin split and it is the only one in the 35 that cannot be resolved by a
precedence rule.

Full list: `research/g71_smeasure_pools.json` → `across_corpus_conflicts`.

**34 of the 35 need a precedence rule, not a re-grade. Resolving them costs zero of his time.**

---

## 3. THE definitive S-accuracy test — `research/g71_smeasure_test.py`

### Design

**Population.** Every symbol-day at least one corpus calls S, pooled through
`build_deck._judgement_key` + the S extractor = **288**. Eligibility funnel, so a miss caused
by "the book never trades that symbol" is never read as a grading miss:

| step | S days |
|---|---:|
| pooled | 288 |
| symbol is in the book's 28-symbol universe | 277 |
| date inside the book window 2024-08-21 → 2026-08-21 | 266 |
| **both — the test pool** | **255** |
| his refused days, same two filters — the negative sample | **775** |

**What counts as a hit.** Four nested definitions, scored on the same 255 days, reported
side by side. Nesting is the point: it localises the loss.

| arm | definition |
|---|---|
| `saw` | the book emitted any signal on that symbol-day |
| `routed` | at least one signal cleared `_route` (`status == "fired"`) |
| `traded` | at least one survived into the book (`traded == true`) — **the answer to his question** |
| `harness` | `t4_engine_recall.run_day` takes an entry — today's published definition, kept only for reconciliation |

**Confidence interval.** 95% **Wilson** score interval on every arm (Wald runs past 1.0 at
n=34, p≈0.9). Arms are compared with the **exact one-sided McNemar** on discordant pairs —
never with mean R. This obeys the standing finding: every A/B this project ran moved less
than its own ±1.5799R bar (`DIRECTION.md:48`).

**The discrimination test — the part that answers "is the whole system meeting my eye".**
Recall alone can be bought by firing on everything. So each arm's rate on his 255 S days is
tested against its rate on his 775 refused days with an unpaired two-proportion z. An arm
whose S rate equals its refused rate has learned nothing about his eye at any recall level.

**Held-out discipline.** Declared per corpus, not assumed (`g71_smeasure_test.py::PROVENANCE`).
`fit` = its labels chose a threshold · `selection` = arms were ranked by their score on it ·
`in_sample` = predates the engine being scored · `clean` = never fit, never selected on.

### Today's number

```
S RECALL on the 255 eligible pooled S symbol-days
  arm                                     hits    n     rate     95% CI
  saw     (engine emitted any signal)      246   255    96.5%   [93.4, 98.1]  ±2.4 pts
  routed  (cleared _route)                  71   255    27.8%   [22.7, 33.6]  ±5.5 pts
  traded  (survived into the book)          58   255    22.7%   [18.0, 28.3]  ±5.1 pts
  harness (t4_engine_recall.run_day)       153   255    60.0%   [53.9, 65.8]  ±6.0 pts

DISCRIMINATION -- his 255 S days vs his 775 refused days, same arm
  arm         S rate   refused      diff       z        p
  saw          96.5%     95.5%    +1.0 pts   +0.68   0.4991
  routed       27.8%     33.4%    -5.6 pts   -1.66   0.0979
  traded       22.7%     28.9%    -6.2 pts   -1.91   0.0557
  harness      60.0%     51.0%    +9.0 pts   +2.51   0.0122

PRECISION
  false fire on his 775 refused days (traded): 224 = 28.9%  [25.8, 32.2]
  precision of the traded book against his ladder: 20.6%  [16.3, 25.7]

RECONCILIATION -- the 34-card sample t0_heldout_recall.py publishes
  1/34 = 2.9%  [0.5, 14.9]  ±7.2 pts     (reproduces t23_stack.md §4b's "1 of 34")

POOLING-RULE SENSITIVITY (traded arm)
  rule_any_corpus_says_S       58/255 = 22.7%  [18.0, 28.3]
  rule_latest_session_wins     57/241 = 23.7%  [18.7, 29.4]
  S days that move between the rules: 14
  discrimination under precedence: -4.9 pts  z=-1.48  p=0.1382

PROVENANCE of the eligible S pool
  in_sample 196 · selection 54 · fit 13 · clean 0
  contested (S in one corpus, not-S in another): 30

HARNESS vs BOOK  harness-only 101  book-only 6  exact one-sided McNemar p < 1e-16
```

**Read it as one sentence: the detector finds 96.5% of his S days, `_route` throws 68.7
points of that away, and what survives is statistically indistinguishable from what survives
on the days he refused.** The wound is not detection and not exits — it is the gate, exactly
where T23 and `research/g4_dropped_s.md` §6 put it.

The only arm that separates his eye at all is the **harness** (+9.0 pts, p = 0.012) — and
that is the arm running the router that isn't shipped. The shipped path (`traded`) separates
by −6.2 pts.

### Pooling-rule sensitivity — the 35 conflicts do **not** change the verdict

"Any corpus says S" is one defensible pooling rule; "the latest grading session wins" is the
other (what `LEDGER.md` already asserts for `austin_verdicts` → v7, and what a regrade batch
means by definition). Both were run:

| pooling rule | traded recall | 95% CI | discrimination vs his refused days |
|---|---:|---|---|
| any corpus says S | 58/255 = **22.7%** | [18.0, 28.3] | −6.2 pts, z = −1.91, p = 0.056 |
| latest session wins | 57/241 = **23.7%** | [18.7, 29.4] | −4.9 pts, z = −1.48, p = 0.138 |

14 S days move between the rules; the answer does not. **Resolve the conflicts for hygiene,
not because they are hiding the number.**

### Sample size — the direct answer to "25 card samples is not enough"

The gate is a **claim** ("fires on ≥90% of his S days"), so it needs a 95% lower bound above
0.90, not a point estimate above it.

| question | n |
|---|---:|
| half-width of today's 23/34 | **±15.0 pts** |
| half-width of the 25-card `sr_` lane at 5/25 | **±15.1 pts** |
| n for ±10 pts at p = 0.90 | 34 |
| n for **±5 pts** at p = 0.90 | **141** |
| n for ±3 pts at p = 0.90 | 384 |
| n to **demonstrate** the 90% gate if true recall is 95% | **127** |
| n to demonstrate it if true recall is 93% | 362 |
| n to demonstrate it if true recall is 92% | 830 |
| n to demonstrate it with a **perfect** engine (100%) | 35 |

**He is right, with a number: 25 cards buys ±15 points. 141 buys ±5. He already has 288 —
he does not need to grade anything to get there, he needs the 288 pooled and the 35 conflicts
resolved.**

### Held-out discipline — and the finding nobody wanted

Of the 255 eligible S days: **196 in-sample · 54 selection · 13 fit · 0 clean.**

**There is no clean hold-out S set in this repo.** `probe_s_sweep_2026-08-28` has been the
selection criterion for T10, T23 and T24 arms; `probe_master_2026-08-29`'s 40 veto labels
**fit** X_LIFT (`research/t10_x_lift_fitted.py:1-30` — "fitted to Austin's 40 veto
verdicts", 13 positive labels). The 67.6% figure is a *training* number wearing the word
"held-out". Any future gate claim needs a set that is sequestered before the arm is chosen.

### Reproducibility caveat, measured not guessed

The harness arm returned **152** at 14:52 and **153** on every run after. It is deterministic
in-process and across `PYTHONHASHSEED` 0–3. The cause is the substrate: `data_archive/` gained
4 CSVs in the preceding 40 minutes (`CRM/2025-05-02`, `DIA/2026-05-07`, `SOFI/2025-06-18`,
`UBER/2025-03-12`) from a concurrent agent. **The metric moves when the archive moves.** The
book arms do not have this problem — `research/bt2y_trades.json` is a frozen artefact
(`generated 2026-08-29T03:14:29`) and is the reason to prefer them.

---

## 4. Proposed fixes — diffs only, nothing applied

### (a) One canonical S reader, beside the one canonical enumerator

Every consumer currently rolls its own, which is why three different S-day counts are
published in this repo. `build_deck.py` already owns `_judgement_key`; give it the grade too.

```diff
--- a/research/build_deck.py
+++ b/research/build_deck.py
@@ -78,6 +78,29 @@
 _GRADE_KEYS = ("austin_tier", "tier", "austin_grade", "grade", "verdict")
 
+# The corpora do not agree on which FIELD carries Austin's grade. _GRADE_KEYS
+# covers the scalar fields; the probe pages answer in `answers`, and
+# probe_s_sweep_2026-08-28.jsonl -- the 100 blind cards the whole project's
+# recall number is scored on -- carries `grade: "none"` on all 100 rows
+# INCLUDING the 34 he called S. Any reader that looks at `grade` alone sees
+# zero S days in the governing sample. 48 distinct S symbol-days are invisible
+# to a grade-field reader (research/g71_smeasure.md section 2).
+_ANSWER_GRADE_KEYS = ("grade", "your_grade", "s", "s_call")
+
+
+def austin_s_grade(row: dict):
+    """-> True (Austin called this an S), False (he judged it, not an S), or
+    None (the row carries no opinion about S). The ONE S reader; do not
+    re-implement it per script."""
+    vals = []
+    for k in _GRADE_KEYS:
+        v = str(row.get(k, "")).strip().lower()
+        if v and v not in ("none", "null"):
+            vals.append(v == "s")
+    ans = row.get("answers")
+    if isinstance(ans, dict):
+        for k in _ANSWER_GRADE_KEYS:
+            a = ans.get(k)
+            if a:
+                first = str(a[0] if isinstance(a, list) else a).strip().lower()
+                if first:
+                    vals.append(first == "s")
+    if not vals:
+        if (str(row.get("grade", "")).strip().lower() in ("none", "null")
+                or row.get("_no_trade")):
+            return False
+        return None
+    return any(vals)
+
```

### (b) Stop publishing a bare 34-card harness number

```diff
--- a/research/t0_heldout_recall.py
+++ b/research/t0_heldout_recall.py
@@ -99,6 +99,14 @@
     return {
         "set": "probe_s_sweep_2026-08-28 (100 blind cards)",
+        # A point estimate on n=34 is not a gate reading: the 95% Wilson
+        # half-width here is +/-15.0 points, and the gate is 90%. Publish the
+        # interval beside the ratio, and never publish this arm without the
+        # traded-book arm from research/g71_smeasure_test.py beside it -- the
+        # same 34 cards score 1/34 in the book (research/t23_stack.md 4b).
+        "recall_ci95_pct": [round(x * 100, 1) for x in
+                            __import__("research.g71_smeasure_test",
+                                       fromlist=["wilson"])
+                            .wilson(len(tp), len(his_s))[1:]],
         "n_cards": len(cards), "n_S": len(his_s), "n_no": len(his_no),
```

### (c) `DIRECTION.md` recall row is a statement about `CaptureRunner`, not about the book

Not applied — it is a published-number change and belongs to whoever lands the router fix.
The honest row is: **22.7% [18.0, 28.3] on 255 pooled S days (traded book)**, with
60.0% [53.9, 65.8] on the harness noted as the rig figure.

---

## 5. What to do next, in order

1. **Land the router fix** (`router` track) — until then every recall number in this repo
   describes a class that does not ship.
2. **Resolve the 35 contested symbol-days** from `g71_smeasure_pools.json`. Zero of Austin's
   time: they are merge overwrites (`austin_verdicts` → v7) and grain mismatches
   (`recovered_reviews`). Precedence rule needed, not a re-grade.
3. **Re-align `recovered_reviews`'s 47 unmatched S days** — `LEDGER.md` already flags this as
   "the highest-value S-recall job in the repo that nobody has taken", and it is +47 on n
   for free.
4. **Sequester a clean hold-out** before the next arm is chosen. 141 S days gives ±5 pts;
   the pool has 255 eligible, so a 141/114 split is affordable today.
5. **Then** ask whether the system meets his eye. It currently does not: `traded` separates
   his S days from his refusals by −6.2 points.
