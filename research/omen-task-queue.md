# OMEN Master Task Queue (2026-07-13)

Goal: tier currently 90 tr/yr, 44.4%W, ~$2,500/mo. Synthesis projects $88–95k/yr all-signals
with recommended config. Target: verified 50%+W tier, live paper-validated, then real money.

## How to dispatch
One task per Claude Code session. Prompt = "Do task <ID> from tradingbot/research/omen-task-queue.md".
Every task is self-contained (files + done-when listed). Mark done by checking the box + one-line result.
Model column = cheapest model that safely does it. HARD RULE for all tasks: signal logic decisions
(omen_bot.py / signal_runner.py behavior changes) = Opus/Fable only; cheaper models run/measure/report.
No task commits — Fable reviews + commits in batches (A1-style tasks).

Models: HAIKU (one-liners, config, schtasks) · SONNET (mechanical edits, run backtests, tables) ·
GLM (same as Sonnet, free-er) · DEEPSEEK (bulk extraction) · OPUS (signal-path code) ·
FABLE (interpretation, audits, go/no-go decisions).

Dependency chain: A before everything live. B1→B2→B3→B4. C tasks independent of each other,
all need A1. F needs A+C done.

---

## EXECUTION LOOP (state as of 2026-07-13: A1, B1, E1, E2 done)

Per-session ritual (every task, any model):
1. New Claude Code session, model per task row.
2. Paste: `Do task <ID> from C:\Users\aharg\tradingbot\research\omen-task-queue.md. When done: check its box in that file with a one-line result, and add a session note to hermes-vault-sync/projects/omen-trading-bot.md. Do NOT commit.`
3. After session: eyeball its one-line result. Backtest tasks: open the report it names —
   **trade count must be >0** (0 trades = yfinance rate-limited garbage → wait 30–60 min, re-dispatch same task).
4. Cross off. Next.

Lane rule (unchanged): backtest/code lane is SERIAL — never two of these running at once.
Extraction + infra lanes run parallel to it. Commit checkpoints: dispatch a Fable
"review + commit everything uncommitted, A1-style" session at each ⛳ marker.

### Round 1 (3 sessions, parallel OK)
| Lane | Task | Model |
|---|---|---|
| backtest | **A2** recommended config | Sonnet |
| audit | **B2** merge videos rulebook into audit + catalog (ALSO: commit B1 pile first) | Fable |
| infra | **E3** pre-market Discord card | Sonnet |

### Round 2
| backtest | **A3** composition check | GLM |
| audit | **B3** A/A+ inversion diagnosis | Fable |
| infra | **E4** sentry staleness alert | Sonnet |

### Round 3
| backtest | **A4** combined tier run | Fable |
| audit | (B4 waits — it edits signal code, joins backtest lane) | — |
| infra | **E5** Sunday auto-backtest cron | Sonnet |

### Round 4
| backtest | **A5** QQQ live plumbing | Opus |
⛳ commit checkpoint (Fable) → **START PAPER WEEK (A6: 5 trading days, log each close)**

### Paper week — backtest lane keeps grinding, SERIAL, one per session:
**B4** (Opus) → **C1** (GLM) → **C2** (GLM) → **C3** (Sonnet) → **C6** (Sonnet) → **C7** (Sonnet)
→ **C8** (Sonnet) → **C5** (Opus) → **C9** (Opus) → **C4** (Fable) → ⛳ → **C10** (Fable, synthesis)
Optional parallel anytime: **B5** (DeepSeek YouTube tranche).

### After C10 + paper week
**D1** (GLM) → **D2** (Opus) → **D3** (Sonnet) → ⛳ →
**F1** (Fable) → **F2** (Fable, 2-week shadow) → **F3** (Fable, go/no-go) → [F4 optional].

### Standing rules
- 0-trade backtest = rate limit, not a result. Re-run later, never accept it.
- Any task that wants to edit omen_bot.py/signal_runner.py but isn't Opus/Fable → abort, re-dispatch higher.
- Config only changes at: A2, C10 verdicts, D verdicts. C tasks measure behind flags, they don't flip defaults.
- Paper week freezes config — C results wait for C10 before anything goes live.
- You only ever: dispatch, eyeball result lines, push commits after ⛳ sessions.

---

## Phase A — Ship the measured wins (recommended config → live paper)

