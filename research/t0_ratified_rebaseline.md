# T0 — the ratified re-baseline

**Headline. The book got BIGGER and more durable and WORSE per trade.** Landing
R1–R27 takes the two years from **1,017 traded to 2,595**, from **23 of 25 months
green to 25 of 25**, and from **+848.3R total to +1,422.3R** — while **mean R falls
+0.8341 → +0.5481 R** and win rate falls **53.1% → 43.1%**. The mean-R fall is
**−0.2860 R against a ±0.1725 R 95% bar**, so it is real and not a null result.

**And the gate that governs did not move at all.** Held-out S recall is
**18 of 34 = 52.9%** before and after, on the identical 34 cards, with the
identical 16 misses. Nothing in the RATIFIED table touched the thing OMEN is
actually blocked on.

Reproduced by:

| artefact | what it is |
|---|---|
| `research/t0_rebaseline.py` | the table below, from two books |
| `research/t0_rebaseline_table.md` | its full output, including month-by-month and symbol spread |
| `research/t0_heldout_recall.py` | held-out recall on both mark sets |
| `research/t0_heldout_recall.json` | its output (after) |
| `research/test_t0_ratified.py` | every ratified default asserted, with his words |
| `research/test_t0_disaster_stop.py` | R1/R2 on hand-built bars, 7/7 |
| `research/bt2y_trades.json` | the AFTER book (75,953 signals, 2,595 traded, 500 sessions) |

BEFORE is `backtest_2y.py --days 730` at `387ee2da`, re-run rather than quoted:
it reproduced the published book exactly — 45,193 signals, 1,017 traded, 500
sessions, +0.8341R, 53.1%, 23/25 green, PF 2.50.

---

## 1. The one table

| figure | before | after | move |
|---|---:|---:|---:|
| signals detected | 45,193 | 75,953 | +30,760 |
| **traded_count** | 1,017 | 2,595 | **+1,578** |
| **mean_r** | +0.8341 | +0.5481 | **−0.2860** |
| **win_rate** | 53.1% | 43.1% | **−10.0 pts** |
| total R | +848.33 | +1,422.33 | +574.01 |
| profit factor | 2.50 | 1.97 | −0.52 |
| **months_green** | 23 of 25 | **25 of 25** | **+2** |
| max drawdown | 14.94 R | 32.43 R | +17.49 R |
| wins | 537 | 1,110 | +573 |
| losses | 475 | 1,468 | +993 |
| scratches | 5 | 17 | +12 |
| worst single trade | −1.250 R | −1.000 R | +0.250 R |
| best single trade | +14.264 R | +24.348 R | +10.084 R |
| losses booked at exactly −1.000R | 14 | 1,460 | +1,446 |
| losses booked worse than −1R | 460 | 0 | −460 |
| losses clamped at the −1.25R bound | 303 | 0 | −303 |
| index (ETF) trades | 18 | 137 | +119 |
| premarket-level trades | 203 | 357 | +154 |
| symbols with at least one trade | 27 | 28 | +1 |
| **held-out S recall** (34 blind S cards) | 18/34 = 52.9% | 18/34 = 52.9% | **0** |
| held-out precision (100 blind cards) | 36.7% | 35.3% | see §4 |
| held-out recall on his 9 S+A vetoes | 0 of 9 | 0 of 9 | 0 |
| false fires on his 27 veto "no"s | 2 (7.4%) | 2 (7.4%) | 0 |
| traded, setup = break_and_retest | 947 | 1,704 | +757 |
| traded, setup = one_candle_rule | 67 | 572 | +505 |
| traded, setup = 84% re-entry | 3 | 319 | +316 |
| traded, level = PMH | 98 | 184 | +86 |
| traded, level = PML | 105 | 173 | +68 |
| traded, engine grade B | 1,000 | 2,447 | +1,447 |
| traded, engine grade A | 15 | 141 | +126 |
| traded, engine grade A+ | 2 | 7 | +5 |
| traded, his ladder S | 128 | 348 | +220 |
| traded, his ladder A | 251 | 570 | +319 |
| traded, his ladder C | 638 | 1,677 | +1,039 |

Every month, both books, and the full symbol spread are in
`research/t0_rebaseline_table.md`. The worst month in the after book is
**+6.01 R** (2025-09); the before book had two red months (2025-06 −9.47 R,
2025-09 −6.07 R).

## 2. Error bar

