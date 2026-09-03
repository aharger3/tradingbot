# Bar availability for the mentor corpus (`research/corpus_sf/`)

**Question:** what fraction of the newly-mined mentor corpus is actually
backtestable — i.e. for every distinct `(symbol, session_date)` a mentor row
claims, do we hold 1-minute bars on disk, and what does it cost to close the gap?

**No bars were pulled.** This is a read-only census.
Rig: `research/corpus_sf/bar_availability.py` (rerun with
`python research/corpus_sf/bar_availability.py`).
Manifest of what is missing: `research/corpus_sf/bar_pull_manifest.jsonl` (400 lines).

---

## Headline

| | pairs | % of equity sessions |
|---|---:|---:|
| **Have bars on disk** | **3,784** | **90.4%** |
| **Need a Polygon pull** | **400** | **9.6%** |
| Equity sessions total | 4,184 | 100% |

Plus 839 pairs that no pull can fix or that are not sessions at all:
**711 futures**, **112 weekend**, **16 market holiday** (see *Not backtestable at
any price*). Grand total 5,023 distinct `(symbol, date)` pairs.

**Pull cost: 400 requests, ~2–7 wall-clock minutes.** The archive is far more
complete than the corpus is demanding. Bar availability is not the bottleneck
for this corpus — symbol coverage of the futures rooms is.

---

## 1. How this was measured

The cost model comes straight from `polygon_feed.fetch_day()`:

- Cache layout is `data_archive/<SYMBOL>/<YYYY-MM-DD>.csv`, premarket + RTH.
- Cache-first: if the CSV exists, the call is a disk read, **zero API cost**.
- One missing `(symbol, day)` = **exactly one** `/v2/aggs/ticker/.../range/1/minute/`
  request, **ever**.

So "instances needing a pull" and "requests" are the same number by construction.

`data_loader.py` is a **mock candle generator** and is not the bar source — it is
a `random.uniform` random walk for unit tests. The real leads are
`polygon_feed.py`, `archive_1m.py`, and `data_archive/`.

**Archive as it stands today:** 35 symbol directories, 17,131 cached CSVs,
660 distinct trading days spanning 2024-01-02 to 2026-08-21. (29 symbols from
`universe.py::ALL_SYMS` plus 6 legacy dirs: ARM, DIA, MSTR, QCOM, RIVN, SMCI.)

### Which rows were pooled

Nine trade-shaped files, **13,585 rows**:

| file | rows |
|---|---:|
| jdub_alerts.jsonl | 3,798 |
| misc.jsonl | 3,634 |
| scarface_alerts.jsonl | 2,955 |
| futures_alerts.jsonl | 2,252 |
| gains.jsonl | 492 |
| backtesting.jsonl | 250 |
| reviews_futures.jsonl | 114 |
| reviews_options.jsonl | 55 |
| pre_market_live.jsonl | 35 |

Excluded, and why — these ask for no bars:

- `questions.jsonl` (277), `general_chat.jsonl` (90), `tips.jsonl` (121),
  `maxims_futures.jsonl` (15) — **rule candidates**, not session claims.
- `live_sessions.jsonl` (547), `reviews_jdub.jsonl` (37),
  `premarket_charts.jsonl` (591) — **zero symbols by construction** (video and
  chart indices). 1,175 rows, none of which can name a bar.

Of the 13,585 pooled rows, **1,302 carry no symbol** and are unresolvable to a
pair (mostly `futures_alerts` live commentary that omits the contract, and
`jdub_alerts` management lines). The remaining 12,283 collapse to **5,023
distinct `(symbol, session_date)` pairs**.

`session_date` is the day the row is *about*, not always the day it was posted:
`trade_date` (reviews_futures) and `session_date` (premarket_charts) win over
`ts` where present.

---

## 2. Results

### Buckets — pairs, rows, and claim-bearing rows

A **claim row** carries at least one of direction / setup / level_name /
level_price / entry / stop / target / outcome / r_multiple. 10,019 of 13,585
pooled rows qualify.

| bucket | pairs | rows | claim rows |
|---|---:|---:|---:|
| **have_bars** — CSV already on disk | **3,784** | **10,002** | **8,165** |
| **need_pull** — real equity session, no CSV | **400** | **550** | **369** |
| futures_not_fetchable | 711 | 1,583 | 1,353 |
| weekend_no_session | 112 | 129 | 115 |
| market_holiday | 16 | 19 | 17 |
| **total** | **5,023** | **12,283** | **10,019** |

