# L4 referee — `TREND_DEF=structure15`

**Builder's commits:** `355d7cc0` (flag lands OFF) and **`f81db426`** (the held result,
the report `research/l4_trend_def.md`, both stamped books, the cycle ledger).
**Referee script:** `research/l4_referee.py` (this file's every number comes out of it;
it re-implements the unit, the monthly bucketing, the `$/day` denominators and the gate
from their written definitions rather than importing `research/loop_cycle.py`, so a bug
in the builder's rig cannot reproduce itself in the check).

## Verdict: **upheld on the decision and on every number — three defects in the report**

The hold is right, the arithmetic reproduces to the dollar, the flag means what the call
settled, and the default matches the decision. What does **not** survive is the report's
explanation of *why* the book moved, and its handling of two sample-size questions.

---

## What reproduced exactly

Unit `up_to_3_stop_win_or_2loss`, `tier == "core"` (CORE_SYMBOLS, 11 names), **close fill**
(`entry_fill.ENTRY_FILL="close"`), **shipped engine exit** (1R hard stop resting on the level,
intrabar-touch fill, `SCALE_PLAN=hod_then_runner_be`, two-loss account halt on), 499 sessions
2024-09-04 → 2026-09-04. Script: `research/l4_referee.py`.

| slice | n_days | arm | trades | total $ | $/day | mean R | win% | avg win | avg loss | W/L | green |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| whole | 499 | OFF | 769 | −25,746 | **−52** | −0.0335 | 45.0 | 801 | 716 | 1.119 | **11/25** |
| whole | 499 | ON | 768 | −30,384 | **−61** | −0.0396 | 45.2 | 780 | 715 | 1.091 | **10/25** |
| H1 | 248 | OFF | 382 | +2,191 | **+9** | +0.0057 | 43.7 | 917 | 701 | 1.308 | **6/12** |
| H1 | 248 | ON | 381 | −7,559 | **−30** | −0.0198 | 43.5 | 863 | 701 | 1.232 | **5/12** |
| H2 | 251 | OFF | 387 | −27,937 | **−111** | −0.0722 | 46.3 | 694 | 732 | 0.949 | **5/13** |
| H2 | 251 | ON | 387 | −22,825 | **−91** | −0.0590 | 46.8 | 704 | 729 | 0.965 | **5/13** |

Gate, re-derived: **H1 fails** (green 6 → 5, and $9 → −$30 is a fall, not a ≤5% one).
**H2 passes** (green 5 → 5, −$111 → −$91 is an improvement). **Decision = hold.**
Identical to the builder's, identical to `research/tape/cycles.md`'s row and to
`research/tape/loop_state.json` cycle 4.

Both halves clear the 30-trade / 12-month floor on the BEFORE side (382 trades / 12 months,
387 trades / 13 months), so the halves themselves are not "not enough" — see defect 3 for
why that is nevertheless not the whole story.

## Stamps and hygiene — all clean

- OFF book `book_id` = **`2c39ced2697c26cc`** = `research/tape/baseline_2026-09-05.json.gz`'s
  and = `research/tape/loop.json`'s `baseline_book_id`. The flag landing OFF really is
  byte-identical to the baseline.
- OFF vs ON stamp flag dicts differ in **exactly one key**:
  `signal_runner.TREND_DEF: "off" → "structure15"`. Nothing else moved.
- Both built at commit `355d7cc0` (an ancestor of the row's commit `f81db426`),
  `dirty_engine_py: []`, `dirty_py_count: 0`, same window `2024-09-04..2026-09-04`,
  499 sessions, built 3½ minutes apart on the same day.
- `TREND_DEF` is present in `research/book_stamp.py` `FLAG_SOURCES` and appears in both
  stamps.
- **Default in code is `"off"`**, which matches the `hold` decision. A research arm never
  defaults on.
- **One change per row:** `git show --stat 355d7cc0` = `signal_runner.py` + `research/book_stamp.py`
  (the flag and its stamp entry); `git show --stat f81db426` = the report, two books,
  `cycles.md`, `loop_state.json`. No second behaviour change rides along.
- **No mark file touched** in either commit (`git show --name-only` over both, filtered for
  every corpus named in CLAUDE.md's "THE ONE RULE": none).
- **Verify gate green at `f81db426`, run by me:** `regression_gate.py` PASS (no baseline-fired
  mark went silent), `test_runner_stop.py` ok (70 checks), `test_universe_single_source.py`
  ok (29 symbols, no private lists).
- The **ntfy push line is plain English**: *"cycle 4: the 15-minute structure trend test —
  held. $/day −52.0 → −61.0, green months 11 → 10"* — no flag name, no ticket id.
- The pre-commit repair of the duplicate cycle-5 row is genuine: the duplicate never entered
  git. `git show f81db426 -- research/tape/cycles.md` adds exactly one data row plus the
  repair comment, and `loop_state.json` goes 3 → 4, `consecutive_holds` 3 → 4, `stop` false.

## Semantics — the flag does what the call settled

`research/omen_recall.py "trend 15-minute structure higher highs higher lows direction"`
returns, verbatim:

> **trend** — *"15-minute structure (higher highs / higher lows, or the reverse) on the 1m
> chart — no indicator"* (`omen-10-0-spec.md`, "What the call settled"; and
> `omen-rulebook.md`, Decided 2026-09-05: *"trend = 15-minute structure (HH/HL) on the 1m
> chart."*)

and the spec's Phase-L row: *"**L4 — trend = 15-min structure** for the OCR/84% direction
test (`TREND_DEF=structure15`). Report how many signals flip direction-eligibility."*

`signal_runner.structure15_trend` aggregates the 1-minute candles into consecutive
15-candle buckets and calls a higher-high-**and**-higher-low `bullish`, a lower-high-**and**-
lower-low `bearish`, anything else `None`. I exercised the function directly (section 0 of
`research/l4_referee.py`): 29 bars → `None`, 30 rising → `bullish`, 30 falling → `bearish`,
flat → `None`, empty → `None`, and the trailing-partial-bucket rule confirmed (44 bars where
the last 14 collapse still reads `bullish`; at 45 the completed bucket flips it `bearish`).
`_trend_ok` is a hard `return True` unless `TREND_DEF == "structure15"`, and a `return True`
on `None`.

Two things I checked because they would have made this "adjacent to the rule" rather than
the rule:

- **Bucket alignment.** `backtest_week`'s loader keeps RTH bars only (pre-09:30 rows go into
  a separate premarket high/low bucket and are dropped from the candle list), so `candles[0]`
  is the 09:30 bar and the 15-candle buckets *are* clock-aligned 15-minute bars: 09:30–09:44,
  09:45–09:59, 10:00–10:14. This is a real 15-minute chart, not an off-grid rolling window.
- **Look-ahead.** `_route` sees `candles[:i+1]` and `structure15_trend` reads nothing else.
  When the bar count is an exact multiple of 15 the newest bucket ends on the signal bar,
  which has already closed. Clean.

One interpretive note, not a defect: "higher highs / higher lows" in trader language usually
means a *swing* sequence; this is a two-bar comparison with no memory and can flip every 15
minutes. The call gave no more detail than the sentence above and said "no indicator", so the
minimal literal reading is defensible — but it is a choice the report should have named.

## Defect 1 — the report's causal sentence is false

`research/l4_trend_def.md` says:

> *"the mechanism is not 'worse trades kept,' it's dedupe-release."*

It is not dedupe-release. I attributed the whole −$4,639 unit move row by row
(`research/l4_referee.py` sections 8 and 9):

| where the unit's $4,639 went | rows | pnl |
|---|---:|---:|
| unit rows present only in OFF | 3 | +7,750 |
| unit rows present only in ON | 2 | +3,111 |
| unit rows shared by both books | 764 | −33,496 (identical in both arms) |
| of the only-in-ON rows: **brand-new fires (dedupe-release)** | **0** | **0** |

**Zero** dedupe-released rows reach the unit. Every changed row is a row that fires in both
books and that the up-to-3 day walk reaches in one arm and not the other. The 4 new-only-in-ON
84%-rule fires the report points at are real, but not one of them is traded into the unit.

The actual mechanism is narrower and much more interesting: **three days move, and one of
them is the whole result.**

| day | OFF day pnl | ON day pnl | delta | what changed |
|---|---:|---:|---:|---|
| 2024-10-25 | +9,732 | −18 | **−9,750** | the gate removed two SPY one-candle-rule puts; the 10:30 one was **+$9,750** and the day walk had taken it |
| 2025-11-05 | −2,000 | +58 | +2,058 | the gate removed an NVDA OCR put (−$1,000), so the walk reached a +$1,058 MSFT break-and-retest instead |
| 2026-02-24 | −1,180 | +1,874 | +3,053 | the gate removed an AMZN OCR put (−$1,000), so the walk reached a +$2,053 NVDA break-and-retest instead |

−9,750 + 2,058 + 3,053 = **−4,639**, the entire whole-window move, to the dollar.

## Defect 2 — a verdict on an n=27 cell

The report's flip table prints the flipped-and-traded one-candle-rule set as
**−0.1219R (n=27)** with no "not enough" label, and the prose then draws a conclusion from
it: *"Both flipped-and-traded means are negative — the gate is removing losing trades on
average."* 27 < 30. Under SWARM.md law 3 that cell gets the count and the interval and the
words "not enough", and no verdict. (The n=3 84%-rule cell *is* correctly labelled, which
makes the omission on the n=27 one look like an oversight rather than a policy.)

My own recount of the flips agrees with the builder's numbers and adds a row the report
dropped:

| setup | fired OFF | fired ON | lost (OFF only) | gained (ON only) | of the lost, traded | mean r of those |
|---|---:|---:|---:|---:|---:|---:|
| one_candle_rule | 259 | 186 | **73** | 0 | 27 | −0.1219 — **n<30, not enough** |
| reentry_84_rule | 53 | 39 | **18** | **4** | 3 | −0.3947 — **n=3, not enough** |
| break_and_retest | 4,329 | 4,332 | **5** | **8** | 2 | +0.1675 — **n=2, not enough** |

The report says its table counts *"exactly the population the new `_trend_ok` gate can
remove"*. It does not: **5 break-and-retest rows disappear and 8 appear**, at a setup the
gate never touches. That is real dedupe-release collateral, and it is the row the report
should have used to make its release argument — it just does not reach the traded unit.

## Defect 3 — "a real verdict, not 'not enough'" understates how thin this is

The report says, correctly under the letter of the rule, that both halves clear the
30-trade / 12-month floor and so this is a real verdict. But the *difference* between the
arms is five rows on three days, and the H1 green-month fail — the thing that decides the
whole gate — is **one month, and inside it one trade**:

| month | OFF | ON | |
|---|---:|---:|---|
| 2024-10 | **+$5,047 (green)** | **−$4,703 (red)** | the only month that flips; 11 → 10 green, and inside H1, 6 → 5 |

Remove that single 2024-10-25 SPY one-candle-rule put (+$9,750) and October 2024 stays green,
H1's green count does not fall, and H1's dollar column goes from +$9 to roughly break-even
rather than −$30. Two further points the report should have carried:

- That +$9,750 row has `status: "halted"` — the shipped engine's account-wide two-loss halt
  blocked it. The unit re-admits halted rows by design (a halt the unit's own stop rule would
  not have reached yet must not erase the rest of the day), so this is baseline behaviour, not
  an L4 bug. But it means the trade deciding this row's verdict is a counterfactual the live
  engine never took.
- The move is **inside the project's own ±1.58R error bar**, which the report does say for
  the dollar column — but it then treats the green-month column as decisive without noting
  that it too rests on the same single row.

**Effect on the decision: none.** Hold is the conservative outcome and hold is correct: a
change that cannot be shown to help stays behind its flag, OFF. But the loop ledger should
not read this as evidence that the 15-minute trend gate *hurts*. It reads as **undetermined**,
decided by one trade.

## Two facts about the gate's reach that the report does not mention

Neither changes the verdict; both matter to whoever proposes L4's successor.

- **The gate is blind before 09:59.** `structure15_trend` needs two completed 15-candle
  buckets, so with an RTH-only candle list the first non-`None` read is at the 09:59 bar. Of
  the OFF book's fired core rows, **37 of 259 one-candle-rule (14%)** and **7 of 53 84%-rule
  (13%)** fire before that and are structurally un-gateable. The engine's session is only
  09:30–11:00, so a full third of the window is out of the flag's reach by construction.
- **BR+OCR is never seen.** The call names four setups (BR, OCR, BR+OCR, 84%). `_trend_ok` is
  wired at the `one_candle_rule` and `reentry_84_rule` emission sites only. A BR+OCR signal is
  emitted at the break-and-retest site with `setup_type = BR_OCR_CONFLUENCE`, so the gate never
  runs on it — **3,856 fired core rows** in the OFF book. That is arguably correct scope (a
  BR+OCR takes its direction from the break, not from an assumed trend, which is the premise
  the report gives for gating OCR at all), but it is a scope decision the report makes silently.

## Defect 4 (wave-wide, not L4's alone) — the write-up trips `test_published_numbers.py`

`python research/test_published_numbers.py` fails at `f81db426` with five files, one of them
this row's:

    research/g212_baseline_verdict.md
    research/l1_min_pt1_r.md
    research/l2_rule84_decided.md
    research/l3_ocr_retest_displacement.md
    research/l4_trend_def.md

The test wants every markdown that publishes numbers to name a committed script, either by a
same-stem `.py` beside it or by a literal ``Run: `research/<x>.py` `` line.
`research/l4_trend_def.md` names its script in prose (``research/loop_cycle.py --flag
TREND_DEF …``) but not in the form the test parses, and there is no `research/l4_trend_def.py`.
This is not in the `verify:` gate line, and L1–L3 landed with it already red, so it is a
wave-level cleanup rather than a reason to reject L4 — but it should be fixed for all five in
one pass before the tape phase publishes off them. (This referee file passes: it has a
committed `research/l4_referee.py` beside it.)

## What I could not fault

- The `--dry-run` duplicate-cycle repair. The duplicate never entered git, the repair notes in
  `cycles.md` and `loop_state.json` describe it accurately, and `consecutive_holds = 4`,
  `stop = false` is the true state.
- `research/tape/loop.json`'s `baseline_figures` block matches the OFF arm on every field I
  checked (trades, `$/day`, green months, on all three slices).
- No engine file outside `signal_runner.py` was touched, and the `signal_runner.py` change is
  additive: four `and self._trend_ok(...)` conditions plus one pure function and one method.

## Verdict, restated

**Upheld.** `TREND_DEF` stays **off**. Every number in `research/l4_trend_def.md` reproduces
under independent code; the flag implements the sentence the call settled; the stamps, the
default, the one-change rule, the mark files and the verify gate are all clean. Three defects
stand against the write-up, not the result: the dedupe-release explanation is false (the move
is three days and one $9,750 trade), an n=27 cell carries a verdict it is not allowed to carry,
and the "real verdict" framing hides that the whole gate outcome turns on a single row.

---

# L4 referee — pass 2 (a different model, told to refute)

**Builder's commits:** `355d7cc0` (the flag lands OFF) and **`f81db426`** (the held result,
`research/l4_trend_def.md`, both stamped books, the cycle ledger).
**Pass 1's commit:** `5369601c` (everything above this line).
**Pass 2's scripts:** `research/l4_referee2.py` (books, unit, gate, causal decomposition,
the flag's own function) and `research/l4_referee2_bars.py` (the semantics and the bucket
alignment, re-computed from the archived 1-minute bars with the bar list physically
truncated at the signal bar). Neither imports `research/loop_cycle.py`,
`research/g72_suppress_price.py` or `research/l4_referee.py`: the unit, the monthly buckets,
the `$/day` denominators and the gate are re-typed from their written definitions.

