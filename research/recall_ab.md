# recall_ab (omen-3.7 T6) — DETECT_WIDE OFF vs ON over austin_marks_v2.jsonl

## Mechanism check (FIRST — if this is void, everything below is void)
- Raw captured signal count: **OFF 738, ON 2101**. Fired count (status=`fired`): **OFF 116, ON 440**.
- The two arms are **NOT identical** (raw 2.8×, fired 3.8×) → DETECT_WIDE took effect. The flag flipped the live `signal_runner` module global at runtime exactly as `signal_runner.main`'s dry-run flips `BNR_DISPLACEMENT_GATE` (the `sys.modules` copy, not a fresh `import`, so the toggle lands on the module `_retest_tol` reads); asserted `OFF: _retest_tol()=0.0`, `ON: =1.0`.
- Denominators: 77 S / 60 A / 22 X (159 marks, 151 symbol-days), identical for both arms. After T1's backfill **all 159 marks are testable (0 no-archive)**, vs 3.6 where 54 marks / 49 pairs had no archive (testable S was 48/77). The all-marks denominators are unchanged; the *testable* population grew, so OFF numerators rise vs 3.6 with no detection change whatsoever.
- Fired S recall: **OFF 10/77 → ON 14/77** (+4). Any-signal S recall (raw, no-dedupe upper bound — the figure 3.6 reported as 19/77): **OFF 29/77 → ON 46/77** (+17); deduped any-signal S: OFF 27/77 → ON 27/77 (flat).
- Precision: **OFF 25/65 = 38.5% → ON 30/155 = 19.4%**. The widening buys +4 fired S but DOUBLES entries (65→155) and HALVES precision — recall bought by firing everywhere, not a win.

---

## 1. Mechanism check (detail)

| metric | OFF | ON |
|---|---:|---:|
| raw captured signals (every bar, no dedupe) | 738 | 2101 |
| fired signals (status=`fired`, no dedupe) | 116 | 440 |
| deduped fired entries (the trades it would take) | 65 | 155 |
| deduped all-grade signals | 229 | 387 |

The arms are unambiguously different. If they had been identical, the flag never took effect and everything below would be void — reported here as the explicit check, not a null. `DETECT_WIDE` is read dynamically by `_retest_tol()` at the two `detect_break_retest` call sites (`signal_runner.py:612`, `:817`), so the runtime flip reaches detection; the harness asserts the global each arm (`research/t6_recall_ab.py`).

## 2. Recall — fired S/A/X, both arms (denominators 77/60/22, identical)

| tier | OFF fired | ON fired | Δ |
|---|---|---|---|
| S | 10/77 | **14/77** | +4 |
| A | 6/60 | 7/60 | +1 |
| X | 6/22 | 5/22 | −1 |

| tier | OFF any-signal (deduped) | ON any-signal (deduped) | OFF any-signal (raw, no-dedupe) | ON any-signal (raw, no-dedupe) |
|---|---|---|---|---|
| S | 27/77 | 27/77 (flat) | 29/77 | **46/77** |
| A | 22/60 | 15/60 | 25/60 | 35/60 |
| X | 11/22 | 6/22 | 13/22 | 16/22 |

No-dedupe fired-only (every fired bar, not the deduped trade): S 10/77 OFF → 23/77 ON; A 6/60 → 9/60; X 7/22 → 8/22.

## 3. OFF arm vs 3.6's numbers (the backfill correction)

3.6 reported **fired S 4/77** and **any-signal S 19/77** (the raw no-dedupe upper bound). This row's OFF arm — byte-identical shipped detection, `DETECT_WIDE=False` — reports **fired S 10/77** and **any-signal S 29/77**. Both numbers are bigger. **That is not an improvement and must not be read as one.** The cause is T1's data-archive backfill, not the engine:

- In 3.6, 54 marks (49 of 151 symbol-days) had no archived bars; `run_day` returned `None` for them and they were counted as recall misses in the all-marks column (testable S was 48/77, testable fired S 4/48).
- After T1's backfill, **0 marks lack archive** (verified: 159/159 have bars). The 29 S marks that were no-archive misses in 3.6 now run. Six of them now fire a deduped entry (4→10) and ten of them now produce any signal (19→29).
- DETECT_WIDE is OFF in both 3.6 and this OFF arm, so detection is byte-identical; the only thing that moved is the runnable population. The denominators are unchanged (still 77/60/22); the *testable* denominators rose (S 48→77) because of backfill, and the numerators rose with them. A bigger OFF number here is the backfill showing up, not the engine getting better.

## 4. Precision — both arms (and the recall-gain caveat in the same breath)

| | OFF | ON |
|---|---:|---:|
| engine entries on marked days | 65 | 155 |
| land within ±2 bars of a mark | 25 | 30 |
| **precision** | **25/65 = 38.5%** | **30/155 = 19.4%** |
| matched tier mix (S/A/X) | S 12, A 6, X 7 | S 15, A 9, X 6 |
| matched grade mix | B 19, C 6 | B 16, C 14 |
| entries on marked days Austin did NOT mark | 40 | 125 |

**The widening raises fired S recall by 4 (10→14) and any-signal S recall by 17 (29→46 raw) — and precision collapses from 38.5% to 19.4% in the same move.** Trade count on marked days roughly doubles (65→155), the unmarked-entry count triples (40→125), and the matched-grade mix shifts from mostly-B (19 B / 6 C) to half-C (16 B / 14 C). This is exactly the failure mode the spec warned about: a widening that lifts recall by firing everywhere is not a win, and here the cost is a halved hit rate and 2.4× the trades for +4 S. Note also the deduped any-signal S column is **flat at 27/27**: the +4 fired S does not come from net-new distinct detection, it comes from the retest band letting already-captured (skip-grade) setups complete with a viable stop and upgrade to fired — while the raw-signal column floods (738→2101). Per the project's own precedent (FVG 2026-07-05, flag detector 2026-07-09 — both plausible widenings that measured as losses) this should not be defaulted ON without a 12mo P&L A/B, which this row deliberately does not run.

## 5. Signals per symbol per day — the trade-count cost on the page

Replay runs only the 151 marked symbol-days, so every entry below is on a marked day.

| | OFF | ON |
|---|---:|---:|
| fired entries (trades) total | 65 | 155 |
| **trades / symbol-day (over 151)** | **0.43** | **1.03** |
| symbol-days that fire ≥1 trade | 50 / 151 | 85 / 151 |
| trades/day distribution | 1×:37, 2×:11, 3×:2 | 1×:35, 2×:34, 3×:12, 4×:4 |
| mean trades / firing day | 1.30 | 1.82 |
| deduped all-grade signals / symbol-day | 1.52 (229) | 2.56 (387) |
| raw captured signals / symbol-day | 4.89 (738) | **13.9** (2101) |

The widening takes the engine from ~0.43 trades per marked symbol-day to ~1.03, and from ~4.9 raw signals/symbol-day to ~13.9 — a 2.4× / 2.8× rise in trade-volume cost for the recall numbers in §2.

## Method / harness

- Marks: `research/austin_marks_v2.jsonl` (159 marks, 151 symbol-days). Archive: `data_archive/<SYMBOL>/<DAY>.csv`, 0 missing after T1.
- Both arms: `research/t4_engine_recall.py` `main()` replayed bar-by-bar over the same marks and the same post-backfill archive; `signal_runner.DETECT_WIDE` flipped OFF then ON via `research/t6_recall_ab.py`, which asserts the global each arm and writes `recall_off.md` / `recall_on.md` (full reports), `recall_off_entries.jsonl` / `recall_on_entries.jsonl` (fired, deduped), `recall_off_signals.jsonl` / `recall_on_signals.jsonl` (all-grade, deduped), and `recall_off_console.log` / `recall_on_console.log` (the raw/fired counts and mixes above).
- `backtest_12mo.py` was NOT run. P&L is not this version's question.
- Per-arm full reports: `research/recall_off.md`, `research/recall_on.md`.
