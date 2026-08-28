# X2 — stops that go past 1R, and max drawdown

Produced by `research/x2_stop_floor_audit.py` and `research/test_x2_stop_floor.py`
at commit `c089b26b`, over the 1,017 traded rows of `research/g3_arm_ow1.json`
(the shipped arm, `ON_WATCH=1`, replayed by `research/g3_onwatch_2y.py` at
`47e60796`), 2024-08-21 → 2026-08-21, 500 sessions, 28 symbols, `data_archive/`
replay, zero fetches. Error bar **±0.0095 R**, the narrow bar (the wide ±1.5799 R
bar was retired 2026-08-28).

Reproduce:

```
python research/x2_stop_floor_audit.py --json research/_x2_audit.json
python research/test_x2_stop_floor.py
```

---

## The answer

**Austin is right, and the book cannot show it.** On the archived tape,
**458 of the book's 474 stop-outs — 96.6% — were triggered by a candle that
closed past 1R**, median **−1.3500 R**, worst **−4.3571 R**. The book records
every one of them as exactly −1.000 R, because `backtest_week.py` triggers the
stop on the close and then fills at `t.stop`.

**DIRECTION.md's standing claim is true of the file and circular as evidence.**
Line 72 says *"Verified in the 2-year replay: worst traded outcome is −1.000R, so
the floor never binds today — it exists for the slippage case."* Verified against
the file: the worst outcome across **all 45,193 rows** is −1.0000 R, **0 rows**
are worse, and **all 474 losses have `exit == stop` to the cent** (max
|exit − stop| = 0.0). The floor never binds because **the fill convention makes
it unreachable**, not because the slippage case does not happen. It happens on
96.6% of stop-outs.

**And max DD is not what he thinks it is.** The book's max drawdown is
**11.44 R over 17 trades** (2025-08-29 → 2025-09-15), and its worst single trade
inside that stretch is **−1.000 R**. It is 14 losses and 3 wins in a row, not one
trade slipping. **Max DD is a portfolio phenomenon.** The per-trade slippage is a
separate, real problem that *deepens* it: honouring the close fill with the
−1.25 R floor takes max DD to **14.49 R over 26 trades**, and without the floor
to **19.34 R over 40 trades**. Longest losing streak is **7** in all three arms.

**The floor is worth 0.1383 R of mean, and it does not touch entries.** Austin:
*"the risk floor shouldnt cause false fires it just stops losers from running
past 1-1.25."* Correct — it is an exit-price clamp, nothing in it reaches
detection. Priced: book mean R **+0.9551 → +0.8644** with the floor,
**→ +0.7261** without it.

---

## 1. The book as booked

`python research/x2_stop_floor_audit.py --book`

| read | value |
|---|---:|
| traded rows | 1,017 (of 45,193 signals) |
| min r / p1 / p5 / median | **−1.0000** / −1.0000 / −1.0000 / +0.5660 |
| rows with `r < −1.0` | **0** |
| rows with `r == −1.0` exactly | **474** |
| rows with `−1.0 < r < 0` | **0** |
| distinct negative `r` values in the whole book | **`[-1.0]`** |
| min r over ALL 45,193 rows (traded and not) | **−1.0000**, 0 worse |
| losses whose `exit == stop` to the cent | **474 of 474** |
| min r recomputed from the stored prices | −1.0000, 0 rows worse |

The last two lines are the finding. The `r` column is not clamped — it agrees
with the prices beside it. The **prices** are the clamp: every losing exit is
booked at the stop price itself. There is no left-tail distribution to describe
because the left tail is a single point mass at −1.0 R.

Outcomes: 538 win / 474 loss / 5 scratch. All 538 scaled rows are wins; all 474
losses are unscaled full stop-outs on the initial stop; the 5 scratches book
≥ 0 R (the stop is tested on the last bar too, so anything still open at the
close is on the good side of its stop).

## 2. The tape — what the triggering close actually was

`python research/x2_stop_floor_audit.py --tape`. Each of the 1,017 rows is
replayed against its archived session with the loader every other W-report uses
(`research.r9_simple_book.Bars` → `p26.load_day`), scanning `entry_i+1` to the
end of RTH for the first bar whose CLOSE is beyond the initial stop — the
identical predicate `backtest_week._stop_hit` runs under `STOP_ON_CLOSE=1`.
0 gaps: 0 missing days, 0 out-of-range indices, 0 zero-risk rows.

