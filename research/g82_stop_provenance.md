# Where the close-only stop rule actually came from — and the two questions hiding next to it

Austin tonight, pushing back:

> "You said I decided stops on candle closed but I don't think that's correct unless you have
> the metrics, and we should just simplify entries and stops on candle closed. But probably
> not, because when you scale out on trades you don't wait for candle closed... you scale in
> the middle of candles and then you take a look and see where the trade is going. And I think
> a market order is pretty good for that."

Short version, checked against the actual files, not against what CLAUDE.md or PHASES.md
summarized: **the "five times" / "ballot a2, a3, b9" citations are both wrong, but the
underlying rule is not stale — it's real, dated 13 times, and the code has already been
built to test his exact objection.** The genuine gap is not stops. It's that **nobody ever
asked him about scale-out timing**, and the code turns out to already do what he wants there
too.

---

## The three questions, separated

**(a) STOPS** — does a wick through the stop end the trade, or only a close?
**Answer: close-only, ratified repeatedly.** Both engine files already implement it.

**(b) ENTRIES** — does the entry trigger on a close through the level, or intrabar?
**Answer: close, with a stated exception near HOD/LOD that is only partly coded.**

**(c) SCALE-OUTS / TARGETS** — does a profit-take fire intrabar at the price, or wait for a
close? **This is the one question that was never put to him as its own ballot** — and the
code (both files) already fires it intrabar, which is what he's asking for tonight.

---

## (a) Stops — every dated statement, file and quote

CLAUDE.md says "settled this five times in one batch of marks." PHASES.md's "Settled, no
longer open" section says it was ballot **a2, a3, b9**. Both are wrong about the citation,
though not about the conclusion:

- **a2** (`research/rule_ballot_batch02.jsonl` line 2) is about **level respect**, not the
  stop: *"if its closing above the level but still wicking around it its fine, invalidation
  happens as soon as close below or vise versa for calls."* That's whether a **level** counts
  as broken — question (b) below in spirit, not the stop trigger.
- **a3** (same file, line 3) is the same topic: *"has to hold the level or candle period.
  chopping around is not respecting."*
- **b9** (same file, line 17) answers a question about **stop placement**, not the trigger:
  *"its not risk too wide but risk less predictable because i find trends respect candles
  with wicks better."* That's about which candle to put the stop under. It has been quoted
  around this repo as if it settled wick-vs-close triggering. It didn't.

None of those three is actually about whether a wick through the stop ends the trade. That
question has its own, much larger paper trail, already assembled in
**`research/g73_intrabar_stops.md`** (written 2026-08-29, the day before tonight's pushback —
this exact objection has already been raised once and measured). Verified directly against
the mark files for this report (not just trusting the prior write-up):

| when | file | quote |
|---|---|---|
| before 2026-08-11 | `research/recovered_reviews.jsonl` | *"stop a little higher... its a candle close above the stop"* — AMZN 2026-01-14 |
| before 2026-08-11 | `research/recovered_reviews.jsonl` | *"stop loss wouldn't have been stopped out because candle didn't close ab[ove]"* — META 2026-05-05 |
| 2026-08-11 | `research/austin_marks_v7.jsonl` (`batch05_84`, line 343) | *"I dont see the stop out until later, stop out happens when candle CLOSES below the level"* — MSTR 2024-09-26 (verified verbatim against the file for this report) |
| 2026-08-11 | `research/austin_marks_v7.jsonl` (`batch05_84`, line 357) | *"stop outs only happen when candle closes by the way"* — MSTR 2024-03-20 (verified verbatim) |
| 2026-08-11 | `research/austin_marks_v7.jsonl` (`batch05_84`, line 363) | *"stop out would've been 5 candles later because thats when the close below happened"* — MU 2026-02-09 (verified verbatim) |
| 2026-08-11 | `research/austin_marks_v7.jsonl` (`batch05_84`, line 374) | *"your entry never closed below the stop so no need 84 percent rule"* — MSFT 2024-01-25 (verified verbatim) |
| 2026-08-23 | `research/rule_ballot_batch01.jsonl` q1, `stop-close-not-wick` | *"this is correct and needs to be implemented, a 1m candle close below is exit, max slippage -1.25r"* (verified verbatim) |
| 2026-08-23 | `research/rule_ballot_batch01.jsonl` q3, `be-stop-wick-rule` | *"if the structure doesent break you dont want to stop out, thats why you wait for candle closes for stops"* (verified verbatim) |
| 2026-08-28 | (per `g73_intrabar_stops.md`, `research/marks/probe_master_2026-08-29.jsonl` lineage) | *"fix stop out 1.25 max slippage this needs to be fixed now"* |
| 2026-08-29 morning | `research/marks/probe_master_2026-08-29.jsonl` | ratified the two-stop model: **"Level stop on the close, disaster stop on touch"** |
| 2026-08-29 evening | (per `g73_board.md`, shown the disaster order sat at the same price as the level stop) | *"i want it to just be 1k max loss so each loss hits that on average, but whatever increases edge right now which was option 1"* — "option 1" is the close-only rule |

