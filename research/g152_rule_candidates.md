# g152 — the 25 rule candidates worth measuring

**What is different now:** the 39 claims the eight F2 theme agents pulled out of his marks are merged into **25 ranked, individually testable candidates**, each one carrying the exact predicate F5 should implement — no agent has to re-read the corpus to start measuring.

Base `f8740f80`. Inputs: `research/g151_rules_1..8.json` (39 claims). Book: `research/bt2y_trades_retest_on.json` — 498 sessions, 2024-09-03 to 2026-09-02, 127,152 signals, 10,830 fired, 4,022 traded, `entry_fill: close`, 1R = $1,000.

Unit for every F5 number: `research/omen_metrics.first_of_day_arm`, size-gated on `signal_runner.min_risk_floor`, stops through `stop_rule.stop_fill_price`, H1/H2 split at 2025-09-01. **No dollar figure in this file** — F3 measures nothing, it only names what to measure.

## How the 39 became 25

| step | n |
|---|---:|
| claims across the 8 theme files | 39 |
| merged as duplicates across themes | -5 |
| untestable and n_rows < 15, dropped | -7 |
| untestable but n_rows >= 15, moved to *needs a feature* | -2 |
| **ranked candidates** | **25** |

Rank = `n_rows x testability_weight` (book-field 1.0, book-field+bars 0.8, bars-feature 0.6). The row's instruction to drop anything already ratified **and wired** removes nothing: every one of the 25 is either unwired, implemented behind a default-off flag, or wired only into the measured-only S/A/C ladder that never gates a fire. Each row says which.

### The four merge groups (five claims absorbed)

- `exhausted-overextended` = rules_6#2 (n=14) + rules_7#1 (n=3) — same claim, two themes.
- `stop-placement-routed` = rules_2#0 (n=5) + rules_3#1 (n=10) + rules_2#1 (n=1) — 'pick the stop per trade', 'pivot structure is a stop input' and 'take the wick not the level' are one `placed_stop()` mode question.
- `chop-session-refusal` = rules_6#3 (n=95) + rules_7#3 (n=90) — the same corpus rows counted from two themes; moved to *needs a feature*.
- `htf-thesis-forgives-and-vetoes` = rules_6#0 (n=6) + rules_6#1 (n=3) — the forgive and the veto are one unwired mechanism; merged n=9 < 15, so dropped.

### Three source claims are stale — corrected here

- g151_rules_1.json#2 says 'the live TRADE_FLOOR sits at 09:40'. It does not -- TRADE_FLOOR is DELETED (live_scanner.py:759) and backtest_week never had one. Only 487 of 10,830 fired rows are before 09:40, so the time-of-day candidate is a ceiling test, not a floor removal.

- g151_rules_4.json#4 says there is no per-symbol cap anywhere. True for the book; live_scanner has GOVERNOR_S_CAP, which exists but defaults to None and has no backtest_week analog.

- g151_rules_1.json#1 treats the entry anchor as open. The committed book's meta.entry_fill is 'close', so every book row is a bar-close fill -- the forming-candle arm is measured against that, not against a limit.

### Where the bars come from

data_archive/<SYM>/<YYYY-MM-DD>.csv -- CSV, not .json as the spec text says. Columns Datetime,Open,High,Low,Close,Adj Close,Volume; 1-minute; premarket included from 04:00 ET; Datetime carries an ISO offset (-04:00 / -05:00). r['entry_i'] indexes the RTH series with 09:30 = 0 (verified: NVDA 2024-09-03, et 09:46, entry_i 16).

## The 25, ranked

