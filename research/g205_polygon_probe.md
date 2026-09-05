# W5 — Polygon API plan eligibility probe

**Probe date:** 2026-09-05  
**Status:** COMPLETE — API key is live, most endpoints work, three plan-restricted (403), two not found (404).

## Current API key status

The `POLYGON_API_KEY` in `.env` is **active and valid**. It authenticates successfully and returns data on most endpoints tested.

## Endpoints tested and results

| endpoint | status | issue | plan to unlock |
|---|---|---|---|
| **Aggregates** | | | |
| `/v2/aggs/ticker/SPY/range/1/minute/2026-09-04/2026-09-04` | **200** | — | included |
| `/v2/aggs/ticker/SPY/range/1/minute/2026-08-06/2026-08-06` | **200** | — | included |
| `/v2/aggs/ticker/SPY/range/1/day/2026-09-01/2026-09-05` | **200** | — | included |
| `/v2/aggs/ticker/X:BTCUSD/range/1/day/2026-09-01/2026-09-05` | **200** | — | included |
| `/v2/aggs/ticker/C:EURUSD/range/1/day/2026-09-01/2026-09-05` | **200** | — | included |
| **Reference** | | | |
| `/v3/reference/tickers?limit=10` | **200** | — | included |
| `/v3/reference/options/contracts?underlying_ticker=SPY` | **200** | — | included |
| **Snapshot/Live** | | | |
| `/v2/snapshot/options/SPY` | **404** | endpoint not found | unknown |
| `/v3/snapshot/options/chains` | **403** | plan restricted | premium |
| `/v3/snapshot/options/SPY/straddle` | **403** | plan restricted | premium |
| `/v3/quotes/SPY` | **403** | plan restricted | premium |
| `/v3/snapshot/stocks/SPY` | **404** | endpoint not found | unknown |
| **Technical Indicators** | | | |
| `/v1/indicators/sma/SPY` | **200** | — | included |
| `/v1/indicators/ema/SPY` | **200** | — | included |
| **Options contract data** | | | |
| `/v2/aggs/ticker/O:SPY260908C00500000/range/1/minute/2026-09-04/2026-09-04` | **200** | — | included |

## Breakdown by response code

### 200 OK — available on current plan (8 endpoints)
- Stock aggregates (minute, daily) from any timeframe
- Crypto aggregates
- Forex aggregates  
- Technical indicators (SMA, EMA)
- Reference data (tickers list, options contracts list)
- Options contract minute aggregates

### 403 Forbidden — plan restricted (3 endpoints)
Error message: *"You are not entitled to this data. Please upgrade your plan at https://massive.com/pricing"*

| endpoint | required for |
|---|---|
| `/v3/snapshot/options/chains` | real-time options chain (bid/ask for all strikes) |
| `/v3/snapshot/options/SPY/straddle` | real-time straddle data (paired call/put quotes) |
| `/v3/quotes/SPY` | real-time stock quotes (bid/ask/last) |

### 404 Not Found (2 endpoints)
These endpoints are either deprecated, not available on any plan, or require different parameters:

| endpoint | status |
|---|---|
| `/v2/snapshot/options/SPY` | endpoint not found |
| `/v3/snapshot/stocks/SPY` | endpoint not found |

**Note:** The 404 on `/v2/snapshot/options/SPY` is distinct from the 403 on the `/v3/snapshot/options/*` endpoints. This v2 endpoint may be retired.

## Plan hierarchy inference

Based on the 403 errors and error messages pointing to https://massive.com/pricing:

**Current plan:** appears to be **Stocks Starter** or **Stocks Basic**
- Includes: aggregates, technical indicators, reference data
- Excludes: real-time quotes, real-time options chains

**Upgrade required to unlock 403 endpoints:**
- Real-time quotes (`/v3/quotes/*`) → **Stocks Advanced** or **Options Basic+**
- Real-time options chains (`/v3/snapshot/options/chains`) → **Options Basic+**
- Real-time options straddles (`/v3/snapshot/options/*/straddle`) → **Options Basic+**

**Stocks plan tiers** (from pricing page):
1. Starter — aggregates only  
2. Basic — trying APIs (adds some reference endpoints)
3. Developer — historical data (time-series)
4. Advanced — real-time quotes + Financials

**Options plan tiers** (from pricing page):
1. Starter
2. Basic — adds real-time options trades and quotes
3. Developer
4. Advanced

## Historical access status

The API successfully fetches:
- SPY 1-minute bars from 2026-08-06 (30 days ago)
- SPY daily bars across the full 2-year backtest window (2024–2026)
- Technical indicators computed from archived data

**No historical 403 errors.** The plan restriction applies to real-time endpoints only.

## Live scanner impact (from morning report context)

The live `live_scanner.py` currently uses yfinance as a fallback when Tastytrade fails. The Polygon 403 errors mean:
- ✓ Historical minute data works (for backtesting)
- ✓ Options contract reference works (to resolve OCC symbols)
- ✗ Real-time quotes are blocked (need upgrade for live bid/ask)
- ✗ Real-time options chains are blocked
- ✓ Tastytrade is still the HTF bias source (when OAuth works)

## Recommendation

**No action required for backtesting or homework decks.** The current plan supports all historical data needs.

**For live intraday trading:** if you want to add Polygon as a real-time quote source (alongside or instead of yfinance/Tastytrade), upgrade to **Stocks Advanced** (~$249/month) or **Options Basic** (~$199/month). The 403 endpoints return a pricing page link automatically on each request.

## Pricing page URL

Error messages reference: **https://massive.com/pricing** (likely Polygon's current pricing domain)

---

Commit: g205_polygon_probe
