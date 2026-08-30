# Number Provenance — Published figures and books

2026-08-30. Inventory of every published dollar and mean-R figure in the trading repo, with source attribution, script verification, and staleness assessment based on current book structure.

---

## Summary

The repo contains **47 published financial figures** across 8 major documents, primarily dated 2026-08-29 to 2026-08-30. All figures from the 4,508-trade book (current, 2026-08-29 18:38) are current. The 2,437-trade book (OMEN 7.1 era, 2026-08-29 03:14) is **superseded but not deleted**. No figures are falsely attributed. All named source scripts exist on disk. One conflict exists: research/g80_ordertype_grid vs research/g80_dollar_reconcile report $48 and $187 per day respectively — same instrument and timestamp, different fills.

---

## Current Book Status

| metric | value |
|---|---|
| **Trade count (total rows)** | 134,012 |
| **Signals generated** | 134,012 |
| **Actually traded (status != X, not halted)** | **4,508** |
| **Generated** | 2026-08-29 18:38:17 |
| **Sessions** | 500 (2024-08-21 to 2026-08-21) |
| **Symbols** | 28 |
| **Risk per trade** | $1,000 (1R) |
| **Loss halt active** | True |
| **Trades halted by loss policy** | 1,662 |

Previous book (superseded, not deleted): **2,437 trades** (from 76,019 signals, built 2026-08-29 03:14).

---

## Figures by Priority (Most Quoted First)

### DIRECTION.md (2026-08-26)

| line | figure | metric | book | source script | script exists | assessment |
|---|---|---|---|---|---|---|
| 21 | $2,633,850 | total 2-year | 4,508 trades | research/g72_after_headline.py | YES | CURRENT |
| 21 | $360,380 | total 2-year | 499 trades (1/day) | research/g72_after_headline.py | YES | CURRENT |
| 21 | mean R 0.58 | per trade | 4,508 trades | research/g72_after_headline.py | YES | CURRENT |
| 21 | mean R 0.72 | per trade | 499 trades (1/day) | research/g72_after_headline.py | YES | CURRENT |
| 21 | $549 / $584 per trade | comparison | 2,437 → 4,508 trades | research/g72_after_headline.py | YES | SNAPSHOT (before/after fix) |

**Freshness**: Document dated 2026-08-26, but cites 2026-08-29 data; reflects latest book. Used as the gate status summary.

---

### OMEN-7.2.md (2026-08-29)

| line | figure | metric | description | assessment |
|---|---|---|---|---|
| 199 | mean 2.0R per day | threshold | money gate target, one-trade-a-day policy | TARGET, not measured |

**Freshness**: Spec document; gate definition, not a measured result.

---

### OMEN-7.3.md (2026-08-30)

| line | figure | metric | book | assessment |
|---|---|---|---|---|
| 22 | $721/day | per-day | 499 (published, 1/day) | CURRENT (from g72_after era) |
| 141 | $683/day | per-day | 499 trades | CONTROL fill (not obtainable) |
| 142 | $68/day | per-day | 499 trades | Limit-chase-once model |
| 143 | $48/day | per-day | 499 trades | Market-at-close model |
| 150 | $613/day | bootstrap CI | control vs chase once | SECONDARY (derived) |
| 156 | $92/day | bootstrap CI | resting-limit model (corrected) | SECONDARY (audited) |
| 165 | $187/day | shares | per-day baseline | instrument comparison |
| 166 | $346/day | options | tape-matched volatility | instrument comparison |
| 174–176 | $44, $162, −$154 | option-spread grid | 2¢, 5¢, 10¢ variations | sensitivity analysis |
| 190 | $117/day cost | exclusion | removing 19 trades (0.42%) | impact measure |
| 197 | $48 or $187 | range conflict | two independent rigs | **CONFLICT NOTED** |
| 203–211 | $397/day bar | target vs achieved | six-figures-a-year = $397/day | bars not met |

**Freshness**: Live analysis 2026-08-30, unpublished until now. Refers to 2026-08-29 data. Multiple instrument scenarios; not all against current book.

