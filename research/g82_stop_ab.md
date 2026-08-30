# The stop A/B and the scale-out A/B — measured, 2026-08-30

Austin said the close-only stop rule stands **"if you have the metrics."** Nobody had ever
run the plain A/B. This is it: six full replays of the 500-session archive through the
shipped engine, one per arm, priced on identical arithmetic.

Companion: `research/g82_stop_provenance.md` traces where the rule came from. This file is
only the metrics.

Script: `research/g82_stop_ab.py`. Numbers: `research/g82_stop_ab.json`.
Reproduce: `python research/g82_stop_ab.py --jobs 3` (about 30 minutes).
1R = $1,000. 500 sessions, 2024-08-21 → 2026-08-21, 28 symbols.

---

## The short version

**The book we ship is not running the close-only rule.** It is running a touch stop, and it
has been since 2026-08-29. When you actually run the close-only rule it is the best arm on
the board: **$6,460 a session against the shipped $5,268** taking everything, **$821 against
$721** on one trade a day. And **profit legs already fill on a touch** — Austin's belief is
what is coded, at all three legs, in both the backtest and the live path. Making them wait
for a close costs **$1,981 a session**.

---

## 1. Why the close-only stop has never been measured

`stop_rule.disaster_stop_price(entry, risk, long, 1.0)` is `entry -/+ 1.0 x risk`
(`stop_rule.py:128`), and `risk` is `abs(entry - stop)`. So the resting "disaster" stop sits
at **exactly the price of the level stop** — the same line, not a line underneath it. It is
tested **first**, on an intrabar **touch** (`stop_rule.py:139`,
`backtest_week.py:490`), before the close-triggered level stop ever gets a look.

So the shipped engine already exits on a wick through the stop, on every leg of every trade
that has not yet scaled out. The close-only rule survives in exactly one place: a runner
whose stop has already been raised to break-even after the first scale rung — and by then
the stop is at entry, not at the level.

The book proves it. In `research/bt2y_trades.json`, of 1,828 losing trades:

- **1,775 book exactly −1.000R**
- **0 book worse than −1.000R**
- worst loss in the whole book: **−1.0000R**

A close-triggered stop that filled at the close would have to book past −1R whenever the bar
ran. It never does, in 4,508 trades. The `stop_hit_on_close` branch and the −1.25R floor are
**unreachable code in the shipped configuration** — the same defect
`research/x2_stop_floor_audit.md` found and T11 fixed, re-created two weeks later by a
different mechanism.

`research/g71_advexitfam.md` §1 already found the price identity (2437/2437 rows,
max |diff| = 0.0) on a stripped ride model. What was missing, and what this is, is the
priced four-arm A/B over the real engine and the whole book.

**The live path has the same shape**: `paper_trader.py:291` tests the resting disaster stop
on a touch first, then the level stop on a close. Live and backtest agree with each other.
They just do not agree with the rule.

---

## 2. The four stop arms

Every named arm turns the disaster stop off, because each one states its own complete stop
semantics. Leaving a second stop underneath measures the two together, which is the exact
confusion this table exists to end.

| arm | $/day, everything | $/day, one a day | trades | win % | mean R | avg loss R | months green | weeks green | worst drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **shipped** (arm 1 as it really runs) | $5,268 | $721 | 4,508 | 59.4% | 0.5843 | −0.9754 | 25 of 25 | 100 of 105 | $11,105 |
| **close, floored at −1.25R** (arm 1 as written) | **$6,460** | **$821** | 4,831 | 63.3% | 0.6686 | −1.1510 | 25 of 25 | 102 of 105 | $14,298 |
| **close, no floor** (arm 4) | $5,512 | $735 | 4,822 | 63.1% | 0.5716 | −1.4010 | 25 of 25 | 96 of 105 | $22,394 |
| **touch, fills at the stop** (arm 2) | $5,241 | $709 | 4,511 | 60.0% | 0.5809 | −0.9870 | 25 of 25 | 100 of 105 | $10,883 |
| **touch + −1.25R floor** (arm 3) | $5,241 | $709 | 4,511 | 60.0% | 0.5809 | −0.9870 | 25 of 25 | 100 of 105 | $10,883 |

