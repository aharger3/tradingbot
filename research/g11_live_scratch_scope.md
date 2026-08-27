# G11 — clause 2's scratch in the LIVE path: scope, not implementation

Scoping only, written by reading `paper_trader.py`, `live_scanner.py`, `archive_1m.py`,
`polygon_feed.py`, `dxlink.py`, `tastytrade_feed.py`, `signal_runner.py`, `omen_bot.py`,
`options_sizer.py` and `backtest_week.py` at `_this commit_`. No code changed. Answers the
G11 row in `TASKS.md`.

## 0. The rule, and the prior finding

`Trading-Bot-Rulesets.md`, Austin's Trading Rules, clause 2 (lines 173-179):

> **Entry is the close, except on an extreme close.** Normally enter on the candle close.
> When a fast candle would close at the session high (long) or low (short), enter intrabar
> at the level instead — *"you want it to look like it will close above that."* If the bar
> then closes back beyond the level, scratch out at that close; a scratch is not a loss and
> does not arm the 84% rule.

`research/p8_scratch.py` (commit `7979a61e`, `research/p8_scratch.md`) proved the BACKTEST
cannot hold this rule: instrumented over n=43374 created trades, the entry bar's close sat on
the good side of both the stop and the retested level every single time — zero crossings,
closest approach +0.0001 bar-ranges — because the backtest only takes the intrabar-fill entry
*after* it has already seen that bar's completed close. The branch was deleted; the book came
out byte-identical on all 45,175 rows. P8 flagged, but did not scope, that "nothing in the live
path implements the rule either." This is that scoping.

## 1. Where the decision would go

### `paper_trader.py`

- **`PaperPosition._check_stop`** (paper_trader.py:73-81) and **`_check_target`** (83-91) —
  the two functions that decide a position's fate on every mark. Both take `(high, low)` only;
  neither has ever seen a `close`.
- **`PaperPosition.exit_for`** (105-150) — dispatches to the two above. Its return contract is
  `(exit_premium, outcome)` with `outcome` one of exactly `"stop"`, `"target"`, `"be_scale"`
  today. `"scratch"` is a new arm here.
- **`PaperBook.mark`** (214-288) — the per-scan-cycle entry point; builds the `CLOSE` event
  dict (272-286) that `live_scanner.py` logs and branches on.
- **`PaperPosition` dataclass** (50-71) / **`PaperBook.open_from_plan`** (190-212) — where new
  state would have to live. Today a position carries `stock_stop`, `stock_target`,
  `stock_entry`, and the Rule 6 `be_*` fields — nothing records whether *this* position's entry
  was clause 2's intrabar-at-the-level exception, versus an ordinary close-confirmed entry.
  Two fields are missing: a `filled_intrabar: bool` (only an intrabar fill is scratch-eligible
  at all — an ordinary close-based entry has nothing to scratch) and `level_price` (the line to
  test against). The check must also fire exactly once, on the entry bar's own close, not on
  every later bar — `PaperPosition` has `opened_at` but `mark()` has no "is this still the entry
  bar" comparison today.

### `live_scanner.py`

- **`_emit_signal`** (508-586), specifically the `open_from_plan` call (576) —
  `sig["level_price"]` (set at 6 signal-creation sites in `signal_runner.py`: 1704, 1776, 1852,
  1926, 1993, 2061 — added in the P8/G2 commit expressly for scratch instrumentation) is never
  passed to `build_options_plan` (536) or `open_from_plan` (576). It dies at this boundary.
  Likewise, whether *this* signal took the intrabar-fill branch is decided upstream by
  `fill_price()` (signal_runner.py:1671-1691) and `bar_extreme_veto()` (signal_runner.py:
  619-634), but only the resulting `entry` number survives onto `sig` — the branch decision
  itself is not recorded anywhere. Both would need adding at signal-creation time, then
  threading through `build_options_plan` → `OptionsPlan` (options_sizer.py:45-65, no
  `level_price` or fill-mode field exists there either) → `PaperPosition`.
- **`scan_once`** (268-431), the marking block (356-372): `paper.mark(symbol, high=last.high,
  low=last.low, ts=last.timestamp)` (359) needs `close=last.close` added — see section 3, this
  is required independent of clause 2. More importantly, `if ev["outcome"] == "stop":
  runner.session.record_loss() ... else: runner.session.record_win()` (362-372,
  `record_loss`/`record_win`/`day_ended` defined at omen_bot.py:760, 764, 753) is exactly two
  arms wide. A `"scratch"` outcome landing in the `else` arm would wrongly call `record_win()`
  and reset `session.consecutive_losses` — clause 2 says a scratch "is not a loss," but it is
  not a win either. This isn't hypothetical: the same `else` arm already double-books
  `BE_SCALE` events (paper_trader.py:242-251, a $0 partial-close, not a true close) as a win
  today, since `outcome == "be_scale"` also falls through to `record_win()`. A third arm is
  required: `elif ev["outcome"] == "scratch": pass`. That same placement is what keeps
  `armed_84[symbol] = (...)` (367-369) from firing on a scratch, satisfying clause 2's "does
  not arm the 84% rule" for free, as long as scratch is kept out of the `outcome == "stop"`
  branch.

