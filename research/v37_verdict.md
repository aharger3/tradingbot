# v37_verdict — omen-3.7 T8

Read-only synthesis of `bar_coverage_v2.md`, `miss_autopsy.md`, `corpus_miss_autopsy.md`,
`rule7_rule10.md`, `universe.md`, `detect_wide.md`, `recall_ab.md`, `mark_batch_02.md`.
**No number here was recomputed and no backtest was run.** Every figure is quoted from those
files; the only new arithmetic is the sample-size estimate in Q5, which is flagged where it
appears and is derived from `rule7_rule10.md`'s own stated MDE formula.

---

## 1. Why is the engine blind?

Denominator: **77 S marks, all of which have bars** (T1's backfill left 0 of 151 marked
symbol-days without an archive file, so 159/159 marks are classifiable — `bar_coverage_v2.md`).

Top three reasons in the S column of `miss_autopsy.md`:

| rank | reason | S marks | % of 77 S |
|---|---|---:|---:|
| 1 | `no_break_retest` | **27** | 35.1% |
| 2= | `vetoed_htf` | **10** | 13.0% |
| 2= | `fired_wrong_bar` | **10** | 13.0% |

(`detected` is also 10; it is not a miss and is excluded from the ranking. Restricting to the
67 S marks that are genuine misses, `no_break_retest` is 27/67 = 40.3%.)

**No reason carries a majority.** `no_break_retest` is the plurality by roughly 3:1 over the
next reason, but it accounts for about a third of S marks and two-fifths of S misses — fixing it
alone cannot make the engine see most of what Austin sees. Second and third are a tie, and they
are different in kind: `vetoed_htf` is a veto on a signal the engine *did* build, while
`fired_wrong_bar` is a signal that fired on the wrong bar. Only `no_break_retest`,
`no_reference_level` (7) and `consolidation_early_return` (4) are true blindness — 38 of 77.

**Does the corpus agree?** On the top reason, yes, and it is worth stating: over
**10,263 classified Discord-alert instances on 3,595 covered symbol-days**,
`no_break_retest` is also first at **4,186 = 40.8%** (`corpus_miss_autopsy.md`), against 35.1%
in the S column. Same classifier, same fixed vocabulary, two independent datasets, same top
reason at two orders of magnitude difference in n. That is real corroboration and is the single
strongest empirical claim this version produced.

**But the tails disagree, and that disagreement is itself a finding.** Below rank 1 the two
distributions are not the same shape:

| reason | corpus % (n=10,263) | S-mark % (n=77) |
|---|---:|---:|
| `fired_wrong_bar` | 29.4% | 13.0% |
| `no_reference_level` | 23.9% | 9.1% |
| `vetoed_htf` | 0.0% (1 instance) | 13.0% |
| `vetoed_stop_too_tight` | 0.0% (0) | 9.1% |
| `detected` | 0.0% (0) | 13.0% |

The corpus fails almost entirely at **detection** (no_break_retest + fired_wrong_bar +
no_reference_level = 94.1%) and essentially never reaches a veto. Austin's S marks fail at
detection too, but 22% of them (`vetoed_htf` 10 + `vetoed_stop_too_tight` 7 + `vetoed_candle_colour` 2)
are setups the engine *built and then threw away*, a failure mode the Discord alerts barely
exhibit. Read plainly: **Austin's setups get further into the engine than the Discord alerts do,
and then die to the veto stack.** The corpus corroborates the headline and cannot be used to
prioritise anything below it — the veto problem is visible only in Austin's own marks, where
n=77.

---

## 2. Did the widening work?

**Mechanism check passes.** `recall_ab.md` flips `signal_runner.DETECT_WIDE` at runtime and the
arms differ by **2.85× raw signals (738 → 2,101)** and **3.79× fired entries (116 → 440)**. The
flag took effect, so the rest of T6 is admissible.

**Recall (denominator 77 S marks, ±2-bar join):**

