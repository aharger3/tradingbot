# L2 — the 84% re-entry as decided on the call

Row L2, OMEN 10.0. Flag: `RULE84_DECIDED` (default OFF, held OFF by this row's gate).
Loop cycle: `research/loop_cycle.py --config research/tape/loop.json --flag
RULE84_DECIDED --on 1`. Two books, stamped, both at commit `7fb977f7` (the flag-OFF
landing commit), 499 sessions, 2024-09-04..2026-09-04:

- OFF (shipped default): `research/tape/book_RULE84_DECIDED_off.json.gz`
- ON (RULE84_DECIDED=1): `research/tape/book_RULE84_DECIDED_on.json.gz`

## Recall check (step 1)

`research/omen_recall.py` on "84% rule reclaim tolerance 25% previous candle range
same session before 11:00 two attempts" returns the settled sentence verbatim
(`omen-10-0-spec.md`, "What the call settled"):

> "84 is a **name only** (the lesson's stat), no threshold. Arms **only after a
> stopped S or A original**. Reclaim = close back at the original entry within
> **25% of the previous candle's range**; two attempts; **same session, before
> 11:00**."

Implemented exactly that. No conflicting reading turned up.

## What the flag does

One composite flag replaces three earlier, superseded readings of the same
rulebook sentence (`RULE84_STRICT`, `RULE84_ARM_SGRADE`, `RULE84_ARM_NOGATE`),
which are all ignored while `RULE84_DECIDED` is on:

1. **Arm gate** (`backtest_week._arm_84`): the stopped-out original must grade
   **S or A** on Austin's own ladder (`downgrade.score`, the same call the
   book's `sgrade` column already makes) — not S alone, not the legacy A+/A
   ladder.
2. **Reclaim tolerance** (`signal_runner._reclaim_gate_ok`, new function): the
   reclaim close must land within **25% of the PREVIOUS candle's range**
   (`BAR_EXTREME_FRAC`, the one 25% constant this file already uses everywhere
   else) of the original entry price — a different unit from the existing
   `RULE84_RECLAIM_TOL`, which is in R (entry-to-stop) units and was left
   alone, per this row's own instruction not to reuse it.
3. Two attempts and same-session-before-11:00 are already the shipped
   defaults (`RULE84_MAX_ATTEMPTS=2`, `SESSION_END`/`ENTRY_CUTOFF="11:00"`) —
   no new flag needed for either.

Everything else about the reclaim clause (no-pattern-vs-strong-PA, the RR
floor, the near-HOD/LOD veto, stop placement) is untouched: one composite
change, not a rewrite.

## The gate result (unit: his day policy)

Fill = close (shipped `ENTRY_FILL` default). Exit = shipped engine: 1R hard
stop, resting order at the level, intrabar-touch fill; `SCALE_PLAN=
hod_then_runner_be`; account-wide two-loss halt on. Unit =
`up_to_3_stop_win_or_2loss` on `universe.CORE_SYMBOLS` (core-11), his day
policy — up to 3 fired-and-traded signals a day in arrival order, stop after
the first win or the second loss. Script: `research/loop_cycle.py` ->
`backtest_2y.py --days 730`.

| | trades | $/day before→after | mean R before→after | green months before→after | gate |
|---|---:|---:|---:|---:|---|
| whole (25 mo) | 773 | -$9 → -$16 | -0.0059 → -0.0103 | 12/25 → 12/25 | — |
| H1 (12 mo) | 378 | $72 → $58 | 0.0472 → 0.0381 | 8/12 → 8/12 | **FAIL** (-19.4%, exceeds the 5% no-regression ceiling) |
| H2 (13 mo) | 395 | -$89 → -$89 | -0.0567 → -0.0567 | 4/13 → 4/13 | pass (no change) |

**Decision: HOLD.** `RULE84_DECIDED` stays OFF. H1 alone fails the
no-regression gate (a $/day drop past the 5% ceiling), so per the row's own
rule both halves must pass and this one doesn't. `research/tape/cycles.md`
and `research/tape/loop_state.json` both carry this cycle
(`target_met: false`, `stop: false`, `consecutive_holds: 3`).

## The row readouts (all-29 book, both fired and traded, since the arm/reclaim
mechanics live upstream of the day-policy unit)

| | fired (all 29 syms) | fired/day | traded | traded/day | mean R (traded) | share of all traded rows |
|---|---:|---:|---:|---:|---:|---:|
| OFF | 542 | 1.086 | 56 | 0.112 | +0.061R | 1.38% |
| ON | 200 | 0.401 | 20 | 0.040 | +0.036R | 0.50% |

Core-11 slice: OFF fires 238 (18 traded); ON fires 95 (9 traded).

**Sample-size rule: neither traded column clears 30 trades.** 56 (OFF) and 20
(ON) are both under the 30-trade floor this project holds every verdict to —
**not enough** to call a winner or a loser on the re-entries' own mean R, only
to describe the funnel.

## Originals: S vs A vs C (engine ladder, `sgrade` where present, `grade`
otherwise), joined by symbol/day/level-price to the nearest prior stopped-out
row before the re-entry's own timestamp

| | S | A | C | total 84%-rule fires (all 29 syms) |
|---|---:|---:|---:|---:|
| OFF (no arm-grade gate) | 78 | 138 | 326 | 542 |
| ON (RULE84_DECIDED) | 69 | 116 | **15** | 200 |

This is a nearest-match join (symbol, day, level price within 2 cents, before
the reclaim bar), not a stored foreign key — the code has no such reference,
so treat exact counts as approximate. The direction is unambiguous either
way: the arm gate did what it says — C-graded originals collapsed from 326 to
15 (the residue is join slop, not a gate failure; the code path used at the
arm point is `_sgrade_84(t, runner) in ("S", "A")` and admits nothing else).

## The 84% share of the book

All-29, all fired signals: 1.14% (OFF) → 0.36% (ON). All-29, all traded
signals: 1.38% (OFF) → 0.50% (ON). The rule is a small slice of the book in
both arms; tightening the arm gate to S/A-only and the reclaim tolerance to
the candle-range unit roughly halves the re-entry count and cuts the traded
share to about a third.

## Bottom line

Every A/B in this repo moves less than its own error bar, and this one is no
exception — the whole-book move (-$9 → -$16/day) is small next to the
per-trade noise. What actually gates the decision is durability, not $/day:
H1's $/day fell more than 5%, which is the no-regression line this loop
enforces on every half. Held, not shipped. No number here should be read as
"the 84% rule is bad" — only that this particular tightening does not clear
the bar this loop was built to enforce, on this book, on this unit.

## What this does NOT establish

- Not enough trades (56 / 20, both under 30) to say whether S/A-gated
  re-entries carry a better or worse mean R than ungated ones — the funnel
  narrowed, the R distribution did not move outside noise on this sample.
- The original-grade join is approximate (nearest match by price and time,
  no stored link) — a hint at the gate's effect, not an audited count.
- This says nothing about the live-fill (phantom) column or any unit other
  than the day policy and the raw fired/traded counts reported here.