## 2. What data it needs

The rule needs to know the close came back through the level *before the minute ends* — while
the position is still open and exposed. **A 1-minute bar cannot support that: a bar only
reports its own close once the full minute has elapsed and been polled, so there is no way to
observe the close forming and correct the fill inside the same minute it happens in — the
information the rule needs does not exist yet at any point during that bar.**

What exists in this codebase, feed by feed:

- **Polygon** — cannot help at any granularity, and isn't wired into the live path regardless.
  `polygon_feed.py:46` calls `/v2/aggs/ticker/{symbol}/range/1/minute/{day}/{day}` — 1-minute
  AGGREGATE bars only, nothing finer is ever requested. `polygon_feed.py:34-37`'s `_throttle()`
  names the plan directly: *"Stocks Starter (2026-07-08): unlimited calls, no rate cap."*
  `archive_1m.py:28-29` states the plan's real constraint: *"Polygon returns 403 for the
  CURRENT day on this plan (no real-time entitlement)"* — same-day data is unavailable outright,
  only completed prior sessions. And moot besides: `live_scanner.py`, `paper_trader.py` and
  `tastytrade_feed.py` never import `polygon_feed` — grep confirms zero references outside a
  comment. Polygon feeds only `data_archive/` for backtests; the live scanner runs entirely on
  Tastytrade.
- **Tastytrade DXLink** is the real live feed (`tastytrade_feed.py:378 fetch_recent_bars`,
  polled every `POLL_INTERVAL_SECONDS = 60` seconds — live_scanner.py:84, 705). `dxlink.py`
  implements exactly two event types:
  - **Candle** (`fetch_candles`, dxlink.py:159-241) — what the scanner uses today, always at
    the default `period="1m"` (nothing in this codebase ever calls it with another value). The
    signature does accept a `period` param that could in principle ask for sub-minute bars, but
    the whole path is flagged `*** NEW / UNTESTED-AGAINST-LIVE-API ***` (dxlink.py:142-149) —
    nobody has confirmed this Tastytrade deployment serves anything but 1-minute here. It also
    opens a fresh, short-lived websocket + HISTORY backfill per call (dxlink.py:182), not a
    held-open stream, so today's architecture polls a snapshot once a minute — it does not
    watch continuously, independent of bar size.
  - **Quote** (`fetch_quotes`, dxlink.py:31-113) — real bid/ask, i.e. a genuine intrabar quote
    stream, already implemented and already live-proven: it is how option premiums are priced
    today (`tastytrade_feed.py:324-350 fetch_option_quote`, called at line 340). It is generic
    to any dxfeed streamer symbol, so nothing structurally stops it from being subscribed to
    the underlying stock — it simply isn't: nothing in `live_scanner.py` or `paper_trader.py`
    calls `fetch_quotes` for a stock symbol, only for the option contract.
  - No **Trade**/tick event is parsed anywhere in this codebase.

So: an intrabar quote stream is the realistic answer, and the mechanism (`dxlink.fetch_quotes`)
already exists and is proven in production, just not for the underlying — pointing it at the
stock symbol and holding it open (or polling far faster than 60s) for open positions is a real
feed-architecture change, not a data-availability wall. Sub-minute Candle bars are unverified
and would need proving against the live API first. Polygon is out regardless of granularity —
no current-day access, and not in the live path at all.

## 3. The wick bug

Confirmed, and it is a real, unconditional live divergence from the settled rule — CLAUDE.md:
*"Stops trigger on the candle CLOSE, fill at that close, floored at −1.25R. Wicks stop nothing
out. Austin settled this five times in one batch of marks."* `Trading-Bot-Rulesets.md`'s
Austin's Trading Rules clause 1 (lines 167-171): *"Stop-outs happen on the close, not the wick.
A trade is stopped out only when a candle closes beyond the stop level. A wick through the stop
is not a stop-out."*

- `PaperPosition._check_stop` (paper_trader.py:73-81): `if low <= self.stock_stop: return
  self.stop_premium, "stop"` (76, calls) / `if high >= self.stock_stop: ...` (79, puts) — tests
  the bar's WICK extreme, never `close`.
- Fed exclusively wick data: `live_scanner.py:359`: `paper.mark(symbol, high=last.high,
  low=last.low, ts=last.timestamp)` — `last = candles[-1]` (358) is a `Candle`
  (`omen_bot.py:80-88`) that DOES carry `.close`; it is simply never read here, and
  `PaperBook.mark` (paper_trader.py:214) has no `close` parameter to receive it even if it were.
