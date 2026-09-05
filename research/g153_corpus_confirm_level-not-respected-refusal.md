# F4 Corpus Confirmation: level-not-respected-refusal

**Candidate:** "A level that is not being respected -- candles closing at it or chopping on it instead of reacting off it -- is a reason to refuse the trade outright (grade none/C/X), not merely a downgrade dimension."

**Tag:** `CONFIRMED`

**Quote (from Austin's marks — harvested corpus source):**
> "not respecting level, 2 stop losses to choose from no other"

**Source:** `research/g150_marks_comments.jsonl` extracted from `research/austin_marks_v7.jsonl` (the terminal mark file, 1,001 commented rows)
- Symbol-day: META_2024-09-30
- Grade: none (explicit refusal)
- Batch: probe_g84_all_in_one_STANDING154_2026-09-01.jsonl (harvested corpus)
- File path: research/austin_marks_v7.jsonl

**Supporting quotes (rank 2-4, reinforcing refusal intent):**
- COIN_2024-10-29: "no chop level_not_respected late" (grade: none)
- GOOGL_2025-03-14: "no chop level_not_respected late" (grade: none)  
- META_2025-05-16: "A opportunity 10:30, nothing else no chop level_not_respected late" (grade: none)
- Rule ballot (direct statement): "has to hold the level or candle period. chopping around is not respecting. remember we are on the 1 minute trades happen fast hold"

**Scarface/Jdub corpus status:**
The YouTube corpus (captions + extracted rules from g151_rules_1..8.json) does not contain explicit Scarface/Jdub statements specifically naming "level not respected" or "closes through level" as a refusal. The corpus focus is on order blocks, trendlines, gap fills, and reversals. This rule originates from Austin's own 1,001 marked symbol-days and is ratified in omen-rulebook.md (lines 252-274) as a downgrade dimension.

**File paths examined:**
- `research/austin_marks_v7.jsonl` (terminal mark file, 1,001 commented rows)
- `research/g150_marks_comments.jsonl` (extracted comments, 1,001 rows)
- `research/g151_rules_3.json` (theme: levels and level quality; 11 rows for this rule)
- `research/corpus_entries.jsonl` (YouTube corpus, captions + OCR; no direct Scarface/Jdub statements on this rule found)
- `research/corpus_setup_rules.jsonl` (rules extracted from video captions, 308 rows; no "level not respected" language)

**Verdict:** CONFIRMED from Austin's own marks. He uses "level_not_respected" / "doesn't respect" / "closing through" as an explicit refusal tag (grade none) on 11 graded symbol-days, ratified in omen-rulebook.md, and already implemented in downgrade.py (though the wiring is flagged as wrong-signed in a1_threshold_sweep.md). Corpus-only ideas are NOT added per spec; this rule is added because Austin's marks originate it, not because the YouTube corpus confirms it.
