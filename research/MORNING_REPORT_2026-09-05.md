# OMEN 9.0 — morning report v2, 2026-09-05

*Both waves, one report. v1 (wave 1 only) is superseded by this file.*

**One sentence:** the night mined 25 candidate rules out of your own marks and **not one survived
being attacked**, the second wave then attacked the three biggest unrefereed claims left standing
and **all three of those fell too** — so there is still no S classifier, but the live lane is now
fully wired to a paper broker, both dead credentials are fixed, and **no funding rung is fundable**,
because every candidate stream loses money in the last twelve months.

Wave 1 base commit `f8740f80`; wave 2 base `2b463bf6`. Everything below names its fill and its
script. Unless a row says otherwise: entry = **signal bar CLOSE**, stops via
`stop_rule.stop_fill_price()`, size-gated on `signal_runner.min_risk_floor`, **1R = $1,000**, book
`research/bt2y_trades_retest_on.json` (RETEST_REQUIRED=1, 498 sessions 2024-09-03 → 2026-09-02),
one-trade-a-day unit `research/omen_metrics.first_of_day_arm`. **H1** = before 2025-09-01,
**H2** = 2025-09-01 onward.

**The three things wave 2 changed, if you read nothing else:**

1. **F9's mid-candle $100/day is dead.** Three referees, three routes, same verdict. The honest
   number is **$27/day against the shipped close's $34–37/day**. The vault was right all along.
2. **The vision eye-test is void.** The 100-card deck leaked your answer in every single card — a
   reader that never looks at a candle scores 100% precision and 100% recall off the chart's cut
   time alone.
3. **The paper broker is wired and armed.** Every fired S now submits a real order to Alpaca's
   **paper** endpoint, and `run_daily.ps1` launches with it on. Replay is asserted never to submit.

---

## 1. THE ANSWER — is there an S classifier?

**No. Not one rule out of twenty-five survived.**

The question was: does a classifier exist that fires 1–3 times a day, holds precision above the bar,
keeps S recall, and pays past $397/day with every month green.

| stage | result |
|---|---|
| comments harvested from your marks | 2,675 rows, **1,521 with prose**, 896 over 40 characters (`research/g150_marks_comments.md`) |
| candidate rules mined from that prose | **25** (`research/g152_rule_candidates.md`) |
| measured on the honest book | 25 of 25 (`research/g154_rule_*.py`, one script per rule) |
| passed the F5 survivor bar | 8 |
| **still standing after three independent refuters each** | **0** (`research/g155_rule_verdicts.md`) |

Eight rules looked like winners. Three separate agents attacked each one — for lookahead, for
multiplicity, and by re-running the script — and all eight went down 3-for-3:

- **`stop-placement-routed`** (+$13.00/day) was a **no-op**. On 7,302 of 7,302 break-and-retest
  candidates the "routed" stop already equals the shipped stop. Routing the stop to *itself*
  reproduces the entire gain to the cent. The $13 was a different exit model, not a different stop.
- **`entry-earlier-satisfiable-bar`** was flagged a survivor by a **bug in the survivor test**:
  precision was OR'd into both half-conditions, so one precision number satisfied "H1 improves" and
  "H2 improves" simultaneously. Its actual H1 money fell **−$145.33/day**.
- **`scale-before-the-level`** (+$43/day) rests on **7 fills where the bar's high equals the limit
  price to the penny and goes no further**. Requiring price to trade one cent through kills it.
- **`exhausted-overextended`**: the shipped rule changed **0 of 498 day-picks**. The reported gain
  came from a re-parameterised threshold picked in-sample, worth +$1.31/day against a ±$104 interval.

### What shipped anyway, and what it does

`signal_runner.py` carries **`S_CLASSIFIER`, default OFF** (commit `eaa62705`,
`research/g156_s_classifier_v0.md`). It drops an OR-high / OR-low break that never retested the
level. It is the best of the non-refuted candidates, and it is an **honest zero**:

| measure | baseline | S_CLASSIFIER v0 | target | met? |
|---|---:|---:|---:|:--|
| precision (fired days you graded S ÷ fired days you graded) | 30.5% (18/59) | **30.5% (18/59)** | >39.5% | **no** |
| S recall, 100-card deck (`probe_s_sweep_2026-08-28.jsonl`, 34 S) | 44.1% | 44.1% | no loss | yes |
| S recall, all bar-backed S days | 49.0% | **48.7%** | no loss | **no, −0.3pp** |
| $/day, whole book | $33.93 | $47.44 | past $397 | **no — and refuted** |
| H1 $/day | $135.71 | $144.27 | | |
| H2 $/day | −$67.85 | −$49.39 | | |

