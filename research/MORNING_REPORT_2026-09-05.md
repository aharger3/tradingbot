# OMEN 9.0 — morning report, 2026-09-05

**One sentence:** the night mined 25 candidate rules out of your own marks, measured every one of
them, and **not a single one survived being attacked** — so there is still no S classifier, the
live lane is breathing again but two credentials are dead, and **no funding rung is fundable**,
because all three candidate streams lose money in the last twelve months.

Base commit `f8740f80`. Everything below names its fill and its script. Unless a row says
otherwise: entry = **signal bar CLOSE**, stops via `stop_rule.stop_fill_price()`, size-gated on
`signal_runner.min_risk_floor`, **1R = $1,000**, book `research/bt2y_trades_retest_on.json`
(RETEST_REQUIRED=1, 498 sessions 2024-09-03 → 2026-09-02), one-trade-a-day unit
`research/omen_metrics.first_of_day_arm`. **H1** = before 2025-09-01, **H2** = 2025-09-01 onward.

---

## 1. THE ANSWER — is there an S classifier?

**No. Not one rule out of twenty-five survived.**

The question was: does a classifier exist that fires 1–3 times a day, holds precision above 39.5%,
keeps S recall, and pays past $397/day with every month green.

| stage | result |
|---|---|
| comments harvested from your marks | 2,675 rows, **1,521 with prose**, 896 over 40 characters (`research/g150_marks_comments.md`) |
| candidate rules mined from that prose | **25** (`research/g152_rule_candidates.md`) |
| measured on the honest book | 25 of 25 (`research/g154_rule_*.py`, one script per rule) |
| passed the F5 survivor bar | 8 |
| **still standing after three independent refuters each** | **0** (`research/g155_rule_verdicts.md`) |

Eight rules looked like winners. Three separate opus agents attacked each one — for lookahead, for
multiplicity, and by re-running the script — and all eight went down 3-for-3. The failures were not
close calls:

- **`stop-placement-routed`** (+$13.00/day) was a **no-op**. On 7,302 of 7,302 break-and-retest
  candidates the "routed" stop already equals the shipped stop. Routing the stop to *itself* through
  the same replay reproduces the entire gain to the cent. The $13 was a different exit model, not a
  different stop.
- **`entry-earlier-satisfiable-bar`** was flagged a survivor by a **bug in the survivor test**:
  precision was OR'd into both half-conditions, so a single precision number satisfied "H1 improves"
  and "H2 improves" simultaneously. Its actual H1 money fell **−$145.33/day**.
- **`scale-before-the-level`** (+$43/day) rests on **7 fills where the bar's high equals the limit
  price to the penny and goes no further**. Requiring price to trade one cent through the limit
  kills it.
- **`exhausted-overextended`**: the shipped rule changed **0 of 498 day-picks**. The reported gain
  came from a re-parameterised threshold picked in-sample, worth +$1.31/day against a ±$104 bootstrap
  interval.

### What shipped anyway, and what it does

`signal_runner.py` now carries **`S_CLASSIFIER`, default OFF** (commit `eaa62705`,
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

**The `>39.5%` target is not apples-to-apples and should be restated.** The 39.5% in `CLAUDE.md`
is candidate-level precision across the whole fired pool. Tonight's 30.5% is graded-day precision on
the one-trade-a-day pick (18 of 59 graded days). Different denominators. The verdict — "the
classifier moved precision by exactly zero" — is unaffected, because both arms score 18/59 with the
same numerator *and* the same denominator.

**Fires/day was never answered.** The measurement unit picks exactly one candidate per day by
construction, so "1–3 fires a day" cannot be read off it. It needs a live-fire count, not a
selection arm.

### The ML ceiling says there is nothing to find in these features

`research/g157_ml_ceiling.py`, 120 judged day-cards (28 S, 23.3% base rate), logistic regression and
gradient boosting, 5-fold CV grouped by month:

| model | AUC | precision at the rule engine's recall |
|---|---:|---:|
| logistic regression | 0.492 | 32.0% |
| gradient boosting | 0.426 | 24.7% |
| predict-everything baseline | — | 23.3% |

**0.5 is a coin flip.** Both models are at or below it. On the eight downgrade variables plus level
type, setup, tier, displacement, HTF bias and time-of-first-candidate, there is **no learnable S
signal at all**. That is the strongest single result of the night: the ceiling is not "the rules are
badly written", it is "these features do not contain the answer". *(Caveat: 120 rows, 4 CV groups.
Small.)*

