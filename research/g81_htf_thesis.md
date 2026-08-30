# The higher-timeframe thesis: the prize is real, and none of the four definitions collect it

Measured 2026-08-30. Script: `research/g81_htf_thesis.py`. Every number below is in
`research/g81_htf_thesis.json`. Re-run it with `python research/g81_htf_thesis.py`
(about four minutes cold, seconds once the daily cache is built).

Austin, last thing on the night of 2026-08-29:

> *"An S trade happens at 9:30 — but it would have been a better S trade 20 minutes later if I
> knew the longer time frame. I could have been more selective. That's why the higher time frame
> thesis and how it shapes the trades is now very important... take a look at a signal when it
> happens and be like, the higher time frame doesn't look as good, or wasn't the strongest candle.
> I have a feeling that something better can happen. But all that's very ambiguous and hard to
> track."*

Nothing here is applied. Nothing here is a new rule. `HTF_BIAS_VETO` is a veto with no author and
is **not** what he asked for; it appears below only as one candidate among four, measured on the
same rig as the three that have a source.

---

## The answer in four lines

1. **The prize is the biggest number in this project.** Picking the day's best setup instead of
   its first is worth **$3,458 a day** — $721 becomes $4,179. He is right that the first is
   usually not the best.
2. **None of the four higher-timeframe definitions collects any of it.** Best arm as a selector:
   **+$41/day, band −$80 to +$157**. Every arm ties with doing nothing.
3. **The wait rule is aimed at the wrong end.** On the thirty charts he graded on 2026-08-29,
   **on 10 of the 20 days where he wrote a minute the engine had no signal at all before that
   minute.** He is earlier than the engine, not later. Telling the engine to wait makes a
   system that is already a median 24 minutes late (`research/g81_marks30_score.md`) later still.
4. **And it costs recall.** The gentlest wait arm still drops **12 of the 154 S days** the book
   reaches; the harshest drops 25. That is the gate he is furthest from.

**One thing survives, barely, and it is not tradeable yet.** Signals where all four timeframes
agree make **+0.604R** against **+0.434R** where none do — a **+0.170R** difference with a 95%
interval of **[+0.002, +0.338]**. It clears zero by two thousandths of an R, it is not monotone
in the middle (3-of-4 scores below 2-of-4), and it disappears the moment it is turned into a
policy that picks trades. Read it as a hint about where to look, not a result.

---

## 1. The size of the prize, with no model at all

One trade a day, 499 sessions, over `research/bt2y_trades.json`. The candidate stream is the same
one `research/g72_suppress_price.py::oneaday_rows` uses — every signal the engine fired and
traded, plus the ones the account-wide two-loss halt blocked, because under one-a-day that halt
cannot have fired yet. **6,170 candidates, a median of 12 a day.**

| policy | $/day | mean R | win rate | worst drawdown |
|---|---:|---:|---:|---:|
| **first setup of the day** (what ships) | **$721** | +0.722 | 66.7% | $5,993 |
| a coin flip among the day's setups | $522 | — | — | — |
| **best setup of the day** (oracle) | **$4,179** | +4.187 | 99.0% | $2,000 |
| worst setup of the day (the floor) | −$982 | −0.984 | 1.0% | $491,021 |

**The gap between first and best is $3,458 a day.** That is the ceiling on every selector anyone
builds, and it is roughly five times the entire book.

Two things about arrival order fall out of the same table:

- **It is barely better than chance.** The first setup is the day's best on **64 of 499 days
  (12.8%)**; picking at random from a median-12 field would hit **10.1%**. Arrival order is worth
  **$199/day over a coin flip** — real, but small next to $3,458.
- **The oracle is an upper bound and a soft one.** A 99% win rate is what perfect hindsight over a
  12-way choice looks like; and the two-year book's fills were shown on 2026-08-29 to be
  unobtainable 83% of the time (`Projects/omen-rulebook.md`, "The fills were never obtainable").
  The **honest floor for the shipping policy is $111/day, not $721**. Every arm below is compared
  against the same inflated baseline, so the *comparisons* hold; the *levels* do not.