That's at least 8 dated statements in the one 2026-08-11 sitting alone (`g73_intrabar_stops.md`
counts 8; four of the eight are quoted above, verified against the raw file), plus the
pre-08-11 recovered reviews, plus the two 2026-08-23 ballot answers, plus the 2026-08-29
ratification — **more than "five," and not the three ballots PHASES.md names.**

**Why he doesn't remember agreeing, and why tonight's sentence isn't new:** `g73_intrabar_stops.md`
already diagnosed this exact reaction one day ago. The morning of 2026-08-29 he ratified
*"level stop on the close, disaster stop on touch."* But the disaster stop's resting distance
(`DISASTER_STOP_R` in `stop_rule.py:125`) is **1.0**× the original risk — i.e. it sits at
**the same price as the level stop**, not further out. So every ordinary loss in the book
already gets stopped on an intrabar touch, because the disaster order fires before the close
can. He is looking at a book that already behaves the way he's describing tonight, and
correctly sensing it doesn't match the "candle close" rule he stated — the fix g73 proposed
(move `DISASTER_STOP_R` out, e.g. to 2.5) was never applied; `DISASTER_STOP_R = 1.0` is still
the shipped default as of this read (`stop_rule.py:125`).

### What the code does today

- `backtest_week.py:409-418` (`_stop_hit`) — close-triggered by default (`STOP_ON_CLOSE`,
  default `"1"`, set at `backtest_week.py:186`). Wick-triggered only if `STOP_ON_CLOSE=0`
  (`_wick_hit`, `backtest_week.py:403-406`, kept only for the old A/B).
- `backtest_week.py:421-429` (`_stop_fill_px`) — fills at that close, floored at −1.25R via
  the shared `stop_rule.stop_fill_price`.
- `backtest_week.py:198-216` — the **disaster stop**, a second, independent resting order at
  entry ± `DISASTER_STOP_R` × risk, filled on an intrabar touch (`disaster_stop_hit`,
  imported from `stop_rule.py`), tested **before** the level stop on every bar
  (`backtest_week.py:608`, `_ladder_bar`). This is the order that makes the book intrabar in
  practice even though the level stop itself is close-only.
- `backtest_week.py:218-244` — a **`STOP_ARM`** scaffold already exists (`""`, `close_floor`,
  `close_nofloor`, `touch`, `touch_floor`) explicitly built for "research/g82_stop_ab.py" (the
  next ticket number after this one) with the comment: *"Austin, on the close-only stop rule:
  it stands 'if you have the metrics.' Nobody had run the plain A/B."* **That script does not
  exist yet** — only the flag scaffold does (`ls research/g82*` finds nothing else). The A/B
  he's asking for tonight is teed up but not run.
- `paper_trader.py:212-220` (`_check_stop`) — close-triggered, same shared `stop_rule` predicate.
  The module docstring (`paper_trader.py:17-22`) states it was **wick-triggered and mismarking
  every paper position until G11** — fixed 2026-08-28. `DIRECTION.md`'s claim that
  "paper_trader.py marks on wicks" is **stale**; that gap was closed and the header now says so.

---

## (b) Entries — close, with a coded exception near HOD/LOD that is only partly built

Two ballot answers, both "tweak," not "yes":

- `research/rule_ballot_batch01.jsonl` q7, `entry-is-bar-close`: *"we miss out on entries that
  are near HOD, because they close too high for our entry risk to reward... if bot knows its on
  watch waiting to see how the candle closes"* (tweak, not a clean ratification).
- `research/rule_ballot_batch01.jsonl` q8, `intrabar-exception`: *"not understanding. if your
  on that waiting for strong PA and theres a level there, you want it to be probable of closing
  above that level. dont just enter when it taps a level"* — this one pushes **against** a pure
  intrabar entry.
- `research/rule_ballot_batch02.jsonl` b3, `entry-timing-close-vs-intrabar`, answer
  `close-except-near-hod`: *"most entries work at candle close, but some that are close to hod,
  you want to get a good fill and not one that will have bad RR, thats what we are working on
  coding"* — this is the actual settled reading: **close by default, with an explicit,
  acknowledged HOD/LOD exception.**
- Separately, the rulebook records repeated marks like *"as candle forming not lod"* /
  *"not HOD"* (CRM 2026-02-11, HOOD 2024-11-06, MSFT 2025-03-13, AMZN 2025-09-10) which he later
  clarified belongs to **ON WATCH and mid-candle entries specifically**, not a general override
  of close-based entry.

