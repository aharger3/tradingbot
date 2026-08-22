# T60 — Archive coverage vs. detection: settling the 16/120 question

Read-and-report only. No source code modified. Method below is fully reproducible from
`research/marks/deck_marks_index_2026-08-19.jsonl` (97 rows) + `research/marks/deck_marks_tsla_2026-08-20.jsonl`
(87 rows) — the two files 04's ticket names — plus `data_archive/` and the four pool-defining
scripts (`universe.py`, `live_scanner.py`, `archive_1m.py`, `build_corpus_instances.py`,
`backtest_week.py`). `research/marks/LEDGER.md` did not exist at the time this was written, so it
was not used.

## 0. What Austin actually graded

`deck_marks_index_2026-08-19.jsonl` + `deck_marks_tsla_2026-08-20.jsonl` contain 120 `type:"day"`
rows (97 + 87 rows total, 64 are `type:"trade"` sub-rows attached to those days). 120 distinct
`(symbol, date)` day-cards, 0 collisions, 0 orphan trade-rows — matches `research/marks_summary.md`
exactly ("day_cards: 120").

**Only three symbols were graded**: QQQ (30 days, 2026-06-29→2026-08-10), SPY (30 days,
2026-06-29→2026-08-10), TSLA (60 days, 2026-05-14→2026-08-10). This is a much narrower set than
the full traded universe — the coverage question for this ticket is really "does the archive cover
QQQ/SPY/TSLA over those three windows," not the whole pool.

## 1. Three-way split

| Bucket | Definition | Count | % of 120 |
|---|---|---:|---:|
| (a) NO BARS | symbol+date absent from `data_archive` | **0** | 0.0% |
| (b) BARS, OUT OF POOL | bars exist, symbol not in *any* pool the engine runs | **0** | 0.0% |
| (c) IN POOL, engine could have looked | bars exist + symbol eligible in the live_scanner/`universe.py` pool | **120** | 100.0% |

By symbol:

| Symbol | (a) no bars | (b) out of pool | (c) in pool | Archive range covers graded window? |
|---|---:|---:|---:|---|
| QQQ | 0 | 0 | 30 | yes, no gaps |
| SPY | 0 | 0 | 30 | yes, no gaps — **but see caveat below** |
| TSLA | 0 | 0 | 60 | yes, no gaps |

**This flips the ticket's working hypothesis.** All 120 graded symbol-days have bars in
`data_archive`, and QQQ/SPY/TSLA are all members of `universe.py`'s `ALL_SYMS` (the pool
`live_scanner.py` actually scans). Under the ticket's own bucket-(b) test ("not in the traded
universe for any pool the engine runs"), SPY does not qualify for (b) — it IS in a pool the engine
runs (`INDEX_POOL`, scanned by `live_scanner.py` and archived by `archive_1m.py`). So strictly,
0/120 graded days are a coverage problem and 120/120 are candidates for a detection problem.

**Caveat — pool disagreement, not a coverage gap:** `backtest_week.py`'s own `SYMBOLS` list
(`CORE_SYMBOLS + EXPERIMENTAL_SYMBOLS`) **explicitly excludes SPY** — comment at
`backtest_week.py:32-33`: *"SPY/QQQ stay as trend reference, rarely traded"* / *"A3: SPY removed
(0-for-5)"*. QQQ stays in `CORE_SYMBOLS`; SPY does not appear anywhere in `backtest_week.SYMBOLS`.
If the "engine ran zero SPY trades ever" claim was measured against `backtest_week.py`'s simulated
trades (not the day-level signal replay `engine_recall.md` describes, which runs
`SignalRunner.detect_signals` directly against `data_archive` with no pool filter), then SPY's 30
days are functionally bucket (b) *for that specific pipeline* even though they pass the strict
per-ticket test against the live_scanner pool. Confirmed: `backtest_week.py` itself does not even
replay `data_archive` — its own comment says yfinance is "the live-fetch path... never the
data_archive replay the research rows run on" (backtest_week.py:24-26). So "zero SPY trades" is a
`backtest_week.SYMBOLS`-exclusion artifact, not a `data_archive` coverage artifact and not what
generated the day-grade decks.

