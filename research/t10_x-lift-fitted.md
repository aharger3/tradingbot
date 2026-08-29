# T10 — the targeted X lift, fitted to his 40 veto verdicts

**The middle exists, and it is `clean`.** On the 100 held-out S-sweep cards it moves S recall
**18/34 → 23/34 (52.9% → 67.6%)** while *raising* precision **36.0% → 40.4%**, for a book that
grows 2,548 → 3,285 traded rows (+28.9%) with **mean R inside its own error bar
(−0.0426 against ±0.1167 — a null on money)**, win rate **+3.9 points (42.8% → 46.7%)**, max
drawdown **32.43R → 27.68R**, and **25/25 months green** unchanged. Five S days are gained and
**zero are lost** — exact one-sided McNemar on (5, 0) is **p = 0.031**. Against the two arms
that already existed, `off` and `on_all`: `on_all` re-run on the T0 engine (`all` below) buys
25/34 but pays 44 false fires against `clean`'s 34, a 2.95× book, mean R **−0.1955 which does
clear its ±0.1028 bar**, and drawdown 40.89R. `clean` is the better arm on every column that
is not raw recall.

**And the second finding is bigger than the first. The X grade is not what stops the engine
from taking the trades Austin wants.** On the 40 vetoes he graded, 11 of his 13 S/A/C cards
produce a signal that satisfies the lift condition **at the exact minute he named** — and
only **1 of those 11** survives `_min_viable_stop`. **10 of 13 are killed by the stop
guard, not by the grade.** At book scale the same thing: `clean` promotes 20,135 signals and
**19,403 of them (96.4%) die on the stop guard**. The engine's own proposed stop on the bars
he graded S/A/C is **0.000%–0.307% of price, median 0.034%** — two of them are literally
zero-width (entry == stop, so `R = 0` and the trade is undefined). Lifting a veto cannot fix a
stop that is inside one candle.

Script: `research/t10_x_lift_fitted.py`. Engine flag: `X_LIFT` in `signal_runner.py`,
**default `off`**. Test: `research/test_t10_x_lift.py`. Books: `research/_t10_arm_*.json`
(not committed — 67 MB each; regenerate with the command in §8).

---

## 0. What the arms are, and why they are not a search

The arms are the clauses of **one sentence of his**, taken in the order he said them
(`research/marks/probe_master_2026-08-29.jsonl`, `fact_ocr_demote`):

> *"s trades are all about being early and the most important thing is that **clear break
> retest** with **displacement** that happens quick and **strong PA entry**."*

| arm | condition | his clause |
|---|---|---|
| `off` | lift nothing | today |
| `br` | `break_and_retest` only | the OCR pool is "not this setup at all" — 17 of 20 |
| `clean` | `br` + the retest is `[clean]`, not `[late]` | "clear break retest" |
| `pa` | `clean` + `[hammer]` or `[disp]` | "strong PA entry" |
| `disp` | `pa` + `[disp]` | "with displacement" |
| `all` | lift every X | the `on_all` control, re-run on the T0 engine |

This is a **nested ladder**, not a search over feature space. With 13 positive labels an
exhaustive conjunction search overfits by construction; §5 runs that search anyway, as a
control, and it does not beat the ladder.

**Every lift must clear `_min_viable_stop`, `all` included.** A lifted signal is promoted to
`B`, and a `B` does not otherwise face that gate — which is exactly how W1's `on_all` book
came to read **+7.4974 mean R on 12,770 rows**: it is full of two-cent stops, and `R =
|entry − stop|` turns a two-cent stop into a fifty-R winner. That is arithmetic, not edge.
The guard makes the ladder and its control differ in exactly one thing.

---

## 1. Held-out first (method rule 2)

