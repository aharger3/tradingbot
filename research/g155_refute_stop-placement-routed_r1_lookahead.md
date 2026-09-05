# g155 refuter #1 (leakage/lookahead) — F5 `stop-placement-routed`

**Verdict: REFUTED.**

**What is different now:** the routed stop is provably identical to the shipped stop on
**0 of 498** one-trade-a-day picks, so the claimed +$9.73 (H1) / +$16.27 (H2) cannot be the
rule — a null control that routes the stop *to itself* through the same replay reproduces the
candidate arm **to the cent**, meaning the entire delta is an unannounced swap of the book's
exit engine for a naive one.

Fill discipline throughout: signal-bar CLOSE entry (`meta.entry_fill == "close"`),
`stop_rule.stop_fill_price` stops, size-gated on `signal_runner.min_risk_floor`, 1R = $1,000,
unit = `research/omen_metrics.first_of_day_arm`, book = `research/bt2y_trades_retest_on.json`
(498 sessions), H1/H2 split at 2025-09-01.

---

## 1. The headline reproduces exactly

`python research/g154_rule_stop-placement-routed.py` re-run on base f8740f80 reprints the
claimed table with no drift.

| arm | $/day | H1 $/day | H2 $/day | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| baseline (book pnl) | $33.93 | $135.71 | −$67.85 | 46.5% | 13/25 | −$21,405 |
| candidate (routed stop) | $46.93 | $145.44 | −$51.58 | 35.1% | 12/25 | −$28,794 |

The arithmetic in the report is correct. The *attribution* is not.

## 2. The null control: the rule is worth $0.00

Same script, same functions, same population — but the "routed" stop is set to the row's own
shipped stop (identity) and pushed through the identical `replay_routed` walk.

| arm | $/day | H1 | H2 | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| baseline (book pnl) | $33.93 | $135.71 | −$67.85 | 46.5% | 13/25 | −$21,405 |
| **NULL (identity stop, replayed)** | **$46.93** | **$145.44** | **−$51.58** | **35.1%** | **12/25** | **−$28,794** |
| candidate (routed stop) | $46.93 | $145.44 | −$51.58 | 35.1% | 12/25 | −$28,794 |

| delta | H1 $/day | H2 $/day |
|---|---:|---:|
| baseline → candidate (**the claim**) | +9.73 | +16.27 |
| baseline → NULL (**exit-model artifact**) | +9.73 | +16.27 |
| NULL → candidate (**what the rule is worth**) | **0.00** | **0.00** |

Identical to the cent, including win rate, green months and max drawdown. The rule contributes
nothing in either half.

## 3. Why the rule is a structural no-op

`routed_stop_for` sends `break_and_retest` to `row["level_px"]`. On this book that value **is**
the shipped stop:

- break_and_retest candidates where `level_px == stop` exactly: **7,302**
- where they differ: **0**

`break_and_retest` is 7,302 of 8,227 candidates and **495 of the 498** first-of-day picks (the
other 3 are `one_candle_rule`). So the dominant route is the identity map by construction, and:

- first-of-day picks whose routed stop differs from the shipped stop: **0 / 498**
- `stop_disagree` median **0.0**, mean **0.0002** (the script's own number, and it is the tell)
- precision **30.5% → 30.5%**, S-recall-100 **5.9% → 5.9%**, pick-set identical (verified)

A stop that never moves on any scored row, leaving the pick set byte-identical, cannot move
$/day by $13. That the report shows both "nothing changed" and "+$13/day" on the same page is
the internal contradiction.

## 4. What actually produced the $13/day: an unmatched exit engine

The baseline reads the book's booked `pnl`, produced by `backtest_week._ladder_bar_4` — a
four-rung scale-out ladder with break-even trailing (`LADDER_TRAIL`), the R2 `_gave_it_back`
discretionary exit, `PESSIMISTIC_FILL` same-bar tie handling, and an EOD flush. The candidate
reads `replay_routed`, an all-or-nothing walk to a single target with none of that.

Measured on the shipped (unchanged) stop, book outcome vs naive replay:

| | book | replay |
|---|---:|---:|
| wins | 231 | 175 |
| losses | 266 | 323 |
| scratch | 1 | 0 |
| max R | **+6.000** | **+2.095** |
| total R (498 picks) | +16.90 | +23.37 |

- outcome flips: **92 / 498 = 18.5%** (74 win→loss, 18 loss→win)
- total R delta +6.470R = **+$12.99/day** — the whole headline

The book's ladder books many small partial wins (hence 231 wins but max 6R runners); the replay
books fewer, fatter, all-or-nothing 2R wins. Win rate falls 11.4 points while $/day rises — a
signature of an exit-model change, not a stop change. Two examples of the loss→win flips that
carry the top of the delta: AMD 2024-12-11 (book −1.000R at 128.75, replay +2.000R at 127.91)
and HOOD 2025-03-05 (book −1.000R at 45.61, replay +2.000R at 45.10) — same entry, same stop,
same target, different engine.

The arm is additionally **mixed**: `build_routed_book` keeps the book's original row whenever
`replay_routed` returns `None` (unreadable bars, or neither level touched by session close), so
358 of 8,227 candidates are scored by the ladder engine and the rest by the naive one, inside
the same arm.

## 5. Lookahead findings (my assigned lens) — none found in the walk itself

For completeness, the leakage checks I ran came back clean; the defect is control-group
mismatch, not future information:

- **Index alignment.** `bars[entry_i].close == row["entry"]` on 294/498 exactly and the rest to
  2-dp export rounding; `09:30 + entry_i minutes == row["et"]` on **497 / 498**. No premarket
  offset, no timeframe mismatch (`entry_tf` is `1m` on all 498).
- **Entry bar.** The replay walks `bars[entry_i+1:]`, strictly after the close fill. The book
  does the same (`backtest_week.py:1310`, `if i <= t.entry_idx: continue`). No same-bar fill.
- **Stop construction.** `ocr_wick` calls `detect_order_block_setup(bars[:entry_i+1])` —
  prefix only, no future bars. `level_px` is known at the break.
- **Same-bar tie.** `replay_routed` tests `disaster_stop_hit` before the target touch, so a bar
  touching both resolves to the stop. Conservative.
- **Horizon.** Both engines run to the RTH session close; no extension.

## 6. Multiplicity

25 rule candidates were tried; this one is reported as a survivor at +$9.73 / +$16.27. Under
Bonferroni at 25 arms nothing here is close — but multiplicity is moot, because the effect
attributable to the rule is exactly zero, not merely small. For scale, the total R delta the
whole arm produces is 6.47R across 498 trades (mean 0.013R/trade), well inside the project's
own ±1.5799R per-arm error bar.

## 7. What would have to change for this rule to be testable

Route the stop and replay the exits **on both arms with the same engine** — i.e. compare
`replay_routed(row, routed_stop)` against `replay_routed(row, row["stop"])`, never against the
book's booked pnl. On this book that comparison is degenerate (0/498 stops move), so the F5
predicate cannot be evaluated against `bt2y_trades_retest_on.json` at all without an engine
re-run in which `placed_stop`'s routed arm actually differs from the shipped structural stop.

## Reproduce

```
python research/g154_rule_stop-placement-routed.py      # reprints the claimed table
```
Null control, outcome-flip and identity checks: scratchpad scripts
`null_control.py`, `exitdiff.py`, `indexcheck.py`, `final.py`, `noop.py` under
`%LOCALAPPDATA%\Temp\claude\C--Users-aharg-Desktop-Projects-tradingbot\a15203c9-f162-4329-b9d8-31a7966cedc7\scratchpad\`
(each loads `g154_rule_stop-placement-routed.py` by path and reuses its own functions —
nothing is reimplemented).
