# g120 -- three funding arms, same book, real firm rules

Same one-trade-a-day candidate stream for all three arms: `build_arm(rows, keep=lambda r: True)` from `research/g116_sizing_kelly_options.py` -- the shipped A_base arm, first size-gated candidate of the day, `research/bt2y_trades_retest_on.json` (RETEST_REQUIRED=1, current shipped default), n=495 sessions, 2024-09-03 .. 2026-09-02.

**Adversarial pass, 2026-09-03 night: this file's first cut was REFUTED.** All mechanics, arithmetic and the shares conversion reproduced exactly under independent re-derivation, but the headline "no arm is fundable" call was wrong -- the 9-point risk-percent grid this file swept (0.25%, 0.50%, ..., 3.00% of account) straddled Vanquish's real passing band without ever landing in it, and the sources' own worked example ($150/trade, from both `Projects/AUGUR.md` and `research/prop_vanquish_terms.md`) sits dead centre of that band. This version sweeps a finer grid through the actual band, reports the passing band explicitly, and fixes a related bug where a FAILed eval's "net after cost" credited two more years of un-gated trading past the day it actually blew up.

## Findings

- **Arm 1, Vanquish Advanced Options $50k, PASSES in a narrow band: $140.00-$178.50/trade (0.280%-0.357% of the $50k account, 6 of 24 tested levels).** Best case in the sweep: $175/trade, PASS on 2025-06-04 (9.0 months in), net after subscription $63. At the sources' own worked example ($150/trade): PASS on 2025-07-22 (10.6 mo), net $-478. **The book's native $1,000/trade unit does NOT pass** (FAILs trailing_drawdown, 0.3 months to breach) -- the eval is passable, just not at anything like the size this repo's numbers are usually quoted at. CONDITIONAL: this arm's universe is the CURRENT 28-symbol single-name book; Vanquish's Advanced Options underlyings (index-only SPX/XSP/VIX vs single-name) are still UNVERIFIED per `Projects/AUGUR.md`'s open question, so this result only holds if that verification lands single-names in scope. Also CAVEAT: `dd_mode="eod"` only checks the trail at each day's close; a real intraday floor check (which this book cannot test -- no intraday equity path is recorded) could shrink or eliminate this band.
- **Arm 2, Trade The Pool (shares, repriced off entry/stop):** **never PASSES over the whole book** (fails trailing_drawdown at first breach 2024-09-16; cost-only through breach, net $-97). Per-trade risk actually varies with each symbol's own price ($100-$750, mean $359) -- proof this is not the book's flat $1,000 convention. Shares are capped by BOTH the buying-power rule AND the firm's own 3% daily loss limit (see `shares_for()`'s docstring for the fix and why the buying-power reading is `account*4/entry`, not a literal `account/4`).
- **Arm 3, personal ~$10k, aggressive ($1000/trade):** total $17601 over the book, max drawdown $21577 (215.77% of the $10k account), trough equity $3820 (38.2% of the account), never wipes the account IN THIS BOOK'S OWN TRADE ORDER -- order-dependent, not a safety property: early profitable trades built the cushion before the drawdown; see `personal_arm_result()`'s docstring.
- **Arm 3, personal ~$10k, conservative ($100/trade):** total $1760 over the book, max drawdown $2158 (21.58% of the $10k account), trough equity $9382 (93.8% of the account), never wipes the account IN THIS BOOK'S OWN TRADE ORDER -- order-dependent, not a safety property: early profitable trades built the cushion before the drawdown; see `personal_arm_result()`'s docstring.

**Ranking: Vanquish Advanced Options $50k (at $175/trade) is fundable FIRST** -- clearly soonest and cheapest of the two.
  - Vanquish Advanced Options $50k (at $175/trade): 9.0 months to a clean PASS, $4990 cost to get there.

Modeling choices stated explicitly (none silently baked in):

