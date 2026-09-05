g210: a 40-line digest of how Austin grades an S day, pulled from `omen-rulebook.md` and AUGUR.md `Decided` — no backtest numbers, his vocabulary only.

## Break-and-retest (BR), in his words

A level breaks, price comes back to retest it, and the retest either holds (trade) or
doesn't (no trade). "BR is focusing on that one level." The one-candle rule (OCR) is
the other level-generator: "one candle that's the opposite color of the way it's
trending" — the down-close candle in an uptrend, or vice versa — and it only counts once
"price respects it and breaks and retests it." OCR is not standalone signal; it
manufactures a level, and BR runs on that level. "BR and OCR is also a setup when both
of them are together" — a third setup class, not two overlapping ones.

## The S/A/C ladder

`grade = S − (downgrades tripped) + (confluence bonus)`, floored at C. **S = clean.
A = one variable downgrade. C = two.** BR+OCR confluence is a **+1 upgrade**, not a
neutral rebate against a downgrade — "with OCR and level confluence, that counts as +1
instead of a downgrade." A second, independent upgrade: "bull/bear PA and below/above
at least 5/6 levels I watch a +1." One downgrade plus clean confluence can still grade S.

## The eight (now nine) downgrade variables

1. No displacement candle — the break has no force behind it.
2. Stale retest — too many bars after the break; the reaction no longer means anything (10 bars).
3. Level not respected — a **close through** the level, not a wick around it; wicking
   around and closing on the correct side is fine. Chopping on it (2+ touches) counts.
4. Stock exhausted — already made a large move; a filter to rule out trades, not a trigger.
5. Counter-trend candles not respected — red candles in an uptrend not bought back,
   graduated: the more it happens, the more overextended, worth roughly 2.
6. Break of a level then rejection — broke, then immediately gave it back.
7. No retest — broke and ran without ever coming back to the level.
8. One-candle rule not respected — OCR present but not honoured (two candles instead
   of one is a pivot break, not OCR, and costs a grade).
9. Large red-body candle — 75%+ body, contained inside its neighbors' range.

A per-symbol sequence downgrade also applies: after an S/A/C entry, a later same-day
entry that isn't an 84%-rule re-entry can't rank the same quality.

## The refusals

No level → no BR. No displacement → refuse, **unless** BR+OCR confluence, a bull/bear
flag opening the day, or a longer-timeframe thesis excuses it. Chop (closing at/on the
level repeatedly) is disrespect, not a setup. Exhaustion (a large move already made)
rules the trade out before entry — it's a filter, never a trigger. A far target does
**not** refuse a trade; find another of the six levels instead.

## The one tolerance unit

**25% of the previous candle's range** — one constant, three jobs: the ON WATCH entry
trigger, the 84%-rule reclaim tolerance, and stop slippage. It is not "close but didn't
touch"-vague; it is one measured unit governing all three, keyed to the *previous* bar
because the current bar's range is unknown until it closes.

## Trend is a downgrade, not a veto

Counter-trend candles not respected cost a grade (variable 5); they do not disqualify
the trade outright. A setup can still reach S with one downgrade if confluence offsets it.

## Stops, entries, ON WATCH

Stop is a **structure point the setup picks**: wick of the OCR candle, the candle
entered on, or the broken level on a B&R — chosen per-trade for best tradable RR, with
a hard disaster stop under it. Max loss is **−1R**, no clamp past it. Entry trigger is
a **close** where a level sits at entry (the confirmation regime); ON WATCH is a
**decision clock** (hold to ~T-15s, take it or abort) for the HOD/LOD-running case with
no level to lean on — it changes the fill, not the verdict. The six levels, closed:
PDH, PDL, PMH, PML, HOD, LOD. No seventh.

## The day policy

Trade the first S setup of the day; if it wins, done for the day. If it loses, "stack a
few more to turn that day green" — the loss-halt count is still being measured, not a
fixed rule. Earlier is better: "the earlier in the day you trade, the more common it is
for S trades and higher probability." The 10:45–11:00 window is bad but stays in the
book — don't re-propose cutting it.
