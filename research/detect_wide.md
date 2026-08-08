# detect_wide (omen-3.7 T5)

Pre-registered **before** the code change and before T6 measures anything. The
prediction at the bottom is the point of this file.

## The reason being targeted

`research/miss_autopsy.md`, S column, top row:

| reason | S marks |
|---|---:|
| **`no_break_retest`** | **27** (of 77 S marks = 35.1%) |
| vetoed_htf | 10 |
| fired_wrong_bar | 10 |

`research/corpus_miss_autopsy.md` (T2.1) **agrees**: `no_break_retest` also tops
the 10,263-instance Discord-alert corpus at 4,186 (40.8%). Two independent
datasets, one classifier, same top reason. No conflict to adjudicate — the S
column and the corpus point at the same thing.

`detect_break_retest` (`omen_bot.py:403`) returned falsy for every level at
those 27 bars: its ordered BREAK → LEAVE → RETEST → CONFIRM sequence did not
complete inside the 12-bar window.

## Which part of the geometry is actually blocking — `research/t5_wide_probe.py`

The autopsy names the function but not the failing *step*, so this row probed it
(reading `miss_autopsy.jsonl`, **not** recomputing it). For each of the 27 S ×
`no_break_retest` marks, the probe re-walks the same FSM over the same near
levels `detect_signals` offers, across the same ±2-bar join window, and records
the furthest state reached.

Deepest blocking step, per mark (27 marks):

| blocking step | marks |
|---|---:|
| **stalled at RETEST** — broke and left the level, never came back to touch it | **14** |
| stalled at LEAVE — broke but never fully cleared | 6 |
| stalled at BREAK — no in-window close through the level | 5 |
| confirm gap too stale | 1 |
| current candle not through the level | 1 |

So step 3 is the binding constraint on more than half of them. The engine
demands the retest candle **touch the level exactly** (`c.low <= level` for a
long, `c.high >= level` for a short). Austin's retests are shallower than that:
price returns to the *area* of the level and turns before tagging it. Treating
the level as a line rather than a zone is what discards these.

Single-mechanism sweep, marks reachable of 27:

| mechanism | reached |
|---|---:|
| baseline (today) | 0 |
| window 12 → 20 | 2 |
| window 12 → 30 | 2 |
| max_confirm_gap 3 → 6 | 1 |
| max_confirm_gap 3 → 9 | 1 |
| drop the LEAVE step | 4 |
| break buffer eps → 0 | 5 |
| **retest band 1.0 × avg range** | **9** |
| retest band 1.3 × avg range | 13 |
| retest band 1.5–2.5 × avg range | 13 (flat) |

The retest band dominates every other single knob by 2–5×, which is what the
blocker table predicts. Window and confirm-gap widening — the two the autopsy
prose guessed at — are worth 2 and 1 marks respectively; they are not the
problem.

## The mechanism being changed

**One knob.** `omen_bot.detect_break_retest` gains a keyword
`retest_tol_mult: float = 0.0`. The RETEST step (steps 3 and 4 of the FSM, the
`seek_retest` and `hold` branches) accepts a candle that comes within
`retest_tol_mult × (average candle range in the window)` of the level instead of
requiring an exact touch:

    back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)

`retest_tol_mult=0.0` reproduces today's `c.low <= level` **exactly** — the
default is byte-identical, not approximately identical.

`signal_runner.DETECT_WIDE` (module global, **default `False`**, flipped at
runtime by the harness exactly as `BNR_DISPLACEMENT_GATE` / `HTF_BIAS_GATE` /
`S_GATE` are) selects `DETECT_WIDE_RETEST_MULT = 1.0` at the two
`detect_break_retest` call sites when ON, `0.0` when OFF.

Nothing else moves: window stays 12, `max_confirm_gap` stays 3, the BREAK
buffer `eps` stays 0.10 × avg range, the LEAVE step stays required, the adverse
wick rule stays, the LATE tagging stays, grading and `_route` are untouched.

**Why 1.0 and not 1.3.** 1.3 reaches 13 of 27 and the curve is flat from 1.3 to
2.5, so 1.3 is the sample's efficient point — and that is exactly why it is not
chosen. "The retest came within one average candle's range of the level" is a
rule with a reading independent of these 27 marks; 1.3 is a number fitted to
them at n=27. Recall bought by over-fitting the pre-registration sample is
recall that will not survive T6's out-of-sample bars. 1.0 costs 4 marks of
in-sample reach and is the honest choice.

## Prediction for T6

