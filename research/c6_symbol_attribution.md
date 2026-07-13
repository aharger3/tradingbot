# C6 — Per-symbol tier attribution (S>=4+[hammer])

**Date:** 2026-07-13
**Source:** `research/c1_off_charts.json` (clean 12mo baseline)
**Prior art:** `c3_tag_split.py`, `b4_analyze.py`, `c1_analyze.py` (tier sim reused verbatim)
**Script:** `research/c6_symbol_attribution.py`
**Scope:** ANALYSIS ONLY — no backtest, no config change, no edits to `omen_bot.py` / `signal_runner.py`.

Baseline 12mo: **671 traded / 866 signals** incl alert-only (251W 419L 37.5%W $78,190).
*Note: charts JSON holds 866 traded+alert-only records. The "9,423 signals" figure in the task
= raw scanner output (pre-filter); not stored in charts JSON.*

Tier (S>=4+[hammer], max 2/day, stop-when-green): **78 tr  42.3%W  $21,000/yr ($1,750/mo)**
— matches B4/C1/C3 baseline (uncontaminated tier), sanity check passed.

---

## 1. Tier trades by symbol (sorted by P&L)

Tier = trades the S>=4+hammer tier actually accepts (sim gate, not all S>=4+hammer signals).

| sym | tr | W | L | win% | P&L | note |
|-----|----|---|---|------|-----|------|
| NVDA | 3 | 3 | 0 | 100.0% | $6,000 | *insufficient data* |
| COIN | 7 | 4 | 3 | 57.1% | $5,000 | |
| AMD | 4 | 3 | 1 | 75.0% | $5,000 | *insufficient data* |
| ORCL | 5 | 3 | 2 | 60.0% | $4,000 | |
| UBER | 3 | 2 | 1 | 66.7% | $3,000 | *insufficient data* |
| PLTR | 4 | 2 | 2 | 50.0% | $2,000 | *insufficient data* |
| AMZN | 4 | 2 | 2 | 50.0% | $2,000 | *insufficient data* |
| NFLX | 1 | 1 | 0 | 100.0% | $2,000 | *insufficient data* |
| INTC | 1 | 1 | 0 | 100.0% | $2,000 | *insufficient data* |
| QQQ | 1 | 1 | 0 | 100.0% | $2,000 | *insufficient data* |
| GOOGL | 5 | 2 | 3 | 40.0% | $1,000 | |
| IREN | 5 | 2 | 3 | 40.0% | $1,000 | |
| AVGO | 3 | 1 | 2 | 33.3% | $0 | *insufficient data* |
| META | 3 | 1 | 2 | 33.3% | $0 | *insufficient data* |
| TSLA | 4 | 1 | 3 | 25.0% | -$1,000 | *insufficient data* |
| SOFI | 4 | 1 | 3 | 25.0% | -$1,000 | *insufficient data* |
| MARA | 1 | 0 | 1 | 0.0% | -$1,000 | *insufficient data* |
| MU | 7 | 2 | 5 | 28.6% | -$1,000 | |
| MSFT | 1 | 0 | 1 | 0.0% | -$1,000 | *insufficient data* |
| TSM | 1 | 0 | 1 | 0.0% | -$1,000 | *insufficient data* |
| BABA | 2 | 0 | 2 | 0.0% | -$2,000 | *insufficient data* |
| AAPL | 2 | 0 | 2 | 0.0% | -$2,000 | *insufficient data* |
| HOOD | 5 | 1 | 4 | 20.0% | -$2,000 | |
| CRM | 2 | 0 | 2 | 0.0% | -$2,000 | *insufficient data* |

Tier symbols: **24** — net-positive: 12, net-negative: 10, net-zero: 2.

---

## 2. Full-pop traded by symbol (context, sorted by P&L)

All traded signals (A+/A/B, not alert-only), not just tier.

| sym | tr | W | L | win% | P&L |
|-----|----|---|---|------|-----|
| ORCL | 41 | 19 | 22 | 46.3% | $15,189 |
| AVGO | 26 | 12 | 14 | 46.2% | $9,785 |
| COIN | 40 | 16 | 24 | 40.0% | $7,711 |
| AMD | 40 | 16 | 24 | 40.0% | $7,658 |
| GOOGL | 20 | 9 | 11 | 45.0% | $6,930 |
| INTC | 23 | 9 | 13 | 40.9% | $6,489 |
| MU | 41 | 16 | 25 | 39.0% | $6,191 |
| UBER | 21 | 9 | 12 | 42.9% | $5,571 |
| TSLA | 45 | 17 | 28 | 37.8% | $4,985 |
| META | 26 | 10 | 16 | 38.5% | $4,000 |
| TSM | 23 | 9 | 14 | 39.1% | $3,663 |
| HOOD | 41 | 15 | 26 | 36.6% | $3,636 |
| MSFT | 24 | 9 | 15 | 37.5% | $3,000 |
| BABA | 21 | 8 | 13 | 38.1% | $3,000 |
| NFLX | 15 | 6 | 9 | 40.0% | $2,838 |
| PLTR | 36 | 13 | 23 | 36.1% | $2,630 |
| IREN | 57 | 20 | 37 | 35.1% | $2,517 |
| NVDA | 28 | 10 | 18 | 35.7% | $2,000 |
| QQQ | 8 | 3 | 5 | 37.5% | $1,000 |
| CRM | 23 | 7 | 16 | 30.4% | -$2,195 |
| MARA | 12 | 3 | 9 | 25.0% | -$3,000 |
| SOFI | 15 | 4 | 11 | 26.7% | -$3,408 |
| AAPL | 23 | 6 | 17 | 26.1% | -$5,000 |
| AMZN | 22 | 5 | 17 | 22.7% | -$7,000 |