## Verdict: **REFUTED** — the decision survives, the write-ups do not

`TREND_DEF` stays **off**, and that is the right call. Every headline number in
`research/l4_trend_def.md` reproduces to the dollar under a third independent
implementation. But the row was published, and left standing after pass 1 named them, with
**three false or unsupported sentences in the builder's report** — and pass 1's own note,
committed as "upheld", added **two more false sentences of its own**. No repair commit
followed `5369601c`. A result whose published explanation is wrong is refuted, whatever its
arithmetic does.

---

## What reproduced exactly (third implementation)

Unit `up_to_3_stop_win_or_2loss` on `tier == "core"` (CORE_SYMBOLS, 11 names), **close fill**
(`entry_fill.ENTRY_FILL="close"`, stamped in both books), **shipped engine exit** (1R hard
stop resting on the level, intrabar-touch fill, `SCALE_PLAN=hod_then_runner_be`, account-wide
two-loss halt on), 499 sessions 2024-09-04 → 2026-09-04.
Script: `research/l4_referee2.py`, books `research/tape/book_TREND_DEF_{off,on}.json.gz`.

| slice | n_days | arm | trades | total $ | $/day | mean R | win% | avg win | avg loss | W/L | green |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| whole | 499 | OFF | 769 | −25,746 | **−52** | −0.0335 | 45.0 | 801 | 716 | 1.119 | **11/25** |
| whole | 499 | ON | 768 | −30,384 | **−61** | −0.0396 | 45.2 | 780 | 715 | 1.091 | **10/25** |
| H1 | 248 | OFF | 382 | +2,191 | **+9** | +0.0057 | 43.7 | 917 | 701 | 1.308 | **6/12** |
| H1 | 248 | ON | 381 | −7,559 | **−30** | −0.0198 | 43.5 | 863 | 701 | 1.232 | **5/12** |
| H2 | 251 | OFF | 387 | −27,937 | **−111** | −0.0722 | 46.3 | 694 | 732 | 0.949 | **5/13** |
| H2 | 251 | ON | 387 | −22,825 | **−91** | −0.0590 | 46.8 | 704 | 729 | 0.965 | **5/13** |