The **+$13.51/day was refuted 3-for-3** (`research/g156_refute{1,2,3}_*.md`). Only 12 of 498
sessions change hands, and **one day — 2025-11-20 — is 50.1% of the entire gain**. A random drop of
the same number of candidates beats +$13.51 about 7–9% of the time, and with 25 candidates tried the
expected number of noise "winners" is ~5.6. Its "both halves positive" credential is also not a
validation: H2 was read to *select* the rule, so no half is held out.

**The `>39.5%` target was never apples-to-apples, and this is now fixed in `CLAUDE.md`** (wave 2,
W8). The 39.5% was candidate-level precision across the whole fired pool. Every measurement here is
graded-day precision on the one-trade-a-day pick, whose baseline is **30.5%** (18 of 59 graded days).
`CLAUDE.md` now names 30.5% on the pick as the lane bar and keeps 39.5% as the secondary
candidate-level read. The verdict is unaffected either way: both arms score 18/59, same numerator
*and* same denominator.

**Fires/day was never answered.** The measurement unit picks exactly one candidate per day by
construction, so "1–3 fires a day" cannot be read off it. It needs a live-fire count — and as of
wave 2 the live path submits real paper orders, so that count starts accumulating on the next
session.

### The ML ceiling says there is nothing to find in these features — and it held up

`research/g157_ml_ceiling.py`, 120 judged day-cards (28 S, 23.3% base rate), logistic regression and
gradient boosting, CV grouped by month:

| model | AUC | precision at the rule engine's recall |
|---|---:|---:|
| logistic regression | 0.492 | 32.0% |
| gradient boosting | 0.426 | 24.7% |
| predict-everything baseline | — | 23.3% |

**0.5 is a coin flip.** Both models are at or below it.

**Wave 2 refereed this independently and UPHELD it** (`research/g202_f8_referee.md`). The referee did
not take the leakage check on trust: it recomputed every feature from `bars[:i+1]` with the bar list
physically truncated at the entry bar and diffed cell by cell — **0 of 35 numeric features differ**.
It then tried **22 additional continuous predictors** the original agent never built (level distance
in ATR, bars since break, break→retest gap, OCR age, entry-bar geometry, position in day range,
volume ratio, risk in ATR). **Best arm anywhere: AUC 0.534, p = 0.24 against a within-month
permutation null.** Nothing clears its own null.

Three real defects were recorded and none of them changes the answer: the CV is **4-fold, not the
5-fold the report claims** (only 4 month groups exist); **5 of the 120 labels are days you graded
twice and differently**, 2 of which flip the S bit; and `displacement` — a feature the spec named —
is computed and then silently dropped before the matrix is built. Re-labelling the contested days
and adding displacement back both leave every arm inside its null.

**The honest caveat, stated by the referee:** 120 rows, 28 positives, one fold holding 55% of the
data, a null spanning 0.36–0.62. *"These features do not contain the answer"* is supported.
*"No features could"* is not.

---

## 2. The live lane — bars are back, both credentials are fixed, and the paper broker is armed

| piece | status | what changed |
|---|---|---|
| **bars** | **fixed** | one batched yfinance call per scan. Was **0 of 29** symbols on 09-04; now **29 of 29** on a real dry run. `live_scanner.py`, `c1f9f2d2`, `research/g140_live_batch_fetch.md` |
| **S sizing** | **fixed** | an S now risks **exactly $1,000**, not $800. Sizing keys off your S/A/C tier instead of the retired A+/A/B/C ladder — 657 S trades move from $604.90 to $1,000.00 average budget. `a53c2c93`, `research/g144_s_flat_1r.md` |
| **the push** | **fixed** | the ntfy S push carries expiry, strike, right, OCC symbol, contracts and 1R dollars — 290 bytes on the worked example. `3120092b`. It now also carries the **real** Alpaca order id instead of a hardcoded `None` |
| **daily pass** | **fixed** | `daily_fetch.py` retries once on a short yfinance day and logs PARTIAL instead of dying. Two dead scheduled tasks disabled. `de6675bd` |
| **Alpaca paper** | **WORKING and WIRED** | keys pasted 01:45, `broker/test_alpaca_paper.py` places/reads/cancels. Wave 2 then **wired it into the live path** — see below. `research/g203_alpaca_wired.md` |
| **Tastytrade / HTF bias** | **WORKING** | the header bug (`Token` vs `Bearer`) was the whole story, fixed in `f720ad9e`. Re-verified live in wave 2: `validate_credentials()` returns True, both accounts (`5WI83217`, `5WI77845`) answer. Higher-timeframe bias is back on the live path |
| **Polygon** | **plan-limited, not broken** | see below |