Key contrast: **AMZN** is the *worst* full-pop symbol (-$7,000, 22.7%W) yet nets +$2,000 in
tier (4 tier trades, 50%W) — tier filter flips it. **TSLA** strong full-pop (+$4,985) but
net-negative in tier (-$1,000). Tier selection and full-pop ranking diverge; symbol-level tier
attribution is the right lens, not full-pop P&L.

---

## 3. Concentration — symbols carrying 80% of tier profit

Net-positive tier P&L total: **$35,000** (the 12 net-positive symbols).
Symbols to reach 80% of that profit: **8 of 12** (67%).

| sym | tr | win% | P&L |
|-----|----|------|-----|
| NVDA | 3 | 100.0% | $6,000 |
| COIN | 7 | 57.1% | $5,000 |
| AMD | 4 | 75.0% | $5,000 |
| ORCL | 5 | 60.0% | $4,000 |
| UBER | 3 | 66.7% | $3,000 |
| PLTR | 4 | 50.0% | $2,000 |
| AMZN | 4 | 50.0% | $2,000 |
| NFLX | 1 | 100.0% | $2,000 |

### Net-negative in tier (10 symbols)

| sym | tr | win% | P&L | note |
|-----|----|------|-----|------|
| TSLA | 4 | 25.0% | -$1,000 | *insufficient data* |
| SOFI | 4 | 25.0% | -$1,000 | *insufficient data* |
| MARA | 1 | 0.0% | -$1,000 | *insufficient data* |
| MU | 7 | 28.6% | -$1,000 | |
| MSFT | 1 | 0.0% | -$1,000 | *insufficient data* |
| TSM | 1 | 0.0% | -$1,000 | *insufficient data* |
| BABA | 2 | 0.0% | -$2,000 | *insufficient data* |
| AAPL | 2 | 0.0% | -$2,000 | *insufficient data* |
| HOOD | 5 | 20.0% | -$2,000 | |
| CRM | 2 | 0.0% | -$2,000 | *insufficient data* |

Only **MU** (7 tr) and **HOOD** (5 tr) are net-negative with adequate sample. The other 8 are
n<5 — noise, flagged insufficient-data, not actionable as "drop".

---

## 4. Proposed tier-specific symbol list

**List (12, net-positive tier symbols):**
`AMD, AMZN, COIN, GOOGL, INTC, IREN, NFLX, NVDA, ORCL, PLTR, QQQ, UBER`

**Insufficient-data flags (8 of 12, n<5):** NVDA, AMD, UBER, PLTR, AMZN, NFLX, INTC, QQQ.
Per task rules: not dropped on noise — marked insufficient-data. Only 4 of 12 proposed
symbols (COIN 7, ORCL 5, GOOGL 5, IREN 5) have adequate tier sample; confidence is thin.

### Tier stats with proposed list as tier gate (refuse off-list symbols)

| config | tr/yr | win% | $/yr | $/mo |
|--------|-------|------|------|------|
| current tier (all symbols) | 78 | 42.3% | $21,000 | $1,750 |
| tier + proposed symbol list | **43** | **60.5%** | **$35,000** | **$2,917** |
| Δ | -35 | +18.2pp | +$14,000 | +$1,167 |

Big apparent jump — but this is an **in-sample** fit. The proposed list is derived *from the
same 12mo run* it's then tested on (net-positive symbols selected by their own P&L, then
"tested" by gating those same symbols). That is textbook overfitting: $35k/yr and 60.5%W are
upper-bound, not a forward expectation. With 8 of 12 symbols at n<5, the gate is mostly
memorizing which 3-trade flukes happened to win. Any live decision needs walk-forward (F1)
before trust.

---

## Verdict

Tier profit is concentrated: **8 of 12 net-positive symbols carry 80%** of tier P&L; **10
symbols are net-negative in tier** (only MU and HOOD with adequate sample, rest n<5 noise).
Gating the tier to the 12 net-positive symbols lifts tier to **43 tr/yr 60.5%W $35,000/yr**
(in-sample, vs 78 tr 42.3%W $21,000/yr) — but **this is overfit**: the list is selected from
the same run it's tested on and 8/12 symbols have n<5. **PROPOSAL ONLY, no config change.**
Forward use requires walk-forward validation (F1) and ideally more tier trades per symbol
before a symbol whitelist is trustworthy. Hand to C10.
