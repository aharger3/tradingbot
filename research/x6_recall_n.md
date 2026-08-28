# X6 — why 160 S trades in two years when his eye sees three a week

**Script:** `research/x6_recall_n.py` (run: `python research/x6_recall_n.py --json research/_x6_out.json`).
**Commit:** `c089b26b`. **Substrate:** `research/g3_arm_ow1.json` — the shipped 2-year book,
45,193 detections / 1,017 traded, 2024-08-21..2026-08-21, 500 sessions, 28 symbols, produced by
`research/g3_onwatch_2y.py`. **Marks:** `research/build_deck.py::mark_sources` /
`marked_card_ids` — called, not reimplemented, so all 817 judged symbol-days are covered.
**Held-out:** `research/marks/probe_omen_test1_2026-08-27.jsonl`.

No mark file was written, moved or read for anything but counting.

---

## The headline

**The detector already sees Austin's rate. The gate throws 98.3% of it away.**

On his own top-10 names the engine *detects* **158.2 S setups per symbol-year** against the
**151.2** his "3 S in one week on one stock" implies — a **0.96x** match — and *trades*
**3.21** of them. That is a **47x** gap, and every unit of it sits after detection.

And his second complaint is the same fact from the other side: **the engine emits an S
detection on 112 of the 246 replayable days he refused (45.5%) and on 99 of his 207 S days
(47.8%).** A 2.3-point separation. The S label carries almost no information about whether
Austin would call the day an S, which is exactly what "too many random s categories" describes.

---

## 1. Count — the engine's S supply, and the size of the gap

His claim, read literally: 3 S per week on a top-10 name = 0.60 per symbol-day =
**151.2 per symbol-year** (252 sessions).

### The supply ladder — four things the word "S" means, one rate each

| what | n over the book | per symbol-year | vs his 151.2 |
|---|---:|---:|---|
| Austin's eye, implied | — | **151.2** | 1.0x |
| engine **detections** graded S by `downgrade.py` | 7,454 | **159.1** | **1.05x — matches** |
| …of those, **strict S** (zero downgrades tripped) | 1,005 | **21.4** | 7.1x short |
| engine **alerts** graded S | 174 | 3.7 | 40.9x short |
| engine **trades** graded S (the book) | **128** | **2.7** | **55.3x short** |

Denominator: 11,808 symbol-days replayed.

Austin said "160 trades over two years". The engine's number is **128 traded S** (12.6% of the
1,017-row book). The nearest other S figure in the book is **174 S alerts**. Neither is 160;
128 is the one that means "trades".

### The top-10 names on their own

| | symbol-days | S detected | S traded | detected /sym-yr | traded /sym-yr | gap |
|---|---:|---:|---:|---:|---:|---:|
| `CORE_SYMBOLS` (10 names) | 4,866 | 3,054 | 62 | **158.2** | **3.21** | **47.1x** |
| strict S (zero downgrades), same 10 | 4,866 | 401 | — | 20.8 | — | 7.3x |

Per name, S trades per symbol-year: TSLA 6.1 · AMD 5.2 · META 4.7 · MSFT 4.7 · PLTR 4.1 ·
NVDA 2.6 · GOOGL 2.1 · AAPL 1.0 · AMZN 1.0 · QQQ 0.5. The best symbol in the whole book is
COIN at 7.7 — still **19.6x** under his implied rate. **No symbol comes close.**

### By month, by detector

S trades per month run 1 to 12 (median 5) against 16–71 traded rows per month; the thinnest is
2025-06 with **1**. By detector: break-and-retest **105** traded from 6,404 S detections
(**1.64%**), one-candle-rule **22** from 1,049 (**2.10%**), the 84%-rule re-entry 1 from 1.

### And the mechanism that inflates the middle rung

`score = tripped − confluence`, S means `score <= 0`. So:

- **105 of the 128 S trades (82.0%)** tripped a downgrade and were promoted back to S by the
  **+1 confluence credit**. Only 23 (18.0%) tripped zero, which is Austin's literal definition.
- Same at detection scale: **6,449 of 7,454 (86.5%)** of S detections are confluence-rescued.
- The credit is not rare. **`confluence == "yes"` on 29,833 of 45,193 detections (66.0%)** —
  a consequence of G8's finding that 29,815 detections are BR+OCR co-detections. A +1 handed
  to two thirds of the population cannot discriminate; it converts "one downgrade" into S by
  default.

**So the 159/symbol-year detection rate that matches his eye is itself mostly manufactured.**
The rate built from his stated rule — zero downgrades — is 21.4/symbol-year, 7.1x short.

---

## 2. Overlap — his S set and the engine's S set barely touch

817 judged symbol-days; 240 of them Austin graded S (232 A, 53 C, 278 none; 17 rows carried a
legacy-ladder `B` and were dropped rather than folded into a tier). **207** of his 240 S days
are inside the book's window and roster, so the book can actually be asked about them.

