# G7.1 adversarial verify — track `samplesize` bar-coverage claim

**Verdict: NOT REFUTED.** Every headline number reproduces independently. Four corrections
attach; none overturns the claim.

Scripts: `research/g71_vsamplesize_priorday.py` -> `research/g71_vsamplesize_priorday.json`.
Re-runs of the prior agent's own scripts went to scratch, not over its artifacts.

## What reproduced

| number | claimed | my re-run |
|---|---|---|
| distinct judged symbol-days | 1,147 | **1,147** — `build_deck.marked_card_ids()` returns 1147 exactly. CLAUDE.md's "1,057" is the stale figure. |
| with archived bars | 1,110 (96.8%) | **1,114 (97.1%)** as of now |
| S days / with bars | 287 / 278 | **287 / 281** as of now |
| replayed days | 1,096 | **1,096** |
| replay errors | 0 | **0** |
| elapsed | 121.7 s (0.111 s/day) | **137.3 s (0.125 s/day)** |
| by-grade recall S/A/C/none | 59.7 / 49.8 / 68.4 / 51.3 | identical to 0.1 pt |

The 100-card calibration (23/34 = 67.6%) also reproduces against the shipped scorer:
`python research/t0_heldout_recall.py` returns `fired_on_S: 23, recall_pct: 67.6` today.
**DIRECTION.md's 52.9% (18/34) is stale**, not the samplesize number.

## Correction 1 — the coverage figures are a moving target

`data_archive/` mutates under the audit. 1,110 -> 1,114 and 278 -> 281 S is exactly the
4 CSV pulls the report discloses in §5; `symbol_never_archived: DIA 8 days` collapsed to 0
because one DIA file landed. Anything citing 96.8% / 278 must carry an as-of stamp, and
the power table's "278 (available)" row is already 281.

## Correction 2 — "zero errors" is liveness, not validity

`levels._prior_day` (`research/levels.py:159-165`) returns the previous **archived** csv
with no calendar-adjacency check, and `htf_bias` (`research/t4_engine_recall.py:112-124`)
walks the previous 40 archived files. On a sparse cache the engine is handed prior-day
levels from an arbitrarily distant session and raises nothing.

Measured (`g71_vsamplesize_priorday.json`): **19 of 996** non-sweep days (1.9%) replay with
a non-adjacent prior day — 5 of them S (MARA 2024-12-17 uses 2024-10-18, a **60-day** gap;
MARA 2024-10-18 uses a 39-day gap; CRM 2025-06-02 a 31-day gap; SOFI 2024-10-30 and
UBER 2025-02-07 have no prior day at all). 41 days get `htf_bias = None`.
**The sweep-100 has zero such days (100/100 clean).** The corpus and the sweep are
therefore not perfectly interchangeable arms — small, but it is one-directional noise that
lives only in the new 996.

Bar completeness itself is fine: 1,095 of 1,096 days carry >=20 bars inside 09:30-11:00.
The one exception is `SPCX_2024-01-30` (3 bars in-window) and it is an A, not an S.

## Correction 3 — "287 S days" is a max-precedence merge, not 287 clean S labels

`top_austin` in both samplesize scripts takes S if **any** of the 19 corpora says S.

- **94 of 287 (32.8%)** also carry a non-S Austin grade from another corpus. 43 of those
  are the direct contradiction S-in-one / `none`-in-another.
- **46 of 287 (16.0%)** rest *solely* on `derived_marks_v1/v2` + `recovered_reviews.jsonl`
  — corpora CLAUDE.md labels "derived, low confidence" and "prose reviews mined back out of
  chat". `recovered_reviews.jsonl` also leaks 14 engine-ladder `B` tokens, i.e. it
  demonstrably mixes ladders.

This does not move the coverage arithmetic, but it does move the power table: label noise
on ~1 in 3 of the S denominator attenuates the very effect size the 278-card McNemar design
is being bought to detect. **Recommend the paired A/B run twice — once on all 287, once on
the 193 S days with no contradicting grade — and report both.**

## Correction 4 — the checks that did NOT land

- **Look-ahead: clean.** `premarket_extremes` reads only 04:00-09:29 same day
  (`t4_engine_recall.py:84-93`); `prior_day_levels` reads strictly the prior file;
  `htf_bias` slices `names[max(0,i-40):i]`, excluding day *i*; `run_day` walks
  `candles[:i+1]` with an 11:00 cutoff (`t4_engine_recall.py:187-191`). No future bar
  reaches the runner.
- **Branch reachable.** `range(5, len(candles))` needs >=6 in-window bars; 1,095/1,096 have
  20+.
- **Wrong-book check is inapplicable.** Nothing in this claim touches the trade book.
  `run_day` imports only `backtest_week.dedupe_window`; it books no trade, calls no fill,
  and the 1,017-vs-2,595 question cannot arise. **Scope limit worth stating instead:** the
  counted fires are engine-ladder `B`/`C` (40 B, 24 C over the first 60 S days) — the alert
  path. `live_scanner._tier():546` promotes to TRADE only on `A+`. "1,096 days are
  replayable" means replayable through the **alert** path, not through the live gate.
