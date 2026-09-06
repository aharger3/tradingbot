# L2 — the 84% re-entry as decided on the call

Row L2, OMEN 10.0. Flag: `RULE84_DECIDED` (default OFF, held OFF by this row's gate).
Loop cycle: `research/loop_cycle.py --config research/tape/loop.json --flag
RULE84_DECIDED --on 1`. Two books, stamped, both at commit `7fb977f7` (the flag-OFF
landing commit), 499 sessions, 2024-09-04..2026-09-04:

- OFF (shipped default): `research/tape/book_RULE84_DECIDED_off.json.gz`
- ON (RULE84_DECIDED=1): `research/tape/book_RULE84_DECIDED_on.json.gz`

## Recall check (step 1)

`research/omen_recall.py` on "84% rule reclaim tolerance 25% previous candle range
same session before 11:00 two attempts" returns the settled sentence verbatim
(`omen-10-0-spec.md`, "What the call settled"):

> "84 is a **name only** (the lesson's stat), no threshold. Arms **only after a
> stopped S or A original**. Reclaim = close back at the original entry within
> **25% of the previous candle's range**; two attempts; **same session, before
> 11:00**."

Implemented exactly that. No conflicting reading turned up.

## What the flag does

One composite flag replaces three earlier, superseded readings of the same
rulebook sentence (`RULE84_STRICT`, `RULE84_ARM_SGRADE`, `RULE84_ARM_NOGATE`),
which are all ignored while `RULE84_DECIDED` is on:

1. **Arm gate** (`backtest_week._arm_84`): the stopped-out original must grade
   **S or A** on Austin's own ladder (`downgrade.score`, the same call the
   book's `sgrade` column already makes) — not S alone, not the legacy A+/A
   ladder.
2. **Reclaim tolerance** (`signal_runner._reclaim_gate_ok`, new function): the
   reclaim close must land within **25% of the PREVIOUS candle's range**
   (`BAR_EXTREME_FRAC`, the one 25% constant this file already uses everywhere
   else) of the original entry price — a different unit from the existing
   `RULE84_RECLAIM_TOL`, which is in R (entry-to-stop) units and was left
   alone. Both existing flags were unusable for the settled meaning:
   `RULE84_ARM_SGRADE` already means "S-only" (not "S or A") and
   `RULE84_RECLAIM_TOL` already means R units (not the previous candle's
   range) — reusing either would silently redefine a shipped flag, so a
   third, composite flag was the right call. (Correction, referee pass 3:
   this is not "per this row's own instruction" — no such instruction exists
   in the spec. The spec's Phase-L bullet names the two existing flags
   directly; the justification above is the actual reason a third flag was
   still correct.)
3. Two attempts and same-session-before-11:00 are already the shipped
   defaults (`RULE84_MAX_ATTEMPTS=2`, `SESSION_END`/`ENTRY_CUTOFF="11:00"`) —
   no new flag needed for either.

Everything else about the reclaim clause (no-pattern-vs-strong-PA, the RR
floor, the near-HOD/LOD veto, stop placement) is untouched: one composite
change, not a rewrite.

## The gate result (unit: his day policy)

Fill = close (shipped `ENTRY_FILL` default). Exit = shipped engine: 1R hard
stop, resting order at the level, intrabar-touch fill; `SCALE_PLAN=
hod_then_runner_be`; account-wide two-loss halt on. Unit =
`up_to_3_stop_win_or_2loss` on `universe.CORE_SYMBOLS` (core-11, `tier ==
"core"`), his day policy — up to 3 fired-and-traded signals a day in arrival
order, stop after the first win or the second loss. Script:
`research/loop_cycle.py` -> `backtest_2y.py --days 730`.

| | trades | $/day before→after | mean R before→after | green months before→after | gate |
|---|---:|---:|---:|---:|---|
| whole (25 mo) | 769 | -$52 → -$57 | -0.0335 → -0.0371 | 11/25 → 11/25 | — |
| H1 (12 mo) | 382 | $9 → -$8 | 0.0057 → -0.0052 | 6/12 → 6/12 | **FAIL** (sign flip, below the 5% no-regression floor) |
| H2 (13 mo) | 387 | -$111 → -$106 | -0.0722 → -0.0686 | 5/13 → 5/13 | pass |

**Decision: HOLD.** `RULE84_DECIDED` stays OFF. H1 alone fails the
no-regression gate, so per the row's own rule both halves must pass and this
one doesn't. `research/tape/cycles.md` and `research/tape/loop_state.json`
both carry this cycle (`target_met: false`, `stop: false`,
`consecutive_holds: 2`).

## The row readouts (all-28 archived book, both fired and traded, since the
arm/reclaim mechanics live upstream of the day-policy unit)

