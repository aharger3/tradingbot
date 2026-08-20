# T2 -- chat-corpus recall with UTC timestamps

Snowflake proof: 50 random rows, `(int(msg_id)>>22)+1420070400000` ms decoded as UTC vs stored `ts`, matched to within 2s. All 50 passed -- `ts` is naive UTC.

Trader channels: futures-alerts, jdub-alerts, premarket-charts, scarface-alerts, swing-ideas. UTC->America/New_York, keep ET time in 09:30-11:00 (OMEN scan window). Engine replayed offline against data_archive (pf.fetch_day stubbed to [] on cache miss).

```
snowflake_utc_match: 50/50
instances_total: 10379
instances_trader_channels: 7319
instances_in_et_window: 3753
ticker_days: 998
engine_fired_days: 134
recall_pct: 13.4
direction_agree: 36/48
prior_claimed_recall_pct: 0.0
```
