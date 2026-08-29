# T9 — spread and tight-RR filter (R30, both readings)

**Headline.** Austin's complaint is two things and both are measured. (a) A stop-distance
floor on the underlying — filtering trades whose entry-to-stop geometry has collapsed to a
few cents — removes a population whose backtest mean R is a **fat-tail artifact, not real
edge** (median R of the removed group is a flat **-1.0**, but a handful of blowup wins pull
the mean to +1.0 to +2.6R on 3-cent-to-17-cent stops), touches **zero** of the 34 held-out S
cards at every threshold tested, and the removed-vs-kept difference is **outside its own 95%
bar** at the recommended threshold (+1.0423R ± 0.7675R) — real, not null. (b) A per-contract
bid-ask cost model shows the RATIFIED book's contract edge (+0.7498R, no spread) survives a
$0.01–$0.05 round-trip spread but **flips negative past a $0.095 round-trip** — and a
symbol-level wide-spread *filter* is **unreachable**: all 28 traded symbols already sit inside
`universe.ALL_SYMS`, which Austin has already restricted to ~200k+ daily-options-volume names.

Reproduced by `research/t9_spread_tight_rr.py`, output `research/t9_spread_tight_rr.json`.

---

## 1. Tight-RR filter on the underlying (R15: "if the trade is too hard to manage it's not a
   good trade")

`stop_pct = risk / entry * 100` is already a field on every row of `research/bt2y_trades.json`
(the T0 ratified book, 2,595 traded). The existing `stopb` bucket calls anything under 0.15%
"tight" — this sweeps thresholds inside that bucket:

| stop_pct floor | removed n (% of book) | removed mean R | removed median R | kept mean R | book move | removed-vs-kept diff ± 95% bar | removed S-tier |
|---|---:|---:|---:|---:|---:|---|---:|
| < 0.03% | 12 (0.5%) | +1.3208 | +0.0730 | +0.5445 | -0.0036 | +0.7763 ± 1.7404 — **null** | 3 |
| < 0.05% | 42 (1.6%) | +2.6308 | +0.0730 | +0.5138 | -0.0343 | +2.1169 ± 1.6970 — real | 13 |
| **< 0.08%** | **115 (4.4%)** | **+1.5442** | **-1.0000** | **+0.5019** | **-0.0462** | **+1.0423 ± 0.7675 — real** | 30 |
| < 0.10% | 192 (7.4%) | +1.1847 | -1.0000 | +0.4972 | -0.0509 | +0.6875 ± 0.5407 — real | 41 |
| < 0.15% | 312 (12.0%) | +0.7970 | -1.0000 | +0.5141 | -0.0340 | +0.2829 ± 0.3822 — **null** | 77 |

Book baseline: mean R +0.5481, win rate 43.1%, n 2,595 (the T0 ratified book, unchanged).

**Why the mean is positive when the median is -1.0.** At 0.08%+ thresholds the removed
population is bimodal: most of it is a straight stop-out (`removed_win_rate` 44.7% at 0.08%,
falling to 35.5% by 0.15% — not better than the book), and the mean is pulled up by a small
number of enormous R prints — the eight biggest removed trades at the 0.08% floor are
CRM +24.348R (3-cent stop), SPY +15.974R, BABA +12.475R, AMZN +11.797R, SPY +11.500R,
GOOGL +9.974R, MSFT +9.822R, GOOGL +9.577R — every one a $0.03-$0.05 stop on a $100-$630
stock. **This is R-multiple blowup, not edge.** `r = (exit - entry) / risk`; when `risk`
collapses toward zero the same target distance produces an arbitrarily large R, and the
backtest fills at the exact modeled price with no slippage. A stop that close sits inside
real execution noise (median removed **dollar** stop distance is **$0.17**, min **$0.03**,
p90 **$0.39** at the 0.08% floor) — real slippage on a stop this tight would erode or erase
these prints, so the backtest's mean R for this slice reads optimistic, not honest.