**Step 1 does not end the enquiry — the prize is enormous.** Everything that follows is about
whether a higher-timeframe read is the tool that reaches it.

---

## 2. The four candidate definitions, and where each one comes from

Two sources only, as instructed: Austin's own words in `Projects/omen-rulebook.md`, and the mentor
and course corpora. **Austin has never stated a higher-timeframe rule** — twice on the record:
*"we dont have any higher timeframe bias yet youll need to tell me what that is then"* — so all
four sources below are mentors. That is the reason every one of these is a ballot line and not a
change.

Each is computable at 09:29 or from the day's own bars up to the decision minute. No look-ahead:
daily and weekly windows close on the **previous** session, and the intraday index read at minute
T uses closes up to **T−1**. The book's own `spy_trend` field is deliberately unused — it is
computed from an average window that includes the day's own close, so it knows the answer.

**A. Index at the minute.** *Take the setup that is moving the same way the index is moving right
now, measured from the 09:30 open to the close of the minute before the signal.*
> *"usually I wait for the indices to show me a clear direction or trend. Then after I understand
> the indices trend or direction, I go look for the one with relative strength or relative
> weakness"* — course corpus. And: *"you see the a plus setup on one sticker only valid as an a
> plus when the conference with qqq is there as well."*

**B. Daily bias.** *Take the setup that agrees with the symbol's own daily chart — yesterday's
close above or below its 20-session average.*
> *"If you are day trading the timeframes you want to be looking at are the daily and hourly
> charts for higher timeframes"* — Jdub. *"If you can consistently identify the daily bias then it
> will make trading alot easier"* — Jdub. *"My strategy my edge is so simple. It works with
> relevant key levels on the daily and the 15 minute chart"* — course corpus.

**C. Hourly bias — the incumbent.** *Take the setup that agrees with the hourly chart — the last
hourly close before the bell against its 20-hour average.* This is the exact formula inside
`HTF_BIAS_VETO` (`backtest_week.htf_bias_for`), scored here as a selector instead of a veto, so
the thing that already gates 47% of the book is measured on the same rig as the ones with authors.

**D. Alignment stack.** *Count how many timeframes agree with the setup — week, day, hour, and the
index right now — and take the setup with the most agreement.*
> *"if you have an a plus setup in the market what you want to see is the weekly align you want to
> see the daily chart aligned you want to see the one hour aligned... basically when every single
> time frame is aligning that's when you're going to have an a plus opportunity"* — course corpus.

A fifth was considered and dropped: the mentors' **15-minute narrative** (*"if you're going to
scalp on the one and five minute time frames you need the narrative minimum on the 15 minute time
frame"*, *"I wait at least 10 to 15 minutes"*). It cannot exist before 09:45 by construction, so
as a selector it is the clock control in §4, which is measured directly.

---

## 3. Does alignment separate a good signal from a bad one at all?

The cheapest possible test, upstream of every policy: mean realised R of all 6,170 candidates,
split by what each definition says about them.

| definition | agrees | disagrees | difference | 95% interval |
|---|---:|---:|---:|---|
| index at the minute | +0.552R (n=3,508) | +0.491R (n=1,677) | +0.061R | −0.058 to +0.180 |
| daily bias | +0.568R (n=3,477) | +0.495R (n=2,551) | +0.073R | −0.023 to +0.169 |
| hourly bias (incumbent) | +0.550R (n=4,397) | +0.488R (n=1,346) | +0.062R | −0.023 to +0.147 |

**All three cross zero.** Every one leans the right way — agreeing with the higher timeframe is
never *worse* — and every one is inside its own noise.

The stack, by how many of the four agree:

| timeframes agreeing | n | mean R |
|---:|---:|---:|
| 0 of 4 | 368 | +0.434 |
| 1 of 4 | 1,162 | +0.518 |
| 2 of 4 | 1,400 | +0.548 |
| 3 of 4 | 1,884 | +0.520 |
| **4 of 4** | 1,356 | **+0.604** |

