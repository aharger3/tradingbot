# Corpus Bar Coverage (merged, shards 1-4)

Merged from the four shard reports research/corpus_bar_coverage_1..4.md.

**Reconstruction note.** The four per-shard reports produced by T2.1-T2.4 were
absent from this runner's worktree at T3 time (the shard runners write only their
sentinel file; they do not commit research/ artifacts back to the repo). The cache
directory `data_archive/` they populated WAS present, so coverage was reconstructed
directly from it: **cached** = bars present in data_archive at T3 start;
**fetched** = bars pulled during T3 reconstruction of the pairs that were still
missing (281 weekday pairs the shards had not banked were recovered here);
**skipped** = pairs Polygon has no bars for (weekends, holidays). The covered
count below is the denominator T4 divides by.

## Summed totals

| metric | shard 1 | shard 2 | shard 3 | shard 4 | total |
|---|---|---|---|---|---|
| Assigned | 914 | 914 | 914 | 913 | 3655 |
| Already cached | 831 | 825 | 828 | 830 | 3314 |
| Newly fetched (T3) | 70 | 71 | 69 | 71 | 281 |
| Covered (cached+fetched) | 901 | 896 | 897 | 901 | 3595 |
| Skipped | 13 | 18 | 17 | 12 | 60 |

**Covered total: 3595** of 3655 assigned distinct (symbol, day) pairs.

## Skip reasons (merged, grouped)

| reason | count |
|---|---|
| weekend (non-trading day) | 56 |
| holiday/no-data (Polygon returned empty) | 4 |

Total skipped: 60
