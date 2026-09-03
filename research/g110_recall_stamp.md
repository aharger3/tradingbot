---
date: 2026-09-03
row: S1
status: blocked
---

# S1 — stamp one honest recall number into the gate scoreboard

BLOCKED: research/g72_recall278_paired.py not in repo

Checked both fallback paths named in the spec:

- `research/g72_recall278_paired.py` — absent from this clone (`aharger3/tradingbot`,
  HEAD `82a4a4cbb`).
- `research/g72_recall278_report.md` — also absent (this is the file the vault's
  `Projects/omen-2y-backtest.md` cites at line 20 as the source of the "corrected recall,
  never previously written into the vault" table).
- `research/g85_recall_honest.md` — also absent (cited by the vault at line 36 for the
  59.1% old-fill vs 74.3% honest-fill split).

All three inputs this row depends on were produced on a machine whose research/ output
isn't in this GitHub clone (per CLAUDE.md, `research/*.jsonl` and `research/*.html` are
gitignored with explicit un-ignore rules for judgement files only — these three files are
`.py`/`.md`, so their absence means they were never committed at all, not filtered by
gitignore).

## plain

Couldn't stamp the recall number because the two files it comes from were never pushed to
GitHub — nothing changed in the scoreboard.

No code change made. No vault edit made (the disputed 67.6%/52.9% figures in
`Projects/omen-2y-backtest.md` stand as-is until the source files are available).
