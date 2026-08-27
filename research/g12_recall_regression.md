# G12 — when the recall regression gate went red, and why

**Provenance.** Bisected with `research/regression_gate.py` as the test; attributed with
`research/g12_attribute.py`, written for this ticket and committed in _this commit_.
Measured at HEAD `76a15fce`, culprit `5e3677ea`, culprit's parent `49821550`.

---

## 1. The answer

| | |
|---|---|
| **culprit** | `5e3677ea` — *omen-5.0 T3/T4/T10/T11/T12: close-based stops + ladder B, session window + intrabar fill, pivot levels, S quality bar, 41 recovered marks* (2026-08-11) |
| **mechanism** | T3(b)'s intrabar fill (`signal_runner.py:677 fill_price`) moves the B&R entry off the bar close and onto the broken level. `stock_risk = entry - stop` collapses, and the **pre-existing** minimum-risk floor at `signal_runner.py:1657` (long) / `:1892` (short) forces `TradeGrade.D`. `D` is an alias of `X` (`omen_bot.py:33`), so the signal is `skipped_d` and never becomes an entry. |
| **verdict** | **Bug** — an incomplete mitigation, not a trade-off anyone chose. The commit author saw this hazard, said in writing it was not acceptable, and shipped a guard that covers only half of it. |
| **red for** | 16 days and **112 commits** (`5e3677ea..76a15fce`). |

The engine's detection is genuinely better — `any_signal` 60 → 75. Its *entry* on Austin's
S marks halved, 10 → 5. Detection up, entry down, and the instrument that would have said
so was never run.

---

## 2. The bisect

Good end is `beaf54fe`, the commit that locked `research/baseline_3.8.json` in the first
place. Bad end is HEAD. 118 revisions, 7 steps, `git bisect run`.

| tested | verdict | `current:` line |
|---|---|---|
| `3b3d53ab` | bad | any_signal 75, s_grade 5 |
| `ab97a267` | bad | any_signal 75, s_grade 5 |
| `4b980c74` | bad | any_signal 75, s_grade 5 |
| `45d0515d` | bad | any_signal 75, s_grade 5 |
| `103eb88c` | good | any_signal 64, s_grade 10 |
| `49821550` | good | any_signal 65, s_grade 10 |
| **`5e3677ea`** | **bad** | **any_signal 75, s_grade 5** |

The transition is one step wide: `49821550` → `5e3677ea`, `s_grade` 10 → 5, and the six
dropped keys at the culprit are byte-identical to the six at HEAD.

### Determinism, checked before blaming anyone

CLAUDE.md's G10 warning applies — `data_archive/` is shared and untracked, and a backfill
can move results independently of code. Two guards:

- The worktree's archive was **310 files behind** the main working copy when this started;
  it was synced to match before any measurement. Every missing file was 2026-07 or
  2026-08. Every mark in this corpus is 2024–2025, so the gap could not have reached them,
  and syncing did not change the result.
- `research/austin_marks_v2.jsonl` and `research/baseline_3.8.json` are both **tracked**
  and **unchanged** across `beaf54fe..76a15fce`. The gate's two inputs are frozen for the
  whole bisect range.

Re-run twice at each end:

| commit | run 1 | run 2 |
|---|---|---|
| `49821550` (parent) | any_signal 65, s_grade 10 — PASS | any_signal 65, s_grade 10 — PASS |
| `5e3677ea` (culprit) | any_signal 75, s_grade 5 — FAIL, same 6 | any_signal 75, s_grade 5 — FAIL, same 6 |

Deterministic. The culprit is code.

---

## 3. The mechanism, at file:line

### What the gate actually executes

`research/regression_gate.py` replays through `t4_engine_recall.CaptureRunner`, whose
`_route` **overrides** `SignalRunner._route` entirely. So `LEVEL_RETIRE_TOUCHES`,
`MESH_S_VETO`, `compute_austin_tier`, `ENFORCE_NO_REPEAT` and `NO_REPEAT_ENTRIES` are all
*absent* from the gate's path. What remains is: `detect_signals()` → `_emit` →
`_grade_for_levels` / `_calibration_grade` → grade-is-not-D → tight-stop check. A dropped
mark therefore has exactly two possible causes: the grade became `D`, or a `C` failed
`_min_viable_stop`. All six here are the first.

### The three lines

**1. The fill moves.** `signal_runner.py:677`, added by `5e3677ea`:

```python
def fill_price(level, candle, is_long, session_hi=None, session_lo=None) -> float:
    ...
    probe = {"entry": candle.close, "direction": "call" if is_long else "put"}
    if not bar_extreme_veto(probe, candle):
        return candle.close
    return min(max(level, candle.low), candle.high)
```