| metric | OFF | ON |
|---|---|---|
| **fired S recall** | **10/77 = 13.0%** | **14/77 = 18.2%** |
| any-signal S, deduped | 27/77 = 35.1% | **27/77 = 35.1% (flat)** |
| any-signal S, raw (no dedupe) | 29/77 = 37.7% | 46/77 = 59.7% |
| fired A / X | 6/60, 6/22 | 7/60, 5/22 |
| any-sig deduped A / X | 22/60, 11/22 | **15/60, 6/22 (both fall)** |

**Cost in precision (denominator = engine entries on the 151 marked symbol-days):**
25/65 = **38.5% OFF** → 30/155 = **19.4% ON**. Entries on marked days that Austin did *not*
mark go 40 → 125. Precision halves and unmarked entries triple.

**Cost in signals per symbol per day (denominator 151 pairs):** fired entries/pair
**0.43 → 1.03**; deduped all-grade signals/pair 1.52 → 2.56; raw signals/pair
**4.89 → 13.91**. Pairs with ≥1 entry go 50/151 → 85/151. QQQ alone goes 9 → 23 fired entries.
The widening is not surgical.

**Against the registered prediction.** `detect_wide.md` pre-registered, before any measurement:
fired S recall ON of **13/77 = 16.9%**, honest interval **12–15/77 (15.6%–19.5%)**, with
"below 12/77 means the veto stack is the real ceiling". Observed: **14/77 = 18.2%**.
**The headline prediction held** — inside the band, above the point estimate. The secondary
prediction (all-tier fired 22/159 → ~27/159 = 17.0%) also lands: 14+7+5 = **26/159 = 16.4%**.

**But it held for the wrong reason, and that matters more than the hit.** The prediction's
stated mechanism was "9 newly reachable marks × 34% survival ≈ 3 new fires" — i.e. new
*detections* converting. T6 shows **deduped any-signal S recall unchanged at 27/77: zero new S
marks detected.** The +4 fires came from firing more often on bars the engine already saw, and
deduped A and X detection actually *fell* (22→15, 11→6). The pre-registered precision warning
(smoke test: 38 → 77 entries, "roughly doubles trade count") under-called it — the real cost was
65 → 155 entries with precision halved.

**Verdict on the flag: not a win. Do not arm `DETECT_WIDE`.** Per CLAUDE.md's bar, fired S
recall at 18.2% is nowhere near 40%; the only figure that clears 40% is the raw no-dedupe upper
bound (46/77 = 59.7%), which is precision-free and is ~14 signals/pair/day — not a tradeable
detection.

---

## 3. Do rule 7 or rule 10 do anything?

`rule7_rule10.md`, 159 usable marks, arms S=77 / A=60 / X=22 before feature nulls. Cohen's d is
S minus the other tier; CI is a 10,000-iteration block bootstrap over whole trading days; MDE_d
is the smallest |d| detectable at that n (α=0.05, power=0.80).

**Rule 7 — `bars_break_to_retest` (speed of the retest):**

| contrast | n(S) | n(other) | d | 95% CI | MDE_d | verdict |
|---|---:|---:|---:|---|---:|---|
| S-vs-X | 34 | 11 | −0.343 | [−1.325, 0.564] | 0.972 | underpowered |
| S-vs-A | 34 | 38 | −0.109 | [−0.562, 0.385] | 0.661 | underpowered |

**Rule 10 — `left_pivot_count`:**

| contrast | n(S) | n(other) | d | 95% CI | MDE_d | verdict |
|---|---:|---:|---:|---|---:|---|
| S-vs-X | 46 | 14 | +0.121 | [−0.468, 0.676] | 0.855 | underpowered |
| S-vs-A | 46 | 43 | −0.121 | [−0.563, 0.299] | 0.594 | underpowered |

**Rule 10 — `left_pivot_at_level`:**

| contrast | n(S) | n(other) | d | 95% CI | MDE_d | verdict |
|---|---:|---:|---:|---|---:|---|
| S-vs-X | 46 | 14 | −0.204 | [−0.901, 0.367] | 0.855 | underpowered |
| S-vs-A | 46 | 43 | −0.329 | [−0.724, 0.094] | 0.594 | underpowered |

