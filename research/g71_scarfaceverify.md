# G7.1 / scarfaceverify — REFUTED: the review channels do carry text trade reviews

**Claim under test** (`research/g71_scarface.md` Finding 1): *"the 'trade review' channels
contain no trade reviews, only links to video recordings... Any pipeline pointed at these
files for text will return nothing."*

**Verdict: REFUTED.** The vidlink counts reproduce exactly. The inference from them does not.

Scripts: `research/g71_scarfaceverify_titles.py`, `research/g71_scarfaceverify_extract.py`,
`research/g71_scarfaceverify_yield.py`. All read-only.

## 1. The counts reproduce; the conclusion does not

`research/g71_scarfaceverify_extract.py` (independent regex set, universe-anchored tickers
from `universe.py`, 33 symbols + futures):

| channel | n | vid | date | sym | $ P&L | DATE+SYM | DATE+SYM+$ |
|---|---:|---:|---:|---:|---:|---:|---:|
| options-trade-reviews | 389 | 357 | 337 | 52 | 27 | 41 | **21** |
| futures-trade-reviews | 152 | 79 | 14 | 72 | 50 | 12 | 4 |
| scarface-trade-reviews | 267 | 264 | 260 | 253 | 248 | 250 | **239** |
| jdub-trade-reviews | 129 | 128 | 86 | 0 | 36 | 0 | 0 |

vidlink 357 / 79 / 264 / 128 matches the claim to the message. But **239 of 267
scarface-trade-reviews messages carry date + symbol + signed dollar P&L in the message
text**, next to the link. The link is a pointer; the title is the record.

## 2. The "all 4 = 1 or 2" figure is a regex artifact

`research/g71_scarface_inventory.py:19` requires `DIR = long|short|call|put|bull|bear|...`.
Scarface's title convention never states direction — `dir` is **0/267** under my
open-vocabulary regex too. A four-way conjunction one of whose terms is zero by construction
returns ~0 regardless of what the channel contains. `sym` was **253/267** and `out` **265/267**
in the prior agent's own table; those two columns already contradicted its Finding 1.

Direction is recoverable without vision: same-day join to `scarface-alerts.json`, which is
what that report's own T1/T2 tiers already do.

## 3. The cited sample row refutes the claim it was offered for

`discord_data/options-trade-reviews.json` id `1341885333280784478` is described as "a Zoom
share URL plus a passcode". Full content:

```
**February 19th Trade Review (TSLA Call + NVDA Put)**
https://us06web.zoom.us/rec/share/...
Passcode: *$40=AM3
```

Date, two symbols, two directions — in text, on line 1. The description dropped the title.

## 4. A text-only parser yields 286 symbol-days, 256 of them new

`research/g71_scarfaceverify_yield.py`, ~40 lines, no vision, no transcripts, on
`scarface-trade-reviews.json` alone:

- 267 msgs → **288 (date, symbol) trade rows → 286 distinct symbol-days**, 2024-04-09 .. 2026-01-14
- unresolved: 28/267 (10.5%), mostly untitled early posts and lowercase tickers (`$500 meta`)
- symbols: TSLA 114, NVDA 66, AAPL 46, AMD 30, GOOGL 6, AMZN 5, SPY 5, PLTR 5, QQQ 4, META 3, HOOD 2
- vs `build_deck.marked_card_ids()` (1,147): **30 overlap, 256 NEW**

`options-trade-reviews` adds 21 rows carrying the **setup name in text**, in OMEN's own
taxonomy: `$4.2k Profit on NVDA (05/30/25) | PWH Break and Retest`; `$1.3k Profit on QQQ
(06/02/25) | Reversal PDH (Break and Retest)`; `Profit: $2k on SPY (06/23/25) VWAP (Break
and Retest)`; `Profit $530 on QQQ (06/11/25) | Reversed 1st Candle Low (BNR)`.
`futures-trade-reviews` is only **52% links** — 73 non-link messages, 50 with a $ P&L
(`Trade Review on NQ 3/13/25 ... Lost $1760 yesterday. Made $7060 today.`).

## 5. The report contradicts itself

