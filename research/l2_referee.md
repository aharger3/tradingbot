# L2 referee — pass 1 REFUTED · pass 2 UPHELD · pass 3 REFUTED · pass 4 REFUTED

> **Pass 4 (2026-09-06, a fourth independent implementation) is at the very bottom of this
> file.** The gate, the funnel and the HOLD reproduce to the dollar for a third time, and
> the flag's semantics check out against raw archived bars on the correct candle. The
> repair commit `0866da4b` is **refuted** all the same: it left the pre-repair versions of
> two of its own five fixes standing in the report's closing section, its replacement
> explanation for the 15 residual C originals is disproved (all 15 have an S-or-A original
> at the identical price — it is the join's tie-break, not an `sgrade` timing effect), its
> "zero ambiguity" rests on a tautological test, and the false citation D13 removed from
> the markdown is still in `signal_runner.py`. Scroll to "Pass 4".

> **Pass 3 (2026-09-06, a third model, told to refute).**
> Every headline number and the HOLD decision reproduce exactly under a third independent
> implementation (`research/l2_referee3.py`, plus `l2_referee3_probe.py` and
> `l2_referee3_join.py`), and the flag's semantics check out against raw archived bars.
> The row is **refuted on its write-up**: `research/l2_rule84_decided.md` publishes two
> false sentences — a sample-size claim whose own arithmetic is wrong (56 is not under 30)
> and a "join slop" explanation an exact-key join disproves — and omits two real mechanics
> (the flag can ADD a fire; it moves 28 non-84% rows through the account-wide halt).
> Passes 1 and 2 are kept verbatim below as the record.

> **Pass 2 (2026-09-05, a different model, told to refute) is in the middle of this file.**
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

---

# Pass 3 — REFUTED (2026-09-06)

Row L2, OMEN 10.0, flag `RULE84_DECIDED`. Builder commits under review:
**`7fb977f7`** (the flag lands OFF), **`5306416e`** (the two stamped books),
**`d317ff43`** (the repair that produced the published numbers), refereed upheld at
**`3d168491`** (pass 2). The builder made **no new commit** in the invocation that
produced the report this pass reviews; it re-asserted the pass-2 state.

Referee scripts, all committed with this write-up and none of them importing
`research/loop_cycle.py`, `research/g72_suppress_price.py` or either earlier referee
script — the day-policy unit, the month arithmetic and the no-regression gate are
retyped from the spec's own sentences, so a bug shared by the builder's rig and the
first two referees cannot reproduce itself here:

| script | what it settles |
|---|---|
| `research/l2_referee3.py` | stamps, the whole gate, `cycles.md`, the funnel, isolation, the flag's semantics, the raw-bar tolerance audit |
| `research/l2_referee3_probe.py` | the three anomalies that audit surfaced, run down one at a time against `data_archive` |
| `research/l2_referee3_join.py` | the originals S/A/C table on an **exact** key instead of a nearest-match join |

Base check at referee time: `git merge-base --is-ancestor 1539dd7f HEAD` ok;
HEAD = `origin/main` = `378b17c6`.

**Verdict: refuted — on the write-up, not on the result.** Every headline number
reproduces to the dollar, the HOLD is correct, the flag does exactly what the settled
table says, and the books are clean. But `research/l2_rule84_decided.md` publishes
**two false sentences** and omits **two real mechanics of its own flag**, and the
builder's dispatcher summary repeats one of the false sentences verbatim. In this
swarm a row whose report states something untrue is written up as refuted even when
its number stands (the same standard pass 4 applied to L1) — so, refuted, and every
correct thing about it is recorded below rather than thrown away.

---

## What reproduces exactly (nothing here was taken on trust)

**The gate.** Unit `up_to_3_stop_win_or_2loss` — up to 3 fired-and-traded signals a day
in arrival order, stop after the first win or the second loss — on the core-11 slice
(`tier == "core"`), fill = **close** (both books' own `entry_fill` stamp), exit = the
shipped engine (1R hard stop, disaster order resting at 1R filled on the intrabar touch,
`SCALE_PLAN=hod_then_runner_be`, account-wide two-loss halt on), window
2024-09-04 → 2026-09-04, 499 sessions, halves split at 2025-09-01. Script:
`research/l2_referee3.py`. 1R = $1,000.

| slice | trades | $/day OFF→ON | mean R OFF→ON | green months | gate |
|---|---:|---:|---:|---:|---|
| whole (25 mo) | 769 | −$52 → −$57 | −0.0335 → −0.0371 | 11/25 → 11/25 | — |
| H1 (12 mo) | 382 | +$9 → −$8 | +0.0057 → −0.0052 | 6/12 → 6/12 | **fail** (dollar column) |
| H2 (13 mo) | 387 | −$111 → −$106 | −0.0722 → −0.0686 | 5/13 → 5/13 | pass |

Identical, cell for cell, to `research/l2_rule84_decided.md`, to
`research/tape/cycles.md`'s single `RULE84_DECIDED` row
(`hold | -52.0 -> -57.0 | 11 -> 11 | fail | pass | 769`) and to
`research/tape/loop_state.json`'s cycle 2. **Decision: HOLD** — reproduced.
Both halves clear the sample-size floor (382 and 387 trades, 12 and 13 months), so
both carry a verdict legitimately.

The OFF arm also reproduces `research/tape/loop.json`'s `baseline_figures` exactly
(whole and both halves), which is the independent proof that the OFF arm really is the
loop's baseline and not a re-measurement of something else.

**The books.** Both stamped at `7fb977f7`, `dirty_py_count: 0`, `dirty_engine_py: []` —
neither was built on a dirty tree. The OFF book's `book_id` is `2c39ced2697c26cc`, byte-equal
to `loop.json`'s `baseline_book_id`; the ON book's is `a50f2552c34dd158`. Diffing the two
stamps' full flag dictionaries returns **exactly one** differing key,
`signal_runner.RULE84_DECIDED`, `False → True`. `RULE84_DECIDED` is in
`research/book_stamp.py`'s `FLAG_SOURCES`. The books are committed at `5306416e`, and
`7fb977f7` (their stamp) is an ancestor of it, which is an ancestor of HEAD.

**The default matches the decision.** `signal_runner.py`:
`RULE84_DECIDED = os.getenv("RULE84_DECIDED", "0")…` — OFF, as a held research arm must be.

**The semantics.** The governing sentence, quoted from the spec's "What the call settled"
table (law, 2026-09-05):

> **84% rule** — 84 is a **name only** (the lesson's stat), no threshold. Arms **only after
> a stopped S or A original**. Reclaim = close back at the original entry within **25% of
> the previous candle's range**; two attempts; **same session, before 11:00**.

Checked clause by clause against the shipped code and, where it can be, against raw bars:

- *Arm gate.* `backtest_week._arm_84` under the flag is
  `grade_ok = _sgrade_84(t, runner) in ("S", "A")`, evaluated **before** every superseded
  `RULE84_*` reading, and `_sgrade_84` scores on `downgrade.score` — Austin's S/A/C ladder,
  not the legacy A+/A one. Correct.
- *Reclaim tolerance, unit.* `signal_runner._reclaim_gate_ok` returns
  `abs(close − entry_price) <= BAR_EXTREME_FRAC * (prev.high − prev.low)`, and
  `BAR_EXTREME_FRAC == 0.25`. A property test over a synthetic candle of range 2.00 puts
  the boundary exactly at ±0.50: 100.50 admitted, 100.51 refused, 99.49 refused. The
  "previous candle" really is the previous one — the call sites pass
  `self.candles[-2]` while `current` is `self.candles[-1]`.
- *A genuinely different unit from the old one.* `RULE84_RECLAIM_TOL` is still `None`
  (unbounded) and untouched; a close the shipped R-unit gate admits is refused by the
  candle-range gate. This row did not repurpose the old flag.
- *Two attempts, before 11:00.* `RULE84_MAX_ATTEMPTS == 2` and `SESSION_END == "11:00:00"`,
  both pre-existing defaults, both unconditional (not flag-gated) — so the flag correctly
  adds nothing here. Every 84% row's own reason string reads `[attempt 2/2]`.
- *Against the tape.* For all 39 ON-arm 84% fires, the reclaim bar was located in
  `data_archive` by its clock minute and its close matched the row's honest close fill.
  **38 of 39 satisfy `|reclaim close − original entry| ≤ 0.25 × previous candle's range`
  outright.** The 39th (ORCL 2025-01-02 10:59) reads 0.0600 against a 0.0575 tolerance
  using the book's stored `level_px` of 166.90 — but `level_px` is rounded to 2dp and the
  original entry's true value is the 10:35 bar's close, **166.895**, straight out of
  `data_archive/ORCL/2025-01-02.csv`. True gap 0.0550 ≤ 0.0575. **39 of 39.**
- *The gate is not a no-op.* 24 of the 124 OFF-arm fires sit outside the new tolerance.
  Of the 87 fires the flag drops, 24 fail the tolerance and 63 pass it — those 63 are the
  S/A arm gate's work.

**The funnel.** Re-counted from the books: 84%-rule rows at any status 542 → 200; fired
124 → 39; traded 56 → 20; core-11 fired 53 → 20, traded 18 → 9. Traded mean R
+0.0613R → +0.0362R (all-28). Every figure matches the report.

**The originals, on an exact key.** The report's join was disclosed as approximate. It need
not be: the 84% row carries `level_name = "not-his: prior entry (84%)"` and
`level_px = <the original's entry price>`, so the original is the same-symbol, same-day,
earlier row whose own `entry` equals that `level_px`. On that key
(`research/l2_referee3_join.py`) **525 of 542 OFF rows and 198 of 200 ON rows resolve, with
zero ambiguity**:

| originals, Austin's ladder | S | A | C |
|---|---:|---:|---:|
| OFF, all statuses (525 resolved) | 80 | 129 | 316 |
| ON, all statuses (198 resolved) | 72 | 111 | **15** |
| OFF, fired only (119 resolved) | 18 | 27 | 74 |
| ON, fired only (39 resolved) | 16 | 21 | 2 |

The arm gate does what it says: C originals collapse 316 → 15. The row's spec deliverable
("how many originals were S vs A") is **80 S / 129 A → 72 S / 111 A** at any status, and
**18 S / 27 A → 16 S / 21 A** on fires.

**Process.** The verify gate is green at HEAD, run here: `research/regression_gate.py`
PASS (no baseline-fired mark went silent), `research/test_runner_stop.py` ok (70 checks),
`research/test_universe_single_source.py` ok (29 symbols, no private lists). No mark file
appears in any of the three L2 commits' `--stat`, and none is modified in the working
tree. `7fb977f7` touches three files for one composite flag
(`signal_runner.py`, `backtest_week.py`, `research/book_stamp.py`), which is the one change
the spec's L2 bullet names.

---

## Defects

**D9 — the report's sample-size sentence is arithmetically false (medium).**
`research/l2_rule84_decided.md` states: *"Sample-size rule: neither traded column clears
30 trades. 56 (OFF) and 20 (ON) are both under the 30-trade floor this project holds every
verdict to."* **56 is not under 30.** The OFF cell clears the floor; only the ON cell (20)
is under it. The conclusion — "not enough" on the re-entries' own mean R — survives,
because the comparison needs both cells, but the sentence carrying it misstates this
project's own governing rule on this project's own published number, in the one section
whose whole job is to apply that rule. The builder's dispatcher summary repeats it
verbatim ("both under the 30-trade floor"). **Fix: "the ON cell (20 trades) is under the
30-trade floor, so the comparison carries no verdict; the OFF cell's 56 does clear it."**

**D10 — "the residue is join slop" is disproved by an exact join (medium).** The report
explains the 15 C-graded originals surviving the S/A arm gate as *"join slop, not a gate
failure"*. Under the exact `level_px` key — 198 of 200 ON rows resolved, **zero
ambiguous** — the residue is still exactly **15**. It is not join slop. The real
explanation is that the book's `sgrade` column is `downgrade.score` evaluated at the
original row's own entry, while `backtest_week._sgrade_84` re-scores the stopped trade at
**arm time** with the runner's then-current `htf_bias`; two different calls, so they can
disagree on a handful of borderline originals. That is a benign explanation too — but it
is a different one, and the published one is wrong. It also means the report's absolute
counts (78/138/326 → 69/116/15) should read 80/129/316 → 72/111/15. **Fix: replace the
join with the exact key and the explanation with the re-score one.**

**D11 — the flag is not purely subtractive, and the report says nothing about it
(medium).** Two of the 39 ON-arm fires **do not exist in the OFF arm**: ORCL 2025-01-02
10:59 and ACHR 2026-02-02 10:15. Mechanism, verified on raw bars: refusing an early
reclaim leaves the two-attempt budget intact, so the next qualifying bar fires instead.
At ORCL's OFF-arm attempt (10:58) the reclaim gap is 0.035 against 25% of the 10:57
candle's range (0.030) — refused — and 10:59 fires in its place. In the **core-11
day-policy candidate pool** the flag removes 84 rows worth +$1,792 and **adds 3**, all
three −$1,000 (MSFT 2025-04-29 10:52, AMD 2026-04-06 10:55, QQQ 2026-08-21 10:29). The
report's only characterisation is that the tightening *"roughly halves the re-entry
count"*. A tightening that can add a losing trade is exactly the kind of thing the next
agent needs told. **Fix: one sentence and the three symbol-days.**

**D12 — 28 non-84% rows move, undisclosed by the report and by both earlier passes
(medium).** Comparing the two books row for row, 28 rows that are **not** 84%-rule rows
flip `status`/`traded` between `halted` and `fired` — on 9 days
(2024-09-12, 2025-06-09, 2025-07-11, 2025-09-29, 2025-10-14, 2026-03-02, 2026-04-10,
2026-06-08, 2026-08-07). Every one of those 9 days carries an 84%-rule traded row that
differs between the arms, on a *different symbol* — the account-wide two-loss halt moving.
It is a downstream consequence of the one change, not a second change, and it is **inert
for this row's headline**: the core-11 day-policy candidate pool differs by exactly 84
removed and 3 added, **all of them 84%-rule rows**, with zero pnl differences on shared
keys, so 100% of the −$5/day delta is the 84% path. But it is **not** inert for the
`every_signal` unit the tape reports beside this one, where `traded` is the membership
test. Neither the report nor passes 1–2 mention it. **Fix: name it, and say which units
it can and cannot move.**

**D13 — the report cites an instruction the spec contradicts (minor).** The report says
the R-unit `RULE84_RECLAIM_TOL` was *"left alone, per this row's own instruction not to
reuse it"*. The spec's Phase-L bullet says the opposite: *"L2 — 84% arming
`RULE84_ARM_SGRADE=1` (S/A originals only), `RULE84_RECLAIM_TOL` = 25% of the previous
candle's range"* — it names the two existing flags. The **behaviour** is right, because the
"What the call settled" table is law and says S-or-A and 25%-of-the-previous-candle's-range,
and `RULE84_ARM_SGRADE` already means S-only while `RULE84_RECLAIM_TOL` already means R
units, so neither could carry the settled meaning without silently redefining a shipped
flag. Building a third flag was the right call. Justifying it with an instruction that is
not in the spec is not. **Fix: cite the settled table and the collision, not an
instruction.**

**D14 — the rulebook still returns the opposite rule first (carried forward, still open).**
`python research/omen_recall.py "84% rule arming grade gate"` returns, as its top hit,
`omen-rulebook.md` Batch 03, 2026-08-28: *"No grade gate at arming. The S filter at trade
time is the only grade gate."* and Austin's own words *"84 percent rule can fire on S A or
C, but we only will trade S of course."* That is the direct negation of the S/A arm gate
this row implements. The 2026-09-05 call supersedes it and the settled table is law, so the
code is right — but the recall tool, the first command every agent in this swarm runs, hands
the next agent the superseded sentence with no marker. The builder named this and correctly
declined to fix a file the row does not own; it stays open here because it is the single
most likely way this decision gets re-argued. **Fix: a one-line "superseded 2026-09-05" note
on that rulebook heading, as its own row.**

---

## What this pass does NOT establish

- Nothing about whether the 84% rule is good or bad. The whole-book move is −$5/day on 769
  trades — far inside the per-trade noise this project measures on every A/B. What decides
  the row is H1's dollar column, and H1 moves from +$9/day to −$8/day, which is a fail
  however small.
- Nothing about the re-entries' own edge. 56 traded re-entries OFF and **20** ON: the ON
  cell is under the 30-trade floor, so the +0.061R → +0.036R comparison carries **no
  verdict**. Same for the core-11 slice (18 and 9 traded, −0.1103R → −0.1123R).
- Nothing about which of the flag's two mechanisms causes H1's failure. It bundles the S/A
  arm gate and the candle-range tolerance; separating them is a second flag and a second
  row. The builder named this and it remains true.
- Nothing about the phantom-fill column or any unit other than the day policy and the raw
  fired/traded counts above.

## Bottom line

The decision is right and the arithmetic behind it survives a third independent
re-derivation, down to the cent and against the raw tape. The write-up around it is not
clean: it misstates the project's own sample-size rule on its own number, explains a real
residue with a cause an exact join disproves, and leaves out both of the flag's
side-effects — one of which is that the tightening can add a losing trade. `RULE84_DECIDED`
stays **OFF** and stays in the tape as a toggle column. Refuted on the report; the number
and the hold stand.


---

# Pass 4 — REFUTED (2026-09-06)

Second referee pass **after the repair round**. Builder repair commit under review:
**`0866da4b`** ("L2 repair: fix pass-3 referee defects in report"), on top of `7fb977f7`
(flag lands OFF), `5306416e` (books + first readout), `d317ff43` (pass-1 repair),
`3d168491` (pass 2), `6f477e89` (pass 3). Referee code committed with this write-up:
**`research/l2_referee4.py`** and **`research/l2_referee4_bars.py`** — a fourth
implementation that imports nothing from `loop_cycle.py`, `g72_suppress_price.py` or any
earlier `l2_referee*.py`; the unit, the month arithmetic and the gate are re-typed from the
spec sentence, and the semantics are re-checked straight off `data_archive/`.

Base check at referee time: `git fetch origin` ok; `git merge-base --is-ancestor 1539dd7f
HEAD` ok; `HEAD == origin/main == 0866da4b`; working tree clean apart from this pass's two
new files.

**Verdict: refuted — on the write-up again, not on the number.** The gate, the funnel, the
candidate-pool diff, the two novel ON fires and the nine halt-cascade days all reproduce.
The HOLD is right. But two of the repair's own five fixes are contradicted by the report's
closing section, the replacement explanation it published for the 15 residual C originals is
disproved, its "zero ambiguity" claim rests on a test that cannot fire, and the false
citation it removed from the markdown is still sitting in `signal_runner.py`.

---

## What reproduces (independently re-derived, not taken on trust)

**The gate.** Fill = close (`ENTRY_FILL` default). Exit = shipped engine: 1R hard stop
(`DISASTER_STOP_R=1.0` resting on the level, intrabar touch), `SCALE_PLAN=hod_then_runner_be`,
account-wide two-loss halt on. Unit = `up_to_3_stop_win_or_2loss` on core-11 (up to 3 taken
signals a day in arrival order, stop after the first win or the second loss). 1R = $1,000,
499 sessions 2024-09-04..2026-09-04. Script: `research/l2_referee4.py`.

| slice | trades | $/day OFF→ON | mean R OFF→ON | green OFF→ON | gate |
|---|---:|---:|---:|---:|---|
| whole (25 mo) | 769 → 769 | −$52 → −$57 | −0.0335 → −0.0371 | 11/25 → 11/25 | fail (−9.6%) |
| H1 (12 mo, < 2025-09-01) | 382 → 382 | **+$9 → −$8** | +0.0057 → −0.0052 | 6/12 → 6/12 | **FAIL** |
| H2 (13 mo, ≥ 2025-09-01) | 387 → 387 | −$111 → −$106 | −0.0722 → −0.0686 | 5/13 → 5/13 | pass |

Identical to the report, to the dollar and to four decimal places on mean R, and identical to
`research/tape/cycles.md`'s RULE84_DECIDED row (`-52.0 -> -57.0`, `11 -> 11`, H1 fail, H2 pass,
769 trades). Every cell clears the sample-size floor: 769 / 382 / 387 trades, 25 / 12 / 13
months. The core-11 slice was cross-checked two ways — the book's own `tier == "core"` column
and the literal `universe.CORE_SYMBOLS` list — and they agree row for row.

**Stamps.**

| | book_id | commit | dirty py / engine | window |
|---|---|---|---|---|
| baseline (`loop.json`) | `2c39ced2697c26cc` | `29e4abc6` | 1 / none | 499 sessions, 2024-09-04..2026-09-04 |
| `book_RULE84_DECIDED_off` | **`2c39ced2697c26cc`** | `7fb977f7` | 0 / none | same |
| `book_RULE84_DECIDED_on` | `a50f2552c34dd158` | `7fb977f7` | 0 / none | same |

Both stamped `book_id`s recompute correctly from the trade rows themselves
(`research/book_stamp.book_id`). The OFF book's fingerprint equals the baseline's exactly.
OFF→ON differ in **exactly one** stamped flag: `signal_runner.RULE84_DECIDED False → True`
(baseline→OFF differ only by two flags that did not exist when the baseline was built,
`MIN_PT1_R None→0.0` and `RULE84_DECIDED None→False`, both inert). `RULE84_DECIDED` is in
`research/book_stamp.py` `FLAG_SOURCES` (line 93). Neither book was built on a dirty tree.
`7fb977f7` is an ancestor of `0866da4b`.

**Default matches the decision.** `signal_runner.py:496`,
`RULE84_DECIDED = os.getenv("RULE84_DECIDED", "0") …` — OFF. The row held; a research arm
does not default on. Correct.

**Semantics against the rulebook, clause by clause.** `research/omen_recall.py "84% rule
arming grade gate reclaim tolerance"` returns, dated 2026-09-05, from
`Projects/omen-rulebook.md`'s Decided list (line 1915) and the spec's settled table:

> **84% rule:** 84 is a name only; arms only after a stopped S/A original; reclaim close
> within 25% of the previous candle's range; two attempts; same session before 11:00.

| the sentence | the code at `0866da4b` | ok |
|---|---|---|
| arms only after a stopped S **or A** original | `backtest_week._arm_84:860` — `grade_ok = _sgrade_84(t, runner) in ("S", "A")`, Austin's ladder via `downgrade.score` | yes |
| reclaim within 25% of the previous candle's range | `signal_runner._reclaim_gate_ok:499` — `abs(close - entry_price) <= BAR_EXTREME_FRAC * (prev.high - prev.low)`, `BAR_EXTREME_FRAC = 0.25` | yes |
| the *previous* candle, not two back | call sites pass `self.candles[-2]` while `current = self.candles[-1]` (`signal_runner.py:3095`) | yes |
| two attempts | `RULE84_MAX_ATTEMPTS` default `2` | yes |
| same session, before 11:00 | `SESSION_END` default `"11:00:00"` | yes |

**Checked against the raw tape, not just the source** (`research/l2_referee4_bars.py`, reading
`data_archive/<sym>/<day>.csv` only). Of the 39 fired 84% rows in the ON arm, **38 satisfy
`|reclaim close − original entry| ≤ 0.25 × previous bar's range`** on the immediately-preceding
bar. The one miss is ORCL 2025-01-02 10:59, gap $0.0600 against a $0.0575 tolerance — the
book stores `level_px` rounded to the cent, and pass 3 already showed it passes unrounded.
Crucially, the **off-by-one alternative is not a better fit**: zero ON fires pass only on the
two-bars-back reading, so the implementation is reading the candle the rule names. In the OFF
arm — where the tolerance is not applied — 24 fires sit outside it, which is exactly the shape
you would expect if the gate is real.

**The funnel.** All-28 archived pool, `status == "fired"` / `traded`:

| | 84% rows (any status) | fired | fired/day | traded | mean R (traded) |
|---|---:|---:|---:|---:|---:|
| OFF | 542 | 124 | 0.248 | 56 | +0.0613 |
| ON | 200 | 39 | 0.078 | 20 | +0.0362 |

Core-11: OFF 53 fired / 18 traded (−0.1103R); ON 20 fired / 9 traded (−0.1123R). All match
the report. **No verdict on the re-entries' own edge**: the ON cell is 20 trades, under the
30-trade floor. The OFF cell's 56 clears it — a comparison needs both, so the funnel says
*not enough*, and it says nothing about which arm's re-entries are better.

**The candidate-pool diff.** In the core-11 pool that feeds the day-policy unit (traded fires
plus halt-suppressed rows), the flag removes **84** rows worth **+$1,792** and adds **3**, all
three −$1,000 and all three 84% rows (MSFT 2025-04-29 10:52, AMD 2026-04-06 10:55,
QQQ 2026-08-21 10:29), with **zero** pnl differences on shared keys. Exactly as reported.

**The two novel ON fires.** ORCL 2025-01-02 10:59 (fired, not traded) and ACHR 2026-02-02
10:15 (fired, traded, −$1,000) exist in the ON arm and not in the OFF arm. Exactly the two
the report names, with the same traded/pnl split.

**The halt cascade.** 30 rows that are not 84% rows flip `status`/`traded` between the arms,
on the **nine** days the report lists (2024-09-12, 2025-06-09, 2025-07-11, 2025-09-29,
2025-10-14, 2026-03-02, 2026-04-10, 2026-06-08, 2026-08-07). The day list is exactly right.
(The count is 30 on a row key verified unique; see defect D17.)

**Verify gate, run by me at `0866da4b`:** `research/regression_gate.py` PASS ("no
baseline-fired mark went silent"), `research/test_runner_stop.py` ok (70 checks),
`research/test_universe_single_source.py` ok (29 symbols, no private lists).

**Mark files: none touched.** `git diff --name-only 7fb977f7^ 0866da4b` (which spans the
sibling rows that landed in between) matches nothing under `research/*marks*.jsonl`,
`research/marks/`, `research/mark_batch_*`, `recovered_reviews`, `marks_clean`,
`derived_marks_v*`, `rule_ballot_*`, `austin_verdicts.json` or `*-manifest.jsonl`.

**One change per row.** `7fb977f7` touches `signal_runner.py`, `backtest_week.py` and
`research/book_stamp.py` — one flag, `RULE84_DECIDED`, plus its stamp entry. `0866da4b` is
documentation only (`research/l2_rule84_decided.md`). Within budget. The flag does bundle two
mechanisms (arm gate + reclaim tolerance), which the spec names in one sentence and the report
discloses; H1's failure still cannot be attributed to one of them.

**Plain English.** The `cycles.md` row reads "the 84% re-entry as decided on the call" —
no ticket id, no flag name in the label. Fine for Austin.

---

## Defect D15 — the repair left the pre-repair version of two of its own fixes in the report (material)

`research/l2_rule84_decided.md`'s final section, "What this does NOT establish", was not
touched by the repair. It still reads, at lines 270 and 273:

> - Not enough trades (56 / 20, **both under 30**) to say whether S/A-gated re-entries carry
>   a better or worse mean R than ungated ones …
> - The original-grade join **is approximate (nearest match by price and time, no stored
>   link)** — a hint at the gate's effect, not an audited count.

Those are verbatim the two sentences D9 and D10 were raised against. The repair rewrote them
in the body — "the ON cell (20 trades) is under the 30-trade floor … the OFF cell's 56 does
clear it", and "This is now an exact key … replacing the earlier approximate nearest-match
join" — and then left the originals standing 150 lines further down, as the document's
closing statement. The report now asserts both readings of both facts. A reader who takes the
last section as the summary (which is what it is for) gets the false arithmetic and the
retracted join description. **56 is not under 30**, and the published join is not
nearest-match. Two of the five fixes the repair commit's message claims are not delivered.

## Defect D16 — "zero ambiguity" is asserted on a test that cannot fire, and the join is in fact tie-break-dependent (material)

The repaired table is captioned: *"On that key (`research/l2_referee3_join.py`), 525 of 542
OFF rows and 198 of 200 ON rows resolve with **zero ambiguity**."*

`l2_referee3_join.py`'s ambiguity counter is:

```python
cands = [q for q in ... if abs(float(q["entry"]) - float(lvl)) < 0.005]
...
if len({round(float(q["entry"]), 2) for q in cands}) > 1:
    ambiguous += 1
```

It selects candidates *because* their entry matches `level_px` to within half a cent, then
asks whether those candidates have different entry prices rounded to the cent. It reports 0
in all four cells because it essentially cannot report anything else. It is not evidence.

The substantive ambiguity is large. Re-run on the same key (`research/l2_referee4.py`):

| arm | 84% rows | with **more than one** earlier candidate original at that price | of those, candidates **disagree on `sgrade`** |
|---|---:|---:|---:|
| OFF | 542 | 107 | **41** |
| ON | 200 | 50 | **35** |

So for 35 of the 200 rows in the ON table (17.5%) the published S/A/C bucket is decided by an
undocumented tie-break — `cands.sort(by et); cands[-1]` — and not by the key. Swapping the
tie-break to first-by-time moves the ON row from 72/111/15 to 69/116/13. The table is not
wrong, but it is not "zero ambiguity" either, and the tie-break is never stated in the report.

## Defect D17 — the replacement explanation for the 15 residual C originals is disproved (material)

This is the fix the repair was proudest of. The report now says:

> the surviving 15 are **not join slop**. The book's `sgrade` column is `downgrade.score`
> evaluated at the original row's own entry; `backtest_week._sgrade_84` re-scores the stopped
> trade at **arm time**, using the runner's then-current `htf_bias`. Those are two different
> calls on the same trade, and they can disagree on a handful of borderline originals — that
> is the real cause of the residue, not join error.

It is testable, and it fails. Under the same exact `level_px` key, for **all 15** of the ON
arm's residual C originals there is **another candidate original at the identical price, on
the same symbol and day, graded S or A**:

```
TSLA 2024-12-02 10:59  candidates {A, C}      AMD  2025-07-24 10:30  {C, S}
TSLA 2026-07-28 10:03  {A, C}                 ACHR 2025-06-26 10:59  {A, C}
MU   2025-12-15 10:52  {A, C}                 ORCL 2025-02-18 10:20  {A, C}
COIN 2024-10-07 10:14  {A, C}                 COIN 2025-05-07 10:51  {A, C, S}
HOOD 2025-01-23 10:06  {C, S}                 IREN 2026-05-26 10:51  {A, C}
IREN 2026-08-04 10:10  {A, C}                 AVGO 2025-04-10 10:12  {A, C}
AVGO 2026-03-26 10:12  {A, C}                 BABA 2026-03-04 09:52  {C, S}
MARA 2026-05-28 09:54  {C, S}
```

15 of 15. In fact **all 198 resolved ON rows have at least one S-or-A candidate original**.
And tightening the join to what the engine can actually arm off — a row that traded and
stopped out — collapses the residue from 15 to **1** (S 48 / A 60 / C 1, 109 resolved).

The residue is the join's tie-break picking a non-arming row that happens to share the price,
not two `sgrade` evaluations disagreeing. That is exactly the "join slop" the repair declared
disproved. No `htf_bias` timing effect is needed to explain any of the 15, and the report
offers no evidence that one occurs at all. **The claim as published is unsupported.**

(This does not weaken the row's finding — it strengthens it. The arm gate is cleaner than the
report says: on the faithful join, essentially no C-graded original arms a re-entry under the
flag.)

## Defect D18 — the false citation D13 removed from the report is still in the engine source (minor)

The repair added, in the report: *"(Correction, referee pass 3: this is not 'per this row's
own instruction' — no such instruction exists in the spec.)"* The sentence it is correcting is
still live in `signal_runner.py:485`, inside the shipped `RULE84_DECIDED` docblock:

> `#       units and is NOT reused here per this row's own instruction. Uses`

The engine comment is the copy the next agent reads. Fixing the markdown and leaving the
source is half a fix.

## Defect D19 — "100% of the −$5/day delta is the 84% path" is true of the candidate pool and false of the priced set (minor, wording)

The report writes: *"the core-11 day-policy pool differs by exactly 84 removed and 3 added,
all of them 84%-rule rows, zero pnl differences on shared keys, so 100% of the −$5/day delta
is the 84% path."*

That holds for the **candidate** pool (confirmed above). It does not hold for the rows the
unit actually prices, after the up-to-3 / stop-after-a-win cap: there the two arms differ by
**2 rows removed** (both 84%, +$2,176) and **2 rows added that are not 84% rows at all** —
AMD 2024-11-18 10:47 (−$1,000) and TSLA 2026-09-03 09:46 (+$384) — because dropping an 84%
row earlier in the day changes which signals the take-3-and-stop sequence reaches. The
arithmetic closes: (−$616 added) − (+$2,176 removed) = −$2,792 over 499 sessions = −$5.6/day.
The flag is still the cause of all of it, but "all of them 84%-rule rows" is not true of the
set that produces the dollars, and the sentence does not say which pool it means.

## Defect D20 — count discrepancy on the halt cascade: 28 published, 30 measured (minor)

The report says 28 non-84% rows flip status across the arms. On a row key verified unique in
both books — `(sym, day, et, setup, dir, level_name, entry, stop, target)`; the obvious
`(sym, day, et, entry)` key collides on 14,592 rows, e.g. COIN 2026-05-01 10:43 is both a
pivot-high retest and an 84% re-entry — the count is **30**. The nine days are exactly the
ones published, and the conclusion (inert for this unit, not inert for `every_signal`) is
unaffected.

## Not a defect, but the report overstates it — D14, the "stale rulebook"

The report's one carried-forward open item says `omen-rulebook.md` "carries no marker"
superseding its 2026-08-28 "No grade gate at arming" line. The rulebook does in fact carry the
2026-09-05 decision, at line 1915 of `Projects/omen-rulebook.md`, in the Decided list, in the
settled wording. What is true is narrower: `omen_recall.py`'s **top hit** for an arming query
is still the 2026-08-28 line, and that line has no "superseded" marker beside it. Worth a
one-line note in the rulebook; not a missing decision.

## Also noted

- The report writes "**H1 alone** fails the no-regression gate". On the whole-book column the
  loss also deepens 9.6% (−$52 → −$57), well past the 5% floor. The gate is defined on the two
  halves, so the decision is unaffected, but "alone" is not accurate.
- Commit `5306416e`'s message still publishes the superseded full-pool figures
  ("$/day -9->-16, green 12/25->12/25"). Git history cannot be rewritten here and the report
  corrects them; flagging only so a future reader of `git log` is not misled.

---

## What this pass does NOT establish

- Nothing about whether the 84% rule is good or bad. −$5/day on 769 trades is far inside this
  project's per-trade noise; the decision turns on H1's dollar column, not on that.
- Nothing about the re-entries' own edge: 56 traded OFF and 20 ON, and the ON cell is under
  the 30-trade floor, so **not enough**.
- Nothing about which of the flag's two bundled mechanisms causes H1's failure.
- Nothing about the phantom-fill column, or any unit other than the day policy and the raw
  fired/traded counts above.
- The corrected join in D17 is a referee diagnostic, not a re-published table: it uses
  `traded and out == "loss"` as the arming proxy and leaves 91 of 200 ON rows unresolved,
  because the book does not store the arm link. The right fix is for the engine to stamp the
  original's id on the re-entry row, not for the next agent to guess a better join.

## Bottom line

Third independent reproduction of the number, third time it lands to the dollar: −$52 → −$57
a day on core-11 under his day policy, H1 fails the no-regression floor, and
`RULE84_DECIDED` correctly stays **OFF** as a toggle column in the tape. The decision has now
been checked enough. The write-up has not: this repair round shipped a correction whose own
replacement explanation the data contradicts, asserted "zero ambiguity" on a check that cannot
fire, and left the pre-repair wording of two of its five fixes standing as the report's closing
paragraph. **Refuted on the report; the number and the hold stand.**
