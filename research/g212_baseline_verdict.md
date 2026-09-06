# The baseline — decided 2026-09-05, re-affirmed 2026-09-06

This is the book the loop measures every change against, and the number every "before"
reads from. Every figure on this page is asserted against the stamped books by
`python research/g212_trace.py` (exit 0 = nothing has drifted). The 2026-09-06 pass re-read
the refereed fill study (`research/r1_referee.md`, fourth pass) and the repaired
reconciliation ladder (`research/r2_referee.md`, third pass); the baseline did not move, the
page says more precisely why, and one rebuild pin was added so the loop can still reproduce it.

## Both fills, side by side

Same command, same minute, same commit, same 499 sessions. Only the fill differs.

`python backtest_2y.py --days 730`, commit `29e4abc6`, built 2026-09-05 18:16, sessions
2024-09-04 → 2026-09-04, engine at its shipped defaults. **Unit: his day policy** — up to 3
fires a day, stop after the first win or the second loss, in arrival order across the 11
core symbols. Exit: the shipped engine (1R hard stop resting on the level and filled on the
touch; scale out at the day's high/low, runner to break-even; two-loss halt on).

| his day policy, 11 core symbols, 25 months | fill | $/day | mean R | win | avg win / avg loss | green months | trades |
|---|---|---:|---:|---:|---:|---:|---:|
| **the baseline** — honest | market at the close of the signal bar | **−$52** | −0.034R | 45.0% | $801 / $716 (1.12×) | **11/25** | 769 |
| the phantom column | the level, even when the bar never traded there | $850 | +0.657R | 63.9% | $1,583 / $980 (1.62×) | 23/25 | 645 |
| **his bar** | | **$500** | | | **2.0×** | **25/25** | |

Honest book: `research/tape/baseline_2026-09-05.json.gz` (id `2c39ced2697c26cc`). Phantom:
`research/tape/baseline_2026-09-05_published.json.gz` (id `9a629a9682f0676b`). The phantom
is the old ruler, kept visible so nobody has to remember it: on every signal across all 29
symbols it books **$5,167/day and $2,578,552 total** on the same build — the $2.6M, rebuilt
that evening, and it is the fill.

**The target is not met.** −$52/day against $500; the average winner is 1.12× the average
loser against 2×; 11 of 25 months green against 25. No half is green either.

## The baseline, exactly

| | |
|---|---|
| trade set | everything the engine fires and trades on the 11 core symbols (TSLA NVDA AAPL AMD META GOOGL AMZN MSFT PLTR QQQ SPY); C-grade fires are logged and not traded; retest required, ON WATCH, the 84% re-entry and the two-loss halt all at their 2026-09-05 shipped setting |
| fill | **close** — a market order at the close of the signal bar. He decides on the candle close (settled); the close is a printed price he can hit within seconds; the other tradable fill, the next bar's open, is the same trade a few seconds later. On the 11 core symbols, held to the engine's own stop, next-open minus close is **+0.013R a trade, interval +0.0001 to +0.026** (`research/r1_referee4.py pairci`, 3,479 paired signals) — the lower edge sits on zero, so there is no measured reason to move the entry off the price he actually decides on |
| exit | the shipped engine. The 1R hard stop is a resting order exactly 1R from entry, and because that is the level itself, it fills on an intrabar touch; scale plan `hod_then_runner_be`; runners closed at the session end |
| unit | **up to 3 fires a day, stop after the first win or the second loss** (his day policy). First fire of the day and every signal reported beside it |
| halves | H1 = sessions before 2025-09-01 (12 months, 382 trades); H2 = 2025-09-01 onward (13 months, 387 trades) |
| script | `backtest_2y.py` builds it; `research/loop_cycle.py` reads it (its `up_to_3_rows`, `compute_all`); `research/g212_trace.py` asserts it |
| rebuild | `DAY_POLICY=first3 PYTHONIOENCODING=utf-8 python backtest_2y.py --days 730 --out research/tape/baseline_2026-09-05.json` — see "Rebuilding it" below for why the pin is there |

**Why this unit.** It is what he does — one to three trades a day, done after a win — and it
is the day-policy ruling of 2026-09-05. It has the sample to carry a verdict on both halves
(382 and 387 trades, 12 and 13 months). "Every signal" (1,909 trades, 3.8 a day on the core
11) is a book nobody trades; "first fire of the day" (498) throws away the second and third
trade he actually takes. The day policy has since been measured as its own rule on this same
book (cycle 5 in `research/tape/cycles.md`): scored on this unit it changes nothing, to the
dollar.

## The baseline's figures

Honest close fill, 11 core symbols, day policy. $/day = total ÷ sessions (499 whole; per
half, the days with a core-symbol candidate).

| | trades | $/day | mean R | win | avg win / avg loss | green months | green weeks | fires/day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **whole, 25 months** | 769 | **−$52** | −0.0335 | 45.0% | $801 / $716 (1.12×) | 11/25 | 45/105 | 1.54 |
| H1 (before 2025-09-01) | 382 | +$9 | +0.0057 | 43.7% | $917 / $701 (1.31×) | 6/12 | | 1.54 |
| H2 (2025-09-01 on) | 387 | −$111 | −0.0722 | 46.3% | $694 / $732 (0.95×) | 5/13 | | 1.54 |

Total −$25,746 over two years; worst drawdown $51,106. The halves differ by $120/day on
about 385 trades each — inside the noise; neither half is a verdict on the other.

Beside it, same book, same fill:

| unit | universe | trades | $/day | mean R | green months | H1 $/day | H2 $/day |
|---|---|---:|---:|---:|---:|---:|---:|
| first fire of the day | core 11 | 498 | −$39 | −0.0392 | 9/25 | +$32 (6/12) | −$109 (3/13) |
| every signal | core 11 | 1,909 | −$132 | −0.0346 | 10/25 | −$7 (6/12) | −$257 (4/13) |
| day policy | all 29 | 773 | −$9 | −0.0059 | 12/25 | +$72 (8/12) | −$89 (4/13) |
| first fire of the day | all 29 | 499 | +$29 | +0.0294 | 14/25 | +$119 (9/12) | −$60 (5/13) |
| every signal | all 29 | 4,053 | −$334 | −0.0412 | 8/25 | | |
| the phantom, day policy | core 11 | 645 | $850 | +0.657 | 23/25 | $813 (10/12) | $886 (13/13) |

**One more column, and why it is not the gate.** The unit above reads each day's trades back
in arrival order and stops the day the moment a winner or a second loser is *on the page*.
A trader stops the day only once that trade has *closed* — if the second signal fires while
the first is still open, he takes it. The engine now carries that causal version
(`day_policy.py`, book `research/tape/book_DAY_POLICY_on.json.gz`, core 11, fired-and-traded
rows, 1,095 candidates blocked by the policy): **814 trades, −$4/day, 12/25 green, 47.3% win,
$761 / $693**; H1 432 trades +$41/day 7/12; H2 382 trades −$45/day 5/13. That is $48/day
better than the gate unit on ~800 trades — inside the error bar, same sign on each half, not a
verdict. The gate stays on the unit every cycle so far was read on; the causal column travels
beside it in the tape and is the one to switch to if a future cycle's answer differs between
the two.

**The ceiling, re-measured on the honest book:** the day's best fire, chosen after the
fact, core 11: **$1,760/day, 95.0% win, 25/25 green** (498 trades; all 29 symbols:
$2,681/day, 99.4%, 25/25). It is proof the setups are in the book every month at an honest
fill. It is not a plan — nothing can pick it in advance.

## Where the money is lost

The reconciliation ladder walked from the lab rig's **$4,569/day** (next-open fill, flat 2R
target, every grade, 29 symbols, 14,327 trades) down to the shipped book, one change at a time.
One step took $5,550 of it; everything else was small.