"Fired" below counts only rows with `status == "fired"` — not every row the
84%-rule setup produced at any status, which is a larger, unrelated number
(542 OFF / 200 ON; see Refereed).

| | fired (all 28 syms) | fired/day | traded | traded/day | mean R (traded) | share of all traded rows |
|---|---:|---:|---:|---:|---:|---:|
| OFF | 124 | 0.249 | 56 | 0.112 | +0.061R | 1.38% |
| ON | 39 | 0.078 | 20 | 0.040 | +0.036R | 0.50% |

Core-11 slice (`tier == "core"`): OFF fires 53 (18 traded); ON fires 20 (9
traded).

**Sample-size rule: the ON cell (20 trades) is under the 30-trade floor, so
the comparison carries no verdict; the OFF cell's 56 does clear it.** Because
the comparison needs both cells and one of them (ON) is short, the funnel
still carries **not enough** to call a winner or a loser on the re-entries'
own mean R — only to describe the funnel.

## Originals: S vs A vs C (engine ladder, `sgrade` where present, `grade`
otherwise), joined by symbol/day/level-price to the nearest prior stopped-out
row before the re-entry's own timestamp

| | S | A | C | total resolved |
|---|---:|---:|---:|---:|
| OFF, all statuses | 80 | 129 | 316 | 525 of 542 |
| ON, all statuses | 72 | 111 | **15** | 198 of 200 |
| OFF, fired only | 18 | 27 | 74 | 119 |
| ON, fired only | 16 | 21 | **2** | 39 |

**Corrected (referee pass 3, 2026-09-05).** This is now an exact key: the
84%-rule row carries `level_name = "not-his: prior entry (84%)"` and
`level_px` equal to the original's own entry price, so the original is the
same-symbol, same-day, earlier row whose own `entry` equals that `level_px`.
On that key (`research/l2_referee3_join.py`), 525 of 542 OFF rows and 198 of
200 ON rows resolve with **zero ambiguity**, replacing the earlier
approximate nearest-match join and its 78/138/326 → 69/116/15 counts.

The arm gate does what it says — C-graded originals collapse 316 → 15 at any
status (74 → 2 on fires) — but the surviving 15 are **not join slop**. The
book's `sgrade` column is `downgrade.score` evaluated at the original row's
own entry; `backtest_week._sgrade_84` re-scores the stopped trade at **arm
time**, using the runner's then-current `htf_bias`. Those are two different
calls on the same trade, and they can disagree on a handful of borderline
originals — that is the real cause of the residue, not join error. The code
path used at the arm point is `_sgrade_84(t, runner) in ("S", "A")` and
admits nothing else; the 15 pass that check at arm time even though the
book's own `sgrade` column reads C for them.

## The 84% share of the book

All-29, all fired signals: 1.14% (OFF) → 0.36% (ON). All-29, all traded
signals: 1.38% (OFF) → 0.50% (ON). The rule is a small slice of the book in
both arms; tightening the arm gate to S/A-only and the reclaim tolerance to
the candle-range unit roughly halves the re-entry count and cuts the traded
share to about a third.

**The flag is not purely subtractive (referee pass 3).** Two of the 39
ON-arm fires do not exist in the OFF arm at all: ORCL 2025-01-02 10:59 and
ACHR 2026-02-02 10:15. Mechanism, verified on raw archived bars: refusing an
early reclaim leaves the two-attempt budget intact, so the next qualifying
bar fires instead. At ORCL's OFF-arm attempt (10:58) the reclaim gap is
0.035 against 25% of the 10:57 candle's range (0.030) — refused — and 10:59
fires in its place. In the core-11 day-policy candidate pool the flag
removes 84 rows worth +$1,792 and **adds 3**, all three −$1,000 (MSFT
2025-04-29 10:52, AMD 2026-04-06 10:55, QQQ 2026-08-21 10:29). A tightening
that can add a losing trade is a real side effect, not just "roughly
halves" — noted here so the next agent has it.