## 2. Per-symbol archive coverage (all 34 symbols in `data_archive`, per-symbol-per-day CSV layout: `data_archive/<SYM>/<YYYY-MM-DD>.csv`)

Trading-day calendar reconstructed as the union of all dates seen across the archive (2024-01-02 →
2026-08-13, 656 sessions).

| Symbol | First | Last | # days present | Gaps >3 trading days inside range |
|---|---|---|---:|---|
| AAPL | 2024-01-02 | 2026-08-11 | 654 | none |
| ACHR | 2024-01-02 | 2026-08-10 | 653 | none |
| AMD | 2024-01-02 | 2026-08-11 | 654 | none |
| AMZN | 2024-01-02 | 2026-08-11 | 654 | none |
| ARM* | 2024-02-20 | 2026-06-15 | 582 | none (but stops ~2mo before archive's current edge) |
| AVGO | 2024-08-05 | 2026-08-11 | 506 | none |
| BABA | 2024-08-19 | 2026-08-11 | 437 | 2025-04-14→2025-07-11 (59td) |
| COIN | 2024-02-20 | 2026-08-11 | 621 | none |
| CRM | 2025-06-02 | 2026-08-11 | 275 | 2025-06-02→2025-07-02 (20td); 2025-07-02→2025-07-11 (5td) |
| GOOG | 2025-04-04 | 2026-02-23 | 4 | 2025-04-04→06-10 (44td); →12-08 (124td); →2026-02-23 (50td) — effectively no usable coverage |
| GOOGL | 2024-01-02 | 2026-08-11 | 654 | none |
| HOOD | 2024-07-01 | 2026-08-11 | 530 | none |
| INTC | 2024-01-02 | 2026-08-11 | 654 | none |
| IREN | 2025-07-11 | 2026-08-11 | 273 | none |
| IWM | 2024-01-02 | 2026-08-10 | 653 | none |
| MARA | 2024-09-09 | 2026-08-11 | 278 | five gaps, largest 2024-12-17→2025-04-02 (70td) |
| META | 2024-01-02 | 2026-08-11 | 654 | none |
| MSFT | 2024-01-02 | 2026-08-11 | 654 | none |
| MSTR | 2024-01-02 | 2026-08-11 | 654 | none |
| MU | 2024-01-02 | 2026-08-11 | 654 | none |
| NFLX | 2024-07-02 | 2026-08-11 | 529 | none |
| NVDA | 2024-01-02 | 2026-08-11 | 654 | none |
| ORCL | 2024-01-02 | 2026-08-11 | 654 | none |
| PLTR | 2024-01-02 | 2026-08-13 | 656 | none |
| QCOM* | 2025-04-03 | 2026-06-12 | 21 | 2025-04-11→2026-05-14 (272td); 2026-05-22→2026-06-04 (7td) — effectively no usable coverage |
| QQQ | 2024-01-02 | 2026-08-11 | 654 | none |
| RIVN | 2025-07-11 | 2026-08-11 | 261 | 2026-07-10→2026-07-29 (12td) |
| SMCI | 2024-03-25 | 2026-08-11 | 280 | four gaps, largest 2024-06-20→2025-05-06 (218td) |
| SOFI | 2024-10-30 | 2026-08-11 | 281 | 2024-11-11→2025-07-11 (163td) |
| SPCX | 2024-01-02 | 2026-08-10 | 527 | 2026-04-06→2026-06-12 (47td) — real, recent gap |
| SPY | 2024-01-02 | 2026-08-11 | 654 | none |
| TSLA | 2024-01-02 | 2026-08-11 | 654 | none |
| TSM | 2024-09-16 | 2026-08-11 | 297 | 2024-10-24→2025-07-11 (175td) |
| UBER | 2025-02-07 | 2026-08-11 | 274 | 2025-02-07→2025-07-11 (104td) |

\* ARM and QCOM are not in `live_scanner`'s/`universe.py`'s pool at all — see §3. They're only
relevant to `build_corpus_instances.py`'s wider universe.

### Verifying the KNOWN PRIOR FINDINGS

- **"12 symbols end 2026-07-10 (AVGO, BABA, COIN, CRM, HOOD, IREN, NFLX, SOFI, TSM, UBER); MARA
  ends 2026-07-20; GOOG ends 2026-02-23)" — STALE, no longer true except GOOG.** All ten named
  "2026-07-10" symbols plus MARA now extend to **2026-08-11**. This matches
  `research/t3_archive_coverage.md` (dated 2026-08-10), which documents a backfill run that pushed
  every tracked symbol's archive out to 2026-08-10/11. **GOOG is still broken** — it stops
  2026-02-23 and only has 4 sparse files total (huge internal gaps), i.e. GOOG coverage was never
  fixed by that backfill (GOOG is not in `ALL_SYMS`; `GOOGL` is the one in the pool and it's fully
  covered).