### What the code does today

`backtest_week.py:274-280` states the mechanism directly: *"this engine is bar-CLOSE driven.
It cannot take an entry 'intrabar' in the sense Austin means: it decides at the close of bar
i, and fill_price() only back-dates the PRICE to the level."* Concretely, `detect_break_retest`
requires the entry bar to **close** through the retested level (`current.close > block.high`
for the order block form, `close >= entry_price` for the 84% reclaim — comment at
`backtest_week.py:269-270`). The ON WATCH mid-candle mechanism Austin is describing exists as a
separate flag (`ON_WATCH`, gated elsewhere) that back-dates the *fill price* to the level once
the close-based decision fires — it does not move the decision itself off the close. So: the
code matches ballot b3's settled reading (close-based entries) but the "as candle forming"
exception is implemented as a price back-date, not as an actual earlier decision point — this
is the one place where the code's mechanism and his stated exception don't fully line up, and
it predates tonight's conversation.

---

## (c) Scale-outs / targets — never asked as its own ballot, and the code already does what he wants

No ballot, no mark, and no ratified sentence in any of the corpora searched (`austin_marks_v7`,
`blind_marks_all`, `recovered_reviews`, `marks_clean`, both rule-ballot batches) settles
whether a profit-take/scale-out fires intrabar or waits for a close. This is a genuine gap —
not a case of him forgetting something he said, because there's nothing to forget here.

**But the code was already built the way he's asking for tonight, and it says so in its own
comments** — this is the part worth leading with:

`backtest_week.py:246-258`:
> "Austin believes a profit target fills the moment price TOUCHES it (a resting limit order)
> and suspects the code may instead require a candle to CLOSE through it. **It does not — every
> profit leg here is an intrabar touch and always has been** (`_target_hit` below, and the three
> call sites it replaced). `TARGET_ON_CLOSE=1` builds the arm he was worried about so the belief
> is measured instead of asserted. Default 0 = touch = shipped, byte-identical. It governs all
> three profit legs together — the blind-2R target, the ladder's PT1 scale rung, and the runner
> target."

Confirmed at the call sites:

- `backtest_week.py:632` — the F1 ladder's scale rung: `if (c.high >= t.scale_level) if long
  else (c.low <= t.scale_level)` — wick/touch, not close.
- `paper_trader.py:222-234` (`_check_target`) — `if high >= self.stock_target` / `low <=
  self.stock_target` — touch, docstring says *"a target is a resting limit order and fills on
  any intrabar touch."*
- `paper_trader.py:236-251` (`_check_breakeven`) — the Rule 6 breakeven scale, same touch logic,
  docstring: *"the Rule 6 scale is a limit order sitting at +1R, not a stop."*

**Only the runner's raised stop is close-based** (`paper_trader.py:241`, `backtest_week.py:604`
via `runner_stop`) — that's still question (a), not (c).

So: his statement tonight — *"when you scale out on trades you don't wait for candle closed...
a market order is pretty good for that"* — describes the code as it already runs. There is
nothing to fix here. `TARGET_ON_CLOSE` exists specifically to prove that if anyone doubts it.

---

## The headline

**Stops are close-only and it's real — 8+ dated statements in one 2026-08-11 sitting alone,
plus pre-08-11 marks, plus two 2026-08-23 ballot answers, plus the 2026-08-29 morning
ratification. Neither CLAUDE.md's "five times" nor PHASES.md's "ballot a2, a3, b9" cites the
right evidence, but the rule itself is not stale.** What makes the book *feel* intrabar to him
is the disaster stop sitting at the same price as the level stop (`DISASTER_STOP_R = 1.0`,
`stop_rule.py:125`) — a decision `g73_intrabar_stops.md` flagged and recommended widening
2026-08-29, still unapplied.

**Entries are close-based with an acknowledged, only-partly-coded exception near HOD/LOD.**

**Scale-outs/targets are already intrabar in both `backtest_week.py` and `paper_trader.py`, and
the code comments show someone already anticipated this exact question and built a flag
(`TARGET_ON_CLOSE`) to prove it.** Nothing needs to change here; it may just need to be shown
to him.

## What was not done

- No backtest was run — this was reading and grepping only, as asked.
- The `research/g82_stop_ab.py` A/B the `STOP_ARM` scaffold was built for does not exist yet —
  that's the natural next ticket if he wants the disaster-stop-distance question measured.
- Every corpus quoted above was opened read-only. Nothing in `research/marks/`,
  `austin_marks_v7.jsonl`, `blind_marks_all.jsonl`, `recovered_reviews.jsonl`,
  `marks_clean.jsonl`, or either rule-ballot batch was modified.