---

## 2. The live lane — bars are back, two credentials are dead

| piece | status | what changed |
|---|---|---|
| **bars** | **fixed** | one batched yfinance call per scan. Was **0 of 29** symbols on 09-04; now **29 of 29** on a real dry run. `live_scanner.py`, commit `c1f9f2d2`, `research/g140_live_batch_fetch.md` |
| **S sizing** | **fixed** | an S now risks **exactly $1,000**, not $800. Sizing keys off your S/A/C tier instead of the retired A+/A/B/C ladder. Over the 2-year book that is 657 S trades moving from $604.90 to $1,000.00 average budget. Commit `a53c2c93`, `research/g144_s_flat_1r.md` |
| **the push** | **fixed** | the ntfy S push now carries expiry, strike, right, OCC symbol, contracts and 1R dollars — 290 bytes on the worked example (AMD 10:13, entry $472.18 / stop $471.06 / target $474.96, 19 contracts). Commit `3120092b` |
| **daily pass** | **fixed** | `daily_fetch.py` retries once on a short yfinance day and logs PARTIAL instead of dying. Two dead scheduled tasks disabled. Commit `de6675bd` |
| **Alpaca paper** | **BLOCKED** | both key pairs in `.env` return **401** from Alpaca's own API, confirmed outside the SDK. The adapter `broker/alpaca.py` is built and untested past the auth call. `research/g142_alpaca_paper.md` |
| **Tastytrade / HTF bias** | **BLOCKED — but probably fixable in code, see below** | live runs still have no higher-timeframe bias |

### The Tastytrade blocker is probably already dead — check before you touch the dashboard

Two agents worked this and their reports disagree. The timeline settles it:

- **01:05** — L2 declared it blocked: the OAuth grant returns a token that 401s on every real
  endpoint (`research/g141_tastytrade_unblock.md`).
- **01:48** — commit `f720ad9e` landed the actual bug: `_headers()` was sending
  `Authorization: Token <t>` for OAuth-issued tokens, which need `Bearer`. Verified live by the L1
  agent — **same token, 401 with `Token`, 200 with `Bearer`**.

**Nobody has re-run the credential check since that fix landed.** So the "recreate the OAuth grant"
human task may be unnecessary. See §6, task 2.

---

## 3. The funding ladder — no rung is fundable, and it is the edge, not the account

`research/g174_funding_ladder.py` / `research/g174_funding_ladder.md`. Same fill as the header.

**The three candidate streams:**

| stream | days | $/day | mean R | green | **H1 $/day** | **H2 $/day** |
|---|---:|---:|---:|---:|---:|---:|
| index pool QQQ/SPY/IWM, first-of-day | 234 | **−$13.50** | −0.0135 | 12/24 | +$46.15 | **−$68.27** |
| full pool, first-of-day | 495 | **+$35.56** | +0.0356 | 13/25 | +$140.29 | **−$69.60** |
| **S-only** (what the live engine now sizes) | 313 | **−$49.07** | −0.0491 | 12/25 | +$19.46 | **−$121.66** |

**Every stream loses money in the last twelve months.** That is the whole story. The rungs:

| # | rung | verdict | evidence |
|---|---|---|---|
| 1 | automatic futures prop | **fails** — 13 of 13 firms fail the walk-forward eval; trailing drawdown ends it inside 13–18 trading days | P1, `research/g171_futures_proxy_arms.md` |
| 2 | manual shares prop (Trade The Pool) | **fails** — 8 of 8 account/plan rows breach the daily loss limit inside 0–1.2 months; net after fees −$97 to −$1,100 | P3, `research/g173_shares_personal_refresh.md` |
| 3 | Vanquish options | **fails** — no risk level from $100 to $1,500 per trade passes, classifier ON or OFF; 0.4% of start dates pass | P2, `research/g172_vanquish_refresh.md` |
| 4 | automatic personal $10k | **operable, not fundable** — at a professional 1% risk it pays **$3.56/day** against your **$397/day** bar. At the book's native $1,000/trade it pays $35.56/day and draws down **$21,577 = 216% of the account** | P3/P4 |

