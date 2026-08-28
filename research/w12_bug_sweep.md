# W12 — the bug-class sweep of the grade and gate path

2026-08-28, overnight. Scope: `signal_runner.py` (grading, skip logic, the two
minimum-risk floors), `research/downgrade.py`, `omen_bot.py`'s veto sites, and the
grade-consuming logic in `backtest_week.py`. Exit policy deliberately untouched —
`research/exit_lab.py` was swept by W2/W9 the same night.

**Why now.** Austin: *"since im changing the ladder still and getting rid of that B
hopefully once and for all, you will need to check everything for bug fixes probably."*
`B` is being deleted and the ladder becomes a pure function of downgrade count
(`Specs/omen6-h2-master-spec.md` §1.2). Everything downstream of a grade is about to
mean something different, and 1,000 of the 1,017 rows in the traded book are `B`.

**Seven findings. Two fixed. Five flagged, none shipped.** The most expensive is #1.

**Error bar.** ±0.0095 R, the narrow bar (`Specs/omen6-h2-master-spec.md` §1.1). The
wide ±1.5799 R bar was retired 2026-08-28 and is not quoted here.

---

## Method — reachability is counted, never read

Every confirmed instance of this bug class in the repo was found by hand, one at a
time, after the rule had been believed for months. Reading is how they were missed.
So no branch below is called dead because it looks dead:

| instrument | what it counts | scope |
|---|---|---|
| `research/w12_dg_probe.py` | every downgrade variable and its internal branches, re-derived on the exact bar `backtest_2y.py` graded | 45,193 signals, 11,808 symbol-days |
| `research/w12_tight_stop.py` | `_min_viable_stop` re-derived on the graded bar | 1,017 traded rows |
| `research/w12_reach.py` | the shipped `backtest_2y.py` replay under `coverage.py --branch`, restricted to the four in-scope modules | 28 symbols × ~500 sessions |
| `research/g3_arm_ow1.json` | the book itself — `grade`, `sgrade`, `downgrades`, `status`, `r` per row | 45,193 signals, 1,017 traded |

Bars come from `data_archive/` via `polygon_feed`. Nothing was fetched. Output JSON
is in `research/_w12/`.

**Line numbers below are against `57235338`**, the HEAD this sweep ran on. The working
tree also carried another agent's uncommitted W1 changes to `signal_runner.py` (+117
lines), so a `grep -n` tonight will read higher — every site is named by symbol as well
so it stays findable.

**A branch that never fires in 45,193 signals is dead. Whether it is dead *by
construction* or *by data* is the second question, and every row below answers it** —
dead by data can be fixed with a threshold, dead by construction cannot be fixed at
all.

---

## The findings

