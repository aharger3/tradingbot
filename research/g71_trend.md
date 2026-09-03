# G71 / trend — does OMEN know how to follow the trend, and should trend be a filter?

Austin, 7.1 blocker 6: *"we dont know if it knows how to follow the trend. this can be
archived but remembered it should be a filter to see if it shapes results."*

**Answer: it has three different ideas of trend, on three different timeframes, and one of
them is already the single biggest veto in the engine — it kills 46.9% of every signal
before the candle is even looked at. Adding trend as a *stronger* filter shapes nothing:
all 18 filter arms measured on the two-year book land inside their own error bars. And on
his held-out S days the setup is counter-trend more often than not, so a with-trend filter
is a recall tax with no money to show for it.**

Scripts: `research/g71_trend.py`, `research/g71_trend_scards.py`,
`research/g71_trend_livegap.py`, `research/g71_trend_cache.py`.
Outputs: `research/g71_trend.json`, `research/g71_trend_scards.json`.
Book: `research/bt2y_trades.json` (2024-08-21 → 2026-08-21, 500 sessions, 76,019 signals,
2,437 traded, mean **+0.5495R**, win 49.5%, months 25/25, weeks 91/105).

---

## 1. What "trend" means in this codebase today

Six live definitions, five names, three timeframes. Ranked by how much they actually do.

| # | where | what it computes | timeframe | shipped effect |
|---|---|---|---|---|
| 1 | `omen_bot.py:240-243` (`grade_trade`) | `opposed = htf_bias in (bullish,bearish) and (htf_bias=="bullish") != is_long` → `return TradeGrade.D` | whatever `htf_bias` was fed | **HARD VETO, ON.** `HTF_BIAS_VETO` defaults `"1"` (`omen_bot.py:29`) |
| 2 | `omen_bot.py:245-246` | `htf_bias == "neutral"` caps `A+`/`A` → `B` | same | ON |
| 3 | `backtest_week.py:713-724` `htf_bias_for` | last **hourly** close before the open vs SMA20 of hourly closes, ±0.1% band ⇒ ~**3 sessions** of lookback | 1h | feeds #1 in `backtest_2y.py:129` — **the money book** |
| 4 | `research/t4_engine_recall.py:108-130` `htf_bias` | prior **daily** RTH close vs SMA20 of **20 daily** closes, ±0.1% ⇒ **20 sessions** | 1D | feeds #1 in `run_day:196` — **the recall gate**, the regression gate, T1, `t0_heldout_recall` |
| 5 | `tastytrade_feed.py:525-551` `fetch_htf_bias` | last 1h close vs SMA20 of 1h closes over a 7-day dxlink pull, **including the in-progress hour** | 1h | feeds #1 **live** (`live_scanner.py:212`) |
| 5b | `futures_feed.py:67-75` `fetch_htf_bias` | 1h close vs SMA20, **no dead band** — binary bullish/bearish, never neutral | 1h | futures path only |
| 6 | `signal_runner.py:2020` `_calibration_grade` | `with_trend = (candles[-1].close >= candles[0].open) == (dir=="call")` — the **day trend so far** | intraday | the `C → B` floor at `signal_runner.py:2055-2062` — **selects 95.3% of the book** |
| 7 | `signal_runner.py:2040`, `:183` | `sig["counter_day_trend"]`; `COUNTER_TREND_CAP` | intraday | **OFF** by R21 — reported observation only |
| 8 | `signal_runner.py:1601-1606,1694-1696`, `:497` | `_htf_opposes` / `HTF_OPPOSITION_VETO="hard"` — clause 4 of Austin's tier | same as #1 | measured-only ladder, never gates a trade |
| 9 | `signal_runner.py:1776`, `:216`, `:3258-3265` | `daily_trend_bias` + `HTF_BIAS_GATE`, "only trade the daily trend", caps counter-trend to C | 1D | **OFF by default** |
| 10 | `signal_runner.py:2220-2244` `_qqq_aligned` | QQQ/SPY structure alignment | intraday | tag only (`[qqqA]`/`[qqqX]`) |

**So yes — it knows what trend is, and it already follows it harder than anything else it
does.** 35,628 of 76,019 signals (**46.9%**) are HTF-opposed, and **35,075 of them (98.4%)
are graded `X`**. The 553 opposed signals that carry any other grade are all `B`, and every
one of them got there through T10's `[x-lift:clean]` un-veto — **not one opposed signal has
ever been graded above `X` by the grader itself.**

