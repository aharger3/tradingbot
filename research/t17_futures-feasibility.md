# T17 — futures / prop-firm feasibility

**Track:** T17 (spec Group 5) · **Script:** `research/t17_futures_feasibility.py`
(run output → `research/t17_facts.json`) · **No backtest ran. None is claimed.**

His ask, verbatim (`research/marks/probe_master_2026-08-29.jsonl`, card `fact_strike`):

> "You recommended 1 DTE, Separate and more important is prop firms too so measure
> those futures trading as well, lots of angles need to be measured here more
> subagents then u think."

## Headline

**Null result by construction, not by measurement: the archive has zero futures bars
(verified below), so there is no futures backtest to report — fabricating one is the
exact failure mode this spec forbids.** What *can* be reported, and is: which prop
firms he has actually talked about, what each imposes, what a real first test would
cost, whether OMEN's mechanics transfer to the instrument, and the one decision this
hands back to him.

## 1. What already exists (found, not rebuilt)

Two prior research passes already answered most of this track's brief, both
committed and both cite primary sources:

- `research/futures-propfirm-research.md` (2026-07-11) — automation/API/copy-trading
  policy for Topstep, Apex Trader Funding, MyFundedFutures, TradeDay, Earn2Trade,
  Funded Futures Family. Its own stated gaps: no verified drawdown type, eval cost,
  fees, or payout split for any firm as of that pass — "source these directly from
  each firm's current pricing page" before spending money.
- `research/g4_prop_fit.md` (2026-07-14) — prices the vehicle (not the edge): a
  Monte-Carlo risk-of-ruin model (`research/g4_prop_fit.py`, `research/d3_risk_of_ruin.py`)
  re-enveloped per firm's 2026 specs. Verdict: Apex $150K EOD at a $250–350 risk unit
  clears its <5% funded-ruin gate; its 20-account copy-stack scales a small edge to
  $17k–32k/mo. **Its own caveat #1, unchanged by this track:** *"The strategy stats
  are from EQUITY OPTIONS backtests. Prop firms are futures-only... 43/45.5/50.6%W
  and the fixed 2:1 R:R have never been measured on ES."* That gap is exactly this
  track's remit and it is still open — see §3.

This report does not repeat that work. It (a) verifies the facts those two reports
and this spec depend on, mechanically, so "no futures data" is a grep result and not
an assertion, and (b) answers the two questions neither prior pass covers: which
firms Austin himself named, and whether OMEN's setups transfer to the instrument at
all.

## 2. Which prop firms Austin has actually mentioned

Vanquish Trader is not a hypothetical — it is the account he trades **now**. OMEN was
named Vanquish until a rename (`Projects/OMEN.md:623`, vault). It is an **options**
account (`$150k, $7,500 trailing DD, support.vanquishtrader.com` — `risk_of_ruin.py`
header, verified 2026-07-10), not futures, and it is DX Trade, not an open API:

> "We have to go with the SignalBot since Vanquish won't let me use the API, but
> later we can probably do that once I am profitable on these 10 Vanquish accounts."
> — dictation, 2026-07-08 (`Projects/OMEN.md:2044`)

He asked about alternatives explicitly the same week:

> "What other options are available for trading with a prop firm apart from Vanquish
> Trader?" — dictation, 2026-07-10 (`Projects/OMEN.md:2095`)

That question is what produced `futures-propfirm-research.md` and `g4_prop_fit.md`.
Firm name-hit counts across the tracked corpus (script output, `t17_facts.json`,
file-count not mention-count):

| firm | files mentioning it |
|---|---:|
| Topstep | 21 |
| Vanquish | 9 |
| Apex Trader Funding | 7 |
| MyFundedFutures | 3 |
| TradeDay | 2 |
| Earn2Trade | 2 |
| Bulenox | 2 |
| Funded Futures Family | 1 |
| FundedNext | 1 |
| TakeProfitTrader | 0 |

