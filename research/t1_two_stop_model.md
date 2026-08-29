# T1 — the two-stop model, priced

**Null result: none of the four stop arms move mean R outside its own error bar
against today's clamp.** The disaster stop does exactly the job Austin
described it for — it caps the worst single trade at -1R (shipped default) or
-1.25R (swept), instead of the -6.06R tail a close-only stop with no floor at
all can book — but on this archive it does that by killing 1,444 (shipped) or
1,120 (swept) trades on an intrabar touch that a close-only stop would have
let run, and roughly 5-9% of those killed trades go on to recover to a WIN
under the close-only book. That give-up (**497R** shipped, **242R** swept)
very nearly cancels the R the cap saves, so mean R moves **-0.1321R**
(shipped) or **-0.1213R** (swept) against a **±0.134R / ±0.139R** bar — both
inside. **Durability moves the other way and is not inside any bar**: the
shipped -1R and today's clamp both hold 25 of 25 months green; moving the
disaster stop out to -1.25R drops one month red (24/25); removing the -1.25R
floor entirely drops two (23/25). Held-out recall does not move by
construction — the disaster stop is an exit rule, and detection is unchanged.

Reproduced by:

| artefact | what it is |
|---|---|
| `research/t1_two_stop_model.py` | all four arms, in one pass over the archive, plus the recovery-cost match and the held-out replay |
| `research/t1_two_stop_model.json` | its full output |
| `research/test_t1_two_stop_model.py` | 15/15 green, on hand-built rows |
| `research/test_t0_disaster_stop.py` | the mechanism itself (T0), 7/7 green, unchanged here |

This track does not touch `stop_rule.py` or `backtest_week.py` — the two-stop
mechanism was already shipped by T0 (`68e276ca`). T1 measures it.

---

## 1. The four arms, same 500-session window (2024-08-12 -> 2026-08-10, 28 symbols)

| arm | traded | mean R | win rate | months green | max DD (R) | worst trade | best trade |
|---|---:|---:|---:|---:|---:|---:|---:|
| **clamp** — today's clamp, no disaster stop, close-fill floored at -1.25R | 2,476 | **+0.6699** | 48.4% | **25/25** | 32.74 | -1.250 | +24.348 |
| **r100** — shipped default, disaster rests at -1R, touch-triggered | 2,548 | **+0.5378** | 42.8% | **25/25** | 32.43 | -1.000 | +24.348 |
| **r125** — disaster moved out to -1.25R | 2,507 | **+0.5486** | 46.0% | **24/25** | 34.82 | -1.250 | +24.348 |
| **nofloor** — no disaster stop AND no -1.25R clamp on the close-fill | 2,476 | **+0.5270** | 48.3% | **23/25** | **44.93** | **-6.063** | +24.348 |

None of the four reach the money gate (mean R >= 2.0) — this track prices the
exit's stop geometry, not the arithmetic gap `DIRECTION.md` already named
(mean R 2.0 is unreachable on a flat 2R target at this win rate; see
`Projects/omen-x-board.md`).

**clamp and nofloor trade the identical 2,476 rows** — confirmation that
removing the -1.25R clamp changes only what a trade BOOKS, never which trades
exist. r100 and r125 trade MORE rows than clamp (+72 and +31) because the
disaster stop exits some trades earlier in the day than a close-only stop
would have, which changes WHEN the 84%-rule re-entry (`backtest_week
._arm_84`, only armed on a full stop-out) gets a chance to fire inside the
9:30-11:00 window — sometimes creating a re-entry that would not have existed
under the clamp, sometimes losing one that needed the extra bars. This is a
real, mechanical side effect of a touch-triggered stop, not noise.

## 2. Error bar — every move is inside it

| comparison | move (mean R) | 95% bar | inside its own bar |
|---|---:|---:|---|
| r100 vs clamp (shipped default vs today) | -0.1321 | +/-0.1343 | **YES — null** |
| r125 vs clamp | -0.1213 | +/-0.1389 | **YES — null** |
| nofloor vs clamp | -0.1429 | +/-0.1437 | **YES — null** (by 0.0008R) |
| r125 vs r100 (which disaster placement) | +0.0108 | +/-0.1330 | **YES — null** |

Every mean-R read in this track is a null result by the project's own
standard (method rule 1). Nothing here says the disaster stop should ship or
should not — mean R cannot tell the two apart on this sample size. What DOES
move outside any comparable notion of noise is durability and tail risk,
neither of which the mean-R bar was built to capture:

| | clamp | r100 | r125 | nofloor |
|---|---:|---:|---:|---:|
| months green | 25/25 | 25/25 | **24/25** | **23/25** |
| worst single trade | -1.250R | -1.000R | -1.250R | **-6.063R** |
| max drawdown | 32.74R | 32.43R | 34.82R | **44.93R** |

`nofloor` is the pre-2026-08-28 world `research/x2_stop_floor_audit.md`
refuted from a different angle (the floor being unreachable code): here, run
for real with the floor actually absent, it is the worst arm on every
durability and tail measure and is not a live candidate — it exists in this
table as the counterfactual that shows what "no cap of any kind" actually
costs, which nobody had run end to end before.

## 3. The real cost: how often the disaster stop kills a trade that recovers

