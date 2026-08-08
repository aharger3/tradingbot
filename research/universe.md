# Tradable Universe — Liquidity Ranking (T4, omen-3.7)

Austin trades names with ~200,000+ daily options contracts and wants a top-10 focus list
out of the 30-symbol `SYMBOLS` list in `archive_1m.py`. This file ranks them. **It changes no
code** — `SYMBOLS` stays as-is until Austin picks from this ranked list.

## Source used and why

**Source used:** `dollar_volume_proxy` (median daily dollar volume of the underlying's 1-min
bars), **not** Polygon options contract volume.

The Polygon options-data endpoints were tried first. The canonical options-volume endpoint —
the options snapshot chain — refused authorization:

- `GET https://api.polygon.io/v2/snapshot/options/TSLA` → **404 page not found**
  (the v2 single-option snapshot path format returned a bare 404)
- `GET https://api.polygon.io/v3/snapshot/options/TSLA` → **HTTP 403**, body
  `{"status":"NOT_AUTHORIZED","message":"You are not entitled to this data. Please upgrade your plan..."}`

The plan also will not yield volume any other way:

- `GET https://api.polygon.io/v3/reference/options/contracts` (with `underlying_asset=TSLA`)
  → HTTP 200, but it returns **contract metadata only** (cfi, contract_type, expiration_date,
  strike_price, ticker, underlying_ticker, …) and carries **no volume field**, so it cannot
  rank liquidity by itself.
- `GET https://api.polygon.io/v2/aggs/ticker/<optionContract>/range/1/day/...` → HTTP 200 but
  `status: DELAYED` with `resultsCount: 0` for the sampled contract, and enumerating every
  contract × 30 symbols to reconstruct volume is impractical and still not live.

Because the plan is not authorized for options data (HTTP **403 / NOT_AUTHORIZED** on the
options snapshot endpoint), the proxy below was used instead. The per-row source column is
labeled `dollar_volume_proxy` accordingly.

**The 200k-daily-options-contracts threshold was NOT applied**, because options-contract
volume data was unavailable from the key's plan (403 NOT_AUTHORIZED on the snapshot
endpoint). A dollar-volume proxy is not a substitute for options volume, so no silent
threshold swap was made — the list below is simply ranked by the proxy, top 10 flagged.

## Proxy definition

For each symbol, for each archived RTH day: `dollar_volume = Σ (close × volume)` over the
09:30:00–15:59:59 ET 1-min bars. The figure shown is the **median over the most recent 60
archived days** in `data_archive/<SYM>/`. `days_used` is how many days actually entered the
median (most have 60; GOOG has only 4 archived days, so its median is over 4 — treat its rank
as provisional). All other symbols used 60.

## Ranked table (sorted descending)

| Rank | Symbol | Median daily $ volume | Source | Days used | Total archived | Focus list |
|-----:|--------|----------------------:|----------------------|----------:|---------------:|:----------:|
| 1  | MU    | 36,735,892,871 | dollar_volume_proxy | 60 | 599 | ★ TOP 10 |
| 2  | SPY   | 30,593,351,987 | dollar_volume_proxy | 60 | 551 | ★ TOP 10 |
| 3  | QQQ   | 24,586,795,686 | dollar_volume_proxy | 60 | 602 | ★ TOP 10 |
| 4  | NVDA  | 24,450,192,133 | dollar_volume_proxy | 60 | 599 | ★ TOP 10 |
| 5  | TSLA  | 17,145,578,355 | dollar_volume_proxy | 60 | 577 | ★ TOP 10 |
| 6  | AMD   | 12,373,985,690 | dollar_volume_proxy | 60 | 599 | ★ TOP 10 |
| 7  | INTC  | 11,837,245,137 | dollar_volume_proxy | 60 | 478 | ★ TOP 10 |
| 8  | MSFT  | 10,401,499,717 | dollar_volume_proxy | 60 | 599 | ★ TOP 10 |
| 9  | AAPL  |  9,932,679,042 | dollar_volume_proxy | 60 | 599 | ★ TOP 10 |
| 10 | AMZN  |  8,439,631,375 | dollar_volume_proxy | 60 | 600 | ★ TOP 10 |
| 11 | GOOGL |  7,377,988,680 | dollar_volume_proxy | 60 | 595 |   |
| 12 | IWM   |  6,913,073,876 | dollar_volume_proxy | 60 | 416 |   |
| 13 | META  |  6,841,197,888 | dollar_volume_proxy | 60 | 599 |   |
| 14 | AVGO  |  6,676,425,531 | dollar_volume_proxy | 60 | 484 |   |
| 15 | GOOG  |  4,856,551,546 | dollar_volume_proxy |  4 |   4 |   |
| 16 | TSM   |  4,731,881,704 | dollar_volume_proxy | 60 | 275 |   |
| 17 | PLTR  |  4,295,835,611 | dollar_volume_proxy | 60 | 502 |   |
| 18 | ORCL  |  4,155,116,215 | dollar_volume_proxy | 60 | 274 |   |
| 19 | NFLX  |  2,541,465,030 | dollar_volume_proxy | 60 | 507 |   |
| 20 | MSTR  |  2,166,173,806 | dollar_volume_proxy | 60 | 469 |   |
| 21 | HOOD  |  2,054,674,878 | dollar_volume_proxy | 60 | 508 |   |
| 22 | IREN  |  1,890,599,041 | dollar_volume_proxy | 60 | 251 |   |
| 23 | CRM   |  1,811,398,988 | dollar_volume_proxy | 60 | 253 |   |
| 24 | COIN  |  1,255,856,549 | dollar_volume_proxy | 60 | 599 |   |
| 25 | SOFI  |  1,187,890,074 | dollar_volume_proxy | 60 | 259 |   |
| 26 | BABA  |  1,163,843,596 | dollar_volume_proxy | 60 | 415 |   |
| 27 | SMCI  |  1,142,745,165 | dollar_volume_proxy | 60 | 270 |   |
| 28 | UBER  |  1,055,084,708 | dollar_volume_proxy | 60 | 252 |   |
| 29 | MARA  |    502,161,338 | dollar_volume_proxy | 60 | 258 |   |
| 30 | RIVN  |    384,882,408 | dollar_volume_proxy | 60 | 251 |   |

## Top-10 focus list (by dollar-volume proxy)

MU, SPY, QQQ, NVDA, TSLA, AMD, INTC, MSFT, AAPL, AMZN

## Caveats

- This is **dollar volume of the underlying**, a liquidity proxy — it is not options open
  interest or options contract volume. It will over-weight high-priced low-options names (e.g.
  MU at ~$37 B/day) and under-weight cheap, options-heavy names (e.g. SOFI, MARA, RIVN).
- GOOG has only 4 archived days; its figure is a 4-day median and its rank is unstable. It
  would very likely rank differently with a full 60-day sample.
- When Austin upgrades the Polygon plan to one serving options data, re-run against the
  snapshot endpoint and apply the real 200k daily-contracts threshold.
