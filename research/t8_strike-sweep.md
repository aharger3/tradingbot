# T8 — Strike Sweep

Austin: *"0DTE and 1DTE, ATM+/-1 strike"* (R29). Nothing in the engine has ever picked a
strike or an expiry — this is the first report that names, per signal, the contract, the
contract count at $1,000 planned risk, and the premium stop. Script:
`research/t8_strike_sweep.py`. Run it with `python research/t8_strike_sweep.py` (full report)
or `--selfcheck`.

## Null result: no strike/expiry combination beats 0DTE-ATM outside its own error bar

All six arms — {0DTE, 1DTE} × {ATM-1, ATM, ATM+1} — land inside a ±0.16R 95% bootstrap bar of
the 0DTE-ATM baseline. The largest gap is **1DTE ATM at +0.0037R**, indistinguishable from
zero. **Do not read "1DTE ATM has the highest mean R" as a finding — it is noise.** The
strike/expiry axis, on this book, does not move the money gate.

Held-out recall is unaffected by construction: T8 is a pricing skin on an already-selected
book (same rows in, same rows out), and `--selfcheck` verifies `black_scholes.py` /
`options_sizer.py` / this file are absent from the detection path
(`backtest_2y.py`/`backtest_week.py`/`signal_runner.py`).

## The sweep (2,595-trade ratified book, prior-session sigma, IV 1.2x, `--selfcheck` pinned)

| expiry | strike | n | mean R | median R | win% | se (boot, 95%=1.96×se) | tick-floored | months green |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0DTE | ATM-1 | 2,592 | +0.5235 | -1.0009 | 30.5% | 0.0561 | 14.9% | 25/25 |
| 0DTE | ATM   | 2,592 | +0.5674 | -1.0161 | 30.7% | 0.0602 |  6.0% | 25/25 |
| 0DTE | ATM+1 | 2,592 | +0.5256 | -0.9330 | 30.5% | 0.0571 | 18.8% | 24/25 |
| 1DTE | ATM-1 | 2,592 | +0.5388 | -1.0034 | 30.6% | 0.0531 | 11.8% | 25/25 |
| 1DTE | ATM   | 2,592 | +0.5712 | -1.0115 | 30.7% | 0.0554 |  4.7% | 25/25 |
| 1DTE | ATM+1 | 2,592 | +0.5454 | -1.0039 | 30.6% | 0.0540 | 13.1% | 25/25 |

(3 of 2,595 rows have no earlier archive session and are dropped from every arm — cannot
price without a prior session to build sigma from.)

**Every pairwise gap against 0DTE ATM is inside its own bar**: 0DTE ATM-1 -0.0440R (±0.161),
0DTE ATM+1 -0.0418R (±0.163), 1DTE ATM-1 -0.0287R (±0.157), 1DTE ATM +0.0037R (±0.160), 1DTE
ATM+1 -0.0220R (±0.159). None clears its bar. **Month greenness is tied at 25/25 across 5 of
the 6 arms** (only 0DTE ATM+1 drops to 24/25) — greenness does not discriminate either.

**Read the median, not the mean, on every arm.** All six medians sit near -1.0R: on this book
the *typical* 0DTE/1DTE contract trade is close to a full loss of premium, and the positive
mean is carried entirely by a right-tail of convex winners (30.5–30.7% win rate on all six
arms — strike/expiry choice barely moves who wins, only how much). This matches
`research/t2_options_tape.py`'s own warning verbatim ("READ THE MEDIAN, NOT THE MEAN... off
ATM the premium risk can collapse") and this report re-confirms it independently on the
strike/expiry axis rather than quoting it.

**The min-tick floor is load-bearing.** Far-OTM strikes (ATM+1, especially on cheap/low-vol
names) can price under $0.05 in this model; `options_sizer.build_options_plan`'s own $0.05
minimum-tick guard is applied here identically (not a new rule) so a sub-cent model price
cannot manufacture an unfillable 4,000+ contract "trade." Before the guard was applied, the
raw mean R for 0DTE ATM+1 read **+0.8426R** — that number was an artifact of the guard being
absent, not a real edge, and it is why the guard belongs in every strike-sweep, not just the
live sizer.

## Representative signals — contract, count @ $1,000 planned risk, premium stop

