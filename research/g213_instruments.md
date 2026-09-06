# g213 -- instrument columns, T2

Baseline: `baseline_2026-09-05.json.gz` (book_id 2c39ced2697c26cc), unit `up_to_3_stop_win_or_2loss`, universe.CORE_SYMBOLS (tier=='core', 11 symbols), fill=close. 769 unit rows priced. Script: `research/g213_instruments.py`.

Options priced from real Polygon 1-minute option aggregates for **20 of 769 rows (2.6%)**; the rest (749 rows) fall back to the 0.42-delta + $0.05-spread model because the wall-clock fetch cap (110 min) was reached, a contract/expiry was not listed, or Polygon returned 403/no data for that leg. `instrument_source` on every row in `research/tape/instruments_2026-09-05.json.gz` says which.

Futures ratio (SPY->MES 10.0x, QQQ->MNQ 41.35x) is a rule-of-thumb, **not fit to data** -- no ES/MES or NQ/MNQ 1-minute bars exist under `data_archive/` on this box, so `research/g213_verify.py` reports this UNVERIFIED rather than checked against a 7-day overlap (the row's own fallback clause). IWM->M2K is defined but never exercised: IWM is not in `universe.CORE_SYMBOLS`.

Sample-size rule (SWARM.md): a cell under 30 trades or 12 months gets no verdict, just the count -- marked inline below. Only 20 rows are real-priced, so the real-vs-model split itself has no verdict either; it is a coverage number, not a comparison.

Why the options model column is this negative: at this engine's typical stop distance, a delta-sized position needs dozens of contracts to reach $1,000 of risk (median ~34 contracts across the model-priced rows here), and the flat $0.05 round-trip spread cost scales with contract count -- median spread cost per trade is **$340**, before the option has moved at all. That is a real structural cost of trading tight-stop setups as options, not a modeling artifact; the 15 real-bar rows above show the same-shaped trades landing both ways (wins to +$4,895, losses to -$1,700) but are too few to say whether the model's spread drag overstates or understates the real cost.

## Shares (769 trades)

- whole window: $-52/day, mean R -0.034, win 45.0%, 11/25 green months
- H1 (before 2025-09-01): $9/day, mean R 0.006, win 43.7%, 6/12 green months
- H2 (2025-09-01 on): $-112/day, mean R -0.072, win 46.3%, 5/13 green months

## Futures (99 trades)

- whole window: $12/day, mean R 0.058, win 52.5%, 12/24 green months
- H1 (before 2025-09-01): $71/day, mean R 0.375, win 63.8%, 9/12 green months
- H2 (2025-09-01 on): $-48/day, mean R -0.229, win 42.3%, 3/12 green months

## Options (769 trades)

- whole window: $-607/day, mean R -0.393, win 31.8%, 2/25 green months
- H1 (before 2025-09-01): $-632/day, mean R -0.410, win 28.9%, 1/12 green months
- H2 (2025-09-01 on): $-583/day, mean R -0.377, win 34.6%, 1/13 green months

Single names (AAPL AMD AMZN GOOGL META MSFT NVDA PLTR TSLA) have no futures column (`instrument: "n/a"` on those rows) -- only SPY and QQQ trade as futures micros in this universe.