**What it would take.** For the cheapest futures eval (Apex 50K, $35) to clear half of start dates,
the index stream's mean R has to go from −0.0135R to **+0.0565R** — a +0.07R per-trade swing. For
Trade The Pool 25K FLEX on the full pool it is +0.0356R → **+0.5456R**. That second number is not a
tuning job.

**Lucid Trading — the firm you most want — has never been priced.** It is the only firm on the
ladder with an explicit written automation permission, and **every primary page returns 403**
(`research/g170_futures_firms_2026-09.md`). Trade The Pool bans automation in writing (T&C §11), so
rung 2 is manual by rule. Vanquish has no automation clause either way (unverified).

---

## 4. The bug sweep — 71 found, 15 confirmed, 15 fixed

`research/g180_bugs_*.json` → `research/g181_bugs_confirmed.md` → `research/g182_bugs_fixed.md`.
Eleven are full fixes with a test; four are partial (root cause committed, test coverage incomplete).

**The ones that were actually costing you money or data:**

- **B-10** — `run_daily.ps1` pulled and then ran the scanner with no syntax check. On 2026-09-03
  `omen_bot.py` was unparseable and it silently killed the whole daily pass. Fixed `bc023fd4`.
- **B-15** — three scheduled tasks were enabled and returning failure, **including
  `OmenDailyHomework`** — the instrument that makes your deck. Fixed `29aa7120`.
- **B-14** — five homework decks were being swallowed by `.gitignore` and were untracked. The trap
  in `CLAUDE.md` fired a third time. Fixed `0e186706`.
- **B-06** — the live contract sizer assumed delta 0.5 against a measured 0.42, **under-sizing every
  trade by 16%**. Fixed `10fc20f4`.
- **B-03** — `HTF_BIAS_VETO` vetoes 42.2% of backtest rows and **zero live signals**, because the
  yfinance fallback returns `bias=None`. Fixed `b5b5dc5a`.