**A downstream, inert-here side effect (referee pass 3).** Comparing the two
books row for row, 28 rows that are **not** 84%-rule rows flip
`status`/`traded` between `halted` and `fired`, on 9 days (2024-09-12,
2025-06-09, 2025-07-11, 2025-09-29, 2025-10-14, 2026-03-02, 2026-04-10,
2026-06-08, 2026-08-07) — every one of those days also carries an 84%-rule
traded row that differs between arms, on a different symbol: the
account-wide two-loss halt cascading off the one change. It is **inert for
this row's headline**: the core-11 day-policy pool differs by exactly 84
removed and 3 added, all of them 84%-rule rows, zero pnl differences on
shared keys, so 100% of the −$5/day delta is the 84% path. It is **not**
inert for the `every_signal` unit reported beside this one elsewhere in this
project, where `traded` is the membership test — flagging it for whoever
uses that unit next.

## Bottom line

Every A/B in this repo moves less than its own error bar, and this one is no
exception — the whole-book move (-$52 → -$57/day) is small next to the
per-trade noise. What actually gates the decision is durability, not $/day:
H1's $/day fell more than 5%, which is the no-regression line this loop
enforces on every half. Held, not shipped. No number here should be read as
"the 84% rule is bad" — only that this particular tightening does not clear
the bar this loop was built to enforce, on this book, on this unit.

## Refereed (2026-09-05, `research/l2_referee.md` / `research/l2_referee.py`)

The referee refuted the original version of this report on three points.
**The hold survives on both pools** — that verdict did not change. Fixed:

1. **Wrong lane priced as core-11.** `research/loop_cycle.py` never applied
   `research/tape/loop.json`'s `universe.row_filter` (`tier == "core"`), so
   the gate table above priced the whole 28-symbol archived pool while every
   line of this report, `cycles.md` and the ntfy push named core-11.
   **Fixed**: added `apply_universe_filter()` to `loop_cycle.py`, called from
   `stage_gate` on both arms before any figures are computed. Re-ran
   `--stage gate` on the same two books (`book_RULE84_DECIDED_{off,on}
   .json.gz`, unchanged, still stamped at `7fb977f7`) — the gate table above
   is that corrected run. The old full-pool numbers were 773 trades, -$9 →
   -$16/day whole, H1 $72 → $58 (a false pass reading — the halves table
   above is the one that governs the decision), H2 -$89 → -$89, 12/25 → 12/25
   green. The correct core-11 numbers (used above) are 769/-$52→-$57,
   H1 $9→-$8 (**fails**, not the old "pass"), H2 -$111→-$106, 11/25→11/25
   green. `research/loop_cycle.py`'s `apply_universe_filter` is a generic
   `FIELD == "VALUE"` reader, not a special case for this row's flag, so
   every future L-row's gate is filtered correctly by default now.
2. **"Fired" column was every 84%-rule row at any status, not fires.** The
   row-readouts table above now reads `status == "fired"` only (124 → 39
   all-28, 53 → 20 core-11), replacing the old 542 → 200, which were total
   rows the setup produced (fired, skipped, everything). Fires/day corrected
   from the old 1.086 → 0.401 (4.4x high) to 0.249 → 0.078, which now agrees
   with this report's own 1.14% → 0.36% share-of-fired line (that line was
   already computed from the correct counts, which is how the referee caught
   the mismatch).
3. **Cycle double-counted.** An earlier `--stage gate` run had appended the
   (wrong, full-pool) cycle to `research/tape/cycles.md` and
   `research/tape/loop_state.json` twice — `loop_state.json` read
   `consecutive_holds: 3` off two experiments (MIN_PT1_R + one RULE84_DECIDED
   run counted as two). Removed both stale rows/history entries, re-ran
   `--stage gate` once with the fixed script; `cycles.md` and
   `loop_state.json` now carry exactly one (corrected) RULE84_DECIDED cycle
   (`cycle: 2`, `consecutive_holds: 2`).

