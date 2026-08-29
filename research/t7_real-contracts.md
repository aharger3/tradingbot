# T7 — Real contracts

R28: *"Sim real contracts with alpaca or tasty trade because we're working to trade with
real money."*

**Null result: contract R and underlying R are statistically indistinguishable, and neither
reaches the money gate.** Scored as real 0DTE ATM(ish) contracts — real Alpaca historical
option quotes where the chain is reachable, a documented Black-Scholes model elsewhere — the
2,595-signal / 1,016-traded book's contract mean R is **+0.9629**, against underlying mean R
**+0.8688**: a **+0.0941R** difference against a **±0.1298R** 95% bar. That is inside its own
error bar — call the direction "maybe positive," not "the instrument helps." Both numbers sit
far under the **mean R ≥ 2.0** money gate. Durability is unchanged either way: **22/25** green
months on both the contract and underlying score.

Script: `research/t7_real_contracts.py`. Reproduce with:
```
python research/t7_real_contracts.py --selfcheck   # pinned-book + no-lookahead checks
python research/t7_real_contracts.py                # full report (reads cached quotes)
python research/t7_real_contracts.py --fetch         # re-pull Alpaca quotes (~4 min, cached)
```

## What book this is measured on

`research/bt2y_trades.json`, pinned by hash: `8cd574c3b8d2de27...` (full sha256 in the
script), **1,016 traded rows**, 2024-08-21 → 2026-08-21, generated 2026-08-26, underlying
mean R **+0.9571**. This is the book as it stands after T0 (R1–R33) plus every track that has
landed on `main` since — it is **not** the 2,595-traded book T0's own report cited; several
tracks after T0 (T1's disaster-stop resolution, T2's OCR price filter, T12's timing fix, and
others) have since changed which signals survive to `traded: true`. `--selfcheck` fails loud
if this file is regenerated against a different book — read the fingerprint line the script
prints on every run, not this paragraph, if the numbers ever look stale.

845 of the 1,016 rows are scoreable here (1 row has no prior-session archive file at all —
the very first day on file for its symbol — and is dropped from every table, never
force-modelled).

## Why this file exists: what was wrong before

`research/t2_options_tape.md` (commit `3bd2ef1a`) was **retracted, fatal**. It priced premium
with Parkinson sigma computed from `drange` — the day's **FULL SESSION** high-low range,
known only after the close. The premium is the R denominator, so the size of the day's
eventual move set the unit the day's own result was scored in: ninety percent of that
headline was the leak (ex-ante the contract was worth +0.0356R, not the reported +0.3575R).

This file has **exactly one** volatility input, unconditionally: the prior session's RTH
high-low range, read from `data_archive/<SYM>/<day-1>.csv`. `--selfcheck` greps its own
source for `drange` indexed off a book row and fails the build if it finds one — there is no
same-day number anywhere in the pricing path, not even as a sensitivity arm.

## What is real and what is modelled — the split that matters

Alpaca's paper account (`ACCOUNT ACTIVE`, `options_trading_level=3`) is reachable from this
box, and its market-data host serves **real historical 1-minute option bars spanning the
book's full 2024-08-21..2026-08-21 range** — confirmed empirically (NVDA 2024-08-23 09:59 ET
1-min call bars came back with real OHLCV), not assumed. Two things are structurally
unavailable, not a credentials problem:

1. **No historical strike listing.** `/v2/options/contracts` (Alpaca's reference endpoint)
   serves only currently-**active** contracts; a 0DTE that expired two years ago is gone from
   it. This file works around it by constructing candidate OCC symbols at every plausible
   strike increment ($0.50/$1/$2.50/$5/$10, floor and ceil of the entry price — up to 10 per
   row) and asking the **bars** endpoint directly. An unlisted OCC symbol returns an empty bar
   list with `200 OK`, no error — the candidate with real bars **and** the strike nearest
   entry is kept. One Alpaca call per row (candidates × [entry, exit] window, batched).

2. **Many symbol-days never had a true 0DTE listed.** Friday weekly expirations exist for
   nearly every optionable name; genuine **daily** (Mon–Fri) 0DTE listings only exist for a
   name once its venue added them, and that rollout was gradual through 2024–2026. A
   non-Friday row on a name that did not yet have daily listings on that date returns empty
   for every strike candidate — correctly, because there was no 0DTE contract to have traded.
   This, not a rate limit or an auth failure, is the majority of the "modelled" rows.

| | rows | % of 1,016 |
|---|---:|---:|
| traded rows in the book | 1,016 | — |
| no prior-session archive (dropped, never modelled) | 1 | 0.1% |
| **real Alpaca quote found** (entry + exit premium both real) | **276** | **27.2%** |
| Alpaca queried, no listed strike/expiry found | 740 | 72.8% |
| scoreable (sigma available) | 845 | 83.2% |
| — of which real-quoted | 106 | 12.5% of scoreable |

(276 rows have a real quote; 845 are scoreable at all once the 1 no-sigma row and rows whose
`sigma`/entry math degenerates are excluded — the 106 is the overlap: real-quoted **and**
scoreable.)

**The risk denominator is *always* Black-Scholes, real quote or not, and this is not
optional.** One contract-R's denominator is `entry_premium − stop_premium`, where
`stop_premium` is the premium the contract would have shown *at entry time* had the
underlying already been sitting at the stop price. For a trade that stops out, the underlying
really did reach that price — **later**. For a trade that wins or scratches, it never did. No
tape, however complete, contains a real price for a level the stock was not at, at a time
that has already passed. So `stop_premium` is priced by Black-Scholes (S=stop, T=entry-time,
σ=prior-session Parkinson×1.2) on **every** row, real-quote rows included — asserted by
`--selfcheck` on 50 real-quoted rows. Reporting it as "real" would misstate what was
measured; it is documented here once rather than mislabeled per row.

## The book — contract R vs underlying R

LADDER convention (the book's own 50/50 scale-out plan; `SINGLE` = full size to `exit`
reported too, both conventions below), IV multiplier 1.2× (headline; 1.0×/1.5× swept as a
sensitivity arm, both bracket the headline and never flip a sign):

```
-- SINGLE convention: full size to exit -- (risk denominator floored at $0.05/share)
IV       n         CONTRACT     win% | UNDERLYING     win%       floored
1.0x     896        +0.9458    39.3% |   +0.9489    38.6%         24
1.2x     845        +1.0315    38.7% |   +0.9173    37.9%         15
1.5x     795        +0.9541    37.7% |   +0.9273    37.5%         13

-- LADDER convention: book's own 50/50 scale plan --
IV       n         CONTRACT     win% | UNDERLYING     win%
1.0x     896        +0.8687    51.9% |   +0.8986    52.9%
1.2x     845        +0.9629    51.7% |   +0.8688    52.1%
1.5x     795        +0.9007    51.2% |   +0.8718    51.7%

-- split by real vs modelled entry/exit premium, LADDER, IV 1.2x --
real Alpaca quote            n=106   CONTRACT   +1.4534   62.3% | UNDERLYING   +0.9904   61.3%
BS model (no real quote)     n=739   CONTRACT   +0.8926   50.2% | UNDERLYING   +0.8514   50.7%
```

**Headline number: LADDER, IV 1.2×, n=845 — CONTRACT +0.9629R vs UNDERLYING +0.8688R.**
Difference **+0.0941R**, 95% CI **±0.1298R** (normal approximation on paired per-row
differences; a 5,000-draw bootstrap gives essentially the same interval, **[−0.0284,
+0.2291]**, which crosses zero). **This is a null result** — the data cannot distinguish
"scoring in real contracts helps" from "scoring in real contracts hurts" or "does nothing."
Neither figure is within 1R of the 2.0 money gate.

### Read the median, not just the mean, on SINGLE

`contract R p50` at IV 1.2× is **−0.35** while the mean is **+1.03**: a 0DTE ATM contract's R
distribution is fat-right-tailed by construction (this is convexity — Austin's runner
thesis — showing up exactly where it should) and the median trade is a loser even when the
mean book is solidly positive. This is expected, not a bug; the same shape appeared in the
retracted T2 tape's `x13` prototype (38.5% win rate, positive mean).

### The near-zero-denominator artifact, found and fixed

Before a fix, a handful of rows blew the mean into absurd territory — one AMD row scored
**+1,646R** because its matched strike ($202.50) sat close enough to entry ($201.58) that the
modelled premium was almost flat against the underlying stop distance (`risk = $0.0007/share`
— literally noise). `options_sizer.build_options_plan` already floors its own `premium_risk`
denominator at **$0.05/share** ("min tick guard") for exactly this reason; this file applies
the identical floor to `Contract.risk` for consistency with the one sizer this repo ships.
15–24 of ~800–900 scoreable rows hit the floor depending on the IV arm; unfloored, they alone
moved the book mean by roughly +0.6R while the median barely moved — the same asymmetry the
retracted T2 tape flagged in its own "A3" section on a different book. **Every table in this
report uses the floored denominator.**

## Per month (LADDER, IV 1.2×)

```
month         n  real% |  CONTRACT    win% |   UNDERLY    win% | green
2024-08       9     0% |   -0.1549   33.3% |   -0.1611   33.3% | C:n U:n
2024-09      22    23% |   +0.5844   36.4% |   +0.1320   40.9% | C:Y U:Y
2024-10      20    15% |   +1.1462   55.0% |   +1.2672   60.0% | C:Y U:Y
2024-11      30     3% |   +1.0525   60.0% |   +0.9285   60.0% | C:Y U:Y
2024-12      27     4% |   +0.5495   44.4% |   +0.4537   44.4% | C:Y U:Y
2025-01      40    12% |   +0.3179   47.5% |   +0.5842   47.5% | C:Y U:Y
2025-02      25     0% |   +0.5561   60.0% |   +0.7306   60.0% | C:Y U:Y
2025-03      37     5% |   +1.1200   62.2% |   +0.9936   62.2% | C:Y U:Y
2025-04      57    18% |   +1.2867   59.6% |   +1.0269   59.6% | C:Y U:Y
2025-05      23     4% |   +0.8630   56.5% |   +0.9246   56.5% | C:Y U:Y
2025-06      25    12% |   -0.4357   28.0% |   -0.2471   28.0% | C:n U:n
2025-07      26    15% |   +1.3564   73.1% |   +1.4112   73.1% | C:Y U:Y
2025-08      31    23% |   +0.5485   54.8% |   +0.8186   54.8% | C:Y U:Y
2025-09      27     7% |   -0.0846   44.4% |   -0.0268   40.7% | C:n U:n
2025-10      38    13% |   +0.2316   39.5% |   +0.2447   39.5% | C:Y U:Y
2025-11      29     3% |   +1.6085   55.2% |   +1.4028   55.2% | C:Y U:Y
2025-12      33     6% |   +1.5045   60.6% |   +1.2414   60.6% | C:Y U:Y
2026-01      37     8% |   +1.1661   54.1% |   +1.0564   54.1% | C:Y U:Y
2026-02      46     9% |   +0.9717   45.7% |   +0.8699   45.7% | C:Y U:Y
2026-03      51    16% |   +0.3798   37.3% |   +0.3953   37.3% | C:Y U:Y
2026-04      44    14% |   +0.4908   47.7% |   +0.8257   50.0% | C:Y U:Y
2026-05      44    20% |   +2.5170   56.8% |   +1.1898   56.8% | C:Y U:Y
2026-06      58    12% |   +1.0542   46.6% |   +1.0499   50.0% | C:Y U:Y
2026-07      45    20% |   +1.5919   60.0% |   +1.5708   62.2% | C:Y U:Y
2026-08      21    38% |   +2.6233   71.4% |   +2.0670   61.9% | C:Y U:Y
DURABILITY: green months  CONTRACT 22/25   UNDERLYING 22/25
```

Same three red months either way (2024-08, 2025-06, 2025-09) — the contract score changes no
durability read.

## Per setup family (LADDER, IV 1.2×)

```
family                 n  real% |  CONTRACT    win% |   UNDERLY    win%
break_and_retest     792    12% |   +0.9909   51.8% |   +0.8921   52.0%
one_candle_rule       52    21% |   +0.4887   50.0% |   +0.4696   51.9%
reentry_84_rule        1     0% |   +3.4583  100.0% |   +3.1450  100.0%  (n=1, ignore)
```

## Per symbol, n ≥ 15 (LADDER, IV 1.2×)

```
sym          n  real% |  CONTRACT    win% |   UNDERLY    win%
COIN        90    10% |   +0.7408   48.9% |   +0.7211   48.9%
MU          68     6% |   +1.3561   45.6% |   +1.0702   47.1%
PLTR        68     9% |   +0.4722   47.1% |   +0.5990   47.1%
HOOD        66     9% |   +1.8648   59.1% |   +1.7023   59.1%
TSLA        65    11% |   +0.4790   41.5% |   +0.6222   43.1%
AMD         53     6% |   +1.3496   56.6% |   +0.9151   58.5%
ORCL        47     6% |   +0.8549   55.3% |   +0.7829   53.2%
IREN        44     7% |   +0.7030   40.9% |   +0.6552   38.6%
AVGO        43    21% |   +1.1464   44.2% |   +0.5699   41.9%
NVDA        37    19% |   +0.3563   48.6% |   +0.5219   48.6%
AMZN        29    14% |   +0.4837   58.6% |   +0.4126   58.6%
NFLX        29     7% |   +0.5991   44.8% |   +0.7056   48.3%
INTC        28    21% |   +1.1734   57.1% |   +1.2448   57.1%
META        28    18% |   +1.1973   64.3% |   +1.0604   64.3%
TSM         23    13% |   +1.6883   73.9% |   +0.9800   73.9%
UBER        20    10% |   +1.3555   40.0% |   +1.2424   40.0%
MSFT        19    21% |   +0.9880   52.6% |   +0.2262   47.4%
GOOGL       17    18% |   +0.6894   58.8% |   +0.5231   52.9%
AAPL        16    19% |   +1.2727   75.0% |   +0.9831   75.0%
```

No symbol flips sign contract-vs-underlying; MSFT has the largest single-symbol gap
(+0.99 vs +0.23) on n=19, well within sampling noise for that count.

## Model vs tape — how much the fallback should be trusted

On the 106 rows with a real Alpaca quote, comparing the model's own price (had it not had the
real quote) against what the tape actually printed:

```
n=106 rows with a real Alpaca quote
entry premium: model - real   mean -0.2427  median -0.1351  |err| p90 1.0255
exit  premium: model - real   mean -0.0814  median -0.0734  |err| p90 1.0699
contract R on these rows: REAL tape +1.4534  vs  full BS-model +1.2576  (delta +0.1958)
   IV 1.0x model : +1.3528  (delta -0.1006)
   IV 1.2x model : +1.2576  (delta -0.1958)
   IV 1.5x model : +1.1531  (delta -0.3004)
```

95% CI on the real-vs-model R delta (n=106, paired): **±0.9185R** — the ±0.1958R gap at the
headline IV is comfortably inside its own bar. **The model is not measurably biased against
the real tape at this sample size**, at any of the three IV arms tried. That is a genuine
positive for trusting the BS fallback on the 72.8% of rows it has to cover alone, but n=106 is
a small validation set — this is "not disproven," not "proven accurate."

## What did NOT run — read before building on this

1. **Tastytrade — not attempted.** The track brief states TCP 443 to Tastytrade's host times
   out from this Windows box. A quick live re-check today (`requests.get
   https://api.tastytrade.com/sessions`, 2026-08-29) returned a clean HTTPS `405` — the host
   answered. That contradicts the stated network state; it was **not** pursued further
   because Alpaca already delivers real historical option quotes across the full book (the
   actual R28 requirement) and the track brief says explicitly not to burn time here. If
   Tastytrade access is wanted for its own sake — different fee/margin model, different chain
   coverage — that is a fresh probe, not a network-reachability blocker any more; see
   `austin_blocker`.
