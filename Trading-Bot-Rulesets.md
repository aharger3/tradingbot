# Trading Bot Rulesets — Scarface Trades Framework

**Created:** 2026-05-16  
**Source:** Austin's actual Zella trades + Scarface Trades framework  
**Status:** Foundation for bot automation

---

## Setup 1: Break and Retest (Opening Range)

**What it is:** Price breaks above/below the opening range (first 5-min candle), then retraces back to that level. Bot enters on the retest.

### Entry Conditions
- Identify the 5-minute opening range (first candle of the session, or defined range)
- Wait for price to **break** above the high or below the low with volume/momentum
- Wait for price to **retest** the breakout level (come back and touch it)
- Enter on the retest (when price bounces off the level again in direction of breakout)
- **Confirmation:** Higher timeframe (HTF) trend should align with breakout direction

### Exit Conditions
- **Profit target:** 10:1 risk/reward minimum (mentioned by Austin as important)
- **Stop loss:** Below the retest level or below the opening range low (depending on direction)
- **Time-based:** If setup hasn't triggered by end of day, close position
- **Early exit:** If price moves against you before proper retest, cut immediately

### Risk Management
- Position size: Based on distance to stop loss (fixed risk per trade)
- Max loss per trade: Calculate based on account size
- Don't be too stubborn: Exit if setup breaks before reaching target (Austin's lesson from TSLA)
- Get good fills: Better entry = smaller risk

### Real Example (Austin's Zella Trade)
- TSLAswing from prior day, HTF looked good
- Sold exact bottom, price rallied to ATH
- Mistake: Sold too early, didn't trust the HTF signal
- Chart shows: Opening range break, retest entry point, proper stop/target placement

---

## Setup 2: 5-Minute Opening Range (84% Rule Related)

**What it is:** The 84% rule is **not a standalone entry**. It is the re-entry you
take *after a losing trade* — a stopped-out break-and-retest, a stopped-out one
candle rule, or both — when the original thesis was right but the stop was wrong.

**VOID (2026-08-09):** the old text below claimed the 84% rule was a standalone
entry on the break of the opening range — *"Once broken, price tends to not
return, so entry on break is high probability."* That is wrong. Austin's ruling:
the 84% rule can never happen by itself; it is only taken after a loser from
break-and-retest, the one candle rule, or both.

### Entry Conditions
- A prior break-and-retest OR one-candle-rule trade was stopped out (this is what
  arms the 84% re-entry — a fair-value-gap or flag loser does **not** arm it)
- Wait for price to close back at or above the price where you originally entered
  (long) / at or below it (short) — the predicament is *correct thesis, wrong stop*
- Take the trade on that reclaim close

### Exit Conditions
- **Stop loss:** leave the stop where it was, or move it to where it makes the most
  sense (a new level, a pivot structure). The thesis is still correct — you keep
  the trade, you just fix the stop
- **Profit target:** ride the momentum toward the original target / market structure

### Risk Management
- This is a re-entry, not a fresh position — it exists because the idea was right
  and the stop was wrong, not because a new edge appeared
- The stop placement is the whole point: keep it where it was, or improve it on
  real structure; do not widen it to force the trade

### Key Learning from Austin
- NVDA trade: "small winner" — needed to aim for at least 10% RR
- Setup was good but needed better execution (fills, exits)
- Good calls at 9:45 would have been the better move (timing matters)

---

## Setup 3: One Candle Rule

**What it is:** Austin, 2026-08-07 — *"you mark the downclose candle in an uptrend and price respects it, or vice versa."*

That is the order block, and `detect_order_block_setup` (`omen_bot.py`) is its
implementation. The candle that closed against the trend just before the move is
the zone; the rule is that price coming back to it *respects* it.

### Entry Conditions
- Uptrend: mark the last **down-close** candle before the structural higher high (mirror for a downtrend: the last **up-close** candle before the lower low)
- Price comes back to that candle's zone and respects it — the retest must be a **wick only**, not a close inside the body (`OB_RETEST_TYPES = ("wick_only",)`)
- Entry on the candle that closes back beyond the block (long: close > block high; short: close < block low)

