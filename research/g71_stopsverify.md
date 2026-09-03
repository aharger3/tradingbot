# G71 adversarial verify — track `stops`, claim 3 ("best RR is the worst arm")

Verdict: **REFUTED.** Every raw number the `stops` track published reproduces
from its own arm JSONs — and the conclusion drawn from them does not follow.
Script: `research/g71_stopsverify.py` (reads only `research/_g71s_*.json`,
edits nothing, reimplements no fill).

## What reproduces (so this is not a numbers dispute)

`research/g71_stops.md` §1/§2 vs my recompute, `S4_bestrr`:

| figure | claimed | recomputed |
|---|--:|--:|
| traded | 2,402 | 2,402 |
| zero-risk rows | 269 (11.2%) | 269 (11.20%) |
| months green | 22/25 | 22/25 |
| weeks green | 73/105 | 73/105 |
| max drawdown | −32.1R | −32.1R |
| paired capped +10R | −0.1197, SE 0.0292, t −4.10 | −0.1187, SE 0.0289, t −4.11 |

Book identity is fine: `S0_shipped` = 2,436 traded, 500 sessions, 28 symbols,
2024-08-21..2026-08-21, matching the current post-T23 book (2,437,
`research/g71_advscaleladder.md:83`). The prompt's "2,595" is the **superseded**
T0 book (`research/g71_advscanners.md:89`, `research/g71_artifacts.md:27`); the
`stops` track used the right one. No look-ahead: `_pivot_stop`
(`research/g71_stops.py:154`) calls `sr.pivot_levels(cs, as_of=len(cs)-1)` on
the runner's already-sliced candle list. Branch is reachable — 137,600 selector
calls logged in `research/_g71s_S4_bestrr_diag.json`.

## Refutation 1 — 94% of the deficit is a harness artefact, not the selector

All 269 zero-risk rows are `one_candle_rule` order-block signals, and **267 of
them book `out: "open"`, `r = 0.0`, `pnl = $0`.** With `risk == 0` every
`if risk > 0:` guard in `backtest_week.py` (target, BE level, scale plan, the
management block from :838) is skipped, so the row is entered and never managed.
They are inert placeholders, not "untradeable stops that lose money".

Splitting S4's paired-capped delta on that line (`decompose()`):

| subset | n | delta | SE | t |
|---|--:|--:|--:|--:|
| all | 1,705 | −0.1187 | 0.0289 | −4.11 |
| `risk == 0` artefact rows | 177 | **−1.0742** | 0.2233 | −4.81 |
| `risk > 0` real trades | 1,528 | **−0.0080** | 0.0172 | **−0.46** |

**On the 1,528 rows where the selector produced a tradable stop, S4 is
statistically indistinguishable from shipped.** The artefact rows carry 94.0% of
the total delta. The headline t = −4.10 measures the harness, not "best RR
tradable".

Root cause, one line: the $0.05 tradability floor is enforced against the bar
**close** (`research/g71_stops.py:210` `c = candle.close`; :220
`d = abs(c - v)`) while the book's risk is `|entry − stop|` and the entry is a
**limit fill at the level**. On a wick-only order-block retest the retest
candle's own extreme *is* the fill, so a candidate $0.05+ from the close is
$0.00 from the entry. The same defect gives `S1_level` 324 such rows.

## Refutation 2 — S4 is not the worst arm, on the report's own ranking metric

`research/g71_stops.md` §"The four lines" line 3 says S4 "is the worst arm on the
board". Line 2 of the same section prints the paired-capped ranking that
contradicts it, and my recompute agrees:

| arm | paired capped +10R | zero-risk rows | inside noise band (their §1) |
|---|--:|--:|--:|
| `S3_pivot` | **−0.1450** (worst) | 4 | 0.59% |
| `S1_level` | −0.1293 | **324 (13.31%)** (worst) | **16.06%** (worst) |
| `S4_bestrr` | −0.1187 (**least bad of the three**) | 269 (11.20%) | 14.32% |

S4 is worst only on months (22/25), weeks (73/105) and drawdown (−32.1R). On
effect size, on zero-risk rows and on the tolerance-unit band it is **beaten by
`S1_level` — the family Austin named first.** The evidence offered for "a machine
for producing untradeable stops" (269 rows, 14.32%) is *less* untradeable than
the plain level rule sitting beside it in the same table.

