# Discord Delta Scrape — T5

channels_updated: 13
new_messages: 1145
new_attachments: 503
newest_before_utc: 2026-07-04
newest_after_utc: 2026-08-21
oldest_unchanged: true

## What was pulled

13 of 30 channels had new messages since the archive's 2026-07-05 cutoff. The
delta covers ~7 weeks (Jul 5 → Aug 21). No channel was re-scraped from origin;
every channel's `oldest` snowflake is byte-identical to `_state.before.json`.

| Channel | New msgs | New images |
|---|---|---|
| trading-floor | 234 | 96 |
| scarface-alerts | 303 | 78 |
| jdub-alerts | 253 | 190 |
| futures-alerts | 166 | 32 |
| trade-feedback | 63 | 8 |
| pre-market-live | 37 | 0 |
| premarket-charts | 35 | 99 |
| options-trade-reviews | 18 | 0 |
| live-sessions | 13 | 0 |
| youtube | 13 | 0 |
| swing-ideas | 3 | 0 |
| backtesting | 3 | 0 |
| futures-trade-reviews | 4 | 0 |

17 channels had zero new messages (education modules, books, tips, etc.).

## Root cause of the previous failure

The previous attempt used the **wrong Chrome profile** — `circle-profile`
(port 9222) — which is the *Circle* scraper's profile, logged out of Discord.
The Discord scraper's own `scrape-queue.cmd` uses a **separate**
`discord-profile` (port 9223) that holds the live Discord session. That profile
was never checked.

Additionally, the token capture script filtered for `"bearer" in auth.lower()`,
but Discord's web client sends user tokens as bare values (no `Bearer` prefix),
so even with the right profile the capture missed the working token. The fix:
capture any `Authorization` header from a `discord.com/api` request after a
hard reload, strip `Bearer` if present, and save to `.disc_token_tmp`.

`playwright` is not installed on this box; `_run_delta_noplaywright.py` stubs
the import so `discord_scraper.main()` runs with the saved token.