| # | class | site | reachability | price on the 2-year book | verdict |
|---|---|---|---|---|---|
| 1 | 3 — sign backwards | `signal_runner._route`'s tight-stop gate (`57235338:1624`) + `_min_viable_stop` (`:1196`) | LIVE, and one-sided: 805 of 45,193 rows are `skipped_tight_stop` and **every one is grade `C`** — the gate is consulted on no other grade. Re-derived over the 1,017 traded rows, **732 (72.0%) would fail it** | it **rejects the better half**: rejected rows mean **+1.0861 R** / median +0.6075, kept rows mean **+0.6188 R** / median +0.5490. Gap **0.4673 R = 49× the error bar**. Killing `B` sends 331 rows into `C` and **247 of them (74.6%) into this gate** | **FLAGGED** |
| 2 | 1 — branch that cannot be true | `research/downgrade.py::break_then_rejection` via `_break_bar` | **dead by construction.** 10 fires in 45,193 (0.022%). 45,039 rows (99.66%) close beyond the level, which is the precondition that makes it unsatisfiable | the same rule read off the FIRST break instead of the most recent fires **18,075 times (40.0%)** — 1,807×. Live, the ladder's `X` bucket goes 13,328 → 18,931 (**+42.0%**) and `S` goes 7,423 → 5,210 (**−29.8%**) | **FLAGGED** |
| 3 | 4 — documented ≠ shipped | `backtest_week.py:223` `SimTrade.counted`, `:227`, `backtest_2y.py:166` | LIVE. Spec §1.2 says 2 downgrades = `C` = **tradeable yes**. `counted` is `status == "fired" and grade != "C"`, so **no `C` has ever entered the book**: traded grades are B 1,000 / A 15 / A+ 2 | 377 fired-`C` rows are booked as alerts, mean **+0.4487 R**, median −1.0000. Under the new ladder **331 of the 1,017 traded rows (32.5%) become `C`**: book **n=379 mean +1.0926 median +0.9400** (C excluded) vs **n=710 mean +1.0069 median +0.7070** (C included) | **FLAGGED** |
| 4 | 1 — branch that cannot be true | `backtest_week.py::_arm_84`, gated by `RULE84_STRICT` (ships ON, `signal_runner.py:215`) | **dead by data, and barely.** The arm needs `t.counted and t.grade in ("A+","A")`; the shipped grader produces **17 A+/A rows in 45,193 signals (0.04%)**, of which **7** are arm-eligible stop-outs. The 84% rule fires **3 times in two years** | under the new ladder 379 of the traded rows are A+/A and **156 are arm-eligible — 22×**, with nobody having decided that | **FLAGGED** |
| 5 | 4 — documented ≠ shipped | `omen_bot.py` `grade_trade` docstring vs `:29` | LIVE and the largest gate in the engine: **21,257 of 45,193 rows (47.0%)** are HTF-opposed and take its `TradeGrade.D` | the docstring said the veto defaults to 0; it has always read `os.getenv("HTF_BIAS_VETO", "1")` and the module comment says DEFAULT ON. Cost: 0 R — the record was wrong, not the code | **FIXED** |
| 6 | 1 — branch that cannot be true | `research/downgrade.py::find_ocr` lookahead guard | **dead by construction.** 0 hits in **853,010 evaluations**; the loop starts one bar before the entry, so the condition it tested can never hold | 0 R. Pure dead code | **FIXED** |
| 7 | 1 + 4 | `spec0b_levels_check.py` | **the check is RED at HEAD** and has been dark. It dies at `:44` before reaching its veto assertion, and that assertion (`:74`) asserts the retired `HTF_BIAS_VETO=0` default | it is the only end-to-end test of the veto path, and it has not run. Root cause diagnosed below — it is W3's mechanism, not a new one | **FLAGGED** |

---

## 1. The minimum-viable-stop gate keeps the worse half, and only `C` ever meets it

`signal_runner._route`:

```python
if sig["grade"] != "C" or self._min_viable_stop(sig["entry"], sig["stop"], sig["direction"]):
```

One grade is tested. The comment says why — *"tight-stop skip only for C — it killed 42
of 303 labeled takes (calibration 2026-07-06); B+ setups size to the stop instead"* —
and in the legacy ladder that was coherent, because `C` meant alert-only.

It stops being coherent tonight. `_calibration_grade`'s first-with-trend floor makes
1,000 of the 1,017 traded rows `B`, and deleting `B` re-files 331 of them as `C`.

`research/w12_tight_stop.py` re-derives the predicate on the bar each traded row was
graded on — same `STOP_RANGE_MULT = 0.75`, same 0.5% risk floor, same $0.20 premium
floor, `self.candles[-11:-1]` read as `bars[i-10:i]`:

| population | n | mean R | median R |
|---|---:|---:|---:|
| traded rows the gate would **reject** | **732** | **+1.0861** | +0.6075 |
| traded rows the gate would **keep** | 285 | **+0.6188** | +0.5490 |

The rows it throws away are worth **0.4673 R more** than the rows it keeps — 49× the
±0.0095 R bar. This is the `level_not_respected` shape from `research/w9_downgrade_signs.md`
(`06aa900e`) in a second place: a filter whose tripped population outperforms its clean
population.

What it costs once the ladder lands:

| book | n | mean R | median R |
|---|---:|---:|---:|
| HEAD, as shipped | 1,017 | +0.9551 | +0.5660 |
| new ladder, `C` still alert-only (today's `counted`) | 379 | +1.0926 | +0.9400 |
| new ladder, `C` tradeable per spec §1.2 | 710 | +1.0069 | +0.7070 |
| new ladder, `C` tradeable **and this gate applied to it** | 463 | +0.9708 | +0.7750 |
| — the 247 rows that gate removes | 247 | +1.0747 | +0.5260 |

**Read the last two rows together.** The gate takes 247 rows worth +1.0747 R out of the
book and the book's mean falls. It is not selecting for quality; it is selecting against
it. The median rises (+0.7070 → +0.7750) because it removes losers *and* the biggest
winners, which is what a filter with the wrong sign looks like when median is the goal.

Three of its constants — `STOP_RANGE_MULT = 0.75`, the 0.5% stock-risk floor, the $0.20
premium floor — are among the 33 in `research/hallucination-audit.md` that **Austin never
stated**. They are ours.

**Not fixed, and not flagged behind a flag either.** Every candidate fix (apply it to all
grades, remove it, retune the constants) changes which trade is taken, so it is Austin's
call. It is also not flagged *in code* tonight for a mechanical reason worth stating:
**`signal_runner.py` carries another agent's uncommitted W1 work in the working tree, and
staging a flag there would have staged their change with it.** The guard test is in place
instead; the flag belongs in the same commit as W1's ladder.

**Caveat, stated rather than buried:** this is a counterfactual on rows that were actually
traded. A row graded `C` from the start would have been gated at emission and would never
have produced an `r` at all, so 732 and 247 are the populations the gate *would* meet,
priced by what those setups went on to do. It is the right order of magnitude and the
right sign; it is not a replay. The replay is W1's, once the flag exists.

---

## 2. `break_then_rejection` cannot fire, and it is not a threshold problem

Austin's rule, unprompted: *"it broke, then immediately gave it back."* One of the eight
variables the new ladder is built out of. It fires **10 times in 45,193 signals**.

The proof it is dead by construction, not by data:

- `_break_bar(bars, i, level, is_long)` returns the **most recent** bar that closed
  through the level.
- `break_then_rejection` then asks whether any of the next `REJECT_BARS = 2` bars closed
  back through it.
- But the graded bar closes **beyond** the level — that is the caller's own entry
  condition, and it holds on **45,039 of 45,193 rows (99.66%)**.
- If any bar after the most recent cross had closed back through, getting back beyond the
  level by bar `i` requires a *later* cross — which would then have been the most recent
  one. Contradiction.

So no value of `REJECT_BARS` recovers this rule. The 10 fires are the residue of the 154
rows that do not close beyond the level.

Priced by measuring the other reading — the rejection scanned from the **first** break of
the session (`first_break_bar` in `research/w12_dg_probe.py`, measurement only, wired into
nothing):

| | shipped | first-break reading |
|---|---:|---:|
| fires | 10 (0.022%) | **18,075 (40.0%)** |
| ladder `S` (net ≤ 0) | 7,423 | **5,210** (−29.8%) |
| ladder `A` (net 1) | 11,067 | 8,710 |
| ladder `C` (net 2) | 13,375 | 12,342 |
| ladder `X` (net 3+) | 13,328 | **18,931** (+42.0%) |

A ninth of the whole population changes tier. That is not a variable worth leaving broken
through a ladder change, and it is not a variable worth un-breaking without Austin looking
at it either — 40% is a big number for a rule he described as a rare disqualifier.

`_break_bar`'s most-recent choice is right for `no_displacement`, `stale_retest` and
`no_retest` (all three ask about the break being retested *now*). It is the wrong input
for this one variable only.

---

## 3. `C` is tradeable in the spec and has never been in the book

`backtest_week.SimTrade`:

```python
@property
def counted(self) -> bool:
    # C is alert-only in live_scanner (SPEC2) — excluded from traded P&L
    return self.status == "fired" and self.grade != "C"
```

`backtest_2y.py:166` writes `"traded": bool(t.counted)`, so **every money-gate number in
this project was measured on a book with all `C` removed**. In the 2-year book: 377 rows
fired as `C`, all filed as alerts, mean **+0.4487 R**, median **−1.0000 R**.

Spec §1.2's table says `C` is tradeable — *yes*. Two records disagree about a third of the
book. This is the same shape as finding 5 (documented default ≠ shipped default), except
here it is the spec that is ahead of the code rather than behind it, so it is not a
docstring fix: turning it on changes what trades.

The size of it, under the new ladder: **331 of the 1,017 currently-traded rows (32.5%)
land on `C`**, worth mean +0.9089 R / median +0.4070 R on their own.

If nobody decides, the default answer is "silently dropped", because that is what
`counted` already does.

---

## 4. The 84% rule's arm gate is keyed to a ladder that is being deleted

`_arm_84` requires `t.counted and t.grade in ("A+", "A")` (`RULE84_STRICT`, ships ON).
The shipped grader produces **17 A+/A rows in 45,193 signals**. Of those, **7** are
arm-eligible stop-outs (a loss, on a B&R or one-candle-rule setup). The 84% re-entry
detector produces **3 signals in two years**.

That is the third confirmed member of the bug class in this file's own history — a real
Austin rule reduced to a branch that essentially cannot be true — and here the cause is
not a bad predicate. It is that the arm gate reads a grade letter that the grader almost
never emits, because `_calibration_grade` floors nearly everything to `B`.

Delete `B` and the same gate, unchanged, sees **379 A+/A rows and 156 arm-eligible
stop-outs — 22× the current population.** The 84% rule goes from decorative to material
as a side effect of a grade remap. Whether that is wanted is Austin's call; what is not
acceptable is it happening without anyone noticing, which is what would have happened.

---

## 5. `HTF_BIAS_VETO`: the record was wrong, the code was right — FIXED

`omen_bot.py:29` has always read `os.getenv("HTF_BIAS_VETO", "1")`, and the comment block
above it says **DEFAULT ON, deliberately** in as many words, with P16's reasoning for
choosing not to flip it. Four artefacts said OFF. Two are now corrected:

- `omen_bot.py`'s `grade_trade` docstring (said "default 0") — rewritten, and it now
  carries the population size so the next reader knows what the flag governs.
- `research/p16_htf_bias.md` §5 — a dated correction block above the paragraph, rather
  than a rewrite of history.

Not touched: `TASKS.md`'s P16 row (a log entry describing what the ticket *did*, and it
did default it — the disagreement is with the code, which never changed) and
`spec0b_levels_check.py` (finding 7 — it is red before it reaches the claim).