| metric | `off` | `br` | **`clean`** | `pa` | `disp` | `all` |
|---|---:|---:|---:|---:|---:|---:|
| **S-sweep recall** (34 S of 100) | 18/34 = 53% | 24/34 = 71% | **23/34 = 68%** | 22/34 = 65% | 21/34 = 62% | 25/34 = 74% |
| S-sweep false fires (of 66) | 32 | 42 | **34** | 33 | 32 | 44 |
| **S-sweep precision** | 36.0% | 36.4% | **40.4%** | 40.0% | 39.6% | 36.2% |
| **combined gate** (recall − false-fire rate) | +0.045 | +0.070 | **+0.161** | +0.147 | +0.133 | +0.069 |
| S days gained / lost vs `off` | — | 6 / 0 | **5 / 0** | 4 / 0 | 3 / 0 | 7 / 0 |
| exact McNemar p | — | 0.016 | **0.031** | 0.063 | 0.125 | 0.008 |
| **Test 1 S recall** (15 S of 100) | 3/15 = 20% | 5/15 = 33% | 4/15 = 27% | 4/15 = 27% | 4/15 = 27% | 5/15 = 33% |
| Test 1 false fire on days he refused | 13/42 = 31% | 19/42 = 45% | 14/42 = 33% | 14/42 = 33% | 14/42 = 33% | 21/42 = 50% |
| Test 1 day precision | 17/30 = 57% | 23/42 = 55% | 18/32 = 56% | 18/32 = 56% | 18/32 = 56% | 25/46 = 54% |
| veto lane: his 5 S | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| veto lane: his 4 A | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| veto lane: his 4 C | 0/4 | 1/4 | 1/4 | 1/4 | 0/4 | 1/4 |
| **veto lane: his 27 `no`** (false fire) | 2/27 = 7% | 2/27 = 7% | 2/27 = 7% | 2/27 = 7% | 2/27 = 7% | 5/27 = 19% |

The gain is **monotone and strictly additive** — every arm's found-S set is a subset of the
next arm's, and **no arm loses a single S day**. The five `clean` gains are `ACHR_2026-02-05`,
`ARM_2024-10-28`, `HOOD_2024-11-06`, `PLTR_2025-07-01`, `QQQ_2025-09-23`; `br` adds
`QQQ_2025-09-16`; `all` adds `PLTR_2025-12-11`.

`clean` buys **+5 true fires for +2 false fires**. `br` buys **+6 for +10**. `all` buys **+7
for +12**. That ratio is the whole argument for stopping at `clean`.

**The veto lane does not move, and §4 is why.** These are the very cards the ladder was fitted
on, and the arm still fires on only 1 of his 13 — because the stop guard, not the grade, is
what holds them.

---

## 2. The book

| figure | `off` | `br` | **`clean`** | `pa` | `disp` | `all` |
|---|---:|---:|---:|---:|---:|---:|
| signals detected | 74,988 | 75,257 | 75,056 | 75,015 | 75,001 | 75,493 |
| **traded** | 2,548 | 5,065 | **3,285** | 2,870 | 2,767 | 7,523 |
| **mean R** | +0.5378 | +0.4903 | **+0.4952** | +0.5155 | +0.5292 | +0.3423 |
| total R | +1,370.2 | +2,483.4 | **+1,626.7** | +1,479.6 | +1,464.4 | +2,575.3 |
| **win rate** | 42.8% | 43.8% | **46.7%** | 44.8% | 44.4% | 39.6% |
| profit factor | 1.9496 | 1.8898 | 1.9433 | 1.9449 | 1.9629 | 1.5813 |
| max drawdown (R) | 32.43 | 26.82 | **27.68** | 30.39 | 26.52 | 40.89 |
| worst trade (R) | −1.000 | −1.000 | −1.000 | −1.000 | −1.000 | −1.000 |
| months green | 25/25 | 25/25 | **25/25** | 25/25 | 25/25 | 25/25 |
| signals the arm's condition reached | 0 | 65,005 | 20,135 | 7,829 | 4,287 | 69,817 |
| of those, killed by `_min_viable_stop` | 0 | 62,521 | 19,403 | 7,506 | 4,067 | 64,935 |
| **survival of the lift** | — | 3.8% | **3.6%** | 4.1% | 5.1% | 7.0% |
| rows carrying `[x-lift:]` | 0 | 2,484 | **732** | 323 | 220 | 4,882 |
| mean R of the lifted rows | — | +0.4553 | **+0.3808** | +0.4076 | +0.4620 | +0.2542 |
| **mean-R move vs `off`** | — | −0.0475 | **−0.0426** | −0.0222 | −0.0085 | −0.1955 |
| its own 95% bar | — | ±0.1097 | **±0.1167** | ±0.1223 | ±0.1241 | ±0.1028 |
| **clears its bar?** | — | no — **null** | no — **null** | no — **null** | no — **null** | **yes** |

**Method rule 1, stated plainly: every ladder arm's mean-R move is a NULL.** The only arm
whose money move is real is `all`, and it is real in the wrong direction (−0.1955 against
±0.1028, and −3.2 points of win rate). The lifted rows are not free money — they mean
**+0.38R** against the book's +0.54R, so they dilute the average while adding total R. That is
the correct read of a recall lever: it is bought with dilution, and here the dilution does not
clear its own bar.

