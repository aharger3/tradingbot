trades_total: 1017
trades_flipped: 0
win_rate_optimistic: 55.0
win_rate_pessimistic: 55.0
ev_optimistic: 0.873
ev_pessimistic: 0.873
flips_change_outcome: 0

## What this measured

The stop needs a candle CLOSE beyond the level; the target is a resting limit
order, so it fills on an intrabar TOUCH. Asymmetric on purpose, and both halves
are right. The open question was the bar that does BOTH: today's book let the
target win it. `PESSIMISTIC_FILL=1` (now the default) says you cannot know, from
a 1-minute bar, whether price tagged the target before or after it collapsed
through the stop — so it books the loss at the stop, at every rung of ladder B.
The 1R scale-out takes no partial credit, and the runner books at the trade's
ORIGINAL stop rather than the breakeven stop mode B moved it to.

**The answer is zero.** Across 1017 traded trades, not one changed from a
win to a loss (or a loss to a win) under the pessimistic rule. Win rate and
average R are identical in both arms to the digit (55.0% and +0.873R either way).

The reason is that the tie was **already** resolved as a loss, in both exit
paths, before this flag existed: `backtest_week._stop_hit` is tested first in
`_ladder_bar` and first again on the binary path. omen-5.0's own caveat said
so; this row is the measurement that proves it.

**So the target-fill assumption is not where the engine's edge came from.** The
reported +0.873R per trade does not shrink by a cent when you take the
most hostile possible view of same-bar fills. That leaves the honest-EV
question resting entirely on the other two inflators — in-sample fitting and
the uncapped runner — which is T4's job, not this one.

## The flip file

`research/t51_fill_flip.jsonl` is deliberately wider than the headline: it carries
all 26 trades in the whole simulated book whose FILL the rule moved, 0 of
them traded. The rest are `counted: false` — signals the engine simulates but
never takes (D-grade, tight-stop, and C-grade fired-but-uncounted), so their R
multiples (a $0.004 stop books 11R) are evidence, not headline numbers. Every row
carries `status` and `counted` so a filtered signal is never read as a traded one,
and `old_outcome`/`new_outcome` are equal on a row whose R moved but whose label
did not.

5 of those 26 rows do change label (win -> loss); the other 21 are
R-reductions only. 5 of the 5 are `counted: false`, which is why `flips_change_outcome`
is 0: the rule bites, but on signals the engine had already thrown
away. That distinction is the whole point of keeping both counts.