Topstep's count is inflated by Discord trading-floor chatter (other community
members' fills, not Austin's own words) — `g4_prop_fit.md` already flags Topstep as
the cleanest fallback firm regardless (cheapest evals, no 30-day expiry, but a
5-account cap vs. Apex's 20). Apex is `g4_prop_fit.md`'s pick on the economics; it is
also the firm with a live policy-risk caveat in the same doc (own-account copy-trading
permission should be reconfirmed in writing before buying 20 evals).

## 3. Does the setup transfer to futures at all

OMEN trades six levels, defined in code (`_extract_days.py::levels_for`):
**ORH/ORL** (opening range, the first five RTH minutes 09:30–09:34), **PMH/PML**
(premarket high/low), **PDH/PDL** (prior day high/low) — plus break-and-retest,
one-candle-rule, and the 84% reclaim all keyed off those levels and the 09:30–11:00
window.

- **The window transfers cleanly.** ES/NQ track the S&P/Nasdaq; their own volume and
  volatility peak at the 09:30 ET cash open, the same bar OMEN already keys its
  window off. Nothing about "09:30–11:00" is equity-specific.
- **PDH/PDL and ORH/ORL transfer, and are if anything more standard in futures
  trading than equities** — prior-day-high/low and opening-range breakout are
  textbook ES/NQ concepts, not something borrowed from the stock side.
- **PMH/PML is the one level that changes meaning.** Equities have a thin,
  low-liquidity premarket session that "premarket high/low" meaningfully separates
  from the prior close. Futures trade nearly 23/5 on Globex — there is no
  low-liquidity premarket to speak of, so "PMH/PML" needs a redefinition (e.g. the
  Asia/London session range, or the prior 5pm–9:30am ET Globex range) before it means
  the same thing it means on a stock. That redefinition is a design decision, not a
  blocker — but it means the six levels are **five that transfer as-is and one that
  needs a rule**, not six-for-six.
- **Break-and-retest, one-candle-rule, and 84% reclaim are price-action rules, not
  equity-specific rules.** Nothing in their code (`signal_runner.py`, `predicates.py`)
  references shares, options, or an equity-only mechanic. They should fire on ES/NQ
  candles exactly as they fire on stock candles, mechanically — **should**, because
  this has never been run (see §4), so this is a code-reading claim, not a measured one.

## 4. What a real first test needs, and what it costs

**Data.** `polygon_feed.py` — the source for every number in `t0`/`t60`/`t70` and
every backtest report in this repo — hits `/v2/aggs/ticker/{symbol}/range/1/minute/`,
Polygon's **stocks** aggregates endpoint (verified: `research/t17_facts.json`,
`polygon_endpoint`). Polygon has no futures product; that endpoint will 404 or
silently return nothing for `ES`/`NQ`. `futures_feed.py` exists but is a **live-only**
`yfinance` wrapper — its own self-check pulls 5 recent 1-minute candles and exits; it
has never written to `data_archive/`, so it cannot answer a 2-year recall or
durability question. `data_archive/` today holds 34 symbols (all equity/index) and
16,817 symbol-days total — **zero of them futures** (script-verified). Building a
comparable futures archive means a new, paid historical-tick vendor for CME futures
(Databento, CQG, or a broker's own historical export) — this report does not price a
specific vendor plan because doing so without checking a live pricing page is exactly
the kind of unverified number `futures-propfirm-research.md` already flagged and
refused to publish for prop-firm fees; the same discipline applies here.

**Money.** `g4_prop_fit.md` already prices the funded-account side: Apex $150K eval
≈ $397/attempt (routinely 80–90% off in promos), $99 activation, $4,000 trailing DD.
That is the cost to get *a* funded account. It is not the cost to know whether OMEN's
edge survives on ES — that is a data cost, upstream of any eval spend, and unpriced
here for the reason above.

**The smallest real first test**, in order, each one gating the next:
1. Pull enough ES/NQ 1-minute history (a small paid sample, weeks not years) to
   run OMEN's six-level detector unmodified except for a PMH/PML redefinition,
   and read off detection rates the same way T2 reads OCR detection rates against
   his marks — a *detection* check, not a P&L check.
2. If detections look real, forward-paper the signals live (yfinance/`futures_feed.py`
   is sufficient for this — it is a live feed, its only defect is that it cannot
   build a backtest archive) for enough sessions to get a held-out win-rate read,
   the same bar `g4_prop_fit.md`'s kill-line already names: **below ~40%W the
   Apex risk unit collapses to ≤$175 and the plan dies; at ≤36%W nothing clears
   the 5% ruin gate at any size.**
3. Only after step 2 clears that bar does spending on an Apex eval (§2, §"Money")
   become a bet on a measured edge instead of a hope.

## 5. The decision this hands to Austin

**Buy a small block of ES/NQ 1-minute history (weeks, not years) from a real futures
data vendor, or say no.** Nothing past step 1 above can start without it — the
archive has 16,817 equity symbol-days and zero futures ones, Polygon does not sell
futures bars, and `futures_feed.py` cannot build an archive because it only reads
live. Every number in `g4_prop_fit.md` (the vehicle) is already priced and waiting;
every number about whether OMEN's edge exists on ES/NQ (the strategy) is blocked on
this one purchase. This is the same fork `g4_prop_fit.md` named seven weeks ago and
it has not moved: **"An F2-style shadow on the ES mode is a prerequisite — this memo
prices the vehicle, not the edge transfer."**

## Caveats

- No futures backtest ran. No futures win rate, mean R, or recall number appears
  anywhere in this report — that is the finding, not an omission.
- `futures-propfirm-research.md`'s own gaps (drawdown type, eval cost/target,
  activation fees, payout splits — largely closed for Apex/Topstep/MFF by the later
  `g4_prop_fit.md`, but not for TradeDay/Earn2Trade/Bulenox/FundedNext) are still
  open and are not re-verified here.
- The PMH/PML redefinition for a near-24hr session (§3) is a design opinion, not a
  measured or ratified fact — nothing in `probe_master_2026-08-29.jsonl` speaks to
  it, because he has never been asked.
- `t17_facts.json`'s prop-firm mention counts are file-hit counts, not a sentiment or
  frequency measure — Topstep's high count is mostly other traders' Discord chatter,
  not Austin's own words; §2 quotes only his own sentences.