**Self-check.** For a row the book charged a full −1.000 R the exit bar must BE
that first close-beyond-stop bar, so `hit_i == entry_i + bars`. It agrees on
**472 of 474**; the 2 that differ are off by exactly one bar (`NVDA 2025-04-24`,
`NFLX 2025-01-21`) and are the half-cent artefact P26 already named — the book
stores entry/stop at 2 dp while the engine ran at full precision.

### The left tail that actually printed

Close-fill R on the 474 booked stop-outs, unfloored:

| statistic | value |
|---|---:|
| min | **−4.3571 R** |
| p1 | −3.5882 R |
| p5 | −2.4595 R |
| median | **−1.3500 R** |
| mean | −1.4913 R |
| worse than −1.00 R | **458 of 474 (96.6%)** |
| worse than −1.25 R | **301 of 474 (63.5%)** |

Widening to all 815 rows whose initial stop was breached at some point in the
session (including scaled winners whose runner was already at break-even):
min −4.8000 R, median −1.3158 R, **777 past 1 R, 473 past 1.25 R**.

### Worst 10

| sym | day | et | side | entry | stop | trigger close | close-fill R | min after entry |
|---|---|---|---|---:|---:|---:|---:|---:|
| BABA | 2025-04-10 | 09:38 | L | 107.32 | 107.04 | 106.10 | **−4.3571** | 2 |
| PLTR | 2024-11-25 | 10:04 | L | 67.00 | 66.89 | 66.55 | −4.0909 | 8 |
| AMD | 2026-04-20 | 09:46 | L | 282.18 | 281.75 | 280.48 | −3.9535 | 2 |
| INTC | 2026-07-13 | 09:45 | S | 103.96 | 104.16 | 104.75 | −3.9500 | 3 |
| IREN | 2026-02-10 | 09:39 | L | 46.46 | 46.32 | 45.93 | −3.7857 | 2 |
| HOOD | 2025-08-14 | 09:49 | S | 107.89 | 108.06 | 108.50 | −3.5882 | 2 |
| INTC | 2026-06-17 | 10:05 | S | 119.01 | 119.19 | 119.64 | −3.5278 | 7 |
| PLTR | 2026-06-17 | 10:20 | L | 135.50 | 135.28 | 134.76 | −3.3409 | 4 |
| META | 2025-02-07 | 10:35 | L | 717.00 | 715.73 | 712.92 | −3.2126 | 18 |
| COIN | 2025-07-10 | 10:22 | L | 374.00 | 373.26 | 371.64 | −3.1892 | 3 |

The shape is consistent: the stop is 11–74 cents from entry and the very next
minute or two travels several times that. **It is not a gap-open phenomenon and
it is not a rare one** — the median trade is 35% past its own stop.

### Who it lands on

By Austin's grade (denominators are the traded rows in that grade):

| sgrade | traded | booked losses | past 1 R | rate |
|---|---:|---:|---:|---:|
| S | 128 | 43 | 40 | **93.0%** |
| A | 251 | 113 | 109 | 96.5% |
| C | 638 | 318 | 309 | 97.2% |

By setup: break_and_retest 425 · one_candle_rule 32 · reentry_84_rule 1. By
level: pivot low 90 · pivot high 68 · OR low 67 · OR high 60 · PML 52 · PMH 45 ·
PDH 23 · PDL 20 · other 33. By symbol (booked losses, of which past 1 R): COIN
53/52 · MU 42/41 · TSLA 38/38 · PLTR 38/36 · AMD 32/32 · IREN 30/30 · HOOD 29/29
· AVGO 31/28 · NVDA 22/22. Only **SPY (1 loss, 0 past 1 R)** escapes it, on a
sample of one — below `universe.MIN_SAMPLE_N = 20` and not readable.

**There is no clean subset.** This is not a per-symbol or per-grade defect to
filter out; it is what a 1-minute close does relative to a stop this tight.

### What honouring the rule costs

Applying the close fill only to the 474 rows the book charged a full stop-out
(every other row keeps its booked R):

| arm | mean R | delta | vs error bar | S mean R (n=128) | months green |
|---|---:|---:|---:|---:|---:|
| booked (shipped) | **+0.9551** | — | — | +1.2829 | 23 / 25 |
| close fill, floored at −1.25 R | **+0.8644** | **−0.0907** | **9.5×** | +1.2250 | 23 / 25 |
| close fill, unfloored | **+0.7261** | **−0.2290** | **24×** | — | — |

