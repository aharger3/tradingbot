# g202 — REFUTE #2 of P3 (Trade The Pool / personal $10k), multiplicity + sampling lens

**Verdict: REFUTED.** P3's "Trade The Pool never passes on any of 8 account/plan rows" is eight
correlated readings of **one** equity path starting 2024-09-03 — sweep the start date instead and
**every one of the 8 rows passes between 10.3% and 41.5% of start dates**; the "net −$97 to −$1,100"
range is literally the eval-fee column, not a measured outcome; and the personal arm's $35.56/day
sits inside a bootstrap interval of **−$59.92 to +$131.84** with a 23.4% chance of being ≤ $0, with
**one day worth 34.1% of the whole total**.

Script: `research/g202_p3_refute2.py` → `research/g202_p3_refute2.json`. Same fill as P3: signal bar
CLOSE entry, `stop_rule.stop_fill_price` stops, size-gated on `signal_runner.min_risk_floor`,
1R = $1,000, one-trade-a-day unit `research/omen_metrics.first_of_day_arm` (verified byte-identical
to the `g116.build_arm` A_base stream P3 uses — 495 sessions, same days), book
`research/bt2y_trades_retest_on.json`. H1 = day < 2025-09-01 (n=248), H2 = 2025-09-01 on (n=247).
Seed 20260905.

---

## 1. This is the P1 bug again: one start date presented as eight tests

P3 reports 30 cells (8 firm rows × {full, H1, H2}, plus 2 personal sizings × 3). **All 30 replay the
same trade sequence from the same first day.** H1 is not a replication of full — it is a *prefix* of
it, starting on the identical day (2024-09-03), which is why all 8 H1 rows report `months_to_event`
identical to the full-book rows to three decimals. The number of independent start dates evaluated
is **one**.

A real evaluation starts the day you buy it. Sweeping every start date in the book, and *also*
enforcing the plan's own `max_days` window that P3's caveat admits it does not enforce:

| firm/plan | P3 as written (uncapped sizing) | with the DLL share cap restored (§2) |
|---|---:|---:|
| | pass rate, in-window starts | pass rate, in-window starts |
| TTP 25K MAX day (cap 60) | 61/436 = **14.0%** | 114/436 = **26.1%** |
| TTP 50K MAX day (cap 60) | 45/436 = **10.3%** | 96/436 = **22.0%** |
| TTP 100K MAX day (cap 60) | 81/436 = **18.6%** | 143/436 = **32.8%** |
| TTP 200K MAX day (cap 60) | 62/436 = **14.2%** | 61/436 = **14.0%** |
| TTP 25K FLEX day (cap 120) | 96/376 = **25.5%** | 132/376 = **35.1%** |
| TTP 50K FLEX day (cap 120) | 142/376 = **37.8%** | 156/376 = **41.5%** |
| TTP 100K FLEX day (cap 120) | 144/376 = **38.3%** | 146/376 = **38.8%** |
| TTP 200K FLEX day (cap 120) | 95/376 = **25.3%** | 95/376 = **25.3%** |

Not one row is at 0%. **"Never passes" is false as stated.** The honest sentence is *"passes 10–42%
of start dates, so buying one eval is a coin-flip you lose most of the time"* — a different and much
weaker claim, and one the morning report already had to publish for P1 after the same mistake
(`window = min(252, n)` evaluating exactly one window; corrected all-starts rates 12–27%).

Why one start date is so misleading here: the single best day in the whole book, **2024-09-06 MU at
+6.00R**, is the *third* session of the arm. It sits inside the opening window of every P3
evaluation, inflates the peak equity every trailing-drawdown check then measures down from, and the
DLL-capped rows all breach within days of it (2024-09-13, 09-16, 10-01, 10-02, 10-11). The verdict is
being set by roughly the first two weeks of one particular book.

## 2. A mechanism the report says is present is missing — and it is the rule 4 of 8 rows fail on

