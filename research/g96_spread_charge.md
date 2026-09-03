# OMEN 8.0 R7 -- charging the option round-trip spread

925 trades, reused from `research/g90_fill_arms_rows.json` (R1's committed two-year book) -- entry/stop/direction/grade only, re-priced through `options_sizer.build_options_plan` at `GRADE_SIZE_PCT`-scaled sizing (matching how `live_scanner.py` actually sizes a trade, not a flat $1,000), spread OFF (entry and exit both at the mid, the pre-R7 behavior) vs spread ON (the shipped default, $0.05 round-trip). 1R = $1,000, this repo's fixed convention.

## Result

**Mean R impact of charging the spread: -0.1428R.** Total spread cost across the sample: $132,120. 894/925 trades size fewer contracts once the spread is charged (a wider per-contract risk buys less size at the same dollar budget) -- the rest hold their contract count and simply pay the cost on it.

`omen-x-board.md:180-181` cites **-0.2042R**. This reconstruction lands at **-0.1428R** at `GRADE_SIZE_PCT`-scaled sizing -- same order of magnitude, same sign, not an exact match (expected: different sample, different date, and the exact book that produced -0.2042R is not reproducible from this repo -- see below).

## The number is sizing-convention-sensitive -- disclosed, not hidden

Adversarial review asked whether the sizing choice itself moves the headline figure. It does: at a flat $1,000 budget (this repo's other stated convention, `CLAUDE.md`: "1R = $1,000") instead of `GRADE_SIZE_PCT`-scaled, the same sample gives **-0.2374R** -- closer to `omen-x-board.md`'s -0.2042R (a 16% relative gap) than the grade-scaled -0.1428R (30% relative gap). Grade-scaled is what `live_scanner.py` actually does in production (`max_loss=DEFAULT_MAX_LOSS * GRADE_SIZE_PCT.get(grade, 0.6)`, confirmed at `live_scanner.py`'s `_emit_signal`), so it is the more representative headline number -- but neither is more "correct" than the other as a reconstruction of an unreproducible figure, and a reader should not treat either digit as more precise than the sizing convention it rests on.

## A consistency bug the spread fix introduced, found and fixed same-day

An early version of the round-trip-spread fix computed `max_loss`/`max_reward`/`contracts` from the pre-rounding model risk (needed to avoid a DIFFERENT rounding bug -- see `research/g95_delta_fix.md`'s history), while `entry_premium`/`stop_premium`/`target_premium` were rounded independently for the card. On a cheap, near-the-`$0.05`-floor contract those two paths could disagree by up to ~10% of the stated budget -- the Discord card's own displayed prices implied a different risk than the number next to them. Adversarial review caught this before it landed. **Fixed**: `stop_premium`/`target_premium` are now DERIVED from the already-rounded `entry_premium` via a single further rounding, and `max_loss`/`max_reward`/`contracts` are computed from those same final card numbers, not a separate pre-rounding path -- `(entry_premium - stop_premium) * 100 * contracts` now equals `max_loss` exactly, and the equivalent holds for `max_reward`, checked over the full 925-trade sample: 0 mismatches, was up to 63.6% of trades with a >1% gap before.

## What could not be reconstructed

"The 1,017-trade contract book" is `research/t8_two_year.md`'s own committed figure -- already established as stale by R3/R5/R6 (re-running `t8_two_year.py` today gives 926, not 1,017) -- and no options-specific book of either size exists anywhere in this repo or the vault. `research/sizing.py`'s docstring explains why no options book can be built from real fills here at all: "this repo has 1-minute underlying bars and no options chain." This script reuses R1's 925-trade stock-side book (the same substitution R6 already made for its own unreachable 204-trade citation) and re-prices it through the committed, now-spread-aware sizer. The -0.2042R figure itself is not independently reproducible from anything in this repo; what IS verified mechanically is that charging the spread produces a real, negative, same-order-of-magnitude R hit, not that it produces exactly -0.2042.