Durability never moves. **25 of 25 months are green in all six arms**, so the durability gate
(T0's one win) survives every arm intact.

---

## 3. The fit on his 40 verdicts, and how much of it rests on single cards

| arm | lifts | his S/A/C caught | his 27 `no` lifted | precision | 95% CI | leave-one-out precision |
|---|---:|---:|---:|---:|---|---|
| `off` | 0/40 | 0/13 | 0/27 | — | — | — |
| `br` | 31/40 | 12/13 | 19/27 | 39% | [24%, 56%] | 37%–40% |
| **`clean`** | 21/40 | **10/13** | 11/27 | **48%** | [28%, 68%] | **45%–50%** |
| `pa` | 11/40 | 7/13 | 4/27 | 64% | [35%, 85%] | 60%–70% |
| `disp` | 5/40 | 3/13 | 2/27 | 60% | [23%, 88%] | 50%–75% |
| `all` | 40/40 | 13/13 | 27/27 | 32% | [20%, 48%] | 31%–33% |

**How much is driven by single cards — the question this track was told to answer:**

- **`clean` and `br` are stable.** Removing any one of the 40 cards moves `clean`'s precision
  by at most **5 points** (45%–50% over all 40 leave-one-outs) and `br`'s by at most 3.
  Their decisions rest on 21 and 31 cards respectively, so no card is load-bearing.
- **`pa` and `disp` are not.** `disp` decides on **5 cards**. One card (`NFLX_2025-06-12`,
  his `no`) swings its precision from 60% to 50%–75%. A 5-card rule is a card list with a
  condition attached, and its held-out gain (3/34, p = 0.125) is not significant either.
  **This is the reason the ladder stops at `clean` and not at its narrowest rung.**
- **Every 95% CI in the column overlaps every other.** On 40 rows the fit cannot separate
  `clean` from `pa`; the held-out sets in §1 can, and they pick `clean`.
- The one-candle-rule pool is 9 of the 40 cards and **8 of the 9 came back `no`** — the single
  strongest signal in the label set, and it is the first rung of the ladder. It matches his
  rare-setup lane exactly: 17 "not this setup at all" + 3 "weak" out of 20.

---

## 4. Reachability, checked BEFORE tuning (method rule 3) — and the real gate

| arm | X rows it reaches | of the 70,319 vetoes | of the whole book | verdict |
|---|---:|---:|---:|---|
| `br` | 65,787 | **93.6%** | 86.6% | **over the 85% line — the finding is the gate, not the threshold** |
| `clean` | 20,333 | 28.9% | 26.8% | in band |
| `pa` | 7,893 | 11.2% | 10.4% | in band |
| `disp` | 4,308 | 6.1% | 5.7% | in band |
| `all` | 70,319 | 100.0% | 92.6% | the control, by definition |

Counted on the **committed** book (`research/bt2y_trades.json`, 70,319 X rows) so the number is
comparable with everything else published against it; §2's "signals the arm's condition
reached" is the same count inside each arm's own shorter-window book (20,135 for `clean`
against 20,333 here), which is why the two differ slightly.

`br` trips on 93.6% of the vetoed pool. Method rule 3 says that is a statement about
`_grade_pa`, not about break-and-retest: **a veto that refuses 93.6% of the B&R signals it
sees is not separating anything.** That is consistent with what `_grade_pa` is — a candle-shape
test — and with T1's finding that the engine reaches Austin's setup and grades it X.

### And the gate that actually binds is the stop guard, not the grade

`research/t10_x_lift_fitted.py guard --arm clean` replays each of his 40 card-days and records,
for every signal that satisfies the lift condition, whether it also cleared `_min_viable_stop`:

| at the `clean` arm | his 13 S/A/C | his 27 `no` |
|---|---:|---:|
| produce a qualifying signal **at the minute he named** | 11 | 8 |
| of those, clear the stop guard | **1** | 0 |
| **blocked by the stop guard** | **10** | 8 |

`_min_viable_stop` is two independent clauses, and both bite:

- **range clause** — the stop may not sit inside one typical candle
  (`risk ≥ 0.75 × avg range of the last 10 bars`). **2 of 11 pass.**
- **width clause** — `risk ≥ 0.5% of entry` OR estimated premium risk `≥ $0.20`.
  **1 of 11 passes.**

The stop widths the engine proposes on the bars he graded:

| card | his grade | engine's stop, % of price |
|---|---|---:|
| `MARA_2026-03-10` | S | **0.000** |
| `PLTR_2026-05-27` | S | **0.000** |
| `QQQ_2026-05-07` | C | 0.007 |
| `GOOGL_2025-08-28` | A | 0.014 |
| `IWM_2024-10-15` | S | 0.031 |
| `NVDA_2025-01-17` | A | 0.034 |
| `GOOGL_2025-04-17` | C | 0.039 |
| `MSFT_2024-09-11` | C | 0.041 |
| `ACHR_2025-12-19` | S | 0.124 |
| `TSM_2026-01-09` | S | 0.125 |
| `AAPL_2025-08-01` | C | 0.307 ← the only one that fires |

Narrowest qualifying signal at his minute where a bar carried more than one (`MARA` had 2,
`NVDA` 3 at 0.034 / 0.163 / 0.236). Median 0.034%; a 0.034% stop on NVDA is about four cents.
Two are zero-width: entry and stop are the same price, so `R = |entry − stop| = 0` and the
trade is undefined. **This is not a grading problem
and no lift can reach it. The engine's stop PLACEMENT on the setups he calls S is the
defect**, and the same guard is what keeps the two-cent-stop artefact out of the book — so it
cannot simply be relaxed. Relaxing it reproduces `on_all`'s +7.4974R fiction.

At book scale the same ratio holds: `clean` promotes 20,135 signals and 19,403 (96.4%) die on
the guard. **The lift is only reaching 3.6% of what it was designed to reach**, and that 3.6%
is where the entire +5 recall came from.

---

## 5. The control search — what a *fitted* rule reaches on 13 positives

Exhaustive over single terms and pairs, drawn from at-detection book fields only. Look-ahead
fields are excluded by name (`drange`, `dret`, `rangeb`, `bars`, `out`, `r`, `exit`, `pnl`,
`scaled`, `traded`, `spy_trend`, `vol_regime`); `seq` is excluded because arrival order is not
stable under the very intervention being measured. Rules lifting fewer than 5 of 40 are
dropped as card lists.

| rank | terms | n | his S/A/C | precision | recall |
|---:|---|---:|---:|---:|---:|
| 1 | `dir==call & stopb==tight` | 14 | 9 | 64% | 69% |
| 2 | `dir==call & stop_pct<0.15` | 14 | 9 | 64% | 69% |
| 4 | `stopb==tight & tag:clean` | 18 | 10 | 56% | 77% |
| 9 | `dir==call & tag:clean` | 12 | 8 | 67% | 62% |

**The best two-term fitted rule reaches 64% precision. `pa` — a clause of his own sentence —
reaches 64% on the same rows.** The search buys nothing, and what it does buy is visibly
spurious: the top three rules are all `dir == call`, i.e. *"only take longs"*, which is a
40-row artefact (his S/A/C cards happen to be 9 longs). Rules 4–8 are five spellings of the
same two conditions. **This is what overfitting on 13 positives looks like, and it is the
reason the shipped arms are his sentence and not the search's answer.**

---

## 6. What ships

**Ship `X_LIFT` as a flag. Default it `off`, and hand `clean` to T22/T23 as the arm to stack.**

| | |
|---|---|
| **money gate** | not reached and not moved. Mean R +0.4952 against a target of 2.0; the move is null. |
| **recall gate** | 52.9% → 67.6% on the S-sweep, p = 0.031, precision up 4.4 points. Target is 90%. |
| **durability gate** | 25/25 months green, unchanged. |

Why default OFF rather than ON, when the recall move is real and the money move is null:

1. This is **not a ratified item**. R3 ("Ther is no B") lifts the *OCR demote*, which T0
   already landed; nothing in the RATIFIED table says to lift `_grade_pa`'s vetoes.
2. **`research/p23_combined_arms.md` already saw a stack underperform its parts.** Twelve
   lanes have now run single-lever A/Bs and zero combinations. T22 adjudicates; T23 stacks.
3. The finding in §4 says the lever is **operating on 3.6% of its intended population**. Its
   measured effect will change once the stop-placement question is answered, so freezing it ON
   now would freeze a number that is about to move.

`DIRECTION.md` records that *"routing stays legacy until T10 or T11 beats 52.5% held-out
recall"*. On the S-sweep, `clean` reads **67.6%** against `off`'s 52.9%. That clears the number
as written. It does **not** clear the other 52.5% in this repo — W1's *grade-agreement* floor,
where always guessing `X` scores 52.5% on the 59 rows he graded — and those two figures should
be disambiguated in `DIRECTION.md` before anyone throws the routing switch on the strength of
this line.