**Held-out recall: zero cost at any threshold tested.** Of the 34 blind S cards
(`research/marks/probe_s_sweep_2026-08-28.jsonl`), the engine currently fires on 18. Replaying
each of those 18 fired entries' actual `(entry, stop)` geometry, **none** would be filtered
at 0.03%, 0.05%, 0.08%, 0.10%, or even 0.15% — recall stays 18/34 = 52.9% at every floor in
this sweep. Method rule 2 governs, and this filter does not touch the thing the gate measures.

**Recommendation for this half: land `MIN_STOP_PCT = 0.08`** (skip a signal whose risk is
under 0.08% of entry price — 4.4% of the current book, 115 of 2,595 trades). It is the
threshold where the removed-vs-kept difference first clears its own error bar cleanly
(+1.0423R ± 0.7675R) while the removed dollar-stop distances (median $0.17) are still
plausibly "too hard to manage" on Austin's own words, not just statistically unusual. In raw
backtest terms this **costs the book money** (kept mean R falls -0.0462 vs baseline) —
that cost is the honest way to report it, but it is concentrated in prints the backtest
cannot actually validate (near-zero-denominator R blowups on 3-to-5-cent stops), so it is
not read here as giving up real edge.

## 2. Bid-ask cost model on the contract (R30, his second reading)

There is no options tape in this repo — same caveat `research/t2_options_tape.py` already
carries (Polygon options snapshot 403s, Tastytrade session sandbox-only per
`broker/tastytrade.py`). This reuses that file's Black-Scholes `Contract` pricer unmodified
(Parkinson realized-vol IV × 1.2, ATM strike, 0DTE), re-pointed at the RATIFIED (post-T0)
2,595-trade book instead of the pinned pre-T0 1,017-trade book t2 uses.

| round-trip spread | mean cost (contract R) | book after cost |
|---|---:|---:|
| (no spread) | — | **+0.7498** |
| $0.01 | 0.0788 | +0.6710 |
| $0.02 | 0.1576 | +0.5923 |
| $0.05 (x9's headline assumption) | 0.3939 | +0.3559 |
| $0.10 | 0.7878 | **-0.0380** |
| $0.15 | 1.1817 | -0.4319 |

**Breakeven round-trip spread: $0.095.** The contract edge on the RATIFIED book survives a
nickel round-trip (typical for a liquid 0DTE ATM name) but is gone past a dime. Modeled
premium risk (the contract's 1R denominator) is median $0.42 per share, so a $0.10 round-trip
already costs a fifth of 1R — this is the same mechanism as §1: a thin denominator makes a
fixed cent-cost hurt more in R terms, not a new finding, but confirms the two readings share
a root cause (denominator size), not just a topic.

**Symbol-level wide-spread filter: unreachable, checked per method rule 3.** All 28 traded
symbols are inside `universe.ALL_SYMS`, and `universe.py`'s own comment records Austin's
watchlist rule: *"all stocks with ~200k+ daily options volume (his rule — high options volume
= cleaner moves, easier fills)."* He already restricts himself to liquid names — a filter on
top of that has zero symbols left to remove given the 29-symbol universe, and there is no real
NBBO in this repo to grade spread *within* a symbol's own chain (the only measurable axis is
the $-spread sweep above). This is the same unreachable-gate bug class flagged in T0's
reachability section, checked and reported before any threshold was tuned.

## 3. What did not run

- No real NBBO — every spread number is a modeled $-cost swept over a range, not an observed
  quote. `broker/tastytrade.py` is sandbox-only and unexercised against a live chain.
- The tight-RR filter is evaluated as a static post-hoc cut on the traded book, not wired into
  `signal_runner.py` as a live downgrade/skip — if landed, R15's `MIN_STOP_PCT` floor belongs
  next to `backtest_2y.py`'s existing `stop_pct` computation (`backtest_2y.py:154`) and the
  live scanner's own stop-sizing path, both untouched here.
- No leave-one-out isolation of this filter against the other 26 already-landed ratified items
  — this report measures it as a standalone cut on the current shipped book, same convention
  as T0's disaster-stop arm.
- `held-out precision` (the 100-card sample's false-fire rate) is unaffected by definition —
  this filter can only remove fires, never add one, so precision cannot fall and was not
  re-measured.

## 4. Regression gate

`python research/regression_gate.py` — PASS, unchanged (this track writes no engine code, only
a measurement script and this report).
