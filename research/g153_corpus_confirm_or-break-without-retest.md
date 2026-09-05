# F4: Corpus Confirmation — "or-break-without-retest"

## Candidate Rule
A break of the opening range that fires without a subsequent retest of ORH/ORL is a lower-probability setup / fakeout, even though the opening range is one of his six levels.

## Search Results

### Corpus Status: **silent**

**Quote:** None found in harvested corpus (YouTube captions from Scarface/Jdub channels).

**Source Path:** Searched `research/corpus_entries.jsonl`, `research/corpus_normalized.jsonl`, `research/corpus_rule_candidates.jsonl`, `research/corpus_setup_rules.jsonl`.

### Evidence of Silence
- The corpus contains 348 opening_range_break_retest labeled rows (per `research/corpus_normalized.jsonl`)
- All extracted trader statements about opening range breaks emphasize the **retest** component: "opening range break and retest", "opening range break and retest"
- Zero trader statements found explicitly calling breaks without retest "lower probability" or "fakeouts"
- The corpus focuses on successful break-and-retest patterns, not failure modes

### Austin's Own Marks (Not Corpus)
For reference, Austin's graded marks show awareness of this rule:
- **GOOG_2025-12-10_38**: "lower probability after break of orh and no retest" (graded A, not S)
- **TSLA_2025-12-18_59**: "never like hod entries lower probability and when it goes below orl with no break and retest. there was actually that would've been a fakeout loser"

These are Austin's observations, not corpus trader confirmations.

## Row Appended
| candidate | tag | quote | source_path |
|---|---|---|---|
| or-break-without-retest | silent | (no corpus statement found) | corpus_entries.jsonl / corpus_normalized.jsonl |
