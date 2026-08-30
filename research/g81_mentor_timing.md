# When a mentor traded, what did OMEN do on the same day

Measured 2026-08-30. Script: `research/g81_mentor_timing.py`. Full per-row output:
`research/g81_mentor_timing.json` (2,597 rows).

Austin, 2026-08-29: *"We need to use Scarface and J Dub because you said one candle rule is
not firing as the earliest best possible entry."*

Input: `research/corpus_sf/pooled_trades.jsonl`, 3,547 deduplicated mentor trade instances
(Scarface, jdub, futures alerts, written reviews, posted gains — already mined and pooled,
not re-derived here; see `research/corpus_sf/pool_report.md`). These are **mentor
judgements, not Austin's**. Nothing here touches an Austin mark file, and nothing here
becomes a rule — a mentor liking a trade is evidence about timing, never a rule Austin has
stated.

The engine replay runs through the real router: `research/t4_engine_recall.CaptureRunner`
delegates to `signal_runner.SignalRunner._route`, checked before anything is measured
(`assert_real_router()`), the same guard `research/g81_marks30_score.py` uses.

---

## 1. The join, reported honestly

| stage | rows | symbol-days |
|---|---:|---:|
| pooled mentor trade instances | 3,547 | — |
| weekend dates dropped | −79 | — |
| on a symbol in `universe.py` | 2,669 | 2,253 |
| that symbol-day has archived bars | **2,597** | **2,183** |
| — of those, mentor posted inside 09:30–11:00 ET | 1,144 | — |
| — posted outside that window (or no timestamp) | 1,453 | — |

**Join yield: 2,597 of 3,547 mentor trade instances (73.2%) land on a session OMEN can
replay.** The loss is almost entirely the universe filter (799 instances, mostly NQ/ES
futures and small-cap names OMEN never covers) — the archive-coverage loss on top of that is
small, 70 symbol-days out of 2,253.

Only 44% of the joined rows were posted inside the 09:30–11:00 window OMEN operates in.
The rest are mid-day management, recap, or after-hours posts about a trade that may have
started in the window — they still tell you what OMEN did on that symbol-day, just not at a
comparable minute. Sections 3 and 6 below use only the in-window subset for timing; section
2 and 5 use the full joined set.

---

## 2. Did OMEN fire, did it trade

Of the 2,597 joined rows, 1,962 name a direction (long/short); 635 are watch-style posts
with no stated side.

| | count | of 1,962 with a stated side |
|---|---:|---:|
| OMEN fired *something* that symbol-day, any side | 1,219 | — |
| OMEN booked an entry that symbol-day, any side | 1,100 | — |
| OMEN fired on the **same side** the mentor traded | 594 | 30.3% |
| OMEN booked on the **same side** | 538 | 27.4% |
| OMEN silent on that side entirely | 1,368 | 69.7% |

Restricted to the 849 rows posted inside 09:30–11:00 (a fair same-window comparison): OMEN
fired same-side on 295 (34.7%) and booked on 281 (33.1%). **On roughly two of every three
symbol-days a mentor traded inside the window, OMEN produced nothing on that side.** That is
a recall number, not a quality number — it says nothing about whether OMEN was right to sit
out; it only says the two are picking different days most of the time.

---

## 3. The direct answer: is OMEN earlier or later than the mentor's post

Restricted to the 849 same-symbol-same-side rows posted 09:30–11:00. Signed minutes, OMEN's
minute minus the mentor's Discord **post** minute (positive = OMEN later):

| | n | median | mean | earlier | exact | later | within 5 min | within 10 min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| first fired signal | 295 | **0** | −1.75 | 146 | 4 | 145 | 66 (22%) | 113 (38%) |
| first booked entry | 281 | **0** | −2.80 | 137 | 4 | 137 | 63 (22%) | 107 (38%) |
| range | | | | | | | | −83 to +78 |

Restricted further to only high/medium-confidence mentor rows (the cleaner 68% of the pool,
per `pool_report.md`) the picture holds: 245 rows, median +1, mean −0.19.