**"No effect" vs "could not have seen one" — this is the second.** Every CI contains zero, so
nothing is detected. But the largest observed |d| across all six contrasts is **0.343**, and the
*smallest* MDE_d across all six is **0.594**. The best-powered contrast in the set could only
have reliably seen an effect ~1.7× larger than the largest effect actually observed. A real,
moderate, tradeable separation (d ≈ 0.3–0.5) would be invisible to this experiment by
construction. 3.6's MDE was 45pp on arms of n=48/45/12; this version's arms (34–46 non-null) are
not materially larger, because the backfill's gain was eaten by feature nulls. **Neither rule is
refuted and neither is supported. They are untested.**

Two things worth carrying forward:

- **The null rates are themselves the finding.** Rule 7 is undefined for **76/159 = 47.8%** of
  marks (56 with no identifiable break candle, 20 more with a break but no retest touch). Rule
  10 is null for **56/159 = 35.2%**. On nearly half of Austin's own marks, "how fast was the
  retest" has no start point — the level he retested was never provably broken by a closing
  body. That is the same geometry failing as `no_break_retest` in Q1, showing up in a second,
  independent measurement.
- **The one near-signal points the wrong way.** `left_pivot_at_level` S-vs-A has d = −0.329 with
  CI [−0.724, **0.094**] — the closest any contrast comes to excluding zero — and the sign says
  S marks have *fewer* pivots at the level than A marks (1.57 vs 2.33). If rule 10 means "more
  confluence at the level is better", this is the opposite. It is not significant and must not be
  acted on, but it is the single most specific thing more labels could resolve.

---

## 4. What is the sample situation?