`research/g173_shares_personal_refresh.md` states the TTP mechanics — *"(share cap, daily-loss-limit
cap)"* — are **"unchanged from `research/g120_prop_arms.py` (arm 2)"**. They are not.
`g120.pool_series` calls `shares_for(..., daily_loss_limit_pct=POOL_KW["daily_loss_limit_pct"])`
(g120's own "ADVERSARIAL FIX #2"). `g173.pool_series_for_account` omits that argument, so
`shares_for` runs with `daily_loss_limit_pct=None` and the cap never applies:

| firm/plan | daily loss limit | P3's max per-trade risk | trades sized over the limit | P3 verdict | verdict with cap restored |
|---|---:|---:|---:|---|---|
| TTP 25K MAX | $250 | **$1,612** (6.4×) | 305/495 (61.6%) | FAIL (daily_loss_limit) | FAIL (trailing_drawdown) |
| TTP 50K MAX | $500 | **$3,225** (6.4×) | 243/495 (49.1%) | FAIL (daily_loss_limit) | FAIL (trailing_drawdown) |
| TTP 100K MAX | $1,000 | **$6,449** (6.4×) | 126/495 (25.5%) | FAIL (daily_loss_limit) | FAIL (trailing_drawdown) |
| TTP 200K MAX | $2,000 | **$6,890** (3.4×) | 38/495 (7.7%) | FAIL (daily_loss_limit) | FAIL (trailing_drawdown) |
| TTP 25K FLEX | $500 | $1,612 | 114/495 (23.0%) | FAIL (trailing_drawdown) | FAIL (trailing_drawdown) |
| TTP 50K FLEX | $1,000 | $3,225 | 78/495 (15.8%) | FAIL (trailing_drawdown) | FAIL (trailing_drawdown) |
| TTP 100K FLEX | $2,000 | $6,449 | 25/495 (5.1%) | FAIL (trailing_drawdown) | FAIL (trailing_drawdown) |
| TTP 200K FLEX | $4,000 | $6,890 | 7/495 (1.4%) | FAIL (trailing_drawdown) | FAIL (trailing_drawdown) |

**Once the cap is restored, not a single row fails on `daily_loss_limit`.** The claim's own words —
*"daily loss limit breached"* — describe a breach caused by taking positions the account was never
permitted to hold. On the 25K MAX row, 61.6% of trades are sized above the limit they are then judged
against. This is not a small correction: it is what lifts the 25K MAX pass rate from 14.0% to 26.1%
in §1.

## 3. "net −$97 to −$1,100" is the fee column, not a measurement

In `ttp_row_result`, a FAIL sets `net_after_cost = -fee` unconditionally. Checked across all 24 TTP
cells in `g173_shares_personal_refresh.json`: **every reported net equals minus that row's eval fee**,
and the four distinct values (−97, −230, −435, −1100) are the four fee values in `TTP_ROWS` verbatim.
The range carries **zero information from the trading** — it would read the same on a book of pure
noise, or a book of nothing but winners that happened to breach. Quoting it as an outcome ("net after
fees −$97 to −$1,100") implies a measured loss that was never measured.

## 4. The personal $10k arm is inside its own noise, and one day is a third of it

Paired bootstrap over the 495 sessions (the resampling unit is the session, 20,000 draws):

| quantity | value |
|---|---:|
| $/day at $1,000/trade | **$35.56** |
| standard error | **$48.71** |
| bootstrap 95% CI | **−$59.92 to +$131.84** |
| P(true $/day ≤ 0) | **23.4%** |
| total over the book | $17,601 |
| best single day (2024-09-06 MU, +6.00R) | $6,000 = **34.1% of the total** |
| top 5 days | **138.9% of the total** |
| $/day with the best day removed | **$23.48** |

$35.56/day is **0.73 standard errors from zero**. It cannot be reported as a rate the account "pays".
The $3.56/day figure is not a second, independent measurement either — it is the same number divided
by ten, since the personal arm is linear in risk-per-trade; it inherits the identical CI scaled by
0.1 (−$5.99 to +$13.18) and the identical 23.4% chance of being ≤ 0.

The split is worse than the whole: H1 $140.29/day (se $76.19), H2 **−$69.60/day** (se $60.07). And
P3's own JSON already flags the H2 personal arm at $1,000/trade as **`wiped: YES`** — the account
goes to zero in the second half. "Operable at $1,000/trade" is not supported by the arm that produced
it.

## 5. The 216% drawdown is a draw, not a property

`personal_arm_result` carries an honest caveat that the path is order-dependent; here is the size of
that dependence. Holding the same 495 R-multiples and reshuffling their order 2,000 times, at
$1,000/trade on $10,000:

| | max drawdown | % of account |
|---|---:|---:|
| P3's reported (actual order) | $21,577 | 215.8% |
| shuffle median | $19,370 | 193.7% |
| shuffle 5th–95th pct | $13,098 – $31,436 | 131% – 314% |
| shuffles worse than P3's | **35.5%** | |

$21,577 is an unremarkable draw from a wide distribution, not a characteristic of the strategy. The
robust statement is *"drawdown at $1,000/trade on $10k is 131%–314% of the account depending on
order — i.e. this sizing is unsurvivable in any ordering"*, which is a stronger and safer claim than
the specific 216%.

---

## What survives

The **direction** does. On this book, from its own first day, the engine does not clear a Trade The
Pool evaluation, and no personal sizing on $10k produces a rate anywhere near the $397/day bar. The
morning report's rung-2 and rung-4 conclusions ("fails", "operable, not fundable") are not overturned
in spirit.

What does not survive is every specific number the claim cites:

| claim as stated | status |
|---|---|
| "never passes on any of 8 account/plan rows" | **false** — 10.3%–41.5% of start dates pass, 8/8 rows |
| "daily loss limit breached" (4 of 8 rows) | **artifact** — the DLL share cap the report says is present was dropped; with it restored, 0 of 8 rows fail on that rule |
| "net after fees −$97 to −$1,100" | **not a measurement** — it is the eval-fee column by construction |
| "$1,000/trade pays $35.56/day" | **inside noise** — CI −$59.92 to +$131.84, P(≤0) = 23.4%, one day = 34.1% of the total |
| "1% risk pays $3.56/day" | **not independent** — the same number ÷ 10 |
| "$21,577 drawdown (216%)" | **one ordering** — shuffle range 131%–314%, 35.5% of orderings worse |
| the H1/H2 split validates it | **no** — H1 is a prefix of full from the identical start day; 30 cells, 1 independent start date |

**One-line replacement for the ladder table, rung 2:** *"Trade The Pool passes 10–42% of start dates
depending on plan; buying one evaluation is a bet you lose about three times in four, and the
whole-book edge ($35.56/day, CI −$60 to +$132) is not distinguishable from zero."*
