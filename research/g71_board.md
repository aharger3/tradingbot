# OMEN 7.1 — the board

Everything below was re-measured today on the book sitting on disk right now:
`research/bt2y_trades.json`, built 2026-08-29 03:14, 500 sessions from 2024-08-21 to
2026-08-21, 76,019 setups looked at, 2,437 trades taken, 1R = $1,000
(`research/g71_board_check.py`).

---

## 1. THE MONEY ANSWER

**Today, one trade a day, you make about $305 a day — $6,400 a month.**

**The one change worth the most money doubles that to $611 a day, $12,800 a month, and it
is not a strategy change. It is that live sells the whole position at 2R and the backtest
does not.**

| | per day | per month (21 days) | 2-year total |
|---|---:|---:|---:|
| **What live actually does now** — whole position out at 2R | **$305** | **$6,409** | $151,374 |
| **What the backtest does** — sell half at the high, let the rest run | **$611** | **$12,841** | $303,289 |

*(both rows: `research/g71_board_check.py`, re-derived from scratch today; matches
`research/g71_rtarget_model.py` and `research/g71_firsts_policy.py` independently)*

Why the gap is exactly that big: **94 of your 496 one-a-day trades (19%) ran past 2R, and
those 94 trades carry 50.1% of every dollar the strategy makes** (`research/g71_board_check.py`).
Live books zero of it. The live system's only exit is a fixed 2R target in the options
sizer, and the paper trader closes the *whole* position the moment price touches it
(`research/g71_rrcapv.md` — verified; no runner leg exists live at all).

**So: half your money is in the part of the trade live cannot take.** Nothing else on this
board is close.

### What NOT to chase
Mean R of 2.0 is not reachable on this exit and never was. At a 55% win rate it needs an
average *winner* of 4.47R; the measured average winner is 1.91R
(`research/g71_rtargetV_verify.py`). Track **dollars per day**, not mean R. At a $500 risk
unit your current +0.305R per day already clears $5,000 a month
(`research/g71_rtarget_model.py`).

---

## 2. THE BUGS THAT ARE ACTUALLY COSTING MONEY, RANKED

| # | one sentence | the fix | how long |
|---|---|---|---|
| **1** | Live sells everything at 2R with no runner, and half the money is above 2R. | Port the backtest's exit — half off at the session high, the rest runs to the next level — into `options_sizer.py` and `paper_trader.py`. | **1 day of agent work, then one paper week to confirm** |
| **2** | The disaster stop sits at *exactly* the same price as your level stop, so a wick alone now stops you out and every single loss books exactly −$1,000. | Delete the resting order, or move it out to −$1,250. **Your call — see §6.** | 1 line, but it reverses what you ratified this morning |
| **3** | The options sizer floors the stop premium at 5 cents but leaves the unfloored number in the target, so the card under-reports your reward by up to 3.8× — one trade booked $6,560 on an $872 risk while the card said $1,744. | Floor both legs the same way in `options_sizer.py`. | **30 minutes** |
| **4** | The stop-loss safety test has been failing since Friday, 12 of 64 checks red, and nothing runs it — the `verify:` line only runs the recall check. | Fix the test to check the shipped setting, then add it to the `verify:` line. | **1 hour** (confirmed red just now: exit 1) |
| **5** | A rejected setup silences the good setup one or two bars later on the same level — 4,231 real entries are being eaten by rejects that were never trades. | Only let a *fire* start the two-bar suppression window. | **1 hour to fix, then a full re-run to price it** |
| **6** | The runner can never aim more than $1 past the session high, so on 2,135 of 2,437 trades (87.6%) it targets a round dollar instead of the real level. | Push the target to the trade's own measured move where that is further out. | **half a day** |

Sizes, where they are known:

- **#1** is worth **+$306 a day** under one-trade-a-day (`research/g71_board_check.py`).
- **#2**, deleting the resting disaster stop, measured **+$120 to +$213 per trade** across all
  trades, win rate **49.5% → 55.0%**, worst drawdown **−$17,132 → −$13,700**
  (`research/g71_stops.py`, `research/g71_exitfam.py`). Not yet measured under one-a-day.
