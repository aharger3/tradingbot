# g173 -- shares prop (Trade The Pool) + personal $10k refresh

What's different: Trade The Pool is now priced across all 8 real account/plan rows (25K/50K/100K/200K x MAX/FLEX day), not one $25,000 pick, and every arm carries H1/H2 alongside full-book -- same 495-session A_base candidate stream (`research/bt2y_trades_retest_on.json`, RETEST_REQUIRED=1), split at 2025-09-01 (H1 n=248, H2 n=247).

Fill: signal bar CLOSE entry, `stop_rule.stop_fill_price` stops, size-gated on `signal_runner.min_risk_floor`. Script: `research/g173_shares_personal_refresh.py`. TTP shares mechanics (share cap, daily-loss-limit cap) and personal-account mechanics are unchanged from `research/g120_prop_arms.py` (arm 2 / arm 3) -- this file adds the firm-row sweep and the H1/H2 split.

## Caveat

Each TTP row's `max_days` (60 MAX / 120 FLEX) is a real evaluation-window clock this arm does NOT enforce -- `evaluate_prop_challenge` has no day-count cutoff. A pass whose `window_days_used` exceeds the plan's window is flagged `exceeds_plan_window: true` below rather than silently counted as a clean pass.

## Trade The Pool, shares -- all 8 firm rows

### full

| firm/plan | account | n trades | verdict | months to event | window used (cap) | net after cost |
|---|---:|---:|---|---:|---|---:|
| TTP 25K MAX day | $25,000 | 495 | FAIL (daily_loss_limit) | 0.0 | - (cap 60) | $-97 |
| TTP 50K MAX day | $50,000 | 495 | FAIL (daily_loss_limit) | 0.2 | - (cap 60) | $-230 |
| TTP 100K MAX day | $100,000 | 495 | FAIL (daily_loss_limit) | 0.2 | - (cap 60) | $-435 |
| TTP 200K MAX day | $200,000 | 495 | FAIL (daily_loss_limit) | 1.0 | - (cap 60) | $-1100 |
| TTP 25K FLEX day | $25,000 | 495 | FAIL (trailing_drawdown) | 0.3 | - (cap 120) | $-97 |
| TTP 50K FLEX day | $50,000 | 495 | FAIL (trailing_drawdown) | 0.3 | - (cap 120) | $-230 |
| TTP 100K FLEX day | $100,000 | 495 | FAIL (trailing_drawdown) | 0.9 | - (cap 120) | $-435 |
| TTP 200K FLEX day | $200,000 | 495 | FAIL (trailing_drawdown) | 1.2 | - (cap 120) | $-1100 |

### H1

| firm/plan | account | n trades | verdict | months to event | window used (cap) | net after cost |
|---|---:|---:|---|---:|---|---:|
| TTP 25K MAX day | $25,000 | 248 | FAIL (daily_loss_limit) | 0.0 | - (cap 60) | $-97 |
| TTP 50K MAX day | $50,000 | 248 | FAIL (daily_loss_limit) | 0.2 | - (cap 60) | $-230 |
| TTP 100K MAX day | $100,000 | 248 | FAIL (daily_loss_limit) | 0.2 | - (cap 60) | $-435 |
| TTP 200K MAX day | $200,000 | 248 | FAIL (daily_loss_limit) | 1.0 | - (cap 60) | $-1100 |
| TTP 25K FLEX day | $25,000 | 248 | FAIL (trailing_drawdown) | 0.3 | - (cap 120) | $-97 |
| TTP 50K FLEX day | $50,000 | 248 | FAIL (trailing_drawdown) | 0.3 | - (cap 120) | $-230 |
| TTP 100K FLEX day | $100,000 | 248 | FAIL (trailing_drawdown) | 0.9 | - (cap 120) | $-435 |
| TTP 200K FLEX day | $200,000 | 248 | FAIL (trailing_drawdown) | 1.2 | - (cap 120) | $-1100 |

### H2

| firm/plan | account | n trades | verdict | months to event | window used (cap) | net after cost |
|---|---:|---:|---|---:|---|---:|
| TTP 25K MAX day | $25,000 | 247 | FAIL (daily_loss_limit) | 0.1 | - (cap 60) | $-97 |
| TTP 50K MAX day | $50,000 | 247 | FAIL (daily_loss_limit) | 0.4 | - (cap 60) | $-230 |
| TTP 100K MAX day | $100,000 | 247 | FAIL (daily_loss_limit) | 0.4 | - (cap 60) | $-435 |
| TTP 200K MAX day | $200,000 | 247 | FAIL (trailing_drawdown) | 2.4 | - (cap 60) | $-1100 |
| TTP 25K FLEX day | $25,000 | 247 | FAIL (trailing_drawdown) | 1.0 | - (cap 120) | $-97 |
| TTP 50K FLEX day | $50,000 | 247 | FAIL (trailing_drawdown) | 1.0 | - (cap 120) | $-230 |
| TTP 100K FLEX day | $100,000 | 247 | FAIL (trailing_drawdown) | 1.1 | - (cap 120) | $-435 |
| TTP 200K FLEX day | $200,000 | 247 | FAIL (trailing_drawdown) | 3.2 | - (cap 120) | $-1100 |

## Personal $10k -- $100 and $1,000 risk/trade

### full

| sizing | risk/trade | total $ | max DD $ | max DD % acct | wiped? |
|---|---:|---:|---:|---:|---|
| book_native_1000 | $1000 | $17601 | $21577 | 215.77% | no |
| conservative_1pct | $100 | $1760 | $2158 | 21.58% | no |

### H1

| sizing | risk/trade | total $ | max DD $ | max DD % acct | wiped? |
|---|---:|---:|---:|---:|---|
| book_native_1000 | $1000 | $34793 | $13980 | 139.80% | no |
| conservative_1pct | $100 | $3479 | $1398 | 13.98% | no |

### H2

| sizing | risk/trade | total $ | max DD $ | max DD % acct | wiped? |
|---|---:|---:|---:|---:|---|
| book_native_1000 | $1000 | $-17192 | $21577 | 215.77% | YES |
| conservative_1pct | $100 | $-1719 | $2158 | 21.58% | no |
