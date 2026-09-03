# G7.1 adversarial verify — track `scaleladder`

Target claim (`research/g71_scaleladder.md` §1, §4 bullet 1):

> His ladder and the current exit are statistically the same number. 30/30/30/10 with the
> runner to break-even books +0.539R at 52.9%; the shipped exit books +0.549R at 49.7%.
> Delta −0.010R against the project's own ±1.5799R error bar.

**Verdict: NOT REFUTED on the numbers. One supporting citation is dead and must be replaced.**

Rig: `research/g71_advscaleladder_verify.py` — an independent re-implementation of the
four-tranche ladder plus the control arm the original report never ran. Offline, whole book,
`data_archive/` covers all 28 book symbols.

---

## 1. Reproduction

| arm | n | win% | mean R | total R | months green |
|---|---:|---:|---:|---:|---:|
| BOOK stored `r` (shipped `hod_then_runner_be`) | 2437 | 49.73% | **+0.5495** | +1339 | 25/25 |
| my his-ladder 30/30/30/10, trail=BE | 2437 | 52.85% | **+0.5391** | +1314 | 25/25 |

Matches the claim to every published digit. **Per-trade agreement with
`research/g71_scaleladder_rows.json` → 2437/2437 identical, 0 differ.** The book's own
baseline recount is independent of both: 2,437 traded, mean +0.549481, win 49.733%.

## 2. The control arm the original never ran — and it PASSES

The report compares a from-scratch ladder rig against the book's stored `r`, which came out
of `backtest_week`. Nothing in `research/g71_scaleladder.py` ever pushes the SHIPPED plan
through the ladder rig, so a −0.010R delta could have been rig noise. It is not:

| arm | n | win% | mean R | paired Δ vs BOOK `r` (95% CI) |
|---|---:|---:|---:|---|
| CTRL: rig, 50/50 T1 + runner to book target | 2437 | 55.46% | +0.5560 | **+0.0065 [−0.034, +0.046]** |
| CTRL: rig, 50/50 T1 + runner to RTH close | 2437 | 44.12% | +0.5916 | +0.0421 [−0.034, +0.118] |

The rig reproduces the shipped 50/50 plan to **+0.0065R**, CI straddling zero. The two arms
are commensurable; the delta is a policy delta, not a rig artifact.

## 3. The one real defect — the error bar is retired

`research/g13_floor_fix_ab.md:150-152`:

| bar | value | status |
|---|---|---|
| NARROW — CARRIED (== T3's) | ±0.0095 R | live |
| WIDE (== T3's) | ±1.5799 R | **RETIRED 2026-08-28** |

`g13_floor_fix_ab.md:94` — "±1.5799 (retired) / ±0.0095 (carried)". `:139` — "*The wide bar
was retired 2026-08-28.*" Austin's ruling killed it: a stop is triggered by a candle CLOSE and
nothing else, and the entry candle's own close counts, so `intrabar_stop` rows are not
ambiguous and there is nothing for the wide bar to reprice.

`DIRECTION.md:48-49` still quotes ±1.5799R and is stale (same stale-DIRECTION.md class already
recorded at `research/g71_advscanners.md:13`). The scaleladder report inherited it from there.

**Against the CARRIED ±0.0095R bar the −0.010R delta does NOT sit inside the error bar — it
exceeds it by ~1.1×.** The claim's stated justification is invalid as written.

### It survives anyway, on a better test

±0.0095R is a one-directional fill-repricing ceiling, not a sampling interval, and neither bar
is the right instrument here: these are 2,437 **paired** observations of the same trades with
only the exit varying, so the paired test is available and is strictly stronger evidence than
anything the report offered.

| test | result |
|---|---|
| paired mean Δ (ladder − book) | **−0.0104 R** |
| paired sd / se | 1.2551 / 0.0254 |
| normal 95% CI | [−0.0603, +0.0394] |
| bootstrap 95% CI (4,000 resamples, seed 7) | **[−0.0608, +0.0376]** |

Zero is comfortably inside. "Statistically the same number" is **correct** — established by the
paired CI, not by ±1.5799R.

## 4. Everything else the adversarial brief asked for

| check | result |
|---|---|
| **Right book?** | Yes. `research/bt2y_trades.json` meta = generated 2026-08-29T03:14:29, 76,019 signals, **2,437 traded**, 500 sessions, 2024-08-21..2026-08-21, 28 symbols. This is the current book; 2,595 is the superseded T0 book (`research/g71_advscanners.md:89`, `research/g71_artifacts.md:27`), 1,017 is the dead `backtest_week` book. No defect. |
| **Dropped rows?** | None. 2,437 book rows → 2,437 usable ctx → n=2437 on every one of the 16 variant rows. No survivorship gap between the arms. |
| **Look-ahead — ORH/ORL** | `p21_target_availability.py:159-161` builds ORH/ORL from `rth[:5]`, which WOULD be look-ahead for an entry before bar 5. Measured: **0 of 2,437 trades have `entry_i` < 5** (min entry_i = 5, n=16). Closed. |
| **Look-ahead — structure pivots** | `g71_scaleladder.py:120-130` files a swing under `j + strength`, the bar that CONFIRMS it, and only scans `j >= max(ei, strength)`. Verified by their own selftest and mine. Causal. |
| **Look-ahead — T1 session extreme** | `ext = max(high for bars[:ei+1])`, a running maximum advanced bar by bar. Causal. |
| **Look-ahead — T2 roster** | PDH/PDL (prior day), PMH/PML (premarket), ORH/ORL (bars 0-4). HOD/LOD deliberately excluded from `SIX`. All known at entry. Causal. |
| **Hindsight arms labelled?** | Yes — `mfe_r()` and the oracle-runner rows are declared hindsight bounds in-text and are never mixed into the §1 comparison. |
| **Branch reachability** | T1 rung fires 1,095/2,437; T2 1,404/2,437; T3 872/2,437. T4 has no rung by construction and is correctly reported `n/a`, not 0. `f=10% / trail=be` and `HIS LADDER 30/30/30/10 be` return byte-identical vectors, which is the right internal consistency check (`weights(0.10) == (0.3,0.3,0.3,0.1)`). No dead branch. |
| **Fill discipline** | Every stop routes through `stop_rule.stop_fill_price` / `disaster_stop_hit`; nothing re-implemented. Both arms sit under the same `DISASTER_STOP_R = 1.0` touch stop, so the −1.25R floor is near-unreachable in BOTH (book: 1,207/1,225 losses exactly −1.000R, min −1.0000; ladder: 781/1,149 exactly −1.000R, min −1.1262). Symmetric — not an arm bias. |
| **Money/durability gates** | Neither arm passes anything. mean R gap to 2.0: ladder +1.461, book +1.451. Win gate 55%: 52.85% and 49.73%, both FAIL. Months green 25/25 both — reproduced. |

## 5. One thing the report understates

The sign test runs hard the other way from the mean. The ladder books a **better** R than the
shipped exit on **1,612 of 2,437 trades (66.1%)** and a worse one on 825 — zero ties. It wins
often and small (four exits, three of them capped at or under ~2R) and loses rarely and large
(it scales away the runners that carry the book). "The same number" is true of the mean and
false of the distribution: this is a variance trade, which is exactly the report's own second
bullet (win% 49.7→52.9, weeks green 91→95, max DD 17.1R→14.7R) stated more strongly than it
states it.

## 6. Required correction

The §4 bullet-1 sentence should read:

```diff
-- **His ladder and the current exit are the same number.** +0.539R vs +0.549R, a -0.010R
--  delta against this project's own +/-1.5799R error bar (`DIRECTION.md`). Nothing here
--  moves the money gate.
+- **His ladder and the current exit are the same number.** +0.539R vs +0.549R. These are
+  2,437 PAIRED observations of the same trades with only the exit varying, so the paired
+  test applies: mean delta -0.0104R, bootstrap 95% CI [-0.0608, +0.0376], zero inside.
+  Nothing here moves the money gate. (The +/-1.5799R bar `DIRECTION.md:49` still quotes was
+  RETIRED 2026-08-28 -- `research/g13_floor_fix_ab.md:150-152`; the carried bar is
+  +/-0.0095R and this delta does NOT clear that one. The paired CI is the load-bearing
+  evidence, not either bar.)
```

Reproduce with `python research/g71_advscaleladder_verify.py`.