### The paper broker is now wired (W3, commit `61c15363`)

Every fired S — and its matching exit — submits a real **MARKET** order to Alpaca's **paper**
endpoint. `run_daily.ps1` launches the scanner with `--paper --paper-broker alpaca`. The simulated
`PaperBook` still owns the state machine; the Alpaca submission is a parallel best-effort mirror, so
a broker outage cannot corrupt the book. Options go through Alpaca's own contract chain; if options
aren't available it falls back to shares sized so `shares × |entry − stop| = 1R`. One JSON line per
submission lands in `journal/alpaca-paper.jsonl`.

Unit tests: **6/6** (`research/test_alpaca_wiring.py`). Real smoke test: 1 limit order placed and
cancelled on the paper endpoint. Verify gate unchanged and green.

**An independent referee checked all five safety claims and all five held**
(`research/g203_alpaca_referee.md`): the live endpoint is unreachable in code (`paper=True` is a
literal, zero hits for `api.alpaca.markets` in any source file), replay physically cannot submit
(`run_replay()` builds no broker and both submit functions assert `not runner.replay`), exactly one
order per fired S (probe-driven, 7 cases), `run_daily.ps1` is the only launcher, and the diff carries
no credential.

Seven defects are on the record, none of which reaches the live endpoint. **Two are worth a minute of
someone's time:** `live_scanner.py` never calls `load_dotenv()`, so the documented `.env` credential
source is *not* what the live path reads — it works only because both keys also exist at Machine
scope; and `AlpacaBroker()` is constructed unguarded, so a key rotation in `.env` alone would kill the
whole scanner at startup for a day. **One `try/except` around that constructor fixes both.**

One trap worth remembering: wave 1's "Alpaca BLOCKED 401" was a **false alarm** — that shell had
stale `ALPACA_*` variables already set in its environment, and `python-dotenv` never overrides an
already-set variable. The exact trap `g142` itself names, fired on the agent writing `g142`.

### Polygon (W5, `research/g205_polygon_probe.md`) — probed at last

The 403 was never a dead key. The plan is **active**; 8 of 13 tested endpoints return 200. All
aggregates, technical indicators and reference data — everything backtests and homework decks use —
are unrestricted. **403 is confined to real-time options chains, the straddle snapshot, and quotes**
(needs a Stocks Advanced / Options Basic upgrade). Two endpoints 404 (deprecated). **No action
required** unless live intraday trading needs a real-time quote feed.

---

## 3. The funding ladder — no rung is fundable, and it is the edge, not the account

`research/g174_funding_ladder.py` / `.md`. Same fill as the header.

**The candidate streams — now four lanes, not three** (wave 2, W4, commit `ff80372f`):

| stream | days | $/day | mean R | green | **H1 $/day** | **H2 $/day** |
|---|---:|---:|---:|---:|---:|---:|
| index pool QQQ/SPY/IWM, first-of-day | 234 | **−$13.50** | −0.0135 | 12/24 | +$46.15 | **−$68.27** |
| **core 11** (`universe.CORE_SYMBOLS`), first-of-day | 495 | **−$0.34** | −0.0003 | 12/25 | +$34.46 | **−$35.00** |
| full pool, first-of-day | 495 | **+$35.56** | +0.0356 | 13/25 | +$140.29 | **−$69.60** |
| **S-only** (what the live engine now sizes) | 313 | **−$49.07** | −0.0491 | 12/25 | +$19.46 | **−$121.66** |

Two notes on the new core lane. It is **11 symbols, not 10** — SPY was re-added on 2026-08-11, so
"core-10" is a name, not a count. And core and index overlap on QQQ+SPY by construction; the three
lanes are slices, not a partition.

**Every stream loses money in the last twelve months.** That is the whole story. The rungs:

| # | rung | verdict | evidence |
|---|---|---|---|
| 1 | automatic futures prop | **fails** — 13 of 13 firms fail the walk-forward eval; trailing drawdown ends it inside 13–18 trading days. Now **16 of 16** with Lucid priced | P1, `research/g171_futures_proxy_arms.md`, W6 |
| 2 | manual shares prop (Trade The Pool) | **fails** — but the *mechanism* published in wave 1 was wrong, see below | P3, `research/g173_shares_personal_refresh.md`, refuted by `g202_p3_refute{1,2,3}.md` |
| 3 | Vanquish options | **fails** — no risk level from $100 to $1,500 per trade passes, classifier ON or OFF; 0.4% of start dates pass | P2, `research/g172_vanquish_refresh.md` |
| 4 | automatic personal $10k | **operable, and thinner than wave 1 said** — see below | P3/P4, refuted |

