# L2 referee — pass 1 REFUTED · pass 2 UPHELD

> **Pass 2 (2026-09-05, a different model, told to refute) is at the bottom of this file.**
> It re-derived everything from the two stamped books with its own code
> (`research/l2_referee2.py`, `research/l2_referee2_join.py`), confirmed all three pass-1
> defects are genuinely fixed by builder repair commit **`d317ff43`**, and **upheld** the
> row — with four smaller defects named there. Pass 1 below is kept verbatim as the record.

---

# Pass 1 — REFUTED

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

---

# Pass 2 — UPHELD

Second referee pass, 2026-09-05, a different model, told to refute. Builder repair commit
**`d317ff43`** ("L2 repair: apply loop.json's universe.row_filter…"), on top of the pass-1
refutation `4f819bf6`, the original hold `5306416e`, and the flag-OFF landing `7fb977f7`.
Referee scripts, both committed with this write-up and both deliberately importing **nothing**
from `research/loop_cycle.py`, `research/g72_suppress_price.py` or pass 1's
`research/l2_referee.py`:

- `research/l2_referee2.py` — stamps, flag diff, the day-policy unit, months/halves, the
  no-regression gate, the funnel, and a read-back of `cycles.md` / `loop_state.json`.
- `research/l2_referee2_join.py` — the S/A/C original-grade join on a tighter key than the
  builder used.

Base check at referee time: `git merge-base --is-ancestor 1539dd7f HEAD` ok; `git status -sb`
= `## main...origin/main`, 0 ahead / 0 behind; HEAD = `d317ff43`.

**Verdict: upheld.** Every number the repaired row publishes reproduces under independent
code, to the dollar. All three pass-1 defects are genuinely fixed. The decision — **hold,
`RULE84_DECIDED` stays OFF** — is correct. Four smaller defects survive and are named below;
none of them moves the number or the decision.

## The three pass-1 defects, re-checked

**1 — Wrong lane. FIXED.** `loop_cycle.apply_universe_filter()` now reads
`loop.json`'s `universe.row_filter` (`tier == "core"`) and is called from `stage_gate` on
both arms before any arithmetic. I re-typed the filter, the unit and the gate myself and got
the repaired table exactly:

| slice | trades | $/day OFF→ON | mean R OFF→ON | green OFF→ON | gate |
|---|---:|---:|---:|---:|---|
| whole (25 mo) | 769 | **−$52 → −$57** | −0.0335 → −0.0371 | 11/25 → 11/25 | — |
| H1 (12 mo, <2025-09-01) | 382 | **+$9 → −$8** | 0.0057 → −0.0052 | 6/12 → 6/12 | **fail** |
| H2 (13 mo) | 387 | **−$111 → −$106** | −0.0722 → −0.0686 | 5/13 → 5/13 | pass |

Fill = **close** (both books stamp `entry_fill.ENTRY_FILL: "close"`). Exit = **shipped
engine**: 1R hard stop resting on the level, filled on the intrabar touch
(`DISASTER_STOP_R = 1.0`), `SCALE_PLAN = hod_then_runner_be`, `LOSS_HALT` on — all read off
the books' own stamps. Unit = **`up_to_3_stop_win_or_2loss`** (up to 3 fired-and-traded
signals a day in arrival order, stop after the first win or the second loss), core-11 rows
only. Sessions 499 / 248 / 251. 1R = $1,000. Script: `research/l2_referee2.py`.

The core-11 OFF arm reconciles to R3's published baseline in `loop.json` on all three
slices — 769 / −$52 / 11 green, 382 / +$9 / 6 green, 387 / −$111 / 5 green — **MATCH on
every cell**. The gate arithmetic is right too: H1 `+9 → −8` fails (`−8 < 9 × 0.95`), H2
`−111 → −106` passes (`−106 ≥ −111 × 1.05`, green 5 ≥ 5), so **hold**. The old full-pool
numbers the report now quotes as superseded (773 trades, −$9 → −$16, H1 $72 → $58, H2
−$89 → −$89, 12/25) also reproduce exactly, so the report's account of what it corrected is
accurate.

**2 — "Fired" column. FIXED.** Independently counted from the same two books:

| | 84%-rule rows, any status | `status == "fired"` | traded | traded mean R |
|---|---:|---:|---:|---:|
| OFF, full pool | 542 | **124** | 56 | +0.0613R |
| ON, full pool | 200 | **39** | 20 | +0.0362R |
| OFF, core-11 | 238 | **53** | 18 | −0.1103R |
| ON, core-11 | 95 | **20** | 9 | −0.1123R |

