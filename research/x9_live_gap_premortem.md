# X9 — what breaks when real money is on it

Pre-mortem, not a feature request. Austin asked: *"will there be time latency issues or all
this is worth it and there wont be bugs in that regard. once i figure out all the kinks,
trades will execute and stop out the way they should?"*

Every number below comes from `research/x9_live_gap_premortem.py` (in this directory, run it),
which reads only two things already in the repo: `research/g3_arm_ow1.json` (the shipped
2-year book, 1,017 traded rows) and `journal/scanner-*.log` (every live session this box has
actually run). **Nothing here recommends going live.** Written 2026-08-28.

---

## The headline

Two execution costs that are certain to exist live and are modelled nowhere in the repo stack
to **−0.8695R**:

| | trades | mean R | win rate |
|---|---:|---:|---:|
| 0. the book as shipped | 1,017 | **+0.9551** | 52.9% |
| 1. + pay the bar's close instead of the backtest's retroactive intrabar fill | 1,017 | **+0.2898** | 38.8% |
| 2. + a $0.05 round-trip option spread | 1,017 | **+0.0856** | 38.4% |
| 2b. + a $0.10 round-trip option spread | 1,017 | **−0.1186** | 37.5% |

The narrow error bar on an A/B of this book is ±0.0095R. Step 1 is **70x** the bar. Step 2 at
five cents is **21x** the bar. Neither is noise, and neither has ever been charged to the book.

The lane brief asked whether the option spread is the single largest unmodelled cost in the
project. It is the **second** largest. The largest is the entry fill, and it is 3.3x bigger.

---

## 1. How a signal becomes an order today

Read `live_scanner.py:main()` top to bottom and this is the whole path:

```
Task Scheduler "OmenSignalBot" 09:25 ET
  → run_daily.ps1  (git pull --rebase, then python live_scanner.py --paper)
    → live_scanner.main()
        TastytradeFeed()  ── DXLink websocket, 1-min Candle events
        RegimeDetector    ── SPY closes from data_archive (yesterday and older)
        while True:
          scan_once() for 29 symbols:
             tasty_feed.fetch_recent_bars(sym, 60)      → candles
                 on exception → _yf_recent_bars(sym)     → yfinance, ~1 min delayed
             paper.mark(sym, high, low, close)           → in-process P&L only
             runner.detect_signals()                      → signal dicts
             _emit_signal() → options_sizer.build_options_plan()
                            → print() + DiscordSignalBot.post_signal()
                            → PaperBook.open_from_plan()  (journal/paper-trades.jsonl)
          sleep(60)
```

**What does not exist yet, plainly:**

- **No order is ever placed.** `live_scanner.py` never imports `broker/`. `grep -rn "from broker"`
  across the repo returns three files: `broker/simulator.py`, `broker/tastytrade.py`, and
  `research/test_broker.py`. The live path's terminal action is a Discord message and a JSONL line.
- **No resting stop.** `broker/base.py` defines `OrderType.STOP` and says in its own docstring
  that a stop the local process merely watches "is explicitly not good enough". Nothing sends one.
  `paper_trader.PaperBook.mark()` closes positions **in memory**, and books the exit at the
  precomputed `stop_premium` — i.e. exactly −1R, always. The −1.25R floor from `CLAUDE.md` is not
  applied on the premium side; `paper_trader.py:81-91` says so in a comment.
- **No state that survives a restart.** `PaperBook.__init__` starts with `open_positions = []`
  and never reads the ledger back. A crash at 09:50 leaves an OPEN line with no CLOSE and, live,
  an unmanaged position with nothing watching it.
- **Phase 1 of T65 is built and green but unwired.** `python research/test_broker.py` → `ALL
  BROKER TESTS PASSED` (5 tests incl. `test_gap_through_stop` and `test_crash_and_recover`).
  `broker/tastytrade.py:69-76` hard-refuses any non-sandbox `base_url`. So the plumbing is real,
  tested, and deliberately fenced off — it just is not connected to `live_scanner.py`.
