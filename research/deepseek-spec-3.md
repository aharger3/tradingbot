# DEEPSEEK Spec 3 (2026-07-12) — extraction tranche

Predecessor: `deepseek-spec-2.md`. Extraction template + citation format:
`deepseek-extraction-spec.md` (verbatim quote + filename + timestamp for every rule, or it
doesn't count). Existing rulebooks: `scarface-rules-{accelerator,mastermind,coaching-bonus,youtube}.md`.

Hard rules:
- Extraction/summarization only. Do NOT touch bot code (`omen_bot.py`, `signal_runner.py`, backtests) — Fable-only territory.
- Never commit. Python313 for any scripts.
- Each deliverable = standalone .md in `research/`, headline findings section on top.

Order (D1 in flight → D3 unblocks Fable → D2 → D4 → D5 background):

## D1. Video/audio transcription extraction (in flight, finish it)
82 `circle_videos` (24GB) + 9 `circle_audio` → whisper transcripts → extraction template →
`research/scarface-rules-videos.md`. Priority: filenames matching a-setups / key-levels / live-sessions.

## D2. Exit-management dossier (NEW — feeds Fable F1)
Sweep ALL sources (4 rulebooks' raw transcripts + videos when D1 lands) for verbatim quotes on:
- scaling % by regime (trending: 20-25% at HOD vs choppy: 50-100%),
- what counts as "next key level" for the runner (PDH/PDL, psych numbers, gap fill, ATH — exact hierarchy),
- BE-after-TP1 vs never-move-stop: WHO says WHAT (Tony vs Scarface vs J-Dub — attribute every quote),
- trailing methods: bar-by-bar, OB-to-OB, 5-10% option value, 20% hot market.
→ `research/exit-management-dossier.md`.

## D3. QQQ/SPY alignment rules (unblocks Fable F4)
The 8 specific non-negotiable alignment rules, verbatim → `research/qqq-alignment-rules.md`.
Include: when individual-name strength overrides weak QQQ (the "trust your key level" tension).

## D4. 84% sizing dossier
`research/84rule-sizing-dossier.md`. Conflict on record: accelerator = same size never bigger
(1450449 27:18) vs YouTube = doubled/tripled (Zt8c-5OcLGk). Collect every sizing quote +
context (who, when, scalp vs A+). Data side DONE: `research/84rule_trades.json` (89 joined
re-entries, 30W/59L) — reference it, don't rebuild it.

## D5. discord_data mining (22,596 files — background, biggest)
Same template → `research/scarface-rules-discord.md`. Hunt: trade-review judgments (good/bad
+ WHY), rule statements not in course materials, shorts "elevator down" playbook specifics
(aggressive entry, fewer criteria — feeds per-direction grading question).
