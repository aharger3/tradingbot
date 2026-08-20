# OMEN 5.2 — Marks summary (T1)

Source mark files (copied byte-for-byte into `research/marks/`):

- `research/marks/deck_marks_index_2026-08-19.jsonl` — QQQ (30) + SPY (30) day cards, 60 day cards / 37 trade marks
- `research/marks/deck_marks_tsla_2026-08-20.jsonl` — TSLA 60 day cards / 27 trade marks

Each line is a JSON object of `type` `day` or `trade`. `day` rows carry
`grade` (S / A / C / none) and `day_type`; `trade` rows carry bar indices
(`entry_i`, `stop_i`, `exit_i`), prices, side, and `r_multiple` — which is the
**tranche-1 only** result (see omen-5.2.md: the runner is unmarked).

## Counts

day_cards: 120
trade_marks: 64
tranche1_mean_r: 1.2416
tranche1_win_rate: 0.9016

## Notes on the tranche-1 stats

- 61 of the 64 trade marks carry a numeric `r_multiple`; 3 (`QQQ_2026-07-27`,
  `SPY_2026-07-02`, `TSLA_2026-06-12`) have `r_multiple: null` and are excluded
  from both the mean and the win rate (a null tranche-1 R is a missing exit,
  not a zero).
- Mean tranche-1 R = 55 wins / 6 losses over those 61 marks; 0 scratches.
  Win rate = 55 / 61 = 0.9016.
- These are **hindsight marks** — Austin marked tranche 1 knowing how the day
  resolved. This is calibration, not a live win rate (T7 must say so).
