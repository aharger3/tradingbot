# G7.1 `scaleladder` -- Austin's four-point ladder, measured

Book `research/bt2y_trades.json` (generated 2026-08-29T03:14:29), 2437 traded signals over 500 sessions 2024-08-21 -> 2026-08-21. Entry, stop, side and entry bar fixed; only the exit varies.

Script: `research/g71_scaleladder.py` (`--selftest` for the mechanics checks). Runners ride to the RTH close, matching `backtest_week.py:810`; one row re-runs with the 11:00 force-flat.

## 1. Current exit vs. his ladder

| exit | n | win% | mean R | total R | months green | weeks green | max DD (R) | % past 2R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **current exit** (shipped `hod_then_runner_be`, 50/50) | 2437 | 49.7% | **+0.549** | +1339 | 25/25 | 91/105 | 17.1 | 19.0% |
| **his ladder** 30/30/30/10, runner to BE | 2437 | 52.9% | **+0.539** | +1314 | 25/25 | 95/105 | 14.7 | 16.5% |
| his ladder, structure = prev-bar low/high | 2437 | 55.2% | **+0.527** | +1284 | 25/25 | 98/105 | 8.3 | 12.8% |
| his ladder, 11:00 force-flat | 2437 | 53.7% | **+0.543** | +1322 | 25/25 | 93/105 | 13.8 | 16.7% |
| his ladder, T2 = flat 2R (no level) | 2437 | 50.8% | **+0.552** | +1344 | 25/25 | 96/105 | 16.6 | 17.6% |

## 2. Runner fraction x trail rule

The remaining `1-f` is split equally across the three scale points, so `f=10%` is exactly his 30/30/30/10.

| exit | n | win% | mean R | total R | months green | weeks green | max DD (R) | % past 2R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `f=0% / trail=be` | 2437 | 53.5% | **+0.532** | +1296 | 25/25 | 96/105 | 13.5 | 16.7% |
| `f=0% / trail=1r` | 2437 | 56.6% | **+0.533** | +1298 | 25/25 | 102/105 | 10.1 | 15.7% |
| `f=0% / trail=struct` | 2437 | 56.2% | **+0.523** | +1273 | 25/25 | 100/105 | 11.4 | 15.2% |
| `f=10% / trail=be` | 2437 | 52.9% | **+0.539** | +1314 | 25/25 | 95/105 | 14.7 | 16.5% |
| `f=10% / trail=1r` | 2437 | 56.5% | **+0.537** | +1308 | 25/25 | 102/105 | 10.5 | 15.9% |
| `f=10% / trail=struct` | 2437 | 56.0% | **+0.526** | +1283 | 25/25 | 99/105 | 11.6 | 15.4% |
| `f=20% / trail=be` | 2437 | 51.7% | **+0.546** | +1332 | 25/25 | 94/105 | 16.0 | 15.4% |
| `f=20% / trail=1r` | 2437 | 56.0% | **+0.541** | +1318 | 25/25 | 102/105 | 10.9 | 16.4% |
| `f=20% / trail=struct` | 2437 | 55.4% | **+0.530** | +1292 | 25/25 | 99/105 | 11.9 | 15.6% |
| `f=30% / trail=be` | 2437 | 50.3% | **+0.554** | +1349 | 25/25 | 92/105 | 17.2 | 14.4% |
| `f=30% / trail=1r` | 2437 | 55.5% | **+0.545** | +1329 | 25/25 | 100/105 | 11.3 | 16.7% |
| `f=30% / trail=struct` | 2437 | 54.8% | **+0.534** | +1301 | 25/25 | 97/105 | 12.1 | 15.8% |

## 3. The arithmetic

`mean R = wT - (1-w)`. Under his ladder the realised win rate is **52.9%** and the mean loss is **-0.785R** (the -1.25R floor and the -1R disaster stop both bind), so the average WINNER has to make

> **T = (2.0 - (1-w)x-0.785) / 0.5285 = +4.484R**

against its actual **+1.720R**. 

### What the ladder can pay at its ceiling

Hindsight bound: every tranche exits at the window's max favourable excursion, T2 still capped at its own target price (2R or the nearer six-level). The stop is ignored entirely, so no policy can beat it.

