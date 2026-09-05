# g210 — the S-day rulebook, in Austin's vocabulary

One-sentence claim: this restates how Austin grades a trade day, sourced only from
`omen-rulebook.md` and `AUGUR.md` (Decided), with no backtest number attached.

## Break-and-retest (BR)

One of his six watched levels — PDH, PDL, PMH, PML, HOD, LOD — gets broken, then price
comes back to retest it. The retest either holds (level respected, keeps working as
support/resistance) or fails. BR is "focusing on that one level," his words. It is the
majority setup in the book — the one-candle rule (OCR) is the minority, and BR+OCR
together is its own third class, not two setups stacked.

## The one-candle rule (OCR)

His own definition: "one candle that's the opposite color of the way it's trending" —
the down-close candle in an uptrend, or the up-close candle in a downtrend. It is a
**level generator**, not a signal by itself: price must then respect it and break-and-
retest it. He counts it when the candle would be "good to use as the stop." Standalone
is fine — "no level BR just OCR ... it's a classic S setup." Two candles instead of one
is not OCR; that is a pivot break, and it costs a grade.

## The S/A/C ladder

**S = clean. A = one variable downgrade. C = two.** Not a vibe call — a count:

    grade = S − (downgrades tripped) + (confluence bonus)

A setup with one downgrade AND clean BR+OCR confluence at the level is still S, because
confluence is a bonus, never a rebate that only cancels a downgrade. Confluence absent
costs nothing.

## The eight downgrade variables

1. No displacement candle — the break has no force behind it (three exemptions forgive
   it: BR+OCR confluence, a bull/bear flag to start the day, a longer-timeframe thesis).
2. Stale retest — too many bars after the break; the reaction no longer means anything.
3. Level not respected — candles **closing through** the level, or chopping on it,
   instead of reacting off it. Wicking the level is fine; a close through is the tell.
4. Stock exhausted — already made a large move; the setup is real but spent.
5. Counter-trend candles not respected — red candles in an uptrend (or green in a
   downtrend) that don't get bought back; graduated, not a switch — each occurrence
   lowers probability further, it does not flip a bit.
6. Break of a level then rejection — broke, then immediately gave it back.
7. No retest — broke and ran without ever coming back to the level.
8. One-candle rule not respected — OCR present but not honoured.

Two later additions, not yet folded into the eight: a large (~75%) red body candle
sitting inside its neighbors' range, and a per-symbol sequence downgrade (a later entry
that isn't an 84%-rule re-entry can't grade as high as the first).

## The refusals — what makes X, not a low grade

- **No level.** BR needs one of the six he watches; without it there's nothing to grade
  against (OCR standalone is the one exception, since it generates its own level).
- **No displacement, and no exemption covers it.** Displacement is required unless
  BR+OCR confluence, an opening flag, or a longer-timeframe thesis excuses its absence.
- **Chop.** A level that's being closed through repeatedly, not reacted off, is a bad
  level to break-and-retest — drop it.
- **Exhaustion.** Not a trigger, a filter: "helps rule out S trades automatically" once
  the stock has already made its large move.

## Trend is a downgrade, not a veto

Higher-timeframe/trend context does not kill a setup outright — there is no authored
HTF veto in his own words ("we don't have any higher timeframe bias yet, you'll need to
tell me what that is"). Counter-trend candles not being respected is downgrade #5, one
count against the grade like any other variable — it costs a grade, it does not zero
the trade. The later HTF idea he described is a **ranker** (prefer the setup the higher
timeframe likes best), not a wait-or-veto gate either.

## The one tolerance unit

**25% of the previous candle's range.** One constant, three jobs: how far beyond a
level price must move to trigger the entry, how close a close may sit to the original
entry on an 84%-rule reclaim, and how much stop slippage is allowed. The previous
candle, never the current one — a bar's own range isn't known until it closes.

## Stops and the day

Level stop triggers and fills on the 1-minute candle **close**, never a wick. A
resting disaster stop exists purely as a catastrophic backstop, not a normal exit.
Three losses ends the trading day. Source: `omen-rulebook.md` (Grading, Stops,
Entries, The 84% rule, The downgrade list, OCR, ON WATCH, sessions 2026-08-29/08-30);
`AUGUR.md` Decided 2026-09-03.