- [x] **A1** FABLE — Review the 5 modified code files (signal_runner, live_scanner, options_sizer,
  config.yaml, backtest_week), then local-commit the whole 82-file pile in logical chunks
  (.gitignore journal/*.log first). Done-when: clean `git status`, Austin only pushes.
  *Done 2026-07-13: 8 commits (eeeb8895..9bb5d5ce+), review fixed 2 issues — dry-run double-import
  bug (toggles hit dead module copy) + RULE6_ENABLED left True from comparison run, reverted.*
- [x] **A2** SONNET — Apply recommended config from Desktop/unified_backtest_synthesis.md:
  drop SMCI/SPY/MSTR/RIVN from symbol list, entry cutoff 10:30, skip-news ON, RULE6 stays OFF,
  SMA Directional 5% regime filter ON. config.yaml + live_scanner defaults. No signal-logic edits.
  Done-when: config diff matches synthesis §recommendations, live_scanner --once --paper runs clean.
  *Done 2026-07-13: 4 symbols dropped (28→24), ENTRY_CUTOFF=10:30 + SKIP_NEWS entry gates added
  to live_scanner (marking continues, new entries blocked), RULE6/regime already correct;
  --once --paper clean, cutoff gate verified via forced ENTRY_CUTOFF. Uncommitted.*
- [x] **A3** GLM — Composition check: 12mo backtest with ALL A2 changes combined (levers were
  measured one-at-a-time; interactions unverified). Report vs $88–95k projection, per-lever
  attribution table. Done-when: report in research/, verdict line "composes / doesn't because X".
  *Done 2026-07-13: Doesn't compose — +$60k vs +$88-95k projected. Levers overlap heavily. Report: research/a3_composition_check.md.*
- [x] **A4** FABLE — Combined tier run: qqqA-S+1 + --skip-news + --entry-cutoff 10:30 (queued
  "next session #1" from F-session). Interpret: new tier stats vs 90/44.4%/$2,500. Done-when:
  tier verdict updated in vault doc.
  *Done 2026-07-13: combined config HALVES tier — 56 tr/yr, 41.1%W, $13k/yr ($1,083/mo) vs
  90/44.4%/$2,500. No re-run (A3 charts json = exact config): skip-news tier-neutral ($0),
  symbol drops −$4k, cutoff −$1k, slot-churn −$9k. Config untouched; C10 decides. Vault updated.*
- [x] **A5** OPUS — QQQ plumbing in live_scanner: fetch QQQ 1-min candles each cycle, compute
  Rule-4 alignment (first RTH close through PDH/PMH/PDL/PML before entry), S+1 on live cards +
  [qqqA] tag. Backtest logic already in repo — port, don't reinvent. Done-when: --once --paper
  shows QQQ state in scanner_status.json, dry-run card carries tag.
  *Done 2026-07-13: ported backtest_12mo.qqq_level_breaks → live_scanner.compute_qqq_breaks
  (reuses get_daily_context for QQQ PDH/PMH/PDL/PML + fetch_recent_bars sized to mins-since-9:30;
  break times lock per session). scan_once sets runner.qqq_breaks once/cycle (skips futures) →
  existing _qqq_aligned drives [qqqA]/[qqqX] tag + S+1 with zero signal_runner edits. scanner_status.json
  gains qqq_state; --once --paper wrote {"up":"15:59:00","dn":null} (off-hours artifact, correct RTH-sized
  live). Tag path verified via self-check. Uncommitted.*
- [ ] **A6** SONNET (recurring, manual) — After each paper day: read daily_review embed, log tier
  compliance + P&L to vault doc. 1 week minimum before any config change. Done-when: 5 trading
  days logged.

## Phase B — Extraction → audit (kill remaining hallucinations)

- [x] **B1** DEEPSEEK — Run research/deepseek-spec-4.md: 36 group calls over 89 video transcripts
  → research/scarface-rules-videos.md. Done-when: headline section lists new/contradicting rules.
  *Done 2026-07-13: 6,115 lines. Headliners: OCR confirmed as named concept (contra accelerator),
  A/A+ = holistic confluence stacking not checklist, stop-after-2-wins NOT FOUND, displacement
  qualitative-only. Interim files research/_b1_interim/ — still uncommitted, fold into B2.*
- [x] **B2** FABLE — Merge scarface-rules-videos.md into research/hallucination-audit.md +
  Desktop/PARAMETER_CATALOG.md. Flag new hallucinations + newly-confirmed rules. Done-when:
  audit updated with videos column.
  *Done 2026-07-13: videos column added (audit §"Videos rulebook column" + catalog §G). NEW
  hallucination flag: stop_after_win unsourced in all 5 rulebooks (C10 verdict, config untouched);
  newly confirmed: SCARFACE_CONTRACT first-OTM+weekly verbatim, OCR≡OB (double-count check → B4),
  engulfing found ONCE (kill stands), B3 hypothesis sharpened (Day 6 confluence stack + QQQ=RS
  not level-break). B1 pile NOT committed per dispatch "Do NOT commit" — fold into next ⛳.*
- [x] **B3** FABLE — A/A+ inversion audit (BIGGEST open anomaly: A/A+ 30.9%W −$6.4k vs B 36.6%W
  +$62.5k). Diff coded grade_trade() criteria vs every rulebook A+ quote (rulebook: A+ = QQQ
  context + HTF thesis + entry level is HTF level). Hypothesis list + which coded criterion
  inverts. Done-when: written diagnosis in research/aplus-inversion-audit.md.
  *Done 2026-07-13: inverter = 84%-rule grade laundering, not the A+ detector — 22 of 68 A-tier
  trades are ungated 84% re-entries (RULE84_LESSON=True bypasses PA gate) floored C→B at
  signal_runner:643 then promoted B→A by clear-road rule, 22.7%W −$8,395 = 131% of tier loss;
  B&R A healthy (+$3k, 37%W). Fix list handed to B4 in research/aplus-inversion-audit.md.*
- [x] **B4** OPUS — Encode corrected A+ definition from B3 behind flag, 12mo A/B vs current
  grading. Done-when: table old vs new grade distribution + P&L by grade.
  *Done 2026-07-13: GRADE_FIX env flag (default OFF) in signal_runner — drops 84% C→B floor +
  blocks clear-road B→A for 84% re-entries. 12mo A/B (671 vs 625 traded): A-tier inversion GONE
  (A 34.0%W −$393 → 36.7%W +$3,000), tier IDENTICAL (78 tr 42.3%W $21k/yr — uncontaminated as B3
  predicted), full-pop −$2,371 (floored-B 84% group was net-positive, benched with the bathwater).
  Report: research/b4_grade_fix_ab.md. C10 decides default; narrower promotion-only variant noted for C9.*
- [ ] **B5** DEEPSEEK (background, low priority) — YouTube tranche: rank ~1300 transcript titles
  by relevance (setup/level/entry keywords), extract top 100 per deepseek-extraction-spec.md
  → scarface-rules-youtube-2.md. Done-when: file exists, rest of tranche listed as skipped.

## Phase C — Win-rate levers (44.4% → 50%+, all independent, each = flag + 12mo A/B)

- [x] **C1** GLM — BNR_DISPLACEMENT_GATE on vs off, 12mo, full-pop + tier. Done-when: table + verdict. *Result (2026-07-13): keep OFF. ON −$3,000/yr full-pop (677 tr 37.3%W vs 671 37.5%W) and −$5,000/yr tier (83 tr 39.8%W vs 78 42.3%W). Displacement split not predictive; gate hurts live tier. Report: research/c1_displacement_gate_ab.md.*
- [x] **C2** GLM — FVG_RETEST new displacement-anchored variant on vs off, 12mo. Done-when: same. *Result (2026-07-13): keep OFF. ON doubles trades (671→1506) but loses everywhere — full-pop 37.5%→34.7%W −$27k; tier 78→63 tr 42.3%→38.1%W −$12k/yr. Displacement-anchor not enough to beat 07-05 dilution evidence. Report: research/c2_fvg_displacement_ab.md.*
- [x] **C3** SONNET — [disp]/[nodisp] + [vwap-]/[chase] tag performance split on latest 12mo run:
  does stacking skip-tags beat S-score alone? Done-when: table in research/.
  *Result (2026-07-13): No real stack win. Only skip-[chase] beats S-score alone on BOTH axes
  (70 tr 44.3%W $23k vs 78 tr 42.3%W $21k) — marginal (+2pp +$2k), just filtering 8 bad chase-tier
  trades, not a new edge. [chase]=28.2%W −$11.5k full-pop (real loser tag). [nodisp] carries the
  tier (+$17k of $21k), skipping it collapses tier. [disp] dilutes win% but net-positive, skip
  raises win% loses $/yr. [vwap-] removed 07-11, 0 occurrences (no-op). Defer skip-[chase] to C10.
  Report: research/c3_tag_split.md.*
- [x] **C4** FABLE — Puts problem (−$21k/24mo structural): A/B (a) puts off entirely,
  (b) puts only when QQQ-aligned bearish, (c) status quo. Decide. Done-when: config set + vault note.
  *Verdict 2026-07-13: (c) STATUS QUO — premise stale. −$21k/24mo was year-1 bull regime;
  current 12mo puts are the STRONGER side (+$43k full-pop vs calls +$35k; $14k of $21k tier).
  (a) puts-off: tier 78→45 tr $21k→$6k. (b) qqqA-only: tier 59 tr $13k — drops 19 counter-QQQ
  tier puts that ran 47.4%W +$8k (hammer+S already selects them). QQQ alignment is real but
  direction-symmetric + already in S-score. No config change (freeze respected). Report:
  research/c4_puts_decision.md.*
- [x] **C5** OPUS — HTF bias gate (SPEC10, long-pending): daily-candle trend proxy via yfinance
  (no DXLink MTF needed), gate: only trade signal direction matching daily trend, flag-gated.
  12mo A/B. Done-when: flag + table.
  *Result (2026-07-13): keep OFF. HTF_BIAS_GATE flag (default OFF) + daily_trend_bias() helper
  (close vs SMA20) in signal_runner. Gate blocks 37% of trades as counter-trend but they were
  net-positive: full-pop 671→423 tr, 37.5→36.2%W, $78k→$32k; tier 78→55 tr, 42.3→40.0%W,
  $21k→$11k/yr (−$10k). Daily SMA20 trend not predictive of intraday B&R; counter-trend
  retest+confirm IS the edge. Same lesson as C1/C2. Report: research/c5_htf_gate_ab.md.*
- [x] **C6** SONNET — Per-symbol tier attribution: which symbols carry S≥4+[hammer] tier P&L;
  propose tier-specific symbol list. Done-when: table + proposed list (no config change yet).
  *Result (2026-07-13): 78 tier trades across 24 symbols (12 net-pos, 10 net-neg, 2 zero). 8/12
  pos symbols carry 80% of tier profit. Proposed 12-symbol whitelist (AMD,AMZN,COIN,GOOGL,INTC,
  IREN,NFLX,NVDA,ORCL,PLTR,QQQ,UBER) → 43 tr/yr 60.5%W $35k/yr in-sample — but OVERFIT (list
  selected from same run, 8/12 symbols n<5). PROPOSAL ONLY; C10 + F1 walk-forward before trust.
  Report: research/c6_symbol_attribution.md.*
- [x] **C7** SONNET — Day-of-week split + Friday-next-week-contracts rule (hard rule in rulebook).
  Encode Friday expiry shift if SCARFACE_CONTRACT lands (D1). 12mo day-of-week table.
  Done-when: table + verdict.
  *Result (2026-07-13): Friday NOT materially worse ($106/trade vs $120 non-Fri, Δ−$14, noise);
  Fri next-week-contract rule is D1's live-sizing/encoding concern, not a win-rate lever.
  Thu($32k)/Tue($2k) spread large but tier per-weekday n=12-22 overfit-prone (C6 class);
  WATCH only — no weekday gate to live config, F1 must validate OOS if C10 wants one.
  Report: research/c7_dow_split.md.*
- [x] **C8** SONNET — Two-consecutive-losses = quit day (rulebook hard rule) as backtest flag,
  12mo A/B vs current loss-halt. Done-when: table + verdict.
  *Result (2026-07-13): Rule == config consecutive_loss_halt:2 == omen_bot.day_ended() — SAME rule, no A/B possible. Backtest does NOT apply it (671 = raw). Sensitivity sim: full-pop no-halt $78.2k > halt-at-1 $69.5k > halt-at-2 $65.3k (rule CUTS -$13k/yr -16.5%, stops net-pos follow-through). Tier: halt-at-2 = no-op (max-2/day dominates), halt-at-1 flat $21k +0.8ppW. Rule redundant at tier, harmful at full-pop. No change. Report: research/c8_loss_halt_ab.md.*
- [x] **C9** OPUS — 84% rule strict-spec variant: require A+ entry + same-thesis (rulebook spec)
  vs current de-martingaled version (+$203). If still ~flat, kill detector. Done-when: verdict.
  *Done 2026-07-13: ADOPT STRICT (don't kill). RULE84_STRICT/RULE84_OFF flags (default OFF) in
  signal_runner, gate in backtest_week._arm_84. 12mo real A/B: current 671 tr / re84 51 tr 39.2%W
  +$2,702; STRICT 624 tr / re84 4 tr 75%W +$4,162; OFF 620 tr / re84 0 (+$0). Rulebook "need an A+
  entry" confirmed — the 47 B-origin re-entries current also takes are net −$1,461; strict keeps
  only the 4 A/A+-origin winners. Strict dominates both. TIER IDENTICAL 78/42.3%/$21k all three
  (84% carries no S-score = full-pop-only, tier no-op). Caveat: n=4/yr, edge unproven → F1. Report:
  research/c9_rule84_strict_ab.md.*
- [x] **C10** FABLE — Synthesize C1–C9: which flags turn ON together; combined 12mo run of winners
  (composition check like A3). Update tier definition if S-formula should change. Done-when:
  new recommended config v2 in vault doc.
  *Done 2026-07-13: TIER v2 = S≥4, skip-[chase], max 2/day — hammer req + stop-green DROPPED →
  156 tr/yr (0.70/day) 50.6%W $81k/yr in-sample (vs 78/42.3%/$21k), halves 48.8/52.6%, maxDD −$6k.
  3,072-config sweep + robustness in research/c10_synthesis.md. Flags: RULE84_STRICT default ON;
  GRADE_FIX stays OFF (combo run = detector-OFF $75,489, kills strict's 4 winners); C1/C2/C5 OFF.
  Config: cutoff reverted 10:30→11:00, stop_after_win off, skip-news stays. S-formula unchanged.
  50%W AND 1–2/day not in population — six figures = v2 + D-phase sizing. F1 gates real money.*

## Phase D — Sizing (profit per trade; only after C10 config stable)

- [ ] **D1** GLM — SCARFACE_CONTRACT A/B: first-OTM + weekly expiry vs current selection, 12mo
  options P&L. Done-when: table + verdict.
- [ ] **D2** OPUS — S-score-scaled sizing: S=4 → 1.0x, S=5 → 1.25x, S=6+ → 1.5x ($1k base risk),
  flag-gated, 12mo A/B vs flat sizing. Done-when: table incl. max drawdown comparison.
- [ ] **D3** SONNET — Re-run risk-of-ruin (fable_ror method) on final tier stats from C10/D2.
  $1k vs $1.5k risk. Done-when: numbers in vault doc.

## Phase E — Live infra (cheap, anytime)

- [x] **E1** HAIKU — schtask: daily_review.py 16:10 ET weekdays, Python313. Done-when: task listed + one dry-run fired.
- [x] **E2** HAIKU — paper_trader.py: date-prefix the `ts` field in paper-trades.jsonl (known gap,
  daily_review P&L bleed). Done-when: new trade line shows full date, daily_review --dry-run clean.
- [x] **E3** SONNET — Pre-market Discord card 9:00 ET: watchlist, key levels (PDH/PDL/PMH/PML),
  QQQ daily bias. Reuse discord_bot + level code from signal_runner. Done-when: --dry-run posts card.
  *Done 2026-07-13: premarket_card.py posted live card to Discord; OmenPremarketCard schtask 9:00
  weekdays created. yfinance rate-limited during test — per-symbol graceful degrade handles it.*
- [x] **E4** SONNET — sentry-bot: alert if scanner_status.json older than 15 min during RTH.
  Done-when: staleness test fires Discord alert.
  *Done 2026-07-13: sentry_scanner.py — RTH(9:30-16:00 ET, weekdays)+15min-stale gate
  on scanner_status.json timestamp; OmenScannerSentry schtask 09:30 /ri 15 /du 06:30.
  --test fired live Discord alert. Uncommitted.*
- [x] **E5** SONNET — Sunday cron: 12mo backtest refresh + diff summary vs prior week to Discord.
  Done-when: one manual run posts diff.
  *Done 2026-07-13: sunday_backtest.py parses backtest_report_12mo.md (signals/WR/P&L +
  per-grade), runs backtest_12mo.py 365 --snapshot, diffs prior→new, posts embed. --test
  posted live diff (SNAP 07-12 vs CURRENT 07-13) to Discord. OmenSundayBacktest schtask
  Sunday 10:00 ET weekly. Uncommitted.*

## Phase F — Go-live gates (after A6 + C10)

- [ ] **F1** FABLE — Walk-forward validation: rolling train-12mo/test-3mo on final config; overfit
  check on every flag turned on in C10. Done-when: walk-forward table, verdict per flag.
- [ ] **F2** FABLE — 2-week live shadow scorecard: paper signals vs backtest expectation
  (win rate CI, slippage estimate from bid/ask). Done-when: scorecard in vault.
- [ ] **F3** FABLE — Real-money go/no-go checklist: F1 pass + F2 within CI + risk-of-ruin <5%
  at chosen size + Austin's manual rules (max 2/day, stop-green) automated in live_scanner.
  Done-when: checklist doc, each gate pass/fail.
- [ ] **F4** OPUS — ES futures tier port (omen --futures exists): apply S-score tier + QQQ
  alignment to ES mode, 12mo backtest. Done-when: table; only pursue if options edge confirmed first.

---

## Sequencing cheat sheet
Now: A1 → dispatch B1 (DeepSeek, parallel) → A2/A3/A4 → A5 → start A6 paper week.
During paper week: C1–C9 (any order, cheap models), B2–B4, E1–E5.
Then: C10 → D → F. ~35 tasks total.
