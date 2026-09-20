# Cycle 12 halves — OMEN_SCALE_PLAN off (shipped ladder) vs on (flat 2R, `none`)
Unit `up_to_3_stop_win_or_2loss`, core-11, `research/loop_cycle.py` helpers on
`book_OMEN_SCALE_PLAN_{off,on}.json.gz`, boundary 2025-09-01 (`loop.json`).

| slice | OFF $/day | ON $/day | OFF green | ON green | OFF trades | ON trades | win% (OFF->ON) | avg win/avg loss (OFF->ON) |
|---|---:|---:|---|---|---:|---:|---|---|
| whole | -52 | -21 | 11/25 | 12/25 | 770 | 831 | 44.9%->33.0% | $801/$714 (1.12x) -> $1994/$1000 (1.99x) |
| H1 (<2025-09-01) | 9 | -53 | 6/12 | 5/12 | 382 | 415 | 43.7%->32.3% | $917/$701 (1.31x) -> $1999/$1000 (2.00x) |
| H2 (>=2025-09-01) | -111 | 10 | 5/13 | 7/13 | 388 | 416 | 46.1%->33.7% | $694/$728 (0.95x) -> $1990/$1000 (1.99x) |

**7 of 25 months change sign (OFF -> ON, $):** 2024-10 +5047->0; 2025-04
+7841->-1000; 2025-07 -4132->+13000; 2025-09 +1064->-4770; 2025-11
-2765->+13000; 2026-01 -3821->+3000; 2026-05 -1017->+7000.

**Mechanics.** Flat 2R drops the ladder's partial exit at HOD/LOD and its
stop-to-breakeven move: no early bank, no runner past the scale point — every
trade rides full size to the fixed 2R target or the full -1R stop, so win%
falls (33.0% vs 44.9%, fewer trades travel the whole 2R untouched) while
avg win/avg loss goes to ~2.0x (vs 1.12x, no partial softening either side).
At a fixed ~2.0x payoff the breakeven win rate is 33.3%: H1's ON win%
(32.3%) sits just under that line, H2's (33.7%) just over it — a 1.4pp gap
flips the sign. The ladder's payoff ratio instead moves 1.31x H1 -> 0.95x H2,
a smaller, more symmetric swing that doesn't hinge on one win-rate cliff.