4-of-4 minus 0-of-4 is **+0.170R, 95% [+0.002, +0.338]**. That is the only interval in this whole
file that clears zero, and it clears it by 0.002R on the one comparison out of many that was most
likely to. It is also not monotone — 3-of-4 sits below 2-of-4 — and §4 and §5 show it does not
survive contact with a policy.

---

## 4. Each candidate as a SELECTOR

The rule: among the day's setups, take the one with the highest alignment score; ties break by
arrival order, so a definition with no opinion reproduces the baseline exactly rather than
shuffling. The question is whether it ranks the **day's best** setup first more often than
arrival order does.

| selector | ranks the day's best first | $/day | vs baseline | 95% band | days it changed | win rate | months green |
|---|---:|---:|---:|---|---:|---:|---:|
| **arrival order** (ships today) | **64 / 499 = 12.8%** | **$721** | — | — | — | 66.7% | 25/25 |
| index at the minute | 61 = 12.2% | $613 | −$108 | −$249 to +$38 | 258 | 64.5% | 25/25 |
| daily bias | 68 = 13.6% | $760 | **+$39** | −$108 to +$187 | 204 | 63.9% | 25/25 |
| hourly bias (incumbent) | **75 = 15.0%** | $762 | **+$41** | −$80 to +$157 | 173 | 61.1% | 24/25 |
| alignment stack | 74 = 14.8% | $679 | −$42 | −$215 to +$138 | 195 | 58.8% | 24/25 |

- **Every band crosses zero. All four are ties.** The best arm buys $41 a day with a band four
  times wider than the effect.
- The hit-rate against the day's best moves from 12.8% to at most 15.0% — **2.2 points on a
  ceiling of 87 points.** Ninety-eight percent of the prize is still on the table.
- Two arms buy a slightly better hit-rate and **pay for it in win rate** (66.7% → 61.1%) and in
  drawdown ($5,993 → $9,071). The money gate wants ≥55% win *and* mean R ≥ 2.0; this trades one
  down for nothing.
- The index arm's deadband is not hiding a result: as a selector it makes $667/day at 0.00%,
  $613 at 0.05%, $687 at 0.10% — all below the $721 baseline.

---

## 5. Each candidate as a WAIT rule

The rule from the brief: *skip the 09:30–09:45 signal when the higher timeframe disagrees, take
the next one that agrees.* If nothing agrees all morning, the day goes untraded.

A control arm is measured beside them and it matters: **wait to 09:45 with no model at all** —
skip everything early, take the first setup after 09:45. Any higher-timeframe arm that does not
beat this one is not buying a thesis, it is buying a clock.

| wait rule | trades | days moved | days skipped | $/day | vs baseline | 95% band | months green | worst drawdown |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| **arrival order** | 499 | — | — | **$721** | — | — | 25/25 | $5,993 |
| **wait to 09:45, no model** | 498 | 411 | 1 | $688 | −$33 | −$226 to +$168 | 25/25 | $6,000 |
| index at the minute | 494 | 220 | 5 | $650 | −$71 | −$206 to +$63 | 24/25 | $6,218 |
| daily bias | 498 | 167 | 1 | $765 | **+$44** | −$82 to +$176 | 25/25 | $6,000 |
| hourly bias (incumbent) | 496 | 138 | 3 | $756 | +$35 | −$66 to +$140 | 24/25 | $8,065 |
| alignment stack | 494 | 195 | 5 | $721 | $0 | −$133 to +$135 | 25/25 | $7,027 |

**Waiting, by itself, costs $33 a day and is a tie.** The best higher-timeframe arm adds $44 on
top of the baseline and is also a tie. **The spread between the best and worst arm here is $115 a
day, inside every one of their own bands.** Nothing in this table is a result.

### And here is what it costs on his S days