### Exit Conditions
- Stop at the far side of the block — the block low (long) / block high (short)
- Target 2R, per the house rule

### Risk Management
- A-grade with a tight stop only. The 12mo split (2026-07-10) put B-grade at 19% win / −$13k and wide stops 0-for-11 / −$10k, so B is demoted to alert-only and a stop wider than 0.4% of entry is skipped outright.

**Note on labelling (omen-3.7 T5):** `SignalType.ONE_CANDLE_RULE` now means this
setup and only this setup. Fair-value-gap entries and flag breakouts used to
share a label with it, which made every per-setup win rate untruthful; they now
carry `SignalType.FAIR_VALUE_GAP` and `SignalType.FLAG`.

---

## Setup 4: 84% Rule (Full Details)

**What it is:** The 84% rule is the re-entry you take after a losing trade when the
thesis was right and the stop was wrong. It is **never a standalone entry** — it
only fires off a stopped-out break-and-retest, a stopped-out one candle rule, or
both.

**VOID (2026-08-09):** the old text below described the 84% rule as a standalone
entry on the break of the opening range — *"When opening range (first 5 minutes)
breaks, 84% of the time price doesn't return inside that range ... a statistical
edge that can be mechanically traded."* That is wrong, and it is the doc-vs-code
conflict that has been open since 2026-08-07. Austin's ruling: the 84% rule can
never happen by itself; it is only taken after a loser from B&R, the one candle
rule, or both. When a candle closes at or above the same price where you
originally entered, take the trade and leave the stop where it was, or where it
makes the most sense (a new level, pivot structure) — because the predicament is
*correct thesis, wrong stop.*

### Core Principle
- The 84% re-entry exists for one situation: you were right about direction, but
  your stop got hit. Price then closes back through your original entry price.
  The thesis is still alive, so you re-enter — you do not abandon the idea
- It is armed *only* by a stopped-out break-and-retest or one-candle-rule trade.
  A fair-value-gap or flag loser does not arm it

### Entry Conditions
- A break-and-retest or one-candle-rule trade was stopped out (arming)
- A candle closes at or above the original entry price (long) / at or below it
  (short) — the reclaim that says the thesis was right, stop was wrong
- Re-enter on that close

### Exit Conditions
- **Stop loss:** leave the stop where it was, or move it to where it makes the
  most sense — a new level, a pivot structure. Keep the trade, fix the stop
- **Profit target:** the original target / market-structure target

### Risk Management
- Re-entry, not a new edge — size and intent follow the original trade, not a
  fresh setup
- The stop is the decision: keep the old one or improve it on real structure;
  do not force the trade by widening the stop

### Attempt count
- **The 84% rule takes 2 attempts, not 3.** After two stopped-out entries on the
  same idea the thesis is no longer "correct, wrong stop" — it is wrong — so a
  third reclaim does not arm another re-entry. Evidence: `CRM_2024-11-11_14`.

### Reclaim speed
- **Reclaim speed** demotes. A reclaim that takes a long time is not the same
  trade as a fast one: the 84% reclaim is an automatic S only when it snaps
  back, and a slow, late reclaim is graded down. Austin graded
  `AMD_2026-05-14_67` an A — *"late + slow to develop"* — despite the rulebook
  calling a reclaim an automatic S. A slow reclaim is an A, not an S.

---

## Austin's Trading Rules (verbatim from his notes)

These are rules Austin repeats in his notes because they were not written down
anywhere in the rulebook. Each is its own numbered clause, in his words, with the
mark ids that establish it.