The last four columns are the **all-trades** policy: calendar months of the 25 in the window,
ISO weeks of 105, and the worst peak-to-trough of the cumulative dollar curve.

**Durability under one-trade-a-day tells a different story, and it favours the shipped book.**
Every month is green all-trades on every arm. On one trade a day only the shipped book keeps
all 25:

| arm | months green, one a day | weeks green, one a day | worst drawdown, one a day |
|---|---:|---:|---:|
| shipped | **25 of 25** | 87 of 105 | $5,993 |
| close, floored at −1.25R | 24 of 25 | 89 of 105 | $6,250 |
| close, no floor | 24 of 25 | 84 of 105 | $9,371 |
| touch (arms 2 and 3) | 23 of 25 | 85 of 105 | $5,993 |
| target on close | 21 of 25 | 75 of 105 | $7,167 |

So the close-only rule buys about $100 a session and two green weeks on his real policy, and
costs one green month. That trade is his to make, not an agent's.

### What each row says

**Shipped and touch are the same rule.** $5,268 vs $5,241 a session, mean R 0.5843 vs 0.5809,
paired difference **−$27 a session, 95% CI [−$137, $86]** — straddles zero. That is not a
coincidence, it is the identity in §1. The $27 is the one place the close rule still applies:
the break-even runner stop after a scale-out.

**Arm 2 and arm 3 are byte-identical books** — same 4,511 trades, same md5 over every exit
price and R. Under a touch stop, no bar in two years ever gapped through the stop badly
enough for the −1.25R floor to have anything to clamp. Worst loss −1.2353R, and that one came
from a gap open, not from slippage. **The floor is worth exactly $0 when the stop fires on a
touch.** It is only worth something when the stop fires on a close.

**The floor is the whole reason the close arm wins.** Close-with-floor makes $6,460 a session;
strip the floor and the same rule makes $5,512 and doubles the drawdown to $22,394, because
**971 of 4,822 trades book worse than −1.25R and the worst books −6.06R**. Austin's two
numbers are one rule and neither half works alone: the close is the trigger, the floor is what
makes the trigger survivable.

**The close-only rule as written is the best arm on the board.** +$1,194 a session over the
shipped book taking everything (95% CI [$848, $1,556]), +$101 a session on one trade a day
(CI [$30, $182]), 102 green weeks against 100, and 25 of 25 green months either way. It pays
for that with a worse average loss (−1.151R against −0.975R) and a worse drawdown ($14,298
against $11,105) — you are holding through wicks, so the losses you do take are bigger, and
you take fewer of them.

---

## 3. The scale-outs — how the profit legs are actually evaluated

**Answer: intrabar touch, everywhere, and always has been.** Austin is right and arm A is
what is coded. There are three profit legs and all three are a touch:

| leg | before today | now |
|---|---|---|
| the blind 2R target | `backtest_week.py:819` — `c.high >= t.target` | `backtest_week.py:905` |
| the PT1 scale rung (50% off at HOD/LOD) | `backtest_week.py:592` — `c.high >= t.scale_level` | `backtest_week.py:678` |
| the runner target | `backtest_week.py:609` — `c.high >= t.runner_target` | `backtest_week.py:695` |

All three now route through one function, `backtest_week._target_hit` (`backtest_week.py:426`),
which is the same expression — the refactor exists so the claim is checkable in one place
instead of three, and so the close-through arm could be built at all. Defaults are unchanged
and measured to be so (§5).

The live path matches: `paper_trader._check_target` (`paper_trader.py:222`) is wick-based on
purpose and says so, the scale rung is a touch (`paper_trader.py:297`), the runner target is a
touch (`paper_trader.py:305`). `stop_rule.py`'s own module docstring already stated the
principle: *"Targets are not stops... Only the STOP trigger moved to the close."*