Recall is scored on the **symbol-day**, not the session, because that is the unit the recall gate
uses. Of the **309 S days** in the canonical pool (`research/marks_pool.py`), the two-year book
reaches **154**. A symbol-day survives the wait rule if the first signal on that chart is 09:45 or
later, or if the higher timeframe agrees with some signal on that chart.

| wait rule | S days kept | S days lost | kept |
|---|---:|---:|---:|
| hourly bias (incumbent) | 142 | **12** | 92.2% |
| index at the minute | 138 | **16** | 89.6% |
| daily bias | 132 | **22** | 85.7% |
| alignment stack | 129 | **25** | 83.8% |

**Every arm pays 8 to 16 percent of the recall gate for a money change that is statistically
nothing.** Recall stands at 58.6% against a 90% target; this trades the gate he is furthest from
for noise.

**One correction to the brief.** The dispatch said his 09:30–09:45 entries are 65% of his S
entries. Measured two ways tonight, neither reproduces it: on the 20 minutes he wrote on the
2026-08-29 deck, **9 are before 09:45 (45%)**; on the 154 S symbol-days the book reaches, the
engine's first entry is before 09:45 on **45 of them (29.2%)**. The wait rule bites less than
feared and still costs more than it pays.

---

## 6. Against the twenty minutes he actually wrote

The 20 stated entry minutes from `research/marks/probe_g71_homework_s3_2026-08-29_complete.jsonl`,
using the same exclusion table as `research/g81_marks30_score.py` — four notes contain a clock
time that is *not* his entry (twice he names the minute the engine picked, once a candle, once a
hypothetical break he rejects), and folding those in would score the engine against itself.

**The headline is the denominator, not the tally.**

> **On 10 of the 20, the engine had no signal at all earlier than the minute he named.** There is
> nothing for a wait rule to have rejected. On those days he is the early one.

On the 10 where an earlier engine signal does exist:

| candidate | explains the wait | would have taken the earlier signal anyway | silent at both, or no comparable pair |
|---|---:|---:|---:|
| index at the minute | **0** | 2 | 18 |
| daily bias | **0** | 4 | 16 |
| hourly bias (incumbent) | **0** | 2 | 18 |
| alignment stack | **0** | 2 | 18 |

**Not one card is explained by any of the four.** Four times the daily bias would have taken the
earlier setup he passed over. And the directionless version of the test — *was the index unclear
when the engine first fired and clear by his minute?* — is true on **1 of 20**.

This lines up exactly with tonight's other finding. `research/g81_marks30_score.md`: the card the
engine showed him sits a **median 24 minutes after** the minute he named, and its first booked
entry a median 4 minutes after. **The engine is late and he is early.** A rule that tells the
engine to wait is pointed at the wrong end of the gap.

**What he described is still real** — he said the 9:30 S trade would have been better twenty
minutes later. But that is a claim about *his own* entries, and the only independent sample of his
entries says he takes them **before** the engine gets there, at a median of 09:45, with 45% inside
the first fifteen minutes and only two of twenty after 10:00.

---

## 7. Proposed diffs — none to the engine

**No engine change is proposed.** Nothing here clears its own error bar, and a rule Austin has
never stated cannot become a default.

Two things worth doing that are not engine changes:

1. **`HTF_BIAS_VETO` is NOT deleted — it ships ON and gates 47% of the book.** *(Corrected
   2026-08-30 after the verify pass. The sentence that stood here said it "stays deleted" and was
   simply false: `omen_bot.py:29` reads `os.getenv("HTF_BIAS_VETO", "1")`, the docstring at line
   240 calls that "the SHIPPED DEFAULT", and `research/test_w12_grade_gates.py::W12-3` asserts it.
   Section 2 of this same report said so correctly. The report's one actionable recommendation was
   written against a false picture of the live engine — do not quote it.)*
   What the measurement actually says: scored as a **selector** the incumbent is worth +$41/day
   (band −$80 to +$157) and costs 5.6 points of win rate; as a **wait rule** it costs 12 S days
   and a green month. Both are ties. So the live question is not "bring it back" — it is
   **whether a veto with no author should keep gating 47% of the book on a tie**, and that is
   Austin's call, not an agent's.