- **#5** is **unpriced and could be bigger than #1** — it takes the book from 4,022 entries to
  8,253 (`research/g71_advsigfire_dedupe.py`). Nobody has run the money on it.
- **#6** is worth **+$23 per trade, +$55,600 over two years**, and it is the *only* exit-side
  change in this project's history that beat its own error bar in the right direction
  (`research/g71_faraway.py`).

---

## 3. S-TRADE ACCURACY — WHAT IS NOW KNOWN

**The system does not pick your S trades. It picks the days you refused slightly more often.**

| | how often it trades them |
|---|---:|
| Your 255 gradeable S days | **22.7%** |
| The 486 days you actually refused | **28.8%** |

Pointing the wrong way, p = 0.077. And on setups that got past the accept/reject gate — before
the two-loss halt removes any — the gap is **31.4% vs 41.2%, p = 0.009**: significantly
backwards (`research/g71_smverify_arms.py`, `research/g71_smverify_ladder.py`).

**Where the loss happens.** Of the 68.6-point fall between "the engine saw the setup" and "the
engine traded it": **61.2 points is the candle-shape grader plus the higher-timeframe veto**,
3.5 points is the two-loss halt, and only **3.9 points** is the accept/reject gate
(`research/g71_smverify_arms.py`). **The wound is grading, not gating.** Every previous board
blamed the gate.

**Three more things now known:**

1. **Your S grade is not stored in one place.** Five different fields mean "S" across your 19
   mark files, and **48 of your S days are invisible to any tool that reads a grade field** —
   including all 34 S days in the 100-card sweep, which are filed as `grade: "none"` with the
   real answer somewhere else. Three different S-day counts are already published in this
   repo: 154, 207, 288 (`research/g71_smeasure_pools.py`, `research/g71_vsamplesize_recount.py`).
2. **34 cards is not enough to steer by.** It buys ±15 points. Proving 90% needs 141 cards for
   a ±5-point read (`research/g71_ssverify_power.py`). It IS enough to prove we are *not* at
   90% — that half is solid.
3. **You do not need to grade more.** **278 of your S days already have bars**, and all 1,096
   graded days replay in **two minutes** (`research/g71_samplesize_full_recall.py`). The
   measurement scripts were each hardcoded to one 100-card file; nothing ever read the whole
   pile.

### The definitive test
Two halves, both ready to go:

- **Machine half, no Austin needed:** re-run every recall comparison *paired* across all 278
  bar-backed S days instead of 34 cards. Power to spot a real 10-point improvement goes from
  0.15 to 0.87, for two extra minutes of compute per run (`research/g71_ssverify_power.py`).
- **Human half, 90 seconds:** `research/g71_homework.html` is built and waiting — 30 charts,
  9:30 to 11:00, your six levels drawn, nothing else on them, no entry line, no stop line, no
  grade, and zero repeats against all 1,548 days you have already been shown or graded. Ten
  of the 84% re-entry rule, ten one-candle-rule, ten break-and-retest as the control. **17 of
  the 30 are days the engine itself would have stayed silent on** — a yes on those is the
  whole finding (`research/g71_homework_build.py`).

---

## 4. SEQUENCING — first trade of the day, stop on a win, loss cap

Measured over 496 trading days, one position at a time. "Green days" = days that finished
positive.

| what you would do | trades | win% | $/day | months green | weeks green | green days | worst drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|
| Everything, as shipped today | 2,437 | 49.5% | $2,700 | **25/25** | 91/105 | 58.1% | $14,714 |
| **First trade only, then done** | 496 | 54.9% | $611 | 22/25 | 77/105 | 55.0% | $20,100 |
| **Your sentence:** first; a win ends the day; 2 losses end the day | 705 | 52.5% | $806 | 22/25 | 83/105 | 68.8% | $16,300 |
| Keep going until the day is green, no cap | 972 | 48.8% | $953 | 23/25 | 87/105 | **78.6%** | $15,900 |
| **Keep going until green, 3-loss cap** | 861 | 50.4% | **$897** | 23/25 | 85/105 | 76.4% | **$12,900** |
| Any of the above restricted to S only | 327 | 45.9% | $182 | **14/25** | 59/105 | 28% | $15,700 |

*(all rows: `research/g71_firsts_policy.py`; independently re-derived by
`research/g71_firstsW_recheck.py` and `research/g71_rtargetV_verify.py`)*

