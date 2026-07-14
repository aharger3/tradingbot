# D1 — SCARFACE_CONTRACT A/B (first-OTM + weekly expiry vs current selection)

**Task:** 12mo options P&L A/B — SCARFACE_CONTRACT (first-OTM strike + nearest-Friday
weekly expiry) vs current selection (nearest-ATM strike + 0DTE/next-day expiry).
**Date:** 2026-07-13 · **Model:** GLM · **Baseline:** `backtest_charts.json`
(post-C10 strict-84 default, refreshed 07-13 16:30).

## Verdict (one line)

**Keep SCARFACE_CONTRACT OFF (default). A == B, bit-identical, on the 12mo backtest
— 0/620 trades differ on premium / contracts / max_loss. The flag is not in the
P&L path; the sizer risk-normalizes to $1000 regardless of strike/expiry. The lever
moves the live *card* (strike/expiry labels) and live execution quality (fill spreads,
gamma/theta at real premium) — routed to F2 live-shadow, NOT a backtest signal-P&L lever.**

## Baseline (current config, RULE84_STRICT on)

| metric | value |
|---|---|
| traded (non-alert) | 620 |
| wins / WR | 231 / 37.3% |
| P&L | $75,489 |
| grades | B 580 · A 29 · A+ 11 |

Matches C9/C10 strict baseline ($75,489 = detector-OFF/strict arm) — current default config.

## TABLE 1 — 12mo options P&L A/B

| arm | n | W | WR | P&L |
|---|---:|---:|---:|---:|
| **A — current (ATM / 0DTE)** | 620 | 231 | 37.3% | **$75,489** |
| **B — SCARFACE (first-OTM / weekly)** | 620 | 231 | 37.3% | **$75,489** |
| **Δ (B − A)** | **0** | **0** | **0.0pp** | **$0** |

Bit-identical. Flipping the flag changes nothing in realized P&L.

## Why identical — two independent reasons

### (1) PATH: flag is not in the backtest P&L path

The 12mo P&L path is `backtest_12mo → backtest_week.simulate_day → SimTrade.pnl`.
`SimTrade.pnl` (backtest_week.py:106-141) computes:

```
pnl = (stock_move / stock_risk) * RISK_DOLLARS     # RISK_DOLLARS = 1000
```

Pure stock R-multiple at flat $1k risk. `backtest_week.py` and `backtest_12mo.py`
**never import `options_sizer`** and never read `SCARFACE_CONTRACT`. The contract
selection (strike / expiry / premium / contract count) never enters realized P&L.
Verified: `grep SCARFACE_CONTRACT|options_sizer|build_options_plan` over the
backtest path = 0 hits (the only `build_options_plan` call near backtest is
`backtest_window.py` — a live TastytradeFeed window *scanner* for card display,
not the 12mo P&L engine).

### (2) MATH: the sizer risk-normalizes to $1000 regardless of arm

`options_sizer.build_options_plan` is only called by the live/paper card path
(`live_scanner.py:537`, `discord_bot`, `paper_trader`, `spec2_grading_check`).
Its sizing math:

```
premium_risk   = stock_risk * delta_estimate(0.5)        # same for both arms
contracts      = max_loss($1000) / (premium_risk * 100)
max_loss       = premium_risk * contracts * 100         # → ~$1000 by construction
```

The sizer's job is to normalize risk to $1000 *whatever* the strike/expiry/premium
are — so R-multiple P&L (`move/risk * $1000`) is contract-selection-invariant by
design. Under the **estimation fallback** (no `tasty_feed` — what backtest/paper
use), `entry_premium = max(round(stock_entry*0.005,2),0.50)` ignores strike AND
expiration entirely, so premium/contracts/max_loss are bit-identical between arms;
only the strike + expiration *labels* on the card differ. Under **live tasty_feed**
(real premiums), the OTM-weekly premium is cheaper → contracts scale up →
`max_loss` re-normalizes back to $1000 → R-multiple P&L still invariant.

## TABLE 2 — per-trade options card (estimation fallback, sample trades)

Shows the lever moves the *card* (strike/expiry labels), not the risk-normalized
sizing or P&L.

