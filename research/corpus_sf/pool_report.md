# Pooled mentor trade instances

Built by `research/corpus_sf/pool_trades.py` on 2026-08-29 from the 15 mined Discord corpora in `research/corpus_sf/`. These are SCARFACE's and the other mentors' judgements -- **not Austin's marks**. No Austin mark corpus was opened for writing; `marked_card_ids()` is used read-only.

## 1. What went in

A row is a **trade instance** when it names a symbol AND asserts a fact about a position: a direction, an outcome, an entry fill, an R-multiple, a dollar P&L, or one of the two OMEN setups (`break_retest` / `one_candle` / `br_ocr`). A row naming only a level or a target is a **watch call**: counted, not pooled.

| source | rows | trade-shaped | watch-only | no symbol | no date |
|---|---:|---:|---:|---:|---:|
| `scarface_alerts.jsonl` | 2955 | 1980 | 818 | 0 | 0 |
| `jdub_alerts.jsonl` | 3798 | 195 | 1345 | 25 | 0 |
| `futures_alerts.jsonl` | 2252 | 785 | 360 | 1107 | 0 |
| `reviews_options.jsonl` | 55 | 27 | 0 | 0 | 0 |
| `reviews_futures.jsonl` | 114 | 65 | 3 | 31 | 0 |
| `reviews_jdub.jsonl` | 37 | 0 | 0 | 37 | 0 |
| `pre_market_live.jsonl` | 35 | 11 | 10 | 10 | 0 |
| `gains.jsonl` | 492 | 492 | 0 | 0 | 0 |
| `misc.jsonl` | 3634 | 2763 | 871 | 0 | 0 |
| **total** | **13372** | **6318** | **3407** | **1210** | **0** |

Excluded wholesale as rule / index / manifest corpora (no trade instances by construction): `questions.jsonl`, `general_chat.jsonl`, `tips.jsonl`, `maxims_futures.jsonl`, `backtesting.jsonl`, `premarket_charts.jsonl`, `live_sessions.jsonl`.

## 2. Dedup

Key = (symbol, trading date, direction, entry within 0.25%). Entry is stated on almost nothing in this data, so in practice the key collapses to symbol-day-direction; that is exactly what folds *alerted -> reviewed -> posted as a gain* into one instance. Null-direction clusters are absorbed into the unique directional cluster for the same symbol-day when exactly one exists (562 absorptions). The richest row wins the merge; any field the winner lacks is backfilled from its cluster-mates and recorded in `fields_backfilled`.

- input trade-shaped rows: **6318**
- distinct trade instances after dedup: **3547** (compression 1.78x)
- instances built from >1 raw row: **1197**
- instances corroborated by >1 SOURCE CHANNEL: **522**
- rows-per-instance: 1 rows x2350, 2 rows x613, 3 rows x253, 4 rows x111, 5 rows x71, 6 rows x48, 7 rows x34, 8 rows x23, 9 rows x13, 10 rows x14, 11 rows x7, 12 rows x3, 13 rows x1, 14 rows x1, 15 rows x3, 16 rows x2
- sources-per-instance: 1 src x3025, 2 src x473, 3 src x45, 4 src x4

**The key merges across people, deliberately.** 755 instances pool rows from more than one author -- three members each posting a TSLA long on the same morning become one instance, because the unit that can be scored against an Austin grade is the symbol-day-side, not the person. If you want per-person trades instead, split on `authors`: that yields **4704** (symbol, date, direction, author) tuples. `n_rows`, `n_authors` and `authors` preserve the multiplicity either way.

Cross-channel agreement (instances two or more channels both saw):

| source combination | instances |
|---|---:|
| misc.jsonl + scarface_alerts.jsonl | 236 |
| gains.jsonl + misc.jsonl | 96 |
| gains.jsonl + scarface_alerts.jsonl | 43 |
| jdub_alerts.jsonl + misc.jsonl | 35 |
| gains.jsonl + misc.jsonl + scarface_alerts.jsonl | 24 |
| futures_alerts.jsonl + reviews_futures.jsonl | 20 |
| futures_alerts.jsonl + misc.jsonl | 10 |
| jdub_alerts.jsonl + scarface_alerts.jsonl | 9 |
| jdub_alerts.jsonl + misc.jsonl + scarface_alerts.jsonl | 9 |
| gains.jsonl + jdub_alerts.jsonl | 7 |
| gains.jsonl + jdub_alerts.jsonl + misc.jsonl | 7 |
| reviews_options.jsonl + scarface_alerts.jsonl | 4 |
| misc.jsonl + reviews_options.jsonl | 4 |
| futures_alerts.jsonl + gains.jsonl | 3 |
| gains.jsonl + reviews_options.jsonl | 3 |

Two measured limits of the merge, both reported per-row so a consumer can filter:

- **Outcome conflict.** 104 of the 1197 multi-row instances (8.7%) contain member rows that disagree on the result -- one person scaled out green while another was stopped, or a scalp and a runner on the same level resolved differently. The richest row's outcome is kept and `outcome_conflict: true` plus the full `outcome_votes` tally is written on the row.
- **Non-weekday dates.** 79 instances sit on a Saturday or Sunday -- weekend swing-idea posts and review write-ups whose post date is not a session date. Filter them before joining to bars.

## 3. Overlap with Austin's judged symbol-days

Enumerator: `research/build_deck.py::marked_card_ids()` (read-only). Overlap is the point: it is where a mentor's call and Austin's grade sit on the same chart, so Scarface can be scored against him.

- symbol-days Austin has judged: **1147**
- distinct symbol-days in the pool: **2915**
- **overlap: 220 symbol-days** (7.5% of the pool's days, 19.2% of Austin's)
- pooled trade instances landing on a day Austin judged: **270**

