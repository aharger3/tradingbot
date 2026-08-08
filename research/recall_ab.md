# recall_ab — omen-3.7 T6: DETECT_WIDE OFF vs ON recall re-measure

## Mechanism check first

Both arms replay `signal_runner.SignalRunner.detect_signals` bar-by-bar over the
same 159 marks (`austin_marks_v2.jsonl`) against the post-T1 archive. DETECT_WIDE
was flipped at runtime by setting the `signal_runner` module global before the
replay — `_retest_tol()` reads it live at every `detect_signals` call (no caching),
the same mechanism the signal_runner dry-run uses for BNR_DISPLACEMENT_GATE.
- **OFF (shipped default): 738 raw signals, 116 fired** (status mix fired 116 / skipped_d 603 / skipped_tight 19).
- **ON (DETECT_WIDE=True): 2101 raw signals, 440 fired** (status mix fired 440 / skipped_d 1611 / skipped_tight 50).
- The arms differ: ON emits 2.85x the raw signals (738→2101) and 3.79x the fires
  (116→440). **The flag took effect; nothing below is void.**

---

## What changed vs 3.6 (read this before any "improvement")

The OFF arm is the shipped engine (DETECT_WIDE=False passes `retest_tol_mult=0.0`,
byte-identical to today's exact-touch test). Compared with 3.6's `engine_recall.md`
numbers — **fired S 4/77, any-signal S 19/77** — the OFF arm reports
**fired S 10/77, any-signal S 27/77**. That is NOT an engine improvement.

- The **all-marks denominators are unchanged**: 77 S / 60 A / 22 X (the same 159
  post-dedup marks, same file).
- What changed is the **testable subset**: in 3.6, 54 marks had no archive (engine
  could not run → counted as misses), so the testable S denominator was **48**.
  After T1's backfill, **0 of 151 marked days lack bars** — testable S is now **77**
  (29 more S marks are runnable; A 45→60, X 12→22 likewise).
- So fired S 4→10 and any-sig S 19→27 is the backfill making previously-untestable
  marks count, not the engine getting better. On the 48 S marks already testable
  in 3.6 the engine behaves identically. Reporting 10/77 as a gain over 4/77
  without this caveat would be a lie — the denominators (testable subset)
  legitimately changed; the engine arm did not.

## Recall — fired entries (+/-2 bars, all marks; denominators 77/60/22)

| tier | OFF (fired) | ON (fired) |
|---|---|---|
| **S** | **10/77 (13%)** | **14/77 (18%)** |
| A | 6/60 | 7/60 |
| X | 6/22 | 5/22 |

## Recall — any signal, any grade (detection, not filtering)

Two rows: deduped (one per setup idea per 30-bar window, the t4 `any-sig` line)
and raw (every captured signal bar, no dedupe — the true upper bound on "the
engine produced *a* signal here").

| metric | OFF | ON |
|---|---|---|
| any-sig deduped S | 27/77 | 27/77 |
| any-sig deduped A | 22/60 | 15/60 |
| any-sig deduped X | 11/22 | 6/22 |
| any-sig raw (no-dedupe) S | 29/77 | 46/77 |
| any-sig raw A | 25/60 | 35/60 |
| any-sig raw X | 13/22 | 16/22 |
| fired raw (no-dedupe) S | 10/77 | 23/77 |

The deduped any-signal S recall is **unchanged at 27/77 in both arms** — the
widening detects **zero new S marks** at the deduped level; it only fires more
often on already-detected S bars. Deduped A and X actually **drop** (A 22→15,
X 11→6): the wider retest tolerance lets a setup fill the 30-bar dedupe window
earlier and suppress the dedup of the genuine A/X setups. The raw (no-dedupe)
upper bound does rise (S 29→46, A 25→35, X 13→16), but a signal that appears as
one of ~14/pair/day is not a tradeable detection.

## Precision — both arms

| | OFF | ON |
|---|---|---|
| engine entries on marked days | 65 | 155 |
| land within +/-2 bars of a mark | 25 | 30 |
| **precision** | **25/65 = 38.5%** | **30/155 = 19.4%** |
| matched mark tier mix (S/A/X) | 12 / 6 / 7 | 15 / 9 / 6 |
| matched engine-entry grade mix | B 19, C 6 | B 16, C 14 |
| entries on marked days Austin did NOT mark | 40 | 125 |

**A widening that raises recall by firing everywhere is not a win, and precision
collapses:** ON lifts fired S recall 10→14 (+4) but halves precision (38.5%→19.4%),
puts 2.4x the entries on marked days (65→155), and triples the unmarked entries
(40→125). The recall gain is bought by spraying 2.85x the raw signals. Per
CLAUDE.md's bar ("no new gate until recall clears 40%"), fired S recall at 18%
ON is nowhere near it; only the no-dedupe raw upper bound (46/77 = 60%) clears
40%, and that is precision-free. **DETECT_WIDE as shipped (mult 1.0) is not a
win and should not arm.**

## Signals per symbol per day — the trade-count cost of the widening

| | OFF | ON |
|---|---|---|
| fired entries / pair (mean) | 0.43 | 1.03 |
| deduped all-grade signals / pair (mean) | 1.52 | 2.56 |
| raw signals / pair (mean) | 4.89 (738/151) | 13.91 (2101/151) |
| pairs with >=1 entry | 50/151 | 85/151 |
| max entries on one pair | 3 | 4 |
| top symbols by fired entries | IWM 9, QQQ 9, COIN 6, GOOG 6 | QQQ 23, IWM 18, MARA 13, COIN 11 |

ON roughly **doubles the entries per pair (0.43→1.03)** and nearly **triples the
raw signals per pair (4.89→13.91)**. QQQ alone goes from 9 to 23 fired entries
across its marked days — the widening is not surgical, it fires across the board.

## Verdict

- The mechanism works (arms differ 2.85x raw / 3.79x fired) and is byte-identical
  to shipped when OFF, so the baseline comparison is clean.
- OFF vs 3.6: the bigger fired-S number (4→10) is **backfill, not improvement** —
  testable S rose 48→77; the engine arm is unchanged.
- ON vs OFF: fired S +4 (10→14) and raw any-sig S +17 (29→46), but **deduped
  any-sig S is flat at 27/77** (zero new S detections) while deduped A/X fall,
  precision halves (38.5%→19.4%), and entries/pair double. This is a widening
  that fires everywhere, not a detection that finds the missing S bars. It does
  not clear the 40% recall bar in any usable form. **Not a win; do not arm.**

## Method

- Harness: `research/t6_recall_ab.py` imports `t4_engine_recall` and runs its
  `main()` twice, setting `signal_runner.DETECT_WIDE` (False then True) and
  redirecting each arm's report to `recall_off.md` / `recall_on.md` and the dumps
  to `engine_{signals,entries}_{off,on}.jsonl`. Flag restored to False after.
- Same replay as `t4_engine_recall.py`: bar-by-bar `detect_signals`, 30-bar
  per-setup-idea dedupe, 11:00 entry cutoff, +/-2 bar join, levels reconstructed
  from `data_archive`, 84% re-entries not armed.
- Marks: `austin_marks_v2.jsonl` (159 marks, 151 distinct symbol|day). After T1's
  backfill, 0 of 151 marked days lack archived bars (the "54 no-archive" string in
  t4's footer is stale boilerplate; the computed line says 0).
- `backtest_12mo.py` was NOT run — P&L is not this version's question.
- Raw per-arm reports: `research/recall_off.md`, `research/recall_on.md`.