Gate re-derived: **H1 fails on both columns** (green 6 → 5 *and* $/day +9 → −30);
**H2 passes** (green 5 → 5, −111 → −91). **Decision = hold** — identical to the builder's,
to `research/tape/cycles.md`'s row and to `loop_state.json`'s cycle-4 history entry.
Both halves clear the 30-trade / 12-month floor on the BEFORE side.

Stamps and hygiene, all re-checked and all clean:

- OFF `book_id` **`2c39ced2697c26cc`** = `research/tape/loop.json`'s `baseline_book_id`
  = `research/tape/baseline_2026-09-05.json.gz`'s own stamp, and the two books have the
  identical row count (127,513). ON `book_id` `bc7889b0cfc5ec67`.
- The two stamps' flag dicts differ in **exactly one key**:
  `signal_runner.TREND_DEF: "off" → "structure15"`. Nothing else.
- Both built at `355d7cc0` (ancestor of `f81db426`), `dirty_engine_py: []`,
  `dirty_py_count: 0`, same window, same session count, 3½ minutes apart.
- `TREND_DEF` default in code is `"off"`; `TREND_DEF` is in `research/book_stamp.py`
  `FLAG_SOURCES`. A held research arm never defaults on — correct.
- **One change per row:** `355d7cc0` = `signal_runner.py` + `research/book_stamp.py`;
  `f81db426` = report, two books, `cycles.md`, `loop_state.json`. No second behaviour change.
