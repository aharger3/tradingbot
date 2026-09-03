# ADVERSARIAL VERIFY — "the whole-dollar target came from the video corpus, not Austin"

**VERDICT: REFUTED.** The whole-dollar target is Austin-authored in three separate
judgement corpora, including one written on 2026-08-29 — the same session as the
"6 levels i watch thats it" quote the claim leans on.

## 1. Austin states it himself, three times, verbatim

| file:line | his words | provenance |
|---|---|---|
| `research/recovered_reviews.jsonl:21` (CRM 2026-05-04, `austin_tier: "C"`) | *"we can target longer timeframe levels **but also whole psychological numbers like 188, 189, etc.**"* | his prose review |
| `research/recovered_reviews.jsonl:39` (MU 2026-03-31, `austin_tier: "S"`) | *"break and two displacement candles and below levels and **target whole psych numbers**"* | his prose review |
| `research/marks/probe_master_2026-08-29.jsonl:112` (AVGO 2026-07-08, `answers.exit: ["level"]`) | *"**Whole psych number**, scale out at top of candles"* | his exit note, 2026-08-29 |

The third row is dated the same day as `omen-rulebook.md:1091` *"you know the 6 levels i
watch thats it."* He did not stop authorising the whole-dollar exit; he wrote it that day.

DIRECTION.md:54 — *"the corpus **validates rules Austin states**. It never invents them."* —
is satisfied here, not violated. This is the textbook case the rule describes.

## 2. The cited evidence does not say what the claim says it says

- `research/scarface-rules-accelerator.md:13` (headline finding 3) lists the liquidity
  draws as **"PDH/PDL, old highs/lows, gap fill, all-time high"**. **It contains no
  whole-dollar / psych mention at all.** The only psych-number line in that file is `:69`,
  which the claim does not cite.
- `research/fable-spec-2026-07-12.md:25,28` do carry "psych whole numbers / psych whole
  dollar" — but the fable spec is a *build spec written after* the marks above
  (recovered_reviews rows are dated 2026-03/05 sessions), so it post-dates his statement.
- `backtest_week.py:107` quotes the fable spec, so it inherits the same ordering.

Corpus and Austin agree. Agreement is not interference.

## 3. The "HTF" referent is misidentified

Austin: *"if some htf corpus was collected, its interfering with the 6 levels"*
(`omen-rulebook.md:1093`). The engine has a concrete, named HTF object and it is **not**
the video corpus:

- `backtest_week.py:713 htf_bias_for()` / `tastytrade_feed.py:521` — 1-hour close vs SMA20
  of prior hourly closes, ±0.1% dead band.
- `signal_runner.py:1601 _htf_opposes`, `:2363-2365 HTF_BIAS_VETO`.
- `research/p16_htf_bias.md:91`: the formula is **UNMENTIONED** in the corpus — zero
  TRADER_SAID/DOC_CLAIMS rows. The corpus actually teaches bias on **daily/weekly**, one
  level *above* the coded 1-hour bar. `PHASES.md:59`, `P33`: *"has no author."*

So the object matching his complaint is an engine invention with no corpus backing, the
opposite of the claim's identification. And he explicitly blesses HTF *targets*:
*"we can target longer timeframe levels"* (recovered_reviews.jsonl:21).

## 4. Category error: six levels are ENTRY references, whole-dollar is a TARGET

`signal_runner.py:2665` — `_active_levels = (pdh, pdl, pmh, pml, or_high, or_low)`.
Exactly six. That is the closed set. The whole-dollar figure at
`backtest_week.py:853,858` never enters `level_pairs`; it is only a runner-target
candidate. `omen-rulebook.md:1047` puts "nearest of the six levels" on the *30% slice*,
and his own note puts "whole psych number" on the *exit*. Two different objects.

## 5. Reachability + measurement (independently re-run, current book)

`research/g71_levels_verify_wholedollar.py` — recomputes the candidate set of
`backtest_week.py:850-859` for every traded row, 730d archive replay, `SCALE_PLAN='hod_then_runner_be'`.

14 of 28 archived symbols, **1,762 traded rows**:

| runner target set by | rows | share | mean R |
|---|---:|---:|---:|
| whole dollar (`floor(scale)+1` / `ceil(scale)-1`) | 1,534 | **87.1%** | +0.4997 |
| PDH/PMH (or PDL/PML) | 228 | 12.9% | +0.4722 |

`|runner_tgt − scale_level|`: median $0.420, p90 $0.880, **max $1.000**.
4-symbol sub-run: 480 rows, 88.1% / 11.9% — stable.

The branch is fully reachable and dominant, by construction: the whole-dollar candidate is
always ≤ $1.00 beyond the scale level, so a named level only wins when it happens to sit
inside that same dollar. **No look-ahead**: `scale_level` is `max(high for candles[:i+1])`
(`backtest_week.py:851`), as-of the entry bar.

## 6. Book identity

The claim offers **no count at all**, so the "right book" test cannot be failed or passed
by it. For the record, the book on disk is **2,437 rows** (`research/bt2y_trades.json`,
`145d564e`), not 2,595 — `DIRECTION.md:20,27` is stale (already flagged at
`research/g71_ddverify.md:33`, `g71_exitfam.md:170`). My numbers above are re-run from
`data_archive/`, not read from either JSON.

## What IS true, and is a separate finding

The whole-dollar candidate **caps every runner at ≤ $1.00 past the session extreme**
(median $0.42). On an $800 stock that is ~0.05%. That is a real target-selection defect
worth a ticket — but it is a *sizing/geometry* bug in how his stated rule was implemented,
not corpus pollution, and deleting the branch would delete a rule he stated three times.
Correct framing: the whole-dollar grid needs a magnitude-aware step
(`research/levels.py:113` already builds a whole+half-dollar grid), not removal.