1. **Stop-outs happen on the close, not the wick.** A trade is stopped out only
   when a candle *closes beyond the stop level*. A wick through the stop is not a
   stop-out — the trade stays on until a bar closes past the stop. Evidence:
   `MSTR_2024-09-26_11_14`, `MSTR_2024-03-20_73_78`, `MU_2026-02-09_24_36`,
   `PLTR_2025-12-10_45_52`, `MSFT_2024-01-25_52_70`, `NVDA_2026-02-05_48_52`.

2. **Entry is the close, except on an extreme close.** Normally enter on the
   candle close. When a fast candle would close at the session high (long) or
   low (short), enter intrabar at the level instead — *"you want it to look like
   it will close above that."* If the bar then closes back beyond the level,
   scratch out at that close; a scratch is not a loss and does not arm the 84%
   rule. Evidence: the 10 *"enter as the candle is forming / closing"* notes,
   `AMD_2025-03-28_31`.

3. **Nothing is traded outside 09:30–11:00**, and that includes the 84% reclaim
   leg — a re-entry is an entry. No new position, and no reclaim re-entry, fires
   outside the 09:30–11:00 window. Evidence: `INTC_2025-02-27_72_153`,
   `PLTR_2024-01-02_196`, `NVDA_2024-01-03_98`, `AMD_2025-10-14_75_137`.

4. **Do not enter at the session extreme.** Distinct from the existing
   `BAR_EXTREME_FRAC` clause (clause 2 of the tiers), which measures position
   *inside the signal candle*. This one measures distance to the day's high/low
   so far and is a **veto, not a demotion** — an entry sitting on the session
   HOD/LOD is not taken regardless of grade. Evidence: 21 HOD/LOD notes
   including `MSFT_2024-01-25_52_70` (*"get a better fill not at HOD"*),
   `AMD_2025-03-28_31`.

---

## Rule 7: Speed of the Retest

**What it is:** Austin, dictation — *"ideally the break and retest happens as soon as possible ...
if it takes too many candles probability decreases."* A level that is broken and reclaimed in the
next couple of candles is the setup; the same level wandered back to twenty candles later is a
different, worse trade that happens to end up at the same price.

This rule sat in the rulebook for months with nothing behind it, and when
`research/rule7_rule10.py` finally measured it the reason became obvious: the feature it built,
`bars_break_to_retest`, counts bars from **the break candle** to the first candle whose wick
returns to the level, and the break candle is a bar whose *body closed across* the level. On
Austin's 159 marks that bar does not exist 56 times (35.2%), and a further 20 marks have a break
but no returning wick before entry — so the feature is `null` on **76 of 159 marks (47.8%)**
(`research/rule7_rule10.md`). A rule the engine cannot evaluate on half the bars it sees is not a
rule the engine has. The fix is to stop anchoring on a candle that may not exist and anchor on the
one that always does: the current bar.

**Detection condition:** `rule7_retest_bars(candles, level) <= 5`, where `rule7_retest_bars` is the
number of bars the level spent **untouched** between price leaving it and now — the away-leg (the
run of bars immediately before the retest whose range did not contain the level) plus the lag (bars
since that retest). A bar "touches" the level when `low <= level <= high`. The scan is capped at a
20-bar window and **saturates at 20** when no bar in the window touched the level at all, which is
exactly the case that used to emit `null`: no retest inside the window is not undefined, it is the
slowest reading the window can produce, and it fails. The value is therefore an integer in `[0,20]`
on every bar, for every level, with no null branch — the same number is available whether or not a
body ever closed across the level.

**Threshold:** 5 bars, read straight off "as soon as possible", **not fitted.** The separation
tables in `research/rule7_rule10.md` are underpowered on every contrast (observed |d| below the
minimum detectable effect at n=34 S / 38 A / 11 X), so no threshold here can honestly claim to be
tuned to Austin's tiers; 5 is a rule in the same spirit as `DETECT_WIDE_RETEST_MULT` taking the
round 1.0 over the fitted 1.3.