- **No mark file touched** by `355d7cc0`, `f81db426` or `5369601c`.
- **Verify gate green, run by me at HEAD `5f2e3fdc`** (which has `f81db426` as an ancestor;
  no agent may check out an older commit here): `regression_gate.py` PASS,
  `test_runner_stop.py` ok (70 checks), `test_universe_single_source.py` ok (29 symbols).
- The ntfy line the ledger row generates is plain English and names no flag:
  *"cycle 4: the 15-minute structure trend test — held. $/day −52.0 → −61.0, green months
  11 → 10."*

## Semantics — checked against raw bars, not against the docstring

`research/omen_recall.py "trend 15-minute structure higher highs higher lows OCR direction"`
returns, verbatim:

> **trend** — *"15-minute structure (higher highs / higher lows, or the reverse) on the 1m
> chart — no indicator"* (`omen-10-0-spec.md`, "What the call settled"), and
> `omen-rulebook.md`, Decided 2026-09-05: *"trend = 15-minute structure (HH/HL) on the 1m
> chart."*

`structure15_trend` exercised directly (`l4_referee2.py` section 9): 29 bars → `None`,
30 rising → `bullish`, 30 falling → `bearish`, flat → `None`, empty → `None`, inside bucket
→ `None`, outside bucket → `None`, 44 bars → `bullish` and 45 → `bearish` (the trailing
partial bucket really is dropped). `_trend_ok` is `return True` unless
`TREND_DEF == "structure15"` and `return True` on `None`.

Against the archived bars (`research/l4_referee2_bars.py`), on the 91 fired core rows the
gate removes at its two wired setups:

- **Bucket alignment is genuinely clock-aligned.** Every one of the 277 archived sessions
  the flip set touches has its first RTH bar at exactly `09:30:00` (`polygon_feed.rth`
  filters `09:30:00 <= ts < 16:00:00`), so bucket 1 is 09:30–09:44, bucket 2 is 09:45–09:59.
  This is a real 15-minute chart, not an off-grid rolling window.
- **No look-ahead.** `backtest_week.simulate_day` sets `runner.candles = candles[:i+1]`;
  I recomputed the trend from a physically truncated bar list and matched.
- **87 of the 91 removals are direct trend disagreements.** The other 4 (all
  `reentry_84_rule`) are allowed by the trend read at their own signal bar — they vanish
  because the 84% rule only arms after a stopped S/A original, and the original the gate
  removed was itself an OCR. That is a cascade, not a direction test.
- **221 of 221 kept rows** are correctly not blocked.

## Defect 5 (new) — the report's 84% flip count is not what the report says it is

`research/l4_trend_def.md` presents its flip table as *"exactly the population the new
`_trend_ok` gate can remove"* and prints **18** removed `reentry_84_rule` rows. Four of
those eighteen (22%) are the cascade above: `AAPL 2025-10-23 10:53`, `AMZN 2025-05-02 10:26`,
`TSLA 2026-04-17 10:30`, `NVDA 2026-02-10 10:25`. Their own trend read allows them. The
direction test removed 14 of them, not 18. (Pass 1 recounted the same 18 and did not
separate them either.)

## Defect 6 (new) — the flag has no opinion on two rows in five, and neither write-up says so

Over all **312** fired gated core rows in the OFF book (259 `one_candle_rule` + 53
`reentry_84_rule`), recomputed from raw bars:

| the trend read at the signal bar | rows | share |
|---|---:|---:|
| abstains (`None` — inside/outside bucket, or under 30 minutes of session) | **123** | **39%** |
| agrees with the trade direction → allowed | 102 | 33% |
| disagrees → blocked | 87 | 28% |

Pass 1 reported the *blind window* (14% of OCR fires land before 09:59, when two full
buckets do not yet exist). That is a third of the abstentions. The other two thirds are
inside and outside buckets in the middle of the session. A rule that declines to have an
opinion on 39% of the population it is wired to judge is a materially weaker rule than
either write-up describes.

## Defect 7 (new) — the read is up to 14 minutes stale, by construction

Dropping the forming bucket is the only way to avoid look-ahead, and it is the right choice —
but it means the trend the engine consults at the signal bar is the comparison of two buckets
that both closed *before* the current one began. Measured over the same 312 rows:
**112 (36%) are read from a bucket pair that is 10 or more minutes old**, and the maximum is
14. A human reading a 15-minute chart at 10:29 sees the forming 10:15 bar; this engine sees
09:45 vs 10:00 and nothing since. Defensible, and it is what "no look-ahead" costs — but it
is an implementation choice the rulebook sentence does not make, and no write-up names it.

## Defect 8 (new) — pass 1's own row-join table does not add up

`research/l4_referee.md`'s decomposition prints "only in OFF 3 / only in ON 2 / shared 764".
3 + 764 = 767, against the 769 trades the same document reports two tables earlier. The join
key `(day, et, sym, dir, setup)` **collides on 5 unit rows in each arm** — five cases where
the same symbol, same minute, same direction and same setup is booked twice and both copies
are inside the day walk (`AMZN 2024-11-04 09:45`, `QQQ 2025-01-24 09:54`,
`META 2025-10-29 09:41`, `GOOGL 2025-12-30 09:37`, `NVDA 2026-02-19 09:40`). The collisions
are identical in both arms, so the *conclusion* is unaffected — and my day-level
decomposition, which uses every row and no join at all, sums to the total exactly — but the
published counts are wrong, and this is precisely the duplicate class T1's "no repeats"
self-check is supposed to fail the build on.

## Defect 9 (new) — pass 1's counterfactual is wrong in both directions

Pass 1 wrote: *"Remove that single 2024-10-25 SPY one-candle-rule put (+$9,750) and October
2024 stays green, H1's green count does not fall, and H1's dollar column goes from +$9 to
roughly break-even rather than −$30."* Recomputed (`l4_referee2.py` section 12), the answer
depends on a counterfactual pass 1 never named, and neither reading matches its sentence:

| counterfactual | 2024-10 OFF | 2024-10 ON | H1 green | H1 $/day | gate |
|---|---:|---:|---|---:|---|
| **A — the row never existed** (drop it from the pool; the day walk re-fills its slot) | **+4,070 green** | −4,703 red | **6 → 5, still falls** | +5 → −30 | **hold** |
| **B — delete it from the OFF unit after the walk** | −4,703 red | −4,703 red | 5 → 5 | −30 → −30 | **ship** |

Under A — the only counterfactual that respects the unit's own day walk — October stays
green (pass 1 right), but H1's green count still falls and the decision is still hold
(pass 1 wrong), and H1's OFF dollars are +$5/day, not "roughly break-even" against −$30
(pass 1 conflated the arms: the ON arm never had the row and does not move at all).
Under B the whole gate flips to ship. Pass 1 asserted A's month result and B's gate
implication in one sentence, which is true of neither.

The honest version: **the day walk absorbs most of that trade.** Removing it costs the OFF
arm only $977 of the $9,750 in October, because the walk then reaches the next candidate.
The gate's outcome is robust to deleting the single largest row — the opposite of pass 1's
"decided by one trade".