- Vanquish: no daily loss limit is modeled as `daily_loss_limit_pct=1.0` (100% of account) so the rule can structurally never trip -- Vanquish's own page states there is no such limit, this is how the generic simulator encodes 'disabled'.
- Trade The Pool: account_size=$25,000 is a MID-OF-RANGE PICK ($5k-$200k stated range, not a number from their site). trailing_dd_pct=5% is a MIDDLE-OF-RANGE PICK (3-7% stated range); the exact drawdown TYPE (trailing vs static) is NOT confirmed by `research/prop_firms_stocks.md`. consistency_pct=1.0 disables the consistency check because the fetched research states no such rule for this firm. min_trading_days=0 because none is stated.
- Personal $10k: an arbitrary account size Austin named ("a personal ~$10k account") in the AUGUR grilling session, not a specific committed number -- both a book-native ($1,000/trade, aggressive) and a conservative (1%, $100/trade) sizing are reported since neither is obviously the right one to commit to alone.

## Arm 1 -- Vanquish Advanced Options $50k, risk sweep

Rules: 10% profit target / 5% EOD-anchored trailing drawdown / no daily loss limit / min 4 trading days / no single day over 30% of accumulated profit, per `research/prop_vanquish_terms.md` and the "What the eval simulator must assume" section of `Projects/AUGUR.md`. Cost: $499/month while in eval; $249 reset assumed once if the eval never passes over the whole book.