Not fixed, and not fixable inside this row's one-change budget — kept as
named limitations:

- **Stale rulebook citation.** `omen_recall.py` on "84% rule arming" also
  surfaces `omen-rulebook.md`'s 2026-08-28 Batch 03 line ("The 84% rule arms
  on any grade ... No grade gate at arming"), which conflicts with the
  implemented S/A arm gate. The 2026-09-05 call superseded that line (this
  row's implementation matches the call, which is law per the spec), but
  `omen-rulebook.md` itself is not marked superseded. That is a documentation
  edit to a file this row does not own — flagging it, not fixing it.
- **One flag, two mechanisms, one H1 failure.** `RULE84_DECIDED` bundles the
  S/A arm gate and the candle-range reclaim tolerance (both named in the same
  spec sentence, one composite flag by the row's own instruction). H1's
  failure cannot be attributed to one or the other from this book alone —
  isolating them would be a second flag, which is out of scope for this row.

## Refereed (pass 3, 2026-09-05/06, `research/l2_referee.md` / `l2_referee3.py`
/ `l2_referee3_join.py` / `l2_referee3_probe.py`)

Pass 3 independently re-derived every headline number under a **third**
implementation that imports neither `loop_cycle.py` nor
`g72_suppress_price.py` — core-11, `up_to_3_stop_win_or_2loss`, close fill,
shipped 1R stop + `hod_then_runner_be` exit, 499 sessions. Every cell
reproduced to the dollar (769 trades, -$52 → -$57/day, 11/25 → 11/25 green,
H1 fail, H2 pass), the stamps and book_ids matched, the semantics checked out
clause by clause against raw archived bars (39/39 ON fires satisfy the
tolerance once ORCL 2025-01-02 is read unrounded), and the verify gate was
green with no mark file touched. **The decision and every number stand.**
What was refuted was the prose around them — five defects, all fixed above:

- **D9 (sample-size sentence false).** Fixed — see the corrected sentence in
  "The row readouts."
- **D10 ("join slop" disproved).** Fixed — the originals table now uses the
  exact `level_px` key (525/542 OFF, 198/200 ON resolve with zero ambiguity)
  and the real cause (two different `sgrade` evaluations — at-entry vs.
  at-arm-time with `htf_bias`), not join error.
- **D11 (flag can add a fire, undisclosed).** Fixed — see "The 84% share of
  the book": 2 of 39 ON fires don't exist OFF, one traded (-$1,000); the
  core-11 candidate pool gains 3 rows, all -$1,000.
- **D12 (28 non-84% rows moving, undisclosed).** Fixed — same section: the
  account-wide two-loss halt cascades onto 28 non-84% rows across 9 days,
  inert for this row's own unit but not for the `every_signal` unit reported
  beside it elsewhere.
- **D13 (false citation).** Fixed — the reclaim-tolerance rationale now cites
  the actual reason (both existing flags already carry a different meaning)
  instead of a nonexistent instruction.

**D14, still open, not fixed here.** `omen_recall.py`'s top hit for "84% rule
arming grade gate" is still `omen-rulebook.md`'s 2026-08-28 Batch 03 line
("No grade gate at arming") plus Austin's quote backing it — the direct
negation of the S/A arm gate this row ships. The 2026-09-05 "What the call
settled" table supersedes it and is law, so the code is correct, but the
rulebook file carries no marker saying so, and it is the first thing every
agent in this swarm reads. This report does not own `omen-rulebook.md` and
does not edit it inside this row's one-change budget. Flagging for a
dedicated one-line-note row rather than fixing here.

## What this does NOT establish

- Not enough trades (56 / 20, both under 30) to say whether S/A-gated
  re-entries carry a better or worse mean R than ungated ones — the funnel
  narrowed, the R distribution did not move outside noise on this sample.
- The original-grade join is approximate (nearest match by price and time,
  no stored link) — a hint at the gate's effect, not an audited count.
- This says nothing about the live-fill (phantom) column or any unit other
  than the day policy and the raw fired/traded counts reported here.
