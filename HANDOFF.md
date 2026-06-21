# Session 2 (2026-06-10) — DXLink live quotes + put-side fix + Scarface

## TL;DR
Real-time option premiums now work. Put-side bug fixed. Scarface methodology documented.

### Task 1 — DXLink real-time quotes: DONE ✅
- **Root cause of the 403:** code hit the legacy `GET /quote-streamer-tokens`
  (old CometD streamer) which returns `403 "Token has insufficient scopes"` for
  OAuth bearer tokens. Verified live against both endpoints.
- **Fix:** use `GET /api-quote-tokens` (the OAuth-compatible DXLink endpoint) →
  returns `{token, dxlink-url, expires-at}` (valid ~24h). Confirmed 200 live.
- New `dxlink.py`: minimal sync DXLink websocket client (SETUP→AUTH→CHANNEL→
  FEED_SUBSCRIPTION→FEED_DATA, COMPACT Quote parsing). Needs `websocket-client`
  (added to requirements.txt).
- `tastytrade_feed.fetch_option_quote(symbol, expiration, strike, type)` resolves
  the dxfeed streamer symbol from the nested chain and returns live bid/ask/mid.
- `options_sizer.build_options_plan` now uses Tastytrade real-time premium first
  (`quote_source="tastytrade_dxlink_realtime"`), Alpaca delayed second, estimate last.
- **Verified live:** TSLA 2026-06-12 440C → bid 0.14 / ask 0.16 / mid 0.15.

### Task 3 — Put-side detection: FIXED ✅
- Reviewed all 3 bearish setups against the sizer's `stop > entry` invariant.
- **Bug:** 84% short could fire with `stop ≤ entry` when a bearish candle wicked the
  recent high but *closed above* it → sizer silently rejected the signal. Same latent
  bug mirrored on call-side 84% (close below recent low).
- **Fix (`signal_runner.py`):** require close back through the level on both —
  `close > recent_low` (long), `close < recent_high` (short). Also = a *true*
  rejection. B&R-short and One-Candle-short were already valid (stop = candle high).
- Verified with synthetic candles: invalid case now yields 0 signals; valid
  rejections fire with stop > entry.

### Task 2 — Scarface Trades: DOCUMENTED ✅ (research, not code)
- New `strategy-scarface-trades.md` + summary block in `rules.md`.
- Channel: YouTube @ScarfaceTrades; community = "The Accelerator" (private Discord).
- Confirmed-aligned: 5-min ORB, 1-min entries, 9:30–11:00 window, 2R, wick/absorption
  confirmation.
- **Gaps to implement next (priority):** (1) displacement gate on the break,
  (2) Fair Value Gap retest zones, (3) One-Candle anchored to *last* opposite-close
  before breakout, (4) premarket/prior-day levels, (5) session stop after 1 win,
  (6) first-OTM contract option. All left as documented next steps (not coded) to
  avoid destabilizing the validated detectors.

### Also fixed
- `live_scanner.py` pre-existing `NameError: Optional` (missing import) — scanner
  couldn't start. Now runs. Production loop also now passes `tasty_feed` (was only
  wired in `--once`).
- Verified: `python live_scanner.py --once --no-discord` runs clean (0 signals
  after-hours, expected — Alpaca returns no fresh bars).

---

# Session Handoff — read this first (Windows Claude Code)

Context from the Mac session that doesn't auto-sync (Claude Code conversations + ~/.claude memory are per-machine). This file IS in the repo, so it reaches Windows.

## Where we are

Building **Vanquish signal bot** for Austin (prop-firm day trader, trades 9:30–11:00 AM ET only).
Repo: https://github.com/aharger3/tradingbot

### The three-part architecture (decided 2026-05-28)
- **Windows PC = RUNNER.** The only machine that executes Python. Runs `live_scanner.py` daily at 9:25 ET via Task Scheduler. ← **THIS is what we're setting up now.**
- **Hermes = EDITOR/brain.** Cloud agent, NO Python runtime — it literally cannot launch the bot (it's telling the truth, not lying). It edits rules/detection code, journals trades, talks strategy. Connects via GitHub (needs a GitHub PAT for aharger3/tradingbot, read+write).
- **GitHub = shared memory.** Hermes commits rule changes → Windows `git pull` before each run picks them up.

## Immediate next step on Windows

Walk Austin through `WINDOWS_SETUP.md` (in this repo). Specifically the part he stopped at: **Task Scheduler** (step 8) — auto-run the bot at 9:25 ET. Earlier steps (install Python+git, clone, create .env, pip install) may or may not be done — verify with him.

Only external dependency: `requests`. Everything else is Python stdlib.

### .env values he needs (gitignored, never commit)
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```
Tastytrade creds (CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, ACCOUNT_NUMBER) go in
`.env.tastytrade` (also gitignored, never commit) — see `tastytrade_feed.py`.

## Known open items
- **Data feed: Tastytrade is now primary (2026-06-13).** Alpaca integration
  fully removed (`alpaca_feed.py` deprecated, all imports removed). Candle
  bars now come from `tastytrade_feed.fetch_recent_bars()` via DXLink Candle
  events — this is NEW and UNTESTED against the live API (no sandbox network
  access to api.tastyworks.com). Verify it returns real bars before relying
  on it for signals.
- **Detection not yet trusted.** Austin has critiques he hasn't fully given yet — said "I don't know if the bot is thinking right" and "when would I actually have gotten the 10:51 signal live?" Needs a real critique/validation session before trusting signals. Put-side logic mirrors call-side but is unvalidated.
- **Journal**: `journal/trade-journal.md` in this repo. Symlinked into vault `Areas/Trading Journal/` on Mac (shows in Finder, NOT Obsidian app — Obsidian skips symlinks).

## Tools
- `python live_scanner.py` — live loop 9:30–11 ET
- `python live_scanner.py --once` — single scan now
- `python backtest_window.py YYYY-MM-DD 09:30 11:00` — replay a past window (May 27 → 2 META calls; May 28 → 0)

## Strategy quick ref
11 symbols: TSLA NVDA AAPL AMD META GOOG AMZN MSFT PLTR SPY QQQ.
3 setups (call+put): break-and-retest, one-candle rule, 84% rule.
Risk: $1K max loss/trade, 2:1 RR, halt after 2 loss days (not yet automated). Nearest expiration (0DTE before 14:30 ET).
