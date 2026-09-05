# F4: Corpus Confirmation — stop-placement-routed

**Rule:** "The stop is a choice among structure candidates -- entry-candle extreme, OCR wick, or the broken level / pivot structure -- picked per trade for the best tradable risk; where they disagree and risk is tight he takes the wick, not the level."

**Verdict:** `silent`

**Corpus Search:** Searched harvested corpus files including:
- `research/corpus_setup_rules.jsonl` (extracted from YouTube videos via qwen3.5:4b)
- `research/marks/probe_g84_all_in_one_STANDING154_2026-09-01.jsonl` (Austin's marked trades)
- `research/discord_curated/rule_statements.txt` (Discord trader statements)
- `omen-rulebook.md` quote database (trader ballots and statements)
- Vault corpus references (CORPUS.md, corpus status)

**Closest Related Statement Found:**

From `C:/Users/aharg/Austin's Vault/Projects/omen-rulebook.md` line 630-633:

> "stops are wherever makes sense live. they are not pre known because we dont have HTF thesis from corpus yet. examples wick of OCR, candle entered on, break and retest of a level stop loss that level. most popular off the top of my head. market and limit orders a different beast."

**Attribution:** This quote appears in Austin's rulebook documentation but is not explicitly attributed to Scarface or Jdub in the corpus. It reads as Austin's synthesis of observed trader practice, not a direct trader statement.

**Finding:** The rule is confirmed in Austin's own marks and decisions (evidence of him choosing between multiple stop candidates), and it is documented in the rulebook. However, no direct corpus statement from Scarface or Jdub explicitly confirms the specific rule about choosing the wick when risk is tight. The corpus is silent on this formulation.

---

## Row Entry

| Rule Candidate | Source | Verdict | Quote | Path | Notes |
|---|---|---|---|---|---|
| stop-placement-routed | corpus-3 harvested | silent | "stops are wherever makes sense live... examples wick of OCR, candle entered on, break and retest of a level" | omen-rulebook.md L630 | Documented in Austin's rulebook; attribution to trader uncertain; no direct Scarface/Jdub statement found confirming the risk-tight-chooses-wick formulation |
