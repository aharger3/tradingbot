# Vanquish Signal Bot

Autonomous scanner for TSLA + NVDA. Detects break-and-retest, one-candle, and 84% setups (both call and put). Posts full options trade card to Discord with strike, expiration, entry/stop/target premiums, and contract count sized for $1K max loss / $2K target (2:1 RR).

## Quick Start

```bash
cd "Projects/TradingBot"
python3 live_scanner.py
```

Loops 9:30-11:00 ET, polls every 60s, posts Discord on any signal. Ctrl+C to stop.

## Files

| File | Role |
|---|---|
| `live_scanner.py` | Main loop — fetches bars, runs detection, fires Discord |
| `signal_runner.py` | Detection engine (3 setups, call + put) + manual-file CLI |
| `alpaca_feed.py` | Alpaca data client — 1-min bars + options snapshots |
| `options_sizer.py` | Builds options trade card from stock entry/stop |
| `position_sizer.py` | Stock-side sizing (legacy, used by manual CLI) |
| `discord_bot.py` | Webhook poster, embed formatter |
| `vanquish_bot.py` | Candle dataclass, price-action helpers, setup detectors |
| `rules.md` | Strategy spec (canonical) |

## Setup

`.env` (gitignored) needs:
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
ALPACA_API_KEY=PK...
ALPACA_SECRET_KEY=...
```

## CLI Flags

```
python3 live_scanner.py --symbols TSLA NVDA AAPL  # custom watchlist
python3 live_scanner.py --window 09:30-11:00       # custom hours (ET)
python3 live_scanner.py --once                     # single scan, exit
python3 live_scanner.py --no-discord               # console only
```

## Discord Output

Each signal posts an embed with:
- Symbol + strike + expiration (e.g. `TSLA 0DTE $435 CALL ↑`)
- Entry / Stop / Target premiums
- Contract count (sized to $1K max loss)
- Stock reference levels
- Quote source (`alpaca_mid_15min_delayed` or `estimated_delta` fallback)
- Setup name + reason text

## Validation

Rules validated against TradeZella backtest of 320 trades:
- Win rate: **53.75%**
- Profit factor: **2.52**
- Avg win / loss: $2,188 / $1,010 (matches 2:1 target)
- Max drawdown: $10,254 (-7.71%)
- Largest streak loss: 11 (mitigation: halt after 4 losing days)

## Known Limitations

- Options quotes are **15-min delayed** on Alpaca free tier — real Vanquish premium may differ slightly. Verify before execution.
- Strike rounding picks nearest available contract from Alpaca chain; may be ±$2.50 from true ATM on TSLA at high prices.
- No automatic kill-switch on 2-loss day rule yet — manual stop.
- 0DTE only when scan runs before 14:30 ET; after that, picks next trading day.
- Put-side detection mirrors call logic; tested at logic level, not validated against historical puts.

## Future Work (Backlog)

- Cron / launchd auto-start at 9:25 ET
- 2-loss-day automatic halt
- Per-account staggering for 10 Vanquish accounts (currently same signal fires for all)
- Hermes integration as Discord reader (paper-trade logger, mobile push)
- Trade journal back into Obsidian
