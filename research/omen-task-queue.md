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

## Phase A — Ship the measured wins (recommended config → live paper)

- [x] **A1** FABLE — Review the 5 modified code files (signal_runner, live_scanner, options_sizer,
  config.yaml, backtest_week), then local-commit the whole 82-file pile in logical chunks
  (.gitignore journal/*.log first). Done-when: clean `git status`, Austin only pushes.
  *Done 2026-07-13: 8 commits (eeeb8895..9bb5d5ce+), review fixed 2 issues — dry-run double-import
  bug (toggles hit dead module copy) + RULE6_ENABLED left True from comparison run, reverted.*
- [ ] **A2** SONNET — Apply recommended config from Desktop/unified_backtest_synthesis.md:
  drop SMCI/SPY/MSTR/RIVN from symbol list, entry cutoff 10:30, skip-news ON, RULE6 stays OFF,
  SMA Directional 5% regime filter ON. config.yaml + live_scanner defaults. No signal-logic edits.
  Done-when: config diff matches synthesis §recommendations, live_scanner --once --paper runs clean.
- [ ] **A3** GLM — Composition check: 12mo backtest with ALL A2 changes combined (levers were
  measured one-at-a-time; interactions unverified). Report vs $88–95k projection, per-lever
  attribution table. Done-when: report in research/, verdict line "composes / doesn't because X".
- [ ] **A4** FABLE — Combined tier run: qqqA-S+1 + --skip-news + --entry-cutoff 10:30 (queued
  "next session #1" from F-session). Interpret: new tier stats vs 90/44.4%/$2,500. Done-when:
  tier verdict updated in vault doc.
- [ ] **A5** OPUS — QQQ plumbing in live_scanner: fetch QQQ 1-min candles each cycle, compute
  Rule-4 alignment (first RTH close through PDH/PMH/PDL/PML before entry), S+1 on live cards +
  [qqqA] tag. Backtest logic already in repo — port, don't reinvent. Done-when: --once --paper
  shows QQQ state in scanner_status.json, dry-run card carries tag.
- [ ] **A6** SONNET (recurring, manual) — After each paper day: read daily_review embed, log tier
  compliance + P&L to vault doc. 1 week minimum before any config change. Done-when: 5 trading
  days logged.

## Phase B — Extraction → audit (kill remaining hallucinations)

- [ ] **B1** DEEPSEEK — Run research/deepseek-spec-4.md: 36 group calls over 89 video transcripts
  → research/scarface-rules-videos.md. Done-when: headline section lists new/contradicting rules.
- [ ] **B2** FABLE — Merge scarface-rules-videos.md into research/hallucination-audit.md +
  Desktop/PARAMETER_CATALOG.md. Flag new hallucinations + newly-confirmed rules. Done-when:
  audit updated with videos column.
- [ ] **B3** FABLE — A/A+ inversion audit (BIGGEST open anomaly: A/A+ 30.9%W −$6.4k vs B 36.6%W
  +$62.5k). Diff coded grade_trade() criteria vs every rulebook A+ quote (rulebook: A+ = QQQ
  context + HTF thesis + entry level is HTF level). Hypothesis list + which coded criterion
  inverts. Done-when: written diagnosis in research/aplus-inversion-audit.md.
- [ ] **B4** OPUS — Encode corrected A+ definition from B3 behind flag, 12mo A/B vs current
  grading. Done-when: table old vs new grade distribution + P&L by grade.
- [ ] **B5** DEEPSEEK (background, low priority) — YouTube tranche: rank ~1300 transcript titles
  by relevance (setup/level/entry keywords), extract top 100 per deepseek-extraction-spec.md
  → scarface-rules-youtube-2.md. Done-when: file exists, rest of tranche listed as skipped.

## Phase C — Win-rate levers (44.4% → 50%+, all independent, each = flag + 12mo A/B)

- [ ] **C1** GLM — BNR_DISPLACEMENT_GATE on vs off, 12mo, full-pop + tier. Done-when: table + verdict.
- [ ] **C2** GLM — FVG_RETEST new displacement-anchored variant on vs off, 12mo. Done-when: same.
- [ ] **C3** SONNET — [disp]/[nodisp] + [vwap-]/[chase] tag performance split on latest 12mo run:
  does stacking skip-tags beat S-score alone? Done-when: table in research/.
- [ ] **C4** FABLE — Puts problem (−$21k/24mo structural): A/B (a) puts off entirely,
  (b) puts only when QQQ-aligned bearish, (c) status quo. Decide. Done-when: config set + vault note.
- [ ] **C5** OPUS — HTF bias gate (SPEC10, long-pending): daily-candle trend proxy via yfinance
  (no DXLink MTF needed), gate: only trade signal direction matching daily trend, flag-gated.
  12mo A/B. Done-when: flag + table.
- [ ] **C6** SONNET — Per-symbol tier attribution: which symbols carry S≥4+[hammer] tier P&L;
  propose tier-specific symbol list. Done-when: table + proposed list (no config change yet).
- [ ] **C7** SONNET — Day-of-week split + Friday-next-week-contracts rule (hard rule in rulebook).
  Encode Friday expiry shift if SCARFACE_CONTRACT lands (D1). 12mo day-of-week table.
  Done-when: table + verdict.
- [ ] **C8** SONNET — Two-consecutive-losses = quit day (rulebook hard rule) as backtest flag,
  12mo A/B vs current loss-halt. Done-when: table + verdict.
- [ ] **C9** OPUS — 84% rule strict-spec variant: require A+ entry + same-thesis (rulebook spec)
  vs current de-martingaled version (+$203). If still ~flat, kill detector. Done-when: verdict.
- [ ] **C10** FABLE — Synthesize C1–C9: which flags turn ON together; combined 12mo run of winners
  (composition check like A3). Update tier definition if S-formula should change. Done-when:
  new recommended config v2 in vault doc.

## Phase D — Sizing (profit per trade; only after C10 config stable)

- [ ] **D1** GLM — SCARFACE_CONTRACT A/B: first-OTM + weekly expiry vs current selection, 12mo
  options P&L. Done-when: table + verdict.
- [ ] **D2** OPUS — S-score-scaled sizing: S=4 → 1.0x, S=5 → 1.25x, S=6+ → 1.5x ($1k base risk),
  flag-gated, 12mo A/B vs flat sizing. Done-when: table incl. max drawdown comparison.
- [ ] **D3** SONNET — Re-run risk-of-ruin (fable_ror method) on final tier stats from C10/D2.
  $1k vs $1.5k risk. Done-when: numbers in vault doc.

## Phase E — Live infra (cheap, anytime)

- [x] **E1** HAIKU — schtask: daily_review.py 16:10 ET weekdays, Python313. Done-when: task listed + one dry-run fired.
- [ ] **E2** HAIKU — paper_trader.py: date-prefix the `ts` field in paper-trades.jsonl (known gap,
  daily_review P&L bleed). Done-when: new trade line shows full date, daily_review --dry-run clean.
- [ ] **E3** SONNET — Pre-market Discord card 9:00 ET: watchlist, key levels (PDH/PDL/PMH/PML),
  QQQ daily bias. Reuse discord_bot + level code from signal_runner. Done-when: --dry-run posts card.
- [ ] **E4** SONNET — sentry-bot: alert if scanner_status.json older than 15 min during RTH.
  Done-when: staleness test fires Discord alert.
- [ ] **E5** SONNET — Sunday cron: 12mo backtest refresh + diff summary vs prior week to Discord.
  Done-when: one manual run posts diff.

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