0DTE ATM cards, one per setup family, prior-session sigma, IV 1.2x:

| sym | day | dir | setup | entry | stop | strike | premium | stop $ | premium risk | contracts @ $1k |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| AAPL | 2024-08-23 | call | break_and_retest | 227.37 | 226.99 | 227.50 | 1.16 | 0.98 | 0.18 | 57 |
| CRM | 2026-07-29 | call | break_and_retest | 184.19 | 183.79 | 185.00 | 0.73 | 0.59 | 0.14 | 69 |
| NFLX | 2025-10-13 | put | break_and_retest | 121.91 | 122.31 | 122.50 | 1.12 | 0.89 | 0.23 | 43 |
| AAPL | 2024-08-21 | call | one_candle_rule | 227.36 | 227.15 | 227.50 | 0.40 | 0.31 | 0.09 | 113 |
| GOOGL | 2025-10-16 | call | one_candle_rule | 254.77 | 254.33 | 255.00 | 1.50 | 1.30 | 0.20 | 49 |
| NFLX | 2026-05-26 | put | one_candle_rule | 87.89 | 88.13 | 87.50 | 0.33 | 0.25 | 0.08 | 122 |
| AAPL | 2024-12-16 | put | reentry_84_rule | 249.21 | 249.47 | 250.00 | 1.24 | 1.07 | 0.16 | 61 |
| GOOGL | 2026-04-30 | put | reentry_84_rule | 369.73 | 371.41 | 370.00 | 3.37 | 2.59 | 0.79 | 12 |
| NFLX | 2026-03-10 | put | reentry_84_rule | 97.42 | 97.58 | 97.50 | 0.70 | 0.62 | 0.08 | 125 |

All 6 arms on the same four cards (illustrating the axis Austin asked for):

| sym | day | expiry | strike | premium | stop $ | contracts @ $1k |
|---|---|---|---|---:|---:|---:|
| AAPL | 2024-08-23 | 0DTE | ATM-1 | 2.75 | 2.46 | 34 |
| AAPL | 2024-08-23 | 0DTE | ATM | 1.16 | 0.98 | 57 |
| AAPL | 2024-08-23 | 0DTE | ATM+1 | 0.33 | 0.27 | 145 |
| AAPL | 2024-08-23 | 1DTE | ATM-1 | 3.19 | 2.93 | 37 |
| AAPL | 2024-08-23 | 1DTE | ATM | 1.70 | 1.52 | 55 |
| AAPL | 2024-08-23 | 1DTE | ATM+1 | 0.76 | 0.66 | 98 |
| CRM | 2026-07-29 | 0DTE | ATM-1 | 2.13 | 1.85 | 35 |
| CRM | 2026-07-29 | 0DTE | ATM | 0.73 | 0.59 | 69 |
| CRM | 2026-07-29 | 0DTE | ATM+1 | 0.15 | 0.10 | 200 (tick-floored) |
| CRM | 2026-07-29 | 1DTE | ATM-1 | 2.54 | 2.28 | 38 |
| CRM | 2026-07-29 | 1DTE | ATM | 1.19 | 1.03 | 62 |
| CRM | 2026-07-29 | 1DTE | ATM+1 | 0.44 | 0.36 | 132 |
| NFLX | 2025-10-13 | 0DTE | ATM-1 | 0.17 | 0.11 | 179 |
| NFLX | 2025-10-13 | 0DTE | ATM | 1.12 | 0.89 | 43 |
| NFLX | 2025-10-13 | 0DTE | ATM+1 | 3.14 | 2.77 | 27 |
| NFLX | 2025-10-13 | 1DTE | ATM-1 | 0.41 | 0.32 | 112 |
| NFLX | 2025-10-13 | 1DTE | ATM | 1.45 | 1.23 | 45 |
| NFLX | 2025-10-13 | 1DTE | ATM+1 | 3.29 | 2.96 | 29 |
| AAPL | 2024-08-21 | 0DTE | ATM-1 | 2.37 | 2.16 | 48 |
| AAPL | 2024-08-21 | 0DTE | ATM | 0.40 | 0.31 | 113 |
| AAPL | 2024-08-21 | 0DTE | ATM+1 | 0.01 | 0.01 | 200 (tick-floored) |
| AAPL | 2024-08-21 | 1DTE | ATM-1 | 2.42 | 2.23 | 52 |
| AAPL | 2024-08-21 | 1DTE | ATM | 0.61 | 0.52 | 107 |
| AAPL | 2024-08-21 | 1DTE | ATM+1 | 0.05 | 0.01 | 200 (tick-floored) |