The open question is unchanged and still queued as R6: **the veto has no author.** Austin,
ballot batch 02 c6: *"we dont have any higher timeframe bias yet youll need to tell me what
that is then."* It is the single largest gate in the engine — **21,257 of 45,193 signals
(47.0%)** are HTF-opposed and take its `TradeGrade.D` — and it is enforcing a definition
nobody has given.

---

## 6. `find_ocr`'s lookahead guard — FIXED

A guard inside `find_ocr`'s loop re-checked that the candidate bar was not the entry bar
itself. The loop starts one bar *before* the entry, so the condition could never hold:
**0 hits in 853,010 evaluations** over the 2-year book. Deleted, with the count in the
comment so it does not come back. `research/test_downgrade.py` and
`research/test_downgrade_grader.py` stay green; `find_ocr` returns the same index on the
selftest fixture.

Cost: 0 R. Listed because it is the cheapest possible specimen of the class, and because
the class is only visible when you count the ones that cost nothing as well as the ones
that cost everything.

---

## 7. `spec0b_levels_check.py` is red at HEAD, and has been dark

```
$ python spec0b_levels_check.py
AssertionError: PDH B&R missing: []      # line 44
```

It never reaches its HTF assertions, so the wrong-default claim at `:74`
(`"HTF_BIAS_VETO=0 default"`) has never fired either way.

Root cause, instrumented rather than guessed — the runner's own skip log on the fixture:

```
('PDH', 'skipped', 'X grade (skip)', entry=101.0, stop=100.9, grade='X')
```

The fixture's last bar closes at 101.70 with the session high at 101.80, so
`near_session_extreme` trips, `fill_price` back-dates the fill to the level (101.00),
`intrabar_stop` moves the stop to the entry bar's own low (100.90), and `stock_risk` is
**$0.10** against a floor of `max(0.10, 0.0015 × 101.70) = $0.1526`. Grade `D`, skipped.

**This is W3's mechanism exactly** (`Specs/omen6-h2-master-spec.md` §W3: the intrabar fill
collapsing `stock_risk` under `max(0.10, 0.0015 × close)`), reproduced on 8 synthetic
candles instead of a 2-year book. It is the cheapest reproduction of that bug in the repo
and W3 should use it as its fixture.

Not fixed here: repairing it means either moving the fixture or moving `B&R_MIN_RISK`, and
`B&R_MIN_RISK = 0.0015 × close` is W3's constant to decide, one of the 33 Austin never
stated.

---

## Negative results — the things that are NOT broken

Stated because a sweep that only reports hits is not a sweep.