---

### research/g71_board.md (2026-08-29)

| line | figure | metric | book | source script | script exists | assessment |
|---|---|---|---|---|---|---|
| 5 | 2,437 trades | book identifier | OMEN 7.1 | (metadata) | N/A | **STALE—superseded book** |
| 12 | $305/day | per-day | 2,437 trades | (no script named) | N/A | STALE |
| 14 | $611/day | per-day | 2,437 trades | (no script named) | N/A | STALE |
| 38 | $1,000 risk unit | sizing context | (generic) | N/A | N/A | CONTEXT ONLY |
| 57 | $306/day | impact (one fix) | 2,437 trades | research/g71_board_check.py | YES | STALE (earlier book) |
| 58–59 | $120–$213 per trade, win +5.5pp | impact (disaster stop) | 2,437 trades | (estimated from narrative) | — | STALE |
| 63 | $55,600 total, $23/trade | impact (target fix) | 2,437 trades | (narrative, not sourced) | — | STALE |
| 125–130 | $2,700, $611, $806, $953, $897 | per-day scenarios | 2,437 trades | (table context, no script) | — | STALE |
| 168–172 | +$550, +$539 per trade | exit models | 2,437 trades | research/g71_rtargetV_verify.py | YES | STALE |
| 183–188 | $40, $85, $56, $11, −$38, −$7 per trade | exit sensitivity | 2,437 trades | (no script named) | — | STALE |

**Freshness**: Document dated 2026-08-29, but all figures from 2,437-trade book built 03:14 on the same day. Superseded by later reports using 4,508-trade book (18:38).

**Note**: This is the OMEN 7.1 board. Even though dated 2026-08-29, all dollar figures are from the earlier (03:14) book and are superseded by the 18:38 build. No one is quoting these figures as the current state anymore — the board was the interim decision point, not the final answer.

---

### research/g76_rebuild_verdict.md (2026-08-29)

| line | figure | metric | book | source script | script exists | assessment |
|---|---|---|---|---|---|---|
| 12 | $721/day published | per-day | 499 (1/day, published) | research/g76_rebuild_engine.py | YES | CURRENT |
| 17 | $28/day | per-day | 500 sessions, honest rebuild | research/g76_rebuild_engine.py | YES | CURRENT REBUILD |
| 18 | $0/day | per-day | honest rebuild | research/g76_rebuild_engine.py | YES | CURRENT REBUILD |
| 19 | $114/day | per-day | 455 trades (resting order) | research/g76_rebuild_engine.py | YES | CURRENT REBUILD |
| 20 | $86/day | per-day | 455 trades (resting order, 1/day) | research/g76_rebuild_engine.py | YES | CURRENT REBUILD |
| 22 | −$103 / −$68 / −$104 per day | lateness penalty | 500 sessions | research/g76_rebuild_engine.py | YES | CURRENT REBUILD |
| 55 | mean +0.70R | per trade | 3,841 trades (prefilled at level) | research/g76_rebuild_engine.py | YES | CURRENT REBUILD ANALYSIS |
| 56 | mean −0.07R | per trade | 667 trades (paid the close) | research/g76_rebuild_engine.py | YES | CURRENT REBUILD ANALYSIS |
| 86–87 | mean +0.584R published vs +0.580R head start | per trade | 4,508 trades | (derived analysis) | — | CURRENT VERDICT |
| 193 | $1,700/month or $86/day | recommendation | 455 trades (resting order, 1/day) | research/g76_rebuild_engine.py | YES | CURRENT RECOMMENDATION |
| 216 | mean +0.095R | per trade | honest rebuild | research/g76_rebuild_engine.py | YES | CURRENT (conclusion) |

**Freshness**: Published 2026-08-29, re-derived from the 2026-08-29 18:38 book. All figures are audits of the current (4,508) book, not new book builds. Non-obtainability verdict is the current consensus view.

---

### research/g72_after.md (2026-08-29)

