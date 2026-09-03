# G7.1 adversarial verify — track "scanners" — VERDICT: REFUTED

CLAIM: "Two live-only scanners have never appeared in any backtest number:
a 50/200-SMA regime filter that can block an entire day's longs or shorts,
and the news-day halt."

## 1. The news halt IS in backtest_week.py — the very file the evidence cites

- `backtest_week.py:1107-1112` `_load_news_days()` reads `news_days.json`
- `backtest_week.py:1127-1128` `--skip-news` CLI flag
- `backtest_week.py:1169-1170` `use = [d for d in use if d not in news_days]`
- `backtest_12mo.py:86-108` same flag, same file

The evidence said "not imported by backtest_week.py". True and irrelevant:
it is implemented locally, no import needed. The 12mo number quoted in
`live_scanner.py:91-94` ("news days run 30.6%W vs 37.2% clean") is itself
a backtest number, produced by that flag.

## 2. The regime filter was SELECTED BY a 24-month backtest

- `backtest_regimes_24mo.py:14-20` imports RegimeDetector/RegimeConfig
- `backtest_regimes_24mo.py:123-135` sweeps 7 configs incl. the shipped
  `RegimeConfig(mode=MODE_SMA, directional=True, ±0.05)`
- `backtest_regimes.py`, `backtest_regimes_fast.py` — two more rigs
- `backtest_regime_report.md:3-21` publishes the table: 522 trading days,
  baseline $6,833 / 497 trades vs SMA Directional (5%) $8,926 / 477 trades,
  **+30.6%** — the exact number `live_scanner.py:763` quotes as its reason.

## 3. Reachability — the bug runs OPPOSITE to the claim

**(a) ACTION_STOP is dead code under the shipped config.**
`regime_detector.py:163,169`: with `directional=True` (the live config,
`live_scanner.py:764`) MODE_SMA returns only STOP_SHORT / STOP_LONG.
It can never return ACTION_STOP. So `live_scanner.py:450-451`
(`if regime_action == ACTION_STOP: signals = []`) is unreachable, and the
message at `:346` ("all trades halted") can never print. The claim's
"can block an entire day's longs *or* shorts" overstates it; only one
side is blockable. `backtest_regime_report.md` "Days Stopped: 0" for
that row confirms.

**(b) The regime filter never fires live at all.**
`live_scanner.py:764` -> `fetch_spy_daily_closes(days_back=400)` ->
`market_data.py:53-67 fetch_daily_closes()` reads ONLY the local
`data_archive/SPY/*.csv` cache ("read-only, no API calls").
Measured 2026-08-29: 263 days returned, newest = **2026-08-11**, 18 days
stale; today is absent by construction (today's daily close does not exist
during 09:30-11:00). `regime_detector.py:274-278` `get_action(today)` then
hits `except ValueError -> (REGIME_UNKNOWN, ACTION_NORMAL)`.
=> `regime_action` is ACTION_NORMAL on every live day; the whole block at
`live_scanner.py:450-455` is unreachable live. The startup banner still
prints "Regime filter active: SMA Directional (5%) — 263 days loaded".
It is not an unmeasured live risk; it is a measured filter that is silently
off.

## 4. Look-ahead in the backtest arm
`regime_detector.py:148` `closes = self._daily_closes[:day_idx + 1]` — the
decision for day D uses D's own daily close, unknown at 09:30-11:00.
The +30.6% in `backtest_regime_report.md` carries that look-ahead.

## 5. Wrong book, and the count is wrong
`research/bt2y_trades.json` meta: 76,019 signal rows, **2,437 traded**,
857 halted, 500 sessions, 2024-08-21 -> 2026-08-21. The stated
"2,595-trade post-T0 book" does not match the committed book.

## 6. Replayed both filters over the right book (2,437 traded)
Script: `research/g71_scanners_verify.py` (read-only).

| arm | n | mean R | win | sum R |
|---|---:|---:|---:|---:|
| baseline (no filter) | 2437 | +0.5495 | 49.7% | +1339.1 |
| SKIP_NEWS=1 (80 news days in window) | 2050 | +0.5697 | 50.3% | +1167.8 |
| regime filter, live config | 2240 | +0.5643 | 50.0% | +1264.1 |

Regime actions over the 496 book days: normal 387, stop_short 64,
stop_long 25, caution 20, **stop 0**.
Both filters move mean R by <= +0.021R — far inside the ±1.5799R error bar
(omen-error-bar-exceeds-arms) — and both REDUCE total R. Even a corrected
version of the claim describes a nothing-lever, not a hidden risk.

## What survives
Only this: neither filter is wired into `backtest_2y.py` — it has no
`--skip-news` arg (`:87-89`) and no regime import, and it imports
`simulate_day` directly (`:18`), bypassing `backtest_week.main()`'s
day-filter. So the *current* 2y book is unfiltered. That is a much smaller
statement than "never appeared in any backtest number", and the measured
effect of closing it is +0.015 to +0.020 mean R with lower total R.

## Suggested diff (NOT applied) — make the live regime filter honest
```diff
--- a/live_scanner.py
+++ b/live_scanner.py
@@
-        regime_det.feed_daily_closes(spy_dates, spy_closes)
-        print(f"  Regime filter active: SMA Directional (5%) — {len(spy_dates)} days loaded")
+        regime_det.feed_daily_closes(spy_dates, spy_closes)
+        _today = now_et().date().isoformat()
+        if _today not in spy_raw:
+            print(f"  Regime filter INERT: no SPY daily close for {_today} "
+                  f"(newest cached {spy_dates[-1] if spy_dates else 'none'}) — "
+                  f"get_action() returns NORMAL every day. Feed prior-close-based "
+                  f"regime or disable.")
```
The real fix is to evaluate the regime on the **prior** session's close
(`day_idx - 1`), which also removes the look-ahead in §4.