## The three defects pass 1 found, re-verified and still standing in the report

No repair commit followed `5369601c`. All three sentences are still in
`research/l4_trend_def.md` as committed at `f81db426`:

1. **"the mechanism is not 'worse trades kept,' it's dedupe-release" — false.** Confirmed
   independently: **0** of the unit's changed rows are absent from the OFF book. The two
   only-in-ON unit rows (`MSFT 2025-11-05 10:25`, `NVDA 2026-02-24 10:24`) are in the OFF
   book at the identical status (`halted`) and identical P&L; the day walk simply reaches
   them once the OCR loss ahead of them is gone. The whole move is three days:

   | day | OFF | ON | delta |
   |---|---:|---:|---:|
   | 2024-10-25 | +9,732 | −18 | **−9,750** |
   | 2025-11-05 | −2,000 | +58 | +2,058 |
   | 2026-02-24 | −1,180 | +1,874 | +3,053 |
   | | | | **−4,639** = the whole-window move, to the dollar |

2. **A verdict on an n=27 cell.** The report prints −0.1219R (n=27) unlabelled and then
   concludes *"the gate is removing losing trades on average."* 27 < 30; SWARM.md law 3 says
   count, interval, "not enough", no verdict.

3. **"exactly the population the new `_trend_ok` gate can remove" — false.** The gate is
   wired at `one_candle_rule` and `reentry_84_rule` only, yet `break_and_retest` loses 5
   fired rows and gains 8. Confirmed: OFF 4,329 → ON 4,332.

## One more the report gets subtly wrong

*"H1 fails … (a green-month drop is an automatic fail regardless of the ±5% dollar-drop
tolerance)"* reads as though the dollar column was fine. It was not: +$9/day → −$30/day is a
fall, and `half_verdict` returns `dollar_ok: False` as well. H1 fails on **both** columns.

## Scope note (not a defect, but it should have been written down)

The call names four setups. `_trend_ok` is wired at two. A **BR+OCR** signal is emitted at
the break-and-retest site with `setup_label = "BR+OCR"` — **3,695 fired core rows in the OFF
book** — and the gate never runs on it. That is arguably right (a BR+OCR takes its direction
from the break, not from an assumed trend), but it is a silent scope decision on a population
14× larger than the one the flag does touch.

## Verdict, restated

**REFUTED.** The decision — hold, `TREND_DEF` off — is upheld and reproduces under a third
independent implementation, and the flag implements the sentence the call settled (87 of 91
removals verified against raw bars). What is refuted is the published record: three false or
unsupported sentences in `research/l4_trend_def.md`, uncorrected since pass 1 named them, and
five more errors found here — two of them (defects 8 and 9) in pass 1's own note, which was
committed as "upheld". Nothing is deleted: this is evidence, and the next agent should not
re-run it.

---

# L4 referee — pass 3 (after the repair round; a different model, told to refute)

**Builder's commits:** `355d7cc0` (the flag lands OFF), `f81db426` (the held result and both
stamped books), **`746ccc2a`** (the report-only repair this pass grades).
**Pass 1:** `5369601c`. **Pass 2:** `6e51cf72`.
**Pass 3's script:** `research/l4_referee3.py` — a fourth independent implementation. It
imports neither `research/loop_cycle.py`, `research/g72_suppress_price.py`,
`research/l4_referee.py` nor `research/l4_referee2*.py`: the unit, the monthly buckets, the
`$/day` denominators, the gate and **the 15-minute structure read itself** are re-typed from
their written definitions. Run it as `python research/l4_referee3.py` (books only) and
`python research/l4_referee3.py --bars` (the raw-bar pass).

## Verdict: **REFUTED** — the hold stands, the repair's replacement mechanism sentence is false

Everything the repair was asked to fix, it fixed. But it kept a narrowed version of the very
sentence pass 1 and pass 2 both refuted, and that narrowed version is **also false** — this
time provably on 16 of 16 rows. It also carries a published count (`3,695`) that reproduces
under no slice of either book.

Unit `up_to_3_stop_win_or_2loss` on `tier == "core"` (11 names), **close fill**, **shipped
engine exit** (1R hard stop, intrabar-touch fill, `SCALE_PLAN=hod_then_runner_be`,
account-wide two-loss halt on), 499 sessions 2024-09-04 → 2026-09-04, books
`research/tape/book_TREND_DEF_{off,on}.json.gz`, script `research/l4_referee3.py`.

## The gate — reproduces to the dollar, fourth implementation

| slice | arm | trades | total $ | $/day | mean R | win% | avg win | avg loss | green | months |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| whole | OFF | 769 | −25,746 | **−52** | −0.0335 | 45.0 | 801 | 716 | **11** | 25 |
| whole | ON | 768 | −30,384 | **−61** | −0.0396 | 45.2 | 780 | 715 | **10** | 25 |
| H1 | OFF | 382 | +2,191 | **+9** | +0.0057 | 43.7 | 917 | 701 | **6** | 12 |
| H1 | ON | 381 | −7,559 | **−30** | −0.0198 | 43.5 | 863 | 701 | **5** | 12 |
| H2 | OFF | 387 | −27,937 | **−111** | −0.0722 | 46.3 | 694 | 732 | **5** | 13 |
| H2 | ON | 387 | −22,825 | **−91** | −0.0590 | 46.8 | 704 | 729 | **5** | 13 |

