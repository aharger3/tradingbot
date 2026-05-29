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
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1509036583150420030/...  (he has full URL)
ALPACA_API_KEY=PKC6UTGX5X4MEI7AWG36A66HGG
ALPACA_SECRET_KEY=4E2MhZp7vwBnEdPdnKxoY4gL4UDPp93VzrJiUDm8sZHu
```

## Known open items
- **Data feed is weak.** Alpaca free = 15-min delayed quotes, bad for 0DTE timing. Austin opened a **Tastytrade CASH account** (real-time, free, $0 balance) — PENDING APPROVAL. When approved, wire it into `alpaca_feed.py` to replace Alpaca. This is the next big fix after Windows is running.
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
