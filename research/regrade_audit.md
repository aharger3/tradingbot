# Austin Tier Re-Grade Audit

Source corpus: `research/blind_marks_all.jsonl`
Input rows (Austin hand-reviews): **162**

## Summary

- Total input rows: **162**
- Matched rows (identity triple `symbol|day|entry_i` found in corpus): **0**
- Unmatched rows: **162**
- Unique input triples: **159**
- Unique matched triples: **0**
- Duplicate input triples (marked twice, later kept): **2**

**Matched + Unmatched = 0 + 162 = 162 = total input rows (162).** ✓

## Before / After tier distribution

Distribution over the 117 marked entries (rows with `entry_i` + a tier). Unmarked `_no_trade` rows (143) carry no tier and are not re-gradable; they are excluded from this table.

| Tier | Before | After |
|------|-------:|------:|
| S | 50 | 50 |
| A | 67 | 67 |
| X | 0 | 0 |
| B | 0 | 0 |
| C | 0 | 0 |
| **total marked** | 117 | 117 |

Full-corpus line counts (260 lines) are unchanged by construction — only `tier` on matched rows is edited in place, no rows added or removed.

## Tier changes applied

**None.** Zero input triples matched a corpus entry, so no tiers were changed. The corpus file is left byte-identical (line count unchanged at 260).

## Unmatched triples (data problems — listed explicitly, not silently skipped)

162 input row(s) found no matching `symbol|day|entry_i` in `research/blind_marks_all.jsonl`. The corpus's marked entries share **zero** `(symbol, day)` pairs with the input set, so no entry_i alignment can recover a match — the input references trades that are not present in this corpus (the marking tool's day/index does not line up with the corpus).

### Duplicate input triples (marked twice; later occurrence kept)

- `IWM|2024-04-03|73` — input rows [17, 18]; kept row 18 (verdict `s`)
- `QQQ|2025-07-01|72` — input rows [155, 156, 157]; kept row 157 (verdict `x`)

### Every unmatched input row