- **"Engine ran ZERO SPY trades ever."** SPY bars are fully present (654/654, no gaps,
  2024-01-02→2026-08-11) and SPY **is** in a pool the engine runs (`INDEX_POOL` in `universe.py`,
  part of `live_scanner.DEFAULT_SYMBOLS` and `archive_1m.ALL_SYMS`). It is **not** in
  `backtest_week.py`'s `SYMBOLS` (explicitly removed, see §1 caveat). So "zero SPY trades" is real
  but is a `backtest_week.py`-specific pool exclusion, not a data or live-scanner-pool problem.
- **"ACHR reported as 0 days in data_archive."** Not true today — ACHR has 653/653 days, full
  range, no gaps. Stale finding, same backfill event likely fixed it (T3's report doesn't list ACHR
  by name, so this may have been fixed in an earlier or separate pass; either way it is fully
  covered now).
- **"SPCX and HTZ questionable coverage."** SPCX: real issue — a 47-trading-day gap
  2026-04-06→2026-06-12, otherwise full range. HTZ: **not in `data_archive` at all** — no directory
  exists for HTZ, and HTZ is not in any pool definition either (see §3).

## 3. Pool membership

Single source of truth is `universe.py` (docstring dated 2026-08-11):

- **MAJOR_15** (equity): NVDA, TSLA, AAPL, SPCX, MSFT, MU, INTC, PLTR, AMZN, META, AMD, GOOGL, ACHR, NFLX, ORCL
- **INDEX_POOL**: QQQ, SPY, IWM
- **OTHER_POOL**: GOOG, SOFI, COIN, HOOD, IREN, AVGO, UBER, BABA, CRM, TSM, MARA
- **ALL_SYMS** = the above 29, and this is exactly `live_scanner.DEFAULT_SYMBOLS` (`live_scanner.py:51-52` imports `MAJOR_15, INDEX_POOL, OTHER_POOL` directly from `universe.py`).

Consumers checked:

| Script | Pool used | Matches `universe.py` ALL_SYMS? |
|---|---|---|
| `live_scanner.py` | `MAJOR_15 + INDEX_POOL + OTHER_POOL` (imported directly) | yes, by construction |
| `archive_1m.py` | `from universe import ALL_SYMS` | yes, exact match |
| `build_corpus_instances.py` | `set(ALL_SYMS) \| {"ARM", "QCOM"}` | **no — adds ARM and QCOM**, which `live_scanner`/`archive_1m` never scan or bank live bars for. Both have weak archives (ARM stops 2026-06-15; QCOM has 272-trading-day gaps and stops 2026-06-12), consistent with them being outside the symbols `archive_1m.py` refreshes daily. |
| `backtest_week.py` | Own hardcoded `CORE_SYMBOLS + EXPERIMENTAL_SYMBOLS` (24 symbols) | **no.** Missing from `universe.py`'s 29 vs `backtest_week`'s 24: **SPCX, ACHR, SPY, IWM, GOOG** (5 symbols in the pool but never backtested by this script). `backtest_week.py` also uses `GOOGL` only, never `GOOG` — consistent, since `GOOG` is a separate (broken) archive entry. |
| `signal_runner.py` | No hardcoded symbol list — `SignalRunner` takes whatever candles/symbol it's called with (used by both `live_scanner.py` and, per `engine_recall.md`'s documented method, a direct `data_archive` bar-by-bar replay). It does not itself gate on a pool. | n/a |