The 220 is capped by two things that are not parser quality. Austin's corpus reaches back before this Discord export starts and covers symbols the mentors never post: only **1107** of his 1147 judged days fall inside 2024-04-02..2026-08-21, and only **1039** of those are on a symbol the pool covers at all. Against that reachable denominator the overlap is **21.2%**.

Top symbols in the overlap: TSLA 66, QQQ 53, NVDA 36, SPY 34, AMD 19, AAPL 18, PLTR 13, AMZN 7, MSFT 5, META 4, MU 4, ORCL 3.

Overlap instances carrying a stated outcome: **93** (win 51, loss 35, be 7).
Overlap instances inside 09:30-11:00 ET: **125**.

Per-channel contribution to the overlap set:

| channel | overlap instances |
|---|---:|
| `misc.jsonl` | 155 |
| `scarface_alerts.jsonl` | 106 |
| `gains.jsonl` | 47 |
| `jdub_alerts.jsonl` | 22 |
| `pre_market_live.jsonl` | 1 |

## 4. The pool

- distinct instances: **3547**
- date range: **2024-04-02 .. 2026-08-21** (641 distinct trading dates)
- distinct symbols: **70**
- on a symbol in `universe.py` ALL_SYMS: **2741** (77.3%)
- **inside 09:30-11:00 ET AND on a universe symbol: 1180** (33.3% of the pool)
  - of those, on a symbol-day Austin judged: **125**

Symbol distribution:

| symbol | instances | in universe | in 09:30-11:00 |
|---|---:|:---:|---:|
| TSLA | 490 | yes | 212 |
| NQ | 432 | - | 40 |
| NVDA | 425 | yes | 187 |
| QQQ | 350 | yes | 149 |
| SPY | 327 | yes | 138 |
| AMD | 264 | yes | 128 |
| AAPL | 250 | yes | 129 |
| ES | 231 | - | 15 |
| AMZN | 122 | yes | 39 |
| PLTR | 103 | yes | 38 |
| META | 72 | yes | 24 |
| MSFT | 64 | yes | 24 |
| GOOGL | 56 | yes | 25 |
| MU | 47 | yes | 28 |
| INTC | 39 | yes | 21 |
| GOOG | 37 | yes | 9 |
| HOOD | 28 | yes | 16 |
| AVGO | 17 | yes | 4 |
| SPX | 15 | - | 5 |
| SNDK | 15 | - | 10 |
| MNQ | 11 | - | 2 |
| NFLX | 9 | yes | 0 |
| ORCL | 9 | yes | 2 |
| COIN | 8 | yes | 0 |
| YM | 8 | - | 0 |
| SPCX | 8 | yes | 3 |
| MES | 7 | - | 0 |
| COST | 7 | - | 1 |
| F | 7 | - | 3 |
| IREN | 7 | yes | 2 |
| SMCI | 5 | - | 1 |
| MSTR | 5 | - | 0 |
| DELL | 4 | - | 1 |
| LULU | 4 | - | 0 |
| TSLL | 4 | - | 1 |
| UNH | 4 | - | 1 |
| MRVL | 4 | - | 1 |
| APP | 3 | - | 1 |
| TGT | 3 | - | 0 |
| BABA | 3 | yes | 0 |
| GC | 3 | - | 1 |
| TSM | 2 | yes | 0 |
| NKE | 2 | - | 0 |
| RGTI | 2 | - | 0 |
| HIMS | 2 | - | 0 |
| IWM | 2 | yes | 1 |
| QCOM | 2 | - | 1 |
| ARM | 2 | - | 0 |
| RKLB | 2 | - | 0 |
| OKLO | 2 | - | 0 |
| WMT | 2 | - | 1 |
| SMH | 2 | - | 0 |
| ABNB | 1 | - | 0 |
| MCD | 1 | - | 0 |
| RIVN | 1 | - | 0 |
| BA | 1 | - | 0 |
| SBUX | 1 | - | 1 |
| GME | 1 | - | 0 |
| ASTS | 1 | - | 0 |
| MARA | 1 | yes | 0 |
| BTC | 1 | - | 0 |
| RTY | 1 | - | 0 |
| CRCL | 1 | - | 0 |
| SHOP | 1 | - | 0 |
| SNOW | 1 | - | 1 |
| SOFI | 1 | yes | 1 |
| JPM | 1 | - | 1 |
| CRWV | 1 | - | 0 |
| DIS | 1 | - | 0 |
| DDOG | 1 | - | 0 |

By year: 2024 687, 2025 1954, 2026 906

Field fill on the pooled set: direction 2795, setup 1953, level_name 1658, level_price 522, entry 49, stop 19, target 411, outcome 980, r_multiple 76, pnl_usd 54, image_urls 1668

Outcome: win 593, loss 340, be 47. Direction: long 1643, short 1152. Setup: break_retest 1186, other 695, one_candle 54, br_ocr 18.

## 5. Caveats

- Entry prices are absent from nearly all of this data (mentors name levels and option strikes, not underlying fills), so the 0.25% arm of the dedup key almost never fires. An instance is therefore *a symbol-day-side*, not a single fill: a mentor who traded TSLA long twice in one morning appears once, with `n_rows` recording the multiplicity.
- Outcomes are self-reports, never measured fills, and the review channels are survivorship-skewed toward winners.
- Futures rows (NQ/ES/YM/RTY) are pooled but are not universe symbols and can never overlap Austin's marks.
- Parser precision on the underlying corpora ranges 70-100% by channel; `confidence` is carried through from the winning row. Filter to `confidence in {high, medium}` for a cleaner set (2495 instances).
- 3407 watch-only rows (symbol + level, no position asserted) were held back. They are the natural extension if the scoring set needs more symbol-day coverage.