- **The simulator models no spread and no slippage.** `grep -in "slippage\|spread\|bid\|ask"
  broker/simulator.py` → zero hits. Phase 1 would validate the state machine, not the fill.

---

## 2. The gaps, each with its R cost

### 2.1 The entry fill is retroactive — **−0.6653R/trade** (measured)

This is the big one and it is not a latency problem, it is a look-ahead problem.

`signal_runner.fill_price()` (line 884) decides *whether* to trade on the completed bar's close,
then books the *fill* at the level — clamped into that bar's range — whenever the bar closed
jammed against its own extreme (`bar_extreme_veto`) or the session extreme (`near_session_extreme`,
the ON WATCH gate). The level is a price that traded **earlier inside that same bar**.

Measured against the cached 1-minute archive, all 1,017 traded rows resolved:

- **56 rows (5.5%)** book the bar's actual close. Those are reachable live.
- **961 rows (94.5%)** book a price the bar traded before it closed.
- On **940** of those, paying the close is worse. Mean cost **+0.6063R**, median +0.3676R,
  p95 +2.0867R, worst +6.3084R.
- Re-priced properly — enter at the close, keep the same stop (so the risk unit widens), keep the
  same exit, apply the −1.25R floor — the book goes **+0.9551R → +0.2898R** and the win rate
  **52.9% → 38.8%**.

A bar-close decision process cannot reach that price. The only live mechanism that could is a
genuine intrabar trigger that enters when price touches the level — which fires on *every* touch,
including the majority whose bar does not go on to close at an extreme. **That larger trade set has
never been generated or measured.** So today there are two options and both differ from the book:
pay the close (−0.6653R, measured) or take an unmeasured superset of trades.

> This is the same wound `DIRECTION.md` records for scratches — "the backtest is optimistic *in
> count* on ON WATCH fills". X9 prices it: it is optimistic in **price** by 0.67R a trade.

### 2.2 The option spread — **−0.2042R at $0.05**, and the whole edge dies at $0.162

`options_sizer.build_options_plan()` takes `snap["mid"]` as the entry premium. `paper_trader`
exits at `stop_premium` / `target_premium`, both derived from that same mid. **Entry at mid, exit
at mid, zero spread paid.** `bid_ask_spread` is computed at line 204 and used for exactly one
thing: printing a "wide spread" warning above $0.50. It never touches P&L or sizing.

Live you lift the ask and hit the bid, so one full spread leaves the account per round trip.
In R that is `spread / premium_risk`, where `premium_risk = stock_risk × delta(0.5)` is the whole
1R unit per share. From the book:

| round-trip spread | median R cost | mean R cost | book mean R after |
|---:|---:|---:|---:|
| $0.01 | 0.048 | 0.059 | +0.8960 |
| $0.02 | 0.095 | 0.118 | +0.8368 |
| $0.05 | 0.238 | 0.296 | +0.6593 |
| $0.10 | 0.476 | 0.592 | +0.3635 |
| $0.15 | 0.714 | 0.887 | +0.0676 |
| $0.25 | 1.190 | 1.479 | −0.5240 |
| $0.50 | 2.381 | 2.958 | −2.0032 |

**A $0.162 round-trip spread erases the entire +0.9551R edge.** The median premium risk in this
book is $0.21 per share, so the R unit is thin enough that a few cents matters enormously.

**What is NOT measured, and why:** the actual spread on these names' near-dated contracts. I could
not read one. Polygon returns `403 NOT_AUTHORIZED` on `/v3/snapshot/options/NVDA` (no options
entitlement on this plan — verified today), and Tastytrade session auth is currently failing
`HTTP 400 missing_request_token`, so DXLink option quotes are unavailable too. The only spread
figure anywhere in the repo is the $0.50 the code itself calls "wide". Someone has to log real
NBBO for a week before that row of the table stops being a parameter and starts being a number.

Three further option-side costs that are not modelled *at all* and that I did not attempt to price:

- **Delta is a hardcoded 0.5** (`options_sizer.DEFAULT_DELTA`). Every entry is 0DTE ATM
  (`nearest_expiration()` returns today before 14:30 ET, and the whole trading window is
  09:30–11:00), where delta moves fastest and is least like a constant.
- **Theta.** A 0DTE ATM contract held for the book's median 6 bars, p95 56 bars, decays. Zero
  decay is charged.
- **IV crush on the news-day / open-drive setups.** Not modelled.
- **Size.** At 1R the sizer buys a median of **47 contracts**, p95 **166**, max **200**
  (`1000 // (premium_risk × 100)`). 17.4% of rows want ≥100 contracts of a 0DTE ATM option filled
  instantly at the mid. Market impact on that is a fourth unmodelled cost.

### 2.3 The bar-close clock — the decision lands **~5 minutes late**, not milliseconds

Austin's question was about latency. Measured, from 805 scan cycles across 38 session logs:

- The loop is `scan_once(); sleep(60)` — a **free-running** loop, never aligned to the minute
  boundary. The scan starts at a median **13 seconds** past the minute (min 0s, p95 55s), and the
  offset drifts through the whole minute across a session.
- A scan cycle takes a median **44 seconds**, p75 **312s**, p95 **402s**, max **979s**.
  On sessions with **no feed failure at all** the median cycle is **291 seconds**.
- Why: `dxlink.fetch_candles()` loops until its deadline and **always burns the full 10-second
  timeout** — it has no "I have what I need" exit. 29 symbols × 10s ≈ 290s. That matches the
  measurement exactly.
- Consequence: **53.1% of cycles skip at least one 1-minute bar entirely** (410 of 772 inter-scan
  gaps are ≥2 minutes). A typical session logs 12–14 scans across a 90-minute window. Each symbol
  gets looked at roughly **once every 5–6 minutes**, not once a minute.

And the bar it looks at is the wrong one:

- `fetch_recent_bars()` returns every Candle event DXLink sends, including the **currently forming
  minute**, and `dxlink._parse_candle_feed_data` **never dedupes by timestamp** — a backfill
  snapshot plus a live update for the same minute both land in the list.
- Every detector reads `self.candles[-1]` as "the completed signal bar" and slices positionally
  (`self.candles[-6:-1]`, `[-11:-1]`, `[-16:-6]`). Live, `candles[-1]` is a partial bar whose
  "close" is just the last print, and a duplicate shifts every one of those windows by one.
- This silently converts the house rule **"stops trigger on the candle CLOSE"** into "stops trigger
  on any tick through the level" — exactly the wick-stop behaviour G11 removed from
  `paper_trader.py`. The fix landed in the stop predicate; the bar handed to it is still wrong.

### 2.4 The 60-minute lookback is not the session

`live_scanner.scan_once` calls `fetch_recent_bars(symbol, lookback_minutes=60)`. The backtest
(`backtest_week.simulate_day`) hands the runner the day's bars from 09:30. Three things read
`self.candles[0]` or the full list as if it were the session:

- `signal_runner.py:1964` — `hod = max(c.high for c in self.candles)` / `lod`. This is the
  `session_hi/session_lo` fed straight into `near_session_extreme`, i.e. **the ON WATCH gate**.
  Live it is a rolling 60-minute extreme. Before 10:30 that window is mostly **premarket** (DXLink
  1-min candles include extended hours and nothing filters them); after 10:30 it has dropped the
  open. Either way it is not the number the backtest measured.
- `signal_runner.py:1508` — `with_trend = (candles[-1].close >= candles[0].open)`, the input to
  `_calibration_grade`'s "first with-trend signal of the day" B floor. `DIRECTION.md` §"two ladders"
  records that this floor is what makes **968 of 1,016** traded signals a `B` — it is what selects
  the entire book. Live it compares against the open of a bar 60 minutes ago. The code already
  carries a `ponytail:` comment admitting it.
