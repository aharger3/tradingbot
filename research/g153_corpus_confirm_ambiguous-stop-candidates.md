# F4: Corpus Confirmation for ambiguous-stop-candidates

**Candidate:** ambiguous-stop-candidates  
**Rule:** A stop that is ambiguous -- two live stop candidates that do not agree, or a muddled structure with several recent highs and lows -- is a downgrade in itself, independent of clean entry criteria.  
**Source rule file:** research/g151_rules_2.json#2 (n_rows=3)

## Verdict: SILENT

The harvested corpus (Discord/YouTube transcripts from Scarface and Jdub) contains no explicit statements about ambiguous or multiple stop candidates as a downgrade criterion.

### Evidence searched:
- `data/night/harvest/` — 6,161 harvested YouTube moments; 0 statements on ambiguous/multiple stops
- `data/jdub_levels.jsonl` — 546 Jdub level statements; none address stop ambiguity
- Discord capture data — no Scarface/Jdub statements found on stop ambiguity or multiple stop candidates

### Source of the rule:
The three quotes supporting this rule all originate from Austin's own marks, not the corpus:
1. "AS CANDLE FORMING, see on that candle close you get a bad entry? and its hard to enter a stock when there 2 stop loss options..." — `probe_trade_anatomy_2026-09-01` (PLTR_2024-10-23)
2. "not respecting level, 2 stop losses to choose from no other" — `probe_g84_all_in_one_STANDING154_2026-09-01.jsonl` (META_2024-09-30)
3. "mini higher highs so makes the stop muddled" — `recovered_reviews.jsonl` (PLTR_2025-08-06)

### Implication:
Per the spec (F4): **Corpus-only ideas are NOT added.** This rule originates from Austin's marks (mined in F1/F2), not from Scarface/Jdub corpus statements. The corpus is silent on whether multiple/ambiguous stops are themselves grounds for downgrade; traders discuss tight vs. wide stops, and the harvest captures stop *placements*, but not the ambiguity criterion as a standalone downgrade signal.

---
**Row: F4** | **Status: SILENT** | **Base: f8740f80**