The report's corrected 124 / 39 / 53 / 20 and 56 / 20 / 18 / 9 are exactly these. Share of
all fired signals 1.14% → 0.36%, share of all traded signals 1.38% → 0.50% — also exact.

**3 — Double-counted cycle. FIXED.** `research/tape/cycles.md` now holds **one**
`RULE84_DECIDED` table row and it carries the core-11 figures. `loop_state.json`:
`cycle_count 2`, `consecutive_holds 2`, `history` length 2 (`MIN_PT1_R`, `RULE84_DECIDED`),
with a `_repair_note` recording what was removed. Nothing was deleted from the tape without
a note.

## The rest of the required checks, all run by me

- **Book identity.** OFF `book_id 2c39ced2697c26cc` **equals** `loop.json`'s
  `baseline_book_id` — the landing changed nothing with the flag off. ON is
  `a50f2552c34dd158`. The stamps differ in **exactly one** key:
  `signal_runner.RULE84_DECIDED: False → True`. Both stamped at commit `7fb977f7`,
  `dirty_py_count 0`, `dirty_engine_py []`, window 2024-09-04..2026-09-04, 499 sessions,
  built 19:33 and 19:37 on 2026-09-05 — same day, same base. `7fb977f7` is an ancestor of
  `d317ff43`. Neither `.json.gz` has been touched since `5306416e`
  (`git log -- <both books>`), so pass 1's byte-level rebuild of the ON arm still stands for
  these exact files.
- **The lane is the lane.** The 11 symbols carrying `tier == "core"` in the book are exactly
  `loop.json`'s list (AAPL AMD AMZN GOOGL META MSFT NVDA PLTR QQQ SPY TSLA). The book holds
  28 symbols in total.
