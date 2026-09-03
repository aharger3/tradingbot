# G7.1 — adversarial verify of track `ruleaudit`'s headline stop claim

**Verdict: REFUTED as stated.** Two of the four limbs reproduce; the headline
limb ("the -1.25R floor is dead code for the second time") is empirically false,
and "the close-triggered level stop is unreachable" is overbroad.

Reproduced by `research/g71_ruleauditV_branch.py` (instrumented branch counter)
and `research/g71_ruleauditV_floor.py` (floor A/B), both over the last 40
archive sessions, 28 symbols, shipped defaults
(`DISASTER_STOP=True DISASTER_R=1.0 STOP_ON_CLOSE=True SCALE_PLAN='hod_then_runner_be' BE_TRIGGER='pt1'`).

| limb of the claim | verdict |
|---|---|
| disaster-stop price == level-stop price on every trade | **CONFIRMED** (algebraic identity) |
| the close-triggered level stop is unreachable | **OVERBROAD** — unreachable only at the ORIGINAL stop; `_stop_hit` fired **481** times, 100% on moved stops |
| wicks now stop trades out | **CONFIRMED but not a defect** — this is R2, ratified, documented |
| the -1.25R floor is dead code for the second time | **FALSE** — reached 481×, clamped 124×, changes booked R on 4 of 462 trades (+0.6696R) |

## 1. The identity is real (confirmed)

`stop_rule.py:125` `DISASTER_STOP_R = 1.0`; `:128` `disaster_stop_price` returns
`entry - stop_r*risk`; `backtest_week.py:389` sets `risk = abs(t.entry - t.stop)`.
For a long with `stop < entry`: `entry - 1.0*(entry-stop) == stop`, identically.
Checked on the book: **0 rows** in `research/bt2y_trades.json` have an inverted
stop, so the identity holds on all 2,437 traded rows.

`disaster_stop_hit` (`stop_rule.py:139`) is `low <= price` — an intrabar touch —
and it is evaluated before `_stop_hit` at `backtest_week.py:538`, `:586`, `:787`.
Since `low <= close <= high` always, any bar that CLOSES beyond the original stop
must first have TOUCHED it. 200,000 randomised bars: **481→0** — the close
trigger at the original stop is dominated in every single case.

**But the prior agent's count is vacuous.** `research/g71_ruleaudit_counts.py:130-137`
computes `px = entry - abs(entry - stop)` and asks whether `px == stop`. That is
true by algebra for any row, on any book, produced by any engine. "2,437 of 2,437
(100.00%)" measures arithmetic, not the engine. The conclusion survives only
because the code-read is independently correct.

## 2. The level stop is NOT unreachable (refutes limb 2)

Instrumented `bw._stop_hit`, 40 sessions:

```
disaster_called 58,679   disaster_fired 4,012
stophit_called  81,380   stophit_fired    481
_stop_hit fires by level: {'fired_moved_stop': 481}   <- 'fired_original_stop': 0
```

The close trigger is unreachable **at the original stop only** (0 of 481). It is
the sole and live trigger for every BE-raised / post-scale runner stop — 481
fires. `backtest_week.py:538` and `:586` gate the disaster test on
`stop_lv == t.stop` precisely so the two coexist, and the comment says so.
The claim drops that qualifier and thereby asserts something false about the code.

## 3. The -1.25R floor is live, reachable, and binding (refutes limb 4)

`_stop_fill_px` (`backtest_week.py:351`) → `stop_rule.stop_fill_price` (`:61`):

```
fillpx_called   481      floor_clamped   124     (raw fill moved by the clamp)
```

A/B with `floor_r=1.25` vs `floor_r=inf`, identical 462 traded rows:

| arm | n | mean R | worst |
|---|---:|---:|---:|
| floored (shipped) | 462 | **+0.5606** | -1.0000 |
| floor removed | 462 | **+0.5592** | -1.0000 |

**4 of 462 rows change their booked R; +0.6696R total.** Largest:
`HOOD 2026-06-29 09:56` +1.3378 → +1.0052 (-0.3326R).

This is structurally different from the x2 failure it is compared to. In x2
(`research/x2_stop_floor_audit.md`) `stop_fill_price` was **never called** — the
fill was `t.stop`. Today it is called on every close-triggered stop-out and
actually moves the fill. What is true is a much narrower statement the claim does
not make: **no whole-trade R lands at exactly -1.2500R** (0 rows on the 2,437-row
book, 0 on my 40-session sample), because the clamp now binds only on runner legs
after a scale-out, whose composite R is a blend of the PT1 rung and the clamped
runner. "The floor never shows up in the R histogram" ≠ "the floor is dead code".

## 4. Book identity — not a refutation

`research/bt2y_trades.json` meta: `signals 76019, traded 2437, sessions 500,
2024-08-21..2026-08-21, generated 2026-08-29T03:14`, committed at `145d564e`
(T23). That **supersedes** the 2,595-row post-T0 book (`9edd2ba7`); no 1,017-row
book exists in the tree. The prior agent counted the current book. Correct.

The disaster-stop mechanism (`68e276ca`, R1+R2) `git merge-base --is-ancestor`
`145d564e` — it was in the engine when the book was generated, so the
1,207/1,222 losses at exactly -1.0000R really are disaster fills, not the old
x2 fill-at-`t.stop` bug. My independent 40-session run reproduces the
fingerprint: 251 of 252 losses book at the disaster price, 0 rows at -1.2500R,
worst -1.0000R.

## 5. No look-ahead

`backtest_week.py:753` `for i in range(5, len(candles))` manages open trades in
step 1 *before* detection in step 2, and entry sets `entry_idx=i` (`:866`). A
trade entered on bar `i` is first tested at `i+1`, so the entry bar's own wick
cannot disaster-stop it. `_disaster_hit` reads only `c.high`/`c.low` of the
current bar. Clean.

## 6. Wicks stopping trades out is the specified design, not a regression

`stop_rule.py:104-125` records R2, verdict `both`, Austin: *"Level stop on the
close, disaster stop on touch."* `research/t1_two_stop_model.md` already priced
the cost (arm r100 +0.5378R / 42.8% vs clamp +0.6699R / 48.4%, 1,444 trades
killed on a touch) and found every arm inside its own ±0.134R bar, with r100 and
clamp both 25/25 months green. The claim cites this document and then presents
its content as a newly-discovered bug.

## What would actually be worth reporting

Not "the floor is dead code" but: **the shipped disaster stop books at the
resting price with zero slippage**, so 1,207 of 1,222 losses book exactly
-1.0000R. Austin's own sentence (`stop_rule.py:105`) was *"-1r is what we want
max slippage -1.25"* — a resting order that never slips is optimistic against the
model he stated. That is a modelling question with a real sign, and it is the one
thing in this area the audit did not raise.