- `self._dir_fired` is set on the runner and **never reset**. `live_scanner.main()` builds **one**
  `SignalRunner` and reassigns `runner.symbol` around the 29-symbol loop, so `_dir_fired` is global
  across the whole watchlist. `simulate_day` builds a **fresh `BacktestRunner(symbol)` per
  symbol-day**. So the B floor can fire at most twice a day live (once per direction, across all
  29 symbols) versus once per symbol-day in the book.

### 2.5 The governor throws away 59.2% of the book

`live_scanner._tier()` marks a signal `TRADE` only if grade is `A`/`A+`, the clock is ≥09:40, **and
`session.signals_today == 0`** — the first qualifying signal of the day, across all symbols.
Everything else is a `WATCH` ding and is never paper-traded, never sized, never ordered.

- Of the 1,017 traded rows, **1,000 (98.3%) are grade `B`**. 15 are `A`, 2 are `A+`.
- Rows that clear the live TRADE gate: **17 of 1,017 = 1.67%**, on **14 of 500 sessions**.
- The book puts on more than one trade on **295 of 415** trading sessions (up to 8 in a day);
  78 sessions exceed `MAX_TRADES_PER_DAY=3`.
- If the grade gate were fixed and only the one-per-day governor remained: first-of-day only is
  415 trades at +1.0527R; the **602 trades it drops are +0.8879R**, 59.2% of the book.

So the shipped live path, wired to a broker exactly as it is today, would place roughly **14 orders
in two years** while the backtest books 1,017. The measured book and the live path are not the same
strategy.

### 2.6 The data feed: it has been blind for 12 straight sessions