Read the top two rows as the answer: **73.6% of every pooled row already has
bars; the 400-request pull lifts that to 77.7%.** On claim rows alone,
**81.5% are already backtestable today**. Everything above 77.7% is
structurally unreachable, not merely un-pulled.

### Per-file pair coverage

| file | distinct pairs | have bars | need pull |
|---|---:|---:|---:|
| jdub_alerts.jsonl | 2,944 | 2,495 | 260 |
| misc.jsonl | 2,085 | 1,781 | 141 |
| scarface_alerts.jsonl | 917 | 893 | 24 |
| gains.jsonl | 430 | 401 | 6 |
| futures_alerts.jsonl | 455 | **0** | **0** |
| backtesting.jsonl | 106 | 60 | 1 |
| reviews_futures.jsonl | 64 | **0** | **0** |
| reviews_options.jsonl | 53 | 48 | 4 |
| pre_market_live.jsonl | 20 | 18 | 1 |

(Columns do not sum to the pair total — a pair is often claimed by several
files, and the two futures files' pairs fall entirely in the non-fetchable
bucket.)

**`scarface_alerts` is 97.4% covered right now** (893 of 917 pairs). The single
richest mentor channel in the corpus needs 24 requests to reach 100%.

---

## 3. What a pull would cost

**400 symbol-days = 400 requests.** No batching is possible: the aggregates
endpoint is per-ticker-per-day and `fetch_day()` issues one call each.

**Rate limit: none.** `polygon_feed._throttle()` is a documented no-op —
*"Stocks Starter (2026-07-08): unlimited calls, no rate cap"*. The old free-tier
12.5 s wait (5 req/min) is commented out; under that regime this pull would have
been 80 minutes. It is not.

Wall clock is therefore latency-bound, not quota-bound. There is **no parallel
fetcher in the repo** — `archive_1m.py` loops sequentially — so:

| assumed per-request latency | 400 requests |
|---|---:|
| 0.3 s | **2.0 min** |
| 0.5 s (likely) | **3.3 min** |
| 1.0 s (pessimistic) | **6.7 min** |

Measured floor from this box: TLS handshake to `api.polygon.io` is 77–123 ms
(median 90 ms, 5 samples, **no API call made**). `requests.get` opens a fresh
connection per call in `fetch_day()` — no `Session` reuse — so that handshake is
paid 400 times; the rest is a ~1,000-row JSON response plus a CSV write.

**Estimate: ~3 minutes, under 10 in the worst case.** Disk cost is
~400 x 80 KB, about **32 MB**.

### What the pull touches

| | pairs | distinct symbols |
|---|---:|---:|
| already in `universe.py::ALL_SYMS` | 211 | 21 |
| new symbol directories | 189 | 41 |
| **total** | **400** | **62** |

In-universe backlog, by symbol:

`GOOG 146`, SPY 8, INTC 6, AMZN 6, PLTR 5, NVDA 4, TSLA 4, AMD 4, MU 3,
SPCX 3, NFLX 3, GOOGL 3, HOOD 3, MSFT 3, AAPL 2, TSM 2, QQQ 2, AVGO 1,
COIN 1, MARA 1, UBER 1.

**GOOG alone is 37% of the entire pull (146 of 400).** `data_archive/GOOG/`
holds **4 CSVs** while `data_archive/GOOGL/` holds **654**. The mentors write
both share classes interchangeably; the archive only ever banked one. This is a
pre-existing archive hole that the corpus merely exposed — and it is the single
highest-value fix in this report.

New symbols the corpus wants that the archive has never seen (top): `SNDK 57`,
`SMH 18`, `WDC 11`, `COST 10`, `MRVL 8`, `F 7`, `DELL 6`, `UNH 5`, then a long
tail of 1–4 days each (HIMS, CRWV, TGT, TSLL, LULU, SMCI, APP, WMT, BTC, SHOP,
OKLO, STX, NBIS, RGTI, SBUX, SNOW, DIS, RKLB, JPM, RDDT, MCD, BA, CRCL, DDOG,
ABNB, NKE, GME, ASTS, BAC, C, and others). `SNDK` is Sandisk — Scarface named it
28 times in `scarface_alerts` and it is in no pool.

By year: 2026 gets 207, 2025 gets 102, 2024 gets 91.

---

## 4. Not backtestable at any price

### 711 futures pairs — 14.2% of the corpus, unreachable via this pipeline

`NQ 384`, `ES 272`, `SPX 16`, `MNQ 15`, `YM 9`, `MES 9`, `GC 3`, `CL 2`, `RTY 1`.