For every trade whose exit price matches its own disaster-stop price to the
cent (`out == "loss"` and `exit == entry -/+ stop_r * risk`), the identical
trade — same symbol, day, entry minute, setup, direction, entry price — is
looked up in the `clamp` arm, where that trade has no disaster order and
rides to its own close-triggered stop or its target. Method: `research
/t1_two_stop_model.py::recovery_cost`, checked in
`research/test_t1_two_stop_model.py` against a hand-built book with a known
answer.

| | r100 (-1R, shipped) | r125 (-1.25R) |
|---|---:|---:|
| disaster-stop exits | 1,444 | 1,120 |
| matched to a clamp-arm trade | 1,386 | 1,098 |
| unmatched (84%-rule re-entry timing shifted the trade set — see §1) | 58 | 22 |
| **would have recovered to a WIN under the clamp** | **125 (9.0%)** | **54 (4.9%)** |
| would have stayed a loss anyway | 1,256 | 1,043 |
| would have scratched | 5 | 1 |
| mean R given up per recovered trade | 3.97R | 4.48R |
| **total R given up** | **496.6R** | **241.7R** |

Read plainly: at the shipped -1R placement, roughly **1 in 11** of the trades
the disaster stop kills would have turned into a win if it had been allowed
to ride to the close-only stop instead, and those trades average +3.97R when
they do recover — that is the disaster stop's true price, and it had never
been measured before this track. Moving the resting order out to -1.25R
roughly **halves** both the count of recovered-trade kills (125 -> 54) and
the total R given up (497 -> 242), because it only intervenes on the bars
that actually gap through where the level stop already sits, rather than
sharing the level stop's own price (see T0's `austin_blocker`: at
`DISASTER_STOP_R=1.0`, the resting order sits at exactly `entry -/+ risk`,
which for most of this book IS the level stop's own price — R125 is the
version of this mechanism that does not collide with the level stop it sits
under).

## 4. Held-out recall — does not move, and cannot by construction

`signal_runner.SignalRunner.detect_signals` — the only code
`research/t4_engine_recall.run_day` (and the regression gate) replay — never
reads `DISASTER_STOP`, `DISASTER_STOP_R`, or `stop_fill_price` (grep-confirmed
against `signal_runner.py`). The disaster stop is an EXIT rule; it cannot
change which bar the engine enters on. Held-out recall is therefore
mechanically identical across all four T1 arms, and this track still ran it
once against the shipped state rather than merely asserting T0's number:

| set | recall | precision |
|---|---:|---:|
| `probe_s_sweep_2026-08-28` (100 blind cards, 34 S) | **18/34 = 52.9%** | 36.0% (32 of 66 non-S fire) |

Identical to T0's post-ratification figure (18/34, same 16 misses card for
card) — expected, and confirms nothing in T1 quietly touched detection.

## 5. What this means for the shipped default

The RATIFIED table is not open for re-litigation (`-1R is what we want max
slippage -1.25` ships DISASTER_STOP_R=1.0), and nothing here overturns it —
every mean-R move in this track is a null result, so there is no measured
case to change the number on money grounds alone. But three things are now on
the table that were not before T1:

1. **The -1R placement's true cost is a name and a number now**: it kills 125
   trades a year that would have recovered, for 497R given up, against a mean
   R move that does not clear its own error bar. The cap is not "free" — it
   trades a measured amount of upside for a tail-risk floor that a plain
   close-only clamp does not have.
2. **-1.25R is a strictly gentler version of the same cap** on every measure
   in this track except worst-single-trade (which matches the clamp's -1.25R
   anyway) and months-green, where it gives up one month (24/25) that the
   shipped -1R does not. It is not a free upgrade — it is a different point on
   the same tradeoff, with less recovery-kill cost and slightly worse
   durability.
3. **A resting order with no outer bound at all (`nofloor`) is worse than
   either disaster-stop placement on every measure that matters to the money
   gate** — worst trade, max drawdown, and months green all move against it.
   This is the one arm in the table that is not a live candidate; it exists
   to price what "no cap" actually costs, which had never been run end to end.

## What did not run

- No re-attribution of T0's other 26 ratified changes — this track holds
  everything else fixed at the shipped ratified config and only sweeps the
  stop model, per the spec's arm list.
- `unmatched_or_duplicate_key` (58 rows for r100, 22 for r125) are trades the
  disaster-stop arm's 84%-rule timing created or shifted such that no
  identical key exists in the clamp arm (see §1) — they are excluded from the
  recovery-cost denominator rather than guessed at, and are reported as their
  own line so the omission is visible, not silent.
- The archive on disk in this worktree tops out at 2026-08-10 for most
  symbols (`git ls-files data_archive/NVDA` confirms the last committed day);
  `research/bt2y_trades.json` (T0's committed AFTER book, mean R +0.5481)
  carries eleven more days (`last: 2026-08-21`) that were live-fetched and
  never committed. This track re-ran r100 itself rather than load that book,
  specifically so all four arms share one identical window — the ~0.01R gap
  between this track's r100 (+0.5378) and T0's published number (+0.5481) is
  archive-window drift, not a disagreement about the engine, and is called
  out here rather than silently reconciled.
- No options/contract instrument scoring — every number here is the
  underlying in R, same as every other track before T7.