### 1a. The definition drift is a bug, not a detail (BLOCKER-adjacent)

`#3` and `#4` are both called `htf_bias`, both feed the same hard veto at
`omen_bot.py:240`, and they are **different indicators**: a ~3-session hourly SMA versus a
20-session daily SMA.

| agreement between `htf_bias_for` (book) and `t4_engine_recall.htf_bias` (recall gate) | |
|---|---|
| all 76,019 signals (aligned/opposed rows) | **67.5%** (22,880 flips) |
| the 2,437 traded rows | **68.0%** (713 flips) |
| **Austin's 34 held-out S days** | **18/34 = 52.9%** — 13 of the 34 are outright **inverted** (`bullish\|bearish` 7, `bearish\|bullish` 6) |

The recall gate and the money book are grading **different engines**. Any track that reads
one number against the other is comparing across a coin flip.

### 1b. `with_trend` means something different live than in every backtest (HIGH)

`signal_runner.py:2020` reads `self.candles[0].open`. The caller decides what that is:

* backtest / recall harness — `runner.candles = candles[:i+1]` from the RTH start
  (`t4_engine_recall.py:196`, `backtest_week`), so `candles[0].open` **is the 09:30 open**.
* live — `candles = tasty_feed.fetch_recent_bars(symbol, lookback_minutes=60)` then
  `runner.candles = candles` (`live_scanner.py:378,422`), a **rolling 60-minute window**.

The rule that floors 95.3% of the traded book to `B` therefore measures "price vs the 09:30
open" offline and "price vs the open 60 minutes ago" live. Priced in
`research/g71_trend_livegap.py`, using the most generous reading (RTH-clamped; if the feed
returns premarket bars it is worse):

* **79 of 2,437 traded rows (3.2%) flip** `with_trend`.
* Of the **328 entries after 10:30**, where a 60-minute window can no longer reach 09:30,
  **24.1% flip**.