**A fourth "stop computed and then not applied" does not exist in the grade path.**
Ticket 02 found two, and `exit_lab.scale_out` was the third. `intrabar_stop` is called at
2 of the 10 fill sites — the long and short break-and-retest. It is absent from the other
8 (FVG ×2, order block ×2, flag ×2, 84% ×2), and that absence is correct, not an omission:
those setups' stops are structurally strictly beyond their fill (`block.low < block.high ≤
entry`, `fvg[0] < fvg[1] ≤ entry`), so `intrabar_stop`'s `collapsed` predicate is false by
construction and the call would be a no-op. Confirmed on the book: geometry collapse
(`entry` at or through `stop`) occurs on **3,016 of 40,800 break-and-retest rows (7.4%)**
and on **0 of 4,390 one-candle-rule rows and 0 of 3 84%-rule rows.**

**No untakeable row reaches the book.** All 3,016 collapsed rows have `entry == stop`
exactly, all 3,016 are graded `X`, and 0 are traded or alerted. The minimum-risk floor is
doing its job on this population — the complaint in W3 is about what else it takes with
them, not about a leak.

**`structural_stop` is computed at both B&R sites and read only when
`ENABLE_STRUCTURAL_RISK_FLOOR` is on.** That is the flag working, not a dropped stop.

**`_SKIP_GRADES = ("X", "D")` — the `"D"` member is unreachable**, because
`TradeGrade.D is TradeGrade.X` and its value is `"X"`, so no grade string is ever `"D"`.
Harmless, costs 0 R, and the alias is documented. Not counted as a finding; noted so the
next reader does not spend an hour on it.

---

## The guard

`research/test_w12_grade_gates.py` — six asserts, no framework, synthetic bars, no
archive. **Red before the two fixes, green after** (`W12-2` and `W12-3` were the two
failures).

```
$ python research/test_w12_grade_gates.py
ok    W12-1 break_then_rejection cannot fire
ok    W12-2 find_ocr has no dead guard
ok    W12-3 HTF_BIAS_VETO doc matches code
ok    W12-4 C grade is still alert-only
ok    W12-5 arm84 gate keyed to legacy ladder
ok    W12-6 tight-stop gate is C-only and backwards

w12 grade-gate selftest ok: 6 checks
```

Two of the six guard a fix. **The other four pin a defect that is still shipped on
purpose**, so that when W1's ladder moves them the failure is loud instead of silent — a
failing `W12-4` after the ladder lands is not a broken test, it is the `C`-is-tradeable
decision arriving and demanding that the book be re-run before anyone quotes a number
off it.

---

## What each finding needs from Austin

1. **#1** — the tight-stop gate rejects rows worth +1.0861 R and keeps rows worth
   +0.6188 R. Apply it to every grade, delete it, or retune `STOP_RANGE_MULT`? All three
   change what trades.
2. **#3** — `C` is tradeable in the spec and excluded from every number in the repo.
   Which is it? The answer moves 331 rows and 0.0857 R of mean.
3. **#2** — should "it broke then gave it back" be measured from the first break of the
   session? At 40% of the book it is a different rule from the one that fires 10 times.
4. **#4** — the 84% rule's arm population goes 7 → 156 as a side effect of killing `B`.
   Wanted, or should the arm gate be re-keyed to `S` (`RULE84_ARM_SGRADE` already exists,
   default OFF)?
5. **#5** — unchanged, still R6: what should higher-timeframe bias mean? 47% of signals
   are being vetoed by a rule with no author.

---

## Provenance

Every number above names the script that made it, and every script is committed.

| number | script | input |
|---|---|---|
| variable fire rates, `_break_bar` branches, net histograms, 853,010 guard evaluations | `research/w12_dg_probe.py` → `research/_w12/dg.json` | `research/g3_arm_ow1.json` + `data_archive/` |
| `_min_viable_stop` pass/fail and its R split | `research/w12_tight_stop.py` → `research/_w12/tight_stop.json` | same |
| line and branch coverage of the four in-scope modules | `research/w12_reach.py` → `research/_w12/cov.json` | shipped `backtest_2y.py` replay under `coverage.py --branch` |
| book composition, grade counts, alert/traded R, arm-eligible counts | `research/g3_arm_ow1.json` (`f5ff006a`, 500 sessions, 2024-08-21 → 2026-08-21) | — |
| `spec0b` root cause | `spec0b_levels_check.py` with `_log_record` instrumented | 8 synthetic candles |

`research/w12_reach.py` records the SHA-256 of all four in-scope modules before and after
its run and refuses to trust its own line numbers if a concurrent agent edited one
mid-flight. Nothing in this sweep re-froze the engine, changed a shipped default, or ran
`omen6_forward.py freeze`.
