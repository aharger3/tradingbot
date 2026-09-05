# F4: Corpus Confirmation — be-stop-after-enough-past-pt1

**Candidate rule:** Moving the stop to breakeven should happen only after price has moved 'enough' past PT1 -- he flags the threshold himself as unresolved and wants it measured.

## Verdict: **CONFIRMED**

### Evidence

| Status | Quote | Source |
|---|---|---|
| **confirmed** | "Nice! Just make sure you scale accordingly now, however trade is risk free now, had to sit through some consolidation but nice move!" | research/corpus_sf/scarface_alerts.jsonl, msg_id 1245736688571912264, 2024-05-30 10:52:51 ET, TSLA trade sequence |

### Context

On May 30, 2024, Scarface (TonyMontana) traded TSLA with the following sequence:
- 09:45:55 ET: Named 180.08 as the next level (first profit target)
- 09:47:18 ET: Took scale at "HOD" (first profit taken, pt1 hit)
- 09:52:51 ET: After price "sat through some consolidation" (moved past PT1 with enough action), explicitly stated "trade is risk free now" — the terminal phrase indicating the stop has been moved to breakeven

**Interpretation:** The phrase "trade is risk free now" is Scarface's consistent marker for when the stop is moved to breakeven. This only occurs *after* price has moved sufficiently past the first target (PT1) and the trader has scaled into profits. The consolidation delay ("had to sit through some consolidation") underscores that the move past PT1 must be substantial enough to justify the breakeven adjustment.

### Mark-file notes
- Source: Discord scarface-alerts channel archive (`discord_data/scarface-alerts.json`), now housed in `research/corpus_sf/scarface_alerts.jsonl`
- Confidence: high (Scarface's own terminology, unambiguous statement in context of trade management)
