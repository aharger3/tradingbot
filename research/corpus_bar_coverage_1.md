# Corpus Bar Coverage - Shard 1 of 4

Reconstructed at T3 (shard report was absent from the worktree).
Shard rule: distinct (symbol, day) pairs from corpus_instances.jsonl,
sorted ascending by (symbol, day); pairs whose zero-based index % 4 == 0.

- Assigned: 914
- Already cached (present at T3 start): 831
- Newly fetched (T3 reconstruction): 70
- Skipped: 13
- Covered (cached + fetched): 901

## Skip reasons

| reason | count |
|---|---|
| weekend (non-trading day) | 11 |
| holiday/no-data (Polygon returned empty) | 2 |
