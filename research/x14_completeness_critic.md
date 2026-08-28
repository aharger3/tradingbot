# X14 — completeness critic: what the twelve lanes did not produce

Run: `python research/x14_completeness_critic.py` (script ships beside this file).

## 1. Coverage of Austin's 23 questions

17 answered outright, 5 partially, 1 missed entirely.

- **Missed:** "a working system that makes money, and then a system that self-improves
  every day." No lane proposes a mechanism by which the engine learns from a new mark,
  a new session, or a forward trade. Twelve lanes measured; none closed a loop.
- **Partial, and the missed half matters:** "should the downgrade detectors grow." X5
  tested *deleting* variables (4 of 8 free), X3 tested deleting detectors, X7 tested
  deleting 787 lines. **Zero lanes tested adding one** — while X6 §5 already publishes
  the candidate features, measured: on the engine's false-S days `clean` runs 32.5% vs
  55.5%, `late` 52.9% vs 32.2%, counter-aligned 47.8% vs 37.0%.
- Also partial: is B grade dead (X7 prices it, nobody asks whether to retire it);
  the peer alternative to scale-in (X12 names it, nobody ran it); trade-only-S
  (money measured, no held-out recall, no "corpus is good enough" criterion);
  the risk floor and false fires (X4 §15 declares the false-fire half not measured).

## 2. The number nobody produced: a STACKED arm

Every lane A/B'd one lever against the shipped book. Not one reported two together,
so nothing in the digest says whether the surviving levers add or overlap.

| arm | n / units | mean | delta |
|---|---:|---:|---:|
| baseline (shipped 1,017-row book) | 1017 | +0.9551 R/trade | — |
| A1 — drop the 10:45–11:00 entry block (X8's ship recommendation) | 954 | +1.0085 R/trade | +0.0534 |
| S3/A1/C0 risk weighting (X12 finding 14) | 635.0 units | +1.1693 R/unit | +0.2142 |
| **STACK — A1 + S3/A1/C0** | **614.0 units** | **+1.1959 R/unit** | **+0.2408** |

The stack is very slightly **sub**-additive (pure addition would give +1.2227), and it
is **0.8041 R short of the 2.0 money gate**. This reproduces X8's A1 (+0.0534) and
X12's sizing arm (+1.1693) exactly, which is the cross-check that the two lanes are
measuring the same book.

X1's flat-2.5R arm could not be stacked: `research/x1_mfe_mae.json` ships per-row
mfe/mae/oracle but no per-arm outcome column. That absence is why nobody could stack
anything.

## 3. The execution model is one question answered two opposite ways

X2 makes the **exit** fill at the bar's close (−0.0907 R). X9 makes the **entry** fill
at the bar's close (−0.6653 R). These are the same unsettled question — does an order
rest at the level, or does the engine pay the close — and `stop_rule.py`'s own docstring
answers it one way ("Austin's stop order still rests at the level") while
`signal_runner.fill_price` back-dates a fill onto the level the other way.

No lane priced entry and exit under **one** model. Under the resting-order reading both
costs go to roughly zero; under the market-order reading both bind and the book mean
falls from +0.9551 to about +0.09. X2 correctly escalates this to Austin; X9 does not,
and publishes the larger of the two numbers as settled.

## 4. Process

`git ls-files` reports **12 of 12** lane scripts (`research/x1_…` … `research/x12_…`)
as untracked. Every number in this digest currently has no committed script behind it,
against CLAUDE.md's "if you publish a number, commit the script that made it" — in a
repo that has silently lost artifacts to `.gitignore` twice.
