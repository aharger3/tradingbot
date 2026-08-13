# T5 — why the index pool fires 18 times in two years

**Diagnose only. No engine default changed.** `signal_runner.py`, `universe.py`,
`backtest_week.py` are byte-identical to `main` (`git diff --exit-code` clean).
What changed is one new research script (`research/t51_index_funnel.py`) that
imports the committed engine and *instruments* it by wrapping — not rewriting —
the detection, grading and routing functions, then drives
`backtest_week.simulate_day` over the exact `t8_two_year` window
(2024-08-12 .. 2026-08-11). The archive ends 2026-08-10, so **500 trading days
× 3 = 1500 ran cells of the 1503 possible** (the missing 3 are 2026-08-11 × 3
symbols — no archive data yet).

## The headline

The loss is **not** upstream of the gates. Levels are detected on **every** index
cell (1500/1500) and a break-and-retest or order-block setup forms on **1451/1500
(96.7%)**. The engine sees the structure. It then **grades 99% of those setups
D and skips them** — that is the `_SKIP_GRADES` gate, and it is where 1419 of the
1451 signal-days die. Only 18 cells (18 trades) survive.

The single gate that kills the most index days is **`_SKIP_GRADES`** (the D-grade
skip). The loss is **downstream** of level detection — it is in the grading, not
in level geometry. The fix is grading / stop-distance assessment, **not** new
level geometry, so this is not forced into a 5.2 build.

## Validation — the replay is faithful

The endpoint here is **trade-level** (`SimTrade.counted` = `status=="fired" and
grade!="C"`), the same definition `t8_two_year` uses for the 18. An earlier draft
counted raw signal fires instead and over-counted ~9× because the same level
re-fires every bar; `simulate_day` dedupes those into one trade. The counted
trades here reproduce `t8`'s INDEX_POOL split exactly:

| symbol | counted trades (here) | t8 INDEX_POOL |
|---|---|---|
| QQQ | 7 | 7 |
| SPY | 5 | 5 |
| IWM | 6 | 6 |
| **INDEX_POOL** | **18** | **18** |
| TSLA (control) | 66 | — |

## The funnel, per symbol (cells = symbol × day)

| stage | QQQ | SPY | IWM | **INDEX_POOL** | TSLA (control) |
|---|---|---|---|---|---|
| ran cells | 500 | 500 | 500 | **1500** | 500 |
| days with ≥1 level | 500 | 500 | 500 | **1500/1503** | 500 |
| mean levels / cell | 15.2 | 12.0 | 15.4 | 14.2 | 22.3 |
| days with a setup | 489 | 474 | 488 | **1451** | 494 |
| days with a signal | 489 | 474 | 488 | **1451** | 494 |
| days ≥1 signal fired (non-D) | 68 | 42 | 88 | 198 | 248 |
| **days traded (counted)** | **7** | **5** | **6** | **18** | **66** |

Read down the INDEX_POOL column: 1500 → 1451 → 1451 → 198 → **18**. The first
drop (1500→1451, 49 cells) is the only upstream loss — 49 cells had a candidate
level but no B&R or OB setup formed at all. Every other drop is **inside the
gates**, and the 1451→198 collapse (a 7.4× cut) is the `_SKIP_GRADES` D-grade
skip. The 198→18 cut after that is `simulate_day`'s idea-dedupe plus the C-alert
cap: a level that re-fires non-D on later bars is suppressed as a repeat idea, so
it does not become a second trade.

### Gate survival (cells where ≥1 signal survived past the gate)

| gate (engine order) | QQQ | SPY | IWM | INDEX_POOL | TSLA |
|---|---|---|---|---|---|
| session window (09:30–11:00; veto OFF) | 489 | 474 | 488 | 1451 | 494 |
| mesh veto (tier demoter — never skips) | 478 | 466 | 477 | 1421 | 482 |
| displacement (low-disp → C cap) | 51 | 31 | 80 | 162 | 188 |
| level retirement (≥2 B&R on the level) | 489 | 474 | 488 | 1451 | 494 |
| no-repeat (NO_REPEAT_ENTRIES, default ON) | 489 | 474 | 488 | 1451 | 494 |
| **_SKIP_GRADES** (≥1 non-D fired signal) | 68 | 42 | 88 | **198** | 248 |
| → traded (counted, trade-level) | 7 | 5 | 6 | **18** | 66 |

