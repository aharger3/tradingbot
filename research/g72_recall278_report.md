# Recall, measured honestly and on the whole pile

**What changed.** Two fixes to how we measure whether the engine finds your S days.
Neither touches the engine, so no trade changes and no dollar figure moves.

1. **We were scoring 34 days. We now score 278.** Every recall number this project has
   published came off one file of 100 cards, 34 of which you graded S. You already have
   **278 S days with the bars on disk**, and the whole graded pile replays in about three
   minutes. Nothing was ever stopping us.
2. **The scorer was running a photocopy of the engine, not the engine.** The recall
   harness had its own hand-written copy of the code that decides whether a setup is
   taken. Every rule the real engine grew after that copy was written was invisible to
   it. It now calls the real engine.

**The number, honestly.**

| | S days | fires on | recall | 95% band | short of the 90% gate by |
|---|---:|---:|---:|---|---:|
| **All 278 of your bar-backed S days** | 278 | 163 | **58.6%** | 52.8% – 64.3% | **31.4 points** |
| The 100 blind cards, as published before | 34 | 23 | 67.6% | 50.8% – 80.9% | 22.4 |
| The same 100 blind cards, real engine | 34 | 22 | **64.7%** | 47.9% – 78.5% | 25.3 |

So: **the engine fires on 59 of every 100 days you called S. The gate is 90. We are 31
points short, and the whole 95% band — 53 to 64 — sits nowhere near it.** The odds of
seeing 163 out of 278 if the true rate were really 90% are 1 in 10⁴².

The published 23-of-34 was the photocopy's answer. The engine's answer on those same
cards is **22 of 34**. One day flipped: QQQ, 23 Sep 2025 — a fire only the copy took.

Scripts: `research/g72_recall278_paired.py` → `research/g72_recall278_paired.json`;
`research/g72_recall278_t0_rerun.json` is the standing 100-card scorer re-run unchanged,
confirming 22/34. The recall regression gate (`python research/regression_gate.py`) is
**PASSING** after the change.

---

## What the bigger sample buys

Everything below is what we can now *see*, at two extra minutes of compute per run.

| | 34 cards | 278 days |
|---|---:|---:|
| How tight the answer is (± points) | **±15.7** | **±5.8** |
| Chance of spotting a real 10-point improvement, paired | 0.33 | **0.99** |
| Same, on the pessimistic assumption | 0.18 | **0.87** |
| Same, unpaired (the old way) | 0.13 | 0.69 |

On 34 cards, a change that genuinely made the engine 10 points better had a **2-in-3
chance of looking like nothing**. On 278 days paired, it has a 1-in-100 chance of hiding.
That is the difference between steering and guessing.

**You do not need to grade more cards for this.** The earlier note that proving 90% needs
141 more cards was arithmetic done on the wrong pile — the days are already graded and
already have bars.

## What the photocopy was actually costing

Run both scorers over the same 278 days, day by day:

- the copy fired on **3 days the real engine refuses** (QQQ 23 Sep 2025, QQQ 7 Jul 2026,
  SPY 20 Jul 2026), and on **no day the engine takes that it missed**;
- that is **+1.1 points of flattery** — 59.7% vs 58.6% — and it is not statistically real
  on its own (McNemar p = 0.25).

So the copy was not wildly wrong; it was **quietly wrong in one direction, always
upward**, and on a 34-card sample one flattered day is 3 points of headline. That is
exactly the size of thing this project has been calling a result.

## Two things worth knowing that fell out of the run

1. **The engine barely tells your S days apart from the days you refused.** Over the full
   graded pile: it fires on **58.6%** of your S days and **50.4%** of the 534 days you
   looked at and refused. Eight points of separation, and the bands nearly touch
   (S: 52.8–64.3, refused: 46.1–54.6). It fires on your A days *less* often than your S
   days (49.3%) and on your C days *more* (66.7%). Whatever it is sorting on, it is not
   your grade. This is the recall harness, not the traded book, so it is a different
   measurement from §3 of `g71_board.md` — but it points the same way.
2. **The legacy A+/A/B/C/X ladder is one bucket, again.** Of the 163 S days it does fire
   on, the entries carry legacy grades B 158, C 44, A 2 — no A+ at all. (Your S/A/C/none
   ladder and the engine's A+/A/B/C/X ladder are kept side by side and never mixed.)

## Housekeeping

- `research/t4_engine_recall.py`'s router now delegates to the shipped engine. The x-lift
  test (`research/test_t10_x_lift.py`) checked for the photocopy by name; it now checks
  the stronger thing — that the recall rig reaches the real router — and is green.
- `research/g71_samplesize_full_recall.py` and `research/g71_ssverify_power.py` are
  marked superseded at the top of the file and left otherwise untouched, so the G7.1
  reports that cite them still resolve. Do not re-run them for a published number.
- **`DIRECTION.md` still advertises 52.9% (18 of 34) as the recall row.** The honest
  number is 58.6% on 278 days / 64.7% on the 34 blind cards. That file belongs to another
  item on this board and was not edited here.