Reading these cards: ATM+1 buys the most contracts for the same $1,000 because the premium is
cheaper, but the "stop $" is compressed by the same min-tick floor — the modelled premium risk
per contract cannot go below $0.05, so once premium itself is near a nickel the displayed stop
premium and the true risk stop diverge (a real artifact of a model with no bid-ask, not a
trading rule).

## What is modelled, what is quoted

**Nothing here is quoted from a real options tape.** There is no options tape in this repo —
Polygon 403s the options snapshot endpoint, and the Tastytrade sandbox adapter
(`broker/tastytrade.py`, landed 2026-08-24) has never completed a live round trip. Every
number above is:

- **Price**: `black_scholes.py`, textbook Black-Scholes-Merton, r = q = 0, flat vol surface,
  no smile, no term-structure jump for the extra day on 1DTE.
- **Volatility**: Parkinson vol of the **prior session's** RTH high-low range
  (`data_archive/<SYM>/<DAY>.csv`, the session strictly before the trade day) × 1.2 — the same
  IV multiplier `t2_options_tape.py` uses as its headline arm. This is ex-ante by
  construction: nothing on the trade day itself feeds sigma, which is the "prior-session sigma
  only" instruction in the ticket, and differs from `t2_options_tape.py`'s own headline arm
  (which uses the full trade-day range, a look-ahead T2 flags in its own A2 section).
- **Strike grid**: `options_sizer.STRIKE_INCREMENT`, 11 symbols named explicitly; every other
  symbol falls back to a flat $2.50 step. That fallback is an assumption for the 16 unnamed
  symbols in the book, not a quote.
- **1DTE's extra day**: +390 RTH minutes added to time-to-expiry at both entry and exit, with
  **no overnight vol scaling and no weekend/holiday calendar correction** — a Friday 1DTE
  really spans three calendar days and is priced here as if it spans one extra session. This
  is the single largest unmeasured gap in the 1DTE arm.
- **Fill**: mid, zero spread, no commission, no market impact, continuous contract size —
  identical to every other assumption in `t2_options_tape.py`'s A5/A9, not re-litigated here.
- **Min-tick floor**: $0.05, `options_sizer.build_options_plan`'s own guard, applied
  identically rather than invented — without it the far-OTM arms' means are pure numerical
  artifact (see above).

## Verification

- `python research/t8_strike_sweep.py --selfcheck` — book fingerprint pinned to the T0-ratified
  book (n=2,595, mean R +0.5481, matching T0's headline exactly); detection path proven not to
  import this file or its pricing modules; contract counts non-negative; time-to-expiry
  positive on all 6 arms; ATM-1 < ATM < ATM+1 strike ordering holds.
- `python research/regression_gate.py` — PASS (unaffected; this track touches no detection
  code, see selfcheck item 1).

## Bottom line for Austin

- **The strike/expiry choice is not where the money gate lives.** All six arms of {0DTE,
  1DTE} × {ATM-1, ATM, ATM+1} land inside noise of each other. If he wants a strike/expiry
  default to ship, **0DTE ATM** is the reasonable pick — not because it wins the sweep (it
  doesn't, nothing does), but because it has the lowest tick-floor rate (6.0%, meaning the
  fewest rows where the model's premium collapses to an unfillable size) and ties the
  greenness leaders.
- **The typical trade loses most of its premium** (median R near -1.0 on every arm); the book
  is profitable in expectation only because of a right-tail of convex winners. That is the
  real behavior of a 0DTE/1DTE ATM options book and is not new to this track
  (`t2_options_tape.md` found the same shape) — T8 confirms it holds across the strike axis
  too, not just at-the-money.
- austin_blocker: **there is still no real options tape to check any of this against.**
  Sandbox Tastytrade auth (`broker/tastytrade.py`) has never completed a live round trip. The
  concrete action: authorize one real sandbox session (log into the Tastytrade sandbox once,
  confirm a quote comes back) so a future track can replace "modelled" with "quoted" on at
  least one contract.