**In code:** `signal_runner.rule7_retest_bars`, applied in `_route` behind `RULE_710_ENABLED`
(module-level, **default `False`**). When armed, a candidate graded A+/A/B whose retest is slower
than the threshold is capped to C (alert-only), mirroring `S_GATE` and `HTF_BIAS_GATE`; it is never
a hard skip. The reference level is `sig["stop"]`, which in every setup above *is* the structure
being retested (`stop_level_name` names it: OR high / PDH / Order block low / FVG low / Flag low).
While the flag is off this is a no-op and shipped behaviour is unchanged.

---

## Rule 10: Left-Side Pivot Noise

**What it is:** Austin, X-card rejection — *"a bunch of candles or pivot structures already there
before your break ... if the break and retest is not clean or the order block is not clean."* The
same break at the same price is worth less when the left side of the chart has already chopped
through that level several times. A level is tradeable because it is *undisturbed*; every prior
swing that turned on it has already spent some of that.

Same failure as Rule 7 and the same cause. `left_pivot_count` counted 3-bar swing pivots in the 20
bars **before the break candle**, so it inherited the break candle's absence and came back `null`
on **56 of 159 marks (35.2%)** — precisely the no-break-identifiable marks
(`research/rule7_rule10.md`). Nothing about pivot noise actually requires a break candle to define
it; the lookback simply has to end somewhere, and the current bar is a perfectly good end.

**Detection condition:** `rule10_left_pivots(candles, level)[1] <= 2` — of the 3-bar swing pivots
whose centre falls in the 20 bars before the current bar, at most two may sit within 0.2% of the
level. A pivot is a high above both its neighbours and/or a low below both (the same definition
`omen_bot.MarketStructure.update` and `research/rule7_rule10.py` use; a bar that is both counts
twice). With too little history the count is simply 0, so the pair `(count, at_level)` is two
non-negative integers on every bar — the "before the break" clause that produced the nulls is gone,
and with it the null.

**Threshold:** at most 2 pivots on the level, again a rule and **not a fit** — the measured means
(S 1.57 / A 2.33 / X 1.93 pivots at level) do not separate the tiers at this sample size, and
`research/v37_verdict.md` puts the sample needed to answer Rule 7 or Rule 10 at roughly 145
non-null marks per arm. Until then this threshold is Austin's sentence made countable, nothing more.

**In code:** `signal_runner.rule10_left_pivots`, evaluated in the same `_route` block behind the
same `RULE_710_ENABLED` flag (**default `False`**), capping A+/A/B to C with a reason naming which
of the two rules capped it. Off by default; arming it is Austin's call, and the honest A/B is the
recall/precision pair from `research/regression_gate.py` with the flag flipped at runtime.

---

## Austin's Tiers (S / A / C / X)

**What it is:** Austin's own vocabulary for marking a chart, settled 2026-08-09. It is not the
engine's A+/A/B/C grade and never has been — the grade is a quality score the detector computes
about a candidate, while a tier is Austin's verdict on whether the thing in front of him is a
trade. Until now `austin_tier` was a slot that always held nothing, because no honest mapping from
A+/A/B/C existed. It does not need one: the tier is computed from the four clauses below, directly.

### S — tradeable

All of clauses 1–8 hold. Anything short of all of them is not an S. Clauses 1–4
are the original negative filters (setup identity, bar-extreme fill, first-of-its-idea,
higher-timeframe). Clauses 5–8 are what was missing — the *positive* requirements
and the hard vetoes that make a break-and-retest an S in the first place.

1. **The setup is one of exactly three.** Break-and-retest, the one candle rule (the order block),
   or an **armed** 84% re-entry. Nothing else is ever S — a fair-value-gap entry and a flag
   breakout can be perfectly good-looking and are still not one of the three setups Austin trades.
2. **The fill is not at the extreme of the bar.** The entry close does not sit in the top 25% of
   the signal bar's own range (long) or the bottom 25% (short), measured against the bar **as it
   stands at the moment of entry**. This is a fill-quality guard — "better fills matter", lesson 4
   above, and "don't buy the top" — and it is emphatically *not* a wait-for-the-close confirmation
   gate: it reads the bar being entered on, never a later bar and never a confirmed close.
   *Exempt: the 84% re-entry, where the close back through the failed entry price **is** the
   signal, so an extreme close is the thing being asked for.*
