# Scarface / J-Dub Rules — Discord Community Mining (22,596 files)

Source: `discord_data/*.json` — trade-feedback (4K), trading-floor (39K), scarface/jdub-alerts (10.4K combined), trade reviews (1.2K), futures (4.8K). Extracted via keyword matching (5,900 high-signal messages, 569 with 4+ keyword hits). Every claim backed by (file, author, timestamp). "NOT COVERED IN THIS SOURCE" = topic not found in Discord.

---

## HEADLINE FINDINGS (vs course materials)

### 1. NEW: 84% Rule Refined — Structure MUST Have Actually Broken
> "I like the 2nd entry but don't see this as 84% rule since 1-candle structure never failed. More of a PDH + 1-candle reclaim play." (Kam, trade-feedback.json, 2025-12-22)

Course materials: "same break, same retest, same hammer, same stop, same target." Discord adds: the 1-candle (order block) structure must have been INVALIDATED by the first trade's stop-out. If it just retested and held, it's a normal B&R — not an 84% re-entry.

> "I don't think this follows the 84% rule. The 84% rule applies when you have a plan for entering at a specific key level and the stock tries to retest that level but fails and goes lower. The 84% rule comes into play when the stock returns to that key level and breaks through it. Typically, with the 84% rule, the stock doesn't retest the key level — it just breaks through and moves in the right direction." (demchy19, trading-floor.json, 2024-10-14)

### 2. NEW: Community-Derived Hard Rules (NOT in course materials)
Course materials cover B&R mechanics. Discord community has evolved ADDITIONAL discipline rules from real losses:

| Rule | Source | Frequency |
|------|--------|-----------|
| Max 3 options trades per day (11 = overtrading) | Das Wookie | Multiple testimonials |
| If green on first 2 trades, done for day | Das Wookie | Community consensus |
| No trading after 11 AM | Das Wookie et al. | Multiple |
| Both QQQ AND SPY must align for shorts | dane | Adds to course "QQQ alignment" |
| HTF key levels > pre-market levels (ignore PM levels) | Markellwhite16, 305 Trader | Community consensus |
| Inside bar day = lower probability, reduce size | Markellwhite16 | Multiple |
| Wait for confirmation — never anticipate entry | Kam, Jay_aye11 | Most common feedback |
| No revenge trading (hard rule, not suggestion) | Das Wookie, Joebag009 | Universal |
| Check options liquidity before entering | Das Wookie ($140k lesson) | Rarely covered |

### 3. NEW: Short Side ("Elevator Down") Playbook Expanded
Course materials mention "elevator down, stairs up." Discord adds specifics:
- Shorts under PDL for big RR (Markellwhite16)
- Bear flag on HTF + breakdown = high-probability short setup
- Both QQQ + SPY alignment required for shorts (stricter than longs)
- Acceptance under key level required (futures language: "acceptance under X")
- Shorts near weekly R levels (opposite of going long off support)
- Futures: "sell setup below OP" (opening print) — common pattern

### 4. CONFIRMED: Course Rules Applied in Practice
Discord trade reviews SHOW (not just tell) the following course rules being used:
- B&R on 1m/5m with HTF context (most common setup)
- Stop at body break / candle close below stop (body close rule)
- Scale partial at HOD/LOD always
- 84% rule requires same level, same thesis (not same stock on same day)
- QQQ context overrides individual thesis
- Order blocks as stop reference and entry zone

---

## 1. DISCIPLINE / PROCESS RULES (Most Common FAILURE patterns)

### Failure Pattern #1: Trading After 11 AM
> "Don't trade after 11 — I couldn't resist the afternoon downturn to go short on PLTR and GOOG." (Das Wookie, trade-feedback.json, 2025-11-20 — part of a catastrophic $140k loss day)

### Failure Pattern #2: Revenge Trading + Chase
> "Don't revenge trade — I lost my first entry, exited, played a Uno Reverse card and immediately re-entered, and lost again! -$4k on both." (Das Wookie)
> "I chased, and entered a trade without a proper setup entry JUST because it looked like it might be good. I sized WAY up to 400 contracts to try and make up for my loss." (Das Wookie, trade-feedback.json, 2025-11-22 — the $140k loss)
> "Lost first two trades, should have walked away. Instead chased, sized up to 400 contracts in an illiquid option with $3.50 spread. Couldn't exit. Dropped ask $3.40 before it sold. Turned green day into $140k loss." (Das Wookie, trade-feedback.json)

