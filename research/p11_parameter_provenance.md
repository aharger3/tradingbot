# P11 (G5) — Parameter Provenance Sweep

**Date:** 2026-08-26. Read-only: `research/corpus_index.jsonl` (5,460 rows) was
queried, never rebuilt. Every verdict below is CONFIRMED / CONTRADICTED / UNMENTIONED
against a rule Austin (or a source he learns from) actually said — the corpus
validates, it does not invent. Reproduce every row here by running
`python research/p11_parameter_provenance.py`, which prints the raw
`corpus_query.py` output (grouped by provenance class) behind each verdict.

Worklist: every tunable in `research/parameter_catalog_draft.md`'s Sections A and B
(34 scored parameters; `_GRADE_RANK` is a structural helper, not a tunable, and is
excluded per the draft's own note), plus `BAR_EXTREME_FRAC` — not in the draft
(written 2026-07-12, before this constant existed in `signal_runner.py`) but named
explicitly in `CLAUDE.md`/`DIRECTION.md` as "the one tolerance unit," so it belongs
in any sweep of coded constants.

Provenance classes (from `research/t63b_corpus_reverify.md`): **TRADER_SAID**
(verbatim quote — the only class that can CONFIRM or CONTRADICT on its own),
**DOC_CLAIMS** (a rule-extraction doc's own assertion, no quote), **CODE_COMMENT**
(a claim living in `signal_runner.py` itself), **DERIVED** (an earlier audit pass's
own verdicts, `hallucination-audit.md`). A `CODE_COMMENT` row is never itself
confirmation — see the Circular Citations section.

---

## A. Module-level named constants

| # | Constant (loc = value) | Verdict | Strongest support (class, quote) |
|---|---|---|---|
| A1 | `OB_RETEST_TYPES` (sr:50 = `("wick_only",)`) | **CONFIRMED** | TRADER_SAID `scarface-rules-youtube.md:22/188` — "the best order blocks... are going to hold the top of the wick... and close above the top of the wick and continue." |
| A2 | `OB_VOLUME_MULT` (sr:51 = `0.0`, gate off) | **UNMENTIONED** | No TRADER_SAID/DOC_CLAIMS row anywhere states a volume-confirmation requirement for OB/B&R entries. The value is a pure backtest-sweep result ($1,335 vs $2,505), never a trader claim either way. |
| A3 | `FVG_RETEST` (sr:63 = `False`) | **CONTRADICTED** (indexed corpus) — see note | TRADER_SAID `scarface-rules-videos.md:11418` (score 11) — "the best order blocks happen when... you have a fair value gap... all those things aligning" teaches FVG as a valid retest zone; the coded value disables using one. **Note:** `signal_runner.py:345/364` carries "Austin, 2026-08-24: 'I don't trade FVG or FLAG. Those are not setups anymore'" — independently echoed in `research/t70_metric_sweep.md:19`. That quote, if real, reverses this verdict to CONFIRMED, but it lives only as CODE_COMMENT (plus one other agent's report, not one of the 10 indexed rule-extraction docs) — not TRADER_SAID in the index. Flagging rather than silently upgrading the verdict off a source outside the corpus this sweep is scoped to. |
| A4 | `FLAG_ENABLED` (sr:67 = `False`) | **UNMENTIONED** | No trader ever teaches a standalone flag (pole→pause→breakout) entry setup; corpus "flag" hits are all about HTF pattern targets, not an OMEN entry detector. Same 2026-08-24 Austin quote as A3 reinforces this outside the index. |
| A5 | `STRONG_PA_MULT` (sr:90 = `1.5`) | **UNMENTIONED** (value) | Concept-adjacent CONFIRMED: TRADER_SAID `scarface-rules-videos.md:220` — "very strong candle... pushes above, retest" — but zero rows state a 1.5x-of-average-body multiplier. |
| A6 | `CHASE_PCT` (sr:98 = `0.005`) | **UNMENTIONED** | No TRADER_SAID row states a "don't chase" threshold, numeric or otherwise. The draft's own citation for the concept traces to a Discord community member (audit #48), not Scarface/jdub — and even that is a paraphrase, not a percent. |
| A7 | `RULE84_LESSON` (sr:103 = `True`) | **CONTRADICTED** | TRADER_SAID `84rule-sizing-dossier.md:151` / `scarface-rules-youtube.md:161` (score 11, verified) — "I need to see some strong buying action near this level... I'm not just going to enter off some random candle" — requires a PA gate on the reclaim candle. `RULE84_LESSON=True` selects the lesson-faithful variant that skips exactly that gate (`hallucination-audit.md` #32, DIVERGES). The other coded variant (`RULE84_LESSON=False`, "Austin's chat def") already matches. |
| A8 | `RULE84_ARM_BNR_ONLY` (sr:111 = arms on any B&R stop-out) | **CONTRADICTED** (partial — source narrower) | TRADER_SAID `scarface-rules-videos.md:162` — "the thing you need to know about the 84% rule is you need an A plus entry." Source restricts arming to A+-quality entries; the coded gate arms on any break-and-retest stop-out regardless of quality (`hallucination-audit.md` #33, SOURCE-SAYS-MORE). |
| A9 | `BNR_STOP_MODE` (sr:120 = `"level"`) | **CONTRADICTED** | TRADER_SAID `scarface-rules-videos.md:5052` (Hayden, score 8) — "the stop loss should just be the time to close stop... it should just be the retest candle low," plus `scarface-rules-mastermind.md:29` (mm 5.0) — "10-15 cents buffer below level for room." Coded stop sits at the exact level. F2 A/B (`research/f2f1_runs/session-notes.md`) found both source-taught alternatives lose money on identical entries — an economically-justified override, still a real divergence from what was taught. |
| A10 | `HODLOD_PAIR` (sr:128 = `False`) | **CONFIRMED** (concept; off-state doesn't contradict) | TRADER_SAID `scarface-rules-mastermind.md:63` (score 10) — "Wait for HOD break and retest or LOD break and retest. Nothing in between — all noise." Austin never says the setup must always be live; F3 measured no edge as specced and turned it off — `hallucination-audit.md` row 126 explicitly re-confirms the concept while agreeing the off-state stands. |
| A11 | `LEVEL_BLOCK_CAP` (sr:152 = `True`) | **CONFIRMED** | TRADER_SAID `scarface-rules-coaching-bonus.md:68` — "2R must be achievable within the stock's average daily range. If target is $15 but stock moves $2/day — skip." |
| A12 | `CLEAR_FOR_APLUS` (sr:153 = `True`) | **CONFIRMED** | Same coaching-bonus citation as A11 (2R-achievability implies a clear road to target); audit #19 covers both under one verdict. |
| A13 | `STOP_RANGE_MULT` (sr:154 = `0.75`) | **UNMENTIONED** (value) — see Circular Citations | No TRADER_SAID row states any numeric stop-vs-range multiplier. `hallucination-audit.md` #20 already says "Not in source." |
| A14 | `_GRADE_RANK` | N/A — structural ordering helper, not a tunable, no evidence needed | — |

## B. Inline tunables

| # | Constant | Verdict | Strongest support |
|---|---|---|---|
| B1 | Hammer confirm thresholds (`_confirm_candle`) | **CONFIRMED** (concept) / **UNMENTIONED** (wick≥body ratio) | TRADER_SAID `scarface-rules-videos.md:6619` — "inverted hammer candles or regular hammer candles or shooting star candle... some of the best trades." No source states a wick/body ratio; audit #50 calls the exact threshold OURS. |
| B2 | Min viable stop (`_min_viable_stop`, ≥0.5% or ≥$0.20) | **UNMENTIONED** | Calibration-derived against 303 labeled trades, not a source-stated numeric floor. |
| B3 | A+ stack displacement (`_aplus_stack`) | **CONTRADICTED** (partial — source requires more) | TRADER_SAID `scarface-rules-videos.md:8297` (score 11) — "an A plus setup would have to have a qqq context [and] a higher time frame thesis" — plus a HTF-level requirement. Coded stack has neither (audit #17, SOURCE-SAYS-MORE). |
| B4 | Stack floor-B / pattern D→C promotions | **UNMENTIONED** | Internal fix ("pattern grader D-benched 38 of 53 stack setups") — engineering, not sourced. |
| B5 | LATE cap (level already broken this session → cap B) | **CONFIRMED** | TRADER_SAID `scarface-rules-mastermind.md:38` — "First retest is best. Fresh level. Not something retested multiple times." |
| B6 | B&R min risk (`max(0.10, 0.0015*close)`) | **UNMENTIONED** | No source states a relative min-risk formula; draft flags the exact multiplier as possibly over-aggressive, itself unsourced. |
| B7 | PMH/PML cap to C | **CONFIRMED** | TRADER_SAID `scarface-rules-videos.md:1932` — PM levels used "when you're either gapping up or gapping below, or if you have no key levels" — secondary/contextual, consistent with alert-only. |
| B8 | S-score weights (clean+2/A+2/stop+2/nonPM+1/hammer+2/qqq+1) | **UNMENTIONED** (the weighting scheme itself) | `hallucination-audit.md` #47: "Data-derived (24mo split), not course-attributed" — OURS. Individual ingredients (hammer, QQQ alignment) are separately sourced elsewhere; the point values are not. |
| B9 | OCR demote + wide-stop D-gate (A-grade+tight-stop only, 0.4% cutoff) | **UNMENTIONED** | Concept "stop below the order block" is sourced (`scarface-rules-accelerator.md:37`); the specific A-only/0.4% gate is calibration-derived, unsourced. |
| B10 | OCR/FVG/Flag min risk $0.50 | **UNMENTIONED** | Flagged in the draft itself as "NO EVIDENCE FOUND," a legacy flat threshold never re-tested. |
| B11 | 84% RR gate (≥1.5x remaining reward) | **UNMENTIONED** | `hallucination-audit.md` #37: "Not in source" — OURS. Source's related statement (re-entries skip the HOD scale) isn't what's coded either. |
| B12 | 84% HOD/LOD proximity skip (top/bottom 20% of day range) | **UNMENTIONED** | `hallucination-audit.md` #38: "Not in source" — OURS; quantifies a qualitative "near high of day" with no stated percentage. |
| B13 | 84% C→B floor (alert-tier promoted to tradeable) | **UNMENTIONED** | No trader statement addresses whether a C-grade 84% signal should be promotable; this is what keeps the setup firing at all, an engineering choice. |
| B14 | 84% one-shot disarm (one re-entry, then disarm) | **UNMENTIONED — reclassifying a prior MATCHES** | `hallucination-audit.md` #35 called this MATCHES against "whenever you see... two or three of the same setups... that just means it's going to be more of a choppy day" (Se_P4N3u48o). `research/t63_corpus_readiness.md` already flagged this exact citation as **an interpretive leap, not a citation** — that quote describes recognizing a choppy-day regime, not a stated cap on re-entry attempts. Agreeing with t63/t63b here, not with the original audit row: no TRADER_SAID row states a numeric or "one" cap on 84%-rule fires. |
| B15 | Calibration grade (`_calibration_grade`) | **CONTRADICTED** (counter-trend proxy) / UNMENTIONED (90-min value) | `hallucination-audit.md` #18: coded counter-trend cap uses the stock's own day trend (`candles[0].open`); source's trend filter is QQQ/SPY-based. The "wait before first entry" half is concept-CONFIRMED (TRADER_SAID `scarface-rules-mastermind.md:64` — "Never trade the first 5 minutes — need trend to develop"), but no source states 90 minutes specifically. |
| B16 | Consolidation skip 0.5% (`_is_consolidation`) | **CONFIRMED** (concept) / UNMENTIONED (0.5% value) | `hallucination-audit.md` #12 cites the source's own menu: "Choppy market: skip entirely or size down" — "skip entirely" is one of two stated options, so the coded behavior matches one of them. No source states 0.5%. |
| B17 | `_closes_strong` shape (body≥0.5x range, close within 0.25x of extreme) | **UNMENTIONED** | Explicitly a replay-derived engineering fix ("Scarface replay 06-12 TSLA"), not a stated threshold. |
| B18 | Blind 2R target (target = entry ± 2x risk, everywhere) | **CONTRADICTED** | DERIVED/TRADER_SAID (`hallucination-audit.md` #7, acc headline 3) — "2:1 is the MINIMUM aggregate expectation, not the exit mechanism"; source scales out at HOD/LOD first, then further liquidity. F1 A/B kept blind 2R anyway (both liquidity-ladder variants lost more tier P&L) — an economic override of a stated rule, same shape as A9. |
| B19 | F3 HOD/LOD level-pair constants (≥43 candles, 30-min age, 0.1% dedupe) | **UNMENTIONED** | No source states these specifics; moot today since `HODLOD_PAIR=False`. |
| B20 | Traded-level ignore band (0.1x risk) | **UNMENTIONED** | Pure anti-self-block engineering; no source addresses it. |

## X. Not in the draft, named in CLAUDE.md as load-bearing

| # | Constant | Verdict | Support |
|---|---|---|---|
| X1 | `BAR_EXTREME_FRAC` (sr:339 = `0.25`) — governs the ON WATCH entry trigger, the 84% reclaim window, and stop slippage (per `CLAUDE.md`) | **UNMENTIONED — circular citation** | See below. Re-confirms `research/t63b_corpus_reverify.md`'s question (c) finding verbatim: zero TRADER_SAID rows across every query tried state any reclaim-distance tolerance. |

---

## 1. Headline: how many coded constants have no stated source at all

**20 of 34 scored parameters (59%) are UNMENTIONED** — no TRADER_SAID or DOC_CLAIMS
row anywhere in the 5,460-row index supports the constant's actual coded value.
A2, A4, A5, A6, A13, B1(ratio), B2, B4, B6, B8, B9, B10, B11, B12, B13, B14, B17,
B19, B20, X1.

The pattern is consistent across all twenty: **the underlying concept is usually
well attested (hammer entries, order blocks, the 84% rule, choppy-day sizing), but
the precise number that operationalizes it — 1.5x, 0.75x, 0.5%, 20%, $0.50,
0.0015, 43 candles, 30 minutes, 0.25 — is never once stated by a trader.**
Austin and Scarface teach qualitative judgment ("strong buying action," "clear
stop," "near high of day"); every quantification is engineering, and none of it
is source-cited beyond the code itself.

## 2. Every CONTRADICTED row, in full

| Parameter | Coded value | What the source actually says instead |
|---|---|---|
| `FVG_RETEST` (A3) | `False` (never retest the FVG) | Source teaches the FVG as a valid retest zone ("all those things aligning") — contradicted **against the indexed corpus**; a newer, out-of-index Austin quote ("I don't trade FVG... not setups anymore") likely reverses this, but isn't TRADER_SAID in the index yet. |
| `RULE84_LESSON` (A7) | `True` — skips the PA gate on the reclaim candle | "I need to see some strong buying action near this level... not just going to enter off some random candle" — source requires a PA gate; the other already-coded variant (`RULE84_LESSON=False`) matches it. |
| `RULE84_ARM_BNR_ONLY` (A8) | Arms on ANY break-and-retest stop-out | "You need an A+ entry" — source restricts arming to A+-quality setups specifically, not any B&R. |
| `BNR_STOP_MODE` (A9) | `"level"` — stop at the exact broken level | Source: stop = retest-candle low, or level minus a 10-15 cent buffer. F2 A/B found both lose money on identical entries — kept `"level"` anyway. |
| A+ stack (`_aplus_stack`, B3) | first break + 1.5x-body displacement + strong PA | Source's A+ additionally requires QQQ/SPY context and a higher-timeframe level — neither is in the coded stack. |
| Calibration counter-trend cap (B15) | Uses the stock's own day trend (`candles[0].open`) | Source's trend filter is QQQ/SPY-based, not the stock's own candles. |
| Blind 2R target (B18) | Target = entry ± 2x risk, everywhere | "2:1 is the MINIMUM aggregate expectation, not the exit mechanism" — source scales at HOD/LOD first, then further liquidity levels. |

Every row above is a **potential bug, flagged and not fixed**, per the task's
invariant. Three of the seven (A9, B3's QQQ leg, B18) are already known and were
kept deliberately after A/B testing showed the source-taught alternative losing
money — those are documented trade-offs, not oversights. A7, A8, and B15 do not
appear to have a documented economic rationale for staying diverged; they read as
gaps rather than deliberate overrides.

## 3. Circular citations — constants whose only support is their own code comment

| Constant | The circularity |
|---|---|
| `BAR_EXTREME_FRAC` (X1, sr:339 = `0.25`) | Cited four times across `signal_runner.py` (339, 546, 565-566, 636-637) — including the line "same 25% that governs the 84% reclaim and stop slippage. One tolerance unit" — and by **nothing else**. No TRADER_SAID/DOC_CLAIMS/DERIVED row states a reclaim-distance, entry-trigger, or slippage tolerance of 25% or any other number. This is the cleanest circular citation in the sweep, and it is load-bearing across three separate gates per `CLAUDE.md`. |
| `STOP_RANGE_MULT` (A13, sr:154 = `0.75`) | The human-proof rationale — Austin: tight stops "lose the $1,000 in a second" (`signal_runner.py:1044`) — does not appear anywhere in `EXTRACTED_TRADING_RULES.md`, any `scarface-rules-*.md` file, or `84rule-sizing-dossier.md`. The quote may well be real (a chat message, not a video transcript), but as far as the indexed corpus is concerned, the only place it exists is the comment that uses it to justify itself. |
| `LEVEL_BLOCK_CAP` (A11) | Partial case, not full: the specific phrase used to justify it — Austin, "middle of a bunch of levels, probability goes down significantly" (`signal_runner.py:150`) — the draft itself notes was "NOT found in `_all_trade_reviews.json` (grep) — inline comment is the only record of it." The row still nets CONFIRMED above because an *independent* TRADER_SAID quote ("2R must be achievable within the stock's average daily range — skip") supports the same substantive rule — but the specific attributed quote is unverifiable outside the code. |

---

## Agreement with `hallucination-audit.md`

Not edited; referenced only. Where this sweep's provenance-index method disagrees:

- **B14 (84% one-shot disarm):** audit #35 says MATCHES. This sweep says
  UNMENTIONED, agreeing instead with `t63_corpus_readiness.md`'s own finding that
  audit #35's citation is an interpretive leap (a choppy-day-regime quote, not a
  stated per-day cap) — better supported by the more careful t63/t63b read than
  by the original audit pass.
- **A8 (`RULE84_ARM_BNR_ONLY`) and B3 (A+ stack):** audit already flags both
  SOURCE-SAYS-MORE (#33, #17). This sweep folds that into CONTRADICTED under the
  task's 3-bucket scheme, since the source states a narrower/stricter rule than
  what's coded — same underlying finding, different bucket name.
- Everywhere else this sweep lands on a row the audit already scored (A1, A9-A12,
  B1, B5, B7, B15, B16, B18), the verdicts agree; this sweep mainly adds the
  parameters the audit's per-rule table never covered (A2-A6, A13-A14, B2, B4,
  B6, B8-B14, B17, B19-B20, X1) and separates "concept confirmed" from "specific
  number confirmed," which the audit's MATCHES/DIVERGES table does not
  distinguish.

## Reproduce

```
python research/p11_parameter_provenance.py
```
Prints the raw `corpus_query.py` results (grouped TRADER_SAID / DOC_CLAIMS /
CODE_COMMENT / DERIVED) behind every verdict above, for all 35 queries run.
