# The suppression bug — fixed, and priced over the full two years

**What was wrong, in one sentence:** when the engine looked at a setup and said
*no*, the backtest wrote that refusal down as "this level is taken" — and then
threw away the real trade that showed up on the same level one minute later.

It is fixed. Here is what it is worth.

---

## The money

Two years, 500 sessions, 28 tickers, $1,000 of risk a trade. Same data, same
engine, same exits, same everything. The only thing changed is who is allowed
to say "this level is taken."

### Every trade the engine takes

| | before (the bug) | after (fixed) |
|---|---:|---:|
| trades | 2,436 | **4,508** |
| win rate | 49.7% | **59.4%** |
| **$ per trade** | $549 | **$584** |
| **$ per day** | $2,676 | **$5,268** |
| $ over the two years | $1,337,757 | **$2,633,850** |
| **months green** | 25 of 25 | **25 of 25** |
| **weeks green** | 91 of 105 | **100 of 105** |
| green days | 58.1% | **69.9%** |
| **worst drawdown** | $17,135 | **$11,105** |

### One trade a day, first signal, then done — the way you would actually run it

| | before (the bug) | after (fixed) |
|---|---:|---:|
| trades | 496 | 499 |
| win rate | 55.0% | **66.7%** |
| **$ per trade** | $611 | **$722** |
| **$ per day** | $607 | **$721** |
| $ over the two years | $303,285 | $360,380 |
| **months green** | 22 of 25 | **25 of 25** |
| **weeks green** | 77 of 105 | **87 of 105** |
| green days | 55.0% | 66.7% |
| **worst drawdown** | $20,137 | **$5,993** |

*(`research/g72_suppress_price.py`, which builds both books from scratch and
prices them on identical arithmetic. Numbers in
`research/g72_suppress_numbers.json`.)*

---

## The honest read, because half of this is noise

**More money per day is real. More money per trade is not.**

Paired day by day across the same 500 sessions, resampled 10,000 times:

| | gain per day | 95% range | verdict |
|---|---:|---|---|
| every trade | **+$2,597** | +$2,149 to +$3,042 | **real** |
| one trade a day | +$114 | −$24 to +$250 | **inside the noise** |

So: taking every signal, the fix is worth about **$2,600 a day** and it clears
its own error bar by a mile — but only because you get **1.85× as many trades**.
Each individual trade is barely different ($549 → $584 a trade; that part is
noise). The engine was not making worse trades. It was making **half as many**.

Under one-a-day, the day still opens on a trade — it just opens on a **different,
earlier one** on 230 of the 499 days. That change is worth $114 a day and cannot
be told apart from luck. **Do not sell one-a-day on the money.** Sell it on the
two things that are not noise:

- **Months green goes 22 of 25 to 25 of 25.** The board's §4 said flatly that
  every one-position-at-a-time policy breaks the one gate OMEN currently meets.
  With this fixed, it does not.
- **Worst drawdown goes $20,137 to $5,993** — a third of what it was.

---

## Is it just twice as many bad trades? No.

The 2,338 entries the fix hands back, scored on their own:

| | the new entries | the ones that already existed |
|---|---:|---:|
| count | 2,338 | 2,170 |
| win rate | **67.3%** | 51.0% |
| $ per trade | $601 | $567 |
| average winner | $1,340 | $2,046 |

They **win more often and win smaller** — which is exactly what you would expect
and not a red flag. They enter one or two minutes later on the same level, so
the session high is nearer, so the half-off-at-the-high leg fills more often and
the runner has less room. Same money per trade, different shape.

265 entries that used to exist do not survive the fix. That is the same rule
working in the other direction: a genuine earlier fire now claims the level and
the later one is correctly folded into it, plus the two-loss halt trips more
often now that there is more to trip it.

**It is not the same trade booked twice.** Across all 4,508 traded rows, the same
symbol + day + direction + level appears more than once **93 times, 2.06%**
(`research/g72_suppress_who_ate.py`).

---

## What was doing the eating

For every unlocked entry, the row that had claimed its level one or two minutes
earlier:

| what had claimed the level | share |
|---|---:|
| **a `D` row — the engine's own "I should not have fired at all"** | **69.4%** |
| a window rolled forward from further back | 28.9% |
| a setup skipped for too tight a stop | 0.8% |
| a genuine earlier fire (correct — this is the rule working) | 0.8% |
| a trade the two-loss halt had already blocked | 0.1% |

