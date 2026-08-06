# OMEN 3.4 — Verdict (T9)

**No number in this file was recomputed.** Every figure is quoted from T1–T8's own reports. The
only arithmetic performed here is the one the spec mandates: ranking the reported p-values for
Benjamini–Hochberg, and converting the spec's own effect-size floor into the units each row
reports in.

## Provenance — read this before the three answers

T1–T8 are marked `[x]` in `specs/omen-3.4.md` and `done: true` in `parsed.json`, but **none of
their artifacts existed in this checkout when T9 started.** The loop runner checks out the target
repo's default branch and opens a PR at the end of a run; those PRs were never merged, so each
run begins on a tree with no prior output. The artifacts were recovered from two unmerged
branches and restored alongside this file:

| run | branch | state |
|---|---|---|
| **run 1** | `loop/omen-3.4-31054219165` | ran before `blind_marks_all.jsonl` was committed. T4 is a **BLOCKED** record. T6/T7 substituted the engine's own S/R levels because `levels.py` did not exist. Restored here with a `_run1_` prefix. |
| **run 2** | `loop/omen-3.4-31059153572` | ran after commit `4af8109` supplied the marks corpus. Has a real `levels.py` and a real T4. **This is the authoritative run** and supplies every headline number below. |

Three consequences, and they are findings, not housekeeping:

1. **T3 was never done on either run.** `research/marks_audit.md` does not exist on either
   branch, and `research/marks_clean.jsonl` carries **none** of the three booleans its done-when
   requires — its keys are `day, entry, entry_i, entry_t, management, marked_at, note, rr,
   setups, side, stop, symbol, target, tier`. There is no `smeared`, no `incoherent`, no
   `sub_1r`. The row is checked off and was not done.
2. **T4 therefore redefined `smeared` to mean something else.** The spec defines it as per-chart
   smear — marks sharing a `symbol|day|marked_at` with another mark. `research/target_autopsy.py:101`
   defines it as "the target sits within tolerance of 2+ distinct rule-source families," and the
   script never reads `marked_at` at all. So T4's "smearing does **not** materially contaminate
   the tier labels" is a true statement about a question nobody asked. **The tier labels remain
   unaudited.** Every split-by-tier number in T4 is unverified.
3. **The other two defects were never flagged either.** T3 also had to mark `incoherent` (target
   on the wrong side of entry) and `sub_1r`. Neither boolean exists, so nothing downstream could
   exclude them — the spec names a known-bad mark by hand (BABA 2024-08-05, entry 74.97, target
   74.82, scored 0.65R), and T4's own rr distribution has min = 0.500 with 4 marks under 1.0R, so
   such marks are inside the 117 that produced the 2R-precedence result.

### Where the two runs disagree

Per the spec, disagreement between reports is itself reported as a finding rather than resolved
by argument.

| quantity | run 1 | run 2 | note |
|---|---|---|---|
| `POPULATION_N` | **974** | **1,289** | Run 1 counted records in `backtest_charts_12mo.json`; run 2 parsed `overall.trade_count` in `backtest_metrics_full.json`, which is the artifact the spec names. Run 2's reading is the spec-correct one. |
| n actually analysed | 974 | **970** | Run 2 declares 1,289 as "the denominator for the whole version" and then runs every hypothesis on 970 unique candle-bearing trades. **Three different denominators are live in one version**; ~319 trades carry no bars and were never testable. |
| veto rate, 0.8R→1.5R | 20.3 / 23.9 / 28.1 / 33.8% — **in band** | 42.3 / 49.6 / 55.2 / 64.0% — **out of band at every threshold** | Different node sets (engine S/R vs. real `levels.py`). The spec's own lie-detector passes in one run and fails in the other. Same null verdict either way. |
| H9 Spearman rho | +0.0425, CI [−0.024, +0.109] | +0.0580, CI [−0.007, +0.126] | Both cross zero. |
| H9 monotonicity | "monotone on the powered buckets, broken in the underpowered tail" | "**NOT** monotone — contradicted at w2.0, w2.3 and w3.0" | Opposite qualitative readings, but **they are not the same variable**: run 1 binned an *additive* confluence score (buckets up to w12/w14, n ≤ 16 in the tail); run 2 binned the T2 *node weight* (1.5–3.0). Only run 2 tests the ordering T2 actually wrote down. Neither reached significance, so the disagreement changes no verdict — but it means "H9's monotonicity" names two different tests in this version's paper trail. |
| mean realized R | +0.0216 | +0.0227 | Same trade set, ±0.001R. |

### Is everything provisional? (T8 first, as instructed)

**No — not on instrument grounds.** Both runs independently put the ambiguous-bar rate at
**0.1% (1 trade)**, two orders of magnitude under the spec's 20% threshold, and both confirm that
no T5/T6/T7 conclusion flips between pessimistic and optimistic scoring. Mean realized R is
+0.0227 pessimistic vs +0.0258 optimistic — a 0.003R gap traceable to one IREN 2025-09-10 call.
1-minute OHLCV is the right resolution. No finer data needs to be bought.