When the close sits inside `BAR_EXTREME_FRAC` (0.25, `signal_runner.py:364`) of the bar's
own extreme in the trade direction, the entry is taken **at the level** instead of at the
close — clamped into the bar's range. Called at `signal_runner.py:1638` (B&R long) and
`:1878` (B&R short).

This rule is Austin's, quoted in its own docstring: *"those candles that move fast and
close at high of day or low of day, i just want to try to not miss out."* It is not the
bug.

**2. The risk collapses.** `signal_runner.py:1641`: `stock_risk = entry - stop`. For
break-and-retest the structural stop **is** the broken level, so a fill at the level is a
fill at the stop.

**3. The floor rejects.** `signal_runner.py:1657` (long) and `:1892` (short) — **unchanged
by the culprit**, present verbatim at `49821550:1009` / `:1209`:

```python
if stock_risk < max(0.10, 0.0015 * current.close):  # relative min
    grade = TradeGrade.D   # T3(b): an intrabar fill sitting on the stop has no trade to size
```

It sits *after* every promotion, so it overrides the A+ stack's floor-B and the
confirmation-entry C. `TradeGrade.D` is an alias of `X` (`omen_bot.py:32-33`), which is why
the skip log reads `retest with X PA` — that is the floor overwriting the letter, **not**
`_grade_pa` changing its mind. `PriceActionAnalyzer.grade_trade` never reads the entry
price at all; `stock_risk` is the only entry-dependent input on that path.

**The guard that was supposed to catch this.** `signal_runner.py:775 intrabar_stop()`, in
the same commit, exists for precisely this hazard. Its docstring:

> *"223 of 744 B&R signals (30%) collapsed this way and were dropped by the minimum-risk
> gate. Silently losing 30% of the detector to a fill rule is not what T3(b) is for."*

But it triggers only on **full collapse** — `collapsed = (entry <= stop) if is_long else
(entry >= stop)`. A fill that merely *squeezes* the risk without reaching the stop is
invisible to it.

---

## 4. Per-mark attribution, all six

Parent `49821550` → culprit `5e3677ea`, at the bar inside the gate's ±2 tolerance. `floor`
is `max(0.10, 0.0015 × close)` evaluated at that bar. Every one is a `break_and_retest`.

| mark | bar | entry → | stop → | risk → | floor | `intrabar_stop` | grade |
|---|---:|---|---|---|---:|---|---|
| `GOOGL\|2024-10-15\|32` | 32 | 166.825 → **166.515** | 166.40 → 166.40 | 0.425 → **0.115** | 0.2498 | no-op (squeeze) | B → X |
| `IWM\|2025-04-10\|16` | 16 | 183.79 → **184.12** | 184.12 → **184.22** | 0.33 → **0.10** | 0.2762 | **fired** (collapse) | B → X |
| `IWM\|2025-12-01\|11` | 12 | 246.35 → **246.13** | 245.92 → 245.92 | 0.43 → **0.21** | 0.3692 | no-op (squeeze) | B → X |
| `IWM\|2025-12-04\|56` | 58 | 250.515 → **250.16** | 250.00 → 250.00 | 0.515 → **0.16** | 0.3752 | no-op (squeeze) | B → X |
| `QQQ\|2025-02-25\|16` | 17 | 516.65 → **517.26** | 517.75 → 517.75 | 1.10 → **0.49** | 0.7759 | no-op (squeeze) | C → X |
| `UBER\|2025-09-11\|15` | 15 | 95.155 → **94.75** | 94.75 → **94.6172** | 0.405 → **0.1328** | 0.1421 | **fired** (collapse) | B → X |

Six for six: `risk_after < floor ≤ risk_before`. Nothing else changed — same bar, same
level, same direction, same PA grader.

Two shapes, and the guard misses both:

- **Squeeze (4 of 6).** The level sits *outside* the entry bar's range, so `fill_price`'s
  clamp lands the fill exactly on the bar's own extreme — GOOGL 166.515 = bar low,
  IWM 246.13 = bar low, IWM 250.16 = bar low, QQQ 517.26 = bar high. `entry` never reaches
  `stop`, so `collapsed` is False and `intrabar_stop` returns the structural stop
  untouched. The squeezed risk falls under the floor.
- **Collapse (2 of 6).** The level sits *inside* the bar's range, the fill lands on it, and
  `intrabar_stop` **does** fire and moves the stop to the entry bar's extreme. The risk it
  restores is still under the floor — UBER by $0.0093, IWM by $0.176. The mitigation runs
  and is not enough.

`IWM|2025-12-04|56` also lost its PMH twin on the same bar (0.505 → 0.15, C → X).

---

## 5. Two A/Bs that pin it

Both at HEAD `76a15fce`, via `research/g12_attribute.py`.

**`--ab-close-fill`** — put the pre-T3(b) fill back (`fill_price` → the bar close),
change nothing else:

```
baseline: any_signal 60, s_grade 10
current:  any_signal 75, s_grade 13
PASS: no baseline-fired mark went silent.
```