**Three honest reads:**

1. **Your rule is a green-day machine, not a money machine.** It lifts green days from 58% to
   69–79% and costs a third to two-thirds of the return. And **77% of that green-day lift
   survives on a completely shuffled book with zero content** — it is stop-when-you-are-ahead
   arithmetic, not something the rule finds in the engine
   (`research/g71_firstsV2_greenday.py`, 30 seeds).
2. **Every one-at-a-time policy breaks the durability gate** — the one gate OMEN currently
   meets. 25/25 green months becomes 22/25 or 23/25. That is the price of holding one position
   at a time, not the price of your stopping rule (`research/g71_firstsW_recheck.py`).
3. **"S trades only" cannot be run today.** It collapses to 14 of 25 green months, because the
   engine's S is flat-to-slightly-negative rather than predictive
   (`research/g71_firsts_policy.py`, `research/g71_firstsverify_sgrade.py`).

### The two-loss rule specifically
**Two losers in a row is not a stopping point.** A trade taken with two closed losses already
behind it still makes **+$308** on average (320 of them, 2.6 standard errors above zero)
(`research/g71_losshalt_grid.py`). What the halt buys is tail, not edge: worst day
**−$10,590 → −$5,780**, worst drawdown **−$27,900 → −$14,700**.

**The medium: stop at 3 losses, plus a −$2,000 floor on the day.** Statistically tied with
today's 2-loss halt on money (+$27,400, range −$23,000 to +$84,500), *identical* worst day and
worst drawdown, and it hands back **162 trades and 60 trading days**. Days the governor stops
you trading go **49% → 37%** (`research/g71_losshalt_grid.py`).

---

## 5. SCALE-OUT

**Your 30/30/30 with a 10% runner and today's half-off-half-runs are the same number.**

| exit | trades | win% | per trade | months green |
|---|---:|---:|---:|---:|
| Shipped (half at the session high, rest runs) | 2,437 | 49.7% | +$550 | 25/25 |
| **Yours: 30/30/30 plus a 10% runner to break-even** | 2,437 | **52.9%** | +$539 | 25/25 |

Difference: **−$10 a trade**. Two independent rigs agree to the dollar, and one of them
reproduces the shipped plan to +$6.50 as a control — so it is a real tie, not test noise
(`research/g71_scaleladder.py`, `research/g71_advscaleladder_verify.py`, 2,437 of 2,437 rows
identical).

**Take your version because it is yours, not because it makes money.** It wins 3.2 points more
often, which is worth having if you are the one watching it.

Everything else in the exit family is a dead end (`research/g71_exitfam.py`, all 2,437 trades):

| tried | worth | verdict |
|---|---|---|
| Aim 2.5R instead of 2R | **+$40 a trade** | real, and free — take it |
| Aim 5R instead of 2R | +$85 a trade | real, but wins only 28.5% and drops a green month |
| Move the stop to break-even at 1R | +$56 a trade | not real — four triggers tested, none survives |
| Cut losers on a 15 / 30 / 45-minute clock | +$11 a trade | not real |
| Get out on the first candle against you | −$38 a trade | not real |
| Hold past 11:00 | −$7 a trade | not real |
| Any strike or expiry other than same-day at-the-money | −$30 a trade or worse | search is closed |

---

## 6. STOPS

**Your own marks answer this, and the answer is not the one you named third.**

114 of your marked days carry both an entry bar and a stop *price*. Matched against the three
families you named (`research/g71_stops.py`):

| where you actually put it | matches |
|---|---:|
| **Bottom of the candle you entered on** | **80 of 114 (70%)** |
| The broken level | 33 of 114 |
| Pivot structure | **7 of 114** |
| None of the three (a named level sitting further away) | 25 of 114 |

Your median stop: **65 cents, 0.197% of price, 0.9× the entry candle's own range.** What ships
today already does the candle-bottom thing 84.8% of the time, so **there is nothing to change
on placement** — all three named alternatives measure *worse* once the too-tight-stop artefact
is removed (all t below −4, paired, `research/g71_stops.py`).