| sym | dir | arm | strike | expiry | premium | premRisk | contracts | maxLoss |
|---|---|---|---:|---|---:|---:|---:|---:|
| TSLA | put | cur | 345 | 2025-08-29 | 1.72 | 0.81 | 12 | 972.00 |
| TSLA | put | scar | 340 | 2025-08-29 | 1.72 | 0.81 | 12 | 972.00 |
| PLTR | put | cur | 175 | 2025-10-13 | 0.88 | 0.36 | 27 | 972.00 |
| PLTR | put | scar | 175 | 2025-10-17 | 0.88 | 0.36 | 27 | 972.00 |
| QQQ | put | cur | 557 | 2025-08-01 | 2.78 | 0.46 | 21 | 966.00 |
| QQQ | put | scar | 556 | 2025-08-01 | 2.78 | 0.46 | 21 | 966.00 |
| AAPL | call | cur | 220 | 2025-08-07 | 1.10 | 0.33 | 30 | 990.00 |
| AAPL | call | scar | 220 | 2025-08-08 | 1.10 | 0.33 | 30 | 990.00 |

Strike differs on some trades (TSLA $5-inc, QQQ $1-inc), expiry differs when the
trade day isn't Friday — but **premium / premRisk / contracts / maxLoss are
identical row-for-row**. (TSLA strike coincides for spot near a $5 boundary; QQQ
$1-inc shows a 1-strike shift. PLTR strike coincides; only expiry moves.)

## INVARIANCE CHECK — all 620 trades

| field | differs (arm A ≠ B) | reason |
|---|---:|---|
| strike | 310 / 620 | coarse-increment symbols (TSLA $5, AMD $5) often coincide; fine-inc (QQQ/SPY $1) shift |
| expiration | 474 / 620 | 0DTE vs nearest Friday — differs on every non-Friday-pre-14:30 trade |
| **premium** | **0 / 620** | fallback formula `entry*0.005` ignores strike/expiry → always identical |
| **contracts** | **0 / 620** | premium_risk identical → contracts identical |
| **max_loss** | **0 / 620** | risk-normalized to ~$1000 in both arms |

## What SCARFACE_CONTRACT *does* change (the real, non-backtest effects)

1. **Live card presentation** — strike (first-OTM vs ATM) + expiration (weekly
   Friday vs 0DTE) labels on the Discord/paper card. Cosmetic from a P&L standpoint.
2. **Live execution quality** — OTM weeklies carry wider bid/ask spreads and lower
   liquidity than ATM 0DTE on the highest-volume symbols; `option_warnings`
   ("wide spread", "no liquidity") would fire more often. Not modeled in backtest.
3. **Gamma/theta convexity at real premium** — OTM-weekly (lower delta ~0.40, lower
   gamma, much lower theta) vs ATM-0DTE (delta ~0.50, huge gamma, huge theta). On
   the binary win/loss outcomes the backtest already has, ATM-0DTE's gamma favors
   intraday wins while its theta punishes scratches (~0% of tier per C10, ~0.2%
   full-pop here — 1 scratch of 620). **This is the only real-$ delta** and it
   requires a Black-Scholes pricing layer with per-symbol IV — not in the repo,
   and fetching IV for 671 trades from yfinance courts the rate-limit the standing
   rule forbids. **Routed to F2 live-shadow** (real bid/ask + premium capture), not
   a backtest signal-P&L lever.

## Bug carry-forward (from C7, NOT fixed per "D1 owns SCARFACE_CONTRACT")

`options_sizer.weekly_expiration()` returns **this week's Friday** — and if today
*is* a Friday, it returns **today**, not next week. Rulebook (C7/B2, verbatim-sourced
mm1.0 L3 / mm2.0 L7) says Friday signals buy **next-week** contracts. One-line fix
if the flag ever flips ON:

```python
# weekly_expiration: Fri → next week (rulebook "Friday = next week contracts")
if d.weekday() == 4:
    return (d + timedelta(days=7)).isoformat()
```

**Not applied** — flag stays OFF, no live behavior changes; the fix is documented
for whoever flips SCARFACE_CONTRACT=True (D2+ or F2). C7 already queued this.

## Hard-rule compliance

- **No signal-logic edits** — `omen_bot.py` / `signal_runner.py` untouched
  (grep-verified; analysis is read-only over `backtest_charts.json`).
- **No flag-gated measurement code added to the P&L path** — none needed: the
  existing backtest already answers (A == B by construction). Adding a speculative
  Black-Scholes options-P&L layer with guessed IV would manufacture fake-precise
  numbers — ponytail rule against unrequested abstractions + the karpathy honesty
  principle (don't fabricate precision the data doesn't support). F2's real
  premium capture is the honest place to measure this.
- **Config defaults unchanged** — SCARFACE_CONTRACT stays OFF (default).
- **0-trade rule** — N/A (no backtest re-run; analysis over existing 620-trade
  baseline, all >0).
- **No commits** — working-tree changes left for Fable review.

## Reproduce

```
py research/d1_scarface_ab.py
```

Reads `backtest_charts.json`, prints TABLE 1 + TABLE 2 + the 620-trade invariance
check. No network, no backtest re-run, no rate-limit risk.
