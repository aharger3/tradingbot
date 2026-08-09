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

**What it is:** The first 5-minute candle of the session sets the range. 84% of the time, price will eventually break this range and not come back inside it.

### Entry Conditions
- Define the opening range: High and low of the first 5-minute candle (or first N candles)
- Wait for price to break above the high OR below the low
- **84% rule**: Once broken, price tends to not return, so entry on break is high probability
- Enter at/near the break of the range

### Exit Conditions
- **Profit target:** If 84% rule holds, ride the momentum for 10:1 RR (or market structure target)
- **Stop loss:** Other side of the opening range, or below the swing low/high
- **Early exit:** If price reverses back into range (the 16% of the time it fails), exit immediately

### Risk Management
- This is a higher-probability setup (84% win rate)
- Position size can be slightly larger due to high probability
- Use tight stops to protect the 16% failures
- Combine with HTF confirmation for best results

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

**What it is:** Extended explanation of the 84% probability rule noted in Austin's charts.

### Core Principle
- When opening range (first 5 minutes) breaks, 84% of the time price doesn't return inside that range
- This is a statistical edge that can be mechanically traded

### Entry Conditions
- [Clarify exact timing and confirmation]

### Exit Conditions
- [Clarify exact targets and stops]

### Risk Management
- [Clarify position sizing for high-probability trades]

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

