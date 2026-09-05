# g154/F5 -- ocr-strict-definition

**What is different now:** applied `signal_runner`'s own strict OCR definition (`OCR_STRICT`, default OFF, `signal_runner.py:63` -> `omen_bot.ocr_is_his`: clear break + quick + strong PA) as a post-hoc filter over the committed book's OCR-derived rows -- no engine re-run, just the same feature computed from `data_archive` bars up to the signal bar.

Book `bt2y_trades_retest_on.json`, 498 sessions (H1 249 / H2 249), size-gated on `signal_runner.min_risk_floor`. 1R = $1000. H1/H2 split at 2025-09-01.

## OCR-touched rows in the one-trade-a-day candidate population

6519 rows in the candidate population match `setup == 'one_candle_rule' or confluence == 'yes'` (8227 total candidates). Of those, **44 survive** `ocr_is_his` (0.7%); 0 had no readable `data_archive` bars for that (sym, day, entry_i); 6475 had readable bars but failed the anatomy detector or one of clear-break/quick/strong-PA.

## Baseline vs arm (first-of-day, size-gated)

| arm | $/day | H1 $/day | H2 $/day | mean R | win | months green | max DD | cand/day | fires/day | recall_100 | recall_all | precision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline (no OCR filter) | $34 | $136 | $-68 | +0.034 | 46.5% | 13/25 | $-21405 | 16.5 | 1.000 | 15/34 | 169/345 | 18/59 |
| **arm** (drop OCR-touched failing ocr_is_his) | $-37 | $50 | $-123 | -0.040 | 42.3% | 11/24 | $-40577 | 3.5 | 0.918 | 1/34 | 50/345 | 19/54 |

## Verdict

H1 delta $/day: -86. H2 delta $/day: -55. Precision delta: +0.0468. Survivor (H1 and H2 both improve $/day or precision, recall_100 not below baseline): **False**.