mean R moved **−0.2860 R**. The 95% bar on that move is **±0.1725 R**
(sd 2.395 → 2.337, n 1,017 → 2,595). **The move is outside its bar.** This is
not a null result; the book really is worse per trade.

For scale, the standing project figure is that no A/B has ever moved more than
±1.5799 R. This one is a re-baseline, not an A/B — it changes what trades, not
how a fixed set of trades is exited — which is why it clears its bar when
single-lever arms never have.

## 3. Where the 1,578 new trades came from, and what they are worth

| slice | trades | mean R | win rate |
|---|---:|---:|---:|
| whole book | 2,595 | +0.5481 | 43.1% |
| break-and-retest | 1,704 | +0.6024 | 47.4% |
| one candle rule (R3, R4) | 572 | +0.5913 | 37.7% |
| 84% re-entry (R6) | 319 | **+0.1804** | 29.3% |
| premarket level (R23) | 357 | +0.4849 | 42.0% |
| counter day trend (R21) | 249 | +0.3512 | 15.1% |
| with day trend | 2,346 | +0.5690 | 45.9% |
| index (ETF) | 137 | **+0.9266** | 56.6% |
| 2nd-or-later trade on its symbol-day (R16, R17) | 433 | +0.3744 | 31.9% |
| first trade on its symbol-day | 2,162 | +0.5829 | 45.3% |
| his ladder S | 348 | **+0.2671** | 42.7% |
| his ladder A | 570 | +0.6507 | 45.3% |
| his ladder C | 1,677 | +0.5716 | 42.4% |

Four readings worth naming, none of which T0 acts on:

1. **The 84% re-entry is the most dilutive lane in the book** — 319 trades at
   +0.18R. `research/p7_84_rule.md` predicted exactly this when it priced the
   open arm at +0.792R against a book mean of +0.955R; the book mean has since
   fallen, and the re-entries have fallen further. R6 is ratified and stays on,
   but T3's rewrite of the rule against Scarface's source is now the track that
   decides whether these 319 rows deserve to exist.
2. **Indices are the best slice in the book** — 137 trades at +0.93R and 56.6%
   win, the only slice that clears the money gate's win-rate half. R7 asked for
   more index trades; the ratified table produced 18 → 137 as a side effect, and
   they are better than everything else. T4 should read this before tuning
   anything.
3. **His own ladder is inverted against P&L.** Rows his downgrade count grades
   **S book +0.2671 R** and rows it grades **C book +0.5716 R**. That is not a
   grader that is merely unwired — on this book it is pointing the wrong way,
   and it is the ladder T10/T14 are proposing to route on. It has to be
   explained before it is trusted.
4. **Counter-trend trades win 15.1%.** R21 was right that the cap should not
   exist (see §5 — it was not doing anything anyway), and the observation it was
   replaced by is worth keeping: 249 rows, +0.35R, 15.1% win.

## 4. Held-out recall — the gate that governs, and it did not move

Scored by `research/t0_heldout_recall.py`, replaying through
`research/t4_engine_recall.run_day`, the same harness the regression gate and T1
use.

**Set 1 — `probe_s_sweep_2026-08-28`, 100 blind cards, 34 of them S.**

| | before | after |
|---|---:|---:|
| fires on his S days | 18 of 34 | 18 of 34 |
| recall | **52.9%** | **52.9%** |
| fires on his non-S days | 31 of 66 | 33 of 66 |
| precision | 36.7% | 35.3% |

The 16 missed S days are **the same 16 cards** in both books, card for card.
Doubling the traded book did not reach one extra S day.

The precision move is **not an engine change**: two cards, `BABA_2026-07-27` and
`COIN_2026-07-27`, have archive bars in the working tree that were not committed
at `387ee2da`, so the BEFORE replay could not run them and the AFTER replay
could. Both are graded "no" and both fire. On the 98 cards both books can
replay, recall and precision are identical.

**Set 2 — `probe_master_2026-08-29` lane `vetoes`, 40 engine vetoes he graded
himself: 5 S, 4 A, 4 C, 27 no.**

| | before | after |
|---|---:|---:|
| fires on the 5 he graded S | 0 | 0 |
| fires on the 4 he graded A | 0 | 0 |
| fires on the 27 he graded no | 2 (7.4%) | 2 (7.4%) |

**Zero of nine.** Every gate the RATIFIED table removed was a gate that was not
what stopped these. This is the single most useful negative in this report: it
says T10's "targeted X lift" cannot be built by taking more caps off, because
the caps are already off and the answer is still zero.

