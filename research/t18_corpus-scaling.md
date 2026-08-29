# T18 -- corpus-scaling

Austin: "scaling and letting runners run needs to come from corpus or watch your own scrape
content if you can."

**Method.** Queried `research/corpus_index.jsonl` (5,460 provenance-tagged rows, drawn from
`scarface-rules-videos.md`, `-youtube.md`, `-mastermind.md`, `-discord.md`,
`-coaching-bonus.md`, `-accelerator.md`, `EXTRACTED_TRADING_RULES.md`, `84rule-sizing-dossier.md`
and `hallucination-audit.md`) via `research/corpus_query.py`, an 11-query set fixed in
`research/t18_corpus_scaling_queries.py`. Full raw output committed at
`research/t18_corpus_scaling_queries.out`. Every quote below is `TRADER_SAID` class (a
mentor's own words) unless marked otherwise, with its source file:line. This report validates
against the corpus -- it does not author rules; where the corpus is silent or split, that is
reported as such, not resolved by invention.

**The engine today** (`backtest_week.py` F1 ladder, `LADDER_MODE="B"`, lines 84-96, 419-470):
50% of the position exits at the first HOD/LOD touch after entry; the stop stays at its
original level until that scale fires, then moves to breakeven; the runner (the other 50%)
rides to the first key level beyond the scale point (PDH/PDL/PMH/PML/next whole dollar,
falling back to the original 2R target).

---

## Finding 1 -- "50% off at HOD" -- CONTRADICTED (as a flat, context-free number)

The corpus never states a flat 50%-always split. It states 50% is *one point on a scale that
moves with market regime*, and trending days -- OMEN's stated edge case, break-and-retest in a
trending 09:30-11:00 window -- sit at the low end of that scale, not at 50%:

> "Choppy day, I'd take 50% off a high day then let the other 50% ride. Day where it's
> trending, I would take 25% off a high day or maybe even less 10% 15% off a high day and then
> let the rest ride."
> -- Scarface/jdub, `research/scarface-rules-videos.md:318` (`bonus_How_To_Swing_Trade_Q_A.txt`
> [2186s-2200s])

> "Trending market: take 25% (even 10-15%) at HOD. Choppy: take 50% or all at HOD."
> -- Scarface/jdub, `research/scarface-rules-coaching-bonus.md:143` (`bonus_1461018`, ~00:36:28)

> "If we're in a range market then I'm gonna take the full position off at high of day... if
> we're in a trending market then I'll only take off 20% of let the rest ride."
> -- Scarface/jdub, `research/scarface-rules-videos.md:519`
> (`bonus_My_Bread_Butter_Strategy_How_To_Draw_Key_Levels_transcript.txt` [5966s-5975s])

> "Choppy market: take 100% off at HOD. Just scalp it."
> -- Scarface/jdub, `research/scarface-rules-mastermind.md:153` (`mastermind-4-0_1461032`,
> 00:10:08)

> "I scale 80% out of high of day, because I know that though I took the risk, QQQ if it breaks
> below this level, the momentum on Tesla may die."
> -- Scarface/jdub, `research/scarface-rules-videos.md:985`
> (`boot-camp-recordings_Day_13_Trameframe_Psychology.txt` [2684s-2689s])

> "If I didn't take the first trade you can look to scale some at high day in this case you can
> do like 25% right higher time frames 50 and then 25 back towards upside."
> -- Scarface/jdub, `research/scarface-rules-videos.md:3494`
> (`building-your-profitable-system_Lesson_6_Building_Logic.txt` [1161s-1181s])

Every one of these ties the scale-out fraction to a stated market-regime read (trending /
choppy / ranging) that the engine's HOD/LOD ladder does not compute or condition on anywhere in
`backtest_week.py`. 50% appears as the value quoted specifically for a **choppy** market; for a
**trending** market the same mentor states 20-25%, and in one instance "even less 10-15%." A
range market gets 100%. The engine's fixed 50% is closest to the choppy-day number and furthest
from the trending-day number -- OMEN's own setup family (break-and-retest, 09:30-11:00) is not
tagged to either regime in the corpus, so there is no clean mapping to hand the engine; the
finding is that a flat 50% is a simplification the corpus does not support, not that a
different flat number would fix it.

## Finding 2 -- "stop to breakeven after the first scale" -- CONTRADICTED, corpus is split against itself

The engine moves the runner's stop to breakeven the moment the 50% scale fires. The corpus
contains a direct statement of exactly this:

> "After first scale: can move stop to breakeven (1:1), then hold runner."
> -- Scarface/jdub, `research/scarface-rules-mastermind.md:161` (`mastermind-1-0_1460324`,
> 00:46:37)

But the *same mentor, same "bread and butter" lesson*, states the opposite -- that the HOD
scale specifically does **not** trigger a breakeven move, and that the stop only moves on a
structure break, independent of any scale event:

> "After my high of day scale that doesn't mean I'm gonna let my stop go break even. Oh my stop
> loss was still still the same."
> -- Scarface/jdub, `research/scarface-rules-videos.md:523`
> (`bonus_My_Bread_Butter_Strategy_How_To_Draw_Key_Levels_transcript.txt` [5748s-5754s])

> "You only move your stop loss when market structure changes. You don't move it before based
> off your trade."
> -- Scarface/jdub, `research/scarface-rules-videos.md:523` (same source, [5772s-5774s])

> "Our stop loss always remains constant until we break that structure."
> -- Scarface/jdub, `research/scarface-rules-videos.md:430` (same source, [1626s-1633s])

This is not one ambiguous line -- it is two full, opposite statements of a rule for stop
management after the first scale, from the same person in different sessions
(`mastermind-1-0` vs. the bread-and-butter bonus video), with no date or context differentiator
in the corpus that reconciles them (e.g. neither ties itself to a regime the way Finding 1's
quotes do). Flagged CONTRADICTED rather than CONFIRMED because the corpus itself does not
converge -- the engine's choice (move to breakeven) has direct textual support, but so does
its negation, in equal-weight sourcing.

## Finding 3 -- "runner to the next key level" -- CONFIRMED

This is the one leg of the engine's three-part rule the corpus supports without internal
contradiction:

> "If you're trading, wanted to contracts, get one is hard but let's just say two, get out a
> high of day for one and then your second one go for higher time frame key levels -- don't
> scale anything until higher time frame key [levels]."
> -- Scarface/jdub, `research/scarface-rules-videos.md:1309`
> (`boot-camp-recordings_Day_15_Conclusion_Final_Q_A.txt` [2871s-2883s])

> "Previous pivot levels right so those are gonna be higher time frame levels that we're going
> to exit on, for example on the four-hour."
> -- Scarface/jdub, `research/scarface-rules-videos.md:430`
> (`bonus_My_Bread_Butter_Strategy_How_To_Draw_Key_Levels_transcript.txt` [1759s-1763s])

> "The trailers can make you more than the whole potential trade."
> -- Scarface/jdub, same source, [5714s-5719s]

> "Gold trailers for next levels which are far and therefore u should be taking hod scales but
> 290 + 293 key level."
> -- Tony, `research/84rule-sizing-dossier.md:214` (2025-05-01 14:33:34)

All four sources describe the same mechanism the engine implements: the first tranche exits at
a near-term extreme (HOD/LOD), and what remains rides toward the *next* higher-timeframe level
rather than a blind fixed-R target. No corpus row found in this pass contradicts running the
remainder to a further key level. This leg needs no change.

## Finding 4 -- market-regime read is UNMENTIONED as engine input

Findings 1 and 2's split both resolve, in the corpus's own words, along a variable the engine
never reads: is the day/market trending, choppy, or ranging. `backtest_week.py`'s F1 ladder has
no regime classifier -- `LADDER_MODE="B"` fires identically on a chop day and a trend day. The
corpus repeatedly makes the scale fraction and (implicitly, via "hold... don't scale" language)
the stop discipline conditional on that read, and OMEN already computes a bias/trend signal
(`runner.htf_bias`, `qqq_breaks` -- see `backtest_week.py` args) that is available at the same
call site as the ladder logic but is not wired into it. This is not a rule to land -- per Method
Rule 6/T18 scope, this report validates, it does not author -- but it is the one place the
corpus's contradictions (Findings 1, 2) stop looking like noise and start looking like a missing
regime input.

---

## Summary table

| Engine rule | Verdict | Corpus support |
|---|---|---|
| 50% off at first HOD/LOD, always | CONTRADICTED | Corpus ties the fraction to market regime: choppy=50-100%, trending=10-25%, range=100%. No flat-50% quote found. |
| Stop to breakeven after first scale | CONTRADICTED | One direct quote for it (`mastermind-1-0`), one direct quote and two supporting quotes against it (bread-and-butter bonus video), same mentor, no reconciling context in the corpus. |
| Runner to next key level | CONFIRMED | Four independent quotes, no contradiction found, matches engine behavior (PDH/PDL/PMH/PML/whole-dollar fallback to 2R). |
| Regime-conditioned scale sizing | UNMENTIONED (as engine input) | Corpus requires it; engine has the signals (`htf_bias`, `qqq_breaks`) already computed but not wired to the ladder. |

## Caveats -- what did not run

- This is a corpus-text validation pass, not a backtest A/B. No `bt2y` re-run, no mean-R or
  recall number is claimed for any alternative scaling scheme -- Method Rule 6 forbids claiming
  a result not run, and none was run here.
- `corpus_query.py` is lexical (token-overlap) ranking, not semantic search. The 11 queries in
  `research/t18_corpus_scaling_queries.py` were chosen to cover the engine's three stated
  mechanisms plus regime language; a different query set could surface additional rows, though
  the ones retrieved were consistent and repeatedly cross-corroborating (same claims recur
  across `-videos.md`, `-mastermind.md`, and `-coaching-bonus.md`, which are three separately
  scraped sources).
- No claim is made about which regime-classification signal (if any) is reachable/well-behaved
  enough to gate the ladder -- Method Rule 3 (check reachability before tuning) is out of scope
  for a corpus-only track and is flagged to whoever picks up Finding 4, not answered here.
- `youtube_data/` and the raw Discord/Circle JSON exports were not queried directly; all of
  their content that has been provenance-tagged already flows through `corpus_index.jsonl`
  (built by `research/corpus_index.py`), which is what this report queries. Anything scraped
  but not yet indexed is outside this pass.

## Files

- `research/t18_corpus_scaling_queries.py` -- the fixed 11-query script (committed, run to
  produce every quote above)
- `research/t18_corpus_scaling_queries.out` -- full raw `corpus_query.py` output for all 11
  queries (committed)
- `research/corpus_index.jsonl` -- read only, not modified
- `backtest_week.py:69-96, 419-470` -- the engine rule being checked (read only, not modified)
