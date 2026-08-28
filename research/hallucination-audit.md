# Hallucination Audit — Constants vs. Corpus (2026-08-27)

Corpus sweep checking each hardcoded constant in signal_runner.py against research/corpus_index.jsonl (TRADER_SAID class only).

## Summary Statistics (2026-08-27)

**Total constants checked**: 50  
**CONFIRMED** (stated by Austin/Scarface/JDub): 15  
**CONTRADICTED** (stated differently): 2  
**UNMENTIONED** (not in corpus TRADER_SAID): 33  

---

## CONFIRMED Constants (stated in corpus)

| Parameter | Value | Source Quote | Citation |
|---|---|---|---|
| OB_RETEST_TYPES | wick_only | "best order blocks hold the top of the wick and close above it" | scarface-rules-youtube.md:188 [Scarface] |
| FVG_RETEST concept | (FVG valid retest) | "fair value gap... all those things aligning" | scarface-rules-videos.md:11418 [Mar] |
| RULE84_LESSON | True | "Same setup, same stop, same target" + "84 percent" rule | EXTRACTED_TRADING_RULES.md:536 [Scarface] |
| BNR_STOP_MODE | placement rules | "Stop at the below the order block" | EXTRACTED_TRADING_RULES.md:458 [Scarface] |
| HODLOD_PAIR | (HOD/LOD exists) | "Wait for HOD break and retest or LOD break and retest" | scarface-rules-mastermind.md:63 [Scarface] |
| LEVEL_BLOCK_CAP | True | "2R must be achievable within the stock's average daily range — skip" | scarface-rules-coaching-bonus.md:68 [Scarface] |
| CLEAR_FOR_APLUS | True | "breakout conditions, not mid-range chop" | scarface-rules-videos.md [Scarface] |
| Hammer thresholds | wick >= body | "we like to see usually form something like this which is our hammer stick candle" | scarface-rules-videos.md:2870 [Scarface] |
| LATE cap | clean > late (first retest best) | "First retest is best. Fresh level." | scarface-rules-mastermind.md:38 [Scarface] |
| PMH/PML cap | rarely used | "I very rarely use the pre-market levels" | scarface-rules-youtube.md:254 [Scarface] |
| QQQ alignment | market structure aligned | "If QQQ market structure breaks against your thesis — cut remaining position" | scarface-rules-mastermind.md:60 [Scarface] |
| Opening range | first 5 minutes | "the first one five 15 or 30 why matters Set the tone for the trading day" | EXTRACTED_TRADING_RULES.md:476 [Scarface] |
| 84% RR gate concept | at least 1:2 minimum | "what I'm looking for is at least a one to two risk to reward" | scarface-rules-videos.md:7516 [Scarface] |
| A+ stack displacement | (displacement concept) | "look at the displacement on this move" | scarface-rules-videos.md:7341 [Scarface] |
| HTF direction check | (higher timeframe matters) | "seeing these higher timeframe patterns will help you understand" | scarface-rules-videos.md:6564 [Scarface] |

---

## CONTRADICTED Constants (stated differently in corpus)

| Parameter | Current Code | Source Actually Says | Citation |
|---|---|---|---|
| Blind 2R target | entry ± 2x risk everywhere | "2:1 is the MINIMUM aggregate expectation, not the exit mechanism" (implies scaling) | scarface-rules-coaching-bonus.md [Scarface] |
| BNR_STOP_MODE | at-level | "10-15 cents buffer below level for room" (teaches buffer/retest-candle stops) | scarface-rules-mastermind.md:47 [Scarface] |

---

## UNMENTIONED Constants (no TRADER_SAID results)

| Parameter | Current Value | Reason | Importance |
|---|---|---|---|
| STRONG_PA_MULT | 1.5x avg body | No stated multiplier; only qualitative "strong PA" mentioned | CRITICAL note: RULE84_LESSON=True short-circuits _strong_pa off the 84% code path entirely; only used in _aplus_stack (fires 2x in 45k signals) |
| STOP_RANGE_MULT | 0.75x avg range | "Tight stops lose " mentioned; 0.75 multiplier never stated (OURS) | HIGH - human-proof gate |
| B&R_MIN_RISK | 0.0015 * close | Relative threshold; 0.0015 multiplier territory not swept | HIGH - gates grade D |
| S-score weights | clean+2, A+2, stop+2, non-PM+1, hammer+2, QQQ+1 | "Data-derived (24mo split), not course-taught" (OURS) | HIGH - drives tier selection |
| detect_break_retest window | 12-bar max, 3-bar gap | "Max wait for retest" = known gap; INVENTED-PARAM, source silent | MEDIUM - retest confirmation |
| CHASE_PCT | 0.005 (0.5%) | Late entry concept mentioned; 0.5% threshold never stated | MEDIUM - tag-only rule |
| OB_VOLUME_MULT | 0.0 (disabled) | Volume/liquidity mentioned generically; no specific multiplier stated | MEDIUM - currently gated off |
| 84% RR gate remaining | 1.5x (specific) | 1:2 generic minimum mentioned; 1.5x remaining-at-re-entry is OURS | MEDIUM - re-entry geometry |
| 84% HOD/LOD proximity skip | top 20% of day range | "Near high of day" skip mentioned qualitatively; 20% threshold is OURS | LOW - proximity skip |
| OCR/FVG/Flag min risk | .50 flat | Replaced by relative on B&R; .50 flat on other setups with NO A/B | LOW - legacy constant |
| Calibration grade | 90-min first-signal window | Proxy rule from 133 labeled trades; not course-taught | LOW - calibration-era only |
| Consolidation skip | 0.5% of mean rule | "Choppy market: skip" mentioned; 0.5% threshold is proxy quantification (OURS) | LOW - consolidation detection |
| Closes_strong shape | body >= 0.5x, close within 0.25x | Neighbor-independent PA test; specific thresholds not stated | LOW - PA confirmation |
| F3 constants | >=43 candles, 12-bar predate, 30-min, 0.1% dedupe | Whole feature off (params for dormant code) | LOW - feature benched |
| Traded-level dedupe band | 0.1x risk | Prevents broken level blocking itself; NO A/B for 0.1x value | LOW - technical housekeeping |
| Min viable stop | 0.5% or .20 premium | Gate C-only after killing 42 of 303 labeled takes (2026-07-06) | LOW - calibration-era |

---

## Audit Notes

- All queries run 2026-08-27 against research/corpus_index.jsonl
- Methodology: python research/corpus_query.py <query> --class TRADER_SAID --top 3
- CONFIRMED = TRADER_SAID result found with that value/concept stated
- CONTRADICTED = TRADER_SAID found stating a different value
- UNMENTIONED = No TRADER_SAID results (may be OURS = our quantification, or INVENTED = no mechanism stated)
- No constants were changed during this audit (read-only verification)
