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

All four clauses hold. Anything short of all four is not an S.

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

### A — one or two clauses missing

Clause 1 holds, and one or two of clauses 2/3/4 do not. These are valid setups under the right
higher-timeframe circumstance, and they are **detected and logged, not traded**. The point of
naming them is that they are the pool clause 4's switch is decided from — an arm that promotes
half the A pool to S is an arm that changes what gets traded, and that has to be measured, not
assumed.

### C — seen, not traded

Clause 1 holds but three or more of the others fail; or the setup fits one of the three but sits in
**in-between mesh** (Austin, 2026-07-06: *"middle of a bunch of levels, probability goes down
significantly"*); or it **targets the session HOD/LOD**. Clause 1 failing outright — a fair-value
gap, a flag — is also C. **Detected and logged, not traded.**

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

