# T19: FVG and Flag Setup Verdict

**Date**: 2026-08-29  
**Status**: Verdict written. Code is dead and can be deleted.

## Summary

The corpus contains **zero explicit references** to fair-value-gap (FVG) or flag as standalone trading setups. Both concepts are permanently disabled in the live engine, and Austin's own judgements never mention them as part of his trading methodology.

## Findings

### Corpus Search Results

Searched all mark files:
- `austin_marks_v2.jsonl` through `austin_marks_v7.jsonl` (full grading history)
- `blind_marks_all.jsonl` (blind pass)
- `recovered_reviews.jsonl` (prose reviews)
- `marks_clean.jsonl`, `derived_marks_v1.jsonl`, `derived_marks_v2.jsonl`
- Probe files (autopsy and head-to-head)

**FVG**: 0 matches  
**FLAG**: 5 matches, all false positives or context misuse (see below)

### What the "FLAG" Matches Actually Are

The 5 matches containing the word "flag" are:

1. **"flagging as S"** (verb, not setup name) — Austin marking a one-candle-rule card as S tier
2. **"bull flag pattern"** (lines 113, 117, 131, 133 in recovered_reviews.jsonl) — Descriptions of price action WITHIN break-and-retest setups, not a standalone flag setup
   - E.g.: "bull flag pattern of bull movement then rest then strong bull movement" (describing retest consolidation)
   - All marked as B&R setup, not flag setup
   - Never referenced as a primary trading pattern

### Setup Universe in Corpus

Complete list of all setups mentioned in 1,836 marked cards:

| Setup | Count | Trading or Marker |
|-------|-------|-------------------|
| break_and_retest | 172 | Trading |
| Break & retest | 56 | Trading (alt spelling) |
| one_candle_rule | 41 | Trading |
| One candle rule | 13 | Trading (alt spelling) |
| 84% re-entry | 67 | Trading |
| OCR | 109 | Trading (likely one-candle-rule misspelling) |
| Order block | 12 | Trading |
| (blank/unknown) | 275 | Not trading |
| **FVG** | **0** | Not found |
| **Flag** | **0** | Not found |

### Code Status

#### FVG (Fair Value Gap)
- **Location**: `omen_bot.py::find_fvg()`, used in `signal_runner.py`
- **Status**: Disabled via `FVG_RETEST = False`
- **A/B Evidence**: 2026-07-05 A/B test showed FVG retest zones diluted break-and-retest badly
  - 206 trades @ 33% win rate, −$216 total
  - B&R alone: 28 trades @ 50% win rate, +$1,400 total
  - Verdict in code comment: "FVG retests diluted B&R badly"

#### Flag (Pattern)
- **Location**: `omen_bot.py::detect_flag_setup()`, called in `signal_runner.py`
- **Status**: Permanently disabled via `FLAG_ENABLED = False` (line 67)
- **A/B Evidence**: 2026-07-08 speculative build (no ordered rebuild, not ordered by Karpathy's rule #1)
  - Fired 465 times over 12 months at 28% win rate = −$57.6k total system loss
  - Austin never visually validated the detector
- **Code Comment**: "Flag detector BENCHED 2026-07-09… Re-enable only after an ordered rebuild + his chart review"
- **Status in T0/ratified**: Not landed (R7/R8/R9/R10/R11 explicitly NOT asserted in `research/test_t0_ratified.py`)

### Mentor Teaching: Scarface/JDub

Searched recovered_reviews for explicit teaching moments from Scarface or JDub mentioning FVG or flag:

**Result**: Zero matches.

Scarface is mentioned teaching:
- Break-and-retest strategy ("Scarface teacher this strategy recently…")
- Order block + retest confluence
- Psychological levels (e.g., 188, 189)
- HOD and LOW targeting

No mention of:
- FVG (fair-value-gap zones)
- Flag (pole-and-flag patterns)

## Verdict

✓ **Corpus does not support FVG or flag as trading setups.**

Austin's rules are:
- Break & retest (with or without displacement)
- One-candle rule
- 84% re-entry after a loser
- Order block + retest
- Pre-market levels (R23)

Neither FVG nor flag appear in his marks, his notes, or his mentors' teaching. The code is:
- **FVG**: Tested and rejected (A/B 2026-07-05, dilutes B&R)
- **Flag**: Built speculatively, never validated by Austin, tested once with −$57.6k loss

## Next Steps (Not This Track)

T22 or T23 (per caveats in T0) should handle code cleanup:
- Delete `find_fvg()` from `omen_bot.py`
- Delete `detect_flag_setup()` from `omen_bot.py`
- Remove imports and test stubs (`test_flag.py`, FVG references in `signal_runner.py`)
- Remove disabled gates: `FVG_RETEST`, `FLAG_ENABLED`
- Update code comments to reference this verdict instead of "await rebuild"

The gate branches themselves stay (they never fire), but the dead code can be removed.