## 5. Reachability — two of the gates he deleted were already dead

Method rule 3: a gate tripping under 1% or over 85% means the finding is about
the gate.

| condition | before | after |
|---|---:|---:|
| chase trips as a downgrade | not recorded (variable did not exist) | **7.5%** |
| the counter-trend cap actually capped a signal | **9 of 45,193 = 0.02%** | n/a (deleted) |
| the level-block cap actually capped a signal | **37 of 45,193 = 0.08%** | n/a (deleted) |
| a level sits in the 2R path (now an observation) | — | 14.7% |
| counter day trend (now an observation) | — | 25.5% |
| scores S on his ladder, all signals | 16.5% | 13.1% |

His card for the counter-trend cap said it "trips on 89.5% of everything". That
is the rate at which the **condition** was true. The rate at which the **gate
changed a grade** was **0.02%** — because the cap only ran on signals already
graded above C, and `_grade_pa` grades 95% of signals X. `LEVEL_BLOCK_CAP` was
the same shape at 0.08%.

So **R21 and R25 are the fourth and fifth instances of this repo's recurring bug
class** (`omen-rules-unreachable-in-code`): a real rule of Austin's compiled into
a branch that could almost never be true. Deleting them is right and changes
almost nothing in the book. The observations they were replaced with — 25.5% and
14.7% trip rates — are in a range where they can actually separate something,
which is what makes them worth reporting.

`chase` as a downgrade variable trips **7.5%** of all signals: comfortably
reachable, neither dead nor a rubber stamp.

## 6. R1/R2 — the disaster stop, priced inside the stack

The disaster stop is the one ratified change that alters **every pre-existing
row**, not just which rows exist, so the before/after above is uninterpretable
without it. `DISASTER_STOP=0` re-runs the same after-engine with only the
resting −1R order removed:

```
DISASTER_STOP=0 python backtest_2y.py --days 730 --out /tmp/bt2y_nodisaster.json
python research/t0_rebaseline.py /tmp/bt2y_nodisaster.json research/bt2y_trades.json
```

(The 67 MB arm book is not committed — three two-year books in one commit is not
worth the repo weight when the two lines above regenerate it in about twenty
minutes. The script that made every number in it is committed.)

| figure | ratified, disaster stop OFF | ratified, disaster stop ON (shipped) | move |
|---|---:|---:|---:|
| traded_count | 2,521 | 2,595 | +74 |
| mean_r | +0.6824 | +0.5481 | **−0.1342** |
| win_rate | 48.6% | 43.1% | −5.5 pts |
| total R | +1,720.22 | +1,422.33 | −297.89 |
| profit factor | 2.13 | 1.97 | −0.16 |
| months_green | 25 of 25 | 25 of 25 | 0 |
| max drawdown | 32.74 R | 32.43 R | −0.31 R |
| worst single trade | −1.250 R | **−1.000 R** | +0.250 R |
| losses booked worse than −1R | 1,224 | **0** | −1,224 |
| losses clamped at the −1.25R bound | 758 | **0** | −758 |

**Error bar on that move: −0.1342 R against ±0.1331 R.** It clears its own bar by
under one percent. Read the SIGN as established and the SIZE as not.

So of the whole −0.2860 R fall in mean R, **the disaster stop is −0.1342 R and
everything else is −0.1517 R.**

It does exactly what he asked for. Without it, 1,224 of the ratified book's
losses book worse than −1R and 758 have to be clamped at the −1.25R bound; with
it, both are **zero** and the worst single trade in two years is −1.000R. The
−1.25R floor stops being a bookkeeping fiction. The bill is 74 extra losing
trades and 297.89 R.

### The collision T1 has to resolve, and it is not re-litigating anything

**At `DISASTER_STOP_R = 1.0` the resting order's price is the level stop's
price.** R is defined as `|entry − stop|`, so entry − 1.0 × risk *is* the stop.
Measured on the shipped book: **1,462 of 1,468 losses exit at exactly the stop
price and 1,460 book exactly −1.000R.**

The consequence is that a wick through the level now stops the trade out, and
`stop_hit_on_close` — the rule Austin settled five times, and the rule R2's own
verdict `both` preserves for the level stop — is unreachable in the shipped
configuration. That is worth **−5.5 points of win rate** on its own.