The results **are** provisional, but for a different reason: the unaudited tier labels, the
three competing denominators, and the fact that the level-node definition itself is broken (see
Question 2).

### BH-FDR at q = 0.10 across every hypothesis actually tested

Eight tests reported a p-value in run 2. Sorted ascending against the BH critical value
(i/m)·q with m = 8:

| i | hypothesis | p | BH crit (i/8)·0.10 | survives? |
|---:|---|---:|---:|---|
| 1 | H9 — OLS slope on weight, **robustness arm** (792 trades) | 0.0369 | 0.0125 | no |
| 2 | H9 — OLS slope on weight, primary (970 trades) | 0.0742 | 0.0250 | no |
| 3 | H3 — veto @ 1.5R, Welch on day-clustered means | 0.171 | 0.0375 | no |
| 4 | H3 — veto @ 1.2R | 0.267 | 0.0500 | no |
| 5 | H3 — veto @ 0.8R | 0.390 | 0.0625 | no |
| 6 | H3 — veto @ 1.0R | 0.502 | 0.0750 | no |
| 7 | H5 — fill rate, McNemar (marks) | 1.0 | 0.0875 | no |
| 8 | H5 — realized R, Wilcoxon | 1.0 | 0.100 | no |

**Zero discoveries.** Not one test survives; the smallest p-value in the version misses its BH
threshold by a factor of three.

Two notes on the family. **Row 1 is the trap.** H9's robustness arm on the 792-trade charts file
returns slope +0.2832, p = **0.0369** — nominally significant at 0.05, and the only sub-0.05
number produced anywhere in this version. It is a strict *subset* of the primary population, not
an independent replication, and it does not survive BH. Do not let it be quoted as "H9 worked on
the smaller file." Second, H5's Wilcoxon appears once though both its arms returned p = 1, and
H5's engine McNemar has no p-value at all (`n_discordant = 0`, undefined). Adding those rows
lowers every critical value and cannot create a discovery, so the table is the generous reading.

Zero discoveries is not the same as zero effects. It means nothing in this version was measured
well enough to act on.

---

## 1. Does level context earn a place in OMEN?

**Answer: NOT-YET-MEASURABLE.**