Both deltas clear the narrow bar. The gap to the 2.0 R money gate widens from
**1.0449 R to 1.1356 R**. Durability does not move (23/25 either way) and the
S-grade edge survives (+1.2250 R).

**The floor is worth +0.1383 R of book mean** — the distance between the two
correction rows — and it is the single largest thing in this report that is
straightforwardly *fixable* rather than merely *true*.

## 3. The code audit

Every path that can realise worse than −1.0 R, traced. Four findings, one of
them a bug that is now fixed.

### 3.1 `backtest_week.py` — the shipped rig — has no floor, because it cannot need one

`_stop_hit` (`backtest_week.py:280`) triggers on the close via
`stop_rule.stop_hit_on_close`. All three exit sites then fill at the stop:

- `:416` `_ladder_bar` pre-scale — `t.outcome, t.exit_price = "loss", t.stop`
- `:431` `_ladder_bar` runner — `t.exit_price = t.stop if (PESSIMISTIC_FILL and hit_target) else stop_lv`
- `:611` non-ladder — `t.outcome, t.exit_price = "loss", t.stop`

`SimTrade.pnl` then computes `move / risk` with `risk = abs(self.entry - self.stop)`.
So a full stop-out is **exactly −1.000 R by construction**, and the string
`1.25` does not appear in `backtest_week.py` at all. **The −1.25 R floor is the
5th instance of this repo's unreachable-rule class** (after `break_then_rejection`,
T4(b)'s failed-entry scratch, `before11`, and the OCR order-block demotion): a
stated rule compiled into a branch that can never be true.

**Two committed documents disagree about the rule itself**, and this is the
thing to settle:

| source | the rule |
|---|---|
| `CLAUDE.md`, "Rules that hold everywhere" | *"Stops trigger on the candle CLOSE, **fill at that close**, floored at −1.25R."* |
| rule ballot q1 (2026-08-23), quoted in `research/exit_lab.py:50` | *"a 1m candle close below is exit, **max slippage −1.25r**"* |
| `stop_rule.py` docstring | *"The trigger moves to the close; **the FILL does not**. Austin's stop order still rests at the level… That is why neither caller needs the −1.25R floor as live code."* |

The first two describe a market exit on the close and are why a −1.25 R floor
exists at all — **a resting stop order triggered by a close can never slip to
−1.25 R, so the floor is meaningless under `stop_rule.py`'s reading.** The floor's
existence is itself evidence for the close fill. `research/exit_lab.py` obeys the
close fill; `backtest_week.py` and `paper_trader.py` obey the resting order. Same
repo, same rule, two answers.

### 3.2 `research/exit_lab.py` — floored on every tranche, and the denominator is never re-based

- `_stop_fill` (`:172`) clamps at `entry ∓ MAX_LOSS_R * risk`, `MAX_LOSS_R = 1.25`.
- `scale_out` calls it for **tranche 1** (`:280`) and `_runner_exit` calls it for
  the **break-even/trail stop** (`:326`, `:369`). Both tranches are floored.
- **Not re-based.** Every leg scores through `realised_r(entry, stop, px, side)`
  with the ORIGINAL entry and stop, and `scale_out` returns `w1*r1 + w_rest*r_rest`.
  There is no path where the runner's R is measured against a shrunk denominator.
  Same in `backtest_week.SimTrade.pnl`: `risk = abs(self.entry - self.stop)`, used
  for both the scale leg and the runner leg.
- `hod_only`'s off-by-one (the stop not live on the HOD exit bar, worst −1.4013 R
  on 5 of 1,017 rows), reported unfixed in `research/w13_scaling.md` §9, **was
  fixed at `f4b9e075`** and is covered by `test_runner_stop.py::hod_bar_craters`.
  Verified green here.
- **One dead parameter, flagged not fixed.** `_stop_fill(bars, i, entry, stop, side, risk)`
  never reads `stop`. That makes the floor a *total-loss* floor (−1.25 R from
  entry) rather than a slippage floor relative to whichever stop fired, so a
  break-even stop can still fill 1.25 R below entry. That matches ballot q1's
  "max slippage −1.25r" reading of the whole trade, so it is left alone — but an
  unread parameter is how a rule quietly changes meaning, and it should either be
  removed or documented at the call site.