### Failure Pattern #3: Anticipatory Entry (No Confirmation)
> "Took an anticipatory reclaim entry off the 1m OB after visual strength near prior pivot, but skipped confirmation and entered on candle stretch... Primary Mistake: Premature Entry — No Reclaim Confirmation." (Kam, trade-feedback.json, 2025-06-26)
> "Findings: entry was uncertain, I was looking for the 3 bar entry but got impatient." (Jay_aye11, trade-feedback.json, 2025-10-31 — on a 10-loss streak)

### Failure Pattern #4: Ignoring No-Trade Zones
> "Between 162.05 & 157.8 still the no trade zone, clearly a chop fest / channel in here." (Markellwhite16, trading-floor.json, 2025-09-22)
> "Between 436.3 & 427 I'm hands off, don't want to trade in a channel." (Markellwhite16, trading-floor.json, 2025-09-22)
> "Be cautious trading between 427-411.4 due to it being a consolidation zone, can't be surprised if PA is bad in there." (Markellwhite16, trading-floor.json, 2025-09-23)

### Failure Pattern #5: Going Against HTF Context
> "In the gameplan I had identified the strength on the higher time frame for GOOGL so why am I looking for an intraday short?" (Mar, trade-feedback.json, 2025-01-11)
> "You went LONG into a major R level on NVDA. Here's all this overhead resistance." (Markellwhite16, trade-feedback.json — giving feedback to another trader)
> "At the time of your entry Qs was at HOD and AAPL was lagging behind." (Royal191, trade-feedback.json, 2025-09-19)

### Failure Pattern #6: Overtrading (Max Trades)
> "Max of 3 daily options trades... I entered in on 11 trades in total today." (Das Wookie)
> "If I do well on either of my initial 2 trades, and I'm green for the day... you're done! I only had two trades, got greedy and wanted more." (Das Wookie)

### Failure Pattern #7: Options Illiquidity
> "There were NO options traders on that symbol. The Bid/Ask Spread was MASSIVE with a $3.50 spread. There were NO buyers. NONE!!! I saw trades of mostly 1 contract, a few for 2, a rare 5 or 10, and then my 400 contracts buy." (Das Wookie)

---

## 2. SHORT SIDE PLAYBOOK ("Elevator Down")

### Short Entry Conditions
**PDL breakdown:**
> "I like shorts under PDL due to this being a big RR trade, worth the risk. Bear flag setting up on the HTF." (Markellwhite16, trading-floor.json, 2025-09-23)

**HTF resistance short:**
> "Shorts under 157.8 also near PDL so if we break down under this level it can really flush." (Markellwhite16, trading-floor.json, 2025-09-22)

**Weekly resistance short:**
> "I'm hands off taking Longs off of PDH due to a weekly R level being right above @ 164.75, not a good RR trade. Shorts under 157.8." (Markellwhite16, trading-floor.json, 2025-09-22)

**Futures short setup (MambaTrades):**
> "ES acceptance under 5769 to target 5751.50. Ideal shorts under 5751.50 to see 5695.50." (futures-alerts.json, 2025-03-06)
> "NQ sell setup below OP. Target gap fill 24424 and 24158.5 PDL." (futures-alerts.json, 2025-10-14)
> "Indices are showing relative weakness... watching for shorts under opening print to target gap fill and PDL." (futures-alerts.json, 2025-10-14)

**Both indices must align for shorts:**
> "I only enter when both SPY and QQQ are below my key level and SPY was not yet." (dane, trade-feedback.json, 2025-11-18)

### Short Specific Rules (from trade reviews)
- Shorts require acceptance UNDER a key level (not just touching)
- Put options: strike below support, 1-2 weeks DTE
- Short scalps: take profits faster than longs — "elevator down" means it can rebound just as fast
- A+ short = HTF resistance + weekly R + bear flag + relative weakness
- Futures: volume must confirm (want 150k min ES volume)

---

## 3. 84% RULE — Discord Refinements

### Critical Condition: Structure Must Have Failed
> "If 1-candle structure never failed, it's not 84% rule." (Kam, trade-feedback.json, 2025-12-22)

This is the KEY Discord refinement. The first trade must have been stopped out because the 1-candle/OB structure actually broke. If the first trade stopped out due to wide spread, bad entry timing, or impatience — not the same thing.

### Re-entry Behavior
> "The 84% rule comes into play when the stock returns to that key level and breaks through it. Typically, with the 84% rule, the stock doesn't retest the key level — it just breaks through and moves in the right direction." (demchy19, trading-floor.json, 2024-10-14)