Seven of every ten trades the engine lost, it lost to its **own bug report**.
`X`/`D` is not a grade; it means the detector should never have spoken. It was
being given the power to veto the trade standing right behind it.

---

## And it moves the gate that actually matters

Recall, on the 100 held-out cards from 26 August — the same measurement
`research/g71_router_bookdedupe.py` scored the book at 20.6%:

| | S days reached | recall | precision |
|---|---:|---:|---:|
| before (a reject arms the window) | 7 of 34 | 20.6% | 20.6% |
| **after (only a fire arms it)** | **22 of 34** | **64.7%** | **38.6%** |

**Fifteen of your S days come back. Not one is lost.**
(`research/g72_suppress_recall.py`; its control arm reproduces the published
20.6% exactly, which is how you know the rig is the same rig.)

This also closes the thing the board called "the harness-vs-book gap." The recall
harness never had this bug — `research/t4_engine_recall.py` only ever wrote its
window on a fired signal. The book did. They now agree, and **22 of 34 is the
same 22 of 34 the harness reports**.

---

## What changed in the code

One file, `backtest_week.py`, two places:

- A new switch `DEDUPE_FIRES_ONLY`, default **on**. `DEDUPE_FIRES_ONLY=0`
  restores the old behaviour, which is how the "before" book above was built.
- In `simulate_day`, the suppression window is opened and extended **only by a
  signal whose status is `fired`**.

Nothing about the rule Austin ratified changed. Two fires on the same level on
back-to-back minutes are still one idea; one quiet minute and the next one is
still a new trade (R16, `DEDUPE_CONTIG = 2`). The only thing that changed is that
a setup the engine refused no longer gets a vote.

The engine itself already had this right. `signal_runner._route` says so in its
own comment, about its own no-repeat registry:

> *Suppression sits inside the accepted branch on purpose: a tight-stop skip
> never fired, so it must not claim the level — the first AVAILABLE entry wins.*

The backtest was overriding that on the way out. **No change was needed in
`signal_runner.py`.**

### Proof it is fixed

`research/g72_suppress_test.py` drives the dedupe with a scripted detector — no
bars, no market data — and checks three cases both ways:

| | with the bug | fixed |
|---|---|---|
| a reject, then the real trade one bar later | trade eaten | **trade survives** |
| a fire, then a fire one bar later | one idea | one idea |
| a fire, a quiet bar, a fire | two trades | two trades |

Passing. `python research/regression_gate.py` is **PASS** — unchanged, 83
any-signal / 13 S-grade, no mark that used to fire went silent.

---

## Two things left open, neither of them mine to close

1. **The book on disk is now stale.** `research/bt2y_trades.json` was built with
   the bug and every board number comes off it. It needs one re-run of
   `python backtest_2y.py`. I deliberately did **not** overwrite it — other
   agents are reading it right now in this same session, and changing it under
   them would silently move their results.

2. **The live path has the same bug in a different shape, and it is bigger.**
   `live_scanner._cooled_down` claims a **20-minute** silence per symbol +
   direction, and it is called *before* `_tier()` decides whether the signal is a
   trade or just a watch ding. So a WATCH ding — a signal the system explicitly
   decided **not** to trade — silences the real TRADE-tier signal for the next 20
   minutes on that symbol. That is the same mistake with a window six hundred
   times longer. I left it alone on purpose: there is no rig that can price a
   live-path change, and this repo's own rule is measure first, wire second. It
   should be somebody's next ticket.

Also worth knowing: several one-shot measurement scripts in `research/` copied the
buggy dedupe inline (`t3_session_extreme.py`, `t11_s_quality.py`, `t51_s_bar.py`,
`t5_no_repeat_effect.py`, `t8_verdict_measure.py`, `x3_detector_census.py`,
`w10_gate_autopsy.py`). Any number they published carries the bug with it.

---

## Scripts behind every number here

| script | what it produced |
|---|---|
| `research/g72_suppress_price.py` | both books, the money tables, the error bars |
| `research/g72_suppress_recall.py` | 20.6% → 64.7% recall, with a control that reproduces the published figure |
| `research/g72_suppress_who_ate.py` | who was claiming the levels, and the duplicate audit |
| `research/g72_suppress_test.py` | the three-case proof, runs in a second |
| `research/g72_suppress_numbers.json` | every figure in the two money tables |
| `research/g72_suppress_recall.json` | the 15 S days that came back, by name |

Reproduce the whole thing with
`python research/g72_suppress_price.py` (about ten minutes).