| # | slug | pol | n | testable as | score | wiring today |
|---:|---|---|---:|---|---:|---|
| 1 | `displacement-forgiven-unless-exempt` | S | 87 | book-field | 87.0 | RATIFIED (ballot q18), NOT WIRED INTO DETECTION |
| 2 | `entry-earlier-satisfiable-bar` | S | 84 | bars-feature | 50.4 | RATIFIED AS A SCORING CONVENTION ('an earlier entry mark is a bug repo |
| 3 | `forming-candle-entry-not-extreme` | S | 56 | bars-feature | 33.6 | RATIFIED, PARTIALLY WIRED |
| 4 | `entry-time-of-day-early` | S | 23 | book-field | 23.0 | NOT WIRED AS A PREFERENCE |
| 5 | `exhausted-overextended` | refuse | 17 | book-field | 17.0 | RATIFIED as downgrade variable #4 in his own words (2026-08-23) and im |
| 6 | `brocr-confluence-upgrade-at-fire` | S | 16 | book-field | 16.0 | RATIFIED and implemented as downgrade |
| 7 | `level-not-respected-refusal` | refuse | 11 | book-field | 11.0 | RATIFIED and implemented as downgrade |
| 8 | `stop-placement-routed` | S | 16 | bars-feature | 9.6 | IMPLEMENTED, DEFAULT OFF |
| 9 | `or-break-without-retest` | refuse | 5 | book-field | 5.0 | PARTLY WIRED and not level-specific |
| 10 | `ocr-strict-definition` | S | 6 | bars-feature | 3.6 | IMPLEMENTED, DEFAULT OFF |
| 11 | `be-stop-after-enough-past-pt1` | S | 4 | bars-feature | 2.4 | PARTLY WIRED |
| 12 | `same-color-run-confluence` | S | 4 | bars-feature | 2.4 | NOT WIRED |
| 13 | `per-symbol-s-cap` | refuse | 2 | book-field | 2.0 | LIVE-ONLY AND OFF |
| 14 | `ambiguous-stop-candidates` | refuse | 3 | bars-feature | 1.8 | NOT WIRED |
| 15 | `displacement-graded-not-boolean` | S | 3 | bars-feature | 1.8 | NOT WIRED |
| 16 | `no-level-to-retest-against` | refuse | 3 | bars-feature | 1.8 | NOT WIRED as a distinct rule |
| 17 | `round-number-targets` | S | 3 | bars-feature | 1.8 | NOT RATIFIED, NOT WIRED |
| 18 | `scale-before-the-level` | S | 3 | bars-feature | 1.8 | NOT WIRED |
| 19 | `hammer-wick-level-candle` | S | 2 | book-field+bars-feature | 1.6 | NOT RATIFIED, NOT WIRED |
| 20 | `trail-stop-to-new-pivot` | S | 2 | bars-feature | 1.2 | NOT WIRED |
| 21 | `cheap-stock-refusal` | refuse | 1 | book-field | 1.0 | NOT RATIFIED, NOT WIRED |
| 22 | `index-etf-avoid-unless-clear-htf` | refuse | 1 | book-field | 1.0 | ALREADY MEASURED THE OTHER WAY, NOT WIRED |
| 23 | `scratch-exit-direction-match` | S | 1 | bars-feature | 0.6 | FEATURE DOES NOT EXIST |
| 24 | `standalone-ocr-no-br` | S | 1 | bars-feature | 0.6 | NOT WIRED as a detector |
| 25 | `trend-conditional-scale-ladder` | S | 1 | bars-feature | 0.6 | NOT WIRED |

## Each candidate, with the predicate F5 implements

### 1. `displacement-forgiven-unless-exempt`

**S-indicator · n_rows 87 · book-field · score 87.0 · theme: displacement and candle shape**

*The rule.* A break-and-retest with no displacement on the break leg is forgiven about 90% of the time when he grades S; the ~10% that is not forgiven is forgiven only by one of three named exemptions -- BR+OCR confluence, a bull/bear flag at the open, or a longer-timeframe thesis.

*Wiring today.* RATIFIED (ballot q18), NOT WIRED INTO DETECTION. downgrade.no_displacement exists but the whole S/A/C ladder is measured-only (ENABLE_DOWNGRADE_GRADER off) and carries zero exemption logic -- it returns a bare bool. The A+/A/B/C/X ladder that actually fires never consults it.

*Predicate.* Selection arm over fired rows. KEEP r if ('disp' in r['tags']) or (r['confluence'] == 'yes') or (r['et'] <= '09:45'). DROP r if ('nodisp' in r['tags'] or 'no_displacement' in r['downgrades']) and r['confluence'] == 'no' and r['et'] > '09:45'. The et<=09:45 clause is the flag-at-the-open exemption proxy; the HTF-thesis exemption has no field and is omitted -- say so in the F5 report. Base rates on the 10,830 fired rows: nodisp 8,014; disp 2,285; confluence=='yes' 8,369.

*Merged from:* g151_rules_5.json#0

### 2. `entry-earlier-satisfiable-bar`

**S-indicator · n_rows 84 · bars-feature · score 50.4 · theme: entries and timing**

*The rule.* The engine fires systematically later than the entry he says he would have taken -- 'entry N candles earlier' is the single most repeated comment in the corpus (median ~24 min behind him).

*Wiring today.* RATIFIED AS A SCORING CONVENTION ('an earlier entry mark is a bug report', rulebook q10), NOT WIRED. Nothing in signal_runner.py pulls a fire earlier when the same condition was already satisfiable N bars sooner.

*Predicate.* Bars feature from data_archive/<sym>/<day>.csv, RTH-indexed with 09:30 = index 0 (matches r['entry_i']: NVDA 2024-09-03 has et 09:46 and entry_i 16). For each fired row scan j from the first RTH bar to entry_i-1 and mark j satisfiable when (a) some bar k<j closed through r['level_px'] in r['dir'] direction, (b) bars[j] traded back to within BAR_EXTREME_FRAC (0.25) x range(bars[j-1]) of r['level_px'], and (c) bars[j] closed back on the signal side of r['level_px']. lag_bars = entry_i - min(satisfiable j), 0 when none. Arm: KEEP rows with lag_bars <= L for L in {0,1,2,3}. Uses only bars at index <= entry_i -- no lookahead.

*Merged from:* g151_rules_1.json#0

### 3. `forming-candle-entry-not-extreme`

**S-indicator · n_rows 56 · bars-feature · score 33.6 · theme: entries and timing**

*The rule.* He takes the entry while the candle is still forming, not after it closes at the low/high of day -- a close at the extreme kills the risk:reward.

*Wiring today.* RATIFIED, PARTIALLY WIRED. BAR_EXTREME_FRAC=0.25 (signal_runner.py:554) is the tolerance unit but the book's entry_fill is 'close' (meta.entry_fill), so every book row entered at the bar close. The rulebook flags the anchor question -- LOD/HOD vs the forming candle -- as still open.

*Predicate.* Bars feature at the signal bar only. rng = High-Low of bars[entry_i]. For r['dir']=='call': extreme_frac = (r['entry'] - Low) / rng. For 'put': extreme_frac = (High - r['entry']) / rng. Because r['entry'] is the bar close, extreme_frac says how near the fill sat to the bar's adverse extreme. Arm: DROP rows with extreme_frac <= 0.25 (long filled in the bottom quartile of its own bar = 'entered at LOD'); sweep the cut at {0.15, 0.25, 0.35}. The signal bar's OHLC is complete at close-fill time, so this is not lookahead.

*Merged from:* g151_rules_1.json#1

### 4. `entry-time-of-day-early`

**S-indicator · n_rows 23 · book-field · score 23.0 · theme: entries and timing**

*The rule.* Earlier in the day is better -- more volatility, cleaner trends -- and he does not want new entries late in the window (past ~11:00 it is management only).

*Wiring today.* NOT WIRED AS A PREFERENCE. Correction to the source claim: the 09:40 TRADE_FLOOR it cites as live is DELETED (live_scanner.py:759, 'it cut 10 of his 34 S days'), and backtest_week never had one. Only 487 of 10,830 fired rows sit before 09:40, so this is a CEILING test, not a floor removal.

*Predicate.* Selection arm on the committed rows: KEEP r if '09:30' <= r['et'] <= T, sweeping T over {'09:45','10:00','10:30'}; plus a control arm at T='11:00' (inert -- every row already satisfies it, max et in the book is 10:59). Report candidates/day at each T alongside $/day, because the tightest cut is also the biggest recall risk.

*Merged from:* g151_rules_1.json#2

### 5. `exhausted-overextended`

**refusal-indicator · n_rows 17 · book-field · score 17.0 · theme: HTF bias and trend / refusals**

*The rule.* A stock that has already made its big move for the day is refused or downgraded -- the setup is real but the move is spent, there is no room left to run.

*Wiring today.* RATIFIED as downgrade variable #4 in his own words (2026-08-23) and implemented as downgrade.exhausted (|close - day open| >= EXHAUSTED_ATR x ATR at i), but the S/A/C ladder is measured-only and never gates a live or backtest fire.

*Predicate.* Selection arm: DROP r if 'exhausted' in r['downgrades']. 1,066 of 10,830 fired rows carry it. Second arm, continuous, from data_archive at the signal bar only: extension = |Close[entry_i] - Open[first RTH bar]| / ATR14(bars[:entry_i+1]); sweep the drop threshold over {1.5, 2.0, 2.5, 3.0} to find whether EXHAUSTED_ATR is set at the right place rather than only whether the flag helps.

*Merged from:* g151_rules_6.json#2, g151_rules_7.json#1

### 6. `brocr-confluence-upgrade-at-fire`

**S-indicator · n_rows 16 · book-field · score 16.0 · theme: OCR and the 84% rule**

*The rule.* BR+OCR confluence is a +1 upgrade and never a downgrade, capped at +1 total even when a second independent confluence type (multi-level) fires on the same signal.

*Wiring today.* RATIFIED and implemented as downgrade.has_confluence (capped at one point), but that module is the measured-only S/A/C ladder. signal_runner._grade_pa -- the ladder that actually gates trades -- does not consult it.

*Predicate.* Selection arm: KEEP r if r['confluence'] == 'yes' (equivalently 'brocr' in r['tags']; the two agree on the book). 8,369 of 10,830 fired rows qualify, so this is a ~23% cut, not a 1-3/day gate on its own -- pair it with one of the higher-cut candidates in F7. Also report the inverse arm (confluence=='no') to confirm the sign.

*Merged from:* g151_rules_4.json#0

### 7. `level-not-respected-refusal`

**refusal-indicator · n_rows 11 · book-field · score 11.0 · theme: levels and level quality**

*The rule.* A level that is not being respected -- candles closing through it or chopping on it instead of reacting off it -- is a reason to refuse the trade outright (grade none/C/X), not merely a downgrade dimension.

*Wiring today.* RATIFIED and implemented as downgrade.level_not_respected (CHOP_TOUCHES=2), measured-only. Untested as an outright veto: today it costs at most one point of score.

*Predicate.* Selection arm: DROP r if 'level_not_respected' in r['downgrades']. 7,176 of 10,830 fired rows carry it -- a 66% cut, the single largest of any candidate here, so candidates/day and S recall are the numbers that decide it, not $/day. Report the veto arm and a softer arm (drop only when it co-occurs with r['confluence']=='no') side by side.

*Merged from:* g151_rules_3.json#2

### 8. `stop-placement-routed`

**S-indicator · n_rows 16 · bars-feature · score 9.6 · theme: stops, wick vs level, disaster stop**

*The rule.* The stop is not one derived point but a choice among structure candidates -- the entry candle's extreme, the wick of the OCR, or the broken level / pivot structure -- and the right one should be picked per trade for the best tradable risk. Where the two disagree and risk is tight he takes the wick, not the level; and pivot structure is a stop input, not a chart overlay.

*Wiring today.* IMPLEMENTED, DEFAULT OFF. signal_runner.placed_stop already has modes {entry_bar, candle_entered, broken_level, ocr_wick, routed} but STOP_PLACEMENT defaults to 'entry_bar' (signal_runner.py:1192) -- the byte-identical-to-legacy path. Nothing forces the flag on.

*Predicate.* Bars feature, no engine re-run. For each fired row recompute the routed stop from data_archive at index <= entry_i: r['setup']=='one_candle_rule' -> ocr_wick (the extreme of the OCR candle), r['setup']=='break_and_retest' -> broken_level (= r['level_px']). Re-derive risk = |r['entry'] - routed_stop|, re-gate on signal_runner.min_risk_floor(r['entry']), and re-run the exit through stop_rule.stop_fill_price against the book's own bars. Report routed vs the shipped entry_bar stop. Also emit stop_disagree = |routed - r['stop']| / |r['entry'] - r['stop']| for the wick-vs-level tie-break sub-claim (n=1, AMZN_2026-01-14).

*Merged from:* g151_rules_2.json#0, g151_rules_3.json#1, g151_rules_2.json#1

### 9. `or-break-without-retest`

**refusal-indicator · n_rows 5 · book-field · score 5.0 · theme: levels and level quality**

*The rule.* A break of the opening range that fires without a subsequent retest of ORH/ORL is a lower-probability setup / fakeout, even though the opening range is one of his six levels.

*Wiring today.* PARTLY WIRED and not level-specific. RETEST_REQUIRED defaults ON (signal_runner.py:221) since 2026-09-02, yet 2,711 of 10,830 fired rows still carry 'no_retest' -- the flag caps grade, it does not veto. No rule treats OR levels differently from pivots.

*Predicate.* Selection arm: DROP r if r['level'] in ('OR high','OR low') and 'no_retest' in r['downgrades']. Control arm: DROP r if 'no_retest' in r['downgrades'] regardless of level -- if the OR-specific arm is no better than the blanket one, the claim's OR specificity is not real. Base rates: OR high 1,140 + OR low 1,037 fired rows.

*Merged from:* g151_rules_3.json#0

### 10. `ocr-strict-definition`

**S-indicator · n_rows 6 · bars-feature · score 3.6 · theme: OCR and the 84% rule**

*The rule.* OCR means literally one candle opposite-coloured to the prevailing trend, and the operational test for whether a candle counts is whether it is usable as the stop -- not its distance from entry.

*Wiring today.* IMPLEMENTED, DEFAULT OFF. signal_runner imports ocr_is_his / OCR_STRONG_PA_MULT and encodes the clause list, but OCR_STRICT defaults to '0' (signal_runner.py:63).

*Predicate.* Bars feature, no engine re-run -- evaluate signal_runner.ocr_is_his(bars, i) at the signal bar from data_archive for every fired row whose r['setup']=='one_candle_rule' or whose r['confluence']=='yes' (the OCR half of BR+OCR). Arm: DROP OCR-derived rows where ocr_is_his is False -- this reproduces the OCR_STRICT=1 semantic as a post-hoc filter on the committed book. Report how many of the 8,369 confluence rows survive.

*Merged from:* g151_rules_4.json#2

### 11. `be-stop-after-enough-past-pt1`

**S-indicator · n_rows 4 · bars-feature · score 2.4 · theme: management and targets**

*The rule.* Moving the stop to breakeven should happen only after price has moved 'enough' past PT1 -- he flags the threshold himself as unresolved and wants it measured, not assumed.

*Wiring today.* PARTLY WIRED. A break-even trail after tranche 1 is shipped, but with no 'enough' threshold -- it arms on the PT1 touch. The rulebook (lines 806-811) records the question as open.

*Predicate.* Exit-side arm, not a selection arm -- it cannot change which day gets traded, so report R and $/day on the same first_of_day_arm rows, not candidates/day. For each traded row replay the post-entry bars from data_archive and arm the BE stop only once price has travelled k beyond PT1, sweeping k over {0.25R, 0.5R, 0.75R, 1.0R}; re-run every stop through stop_rule.stop_fill_price. Decides only on bars already elapsed, so no lookahead.

*Merged from:* g151_rules_8.json#2

### 12. `same-color-run-confluence`

**S-indicator · n_rows 4 · bars-feature · score 2.4 · theme: displacement and candle shape**

*The rule.* A run of 2-3 consecutive same-coloured candles into the entry reads as strength in its own right, additive to break-leg displacement -- but one of his own cards cuts the other way, preferring an isolated candle in trend.

*Wiring today.* NOT WIRED. downgrade.has_confluence knows exactly one thing (BR+OCR co-occurrence); a same-colour-run signal does not exist anywhere in the codebase.

*Predicate.* Bars feature from data_archive, bars at index <= entry_i-1 only: run_len = count of consecutive bars ending at entry_i-1 with the same sign(Close-Open). Report three buckets SEPARATELY -- run_len in {0,1} (isolated), {2,3}, >=4 -- against S rate and realized R. Do NOT sum into a score: NVDA_2026-06-25 says two green candles at the open read as LESS clean, so a naive additive feature gets that card backwards.

*Merged from:* g151_rules_5.json#4

### 13. `per-symbol-s-cap`

**refusal-indicator · n_rows 2 · book-field · score 2.0 · theme: OCR and the 84% rule**

*The rule.* He caps how many S trades one symbol can produce -- he said 2, then revised to 3, with a back-of-envelope ~0.8 S-trades/day/symbol.

*Wiring today.* LIVE-ONLY AND OFF. live_scanner.GOVERNOR_S_CAP exists but defaults to None (uncapped) and has no backtest_week analog, so the committed book enforces no per-symbol or per-day cap at all. His ballot gave three conflicting numbers; unresolved.

*Predicate.* Selection arm: within each (r['sym'], r['day']) group ordered by r['et'], KEEP only the first k fired rows, k in {2,3}. Note up front that on the one-trade-a-day unit this is close to inert by construction -- the honest read is candidates/day and precision against his marks, and whether the cap only trims duplicate re-fires on the same r['level_px'].

*Merged from:* g151_rules_4.json#4

### 14. `ambiguous-stop-candidates`

**refusal-indicator · n_rows 3 · bars-feature · score 1.8 · theme: stops, wick vs level, disaster stop**

*The rule.* A stop that is ambiguous -- two live stop candidates that do not agree, or a muddled structure with several recent highs and lows -- is a downgrade in itself, independent of the entry criteria being clean.

*Wiring today.* NOT WIRED. No variable in downgrade.py or signal_runner.py counts competing stop candidates.

*Predicate.* Bars feature from data_archive at index <= entry_i. Compute three stops: ocr_wick (extreme of the OCR candle), broken_level (= r['level_px']), entry_bar (the signal bar's adverse extreme). avg_rng = mean(High-Low) over the prior 10 bars. Flag ambiguous when at least two of the three differ by more than 1 x avg_rng AND neither is nested inside the other (i.e. both sit on the same side of the entry with a gap between them). Arm: DROP ambiguous rows. Report the ambiguous rate against his S/A/C/none grades on the 100-card deck as well as against realized R -- with n=3 source cards the grade read is the honest one.

*Merged from:* g151_rules_2.json#2

### 15. `displacement-graded-not-boolean`

**S-indicator · n_rows 3 · bars-feature · score 1.8 · theme: displacement and candle shape**

*The rule.* Displacement strength is graded, not boolean -- a weak displacement candle still fails to earn an A, and borderline cases are explicitly hard to call on displacement strength alone.

*Wiring today.* NOT WIRED. downgrade.no_displacement is strictly boolean (body < DISP_BODY_MULT x avg_body); no graded threshold exists anywhere.

*Predicate.* Bars feature from data_archive. break_bar = the last bar at index <= entry_i whose Close crossed r['level_px'] in r['dir'] direction. disp_ratio = |Close-Open| of break_bar / mean(|Close-Open|) over the 10 bars before it. Arm: KEEP rows with disp_ratio >= T, sweeping T over {1.0, 1.5, 2.0, 2.5} and reporting the shipped boolean (DISP_BODY_MULT) as one point on the same curve, so 'graded beats boolean' is a comparison and not an assertion.

*Merged from:* g151_rules_5.json#1

### 16. `no-level-to-retest-against`

**refusal-indicator · n_rows 3 · bars-feature · score 1.8 · theme: refusals**

*The rule.* No level to break-and-retest against is a standalone refusal, distinct from a level being present but chopped through. He does NOT refuse for lacking a level to TARGET -- QQQ_2025-08-01 is graded S with exactly that complaint.

*Wiring today.* NOT WIRED as a distinct rule. downgrade.level_not_respected covers a level that exists and is being chopped, which is a different failure mode.

*Predicate.* Book proxy first (cheap): DROP r if r['level'] == 'other' (531 of 10,830 fired) or r['level_name'].startswith('not-his:'). Bars form: from data_archive, no named level (PDH/PDL/PMH/PML/ORH/ORL/HOD/LOD) within 0.5 x ATR14 of Close[entry_i]. Any implementation must distinguish entry-level absence from target-level absence -- the QQQ card falsifies the target version.

*Merged from:* g151_rules_7.json#0

### 17. `round-number-targets`

**S-indicator · n_rows 3 · bars-feature · score 1.8 · theme: management and targets**

*The rule.* Targets should include whole psychological round numbers (188, 189), not only chart levels (HOD/LOD/PDH/PDL/pivots).

*Wiring today.* NOT RATIFIED, NOT WIRED. 'psych' appears nowhere in omen-rulebook.md.

*Predicate.* Exit-side arm. round_grid = whole dollars, or half dollars when r['entry'] < 20. cand = the nearest round_grid price strictly between r['entry'] and r['target'] in the trade direction. When cand exists, replace the target with cand and replay the exit from data_archive using stop_rule.stop_fill_price for stops; otherwise leave the row untouched. Report the fraction of rows the substitution touches before reporting its R.

*Merged from:* g151_rules_8.json#3

### 18. `scale-before-the-level`

**S-indicator · n_rows 3 · bars-feature · score 1.8 · theme: management and targets**

*The rule.* Scale-out orders should sit slightly before the exact level (HOD/LOD), not resting at it, because price stalls and consolidates right at the level before tagging it.

*Wiring today.* NOT WIRED. The only 'few cents' ruling in omen-rulebook.md (line 1437) is the entry retest tolerance, a different mechanism -- and that one was swept to zero (g87).

*Predicate.* Exit-side arm, the mirror of the zero-tolerance retest finding. Fill the target at target - b for r['dir']=='call' and target + b for 'put', with b in {$0.02, $0.05, 0.05 x ATR14(entry_i)}. Report the change in target-hit RATE and in realized R separately -- the whole claim is that the rate rises more than the R per fill falls. Size gate stays on signal_runner.min_risk_floor; b never touches the stop, so the risk denominator cannot collapse the way g87's entry tolerance did.

*Merged from:* g151_rules_8.json#4

### 19. `hammer-wick-level-candle`

**S-indicator · n_rows 2 · book-field+bars-feature · score 1.6 · theme: displacement and candle shape**

*The rule.* A candle with a visible wick reads as more predictable, better-respected support/resistance in a trending market than a full solid-body candle -- separate from whether it is tagged OCR.

*Wiring today.* NOT RATIFIED, NOT WIRED. The rulebook defines the order-block stop-usability test but never scores a standalone wick-quality signal. Thin: n=2, and one of the two is a rule-ballot answer rather than a graded symbol-day.

*Predicate.* Book proxy: KEEP r if 'hammer' in r['tags'] (1,202 of 10,830 fired). Bars form on the level-generating candle (the bar that set r['level_px']): for r['dir']=='call' wick_ratio = (min(Open,Close) - Low)/(High - Low); for 'put' wick_ratio = (High - max(Open,Close))/(High - Low). Arm: KEEP wick_ratio >= 0.3, swept over {0.2, 0.3, 0.4}. Report the book proxy and the bars feature side by side -- if they disagree, the 'hammer' tag is not measuring what the claim says.

*Merged from:* g151_rules_5.json#2

### 20. `trail-stop-to-new-pivot`

**S-indicator · n_rows 2 · bars-feature · score 1.2 · theme: stops, wick vs level, disaster stop**

*The rule.* Once a trade has moved favourably -- the second push after an initial hold -- the stop should be raised to the newly formed, tighter pivot level rather than left at the original structural stop.

*Wiring today.* NOT WIRED. Distinct from the shipped break-even trail: this names a specific tighter structural level, not BE.

*Predicate.* Exit-side arm that can only tighten a stop already past min_risk_floor, so it cannot manufacture a small risk denominator. After entry, on each new bar find the most recent 3-bar pivot in the trade's favour (a bar whose Low is below both neighbours for a call, High above both for a put), and move the stop there when it is tighter than the current stop and still on the safe side of entry. Replay through stop_rule.stop_fill_price. Report on ALL traded rows, not winners only -- restricting to winners is the look-ahead that would make this arm look free.

*Merged from:* g151_rules_2.json#3

### 21. `cheap-stock-refusal`

**refusal-indicator · n_rows 1 · book-field · score 1.0 · theme: refusals**

*The rule.* Cheap, low-priced stocks are harder to trade and get refused or capped below S, independent of setup quality.

*Wiring today.* NOT RATIFIED, NOT WIRED. Thin: exactly one outright refusal card (IREN_2025-08-22, X); the other two quotes are a downgrade note on a card still graded A, and a rule-ballot comment.

*Predicate.* Selection arm: DROP r if r['entry'] < P, P in {$10, $20}. Report it as an effect-size measurement, not a rule -- one refusal card cannot establish a price floor, and the F5 report must say so in the first sentence.

*Merged from:* g151_rules_7.json#2

### 22. `index-etf-avoid-unless-clear-htf`

**refusal-indicator · n_rows 1 · book-field · score 1.0 · theme: refusals**

*The rule.* Index ETFs (SPY, QQQ) are avoided by default and traded only when the higher-timeframe direction is very clearly bullish or bearish.

*Wiring today.* ALREADY MEASURED THE OTHER WAY, NOT WIRED. g91_lane_slice.py measured the index lane at 2.3 cand/day and $51/day, and CLAUDE.md records the decision to keep the pool FULL because narrowing caps the ceiling at $437/day against his $397 bar. One symbol-day of textual support.

*Predicate.* Selection arm: DROP r if r['sym'] in ('SPY','QQQ') and not (r['aligned'] == 'with' and r['bias'] in ('bullish','bearish')). Base rate: r['cls']=='etf' is 13,316 of 127,152 rows. This is a corroboration check on an existing decision -- if it moves nothing, say nothing moved.

*Merged from:* g151_rules_7.json#4

### 23. `scratch-exit-direction-match`

**S-indicator · n_rows 1 · bars-feature · score 0.6 · theme: displacement and candle shape**

*The rule.* A scratch-exit rule should require the entry candle's direction to match the prevailing trend before it can fire.

*Wiring today.* FEATURE DOES NOT EXIST. There is no scratch exit in the codebase; the single source row is a rule-ballot answer ('im ok with implementing scratch'), a conditional yes on an unbuilt feature, not a graded card.

*Predicate.* Descriptive split only -- there is nothing to gate. From data_archive: entry_dir = sign(Close[entry_i] - Open[entry_i]); trend_dir = +1 for r['dir']=='call', -1 for 'put'. Report S rate and realized R for entry_dir == trend_dir vs not. If the split is flat, the precondition is moot and the scratch feature should not be built on this basis.

*Merged from:* g151_rules_5.json#3

### 24. `standalone-ocr-no-br`

**S-indicator · n_rows 1 · bars-feature · score 0.6 · theme: OCR and the 84% rule**

*The rule.* OCR is standalone-valid: a one-candle-rule level with no break-and-retest event can still be a full, clean S setup on its own.

*Wiring today.* NOT WIRED as a detector. downgrade.find_ocr can locate a standalone OCR level, but BreakAndRetestDetector and RuleOf84Detector both arm only off a level-break event, so no signal type fires on an OCR level alone.

*Predicate.* Measurable on the committed book without a new detector: treat r['setup'] == 'one_candle_rule' (6,803 of 127,152 rows) as its own stream and report its $/day, mean R and S rate against the break_and_retest stream (119,806). Separately, a bars scan for how often a clean standalone OCR appears with no accompanying break -- that count decides whether a new detector is worth building. n=1 card: this is a sizing exercise, not a rule.

*Merged from:* g151_rules_4.json#1

### 25. `trend-conditional-scale-ladder`

**S-indicator · n_rows 1 · bars-feature · score 0.6 · theme: management and targets**

*The rule.* The scale-out ladder should vary with the day's regime: on a trending day run a smaller first scale and let more ride (50/20/10/10); on a choppy day take profit earlier and heavier (30/30/30/10).

*Wiring today.* NOT WIRED. omen-rulebook.md ratifies a single fixed 30/30/30/10 ladder with no trend-conditional variant, and paper_trader.py's LIVE_LADDER_PLAN is default OFF and not tied to any regime.

*Predicate.* Exit-side arm with a CAUSAL regime feature only: trendiness = |Close[entry_i] - Open[first RTH bar]| / sum(|Close[j]-Close[j-1]|) over the RTH bars up to entry_i, from data_archive. Split at the in-sample H1 median and apply 50/20/10/10 above, 30/30/30/10 below. Read g151_rules_6.json#3 first: the finished-chart version of this measure separates his yes/no, but nine causal proxies were coin flips -- so treat a win here as suspect until F6 checks the split point was not fit on H2.

*Merged from:* g151_rules_8.json#1

## Needs a feature — real, high-n, and not measurable tonight

Both cleared the n_rows >= 15 bar, so they are kept rather than dropped, but neither has a predicate anyone can write today.

### `chop-session-refusal` — n_rows 95, refusal-indicator

*The rule.* A choppy, noisy session -- candles chopping around a level or channel instead of trending cleanly -- is his single most common stated refusal, and cleaner/trendier days correlate with his S verdicts.

*Why there is no predicate.* Already run to a conclusion and explicitly killed as a shippable filter. On the FINISHED chart, session trendiness separates his yes/no at p=0.014 and holds on the full 812-day corpus (0.133 vs 0.101, p<0.0001), and his own 'chop' tag scores 0.072R against a 0.123R baseline (p=0.70, not predictive). Nine causal, pre-09:30-observable proxies were tried and every one is a coin flip, two leaning backwards; the best honest filter is +$46/day with a -$41 to +$140 band and costs 39 of 163 S days. What is missing is a causal feature nobody has found -- not an arm. Do NOT re-derive a chop filter without re-reading that finding.

*Merged from:* g151_rules_6.json#3, g151_rules_7.json#3

### `management-tag-splits-by-grade` — n_rows 40, S-indicator

*The rule.* The blind-mark management tag splits by grade: cards tagged 'Hold to 2R' are mostly S (9 of 12 unique symbol-days), cards tagged 'Scale 1R + runner' split evenly S/A (14 of 28).

*Why there is no predicate.* The management tag is assigned after grading and after entry, so it cannot gate whether to fire -- it is an outcome label, not a signal-time feature. What is missing is a PRE-ENTRY feature that predicts which management style he picks (tighter structure -> hold to 2R is the obvious hypothesis). New observation, not in omen-rulebook.md.

*Merged from:* g151_rules_8.json#0

## Dropped — untestable and n_rows < 15

| slug | n | why |
|---|---:|---|
| `htf-thesis-forgives-and-vetoes` | 9 | Untestable and n<15 (merged 6+3). A higher-timeframe thesis can forgive a downgraded setup, and an opposed one can veto a clean setup. Ratified in principle, unwired: the rulebook settles that HTF is a RANK rule, not a wait or a veto, and the only committed HTF flag (HTF_BIAS_VETO, an SMA20-of-hourly formula nobody authored) is default-off. No bars-derivable proxy for 'his HTF thesis' exists, and the DIA 2025-10-06 card uses the phrase in both directions on the same theme. This is F4 corpus territory (Scarface/Jdub charts), not a book field. |
| `deck-shows-too-little-history` | 6 | Untestable, n<15, and not a market rule at all -- when he cannot see enough candle history before the signal bar he marks X/none for lack of context. That is a grading-tool artifact of build_deck.py / probe_page.py chart windows. Listed here only so a downstream merge does not mistake it for a refusal rule. |
| `stop-width-preference-unsettled` | 3 | Untestable, n<15, and genuinely contradictory: some marks want tighter stops, others explicitly want more room, and 'too tight' is itself a downgrade reason. Cannot be turned into one predicate without picking a side he has not picked. The real signal buried in the 'muddled' complaints is ambiguous-stop-candidates, which is kept. |
| `multi-tier-target-ladder` | 2 | Untestable, n<15. The fraction split (30/30/30/10) and 'target = nearest structural level, not a fixed 2R' are already ratified in omen-rulebook.md. The only unratified piece is choosing the final runner leg's target from HTF bias or a median-move average, and there is no field for an HTF-selected runner target to test against. |
| `ocr-candle-selection-unresolved` | 1 | Untestable, n<15. Which candle to treat as the OCR when several sit near the entry is a judgement call he flags himself as needing more code work ('needs to be discussed more', 'can be broadened by code'). Not ratified, not wired, and no predicate exists -- this is a ballot question for the next grilling round. |
| `ocr-grading-path-underbuilt` | 1 | Untestable, n<15, and not a standalone claim -- 'wire downgrade to understand OCR better' is a general flag that corroborates brocr-confluence-upgrade-at-fire and ocr-strict-definition, both of which are kept. Carried as supporting evidence that the OCR path's unwired pieces should be turned on together rather than singly. |
| `trendline-break-second-confirmation` | 1 | Untestable, n<15. A trendline break needs a second confirmation candle with strength. One symbol-day (ORCL 2025-03-28), and trendlines are not one of his six levels nor a setup family anywhere in omen-rulebook.md. A ballot question, not a candidate. |

## What F5 should watch for

- **Cut size is the story, not $/day.** `level-not-respected-refusal` alone removes 7,176 of 10,830 fired rows and `displacement-forgiven-unless-exempt` touches 8,014. Report candidates/day and S recall first; a $/day move on a 66% cut is mostly a different book.

- **A C-cap gate adds candidates as well as removing them.** `backtest_week.DEDUPE_FIRES_ONLY` means only a *fired* signal claims the dedupe suppression window, so capping one releases previously-suppressed candidates on the same level. This killed the g93 forecast. Every arm here must be measured on the real book, never modelled.

- **Size-gate every money number.** Six of the 25 touch the stop (`stop-placement-routed`, `ambiguous-stop-candidates`, `trail-stop-to-new-pivot`, `be-stop-after-enough-past-pt1`, `displacement-graded-not-boolean` via the break bar, `scale-before-the-level` via the target). A fill landing a cent from its stop is a 100,000-share position; `signal_runner.min_risk_floor` is the gate, and g87 printed $15,119/day without it.

- **The error bar exceeds the arms.** Every A/B this project has run moves less than ±1.5799R. Nine of the 25 rest on n_rows <= 3 — those are effect-size measurements, and the F5 report should open by saying so rather than closing by admitting it.

