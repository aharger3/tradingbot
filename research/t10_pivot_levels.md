# T10 — pivot structure as a first-class level: before / after

Detection replayed over **160 marked equity-pool (symbol, day) pairs** from `research/austin_marks_v7.jsonl`, once with `PIVOT_LEVELS=0` and once with it on. `s_explained` = an Austin S mark with ANY engine signal (fired or filtered) within ±2 bars of his marked entry — detection, not routing.

```
s_marks_total: 56
s_explained_before: 34
s_explained_after: 36
pivot_fires_per_day: 6.78
```

**Verdict: POSITIVE.**

## S marks a pivot level now accounts for

| mark | levels the engine now fires on |
|------|--------------------------------|
| AMD_2026-05-14_65 | pivot high @10:15 |
| INTC_2025-02-27_86 | pivot high @10:31 |

## Reading this

The gap this row was built to close is real in Austin's notes — 'pivot-structure break > level break', 'no clean break it just respect pivot structures', 'dont see any levels, unless some were forgot to be marked'. What the replay measures is narrower: whether a pivot level puts an engine SIGNAL within two bars of a mark that had none. Explaining a mark is necessary for agreement, not sufficient — a signal at the right bar with the wrong grade still disagrees with him, and that is T11's row.

Pivot levels are live: 1085 pivot-keyed signals across 160 days (6.78/day) with `PIVOT_STRENGTH=2` and a `PIVOT_LOOKBACK=30`-bar horizon. They are fed to break-and-retest exactly as named levels are, they cannot be seen before they complete (`usable_from = index + PIVOT_STRENGTH + 1`, asserted in `test_austin_tier.py`), and a pivot-keyed B&R carries `level_rank: 0` so T11 can read the ordering Austin asked for.