| line | figure | metric | book | source script | script exists | assessment |
|---|---|---|---|---|---|---|
| 18 | $5,268/day | per-day | 4,508 trades | research/g72_after_headline.py | YES | CURRENT |
| 22 | $2,633,850 | total 2-year | 4,508 trades | research/g72_after_headline.py | YES | CURRENT |
| 30 | $721/day | per-day | 499 (1/day) | research/g72_after_headline.py | YES | CURRENT |
| 34 | $360,380 | total 2-year | 499 (1/day) | research/g72_after_headline.py | YES | CURRENT |
| 53 | mean 0.58R | per trade | 4,508 trades | (narrative context) | — | CURRENT |
| 53 | mean 0.72R | per trade | 499 (1/day) | (narrative context) | — | CURRENT |
| 109–115 | $5,268 (all), −$271, −$125, $355 (resting), −$671 (late) per day | per-day scenarios | 4,508 trades | research/g72_suppress_price.py (implied) | ? | CURRENT (multiple scenarios) |
| 148–149 | +2.40R / −1.00R | resting order model | (derived from rebuild) | — | — | CURRENT REBUILD FINDING |

**Freshness**: Published 2026-08-29 18:38, reflects the book built at that timestamp. The definitive report on the 4,508-trade book post-fix-pass. This is the book in the repo right now.

---

## Figures Grouped by Book

### 4,508-Trade Book (CURRENT — 2026-08-29 18:38)

All figures below are in the repo's `research/bt2y_trades.json` right now.

| Per day / Per trade | one-trade-a-day (499 trades) | all signals (4,508 trades) | source | date |
|---|---|---|---|---|
| **Dollars per day** | $721 | $5,268 | research/g72_after_headline.py | 2026-08-29 |
| **Dollars total 2-year** | $360,380 | $2,633,850 | research/g72_after_headline.py | 2026-08-29 |
| **Mean R per trade** | 0.72R | 0.58R | research/g72_after_headline.py | 2026-08-29 |
| **Win rate** | 66.7% | 59.4% | research/g72_after_headline.py | 2026-08-29 |
| **Months green** | 25 of 25 | 25 of 25 | research/g72_after_headline.py | 2026-08-29 |
| **Weeks green** | 87 of 105 | 100 of 105 | research/g72_after_headline.py | 2026-08-29 |
| **Worst drawdown** | $5,993 | $11,105 | research/g72_after_headline.py | 2026-08-29 |

Honest rebuild (NOT currently tradeable, for comparison):
- Resting order, one order a day: **$86/day** = **$1,724/month** (range −$1,100 to +$4,700, not distinguishable from zero)

### 2,437-Trade Book (SUPERSEDED — 2026-08-29 03:14)

Figures from the OMEN 7.1 board era. Built earlier on 2026-08-29.

| Per day | one-trade-a-day (496 trades) | all signals (2,437 trades) | 
|---|---|---|
| **Dollars per day** | $611 | $2,700 |
| **Win rate** | 54.9% | 49.5% |
| **Months green** | 22 of 25 | 25 of 25 |
| **Worst drawdown** | $20,100 | $14,714 |

**Status**: STALE. These are cited in research/g71_board.md (the board itself) as the state before a fix pass. The 4,508-trade book (18:38) is the state after the pass. No active reports use the 2,437 book anymore.

### 1,017-Trade Book (DEAD)

Referenced in comments as `backtest_week` era. No figures published; no longer on disk.

---

## Known Conflicts

### $48 vs $187 per day (options fill)

| source | $/day | basis | date |
|---|---|---|---|
| research/g80_ordertype_grid.md (implied title) | $48 | market at close, A/B control | 2026-08-30 |
| research/g80_dollar_reconcile.md (implied title) | $187 | market at close, honest rebuild | 2026-08-30 |

**Assessment**: Both measure the same instrument (shares via market at close), same book (4,508), same timestamp. One reports $48, the other $187. Per OMEN-7.3.md line 197, both reproduced under their respective frameworks. The rigs differ in some detail of fill or accounting; the discrepancy is documented as **worth $139 a day** and unresolved. No figure claimed as the reconciled truth.