The durability half does survive: filtering S4 to `risk > 0` still gives 22/25
months, 73/105 weeks, −32.1R. That is the only part of claim 3 that stands.

## Refutation 3 — the selector never consults a target, so the arithmetic story is wrong

`_best_rr` (`research/g71_stops.py:235-236`):

```python
num  = abs(tgt - c)
best = max(ok.items(), key=lambda kv: num / abs(c - kv[1]))
```

`num` is a positive constant across candidates, so it **cancels**: the argmax is
`argmin |c − stop|` for *any* target, and the `tgt is None` fallback (:234) is the
same operation written out longhand. Driven directly (`target_is_inert()`),
candidates {level 99.50, candle 99.00, pivot 98.00} against close 100.00 return
**99.50 for targets 105, 1000, 100.5 and None alike**.

So the claim's premise — *"with the target fixed at a real level the numerator is
shared"* — describes as a special case something that is unconditional here. The
arm never measured "best RR tradable"; it measured
*tightest-tradable-relative-to-close*. Austin's phrase most naturally reads as
choosing among **(stop, target) pairs at real structure** — pivot stop with the
pivot target, level stop with the next level — under which the numerator is *not*
shared and the tightening identity collapses. That selector was never built.

Worse, §6 of `g71_stops.md` prescribes "a target that does **not** move with the
stop" as the fix. `_nearest_target` already is exactly that, and it is precisely
why the selector degenerated. The diagnosis and the remedy contradict each other.

## Refutation 4 — "every RR is exactly 2.00 by construction" is false

The line is `backtest_week.py:837`, not `:836` (`:836` is
`target = sig.get("target") or (`). The `or` is load-bearing: 84%-reclaim signals
carry the original trade's target. On the shipped book **569 of 2,436 traded rows
(23.4%) have a target that is not 2R** (`rr_universality()`). And it is irrelevant
to S4 either way, which selects on `_nearest_target` — so the sentence is not
evidence for the claim at all.

## What a corrected claim would say

> Implemented as `research/g71_stops.py::_best_rr`, "best RR tradable" degenerates
> to "tightest tradable stop measured against the bar close" — the target cancels
> out of the argmax, so no RR was ever compared. Measured that way it is −0.1187R
> paired-and-capped (t −4.11), but **94% of that is 177 order-block rows whose
> stop lands on the fill price and book r = 0.0 / `out: "open"` because
> `backtest_week`'s `if risk > 0` guards skip management; on the 1,528 real trades
> it is −0.0080R, t = −0.46, a null.** It is not the worst arm: `S3_pivot` is
> worse on effect size and `S1_level` is worse on both untradeable-stop counts.
> What holds is durability — 22/25 months, 73/105 weeks, −32.1R drawdown, and that
> survives removing the artefact rows.

## The fix, not applied (diagnosis pass)

```diff
--- a/research/g71_stops.py
+++ b/research/g71_stops.py
@@ -217,7 +217,13 @@ def _best_rr(runner, candle, is_long, level_stop, structural_stop):
         if not _valid(v, c, is_long):
             REASONS[k + ":wrong_side"] += 1
             continue
-        d = abs(c - v)
+        # The tradability floor must be measured against the price the trade
+        # FILLS at, not the bar close: on a wick-only retest the entry is a
+        # limit at the level and the retest candle's own extreme IS that fill,
+        # so a candidate $0.05 from the close can be $0.00 from the entry.
+        # 269 of 2,402 S4 rows landed at risk == 0 this way, all order blocks,
+        # 267 booking r = 0.0 / out "open" -- see research/g71_stopsverify.md.
+        d = abs(_fill_reference(runner, candle, is_long) - v)
         if d < MIN_TRADABLE_ABS:
             REASONS[k + ":too_tight"] += 1
             continue
```

`_fill_reference` must be the detector's own entry price (the level for a B&R
limit fill, the block edge for an order block), reached through the existing
`signal_runner.order_fill` / `fill_price` seam — **not** a locally re-derived fill.

Second, cheaper, independent guard: `backtest_week` should not book a `traded`
row at all when `risk == 0`. 269 rows on S4 and 324 on S1 currently enter the
book with `r = 0.0` and dilute every mean on that sheet.
