# F4 Corpus Confirmation: cheap-stock-refusal

## Candidate
**cheap-stock-refusal**: "Cheap, low-priced stocks are harder to trade and get refused or capped below S, independent of setup quality."

## Corpus Search Results

### Tag: **CONFIRMED**

**Quote (direct, verbatim from Austin's marks):**
> "this is a cheap stock thats why I won't upgrade to s"

**Source:** `research/marks/probe_omen_test1_2026-08-27.jsonl`, card ACHR_2026-03-30, symbol ACHR, date 2026-03-30

**Context:**
- Card graded: A (Austin explicitly capped at A instead of S)
- Setup: BR+OCR with confluence
- Entry: 09:46 ET at $5.00
- Stop: $5.03 (swing high)
- Side: Short
- Note from Austin: "9:39 another possible entry but this is a cheap stock thats why I won't upgrade to s"

**Supporting Evidence from Same File:**
1. ACHR_2026-04-10: "would never trade this because of how ugly the candles and cheap the stock is" (graded S, but explicitly refused)
2. MARA_2026-02-17: downgrades as "cheap stock, and high risk low reward" (downgraded from baseline)
3. MARA_2026-03-02: "only caveat is this stock is super cheap" (graded S but flagged as caveat)
4. `probe_master_2026-08-29.jsonl`: "FVG and flag we don't trade, cheap stocks suck" (categorical refusal)

## Verdict
The rule is **CONFIRMED** in Austin's own grading. He explicitly refuses or caps below S based on stock price alone, independent of setup quality. ACHR_2026-03-30 shows a valid setup (BR+OCR) that would qualify for S, but is capped at A specifically because the stock is "cheap." This directly matches the candidate definition.

