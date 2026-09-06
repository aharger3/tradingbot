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
