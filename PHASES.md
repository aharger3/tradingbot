# PHASES — the dispatch board

Everything in the queue, grouped into phases that can be handed to a subagent as a unit.
`TASKS.md` holds the detail; this is the order and the parallelism. Lanes are from
`DIRECTION.md`: **green** runs unattended, **amber** runs then flags, **red** needs Austin.

To dispatch: say the phase number. Phases inside the same block are independent and can run
at once; blocks are sequenced because a later one reads an earlier one's answer.

---

## Block 1 — the entry side (running now)

The binding constraint. G7 proved the exit is already at the top of its family, so
everything that closes the money gate is upstream of the fill.

| phase | task | lane | state |
|---|---|---|---|
| **P1** | **G4 — what the grader throws away.** Re-run `_grade_pa` over the 7,219 dropped S-signals and record which `return` branch killed each. Cost of the colour gate, cost of the OR-only level test, honest expectancy of the dropped set, OCR-vs-B&R funnel side by side. | green | **dispatched** |
| **P2** | **A1 — threshold sweep on `downgrade.py`.** Austin gave the eight variables, never the numbers. Every constant in that file is a commented guess. Sweep them against the 120 graded day-cards; his corpus is 28 S / 27 A / 3 C and the grader currently produces ≈13% / 24% / 62%. | amber | ready |
| **P3** | **G8 — BR+OCR confluence as its own setup.** `downgrade.has_confluence` already detects it; give it a `SignalType` so it routes, grades and counts like any other setup. Confluence is already worth +6.5 points of win rate. | green | ready |

## Block 2 — retire the legacy ladder

Austin, 2026-08-26: *"no more A+, it's just S A C. That's what needs to be coded."*
Sequenced after P2 because wiring a grader whose thresholds are unratified guesses is the
exact mistake `downgrade.py`'s header exists to prevent.

| phase | task | lane |
|---|---|---|
| **P4** | **R3 — wire `downgrade.py` into detection**, behind a flag defaulting to the new ladder, with `_grade_pa` still reachable so every published number stays reproducible. Routing becomes: trade S, decide on A, skip C. `X` stops being a grade and becomes what it already means — the engine should not have fired. | red → green once P2 lands |
| **P5** | **Rename `LADDER_MODE`.** The exit ladder's modes are called `A` and `B`, which collide with grade letters in every table and conversation. Rename to something that cannot be read as a grade (`SCALE_PLAN` / `hod_then_runner`). Pure rename, no behaviour change. | green |
| **P6** | **Re-baseline everything on the new ladder.** Re-run the 2-year replay, the report, and G7 against S/A/C routing. Record which published figure moved and by how much (this is A2). | amber |

## Block 3 — the rules that barely fire

| phase | task | lane |
|---|---|---|
| **P7** | **G1 — 84%-rule three-arm A/B**: `RULE84_STRICT=1` (today) vs `0` vs armed on `sgrade == "S"`. Diagnosis is already done: the strict gate arms only off legacy `A+`/`A`, which fires 17 times in two years, so 465 of 472 arming opportunities are discarded. | green |
| **P8** | **G2 — the dead scratch branch.** The T4(b) failed-entry scratch has never fired in two years: it needs the entry bar to close back through the level while the entry rule requires a close through it. Fix the trigger so it can express Austin's rule, or delete it and record why. | green |
| **P9** | **G3 — ON WATCH at 2-year scale.** Shipped and on by default, but only ever A/B'd over the 120 graded day-cards. Flip `ON_WATCH=0` against the full rig and report the delta in recall and mean R. | green |

## Block 4 — exits, the one direction still open

| phase | task | lane |
|---|---|---|
| **P10** | **G9 — structure trail + far-target scale-out.** G7 ruled out every mechanical trail (ATR14 / prior-bar, 5-bar consolidation exit) and showed `flat_5r` is the only policy the extra room helps. Untested: a tail riding to 4–5R behind a *structure* trail with no 11:00 clock, and partial exits at the far targets. | green |

## Block 5 — hygiene and validation

| phase | task | lane |
|---|---|---|
| **P11** | **G5 — corpus sweep.** Run `corpus_query.py` over every constant in `parameter_catalog_draft.md`; mark each CONFIRMED / CONTRADICTED / UNMENTIONED against what a trader actually said. The safest unattended lane in the project. | green |
| **P12** | **G6 — per-symbol sample floor.** COIN has 104 traded signals, SOFI and ACHR have 2. Suppress or grey sub-threshold rows so reports stop printing noise next to signal. | green |

## Needs Austin, always

| | |
|---|---|
| **R1** | Grade the outstanding deck / master homework. The only unrecoverable input in the project. |
| **R2** | Ratify or reject the S/A/C thresholds after P2. |
| **R4** | `INCLUDE_SPY_IN_BACKTEST` — SPY is 30 of his 120 graded symbol-days and excluded from `CORE_SYMBOLS`. |

---

## Settled, no longer open

- **The 09:30–11:00 window is correct.** The old "everything fires before 10:00" bug is
  gone: entries in the 2-year book run 09:35 → 10:59, 55.4% in the 09:30 half-hour, 44.6%
  after 10:00, 140 after 10:30. The 10:30 slot's 39.4% win rate is a *result*, not a bug.
- **Ladder B is not a grade.** It is `LADDER_MODE`, the exit scale-out plan: 50% off at the
  first HOD/LOD after entry, stop to breakeven, runner to the next key level. The letter
  collision with grade B is a naming accident — P5.
- **Grades exist to route trades, and the downgrade system is the whole of it.** Grade =
  `S − (downgrades tripped) + (1 if confluence)`, floored at C. Nothing else feeds it.