- `PaperPosition._check_target` (83-91, lines 86/89) has the same high/low shape, but this side
  is **not** part of the divergence — a target is a resting limit order that fills on any
  intrabar touch in the settled rules too (`backtest_week.py:606`: `c.high >= t.target` /
  `c.low <= t.target`, the same engine that gets the stop side right). Only the stop check is
  wrong.
- Same bug, same file, currently dormant: `_check_breakeven` (paper_trader.py:93-103, Rule 6's
  scale-out trigger) has the identical wick pattern (`high >= self.be_scale_level` /
  `low <= self.be_scale_level`) — inert only because `RULE6_ENABLED = False` (paper_trader.py:25).

**This is a real divergence, not a modeling nuance.** For a call, wick-checking means a low
WICK through the stop closes the position immediately even if the candle recovers and closes
back above the stop — exactly the premature stop-out clause 1's evidence list exists to rule
out (`MSTR_2024-09-26_11_14`, `MU_2026-02-09_24_36`, `PLTR_2025-12-10_45_52`, and three more,
Trading-Bot-Rulesets.md:169-171). The backtest engine already gets this right: `backtest_week.py
:120-127, 599-606` implements `STOP_ON_CLOSE` (default on) — `stopped = (c.close <= t.stop) if
STOP_ON_CLOSE else _wick_hit(c, t.stop, True)` — with the identical clause-1 citation in its own
comment (`backtest_week.py:120-122`: *"stop out happens when candle CLOSES below the level"*).
So `paper_trader.py` is not implementing a rule nobody has coded — it is diverging from a rule
that is already correctly coded one file over.

**Size of the fix**, mechanically:

1. Thread a `close` parameter through `PaperBook.mark` (214) → `PaperPosition.exit_for` (105)
   → `_check_stop` (73), and switch the stop side's comparison from `low`/`high` to `close`
   (leave the target side wick-based, per above).
2. One call-site change: `live_scanner.py:359` needs `close=last.close`.
3. `research/exit_lab.py:169-183 _stop_fill` is the reference for the −1.25R floor
   (`MAX_LOSS_R = 1.25`, `research/exit_lab.py:55`) — but it floors a STOCK-side price
   (`entry − MAX_LOSS_R * risk`), and `paper_trader.py` exits in OPTION PREMIUM terms via a
   single precomputed `stop_premium` from `options_sizer.py`, not a price path. Every stop-out
   already books exactly `stop_premium` today regardless of how far the close overshoots — there
   is no existing "worse than the stop" case on the premium side to floor, so switching wick to
   close doesn't, by itself, need new floor logic. Whether the premium model should react to
   overshoot at all is a separate, deeper question than this bug.
4. The self-test at the bottom of `paper_trader.py` (`__main__`, lines 295-342) asserts against
   high/low wick scenarios (e.g. 311, 321, 336) and would need rewriting around close values.

Net: small in code surface — a handful of functions in one file, one call site, one test
rewrite — bounded further by an already-shipped, already-tested reference implementation to
mirror (`backtest_week.py`'s `STOP_ON_CLOSE`). Not small in consequence: it has been silently
mismarking every paper position, every day paper trading has run, independent of clause 2
entirely, always in the direction of cutting trades early that the settled rule would have let
ride.

**This is the more important finding than clause 2 itself.** Clause 2 needs a feed that doesn't
reach the live path yet and, per P8, only ever applies to the minority of entries that took the
intrabar-fill exception in the first place. The wick bug applies to every position, every day,
right now, in code that already has everything it needs to fix it — it is blocked on nothing but
someone doing it.

## 4. Recommendation

- **Clause 2: defer.** Not for lack of code — the mechanism in section 1 is a normal, boundable
  change — but for lack of data. The rule needs to observe price intrabar, inside the same
  minute the entry was taken, and the live feed does not do that today: DXLink's Candle path is
  1-minute, polled once a minute, and unverified against the live API at any other period;
  DXLink's Quote path is real and proven but is wired to option premiums, not the underlying,
  and would need a held-open subscription architecture the scanner doesn't have (today it polls
  a snapshot every 60s). Building the scratch outcome before that feed exists means shipping
  dead code with nothing to feed it — the same shape P8 found in the backtest, for a different
  reason. Prerequisite, and its own scoped piece of work, not part of G11: point
  `dxlink.fetch_quotes` at the underlying symbol and prove it holds up live, or prove the Candle
  path actually serves sub-minute bars.
- **The wick bug: implement.** It has no data dependency — `close` is already on every `Candle`
  the scanner receives, `backtest_week.py` already has a working reference implementation of
  the exact rule, and the fix is bounded to one file plus one call site plus a test rewrite.
  Per this task's own scope, no live-path code changes here — that is Austin's call to
  schedule — but the recommendation is to prioritize it over clause 2: it is blocked on nothing,
  and it has been diverging from a rule Austin settled five times, silently, every day paper
  trading has run.
