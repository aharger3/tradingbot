# Corpus Bar Coverage - Shard 2 of 4

Reconstructed at T3 (shard report was absent from the worktree).
Shard rule: distinct (symbol, day) pairs from corpus_instances.jsonl,
sorted ascending by (symbol, day); pairs whose zero-based index % 4 == 1.

- Assigned: 914
- Already cached (present at T3 start): 825
- Newly fetched (T3 reconstruction): 71
- Skipped: 18
- Covered (cached + fetched): 896

## Skip reasons

| reason | count |
|---|---|
| weekend (non-trading day) | 17 |
| holiday/no-data (Polygon returned empty) | 1 |