### Lucid Trading is finally priced (W6, commit `c3eeb4b4`)

The firm you most want is no longer a blank row. Every primary `lucidtrading.com` page still 403s, so
the specs came from **six independent secondary review sites that agree on every field** — account
sizes, targets, daily loss limits, max drawdowns, costs, consistency rules. Three Lucid Pro tiers
(50K / 100K / 150K, $185–$370) were added to `g171` and re-run.

**Automation is confirmed in writing:** *"Algorithmic systems and automated execution are permitted
across all account types."* Micro contracts verified (MES/MNQ/M2K/MYM at $0.50/side).

**All three Lucid rows fail on trailing drawdown**, for the same reason every other firm does: the
baseline stream is unprofitable in H2. Lucid was never the blocker. The edge is.

### Rung 2's mechanism was wrong, and rung 4 is thinner than published (W1, P3 refuted 3/3)

Three independent refuters attacked P3. The **conclusion survives** — Trade The Pool is not fundable —
but three of its specifics do not:

| P3 said | what actually holds |
|---|---|
| 8 of 8 rows breach the **daily loss limit** inside 0–1.2 months | `pool_series_for_account()` silently **dropped g120's own daily-loss-limit share cap** — 305 of 495 trades on the 25K MAX row risk more than the entire $250 daily limit (max risk taken $1,612). With the cap restored, **0 of 8 fail on the daily limit; all 8 fail on trailing drawdown**, 0.3–1.2 months. Four rows carried the wrong cause of death, three the wrong date |
| "**never** passes on any of 8 rows" | that is **one start date**, the same `window=min(252,n)` failure class that killed P1's headline. Re-run from all 495 start dates, every row passes on **5.7%–32.9%** of them. Still not a funding plan against a $97–$1,100 fee — but "never" is false |
| net after fees **−$97 to −$1,100** | technically true and **vacuous**: on a FAIL, `net_after_cost = −fee` unconditionally. That range *is* Trade The Pool's fee schedule, carrying zero information about the engine |
| personal $10k pays **$35.56/day** at $1,000/trade | reproduces to the cent and is **not buyable**. Risking $1,000 at the book's stop distances needs a mean position of **$299,319 notional**; a $10k account at 4:1 holds $40,000. **99.8% of those trades are un-buyable.** Priced at the account's real buying power: **−$5.75/day** (−$1.24/day with a 1,000-share cap). The 1% arm degrades from $3.56 to **$2.38/day** |
| drawdown **$21,577 = 216% of the account** | wrong denominator. The drawdown ran from a **$48,299 peak to a $26,722 trough = 44.7% of the equity it drew down from**. The markdown also dropped `min_equity_ever` ($3,820) |
| "wiped: no" | order-dependent. **686 of 2,000 shuffles of the same 495 trades (34.3%) wipe the account.** And in H2 the account wipes on 2026-02-03 after 107 trades, then books **140 more trades and −$7,158 on a dead account** — the exact bug g120 fixed for the prop arms and not for this one |

A clean lookahead audit was run and came back **clean**: the arm consumes only day/et/sym/entry/stop/
r/traded, no blacklisted field, the prefix replay is causal, 0 traded rows dropped. The leak was one
class out — capital the account does not have at the moment of entry.

**Rung 4 restated honestly: an automatic personal $10k account, sized to what it can actually buy,
pays between −$5.75 and +$2.38 a day against your $397 bar.**

**What it would take.** For the cheapest futures eval (Apex 50K, $35) to clear half of start dates,
the index stream's mean R must go from −0.0135R to **+0.0565R**. For Trade The Pool 25K FLEX on the
full pool it is +0.0356R → **+0.5456R**. That second number is not a tuning job.

---

## 4. The eye-test — can a model read your S off the chart alone?

**Unanswerable as run. The deck leaked your answer in 100 of 100 cards.**

Wave 2 rendered 100 blind PNG charts from `probe_s_sweep_2026-08-28.jsonl` (34 of them graded S),
cut at the entry bar with levels drawn and no grade or engine text anywhere on the image, then had
Haiku and Sonnet each grade S/A/C/none off the picture plus a rulebook digest.
Scripts: `research/g210_render_cards.py`, `research/g211_eye_test.py`.

### The scores, as measured

| model | precision (S) | recall (S) | exact S/A/C/none agreement | bootstrap 95% band | clears the 30.5% baseline? |
|---|---:|---:|---:|---:|:--|
| Haiku | 38.5% (10 of 26 S-calls) | 29.4% (10 of 34) | 45/100 | [20.0%, 58.3%] | **no** |
| Sonnet | 40.0% (4 of 10 S-calls) | 11.8% (4 of 34) | 45/100 | [10.0%, 72.7%] | **no** |
| his deck's own S rate | 34.0% | — | — | — | — |

