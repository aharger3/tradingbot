# C8 — Two-consecutive-losses = quit day (12mo A/B sim)

**Date:** 2026-07-13 · **Data:** `research/c1_off_charts.json` (clean 12mo baseline, 671 traded / 866 signals) · **Script:** `research/c8_loss_halt.py` · **Method:** SIMULATION over existing baseline — no bot-code edits, no config change, no new backtest.

## 1. What the CURRENT loss-halt actually is

Read-only trace through config + signal path:

| Source | Behavior |
|---|---|
| `config.yaml:15` | `consecutive_loss_halt: 2` |
| `config.yaml:1,26` | `max_loss: 1000`, `stop_after_win: true` |
| `omen_bot.py:652-657` | `TradingSession.day_ended()` → `consecutive_losses >= 2 OR signals_today >= max_signals_per_day(3)` |
| `live_scanner.py:607` | `max_losses = CONSECUTIVE_LOSS_HALT` env (default `2`) → passed as `max_consecutive_losses` |
| `live_scanner.py:62-66` | `STOP_AFTER_WIN` (default on) — first recorded win ALSO ends the day (paper mode only, win feedback) |
| `live_scanner.py:485,488` | tier gate: `TRADE` only while `consecutive_losses < 2` |

**The rulebook hard rule "two consecutive losses = quit day" IS the config's current `consecutive_loss_halt: 2` IS `omen_bot.day_ended()`. Same rule, three names.** There is nothing to A/B "vs current" — they are identical.

**Critical:** the backtest does NOT simulate this governor. `grep` of `backtest_12mo.py` for `halt / consecutive / day_ended / stop_after` = zero hits. The 671-trade baseline is raw detector output (all A+/A/B signals, no per-day session cap, no loss-halt, no stop-after-win). So the "current baseline" the backtest reports = **no-halt**. Per the task's fallback ("if same rule, A/B halt-at-2 vs no-halt vs halt-at-1 for sensitivity"), that is what we run.

To isolate the loss-halt dimension, the sim layers ONLY the consecutive-loss governor on the raw baseline — no max-trades cap, no stop-after-win (those are separate live governors; mixing them would muddy the loss-halt signal). One shared session per day across all symbols (matches live: `consecutive_losses` is portfolio-wide, not per-symbol).

## 2. Sensitivity A/B — full population

Replay 671 traded signals chronologically per day; `consecutive_losses` resets on win, +1 on loss; at N the session stops for the day.

| Variant | tr/yr | win% | $/yr |
|---|---|---|---|
| no-halt (raw = current backtest baseline) | 671 | 37.4% | $78,190 |
| halt-at-1 (quit after 1st loss) | 308 | 40.6% | $69,489 |
| **halt-at-2 (= rulebook hard rule = config current)** | 503 | 37.6% | **$65,317** |

halt-at-2 cuts $12,873/yr (−16.5%) vs no-halt. The 168 trades it suppresses (those scheduled after a 2-loss streak already hit) are net-positive as a block — the governor throws away follow-through that would have recovered. halt-at-1 lifts win% 3.2pp but still loses $8.7k vs no-halt (kills profitable 2nd/3rd trades after a single loss).

## 3. Sensitivity A/B — tier (S≥4 + [hammer], max 2/day, stop-when-green)

| Variant | tr/yr | win% | $/yr |
|---|---|---|---|
| tier no-halt (current tier baseline) | 78 | 42.3% | $21,000 |
| tier halt-at-1 | 72 | 43.1% | $21,000 |
| tier halt-at-2 (= rulebook hard rule) | 78 | 42.3% | $21,000 |

**halt-at-2 is a no-op at the tier** — exactly as predicted: the tier's existing `max 2/day` cap means a 2-loss day already hit the trade ceiling, so "quit after 2 losses" never fires an extra suppression. halt-at-1 trims 6 trades for a 0.8pp win% bump and $0 change.

## 4. Verdict

**Rulebook "2 consecutive losses = quit day" = config `consecutive_loss_halt: 2` = current code — already wired, identical rule. Do NOT change config.**

- **Tier:** the rule is redundant — `max 2/day + stop-when-green` already encodes the spirit and dominates it (halt-at-2 = no-op, $21k either way). No action.
- **Full-pop:** applying the governor to the unfiltered population is harmful — it cuts −$13k/yr (−16.5%) by stopping net-positive follow-through trades. The backtest's no-halt baseline already outperforms every halt variant on $/yr.
- **Net:** the rule is correctly NOT enforced in backtest (the data shows that would lose money), and correctly IS redundant at the live tier. The rulebook hard rule is already satisfied by existing config + tier caps. **No flag, no config change, defer to C10.** If C10 ever wants a stricter daily guard, halt-at-1 is the only one that moves win% (308 tr 40.6%W) and it costs $9k/yr — a defensibility-for-dollars trade, not a clear win.