Polygon does not sell the current day on this plan (`archive_1m.py` docstring: "Polygon returns 403
for the CURRENT day"). It is the overnight archiver, not a live feed. Live detection runs on
Tastytrade DXLink, with yfinance as the fallback. Measured from the logs:

- **16 of 33** sessions with scans had at least one feed failure.
- **12 sessions were fully blind** — DXLink *and* the yfinance fallback both failed for every
  symbol: 2026-07-08, 07-09, 08-12, 08-13, and then **every session from 08-19 through 08-28**.
  Today's log is 1,465 `tasty fetch failed` + 1,465 `yfinance fallback failed` + 1,466
  `session auth failed` lines. The scanner ran the whole window and saw zero bars.
- In 33 sessions of paper trading, the scanner has opened **1** paper position, total, ever.
- `sentry_scanner.py` did not fire on any of it. It checks the **age** of
  `journal/scanner_status.json`, and `_write_scanner_status()` is called unconditionally at the end
  of every cycle even when every symbol failed. `last_error` is written into the file and printed
  in the alert body but is **never a trigger condition**. The heartbeat monitors the process, not
  the data.

### 2.7 The stop, live

The rule is "stop triggers on the candle CLOSE, fill at that close, floored at −1.25R." What the
code would actually do:

1. There is **no resting stop at the broker**, so protection is a market order the local process
   decides to send. If the process is dead, wedged in a 10-second websocket read, or 5 minutes into
   its scan cycle, nothing is protecting the position.
2. The trigger is evaluated on a **partial bar** (§2.3), so it fires early and on noise.
3. When it does fire, `paper_trader._check_stop` books `stop_premium` — a price derived from the
   entry mid and a 0.5 delta — i.e. **exactly −1R, every time**. Live it is a market order into
   whatever the option's bid is after the underlying just moved through the level. The −1.25R floor
   exists precisely for that case and is not applied on the premium side at all.
4. On a fast move: the decision lands a median 13 seconds and up to ~6 minutes after the close it
   is supposedly reacting to. 48 of 1,017 traded rows resolve inside a single bar, and **100% of
   those are losses** — those are the rows a late decision loses outright.

### 2.8 Clock, halts, holidays, duplicates

- **DST bug, live path.** `paper_trader._now_et_iso()` (line 39) and `options_sizer`'s
  `nearest_expiration()` / `weekly_expiration()` (lines 125, 137) all compute ET as
  `utcnow() - timedelta(hours=4)`. That is EDT. **From November to March they are one hour off.**
  `polygon_feed`, `market_data`, `tastytrade_feed` and `live_scanner.now_et()` were all fixed to
  `ZoneInfo("America/New_York")`; these three were missed. Consequence today is wrong timestamps in
  the paper ledger; the moment expiry selection matters it is an expiry-picking bug.
- **No market calendar.** `live_scanner` checks `weekday() >= 5` and nothing else. No holidays, no
  half-days. Harmless while the window ends at 11:00, but there is no code that knows a holiday.
- **No halt handling anywhere.** No LULD, no trading-status check. A halted symbol returns its last
  bars; the stop check evaluates a stale close and either fires on nothing or sits through the halt
  and eats the reopening gap. `broker/base.py` mentions symbol halt only as a rejection reason.
- **Duplicate fires** are guarded by `_cooled_down()` (one ding per symbol+direction per 20 min) and
  by `seen_signal_keys` keyed on `candles[-1].timestamp`. Both hold **within a process**. Every
  module-level counter — `_last_alert`, `_watch_dings`, `_qqq_state`, `armed_84`,
  `session.signals_today` — is process memory with no persistence, so any restart inside the window
  resets the daily trade cap and the cooldowns. `sentry_scanner` only alerts, it does not restart,
  so nothing does this automatically today — but a manual restart at 10:00 silently re-arms
  everything.
- **`git pull --rebase --autostash` runs at 09:25, five minutes before the scanner starts**
  (`run_daily.ps1:26`). Today's log shows an 83-commit rebase. The code that trades is whatever
  landed on `main` overnight, applied minutes before the open, with no test gate.

---

## 3. Top five, ranked by expected R cost × probability

| # | gap | R cost | probability | smallest change that de-risks it |
|---|---|---|---|---|
| 1 | **Retroactive intrabar entry fill** (§2.1) | **−0.6653R/trade**, measured | 1.0 — it is structural | Add `FILL_AT_CLOSE=1` to `signal_runner.fill_price` as an env flag (default OFF, changes nothing) and publish the book both ways. That one number is the honest live floor. Then decide whether ON WATCH gets a real intrabar trigger or gets retired. |
| 2 | **Unpriced option spread + 0.5 delta + 0DTE theta** (§2.2) | **−0.2042R at $0.05**; whole edge gone at $0.162 | 1.0 that a spread exists; its size is unmeasured | Log NBBO, don't model it. Add `bid`, `ask`, `mid` and the observed delta to every `log_signal()` row and every `PaperBook` OPEN/CLOSE event. One week of real quotes on the 29 names turns the parameter into a number. Fix the auth first (§5). |
| 3 | **Feed blind for 12 straight sessions, unnoticed** (§2.6) | unbounded — a blind engine with money on it holds positions it cannot see | ~0.36 of sessions historically, currently 1.0 | Make `sentry_scanner` trip on `last_error` and on `signals_fired_today == 0 AND bars_fetched == 0`, not only on file age. Add `bars_fetched` to `_write_scanner_status`. ~20 lines. |
| 4 | **Partial-bar decisions ~5 minutes late** (§2.3) | not separable in R from #1; it is what makes stops fire on ticks instead of closes | 1.0 | Two small changes: drop the forming bar (`candles = [c for c in candles if c.timestamp < current_minute]`) and dedupe by `time` in `_parse_candle_feed_data`. Then give `fetch_candles` an early exit once it has the requested window, so a cycle is seconds not 5 minutes. |
| 5 | **No resting stop, no state across a restart** (§2.7, §1) | one unprotected gap ≫ 1.25R, and it is the loss that ends the account | low per day, certain over a year | Wire `broker/` Phase 1 in behind the existing sandbox guard, and have `PaperBook.__init__` replay `journal/paper-trades.jsonl` so a restart re-adopts open positions instead of orphaning them. Phase 1 is already green. |

Runner-up, deliberately not in the top five because it is a *selection* bug rather than a *fill*
bug: §2.5 — the live TRADE tier would place 14 orders in two years against the book's 1,017.
It matters enormously, but it makes the live path trade *less*, not lose more per trade, and G14
in `TASKS.md` is already pointed at the selector.

---

## 4. What an honest minimum viable live test looks like

Not a recommendation to run it. This is what it would have to be to mean anything.

**Instrument: measure it in R on the OPTION, not on the underlying.** Every number in this project
is R on the underlying. The whole point of a live test is to find out what the option costs, so the
unit of measurement has to be the option's own realized P&L divided by the option's own risk at
entry (`entry_premium − stop_premium`, at the prices actually filled). Reporting a live test in
underlying-R would reproduce the exact blind spot the test exists to remove.

**Size: one contract.** Not "small size" — literally `contracts = 1`, hardcoded, with the sizer
bypassed. At one contract the P&L is noise but the **fill data** is real, and the fill data is the
entire point. A $0.05 spread on one contract costs $5 to learn; on the sizer's median 47 contracts
it costs $235 to learn the same fact.

**Symbols: SPY, QQQ, NVDA — and only those.** They are the three deepest 0DTE chains in the
universe, so they are the *best case* for spread. If the edge does not survive there it survives
nowhere. `research/c6_symbol_attribution.md`-style per-symbol reads under ~20 trades are noise
anyway (`DIRECTION.md`), and COIN/IREN/MARA/ACHR/SPCX spreads would swamp everything. Note that
adding SPY back is a **red** decision per `DIRECTION.md` (`INCLUDE_SPY_IN_BACKTEST`) — for a
spread-measurement test it is data collection, not a strategy change, but it is Austin's call.

**What has to be true for a week before size goes up — all of them, not any of them:**

1. **Zero blind sessions.** Five consecutive sessions where every symbol returned bars on every
   cycle. Today's streak is 12 blind sessions; the counter starts at zero.
2. **Fill fidelity.** Logged fill price within one tick of the price the engine said it would pay,
   on ≥90% of fills. This is the check that catches §2.1 and §2.3 in the wild.
3. **Stop fidelity.** Every stop-out fires on a completed bar's close, and the realized loss lands
   inside [−1.25R, −1.0R] measured **in option R**. Any fill outside that band is the −1.25R floor
   doing its job and needs an autopsy, not a shrug.
4. **A measured spread distribution** — bid, ask and mid captured on every entry and every exit, so
   the §2.2 table can be collapsed to one row.
5. **Scan cadence under 60 seconds** per cycle, so "the engine decides on a bar close" is true.
6. **No reconciliation break.** Broker position == local state at 11:00, every day.
7. **A kill switch Austin can hit from his phone**, tested at least once for real.

Gates 1–3 and 5–6 are plumbing and can be true even if the strategy is worthless. **They are the
only things this test is qualified to answer.** Whether the edge is real is `t65_execution
_architecture.md` §4's question, and its Section 0 answer — recall 17.9% in-sample, 3-of-15 held
out — has not moved.

**What would end the test immediately:** any stop that does not fire on a bar close; any position
open at 11:05; any session where the process restarted inside the window; any fill more than one
tick from the quoted mid at decision time.

---

## Provenance

- Script: `research/x9_live_gap_premortem.py` — run it, it prints every number above.
- Book: `research/g3_arm_ow1.json` (`generated 2026-08-27T17:51:28`, 45,193 signals / 1,017 traded /
  500 sessions / 2024-08-21..2026-08-21), produced by `research/g3_onwatch_2y.py`.
- Bars: `data_archive/<SYM>/<DAY>.csv`, read directly. All 1,017 rows resolved, none skipped.
- Logs: `journal/scanner-*.log`, 38 files, 805 scan cycles.
- Broker Phase 1 status: `python research/test_broker.py` → `ALL BROKER TESTS PASSED`, 2026-08-28.
- Polygon options entitlement: `GET /v3/snapshot/options/NVDA` → `403 NOT_AUTHORIZED`, 2026-08-28.
- Not measured, and named as such: the real bid/ask spread on these contracts; theta and IV cost;
  market impact at 47–200 contracts; the size of the trade set an intrabar ON WATCH trigger would
  actually take.
