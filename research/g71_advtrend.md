# G71 / advtrend — adversarial verify of the `with_trend` live/backtest gap

Verdict: **NOT REFUTED.** The mechanism and both headline numbers reproduce exactly.
One embedded figure ("floors 95.3% of the traded book") is wrong, and the claim stops
one step short of the number that matters.

## 1. Mechanism — confirmed

| leg | file:line | what `candles[0]` is |
|---|---|---|
| predicate | `signal_runner.py:2020` | `(candles[-1].close >= candles[0].open) == (d=="call")` |
| backtest | `backtest_week.py:818` `runner.candles = candles[:i+1]` | RTH-only day list — `fetch_week` drops every bar with `t < 09:30` (`backtest_week.py:684-693`) ⇒ `candles[0]` **is** the 09:30 bar |
| recall rig | `research/t4_engine_recall.py:191` (claim said `:196` — off by 5) | same prefix |
| live | `live_scanner.py:378` `fetch_recent_bars(symbol, lookback_minutes=60)` → `:422 runner.candles = candles` | rolling 60-minute buffer |

`tastytrade_feed.py:382-403` sets `fromTime = now − 60 min` with **no RTH filter**, so before
10:30 `candles[0]` can be a premarket bar — the RTH-clamped model is a lower bound there.
For the yfinance fallback (`live_scanner.py:149-154`, `period="1d", prepost=False, .tail(60)`)
the buffer is clamped to today's RTH, so the RTH-clamped model is **exact**, not merely generous.

Also confirmed: `entry_time = c.timestamp` and `entry_idx = i` with `runner.candles = candles[:i+1]`
(`backtest_week.py:818, 862-867`), so the book's `et` bar **is** `candles[-1]`. No look-ahead in
the measurement — only bars at or before the signal bar are read.

## 2. Numbers — reproduced

`python research/g71_trend_livegap.py` reruns to the digit: `2358/2437 = 96.8%` agree,
**79 flips = 3.2%**; after 10:30, `328 rows, 79 flips = 24.1%`.

Independent re-measure (`research/g71_advtrend_livegap_verify.py`), using the entry **bar close**
rather than the entry fill price as `candles[-1].close`:

| px used | fired rows (3,487) | traded rows (2,437) |
|---|---|---|
| `r["entry"]` (original) | 156 = 4.5% | 79 = 3.2% |
| entry-bar close (correct) | 151 = 4.3% | **70 = 2.9%** |

Structural note the claim presents as two findings: flips are **impossible before 10:30**
(`ref_m = max(570, m-60)` collapses to the 09:30 open), and every fired signal sits in
09:35–10:59. So "3.2% of the book" and "24.1% of post-10:30 entries" are the *same* 79 rows.

## 3. Book identity — correct, the prompt's premise is the stale one

`research/bt2y_trades.json` meta: `generated 2026-08-29T03:14, sessions 500, signals 76019,
traded 2437`. That is the current post-T23 book (`145d564e`); the 2,595-trade book is the
**superseded** T0 book (`research/g71_advscanners.md:89`, `g71_ddverify.md:33`).

## 4. What is wrong: "floors 95.3% of the traded book to B"

`research/g71_trend.md:33,69` and the claim. Not reproducible on any slice:

| slice | value |
|---|---|
| rows carrying `[floor B: first with-trend signal of the day]`, traded | **1,370 / 2,437 = 56.2%** |
| same, of all fired | 1,370 / 3,487 = 39.3% |
| `with_trend` TRUE, traded | 2,273 / 2,437 = 93.3% |
| grade `B` share of traded | 2,361 / 2,437 = 96.9% |

Nothing is 95.3%. The load-bearing number is **56.2%** — the share of the traded book that
exists *because* the arrival floor lifted it out of `C` (C is alert-only,
`backtest_week.py:283-289`).

## 5. What the claim omits: the branch, and the consequence

`COUNTER_TREND_CAP` defaults to **0** (`signal_runner.py:183`) and `capped C` appears on
0 of 76,019 rows, so `with_trend`'s only path to a grade is `arrival_first`
(`signal_runner.py:2026`) → the `C → B` floor (`:2051-2061`). `ENABLE_SAC_LADDER` /
`ENABLE_KILL_B_FLOOR` / `ARRIVAL_LADDER` all default off, so the branch is live and reachable.
Because every fired signal is 09:35–10:59, the `0 <= mins <= 90` gate never binds.

Priced (`research/g71_advtrend_recon_audit.py`), under the same RTH-clamped live model:

* **24 traded rows lose the floor** and revert to alert-only `C` (exact — keyed on the
  ground-truth floor tag; 25 with the entry-price variant).
* **≤ 39 alert-only `C` rows gain it** and become trades (upper bound: `_dir_fired`
  (`signal_runner.py:2612`) also counts signals the backtest's own dedupe
  (`backtest_week.py:828`) drops from the book, so a reconstructed "first" is over-permissive —
  200 fired `C` rows reconstruct as `arrival_first` when they cannot have been).

So the live/backtest churn is ~1.0% of the traded book removed and up to ~1.6% added, not
"3.2% flips" of an unnamed quantity. The claim is directionally right and materially
under-specified.

## 6. Suggested correction to `research/g71_trend.md` (not applied)

```diff
--- a/research/g71_trend.md
+++ b/research/g71_trend.md
-| 6 | `signal_runner.py:2020` `_calibration_grade` | ... | intraday | the `C → B` floor at `signal_runner.py:2055-2062` — **selects 95.3% of the book** |
+| 6 | `signal_runner.py:2020` `_calibration_grade` | ... | intraday | the `C → B` floor at `signal_runner.py:2055-2062` — **lifts 1,370 / 2,437 = 56.2% of the traded book out of alert-only `C`** (`COUNTER_TREND_CAP=0`, so this is its only grade path) |
-The rule that floors 95.3% of the traded book to `B` therefore measures "price vs the 09:30
+The rule that floors 56.2% of the traded book to `B` therefore measures "price vs the 09:30
```