---

## Script Inventory

All source scripts named in the figures above:

| script | exists | last modified | lines | purpose |
|---|---|---|---|---|
| research/g72_after_headline.py | YES | 2026-08-29 18:37 | 250 | read 4,508-trade book, reuse old arithmetic |
| research/g71_board_check.py | YES | 2026-08-29 16:22 | 120 | impact analysis for one policy |
| research/g71_rtargetV_verify.py | YES | 2026-08-29 16:09 | 420 | target value hypothesis testing |
| research/g76_rebuild_engine.py | YES | 2026-08-29 23:07 | 600 | rebuild trades under honest fills |
| research/g80_ordertype_grid | NO RULE FOUND (referenced in text) | — | — | inferred from context |
| research/g80_dollar_reconcile | NO RULE FOUND (referenced in text) | — | — | inferred from context |

---

## Rules for This Inventory Going Forward

1. **Every published figure goes in a table row.** Measured results, not targets. Targets (like "mean 2.0R") go in a separate section.

2. **Trade count is the book identifier.** If the current `research/bt2y_trades.json` shows `"traded": 4,508`, all figures from the 2,437-trade book are STALE.

3. **Source script must be named or the figure is unsourced.** Unsourced figures are allowed (e.g., derived in prose) but marked as such.

4. **Date is the report date, not the book date.** A report dated 2026-08-30 can cite 2026-08-29 data if it re-reads that book.

5. **Scripts are re-runnable guardrails.** If a figure names a script, the script must exist on disk. If it doesn't, it has been deleted or refactored, and the figure should be marked AUDITED NOT REPRODUCIBLE.

---

## Next Steps

- **Conflict resolution**: Audit research/g80_ordertype_grid and research/g80_dollar_reconcile (or equivalents) to settle $48 vs $187.
- **Superseded book cleanup**: Once a newer book is built, old figures are stale but not deleted. Update this inventory as each build happens.
- **Spec documents**: DIRECTION.md should cite this table as the source of truth for quoted figures, not re-type them.

---

## The staleness that matters more than book size

*Added 2026-08-30 after the order-type and look-ahead work landed. The inventory above checks
whether a figure was computed on the current BOOK. That is the smaller of the two problems.*

Every dollar figure in this repo computed on the **published fill** is from the right book and is
still unobtainable, because of how the entry price is chosen (`signal_runner.py:1330`):

- **Only 105 of 4,508 trades (2.3%, $111,556) are genuinely obtainable at the book's price.**
- **2,067 of 3,841 intrabar fills (53.8%, $1,504,056)** sit at the minute's own low or high with the
  level *outside* the bar. A resting order at the level fills **nothing** on those.
- Of the 1,769 that are genuinely at the level, the level was first touched on an **earlier
  minute in 96.9%** of traced cases — the order was already filled, holding a different position.
- Held fixed on the same trades, changing only the price paid: mean **+0.698R → +0.022R**.

So a figure can pass every check in the table above and still describe money nobody could have made.

**The rule for anyone reading this repo: a dollar figure is only live if it names its FILL as well
as its book.** The obtainable figures, one trade a day, are:

| fill | $ / day |
|---|---:|
| the published book fill — **not obtainable** | $683 – $721 |
| market at the signal minute's close, shares | $48 – $187 *(two rigs, unreconciled)* |
| chase-once (limit one bar, then market), shares | $68 |
| market at close, same-day options, tight spread | $242 – $346 |

*Sources: `research/g80_lookahead_refute.md`, `research/g80_ordertype_grid.md`,
`research/g80_options_honest.md`, `research/g80_dollar_reconcile.md` — all four scripts on disk.*

**Correction to the summary above:** `research/g80_ordertype_grid.py` and
`research/g80_dollar_reconcile.py` both exist on disk (30,817 and 17,951 bytes, written 02:20 and
01:53 on 2026-08-30). An earlier draft of this inventory reported them as inferred-but-not-found.
