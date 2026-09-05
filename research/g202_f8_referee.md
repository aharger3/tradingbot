# g202 — independent leakage referee for F8 (`research/g157_ml_ceiling.py`)
**One sentence: F8 has no lookahead — every feature survives having the entire future of the day overwritten with garbage — but its label column and its feature list are both not what the report says they are, and the "AUC at chance" headline survives every correction I could make to them, because at 120 rows and 28 positives the null band alone is 0.501 ± 0.161.**

Reproduction: `python research/g157_ml_ceiling.py` rewrote `research/g157_ml_ceiling.md` **byte-identically** (no git diff). AUC 0.492 / 0.426, 120 rows, 28 S, engine recall 17.9%.

## 1. Leakage — clean
Two attacks on every one of the 120 rows, plus a replay check and a source check.

| attack | rows | failures |
|---|---:|---:|
| truncate bars to `[:i+1]`, re-score | 120 | **0** |
| overwrite every bar after `i` with x1000 garbage, re-score | 120 | **0** |
| re-run the full engine replay, compare first candidate's bar/stop/grade | 15 | **0** |

- `research/downgrade.py`: every loop is bounded at `i` or `min(..., i+1)`. `find_ocr` reads `bars[j+1]` but starts at `j = i-1`, so `j+1 <= i`. `large_counter_body` clamps `hi = min(i, ...)`. Verified by the corruption attack, not by reading.
- `research/t66_downgrade_measure.replay()` feeds the runner `candles[:i+1]` and nothing else; `pdh/pdl/pmh/pml` are prior-session, `htf_bias` is prior-session.
- `t4_engine_recall.htf_bias()` slices `names[max(0, i - 40):i]` — the day being graded is **excluded** (source check: True). This is the field O1 was refuted on tonight (`spy_trend` reading today's close); F8 does **not** have that bug.

**Verdict on the leakage question the row asked: no leak. F8's numbers are honestly out-of-sample.**

## 2. CV grouping — sound, but it is 4 folds, not 5, and they are lopsided

- `GroupKFold(n_splits=min(5, n_groups))` with **4 month groups** ⇒ **4 folds**, one month each. Both section headings in `g157_ml_ceiling.md` say "5-fold GroupKFold CV by month"; it ran **4**. Cosmetic, but it is the kind of mislabel that hides a real fold problem.
- month appears on both sides of a fold: **0** folds
- calendar date appears on both sides of a fold: **0** folds
- a (symbol, date) card appears on both sides of a fold: **0** folds

| fold | test month | test rows | test S | train rows |
|---:|---|---:|---:|---:|
| 0 | 2026-07 | 66 | 15 | 54 |
| 1 | 2026-06 | 25 | 7 | 95 |
| 2 | 2026-08 | 18 | 4 | 102 |
| 3 | 2026-05 | 11 | 2 | 109 |

Grouping by month is *coarser* than grouping by date, so the QQQ/SPY pairs that share a calendar day — 30 QQQ and 30 SPY cards against 60 TSLA — can never straddle a fold. That is the one grouping risk this design had and it is closed.

**But the folds are not usable as a variance estimate.** One fold is 66 of 120 rows and trains on only 54. The pooled OOF AUC is the only readable number here, and it needs the null band in section 4.

## 3. Labels — three defects, none of them fatal to the headline

- 120 cards, 28 S. That count is right **for the two deck files `load_day_cards()` reads** (`research/marks/deck_marks_tsla_2026-08-20.jsonl` 9 S + `research/marks/deck_marks_index_2026-08-19.jsonl` 19 S = 28).
- It does **not** come from `research/marks_pool.py`, the repo's canonical cross-corpus grade. Against the pool, **5 of 120 cards disagree** and the S count would be **30, not 28**:

| card | F8 label | marks_pool canonical | opinions |
|---|---|---|---:|
| `QQQ_2026-07-02` | `none` | `A` | 2 |
| `QQQ_2026-07-21` | `none` | `C` | 2 |
| `QQQ_2026-07-31` | `none` | `S` | 2 |
| `SPY_2026-08-03` | `(blank)` | `none` | 1 |
| `TSLA_2026-07-09` | `A` | `S` | 3 |

**Defect 1 — a blank grade is scored as a hard negative.** 1 card (`SPY_2026-08-03`) carries `grade: ""`. `SPY_2026-08-03` also carries a `type:"trade"` row with `source:"taken"` and `r_multiple: 1.75` — he took a trade that day and left the day grade empty. F8 counts it as *not S*. An ungraded card is not a negative; it should be dropped.

**Defect 2 — two days he graded S elsewhere are labelled 0.** `TSLA_2026-07-09` is `A` on the deck card and `S` in `austin_marks_v7.jsonl` + `recovered_reviews.jsonl` (3 opinions). `QQQ_2026-07-31` is `none — "missed it"` on the deck card, and in `probe_master_homework_2026-08-26.jsonl` he graded that day's candidate `your_grade: ["S"]` with the note *"large wicks like that are scary but I like the weakness in the day"*. **"Missed it" is not "not an S setup"** — and an S classifier's target is whether the setup was there, not whether he was at the desk.

**Defect 3 — the feature list is not the one the spec ordered.** The row required level type, setup, tier, displacement, HTF bias, time of first candidate.

| feature | in the report | actually seen by the model |
|---|---|---|
| level type (`stop_level_name`) | claimed | **constant `"unknown"` on 120/120 rows** — `replay()`'s output dict has no `stop_level_name` key at all, so `first.get(...)` is always `None` |
| displacement | claimed | **dropped** — `make_xy()` never lists it; and as built it was the exact complement of `no_displacement`, so it carried zero new information anyway |
| `stale_retest`, `break_then_rejection` | 2 of the 8 downgrade variables | **constant 0 on 120/120 rows** |
| column count | 25 | 18 non-constant |

So the honest description of F8 is: *18 live columns, not 25, and two of the six spec-named features were missing or dead.* That is a real reason to distrust "these features do not contain the answer" **as written** — the sentence should be "the eight downgrade booleans, setup, tier, HTF bias and entry minute do not contain the answer."

## 4. One stronger feature set — AUC does not move

I added 34 columns the F8 agent did not try, all computed at the entry bar and all put through the same corruption attack: level distance in ATR, signed and absolute; ATR as a fraction of price; entry-bar range/body/wick geometry; bars since break, bars since retest, break→retest gap, bars since OCR; a continuous displacement ratio in place of the boolean; move from the open in ATR; distance to the session high and low; the level's position inside the session range; volume z-score and ratio; same-colour run length; the level's distance to the $1 / $5 / $10 round numbers; and the entry-bar-computable g154 predicates (`or-break-without-retest`, `standalone-ocr-no-br`, `ocr-strict-definition`, `hammer-wick-level-candle`, `entry-time-of-day-early`, `index-etf`, `cheap-stock-refusal`, `forming-candle-entry-not-extreme`, `exhausted-overextended` as a continuous ratio, `chase`, `large_counter_body`, `level-not-respected-refusal`).

| feature set | model | ROC AUC (out-of-fold) | precision at engine recall (17.9%) |
|---|---|---:|---:|
| F8's own (25 cols) | logistic regression | **0.492** | 32.0% |
| F8's own (25 cols) | gradient boosting | **0.426** | 24.7% |
| F8's own (25 cols) | random forest | **0.516** | 41.7% |
| g202 stronger (59 cols) | logistic regression | **0.446** | 24.1% |
| g202 stronger (59 cols) | gradient boosting | **0.504** | 45.5% |
| g202 stronger (59 cols) | random forest | **0.529** | 29.7% |
| — | predict-everything baseline | 0.500 | 23.3% |

### The number that makes all of the above moot
400 label permutations *within month groups*, same models, same folds — what AUC looks like when there is provably nothing to learn:

| feature set | null-AUC mean | null-AUC sd | 95% null band |
|---|---:|---:|---|
| F8's own | 0.501 | 0.082 | 0.347 – 0.656 |
| g202 stronger | 0.501 | 0.081 | 0.335 – 0.660 |

**At 120 rows and 28 positives, an AUC anywhere inside that band is indistinguishable from noise.** F8's 0.492 and 0.426 sit inside it; so does every arm in the table above. The honest statement is not "these features contain no signal" — it is **"this sample cannot detect a signal of any size that would matter, in these features or in thirty more."** Those are different claims and only the second one is supported.

### Labels corrected to `marks_pool` (rich features)

| model | AUC, F8 labels (28 S) | AUC, pool labels (30 S) |
|---|---:|---:|
| logistic regression | 0.446 | 0.503 |
| gradient boosting | 0.504 | 0.515 |
| random forest | 0.529 | 0.538 |

Fixing the labels does not rescue it either.

## 5. Verdict

- **Leakage: none.** 120 rows, two independent attacks each, zero failures. The row's primary question comes back clean.
- **CV grouping: sound.** No month, date or card straddles a fold. The "5-fold" label is wrong — it ran 4 — and one fold holds 66 of 120 rows, so per-fold numbers are meaningless; the pooled OOF AUC is fine.
- **Labels: three defects.** 1 blank grade scored as a negative, 2 cards graded S in another corpus scored as negatives, and the set never touches `marks_pool`.
- **Features: two of the six the spec named were absent or dead** — `stop_level_name` is constant, `displacement` never reaches the model.
- **Stronger features: AUC does not move.** Best arm across six model/feature combinations is 0.529, inside the null band.

**Refuted: yes — the report's method claims, not its direction.** "AUC at chance" is correct and, if anything, understated. What is not correct is *the reason given for it*: the strongest single result of the night was published as "these features do not contain the answer" when the honest reading is "120 rows and 28 positives cannot tell a real effect from noise, and two of the features named were never actually there." **Do not use g157 to close the door on a learned classifier.** It is not evidence that one is impossible; it is evidence that the judged corpus is too small to test one. The thing that would change this is more marks, which is exactly what the completeness critic already said.
