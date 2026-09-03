# What the Discord corpus became

You said: *"it has trade reviews from scarface years of data, it could pool all of those and
then those backtest results would be astronomical and it could refine the code."*

Here is what actually came out.

---

## The honest number

**2,604.**

That is how many distinct mentor trade instances we mined that have 1-minute bars sitting on
disk right now, ready to replay with no further work.

| | |
|---|---:|
| Discord messages parsed | ~112,000 |
| Rows a parser could extract | 13,372 |
| Rows that assert a real position (not just a level, not chatter) | 6,318 |
| Distinct trade instances after folding duplicates | **3,547** |
| — of those, bars already on disk | **2,604** |
| — need a 3-minute pull | 155 |
| — futures, can never be pulled with what we own | 709 |
| — weekend posts, not sessions | 79 |

Against your two reference points:

| | count |
|---|---:|
| Symbol-days **you** have judged yourself | 1,147 |
| Trades in the two-year book | 2,437 |
| **New mentor instances backtestable today** | **2,604** |

So in raw volume the corpus roughly doubled your judged corpus and matched the size of the
whole two-year book. That is the good news, and it is the last of the good news about volume.

---

## Was "astronomical" justified? No.

Three reasons, in order of how much they hurt.

**1. Almost none of them are trades.** Of 3,547 instances, **49 state an entry price and 19
state a stop.** These men do not post fills. They post *"took 350 TSLA calls for the HOD"* and
*"stop below PDH."* The numbers in their messages are option strikes and dollar P&L, not chart
prices. So you cannot add a single one of these to the backtest book — there is nothing to
compute a P&L from. What each row really is: **"this mentor was long TSLA on this morning, off
this level."** A dated opinion, not a trade.

**2. The overlap with your own grades is small.** Only **220 symbol-days** have both a mentor
call and an Austin grade on them — 270 instances, 125 of them inside 09:30–11:00. That is the
only set where a mentor can be scored against you head to head, and it is a fifth the size of
your own mark corpus, not a multiple of it.

**3. A third of the mentor content is futures and unreachable.** 709 instances are NQ/ES/YM.
No futures data product is wired into this repo, and that room's vocabulary (opening print,
gap fill, London session highs) is not your six levels anyway.

**What it did produce, which is worth more than the volume was ever going to be:**

- **A second, independent panel to score the engine against** — 1,959 mentor symbol-days that
  the two-year book already covers.
- **225 stated rules** from six mentors, pooled and cross-referenced against your rulebook:
  31 agree with you, 14 contradict you, 15 are things you have never said. Ballot below.
- **A level audit** that says the engine is drawing the wrong levels. Already measured, free.

---

## Three things you can measure tomorrow with zero further work

**1. Does the engine see what six professionals see?** On the 1,959 mentor symbol-days the
book already covers, the engine **fired on 481 (25%)** and actually traded 386 (20%). Inside
the 09:30–11:00 window: fired on 226 of 906 days. So on three days in four where a mentor took
a trade, OMEN was silent. That is a recall number against people who are not you, and nothing
has to be pulled, graded, or decided to compute it properly.

**2. Head-to-head on the 220 days you both judged.** All 270 of those instances already have
bars, and 93 carry the mentor's own claimed result. This answers "when Scarface and I look at
the same chart, do we agree?" — and if you agree often, his other 2,300 days become usable
labels.

**3. Do their self-reports survive the tape?** 851 backtestable instances carry a claimed
result (497 win, 313 loss, 41 breakeven). Replay the bars and you get a per-mentor honesty
score. The review channels only post winners, so expect this to bite.

### Already measured, free, and it matters

The mentors' six levels are not your six levels.

- What humans actually name: **PDH (975 symbol-days), PMH (468), HOD (448), PDL (442),
  PML (253), LOD (212).**
- Opening-range high and low — which the engine ships — rank **16th and 17th** out of
  everything humans name. Behind order blocks, gap fills, and plain "key level."
- **HOD/LOD is switched off in the code** (`HODLOD_PAIR = False`), and HOD alone is the single
  biggest thing the engine misses: 413 symbol-days.
- The engine has 56% of what humans name and misses 44%.
- On top of its own named six, the engine draws **13 more levels per symbol-day** from pivot
  structure, on by default. It carries 3.2x its own stated level set.
- Your higher-timeframe suspicion is not what the data shows: HTF levels are **8.6%** of what
  humans name. The pollution is the pivot machinery, not a higher-timeframe set.

---

## What needs a bar pull, and how long

**400 symbol-days. About 3 minutes, 10 at worst. 32 MB.** No rate limit on the current data
plan.

- **146 of the 400 are GOOG** — the archive banked GOOGL, and the mentors write both. That one
  symbol is 37% of the gap.
- The pull only unlocks **155 more pooled instances**, and they are thin ones (375 of the 550
  underlying rows are low confidence). Cheap, worth doing, not a turning point.
- **The 709 futures instances are not a pull.** A futures data product is not wired into this
  repo. That is a purchase decision, not a script, and the payoff is unclear.

---

## The ballot — 15 things they say that you never have

Yes / no / ignore. Anything you skip stays parked. Nothing here is wired into anything.

1. **A retest is never to the penny** — it lands *near* the line, not on it. *(Neto, said 3x)*
   The code has no retest tolerance at all. Your 25%-of-previous-candle unit would just get a
   fourth job. Nearly free.
2. **Chop is anything short of a strong close through the level** — only trade a strong closure
   above it. *(Scarface, 2x)* A new anchor for your highest-tripping downgrade, which has
   failed three implementations and currently points backwards.
