# DeepSeek Extraction Spec — Scarface/J-Dub Transcript Mining

Goal: build cited rulebooks from remaining transcripts so OMEN's coded rules can be audited against source (kill hallucinated rules). Accelerator course (29 files) ALREADY DONE → `research/scarface-rules-accelerator.md`. DO NOT redo it.

## Inputs (in priority order)
1. `C:\Users\aharg\tradingbot\circle_data\transcripts\mastermind-*` — 28 .vtt files (masterminds 1.0–5.0). HIGHEST VALUE: advanced setups, live trade review.
2. `C:\Users\aharg\tradingbot\circle_data\transcripts\bonus_*` (3) + `boot-camp-recordings_*` (1).
3. `C:\Users\aharg\tradingbot\circle_data\transcripts\performance-coaching_*` — 40 files. Mostly psychology; SKIM, capture only concrete methodology + trade-review judgments ("this trade was bad because X").
4. `C:\Users\aharg\tradingbot\youtube_data\*_transcript.txt` — ~1300 files, later tranche, same template.

VTT format: strip timestamps headers, but KEEP approximate timestamp for each cited quote.

## Batching
One model call per transcript (they're 80–200KB; chunk if context-limited: 25k-char chunks, carry running notes forward). Temperature 0. Output one .md per source category (see below).

## Extraction template (per file, verbatim quotes + (filename, timestamp) for EVERY rule)
1. Break-and-retest: valid break (bodies vs wicks, displacement size), valid retest (touch? zone? max wait?), entry trigger candle (hammer/shooting star qualities), stop placement, targets, invalidation, first-break-of-day vs later breaks (late entries).
2. **"One candle rule"** — TOP PRIORITY: course transcripts never use this name (only "opening candle retest"). Find any use of "one candle rule" and its exact spec.
3. 84% rule / re-entries: conditions, sizing, disqualifiers.
4. Order blocks: definition, drawing (wick-to-body), entry/stop use, "isolated" quality criteria.
5. Key levels: PDH/PDL, PMH/PML, opening range, HOD/LOD, gap fill — hierarchy, when each matters.
6. Time-of-day + day-of-week rules; news days.
7. Exits: scaling %s, breakeven rules, trailing, hold-to-target, runners.
8. Higher-timeframe / swing / long-term application of break-and-retest (daily/weekly levels, inside bars, multi-day holds).
9. Trade selection: A+ criteria, confluence lists, max trades/day, stop-when-green, market-regime awareness (melt-ups, chop, VIX).
10. Concrete numbers: win rates, R:R, risk %, drawdown norms.

Rules: quote verbatim, cite (file, timestamp). If a topic never appears: "NOT COVERED IN THIS SOURCE". NEVER fill gaps from general trading knowledge — that is the exact failure mode this project kills. Trade-review commentary (a specific trade judged good/bad and WHY) is gold — always capture criteria used.

## Outputs
- `research/scarface-rules-mastermind.md`
- `research/scarface-rules-coaching-bonus.md`
- `research/scarface-rules-youtube.md` (later)
Same structure as scarface-rules-accelerator.md (headline findings, then topics 1–10, then Ambiguities).

## After extraction (Claude Code takes back over)
Diff every coded rule in omen_bot.py / signal_runner.py against the rulebooks → hallucination audit + fix list.