**"Pick whichever gives the best risk-to-reward" is a trap.** With the target fixed at a real
level, maximising reward-over-risk *is* minimising the stop distance — so it walks into the
tightest possible stop every time. Implemented literally: **269 of 2,402 trades (11.2%) end
with zero risk**, green months fall to 22/25, drawdown blows out to −$32,100
(`research/g71_stops.py`). Do not build it.

**Fixed $1,000 is right, and one number settles it:** the correlation between stop width and
outcome is **−0.013** (`research/g71_stops.py`). Stop width tells you nothing about whether the
trade works, so varying your risk with it adds leverage and nothing else.

**Your "$1,000 or $1,250" question is really the disaster-stop question.** Right now the
disaster order rests at exactly your level stop's price, which means a wick alone ends the
trade and **every loss books exactly −$1,000; the −$1,250 you asked for cannot happen on a
whole trade** (0 of 76,019 rows, `research/g71_capture_verify_book.py`). Deleting the resting
order gives you back your close-only rule, takes win rate to **55.0%** and worst drawdown to
**−$13,700** — but it reverses what you ratified this morning, so it is yours to call.

---

## 7. PROP FIRM AND INSTRUMENT

**No prop firm on the challenge model will let you trade options.** Not Topstep, not Apex, not
Trade The Pool, not any CFD shop. The only options-capable desks want $7,500–$12,200 up front
(`research/g71_propfirm.md`, all four vendor pages fetched 2026-08-29).

So the fork is real, and the data picks **shares**:

| route | what you trade | days you keep | best account | risk/trade | pass rate |
|---|---|---:|---|---:|---:|
| **Shares — Trade The Pool** | your 29 tickers, same setups | **100%** | **$50k FLEX Day** | **$150** | **99.6%** |
| Index futures — Topstep / Apex | only SPY/QQQ/IWM as MES/MNQ/M2K | **28%** | 50K only | $350 | 90.3% |

*(`research/g71_propfirm_sim.py`, 10,000 bootstrapped paths per risk level)*

- **Futures throws away 72% of your trading days** — only 139 of 500 sessions produce an index
  signal, and the 100K and 150K futures accounts **cannot be passed 90% of the time at any risk
  level**, because a 6% target needs more opportunities than SPY/QQQ/IWM gives.
- Restricting shares to SPY, NVDA and TSLA only: risk **$250**, pass **95.4%**, median **18
  trading days** to funded.
- **Your "I would fail 10% of the time" number:** on the Apex $150k account, the largest risk
  unit that keeps a genuine blow-up at or under 10% is **$650** — 8.45% blow up, 48.7% pass,
  42.8% simply run out of clock (`research/g71_rtargetV_evalscan.py`). Running out of clock
  costs the entry fee, not the account.
- **Stress test:** the $150-a-trade answer holds only if the −$1,000 stop actually fills at
  −$1,000. At −$1,250 the futures band collapses to $100–$150. At −$2,000, **no futures account
  passes 90% at any risk** (`research/g71_propfirm_sim.py`). Size off the −$1,250 column.

### Instrument
**Buy ThetaData "Options Standard", $80 a month** (`thetadata.net/pricing`, fetched 2026-08-29).
It is the only vendor serving every expired-contract quote back to 2016 at that price. One or
two months closes every open options question in this repo.

Why it matters: **there is no options tape in this repo.** Every option price ever published
here is a textbook model on estimated volatility. The +1.4988R "options edge" that
`DIRECTION.md` still quotes is dead — it was contaminated by using the whole session's range to
price the entry. The clean replacement is **+0.96R with contracts vs +0.87R with shares, a
null** (`research/g71_instrument_spread.py`). What *is* real: an option dies at a **7.5-cent**
round-trip spread, while one futures tick costs a third as much and survives 27.7 ticks.
**The instrument is where the risk is, not where the money is.**

---

## 8. THE SCARFACE CORPUS — how much is really there

**The text is there and it is big. The video is a third done. The images have essentially never
been looked at.**

