---
date: 2026-09-03
status: draft
type: onboarding
priority: high
version: 1.0.0
---

# AUGUR's understanding of your trading system

Forty statements, in AUGUR's own words, of what your system is — read from `omen-rulebook.md`
(your rules, each with the sentence you said it in), `AUGUR.md` (the daily loop and the
2026-09-03 rulings), `omen-decks.md`, `MORNING_REPORT.md` §3 (what your marks say), the
mark-file ledger, `research/g92_*` (77 claims decoded from your marks), `omen-blockers.md`'s
"Already settled" table, and `CORPUS.md` / the `omen-corpus` mentor archive (Scarface,
jdub, Discord, Circle — never a rule source, only a validator).

**How to read a statement.** Each one has three parts: the claim in plain English, the source
it traces to, and a confidence tag.

- **settled** — you said this, in these words or close to them, on a specific date.
- **measured** — a number counted from your marks or the real book, not a sentence you spoke.
- **inferred** — AUGUR pieced this together across several of your marks. You have never
  ratified it as a rule. **These are the ones most worth your correction.**

30 are settled, 3 are measured, 2 are inferred — 5 of the 40 are not your own words, and
those are flagged individually below, not just in this count.

The companion homework page is `research/probes/augur-understanding.html` — same 40
statements as tap cards: right / wrong / partly, plus a box to correct AUGUR where it's wrong.

---

## Setups (6)

**S1. Break-and-retest is your bread-and-butter setup: price breaks a level, then comes back
to retest it before you take the trade.**
Source: constant across the rulebook and the corpus — 947 of 1,017 traded rows in the two-year
book are break-and-retest (`omen-rulebook.md`, "Kill B and A+ outright", 2026-08-29).
Confidence: **settled**.

**S2. The one-candle rule (OCR) is your name for an order block: one candle the opposite
color of the trend, that price is expected to respect, then break, and retest.**
Source: *"i forgot my OCR definition is simple, it's in the name 'one candle' — one candle
that's the opposite color of the way it's trending."* — Austin, 2026-08-23.
Confidence: **settled**.

**S3. An OCR candle only counts if it would work as the stop — the test is "would the candle
be good to use as the stop?", not how big or clean the candle looks.**
Source: `omen-rulebook.md`, card 11, ratified "Round two", 2026-08-28.
Confidence: **settled**.

**S4. The 84% rule is a re-entry modifier that fires after a stop-out, not a standalone
setup — it re-enters the price you originally entered on (not just the level), on a candle
close that reclaims it.**
Source: rule ballot batch01 q12/q13 — Austin, 2026-08-23.
Confidence: **settled**.

**S5. Break-and-retest with an OCR at the same level (BR+OCR) is its own third setup, and it
is worth a +1 upgrade to the grade — not just a rebate against a downgrade.**
Source: *"remember BR and OCR is also a setup when both of them are together"* and *"we also
need to work BR and OCR as +1 upgrade not downgrade confluence."* — Austin, 2026-08-29.
Confidence: **settled**.