**Against the mentor's post time, OMEN is not systematically early or late — it's a
near-even split (146 earlier / 145 later on first fire) with a median of exactly zero
minutes.** That is a different answer than `research/g81_marks30_score.md` found against
Austin's own stated entry minute (median +24 minutes late, OMEN behind). The two numbers
are not in conflict, because **a Discord post time is not an entry time** — see section 6.
If a post systematically comes some minutes *after* a trader actually enters, then OMEN
landing even with the *post* means OMEN is landing late relative to the *entry*, consistent
with the Austin-minute finding. This dataset cannot fully resolve that because so few
mentor rows carry a real fill price (next section) — but it does not contradict the earlier
finding, and the honest read is that "even with the post" is the more optimistic of the two
numbers this project has, not the more reliable one.

---

## 4. Entry price: OMEN vs. the mentor's stated fill

The pool's `entry` field is unreliable on its face — it mixes underlying stock prices with
option premiums and strikes parsed from the same sentence (`"AMD Puts 870 @2.5"` parses
`entry: 2.5`, the $2.50 premium, not AMD's price). Of the 29 stated-direction, joined rows
carrying any price, only **3** survive a plausibility filter (the price sits inside that
day's actual RTH range, padded 50%):

| symbol / day | mentor's price | OMEN's price | OMEN's minute | diff |
|---|---:|---:|---:|---:|
| TSLA 2024-11-22 | 342.20 | 341.96 | 10:05 | −$0.24 (−0.07%) |
| AMD 2025-08-20 | 163.10 | 160.12 | 10:16 | −$2.98 (−1.83%) |
| SPY 2026-03-30 | 636.00 | 636.27 | 10:17 | +$0.27 (+0.04%) |

**n = 3. This is not a result — it is too small to say whether OMEN enters at a worse
price, and reporting a mean or a rate off three rows would overclaim.** It is included
because the task asked for it and the honest answer is "the corpus does not support this
comparison," not silence.

---

## 5. Directional agreement — the bug-smell number

Of the 1,962 rows with a stated mentor direction, 907 are symbol-days where OMEN fired
*something*, either side:

| | count | % of the 907 with any OMEN signal |
|---|---:|---:|
| OMEN's only signal(s) matched the mentor's side | 531 | 58.5% |
| **OMEN's only signal(s) were the opposite side** | **313** | **34.5%** |
| OMEN fired both sides that day | 63 | 6.9% |
| (OMEN silent both sides — excluded from this %) | 1,055 | — |

**On a third of the symbol-days where OMEN fired and a mentor also traded, the only thing
OMEN fired was the opposite side of the mentor's trade.** This is concentrated in the
highest-volume names roughly in proportion to their share of the pool (TSLA 72, NVDA 60,
AMD 44, QQQ 38, SPY 21 of the 313) — it is not one symbol misbehaving, it is spread evenly
across the book.

**What this number is not:** proof OMEN is wrong. Both sides can be legitimately in play on
the same symbol-day (a fade after a failed break, a reversal), and a mentor's single post
is one trader's read, not ground truth. What it is: a concrete, checkable count worth
looking at chart-by-chart before trusting it either way — 313 cases is enough to sample and
small enough to read by hand.

---

## 6. Quantifying the Discord-post lag directly

For the 3 rows above with a plausible underlying price, the RTH minute whose close was
closest to that price was located, independent of the post time:

| symbol / day | stated price | post time | closest-price minute | post minus match |
|---|---:|---|---|---:|
| TSLA 2024-11-22 | 342.20 | 9:58 | 9:59 | **−1 min** (price gap $0.19) |
| AMD 2025-08-20 | 163.10 | 10:37 | 12:02 | −85 min (price gap $0.001) |
| SPY 2026-03-30 | 636.00 | 10:05 | 12:22 | −137 min (price gap $0.00) |

The TSLA row is the one clean read: the post landed one minute from the moment the price
was actually at the stated level — a real, near-zero lag. The other two are not trustworthy
lag measurements: their "nearest price" match is a coincidental midday revisit of a level
the stock also touched near the actual post time, which a nearest-price search cannot tell
apart from the real entry when a level gets retested hours later. **n = 3, one interpretable
row. This does not establish a lag number for the corpus** — it demonstrates the method
(and its failure mode) on the only rows precise enough to try it, and confirms the
qualitative point stated up front: a post time is a proxy, not a fill, and this dataset is
too thin on stated prices to convert that into a number worth publishing.

---

## Caveats, stated plainly

- **The `entry` field in the mentor pool is mostly option premiums, not stock prices.**
  Only 3 of 1,962 direction-bearing joined rows survived a plausibility check. Sections 4
  and 6 are demonstrations of method on a token sample, not results.
- **A Discord post time is not an entry time.** Every timing number in section 3 compares
  OMEN against the *post* minute because that is the only timestamp this corpus has for
  most rows — not because it is assumed correct. Section 6 shows the one case where the gap
  could be checked directly was small (1 minute); the project has no basis to claim that
  holds generally.
- **The opposite-side count (34.5%, section 5) is not scored against outcomes.** It says
  OMEN and a mentor disagreed on direction; it does not say which of them was right.
- **This is not a recall or a money measurement.** Sections 2 and 3 describe how often and
  when OMEN and mentors land on the same symbol-day — they do not say whether either side
  made money, and are not a substitute for `research/t60_baseline.py` or `backtest_2y.py`.
- **Confidence-filtering the mentor rows (high/medium only, 68% of the pool) does not move
  the section 3 result** — median +1 minute vs. median 0, both effectively even. This is
  the one robustness check performed; parser-precision limits documented in
  `research/corpus_sf/pool_report.md` (8.7% outcome conflicts on multi-row instances) apply
  to everything else here as they did there.
- **No Austin mark file was opened for writing.** `research/marks_pool.py`,
  `research/austin_marks_v7.jsonl` and every corpus named in the repo's mark-file rules were
  left untouched; this file draws only on `research/corpus_sf/pooled_trades.jsonl` and the
  archived bars.

---

## ⚠ REFUTED by the verify pass, 2026-08-30 — do not quote §5 or the "median 0" framing

An Opus verifier rebuilt the whole join from scratch in `research/g81_verify_2.py`, never importing
this script. **Every published number reproduces to the digit** once the entry fill is pinned to the
one in force at run time (`ENTRY_FILL=published`). The arithmetic is sound. Two things in the
headline are not.

### 1. The unit is wrong on the most quotable number, and fixing it moves it by a third

The headline says *"on the 313 symbol-days (34.5% of days both fired)"*. **Those are rows, not
days.** The mentor pool holds 3,547 rows across only 2,915 distinct symbol-days; the 1,962
direction-bearing joined rows sit on 1,696 distinct symbol-days.

| read | opposite-side-only | denominator | rate |
|---|---:|---:|---:|
| as published (rows) | 313 | 907 | 34.5% |
| **deduplicated to symbol-days** | **201** | **783** | **25.7%** |
| strictest honest (posted in window, mentors not on both sides) | 70 | 299 | **23.4%** |

Worse: **111 of the 313** sit on a symbol-day where the mentor pool itself carries *both*
directions — OMEN matched one mentor's side and is "opposite" only to a *different* mentor's post.
And **195 of the 313 (62%)** are posts made outside 09:30–11:00, which §1 of this report itself
declares not comparable.

### 2. "Median 0, looks even" is a null result sold as a finding

Both clocks are truncated into the same 90-minute box (OMEN cannot fire past 11:00; the subset is
restricted to posts inside 09:30–11:00). Shuffling the mentor post minutes against the OMEN minutes
2,000 times, **the null gives median 0 (95% band −3 to +2) and mean exactly −1.75** — identical to
the observed. The "near-even split, median exactly zero" is forced by construction and carries no
information about co-timing.

**The one statistic that actually beats its null is never reported: 38.3% land within ten minutes
against a null of 27.5% (95% band 22.7–32.5%).** That is the real, modest signal, and it is buried
in a column.

### 3. Reproducibility break — pin the fill

This script no longer produces the published numbers on this tree. A concurrent change to the entry
fill (new `entry_fill.py`, rewritten `signal_runner.fill_price`, edited `backtest_week.py`, all
written 10:29–10:31 after the 10:27 JSON) moves same-side fire **30.3% → 40.0%** and in-window
**34.7% → 44.5%**. Everything reproduces under `ENTRY_FILL=published`. **A report that does not name
its fill cannot be re-run** — the same lesson as the `DIRECTION.md` banner.

Encouragingly the opposite-side rate is stable across both engines (25.7% vs 25.5% on days), so
finding 1 is not an artifact of the fill.

**Clean on everything else:** no look-ahead in any headline number (`run_day` feeds a strict prefix,
`simulate_day` walks bar by bar, the engine minute is its own earliest same-side fire and is not
picked with the mentor's clock); no R number quoted inside ±1.5799R as a winner; no rule applied.