Notes on the gates the spec names:
- **session window** — `SESSION_EXTREME_FRAC=0` so the session-extreme veto is
  OFF; the only session gate is the 09:30–11:00 cutoff inside `detect_signals`.
  Signals cannot generate after 11:00, so this never *kills* a day that already
  had a signal — it is already folded into "days with a signal".
- **mesh veto** — `MESH_S_VETO=1` but it only demotes Austin's S tier to A; it
  does not skip an engine-grade (A+/A/B/C) signal. It kills **0** counted-trade
  paths (all 18 counted index trades are engine grade B / tier C). It is a
  reporting demoter, not a trade killer.
- **displacement** — `BNR_DISPLACEMENT_GATE=1` (ON) caps low-displacement B&R
  to **C** (alert-only, fired but not counted). It is the second killer: 14
  index cells fired only as a C alert and so were not counted.
- **level retirement / no-repeat** — `LEVEL_RETIRE_TOUCHES=2`,
  `NO_REPEAT_ENTRIES=True`. They retire a handful of signals (5 / 60 index
  signal-skips) but kill 0 whole days — every day they touched also had a D-skip
  that dominates.

## Which gate kills the most index days

Each no-trade cell is attributed to the gate that stopped its **best** signal
(furthest it reached: counted > fired-C > D-skip > tight-stop/repeat/retire):

| killer gate | INDEX_POOL cells | TSLA cells |
|---|---|---|
| **`_SKIP_GRADES`** (graded D → skipped) | **1419** | 382 |
| no_setup_formed (levels but no B&R/OB) | 49 | 6 |
| displacement (fired only as a C alert) | 14 | 46 |
| traded (survived) | 18 | 66 |

`_SKIP_GRADES` kills **1419 of 1451** index signal-days — 97.8% of the loss
after setups form. Displacement is a distant second (14). TSLA loses 382 cells
to the same D-skip but converts far more (66 traded) because its setups clear the
D-rule more often (see below).

## Root cause — why index setups are graded D

The D-grade is not random. Splitting every D-skipped signal by the rule that
produced it (signal-level, every bar):

| symbol | D via tight-stop rule | D via PA pattern | tight-stop share |
|---|---|---|---|
| QQQ | 4364 | 232 | **94.9%** |
| SPY | 4299 | 107 | **97.6%** |
| IWM | 4624 | 329 | **93.4%** |
| TSLA | 3737 | 1570 | 70.4% |

The dominant D-producer on indices is the **price-scaled tight-stop D-rule**
(`signal_runner.py`, the `stock_risk < max(0.10, 0.0015 * close)` line, applied
to every B&R / OCR entry): a setup whose `entry − stop` is under **0.15% of
price** is graded D and skipped. For high-priced, low-range indices the
threshold is an absolute few cents and the retest stop sits right at the level,
so structurally valid B&R entries almost never clear it:

| symbol | median close | tight-stop D threshold (0.15%) |
|---|---|---|
| QQQ | $568 | $0.85 |
| SPY | $637 | $0.96 |
| IWM | $235 | $0.35 |
| TSLA | $362 | $0.54 |

QQQ needs a >$0.85 retest stop, SPY >$0.96, just to avoid an automatic D — and
index retests are tighter than that on most bars. TSLA, lower-priced with wider
relative ranges, clears it ~3× as often (only 70% of its D's are tight-stop),
which is the structural reason the engine "handles it well" and indices do not.

The PA pattern grader (`PriceActionAnalyzer._grade_pa`: hammer / large-wick /
at-key-level) is the secondary D source; it benches the rest. Both are grading
decisions on a level that **was** detected — the level geometry itself is fine.

## Conclusion

- **Detection is not the problem.** Levels on 100% of index cells, setups on
  96.7%. The engine is not blind to index structure.
- **The killer is `_SKIP_GRADES`** — the D-grade skip — taking 1419/1451
  signal-days. It is a grading/stop-distance gate, not a level-detection failure.
- **The mechanism is the 0.15%-of-price tight-stop D-rule**, which benches
  93–98% of index D-skips because high-priced indices cannot form a retest stop
  wide enough in dollar terms. TSLA clears it ~3× more often, which is the whole
  handled-well / not-handled gap.
- **`loss_is_upstream_of_gates: no`.** The fix lives in grading (the
  price-scaled D-rule and the PA pattern grader), not in new level geometry, so
  it is gate/grading work — not a forced 5.2 build.

---
index_days_with_levels: 1500/1503
index_days_with_setup: 1451
index_days_with_signal: 1451
index_days_traded: 18
top_killer_gate: _SKIP_GRADES
loss_is_upstream_of_gates: no
