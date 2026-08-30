# The futures arm

Script: `research/g83_futures_arm.py` · data: `research/g83_futures_arm.json`.
1R = $1,000. The money bar, ratified 2026-08-30: **$397 a day** ($100,000 / 252 sessions).

```
python research/g83_futures_arm.py             # the numbers below
python research/g83_futures_arm.py --selfcheck  # the checks this file makes
```

Both repo gates re-run green after this work (`research/regression_gate.py`,
`research/test_runner_stop.py`). No engine file touched, no mark file opened, no network
call made — every SPY/QQQ/IWM one-minute bar this uses was already archived on disk.

---

## The answer, in dollars

Same 500 sessions (2024-08-21 to 2026-08-21), same honest fill (market order at the
close of the signal minute — not the shipped book's own recorded entry, which
`OMEN-7.3.md` section 1 already found hands the trade a free head start), one trade a
day.

| instrument | universe | trades | win rate | $/day | months green /25 | worst drawdown | distance to $397/day |
|---|---|---:|---:|---:|---:|---:|---:|
| **Options** (0DTE ATM) | all 29 symbols, fires 499/500 days | 499 | 41.7% | **$242** | 20/25 | $14,997 | **$155 short** (61% of goal) |
| **Shares** | all 29 symbols, fires 499/500 days | 499 | 43.1% | **$187** | 17/25 | $17,925 | **$210 short** (47% of goal) |
| **Futures** (MES/MNQ/M2K) | SPY/QQQ/IWM only, fires 230/500 days | 230 | 40.4% | **$55** | 13/25 | $16,607 | **$342 short** (14% of goal) |

**None of the three reaches six figures a year.** Options gets closest — $242/day is
$61,000/yr, 61% of the $100,044/yr bar — and it is still $155 a day short. At the more
tape-accurate volatility multiplier (`g80_options_honest.md`'s sensitivity, not
re-measured here) options read $346/day, $87,192/yr, still $51 short. **Futures is a
distant third, at 14% of the bar**, and the shortfall is not mainly the instrument — see
the same-trades comparison below — it is that a futures-only account can only see index
setups, and those show up on fewer than half the days.

Shares and options figures are `g80_options_honest.md`'s own published "market at close,
1/day" row (inherited 1.2x volatility) — not recomputed here; this file's job was the
missing third column. **What it costs him in trading days**: options and shares get a
signal on 499 of 500 sessions. Futures gets one on **230 of 500 (46.0%)** — the account
sits out more than half the calendar.

---

## The day count, verified — and it moved

The task brief pointed at `research/g71_propfirm.md`'s claim that only **139 of 500
sessions (27.8%)** produce an index signal, and asked for that number to be checked
because it is the fact that decides this arm. It does not reproduce.

