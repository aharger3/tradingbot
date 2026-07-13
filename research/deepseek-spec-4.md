# DEEPSEEK Spec 4 (2026-07-13) — video-transcript extraction (finish D1)

Predecessor: `deepseek-spec-3.md` (D1 transcription half DONE — 89/89 WAVs whisper-transcribed).
This spec = the extraction half. Template + citation format: `deepseek-extraction-spec.md`
(verbatim quote + filename + timestamp for EVERY rule, or it doesn't count).

Hard rules:
- Extraction/summarization only. Do NOT touch bot code (`omen_bot.py`, `signal_runner.py`, backtests) — Fable-only territory.
- Never commit. Python313 for any scripts.
- NEVER fill gaps from general trading knowledge. Topic absent → "NOT COVERED IN THIS SOURCE".

## Inputs
`C:\Users\aharg\tradingbot\research\video_transcripts\*_transcript.txt` — 89 files, ~7.4MB total.
Whisper output; segments carry `[Ns]`-style timestamps — cite them.

Batching already prepared: `video_transcripts\_extract_groups.json` — 36 groups covering all 89
files, sized for one model call each. One call per group; chunk if context-limited (25k-char
chunks, carry running notes forward). Temperature 0.

Source breakdown (89): boot-camp-recordings 16, performance-coaching 16,
building-your-profitable-system 12, mastermind-1-0 11, mastermind-4-0 8, mastermind-5-0 8,
hayden-s-coaching 7, the-accelerator-course 5, bonus 3, mastermind-2-0 2, mastermind-3-0 1.

Priority order (new material first):
1. **building-your-profitable-system (12) + hayden-s-coaching (7) + boot-camp (16)** — sources with
   NO existing rulebook coverage. Highest value.
2. **mastermind-* (30) + accelerator (5) + bonus (3)** — course names overlap the VTT-derived
   rulebooks (`scarface-rules-{accelerator,mastermind}.md`) but these are DIFFERENT recordings
   (video/audio lessons, not the VTT set). Extract fully; where a rule confirms an existing
   rulebook entry, one line + citation is enough — spend words on anything NEW or CONTRADICTING.
3. **performance-coaching (16)** — SKIM: psychology mostly; capture only concrete methodology +
   trade-review judgments ("this trade was bad because X").

Already extracted (do NOT redo): boot-camp Day 5 + Day 6 → `research/EXTRACTED_TRADING_RULES.md`.
Fold its content into the output unchanged (reformat to match, keep citations).

## Extraction topics
Topics 1–10 from `deepseek-extraction-spec.md` (B&R spec, one-candle-rule naming, 84% rule,
order blocks, key levels, time-of-day, exits, HTF application, trade selection, concrete numbers).
Plus, flagged for the open audit questions:
- **A/A+ grading criteria** — backtest shows A/A+ INVERTED vs B (30.9%W vs 36.6%W). Capture every
  quote defining what makes a setup A vs B; the coded grading may be wrong.
- **QQQ alignment** — anything adding to `research/qqq-alignment-rules.md` (Rule-4 proxy now live in backtest).
- **Displacement / FVG** — gate + detector newly coded (off, pending A/B); capture exact size/definition quotes.
- **Stop-after-win / max trades/day** — tier rules (S≥4+[hammer], max 2, stop-green) came from these
  sources; confirm or contradict.

## Outputs
- `research/scarface-rules-videos.md` — same structure as scarface-rules-accelerator.md
  (headline findings on top, topics 1–10, Ambiguities section at bottom).
- Headline section MUST list: (a) rules found NOWHERE in prior rulebooks, (b) contradictions
  with prior rulebooks (attribute WHO says WHAT), (c) anything bearing on A/A+ inversion.

## After extraction (Claude Code takes back over)
Diff new rulebook vs `research/hallucination-audit.md` + `Desktop/PARAMETER_CATALOG.md` (33 params)
→ update audit, flag new hallucinations / new evidence for coded rules.