**Disagreement confirmed, matching the ticket's prior finding that `archive_1m` and
`build_corpus_instances` carry symbols `live_scanner` doesn't** — except in this repo's current
state it's `build_corpus_instances.py` (not `archive_1m.py`, which now matches `live_scanner`
exactly) that diverges, by adding **ARM** and **QCOM**. Separately, `backtest_week.py` diverges the
other way — it's *missing* SPCX, ACHR, SPY, IWM, GOOG relative to `universe.py`.

**Symbols in NO pool at all** (checked against `universe.py` ALL_SYMS ∪ `build_corpus_instances`'s
extra ARM/QCOM ∪ `backtest_week.SYMBOLS` — i.e. not eligible under *any* of the four definitions):
- **HTZ** — not in any pool definition, and not in `data_archive` either (both a and b apply — moot since it's not part of Austin's graded set, but matches the ticket's flagged concern).
- No symbol Austin actually graded (QQQ, SPY, TSLA) is excluded from every pool — QQQ and TSLA are in all four; SPY is in three of four (missing only from `backtest_week.SYMBOLS`, see §1).

## 4. Backfill list

**For Austin's actual 120 graded days: none needed.** QQQ, SPY, and TSLA are already fully covered
with zero gaps across the entire graded window (2026-05-14→2026-08-10) and well beyond it
(archive runs 2024-01-02→2026-08-11/13 for all three). The archive-coverage backfill this ticket
was worried about already happened (`research/t3_archive_coverage.md`, 2026-08-10) and, for these
three symbols specifically, fully closed the gap.

If Austin's grading later expands beyond QQQ/SPY/TSLA into the rest of the pool, these ranges would
need fetching first:

| Symbol | Range to backfill | Why |
|---|---|---|
| GOOG | 2024-01-02→2025-04-03, and fill the 44/124/50-trading-day holes between 2025-04-04 and 2026-02-23, and 2026-02-24→present | Only 4 files exist total; unusable |
| QCOM | 2024-01-02→2025-04-02, 2025-04-12→2026-05-13, 2026-06-05→2026-06-11, 2026-06-13→present | Only 21 files exist total; unusable |
| SPCX | 2026-04-06→2026-06-12 | 47-trading-day hole in an otherwise-complete archive |
| MARA | five gaps, largest 2024-12-17→2025-04-02 | Sparse early history |
| SMCI | four gaps, largest 2024-06-20→2025-05-06 | Sparse early history |
| SOFI, TSM, UBER, BABA, CRM | pre-inception gaps (each starts partway through 2024/2025) | Archive starts after symbol's first graded-eligible date, if ever graded |
| ARM, QCOM | full history if `build_corpus_instances.py`'s extra pool members are ever meant to run live | Currently outside `live_scanner`/`archive_1m`'s daily refresh entirely |
| HTZ | entire history | Not archived, not pooled anywhere — would need both a pool decision and a backfill |

## 5. Headline

**Of the 120 days Austin graded, 0 are missing bars and 0 fail the strict "not in any pool"
test — so on the numbers as defined, up to 100% (all ~104 days the engine didn't fire) is a
genuine detection question, not a coverage one; the only asterisk is SPY (30/120 = 25% of the
set), which is fully covered and in the live-scanner pool but is explicitly excluded from
`backtest_week.py`'s own symbol list, so if "zero SPY trades" was measured against that script
specifically, the confirmed-detection floor is 90/120 (75%) rather than 120/120.**
