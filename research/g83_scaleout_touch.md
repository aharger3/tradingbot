# Profit targets fill on touch — checked, and it was already true

**Austin, 2026-08-30, ratified:** *"A profit target is a resting limit order and it fills the
moment price touches it."*

**The answer: the code already does this. Everywhere. Nothing was broken, so nothing was
changed.** There is now a test that fails the build if any profit leg ever starts waiting for a
candle to close.

**What the rule is worth: $188 a day**, one trade a day, over the two-year book. Waiting for a
close instead would take one trade a day from **$721/day to $533/day**, and — the part that
actually matters — from **25 of 25 green months to 21 of 25**. Against the six-figure bar of
**$397/day**, touch-fills sit **+$324/day above it** and close-fills sit **+$136/day above it**.

---

## 1. Where every profit leg is, and what it does today

Four legs exist. Every one of them triggers on the bar's **high** (long) or **low** (short) —
an intrabar touch — and not one of them looks at the close.

| leg | file : line | trigger today |
|---|---|---|
| first scale rung (half off at the session high/low) | `backtest_week.py:678` — `_ladder_bar` | **TOUCH** |
| runner target (the rest, at the next key level) | `backtest_week.py:695` — `_ladder_bar` | **TOUCH** |
| blind 2R target (when the ladder is switched off) | `backtest_week.py:905` — inside `simulate_day` | **TOUCH** |
| break-even move (stop goes to entry after the rung) | `backtest_week.py:679-681` — `_ladder_bar` | **TOUCH** — it moves the instant the rung is touched |

All four route through one function, `backtest_week.py:426 _target_hit`, which reads
`c.high` / `c.low`. Before that function existed the same comparison was written out inline at
each of the three call sites; the committed version at `35db9256` reads
`c.high >= t.scale_level` at line 562, `c.high >= t.runner_target` at 579 and
`c.high >= t.target` at 789. **This has been touch-based for the whole life of the file.**

The live path is the same:

| live leg | file : line | trigger today |
|---|---|---|
| 2R target | `paper_trader.py:222 _check_target` | **TOUCH** (`high`/`low`) |
| break-even scale | `paper_trader.py:236 _check_breakeven` | **TOUCH** |
| ladder scale rung | `paper_trader.py:297` inside `_ladder_exit` | **TOUCH** |
| ladder runner target | `paper_trader.py:305` inside `_ladder_exit` | **TOUCH** |
| runner target after a break-even scale | `paper_trader.py:370` inside `exit_for` | **TOUCH** |

And the third rig that books a target, `research/exit_lab.py:214 flat_target`, is touch too.

`signal_runner.py` and `options_sizer.py` **do not evaluate exits at all.** `signal_runner`
computes the target price (line 2328: `entry + 2 * risk`) and hands it off; `options_sizer`
prices the two rungs (`ladder_levels`, line 159) and the premium each one is worth. Neither one
decides when a leg fills, so neither can get touch-vs-close wrong. That is worth saying out loud
because the question was asked of all four files.

## 2. The test

`research/test_scaleout_touch.py` — assert-based, no framework, same shape as
`research/test_runner_stop.py`. 34 checks, synthetic bars, no archive and no network, runs in
under a second.

Every case is the one bar shape that separates the two rules: **the wick reaches the profit
level and the close does not**, with the close left safely on the right side of both the level
stop and the resting −1R order, so nothing in the case can be resolved by a stop rule. Long and
short, both scale plans, backtest and live.

The blind 2R target is the one leg with no seam a test can drive — it lives inline inside
`simulate_day`'s bar loop and reaching it needs a real replayed session. It is covered by a
source check instead: the forbidden shape (a candle close compared against a profit level) must
not appear anywhere in `simulate_day`, `_ladder_bar` or `PaperPosition`, and the trigger that is
there must read the bar's extremes. That check is stated as a rule about the code, not a
snapshot of it, so a rewrite that keeps the rule keeps passing.

**It passes on the first run: 34 of 34.** Which is the whole finding — so the test was then
checked for whether it is capable of failing at all, because a check that cannot go red measures
nothing:

- Run the whole book with the profit legs flipped to close-triggered
  (`TARGET_ON_CLOSE=1 python research/test_scaleout_touch.py`) and **10 checks go red** — every
  scale rung, every runner target, every break-even move, long and short.
- Replace the four live methods with close-waiting versions and **10 of those 12 checks go red**;
  the two that did not were an artifact of how the harness patched the module, and they go red
  when patched at the binding the test actually uses.