> "Entry a bit uncertain, 84% rule entered on the 'retest', buyers appeared to enter gave us a wick, trading below the Premarket high, I was anticipating a break above... entry was uncertain, I was looking for the 3 bar entry but get impatient." (Jay_aye11, trade-feedback.json, 2025-10-31 — describes a failed 84% attempt)

### When 84% Rule Does NOT Apply
- Structure never broke (Kam)
- Thesis changed (trending→consolidating) — from mastermind
- Same stock different setup (not same level, same thesis)
- Inside bar day or choppy context

---

## 4. EXIT MANAGEMENT — Discord Practice

### Scaling Examples
> "I would have taken profit like you at HOD. After taking profits at HOD, the trade is de-risked so if it comes back it comes back, stop out for BE or small loss." (Kam, trade-feedback.json, 2025-06-27)
> "I was able to scale out 20% of my size." (Mar, trade-feedback.json, 2025-01-11)
> "Exited near LOD 9:53 candle." (Kuba, trade-feedback.json, 2025-06-13 — explained as scaling approach)

### Stop Management
> "Exited when a candle closed below the first order block." (Tito Frescado, trade-feedback.json, 2025-03-19)
> "SL just below the order block as I don't want to have a big loss with 2 cons." (Kuba, trade-feedback.json, 2025-06-13)
> "I don't move my stop unless I have a first high of day or low of day scale." (xhD_SRbyMNE, YouTube — confirmed in Discord practice)

### Trailing Methods (from community)
> "I tend to use OB's and structure to trail, but others use trendlines and EMAs. __ uses a 5m timer! Just have to find your style!" (Kam, trade-feedback.json, 2025-06-27)

Confirms multiple trailing methods coexist in the community: OBs, trendlines/EMAs, time-based.

---

## 5. RULES STATED IN DISCORD (Not in Course Materials) — COMPLETE LIST

| Rule | Evidence | Source |
|------|----------|--------|
| Max 3 options trades/day | 11 trades = overtrading violation | Das Wookie |
| Stop after 2 green trades | Done for day | Das Wookie |
| No trading after 11 AM | Revenge afternoon trades most destructive | Das Wookie + others |
| Both QQQ+SPY for shorts | Entered short without SPY, broke rule | dane |
| HTF key levels > PM levels | PM levels = low conviction, HTF = liquidity | Markellwhite16, 305 Trader |
| Inside bar day = lower probability | Mark no-trade zones | Markellwhite16 |
| No anticipatory entries | Wait for candle close/confirmation | Kam, Jay_aye11 |
| Check options liquidity | $140k lesson on illiquid options | Das Wookie |
| 84% rule requires structural failure | Not same as re-entering after losing | Kam, demchy19 |
| No trade zones are real | Draw them, respect them | Markellwhite16 |
| Futures: volume >150k ES = go | 271 "great," 164 "good," <150 caution | MambaTrades |

---

## 6. NOT COVERED IN DISCORD (noise floor too high or absent)

- One candle rule specifics — covered in trade reviews (student-level, not instructor instruction)
- Order block definition (students reference it but don't define it — assumed from course)
- News day rules (referenced by MambaTrades but not systematically covered)
- Specific scaling %s for trending vs choppy (course material covers this; Discord just applies it)
- QQQ 8 alignment rules (students say "QQQ aligned" but don't enumerate rules)

---

## 7. AMBIGUITIES / CAVEATS

1. **Discord is student-dominant** — 90% of trade-feedback.json is students posting their trades. Only Kam, Markellwhite16, and 305 Trader show advanced judgment. Take student rules as community norms, not instructor doctrine.

2. **Price targets for shorts** — no consistent R:R mentioned for shorts in Discord. Students say "big RR" without quantifying.

3. **84% rule confusion** — multiple students misapply it. Only Kam and demchy19 corrected the definition. Most students treat any re-entry as "84% rule."

4. **Start time "after 11" rule** — Das Wookie's personal rule, not explicitly from instructors. Course materials say "75% of trades around 10 AM" (YouTube) and mastermind says "no entries after 11:00-11:30." Student data aligns but may be stricter than taught.

5. **Scaling % in practice** — students mention "20% scale" once (Mar) and "exited 1 con" (Kuba). No student provides full scaling breakdowns. Course material (D2 dossier) has better data.

6. **Futures vs options playbook** — MambaTrades futures alerts show a different language (acceptance, volume threshold, data high/low). These use QQQ/ES/NQ levels but with futures-specific entry criteria not in the shared B&R course.

7. **Trade review quality varies** — some students post detailed self-reviews (Kam, Kuba, Das Wookie), others post "why did I lose" without analysis. Filter by author when evaluating.
