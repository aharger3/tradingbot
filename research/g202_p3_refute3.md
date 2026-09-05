# g202 — P3 refuter #3 (reproduce / null control / adversarial)

**REFUTED on mechanism, upheld on direction.** g173 reproduces byte for byte, but the headline
sentence is wrong about *why* Trade The Pool fails: g173's own report says it carries g120 arm 2's
daily-loss-limit share cap and **the code does not pass that argument**, so 62% of trades on the
25K MAX row are sized above the daily loss limit a real TTP account would have refused. Put the cap
back — the mechanic the report claims — and **zero of eight rows fail on the daily loss limit**;
all eight fail on trailing drawdown, and the headline "0.0 months" becomes 0.33 months. The
verdict (8 of 8 FAIL, net −$97 to −$1,100) and the personal-account numbers survive; the personal
$1,000/trade arm is separately shown to be un-executable.

Script: `research/g202_p3_refute3.py` → `research/g202_p3_refute3.json`.
Fill: signal bar CLOSE entry, `stop_rule.stop_fill_price` stops, size-gated on
`signal_runner.min_risk_floor`, 1R = $1,000, book `research/bt2y_trades_retest_on.json`
(RETEST_REQUIRED=1), one-trade-a-day arm `research/omen_metrics.first_of_day_arm` via
`g116_sizing_kelly_options.build_arm(keep=all)`, n=495 (2024-09-03..2026-09-02), H1=248 / H2=247
split at 2025-09-01.

---

## 1. Reproduction — clean

`python research/g173_shares_personal_refresh.py` rewrote both outputs to the same bytes.

| file | md5 before | md5 after |
|---|---|---|
| `research/g173_shares_personal_refresh.md` | `4113849fac7582e2a6fb6389073595af` | identical |
| `research/g173_shares_personal_refresh.json` | `f9e82c81208ac5357136fce5ed14507f` | identical |

`diff` empty on both. Every number in the claim — 8 FAIL rows, 0.0–1.2 months, −$97/−$230/−$435/
−$1,100, $3.56/day, $35.56/day, $21,577 DD, 215.77% — is what the committed script prints.

---

## 2. Null controls — the rig is sound, but the FAIL verdict is nearly content-free

### B. Zero-edge placebo (r = 0 on all 495 trades, same days, symbols, prices, share counts)

A working rig must breach nothing. It breaches nothing.

| arm | result |
|---|---|
| all 8 TTP rows | `profit_target_not_reached`, no `daily_loss_limit`, no `trailing_drawdown` |
| personal $10k, both sizings | total $0, max DD $0, min equity $10,000, wiped = no |

Placebo produces zero. **Passes.**

### D. Perfect-trader control (r = +2.0 on every trade)

Needed to prove "8 of 8 FAIL" is not a stuck needle. All 8 rows PASS in 0.10–0.46 months, net
+$1,562 to +$10,980. **Passes.**

### C. Coin-flip control (r = ±1 at random, 200 seeds, same sizing) — this one hurts

A **zero-expectancy** trader run through the identical rig:

| firm/plan | FAIL daily_loss_limit | FAIL trailing_drawdown | **PASS** | OMEN's verdict |
|---|---:|---:|---:|---|
| TTP 25K MAX day | 186 | 5 | **9 (4.5%)** | FAIL daily_loss_limit |
| TTP 50K MAX day | 182 | 6 | **12 (6.0%)** | FAIL daily_loss_limit |
| TTP 100K MAX day | 180 | 11 | **9 (4.5%)** | FAIL daily_loss_limit |
| TTP 200K MAX day | 157 | 30 | **13 (6.5%)** | FAIL daily_loss_limit |
| TTP 25K FLEX day | 108 | 54 | **38 (19.0%)** | FAIL trailing_drawdown |
| TTP 50K FLEX day | 49 | 102 | **49 (24.5%)** | FAIL trailing_drawdown |
| TTP 100K FLEX day | 18 | 123 | **59 (29.5%)** | FAIL trailing_drawdown |
| TTP 200K FLEX day | 38 | 111 | **51 (25.5%)** | FAIL trailing_drawdown |

On the headline 25K MAX row, a random number generator lands on **the same fail reason 93% of the
time**. On the FLEX rows a coin flip *passes* the evaluation 19–29.5% of the time and OMEN's real
book never does. So "TTP never passes" is a statement about the *position-sizing model plus this
book's particular loss ordering*, not evidence about the engine's edge — you would draw the same
conclusion from noise. The claim is not false, it is **not discriminating**.

---

## 3. Adversarial variant — the daily-loss-limit share cap that g173 says it has and does not