| | how much | usable now |
|---|---:|---|
| Scarface alert messages (Apr 2024 → Aug 2026) | **6,692** | yes — 5,066 carry a chart image |
| Jdub alerts | 4,274 | yes |
| Trading floor | 39,527 | yes |
| Futures alerts | 4,789 | yes |
| Trade-review posts with date + symbol + P&L extractable **as text** | **239 of 267** | yes |
| YouTube videos known | 2,475 | **only 805 transcribed (32.5%)** |
| Course lessons | 195 | **195 transcribed (100%)**, but 105 never mined for rules |
| Chart images stored | **47,551** | **200 ever shown to a model (0.4%)** |

*(`research/g71_scarface_inventory.py`, `research/g71_media_inventory.py`,
`research/g71_scarfaceverify_extract.py`, `research/g71_media_yt_gap.py`)*

**The video hole is smaller than it looks, and it is not a "we need more agents" problem.** Of
the 1,670 untranscribed videos: 593 are dead, private or members-only; 207 were never attempted;
1,463 were reached and the transcript was refused. Realistic recoverable ceiling is **about
1,077, not 1,670**. Four scrapers cannot even start because a library is not installed, and
**both rule-extraction scripts are dead as written** — they hardcode
`C:\Users\aharg\tradingbot\...`, a folder that does not exist (`research/g71_media_mining_gap.py`).

**The catch, and it is the important one:** these are Scarface's judgements, not yours. Pooling
them gives more *rules* and more *examples*. It cannot fix the money gate, because the scarce
input is your eye, and there is exactly one of you.

---

## WHAT AGENTS DO NEXT — no Austin needed

1. **Port the backtest's exit into the live path**, behind an off-by-default switch, with a test
   that proves live and backtest book the same result on the same trade. This is the
   $6,400-a-month item. Build it; do not turn it on.
2. **Fix the options sizer's 5-cent floor bug** so the reward on the card matches the reward in
   the account. 30 minutes.
3. **Fix the stop-loss safety test and wire it into the `verify:` line** so it can never go red
   silently again. It is red right now (exit 1, 12 of 64 checks).
4. **Fix the suppression bug** — a rejected setup must not silence the next one — and **re-run
   the full two years** to price it. It is the only unpriced item that could be bigger than #1.
5. **Re-run every recall comparison paired across all 278 bar-backed S days** instead of 34
   cards. Two minutes of compute per run, and it turns a coin flip into a real read.
6. **Make the recall scorer use the actual engine** instead of its hand-written copy, and
   re-publish the number honestly (23 of 34 becomes 22 of 34). The recall gate stays green —
   confirmed by running it just now.
7. **Give every judged S day one spelling.** One function that reads all five fields, so the 48
   invisible S days stop being invisible and the repo stops publishing three different S-day
   counts.
8. **Put the setup name and the level name on every trade row** so homework cards can say
   "break-and-retest of the opening-range high" instead of "other". Both labels already exist
   on the signal and are thrown away one line later.
9. **Fix the four stale numbers in `DIRECTION.md`** — it advertises 2,595 trades, 43.1% win,
   $32,400 drawdown and 18-of-34 recall; the book on disk says 2,437, 49.5%, $17,132 and 23-of-34.
10. **Re-measure the disaster-stop deletion under one-trade-a-day.** It has only ever been
    measured across all trades, and one-a-day is the policy you are actually going to run.
11. **Repoint the two dead rule-extraction scripts** at the real folder, then run the 105 unmined
    course transcripts and the ~1,077 recoverable videos.

## WHAT ONLY AUSTIN CAN DECIDE — each one under 2 minutes

1. **The disaster stop.** Keep it resting at −$1,000 on a touch (what you ratified this morning;
   gives 25/25 green months and a worst loss of exactly −$1,000) — or delete it, which restores
   your "wicks stop nothing" rule, takes win rate 49.5% → 55.0% and worst drawdown
   −$17,132 → −$13,700. **One word.**
2. **Which sequencing rule.** Your sentence — first trade, a win ends the day, two losses end the
   day ($806 a day, 69% green days) — or keep going until the day is green with a 3-loss cap
   ($897 a day, 76% green days, smallest drawdown on the board). **One word.**
3. **Prop route.** Shares at Trade The Pool (keeps all 29 tickers, $150 a trade, 99.6% pass) or
   index futures (throws away 72% of your days). **One word.**
4. **$80 a month for the real options data.** Yes or no.
5. **The live card.** When the runner ships, do you want it to show two rungs — sell half at the
   high, let the rest run, which is what the book measures — or keep one all-out exit with the
   target pushed further out? **One word.**