**The money is lost at step 2 — where the lab's exit is replaced by the real engine's trade
management — because the $4,569/day was earned by a stop that only fired on a candle close,
so every wick through the level and back was a free pass; the real engine's 1R hard stop
rests on the level and fills on that wick, which turns about one trade in twenty from a +2R
win into a −1R loss (win rate 38.8% → 33.6%, counted as winners ÷ all filled trades:
5,556 of 14,327 → 4,820 of 14,332, no scratches in either book; average win and average
loss unchanged) and takes $4,420 of the $5,550, and the scale-out ladder takes the remaining
$1,131.**

The three books behind that sentence, every filled signal, 29 symbols, next-open fill,
2024-09-04 → 2026-09-04:

| | trades | $/day | mean R | win | avg win / avg loss (R) |
|---|---:|---:|---:|---:|---:|
| lab rig: close-only stop, flat 2R | 14,327 | $4,569 | +0.1592 | 38.8% | +1.98 / −1.00 |
| real engine: 1R touch stop, flat 2R | 14,332 | $150 | +0.0052 | 33.6% | +1.98 / −1.00 |
| real engine: 1R touch stop, shipped scale-out | 14,332 | −$981 | −0.0342 | 42.7% | +1.03 / −0.83 |

Substrate leg −$4,420/day (79.6%); ladder leg −$1,131/day (20.4%); both hold in both halves
(`research/r2_referee_pass2.py`, `research/r2_referee_pass3.py`). The third pass also
replayed the raw one-minute bars for 200 of the 697 trades that flip between the first two
rows: 183 of them (91.5%, interval 86.8–94.6%) are exactly the mechanism named — a wick
through the stop on a candle that closed back on the right side. Books:
`reconcile_fwd_1_add_C_grades` (id `d3b7151c374a9f7f`),
`r2ref_simd_next_open_blind2r_real_engine` (id `6b3b862ce4ffebe0`),
`reconcile_fwd_2_swap_exit_shipped_ladder` (id `a2ff837493e9a7d2`), all in `research/tape/`.
The first and third were regenerated on 2026-09-06 (commit `5f8b554e`) by the ladder's repair;
the middle one is the referee's own from 2026-09-05 (`15a729ce`). Every cell reproduced to
the cent across that regeneration; the referee checked the two commits differ by nothing
that reaches these books (identical entry and stop on all 13,218 shared trades).