| | n | |
|---|---:|---|
| his replayable S days | 207 | |
| engine **traded** an S on the same day | **4** | **1.9%** of his S days, 3.1% of the engine's 128 |
| engine **detected** an S on the same day | 99 | 47.8% of his S days |
| engine traded **anything at all** | 32 | 15.5% — this is the recall wound |

What the engine grades on his S days (traded rows): **C 20 · A 9 · S 4** on 32 days.
On the days he **refused**: **C 47 · A 14 · S 4** on 65 days. Identical shape.

### When it does fire, it is looking at the right thing

Over the 32 days he called S and the engine traded any grade:

| agreement | result |
|---|---|
| **setup** (BR vs OCR) | **16 / 18 = 88.9%** |
| **entry bar ±3** | **11 / 14 = 78.6%** |
| entry bar ±1 | 10 / 14 = 71.4% |
| bar delta | min 0, **median 0**, mean 5.4, max 55 |

Ten of the fourteen are an exact bar match. The two setup misses are
`ORCL_2025-11-03` (his OCR, engine BR, 13 bars apart) and `TSM_2026-02-23` (his BR, engine OCR,
55 bars apart).

Restricted to the 4 days where *both* said S, setup agreement is 4/4 and bar agreement 1/1 —
true, and **n=4 is not a measurement**; the 32-day row above is the one to read.

**The disagreement is not about setup and it is not about timing. It is about which days
get traded at all, and about what grade goes on them once they are.**

---

## 3. The "random S" — what the false ones have in common

At trade level this cannot be answered: only **8** of the 128 S trades land on a day Austin has
judged (4 on S days, 4 on refused days) and **107 (83.6%) are on days he has never seen**. A
feature table on n=4 is noise and the script prints it labelled as such.

At **detection** granularity there is a real sample: **157** S detections on his refused days
against **146** on his S days.

**The shared feature, named: the false S is late, dirty and counter-aligned.**

| feature | refused days (n=157) | S days (n=146) | gap |
|---|---:|---:|---:|
| tag `clean` | 32.5% | 55.5% | **23.0 pp** |
| tag `late` | **52.9%** | 32.2% | **20.7 pp** |
| outcome loss | 62.4% | 47.9% | 14.5 pp |
| 10:30 slot | 35.7% | 22.6% | 13.1 pp |
| `vol_regime` calm | 24.2% | 37.0% | 12.8 pp |
| `aligned` **against** | **47.8%** | 37.0% | 10.8 pp |
| `rangeb` big range | 54.8% | 44.5% | 10.3 pp |
| `stopb` tight | 75.8% | 85.6% | 9.8 pp |

Confluence-rescued share is 84.7% on refused days vs 79.5% on S days — **5 points**, so the
rescue mechanism is not what separates them; it is uniformly present in both.

**And the separation is small in absolute terms.** The single biggest discriminator is a
23-point difference in one tag, on populations that are otherwise the same shape. The engine
fires an S detection on 112 of 246 refused days (45.5%) and 99 of 207 S days (47.8%). That is the
measurement behind "too many random s categories": the label is close to independent of his
judgement.

---

## 4. Where the missing N is — w4's 198 candidates, today

`research/w4_recall_sources.md` nominated 198 gradeable symbol-days. Re-checked against the
current 817-key `marked_card_ids()`:

| | n |
|---|---:|
| w4 candidates | 198 |
| already judged since w4 was written | **2** |
| still new | **196** |
| — `austin_said` | 62 |
| — `third_party` | 109 |
| — `model_inferred` | 25 |
| on a symbol the book carries | 196 (all) |
| inside the 2-year book window | 158 |

**Ceiling.** Harvesting every one of them takes judged symbol-days **817 → 1,013, +24.0%**.
At Austin's own historical S share (29.9% of judged days), that is **≈59 new S days**,
taking his S corpus 240 → ~299.

That is the honest ceiling, and it is a corpus number, not a trade number. It buys **more
places to measure recall**, not more S trades — which is worth doing (the held-out set is 15 S
cards and every gate claim rests on it) but does not touch either complaint.

Two cheaper sources w4 already flagged and nobody has taken: **47 S-tier symbol-days sitting
in `recovered_reviews.jsonl`'s unmatched 135**, excluded only for a missing bar index — real
Austin judgements needing zero new grading — and the 652 undated Circle image pairs.

---

## 5. How to get more S trades — all three priced

All five arms below are measured on the **same book**, so the deltas are comparable.
The A0 absolute is **not** the published held-out figure: 3/15 and 12/42 come from
`research/t70_test1_score.py`, which drives `t4_engine_recall.run_day`, a different replay.
15 of the 100 held-out cards (4 of the 15 S cards) have **no detection at all** in this book —
structurally silent days no arm can reach.

### (a) Loosen detection — **priced, and it fails**

