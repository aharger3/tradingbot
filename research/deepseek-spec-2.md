# DeepSeek Spec Round 2 — targeted extraction + research (2026-07-11)

Discord tranche DONE (findings received: OCR=order-blocks confirmed; 84% size-up contradiction;
75%-of-trades-~10AM stat; 8 QQQ/SPY alignment rules; elevator-down short playbook; win-rate range).
Next tasks, in priority order:

## Task 1 — Conflict resolution dossier: 84% rule sizing
Accelerator says SAME size ("if I'm risking $1,000 on the first trade, I'm gonna risk $1,000 on
the second" — 1450449). Discord/YouTube extraction says CAN size up. Our live data: 2× sizing was
a martingale disaster (−$8.7k); bot runs 1×.
→ Collect EVERY quote about 84%-rule sizing across ALL sources (Circle transcripts, YouTube incl.
VesUpLmHCcw, Discord) verbatim with full surrounding context (who says it, about what trade, what
conditions). Output `research/84rule-sizing-dossier.md`. Do NOT conclude — just assemble evidence;
Fable + Austin decide.

## Task 2 — QQQ/SPY alignment rules, verbatim
The Discord extraction found "8 specific rules on alignment (non-negotiable)". Fable needs them
EXACT to encode. Output `research/qqq-alignment-rules.md`: each rule verbatim + source + timestamp
+ any worked example. Also pull every "relative strength / relative weakness" definition (stock vs
index) — our backtest shows stock-leading-index wins 43.8% vs 34.7%, we need the taught version.

## Task 3 — Short playbook ("elevator down") spec
Collect all criteria differences shorts vs longs (aggressive entries, no displacement needed on
rejection?, PDL playbook) verbatim → `research/short-playbook.md`. Our per-direction split can
then be graded separately.

## Task 4 — Video/audio transcription + extraction
circle_videos (82 files, 24GB) + circle_audio (9 files): whisper-transcribe (medium model fine),
then run the template from `research/deepseek-extraction-spec.md` → `research/scarface-rules-videos.md`.
Priority order: filenames matching a-setups, key-levels, live-sessions, boot-camp. Live-session
videos are gold: real trades narrated in real time = entry-timing ground truth (ambiguity #1).

## Task 5 — Futures prop-firm research (Austin's ES-bot scaling path)
Web research report `research/futures-propfirm-research.md`:
- Futures prop firms with API/automation-friendly execution (Topstep, Apex Trader Funding, MyFundedFutures,
  TradeDay, Earn2Trade...): drawdown type (EOD vs intraday trailing vs static), eval cost/target,
  activation/monthly fees, payout split + schedule, automation/API policy (CRITICAL — which allow
  automated/semi-automated trading, which ban it), copy-trading across accounts policy, max accounts.
- Same risk-of-ruin lens as Vanquish analysis: $X risk/trade vs drawdown size.
- ES/NQ micro vs mini contract math at our 2R system.
- Copy-trading services used with prop firms (e.g., multi-account trade copiers), their rules risk.
Cite sources. Flag rules that changed in 2025-2026 (prop firm rules churn fast).