**Marks with bars after T1's backfill: 159 / 159** (`bar_coverage_v2.md`), across 151/151
distinct symbol-days. Zero still-missing pairs, zero dropped for `entry_i` out of range. Of the
49 symbol-days missing in 3.6, the omen-corpus-1.0 backfill (PR #8) resolved 17 and T1 fetched
the remaining 32, all HTTP 200 with non-empty bars. IWM and GOOG are now in `archive_1m.py`'s
`SYMBOLS` and `live_scanner.DEFAULT_SYMBOLS`, so daily runs bank them going forward.

Tier arms: **S=77, A=60, X=22.**

**This is why 3.6's numbers are not comparable to 3.7's.** In 3.6, 54 marks had no archive and
counted as misses, so testable S was 48. Fired S going 4/77 → 10/77 and any-sig S 19/77 → 27/77
is **the backfill making previously-untestable marks count, not the engine improving**. On the
48 S marks testable in both versions the engine behaves identically. Anyone quoting 4→10 as
progress is quoting an artefact.

**What `mark_batch_02.md` adds if Austin grades it: 60 new labels**, as a self-contained
`research/mark_batch_02.html`, split:

- **40 S-miss bars** — every S mark whose `miss_reason` is not `detected`, most recent first.
  Reason mix: no_break_retest 18, vetoed_htf 8, fired_wrong_bar 6, no_reference_level 4,
  vetoed_stop_too_tight 2, consolidation_early_return 1, vetoed_candle_colour 1. Grading these
  doubles as an audit of the T2 autopsy.
- **20 unmarked engine entries** — engine fires on days Austin marked something, at bars he did
  not mark. These are the **first real negative labels the project would have**. Today precision
  (38.5% / 19.4%) is computed against "Austin didn't mark it", which conflates a false positive
  with an unlabelled bar; an X on these converts that guess into a measurement.

Grades are collected blind (no tier, no engine grade printed) and returned as 60 rows of
`day symbol time-of-day → S|A|X` in card order.

**Honest scale of the gain: 159 → 219 marks, about +38%.** MDE scales as 1/√n, so the
best-powered contrast's MDE_d ≈ 0.594 would improve to roughly 0.50 — still well above the
0.33 effect it needs to see. Batch 02 is necessary and not sufficient.

---

## 5. The one change to make next

**No new gate, filter, or score is admissible.** Fired S recall in `recall_ab.md` is **13.0% OFF
and 18.2% ON**, far below the 40% bar. Even the ceiling is short: deduped any-signal S recall is
**35.1% in both arms**, so *even if every S bar the engine detects also fired*, recall would be
35% — under 40%. The engine is not seeing 65% of Austin's S bars, and a filter has nothing to
filter. Anything shaped like "add a gate to improve precision" is off the table this version.

**The one concrete change: fix the recall harness's dedupe attribution, then re-read T6.**
`research/t6_recall_ab.py` / `t4_engine_recall.py` dedupe to one signal per setup idea per
30-bar window *before* the ±2-bar join to the mark. That convention produces a 19-mark
contradiction inside a single file: deduped any-sig S is **27/77 flat** across arms (the basis of
"zero new S detections — do not arm"), while raw any-sig S rises **29/77 → 46/77**. T6 itself
diagnoses the cause — a wider retest tolerance lets a setup fill the 30-bar window *earlier*, so
the early instance wins the window and the genuine bar is deduped away; that is also why deduped
A and X *fall* (22→15, 11→6) when the engine unambiguously produces strictly more signals. A
detection metric that goes down when signals go up is measuring the dedupe, not the engine.
The fix is one file and no new data: join to the mark first, dedupe within the ±2-bar window
second. It decides whether `DETECT_WIDE` found 0 new S bars or 17, which is the difference
between "the retest-as-zone idea is dead" and "it works and the harness hid it". Do this before
anything else, because T5's probe predicted 9 newly reachable marks and T6's headline says 0 —
one of the two is wrong and it is cheap to find out which.

Note this changes no trading decision either way: ON precision is 19.4% with 125 unmarked
entries, so `DETECT_WIDE` stays off regardless of how the detection count resolves.

**Beyond that, nothing about the engine's rules is testable without more labels.** Naming exactly
what is needed:

1. **The 60 graded cards of `mark_batch_02.html`** — the 20 unmarked engine entries are the
   blocking item, because without confirmed negatives every precision number in this version is
   an assumption, not a measurement.
2. **For rule 7 / rule 10 to be answerable at all: roughly 145 non-null marks per arm.** Derived
   from `rule7_rule10.md`'s own MDE formula (MDE_d = 2.80 × √(2/n) for equal arms) set to the
   largest observed effect, |d| = 0.33. Current non-null arms are S=46 / A=43 — about **3× more
   labelled marks**, and after the 35% rule-10 null rate that means on the order of **200+ graded
   S setups**, not 77. Batch 02 gets partway; two or three more batches at this cadence is the
   real requirement. Any claim about rule 7 or rule 10 before then is unsupportable in either
   direction.
3. **Nothing from `universe.md` is actionable yet.** The Polygon plan returns
   **403 NOT_AUTHORIZED** on the options snapshot endpoint, so the 200k-daily-contracts threshold
   Austin actually trades by **was not applied**; the top-10 list (MU, SPY, QQQ, NVDA, TSLA, AMD,
   INTC, MSFT, AAPL, AMZN) is ranked by underlying dollar volume, which over-weights MU and
   under-weights cheap options-heavy names. Correctly, `SYMBOLS` was left unchanged. Do not cut
   the universe on this proxy; the required data is an options-entitled Polygon plan.

---

## FOR AUSTIN
1. The engine fires on 10 of your 77 S bars (13%). It still is not seeing your trades.
2. Biggest blind spot is break-and-retest geometry, 27 of 77 S marks; no reason is a majority (HTF veto 10, wrong-bar 10).
3. The 10,379-alert Discord corpus agrees on that top reason (40.8%, n=3,595 symbol-days); the veto losses are yours alone.
4. Leave the retest-as-zone widening OFF: recall 13%→18%, but precision halves (38.5%→19.4%) and 125 unmarked entries appear.
5. Rules 7 and 10 got no answer, not "no effect" — every arm is too small to have seen one. Do not change your process on them.
6. The 4→10 recall "gain" over 3.6 is backfilled data, not a better engine; all 159 marks now have bars (was 105).
7. Next, ours: fix the recall harness's dedupe-before-join, which may be hiding 17 detections. One file, no new data.
8. Next, yours: grade `research/mark_batch_02.html` — 60 blind charts, ~30 min; the 20 false-positive cards matter most.
9. No new filter until recall clears 40% (we are at 18%, ceiling 35%), and the top-10 universe is a proxy — do not trade off it.
