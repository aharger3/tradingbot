# T3 — the 84% rule, rewritten from the source

script: `signal_runner.py` (the rewrite), `research/test_rule84_source.py` (selftest),
`research/t3_spy1216_case.py` (the flagged live instance), `research/
t3_backtest_compare.py` (the 2-year error bars), `backtest_2y.py` (the 2-year
arm), `research/t0_heldout_recall.py` (recall). commit `_this commit_`

Austin: *"Please watch an 84 percent rule YouTube video from Scarface to fix and
implement this rule and the codebase."* And, in the same probe answer: *"84 percent
rule needs a reclaim and enters when that happens with same stop unless a new stop
makes more sense."* (`research/marks/probe_master_2026-08-29.jsonl`, `card_id:
fact_rule84_arm_setups`.)

## What was watched

Nothing needed fresh ingestion. The corpus already holds a verbatim transcript of
the exact lesson Austin is describing — `research/scarface-rules-videos.md`,
`boot-camp-recordings_Day_5_Every_Setup.txt`, section "3. 84% Rule / Re-entries"
(source timestamps `[7438s-8851s]`) — corroborated by 84 more verbatim quotes across
the accelerator course, the mastermind calls, 12 raw YouTube transcripts and four
Discord channels in `research/84rule-sizing-dossier.md`. `python
research/corpus_query.py "84 rule reclaim" --top 15` surfaces both as the top
`TRADER_SAID` hits. This report rewrites the rule against those, not against the
code that already exists.

## What the source actually teaches

> "If price stops you out on a trade and the same trade presents itself again, you
> can take the same original trade a second time using the original stop and
> targets and it'll work out 84% of the time." — Day 5 Every Setup, 7751s-7764s

> "There does not need to be a pattern on the second entry so this is key... A lot
> of people will be like you need to wait for a retest. No, it's a reclaim entry...
> And it says a reclaim of a key level. There does not need to be a pattern." —
> 7781s-7801s

> "Our signal really the only thing is a strong confirmation if it closes above we
> can be looking for the reclaim for a continuation higher." — 7801s-7807s

> "A lot of people think they're taking 84% rules, but if you take... a proper
> break and retest... take the second setup thinking it's invalid and 84% rule
> you're gonna lose again because essentially you're taking an improper initial
> setup." — 8475s-8485s

> "Now I'm primarily gonna be holding for my original target which may it might be
> like a previous day high or some sort of higher time frame objective... So
> instead instead of selling at highday, now I'm gonna be looking for my main
> target." — 8317s-8325s

> "If 84% rule fails, it's a very good chance that it's choppy and you would be
> very cautious." — 8068s-8072s

Five load-bearing facts, all agreed across the accelerator, the mastermind calls
and the free YouTube content (`research/84rule-sizing-dossier.md` section 6):

1. Re-entry only after a real stop-out on a real (proper) first setup.
2. The reclaim itself has **no pattern requirement** — a strong CLOSE through the
   key level is the whole signal.
3. **Same stop, same target as the original trade**, by default.
4. Hold for the ORIGINAL target, not HOD/LOD.
5. One re-entry per failed idea (the corpus's own community members count "84% of
   84%" as a joke about a *third* attempt, i.e. two is the norm).

Sizing (same-size vs. size-up) is contradictory across sources and is R10/R32
territory, not this track. Which setups may arm the rule at all is R6 (already
`any`, landed) and T-84/C9/P7 territory, not this track either.

## The gap: three things the shipped reclaim clause does that the source doesn't ask for

`signal_runner.py`'s reclaim blocks (`~2553` long / `~2794` short before this
change) implement facts 1, 3 (as "same stop", unconditionally) and 4 correctly.
They also do three things the source never asks for:

| # | shipped code | source |
|---|---|---|
| A | requires `current.is_bullish` (call) / `is_bearish` (put) on the reclaim candle | "there does not need to be a pattern" |
| B | requires the remaining reward be ≥1.5× the remaining risk (`rr_ok`) | not mentioned anywhere in 85 quotes |
| C | vetoes a reclaim within 20% of the day's range from HOD/LOD | not mentioned anywhere in 85 quotes |

And one thing the source asks for that the code never implemented:

| # | source | shipped code |
|---|---|---|
| D | "same stop **unless a new stop makes more sense**" | `RULE84_LESSON=True` used the original stop **unconditionally** — the qualifier was never read |

(A) and (B)/(C) have no citation in the code either — the nearest comments read
"2026-07-10: remaining reward must still be >=1.5x risk at re-entry" and "Skip if
close near high of day" with no source named, which is exactly the failure mode
`research/test_published_numbers.py` and `research/test_provenance.py` exist to
catch for numbers; the same discipline applies to rules.

## The rewrite: `RULE84_SOURCE`

`signal_runner.py`, flag-gated, **default OFF** (unvalidated, same convention as
every other `RULE84_*` flag in this file — `RULE84_STRICT`, `RULE84_ARM_SGRADE`,
`RULE84_ARM_NOGATE`). When ON, at both reclaim blocks:

- (A) dropped: the entry gate no longer requires `is_bullish`/`is_bearish`.
- (B) and (C) dropped: no RR floor, no HOD/LOD-proximity veto.
- (D) implemented: `rule84_source_stop(original_stop, candle, entry, is_long)` —
  keeps the original stop **unless** the reclaim bar's own extreme is BOTH tighter
  (less risk) and still valid (on the losing side of the fill), in which case that
  tighter extreme is used. A wider natural extreme never overrides the original —
  "makes more sense" is read as *less risk for the same setup*, never more.

Facts 1, 4 and 5 (real stop-out required, original target held, one re-entry) were
already correct and are untouched.

`research/test_rule84_source.py` (18 checks, all passing) pins all four changes
down, plus one boundary proven directly rather than assumed:

**"No pattern" lands at the entry gate but is not sufficient alone.** A doji or
red-bodied reclaim now reaches the router under `RULE84_SOURCE=1` (it did not
before), but it still grades X and never reaches the traded book, because
`PriceActionAnalyzer._grade_pa` (`omen_bot.py`) — the ONE shared price-action
grader every setup type in this engine routes through, not an 84%-specific one —
carries its own unconditional `if not candle.is_bullish: return TradeGrade.D`
ahead of any pattern check. That gate is logically identical to the one this track
removed, so for a non-bullish reclaim the two are provably a no-op together. Making
the pattern-free reclaim Austin describes reachable end-to-end needs `_grade_pa`
relaxed too — that is **T13/R19** ("not just hammers lol"), a change to shared
infrastructure well outside this track's blast radius, not a gap in this rewrite.
(B) and (D) are not affected by this boundary — they change the traded book on
their own, proven in the 2-year arm below.

## The test case: SPY 2024-12-16

Austin flagged this live: *"10:07 84 percent happens btw"* (`research/marks/
probe_master_2026-08-29.jsonl`, `card_id: SPY_2024-12-16`, lane `index`).

The engine's own candidate original entry that day is a break-and-retest above
OR-high/PMH ($606.39-606.40, both equal to the actual archived opening-range high
and premarket high — `data_archive/SPY/2024-12-16.csv`), taken at 10:05. It never
closes back below its stop through the rest of the session — the 10:06 bar only
*wicks* to $606.275 (close $606.41) — so under the close-only level stop it is
never "stopped out" at all. It IS stopped by the **disaster stop** (R1/R2,
`DISASTER_STOP_R = 1.0`, `stop_rule.py:125`): at `DISASTER_STOP_R=1.0` the resting
order sits exactly at the level stop's price, and a resting stop fills on TOUCH —
the $606.275 wick trips it. This is exactly the mechanism T0's `austin_blocker`
named: a real trader's resting stop gets hit by a wick the backtest's close-based
level stop does not register. The candle closes back above $606.39-606.40 at
**10:07** — the bar Austin named.

`python research/t3_spy1216_case.py --show-day` prints the six lines above
directly from the engine. `python research/t3_spy1216_case.py` arms the
session via the real `backtest_week._arm_84` codepath off that exact original
trade (entry $606.39, stop $606.38, the engine's own numbers) at the exact bar
it loses (10:06, disaster-stop touch), then replays forward:

| arm | fires at 10:07? |
|---|---|
| shipped default (`RULE84_SOURCE=0`) | **no** — blocked by the RR floor: the tiny 2R fallback target ($606.41) is already exceeded by the reclaim close ($606.48), so remaining reward is negative |
| T3 rewrite (`RULE84_SOURCE=1`) | **yes** — `10:07:00, entry=606.39, stop=606.38 (Original stop), target=606.41` |

The rewritten rule fires exactly on Austin's flagged instance; the shipped rule's
own unsourced RR floor is what was silencing it.

**Caveat, stated plainly:** in the FULL shipped pipeline (not this isolated
harness), SPY 2024-12-16 still produces zero 84%-rule fires end to end, because the
original 10:05 setup itself grades X under `PriceActionAnalyzer._grade_pa`'s
price-action-strength test ("X PA", weak retest) and so is never `counted`/`fired`
— it never reaches `_arm_84`'s `if t.counted and setup_ok:` gate regardless of the
reclaim rule. That grading question is the SAME shared-grader boundary named above
(T13/R19), and toggling `BNR_DISPLACEMENT_GATE` does not change the result (checked
directly — grade X persists with the gate off, so a different PA-quality check is
what's failing it, not the displacement gate). Austin's flagged instance is real
and the rewritten rule is proven to handle it correctly the moment a valid original
trade is on file; the reason nothing fires TODAY on that specific day is an
upstream grading gate this track does not own.

## The 2-year book

    python backtest_2y.py --out research/t3_scratch/bt2y_baseline.json                       # shipped default
    RULE84_SOURCE=1 python backtest_2y.py --out research/t3_scratch/bt2y_source.json          # T3 rewrite
    python research/t3_backtest_compare.py research/t3_scratch/bt2y_baseline.json research/t3_scratch/bt2y_source.json

Same window both arms: 29 symbols, 500 sessions, 2024-08-27..2026-08-28.

**The "today's 3 signals" figure this track was handed does not match a fresh
run on `t0-ratified`.** Measured here — freshly, on the branch this track was
told to rebase onto — the shipped default (`RULE84_SOURCE=0`, no other flag
set) already produces **315 reentry_84_rule signals, 312 traded, in 500
sessions**, not 3. This is not a bug introduced by this track: the regression
gate and a direct code read both confirm the flag-off path is byte-identical
to what shipped before this commit (see Regression gate, below), and the
number reproduces `research/t0_heldout_recall.py`'s own held-out figures
exactly. The "3 re-entries in two years" line lives in a comment written
*while* R6 was landing, in the same commit series as eleven other gates T0
also removed — `NO_REPEAT_ENTRIES` off, `S_PLUS_PER_DAY` deleted,
`LEVEL_RETIRE_TOUCHES` deleted, the OCR B→C demote lifted — every one of
which independently widens how many stop-outs ever become `counted` and
therefore eligible to arm the rule. The comment describes an intermediate
point inside that series, not the fully-landed book this track measures
against. Treat 312, not 3, as today's baseline.

| | shipped default | T3 rewrite | move | 95% error bar | inside bar? |
|---|---:|---:|---:|---:|---|
| 84-rule signals detected | 315 | 798 | +483 | — | — |
| 84-rule signals **traded** | 312 | 764 | +452 | — | — |
| 84-rule slice mean R | +0.1908R | +1.0687R | **+0.8779R** | ±0.6158R | **no** |
| 84-rule slice win rate | 29.5% | 32.3% | +2.8pp | — | — |
| whole-book traded n | 2,548 | 3,000 | +452 | — | — |
| **whole-book mean R** | **+0.5378R** | **+0.7091R** | **+0.1713R** | **±0.1861R** | **yes** |

**Null result: at the whole-book level, the move is inside its own error
bar** (+0.1713R against a ±0.1861R 95% bar) — the same "moved less than the
noise floor" pattern every single-lever A/B in this project has hit. The
84-rule SLICE's own effect is real (+0.8779R against a ±0.6158R bar, clears
it), which makes sense mechanically: the rewrite adds 452 new traded signals
at a slice mean (+1.07R) well above the book's own mean, which necessarily
drags the whole-book average up — but 452 rows out of a ~2,550-row book is not
enough to move the WHOLE book's mean outside its own noise floor. Both
readings are true at once and neither is cherry-picked over the other.

**The raw slice mean is outlier-sensitive; report it alongside robustness
readings, not instead of them.** `stop_pct: "tight"` original stops (a few
cents wide, common on B&R/OCR retests with a tight range) combined with
"same stop by default" plus "hold for the ORIGINAL target" (fact 3+4, both
correctly source-faithful) occasionally produce enormous R multiples — e.g.
AMD 2025-11-07 10:23, entry $231.05, stop $231.07 (2 cents = 0.009% risk),
exit $227.00 → **187.5R** on one trade. This is not a bug this track
introduced: the SAME artifact already exists in the shipped baseline (2 rows
>10R, up to 11.25R) — T3's wider funnel just produces more chances to hit it
(19 rows >10R of 764, vs. 2 of 312). Robustness readings, same two books:

| | shipped default | T3 rewrite |
|---|---:|---:|
| median R | -1.0000 | -1.0000 |
| 5%-trimmed mean R | -0.0640R | +0.2105R |
| mean R, capped at 20R/trade | +0.1908R | +0.7332R |

Even fully discounting the outliers (trimmed mean, or a hard 20R cap), the
rewrite still reads meaningfully better than the shipped default on this
slice (+0.27R trimmed, +0.54R capped) — the improvement is not purely an
artifact of a handful of tiny-risk trades, but its exact size is. **This is
the same open question R32 already named** ("flat $1,000 planned loss...
separately test sizing for grade and for the 84% rule") — a naive
$1,000-sized-to-the-stop position on a 2-cent stop is not a real, fillable
options trade, and no sizing model has been applied to any of these numbers
(same caveat T0 and every other track in this spec carries: everything here
is the underlying in R, not a contract).

## Held-out recall

Scored against `research/marks/probe_s_sweep_2026-08-28.jsonl` (34 held-out
S) and `research/marks/probe_master_2026-08-29.jsonl` lane `vetoes` (his 40
S/A/C/no verdicts), via `research/t0_heldout_recall.py` — the same harness
and the same two sets T0 and every other track score against, so the numbers
are directly comparable, not a second definition of recall.

    python research/t0_heldout_recall.py --out research/t3_scratch/heldout_baseline.json
    RULE84_SOURCE=1 python research/t0_heldout_recall.py --out research/t3_scratch/heldout_source.json

| | shipped default | T3 rewrite | move |
|---|---:|---:|---:|
| sweep recall (34 held-out S) | 18/34 = 52.9% | 18/34 = 52.9% | **0** |
| sweep precision | 36.0% | 36.0% | 0 |
| his S recalled (vetoes, n=5) | 0/5 | 0/5 | 0 |
| his A recalled (vetoes, n=4) | 0/4 | 0/4 | 0 |
| false fires on his 27 "no" | 2 (7.4%) | 2 (7.4%) | 0 |

**Recall does not move, card for card — the identical 16 S cards are missed
both ways.** This track adds signal volume and (on its own slice) mean R, but
it does not touch recall: every held-out S the engine was already going to
miss, it still misses; every one it already caught, it still catches. This
matches T0's own finding on the ratified table as a whole ("held-out S
recall does not move at all... same 16 misses card for card") — the 84% rule
is a small, late-session re-entry surface layered on top of whatever the
primary detectors (B&R, OCR) already found or missed earlier in the day, and
none of the 16 missed cards had an armable 84% setup on file.

## Regression gate

`python research/regression_gate.py` — PASS with the flag at its shipped default
(OFF): any_signal 75→80 (+5, unrelated to this track — carried from T0's landed
book), s_grade 5→5, no baseline-fired mark went silent.
`python research/test_rule84_source.py` — 18/18 checks pass.
Existing 84%-rule tests unaffected: `test_no_repeat.py`, `research/
test_confluence_setup.py`, `research/test_onwatch_fill.py`, `research/
test_w12_grade_gates.py` all still pass with the flag at its default.

## Recommendation

**Ship `RULE84_SOURCE` OFF (default), do not flip it live yet.** The rewrite is
correctly source-faithful — three of four fixes are proven with a fresh,
provable regression-test boundary (`research/test_rule84_source.py`, 18/18),
and the fourth (SPY 2024-12-16) is proven to fire on Austin's own flagged
instance the moment a valid original trade is on file. But:

1. Held-out recall — the metric method rule 2 says governs — does not move.
2. The whole-book mean-R effect is a **null result** (inside its own bar).
3. The one effect that IS real (the slice's own mean R) is partly an
   artifact of tiny-risk original stops producing triple-digit R multiples
   that R32 already flagged as needing separate sizing treatment — the
   number is not safe to plan around until that's resolved.
4. "No pattern needed" (fact 2) is landed at the entry gate but proven inert
   today: `PriceActionAnalyzer._grade_pa`'s own unconditional bullish/bearish
   gate absorbs it. It becomes consequential only once T13/R19 relaxes that
   shared grader — worth knowing before anyone reads this rewrite as "the
   84% rule is now pattern-free" in the traded book, because it is not, yet.

What IS settled and safe to carry forward regardless of the flag decision:
the "same stop unless a new stop makes more sense" qualifier (fact 3) was
never implemented before this track, and now is, with a literal, provable
reading of "makes more sense" (tighter and still valid). That gap existed
independent of everything else in this report and is now closed.

**austin_blocker:** Watch the AMD 2025-11-07 84% re-entry (10:23, entry
$231.05, stop $231.07, exit $227.00, booked as 187.5R on a naive $1,000-per-R
sizing) and answer one concrete question: *should the 84% rule's re-entry
carry the same no-minimum-stop-distance policy R4 gave the one-candle rule
("no minimum stop distance on OCR, size to the stop"), or does a stop this
tight need a floor before the 84% rule ships live?* Both readings are
defensible from his own words and only he can pick — R4 is about a different
setup type and does not, on its own text, decide this one.