**The number that decides it: the day-block bootstrap 95% CI on H9's Spearman rho, `[−0.0071,
+0.1258]`.**

The spec's floor is 4 percentage points of win rate or d = 0.15. In correlation units d = 0.15
corresponds to r ≈ 0.075. That value sits **inside** this interval. The confluence-weight test —
the only row that used the whole population rather than a subgroup, and the row the spec sized at
~780 trades — cannot distinguish "level weight is worth nothing" from "level weight is worth
exactly the floor." The point estimate (+0.0580) is below the floor; the upper bound (+0.1258) is
comfortably above it. That is the definition of not-yet-measurable, and it is the honest answer.

The other three rows do not rescue it:

- **H5 (front-running a round number) never ran as a test.** `n_discordant = 0` on the engine and
  `1` on the marks, against a stated power floor of 250. The weight ≥ 3.0 qualification admits
  only HOD/LOD and $50-multiples; the engine's 2R auto-targets land within one tick of such a
  node **11 times in 970**, and never within one tick of a $50-multiple. The population the Osler
  story is about — whole dollars — is weight 2.0 in `levels.py` and was excluded by the spec's own
  cutoff. This is a design mismatch, not a result.
- **H3 (veto in front of a wall) is null and structurally invalid.** The veto rate is 42–64%,
  above the spec's own 40% ceiling at every threshold, so by the row's own diagnostic it is
  measuring something other than what it claims. The mean-R difference is within ±0.08R
  everywhere, every bootstrap CI straddles zero, and the sign is wrong at the tightest threshold
  (0.8R: the vetoed trades were **+0.032R better** than the ones kept).
- **H9's binned table contradicts its own ordering.** Mean R by weight: 1.5→+0.304, 2.0→−0.043,
  2.3→−0.091, 2.5→+0.571, 3.0→+0.204. Three breaks. The single largest bucket mean belongs to
  weight 2.5 on n = 21.

One thing did land, and it is not a level result. **T4 is the row that worked.** On 117 hand
marks, when a structural level and a blind 2R point to different prices, his target follows 2R in
**47 of 75** disagreements. His rr distribution is Q1 = 2.000, median = 2.039, Q3 = 2.290 — it
clusters hard on exactly 2.0. He describes his targets as liquidity levels; his hand draws 2R.
(Caveat: 42 of the 117 marks have no archived bars and were classified against psychological
numbers alone, which biases them away from `at_level` — so the true level share is a floor, not a
point estimate. And per the provenance section, the tier split of these buckets is unaudited.)

## 2. What is the one change to make next?

**`research/levels.py` → `hod_lod_nodes()` (defined line 135): change line 137 from
`seg = bars[: entry_i + 1]` to `seg = bars[: entry_i]`.**

One line. Here is why it is the one that matters more than any new analysis.

`hod_lod_nodes` computes the session high and low **through and including the entry bar**. A
break-and-retest entry is by construction a bar that makes a new session extreme. So for most
trades the function returns, as "the nearest wall ahead of you," the high that the entry bar
itself just printed — a few ticks away, always.

That single choice is what produced the version's worst number. In H3, the nearest weight ≥ 3.0
node in the trade's direction is **HOD or LOD in 938 of 970 trades (96.9%)**. A $50-multiple —
the wall the "veto in front of a wall" story is actually about — is nearest in **22 trades
(2.3%)**. The veto is therefore not testing "is there a wall in front of this trade." It is
testing "did this entry happen at the session extreme," which for a breakout strategy is very
nearly a constant. That is exactly why the rate came out at 42–64% instead of inside the 5–40%
band, and it is why the highest-value row in the version returned a measurement of its own
definition rather than of the market.

`h3_veto.md` caveat 2 identifies this and correctly declines to act on it, because changing the
node definition mid-row would be changing the test the spec defined. T9 is where that call gets
made. Excluding the entry bar makes HOD/LOD mean *the prior session extreme — the wall that was
standing there when the decision was made*, which is what the rule was always supposed to mean.

Do this before re-running anything. Re-running H3 or H9 on the current definition spends compute
to re-measure a definition. Note also that the fix will change H9's weight-3.0 bucket (n = 180,
95 HOD + 76 LOD), so H9 must be re-run after it, not before.

## 3. What is now settled negative?

Three tombstones, all descriptive rather than inferential — nothing was killed by a p-value,
because BH-FDR at q = 0.10 returned zero discoveries across all eight tested hypotheses.

```
2026-08-06 (omen-3.4) — "Targets are liquidity levels, 2R is only a minimum." DEAD as a
  description of his hand. On 117 blind marks, when a structural level and a blind 2R
  disagree, his target follows 2R in 47 of 75 cases; rr Q1=2.000, median=2.039. He draws 2R
  and describes a ladder. OMEN's existing 2R auto-target already matches what he does — no
  change needed there. (research/target_autopsy.md)

2026-08-06 (omen-3.4) — "Shave the target a few ticks short of the round number (Osler queue
  effect)." DEAD as a description of his hand: signed distance from target to nearest whole
  dollar is median −1.0 tick on calls and 0.0 ticks on puts. He targets the round numbers
  themselves. Whether shaving would PAY is NOT settled — H5 got n_discordant = 0 against a
  power floor of 250 and never ran. (research/target_autopsy.md, research/h5_frontrun.md)

2026-08-06 (omen-3.4) — "Veto a trade when a weight>=3.0 node sits within 1R, with HOD/LOD
  computed through the entry bar." DEAD by construction, not by statistics. That node is the
  session extreme the entry bar itself just made, so it is nearest in 96.9% of trades and the
  veto fires on 42-64% — outside the spec's own 5-40% validity band at every threshold. The
  idea of a wall-veto is untested; this operationalisation of it is void.
  (research/h3_veto.md)
```

**Explicitly NOT killed, and do not let anyone record them as killed:** confluence weight
predicting outcome (H9 — CI spans the effect floor, genuinely undecided); front-running round
numbers (H5 — never tested); the wall-veto idea itself (H3 — only this encoding of it died).

Also not killed but newly broken: the loop's own bookkeeping. **T3 is `[x]` in the spec and
`done: true` in `parsed.json` on both runs and produced neither deliverable** — no
`research/marks_audit.md` on either branch, and the `marks_clean.jsonl` that does exist was
written by T4, not T3, and carries none of the three booleans. T4 is likewise `done: true` while
run 1's `_run1_target_autopsy.md` is a self-declared **BLOCKED** record. A row that writes a
blocker file still reports done; that is a defect in the runner, not in the analysis.

---

## FOR AUSTIN

Nothing changes on your chart tomorrow. Trade it exactly as you did today.

You say you target liquidity levels and treat 2R as a minimum; your marks say otherwise. When a
level and a plain 2R point to different prices you take the 2R, 47 times out of 75, and half your
marks sit within a hundredth of exactly 2.0R. That is not a mistake — the bot already targets 2R, so
you and it agree. And when you target a round number you put the order right on it, not a few cents
in front; we tested whether shaving a few cents fills more often and the sample was far too small to say.

The "skip it if there's a big level in the way" rule did not work — not because levels don't matter, but because we measured the wrong thing and haven't measured the right one yet.