Geometric reach is not detection. A truthy `detect_break_retest` still has to
survive `grade_trade`, the candle-colour and HTF checks, the
`stock_risk < max(0.10, 0.0015 × close)` veto, and `_route`. T2's own S column
gives the survival rate: 29 S marks built a signal (10 `detected` + 10
`vetoed_htf` + 7 `vetoed_stop_too_tight` + 2 `vetoed_candle_colour`) and 10
fired — **34%**.

9 newly reachable × 34% ≈ 3.

**Registered prediction — S recall with `DETECT_WIDE=True`:**

> **13 of 77 = 16.9%**, up from the T4/T2 baseline of 10 of 77 = 13.0%.
>
> Honest interval: **12–15 of 77 (15.6% – 19.5%)**.
> Below 12/77 means the veto stack, not the B&R geometry, is the real ceiling
> and T7 should target `vetoed_htf` next. Above 15/77 means the attrition
> estimate was pessimistic.

Secondary, stated so it cannot be retrofitted: the A column carries 19
`no_break_retest` marks and should move by a similar ratio, so all-tier
`detected` should go from 22/159 (13.8%) to roughly **27/159 (17.0%)**.

This row does **not** measure any of the above. It changes the mechanism and
registers the number; T6 produces it.

### Precision warning, registered alongside the recall prediction

A wiring smoke test (not T6's measurement — no marks were joined) replayed the
first 60 marked symbol-days both ways: the engine took **38 entries with
`DETECT_WIDE` off and 77 with it on**. The widening roughly *doubles* trade
count. The prediction above is a recall prediction and says nothing about
whether those extra entries are good ones. If T6 lands inside the predicted
band on recall, the flag still should not be defaulted ON until a 12mo P&L A/B
runs, on this project's own precedent: FVG (2026-07-05) and the flag detector
(2026-07-09) were both plausible widenings that measured as losses.

## Verification performed in this row

- `python test_detect_wide.py` — 34 checks, exit 0. Runs from any working
  directory (it resolves its import path and its source-text read against
  `__file__`, not the caller's cwd).
- **Shipped behaviour is unchanged.** The engine was replayed over 60 marked
  symbol-days on the pre-change code and the post-change code with every flag at
  its default; all 352 signal rows (fired *and* skipped, with grade, direction,
  entry, stop and status) are identical apart from the intended `D` → `X`
  letter. The widening is genuinely inert until the flag is flipped.
- `spec3_orderblock_check.py` fails, but fails identically on the unmodified
  code — a pre-existing failure, not this row's.

## Also in this row (no bearing on the prediction)

**`D` → `X`.** `TradeGrade.X = "X"` is now the canonical skip grade; `D` is kept
as an enum alias (`TradeGrade.D is TradeGrade.X`) and `TradeGrade("D")` still
resolves, so existing readers of the old letter keep working. `_GRADE_RANK`
ranks both at 0 and every `grade.value in ("C", "D")` comparison now also
accepts `"X"`. Pure rename — both letters always meant *skip*.

**`austin_tier`.** Added to the signal dict and the log record, **always
`None`**. It is an empty slot for a future S/A/C mapping, not a mapping. No
mapping from `A+`/`A`/`B`/`C` is asserted, because there is no evidence for one:
`B` is the only profitable engine tier (+$62,451 at 36.6% over 693 trades,
`backtest_report_12mo.md`) while `A+` and `A` both lose at ~31%, and omen-3.6
found no feature that separates S from A. Writing the mapping today would encode
a falsehood in the taxonomy.

**Three setups, three labels.** `SignalType.FAIR_VALUE_GAP` and
`SignalType.FLAG` added; `ONE_CANDLE_RULE` now means the order block alone,
which is the correct implementation of Austin's 2026-08-07 One Candle Rule
(*"you mark the downclose candle in an uptrend and price respects it, or vice
versa"*) — `detect_order_block_setup` is unchanged.

One correction to the T5 spec's description of the defect, recorded because the
spec's line numbers had drifted: the FVG branches
(`signal_runner.py:652`, `:843`) were emitting `BREAK_AND_RETEST`, not
`ONE_CANDLE_RULE`; it was the **flag** branches (`:705`, `:890`) that shared
`ONE_CANDLE_RULE` with the order block. The defect is the same in kind and the
fix is the one the spec asked for — FVG and flag each get their own
`SignalType`, `ONE_CANDLE_RULE` is left to the order block — but FVG was
previously indistinguishable from plain B&R rather than from the order block.
Both branches are dormant at ship (`FVG_RETEST = False`, `FLAG_ENABLED = False`),
so this is a label fix with no behaviour change.

Setup 3 of `Trading-Bot-Rulesets.md` no longer reads "[TO BE DOCUMENTED]".
