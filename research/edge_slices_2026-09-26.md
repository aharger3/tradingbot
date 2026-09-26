# Edge slices: does any subset of the existing signals have a real, stable edge?

2026-09-26. Script `research/edge_slices.py` → `research/edge_slices.json`
(re-run: `python3 research/edge_slices.py`, about 80 s on 8 cores). Follows PR #27
(`research/propfirm_overlay_search.py`): no sizing or stop overlay passes robustly, so this asks
whether the problem is the edge itself.

**Fill, everywhere below:** the gate's own book, `research/bt2y_trades_retest_on.json.gz`
(RETEST_REQUIRED=1, 498 sessions, 2024-09-03 → 2026-09-02). Signal-bar CLOSE entry,
`stop_rule.stop_fill_price()` stops, size-gated on `signal_runner.min_risk_floor`. The population
is the stream PR #26/#27 use (fired-and-traded plus halted rows). Every candidate is kept, not
just the first of the day: **6,889 trades**. `check_stream()` asserts this is exactly
`propfirm_overlay_search.load_candidates`.

## The answer

1. **No. Nothing survives the multiple-testing correction.** We tested 1,105 slices. None has
   Benjamini–Hochberg q ≤ 0.05, and none reaches q ≤ 0.10 either. The best q is **0.177**.
2. **There are fewer "hits" than chance alone would give.** 47 slices have a nominal p ≤ 0.05.
   With 1,105 tests, pure noise should give about 55. The book looks like zero-edge signals cut
   1,105 ways.
3. **The whole book loses a little on every trade:** **−0.035R/trade**, 43.0% win rate, PF 0.92,
   −0.014R in H1 and −0.050R in H2. No single filter turns that positive in both halves with any
   significance.
4. **Austin's S grade is the worst grade, not the best.** S: −0.085R, PF 0.81, negative in both
   halves, day-clustered t = −2.43. A: −0.032R. C: −0.022R. The ladder doesn't sort outcomes. This
   matches CLAUDE.md's finding that gating on `sgrade=='S'` costs −$29/day.
5. **The three lowest-p slices also fail the prop-firm gate.** They are not survivors and were
   gated only as an illustration. Their day-shuffle pass rates sit under 50% in at least one half
   for every firm.
6. **The test was generous.** The permutation test treats the ~14 trades a day as independent,
   when same-day trades are correlated. Measuring against the book's mean (−0.035R) also makes the
   bar lower than measuring against zero. A stricter test would find even less.

## The family

Each dimension is decidable before the entry. None uses a same-day close.

| dim | levels | note |
|---|---|---|
| grade | S, A, C, S+A | Austin's `sgrade` (downgrade.py, measured only) |
| setup | BR, OCR, 84 | break_and_retest / one_candle_rule / reentry_84_rule |
| sym | 28 symbols | |
| tod | 15-min entry bucket, 09:30 … 10:45 | |
| dow | Mon … Fri | |
| dir | call / put | |
| htf | with / against / neutral | the book's `aligned`: 1h close vs SMA20 of 1h closes **before** the session |
| mkt | with / against | the **prior** session's SPY 20-day trend |
| spyvol | calm / normal / wild | the **prior** session's SPY 20-day realized-vol tercile |
| symrange | quiet / normal / big | the symbol's **prior** session range (<1.5%, <3%, ≥3%) |
| gap | flat / small / big | the opening gap, known at 09:30 |

- **Excluded as lookahead:**
  - `rangeb`, `drange` and `dret` describe the full session.
  - The book's same-day `spy_trend` and `vol_regime` use that day's 16:00 SPY close
    (`backtest_2y.spy_context`).
- **Still slightly lookahead:** the vol terciles' cut points are full-sample. This is flagged,
  not fixed.
- **Family size:** 60 single filters plus 1,045 two-filter combinations, each with n ≥ 50 trades,
  for **1,105 tests**. Two filters is the maximum, as a guard against data mining.

**Statistics per slice:**

- n, days, avg R, win rate (R > 0), PF (sum of wins / |sum of losses|), and H1 / H2 avg R
  (H1 = before 2025-09-01).