- **Semantics match the settled sentence.** `omen_recall.py` and the spec's "What the call
  settled" row agree: *"84 is a **name only** (the lesson's stat), no threshold. Arms **only
  after a stopped S or A original**. Reclaim = close back at the original entry within **25%
  of the previous candle's range**; two attempts; **same session, before 11:00**."*
  `backtest_week._arm_84` under the flag: `grade_ok = _sgrade_84(t, runner) in ("S", "A")`
  (Austin's ladder via `downgrade.score`). `signal_runner._reclaim_gate_ok`:
  `abs(close − entry_price) <= BAR_EXTREME_FRAC * (prev.high − prev.low)`, with
  `BAR_EXTREME_FRAC = 0.25` and `prev = self.candles[-2]` where both call sites set
  `current = self.candles[-1]` (line 3010) — the *previous* candle, no off-by-one. Two
  attempts = `RULE84_MAX_ATTEMPTS` default 2; before 11:00 = `SESSION_END "11:00:00"`, both
  pre-existing. Not an adjacent rule.
  *One divergence from the spec's ticket text, resolved correctly:* the spec's L2 bullet
  (line 87) names `RULE84_ARM_SGRADE=1` "(S/A originals only)", but that existing flag is
  **S-only** in code. The settled table (line 37) is law and says S **or** A, so the new
  composite flag is the right resolution; the ticket line is the thing that is stale.
- **Default matches the decision.** `RULE84_DECIDED = os.getenv("RULE84_DECIDED", "0")` —
  OFF, a research arm, consistent with "hold". Present in `research/book_stamp.py`
  `FLAG_SOURCES` (and it appears in both stamps, which is the harder proof).
- **Sample size.** Day-policy cells clear both floors on both halves (769 / 382 / 387
  trades; 25 / 12 / 13 months). The 84% traded cells do not — 56 and 20 (full pool), 18 and
  9 (core-11) — and the report writes **"not enough"** there. No verdict is offered on the
  re-entries' own mean R, by the builder or by me.
- **The verify gate is green at `d317ff43`, run by me:** `regression_gate.py` exit 0
  (*"PASS: no baseline-fired mark went silent"*, new fires +5 any-signal / +20 s-grade, not
  a failure), `test_runner_stop.py` exit 0 (70 checks), `test_universe_single_source.py`
  exit 0 (29 symbols, 25 backtested, no private lists).
- **No mark file touched** by `7fb977f7`, `5306416e`, `4f819bf6` or `d317ff43`
  (`git show --name-only` across all four: zero hits on `*marks*`, `research/marks/**`,
  `mark_batch_*`, `recovered_reviews`, `marks_clean`, `derived_marks_v*`, `rule_ballot_*`,
  `austin_verdicts.json`). Working tree clean apart from this pass's own two scripts.
- **The push line is plain English.** `[OMEN] cycle 2: the 84% re-entry as decided on the
  call -- held. $/day -52.0 -> -57.0, green months 11 -> 11` — the label, not the flag name;
  no ticket ids.
- **The S/A/C join, re-done on a tighter key.** A re-entry row's `level_px` **is** the
  original entry price (`level_name == "not-his: prior entry (84%)"`), so I joined on
  symbol + day + `abs(original.entry − level_px) <= $0.01` + `out == "loss"` + earlier `et`,
  reading the original's `sgrade`. Result (`research/l2_referee2_join.py`), any-status rows:

  | | S | A | C | unmatched |
  |---|---:|---:|---:|---:|
  | OFF full pool (542) | 53 | 67 | **170** | 252 |
  | ON full pool (200) | 48 | 61 | **0** | 91 |
  | ON core-11 (95) | 26 | 29 | **0** | 40 |

  **C-graded originals go to exactly zero under the flag**, which is stronger than the
  builder's "15, the residue is join slop" and confirms the arm gate does what the code
  says. The builder's absolute counts (S 78 / A 138 / C 326 → S 69 / A 116 / C 15) do **not**
  reproduce under this tighter key; they were disclosed as approximate and the direction is
  the same, so this is a caveat on their precision, not a contradiction.

## Defects that survive (none move the number or the decision)

**D4 — the tape now mixes two lanes in one table (medium).** `cycles.md` row 1 is L1
(`MIN_PT1_R`, −$9 → $29, 12 → 12 green, 767 trades) priced on the **unfiltered 28-symbol
pool**; row 2 is L2 priced on **core-11**. Same table, same column headers, no marker
distinguishing them, and `loop_state.json`'s `history` carries the same mix. Anyone reading
the loop's own record will compare two different universes. The repair fixed the script for
everyone but re-gated only its own row — pass 1 asked for both. **Fix: a separate row that
re-runs `--stage gate` for `MIN_PT1_R` off the books already in the tape** (seconds, no
rebuild) and rewrites row 1 and its history entry.

**D5 — the row's own deliverable is published off-lane (medium).** The spec's L2 bullet asks
for "re-entries fired, their mean R, and how many originals were S vs A". The only mean R in
the report is the **full 28-symbol pool's** (+0.061R OFF → +0.036R ON). On the configured
lane it has the **opposite sign**: −0.1103R OFF → −0.1123R ON (core-11, 18 and 9 traded).
Both cells are under the 30-trade floor so neither carries a verdict either way, and the
report's table is honestly labelled "all 28 syms" — but after a refutation whose whole
content was "you priced the wrong lane", leaving the lane's own mean R unpublished, with a
sign flip hiding in it, is the same defect's shadow. **Fix: add the core-11 mean R row to
`research/l2_rule84_decided.md`, with the "not enough" note it already carries.**

**D6 — "All-29" on a 28-symbol book (minor).** The "84% share of the book" section says
"All-29" twice; the funnel table two paragraphs above says "all 28 syms". The book holds 28
symbols. The percentages themselves (1.14% → 0.36%, 1.38% → 0.50%) are correct.

**D7 — one change per row, stretched (process).** The repair added
`apply_universe_filter()` to `research/loop_cycle.py`, the shared measurement harness, inside
a row whose declared one change is a flag — after pass 1 said explicitly that this "is a
separate row … and should be dispatched before L3". It touches no engine file and neither
book, the corrected numbers reproduce, and the alternative (leaving every future L-row
mis-lane) was worse; but it silently re-bases every subsequent row's gate from inside L2, and
that is exactly how D4 came to exist.

**D8 — unverifiable: what Austin actually received (minor).** `stage_gate` pushes an ntfy
line unless `--dry-run`, and the gate stage ran at least three times against these two books
(two wrong-lane, one corrected). Nothing on disk records which pushes went out. If they did,
he saw "$/day -9.0 -> -16.0" for this experiment before he saw "-52.0 -> -57.0", with no
correction line. **Fix: `notify_ntfy` should append every push to a log, and a corrected
cycle should push a one-line "replaces the earlier figure" note.**

Two limitations the builder named and did not fix are correctly named and remain open: the
stale `omen-rulebook.md` Batch-03 line ("The 84% rule arms on any grade … No grade gate at
arming"), superseded by the 2026-09-05 call but not marked so; and `RULE84_DECIDED` bundling
the arm gate and the reclaim tolerance, so H1's failure cannot be attributed to either
mechanism without a second flag and a second row.

## Bottom line

The 84% re-entry, tightened the way the call settled it, does not clear the no-regression
gate on the settled lane: the first half of the two years goes from just-about-flat to
slightly negative, which is a fail however small it is, and the whole book moves −$5/day —
well inside the noise. Held, OFF, kept as a toggle column in the tape. That is the right
call and the arithmetic behind it now holds up under independent re-derivation.