The code comment at `signal_runner.py:2018-2019` admits the hazard ("live lookback may start
after 9:30; good enough inside the 90-min window we trade") — it is good enough until 10:30
and then it is not.

---

## 2. Trend as a filter on the two-year book

Six definitions × three arms. The book is un-halted, filtered, and R31
(`loss_halt.apply_to_book`) is re-run on the survivors, because dropping a trade changes
which days halt. `move` is against the base **+0.5495R**; `*` would mark a move outside its
own 95% bar.

| def | arm | n | mean R | move | bar | win% | months | weeks | S recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| base | — | 2437 | +0.5495 | — | — | 49.5 | 25/25 | 91/105 | 1/34 |
| htf_h1sma20 | with | 1889 | +0.5207 | −0.0288 | 0.131 | 45.0 | 24/25 | 81/104 | 1/34 |
| htf_h1sma20 | against | 525 | +0.4514 | −0.0980 | 0.138 | **63.9** | 21/25 | 67/99 | 0/34 |
| htf_h1sma20 | with+flat | 2053 | +0.5337 | −0.0157 | 0.129 | 45.2 | 25/25 | 88/105 | 1/34 |
| dayopen | with | 2150 | +0.5229 | −0.0266 | 0.116 | 51.9 | 25/25 | 89/105 | 0/34 |
| dayopen | against | 256 | +0.4093 | −0.1402 | 0.427 | 19.0 | 13/25 | 33/91 | 1/34 |
| dayopen | with+flat | 2320 | +0.5296 | −0.0199 | 0.115 | 51.2 | 25/25 | 90/105 | 0/34 |
| pd_dir | with | 1615 | +0.5453 | −0.0042 | 0.140 | 46.0 | 23/25 | 75/105 | 0/34 |
| pd_dir | against | 973 | +0.5095 | −0.0399 | 0.144 | 53.3 | 23/25 | 75/105 | 1/34 |
| pd_dir | with+flat | 1708 | +0.5319 | −0.0176 | 0.137 | 45.8 | 22/25 | 76/105 | 0/34 |
| dsma20 | with | 1548 | +0.5432 | −0.0063 | 0.135 | 48.1 | 25/25 | 84/105 | 1/34 |
| dsma20 | against | 1141 | +0.5137 | −0.0358 | 0.148 | 49.9 | 22/25 | 74/105 | 0/34 |
| dsma20 | with+flat | 1580 | +0.5407 | −0.0088 | 0.134 | 48.2 | 25/25 | 84/105 | 1/34 |
| or15 | with | 1515 | +0.5130 | −0.0365 | 0.132 | 49.1 | 25/25 | 85/105 | 0/34 |
| or15 | against | 666 | +0.4720 | −0.0775 | 0.207 | 40.5 | 20/25 | 64/105 | 1/34 |
| or15 | with+flat | 2029 | +0.5472 | −0.0023 | 0.121 | 51.3 | 25/25 | 91/105 | 0/34 |
| ema20_5m | with | 1839 | +0.4835 | −0.0660 | 0.121 | 50.9 | 25/25 | 81/105 | 1/34 |
| ema20_5m | against | 585 | **+0.7221** | +0.1726 | 0.240 | 43.3 | 21/25 | 67/105 | 0/34 |
| ema20_5m | with+flat | 2028 | +0.4786 | −0.0709 | 0.119 | 50.0 | 25/25 | 83/105 | 1/34 |

**Every one of the 18 arms is a NULL** — the standing method finding holds again. Two
readings that are not nulls but are worth naming, because they both point *away* from a
with-trend filter:

* **The best mean R in the whole table is the COUNTER-trend arm** — `ema20_5m against`,
  +0.7221R on 585 trades (+0.1726 against a ±0.240 bar). Every single `with` arm is
  *below* the base.
* **The only arm that clears the 55% win-rate gate is also counter-trend** —
  `htf_h1sma20 against`, **63.9%** on 525 trades. Its mean R is 0.4514, so it clears one
  gate and not the other; and it is 525 trades that the shipped veto only lets through via
  `[x-lift:clean]` in the first place.

Definitions do not measure the same thing, either — pairwise agreement on the traded book
(aligned/opposed rows only): `dayopen`↔`or15` 84.7%, `dayopen`↔`ema20_5m` 80.4%,
`htf_h1sma20`↔`pd_dir` 77.3%, `htf_h1sma20`↔`dsma20` 68.0%, `dsma20`↔`or15` **54.3%**.
"With the trend" is not one predicate; picking the definition picks the answer.

*Caveat on the recall column:* book-level recall is 1/34 on every arm because the traded
book covers almost none of those symbol-days (its universe is 28 symbols; MSTR, ARM, SMCI
are not in it, and the engine-level rig is a different router — see
`research/t23_stack.py::book_funnel`). Recall is scored properly in §3.

---

## 3. Cross with his marks: are his S setups with-trend?

`research/g71_trend_scards.py` replays all 34 S cards of
`research/marks/probe_s_sweep_2026-08-28.jsonl` through `t4_engine_recall.run_day` — the
harness the recall gate itself uses — and takes the direction of the signal nearest the
minute he wrote on the card. All 34 cards carry a minute, so every one is pinned to a bar.

| definition | aligned | opposed | flat / na |
|---|---:|---:|---:|
| **hourly HTF (the book's `htf_bias_for`)** | 13 | **20** | 1 |
| daily HTF (the recall gate's `htf_bias`) | 18 | 14 | 2 |
| prior-day direction | 17 | 15 | 2 |
| daily SMA20 | 18 | 14 | 2 |
| opening range 15m | 17 | 6 | 11 (pre-09:45) |
| 20-EMA on 5m | 19 | 11 | 4 |
| day-open (`_calibration_grade`'s own) | 25 | 4 | 5 |

**Under the engine's own money-book definition, 20 of his 34 S setups (58.8%) are
counter-trend.** No definition gets past 25/34 aligned, and the one that does — `dayopen` —
is the one the engine already uses as a *floor* rather than a veto, exactly as R18 said it
should ("don't let it cap you of S opportunities").

**He grades counter-trend setups S. A with-trend filter on the HTF bias would refuse 20 of
his 34 S days by construction.** That is the check the ticket asked for, and it fails.

### 3a. What the shipped veto actually costs, on the governing metric

A/B on the held-out gate itself (`research/t0_heldout_recall.py`, 100 blind cards):

| | S recall | precision | fires on his 66 refusals |
|---|---|---|---|
| `HTF_BIAS_VETO=1` (SHIPPED) | **23/34 = 67.6%** | 39.7% | 35/66 |
| `HTF_BIAS_VETO=0` | **24/34 = 70.6%** | 37.5% | 40/66 |

The trend veto costs **exactly one held-out S day** (`PLTR_2025-12-11`) and buys **five
fewer false fires**. On the 34 nearest-minute signals, lifting it changes the grade on
**2 of 34** (`ARM_2024-10-28` X→B, `PLTR_2025-12-11` X→A); the other 32 stay `X` because
`_grade_pa` vetoes them on candle shape. **Trend is not what is eating his S days** —
DIRECTION.md's "the miss is grading, end to end" survives this track intact.

(Note for the wave: HEAD's held-out recall reads **23/34 = 67.6%**, not the 52.9% still
printed in `DIRECTION.md` — that figure predates the T10/T23 stack.)

---

## 4. Recommendation

**ARCHIVE trend as a filter. Do not wire a with-trend gate.** The number behind it: 18 of
18 filter arms are inside their own error bars, the best arm in the table is
*counter*-trend (+0.7221R), and 20 of his 34 S days are counter-trend on the engine's own
definition — a with-trend gate is a recall tax with no measured money on the other side.

**Two things this track found that are not "trend as a filter" and should not be archived
with it:**

1. **Pick one `htf_bias`.** Two functions with the same name feed the same hard veto and
   agree on 67.5% of signals and 52.9% of his S days. Until they are one function, the
   recall gate and the money book describe different engines. This is a diagnosis pass so
   nothing is applied; the smallest honest fix is to make the recall harness call the
   book's definition, which is the one the live path (`tastytrade_feed.fetch_htf_bias`,
   1h/SMA20) actually matches:

   ```diff
   --- a/research/t4_engine_recall.py
   +++ b/research/t4_engine_recall.py
   @@
   -def htf_bias(symbol: str, day: str):
   -    """Close-vs-SMA20 over prior archived days' RTH closes (mirrors
   -    signal_runner.daily_trend_bias / backtest_week.htf_bias_for)."""
   -    files = sorted(glob.glob(os.path.join(levels.ARCHIVE, symbol, "*.csv")))
   -    names = [os.path.basename(f)[:-4] for f in files]
   -    if day not in names:
   -        return None
   -    i = names.index(day)
   -    closes = []
   -    for d in names[max(0, i - 40):i]:
   -        b = levels.load_rth_bars(symbol, d)
   -        if b:
   -            closes.append(b[-1]["c"])
   -    if len(closes) < 20:
   -        return None
   -    sma = sum(closes[-20:]) / 20
   -    last = closes[-1]
   -    if last > sma * 1.001:
   -        return "bullish"
   -    if last < sma * 0.999:
   -        return "bearish"
   -    return "neutral"
   +def htf_bias(symbol: str, day: str):
   +    """The BOOK's definition, not a second one wearing the same name.
   +
   +    G71/trend: this function used to read SMA20 of 20 DAILY closes while
   +    backtest_2y fed omen_bot.grade_trade's hard veto SMA20 of ~3 sessions of
   +    HOURLY closes. Both are called `htf_bias`; they agreed on 67.5% of the
   +    76,019-signal book and on 18 of Austin's 34 held-out S days, 13 of which
   +    were outright inverted. The recall gate and the money book were grading
   +    different engines. `backtest_week.htf_bias_for` is the one the live path
   +    (tastytrade_feed.fetch_htf_bias, 1h close vs SMA20) matches, so it wins.
   +    """
   +    import polygon_feed as pf
   +    from backtest_week import htf_bias_for
   +    from backtest_12mo import hourly_from_1m
   +    files = sorted(glob.glob(os.path.join(levels.ARCHIVE, symbol, "*.csv")))
   +    names = [os.path.basename(f)[:-4] for f in files]
   +    if day not in names:
   +        return None
   +    hourly = []
   +    for d in names[max(0, names.index(day) - 8):names.index(day)]:
   +        try:
   +            bars = pf.rth(pf.fetch_day(symbol, d))
   +        except Exception:
   +            continue
   +        if bars:
   +            hourly.extend(hourly_from_1m(d, bars))
   +    return htf_bias_for(hourly, day)
   ```

   **This moves a published number and must be re-measured before it lands** — it is the
   input to the veto that gates every recall figure in `DIRECTION.md`.

2. **`with_trend` is computed off a rolling 60-minute window live and off the 09:30 open in
   every backtest** (`signal_runner.py:2020` vs `live_scanner.py:378,422`). 3.2% of the
   traded book and 24.1% of post-10:30 entries flip. The fix is to give the runner the
   session open explicitly rather than inferring it from `candles[0]`; it belongs to
   whichever track owns the live/backtest parity, not to this one.

**Keep the reported observation.** `sig["counter_day_trend"]` (`signal_runner.py:2040`) and
the book's `bias`/`aligned` columns cost nothing and are what made this measurement
possible in an afternoon. R21 already settled that they observe and never cap — leave them
exactly there.
