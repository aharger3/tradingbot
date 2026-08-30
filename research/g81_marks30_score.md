# The 30 fresh judgements, scored against the engine

Measured 2026-08-30. Script: `research/g81_marks30_score.py`. Full per-card output:
`research/g81_marks30_score.json`.

Input: `research/marks/probe_g71_homework_s3_2026-08-29_complete.jsonl` — 30 charts Austin
graded on 2026-08-29. Session window only, his six levels drawn, no entry line, no stop
line, no grade shown, zero repeats against the 1,548 symbol-days he had already been
served. 21 yes, 9 no, ten cards each of the 84% rule, the one-candle rule, and
break-and-retest. Twenty-one of them carry the minute he would have entered.

**The router is the real one.** The script refuses to run unless the capture subclass in
`research/t4_engine_recall.py` delegates to `signal_runner.SignalRunner._route`. It does —
`assert_real_router()` reads the source and checks for the `super()._route(` call before
anything is measured. Every number below is the shipped decision logic, not the
hand-written copy that used to flatter recall.

---

## Read this before the headline numbers

**This deck cannot measure recall in the usual sense, and the 100% detection row is an
artefact of how it was built.** Every one of the 30 cards was drawn from a symbol-day the
engine had *already* flagged and that `research/downgrade.py` had *already* graded S. The
deck was built as a precision instrument — "here are three stocks I believe are S trades,
say yes or no" — so "did the engine detect something here" is true by construction on all
30. Reporting it as recall would be scoring the engine against its own selection.

What this sample *can* answer, and what nothing before it could, is:

1. Of the days the engine claims are its best, how many does Austin agree with.
2. Of those he agrees with, how many survive the router to a booked entry.
3. **Whether the engine is at the right minute.** This is the new thing. The chart carried
   no entry line, so his minute is independent of the engine's.

---

## The two headline numbers

| | his 21 yes-days | his 9 no-days |
|---|---|---|
| engine produced any signal | 21 (100%) — by construction | 9 (100%) — by construction |
| the router accepted one | **14 (66.7%)** | **6 (66.7%)** |
| it survived to a booked entry | **14 (66.7%)** | **5 (55.6%)** |

Booking on 14 of 21 days he liked and 5 of 9 days he refused is a difference of 11 points
on 30 cards. Fisher exact two-sided **p = 0.687**. **The engine's decision to trade carries
no measurable information about whether Austin would take the day.** On a sample this size
that is not proof of no signal, but it is the honest read: nothing here separates the two
groups.

### By bucket, booked entries

| bucket | his yes | booked | his no | booked |
|---|---|---|---|---|
| 84% rule | 6 | **6 (100%)** | 4 | 3 (75%) |
| one-candle rule | 8 | **4 (50%)** | 2 | 0 (0%) |
| break-and-retest | 7 | **4 (57%)** | 3 | 2 (67%) |

The 84% rule books everything — every yes and three of four noes. It is not
discriminating; it is saying yes to almost the whole bucket. The one-candle rule is the
opposite: it books half his yeses and refused both of his noes, the only bucket that
looks like it is choosing. Break-and-retest books slightly *more* of his noes than his
yeses.

Every one of these cells is 2–8 cards. Do not tune anything on them.

---

## The timing result, and it is the important one

Twenty-one yes-cards carry his entry minute. (The prompt for this work said twenty; the
twenty-first is `IWM 2026-08-06`, written `9:%5` — the shift key held on the 5. Read as
9:55 and flagged as inferred in the script. Every number below is reported with it in; it
changes no conclusion.)