6. **Grade the first slate on `research/g71_homework.html`.** Three charts, yes or no on each.
   **90 seconds.** Do more if you feel like it: there are ten slates, and 17 of the 30 are days
   the engine went silent on.
7. **QQQ, 31 July 2026.** You graded it S on the 26 Aug homework and not-S on the 19 Aug index
   deck. Same chart, seven days apart. **Which one stands?**
8. **Green weeks.** 105 of 105 is not reachable. You are at 91 of 105 (86.7%), and buying your
   way to 97% costs 86% of the income (`research/g71_weeks.py`). **Is 87% of weeks green the
   target — yes or no?**

---

## DID NOT HOLD UP

Each of these was claimed by a track today and then knocked down by an independent check.
Listed so nobody acts on them.

- **"The drawdown busts every prop firm."** No. With each firm's drawdown *lock* modelled, the
  book survives the 4%, 5% and 6% floors with $15,796 to spare. Only Apex's $150K account
  fails, by touching exactly −$4,000 on trading day 2 (`research/g71_ddverify_lock.py`).
- **"$350 a trade is the ceiling, and two independent methods agree."** Neither half. The two
  methods are the same method, the 4% floor used is not a floor any modelled firm has, and the
  correct answer under Apex's own rules is **$375** (`research/g71_ddverify_prelock.py`).
- **"18 positions open at once, $22,500 of risk."** It is **12** positions and **$12,000** — six
  of the eighteen were the same trade filed against different level names, and the price it was
  costed at cannot happen (`research/g71_verify_drawdown_concurrency.py`).
- **"Two filters kill 93% of your S setups."** They are 87% the same filter. The higher-timeframe
  veto's own contribution is 1.7–6%, and the S rows it kills are the *worst*-earning bucket
  anyway (`research/g71_advscanners_funnel.py`).
- **"Your 'it broke then gave it back' rule can never fire."** It fires fine. It is blind because
  the code hands it the trade's *stop* as the level instead of the level itself
  (`research/g71_btrverify_reach.py`).
- **"Pivot levels carry 5 of your 23 held-out S days."** The real pivots-off re-run costs
  −$310,000 and one green month, and the book takes **zero** trades on all five of those days
  (`research/g71_scanners_pivotverify.py`).
- **"Restricting the target to your six levels loses money."** It is **flat** (+$16 a trade,
  25/25 green months). The loss came from a 2R fallback the test silently added on the 48% of
  trades where none of your six was in range (`research/g71_levelsv_book2.py`).
- **"The whole-dollar target came from the Scarface videos."** You said it yourself, three times,
  including on 2026-08-29 (`research/recovered_reviews.jsonl:21,39`,
  `research/marks/probe_master_2026-08-29.jsonl:112`).
- **"Only 4 live trades in two years."** 127 — the 84% re-entry rule is exempt from the grade
  check (`research/g71_sigfireverify_tier.py`).
- **"Book-reachable S recall is 44%."** 63% — the check used the wrong ticker list and divided by
  the wrong denominator (`research/g71_advcapture_universe_check.py`).
- **"Swapping in your S/A/C grading costs 6 of your 34 S days."** On the traded book it costs
  **zero** (`research/g71_ladder_verify_bookrecall.py`).
- **"The suppression bug is THE cause of the harness-vs-book gap."** It is 13 of 16 cards; the
  other 3 are the two rigs computing the higher-timeframe bias from different bars
  (`research/g71_advrouter_16cards.py`).
- **"The trade-review channels contain no text."** 239 of 267 Scarface reviews carry date,
  symbol and P&L as plain text (`research/g71_scarfaceverify_extract.py`).
- **"Mean R ranks the day policies backwards."** At equal risk deployed it ranks them correctly,
  and on the live exit the gap between the two policies vanishes into noise
  (`research/g71_rtargetV_verify.py`).
- **"34 cards has 99.9% power."** 90.3%, and the number behind it was a stale recall constant
  (`research/g71_ssverify_power.py`).
- **"The two-loss halt is the only day governor."** There are at least five, including a hard
  3-trades-per-day cap nobody mentioned (`omen_bot.py:885`).