### 3.3 `paper_trader.py` — the break-even stop filled a full 1R below break-even (FIXED)

`PaperPosition.exit_for` raises the runner's stop to the entry price when Rule 6's
break-even scale fires (`self.runner_stop = self.stock_entry`), and then returned
**`self.stop_premium`** — the premium at the ORIGINAL stock stop — when that
break-even stop triggered:

```python
if stop_hit_on_close(close, self.runner_stop, long):
    return self.stop_premium, "stop"       # <- the bug
```

The runner's stop was at 0 R and the fill was booked at −1 R. On the test plan
(TSLA call, entry $2.00, stop $1.65, 5 contracts, Rule 6 scaling 50%) the runner
booked **−$105.00** on a stop resting at break-even; the put plan booked
**−$100.00**. **This is Austin's exact complaint — "some stops are going past 1R"
— in the live path**, and it is the same bug class `research/test_runner_stop.py`
was written for: *a stop computed and then not applied to the tranche it governs*.

Fixed at `paper_trader.py:153` to return `self.entry_premium`.
`research/test_x2_stop_floor.py::check_be_stop_fill` is **red before, green
after** (4 assertions, call and put). `_check_stop` is untouched — that one is
the ORIGINAL stop and `stop_premium` is the right price there.

**Scope, stated honestly:** `RULE6_ENABLED = False` in `paper_trader.py:33`, so
this path is off in the shipped live config and no journal row is wrong today. It
is a latent bug on a flag Austin's own stated management (scale at HOD/BE) would
turn on. `research/test_paper_trader_stop.py` (18 checks) and
`paper_trader.py`'s own self-test both still pass.

`backtest_week._ladder_bar:431` is the mirror image of this in the backtest and
is **deliberate and documented** (omen-5.1 T2: a bar that tagged the runner
target and still closed beyond the stop books at the ORIGINAL stop). Left alone;
it is a pessimism knob (`PESSIMISTIC_FILL`), not a mis-priced fill, and it cannot
take a trade past −0.5 R because the scale leg is already ≥ 0.

### 3.4 `OMEN_SSCORE_SIZING=1` books `r` past −1.25 R, and it is sizing, not slippage

`SimTrade.pnl` multiplies by `sscore_mult(reason)` (1.0 / 1.25 / 1.5x at S4 / S5 /
S≥6) and `backtest_2y.py:171` then writes `"r": round(t.pnl / RISK_DOLLARS, 3)`
against a **fixed** $1,000. Measured directly:

| S-score | pnl on a full stop-out | `r` as written |
|---|---:|---:|
| S4 | −$1,000.00 | −1.000 |
| S5 | −$1,250.00 | −1.250 |
| S6 | −$1,500.00 | **−1.500** |
| S7 | −$1,500.00 | **−1.500** |

Default is OFF (`SSCORE_SIZING = os.environ.get("OMEN_SSCORE_SIZING", "0") == "1"`),
so the shipped book is unaffected — the audit confirms 0 of 45,193 rows past
−1.0 R. But **any report run with that flag on shows a left tail past the floor
that is position size, not slippage**, and no floor can stop it because the
multiplier is applied after the R is formed. That inverts `CLAUDE.md`'s
*"R-multiples are the result; dollars are a sizing skin."* The `r` column should
divide by the trade's own risk dollars, or the flag should be documented as
making `r` non-comparable.

### 3.5 The three specific questions, answered

- **Gap through the stop?** Cannot book past −1.0 R in `backtest_week` (fills at
  `t.stop` however far the bar ran). `exit_lab` books the close and floors at
  −1.25 R — pinned by `test_x2_stop_floor.py::check_gap_through_stop`, a bar
  closing 6.00 R through the stop, all four policies × both sides return exactly
  −1.2500 R.
- **Same-bar stop and target?** Both rigs give the bar to the stop
  (`backtest_week:611` comment *"both in one bar -> conservative: loss"*;
  `exit_lab._stop_hit_first` runs first). Pessimistic in outcome, optimistic in
  price.
- **11:00 backstop?** `backtest_week` has no 11:00 force-flat at all — `ENTRY_CUTOFF`
  stops new entries and open positions are managed to the last RTH bar, scratching
  at `candles[-1].close`. The stop is tested on that final bar first, so a scratch
  is always on the good side of its stop; all 5 book ≥ 0 R. `exit_lab`'s
  `CLOCK_BAR = 90` exit is likewise preceded by the stop check on the same bar.
  Neither can book a close far beyond the stop through the clock.