Four other notes contain a clock time that is **not** his entry — twice he is naming the
minute *the engine* picked ("9:47 is what you liked", "9:45 its close i see what your
seeing"), once a candle, once a hypothetical break. Those are excluded by hand, with the
reason recorded in `STATED` in the script. Folding them in would be scoring the engine
against itself.

### The funnel at his minute

Within ±2 minutes of the minute Austin named, over all 21:

| | within ±0 | ±1 | ±2 | ±5 |
|---|---|---|---|---|
| engine produced any signal there | 4 | 8 | **10 (48%)** | 10 |
| the router accepted one there | 1 | 2 | **5 (24%)** | 5 |
| it booked an entry there | 1 | 2 | **5 (24%)** | 5 |

**On more than half his entries the engine never fires a signal at all within five minutes
of the right moment.** Of the ten it does reach, the router throws away five. Widening the
tolerance from two minutes to five buys nothing — the miss is not a near-miss, it is a
different part of the session.

By bucket at ±2 minutes: break-and-retest reaches his minute most often (5 of 7 detected)
and keeps it least (1 booked). The 84% rule reaches only 2 of 6 but keeps both. The
one-candle rule reaches 3 of 8 and keeps 2.

### The signed distribution — the engine is late

Engine's **first booked entry of the day** minus Austin's minute, over the 14 yes-days
where it booked anything:

```
-43  -19   0  +1  +2  +2  +2  +6  +10  +12  +13  +19  +32  +41
```

median **+4**, mean **+5.6**. Eleven late, one exact, two early. Only five of fourteen land
within two minutes; only five within five minutes. The two early ones are large (−43, −19),
so the mean understates how one-sided this is: on the 12 cards that are not those two
outliers, the engine is late on 11.

And the **card the engine actually showed him** — each card is one specific engine signal,
at the minute that signal happened — is later still. Card minute minus his minute, all 21:

```
-4  -1  -1   0  +12 +12 +12 +12 +16 +23 +24 +28 +30 +32 +41 +43 +45 +48 +49 +54 +59
```

median **+24 minutes**, mean **+25.4**. Seventeen of twenty-one are late; only four land
within five minutes. **The moment the engine believes is its best setup of the day is,
typically, twenty-four minutes after the moment Austin would already be in the trade.**

This contradicts the standing claim that the engine's timing is exact (median +0.0 bars,
`research/t1_entry_minute_autopsy.md`). That measurement joined against marks whose entry
bar came off an engine-annotated card — the entry line was on the chart. This deck drew no
entry line, so it is the first time his minute was produced independently, and the answer
is different. **Timing is not solved. It was never measured on an independent sample
until tonight.**

---

## Both grade ladders, side by side

Every signal the router accepted on these days, counted by ladder. Never mixed — Austin's
`S/A/C` from `research/downgrade.py` (level proxy = the trade's stop, the same convention
`backtest_2y.py` uses), the legacy `A+/A/B/C/X` off `signal_runner.py::_grade_pa`.

| | legacy ladder | Austin's ladder |
|---|---|---|
| on his 21 yes-days | A 1 · **B 13** · C 3 · **A+ 0** | S 6 · A 3 · C 8 |
| on his 9 no-days | B 6 · C 3 · **A+ 0** | S 1 · A 3 · C 5 |

Two things fall out.

**Not one A+.** `live_scanner._tier()` promotes to TRADE only on `grade == "A+"`. Zero of
the 21 days Austin said yes to would be traded by the live path. That is the real-money
blocker in `DIRECTION.md`, reproduced on a fresh held-out sample.

**Austin's own ladder does not reproduce its own selection.** Every card in this deck was
picked *because* `downgrade.py` scored it S. Replayed today at the bar the router actually
fires, the same code calls only 6 of 17 fired signals on his yes-days S, and calls C on 8.
The deck's grade was computed at one specific bar from the two-year book; this replay
grades whichever bar the router picks today, on archive bars rather than the book's fetch
path. The two are not measuring the same instant — but they were presented as one claim on
the card, and they disagree. Worth a separate look before any number computed off `sgrade`
is quoted again.

---

## The silent days

The claim to check: *17 of these 30 were days the engine would have stayed silent when the
deck was built.* Three different counts are hiding behind that sentence, and none of them
is 17:

- **16** cards carry legacy grade `X` in the deck manifest. `research/g71_homework.md` says
  17; the manifest says 16. That line is off by one.
- **25** of 30 cards were not traded when the deck was built (`traded: false`).
- **15** of the 30 symbol-days have no traded row at all anywhere in
  `research/bt2y_trades.json`.

Austin's yes-rate on each:

| the "silent" set | n | he said yes |
|---|---:|---:|
| legacy grade `X` cards | 16 | **11 (69%)** |
| cards not traded when the deck was built | 25 | **17 (68%)** |
| of those 25, still not booked on today's replay | 10 | **7** |