Its Finding 5 mines **1,309 video ids and post dates out of these same channels' text** and
joins 662 transcripts with them. That is a text pipeline, pointed at these files, returning
662 rows. "Returns nothing" cannot stand beside it.

## 6. What survives

The **level** is genuinely not in the review-channel text (Finding 2 stands, verified: 0/267
scarface and 0/152 futures messages match `retest|reclaim|pdh|pdl|vwap|one candle`). Vision
is still required for the entry level.

**Real hazard the claim masks:** the parsed P&L is self-reported and shows an **84.0% win
rate** (242W/46L). It is survivorship-curated and must never be used as an outcome label —
replay bars through `stop_rule.stop_fill_price()`. That is a label-quality problem, not an
absence-of-text problem, and burying it under "there is no text" is how it would have been
missed.

## 7. Scope notes

- No book dependency. This claim is about `discord_data/*.json`; the 2,595 vs 1,017 post-T0
  book question does not apply. The report's *separate* 46.5% recall claim (Section 3, via
  `research.t4_engine_recall.run_day`) does have a book dependency and was not tested here.
- No look-ahead in the extraction itself: post timestamp ≥ trade date in every parsed row.
- `discord_data/scarface-trade-reviews.json` and `jdub-trade-reviews.json` are stale scrapes
  (mtime 2026-08-21, last msg 2026-04-08 / 2026-06-10) — Scarface moved reviews to a second
  channel 2026-02. A re-scrape adds ~7 more months.

## Correction to `research/g71_scarface.md` Finding 1

Replace with: *the review channels carry the video, the date, the symbol and the
self-reported P&L in text, but not the entry level. A text-only parser yields 286 symbol-days
(256 new). The claimed P&L is 84% wins and is survivorship-curated — use it as a
symbol-day recall label, never as an outcome.*

---

# REFUTED (2) — the 53.5% "OMEN silent on Scarface days" is the engine's base rate

**Claim under test** (`research/g71_scarface.md` §3 / §6): *"OMEN is silent on 53.5% of days
a professional actually traded in the 09:30–11:00 window — the largest engine-independent
recall signal in the repo... an independent corroboration of the recall wound at 6x the
sample size."*

Scripts: `research/g71_scarfaceverify_recall.py` (re-run + per-day detail),
`research/g71_scarfaceverify_control.py` (the missing control arm).
Detail dump: `research/_g71_scarfaceverify_recall.json`.

## The arithmetic reproduces exactly. The interpretation does not survive a control.

Re-running `research/t4_engine_recall.run_day` over the same 200 rows reproduces all four
published numbers to the digit:

| | claimed | reproduced |
|---|---:|---:|
| fired ≥ once | 93 (46.5%) | **93 (46.5%)** |
| "SILENT" | 107 (53.5%) | **107 (53.5%)** |
| fired in Scarface's direction | 72 (36.0%) | **72 (36.0%)** |
| fired only opposite | 21 (10.5%) | **21 (10.5%)** |

## Killer 1 — random days give the same number

`g71_scarfaceverify_control.py` draws 200 in-universe symbol-days matched to the target's
**symbol mix** and **date range** (2024-04-11…2025-09-18), excluding every day any Discord
channel mentions, and replays them through the same `run_day`:

| arm | n | day-level fired | any signal |
|---|---:|---:|---:|
| Scarface T1+T2 (their slice) | 200 | **93 = 46.5%** | 199 = 99.5% |
| random control, seed A | 200 | **93 = 46.5%** | 196 = 98.0% |
| random control, seed B | 200 | **95 = 47.5%** | 198 = 99.0% |

The Scarface label carries **zero** information about whether OMEN fires. 53.5% is OMEN's
unconditional non-fire rate on any in-universe day in that window, not a recall miss.

The same control demolishes the corroboration claim in the other direction. The 52.9% in
`DIRECTION.md` is the *same* day-level metric (`research/t0_heldout_recall.py:92-94`,
`fired(r) = bool(d.get("fired"))`), and that rig already carries its control:

- fired on his 34 **S** days: 18 = **52.9%**
- fired on his 66 **none** days: 33 = **50.0%** (`research/t0_heldout_recall.json`)
- fired on 200 **random** days: **46.5% / 47.5%**

46.5% is *below* both of Austin's arms. It corroborates nothing; it sits inside the noise
band of a coin flip.

## Killer 2 — "silent" is the wrong word, and it inverts the T1 conflict

`run_day` returns `(entries, all_sigs, raw_sigs)`. `g71_scarface_recall.py:27` binds only
`entries` — the **fired** list — and discards `all_sigs` and `raw_sigs`. So its "SILENT"
means *the router refused to fire*, a filter outcome, not *the engine produced nothing*.

On the same 200 days the engine emits a deduped signal on **199 (99.5%)**, and a signal in
Scarface's own direction on **175 (87.5%)**. Examples from the "silent" bucket:
`NVDA_2024-04-11` n_sig=9 (both directions), `META_2024-04-16` n_sig=1 (put, his direction).

This is the opposite of the report's §3 conclusion. T1's *"the engine is never silent on his
S days, it reaches the setup and grades it X"* is **confirmed at 99.5%** by this data, not
contradicted. There is no "selection bias in the graded deck" to investigate; the two
measurements disagreed only because one of them renamed "did not fire" to "silent."

## Killer 3 — the 200 is the oldest 55% of the corpus, and the full sample is 50.1%

`g71_scarface_recall.py:16-17` sorts by day then truncates to `LIMIT`, so the tested set is
the **chronologically earliest** 200 of 365, ending 2025-09-18 — a year of the corpus is
excluded. All 365:

| set | n | fired | "silent" | same-dir |
|---|---:|---:|---:|---:|
| earliest 200 (published) | 200 | 46.5% | **53.5%** | 36.0% |
| all 365 | 365 | 49.9% | **50.1%** | 38.4% |
| T1 only (level in context) | 54 | 42.6% | 57.4% | — |
| T2 only (chart, no level) | 311 | 51.1% | 48.9% | — |

The headline is a slice artifact; the sample-wide figure is 50.1%, and no reason for the
truncation is stated.

## Killer 4 — "days a professional actually traded" is not what the label means

`research/g71_scarface_candidates.py:28` compiles an `ENTRY` regex (`took|entered|bought|
N calls|filled|…`) and **never uses it** — `build()` never references `ENTRY`. Nothing in
the tiering requires the message to indicate a trade was taken. A row qualifies as T2 on
*symbol mentioned in-window + an image attached + one directional word*, where
`DIRC`/`DIRP` count `reclaim|buyers|bull` vs `reject|sellers|bear` (`:41-42`). Symbol is
carried forward: a message with no ticker inherits the day's last-seen ticker
(`sym = hit[0].upper() if hit else last.get(day)`).

Applying the unused `ENTRY` regex to the 200 tested rows' own message text: only **147
(73.5%)** contain any entry verb or strike. 53 of 200 carry no textual evidence a trade
happened. The report's own `g71_scarface_validate.py` independently measures the damage —
**22.7% of T1 levels do not fall inside the day's actual range**.

## Two small ones

- `g71_scarface_recall.py:25` does `entries = entries or []`, collapsing `run_day`'s
  `None` (no archived bars → engine cannot run) into "silent". 0 of the tested 200 and 3 of
  365 hit it, so it does not move this number — but `t4_engine_recall.main()` deliberately
  separates a "testable" column for exactly this, and the derived script dropped it.
- 17 of the 200 are days Austin has already judged (`already_marked_by_austin`), so the
  sample is not fully engine-independent of the graded corpus either.

## Corrected statement

> On 200 Scarface alert-days OMEN takes an entry on 46.5% — statistically identical to the
> 46.5–47.5% it takes on 200 **random** matched days, and below the 52.9% / 50.0% it takes
> on Austin's S / none days. The Scarface label predicts nothing about engine firing, so
> this is not a recall signal. What the data does show is that the engine **emits a signal
> on 99.5% of these days, and in Scarface's own direction on 87.5%** — confirming T1: the
> failure is grading, not detection.

