# Corpus Bar Coverage - Shard 3 of 4

Reconstructed at T3 (shard report was absent from the worktree).
Shard rule: distinct (symbol, day) pairs from corpus_instances.jsonl,
sorted ascending by (symbol, day); pairs whose zero-based index % 4 == 2.

- Assigned: 914
- Already cached (present at T3 start): 828
- Newly fetched (T3 reconstruction): 69
- Skipped: 17
- Covered (cached + fetched): 897

## Skip reasons

| reason | count |
|---|---|
| weekend (non-trading day) | 16 |
| holiday/no-data (Polygon returned empty) | 1 |
