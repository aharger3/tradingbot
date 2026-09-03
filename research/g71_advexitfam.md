# G7.1 adversarial verify — `exitfam`'s "the −1R disaster stop is the only real exit lever"

**Verdict: REFUTED.** The arithmetic reproduces to four decimals; every load-bearing
sentence around it is wrong. Script: `research/g71_advverify_dz.py`.

## The claim, clause by clause

| clause | verdict |
|---|---|
| "the only lever in the exit/BE/faster-cut families whose effect survives its own error bar" | **FALSE** — seven other arms in `g71_exitfam.md`'s own tables are marked `**yes**` |
| "turning it OFF is +0.2130R [+0.1159, +0.3293] per trade" | **arithmetic reproduces; generalisation FALSE** — that is the `ride` toy arm only; on the shipped-shape policies the same rows read +0.1215 / +0.1274 / +0.1257, and the engine-native figure published the same day is **−0.1342 R ± 0.1331** (`research/t0_ratified_rebaseline.md:211-231`) |
| "It bought 25/25 green months" (`g71_exitfam.md` F4 note) | **FALSE** — months green are identical with and without the stop on every arm ever measured |
| "a faster-cut lever" that "did not exist" before 2026-08-29 | **FALSE** — at `DISASTER_STOP_R = 1.0` the resting order's price **is** the level stop's price on 2437/2437 rows, so the A/B is the wick-vs-close stop trigger, i.e. `stop_rule.stop_hit_on_wick`, already measured in `research/t4_stop_on_close.md` and ratified against |
| "the whole family was priced on downside the book no longer has" | **inverted** — the book "no longer has" it because the close-triggered level stop is now unreachable code |

## 1. The disaster stop IS the level stop (2437/2437 rows, max |diff| = 0.000e+00)

`risk = abs(entry - stop)`, so `disaster_stop_price(entry, risk, long, 1.0) = entry - 1.0*risk = stop`
(`stop_rule.py:128-137`, `backtest_week.py:388-392`). Measured, not argued:

```
CHECK A: disaster price == original stop on 2437/2437 rows; max |diff| = 0.000e+00
CHECK B: exit reasons, disaster ON : {'disaster': 1981, 'clock': 456}  rows hitting the -1.25R floor: 0
         exit reasons, disaster OFF: {'stop': 1881, 'clock': 556}      rows hitting the -1.25R floor: 999
```

The `stop` branch fires **zero times** with the disaster stop on. `low <= close`
always, so any bar that closes beyond the level has already touched it, and the
disaster order is tested first (`backtest_week.py:787`, `research/g71_exitfam.py:148-152`).
`stop_rule.stop_hit_on_close` and the −1.25R floor are **dead code** in the
shipped configuration — the identical defect `research/x2_stop_floor_audit.md`
and `research/t11_stop_fill_fix.md` diagnosed, and CLAUDE.md warns about by name.

The shipped book confirms it: `research/bt2y_trades.json` min r = **−1.0000**,
1207 of 1222 losses exactly −1.000R, **0 rows worse than −1R**.

`python research/t11_stop_fill_fix.py` → **exit 1**, 12 of 64 checks red.
`DISASTER_STOP=0 python research/t11_stop_fill_fix.py` → **exit 0**, 64 of 64.
`g71_exitfam.md` never mentions this; it calls the lever "a risk decision, not a
money one — Austin's call."

## 2. Reproduction of F4 (exact)

```
ride       n=2437 win=18.0% mean=+0.5597 med=-1.0000 tot=+1364.0 worst=-1.0000
ride_nodz  n=2437 win=21.8% mean=+0.7727 med=-1.1613 tot=+1883.0 worst=-1.2500
delta nodz-ride = +0.2130 [+0.1159, +0.3293]   (10,000 paired resamples, seed 20260829)
```

Independently re-implemented off `stop_rule` primitives, not by importing
`g71_exitfam.ride`. The number is right. It is also the largest of four, and the
only one measured on a policy the engine does not run.

| policy | disaster OFF − ON | 95% paired |
|---|---:|---|
| `ride` (no target, no scaling) — **the quoted headline** | **+0.2130** | [+0.1159, +0.3293] |
| `hod_only` | +0.1215 | [+0.0818, +0.1638] |
| `30_30_30_10` | +0.1274 | [+0.0858, +0.1707] |
| `50_20_20_10` | +0.1257 | [+0.0847, +0.1685] |
| **engine-native, whole stack re-run** (`research/t0_ratified_rebaseline.md:211`) | **+0.1342** | ±0.1331 — "clears its own bar by under one percent" |

