# C5 — HTF_BIAS_GATE A/B: daily-trend bias gate ON vs OFF (2026-07-13)

**Flag:** `HTF_BIAS_GATE` module global in `signal_runner.py` (default **OFF** —
shipped behavior unchanged, config untouched). Also an env override
(`HTF_BIAS_GATE=1`) for live/backtest toggling. SPEC10 daily-trend gate — **no
DXLink MTF needed.**

**Daily-trend proxy** (`signal_runner.daily_trend_bias`, the shippable
predicate the A/B measures): for a signal on day D, take that symbol's
**completed daily closes strictly before D** and compare the last close to its
**SMA20** — `bullish` if close > SMA20, `bearish` if <, `neutral` on an exact
tie. No look-ahead (D-1's close is known at D's open). Daily candles from
yfinance (per task). Simple close-vs-SMA20, one proxy, no framework.

**Gate ON** = only trade signals whose direction matches the daily trend
(call↔bullish, put↔bearish). Counter-trend signals are capped to C / alert-only
(they don't trade and free the day's tier slot). Days with no clear trend
(neutral / insufficient SMA20 buffer / no daily data) pass through ungated.

**Run:** SIMULATION on the clean 12mo baseline `research/c1_off_charts.json`
(671 traded / 866 signals, 24 symbols, 2025-07-14..2026-07-10) — same c3/c8
tier-sim pattern, so the baseline is bit-identical to every other C task. No
re-run (the gate is a directional filter over the existing population). Daily
bars fetched clean: **310 bars/symbol, 0 missing** (not rate-limited). Bias
coverage over (symbol, day) pairs: 397 bullish / 329 bearish, 0 neutral.
Analyzer: `research/c5_htf_gate.py`.

## Headline

| Metric | OFF (baseline) | ON (gate) | Δ |
|---|---|---|---|
| Traded (A+/A/B) | 671 tr, 37.5%W, +$78,190 | 423 tr, 36.2%W, +$32,320 | −248 tr, −1.3%W, −$45,870 |
| **S≥4+[hammer] tier** | **78 tr, 42.3%W, +$21,000/yr ($1,750/mo)** | **55 tr, 40.0%W, +$11,000/yr ($917/mo)** | −23 tr, −2.3%W, −$10,000/yr |

The gate blocks **248 of 671 traded signals (37%)** as counter-trend — but the
removed set was net-**positive**, so full-pop P&L is more than halved and win%
still drops. At the live S≥4+[hammer] tier it cuts 23 trades, drops win rate
42.3%→40.0%, and halves annual P&L.

## Verdict

**Keep OFF.** The daily SMA20 trend is not predictive of intraday
break-and-retest outcomes — gating on it removes ~37% of trades that were
collectively profitable, lowering both win% and P&L at the full population AND
at the only thing that trades live (the S≥4+[hammer] tier: −2.3ppW, −$10k/yr).
This is the same lesson as C1 (BNR_DISPLACEMENT_GATE) and C2 (FVG displacement):
untested directional gates in this codebase lose. A counter-trend break that
retests and confirms is a mean-reversion / reversal setup — exactly the trades
the strategy is built to catch — so forcing trend-alignment throws away real
edge. Leave `HTF_BIAS_GATE = False` as the shipped default. Do not revisit
unless a future variant uses daily bias for *sizing* (smaller counter-trend
size) rather than binary trade selection.

**Files:** analyzer `research/c5_htf_gate.py`; baseline
`research/c1_off_charts.json`. Code: `signal_runner.py`
(`HTF_BIAS_GATE` flag + `daily_trend_bias()` helper + `self.daily_bias` slot +
gate block before `return signals`). Default behavior unchanged.
