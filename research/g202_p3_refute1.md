# g202 — refuter #1 (lookahead / leakage) vs P3 — **REFUTED**

**What is different now:** P3's "Trade The Pool never passes" survives, but everything it says about
*why* and everything it says about the personal $10k account does not — the script silently drops the
daily-loss-limit share cap its own report claims to carry, so **305 of 495 trades on the 25K row are
taken at a size that account is not permitted to hold**, and the personal arm risks $1,000 a trade
without ever checking whether a $10k account can buy the shares: **99.8% of those trades need more
notional than the account has, and pricing them at the account's real 4:1 buying power turns
+$35.56/day into −$5.75/day**.

Fill contract for every number below: signal bar CLOSE entry, `stop_rule.stop_fill_price()` stops,
size-gated on `signal_runner.min_risk_floor`, book `research/bt2y_trades_retest_on.json`
(RETEST_REQUIRED=1), one-trade-a-day unit `g116.build_arm(keep=True)` = the A_base arm P3 uses,
495 picks 2024-09-03..2026-09-02, H1 n=248 / H2 n=247 split at 2025-09-01.
Script: `research/g202_p3_refute1.py`, data `research/g202_p3_refute1.json`.

## Verdict per sub-claim

| P3 sub-claim | verdict |
|---|---|
| TTP never passes on any of 8 rows | **stands** — 8/8 still FAIL with the sizing fixed |
| "daily loss limit breached" | **refuted** — 0 of 8 rows fail on the daily loss limit once sizing is legal; all 8 fail on trailing drawdown |
| "inside 0–1.2 months" | **refuted** — 0.3–1.2 months full-book, 1.0–3.2 in H2 |
| "net −$97 to −$1,100" | **stands** — a FAIL books the eval fee either way |
| personal $10k, $1,000/trade pays $35.56/day | **refuted** — **−$5.75/day** at 4:1 buying power, −$1.24/day with the 1,000-share cap the sibling arm carries |
| personal $10k, 1% risk pays $3.56/day | **refuted (degraded)** — $2.38/day; 28.1% of trades are still un-buyable |
| "$21,577 drawdown (216% of account)" | **refuted as stated** — it is 44.7% of the $48,299 peak it drew down from; 216% is a starting-balance denominator, not a drawdown the account ever experienced |

## Lookahead lens — clean, and that is not the problem here

| check | result |
|---|---|
| fields the arm reads | `day, entry, et, r, stop, sym, traded` |
| blacklisted fields consumed (`spy_trend`, `vol_regime`, `out`, `exit`, `pnl`, `cls`, `status`, `scaled`) | **none** — unlike `backtest_2y.spy_trend` in g160, nothing here reads a same-day-inclusive feature |
| `shares_for()` inputs | `entry`, `stop` — both fixed at the signal bar close |
| `pass_day_series()` prefix replay | causal: prefix *i* is evaluated on its own, and `evaluate_prop_challenge` re-detects any earlier breach, so no "pass" is claimed past a fail |
| survivorship filter `traded and r is not None` | **0** traded rows dropped |

The leak is not price information. It is **capital information**: both arms spend buying power the
account does not have at the moment of entry, which is the same bug class one step out — a fill the
account could not have gotten.

## A. The daily-loss-limit share cap was dropped

`g120_prop_arms.pool_series()` calls `shares_for(entry, stop, daily_loss_limit_pct=...)` — its own
"ADVERSARIAL FIX #2", added because "a real Trade The Pool account could not have taken those
position sizes in the first place". `g173_shares_personal_refresh.pool_series_for_account()` calls
`shares_for(r["entry"], r["stop"], account=account)` and **never passes `daily_loss_limit_pct`**,
while the report states the mechanics are "unchanged from `g120_prop_arms.py`".

Full book, all 8 rows:

| firm/plan | DLL | trades risking over the DLL | max risk taken | P3 verdict | verdict with the cap |
|---|---:|---:|---:|---|---|
| TTP 25K MAX | $250 | **305 / 495 (61.6%)** | $1,612 | FAIL(daily_loss_limit) 0.0 mo | FAIL(trailing_drawdown) **0.3 mo** |
| TTP 50K MAX | $500 | 243 / 495 | $3,225 | FAIL(daily_loss_limit) 0.2 mo | FAIL(trailing_drawdown) **0.3 mo** |
| TTP 100K MAX | $1,000 | 126 / 495 | $6,449 | FAIL(daily_loss_limit) 0.2 mo | FAIL(trailing_drawdown) **0.4 mo** |
| TTP 200K MAX | $2,000 | 38 / 495 | $6,890 | FAIL(daily_loss_limit) 1.0 mo | FAIL(trailing_drawdown) **1.0 mo** |
| TTP 25K FLEX | $500 | 114 / 495 | $1,612 | FAIL(trailing_drawdown) 0.3 mo | FAIL(trailing_drawdown) 0.3 mo |
| TTP 50K FLEX | $1,000 | 78 / 495 | $3,225 | FAIL(trailing_drawdown) 0.3 mo | FAIL(trailing_drawdown) 0.3 mo |
| TTP 100K FLEX | $2,000 | 25 / 495 | $6,449 | FAIL(trailing_drawdown) 0.9 mo | FAIL(trailing_drawdown) 0.9 mo |
| TTP 200K FLEX | $4,000 | 7 / 495 | $6,890 | FAIL(trailing_drawdown) 1.2 mo | FAIL(trailing_drawdown) 1.2 mo |

