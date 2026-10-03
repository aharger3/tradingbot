# stock_cards: the forward S2 feed (row W9)

Paper research only. No orders (Alpaca is used for read-only market data). Not investment advice.

Mon-Thu, 09:36-11:00 ET: scan Austin's 28 tickers on Alpaca IEX 1-minute bars, run the S2 engine at each decision bar
(close of the signal bar), and push one ntfy card per eligible candidate with S / Not S / Skip buttons. Taps land in
`eye_card\labels.csv` / `skips.csv` through the existing `tap-answer` service; `export_taps` turns them into the CSVs
`s2_confirm.py` (PR #100) reads.

## Run
    python -m stock_cards.run_day                                  # the scheduled task (OmenStockCards, hidden, Mon-Thu 09:30)
    python -m stock_cards.run_day --replay 2026-10-02 --ignore-weekday   # dry run on a stored session, sends nothing
    python -m stock_cards.compare 2026-10-02                       # IEX candidates vs the Polygon archive for a day
    python -m stock_cards.export_taps [--archive-pool]             # taps + candidate pools for s2_confirm
    python -m pytest stock_cards -q --basetemp <writable dir>      # 41 tests, no network, no vault

## Turn real sends on (after subscribing to the ntfy topic)
Create an empty file `C:\Users\aharg\Desktop\AI-Outputs\stock-cards\SEND_ENABLED`. Without it every run is a dry run
(`cards_dry.jsonl` holds what would have been sent, secrets masked). Delete the file to stop sends.

## Rules (all declared before any forward data; constants in `config.py`, logic in `policy.py`)
- Signal bar 09:35-10:58 ET, card sent within 45 s of the bar closing (else logged `stale`).
- Eligible = engine status `fired` and tag `[clean]`. Cards go to the first eligible candidates of the morning, at least
  5 minutes apart, max 6 a day, never the same symbol and side again within 30 minutes. Mon-Thu only.
- Every candidate (carded or not) is appended to `candidates.jsonl` with its status, tags and the reason.
- The card shows ticker, side, bars through the signal bar, level, entry, stop, 2R. No grade, score, badge or outcome.
- Buttons: `TAP_BASE_URL/tap/<token>` (Cloudflare tunnel) if that vault secret exists, else the private ntfy answer topic
  that `tap-answer` already streams. Neither route is Tailscale.

## Files (DATA_DIR = `C:\Users\aharg\Desktop\AI-Outputs\stock-cards`, logs in `C:\Users\aharg\Desktop\logs\stock-cards`)
`candidates.jsonl`, `cards_sent.jsonl` (live), `cards_dry.jsonl` (dry), `charts\`, `export\`, `replay\<day>\` (dry runs).
