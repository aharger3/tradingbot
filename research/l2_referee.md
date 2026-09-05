# L2 referee — REFUTED

Row L2, OMEN 10.0, flag `RULE84_DECIDED`. Builder commits **`7fb977f7`** (flag lands OFF)
and **`5306416e`** (the gate readout, `research/l2_rule84_decided.md`). Referee script:
`research/l2_referee.py` (this commit) — it re-types the day-policy unit, the month
arithmetic and the no-regression gate rather than importing `research/loop_cycle.py` or
`research/g72_suppress_price.py`, so a bug in the builder's rig cannot reproduce itself in
the check.

**Verdict: refuted.** The builder's *decision* (hold, flag stays OFF) survives — it holds on
both pools — but **every gate number the row published is the wrong lane**, and the funnel
table's fire counts are 4.4x too high. Nothing here is deleted; the books stand and the
correct numbers are below.

Base check at referee time: `git merge-base --is-ancestor 1539dd7f HEAD` ok, HEAD =
`origin/main` = `5306416e`.

---

## What is right (checked, not taken on trust)

**Semantics match the settled sentence, exactly.** `research/omen_recall.py` returns, from
`omen-10-0-spec.md` "What the call settled" and `omen-rulebook.md ## Decided 2026-09-05`:

> "84 is a **name only** (the lesson's stat), no threshold. Arms **only after a stopped S or
> A original**. Reclaim = close back at the original entry within **25% of the previous
> candle's range**; two attempts; **same session, before 11:00**."

Line by line against the code at `7fb977f7`:

| the sentence | the code | ok |
|---|---|---|
| arms only after a stopped S or A original | `backtest_week._arm_84`: `grade_ok = _sgrade_84(t, runner) in ("S", "A")` — Austin's ladder via `downgrade.score`, not the legacy A+/A one | yes |
| reclaim within 25% of the **previous** candle's range | `signal_runner._reclaim_gate_ok`: `abs(close - entry_price) <= BAR_EXTREME_FRAC * (prev.high - prev.low)`, `BAR_EXTREME_FRAC = 0.25` | yes |
| …the *previous* candle | call sites pass `self.candles[-2]`; both 84% blocks set `current = self.candles[-1]` (line 3010), so `[-2]` is genuinely the bar before — **no off-by-one** | yes |
| two attempts | `RULE84_MAX_ATTEMPTS` default `2`, enforced by the existing `caps_ok` — no new flag | yes |
| same session, before 11:00 | `SESSION_END` default `"11:00:00"`, same `caps_ok` — no new flag | yes |

Not an adjacent rule. Its unit is also genuinely new: `RULE84_RECLAIM_TOL` is in R
(entry-to-stop) units and was left alone, as the row instructed.

**Default matches the decision.** `RULE84_DECIDED = os.getenv("RULE84_DECIDED", "0")` — OFF,
a research arm, consistent with "hold". It is in `research/book_stamp.py` `FLAG_SOURCES`.

**Books are clean and honestly paired.**

| | book_id | commit | dirty py | window | sessions |
|---|---|---|---|---|---|
| baseline (`loop.json`) | `2c39ced2697c26cc` | `29e4abc6` | 1 | 2024-09-04..2026-09-04 | 499 |
| `book_RULE84_DECIDED_off` | **`2c39ced2697c26cc`** | `7fb977f7` | 0 | same | 499 |
| `book_RULE84_DECIDED_on` | `a50f2552c34dd158` | `7fb977f7` | 0 | same | 499 |

OFF reproduces the baseline fingerprint to the byte — the landing changed nothing with the
flag off. OFF→ON differs in **exactly one** stamped flag: `signal_runner.RULE84_DECIDED
False → True`. `7fb977f7` is an ancestor of the row's commit `5306416e`.

**The ON book reproduces.** I rebuilt it myself —
`RULE84_DECIDED=1 python backtest_2y.py --days 730` at `5306416e`, log
`research/tape/logs/l2ref_rebuild_on.log` — and got `book id a50f2552c34dd158`, 127,171
signals, 4,027 traded, 499 sessions: identical to the builder's ON book. (The 132 MB raw
JSON was deleted after the id check; the stamped `.json.gz` already in the tape is the same
book.)

**Verify gate, run by me at `5306416e`:** `regression_gate.py` PASS (no baseline-fired mark
went silent), `test_runner_stop.py` ok (70 checks), `test_universe_single_source.py` ok
(29 symbols, no private lists). **No mark file touched** by either commit
(`git show --name-only` on both: only `backtest_week.py`, `signal_runner.py`,
`research/book_stamp.py`, `research/l2_rule84_decided.md`, the two books, `cycles.md`,
`loop_state.json`).

---

## Defect 1 — the gate ran on the full 28-symbol pool, not the core-11 lane it names (material)

`research/tape/loop.json` declares `universe: {slice: "core11", row_filter: 'tier ==
"core"', symbols: [the 11]}`. **`research/loop_cycle.py` never applies it.** The word
`core` does not appear in that file outside its docstring; `compute_all()` passes the whole
`rows` list straight to the unit function. So the row's headline table — presented as
"Unit = `up_to_3_stop_win_or_2loss` on `universe.CORE_SYMBOLS` (core-11), his day policy" —
is the full-pool slice.

Re-derived with `research/l2_referee.py`, fill = close, exit = shipped engine (1R hard stop,
`DISASTER_STOP_R=1.0`, `SCALE_PLAN=hod_then_runner_be`, `LOSS_HALT` on), unit =
up to 3 fires a day / stop after a win or 2 losses, 1R = $1,000:

| pool | slice | trades | $/day OFF→ON | green OFF→ON | gate |
|---|---|---:|---:|---:|---|
| **full 28** (what ran) | whole | 773 | −$9 → −$16 | 12/25 → 12/25 | — |
| | H1 | 378 | $72 → $58 | 8/12 → 8/12 | fail |
| | H2 | 395 | −$89 → −$89 | 4/13 → 4/13 | pass |
| **core 11** (what it names) | whole | 769 | **−$52 → −$57** | **11/25 → 11/25** | — |
| | H1 | 382 | **+$9 → −$8** | 6/12 → 6/12 | **fail** |
| | H2 | 387 | **−$111 → −$106** | 5/13 → 5/13 | pass |

The core-11 OFF arm reproduces R3's published baseline **to the dollar** — `loop.json`
`baseline_figures`: whole 769 trades / −$52 / 11 green, H1 382 / +$9 / 6 green, H2 387 /
−$111 / 5 green. The full-pool OFF arm does not (773 / −$9 / 12 green). That is the proof
of which slice is the baseline: **the numbers the row published are not on the baseline the
row says they are on.**

Consequences:

- The decision is unchanged — **hold on either pool**, H1 fails both times.
- But the *reason* changes. Published: "H1 $72 → $58, −19.4%". On the lane the spec settled,
  H1 goes **+$9 → −$8** — a sign flip from a marginally green half to a red one, not a
  percentage haircut. The whole-book move is −$5/day, not −$7.
- The ntfy line Austin received carries the full-pool `−9 → −16` figures. Its wording is
  plain English (the label, no flag name — that part is right); its numbers are the wrong
  lane.

This is the **same defect the L1 referee raised at `af028359`** ("gate ran on all 28
symbols, not the core 11 it names"). The L1 repair `d062da84` relabelled the L1 *report* and
left `loop_cycle.py` alone, so every subsequent L-row inherits it. **Fixing
`loop_cycle.py` to honour `universe.row_filter` is a separate row** (it is not L2's one
change) and should be dispatched before L3.

## Defect 2 — the funnel table's "fired" column is not fires

Published: "fired (all 29 syms) 542 → 200, fired/day 1.086 → 0.401", and "Core-11 slice: OFF
fires 238 (18 traded); ON fires 95 (9 traded)."

Counted from the same two books:

| | 84%-rule rows, any status | actually `status == "fired"` | traded |
|---|---:|---:|---:|
| OFF, all 28 | 542 | **124** | 56 |
| ON, all 28 | 200 | **39** | 20 |
| OFF, core 11 | 238 | **53** | 18 |
| ON, core 11 | 95 | **20** | 9 |

542 / 200 / 238 / 95 are total rows the detector emitted at any status (most are
`skipped_d`), not fires. True fires/day: **0.249 → 0.078**, not 1.086 → 0.401 — off by
4.4x. The report contradicts itself two paragraphs later: its "84% share of all fired
signals, 1.14% → 0.36%" is 124/10,873 and 39/10,798, i.e. computed from the *correct* fire
counts. The traded counts (56 → 20) and traded shares (1.38% → 0.50%) are right, and the
report correctly refuses a verdict on their mean R under the 30-trade floor.

The S/A/C original-grade join (326 → 15 C-graded originals) is, as the report itself says,
a nearest-match approximation with no stored key; I did not re-derive it and it carries no
verdict either way. The code path `_sgrade_84(t, runner) in ("S", "A")` is unambiguous on
its own.

## Defect 3 — the cycle was double-counted

`research/tape/cycles.md` carries the RULE84_DECIDED row **twice**, identical, and
`loop_state.json` records it as cycles 2 and 3 with identical figures. `consecutive_holds`
now reads **3** off **two** experiments, so the loop's "stop after 5 consecutive holds" is
one cycle nearer than the work justifies. Two build-stage logs exist
(`logs/l2_build.log`, `logs/l2_build2.log`), so the gate stage was run twice against the
same pair of books.

## One more thing the report should say and does not

`RULE84_DECIDED` is **one flag but two mechanisms** — the S/A arm gate and the
candle-range reclaim tolerance. The spec's own L2 row asks for both, so this is not a
one-change-per-row violation; but it does mean the H1 failure **cannot be attributed** to
either mechanism, and the write-up does not flag that. Separating them needs a second flag,
which is a second row.

The report also states "No conflicting reading turned up" from recall. `omen_recall.py`
on "84% rule arming reclaim tolerance" does return one:

> 2026-08-28, `omen-rulebook.md`, Batch 03 — *"The 84% rule arms on any grade … No grade gate
> at arming."*

The 2026-09-05 call supersedes it, so the code is right, but the rulebook line is now stale
and unmarked, and the report should have named it rather than claiming none existed.

## Sample sizes

Day-policy cells clear both floors on both pools and both halves (369–395 trades, 12 and 13
months). The 84% traded cells do not — 56 (OFF) and 20 (ON) all-28, 18 and 9 core-11 — and
the report correctly writes **"not enough"** there. No verdict is offered on the
re-entries' own mean R by the builder or by me.

## What should happen

1. Keep the hold. `RULE84_DECIDED` stays OFF — correct on either pool.
2. Correct `research/l2_rule84_decided.md`, `research/tape/cycles.md` and
   `research/tape/loop_state.json` to the core-11 figures above, and de-duplicate the cycle.
3. Open a row to make `loop_cycle.py` honour `loop.json`'s `universe.row_filter` before L3
   runs, and re-gate L1 and L2 from the books already in the tape (no rebuild needed —
   `research/l2_referee.py` does it in seconds).