| input row | symbol | day | entry_i | verdict |
|----------:|--------|------|--------:|---------|
| 0 | HOOD | 2025-08-04 | 40 | a |
| 1 | SOFI | 2026-03-11 | 63 | a |
| 2 | QQQ | 2025-06-25 | 48 | a |
| 3 | SPY | 2026-01-08 | 42 | x |
| 4 | MSFT | 2026-02-11 | 20 | a |
| 5 | QQQ | 2025-02-26 | 28 | s |
| 6 | SPY | 2026-02-09 | 24 | a |
| 7 | HOOD | 2026-05-19 | 19 | a |
| 8 | META | 2025-09-23 | 9 | a |
| 9 | NVDA | 2024-11-19 | 18 | a |
| 10 | COIN | 2025-10-21 | 8 | s |
| 11 | IWM | 2026-07-24 | 29 | s |
| 12 | QQQ | 2025-06-24 | 15 | s |
| 13 | META | 2026-06-10 | 18 | x |
| 14 | SPY | 2024-10-22 | 41 | a |
| 15 | MARA | 2025-08-18 | 23 | x |
| 16 | IWM | 2024-04-03 | 13 | s |
| 17 | IWM | 2024-04-03 | 73 | s |
| 18 | IWM | 2024-04-03 | 73 | s |
| 19 | AMZN | 2025-08-14 | 18 | x |
| 20 | CRM | 2025-07-02 | 17 | a |
| 21 | MARA | 2025-04-02 | 14 | a |
| 22 | BABA | 2025-07-22 | 20 | s |
| 23 | TSM | 2025-10-07 | 74 | a |
| 24 | QQQ | 2024-12-23 | 47 | a |
| 25 | CRM | 2026-05-07 | 18 | x |
| 26 | IWM | 2025-12-01 | 11 | s |
| 27 | SPY | 2026-03-25 | 10 | x |
| 28 | AMD | 2026-04-21 | 35 | a |
| 29 | GOOGL | 2025-08-07 | 18 | s |
| 30 | QQQ | 2024-05-08 | 8 | s |
| 31 | HOOD | 2025-03-04 | 44 | s |
| 32 | INTC | 2025-06-05 | 10 | x |
| 33 | QQQ | 2024-03-05 | 11 | a |
| 34 | QQQ | 2024-03-05 | 21 | s |
| 35 | QQQ | 2025-03-17 | 16 | s |
| 36 | SPY | 2024-04-03 | 9 | s |
| 37 | GOOG | 2025-06-10 | 21 | a |
| 38 | QQQ | 2026-02-11 | 32 | s |
| 39 | QQQ | 2026-02-11 | 45 | s |
| 40 | SPY | 2025-02-21 | 18 | x |
| 41 | IWM | 2025-09-05 | 12 | s |
| 42 | IWM | 2025-09-05 | 51 | a |
| 43 | QQQ | 2025-12-05 | 27 | s |
| 44 | QQQ | 2025-12-05 | 35 | s |
| 45 | CRM | 2025-06-02 | 27 | s |
| 46 | QQQ | 2025-03-18 | 13 | s |
| 47 | SPY | 2025-06-02 | 40 | a |
| 48 | QQQ | 2024-01-04 | 41 | s |
| 49 | MSFT | 2026-01-20 | 12 | s |
| 50 | IWM | 2024-02-28 | 9 | s |
| 51 | IWM | 2024-02-28 | 18 | a |
| 52 | AMZN | 2026-07-17 | 7 | a |
| 53 | COIN | 2026-03-04 | 43 | a |
| 54 | MU | 2025-11-07 | 22 | s |
| 55 | QQQ | 2025-01-16 | 23 | s |
| 56 | QQQ | 2025-12-30 | 24 | s |
| 57 | GOOG | 2025-12-08 | 58 | x |
| 58 | TSLA | 2026-02-18 | 42 | s |
| 59 | QQQ | 2024-10-03 | 18 | s |
| 60 | UBER | 2026-06-09 | 11 | a |
| 61 | NVDA | 2024-11-18 | 10 | s |
| 62 | QQQ | 2025-05-16 | 63 | a |
| 63 | IWM | 2025-04-10 | 16 | s |
| 64 | MARA | 2025-05-14 | 23 | x |
| 65 | GOOGL | 2024-09-03 | 10 | a |
| 66 | ORCL | 2025-11-03 | 17 | s |
| 67 | ORCL | 2025-03-28 | 12 | s |
| 68 | IWM | 2025-10-21 | 9 | s |
| 69 | HOOD | 2025-02-24 | 16 | a |
| 70 | QQQ | 2024-08-23 | 36 | s |
| 71 | UBER | 2025-09-11 | 15 | s |
| 72 | GOOGL | 2024-10-15 | 32 | s |
| 73 | NVDA | 2024-12-16 | 12 | a |
| 74 | MSFT | 2025-03-04 | 13 | s |
| 75 | QQQ | 2025-01-10 | 13 | s |
| 76 | TSLA | 2024-03-27 | 13 | s |
| 77 | QQQ | 2026-03-04 | 42 | s |
| 78 | MARA | 2026-07-09 | 19 | s |
| 79 | CRM | 2025-11-18 | 16 | a |
| 80 | NVDA | 2024-12-30 | 34 | a |
| 81 | MU | 2026-01-28 | 13 | s |
| 82 | SPY | 2025-09-25 | 45 | a |
| 83 | HOOD | 2026-04-13 | 16 | s |
| 84 | SPY | 2025-02-20 | 35 | a |
| 85 | TSM | 2026-05-29 | 23 | s |
| 86 | GOOG | 2026-02-23 | 19 | x |
| 87 | MARA | 2026-07-17 | 13 | a |
| 88 | SPY | 2024-02-22 | 25 | a |
| 89 | UBER | 2026-01-06 | 22 | a |
| 90 | SPY | 2025-11-05 | 52 | a |
| 91 | QQQ | 2024-02-01 | 44 | x |
| 92 | SPY | 2026-03-03 | 17 | s |
| 93 | IWM | 2024-03-22 | 24 | s |
| 94 | SPY | 2025-03-18 | 13 | s |
| 95 | PLTR | 2024-10-23 | 21 | s |
| 96 | QQQ | 2026-07-09 | 11 | s |
| 97 | ORCL | 2026-06-09 | 8 | a |
| 98 | SPY | 2026-05-05 | 10 | a |
| 99 | AMD | 2026-05-14 | 25 | a |
| 100 | HOOD | 2026-02-05 | 40 | s |
| 101 | TSLA | 2024-12-03 | 8 | a |
| 102 | IWM | 2024-08-22 | 27 | s |
| 103 | COIN | 2025-12-01 | 11 | a |
| 104 | QQQ | 2024-01-30 | 35 | x |
| 105 | ORCL | 2025-07-08 | 7 | s |
| 106 | TSLA | 2024-06-24 | 9 | s |
| 107 | UBER | 2026-07-06 | 12 | s |
| 108 | QQQ | 2026-03-06 | 47 | x |
| 109 | MARA | 2025-07-30 | 30 | a |
| 110 | MARA | 2024-09-09 | 38 | x |
| 111 | IWM | 2026-06-24 | 28 | a |
| 112 | MARA | 2024-10-18 | 11 | s |
| 113 | HOOD | 2026-07-07 | 37 | a |
| 114 | TSLA | 2024-02-05 | 16 | a |
| 115 | MU | 2025-12-08 | 12 | x |
| 116 | UBER | 2025-07-31 | 48 | a |
| 117 | PLTR | 2026-03-31 | 23 | s |
| 118 | IWM | 2026-05-28 | 46 | s |
| 119 | MARA | 2024-12-17 | 49 | s |
| 120 | SPY | 2025-12-02 | 14 | x |
| 121 | AMD | 2025-06-05 | 6 | s |
| 122 | IWM | 2024-08-01 | 44 | a |
| 123 | QQQ | 2024-03-15 | 11 | s |
| 124 | MSFT | 2026-06-10 | 17 | a |
| 125 | UBER | 2025-02-07 | 22 | s |
| 126 | CRM | 2025-09-26 | 12 | a |
| 127 | PLTR | 2025-09-18 | 14 | s |
| 128 | SOFI | 2024-10-30 | 16 | s |
| 129 | QQQ | 2025-01-28 | 40 | a |
| 130 | QQQ | 2024-12-16 | 28 | s |
| 131 | MARA | 2026-07-20 | 11 | a |
| 132 | SOFI | 2026-05-20 | 55 | a |
| 133 | NVDA | 2025-03-25 | 25 | a |
| 134 | COIN | 2025-06-26 | 18 | s |
| 135 | TSLA | 2024-01-12 | 18 | x |
| 136 | QQQ | 2025-05-07 | 31 | a |
| 137 | HOOD | 2025-12-29 | 12 | x |
| 138 | ORCL | 2025-09-17 | 11 | a |
| 139 | AMD | 2026-03-04 | 9 | a |
| 140 | AMZN | 2026-04-10 | 74 | a |
| 141 | UBER | 2025-08-13 | 25 | s |
| 142 | IWM | 2025-12-04 | 56 | s |
| 143 | IWM | 2024-09-24 | 35 | x |
| 144 | IWM | 2024-09-24 | 53 | x |
| 145 | HOOD | 2026-07-10 | 23 | s |
| 146 | SPY | 2025-07-01 | 41 | a |
| 147 | GOOG | 2025-04-04 | 26 | a |
| 148 | SPY | 2024-06-11 | 23 | s |
| 149 | SPY | 2026-03-02 | 24 | s |
| 150 | COIN | 2026-04-09 | 30 | s |
| 151 | SPY | 2026-03-05 | 56 | s |
| 152 | NVDA | 2026-05-21 | 10 | a |
| 153 | MSFT | 2025-03-20 | 28 | s |
| 154 | BABA | 2025-12-26 | 36 | a |
| 155 | QQQ | 2025-07-01 | 72 | x |
| 156 | QQQ | 2025-07-01 | 72 | x |
| 157 | QQQ | 2025-07-01 | 72 | x |
| 158 | SPY | 2025-11-19 | 9 | s |
| 159 | SPY | 2024-09-19 | 19 | s |
| 160 | QQQ | 2025-02-25 | 16 | s |
| 161 | QQQ | 2025-02-25 | 53 | a |

---
Verdict code map: `s`→S, `a`→A, `x`→X (old B/C tiers would also be overwritten per the S/A/C/X ladder; none present in this corpus).
