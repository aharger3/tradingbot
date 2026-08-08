# bar_coverage_v2

Per-mark archive coverage for `research/austin_marks_v2.jsonl` (159 marks, 151 distinct symbol-days), recomputed against `data_archive/` after the omen-corpus-1.0 backfill (PR #8) and the T1 backfill.

- Covered symbol-days (archive file exists): **151 / 151**
- Covered marks (archive file exists): **159 / 159**
- Marks usable (file exists AND entry_i < n_rth): 159 / 159
- Still-missing symbol-days (no archive file): **0**
- Marks dropped for entry_i out of range: 0

A symbol-day is *covered* iff `data_archive/<SYMBOL>/<DAY>.csv` exists. Of the **49** distinct `no_archive_file` symbol-days (54 marks) in the 3.6 `bar_coverage.md`, the omen-corpus-1.0 backfill (PR #8, 13,815 CSVs) already resolved **17** and T1 had to fetch the remaining **32** — all 32 returned bars from Polygon (HTTP 200, non-empty), so the on-disk set went 119→151 covered. `IWM` and `GOOG` are now in `archive_1m.py`'s `SYMBOLS` list (and `live_scanner.DEFAULT_SYMBOLS`), so future daily runs bank them too.

## Still-missing pairs

None. Every one of the 151 marked symbol-days now has an archive file on disk; the T1 fetch returned bars (HTTP 200, non-empty results) for all 32 pairs that were missing after the corpus backfill.