- **`ENTRY_SCRATCH`?** Clamped: `return max(c.close, t.stop)` (`backtest_week:373`).
  Never worse than the stop-out it replaces. Default OFF regardless.

## 4. Max drawdown

`python research/x2_stop_floor_audit.py --dd`. Equity curve in R, 1 R per trade,
chronological, no compounding.

| ordering / fill | total R | max DD | over | window | longest losing streak |
|---|---:|---:|---:|---|---:|
| booked, by entry time | +971.38 | **11.44 R** | 17 trades | 2025-08-29 → 2025-09-15 | 7 |
| booked, by exit time | +971.38 | **11.44 R** | 17 trades | 2025-08-29 → 2025-09-15 | 7 |
| close fill floored −1.25 R | +879.10 | **14.49 R** | 26 trades | 2025-08-22 → 2025-09-15 | 7 |
| close fill unfloored | +738.48 | **19.34 R** | 40 trades | 2025-05-08 → 2025-06-26 | 7 |

Entry-time and exit-time ordering give the identical curve, so the answer is not
an artefact of when P&L is credited.

**The deepest drawdown is 17 trades: 3 wins and 14 losses, worst single trade
−1.000 R.**

So, plainly: **max DD is a PORTFOLIO phenomenon in this book, not a per-trade
one.** Austin's *"max dd if thats rr loss its slipping back 1r"* conflates two
different problems:

1. **A run of full stop-outs.** 474 of 1,017 trades lose, the longest losing
   streak is 7, and 14 of 17 consecutive trades lost in the worst stretch. No
   change to the stop fill fixes this; it is selection and it is the same
   constraint every exit sweep in this repo has landed on.
2. **Per-trade slippage past 1 R.** Real, measured above at 96.6%, and invisible
   in the book. It does not *cause* the drawdown — it **deepens** it by
   **+3.05 R (11.44 → 14.49)** with the floor honoured, and by **+7.90 R
   (11.44 → 19.34)** without it.

Both are true. They need different fixes, and only the second is a code change.

## 5. What this does not say

- **No shipped default was changed and no published figure moved.** The only
  behaviour change in this lane is `paper_trader.py:153`, on a path gated OFF by
  `RULE6_ENABLED = False`. `research/g3_arm_ow1.json` is untouched and every
  number in §1 is read from it as committed.
- **The +0.8644 R correction is not a new book.** It is the shipped book with 474
  rows re-priced at their own trigger bar's close; the other 543 rows keep their
  booked R exactly. A real close-fill replay would also change which trades exist
  (a stop that fills worse changes nothing about entry, but `_arm_84` and the
  ladder's scale rung read outcomes), so treat −0.0907 R as **a lower bound on the
  cost, priced on a matched row set**, not as the arm's mean.
- **It does not settle which fill is right.** That is the `CLAUDE.md` /
  `stop_rule.py` contradiction in §3.1 and it is Austin's call: it moves every
  R-multiple this repo has ever published, in one direction, by roughly a tenth
  of an R.
- **It does not model options slippage.** Everything here is the stock tape. On an
  options book a −4.36 R stock close is worse still, and 1-minute OHLCV cannot say
  what the spread was.
- **It is in-sample over the whole two years.** No held-out split; there was no
  parameter to fit, so there is nothing to overfit — but the S-grade rate (93.0%)
  rests on 43 booked losses and should not be read as different from A or C.
- **The two self-check mismatches were not root-caused past the half-cent
  hypothesis.** Both are ±1 bar and neither is in the worst 20.

## 6. Provenance

| artefact | what it is |
|---|---|
| `research/x2_stop_floor_audit.py` | the three sections; `--json` dumps every number above |
| `research/test_x2_stop_floor.py` | 19 assertions: break-even fills, the gap floor, the `backtest_week` convention |
| `research/g3_arm_ow1.json` | the book, `g3_onwatch_2y.py` at `47e60796` |
| `research/exit_lab.py`, `stop_rule.py`, `backtest_week.py`, `paper_trader.py` | the audited paths |
| `research/test_runner_stop.py`, `research/test_paper_trader_stop.py` | pre-existing, re-run green |
| commit | `c089b26b` |
