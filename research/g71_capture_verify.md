# G7.1 adversarial verify — track `capture`, the T11 stop-fill guard claim

Verdict: **NOT REFUTED on substance; one clause of the stated mechanism is wrong.**

Scripts: `research/g71_capture_verify_identity.py`, `research/g71_capture_verify_book.py`.
Nothing shared was edited. HEAD `a0997963`; working tree dirty only in json/report
artefacts, none of which any check below reads.

## What reproduced verbatim

| claim | reproduced |
|---|---|
| `python research/t11_stop_fill_fix.py` -> "T11 STOP-FILL SELFTEST FAILED: 12 of 64 checks are wrong." | yes, exit code **1** |
| `DISASTER_STOP=0 python research/t11_stop_fill_fix.py` -> "ok: 64 checks" | yes, exit **0** |
| the 12 red are the 1.6R-floor / 1.1R-clamp / wick-only checks on `backtest_week`'s ladder AND binary paths, long and short (2 paths x 2 sides x 3) | yes; `exit_lab` and `paper_trader` sections stay green because neither has a disaster stop |
| cause is `68e276ca` shipping `DISASTER_STOP=1` / `DISASTER_STOP_R=1.0` (`backtest_week.py:199-200`) | yes — the env toggle is a clean A/B |
| the `verify:` line (`CLAUDE.md:6`) runs only `research/regression_gate.py` | yes; that script is a recall diff over `austin_marks_v2.jsonl`, it never imports `backtest_week`'s fill |
| nothing runs the guard | yes — no `.github/workflows`, no pytest config, and `t11_stop_fill_fix.py` is referenced only by prose (`DIRECTION.md:105`, `CLAUDE.md:122`, `research/test_x2_stop_floor.py:233`, the `g71_capture` files). Its filename is not `test_*`, so a pytest collection would miss it too. |

## The clause that is wrong

> "with `BNR_STOP_MODE='level'` the resting disaster order sits at the level stop's own price"

The stop-placement mode is irrelevant. `stop_rule.disaster_stop_price(entry, risk, long, 1.0)`
with `risk = abs(entry - stop)` (`backtest_week.py:387-391`) returns `entry - 1.0*risk`, which
**is** `stop` by arithmetic identity, for every placement. Measured in
`g71_capture_verify_identity.py`: level 100.50/100.00, buffer 100.50/99.87, retest-low
100.50/99.60, and both short cases all return `disaster == stop`, `equal=True`. The cause is
`DISASTER_STOP_R = 1.0` alone (`stop_rule.py:125`).

## The bigger finding the claim understates

The guard's red is not the engine breaking a convention — `68e276ca` implements Austin's own
ratified card (`research/marks/probe_master_2026-08-29.jsonl:2`, `fact_two_stops` verdict
`both`). The guard is stale w.r.t. the two-stop rule. What is genuinely broken is the other
half of the same probe card (`fact_stop_floor_is_fiction`, verdict `hard`, his note
"-1r is what we want max slippage -1.25"):

**with the resting order at exactly 1.0R and `disaster_stop_hit` = `low <= price` (intrabar
touch), the -1.25R floor is unreachable again.** Any bar whose close is past the stop has
`low <= close <= px`, so the disaster order always fires first and always books exactly
-1.0000R. Measured on the shipped book `research/bt2y_trades.json`
(`meta.generated 2026-08-29T03:14`, i.e. post-`68e276ca`; 500 sessions, 76,019 signals,
3,487 fired, 2,437 traded):

- min r over all 76,019 rows: **-1.0000**; rows worse than -1.0R: **0**
- fired rows: 1,850 losses, **1,828 exactly -1.0000R**, 0 worse than -1.0R

That is the same shape `research/t11_stop_fill_fix.md` documents as the bug it fixed
("0 of 45,193 rows were worse than -1.0R"). Seventh instance of the unreachable-rule class.

Secondary defect, same site: `backtest_week.py:189-191` says -1.25R "stays the outer bound the
close-fill is clamped to, for the bars that gap straight past the resting order", but
`_disaster_hit` (`backtest_week.py:379-392`) returns `px` unconditionally, so a bar that gaps
open below the resting order still books -1.0R instead of its gap fill. Optimistic, not
look-ahead.

## Checks the verify brief asked for

- **look-ahead**: none. `disaster_stop_hit(c.high, c.low, px, long)` reads only bar `i`'s own
  high/low; the guard's fixtures are synthetic bars, no archive, no network
  (`t11_stop_fill_fix.py:31`).
- **branch reachable**: yes. `DISASTER_STOP` defaults ON (`backtest_week.py:199`), and the
  branch is guarded only by `stop_lv == t.stop` (`:538`, `:586`, `:787`) — true for every
  trade before a scale-out or BE raise.
- **right book**: not applicable to the 12/64 count — it is a synthetic selftest, no book is
  read. The book figures above are from the current 3,487-fired / 2,437-traded run; neither
  "2,595" nor "1,017" matches anything in `research/bt2y_trades.json`'s meta.