All 75 detections are kept and `s_grade` goes 5 → **13**. So the fill rule alone costs
**8 S entries** at HEAD, and all 112 commits since `5e3677ea` — P16's `HTF_BIAS_VETO`
default, P17's `STALE_BARS` 15→10, `b55bd9c9`'s confluence relabel, the `_grade_pa` work —
are gate-neutral. None of them is implicated.

**`--ab-stop-on-entry-bar`** — widen `intrabar_stop`'s trigger from "collapsed" to the same
minimum-risk floor the grader uses, so a squeeze also moves the stop to the entry bar's
extreme (Austin's own rule: *"stop loss at the bottom of the wick you entered"*):

```
current:  any_signal 75, s_grade 5
FAIL: 0 any_signal + 6 s_grade mark(s) no longer fired.
```

**Recovers 0 of 6.** The obvious fix is dead, and the reason is worth keeping: in the four
squeeze cases the fill already *is* the bar's extreme, so "stop at the entry bar's extreme"
resolves to the entry itself and the rule is degenerate.

---

## 6. Bug or trade-off

**Bug.** Specifically: a correct new rule, a mitigation scoped to the wrong half of its
failure mode, and no gate run to catch the rest.

Reasons, in order of weight:

1. **The author stated the opposite intent, in the same commit.** `intrabar_stop`'s
   docstring calls losing detector output to the fill rule *"not what T3(b) is for"* and
   measures the damage at 30% of B&R signals. Losing 8 S entries is the thing the commit
   was trying to avoid, not something it chose.
2. **The guard covers the collapse case only.** Four of the six are squeezes it cannot
   see, and the two collapses it does see still land under the floor. Under-scoped and
   under-powered.
3. **`research/regression_gate.py` was never run.** Not by `5e3677ea`, not by any of the
   112 commits since. It is wired into no CI and no `verify:` line. `research/g3_onwatch_2y.md`
   line 116 noticed the failure and correctly placed it in "a commit, not a working-tree
   edit", but never bisected it — so several sessions of measurement sat on a red gate.
4. **The floor and the fill rule are structurally incompatible on expensive, quiet
   symbols.** The floor is 0.15% of price, so it is *largest* exactly where a B&R stop at
   the level is *tightest*. Four of the six lost marks are index ETFs — IWM ×3, QQQ ×1 —
   with floors of $0.28–$0.78 against structural risk of $0.10–$0.49. This is not a
   judgement about setup quality; it is a unit mismatch.

What is *not* a bug, and should not be reverted: the fill rule itself. It is Austin's, in
his words, and it is the whole point of T3(b).

### The smallest fix — Austin's call, not this report's

**Evaluate the minimum-risk floor on the structural geometry, not on the improved fill.**
`stock_risk` should be measured from the pre-fill (close) entry to the stop; `fill_price`
should only improve the price actually paid. The floor exists to reject setups with *no
room to size*. An intrabar fill that gets a better entry does not make a setup unsizeable —
it makes it better, and the R denominator it is judged on should not shrink because the
fill improved.

That is two lines at `signal_runner.py:1657` and `:1892`, not a revert.

**Caveats on the number.** `--ab-close-fill` reverts the entry everywhere, including for
`_grade_for_levels` and `_min_viable_stop`, which also read `sig["entry"]`. So **13** is the
measured bound for *"revert the fill"*; the exact recall for *"keep the fill, floor on
structural risk"* needs its own A/B. And these six are only what a 159-mark gate can see —
`intrabar_stop`'s own measurement puts the population-wide cost at 30% of B&R signals, so
the true recall bill is larger.

**Nothing here has been changed.** Re-freezing the engine voids the forward book
(`research/omen6_forward.py`), and anything that moves what trades is Austin's decision.

---

## 7. Reproduce

```bash
python research/regression_gate.py                       # FAIL: 6 dropped s_grade
python research/g12_attribute.py --out research/_g12_head.json
git checkout 49821550 && python research/g12_attribute.py --out research/_g12_parent.json
git checkout 76a15fce
python research/g12_attribute.py --diff research/_g12_parent.json research/_g12_head.json
python research/g12_attribute.py --floor research/_g12_head.json      # risk vs floor
python research/g12_attribute.py --ab-close-fill                      # PASS, s_grade 13
python research/g12_attribute.py --ab-stop-on-entry-bar               # FAIL, 0 of 6 back
```

Sync `data_archive/` with the main working copy first; a stale archive is a confound the
gate cannot distinguish from a code change.

**Noted in passing, not fixed here:** `python research/test_provenance.py` is already red at
`76a15fce` on three tracked reports that predate this ticket — `a1_threshold_sweep.md`,
`g10_arming_funnel.md`, `p26_intrabar_ambiguity.md`, each missing the commit. This file is
not among them. Those three belong to their own tickets.
