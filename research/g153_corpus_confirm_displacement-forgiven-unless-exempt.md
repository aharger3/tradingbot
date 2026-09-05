# F4: Corpus Confirmation — Displacement Forgiveness Rule

**Candidate Rule:** A break-and-retest with no displacement on the break leg is forgiven ~90% of the time when he grades S; the other ~10% only via three named exemptions -- BR+OCR confluence, a bull/bear flag at the open, or an HTF thesis.

## Finding

| tag | quote | source |
|---|---|---|
| **confirmed** | "This is true for 90 percent of S trades. for the other 10 percent, no displacement is forgiven if: BR OCR confluence, bull/bear flag to start the day, longer timeframe thesis" | `research/rule_ballot_batch01.jsonl` q18, ballot answer from Austin |

## Evidence

1. **Direct confirmation from Austin's rule ballot** (ballot q18, rule `br-needs-displacement`):
   - Answer: "tweak" (applies with conditions)
   - 90% S-trade statement matches the candidate exactly
   - Three exemptions named: BR+OCR confluence, bull/bear flag at open, longer-timeframe thesis

2. **Measured evidence from marked decks** (H2/3-lane probe):
   - AAPL_2025-07-01_b23: graded S, engine flagged `no_displacement`
   - AAPL_2026-08-03_b6: graded S, engine flagged `no_displacement`
   - BABA_2025-04-01_b12: graded S, engine flagged `no_displacement`
   - Pattern: Austin grades these S despite `no_displacement` downgrade, supporting the ~90% forgiveness claim

3. **Corpus-only idea test**: Not a corpus-only idea. Rule originates from Austin's own ballot answer, not from Scarface/Jdub statements. No contradicting corpus statements found.

---

**Status:** Confirmed — rule is ratified in `omen-rulebook.md` with identical three exemptions.
