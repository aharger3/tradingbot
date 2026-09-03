# G7.1 / `weeksverify` — adversarial verify of the `weeks` track's P1 claim

**Verdict: NOT REFUTED.** Every number in the claim reproduces digit-for-digit from
`research/bt2y_trades.json` with an independent re-implementation that does not import
`research/g71_firsts_policy.py`. Two qualifications below; neither overturns the finding.

Scripts: `research/g71_weeksverify_repro.py`, `research/g71_weeksverify_tiebreak.py`.

## 1. Reproduction (independent walker, own ISO-week and McNemar code)

| arm | trades | weeks green | %grn | total R | claim | match |
|---|---:|---:|---:|---:|---|---|
| P0 shipped | 2437 | 91/105 | 86.67% | +1339.09 | 91/105 | yes |
| P1 first signal only | 496 | 77/105 | 73.33% | +303.29 | 77/105 = 73.3% | yes |
| P2 | 705 | 83/105 | 79.05% | +399.56 | 79.0% | yes |
| P3 | 972 | 87/105 | 82.86% | +472.50 | 82.9% | yes |
| P4 | 861 | 85/105 | 80.95% | +444.82 | 81.0% | yes |
| P5 (S proxy) | 327 | 59/105 | 56.19% | +90.04 | 56.2% | yes |

McNemar exact, recomputed: P0 vs P1 **22/8, p = 0.01612**; P2 0.15159; P3 0.50344;
P4 0.28628; P5 38/6, p = 0.00000 (2·ΣC(44,i≤6)/2⁴⁴ = 4.7e-7); P0seq 0.79053;
CAP-3 0.60724. Identical to `research/_g71_weeks.json::paired_weekly_mcnemar`.

## 2. Attacks that FAILED to break it

- **Wrong book?** No. `research/bt2y_trades.json` meta = generated 2026-08-29T03:14:29,
  76,019 signals, **2,437 traded**, 857 halted, 500 sessions, 2024-08-21→2026-08-21 —
  the current post-T23 book (`145d564e`), which **supersedes** the 2,595-trade post-T0
  book. `DIRECTION.md:20,27` is the stale line, already flagged at
  `research/g71_advscanners.md:13`, `g71_ddverify.md:33`, `g71_ruleauditverify_btr.md:20`.
  No 2,595-row book exists on disk (`g71_advcapture.md:80`).
- **Look-ahead?** None in P1. `P_FIRST = lambda s: s[0] >= 1`
  (`research/g71_firsts_policy.py:150`) stops after one trade; it needs no outcome.
  (P3/P4 read `cum_r` and P5 reads `sgrade`, but those are the n.s. arms and `downgrade.score()`
  is bar-causal.)
- **Stream mismatch?** P0 is `traded` (2,437) while P1 draws from `counted`
  (2,437 + 857 halted). Checked: **all 496 P1 picks have `status == "fired"`, 0 halted** —
  P1 is a strict subset of P0's own rows, so the comparison is not smuggling in trades P0
  never took.
- **Flat-week convention?** Not load-bearing. P0 and P1 both have **0 flat weeks**
  (P1 = 496 trades on 496 candidate days). Only P5/P5b have one flat week each.
- **Arbitrary tie-break?** `ekey = (entry_i, et, sym)` decides "first" by ticker alphabet
  when signals share a bar. 51/496 days (10.3%) are contested, mean tie size 2.12.
  2,000 random re-draws of the tie-break: green weeks **75–80 (median 77)**, McNemar
  p median 0.0201, **97.5% of draws p < 0.05**. Not an alphabet artefact.
- **Week-level resampling?** Paired bootstrap over the 105 weeks, 5,000 draws:
  (P0 green − P1 green) median **14, 95% CI [4, 25]**, P(≤0) = 0.0044.

## 3. Two qualifications the claim should carry

**(a) "significantly" is nominal-only against the family that produced it.** The same
`research/_g71_weeks.json` reports **13** McNemar tests. Holm over those 13: only
`P0 vs P5` (0.0000 → 0.0000) and `P0 vs W1` (0.00342 → 0.041) survive. `P0 vs P1`
0.01612 → **Holm-adjusted 0.161, n.s.**; `P0 vs W2-8` 0.01294 → 0.142, n.s. The
`weeks` report's own line "Two of these clear their own error bar" is therefore right
about *which* two — P5 and W1 — and P1 is not one of them at family-wise α.

**But the finding survives on a better-specified single test.** P0 and P1 differ in two
things at once (stop rule *and* concurrency). The concurrency-isolated comparison is
**P0seq vs P1**, both sequential one-at-a-time on the same counted stream — the `weeks`
script never ran it. It gives **21/5, p = 0.00249**, which clears Holm at m = 13
(0.032). So the direction and the significance hold; the paired arm was just the wrong one.

**(b) "P1 is worse" is a trade-count effect, not a trade-quality effect.** P1's per-trade
edge is *better* than P0's: **mean R 0.6115 (sd 1.8681, n = 496) vs P0's 0.5495
(sd 2.1192, n = 2,437)**. Feeding **P0's own** μ/σ into the report's own
Φ(√n·μ/σ) at each arm's trades-per-week reproduces the whole ranking with no quality term:

| arm | t/wk | predicted %green | observed |
|---|---:|---:|---:|
| P1 | 4.72 | 71.3% | 73.3% |
| P2 | 6.71 | 74.9% | 79.0% |
| P3 | 9.26 | 78.5% | 82.9% |
| P4 | 8.20 | 77.1% | 81.0% |
| P0seq | 17.76 | 86.3% | 88.6% |
| P0 | 23.21 | 89.4% | **86.7%** |

Every cut arm **beats** its iid prediction; P0 is the only arm that **undershoots** its own.
So the correct sentence is *"one trade a day halves the weekly sample, and green-week share
follows √n"* — not *"his day rule picks worse trades."* The claim's wording ("all reduce
green weeks") is arithmetically true and causally misleading if handed to Austin as an
argument against his rule.

## 4. P5 caveat: confirmed and unchanged

P5 = `P_2LOSS` over rows with `sgrade == "S"`, and `signal_runner.S_GATE = False`
(line 380) / `ENABLE_SAC_LADDER = 0` (line 660) — nothing gates on S in detection. P5's
56.2% measures `research/downgrade.py`'s proxy, not Austin's S rule. The claim states
this caveat correctly. Do not report P5 to Austin as a test of his rule.

## No diff proposed

Diagnosis only; no engine file touched. If the `weeks` report is edited, the two edits
worth making are: add the **P0seq vs P1** row (21/5, p = 0.00249) as the concurrency-isolated
test, and mark the McNemar table's p-values as **uncorrected across 13 comparisons**.
