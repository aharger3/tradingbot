# omen-4.0 T6 — no-repeat-entries before/after

Replays the engine's own detection (the real `signal_runner.SignalRunner` _route, so the rule applies when armed) bar-by-bar over the 151 marked (symbol, day) pairs in `austin_marks_v2.jsonl`, mirroring `t4_engine_recall.run_day`'s walk-forward loop + 11:00 entry cutoff. Run once with `NO_REPEAT_ENTRIES` off (today's behaviour) and once on. The 84% re-entry (`SignalType.REENTRY_84_RULE`) is the one exemption — it is by definition the sanctioned second bite at the same idea.

Austin settled this on 2026-08-09 (Projects/OMEN.md): **no repeat entries — take the first one available.** Scope is symbol + direction + level; a different level or the other direction is a different idea and may still fire.


## Headline

```
signals_flag_off: 108
signals_flag_on: 59
duplicates_suppressed: 49
```

## Per-pool breakdown

| pool | fired (off) | fired (on) | duplicates suppressed |
|---|---:|---:|---:|
| equity | 29 | 16 | 13 |
| index | 29 | 14 | 15 |
| other | 50 | 29 | 21 |
| **total** | **108** | **59** | **49** |

`duplicates_suppressed` is counted directly at the skip point (the `[skip: repeat entry]` branch in `_route`), not inferred from the fired delta — so it is exact even where suppressing a repeat second-order changes a later signal's calibration floor.

## Cited batch-04 violation days

Days the task spec called out as the engine firing the same idea twice. The batch-04 "fired" counts there use the `CaptureRunner` convention (X-grade counts as fired); the **real** engine skips X-grade before the no-repeat check runs, so a duplicate that grades X is already gone. The rule's marginal value is the duplicates that grade **above X** (B/C/A) and would otherwise take a real entry. Per day below: fired off / fired on / duplicates suppressed.

**TSLA 2024-03-27** — fired 0 -> 0 (0 duplicate(s) suppressed):
- no real-entry duplicate: the repeats on this day grade X (already skipped), so the no-repeat check is never reached

**TSLA 2024-02-05** — fired 2 -> 1 (1 duplicate(s) suppressed):
- bar 09:48:00 put level $183.36 (break_and_retest) — skipped as repeat entry

**MSFT 2026-02-11** — fired 0 -> 0 (0 duplicate(s) suppressed):
- no real-entry duplicate: the repeats on this day grade X (already skipped), so the no-repeat check is never reached

**NVDA 2024-12-16** — fired 5 -> 2 (3 duplicate(s) suppressed):
- bar 09:44:00 put level $132.27 (break_and_retest) — skipped as repeat entry
- bar 10:12:00 put level $132.27 (break_and_retest) — skipped as repeat entry
- bar 10:13:00 put level $132.27 (break_and_retest) — skipped as repeat entry

## Days with the most real-entry duplicates suppressed

Where the rule actually catches a duplicate that would have traded.

| symbol | day | duplicates suppressed |
|---|---|---:|
| MARA | 2024-10-18 | 7 |
| QQQ | 2025-01-10 | 4 |
| HOOD | 2026-05-19 | 3 |
| NVDA | 2024-12-16 | 3 |
| QQQ | 2024-08-23 | 3 |
| AMZN | 2026-07-17 | 2 |
| GOOG | 2025-06-10 | 2 |
| IWM | 2025-09-05 | 2 |
| IWM | 2025-12-04 | 2 |
| MU | 2025-12-08 | 2 |
| QQQ | 2025-02-25 | 2 |
| AMD | 2026-05-14 | 1 |

## Mechanism

`_route` keeps a per-session set `self._fired_levels` keyed by `(symbol, direction, round(sig['stop'], 2))`. On the accept path (after the tight-stop gate, so a skipped tight stop never claims a level) a signal whose key is already present is suppressed with `[skip: repeat entry]`, unless it is an armed 84% re-entry. The level is its **price** (rounded to cents), not its name: two names at the same price on the same side is the same idea. The flag `NO_REPEAT_ENTRIES` defaults **True**; flip it False to measure the no-rule arm above.