---

## 7. Caveats — what did not run, and what is an estimate

1. **The window is 500 sessions ending 2026-08-10, not 2026-08-21.** The committed book
   (`research/bt2y_trades.json`, 75,953 signals / 2,595 traded / +0.5481R) was generated in the
   main working copy, whose `data_archive/` carries 11 sessions that are not committed and are
   therefore absent from this worktree. My `off` control reads **74,988 / 2,548 / +0.5378R** on
   the same command. **All six arms share that window**, so every comparison here is
   like-for-like; but do not read my `off` column against T0's published numbers.
2. **2 of the 100 S-sweep cards and 2 of the 40 veto cards cannot be replayed** here for the
   same reason (`INTC_2026-08-17`, `AVGO_2026-07-23`, both his `no`). Identical in every arm.
3. **The fit's precision is an upper bound, not the arm's behaviour.** The book-row predicate
   scores the lift *condition*; the engine also requires `_min_viable_stop`, which no book row
   can evaluate. §4 measures the gap rather than modelling it, and the gap is 96.4%.
4. **The arm books are not committed** (67 MB each). Regenerate any of them with
   `python research/t10_x_lift_fitted.py books --arms clean`; every number in §2 comes from
   `research/t10_x_lift_fitted.py stats` over those files.
5. **`_grade_pa` itself was not touched.** This track lifts its output; it does not fix it.
   T2 owns the detector question.
6. **No options, contracts, spreads or futures.** Every number here is the underlying in R.
7. **One card, `TSLA_2025-05-15` (his `no`), joins to two book rows** at the same
   symbol/day/minute/setup and its level does not disambiguate. The first is used and it is
   reported by `fit` rather than dropped; it is a `no` card and both candidates are `late`, so
   no arm's decision turns on it.
8. **The exact McNemar p-values in §1 are one-sided binomials on (gained, lost)** — legitimate
   because no arm lost a single S day, which is itself the strongest single fact in the table.
9. **`_apply_x_lift` was refactored out of `_route` mid-run** so that the research replays,
   which override `_route` and do not delegate, could reach it. The three arm books produced
   before the refactor (`off`, `clean`, `disp`) were re-run afterwards and **every reported
   statistic matched exactly**; §2's numbers are from the post-refactor books.

---

## 8. Reproducing

```
python research/t10_x_lift_fitted.py verify     # predicate == engine, 75,953 rows x 6 arms
python research/t10_x_lift_fitted.py fit        # the 40 labels, leave-one-out, control search
python research/t10_x_lift_fitted.py books      # 6 x 2-year replay, ~10 min each
python research/t10_x_lift_fitted.py stats      # the §2 table
python research/t10_x_lift_fitted.py heldout    # the §1 table, 3 sets x 6 arms
python research/t10_x_lift_fitted.py guard --arm clean   # the §4 table
python research/test_t10_x_lift.py              # the six invariants
```

---

## 9. The bug this track hit, recorded so the next lever does not

The first cut put the lift inline in `SignalRunner._route`. Every book arm moved; **every
held-out number came back identical to `off`.** `backtest_week.BacktestRunner._route`
delegates to `super()._route`, so the books saw it — but
`research/t4_engine_recall.CaptureRunner._route` is a hand-rolled copy that does not delegate,
and that class is what `regression_gate`, `t70_test1_score` and `t0_heldout_recall` all replay
through. **The lever was inert in exactly the rig that decides whether a lever is good.**

This is the **sixth** instance of the unreachable-rule bug class in this repo
(`omen-rules-unreachable-in-code`), and the second time a `_route` copy was the cause —
`backtest_week` was fixed for the same reason in omen-5.0, which had silently made
`austin_tier`, `ENFORCE_NO_REPEAT`, `NO_REPEAT_ENTRIES`, the mesh S-veto, level retirement,
`S_GATE` and `RULE_710` inert in *every backtest ever run*.

The lift now lives in `SignalRunner._apply_x_lift`, called from both `_route`s, and
`research/test_t10_x_lift.py` §6 fails if either call disappears. **Eight further `_route`
overrides exist under `research/`** (`g12_attribute`, `g13_floor_fix_ab`, `t10_pivot_levels`,
`t11_s_quality`, `t3_session_extreme`, `t51_eye_match`, `t51_s_bar`, `w10_gate_autopsy`) plus
one in `test_austin_tier.py`, and none of them call it. They are single-purpose rigs that do
not score held-out recall, so that is correct today — but the next agent to add a routing gate
should walk that list before trusting a null.