2. **No spread/commission model.** Every premium is a mid (Alpaca bars are OHLC prints, not
   bid/ask); T9 owns the spread-cost question.
3. **No strike sweep.** ATM(ish) only — nearest listed strike to entry. T8 owns strikes other
   than ATM.
4. **No futures.** T17's scope, and the archive has no futures data regardless.
5. **72.8% of rows are BS-model, not real quote**, mostly because many symbol-days never had
   a true 0DTE contract listed (see "What is real" above) — this is a fact about historical
   options market structure, not a fetch failure. It cannot be closed by retrying; it could
   only be closed by trading the *actual* nearest-Friday contract those days really had, which
   changes the time-decay framing enough that it is a different, larger track, not a patch
   here.
6. **The 1,016-row book itself is not this track's to question.** It is whatever `main`
   currently produces; T7 changes no detection code, and the recall gate (held-out S/A/C
   recall) cannot move because this file is a scoring skin on an already-selected book —
   same argument the retracted T2 tape made about itself, still true here. `python
   research/regression_gate.py` passes unchanged.

## Reproducibility

`research/t7_alpaca_cache.json` (70KB, committed) holds every row's real-quote lookup result
so a re-run is deterministic and offline; delete it and pass `--fetch` to re-pull (~4 minutes
against Alpaca, 1,016 calls). `--selfcheck` pins the book by sha256, asserts no same-day
`drange` reference exists in the pricing path, confirms the recovered ladder-underlying arm
reproduces the book's own `r` field exactly (845/845 within the 3dp rounding tolerance the
book writer uses), confirms the risk denominator is Black-Scholes even on real-quoted rows,
and confirms every scoreable row's sigma traces to a prior-session archive range.
