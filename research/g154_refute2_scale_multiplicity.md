# REFUTED — g154 "scale-before-the-level" (refuter #2, multiplicity + sampling error)

**The claim's numbers reproduce exactly, but the half that makes it a survivor is noise: the H1 improvement is +$9.40/day against a standard error of $25.63 (t = +0.37), no b anywhere in the plausible $0.01–$0.20 region reaches t > 1.96 on H1, and the survivor gate it clears fires 35.4% of the time when the true effect is set to exactly zero — which is the same rate at which the 25-candidate F5 family actually produced survivors (8/25 = 32%).**

Verdict: **refuted.**

Instrument: `research/g154_refute2_scale_multiplicity.py` (imports the claim script's own
`simulate_exit` / `shifted_target` / `bars_for` unmodified — nothing is re-implemented).
Cache `research/g154_refute2_scale_grid.json`, results `research/g154_refute2_scale_multiplicity.json`.

**Fill, named:** entry = the signal bar CLOSE (the book's own `entry`); level stop via
`stop_rule.stop_hit_on_close` filled at `stop_rule.stop_fill_price`; disaster stop
`stop_rule.disaster_stop_price` at `DISASTER_STOP_R = 1.0`, intrabar; target touched intrabar,
filled at the bar open on a gap-through; one-trade-a-day unit =
`research.omen_metrics.first_of_day_arm(rows, size_gate=True)` with the
`signal_runner.min_risk_floor` size gate; 1R = $1,000. Book `bt2y_trades_retest_on.json`,
498 sessions, H1/H2 split 2025-09-01.

## 1. Reproduction — the claim's arithmetic is correct

`python research/g154_rule_scale-before-the-level.py` re-run on base f8740f80:

| figure | claimed | reproduced |
|---|---:|---:|
| baseline $/day | $50 | **$50** ($50.09) |
| cents_005 $/day | $93 | **$93** ($93.04) |
| H1 delta | +9.4 | **+9.40** |
| H2 delta | +76.5 | **+76.49** |
| precision | 0.305 → 0.305 | **18/59 = 30.5%, both** |
| recall_100 | 0.0588 → 0.0588 | **2/34 = 5.9%, both** |

No lookahead found: `b` is causal (ATR14 ending at `entry_i`), the walker starts at `entry_i + 1`,
and the intrabar-target-before-close-stop ordering is correct in time (the close is the last tick
of the bar) and identical on both sides. The refutation is not about lookahead.

## 2. The H1 half — the load-bearing half of the gate — is indistinguishable from zero

The survivor rule is "H1 delta > 0 AND H2 delta > 0". Paired bootstrap over the 498 sessions,
10,000 resamples:

| | delta $/day | CI95 | P(delta ≤ 0) |
|---|---:|---|---:|
| full | +42.95 | [+5.07, +85.54] | 0.013 |
| **H1** | **+9.40** | **[−35.05, +63.84]** | **0.381** |
| H2 | +76.49 | [+18.17, +144.00] | 0.003 |

**P(both halves positive on a resample of its own data) = 0.617.** The published verdict does not
replicate on 38% of resamples of the very data it was computed from.

## 3. No b anywhere in the region is significant on H1

Per-arm delta ± standard error, both halves (section E):

| b | H1 delta | SE | t | H2 delta | SE | t | survivor |
|---|---:|---:|---:|---:|---:|---:|---|
| $0.01 | +14.21 | 16.66 | +0.85 | +18.11 | 16.42 | +1.10 | True |
| $0.02 | +16.33 | 20.27 | +0.81 | +35.67 | 22.92 | +1.56 | True |
| $0.03 | +6.44 | 20.11 | +0.32 | +34.91 | 23.13 | +1.51 | True |
| **$0.04** | **−3.44** | 19.99 | −0.17 | +39.21 | 25.04 | +1.57 | **False** |
| **$0.05 (published winner)** | **+9.40** | **25.63** | **+0.37** | +76.49 | 32.71 | +2.34 | **True** |
| **$0.06** | **−0.76** | 25.55 | −0.03 | +68.86 | 32.10 | +2.15 | **False** |
| $0.08 | +9.53 | 31.17 | +0.31 | +64.62 | 32.76 | +1.97 | True |
| $0.10 | +11.35 | 35.16 | +0.32 | +58.34 | 32.96 | +1.77 | True |
| $0.12 | +23.50 | 40.25 | +0.58 | +42.38 | 31.94 | +1.33 | True |
| $0.15 | +9.83 | 42.78 | +0.23 | +52.54 | 35.23 | +1.49 | True |
| $0.20 | +2.35 | 48.42 | +0.05 | +50.44 | 37.81 | +1.33 | True |
| $0.25 | −14.87 | 52.55 | −0.28 | +66.73 | 43.06 | +1.55 | False |
| $0.30 | −41.36 | 55.02 | −0.75 | +52.78 | 44.53 | +1.19 | False |
| $0.50 | −132.12 | 63.20 | −2.09 | +28.43 | 51.79 | +0.55 | False |
| 0.05×ATR14 | +10.72 | 20.61 | +0.52 | +15.56 | 20.46 | +0.76 | True |

**0 of the 11 arms with b ≤ $0.20 reach t > 1.96 on H1.** The published winner sits at t = +0.37 —
and both of its immediate neighbours, $0.04 and $0.06, have a **negative** H1 delta and fail the
gate. A claim about a *region* ("rest the scale slightly before the level") cannot have its winner
sandwiched between two failures one cent away. That sign-flipping is the signature of a
noise-dominated surface, not a threshold.

Read the same table the other way and the stated rule is not what was measured: b = $0.20 is not
"slightly before the level", yet it books +$26/day over baseline. What the sweep actually shows is
generic "take a nearer target", flat across a 20× range of b, with a $9–25/day ripple on top that
is the cherry-pick.

## 4. Multiplicity: the gate fires this often on nothing

Centered null — de-mean each published arm's per-day delta so the true effect is exactly zero,
then resample:

| | rate |
|---|---:|
| one arm clears "H1 > 0 AND H2 > 0" under a true-zero effect | **8.9%** |
| **any of the 3 published arms clears it** | **35.4%** |

25 candidates were tried in F5. At 35.4% per candidate, noise alone is expected to hand back
**≈8.9 survivors**. The family actually returned **8 of 25 (32%)** with a true survivor flag
(`ambiguous-stop-candidates`, `be-stop-after-enough-past-pt1`, `displacement-graded-not-boolean`,
`entry-earlier-satisfiable-bar`, `exhausted-overextended`, `scale-before-the-level`,
`scratch-exit-direction-match`, `stop-placement-routed`). **The observed survival rate of the whole
F5 family is what pure noise produces.** Surviving this gate carries no information.

And that is before this script's own 15-point grid: 10 of 15 b values clear the gate, so the
3 published arms were themselves a favourable slice of a surface where two-thirds of points "pass".

Selection stability (best-of-3 by $/day, per resample): cents_005 wins 84.4%, cents_002 11.3%,
atr_005 4.3% — the winner is stable, but it is the winner of a coin-flip family.

## 5. Concentration: ~10 sessions out of 498 carry the whole result

188 of 498 sessions change at all. Of the +$21,389 total delta, the **top 1 session carries 14%,
the top 3 carry 41%, and the top 10 carry 130%** — i.e. the other 178 changed sessions are net
**negative** by about $6.4k. Top five: 2026-05-12 (+$2,946), 2025-04-04 (+$2,945), 2025-03-11
(+$2,875), 2025-10-24 (+$2,800), 2024-10-25 (+$2,783). Each is one day flipping from a −1R stop to
a ~+1.9R target hit, worth ~+3R. The entire "$50 → $93/day" headline is about seven net day-flips.

## 6. The headline dollars are not the engine's dollars

Both the "$50 baseline" and the "$93 candidate" are the claim script's **single-stage proxy walker**
(one target, one stop), not the shipped multi-stage `SCALE_PLAN` ladder. The claim report says so in
its own last paragraph, but the headline does not travel with that caveat. On the same 498-session,
size-gated one-trade-a-day unit, the book's own booked ladder is **$33.93/day (H1 $135.71,
H2 −$67.85, mean R 0.034)**. Nobody should read "$93/day" as money this engine would make.

## What would change the verdict

Pre-register a single b (or an ATR multiple) before looking, and show H1 delta with t > 1.96 on a
held-out window — or re-run the shift inside `backtest_week._ladder_bar` so the number is the book's
own money rather than a proxy. Neither exists today.