Both numbers in R1 are his and the spec's RATIFIED table is not open for
re-litigation, so this ships at `DISASTER_STOP_R = 1.0`. But it is a genuine
collision between two ratified items, and it is **the same reachability bug
class as §5 running in reverse**: a rule made unreachable by a constant rather
than by a branch. `DISASTER_STOP_R = 1.25` is the value at which the disaster
stop sits *underneath* the level stop — which is what the card he answered
literally proposed ("a disaster stop sitting underneath your level stop") — and
both rules survive. It is already a flag, and it is already T1's second arm.
**T1 should report the −1.25R arm beside the −1R one and put the choice in front
of Austin as one sentence: at −1R, wicks stop you out.**

## 7. What T0 did NOT land, and who owns it

Twelve of the 33 ratified items are measurement tracks, not configuration flips.
`research/test_t0_ratified.py` prints this list on every run so an unasserted
item is a visibly unlanded one:

| ratified | owner |
|---|---|
| R7 index quota | T4 |
| R8 symbol balance | T15 |
| R9 level target first, 2R fallback | T5 |
| R10 runner sizing / 50-20-20-10 | T5 |
| R11 break-even on movement | T11 |
| R19 candles beyond the hammer | T13 |
| R24 sweep the consolidation 0.5% | T16 |
| R28 real contracts | T7 |
| R29 strike sweep, futures / prop firms | T8, T17 |
| R30 spread and tight-RR filter | T9 |
| R31 loss halt in both paths | T20 |
| R33 confirm or bury FVG and flag | T19 |

Two more notes on what landed but did not move a number:

- **R12 (delete the 09:40 floor)** is a LIVE-path change only. `backtest_week`
  never had a time floor, so no backtest figure moves with it.
- **R13 (runners keep running)** was already true in the backtest — 324 of the
  2,595 traded rows exit after the 11:00 bar. The live path was the broken half:
  the scan loop slept outside `--window`, so a live runner was flattened by the
  clock at 11:00. `live_scanner.MANAGE_END` fixes that and is unmeasurable here
  by construction.

## 8. Gate status after T0

| gate | target | before | after |
|---|---|---|---|
| Recall | fires on ≥90% of his S days | 52.9% | **52.9% — unmoved** |
| Money | ≥55% win, mean R ≥ 2.0 | 53.1% / +0.8341 | **43.1% / +0.5481 — further away** |
| Durability | every month green | 23 of 25 | **25 of 25 — MET** |

One of the three gates is now met for the first time. The money gate moved
backwards. Recall did not move at all.

## 9. What this hands the next tracks

1. **The money gate is now a selection problem with a much larger candidate
   pool.** 2,595 rows at +0.5481R is +1,422R of gross material; before it was
   1,017 rows at +0.8341R. Every ratified gate is off, so what is left to build
   is a way to pick, not a way to un-block. That is T5, T10 and T23.
2. **T10 has to stop assuming the answer is a lift.** Zero of his nine S/A veto
   cards fire with every ratified gate removed.
3. **His downgrade ladder currently scores backwards on this book** (S +0.267R,
   C +0.572R). T14 must not throw the routing switch on the strength of a recall
   number without explaining that.
4. **Indices are the best slice at +0.93R and 56.6% win.** T4 opens on a
   different question than it was written for.
5. **The 84% re-entry lane is 319 trades at +0.18R.** T3's rewrite decides
   whether it survives.

## 10. The one thing only Austin can settle

**At −1R the disaster stop sits on the level stop, so a wick now stops him out.**
Ratifying `hard` at −1R and ratifying "level stop on the close" are, on this
engine's definition of R, the same price — 1,462 of 1,468 losses exit at the stop
price. He has settled "closes, not wicks" five times and he also settled this;
both cannot hold at −1R.

The action, phrased as an action rather than a question: **put the −1R and
−1.25R disaster-stop arms side by side and ask him to pick, with the one line
"at −1R a wick takes you out; at −1.25R your close rule survives and −1.25R
becomes a real order."** That is T1's deliverable and it is the only item in T0
that is genuinely blocked on him. Everything else in the RATIFIED table landed.

## Never claimed, never run

- No per-lever attribution beyond the disaster stop. Twelve gates came off in
  one commit series; only R1/R2 has an isolated arm here, because it is the only
  one that changes rows that already existed. Leave-one-out for the rest is
  T22/T23's job and each arm is a full two-year run.
- No options, contract, spread or futures scoring. Every number here is the
  underlying in R.
- `research/regression_gate.py` **PASSES**: detection went from 75 to 80 baseline
  marks (`any_signal +5`), S-grade fires unchanged at 5, and nothing that fired
  before went silent.
