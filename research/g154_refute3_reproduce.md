# g154 refuter #3 — be-stop-after-enough-past-pt1: REFUTED

**What is different now:** the claim's own script reproduces byte for byte and shows no lookahead,
but its surviving arm is one of 4 k-arms whose survivor test a null arm passes 25.2% of the time,
its $/day delta straddles zero (bootstrap 95% CI −$14 to +$49), and its "$47/day baseline" is the
script's own simplified replay running +38% above the shipped book on the identical 498 picks.

Fill for every figure below: signal-bar CLOSE entry (the book's `entry`), `stop_rule.stop_hit_on_close`
+ `stop_rule.stop_fill_price` stops, `stop_rule.disaster_stop_price` at `DISASTER_STOP_R=1.0`,
one-trade-a-day = `research/omen_metrics.first_of_day_arm(size_gate=True)` on
`research/bt2y_trades_retest_on.json`, 498 sessions, 1R = $1,000, H1/H2 split 2025-09-01.

## 1. Reproduction — exact

`python research/g154_rule_be-stop-after-enough-past-pt1.py` re-run on base f8740f80 prints the
claim's table unchanged.

| | claim | my run |
|---|---:|---:|
| baseline $/day (script's own no-BE replay) | $47 | $47 |
| k=0.50 $/day | $65 | $65 |
| H1 delta | +19 | +19 |
| H2 delta | +18 | +18 |
| precision | 0.3051 (18/59) | 0.3051 (18/59) |
| recall_100 | 0.0588 (2/34) | 0.0588 (2/34) |

## 2. Lookahead — none found

The arm check is step 4 of 4 inside `_sim`, after the disaster/level-stop/target tests, and sets
`runner_stop` for the NEXT bar only. The replay starts at `bars[idx+1]`, strictly after the signal
bar. `target` is the book's pre-committed price. No read past the entry bar. This axis clears.

## 3. Multiplicity — the survivor test is a coin flip a null arm wins 1 time in 4

Sign-flip permutation on the 498 paired per-pick dR (`research/g154_refute3_signflip.py`, 20,000
draws): a null arm passes the claim's own criterion (H1 $/day delta > 0 AND H2 $/day delta > 0)
**25.2%** of the time. The script tries 4 k values; the swarm tried 25 candidates. Uncorrected
p for both halves at least as good as observed is 0.047 — Bonferroni over the 4 in-script arms
alone puts it at 0.19, and over 25 candidates it is not a finding.

The script's `survivor` flag also carries a tautology: `(rp["recall_100"] or 0) >= (rp["recall_100"] or 0)`
is always True, so the recall guard tests nothing.

## 4. Effect size — indistinguishable from zero

`research/g154_refute3_reproduce.py`, paired per-pick, k=0.50 vs the script's own no-BE replay:

| | value |
|---|---:|
| picks whose R changed | 46 / 498 (9.2%) |
| mean dR | +0.0180 (sd 0.362, se 0.0162) |
| paired t | +1.11 |
| bootstrap 95% CI on $/day delta | **[−$14, +$49]** |

A ±$63/day-wide interval around a +$18/day point estimate. The five largest single moves are all
**against** the rule (AVGO 2025-04-17 +2.00R → −0.35R; ORCL 2024-11-06, AAPL 2026-02-12,
TSM 2025-12-19, NVDA 2025-08-19 the same shape): the arm trades a handful of full 2R target hits
for many small saves, which is exactly the shape that does not survive a re-draw.

Fine k grid (0.05 → 2.00 in 0.05 steps) does show a contiguous plateau of survivors at k = 0.30–0.70,
which is the one point in the claim's favour — but 11 of 40 grid points pass, close to the 25.2%
null rate, and every k ≥ 1.05 is byte-identical to the baseline (the target is tagged before the arm
price, so the rule is inert there).

## 5. The baseline is not a shipped baseline

On the same 498 size-gated first-of-day picks, the book's **own recorded r** reads **$34/day**
(H1 $136, H2 −$68, mean R +0.034, win 46.5%, 13/25 green). The script's simplified no-BE replay
reads **$47/day** — **+38%** — because it drops the shipped partial-scale ladder and books
full-position outcomes. So "$47 → $65" is a delta inside a model that is not the engine. Worse for
the rule: the shipped ladder already scales out at the PT1 rung, so the de-risking this arm claims
credit for is partly already booked; the honest comparison is not run.

The modelled "breakeven" stop is also not a breakeven: it is close-triggered and fills at the close
(`stop_fill_price(c.close, entry, risk, long)`), so an armed trade books a loss rather than 0R —
Austin's stated rule is a resting order at entry. That biases against the arm, but it means the
thing measured is not the thing claimed.

## 6. What it would have to clear anyway

k=0.50 leaves H2 at **−$34/day** — the second half still loses money — and $65/day is 6x below the
$397/day bar in CLAUDE.md. Even taken at face value the arm does not move the lane.

## Verdict

**REFUTED.** Reproduces exactly and is clean of lookahead, but the survivor label is a 1-in-4 null
event tried 4 ways inside a 25-candidate swarm, the $/day delta's 95% interval contains zero, and
the baseline it improves on is a non-shipped model running 38% hot.