| arm | held-out S recall | held-out false fire (X) | gate | book n | win % | median R |
|---|---|---|---:|---:|---:|---:|
| **A0 shipped** (`traded`) | **1/15 · 6.7%** | **7/42 · 16.7%** | −0.100 | 1,017 | **52.9%** | **+0.566** |
| A1 alert or traded | 1/15 · 6.7% | 9/42 · 21.4% | −0.148 | 1,394 | 47.1% | −1.000 |
| A2 every detection graded S | 5/15 · 33.3% | 27/42 · 64.3% | −0.310 | 7,454 | 36.1% | −1.000 |
| A3 every detection graded S or A | 6/15 · 40.0% | 32/42 · 76.2% | −0.362 | 18,509 | 34.8% | −1.000 |
| A4 every detection, no filter | 11/15 · **73.3%** | 38/42 · **90.5%** | −0.171 | 45,193 | 31.9% | −1.000 |

Gate = S recall − false-fire rate.

- **Every loosening makes the gate worse**, A2 and A3 worst of all: −0.100 → −0.310 → −0.362.
- **The recall gate is not reachable this way at all.** Firing on literally every detection
  in the book — the maximum possible loosening — reaches **73.3%**, short of the 90% gate,
  while false-firing on **90.5%** of the days he refused.
- **The money gate breaks first.** Win rate collapses 52.9% → 36.1% at A2 and the median
  outcome becomes a full stop-out. The 55% gate is gone one step in.
- Mean R for any arm containing non-traded rows is **unusable and is labelled so**: 1,044
  dropped-S rows have `|entry − stop| < $0.01` and the max R in that population is **+16,350**.
  Read the win rate and the median, which have no risk denominator in them.

This is the fifth arm in three days to buy in-sample looseness and no held-out recall.

### (b) Widen the universe — **priced, and there is nothing there**

| | n |
|---|---:|
| held-out cards on a symbol the book does not carry | **0 of 100** |
| held-out **S** cards off-roster | **0 of 15** |
| Austin S days off-roster | **4 of 240** (DIA 3, MSTR 1 — MSTR is `RETIRED`) |
| Austin S days on-roster but outside the 2-year window | 20 |
| w4 new candidates off-roster | **0 of 196** |

The roster is not the constraint. Every day he has ever called S, bar four, is on a symbol the
book already replays. Widening the universe adds symbol-days with no evidence attached to them.

### (c) Accept the count, improve per-trade R — **priced, and it is the least bad**

| pool | n | mean R | win % | total |
|---|---:|---:|---:|---:|
| S | 128 | **+1.2829** | 66.4% | +164.2R |
| A | 251 | +0.9956 | 54.6% | +249.9R |
| C | 638 | +0.8735 | 49.5% | +557.3R |
| whole book | 1,017 | +0.9551 | 52.9% | +971.4R |

S already beats the book by **+0.328R** and clears the 55% win-rate half of the money gate at
66.4%. To reach mean R 2.0 at that win rate, wins must average **+3.52R**; they average
**+2.44R**. G7 swept eight exit policies and G9 fourteen structure trails over this same book
and **nothing beat the incumbent** — best whole-book +0.955R, best on S +1.383R — against a
stop-respecting oracle ceiling of +3.501R.

### Which one the evidence supports

**(c), and it does not close a gate.** (a) is refused on its own numbers — no threshold
loosening reaches 90% recall even at zero filtering, and the money gate breaks at the first
step. (b) is empty — 0 of 15 held-out S cards and 4 of 240 of his S days are off-roster.
(c) is the only arm that is not actively negative, and the exit family that would deliver it
was closed twice already.

**The thing the evidence actually points at is not on the list of three: which day gets
traded.** The engine trades on 15.5% of his S days, and when it does fire it has the setup
right 88.9% of the time and the bar right 78.6% of the time. It is not failing to see his
setups; it is failing to pick his days, and then labelling the ones it does pick with a grade
that is 2.3 points away from a coin flip against his judgement. That is `_calibration_grade`'s
first-with-trend-signal-of-the-day floor — **G14 in `TASKS.md`, still the untested lever**.

---

## What this does NOT establish

- **Nothing here was A/B'd into the shipped engine.** No flag flipped, no default changed.
- **The `sgrade` column is `downgrade.py` output and every threshold in it is a guess**
  (A1, `research/a1_threshold_sweep.md`); `level_not_respected` is measured wrong-signed. All
  "S detected" counts inherit that. The strict-S rung (zero downgrades) inherits it too.
- **Austin's S corpus is not a random sample of sessions.** It is what decks put in front of
  him, and decks were built from engine-fired and engine-silent days by design. The 207/240
  in-window figure is exact; the 45.5% / 47.8% comparison is over that selected set.
- **Held-out n is 15 S cards.** Every recall arm above moves in units of 1/15 = 6.7 points.
- **"3 S per week" is read literally.** If he meant "in a good week" the implied 151/symbol-year
  is an overstatement and every gap multiple above shrinks proportionally. The 47x on the
  top-10 names would have to fall by 47x before the engine's 3.21/symbol-year met it.