The headline is **59% larger** than the engine-native figure T0 published on the
same day. `ride` carries no target, so every row that would have booked +2R stays
exposed to the wick for the whole session; that is where the extra 0.08R lives.
Quoting "+0.2130R per trade" without the policy qualifier overstates the shipped
effect by ~70%.

## 3. "It bought 25/25 green months" is false

| arm | months green, disaster ON | disaster OFF |
|---|---|---|
| `ride` | 23/25 | 23/25 |
| `hod_only` | 25/25 | 25/25 |
| `30_30_30_10` | 25/25 | 25/25 |
| `50_20_20_10` | 25/25 | 25/25 |
| whole stack (T0, engine-native) | 25/25 | 25/25 |

Zero green months bought, on every arm ever measured including T0's own. The
25/25 in that sentence belongs to `book_r`, not to the arm the +0.2130 came from —
which is 23/25 both ways. The "worst trade of −1.00R" is a tautology: the order
rests at −1R and fills on touch, so −1.000R is the worst loss **by construction**,
which is the thing `t11_stop_fill_fix.py` exists to forbid.

## 4. "The only lever whose effect survives its own error bar" — false on its own page

`g71_exitfam.md`'s own tables mark these `**yes**`: `flat_1r` (−0.1128
[−0.1561, −0.0674]), `flat_2.5r` (+0.0402 [+0.0080, +0.0712]), `flat_5r` (+0.0847
[+0.0020, +0.1647]), `hod_only+dz` (+0.0419 [+0.0047, +0.0802]), `30_30_30_10+dz`
(+0.0439 [+0.0054, +0.0844]), `50_20_20_10+dz` (+0.0433 [+0.0065, +0.0818]), and
F5's 1DTE ATM−1 (−0.0323 [−0.0629, −0.0028]). Seven arms survive their bars. The
report's own prose says the weaker and true thing — "the only exit lever on this
page that moves **more than a rounding error**". The claim as stated is not that
sentence.

## 5. What the claim gets right (checked, not conceded blindly)

- **Look-ahead: none.** `disaster_stop_hit(b["h"], b["l"], px, long)` reads only
  bar `i`'s own extremes; the loop starts at `entry_i + 1` (`research/g71_exitfam.py:145`).
- **Branch reachable: yes.** `DISASTER_STOP` defaults ON (`backtest_week.py:199`)
  and fires on 1,981 of 2,437 rows.
- **Right book: yes.** `research/bt2y_trades.json` meta = 2,437 traded, generated
  2026-08-29T03:14:29, 500 sessions, 28 symbols. 2,595 is the superseded T0 book
  (`9edd2ba7`), 1,017 the dead one. The prompt's "2,595 is the right book" premise
  is itself stale.
- Gaps `{'day': 0, 'bar': 0, 'index': 0}` — all 2,437 rows replayed, none dropped.

## 6. The caveat the paired bootstrap cannot see

`bt2y_trades.json` was generated with `DISASTER_STOP=1` and `loss_halt: True`
(857 trades blocked). The daily loss halt is a function of realised R, so the
disaster stop changes **which rows are in the book** — T0 measured 2,521 rows OFF
vs 2,595 ON, a 74-row swing. Every `_nodz` arm in `g71_exitfam.md` is therefore
evaluated on the trade population the treatment itself selected. The paired
interval holds the rows fixed by construction and cannot price that; T0's
whole-stack re-run can, does, and lands at half the size.

A second one: with the disaster stop on, **1,981 of 2,437 exits (81%) are decided
by an intrabar touch** on 1-minute bars with no sub-minute path, versus **0** in
the `nodz` arm, where every exit is a close or the clock. `g71_exitfam.md` keeps
quoting the ±0.0095R "narrow fill bar" carried since T3, which was priced on
close-triggered fills. It does not cover this arm.

## The correction

Replace F4's last row note:

```diff
-| `ride`, disaster stop OFF | ... | +0.2130 [+0.1159, +0.3293] | **yes** | the pre-2026-08-29 physics |
+| `ride`, disaster stop OFF | ... | +0.2130 [+0.1159, +0.3293] | **yes** | `ride`-only. Engine-native, whole stack: **+0.1342 R ± 0.1331** (`research/t0_ratified_rebaseline.md:211`). Not a faster cut: at `DISASTER_STOP_R = 1.0` the resting order sits ON the level stop (2437/2437 rows), so this arm is the wick-vs-close trigger of `research/t4_stop_on_close.md`, and `stop_hit_on_close` plus the −1.25R floor are unreachable in the shipped config — `research/t11_stop_fill_fix.py` is RED at HEAD (12/64), green at `DISASTER_STOP=0`. It buys **zero** green months (25/25 both ways). T1's `DISASTER_STOP_R = 1.25` arm is the open question. |
```

Not applied — this is a diagnosis pass.
