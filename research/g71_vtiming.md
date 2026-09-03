# G71 / adversarial verify of the "timing" track's load-bearing finding — REFUTED

Target: `research/g71_timing.md` §4, and the claim as stated:

> On the 9 held-out S days where the engine both SAW a setup within ±2 bars of the
> minute Austin typed AND traded it, the bar it entered on is 1–3 bars after the bar
> it first saw it on — 9 of 9, same sign, median +2.0, sign test p = 0.0039. Eleven of
> the twelve signals it emitted at his candle are graded X / skipped_d.

Scripts: `research/g71_vtiming_check.py`, `research/g71_vtiming_check2.py`.
Mark files read-only. No engine file edited.

## The arithmetic reproduces. The interpretation does not survive.

Re-ran `python research/g71_timing.py --marks` — byte-identical to
`research/g71_timing_out.txt` / `g71_timing_marks.txt`: gaps `+1 +3 +1 +1 +2 +2 +2 +2 +2`,
median +2.0, 9 of 9 positive. Nothing is fabricated. Six defects void what it is used for.

### 1. The sign test's null hypothesis is unattainable. p = 0.0039 is void.

All 9 (seen, fired) pairs are the **same setup key** — `(signal_type, direction, idea)` —
verified 9 of 9 (`g71_vtiming_check.py`). `t4_engine_recall.run_day:205-223` builds
`all_sigs` as the **first bar of a contiguous run** of a key and `entries` as the **first
bar of that same run with `status=="fired"`**. A bar-close walk-forward loop cannot enter a
setup before it detects it.

- deduped-fired-bar < deduped-seen-bar for the same key, across all 34 cards: **0**.
- sweep the same estimator over every hypothetical his-bar 0..89 on all 34 cards:
  **negative 9 / zero 35 / positive 102 → P(gap<0) = 0.0616**, not 0.5.

`p = 2×(½)^9` assumes each gap is a fair coin. It is not. The measured base rate is ~6%,
and for a same-key pair it is 0. The finding "9 of 9 positive" is the arrow of time.

### 2. "Eleven of twelve are X" is the same fact printed twice, not corroboration.

`t4_engine_recall.py:151-160`: `status = "skipped_d"` **iff** `grade == TradeGrade.D`.
`omen_bot.py:100-101`: `D = "X"` — an alias of the same enum member. So "graded X" and
"skipped_d" are one field, and the claim's "X / skipped_d" double-counts it.

Logically: `gap > 0` ⟺ the deduped seen bar did not fire ⟺ it carries a skip status.
9 of the 12 are the seen bars themselves (X by construction); the one non-X, PLTR bar 15,
**is** the fired bar (non-X by construction). Zero information beyond the gap sign.

### 3. "AND traded it" is FALSE on the book. 0 of 9.

`research/bt2y_trades.json` — 76,019 signals, **2,437 traded**, 500 sessions
2024-08-21→2026-08-21 (the post-T0 book after R31's loss halt; DIRECTION.md's 2,595 predates R31):

| sym | day | book rows | fired | grades | **traded** |
|---|---|---:|---:|---|---:|
| CRM | 2025-09-19 | 6 | 0 | — | **0** |
| SMCI | 2025-11-17 | 0 | 0 | — | **0** |
| TSM | 2026-02-02 | 4 | 0 | — | **0** |
| BABA | 2025-02-05 | 10 | 0 | — | **0** |
| PLTR | 2024-03-11 | 0 | 0 | — | **0** (outside the book window) |
| HOOD | 2024-11-06 | 1 | 0 | — | **0** |
| MSFT | 2025-03-13 | 4 | 0 | — | **0** |
| AVGO | 2025-10-10 | 18 | 2 | **C**, C | **0** |
| QQQ | 2025-09-23 | 6 | 0 | — | **0** |

The engine traded **none** of the nine days. The `FIRED` verdict and the grade-`B` labels
come only from `t4_engine_recall.CaptureRunner._route`, which its own comment
(`t4_engine_recall.py:144-149`) warns *"does NOT delegate to super()._route … every gate the
base grows has to be named here or it is inert in exactly the rig that scores held-out
recall."* It also skips every `backtest_week.simulate_day` gate. The claim describes a
detection-only replay and calls it the book.

### 4. "the bar it first saw it on" is wrong for MSFT.

MSFT 2025-03-13: the fired key's **first raw emission is bar 17**, entry bar 21 → **+4**,
not +2. The reported +2 comes from `DEDUPE_CONTIG = 2` (`backtest_week.py:83,87-90`)
re-admitting the same key at bar 19 after one quiet bar. The vector is *entry minus nearest
deduped signal record*, not *entry minus first sighting*. True first-sighting vector:
`+1 +3 +1 +1 +2 +2 +4 +2 +2`.

### 5. "at his candle" is wrong on 5 of 9 days.

Deduped signals exactly at his typed bar: **4 of 9** (CRM, PLTR, MSFT, QQQ). On SMCI, TSM,
BABA, HOOD and AVGO the nearest signal is one bar **before** his minute — the engine emitted
nothing on his candle at all.

### 6. p = 0.0039 is not produced by committed code.

`research/g71_timing.py:786-795` prints the gaps and "positive on 9 of 9" and computes **no**
p-value for them. 0.0039 is hand arithmetic in the .md. Repo rule: publish a number, commit
the script that made it.

### 7. Sample construction.

n = 9 after three nested filters on 34 cards (S grade → typed minute → both `nf` and `ns`
within ±2). The ±2 conditioning truncates the right tail only (gap ≤ 4) and cannot create
the sign. The report itself reports 5 window arms over the same 34 rows.

## What actually survives

The gaps are real and mechanically explained, and `g71_timing.md` §5 already says it:
the engine holds a B&R in `skipped_d` while the retest is incomplete and fires on the first
bar its own trigger is satisfied (`backtest_week.py:216` — *"this engine is bar-CLOSE driven.
It cannot take an entry 'intrabar' in the sense Austin means"*). §4's framing — *"it writes
X on his candle and buys the one two candles later"* — contradicts §5 and is unsupported.

Corrected statement: **On 9 held-out S days the engine's own FSM held the setup in a
pre-trigger `skipped_d` state for 1–4 bars before its entry condition was satisfied — a
same-setup, causal, non-negative-by-construction latency, not a grading rejection of Austin's
candle. The sign test is void (H0 unattainable; measured P(neg) = 0.0616), "graded X" is the
same field as "skipped_d", and on the 2,437-trade post-T0 book the engine traded 0 of those
9 days.**