3. **It is the first S of its idea today.** No prior S has fired today on the same
   **symbol + direction + level**. The same level re-broken in the same direction is the same idea
   having a second go, not a second trade. *Exempt: an armed 84% re-entry, which exists precisely
   to be the second entry on an idea that already fired and stopped out.*
4. **The higher timeframe does not oppose the direction** — **unless clause 2 passes**, in which
   case a good fill may be allowed to carry an opposing higher timeframe. Clause 4 is the one
   clause Austin has **not** settled. It is therefore a switch, not a constant, and both arms are
   measured before anyone picks one.
5. **Displacement.** The break leg must show displacement — a decisive move off
   the level rather than a drift — and a break-and-retest without it can **never**
   be S. Define it once, concretely, so `BNR_DISPLACEMENT_GATE` implements exactly
   what this paragraph says: a beyond-level candle in the 5-bar break leg whose
   body (`|close − open|`) is **≥ 1.5× the average body of the 10 candles before
   it** (the `DISPLACEMENT_MULT = 1.5` convention shared with
   `omen_bot._has_displacement` and the A+ stack). The displacement candle must
   not touch the level being broken. A B&R that drifts through the level with no
   bar clearing that 1.5× body threshold is not an S, whatever the other clauses
   say. Evidence: `GOOGL_2026-01-20_67` (*"way to many break and retests with no
   displacement"*), `QQQ_2024-05-08_8`, `SPY_2024-07-11_44`, `TSLA_2024-12-03_17`,
   `NVDA_2024-11-18_10`.
6. **Too much consolidation, or too slow a retest, demotes.** Austin, 2026-08-10:
   an OCR or B&R with too much consolidation before entry, or too long between
   the break and the retest of the level (or one candle), is subject to
   **demotion** — not an outright veto, but it cannot stay S. This is the same
   rule stated numerically by **Rule 7** (retest speed: `rule7_retest_bars ≤ 5`)
   and **Rule 10** (left-side pivot count: `rule10_left_pivots ≤ 2`); cite them
   here so the paragraph and the code are one rule. Evidence:
   `MSFT_2025-03-20_28` (*"too much consolidation before entry"*),
   `NVDA_2024-11-13_17` (*"too choppy and taking too long"*), `QQQ_2024-07-24_23`,
   `MSTR_2024-12-17_89` (*"chop"*).
7. **In-between mesh is a hard veto, not a demotion.** Austin, 2026-07-06:
   *"middle of a bunch of levels, probability goes down significantly."* A
   candidate sitting in the mesh between several nearby levels is not a demoted S
   or a C — it is **not taken at all**. This is a hard veto, distinct from the
   consolidation demotion of clause 6. (Earlier in this document it was written
   as a C-condition; it is a veto, and it is implemented nowhere yet.)
   Evidence: `AAPL_2024-10-28_162` (*"tight and chop in-between channels"*),
   `SPCX_2026-06-29_47` (*"overextended and no great entry presented itself"*).
8. **Pivot structure is a level.** Swing highs and lows are levels Austin trades
   off, on equal footing with OR high/low, PDH/PDL and PMH/PML, and **a break of
   pivot structure outranks a break of a named level.** A break/retest of a
   2-candle pivot structure is a valid S-level even when no named level sits
   there; and when both are present the pivot-structure break governs the stop
   and the grade. Evidence: `AMZN_2025-07-17_34` (*"pivot-structure break >
   level break"*), `NVDA_2024-09-06_53` (*"no clean break it just respect pivot
   structures"*), `TSLA_2024-12-03_17` (*"break/retest of a 2-candle structure,
   not a large pivot"*), `NVDA_2025-11-28_14_22` (*"raise the stop to the higher
   piece of the pivot structure"*).

### S+ — the top 1–3 per day (reporting rank, not a fifth tier)

All S signals stay S on one grading scale — there is no fifth tier letter. The
top **1–3 per day** universe-wide are reported as **S+** — *"the top S trades
which usually happen earlier in the day."* This is a **reporting rank**, not a
quality gate: the S signals that are not in the top 1–3 are still S and are
**never discarded**. `S+` is a label applied to the day's best handful of S
candidates for reporting; it does not change whether the rest are taken.

### Confluence is a bonus

Two of the three setups firing on the same bar is **recorded and reported, never
required**. Confluence raises confidence and is noted on the signal, but a
single-setup S is still an S; confluence is not a gate and does not demote a
signal that lacks it. Evidence: `PLTR_2025-12-10_45_52` (*"perfect S entry OCR
BR confluence"*), `NVDA_2024-12-16_14` (*"OCR+BR confluence"*).

### A — one or two clauses missing

Clause 1 holds, and one or two of clauses 2–8 do not (consolidation / slow
retest under clause 6 being the most common demoter). These are valid setups
under the right higher-timeframe circumstance, and they are **detected and
logged, not traded**. The point of naming them is that they are the pool clause
4's switch is decided from — an arm that promotes half the A pool to S is an arm
that changes what gets traded, and that has to be measured, not assumed.

### C — seen, not traded

Clause 1 holds but three or more of the others fail; or the setup **targets the
session HOD/LOD** (clause 4 of *Austin's Trading Rules* — the session-extreme
veto — also drops a target here). Clause 1 failing outright — a fair-value gap,
a flag — is also C. **Detected and logged, not traded.** (In-between mesh is not
listed here: per clause 7 it is a hard veto, not a C.)

### X — Austin's marker, not an engine output

X is *"not a level worth tracking"* — his own do-not-trade mark on a chart. It is a marking
vocabulary, not a signal class the engine emits, so `compute_austin_tier` never returns `"X"`. (The
engine's *skip* grade is also spelled `X`; that is `TradeGrade.X`, a different field, and the two
should not be read as the same statement.)

**In code:** `signal_runner.compute_austin_tier(sig, candles, fired_ideas, htf_bias)`, called from
`_route` so that **every** signal — accepted or skipped — carries `sig["austin_tier"]`. One named
helper per clause, so later rows can cite a clause rather than re-derive it:
`setup_is_s_eligible(sig)` is clause 1, `bar_extreme_veto(sig, candle)` is clause 2 (True = vetoed;
unconditionally False for `SignalType.REENTRY_84_RULE`), and `idea_key(sig)` is clause 3's identity
`(symbol, direction, level_name)` — the *name* of the reference level (OR high / OR low / PDH /
PDL / PMH / PML), never its price, so the same level at a different tick is still the same idea.

Clause 4 is the parameter `HTF_OPPOSITION_VETO`, **default `"hard"`** because hard is today's
behaviour: an opposed higher timeframe can never be S. The other arm, `"fill_override"`, lets a
signal that passes clause 2 stay S with an opposing higher timeframe. Both arms get measured before
Austin picks.

`AUSTIN_TIER_ENABLED` ships **`True`**: this is a reported field and nothing branches on it, so
there is nothing to gate. `TRADE_S_ONLY` — the switch that would restrict entries to S alone —
ships **`False`** and is **read nowhere in this version**; it exists so the tier can be A/B'd
against today's routing before anyone arms it. Adding the tier changed no grade, no `_SKIP_GRADES`
membership and no routing decision; `research/regression_gate.py` is the proof.

---

## Written but not yet implemented

The clauses below are pulled from Austin's notes and from the 2026-08-11 session
sweep. Each is written as its own short line so a later version can implement it,
and the **whole group is explicitly not yet implemented** — nobody should read
this paragraph as shipped behaviour. None of these have a detector, gate, or
flag in the engine today.

- **Wick-touch is a hard filter for break-and-retest too**, not only for the one
  candle rule. The B&R retest must touch the level as a wick, not close inside
  it. Evidence: `PLTR_2024-10-23_10` (*"wick not touching a level"*).
- **A pre-signal wick raises confidence.** A large wick on the candle before
  entry gives confidence even when the entry candle is not the absolute strongest
  green candle. Evidence: `IWM_2024-04-03_13` (*"large wick before candle entry
  gives confidence even though it's not the absolute strongest green candle"*).
- **A trendline break wants a second confirmation candle with strength.**
  Evidence: `ORCL_2025-03-28_12`.
- **Order-block stop selection.** Austin: *"you want the stop to always be
  somewhere in the order block"*, and *"if you want a price target high of day
  and you can only go so far for your stop loss to hit the 2-1 then you use the
  stop-loss to whatever is the closest to that level, top of the order block."*
  The rulebook currently says only "stop at the far side of the block"; his rule
  picks the stop **closest to the level that still clears 2:1**, which is a
  different and better-defined rule.
- **Candle speed.** Austin: *"We need to figure out a system to detect how fast
  the candle's moving... you have a clean break and retest and you're waiting on
  one more candle to do what you want it to do and that puts you on high alert."*
  No velocity feature exists anywhere in the engine.
- **One-candle-rule prior-visit veto.** Austin: *"I don't like one candle rule
  when there's noise previously (the stock has already been there before) — you
  have to have premarket or higher timeframe thesis to take middleman stuff like
  this."*
- **Entries come off retests, never breaks.** Austin: *"I never enter on breaks,
  I enter on retests with strong price confirmation."* The break-and-retest
  detector already implies this; it is stated here so it cannot be loosened by
  accident.

---

## Bot Decision Engine (Pseudocode)

```
WHILE market is open:
    
    # Scan for Setup 1: Break and Retest
    IF price breaks opening range high/low:
        IF price retraces back to break level:
            IF HTF trend confirms breakout direction:
                ENTER position
                SET stop_loss = opening_range_opposite_side
                SET profit_target = 10:1 risk_reward_minimum
    
    # Scan for Setup 2: 84% Rule
    IF opening_range is defined:
        IF price breaks opening_range_high OR opening_range_low:
            ENTER (84% probability doesn't return inside)
            SET stop_loss = opening_range_opposite_side
            SET profit_target = 10:1 RR or market structure
    
    # Monitor open positions
    FOR each open_position:
        IF position_hits_profit_target:
            EXIT trade
        IF position_hits_stop_loss:
            EXIT trade (cut early, don't be stubborn)
        IF time_to_end_of_day:
            CLOSE position
```

---

## Austin's Key Lessons (From Zella Trade)

1. **HTF Confirmation is Critical** — Don't trade against the higher timeframe trend
2. **Don't Sell Too Early** — Wait for the full target, not premature profits
3. **Trust Your Setup** — PLTR was a good setup but Austin didn't trust his eyes
4. **Better Fills Matter** — Same setup, different entry price = different risk management
5. **10:1 Risk/Reward** — This is the minimum threshold Austin targets
6. **Cut Early if Wrong** — GOOGL: "Stop Loss Detailed down cut below resistance trade" — know when to exit
7. **Small Wins Are Okay** — Better to take consistent small winners than miss big moves

---

## Next Steps for Bot

1. ✅ Define the 4 setups (3 remaining to be documented from Scarface videos)
2. [ ] Code the setup detection logic (pattern recognition)
3. [ ] Code the entry/exit execution logic
4. [ ] Backtest against historical options data
5. [ ] Paper trade to verify real market conditions
6. [ ] Live trade with bot account (separate from Austin's manual account)

---

## Video References
- Break and Retest: https://youtu.be/5KHVU0zOmks
- [Other setup]: https://youtu.be/dNXhFwy5tjY
- More to gather from Scarface Trades YouTube channel