The coincidence is worth naming so nobody conflates them later: the "17" that comes out of
this analysis is *the number of yes-days among the 25 untraded cards*, not a count of
silent days.

**Seven days are pure misses** — Austin said yes, and the engine books nothing on them
today:

| day | bucket | his minute | engine signal minutes that day |
|---|---|---|---|
| NFLX 2025-07-08 | one-candle | 9:38 | 10:01, 10:02, 10:04, 10:06, 10:10, 10:24 |
| TSLA 2025-09-03 | break-retest | 9:45 | 09:44, 10:29 |
| SPY 2025-05-21 | one-candle | 9:45 | 10:17, 10:33, 10:35, 10:38, 10:50 |
| AVGO 2024-11-04 | break-retest | 9:47 | 09:38, **09:47**, 09:49, 10:05, 10:20, 10:45, 10:50 |
| SPY 2026-06-17 | one-candle | 9:48 | **09:48**, 09:53, 10:42, 10:44, 10:52, 10:53 |
| ACHR 2026-04-13 | one-candle | 10:09 | 09:41, 10:17, 10:33, 10:57 |
| QQQ 2024-08-26 | break-retest | 9:56 | 09:52, 09:54, 10:24 |

Three of the seven are **the router's fault, not the detector's**: AVGO and SPY 2026-06-17
produced a signal on the exact minute he named, TSLA one minute before, and the router
discarded all three. The other four the detector genuinely never reached — its signals that
day cluster twenty to forty minutes after him.

## Where the engine and Austin agree to refuse

Four of his nine noes the engine also refuses: NVDA 2025-06-24 and QQQ 2025-12-22 (he wrote
"no displacement"), AAPL 2026-03-11 ("chop"), AVGO 2025-12-03 ("no retest"). Five it books
anyway. His stated reasons on those five — level not respected, no displacement, chop, late,
took too long for the entry — are the same eight variables `downgrade.py` already computes
but that nothing gates on.

---

## Proposed changes — measure first, apply nothing

This workflow measures. Nothing below is applied.

1. **Nothing in the engine should be tuned on 30 cards.** Every bucket cell is 2–8 cards;
   the standing error bar on this project is ±1.5799R and the equivalent here is roughly
   ±20 points on any 8-card rate. The one finding large enough to act on is the timing
   offset, and even that wants a second independent sample before a diff.
2. **Run the same measurement on a second no-entry-line deck before believing +24 minutes.**
   The cheapest confirmation available: build another thirty cards the same way, thirty
   fresh symbol-days, and see whether the median stays north of twenty minutes. If it does,
   entry timing is the largest single gap this project has, larger than the grade ladder.
3. **Autopsy the three router discards at his exact minute** (AVGO 2024-11-04 09:47,
   SPY 2026-06-17 09:48, TSLA 2025-09-03 09:44). These are the cheapest possible
   diagnostics: the detector was right, one gate said no, and there are only three of them.
   Which gate, on each. No code change until that is known.
4. **Re-open the `sgrade` reproducibility question.** The deck's S and today's replay's S
   disagree on 11 of 17 fired signals on his yes-days. Before that, find out whether the
   cause is the bar source, the entry bar, or the grade code. If a published number moved,
   it moved.

## Caveats

- **Detection recall of 100% is by construction.** This deck is a precision instrument.
  Do not quote it next to the 58.6% held-out recall in `DIRECTION.md` — different question,
  different sample.
- Both replays are fed the same reconstructed levels from `research/t4_engine_recall.py`
  and `qqq_breaks = None`, matching the recall rig. `backtest_2y.py` feeds real QQQ breaks;
  that input is a tag, not a gate, but it is a difference from the book.
- Bars come from the archive CSVs, not `backtest_2y`'s fetch path. That is the likely
  source of the small disagreements with the deck manifest's `traded` and `et` fields.
- Booked entries come from `backtest_week.simulate_day` and `SimTrade.counted` — fired and
  grade not C, since C is alert-only in the live scanner. Alert-only signals are recorded
  separately per card in the JSON.
- Austin's minute is a minute, not a bar. Comparisons are in wall-clock minutes on
  one-minute bars, so ±1 minute is ±1 bar.
- **No mark file was written.** Everything under `research/marks/` was opened read-only.