`half_verdict` re-derived: **H1 `green_ok: False` and `dollar_ok: False`** (both columns fail,
as the repair now says); **H2 passes**; **decision = hold**. Identical to
`research/tape/cycles.md`'s TREND_DEF row (`-52.0 -> -61.0`, `11 -> 10`, fail/pass, 768) and to
`loop_state.json` cycle 4. Both halves clear the 30-trade / 12-month floor on the BEFORE side
(382/12, 387/13), so the halves themselves carry a verdict legitimately.

## Identity, stamps, hygiene — all clean

- OFF `book_id` **`2c39ced2697c26cc`** = `research/tape/baseline_2026-09-05.json.gz`'s stamp
  = `research/tape/loop.json`'s `baseline_book_id`. ON `book_id` `bc7889b0cfc5ec67`.
- The two stamps' flag dicts differ in **exactly one key**:
  `signal_runner.TREND_DEF: "off" → "structure15"`. Nothing else, checked as a set difference
  over both dicts.
- Both stamps: commit `355d7cc0` (an ancestor of `f81db426` and of `746ccc2a`),
  `dirty_engine_py: []`, `dirty_py_count: 0`, window 2024-09-04..2026-09-04, 499 sessions,
  built 3½ minutes apart on 2026-09-05.
- **Default in code is `"off"`** (`signal_runner.py:535`, `os.getenv("TREND_DEF", "off")`) —
  matches the `hold`. A research arm never defaults on. `TREND_DEF` is in
  `research/book_stamp.py`'s `FLAG_SOURCES` under `signal_runner`.
- **One change per row:** `git show --stat 746ccc2a` = `research/l4_trend_def.md` only
  (109 insertions, 15 deletions). No code, no flag, no book, no ledger row touched — exactly
  what a report-only repair should be.
- **No mark file touched** by `355d7cc0`, `f81db426` or `746ccc2a` (`git show --name-only`
  over all three, filtered against every corpus named in CLAUDE.md's "THE ONE RULE").
- **Verify gate green, run by me at HEAD `746ccc2a`:** `regression_gate.py` **PASS** (no
  baseline-fired mark went silent), `test_runner_stop.py` ok (70 checks),
  `test_universe_single_source.py` ok (29 symbols, no private lists).
- The ntfy line `loop_cycle.py` emits is plain English and names no flag: *"cycle 4: the
  15-minute structure trend test -- held. $/day -52.0 -> -61.0, green months 11 -> 10."* The
  `cycles.md` label column reads the same way.

## Semantics — verified against the rulebook sentence and against raw bars

`python research/omen_recall.py "trend 15-minute structure higher highs higher lows OCR direction test"`:

> *"trend — **15-minute structure** (higher highs / higher lows, or the reverse) on the 1m
> chart — no indicator"* (`omen-10-0-spec.md`, "What the call settled"), and
> `omen-rulebook.md`, 2026-09-05: *"trend = 15-minute structure (HH/HL) on the 1m chart."*
> Spec Phase-L row: *"**L4 — trend = 15-min structure** for the OCR/84% direction test
> (`TREND_DEF=structure15`). Report how many signals flip direction-eligibility."*

I re-typed the read (`l4_referee3.my_structure15`) from that sentence and ran it against
`signal_runner.structure15_trend` on all 312 fired gated rows, truncated bar lists:
**0 mismatches**. The four wired call sites are the OCR long/short order-block blocks
(`signal_runner.py:3343, 3611`) and the two 84%-rule reclaim blocks (`:3431, :3684`) — the
two setups the spec row names, and no others. Raw-bar pass (own code, bars physically
truncated at the signal bar, `research/l4_referee3.py --bars`):

- **277 of 277** touched sessions have their first RTH bar at exactly `09:30:00` — the
  15-candle buckets really are clock-aligned 15-minute bars.
- **Reach over the 312 fired gated core rows: 123 abstain (39%) / 102 allowed (33%) /
  87 blocked (28%)** — the repair's numbers exactly.
- **4 cascade removals**, the same four rows the repair names (NVDA 2026-02-10 10:25,
  TSLA 2026-04-17 10:30, AAPL 2025-10-23 10:53, AMZN 2025-05-02 10:26), and **0** kept rows
  that the trend blocks. So the direction test itself removes **14** of the 18 84%-rule rows,
  as repaired.
- **Staleness: 112 of 312 (36%) read a bucket pair ≥10 minutes old, maximum 14** — exact.

## Pass 2's defects: fixed

| pass-2 defect | fixed in `746ccc2a`? |
|---|---|
| whole-book "it's dedupe-release" mechanism claim | **yes** — withdrawn, no mechanism now claimed for the whole-book move |
| verdict drawn from the n=27 cell | **yes** — both n=27 and n=3 labelled "not enough", the conclusion removed |
| "exactly the population the gate can remove" | **yes** — corrected, `break_and_retest` added as a reference row plus a scope note |
| the 4 cascade removals undisclosed | **yes** — disclosed and correct |
| the 39% abstain rate undisclosed | **yes** — disclosed and correct |
| the ≥10-minute staleness undisclosed | **yes** — disclosed and correct |
| H1 phrased so only green months looked responsible | **yes** — both columns now named, and both do fail |
| pass 1's own row-join arithmetic and counterfactual | declined as out of scope — **correct call**, they are pass 1's document, not the row's |

## Defect 10 (new, decisive) — the replacement mechanism sentence is false too

The repair kept a narrowed dedupe-release claim. `research/l4_trend_def.md` now says the
`break_and_retest` diff is *"purely from dedupe-release on the gated setups' neighbouring
levels"*, that the four ON-only 84% fires are *"the same dedupe-release mechanism … a
capped/gated candidate is not `fired`, so it releases `backtest_week`'s dedupe suppression
window"*, and that *"this dedupe-release effect explains the ON-only rows."*

It does not. A dedupe-suppressed candidate is booked `skipped_d`; a released one would appear
in the OFF book as `skipped_d` and in the ON book as `fired`. I looked every changed fired row
up in the *other* book by `(day, minute, symbol, direction, setup)`
(`research/l4_referee3.py` section 4):

| the flag's fired-row changes | rows | what the OFF book already holds at the same key |
|---|---:|---|
| `break_and_retest` gained (ON only) | 8 | **8 of 8 present as `halted`, identical P&L** |
| `break_and_retest` lost (OFF only) | 5 | **5 of 5 present in ON as `halted`**, identical P&L |
| `reentry_84_rule` gained (ON only) | 4 | **3 of 4 present as `halted`, identical P&L**; 1 absent |
| **dedupe-released rows (`skipped_d` → `fired`)** | **0** | **none, at any setup** |

The one genuinely new row — `PLTR 2025-11-18 10:59 put`, absent from the OFF book at any
status — is a new *84%-rule arming* (the rule arms off a stopped original, and the ON arm
stopped a different original), not a released dedupe slot. **Zero of the sixteen gained fired
rows are dedupe-release.** The real mechanism for fifteen of them is the **account-wide
two-loss halt**: removing an OCR fire earlier in the day moves where the halt bites, so a row
already detected and booked `halted` in one arm is booked `fired` in the other, at exactly the
same P&L. That is the same error class the L3 referee's pass 4 found (`5f2e3fdc`: "11 of 11
are already in the OFF book at identical P&L") — asserted, in three successive L-rows now,
without opening the other book's statuses.

The whole-book `$`-move is unaffected (0 of these rows reach the traded unit — I confirmed it
independently), and the decision is unaffected. What is refuted is the published explanation,
for the third pass running.

## Defect 11 (new) — the `3,695` count reproduces under no slice of either book

The repair prints *"`break_and_retest` (`setup_label` `BR+OCR`, 3,695 fired core rows in the
OFF book, 14x the size of the two gated setups combined)"* in the flip-table preamble and
again in the scope note. Counted from the OFF book:

| what | rows | distinct `(day, minute, sym, dir, setup)` keys |
|---|---:|---:|
| `setup == break_and_retest`, `status == fired`, `tier == core` | **4,746** | **4,329** |
| `setup_label == "BR+OCR"`, `status == fired`, `tier == core` | **3,856** | 3,525 |
| the two gated setups (`one_candle_rule` + `reentry_84_rule`) | **312** | 312 |

**3,695 is none of them**, under any combination of tier / label / setup / status / traded I
swept. It was carried across from pass 2's note without re-derivation. The `14x` is right only
against 4,329 (13.9x) — against the 3,695 it is printed beside, it would be 11.8x. And
`break_and_retest` is not `setup_label BR+OCR`: BR+OCR covers 3,856 of that setup's 4,746
fired core rows, the other 1,051 carrying the label `break-and-retest`.

## Defect 12 (new, minor) — two different things are both called "fired rows"

The flip table's `break_and_retest` "fired OFF 4,329 → ON 4,332" is a count of **distinct
keys**; the prose's "fired core rows" is a count of **rows**, and the two differ by 417 at that
setup alone (4,746 rows collapse to 4,329 keys). The gated setups have no collisions
(259 + 53 = 312 both ways), so nothing in the gate or the flip counts is wrong — but the
report uses one label for two units. Pass 2 raised the same collision class against pass 1's
unit join (5 rows); it is still nowhere in the builder's report.

## Defect 13 (standing, wave-level, now two repairs old) — `test_published_numbers.py` is red

`python research/test_published_numbers.py` fails at HEAD on **6** files, `l4_trend_def.md`
among them (`l5_day_policy.md` has joined since pass 1 named the first five). The test wants a
same-stem `.py` beside the markdown or a literal `Run: research/<x>.py` line; L4's report names
`research/loop_cycle.py --flag TREND_DEF …` in prose only. It is not in the `verify:` line, so
it does not block, and it is genuinely wave-level — but it is a one-line fix that a report-only
repair could have made, and two repair rounds have now passed it by.

## Verdict, restated

**REFUTED.** The decision — **hold**, `TREND_DEF` **off** — is right, and every number that
matters reproduces to the dollar under a fourth independent implementation: the gate, both
halves, the flip counts, the bucket alignment, the reach split, the cascade set, the staleness
split, the stamps and the identity of the OFF arm with the baseline. The six pass-2 defects are
genuinely fixed. What is refuted is the published record, again: the repair's replacement
mechanism sentence is false on 16 of 16 rows (the account-wide two-loss halt, not
dedupe-release, and 0 released rows exist), and a headline count it publishes twice (3,695)
matches no slice of either book. Nothing is deleted — this is evidence; the next agent should
fix the two sentences and the count, and must not re-run the books.