**S6. Order block is a setup family you rate highly — 9 of 12 tagged cards graded S — that the
engine currently has no detector for at all: a coverage hole, not a weak signal.**
Source: `research/MORNING_REPORT.md` §3 HINTS ("Order block is your highest-conviction claimed
setup").
Confidence: **measured** (n=12, thin — flagged as a hint in its own source).

---

## Levels (4)

**L1. The six levels you break, retest and target are PDH, PDL, PMH, PML, ORH, ORL — the
opening range counts, HOD and LOD do not.**
Source: *"the level confusion was probably me, the 6 levels have always been correct."* —
Austin, 2026-08-29 (superseding an earlier answer the same day that named HOD/LOD instead).
Confidence: **settled**.

**L2. Pivot-structure levels can be drawn on a chart for context, but they never gate an
entry, a stop, or a target.**
Source: *"only the 6 levels, but you can still visualize those pivots."* — Austin, 2026-08-29.
Confidence: **settled**.

**L3. PDH and PDL are good levels to trade, full stop — even though a measured backtest found
avoiding them adds real edge, you ruled that a flag to watch, not a rule to ship.**
Source: *"PDHPDL are good levels."* — Austin, 2026-09-03 evening (`AUGUR.md`, "Rulings
2026-09-03, evening").
Confidence: **settled**.

**L4. There is no higher-timeframe bias rule in your system today — you've said twice you'd
need to be told what one even means, so nothing gets to veto a trade on "the higher timeframe
disagrees."**
Source: *"we dont have any higher timeframe bias yet youll need to tell me what that is
then."* — Austin, ballot batch02 c6, 2026-08-27.
Confidence: **settled**.

---

## Entry (4)

**EN1. You enter as the candle is forming, not waiting for its close — especially near
HOD/LOD, so you don't pay a bad price.**
Source: *"as candle forming not lod/HOD"* — a note that recurs across the mark corpus (14 of
58 graded note fields, per `OMEN.md:124`); most recently *"candle close for most, some as
candle forming so i dont get a bad fill at high of day"* — Austin, 2026-08-30.
Confidence: **settled** (restated 20+ times across the corpus).

**EN2. That forming-candle entry is not a separate rule — it belongs to ON WATCH, the state
where the engine watches a level mid-bar instead of waiting for the close.**
Source: *"it should exist already its called ON WATCH... it had to do with on watch and mid
candle entries."* — Austin, 2026-08-28/30.
Confidence: **settled**.

**EN3. Most entries are fine waiting for the close — the early-entry exception exists
specifically for setups running toward the high or low of day, where waiting would wreck the
risk-reward.**
Source: *"most entries work at candle close, but some that are close to hod, you want to get
a good fill and not one that will have bad RR."* — Austin, ballot batch02 b3, 2026-08-27.
Confidence: **settled**.

**EN4. Earlier in the day is better, and you'd rather end the day early — the earliest S setup
usually has the best odds, though you've named one exception: a later setup with a materially
better target can beat an earlier one.**
Source: *"a golden rule the earlier in the day you trade, the more common it is for S trades
and higher probability. you want to end the day early."* — Austin, 2026-08-28; exception from
*"sometimes we dont want to take the earliest s because..."* — Austin, 2026-08-29.
Confidence: **settled**.

---

## Stop (5)

**ST1. A stop triggers on the candle's CLOSE beyond the level — a wick through it, alone,
does not take you out.**
Source: rule ballot batch01 q1 — Austin, 2026-08-23; reaffirmed *"stop losses are candle close
you're right"* — Austin, 2026-08-30.
Confidence: **settled** (restated at least thirteen dated times, per the rulebook's own
count).

**ST2. The hard floor on any one loss is −1R — the earlier −1.25R disaster-stop clamp has
been dropped for a simpler number.**
Source: *"1R is simpler so why not go with that? no stocks should be running to −10R"* —
Austin, 2026-09-03 evening (`AUGUR.md`, "Rulings 2026-09-03, evening").
Confidence: **settled**.

**ST3. A break-even stop is close-based too, not wick-based, and because it fills at that
close it can book a small loss instead of landing at exactly zero.**
Source: `omen-rulebook.md`, "Break-even slippage — same rule as the initial stop," 2026-08-28.
Confidence: **settled**.

**ST4. The stop is picked per-trade from three structural candidates — the wick of the OCR,
the candle you entered on, or the level that broke on a break-and-retest — whichever gives the
best tradable risk-reward, with a disaster stop underneath.**
Source: *"stops go where they make sense... wick of OCR, candle entered on, break and retest
of a level stop loss that level."* — Austin, 2026-08-29.
Confidence: **settled**.

**ST5. AUGUR infers you don't have one fixed answer for wick-vs-level on a stop: your own
marks name three different anchors on three different cards (a candle's body, its low, its
wick), and you've called the tension genuinely unresolved.**
Source: *"if its tight and you have to chose the wick or the level, choose the wick"*
(AMZN 2026-01-14) vs. *"those 3 green candles even though i dont like bodies that wouldve
been a better stop"* (NVDA 2024-09-03) vs. *"stop body of opening range"* (GOOGL 2024-10-15) —
`research/g92_master_spec.md`, Contradictions §5.
Confidence: **inferred**, n≈6 cards. **Never stated by you as one rule — worth your
correction.**

---

## Target and exits (5)

**EX1. The target isn't a flat 2R — it's the next real structural level (a PDH/PMH/whole
dollar), with 2R used as the fallback only when nothing else sits close.**
Source: *"its about sizing for the mean 2rr, so if there are no other levels to target...
harder to trade."* — Austin, ballot batch02 b4, 2026-08-27; ratified as "the target is the
next structural level, not 2x risk," 2026-08-28.
Confidence: **settled**.

**EX2. Your stated scale-out ladder is 30% off at HOD (LOD on puts), 30% at 2R or the nearest
of your six levels, 30% on a break of trend/structure, and a 10% runner trailed to
break-even.**
Source: *"scalling 30 HOD, 30, 2r or nearest level, other 30 break of trend/structure/10
runner stop loss break even."* — Austin, 2026-08-29.
Confidence: **settled** (his stated numbers; not yet what the shipped code runs).

**EX3. One trade a day is the actual goal: you take the first S setup that shows up, and if
it wins, you're done for the day.**
Source: *"we trade the s trade that comes up first, and if it wins, were done for the day."*
— Austin, 2026-08-29.
Confidence: **settled**.

**EX4. The two-loss-halt question was left open on purpose, and the answer that came back:
three losses ends the day, with a −$2,000 floor — not the two-loss rule you first mentioned,
once the money showed a trade taken after two losses still profits on average.**
Source: *"we dont know if 2 losers in a row is a stopping point, keep trading s trades until
youve hit profit... 2 consecutive halts is bad, but overtrading is too, subagents will find
the medium"* — Austin, 2026-08-29; resolved same day, `omen-rulebook.md` "The day rule —
settled."
Confidence: **settled**.

**EX5. Green weeks are a target you watch — 87% — not a hard constraint the whole strategy
has to bend around, since chasing 100% costs most of the income.**
Source: *"87% is the target, keep the money."* — Austin, 2026-08-29.
Confidence: **settled**.

---

## Grading (6)

**GR1. Your grade is arithmetic, not a feel call: S is clean, A is one tripped downgrade, C
is two — S minus downgrades plus a confluence bonus, floored at C once three or more
variables trip.**
Source: *"S = clean. A = one variable downgrade. C = two variable downgrades."* — Austin,
2026-08-23; floor rule from Q&A batch 04, 2026-08-28.
Confidence: **settled**.

**GR2. Confluence — BR+OCR together, or price on the right side of most of the levels you
watch — is worth one upgrade point, capped: the two upgrade paths don't stack, and you've
called confluence rare, under 1 in 5 setups.**
Source: ballot batch02 b5, 2026-08-27; *"rare, under 1 in 5"* — Austin, 2026-08-24/28.
Confidence: **settled**.

**GR3. Nine variables can cost a grade: no displacement, a stale retest, a level not being
respected, an exhausted stock, disrespected counter-trend candles, a break that got rejected,
no retest at all, an OCR not honored, and — added later — an oversized red-body candle
sitting inside recent chop.**
Source: `omen-rulebook.md`, "The downgrade list — settled 2026-08-23" plus ballot batch02 b6.
Confidence: **settled**.

**GR4. AUGUR reads chop — closing at, or chopping around, a level instead of reacting off it
— as your sharpest tell between an S day and a refusal: it shows up in 2% of your S-day notes
against 20% of your non-S notes, a 10x gap.**
Source: `research/MORNING_REPORT.md` §3, "Chop is the discriminator" (n=295 S-day notes,
453 non-S notes).
Confidence: **measured**, from your own marks — not a sentence you've said this way.

**GR5. C is graded and logged for the record, but never surfaced as an alert and never
traded — only S ever gets traded.**
Source: *"i dont need physical alerts, its just to collect data. the priority is always S."*
— Austin, Q&A batch 04, 2026-08-28.
Confidence: **settled**.

**GR6. AUGUR infers displacement is not a hard requirement for S but one of several
substitutable signals — displacement, an OCR holding, a wick reclaim of the level, strong
price action, or being early with an HTF read — because you have both demanded it flatly and
graded S trades that had none.**
Source: *"just always need that displacement for S trades"* (rule ballot, rule_03) against
*"9:46 as candle forming above ORH, no displacement but 9:30 ocr wick confluence with pmh"*
(NVDA 2025-06-03, graded S) and two more S grades carrying no displacement —
`research/g92_master_spec.md`, Contradictions §2.
Confidence: **inferred**, n≈20 cards across three separate homework sections. **You have
never been asked whether displacement should be one variable among several — worth your
correction.**

---

## Instrument and sizing (4)

**IN1. All three instruments — options, shares through a prop firm, and futures — stay open;
nothing has been narrowed to just one.**
Source: *"Option one is fine... Index and futures is a good option too, so leave options
open."* — Austin, 2026-08-30.
Confidence: **settled**.

**IN2. Position size is meant to come from whichever prop firm's own drawdown rules you're
trading under, not from a dollar figure you're personally comfortable with.**
Source: *"the way i would decide risk per trade now is based on the prop firm im going to be
using, read its rules and what makes sense for my strategy and profit goals."* — Austin,
2026-08-29.
Confidence: **settled**.

**IN3. The near-term prop target is Vanquish Trader's $50k Advanced Options plan: a 10%
profit target, a 5% end-of-day trailing drawdown, a 4-day minimum, and a 100% profit split
once funded — the only fee-based evaluation found that permits options, and the engine is
meant to fire separately for whichever firm you're under.**
Source: `AUGUR.md`, "Decided 2026-09-03" and its Research section (verified against Vanquish's
own pages; underlyings and same-day expiry unconfirmed); *"the trading bot would need to have
its separate firing that works with the prop firm stocks"* — Austin, 2026-09-03.
Confidence: **settled**.

**IN4. AUGUR infers a $1,000 account cannot actually run this in options: on real option
prices, one contract is the whole sizing grid, and a typical stop cannot be bought at 1% of
$1,000 — the arithmetic needs roughly $12,000 before one contract matches what a prop
evaluation would allow you to risk.**
Source: `research/MORNING_REPORT.md` §5, "The $1,000 question" (priced against 276 real
Alpaca 0DTE ATM option prints).
Confidence: **measured**, derived from real option prices — not something you've stated.

---

## What he has refused (6)

**RF1. The legacy A+/A/B/C/X engine grade ladder is dead — you've never used it and have said
so more than once; only your own S/A/C/none ladder counts anywhere a number is reported.**
Source: *"a+ shouldnt exist. a+ and b shouldnt exist if they do."* — Austin, 2026-08-28
("the fifth time of asking," per `omen-rulebook.md`, 2026-08-29).
Confidence: **settled**.

**RF2. Nobody gets to refute your S marks — they're ground truth backed by real work, and a
report may say the engine's own label disagrees with you, but never that your judgement was
wrong or noisy.**
Source: *"you cant refute my s marks they are important and hard work and stats have been
backing them up."* — Austin, 2026-08-28.
Confidence: **settled**.

**RF3. A symbol-day you've already graded must never be shown to you again — even being
served the repeat counts as wasting your time, whether or not you re-grade it.**
Source: *"i never want to see stock repeats of stocks i have already graded, beacuse how is
that worth my time?"* — Austin, 2026-08-29.
Confidence: **settled**.

**RF4. A stop too tight to survive real spread and slippage is not a valid stop, no matter
how good it makes the backtested R look — "robot-tradable" is a hard constraint, not a
nice-to-have.**
Source: *"i want trades that can realistically be done by a robot and where it wont get
killed or destroyed by fills or too tight rr."* — Austin, 2026-08-29.
Confidence: **settled**.

**RF5. FVG and flag patterns stay computed in the code but never gate a trade and never get
counted as one of your setups — you keep them visible without trading them.**
Source: *"sure keep fvg and flag but they are not setups i trade and they dont do anything im
sure."* — Austin, 2026-08-29.
Confidence: **settled**.

**RF6. You've refused to widen the graded set past QQQ, SPY and TSLA for now, and refused to
re-open the 47 extra low-confidence rows from old chat mining just to grow the S-day count —
not because they're wrong, just not the best use of your time right now.**
Source: Q&A batch01 defaults (*"no, that is OMEN 7"* / *"No. Gate on 154"*) — Austin,
2026-08-23/24; `omen-blockers.md`, "Already settled" table.
Confidence: **settled**.

---

## Tally

| group | statements |
|---|---:|
| Setups | 6 |
| Levels | 4 |
| Entry | 4 |
| Stop | 5 |
| Target and exits | 5 |
| Grading | 6 |
| Instrument and sizing | 4 |
| What he has refused | 6 |
| **Total** | **40** |

| confidence | count |
|---|---:|
| settled | 35 |
| measured | 3 |
| inferred | 2 |

The 5 that are not your own words (3 measured, 2 inferred): S6 (order block coverage), GR4
(chop as discriminator), IN4 ($1,000-account arithmetic) are measured from your marks or real
prices; ST5 (wick vs. level) and GR6 (displacement as substitutable, not required) are AUGUR's
own synthesis across contradicting cards and have never been asked of you directly. Those two
are the ones most worth a wrong or partly tap.