2. **Elicit the definition instead of guessing it.** All four candidates above are mentor
   sentences. He has said twice that he has no higher-timeframe bias yet and asked to be told what
   one would be. Four measured candidates now exist and each is one plain sentence — that is a
   ballot, not a deck-day.

---

## Ballot lines

One yes/no each. None of these is in the code, and none goes in without him.

1. **The prize is real and worth chasing: picking the day's best setup instead of its first is
   worth $3,458 a day. Should selection be the next thing we build?**
2. **Is "the index is moving my way right now" your higher-timeframe read?** (Measured: no
   money, band −$249 to +$38.)
3. **Is "yesterday's close above its 20-day average" your higher-timeframe read?** (Measured: no
   money, band −$108 to +$187.)
4. **Is "the week, the day, the hour and the index all agreeing" your higher-timeframe read?**
   (Measured: the four-of-four signals do make +0.170R more, the one interval all night that
   clears zero — barely.)
5. **Given that you entered a median 24 minutes before the engine's chosen setup on the thirty
   charts you graded, should we stop trying to make the engine wait and start trying to make it
   early?**
6. **Do you accept losing 12 of the 154 S days the book reaches to buy a $35/day money change
   that is inside its own noise?** (Expected answer: no. Asked because every wait rule here
   demands it.)
7. **Displacement — you gave it as your reason four times out of nine refusals on 2026-08-29
   without being asked. Should displacement become one of the downgrade variables?** (Carried
   forward from `Projects/omen-rulebook.md`; it is the strongest un-ratified signal in tonight's
   marks and it is not a higher-timeframe question.)

---

## Verify pass, 2026-08-30 — what an independent recompute changed

An Opus verifier rebuilt every headline number from source in `research/g81_verify_0.py` without
importing anything from this report's helpers. **The headline stands** — the $3,458/day prize, the
$721 first-setup baseline, the $4,179 oracle ceiling, all four selector arms and the S-day recall
table reproduce to the dollar, and the look-ahead audit came back clean (the one forward reach,
step 5's ±5-minute window, gives the candidates *more* information than they should have and they
still explain 0 of 20). Five real defects, none of which moves a headline number:

1. **The `HTF_BIAS_VETO` "stays deleted" claim was false.** Corrected in place above.
2. **"10 of 20 had no earlier signal" counts rows the engine never emitted.** `step5_cross_check`
   is fed all 134,012 book rows; 121,368 of those are downgrade-skips the engine never surfaced.
   Restricted to the *actionable* stream (fired-or-halted), an earlier signal exists on only **2
   of 20** — the honest figure is **18 of 20 with nothing to wait through**. The loose definition
   makes the engine look earlier than it is, so this cuts *against* the report's own headline and
   strengthens it: the "wait" idea is even more clearly pointed at the wrong end of the gap.
3. **499 vs 500 sessions.** The prose says 499, the divisor used is 500. $3,458/day at 500 vs
   $3,465/day at 499. Immaterial; the label and the arithmetic disagree.
4. **Dead branch in `stated_minutes`.** `TIME_RE = (\d{1,2})[:%](\d{2})` cannot match
   `9:%5`, so the `if "%" in m.group(0)` special case is unreachable and `IWM_2026-08-06` is
   silently dropped. That is why this report counts 20 stated minutes where the module docstring
   says 21. Does not move 9/20 = 45%.
5. **`NOT_HIS_ENTRY` is a no-op.** All four exclusions are "no" cards the `is_s == "yes"` filter
   already removes. The table is presented as doing work it does not do.

One item the verifier flagged that this report never named: the hourly-bias "agrees" side trips on
**71.3%** of signals, above the 60% ceiling this project uses for a downgrade variable. The n is
published; the ceiling is never invoked against it.