These carry **1,583 rows and 1,353 claim rows** — the largest single block of
lost signal in the corpus, and it is the *entire* usable content of
`futures_alerts.jsonl` (455 pairs) and `reviews_futures.jsonl` (64 pairs).

`polygon_feed.fetch_day()` calls the **stocks** aggregates endpoint. It cannot
return NQ or ES: index futures need Polygon's Futures product (a separate
entitlement and a different ticker convention, e.g. continuous contracts), and
`SPX` / `NDX` / `VIX` need the Indices product. Neither is wired into this repo.

That is a **procurement decision, not a pull**. Even if bought, MambaTrades'
vocabulary (opening print, gap fill, London/Asia session highs) is not the OMEN
six-level break-and-retest taxonomy, so the payoff is not obvious. Recorded here
so the cost of ignoring it is visible: it is a third of the corpus's claim rows.

### 112 weekend + 16 holiday pairs — parser artifacts, not sessions

Weekend pairs come overwhelmingly from `misc.jsonl` (85) and
`backtesting.jsonl` (26): weekend recap and methodology chat that names a ticker,
timestamped Sat/Sun. There is no session to replay. Holiday pairs cluster on
2025-01-20 (MLK, 7 pairs), 2026-07-03 (2), 2025-04-18 (Good Friday, 2), and six
single hits.

These are correctly-parsed rows about a *market that was shut*. Any downstream
consumer joining corpus rows to bars must drop them, or it will silently
mis-date a claim onto the neighbouring session.

---

## 5. Caveats a consumer must carry

1. **File existence was validated as a proxy for usable bars, and it holds
   here.** `research/bar_coverage.md` drops a mark on either `no_archive_file`
   *or* `entry_i >= n_rth`; in that report all 54 drops were the former.
   Checked directly for this corpus: of the 3,784 cached pairs, **3,783 have
   at least 250 bars; exactly one (HOOD, one day) is thin**. Note the archive
   does hold 589 near-empty CSVs overall — almost all `SPCX`, some header-only
   at 93 bytes — but the corpus never asks for them.

2. **Two "holidays" were archive-wide gaps, and are in the pull.**
   `2026-08-14` and `2026-08-18` are weekdays absent from **all 35** symbol
   directories. Inferring the calendar from the archive alone would have written
   them off as closures; an explicit NYSE closure table (in the script)
   reclassifies them as pullable. 25 pairs were recovered this way.

3. **53 pairs are dated by post date, not trade date.** All in
   `reviews_options.jsonl`, where Lauren and Hayden post a review hours or days
   after the trade. `have_bars` on those pairs means "we have bars for the day
   the *post* landed" — it does **not** mean the reviewed session is covered.
   Treat those 53 as date-unsafe and re-derive the date from the title.

4. **The pull backlog is low-confidence.** The 550 rows sitting on the 400
   missing pairs grade **375 low / 152 medium / 23 high**. Spending the 3
   minutes is still right — it is 3 minutes — but do not expect 400 new
   gradeable setups out of it.

5. **Polygon history depth is the one unverified assumption.** 23 of the 400
   missing pairs are older than two years (oldest: `2024-04-03`). The
   `polygon_feed` docstring says *"2 years of history on the free tier"*; the
   throttle comment says the account is on **Stocks Starter**, which carries 5
   years. If the plan ever reverts, those 23 pairs — and re-fetching anything
   from H1 2024 — become impossible. The 17,131 CSVs already banked are the
   hedge, and they are why the archive reaches back to 2024-01-02.

6. **Row counts are claims, not trades.** A pair with 11 corpus rows is 11
   *messages* about that symbol-day, at the parsers' stated precision
   (87–100% depending on channel). Bar availability says nothing about whether
   the claim is true.

7. **`questions.jsonl` is malformed JSONL.** 9 of its 277 rows carry raw
   newlines inside `quote`, so a per-line `json.loads` dies. The rig
   stream-decodes instead. All nine trade-shaped files are clean (per-line count
   equals stream count on every one). Flagged for whoever consumes that file
   next; nothing was rewritten.

---

## 6. One-line answer

Of 5,023 distinct mentor `(symbol, date)` claims, **3,784 (75.3%) are
backtestable today at zero API cost**; **400 more (8.0%) cost one 3-minute
sequential pull**, of which GOOG is 146; and **711 (14.2%) are index futures
that this repo's stocks-only Polygon pipeline cannot fetch at all** — the last
being the only number here that needs a decision rather than a script.
