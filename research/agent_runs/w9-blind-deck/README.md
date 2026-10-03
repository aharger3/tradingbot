# W9 blind stock deck

Paper research, not investment advice, no orders. Pre-registration: `life-plan/07-money/omen/night-1003/prereg-blind-stocks.md` (the build refuses to run unless it already contains the sha256 of `w9_blind.py`, `w9_build.py`, `judged_marks_keys.txt` and `s2_lib.py`).

- `w9_build.py OUTDIR PREREG [--dry-run]`: draws 20 decks x 40 cards from engine candidates on dates where nothing was ever marked, renders chart-cut PNGs (nothing after the decision bar, no ticker/date/absolute price), seals the outcomes (frozen `s2_lib.sim`) in `sealed.bin`, writes `deck.json` (public: card ids, image hashes, commitment). Key file: `%LOCALAPPDATA%\w9-blind\seal.key`, created once, never overwritten.
- `w9_blind.py serve|status|verify|score`: runtime, stdlib + numpy + cryptography only (the build copies it next to the deck). `score` refuses until the verdict locks (first complete deck with >= 30 cumulative S taps, or all 20 decks) and aborts if the sealed file does not match the commitment.
- Needs `OMEN_DATA_DIR` pointing at a checkout with `data_archive/` and `research/tape/` (same as S2).
- Tests: `python -m pytest research/agent_runs/w9-blind-deck -q`.
- `judged_marks_keys.txt`: the 1,273 ticker-days in `marks_pool.canonical_pool()` (dates of these are excluded from the pool).