**The 139 figure is stale.** `g71_propfirm_sim.py`'s own docstring says its cache
(`g71_propfirm_daily.json`, and by extension `g71_propfirm_daily_index.json`) holds
**2,437 traded rows** — the pre-G72 book. The current `bt2y_trades.json` holds **4,508**
traded rows, from the same day's fix pass (`DIRECTION.md`, "G72 fix pass," 2026-08-29,
same date the propfirm doc was written). No script that regenerates the daily-index cache
from the current book exists on disk — it was a one-off run whose output was committed
without its generator, exactly the failure mode `CLAUDE.md` warns about ("if you publish
a number, commit the script that made it").

Recomputed here, on the current 4,508-row book: **230 of 500 sessions (46.0%)** produce
at least one SPY/QQQ/IWM traded signal — up from the stale 27.8%, because the whole book
grew 1.85x in the G72 pass and the index names grew with it (54 SPY + 117 QQQ + 59 IWM =
230 rows across 230 distinct days; no day has more than one traded row per symbol, and
no day in this count needed more than one index name to qualify).

A second, narrower question — "of the days where the account's single global first
trade (across all 29 symbols) happened to be an index name" — gives a different, smaller
number: **31 of 500 (6.2%)**. That is not the right question for this table. A
futures-only account does not watch NVDA; it watches the index names only, so its one
trade a day is the first index-eligible signal of *that* day, full stop, regardless of
what fired first on a symbol the account cannot trade. The 230-day figure is the one this
file uses throughout, and both counts are in the JSON (`day_count`) so either can be
re-derived.

---

## Contract multipliers and tick sizes — sourced, not modelled

`t17_futures_feasibility.md` found the archive holds zero futures symbol-days and
refused to fabricate a backtest. That finding is untouched here — **no MES, MNQ, or M2K
bar exists anywhere in this repo and this script never reads or writes one**
(`--selfcheck` greps its own call graph for exactly that). What follows is arithmetic on
data that already exists: OMEN's real SPY/QQQ/IWM signals, already detected and stopped
by the shipped engine, translated into what a micro index-futures contract would have
paid, using the exchange's own published multiplier and tick size.

CME's own contract-spec pages (`cmegroup.com/markets/.../*.contractSpecs.html`) timed
out on a direct fetch from this sandbox. Every number below is corroborated from at
least two independent broker/vendor pages quoting the same published spec, retrieved
2026-08-30, and cross-checked against the parent E-mini's own well-known multiplier
(the "micro" family is defined as 1/10th the parent, which the numbers below satisfy for
MES and M2K exactly, and for MNQ against the well-known NQ = $20/point):

| contract | tracks | multiplier | tick size | tick value | source |
|---|---|---:|---:|---:|---|
| **MES** | S&P 500 | $5/point | 0.25 pt | $1.25 | [ironbeam.com](https://www.ironbeam.com/knowledge-base/micro-e-mini-sp-500-futures-mes-contract-specifications/), [quantvps.com](https://www.quantvps.com/blog/mes-tick-value) |
| **MNQ** | Nasdaq-100 | $2/point | 0.25 pt | $0.50 | [ironbeam.com](https://www.ironbeam.com/knowledge-base/micro-e-mini-nasdaq-100-futures-mnq-contract-specifications/), [quantvps.com](https://www.quantvps.com/blog/mnq-tick-value) |
| **M2K** | Russell 2000 | $5/point | 0.10 pt | $0.50 | [ironbeam.com](https://www.ironbeam.com/knowledge-base/micro-e-mini-russell-2000-futures-m2k-contract-specifications/), [futurespositionsizecalculator.com](https://www.futurespositionsizecalculator.com/contract-specifications/m2k) |

`research/sizing.py` already carried MNQ and MES tick values (added 2026-08-23) and this
file's numbers match them exactly; M2K was missing there and is added here, sourced the
same way. `research/g71_instrument_spread.py` already prices ES/MES friction on the same
"stop distance in index points" idea this file uses — reused, not reinvented.

**The one genuinely approximate step**: an ETF's stop distance, in dollars, has to be
converted to index points before it can be priced in a contract's own units. That
conversion is an ETF:index ratio, and it is sourced, not fitted:

| ETF | index | ratio used | how it was gotten |
|---|---|---:|---|
| SPY | S&P 500 | 10.0 | SPY was structured at 1993 launch to trade near 1/10 of the index. `g71_instrument_spread.py` already uses this exact "ES ≈ 10 × SPY" approximation; kept identical here so the two files cannot silently disagree. |
| QQQ | Nasdaq-100 | 41.09 | Sourced 2026-08-30 from [spxytrader.com](https://spxytrader.com/content/intro/ndx-vs-qqq), citing a May-2026 NDX/QQQ close ratio. QQQ launched at a nominal 1/40 in 1999; cash-drag and its expense ratio have pulled the true ratio to ~41.1 by 2026. |
| IWM | Russell 2000 | 9.91 | Computed here from two live prints, both dated 2026-08-28: RUT closed 2,972.37 ([cnbc.com](https://www.cnbc.com/quotes/.RUT)), IWM's previous close was $299.81 ([finance.yahoo.com](https://finance.yahoo.com/quote/IWM/)); 2972.37 / 299.81 = 9.914. **Flagged UNVERIFIED as a multi-year constant** — this is a single day's ratio, not a fitted one like SPY's or QQQ's, though it lands almost exactly on IWM's commonly-cited "designed as 1/10" figure. |

Using 40 instead of 41.09 for QQQ moves every QQQ stop width 2.7% and does not change
which instrument wins this table. The ratios, the specs, and every trade-level row are
in `g83_futures_arm.json` so a real CME fetch, if one is ever run, can be diffed against
this table directly.

---

## Method

For each of the 230 picked index rows: the shipped engine's real entry-index minute
(`entry_i`), stop and direction come straight from `bt2y_trades.json`. The **market order
at the close of the signal minute** honest fill and the flat-2R / close-triggered-stop /
−1.25R-floor simulation are `research/g80_options_honest.py`'s own `entry_for("B", ...)`
and `simulate(...)` functions, imported here rather than reimplemented, so this file's
R-multiples cannot silently drift from the shares/options numbers it stands next to.

From that honest fill: `abs(entry − stop)` in ETF dollars × the ratio above = the stop
distance in index points, rounded to the nearest tick (minimum one tick — a real futures
stop cannot be finer). `research/sizing.py::dollars_futures` sizes the largest whole
number of contracts whose risk does not exceed the $1,000 budget (contracts are
integers; risk is rounded **down**, never up, and the leftover margin is reported, not
hidden) and applies the trade's real R-multiple to that realised risk, not to the
nominal $1,000. Median position sizes: MES 25 contracts (median stop 34 ticks), MNQ 12
contracts (median stop 159 ticks), M2K 37 contracts (median stop 53 ticks) —
`g83_futures_arm.json::per_contract`.

The shares and options columns in the *headline* table are `g80_options_honest.md`'s
own published full-universe numbers, cited, not recomputed. To isolate whether futures
loses to the day-count restriction or to the instrument itself, the same 230 index-only
trades were also priced as shares and as same-day ATM options (same honest fill, same
Parkinson-sigma/1.2x pricer `g80_options_honest.py` uses):

| instrument, same 230 trades | win rate | $/day | months green /25 | worst drawdown |
|---|---:|---:|---:|---:|
| Futures (MES/MNQ/M2K) | 40.4% | $54.64 | 13/25 | $16,607 |
| Shares | 40.4% | $58.17 | 13/25 | $17,393 |
| Options (0DTE ATM) | 40.4% | $76.12 | 14/25 | $18,286 |

**On identical trades the three instruments are close** — futures trails shares by about
$4 a day and options by about $22, both inside this project's ±1.5799R error bar. The
real cost of the futures route is not the contract. **It is that a futures account only
gets to play on 230 of 500 days**, and $54.64 × 500 = $27,318 total against shares'
$187 × 499 ≈ $93,313 and options' $242 × 499 ≈ $120,758 over the same two years.

---

## Which instrument gets closest, in one sentence

**Options gets closest to six figures a year — $242 to $346 a day, 61% to 87% of the
$397 bar, still short by $51 to $155 — and futures is a distant third at $55 a day (14%
of the bar), costing him not the instrument but 54% of his trading days: a futures-only
account can only see SPY/QQQ/IWM setups, and those show up on fewer than half the
sessions.**

---

## What I did not do

- **No futures bar was fetched, cached, or fabricated.** Every number above is ETF
  price action translated through a published contract spec, never a modelled futures
  candle.
- **No commission or spread is charged on the futures leg.**
  `g71_instrument_spread.py` already priced MES round-turn friction at $2.64/contract
  (dated, sourced there); at a median 12–37 contracts that is $32–$98 a trade, small next
  to the $55/day headline but not zero, and not applied here.
- **No CME contract-spec page was actually fetched** — both `WebFetch` calls to
  `cmegroup.com` timed out in this sandbox. The specs are corroborated from vendor pages
  quoting the same numbers, not from the exchange's own page directly. If that page is
  ever reachable, diff it against `FUT_SPEC` in `g83_futures_arm.py`.
- **The IWM:RUT ratio (9.91) is a single day's snapshot**, not a ratio checked across
  the 500-session window the way SPY's structural 1/10 is. It is flagged UNVERIFIED as a
  multi-year constant in the script's own comments.
- **No prop-firm evaluation rules are applied here** — no daily-loss limit, no trailing
  drawdown, no consistency rule. `research/g71_propfirm.md` already models those against
  a stale day count; a re-run of that sim against the corrected 230-day series is a
  natural next step and is not done in this file.
- **Overnight/margin mechanics are not modelled** — irrelevant at this window (09:30–
  11:00 ET, closed same session) but noted for completeness.
