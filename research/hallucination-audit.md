# Hallucination Audit — coded rules vs the rulebooks (2026-07-11, videos pass 2026-07-13)

Scope per next-session-brief: every rule in `omen_bot.py` (detect_break_retest,
detect_order_block_setup, one-candle routing, grading) and `signal_runner.py`
(grading, stops, targets, S score, 84% arm/fire) diffed against:
`scarface-rules-{accelerator,mastermind,coaching-bonus,youtube}.md`.
**B2 2026-07-13:** fifth source merged — `scarface-rules-videos.md` (89 Whisper transcripts,
36 extraction groups). Per-rule videos column in the "Videos rulebook column" section below;
verdict changes and new flags listed there.

Verdicts: **MATCHES** (source teaches it), **DIVERGES** (source teaches something else),
**INVENTED** (no source basis — course-attributed rules only; Austin's own dated rules
and data-derived thresholds are labeled **AUSTIN**/**OURS**, not hallucinations),
**SOURCE-SAYS-MORE** (source rule exists that we haven't coded).

---

## Verdict table

### Break-and-retest core (`detect_break_retest`, B&R blocks in `detect_signals`)

| # | Coded rule | Source rule | Verdict | Fix |
|---|-----------|-------------|---------|-----|
| 1 | Ordered FSM: break (close through) → leave → retest → confirm close | "Bodies tell the story" (acc 1450664); "enter on the retest, not the breakout" (mm 3.0); displacement = "candle does not touch your previous resistance turn support" (mm 5.0 / bonus) — that IS our LEAVE state | MATCHES | none |
| 2 | Break uses candle CLOSES, wicks ignored | "The wicks do the damage, bodies tell the story"; invalidation = close back through | MATCHES | none |
| 3 | eps buffer = 10% avg range (close AT level ≠ break) | "Levels are zones, not ticks. 2-10 cent zone" | MATCHES (Austin's quantification) | none |
| 4 | window=12 bars, max_confirm_gap=3 | Not stated anywhere ("max wait for retest" = known gap) | INVENTED-PARAM | keep — some window needed; source silent |
| 5 | LATE tag: level broken earlier in session = dirty, cap B | "First retest is best. Fresh level." (mm 4.0); "The first time it touches the level are the high probability ones" (yt) | MATCHES | none — Austin's rule now source-confirmed |
| 6 | Stop = the broken level exactly | Stop = break of retest candle / structure / below OB, "10-15 cents buffer below level for room" (mm 5.0) | **DIVERGES** | A/B later: stop = retest-candle low (long) or level − buffer. Changes geometry → separate run, don't mix with today's |
| 7 | Target = blind 2R | First scale ALWAYS HOD/LOD, then next liquidity (PDH/PDL, gap fill, psych, ATH). "2:1 is the MINIMUM aggregate expectation, not the exit mechanism" (acc headline 3) | **DIVERGES** | biggest structural divergence. Needs backtester exit-model rework (liquidity-ladder sim). Future FABLE session |
| 8 | Entry at confirm-candle close | "Wait for candle to close. Second that candle closes, enter immediately" | MATCHES | none |
| 9 | Adverse-wick veto on entry candle | Hammer/inv-hammer preference implies; "sellers wick it above" invalidation quotes | MATCHES (AUSTIN quantification) | none |
| 10 | Levels traded: OR, PDH/PDL, PMH/PML | Source playbook ALSO has: **HOD/LOD break-retest** ("Wait for HOD break and retest or LOD break and retest. Nothing in between — all noise." mm 5.0), **opening candle print** (1-min candle high/low, yt headline 7), gap fill | **SOURCE-SAYS-MORE** | top new-setup candidate: intraday HOD/LOD B&R. Needs own detector + backtest. Queue for next session |
| 11 | PMH/PML B&R capped alert-only (our 24mo data: negative) | "I very rarely use the pre-market levels" (yt 7kajZjCStT8) | MATCHES | none — data and source agree |
| 12 | Consolidation skip: all 4 levels within 0.5% | "Choppy market: skip entirely or size down" | MATCHES concept (proxy OURS) | none |

### Grading (`grade_trade`, `_grade_pa`, `_grade_for_levels`, `_calibration_grade`)

| # | Coded rule | Source rule | Verdict | Fix |
|---|-----------|-------------|---------|-----|
| 13 | Hammer at level = A+ candidate | Hammer (long) / inverted hammer-shooting star (short) is THE entry candle, "the candle I trade 90% of the time" | MATCHES | none |
| 14 | **Bullish/bearish engulfing at level = A** | Engulfing appears in ZERO of the 4 rulebooks (101 Circle + 558 YouTube transcripts). *Videos 07-13: ONE passing mention (Day 6) — see videos column* | **INVENTED → MENTIONED-ONCE** | **KILLED 2026-07-11** — branch removed from `_grade_pa`; kill stands (see videos section) |
| 15 | Large-wick-at-level = B, any-retest = C ladder | Source has no letter ladder below A+/regular | OURS (scaffolding, not course-attributed) | keep |
| 16 | HTF opposed → D; neutral caps A+/A → B | "Shorting when higher time frames still intact = low probability"; A+ requires all timeframes aligned | MATCHES | none |
| 17 | A+ stack = first clean break + displacement + strong PA + clear road | Source A+ = that PLUS QQQ/SPY alignment + entry level is a HTF level | **SOURCE-SAYS-MORE** | QQQ leg pending `qqq-alignment-rules.md` (DeepSeek, 8 verbatim rules). Do NOT re-code the crude OR-break proxy — it inverted |
| 18 | Counter-day-trend cap C (stock's own trend from candles[0].open) | Source trend filter is QQQ/SPY-based, not the stock's own day trend | DIVERGES (proxy) | replace with real QQQ rules when extraction lands |
| 19 | LEVEL_BLOCK_CAP: level inside 2R path caps C; CLEAR_FOR_APLUS | "2R must be achievable within the stock's average daily range — skip" (bonus); targets are liquidity levels | MATCHES spirit (AUSTIN rule) | none |
| 20 | STOP_RANGE_MULT 0.75× avg range human-proof gate | Not in source (source: "clear stop — if unclear, skip") | OURS | keep — validated on labeled takes |

### Order block / "one candle rule" (`detect_order_block_setup`, OCR routing)

| # | Coded rule | Source rule | Verdict | Fix |
|---|-----------|-------------|---------|-----|
| 21 | OB = last opposite-close candle before structure-breaking leg | "Order block = down-close candle before continuation move up"; "it's the whole down close candle" | MATCHES | **OCR = order blocks now explicit in YouTube — SPEC3 routing question CLOSED** |
| 22 | wick_only retest = only accepted strength | "The best order blocks hold the top of the wick and close above it" | MATCHES | none — our sweep found the same thing |
| 23 | Entry requires current close beyond block | "Not valid until we have a candle closure above this down close candle" | MATCHES | none |
| 24 | Displacement gate on the leg | "The best order blocks happen when there's displacement" | MATCHES | none |
| 25 | Stop = far side of block | "Stop loss = break of OB" | MATCHES | none |
| 26 | OB traded anywhere on chart | "OB alone is not edge. OB + key level confluence = edge" (Neto, coaching) | **SOURCE-SAYS-MORE** | candidate: require block zone within ~0.2% of an active level. Low priority — OCR already demoted to A-grade+tight-stop, n≈10/yr |
| 27 | `_is_isolated` (≤1 of 4 prior candles overlaps body) | Austin 2026-07-06, not course | AUSTIN | keep |
| 28 | No last-5-minutes OCR ban | "Don't take the 1 candle rule / OB rule in the last 5 minutes" (Neto) | SOURCE-SAYS-MORE | moot — live window ends 11:00, but note for any window change |

### 84% rule

| # | Coded rule | Source rule | Verdict | Fix |
|---|-----------|-------------|---------|-----|
| 29 | Arm only on stop-out of a counted trade | "Only valid if the first trade would have stopped you out" | MATCHES | none |
| 30 | Fire on reclaim CLOSE of failed entry | "Majority of my 84% rules are reclaims (80%)" | MATCHES | none |
| 31 | Original stop + original target (RULE84_LESSON) | "Same setup, same stop, same target" | MATCHES | none |
| 32 | **No PA gate on the reclaim candle** (RULE84_LESSON=True skips `_strong_pa`) | "I need to see some strong buying action near this level — not just going to enter off some random candle" (yt pGLsdLZahVY); mastermind: "same hammer" | **DIVERGES** | [hammer] tag added to 84% entries 2026-07-11 — measure split, gate if it holds |
| 33 | Arm off ANY counted B&R stop-out | "You need an A+ entry" — arming setup must be A-quality; "if the first trade was bad, the second will destroy you" | **SOURCE-SAYS-MORE** | candidate: arm only off A/A+ (or S≥4) stop-outs. Measure first — 84% n is small |
| 34 | Re-entry allowed any time rest of day | "Wait 5, 10, 15, 20 minutes. Come back to same area" — 5-20 min window | SOURCE-SAYS-MORE | note only; measure gap distribution before gating |
| 35 | One re-entry per failed setup, then disarm | "Two or three of the same setups = choppy day" — 2nd fail means stop | MATCHES | none |
| 36 | 1× size on re-entry | Accelerator: same size, explicitly never bigger. YouTube: can double/triple. **CONFLICT across sources** | MATCHES (accelerator) | keep 1× — our own 2× test was −$8.7k martingale. Await `84rule-sizing-dossier.md` |
| 37 | rr_ok: ≥1.5× remaining reward at re-entry | Not in source (source keeps original plan; also says 84 re-entries skip the HOD scale because continuation odds are higher) | OURS | keep — validated 2026-07-10 (avg 1.4R left, some 0.6R) |
| 38 | HOD-proximity skip (top 20% of day range) | Not in source | OURS | keep |

### Session / discipline / time

| # | Coded rule | Source rule | Verdict | Fix |
|---|-----------|-------------|---------|-----|
| 39 | 2 consecutive losses = day over | "After 2 consecutive losses — quit for the day. Hard rule." | MATCHES | none |
| 40 | Max 3 signals/day | "3 absolute max, avg 1-2" | MATCHES | none |
| 41 | `day_ended` docstring claimed "or 11 AM" but never checked time | 11:00 IS a source hard rule — enforced by live_scanner window + backtest ENTRY_CUTOFF, not by this method | DOCSTRING LIE | **FIXED 2026-07-11** — docstring corrected |
| 42 | Live window 09:30–11:00; backtest ENTRY_CUTOFF 11:00 | "Trade only 9:30-11:00 ET. Never seen me trade after 11:30. Ever." | MATCHES | none |
| 43 | No VWAP filter anywhere | "Stock must be above VWAP for calls, below VWAP for puts" (mm hard rule; acc beginner rule; yt directional bias) | **SOURCE-SAYS-MORE** | [vwap+]/[vwap-] tag added 2026-07-11 — verify sign on 12mo run, then wire into S |
| 44 | No news-day awareness | "Skip FOMC/red-folder days"; "trade after 2PM only or skip" | SOURCE-SAYS-MORE | blocked on `news_days.json` (GLM task) |
| 45 | No day-of-week logic | Acc: Tue–Thu best. MM: no preference. YT: Fridays risk-off, size down | SOURCE-CONFLICT | skip — sources disagree; test on own data before coding anything |
| 46 | No time-of-day S input | "75% of trades occur around 10:00" (yt) | SOURCE-SAYS-MORE | GLM adding per-hour split to report; encode only if our data confirms |

### S score & sizing

| # | Coded rule | Source rule | Verdict | Fix |
|---|-----------|-------------|---------|-----|
| 47 | S: clean+2, A-grade+2, stop≥0.3%+2, non-PM+1, hammer+2 | Data-derived (24mo split), not course-attributed | OURS | keep |
| 48 | Structural +2 for ALL widths ≥0.3% | Community: "close far beyond level = extended, don't buy the top". Our snapshot: width 0.3–0.5% wins 40.1%, ≥0.5% wins 28.0% (n=103) | **SOURCE-SAYS-MORE (chase)** | [chase] tag at ≥0.5% added 2026-07-11; S-variant measured offline |
| 49 | No daily-wick-zone awareness | Community reviews: "daily wick zones produce chop" | SOURCE-SAYS-MORE | [pdwick] tag added 2026-07-11 (entry inside prior day's daily-candle wick range); measured offline |
| 50 | Two hammer definitions (`is_hammer_stick` 2×-wick strict vs `_confirm_candle` 1×-wick) | Source is qualitative — no threshold taught | OURS (inconsistency, not hallucination) | harmless; S/take-tier uses `_confirm_candle`. Documented here |

### Dead code (not live paths — no verdicts needed)

- `BreakAndRetestDetector`, `OneCandleRuleDetector`, `RuleOf84Detector` classes: legacy,
  used only by old analysis scripts (`backtester.py`, `align_reviews_v2.py`). Live path is
  `detect_break_retest` + `detect_order_block_setup` + inline 84%. Leave for those scripts.
- `detect_flag_setup`: BENCHED (FLAG_ENABLED=False) — was my invented setup, −$57.6k/12mo.
  Stays dead until ordered rebuild + Austin's chart review.
- `find_fvg`: FVG concept IS taught (J-Dub session) but our retest variant diluted B&R —
  off (FVG_RETEST=False). Concept-MATCHES, implementation benched.

---

## Videos rulebook column (B2, 2026-07-13)

Fifth source: `scarface-rules-videos.md` — 89 video transcripts (boot camp, mastermind 1.0–5.0
lessons, Hayden's coaching, performance coaching, Building Your Profitable System, bonus).
Per-rule verdicts below; rules not listed = **videos silent** (extraction returned
"NOT COVERED IN THIS SOURCE"): #3, #4, #6, #12, #15, #19, #20, #25–28, #29–31, #33–38,
#45(partial, see below), #46–50.

| # | Rule | Videos verdict | Evidence (scarface-rules-videos.md) |
|---|------|---------------|-------------------------------------|
| 1,2,8 | B&R FSM, closes-not-wicks, enter on confirm close | **RE-CONFIRMED** | "you always wait for the candlestick to close" + hammer-fakeout warning (bonus B&B, :72-76) |
| 5 | LATE cap / first retest best | RE-CONFIRMED (implicit) | "first pullback" is an A-setup confluence (Day 6 A-setup definition, :28) |
| 7 | Blind 2R vs liquidity exits | **DIVERGES re-reinforced** | "first scales at high of day EVERY TIME", 40%/60% trailer split, psych numbers + HTF pivots as final targets (:220-242). F1 A/B still refuted the literal ladder — tension documented, no action |
| 9,13 | Hammer entry candle | RE-CONFIRMED | "weak/strong candle to confirm" per direction (:68-70) |
| 10 | HOD/LOD B&R setup exists | RE-CONFIRMED (HODLOD_PAIR stays off — F3 measured no edge) | HOD/LOD framing throughout exits/liquidity sections |
| 11 | PMH/PML demoted | **RE-CONFIRMED, now explicit hierarchy** | "The previous day high is gonna be a lot more important than the premarket high"; PM levels only "if there's nothing else to go off of" (Day 10, :180-184) |
| 14 | Engulfing | **MENTIONED-ONCE, not a graded entry rule** | Single Day 6 observation: bullish engulfing holding above prior body high = continuation signal (:5936-5941). NOT taught as an at-level entry pattern anywhere else in 89 files. Kill stands — removal was net +$4k and tier composition unchanged |
| 16 | HTF bias gates | RE-CONFIRMED + nuance | "thesis on daily/4h/1h, trade on the 1-min" (:84); NEW: "a higher timeframe thesis can sometimes overpower the relative strength" (Day 6, :6051) |
| 17,18 | A+ stack / QQQ leg | **DIVERGES — sharpened (feeds B3)** | Day 6 A-setup = holistic confluence STACK (gap up + above PDH + 5-min all-green + OCR holding + HTF level + first pullback + QQQ relative strength), graded on quality not outcome; A+ vs A is a GRADIENT, no checklist ("I wouldn't say it's an A plus setup, but I would say it's an A setup"). Bot scores discrete mechanical checks → primary B3 hypothesis. ALSO: videos operationalize QQQ alignment as moment-to-moment RELATIVE STRENGTH at entry (+ maintenance after entry), NOT level-break direction — Rule-4 "first RTH close through PDH/PMH/PDL/PML" is a proxy, flag for A5/qqqA interpretation |
| 21 | OCR = named concept | **CONFIRMED — accelerator "naming hallucination" worry closed** | Day 4/Day 6/Hayden/BYPS all name it; "the order block and the one candle rule is I consider the exact same thing" (:13-18). NEW ISSUE: OCR ≡ OB per source → coded OCR + OB detectors must not double-count confluence (queued below) |
| 22–24 | OB wick-hold, close-through entry, displacement leg | RE-CONFIRMED | OB sections across groups |
| 32 | 84% reclaim PA gate | Videos add little | 84% only referenced in passing, no full definition; "Reclaims generally work best before 11 am EST" (:2164); "second best entry" framing → secondary setup, consistent with current handling |
| 39 | 2-consecutive-losses quit | Weak support only | Only as a journaling stat ("max consecutive losses, 2"); accelerator remains the source. No contradiction |
| 40 | Max 3/day | RE-CONFIRMED (spread) | "three trades a day" (mm5.0 L8, :4125); "tried to not take more than two" + "best days are one trade" (perf coaching, :4885-4892) |
| 42 | 09:30–11:00 window | **RE-CONFIRMED (multiple)** | "I trade before 11 o'clock" (mm5.0); "not trading after 11 o'clock whatsoever" (accelerator journal); "after 11 momentum is lost" (perf coaching) |
| 43 | VWAP directional | RE-CONFIRMED verbatim | "above VWAP → long, below VWAP → short" (bonus B&B, :296-304) + "you don't really need it" — stays TAG-ONLY per 07-11 measurement |
| 44 | News-day awareness | **NUANCE — sharper than "skip"** | "news always Trumps technicals"; avoid BEFORE news, "we usually like trading right after news events" (Day 10, :120-124). Current skip-news lever skips whole days — source only avoids pre-news. Note for A3/C10 interpretation, config untouched (A2 owns it) |
| 45 | Day-of-week | Still SOURCE-CONFLICT | Adds "Monday and Tuesday most likely get ahead higher" (Day 10, :216) to the existing 3-way disagreement. Keep: test on own data (C7) |

### New flags raised by the videos pass (B2 expanded 2026-07-13: full 36 groups analyzed)

The existing 6 flags (stop_after_win, FVG downgrade, displacement threshold, OCR/OB double-count,
SCARFACE_CONTRACT grounding, regime filter support) are all confirmed by the full 36-group scan.
Additionally:

7. **84% personal rejection (new).** Group 35 (performance coaching): "In my edge I don't take 84
   percent for trades... I feel that when I'm taking them it's my mind tricking me... like a
   revenge trade" — an experienced coach chooses to avoid the 84% rule entirely. Contradicts the
   core system teaching. Implication: 84% rule is optional even per instructors, not mandatory.
8. **VWAP contradiction (new).** Accelerator teaches VWAP as beginner directional filter ("no
   calls under VWAP"). Masterminds 4.0/5.0 say: "I don't even use VWAP in my regular trading...
   VWAP could matter less" (group_26); "VWAP... shouldn't be here anymore" (group_28). Direct
   instructor contradiction across courses. Stays TAG-ONLY per 07-11 measurement.
9. **Entry timing contradiction (new).** Hayden: "Zero percent of the time you enter on the retest
   candle" (group_17, 1293s). Boot camp: "Enter on the level-touch candle close" (group_07,
   4664s). Omen enters at confirm-candle close (= boot camp). Different instructors teach
   different entry timing.
10. **A/A+ grading sharpened (feeds B3).** Group 26 defines A+ as THREE required factors: QQQ
    context + HTF thesis + HTF level. Day 6 defines A as holistic confluence stack (gap up + PDH
    + first 5min green + OCR + HTF level + first pullback + QQQ RS). The bot scores discrete
    mechanical checks vs a gradient definition — feeds B3 inversion hypothesis.
11. **84% rule: A+ entry required (new).** Group 28 (mastermind 5.0): "The thing you need to know
    about the 84% rule is you need an A plus entry." Accelerator omits this requirement entirely.
    Bot currently arms off ANY counted B&R stop-out (RULE84_ARM_BNR_ONLY=True, which requires
    B&R but not A+). Stricter arm gate candidate.
12. **Breakeven rule nuance (new).** Accelerator: "move stop to BE after TP1 hits." Mastermind
    4.0: "only move stop loss when market structure changes" (group_23, 5748s-5774s). Different
    trigger events for the same action. Bot uses accelerator rule (BE after TP1).

### Grading-as-KPI observation (feeds B3)

1. **`stop_after_win` (config.yaml, ON since OPUS-SPEC gap #5) — SOURCE UNTRACEABLE.**
   "Stop-when-green / stop-after-win" returned NOT COVERED in every one of the 36 extraction
   groups; videos file's own gap list calls "stop after 2 consecutive wins" *"either from
   unextracted YouTube (~1300 files) or a hallucination"* (:6107). Closest real quotes are
   softer ("best days are one trade"). The gap #5 rationale "Scarface 1 win / 2 attempts" has
   no verbatim source anywhere in 5 rulebooks. **Not a config change here (paper week freezes
   config; A2/C10 own verdicts)** — but C10 must treat `stop_after_win` as OURS/unsourced,
   not source-mandated. B5 (YouTube tranche) may still locate it.
2. **FVG teaching downgraded.** Across 89 transcripts: ONE passing mention ("boxes can be
   used for... fair value gaps"), zero methodology. The dead-code note's "FVG concept IS
   taught (J-Dub session)" now rests on that single session only — `FVG_RETEST=False` stands,
   and the displacement-anchored variant (C2) should be treated as OURS, not course material.
3. **Displacement threshold confirmed arbitrary.** No numeric threshold in ANY of the 5
   sources ("there's not enough big there's not enough move" — purely subjective). The 1.5×
   body convention (`STRONG_PA_MULT`, `_bnr_displacement`) is OURS quantification. C1 A/B is
   the only arbiter.
4. **OCR/OB double-count risk (new, from #21).** Sources treat one-candle rule and order
   block as the same concept. If `detect_order_block_setup` and any OCR-labeled path can
   both credit the same candle as separate confluence, that inflates stacking. Low priority
   (OCR demoted to A-grade+tight-stop, n≈10/yr) — verify during B4.
5. **Newly source-CONFIRMED (was thin):** `SCARFACE_CONTRACT` first-OTM + weekly now has
   verbatim grounding: "I always trade the first out of the money" (mm1.0 L3, :2819; repeated
   mm2.0 L3) + "I'm trading one week out... this Friday's contracts... one out of the money...
   for most traders, I recommend the one DTEs" (mm2.0 L7, :3123). Nuance: swing trades use
   2–3 OTM; SPY sometimes 0DTE. D1 A/B has a real source spec to test against.
6. **Regime filter support.** "Only trading in a trending market"; sideways = "only the most
   A+ setups... low size"; "I don't take calls when it's down trending" — backs the A2 SMA
   Directional regime filter and the C5 HTF-bias gate direction.

### Grading-as-KPI observation (feeds B3)

Performance coaching treats A/B/C grades as a tracked self-coaching metric ("goal was to
reduce if not eliminate C type trades") — grade quality vs outcome independence is explicit
("just because some trades work doesn't make it A plus"). Bot's C=alert-only matches the
"eliminate C" intent. The A/A+ inversion diagnosis (B3) should start from the Day 6
confluence-stack definition, not from more mechanical criteria.

---

## Actions taken this session (2026-07-11)

1. **KILLED** engulfing→A grading branch (INVENTED, #14). `spec2_grading_check.py` updated.
2. **FIXED** `day_ended` docstring (#41).
3. **TAGGED** (no behavior change — measured offline from the 12mo snapshot, then wired
   into S only where the sign verifies): `[vwap+]/[vwap-]` (#43), `[chase]` ≥0.5% (#48),
   `[pdwick]` (#49), `[hammer]` on 84% re-entries (#32).
4. Prior-day open/close plumbed through backtest_12mo / backtest_week / live_scanner
   for the wick-zone tag.

## Measurement results (12mo re-run, 2026-07-11, post-engulfing-kill)

Baseline: **760 traded signals, 36.0%W, +$61,489 blind-2R** (was 728 / 35.9% / +$57,489 —
engulfing kill was net POSITIVE ~+$4k). Take-tier S≥4+[hammer] max2/day stop-green:
**83 tr, 43.4%W, $25,000/yr ($2,083/mo) — identical to before** (tier = hammer entries;
engulfing and hammer are mutually exclusive shapes, so tier composition unchanged).

| Tag | Full population (651 traded B&R) | Take-tier effect | Decision |
|-----|----------------------------------|------------------|----------|
| `[vwap-]` misaligned | 48 tr, **25.0%W, −$12,000** (aligned: 36.7%, +$62k) | require vwap+: 78 tr 42.3% $21k (worse) | **TAG-ONLY.** Sign verified hard in full pop; tier already screens it out. Encoding = −$4k/yr for nothing |
| `[chase]` ≥0.5% | 107 tr, **28.0%W, −$14,511** (no-chase: 37.3%, +$65k) | exclude: 73 tr 43.8% $23k (±noise) | **TAG-ONLY.** Same story |
| `[pdwick]` | 150 tr, 36.7%W vs 35.5% outside — **community claim REFUTED** (wick-zone entries win slightly MORE; tier exclusion HURTS: 39.7%) | — | **TAG-ONLY, claim rejected on our data.** Do not encode −1 |
| 84% `[hammer]` | 8 of 61 re-entries had hammer; 37.5% vs 37.7% — n too small | — | inconclusive; RULE84_LESSON stays. Revisit with more data |
| QQQ OR-break proxy | aligned 34.8% vs non-aligned 43.1% — **still inverted** | — | reconfirmed: wait for the 8 verbatim rules, do not encode proxy |

S-penalty variant (−1 per bad tag, tier at S′≥4): 81 tr, 43.2%, $24k/yr — no better than baseline.
Bottom line: **the S≥4+hammer tier already absorbs everything the source-rules would add.**
The −$26k/yr combined vwap+chase bleed is real but lives in signals Austin doesn't take.
Tags stay on Discord cards as discretion guards. Tier did NOT move toward 55% this session;
the remaining candidates for that are the queued structural changes below (exits, stops, QQQ rules).

## Queued (blocked or next session)

- QQQ alignment 8 rules → S input (blocked: DeepSeek `qqq-alignment-rules.md`) — #17, #18.
- News-day size-down tag (blocked: GLM `news_days.json`) — #44.
- **HOD/LOD intraday break-retest detector** (#10) — biggest uncoded source setup.
- Liquidity-ladder exit model replacing blind 2R (#7) — backtester rework, big.
- Stop-buffer A/B: retest-candle low vs level−10-15¢ (#6).
- 84% arm-quality gate (A/A+ only) + 5-20min window measurement (#33, #34).
- OB key-level confluence gate (#26) — low priority.
- (B2 2026-07-13) `stop_after_win` unsourced — C10 treats as OURS; B5 may locate it in YouTube tranche.
- (B2 2026-07-13) OCR/OB double-count check during B4 (sources say same concept).
- (B2 2026-07-13) B3 starting hypothesis: grade_trade() mechanical checks vs Day 6 holistic confluence stack; QQQ leg = relative strength at entry, not level-break proxy.