| arm | $/day, everything | $/day, one a day | trades | win % | mean R | avg loss R | months green | weeks green | worst drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **A — touch (shipped)** | **$5,268** | **$721** | 4,508 | 59.4% | 0.5843 | −0.9754 | 25 of 25 | 100 of 105 | $11,105 |
| **B — close through the target** | $3,291 | $533 | 4,160 | 51.6% | 0.3955 | −0.9884 | 25 of 25 | 93 of 105 | $20,277 |

Requiring a close costs **$1,981 a session** (95% CI [−$2,307, −$1,662]), drops the win rate
from 59.4% to 51.6%, costs 7 green weeks and nearly doubles the drawdown. The fear was
unfounded, and had it been founded it would have been expensive.

---

## 4. Does any of it beat the error bar?

**No — on the project's standing yardstick, every arm is a tie.** DIRECTION.md's standing
method finding is that every A/B here moves less than **±1.5799R per trade**. Measured against
that bar:

| arm vs shipped | Δ mean R per trade | verdict |
|---|---:|---|
| close, floored | +0.0843R | tie |
| close, no floor | −0.0127R | tie |
| touch | −0.0034R | tie |
| touch + floor | −0.0034R | tie |
| target on close | −0.1888R | tie |

Nothing here is within an order of magnitude of ±1.5799R. **Tie.** That is the honest answer
and it is the one he asked for.

The paired per-session dollar test is a much tighter instrument than the per-trade R bar, and
on that test two arms do move: close-with-floor at +$1,194 [+$848, +$1,556] and target-on-close
at −$1,981 [−$2,307, −$1,662]. Both intervals exclude zero over 10,000 day-resamples of the
same 500 sessions. They are answering a different question — *what does a day earn* rather than
*what does a trade earn* — and the split shows why:

| arm vs shipped | from taking more trades | from better trades |
|---|---:|---:|
| close, floored | +323 trades → +$377/session | +$766/session |
| target on close | −348 trades → −$406/session | −$1,695/session |

Close-with-floor gets a third of its gain from volume. Its extra 323 trades are mostly the
account-wide two-loss halt firing less often: **1,220 halted trades against the shipped 1,662**.
Holding through wicks means fewer back-to-back losses, so the day stays alive.

---

## 5. What was changed, and the proof it changed nothing by default

Three new knobs in `backtest_week.py`, all off by default:

- `STOP_ARM` (`backtest_week.py:240`) — names one of the four arms; `""` is the shipped book.
- `TARGET_ON_CLOSE` (`backtest_week.py:258`) — `0` is the shipped touch.
- `_target_hit` (`backtest_week.py:426`) — one function behind the three profit legs.

`_stop_fill_px` gained a `level` argument so a resting-stop arm fills where it *rests* rather
than at the original stop; the shipped path ignores it.

**Byte-identity check, run not asserted.** The pre-change file was reconstructed by reversing
each edit, and both versions were replayed over NVDA, COIN and AAPL, last 90 sessions each:
**3,059 signals, md5 `deaacb125561925bff7da5982b02f585`, identical**. Both verify gates pass
(`research/regression_gate.py`, `research/test_runner_stop.py`).

## 6. What this does not answer

- **Nothing was switched on.** `DISASTER_STOP` still defaults to 1 and the book still ships
  as a touch stop. Turning it off is a change to a shipped default and to every published
  money figure — that is Austin's call, not an agent's.
- **The arms change which trades exist**, through the 84% re-entry arming and through the
  two-loss halt. That is why each arm is a full replay rather than an exit-only re-scoring,
  and it is also why "more trades" is a real part of the answer and not an artefact.
- **The money gate is untouched.** The best arm here is mean R **0.6686** against a gate of
  **2.0**. This is a stop-rule question, and DIRECTION.md's finding stands: the exit family is
  not where the gate is won.
- **Grades, both ladders, are unchanged** — no arm here touches detection or grading.