3. **Require a strong reaction at the level after the retest**, not more candles. *(Neto, 7x
   across two phrasings)* Adds a fourth required element; the engine currently enters on the
   retest itself.
4. **Don't take it unless the name can reach HOD or LOD.** *(Scarface, 4x)* Target availability
   as an entry gate — your own "no other levels to target" note, stated as a hard precondition.
5. **Which level family works best is per-ticker** — backtest each name against premarket vs
   previous-day vs opening-range. *(Neto, 3x)* Your six are applied uniformly today. Pure
   measurement; testing it changes nothing.
6. **When the available reward is small, take profit more aggressively.** *(Neto, 2x)* This
   unparks your own 30%-vs-50% first-scale question by naming the discriminator.
7. **Higher-timeframe context = weekly / daily / 4H trend, levels and liquidity.** *(Lauren,
   Mamba, Jdub — 13x combined)* You asked what HTF bias even means. Three of them answer, and
   adopting it would re-gate something you deleted.
8. **The highest-probability trades sit outside the previous day's range.** *(Hayden, 3x)*
   Computable at 09:29, joins the premarket filter that already ships.
9. **The retest candle should be a hammer** — long wick into the level, body respecting it.
   *(Neto, 3x)* You said trends respect wicky candles; you never named the shape.
10. **Use the 09:30 opening price as a reference when no level is close enough.** *(Mamba, 2x)*
    A seventh reference. Your six are closed, so this is a ballot line, not a change.
11. **Specialise — trade four names, or one name and one setup, for a long stretch.**
    *(Neto and Scarface, 7x combined)* You flagged the book's symbol imbalance as a bug. They
    say concentration is the point.
12. **Always take one strike out of the money, or the most liquid contract.** *(Jdub and Neto,
    9x combined)* The options skin has no strike rule at all, and you want reports led in
    dollars.
13. **Mandatory break after a single loss** — plus fixed hours and a daily trade cap.
    *(Neto, 2x)* A third answer to your halt question: not "stop at two," not "trade until
    green," but pause after one.
14. **Take a starter position on an A+ setup rather than miss the move.** *(Jdub, 3x)*
    Scaling *in*. The engine only knows how to scale out.
15. **Cap the stop at 18–25% of the contract premium.** *(Neto, 2x)* Your stop is on the
    underlying; this bounds what it is allowed to cost in the option.

**The two conflicts worth your eyes** (nothing to answer, but they are loud): Scarface waits
out the first five minutes while you say the earliest trades are the best ones — that is the
largest disagreement in the corpus, and your own held-out S entries back you up. And everyone
else takes a fixed 1.5–2R, which you already proved can never average 2R.

**One honest negative on the whole rulebook:** you would expect a core rule to be said forty
times. The most-repeated rule in 8,790 mentor sentences was said **seven** times, and only 21
of 225 were said five times or more. These men teach in prose once, then trade. Frequency ranks
the ballot; it cannot carry it.

---

## How much to trust the parsing

Every channel got a deterministic regex parser, then a hand-read sample of 30 rows after each
fix round — no model was let loose on the messages. **Precision runs 87–100% by channel, about
95% weighted by volume**; the weakest are the money channel at 87% and the rule-miner at 83%,
so treat the ballot's wording as right and its *completeness* as unproven. Filtering to
high+medium confidence leaves 2,495 of the 3,547 instances.

Two dead ends worth knowing: **premarket-charts has zero level data in text** — 591 posts,
3,980 chart images, not one price typed, and the image links have already expired. And **the
review channels are video indexes** — the reasoning is spoken in roughly 250 YouTube
recordings, never written down.

---

## What happens next

**Agents do these unattended — all measurement, no rule changes, nothing that needs you:**

1. Score engine recall properly against the 1,959 mentor symbol-days and report where it goes
   silent, by symbol and by level.
2. Replay the 851 outcome-bearing instances against bars; publish a per-mentor honesty score.
3. Run the 400-symbol-day pull (3 minutes) so GOOG stops being a hole, then re-run 1 and 2.
4. A/B the two-year book with HOD/LOD turned on, and with the pivot-level count turned down.
   Both are measured levers and both report both sides.
5. Measure ballot line 5 (per-ticker level weighting) as a slice — measuring it changes nothing.

**Nothing from the mentor rulebook gets wired into detection without a yes from you.**

**The one thing only you can decide:** *do these six people's calls count as evidence about
your engine?* If yes, 2,604 dated mentor opinions become labels, and every measurement above
becomes a scoring run against a second panel. If no, this corpus is a 15-line rule ballot and a
level audit, and the trade instances are a curiosity. That single yes/no gates everything else
here, and no agent can answer it for you.

---

## Files

| file | what it is |
|---|---|
| `pooled_trades.jsonl` | the 3,547 instances, deduped across channels, source and author kept |
| `pool_report.md` | how the pooling was done, and every caveat |
| `bar_availability.md` | what has bars, what needs pulling, what can never be pulled |
| `bar_pull_manifest.jsonl` | the 400 symbol-days to pull |
| `mentor_rules.md` | the ballot above, with the agreements and conflicts in full |
| `mentor_rules.jsonl` | all 225 rules, every verbatim restatement, who said it and when |
| `level_grading.md` | the level audit — what humans draw vs what the engine draws |
| `human_levels.jsonl` | 8,550 level mentions, parsed |
| `parse_*.py` | one parser per channel, rerunnable, no arguments, no network |
| `*.jsonl` (per channel) | the raw mined rows behind everything above |

**These are Scarface's and the other mentors' judgements. They are not your marks.** No Austin
mark corpus was opened for writing. Nothing was committed, pushed, or cleaned.