- **perm p:** one-sided. Shuffle R across all 6,889 trades 100,000 times, recompute the slice mean
  each time, and set p = (1 + #reps ≥ observed) / 100,001.
- **BH q:** Benjamini–Hochberg across all 1,105 slices.
- **day t:** avg R divided by a day-clustered standard error, tested against zero.

**Survives** = q ≤ 0.05 AND avg R > 0 AND avg R > 0 in both halves.

## The ten lowest-p slices (none survive)

| slice | n | days | avg R | win | PF | H1 / H2 avg R | perm p | BH q | day t |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| INTC & small gap | 50 | 39 | +0.711 | 64.0% | 6.13 | +0.292 / +1.201 | 0.00018 | 0.177 | 2.17 |
| grade A & INTC | 55 | 49 | +0.608 | 49.1% | 2.95 | +0.035 / +0.843 | 0.00032 | 0.177 | 1.80 |
| AMD & prior-day range normal | 98 | 81 | +0.325 | 49.0% | 1.82 | +0.356 / +0.263 | 0.0031 | 0.805 | 1.79 |
| Mon & with prior SPY trend | 727 | 94 | +0.079 | 45.1% | 1.18 | +0.106 / +0.059 | 0.0041 | 0.805 | 1.40 |
| NVDA & Mon | 63 | 51 | +0.411 | 46.0% | 2.01 | +0.760 / +0.113 | 0.0042 | 0.805 | 1.69 |
| AVGO & 10:30 | 50 | 45 | +0.465 | 50.0% | 2.16 | −0.149 / +1.468 | 0.0044 | 0.805 | 1.70 |
| grade A & setup 84 | 51 | 49 | +0.441 | 45.1% | 1.80 | +0.499 / +0.401 | 0.0057 | 0.906 | 1.77 |
| BR & Mon | 1,168 | 96 | +0.043 | 45.8% | 1.11 | +0.109 / −0.000 | 0.0079 | 0.996 | 1.18 |
| grade A & NVDA | 78 | 68 | +0.315 | 52.6% | 2.03 | +0.155 / +0.459 | 0.0084 | 0.996 | 2.12 |
| AMD & Thu | 64 | 49 | +0.348 | 51.6% | 1.88 | +0.484 / +0.212 | 0.0098 | 0.996 | 1.52 |

This list is what data mining looks like:

- The slices are small symbol-specific pairs.
- The two INTC slices get most of their R from H2.
- No large, structural slice (grade, setup, time, direction) makes the list.

The largest near-positive slice is "Monday & trading with the prior session's SPY trend". It
covers 727 trades and makes +0.079R, which is 94 independent days at a day t of 1.40.

## Single filters

| slice | n | avg R | win | PF | H1 / H2 avg R | perm p | day t |
|---|---:|---:|---:|---:|---|---:|---:|
| **book** | 6,889 | −0.035 | 43.0% | 0.92 | −0.014 / −0.050 | — | — |
| grade S | 1,196 | **−0.085** | 41.2% | 0.81 | −0.058 / −0.106 | 0.945 | −2.43 |
| grade A | 1,801 | −0.032 | 42.6% | 0.93 | −0.065 / −0.008 | 0.439 | −1.06 |
| grade C | 3,892 | −0.022 | 43.7% | 0.95 | +0.024 / −0.053 | 0.140 | −1.03 |
| grade S+A | 2,997 | −0.053 | 42.1% | 0.88 | −0.062 / −0.046 | 0.860 | −2.30 |
| setup BR | 6,222 | −0.031 | 44.2% | 0.92 | −0.011 / −0.045 | 0.198 | −1.98 |
| setup OCR | 384 | −0.170 | 31.0% | 0.74 | −0.119 / −0.214 | 0.991 | −2.12 |
| setup 84 | 283 | +0.060 | 32.9% | 1.09 | +0.076 / +0.047 | 0.086 | 0.58 |
| call | 3,543 | −0.036 | 43.0% | 0.92 | −0.026 / −0.043 | 0.517 | −1.56 |
| put | 3,346 | −0.035 | 43.0% | 0.92 | −0.001 / −0.057 | 0.483 | −1.51 |
| 09:30–09:44 | 1,234 | +0.015 | 48.7% | 1.04 | +0.076 / −0.030 | 0.052 | 0.52 |
| 09:45–09:59 | 1,964 | −0.032 | 47.5% | 0.92 | −0.022 / −0.038 | 0.443 | −1.35 |
| 10:00–10:14 | 1,474 | −0.065 | 40.6% | 0.86 | −0.093 / −0.041 | 0.864 | −1.91 |
| 10:15–10:29 | 976 | −0.078 | 37.7% | 0.85 | −0.016 / −0.121 | 0.890 | −1.82 |
| 10:30–10:44 | 738 | −0.021 | 37.4% | 0.96 | +0.018 / −0.048 | 0.357 | −0.33 |
| 10:45–10:59 | 503 | −0.021 | 36.6% | 0.96 | +0.001 / −0.035 | 0.381 | −0.30 |
| Mon | 1,280 | +0.006 | 44.1% | 1.01 | +0.071 / −0.038 | 0.085 | 0.15 |
| Tue | 1,410 | −0.006 | 44.5% | 0.99 | +0.101 / −0.086 | 0.150 | −0.19 |
| Wed | 1,363 | −0.033 | 42.8% | 0.92 | −0.072 / −0.007 | 0.467 | −0.91 |
| Thu | 1,378 | −0.049 | 41.1% | 0.89 | −0.086 / −0.023 | 0.683 | −1.25 |
| Fri | 1,458 | −0.088 | 42.5% | 0.80 | −0.079 / −0.096 | 0.975 | −2.86 |
| HTF with | 3,875 | −0.030 | 39.1% | 0.94 | −0.012 / −0.043 | 0.335 | −1.26 |
| HTF against | 2,616 | −0.039 | 49.4% | 0.87 | −0.028 / −0.046 | 0.581 | −2.11 |
| HTF neutral | 398 | −0.062 | 38.4% | 0.88 | +0.035 / −0.171 | 0.673 | −0.92 |
| with prior SPY trend | 3,529 | −0.026 | 42.4% | 0.94 | +0.005 / −0.051 | 0.260 | −1.08 |
| against prior SPY trend | 3,340 | −0.044 | 43.6% | 0.90 | −0.035 / −0.050 | 0.721 | −2.02 |
| SPY vol calm | 2,050 | −0.051 | 43.5% | 0.88 | −0.033 / −0.062 | 0.760 | −1.70 |
| SPY vol normal | 2,227 | −0.029 | 43.7% | 0.93 | −0.004 / −0.041 | 0.383 | −1.05 |
| SPY vol wild | 2,592 | −0.027 | 41.9% | 0.94 | −0.006 / −0.050 | 0.325 | −1.03 |
| prior-day range quiet | 484 | −0.034 | 45.7% | 0.91 | +0.021 / −0.095 | 0.485 | −0.80 |
| prior-day range normal | 2,380 | −0.024 | 43.4% | 0.94 | +0.003 / −0.046 | 0.291 | −1.00 |
| prior-day range big | 3,848 | −0.036 | 42.3% | 0.92 | −0.023 / −0.045 | 0.534 | −1.58 |
| gap flat | 1,170 | −0.072 | 42.0% | 0.83 | −0.068 / −0.076 | 0.881 | −2.15 |
| gap small | 2,481 | −0.046 | 43.9% | 0.89 | −0.017 / −0.067 | 0.709 | −1.87 |
| gap big | 3,238 | −0.014 | 42.6% | 0.97 | +0.013 / −0.030 | 0.078 | −0.57 |

**Symbols** (28, in `edge_slices.json`):

- Best: NVDA at +0.085R (p 0.029), but +0.224 in H1 and −0.019 in H2.
- Worst: IREN at −0.158R and MSFT at −0.140R.
- Positive in both halves: only INTC (+0.042R, +0.098 / +0.017, p 0.16).

## Prop-firm gate on the three lowest-p slices (not survivors, illustration only)

The gate reuses the earlier PRs' code as-is:

- **PR #26:** `propfirm_gate.gate_series` on the slice's first trade of the day at $1,000/R.
- **PR #27:** `propfirm_overlay_search.build_series` / `score_windows` / `_shuffle_job`.
  - It uses per-half 120-session windows.
  - The grid is max 1/2/3 trades a day, no day stop or a −1R day stop, at $150–$500/R.
  - Each firm's config is chosen by min(shuffled H1, H2), from 40 shuffles.
  - Shuffled and zero-drift rates come from 200 shuffles.
  - **Robust** means shuffled ≥ 50% in both halves and above zero drift in both.

| slice | best firm (PR #27 config) | real order H1 / H2 | shuffled H1 / H2 | zero-drift H1 / H2 | $/day H1 / H2 | PR #26 all-starts (Apex) | robust firms |
|---|---|---|---|---|---|---:|---:|
| INTC & small gap | Apex, max 2/day, $500/R | 0.0 / 100.0 | 3.5 / 71.8 | 0.0 / 13.7 | +14 / +53 | 71.7% | **0 / 6** |
| grade A & INTC | Apex, max 1/day, $400/R | 0.0 / 98.5 | 0.0 / 80.5 | 0.0 / 16.0 | +3 / +54 | 63.7% | **0 / 6** |
| AMD & prior-day range normal | Apex, max 2/day, $500/R | 74.6 / 44.6 | 67.1 / 42.5 | 30.6 / 15.9 | +47 / +17 | 41.8% | **0 / 6** |

**Reading the table:**

- **The two INTC slices only pass in H2.** In H1 they have 27 and 16 trades. At ≤ $500/R that is
  too few to reach a $3,000 target inside 120 sessions.
- **The INTC & small gap slice passes PR #26's first-day check at $1,000/R for all 6 firms.** That
  is one start date on a slice with q = 0.18. It is not evidence.
- **AMD on normal prior-range days is the closest miss.** It has 98 trades, is positive in both
  halves, and beats zero drift. It passes 67% of shuffled windows in H1 and 42–47% in H2 (Apex,
  MFFU, Topstep), so it misses the bar in H2. It is still one of 1,105 tests (q = 0.81).
- **The full per-firm rows are in `edge_slices.json → gates`.**

## Why this is the end of slicing this book

- **Power.** Per-trade SD is 1.19R. At the rank-1 BH bar (p ≤ 0.05/1,105, one-sided z ≈ 3.9),
  this family could have detected either of these:
  - a 1,000-trade slice at about **+0.10R**;
  - a 300-trade slice at about **+0.23R**.

  A real, tradeable subset of that size would have shown up, and none did. What remains are tiny
  symbol pairs, where one slice in a thousand looks like the INTC rows by chance.
- **More slicing is more mining.** Three filters, a finer time grid or more symbols would only
  widen the family and lower the bar each test has to clear.
- **The stop model is where the money goes** (CLAUDE.md, r2 referee). The wick-touch 1R stop
  turns about 1 trade in 20 from +2R into −1R. No selection filter can recover a per-trade
  expectancy that the exit model sets.

## What data would be needed next

1. **Out-of-sample forward data, with one pre-registered slice.** The in-sample family is spent.
   - If Austin wants a candidate, pre-register exactly one (say AMD on normal prior-range days, or
     setup 84) and paper-trade it forward.
   - At SD 1.2R, confirming a +0.1R edge with one test (one-sided α 0.05, 80% power) takes about
     **900 trades**. For +0.05R it takes about **3,600**.
   - At the slice's current rate (~50 trades/yr for AMD-normal) that would take many years. Only
     a broad slice can be confirmed in months.
2. **Futures-native signals.** Run the same detector on MES/MNQ/ES 1-minute bars, so that R is
   measured on the instrument the prop firm actually trades. Today's book is equity/options R on
   28 stocks, and the transfer to futures is untested.
3. **More history, frozen and pre-split.** 25 months is 2–3 independent prop evals per half.
   - Extend the archive (Massive/Polygon permitting) to 4–5 years.
   - Fix the H1/H2/H3 split **before** any look.
4. **A different exit.** The per-trade expectancy is set by the wick stop, not by which trades are
   taken. An exit/stop change goes through the gate as a rule change (Austin's 2026-09-03 ruling)
   and is re-measured on a new book. Slicing this book cannot answer it.

## Method notes

- **Permutation null.** The null is "the slice is a random draw from the book", so it centres on
  −0.035R, not zero. A slice can beat the book and still lose money. That is why "survives" also
  needs avg R > 0 in both halves.
- **Independence.** The trade-level shuffle treats same-day trades as independent, which makes p
  too small. `day_t` is the day-clustered check, and its largest value in the family is 2.17.
- **Why BH is used.** BH is valid under positive dependence, and overlapping slices are positively
  dependent. Benjamini–Yekutieli would be stricter still, and nothing survives BH.
- **Caveats carried from PR #27:**
  - Commissions and futures slippage are not modeled.
  - The daily loss limit is checked on realized closes.
  - Firm rules for Apex, MFFU, Alpha's DLL and TPT's trailing drawdown are flagged "verify" in
    `propfirm_gate.FIRM_RULES`.