`g120_prop_arms.pool_series()` calls
`shares_for(entry, stop, daily_loss_limit_pct=POOL_KW["daily_loss_limit_pct"])` — its
"ADVERSARIAL FIX #2", written in the 2026-09-03 refute pass precisely because trades were being
sized above the firm's own daily loss limit. g173's `pool_series_for_account()` calls
`shares_for(r["entry"], r["stop"], account=account)` — **the argument is dropped**, while g173's
report states "TTP shares mechanics (share cap, daily-loss-limit cap) … unchanged from
`research/g120_prop_arms.py` (arm 2)".

What that costs, on the shipped (uncapped) arm:

| firm/plan | daily loss limit | mean risk/trade | trades sized **over** the DLL |
|---|---:|---:|---:|
| TTP 25K MAX day | $250 | **$372** | **62%** |
| TTP 50K MAX day | $500 | $611 | 49% |
| TTP 100K MAX day | $1,000 | $800 | 25% |
| TTP 200K MAX day | $2,000 | $867 | 8% |
| TTP 25K FLEX day | $500 | $372 | 23% |
| TTP 50K FLEX day | $1,000 | $611 | 16% |
| TTP 100K FLEX day | $2,000 | $800 | 5% |
| TTP 200K FLEX day | $4,000 | $867 | 1% |

Mean risk is 49% **above** the daily loss limit on the headline row. A DLL breach is arithmetically
guaranteed on the first loser — which is exactly what "0.0 months" means.

### Re-run with the cap reinstated (full book)

| firm/plan | shipped verdict | **capped verdict** | shipped months | **capped months** | mean risk after cap | over DLL | net |
|---|---|---|---:|---:|---:|---:|---:|
| TTP 25K MAX day | FAIL daily_loss_limit | **FAIL trailing_drawdown** | 0.0 | **0.33** | $227 | 0% | −$97 |
| TTP 50K MAX day | FAIL daily_loss_limit | **FAIL trailing_drawdown** | 0.23 | **0.33** | $412 | 0% | −$230 |
| TTP 100K MAX day | FAIL daily_loss_limit | **FAIL trailing_drawdown** | 0.23 | **0.43** | $631 | 0% | −$435 |
| TTP 200K MAX day | FAIL daily_loss_limit | **FAIL trailing_drawdown** | 0.95 | 0.95 | $788 | 0% | −$1,100 |
| TTP 25K FLEX day | FAIL trailing_drawdown | FAIL trailing_drawdown | 0.33 | 0.33 | $328 | 0% | −$97 |
| TTP 50K FLEX day | FAIL trailing_drawdown | FAIL trailing_drawdown | 0.33 | 0.33 | $558 | 0% | −$230 |
| TTP 100K FLEX day | FAIL trailing_drawdown | FAIL trailing_drawdown | 0.92 | 0.92 | $758 | 0% | −$435 |
| TTP 200K FLEX day | FAIL trailing_drawdown | FAIL trailing_drawdown | 1.25 | 1.25 | $855 | 0% | −$1,100 |

**4 of 8 rows change their stated cause of death.** "Daily loss limit breached inside 0–1.2 months"
goes to **zero of eight rows**; the honest sentence is *trailing drawdown breached in 0.33–1.25
months*. H1 is identical to full (0.33–1.25 months, all trailing drawdown); H2 runs 0.99–3.19
months, all trailing drawdown. Net after cost is unchanged at −$97 to −$1,100 in every arm,
because a FAIL always books fee-only.

**Not fixed by this:** the `max_days` window is still unenforced (g173 flags this itself), and
`trailing_dd` type/size for TTP remains a modelling pick carried from `g71_propfirm_sim.py`.

---

## 4. Personal $10k — numbers reproduce, the $1,000/trade arm is not executable

Reproduced exactly: $3.56/day at 1% risk ($1,760.10 / 495), $35.56/day at $1,000/trade
($17,601 / 495), max DD $21,577 = 215.77% of the account.

### The full-book $/day hides a negative second half

| sizing | full | H1 | H2 |
|---|---:|---:|---:|
| $100/trade (1%) | **+$3.56/day** | +$14.03/day | **−$6.96/day** |
| $1,000/trade | **+$35.56/day** | +$140.30/day | **−$69.60/day** |

Neither figure is a forward expectation; the last twelve months lose money at both sizings.

### "Not wiped" is a coin flip on trade order, not a property of the sizing

1,000 random shuffles of the same 495 trades, same sizing:

| sizing | wiped | max DD median | max DD p95 | shipped-order DD |
|---|---:|---:|---:|---:|
| $1,000/trade | **377 / 1,000 (37.7%)** | $19,501 | $31,137 | $21,577 |
| $100/trade | 0 / 1,000 | $1,950 | $3,114 | $2,158 |

The full-book "wiped = no" survives only because this book's early trades were profitable. H2 on
its own wipes the account (min equity −$8,071).

### And the model keeps risking $1,000 after the account cannot fund it

The arm sizes a flat $1,000 even at $3,820 of equity (26% of remaining capital) and past $0. Two
executable variants:

| slice | flat $1,000 capped at equity | fixed 10% of equity |
|---|---|---|
| full | +$17,601, DD $21,577 | **−$5,841**, DD $84,496 |
| H1 | +$34,793 | +$56,550 |
| H2 | **−$10,000, WIPED** | −$9,375 |

The one way to run 10%-of-account risk that a real broker permits — sizing off live equity — turns
the +$17,601 headline into **−$5,841**. **$35.56/day is an artifact of unlimited negative-equity
sizing.** The conservative 1% row ($3.56/day, DD 21.6% of account) is the only personal figure that
is both reproducible and executable, and it is 0.9% of the $397/day bar.

---

## 5. Verdict

| sub-claim | status |
|---|---|
| g173 reproduces byte for byte | **upheld** |
| TTP never passes on any of 8 rows | **upheld** (but a coin flip passes 4.5–29.5% of the time on the same rig — the verdict does not discriminate the edge) |
| "daily loss limit breached" | **REFUTED** — an artifact of a dropped share cap the report claims it applies; 0 of 8 rows fail on DLL once it is restored |
| "inside 0–1.2 months" | **REFUTED as stated** — 0.33–1.25 months with the cap on; the "0.0 months" row does not exist |
| net −$97 to −$1,100 | **upheld**, unchanged under every variant (fee-only on a FAIL) |
| personal 1% pays $3.56/day | **upheld** full-book; H2 is −$6.96/day |
| personal $1,000/trade pays $35.56/day, DD $21,577 = 216% | **REFUTED as a tradeable result** — 37.7% of orderings wipe the account, H2 alone wipes it, and equity-aware 10% sizing pays −$5,841 |

Direction unchanged: **no Trade The Pool row is fundable, and $10k is not fundable.** The reasons
in the P3 report and in the morning report's funding table are wrong and should be restated.

---

## 6. Independent second pass, 2026-09-05 (wave 2 re-dispatch of refuter #3)

This row was re-dispatched and re-run from scratch on HEAD `d19e5fcf` by a second agent that had
not read the section above. It reached the same three conclusions independently, which is the
reason this section exists rather than a rewrite — the findings below are confirmation, not new
claims.

| check | second pass | agrees with above |
|---|---|---|
| `g173_shares_personal_refresh.py` re-run, md5 of both outputs | `4113849f…` / `f9e82c81…`, `diff` empty | yes |
| zero-edge placebo (r = 0), 8 TTP rows | `profit_target_not_reached` on 8/8, **0/8 breach a loss limit**; personal $0.00/day, DD $0 | yes |
| `daily_loss_limit_pct` dropped in `g173.pool_series_for_account` | confirmed; 61.6% of trades on 25K MAX risk more than the whole $250 daily limit (mean risk $372) | yes |
| DLL share cap re-armed per plan row | 8/8 still FAIL, all on `trailing_drawdown`, earliest 0.329 mo; 25K MAX 0.0 → 0.329, 100K MAX 0.23 → 0.427 | yes |
| personal $1,000/trade by half | H1 +$140.29/day · H2 −$69.60/day, **H2 wipes** (min equity −$8,071) | yes |
| order-shuffle wipe rate, $1,000/trade | **686 / 2,000 orderings wipe (34.3%)**, max DD p50 $19,195 / p95 $30,739, min equity p05 −$10,964 (independent seed 20260905, 2,000 draws vs the 1,000 above) | yes — 34.3% vs 37.7% is the same finding at a different draw count |

One point the second pass adds explicitly: **"net −$97 to −$1,100" is not a measurement.** On every
FAIL row `net_after_cost = −eval_fee`, so that range is Trade The Pool's own fee schedule copied out
of `g71_propfirm_sim.py::FIRMS`. It contains no information about this engine and must not be read
as a P&L result in the morning report or the funding-ladder table.

Verdict unchanged: **REFUTED as stated, direction upheld** — no TTP row is fundable and $10k is not
fundable, but the stated failure mechanism ("daily loss limit"), the stated timing ("0.0 months"),
the "net" range, and the personal $35.56/day headline are each wrong for a different reason.