- **B-11 / B-12 / B-13** — three scripts pointing at paths that do not exist
  (`run_weekly_digest.ps1`, a doubled `aharg\aharg\`, a missing `Desktop\`).

**Still partial:** B-01 and B-02 (the two grade ladders still disagree in places), B-07 (the
premium-risk floor still hardcodes ×0.5), B-08 (**14 test files fail and the verify gate only runs
2** — `test_universe_single_source.py` is not actually run despite `CLAUDE.md` promising it is).

---

## 5. What was refuted — write these down as refuted

Ten adversarial passes ran tonight. Six overturned something:

| claim | verdict | why |
|---|---|---|
| all 8 F5 "surviving" rules | **REFUTED 3/3 each** | no-ops, a broken OR in the survivor gate, penny-exact fills, in-sample threshold picks |
| F7's "S classifier pays +$13.51/day" | **REFUTED 3/3** | one day is 50% of the gain; H2 was used to select, not validate; ~5.6 noise winners expected from 25 tries |
| O1's "best grid arm pays $11.2/day, VETO_1D is the one lever" | **REFUTED 2/3** | `spy_trend` compares **today's closing price** to an SMA containing it — a read 5–6 hours past the entry. The repo already blacklists that exact field. The *causal* version is stronger ($17.8/day), so the lever is real but every published cell is wrong |
| P1's "0.0% rolling-252 pass rate for every futures firm" | **REFUTED 3/3** | `window = min(252, n)` with n=234 evaluates **exactly one window**. Corrected all-starts pass rates are **12%–27%**, not 0% |
| L1's "replay could not be verified" | **REFUTED** | the replay runs fine (23 signals, 2 S setups on 2026-09-04). The code fix is real; the report's excuse was false |
| O1's own conclusion ("ship nothing") | **upheld** | corrected for the lookahead, still no arm positive in both halves |
| P2 (Vanquish never passes) | **upheld 2/3** | survives a 500-level continuum sweep and a corrected rolling window |
| P4 (the ladder table) | **upheld** | every cell traced to a committed source and reproduced byte-identically |

**Direction matters.** The refutations of P1 and O1 make those arms look *better*, not worse — and
they still fail. The refutations of the F5/F7 rules delete the edge entirely.

---

## 6. Still yours — three things, 20 minutes total

**1. Alpaca paper keys — 5 minutes.** Both pairs in `.env` are dead (401 from Alpaca's own API, not
an adapter bug). Go to the Alpaca dashboard, regenerate a **paper** API key/secret, paste over
`ALPACA_PAPER_KEY` / `ALPACA_PAPER_SECRET` in `.env`.
**Done-signal:** `python broker/test_alpaca_paper.py` exits 0.

**2. Tastytrade — 2 minutes of *checking* first, 10 minutes of clicking only if it fails.** Do not
go to the dashboard yet. The header bug was fixed 43 minutes after the agent declared this blocked,
and nobody re-tested. Run:
`python -c "import tastytrade_feed as t; print(t.TastytradeFeed().validate_credentials())"`
If it prints OK, this blocker is gone and you skip the rest. If it still 401s, then
`research/g141_tastytrade_unblock.md` has the exact my.tastytrade.com clicks to recreate the
personal OAuth grant with account + streaming scope.
**Done-signal:** the same command prints OK.

**3. Vanquish support email — 5 minutes.** Unchanged from 09-03: 0DTE policy and the single-name
list. Still unanswered, and Vanquish is the only options rung on the ladder.

Nothing else needs you. **No grading session is requested this morning** — the night added zero
judged symbol-days and no mark file was touched or read for writing.

---

## 7. Completeness critic — what the night could not do

### Modalities that were never run

- **No image and no video was looked at.** Your call named *"Scarface/JW videos and trade images and
  reviews"*. F4 searched the **text** harvest only, and tagged 25 candidates
  10 confirmed / 4 contradicted / 11 silent. **Zero chart images were read by any agent.** If the
  rules live in the pictures, tonight could not have found them.
- **No new marks were collected.** The scarce input did not grow. 25 rules were mined from prose you
  wrote weeks ago, and the ML result says those prose-derived features contain no signal — which
  points at *more marks* or *a different feature family*, not at more mining of the same text.
- **The Polygon probe named in row L1 was never run.** The 403 status is unretested.
- **No live-fire count exists**, so "1–3 fires a day" is still unmeasured (see §1).

### Claims that are unverified

- **F9 (mid-candle) had no adversarial pass**, and it directly contradicts a settled ruling. F9
  reports MID25 at **$100/day** and MID50 at **$90/day** against the CLOSE arm's $34/day, with
  **7,096 of 8,227 candidates (86%) mid-fillable** (`research/g158_mid_candle_arms.py`). The vault
  says the opposite (see below). **One of these two is wrong and nobody refereed it.** Highest-value
  single follow-up available.
- **F8's leakage check was done by the agent that built it**, not by an independent refuter as the
  spec required.
- **P3 (Trade The Pool / personal) got no adversarial pass.** Given that P1's headline statistic in
  the same phase was a one-window bug, P3's numbers should be treated as unrefereed.
- **O2 shipped four new flags with no adversarial pass.** Low risk — every default reproduces
  today's behaviour exactly, and 24/24 tests pass — but it is untested by an attacker.
- **P1's futures overlap check rests on 2 matched signal pairs** from a simplified detector that is
  not the shipped engine, on ES bars spanning ~23 hours against SPY bars spanning 6.5. It establishes
  nothing.
- **B-08 stands: 14 test files fail** and the verify gate runs 2 of them. Every "verify green"
  claim in this report means those two passed.

### Vault notes that now contradict a result — retire or correct these

*Listed, not edited. The vault was not touched tonight.*

| note | line | what it says | what tonight says |
|---|---|---|---|
| `Projects/omen-next-session.md` | 226 | *"Alpaca — cleared. Paper account ACTIVE, keys in `.env`, both name pairs."* | **both pairs 401.** Dead. |
| `Projects/OMEN.md` | 272–275 | *"Alpaca keys are dead weight … revoke the Alpaca pair outright."* | reversed by your own call — **Alpaca paper is the chosen paper venue** (row L3). Do not revoke. |
| `Projects/omen-blockers.md` | 48, 120–121, 266–267 | *"Still open: `GRADE_SIZE_PCT` is still keyed on the retired A+/A/B/C ladder … the blocker on running this live with real money stands"* | **closed by L5** (`a53c2c93`). Live S sizing is flat $1,000 off your S/A/C tier. |
| `Projects/omen-blockers.md` · `Projects/omen-brief-2026-09-03.md` | 95 · 45 | *"mid-candle … never happens for ~20% of signals and on the 80% where it is reachable it pays 0.2458R LESS than the close"* / *"R2 mid-candle entry … **Dead**"* | **F9 says the opposite** — 86% fillable and MID25/MID50 pay *more*. Unrefereed conflict; reopened until someone referees it. |
| `Projects/omen-brief-2026-09-03.md` | 16 | *"A $50k prop eval passes on the full-book path … 38.7% of rolling start dates"* | superseded — **no rung passes** on tonight's honest measurement; corrected futures all-starts rates are 12–27% and every firm fails the walk-forward. |
| `Projects/omen-blockers.md` 418 · `Projects/omen-x-board.md` 142 · `Projects/omen-2y-backtest.md` 175 · `Projects/omen-brief-2026-09-03.md` 38, 67 | the **−1.25R floor** as a live rule / an open question | **there is no −1.25R clamp.** Max loss is −1R hard on the shipped path; the floor is fiction and belongs only to `exit_lab.py`. Confirmed again tonight by `test_runner_stop.py` (70 checks). |
| `Projects/omen-next-session.md` 40–58, 133 · `Projects/omen-x-board.md` 193, 322 | the live gate is `grade == "A+"` and must be replaced | already replaced 2026-09-03, and **L5 finished the job tonight**. Stale. |
| `Projects/OMEN.md` | 679 | *"B is the only profitable tier (+$62,451, 36.6%, 693 trades)"* | a **pre-honest-fill** dollar figure. Kill it — it does not name an obtainable fill. |
| `Projects/omen-2y-backtest.md` | 88, 146 | *"A+ fired 7 times in 76,019 signals"* | different denominator from `CLAUDE.md`'s "twice in two years"; both describe a ladder that no longer gates sizing. |

### One number in `CLAUDE.md` needs a footnote

`CLAUDE.md` sets the precision bar at **39.5%** (candidate-level, whole fired pool). Every
measurement tonight reports **graded-day precision on the one-trade-a-day pick**, whose baseline is
**30.5%**. Both are honest; they are not the same quantity, and the spec's `>39.5%` target was
therefore never testable as written. Pick one definition and put it in `CLAUDE.md`.

---

## 8. Where this leaves the lane

The lane in `CLAUDE.md` closes on "an S classifier that fires 1–3 times a day, lifts precision above
39.5%, keeps recall, and carries one-trade-a-day past $397/day with every month green."

**Tonight moved it zero.** Precision is unchanged at 30.5%. The best honest arm on the board is the
unchanged baseline, $33.93/day full pool, and its second half is **−$67.85/day**.

Two facts are worth more than the twenty-five dead rules:

1. **The ML ceiling is at chance.** The features you and the engine currently describe a setup with
   do not separate your S days from your not-S days. More rule-mining over the same text will not
   help.
2. **F9's mid-candle arms.** $100/day against $34/day, on 86% of candidates, from a fill that is
   strictly after the signal bar — and it has never been attacked. It contradicts a ruling already
   in the vault. **That referee is the highest-value hour available today**, because if F9 is right
   it is a bigger number than anything the classifier work produced, and if it is wrong the vault is
   already correct and nothing is lost.

**Next action, under two minutes:** run
`python -c "import tastytrade_feed as t; print(t.TastytradeFeed().validate_credentials())"`
and find out whether you owe Tastytrade ten minutes or nothing at all.

---

*Artifact with every table and chart: `research/omen-9-0-report.html` (18.3 KB, static, opens on a
phone), also at `Desktop/AI-Outputs/omen-daily/omen-9-0-report-2026-09-05.html`. Built by
`research/build_report_9_0.py`, row R1.*
