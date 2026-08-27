# P16/W3 — `htf_bias` has no author

Date: 2026-08-27. Trigger: Austin, rule ballot batch 02 (`research/rule_ballot_batch02.jsonl`,
row `c6`), asked directly what higher-timeframe bias should mean and answered:
**"we dont have any higher timeframe bias yet youll need to tell me what that is then."**
Meanwhile `research/g4_dropped_s.md` attributed **3,525 of 7,219** dropped S signals to
"HTF bias opposed" — the single largest killer in the legacy grader. This is the trace,
the plain-language read, the corpus check, and the deletion measurement that ticket asked for.

**Files that carry a human judgement are untouched.** No `*marks*.jsonl`, `research/marks/`,
or `rule_ballot_*.jsonl` file was written to in this pass — read-only.

---

## 1. Trace — every producer and consumer

Two genuinely different "HTF bias" concepts share a name in this codebase. Keeping them
apart is the first finding.

### 1a. The veto this ticket is about — 1-hour close vs SMA20 of prior hourly closes

| role | file : line | what it does |
|---|---|---|
| **produce** (backtest) | `backtest_week.py:537` `htf_bias_for(hourly, day_iso)` | close vs SMA20 of the last 20 hourly closes strictly before the session, ±0.1% dead band |
| **produce** (backtest) | `research/t4_engine_recall.py:104` `htf_bias(symbol, day)` | same formula, reading `data_archive` RTH bars instead of an hourly series — 12 research scripts (`t3_session_extreme.py`, `t5_no_repeat_effect.py`, `t6_no_repeat.py`, `t6_count_arming.py`, `t8_verdict_measure.py`, `t10_pivot_levels.py`, `t11_s_quality.py`, `t51_*.py`, `t62_veto_autopsy.py`, `t66_downgrade_measure.py`, `t71_near_miss.py`, `build_calibration.py`) import this one function rather than re-deriving it |
| **produce** (live, stocks) | `tastytrade_feed.py:521` `TastytradeFeed.fetch_htf_bias()` | same SMA20-of-hourly formula, ±0.1% dead band, fetched live over DXLink 1h candles |
| **produce** (live, futures) | `futures_feed.py:67` `FuturesFeed.fetch_htf_bias()` | same idea via yfinance 1h candles, but **no dead band** — returns only bullish/bearish, never neutral (a third, slightly different reimplementation) |
| **wire live -> runner** | `live_scanner.py:155-190`, `:377-384` | `get_daily_context()` calls the feed's `fetch_htf_bias`, caches it, refreshes every 15 minutes, and stamps it onto `runner.htf_bias` before every scan |
| **consume — the veto** | `omen_bot.py:172-193` `PriceActionAnalyzer.grade_trade` (imported and called by every one of `signal_runner.py`'s ten detection sites: lines 1643, 1734, 1758, 1789, 1832, 1883, 1954, 1977, 2003, 2045) | opposed direction -> `TradeGrade.D` (hard skip); `neutral` caps A+/A down to B. **This is the veto that kills the 3,525.** Live path: `live_scanner.py` -> `SignalRunner.detect_signals()` -> these same call sites, so a real scan is gated the same way a backtest replay is. |
| **consume — demoted, no vote** | `research/downgrade.py:345-370` `score()` | reports `observations["htf_opposed"]` and does not touch `grade`/`net` — already the shape this ticket asks the legacy grader to match (confirmed green by `research/test_downgrade.py`) |
| **consume — reported only, third code path** | `signal_runner.py:821-826` `_htf_opposes()`, `:874-925` `compute_austin_tier()` clause 4 | a **separate** S/A/C/X tier (`Trading-Bot-Rulesets.md` "Austin's Tiers", dated 2026-08-09) that also votes on `htf_bias`, gated by a **hardcoded, non-configurable** `HTF_OPPOSITION_VETO = "hard"` (`signal_runner.py:362`). Its own comment says *"the one clause Austin has not settled"* and *"T8 A/Bs it"* — `research/t8_verdict_measure.md` does not exist yet, so that measurement is still open. This field is reported-only: the code comment at `signal_runner.py:351-353` states `sig["grade"]`, `_SKIP_GRADES` and what `_route` accepts are untouched by it, and `austin_tier` is a separate ladder from `downgrade.py`'s (a third ladder, not the two named in the project's own "two grade ladders" note) — it does not gate a trade today, but it is a second unauthored veto, hardcoded rather than flagged, and out of this ticket's scope (**flagging it, not fixing it** — see §5). |
| **measure** | `research/g4_dropped_s.py` (this ticket's edit, §8) | instruments `PriceActionAnalyzer.grade_trade` to record the branch with and without the veto (`pa_branch(..., skip_bias=True)`), joined onto `research/bt2y_trades.json` |

**`paper_trader.py` has no direct producer or consumer of `htf_bias`.** It only opens
positions from whatever `SignalRunner._route()` already emitted, so it inherits the
veto's effect through the live path above rather than reading the field itself — confirmed
by grep, zero hits for `htf` in `paper_trader.py`.

### 1b. A different thing wearing the same name — `HTF_BIAS_GATE` (SPEC10, already measured)

| role | file : line | what it does |
|---|---|---|
| produce | `signal_runner.py:994` `daily_trend_bias(daily_closes, period=20)` | close vs SMA20 of **daily** (not hourly) candles |
| consume | `signal_runner.py:191` `HTF_BIAS_GATE` env flag (**default OFF**), `:2070-2072` | caps counter-daily-trend signals to alert-only |

This one is unrelated to the ballot question and already A/B'd on the 12-month rig
(`research/c5_htf_gate.py` / `c5_htf_gate.md`). It is default OFF, env-configurable, and
not touched by this ticket. `research/g4_dropped_s.md` §7 item 2 already made this
distinction; it is repeated here because the two are easy to conflate by name alone.

### 1c. The bug this is *not*

`8797aee6` ("the 'vs HTF bias' facet was really 'call vs put'") fixed `backtest_2y.py`'s
own `aligned` **reporting field**, which compared `bias == "bull"` against a value that is
actually `"bullish"`/`"bearish"` — a string mismatch that made the comparison always
False. That field is read by nothing in detection or simulation; it only broke one
interactive-report facet. The veto in `omen_bot.py::grade_trade` uses the correct strings
throughout and is wired into every live and backtest detection site — a different bug
class from the one `8797aee6` found, not the same bug recurring.

---

## 2. What the veto actually computes (plain language)

`htf_bias` is the close of the most recent completed **1-hour** candle compared to the
20-period simple moving average of the 20 hourly candles before it — both taken from bars
strictly before the trading day's 9:30 open, never from the current session. If that last
hourly close sits more than 0.1% above the average, the hour is called "bullish"; more
than 0.1% below, "bearish"; inside that band, "neutral." The grader then throws out any
signal whose direction disagrees with that label outright — a long when the label is
"bearish" is skipped entirely, and vice versa — and caps a "neutral" hour's best signals
down one notch. It is a genuine higher-timeframe read (the 1-hour bar really does sit
above the engine's 1-minute working timeframe, unlike the `8797aee6` bug), but it is a
plain trend filter that nobody on the team ever specified or ratified: three modules
(`tastytrade_feed.py`, `futures_feed.py`, `backtest_week.py`/`t4_engine_recall.py`) each
reimplement the same SMA20-of-hourly-closes idea independently and slightly differently,
which is what an unowned rule looks like when it has been copy-pasted around a codebase
instead of written once and cited.

---

## 3. Corpus check

Queried `research/corpus_index.jsonl` (5,460 rows) with `research/corpus_query.py`, P11's
convention: CONFIRMED / CONTRADICTED / UNMENTIONED against a rule someone actually stated,
never invented from silence.

| question | verdict | strongest support |
|---|---|---|
| Does a higher-timeframe bias/thesis matter at all? | **CONFIRMED (concept)** | TRADER_SAID `scarface-rules-videos.md:8297` (score 11) — *"an A plus setup would have to have a qqq context [and] a higher time frame thesis"*; `scarface-rules-videos.md:4870` (Hayden) — *"if the daily is bullish the four hours... same thing with the 15 minute and the one hour... you're trading the trend"*; `scarface-rules-youtube.md:24` (DOC_CLAIMS) — *"QQQ/SPY Alignment is Non-Negotiable."* Already partially captured in `research/p11_parameter_provenance.md` B3 as CONTRADICTED (partial) for a different reason: the coded A+ stack lacks the QQQ-context half of this same requirement. |
| Is the specific formula — **1-hour** close vs a **20-period SMA**, **±0.1%** dead band — stated anywhere? | **UNMENTIONED** | Zero TRADER_SAID or DOC_CLAIMS rows across "higher timeframe bias," "daily trend bias," "20 period moving average hourly," or "1 hour candle trend direction" name a moving-average length, a specific timeframe pairing, or a numeric dead band. The closest is Scarface's own multi-timeframe menu — *"daily and weekly... for bias, one hour and 15 minute... for narrative"* (`scarface-rules-videos.md:1702`) — which puts bias on **daily/weekly**, not the 1-hour bar this veto reads. If anything, the taught timeframe for "bias" is one level higher than what is coded. |
| Has Austin (the only person who can ratify an OMEN rule) ever defined or approved this computation for this engine? | **CONTRADICTED** | Austin himself, TRADER_SAID (rule ballot batch 02, c6, 2026-08-27): *"we dont have any higher timeframe bias yet youll need to tell me what that is then."* This is a direct statement, from the rule's only possible author, that no such rule exists yet in his system — regardless of what the course material teaches or what the code computes. |

**Net verdict: concept CONFIRMED by the source material Austin learned from; the specific
coded formula UNMENTIONED anywhere in the corpus; and Austin's own ratification of *any*
OMEN-specific HTF rule is CONTRADICTED by his own words two days ago.** The code is not
hallucinating a concept that doesn't exist in trading — it is hallucinating that a real
concept was ever turned into a specific, author-approved rule for this engine.

---

## 4. Deletion measurement

Reproduced by `research/g4_dropped_s.py` (committed; `python research/g4_dropped_s.py`
regenerates `research/g4_dropped_s.md` from `research/bt2y_trades.json`, same two-year,
28-symbol, 500-session window as every other G4 number). New in this pass: `pa_branch()`
takes a `skip_bias` argument and the instrumented replay records both the with-veto and
without-veto verdict for every signal (`research/g4_dropped_s.py` lines 78-122, 130-137,
150-163, 343-347), reported in full in `research/g4_dropped_s.md` §8.

| set | n | win rate | mean R | median R |
|---|---:|---:|---:|---:|
| dropped S, viable stop, all gates (§4 baseline) | 588 | 50.2% | +0.465 | +0.136 |
| **HTF-veto arm: viable stop AND grades B+ with the veto off** | **60** | **55.0%** | **+1.012** | **+0.464** |
| S signals the engine actually traded (incumbent) | 128 | 66.4% | +1.283 | +1.129 |
| the whole traded book (incumbent, money gate = 2.0R) | 1016 | 53.4% | +0.957 | +0.575 |

Of the 3,525 signals the veto currently kills, restricted to the 323 that clear
`_min_viable_stop` (the same exclusion `research/g4_dropped_s.md` §4 uses everywhere else
— degenerate two-cent stops manufacture triple-digit R and are unquotable):

- **60 (1.7% of 3,525) reach a tradeable tier** (`B` or `A+`) once the veto line is deleted.
- **84 more become alerts** (`C`).
- **263 still die elsewhere** — the colour gate or "never touched the level" — with or
  without the bias veto.

The 60 that would newly trade average **+1.012R**, *above* the book's own incumbent mean
of +0.957R and well clear of the general dropped-S set's +0.465R — unlike the colour-gate
counterfactual in §2 of the same document (+0.293R, indistinguishable from the discard
pile), this freed set is not obviously worse than what already trades. **Read the sample
size honestly: n=60 is a fifth the size of the traded S book (n=128)** and this is still
short of the 2.0R money gate. It is a candidate worth a real, deduped A/B — not a result
to size a position on.

---

## 5. What changed, and what didn't

**Changed.** `omen_bot.py`: a new `HTF_BIAS_VETO` env flag, **default OFF**, gates the
opposed-direction `-> TradeGrade.D` line inside `PriceActionAnalyzer.grade_trade` (the
legacy grader). Default OFF means an opposed hour no longer skips a signal outright — it
grades on price action alone, same as today's `htf_bias=None` (unknown) behavior. The
"neutral caps A+/A to B" line is untouched (it was never the thing measured or disputed;
`research/downgrade.py::score()` has no observation for it either, so touching it would
go beyond what this ticket demoted). `HTF_BIAS_VETO=1` restores the exact old behavior —
verified directly (see `spec0b_levels_check.py`, updated in the same commit) and by
`research/test_downgrade.py` staying green (untouched, `downgrade.py` was not edited).

**Not changed.** The computation itself (`htf_bias_for`, `fetch_htf_bias`, `t4_engine_recall.htf_bias`)
is untouched everywhere — the value is still computed and still available as
`observations["htf_opposed"]` in `downgrade.py` and as `runner.htf_bias` for anything that
wants to read it. Nothing about the read is deleted, only its vote in the legacy grader.

**Flagged, not fixed (Amber — this moves a live default, say so).** This flag flips a
default that is wired into the **live path**, not only the backtest: `live_scanner.py`
feeds real `fetch_htf_bias()` reads into `SignalRunner`, and every one of its ten
`grade_trade` call sites will now grade an opposed-bias signal on price action alone
instead of skipping it, the moment this ships without `HTF_BIAS_VETO=1` set. That is the
point of the ticket (Austin's own default is to delete an unauthored veto), but it is a
real behavior change to what fires live, not just a backtest number, and is called out
here explicitly per the ticket's own instruction to treat a live-path rule differently
from a backtest-only one.

**Found, not touched — a second unauthored HTF veto.** `signal_runner.py::compute_austin_tier`
clause 4 (`_htf_opposes`, `HTF_OPPOSITION_VETO = "hard"`, hardcoded, not flagged) is a
third, independent implementation of the same idea, feeding a different reported field
(`austin_tier`) that does not gate `_route`/trading today. Its own code comment already
calls it "the one clause Austin has not settled." Out of scope for this ticket (it is not
"the legacy grader," and its measurement, T8, has not been run) but worth a line to
Austin: the same unresolved question exists twice in the codebase under two different
names.

---

## 6. For Austin — one paragraph, one number

**What it is:** the engine compares each stock's last completed 1-hour candle to the
average of its last 20 hourly candles (before that day even opens) to call the hour
"bullish," "bearish," or "neutral," then used to hard-skip any trade going the other way.
Nobody wrote that rule down or picked those numbers for OMEN specifically — the code
copied it into three different places on its own. **The number:** turning that skip off
frees 60 signals (out of the 3,525 it currently kills) into a tradeable grade, and those
60 would have averaged +1.012R — a little better than the book's own +0.957R average,
on a small sample. Your call, same as the ticket asked: tell us what higher-timeframe bias
should mean, or leave the veto off.