| bound | mean R | % of trades >= 2R |
|---|---:|---:|
| ladder ceiling (perfect timing, his weights) | **+5.462** | 77.8% |
| uncapped ceiling (100% at MFE, no ladder) | +7.176 | 79.5% |

### Where the R actually comes from, leg by leg

`own rung` counts the legs that exited where he said they should; the rest were swept out by the shared stop, which is why every leg's mean is dragged toward the loss side. Mean R is the LEG's own R, unweighted.

| leg | own rung | mean R at own rung | mean R all exits | weighted contribution |
|---|---:|---:|---:|---:|
| T1 30% causal HOD/LOD | 1095 / 2437 | +2.223 | +0.580 | +0.174 |
| T2 30% 2R-or-nearest-level | 1404 / 2437 | +1.427 | +0.467 | +0.140 |
| T3 30% structure break | 872 / 2437 | +2.815 | +0.548 | +0.164 |
| T4 10% runner to BE | n/a | n/a | +0.605 | +0.060 |

T4 has no rung by construction -- it exits only on its trail, the shared stop, or the close -- so `own rung` is n/a for it, not zero.

### The direct answer to "let more than 10% run past 2R"

Sweep the runner fraction `f` with the OTHER three legs held at their measured exits. Two runners: the real one (trailed to break-even) and an ORACLE runner that exits at the window's MFE -- except on a full pre-scale stop-out, where the leg is already closed and no hindsight rescues it.

| runner fraction f | mean R, real runner | mean R, ORACLE runner |
|---:|---:|---:|
| 10% | +0.539 | +0.972 |
| 20% | +0.546 | +1.412 |
| 30% | +0.554 | +1.851 |
| 50% | +0.568 | +2.731 |
| 75% | +0.587 | +3.831 |
| 100% | +0.605 | +4.931 |

- Smallest `f` reaching mean R 2.0 with the REAL runner: **none -- 100% runner still only reaches +0.605R**.
- Smallest `f` reaching mean R 2.0 with a PERFECT (MFE) runner: **f = 34%**.

### How far past 2R the runner would have to go

Under his weights 90% of the position is structurally capped at or below ~2R (T1 exits on the first stall after the session extreme, T2 is a limit at <=2R, T3 exits on a structure break). Even granting all three the full 2R, they contribute 1.800R of the +4.484R a winner needs, leaving the 10% runner to supply +2.684R of composite -- i.e. the runner leg itself must average **+26.8R**.

## 4. Read

- **His ladder and the current exit are the same number.** +0.539R vs +0.549R, a -0.010R delta against this project's own +/-1.5799R error bar (`DIRECTION.md`). Nothing here moves the money gate.
- **What his ladder DOES buy is shape.** Win rate 49.7% -> 52.9%, weeks green 91/105 -> 95/105, max drawdown 17.1R -> 14.7R. Months green stays 25/25.
- **The runner fraction is not the lever.** Across f = 0% -> 30% mean R moves +0.022R (0.532 -> 0.554, trail=BE). A 100% runner, really trailed to break-even, still books only +0.605R. The gap to 2.0 is +1.461R.
- **His >10%-past-2R condition is already met and does not deliver.** 19.0% of the incumbent's trades book past 2R and 16.5% of his ladder's do; both clear his 10% and both sit near +0.54R.
- **The room is in the tape; the missing thing is knowing when to leave.** A runner that exits at the window's MFE reaches 2.0R at f = 34%. So the ladder is not arithmetically impossible -- the ceiling with perfect timing is +5.462R -- but capture is 9.9% of it, and no weighting of blind exits closes that.
- **The legs that fire pay; they just do not fire.** T1 reaches its HOD rung on 1095 of 2437 trades (44.9%) and books +2.223R when it does; T3 reaches a structure break on 872 (35.8%) for +2.815R. The other 55% of the time the shared stop sweeps the whole position before any rung is reached -- which is an ENTRY problem, not a scaling one.
- Best variant of the 16 measured: `f=30% / trail=be` at +0.554R -- still +1.446R short.