The mechanism inverts because the disaster stop floors every trade at −1.000R
(`DISASTER_STOP_R = 1.0`), so once shares are capped at `floor(DLL / |entry − stop|)` **no single day
can lose the daily limit** — the eval can only die on the trailing drawdown. P3's headline reason is
an artifact of the missing argument.

H2 is where the months move most: the four MAX rows go 0.1 / 0.4 / 0.4 / 2.4 months → **1.0 / 1.0 /
1.1 / 2.4**. H1 is unchanged in verdict (0.3 / 0.3 / 0.4 / 1.0).

**"Never passes" survives.** 8 of 8 rows still FAIL in all three slices, and a FAILed eval still books
only the fee, so −$97 … −$1,100 is unaffected.

## B. The personal $10k arm buys shares it cannot afford

`personal_arm_result()` applies a flat $1,000 of risk per trade with **no share, notional or
buying-power constraint at all** — in the same file that enforces 4:1 buying power and a 1,000-share
cap for Trade The Pool. To risk $1,000 with the book's own stop distances you need a mean position of
**$299,319 of notional**. A $10,000 account at 4:1 can hold **$40,000**.

Full book:

| sizing | constraint | trades it cannot afford | $/day | total | max DD | min equity |
|---|---|---:|---:|---:|---:|---:|
| $1,000/trade | none (**as published**) | 0.0% | **$35.56** | $17,601 | $21,577 | $3,820 |
| $1,000/trade | 4:1 buying power | **99.8%** | **−$5.75** | −$2,847 | $4,772 | $6,514 |
| $1,000/trade | 4:1 BP + 1,000-share cap | 100.0% | **−$1.24** | −$613 | $4,494 | $8,198 |
| $100/trade | none (**as published**) | 0.0% | **$3.56** | $1,760 | $2,158 | $9,382 |
| $100/trade | 4:1 buying power | 28.1% | **$2.38** | $1,178 | $2,051 | $9,140 |

H1 / H2:

| sizing | constraint | H1 $/day | H2 $/day |
|---|---|---:|---:|
| $1,000/trade | none (as published) | $140.29 | −$69.60 |
| $1,000/trade | 4:1 buying power | **$4.91** | **−$16.45** |
| $1,000/trade | 4:1 BP + share cap | $13.15 | −$15.68 |
| $100/trade | none (as published) | $14.03 | −$6.96 |
| $100/trade | 4:1 buying power | $11.37 | −$6.65 |

The $1,000/trade arm's whole apparent edge is leverage the account does not have. Both halves collapse
toward zero and the full book sign-flips negative.

*(If the intended instrument for this arm is options rather than shares — CLAUDE.md says "the
instrument is options, not shares" — then the constraint is premium, not notional, and B does not
apply as written. But the file is `g173_shares_personal_refresh.py`, the arm sits beside a shares arm,
its own note reads "10% of $10k per trade **at max loss**", and no options-premium model is invoked
anywhere in it. On the file's own framing, B stands. Either way P3 cannot claim $35.56/day without
naming which instrument buys it.)*

## C. Two reporting defects that hide the above

1. **`min_equity_ever` was dropped from the markdown.** g120 added it explicitly so the order
   dependence would be "visible, not implied by a bare 'never wiped'". g173's tables print only
   `wiped?`, so full-book reads "no" while the curve passes through **$3,820**, and the JSON's own
   `order_dependent_caveat` never reaches the page.
2. **The personal arm trades past its own wipe.** g120 fixed exactly this for the prop arms — "a
   FAILed eval stops trading the day it breaches, so nothing past that day is real" — and did not fix
   it for the personal arm. In H2 at $1,000/trade the account is **wiped 2026-02-03 after 107
   trades**, and **140 of 247 trades (56%) and −$7,158 of P&L are booked on a dead account**. The
   published H2 total of −$17,192 includes them.
3. **"216% of account" is the wrong denominator.** The $21,577 drawdown runs from a peak of $48,299
   to a trough of $26,722 on 2026-07-02 — **44.7% of the equity it drew down from**. Dividing a
   late-book drawdown by the starting balance makes a survivable drawdown read as an impossibility.

## What P3 should say instead

Trade The Pool never passes on any of 8 account/plan rows — but on **trailing drawdown**, not the
daily loss limit, at **0.3–1.2 months** full-book, once positions are sized to what the account may
legally hold; net after cost −$97 to −$1,100 either way. A personal $10k account trading this book as
shares pays **$2.38/day at 1% risk** and **loses $5.75/day at the book's native $1,000 unit**, because
99.8% of $1,000-risk positions need $299k of notional against $40k of buying power. **No arm here is
fundable, and the personal arm is not a $35/day business — it is a losing one.**