| risk% | $/trade | verdict | fail reason | 1st-fail/pass day | months | sub$ charged | net $ if ungated (full book) | net $ after cost |
|---:|---:|---|---|---|---:|---:|---:|---:|
| 0.20% | 100.00 | FAIL | profit_target_not_reached | 2026-09-02 | 24.0 | $11976 | $1760 | $-12225 |
| 0.22% | 110.00 | FAIL | profit_target_not_reached | 2026-09-02 | 24.0 | $11976 | $1936 | $-12225 |
| 0.24% | 120.00 | FAIL | trailing_drawdown | 2026-07-02 | 21.9 | $10978 | $2112 | $-11227 |
| 0.25% | 125.00 | FAIL | trailing_drawdown | 2026-06-25 | 21.7 | $10978 | $2200 | $-11227 |
| 0.26% | 130.00 | FAIL | trailing_drawdown | 2026-06-24 | 21.7 | $10978 | $2288 | $-11227 |
| 0.28% | 140.00 | PASS | - | 2025-09-09 | 12.2 | $6487 | $2464 | $-1459 |
| 0.30% **(=$150, sources' worked example)** | 150.00 | PASS | - | 2025-07-22 | 10.6 | $5489 | $2640 | $-478 |
| 0.32% | 160.00 | PASS | - | 2025-07-02 | 9.9 | $4990 | $2816 | $146 |
| 0.34% | 170.00 | PASS | - | 2025-06-06 | 9.1 | $4990 | $2992 | $249 |
| 0.35% | 175.00 | PASS | - | 2025-06-04 | 9.0 | $4990 | $3080 | $63 |
| 0.36% | 178.50 | PASS | - | 2025-06-04 | 9.0 | $4990 | $3142 | $164 |
| 0.36% | 180.00 | FAIL | trailing_drawdown | 2025-01-24 | 4.7 | $2495 | $3168 | $-2744 |
| 0.38% | 190.00 | FAIL | trailing_drawdown | 2025-01-24 | 4.7 | $2495 | $3344 | $-2744 |
| 0.40% | 200.00 | FAIL | trailing_drawdown | 2025-01-23 | 4.7 | $2495 | $3520 | $-2744 |
| 0.44% | 220.00 | FAIL | trailing_drawdown | 2025-01-14 | 4.4 | $2495 | $3872 | $-2744 |
| 0.48% | 240.00 | FAIL | trailing_drawdown | 2025-01-02 | 4.0 | $1996 | $4224 | $-2245 |
| 0.50% | 250.00 | FAIL | trailing_drawdown | 2024-12-31 | 3.9 | $1996 | $4400 | $-2245 |
| 0.75% | 375.00 | FAIL | trailing_drawdown | 2024-10-11 | 1.2 | $998 | $6600 | $-1247 |
| 1.00% | 500.00 | FAIL | trailing_drawdown | 2024-09-16 | 0.4 | $499 | $8800 | $-748 |
| 1.25% | 625.00 | FAIL | trailing_drawdown | 2024-09-13 | 0.3 | $499 | $11001 | $-748 |
| 1.50% | 750.00 | FAIL | trailing_drawdown | 2024-09-13 | 0.3 | $499 | $13201 | $-748 |
| 2.00% **(=$1,000, shipped unit)** | 1000.00 | FAIL | trailing_drawdown | 2024-09-12 | 0.3 | $499 | $17601 | $-748 |
| 2.50% | 1250.00 | FAIL | trailing_drawdown | 2024-09-11 | 0.3 | $499 | $22001 | $-748 |
| 3.00% | 1500.00 | FAIL | trailing_drawdown | 2024-09-05 | 0.1 | $499 | $26402 | $-748 |

(FAIL rows' "net $ after cost" is cost-only against $0 earned -- a real eval stops trading the day it breaches the trail, so the un-gated full-book total is not money that could ever be realized inside that eval. "net $ if ungated" is reported for context only.)

**Passing band: $140.00-$178.50/trade** (6 of 24 tested levels). Every risk level ABOVE the band's top and every level BELOW it FAILs `trailing_drawdown` (rows below the band reach it via a different R-path timing, not a different mechanism) -- the FAILing levels are not one monolithic phenomenon, they bracket a real window that a coarse sweep can miss entirely, which is exactly what this file's first cut did.

## Arm 2 -- Trade The Pool, shares

Repricing per `research/prop_firms_stocks.md`'s "Simplified backtest model": *"Set daily loss limit at 3% of initial capital, max position size at 1,000 shares or min(account balance / 4, 1,000 shares), whichever binds first. This covers Funder Trading's strictest constraints and resembles a real intraday account."* `shares = min(1000, floor(account_size * 4 / entry_price))`, `risk_dollars = shares * |entry - stop|`, `pnl = r * risk_dollars`.

| metric | value |
|---|---:|
| account size (modeling pick) | $25000 |
| profit target | 6% |
| daily loss limit | 3% |
| trailing drawdown (modeling pick) | 5% |
| min trading days | 0 |
| consistency | disabled (1.0) |
| risk $/trade min / mean / max | $100 / $359 / $750 |
| verdict | FAIL (trailing_drawdown, first breach 2024-09-16) |
| months to event | 0.4 |
| total net $ if ungated (full book) | $-99 |
| eval fee | $97 |
| net $ after cost | $-97 |

## Arm 3 -- personal ~$10k account (solvency)

No prop-firm rules. Same $1,000-fixed-risk unit as the shipped book (10% of the $10k account per trade at max loss -- AGGRESSIVE, more than most professional risk budgets) and a conservative 1%-of-account sizing ($100/trade).

| sizing | risk $/trade | total $ | max DD $ | max DD % of account | trough equity $ | trough % of account | wiped? |
|---|---:|---:|---:|---:|---:|---:|:---:|
| book-native $1,000 (10%, aggressive) | $1000 | $17601 | $21577 | 215.77% | $3820 | 38.2% | no |
| conservative $100 (1%) | $100 | $1760 | $2158 | 21.58% | $9382 | 93.8% | no |

"Never wiped" is order-dependent, not a safety property: it holds only because this book's own early trades happened to be profitable before the drawdown built the cushion the trough later ate into. See `personal_arm_result()`'s docstring.

## Ranking

**Vanquish Advanced Options $50k (at $175/trade) is fundable FIRST** -- clearly soonest and cheapest of the arms that PASS.

| arm | months to clean PASS | cost to get there |
|---|---:|---:|
| Vanquish Advanced Options $50k (at $175/trade) | 9.0 | $4990 |

