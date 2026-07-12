# Hallucination Audit — coded rules vs the 4 rulebooks (2026-07-11)

Scope per next-session-brief: every rule in `omen_bot.py` (detect_break_retest,
detect_order_block_setup, one-candle routing, grading) and `signal_runner.py`
(grading, stops, targets, S score, 84% arm/fire) diffed against:
`scarface-rules-{accelerator,mastermind,coaching-bonus,youtube}.md`.

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
| 14 | **Bullish/bearish engulfing at level = A** | Engulfing appears in ZERO of the 4 rulebooks (101 Circle + 558 YouTube transcripts) | **INVENTED** | **KILLED 2026-07-11** — branch removed from `_grade_pa` |
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