**And the fill study agrees.** Held to the engine's real stop, the six ways of filling the
same signals on the core 11 (every traded signal, flat 2R, `research/r1_referee3.py`
uniform) read: as booked $395/day 22/25 · next open $44 12/25 · close −$46 13/25 ·
resting limit at the level −$23 8/25 · mid-candle −$720 7/25 · chase once −$1,457 3/25.
Under a close-only stop the same next-open column reads $1,250/day 22/25. The fill was
never the edge; the stop model was.

What that means in trading terms: the honest engine's "stop on the candle close" rule never
gets to act, because the 1R hard stop he asked for on 2026-09-03 sits at exactly the same
price and a resting order fills first. The stop that governs this book is the wick. That is
his ruling and it stands; it is also where four fifths of the lab book's money went, and any
change that moves the hard stop off the level is a rule change that must go through the
gate like every other.

## Rebuilding it

Since the day-policy rule shipped inside the engine (2026-09-05, cycle 5), a bare
`python backtest_2y.py --days 730` at the current code builds a *different* book
(id `205d3dcee96c5282` — the engine applies the policy across all 29 symbols and blocks
1,095 core candidates). Scored on the gate unit that book reads the same −$52/day, 11/25,
769 trades, but its fingerprint is not the baseline's, and the loop refuses to run a cycle
whose "before" does not match the baseline exactly. So the rebuild carries one pin:

`DAY_POLICY=first3 PYTHONIOENCODING=utf-8 python backtest_2y.py --days 730 --out research/tape/baseline_2026-09-05.json`

That command reproduced id `2c39ced2697c26cc` byte-for-byte at commit `5e8b5b89`
(`research/tape/book_DAY_POLICY_off.json.gz`) and again at `24b009e5` on 2026-09-06
(this pass, in the background, 499 sessions, 127,513 signals, 4,053 traded). The pin lives
in `research/tape/loop.json` under `rebuild.env`; the loop strips only the flag under test
from each OFF arm, so it survives every cycle. The referee of that cycle asked for the
engine default to be put back; that is an engine change and not this page's — the pin makes
the baseline reproducible either way.

The window is the other clock. `--days 730` counts back from the last archived session,
and the archive advances every weekday at 16:15 ET. Its last session is still 2026-09-04,
so the command above reproduces this window until 2026-09-08 at the earliest (the 7th is a
holiday). After that the OFF arm cannot match this fingerprint without a fixed start/end
date in `backtest_2y.py` — an engine change nobody has landed.

## What this page settles

- The loop's "before" is **−$52/day, 11/25 green, 1.12×**, on the day policy, core 11, honest
  close fill, shipped exit, book `baseline_2026-09-05.json.gz`. A change ships only if green
  months do not fall and $/day does not fall more than 5% on both halves.
- The phantom column travels beside it in the tape and is never a target.
- The five cycles run so far (`research/tape/cycles.md`) were all read on this book and this
  unit; nothing on this page moves any of them.
- Next: pin the rebuild window in `backtest_2y.py` before the archive advances on
  2026-09-08, or the loop's next OFF arm will be a different universe.