- Feed the source check a mutated line and it flags it.

So the test is sensitive to the failure it is written to catch, on every leg.

## 3. What it is worth — the price of the rule

Two complete two-year books, same engine, one flag apart. Nothing about a stop differs between
them: same close trigger, same resting −1R order, same −1.25R floor. Built with
`backtest_2y.py --days 730` and priced by `research/g83_scaleout_price.py`, which imports its
arithmetic from `research/g72_suppress_price.py` so "dollars a day" means what it means
everywhere else. 1R = $1,000, 500 sessions.

### One trade a day — the unit that matters

| | touch (shipped, ratified) | waits for the close | difference |
|---|---:|---:|---:|
| **dollars a day** | **$721** | **$533** | **+$188** |
| **distance to the $397/day bar** | **+$324/day** | **+$136/day** | **+$188** |
| green months | **25 of 25** | 21 of 25 | **+4** |
| green weeks | 87 of 105 | 75 of 105 | +12 |
| worst drawdown | **$5,993** | $7,167 | $1,174 better |
| win rate (a read, not a gate) | 66.7% | 59.3% | +7.4 pts |
| trades | 499 | 499 | — |
| two-year total | $360,380 | $266,474 | +$93,906 |

### Taking every signal the engine fires

| | touch (shipped) | waits for the close | difference |
|---|---:|---:|---:|
| dollars a day | $5,268 | $3,291 | +$1,977 |
| distance to the $397/day bar | +$4,871/day | +$2,894/day | +$1,977 |
| green months | 25 of 25 | 25 of 25 | — |
| worst drawdown | $11,105 | $20,277 | $9,172 better |
| trades | 4,508 | 4,160 | +348 |

### Reading it honestly

**On dollars alone this is a tie.** $188 a day one-trade-a-day is 0.188R a trade, and the
standing error bar on every A/B this project has run is ±1.5799R. Nothing about a per-trade mean
separates these two arms and this note does not claim it does.

**On durability it is not a tie, and durability is the ratified tiebreaker.** 25 of 25 green
months versus 21 of 25 is the difference between meeting the durability bar and missing it, and
Austin settled tonight that green months win when gates conflict. The drawdown moves the same
way in both streams, and hard: taking every signal, close-waiting nearly doubles the worst
drawdown, $11,105 to $20,277.

**The caveat that outranks the level of both numbers.** Roughly 85% of this book's entries fill
at a price that had already traded earlier in the entry minute (`OMEN-7.3.md` §1, being
re-checked in `research/g80_lookahead_refute.md`). Both arms carry that head start equally, so
the **difference** between them is the trustworthy figure here; the absolute $721 and $533 are
not, and neither is the "+$324/day above the bar". Do not quote the level from this note.

## 4. What was NOT touched, and one thing left open for Austin

- **No stop logic was changed, or read for a decision.** Stops are a separate question he has
  explicitly not re-ratified, and the stop A/B is running elsewhere tonight. Every stop fill
  still goes through `stop_rule.stop_fill_price()`.
- **No production code changed at all.** The only new files are the test, the pricing script and
  this note. The book is byte-identical.
- Both gates re-run green: `research/regression_gate.py` **PASS** (83 firing marks against a
  baseline of 75, nothing went silent), `research/test_runner_stop.py` **ok** (18 laddered
  results, floored at −1.25R).

**The one open item, and it needs him.** There is a single place where a target that was touched
does *not* fill: when the same one-minute bar tags the profit level **and** closes beyond the
stop. The book calls that a full loss and gives the scale rung no partial credit
(`backtest_week.py:660-678` — the stop is tested before the scale rung — and `:705-716`,
`PESSIMISTIC_FILL`, on by default; the live path does the same at `paper_trader.py:293-297`
and `:308`). The reasoning on file is that a 1-minute bar cannot say
which came first, and assuming the target went first is the single most optimistic assumption in
the whole rig.

That is a deliberate, documented tie-break, not a leg waiting for a close — but it is the only
case where his ratified sentence and the shipped code point different ways, and it sits on the
stop side of the line, so it was left alone. **It is a one-word answer from him:** on a bar that
tags the target and closes through the stop, does the half come off first, or does the whole
thing lose?

---

*Test: `research/test_scaleout_touch.py`. Pricing: `research/g83_scaleout_price.py` →
`research/g83_scaleout_price.json`. Books built with `backtest_2y.py --days 730`, with and
without `TARGET_ON_CLOSE=1`, 2026-08-30.*