Both point estimates land a few points above the baseline; **both bootstrap bands straddle it.**

### Why the numbers are void anyway (`research/g211_referee_leak.md`, `g211_referee_score.md`)

**The leak is total and structural.** The renderer cuts each chart at `notes.min` — *your entry
minute* — when the field exists, and at a blind 10:00 when it does not. That field exists on **34 of
34 cards you graded S and 0 of 66 you refused**. So:

- every S card is cut at 09:34–10:19, **never** 10:00; every refused card is cut at exactly 10:00:00
- the cut is **printed in the title** of every image
- and encoded in the width: refused cards draw **exactly 31 candles**, S cards draw 5–50, and **none
  of them draws 31**. Zero overlap
- a reader that never looks at a single candle and answers *"S if the title doesn't say 10:00"*
  scores **precision 1.000, recall 1.000**

In fairness, **neither model actually exploited it** (Haiku took 10 of 26 S-calls on leaked cards
against 8.8 expected by chance; Sonnet 4 of 10 against 3.4) — so the reported scores are not
inflated. But the experiment cannot separate a model reading price action from one reading a clock,
and 64 of Sonnet's 100 written reasons contain the word "cut". The readers demonstrably saw it.

**Two more findings that would sink it independently:**

- **The 30.5% baseline is the wrong null for this test.** It is graded-day precision on the
  one-trade-a-day pick; this is card-level S-precision on a deck curated to 34.0% S. Against the
  honest 34.0% null, Haiku is p=0.385 and Sonnet p=0.459 — and a trivial **"always say S" reader
  beats both on F1** (0.507 vs 0.333 and 0.182).
- **The reader outputs were silently swapped between two commits and the reader does not agree with
  itself.** All 200 rows have different prose; grades moved on 59 of 100 Haiku cards. Haiku's recall
  moved 0.500 → 0.294, a 20.6pp swing, against a claimed effect of 4.5pp. **The measurement is
  noisier than the thing being measured**, and no committed script opens a PNG, calls a model and
  writes those rows — no model id, no prompt, no digest hash. That is how a full-dataset swap went
  unnoticed.

### What it means

**The conclusion "this does not justify building a vision classifier" happens to be right, but it was
reached by luck, not by the comparison that was made.** The real finding is a repeatable recipe for
the *next* attempt: cut every card at a **fixed** clock time regardless of grade, strip symbol and
date from the image and filename, score against the **deck's own base rate**, and commit the harness
that calls the model. Until that runs, "can a model see your S on the chart" is **still open** — and
it is the one question the ML ceiling result actively points at, because the pixels are the feature
family the tabular features are not.

---

## 5. Mid-candle entry — the referee verdict

**F9 is REFUTED. R2 stands unamended. No flag ships.** (`research/g201_mid_candle_referee.md`)

Wave 1 left the single highest-value open conflict on the board: F9 reported a resting limit at 25%
of the signal bar's range paying **$100/day** against the shipped close's $34/day, on 86% of
candidates — while the vault carried a settled 2026-09-03 ruling that mid-candle entry pays **0.2458R
less** than the close. One of them had to be wrong.

Three independent referees each reproduced F9's arithmetic **to the dollar** (one regenerated its JSON
byte-identically) and each found the same defect from a different angle:

| arm | F9's published $/day | H2 | honest $/day | H2 |
|---|---:|---:|---:|---:|
| shipped CLOSE | $34 | −$68 | $34–37 | −$65 to −$68 |
| MID25 (F9's headline) | **$100** | +$35 | **$27–39** | **−$64 to −$68** |
| MID50 | $90 | +$1 | $6 | −$68 |
| MID75 | −$47 | −$116 | −$8 | −$50 |

**What was actually wrong — two harness leaks, not the price:**

1. **The day-pick moved.** F9's one-trade-a-day picker walks a day's candidates and takes the first
   one that *has a priced result*. A mid arm has no result exactly when its limit never traded before
   11:00 — a fact about the future of that session. So the mid arm **silently traded a different
   candidate than the close arm it was compared against on 129 of 498 sessions (26%)**. It is also
   not implementable: the abandoned candidate's order is still working to the cutoff, so on those days
   the "one trade a day" rule is holding two positions. Hold the day's pick fixed and $100/day becomes
   **$39/day** against a like-for-like close control of $37.
2. **The fill bar is never risk-managed.** `run_trade` manages bars from `fill_i+1`, so a disaster
   stop already touched inside the fill bar is invisible. **944 of 7,609 MID25 fills (12.4%)** are in
   that state, worth **−$38/day**.

Fix both and MID25 pays **$27/day, below the shipped close**, with a paired 95% interval of
**[−$112, +$95]** straddling zero.

**Three more nails, any one sufficient:**

- **A placebo fires.** A limit resting at exactly the signal bar's own close — *zero* mid-candle
  depth — pays **$105/day**, more than MID25. With the day-pick held fixed the whole depth ladder runs
  backwards: MID00 $79 > MID25 $39 > MID50 $6. **The variable F9 names has the wrong sign.**
- **Multiplicity.** The headline is the max of three arms chosen on the combined number. Under a
  joint sign-flip null, **the best of three beats $65.8/day 38.9% of the time.** The entry-fill axis
  on this same book has now been swept five times.
- **One session is 627% of what's left.** MID25's fixed-pick edge over the close is **+$957 across two
  years** ($2/day), and 2024-09-06 alone is 627% of it.

**On the "one of these must be wrong" framing:** it was a false dilemma. The two measured different
things (midpoint vs close-minus-25%-of-range; 12 bars vs the 11:00 cutoff; blind 2R vs the shipped
ladder; 925 signals vs 8,227 candidates; paired R vs unpaired $/day). But decisively, **MID50 — the
depth closest to R2's midpoint — pays −$32/day against the close on the matched walk**, so F9's own
harness reproduces R2's sign. The vault lines in `omen-blockers.md:95` and
`omen-brief-2026-09-03.md:45` are **correct as written** and have been re-closed.

One reporting bug in F9 for the record: its category table's ALL row sums to 8,188 against 8,227
candidates — never-returns is printed as 578 and is actually 617. The 86.3% mid-fillable headline
reproduces exactly and is unaffected.

---

## 6. The bug sweep and the test suite

`research/g180_bugs_*.json` → `g181_bugs_confirmed.md` → `g182_bugs_fixed.md`. **71 raw findings, 15
confirmed, 15 fixed.**

**The ones that were actually costing you money or data:**

- **B-10** — `run_daily.ps1` pulled and then ran the scanner with no syntax check. On 2026-09-03
  `omen_bot.py` was unparseable and it silently killed the whole daily pass. Fixed `bc023fd4`.
- **B-15** — three scheduled tasks enabled and returning failure, **including `OmenDailyHomework`** —
  the instrument that makes your deck. Fixed `29aa7120`.
- **B-14** — five homework decks swallowed by `.gitignore`, untracked. The trap in `CLAUDE.md` fired a
  third time. Fixed `0e186706`.
- **B-06** — the live contract sizer assumed delta 0.5 against a measured 0.42, **under-sizing every
  trade by 16%**. Fixed `10fc20f4`.
- **B-03** — `HTF_BIAS_VETO` vetoed 42.2% of backtest rows and **zero live signals**, because the
  yfinance fallback returns `bias=None`. Fixed `b5b5dc5a`.

### B-08 is closed (W7, commit `d72bceee`)

All 14 failing test files are triaged: **11 fixed, 3 retired, 0 left unactioned.** No production
module was edited and `CLAUDE.md`'s `verify:` line is unchanged.
**`research/run_tests.py` now runs the canonical set — 66 of 67 pass** (the one failure is a live race
against other agents writing report files) — and it is wired into `daily_run.cmd`, log-only and
non-fatal.

**The pattern worth naming:** every one of the 14 broke because a *shipped default* changed and
several tests were still exercising the removed mechanism directly — the 2026-08-30 always-CLOSE fill
refactor, 2026-09-02's `RETEST_REQUIRED=ON`, and 2026-09-03's −1R hard floor. Three changes, fourteen
red tests, no one noticing because the gate only ran two files.

**One substantive finding flagged and not fixed** (it would need production changes):
`ENABLE_STRUCTURAL_RISK_FLOOR`'s entire empirical justification — g12's "six dropped marks" — depended
on the now-dead bar-extreme clamp fill. **Its off and on arms are currently identical on every
documented example.** That is another "rule unreachable in code" in the making.

**Still partial:** B-01 and B-02 (the two grade ladders still disagree in places), B-07 (the
premium-risk floor still hardcodes ×0.5).

---

## 7. What was refuted — write these down as refuted

Sixteen adversarial passes ran across the two waves. Ten overturned something:

| claim | wave | verdict | why |
|---|---|---|---|
| all 8 F5 "surviving" rules | 1 | **REFUTED 3/3 each** | no-ops, a broken OR in the survivor gate, penny-exact fills, in-sample threshold picks |
| F7's "S classifier pays +$13.51/day" | 1 | **REFUTED 3/3** | one day is 50% of the gain; H2 was used to select, not validate; ~5.6 noise winners expected from 25 tries |
| **F9's "mid-candle MID25 pays $100/day"** | **2** | **REFUTED 3/3** | the day-pick silently moved on 26% of sessions; the fill bar is never risk-managed; a **zero-depth placebo pays more**; honest number $27/day, *below* the close |
| **P3's "TTP breaches the daily loss limit, 8/8, never passes"** | **2** | **REFUTED 3/3** | the daily-loss-limit share cap was dropped, so the arm was failed for a breach its own sizing guaranteed; with it restored all 8 fail on *trailing drawdown*. "Never" is one start date — all-starts pass rate is 5.7–32.9% |
| **P3's "personal $10k pays $35.56/day"** | **2** | **REFUTED** | 99.8% of those trades are un-buyable at 4:1; priced honestly it is **−$5.75/day**. "216% of account" is the wrong denominator (44.7% of peak). 34.3% of trade orderings wipe the account |
| **W9's vision eye-test** | **2** | **REFUTED 2/2** | the deck leaks your grade via the cut time in 100 of 100 cards; a trivial clock-reader scores 1.000/1.000. Wrong null, and the reader data was swapped between commits |
| O1's "best grid arm pays $11.2/day, VETO_1D is the one lever" | 1 | **REFUTED 2/3** | `spy_trend` compares **today's closing price** to an SMA containing it — a read 5–6 hours past entry. The *causal* version is stronger ($17.8/day), so the lever is real but every published cell is wrong |
| P1's "0.0% rolling-252 pass rate for every futures firm" | 1 | **REFUTED 3/3** | `window = min(252, n)` with n=234 evaluates **exactly one window**. Corrected all-starts rates are **12%–27%** |
| L1's "replay could not be verified" | 1 | **REFUTED** | the replay runs fine (23 signals, 2 S setups on 2026-09-04) |
| F9's category table | 2 | **arithmetic error** | ALL row sums to 8,188 not 8,227; never-returns is 617, printed as 578 |
| **F8's ML ceiling (AUC at chance)** | **2** | **UPHELD** | leakage tested empirically (0 of 35 features differ under truncation), 22 new features tried, best arm AUC 0.534 at p=0.24 |
| **O2's four new flags** | **2** | **UPHELD** | every changed line is a flag read; all four defaults resolve to pre-O2 behaviour; deployed `.env` sets none of them; 27/27 tests pass |
| **W3's Alpaca wiring safety** | **2** | **UPHELD 5/5** | live endpoint unreachable in code, replay cannot submit, one order per fired S, one launcher, no credential in the diff |
| O1's own conclusion ("ship nothing") | 1 | **upheld** | corrected for the lookahead, still no arm positive in both halves |
| P2 (Vanquish never passes) | 1 | **upheld 2/3** | survives a 500-level continuum sweep and a corrected rolling window |
| P4 (the ladder table) | 1 | **upheld** | every cell traced to a committed source and reproduced byte-identically |

**Direction matters.** The refutations of P1, P3 and O1 make those arms look *better* on paper, and
they still fail. The refutations of the F5/F7 rules and F9 delete the edge entirely.

---

## 8. Still yours — one email, 5 minutes

**1. Alpaca paper keys — ✅ DONE.** Keys pasted 01:45, verified, and as of wave 2 the live path
submits real paper orders through them. Nothing left to do.

**2. Tastytrade OAuth — ✅ DONE.** It was a code bug (`Token` vs `Bearer`), not your grant.
Re-verified live in wave 2: `validate_credentials()` returns True, both accounts answer. The
higher-timeframe bias is back on the live path. **You never had to touch the dashboard.**

**3. Vanquish support email — 5 minutes. The only one left.** Unchanged from 09-03: ask about the
0DTE policy and the single-name list. Still unanswered, and Vanquish is the only options rung on the
ladder.
**Done-signal:** the email is in your sent folder.

**Optional, 2 minutes — reset the Alpaca paper account.** The paper account still carries whatever
the smoke tests left in it. Resetting the balance from the Alpaca dashboard before the next session
gives the newly-wired paper broker a clean equity curve to measure from, which is the only way the
live-fire count in §1 becomes readable.
**Done-signal:** paper equity reads its starting balance.

Nothing else needs you. **No grading session is requested this morning** — the night added zero
judged symbol-days and no mark file was touched or read for writing.

---

## 9. Completeness critic — what the two waves could not do

### Modalities that were never run properly

- **Chart images were finally read — and the test was void.** 100 PNGs were rendered and graded by
  two models, but the deck leaked your answer in every card (§4). *"Can a model see your S on the
  chart"* is still open, and the fix is now a known recipe.
- **No video was looked at.** Your call named *"Scarface/JW videos and trade images and reviews"*.
  F4 searched the **text** harvest only. If the rules live in the videos, neither wave could have
  found them.
- **No new marks were collected.** The scarce input did not grow. 25 rules were mined from prose you
  wrote weeks ago, and the ML ceiling says those prose-derived features contain no signal — which
  points at *more marks* or *a different feature family*, not at more mining of the same text.
- **Still no live-fire count**, so "1–3 fires a day" remains unmeasured. It starts accumulating on the
  next session now that the paper broker submits.

### Claims that are still unverified

- **P1's futures overlap check rests on 2 matched signal pairs** from a simplified detector that is
  not the shipped engine, on ES bars spanning ~23 hours against SPY bars spanning 6.5. It establishes
  nothing, and nobody attacked it.
- **Lucid's specs are secondary.** Six review sites agree on every field and every primary page 403s.
  The automation permission is the one quote worth having, and it is not from Lucid's own server.
- **Nobody has re-refereed the corrected numbers.** The honest MID25 ($27/day), the capped TTP rows,
  and the buying-power-constrained personal arm are all first-pass results from the refuters
  themselves.
- **`ENABLE_STRUCTURAL_RISK_FLOOR` may be a dead branch** (§6) — flagged, unmeasured.
- **The eye-test reader harness does not exist.** No committed script calls a model on a PNG. Two
  different reader datasets are in git history and they disagree on 59 of 100 cards.

### The vault is now current (W8, tradingbot `ec50577b`, vault `7584ef1`)

All 20 stale lines named in v1's §7 now carry dated 2026-09-05 corrections across **9 vault files**
(`omen-next-session.md`, `OMEN.md`, `omen-blockers.md`, `omen-x-board.md`, `omen-2y-backtest.md`,
`omen-brief-2026-09-03.md`). **Nothing was deleted or un-checked** — corrections were appended, in
line with never losing a record. The Tastytrade human task is marked done with a re-verified reason.

`CLAUDE.md` now carries the precision footnote: **the lane bar is 30.5% graded-day precision on the
one-trade-a-day pick**; 39.5% stays as the secondary candidate-level read.

One correction to W8's own framing: it flagged the mid-candle conflict as "reopened and unrefereed"
in every note that cited it, because the referee had not landed yet. **It has now — R2 stands, and
those lines were right the first time.**

---

## 10. Where this leaves the lane

The lane in `CLAUDE.md` closes on "an S classifier that fires 1–3 times a day, lifts precision above
the bar, keeps recall, and carries one-trade-a-day past $397/day with every month green."

**The night moved it zero.** Precision is unchanged at 30.5%. The best honest arm on the board is the
unchanged baseline, $33.93/day full pool, and its second half is **−$67.85/day**.

What the two waves actually bought you:

1. **The ML ceiling is at chance, and it survived a real attack.** Thirty-five features from the
   rulebook plus 22 the referee invented, and the best arm anywhere is AUC 0.534 at p=0.24. **More
   rule-mining over the same text will not help.** This is now the most load-bearing result on the
   board.
2. **Every headline number that looked like an edge was a measurement artifact.** F9's $100/day was a
   moving day-pick and an unmanaged fill bar. P3's daily-loss-limit failure was its own dropped share
   cap. P1's 0.0% was one window. The engine did not get worse; the rulers got honest, again.
3. **The lane is now instrumented end to end.** Bars fetch, sizing is flat $1R on your own ladder,
   the HTF bias is back, the paper broker submits real orders, the test suite runs in one command,
   and the vault matches the measurements. **Nothing measured tonight is blocked on infrastructure
   any more.** The next thing that moves this lane has to be an actual edge.

**The two open questions worth a day, in order.** First: **can a model read your S off a chart?** —
the eye-test is void, not answered, and it is the only untried feature family after the ML ceiling
result. Second: **more marks.** Everything on the board says the scarce input is the constraint, and
it is the one thing no agent can manufacture overnight.

**Next action, under two minutes:** run `python research/run_tests.py`. It is the first time the
whole canonical suite has been runnable in one command; 66 of 67 pass, and it tells you in under a
minute whether tonight's eleven test fixes hold on your box before the paper broker fires live on
Monday's open.

---

*Artifact with every table: `research/omen-9-0-report.html` (static, opens on a phone), also at
`Desktop/AI-Outputs/omen-daily/omen-9-0-report-2026-09-05.html`. Built by
`research/build_report_9_0.py` (rows R1 and W10).*
