# omen-3.4 — Frozen Inputs (T1)

Every path below is repo-relative and was resolved against the checked-out repository
on 2026-08-06. Every record count was produced by **parsing the file**, not read from a
filename, a prior doc, or this note. Downstream rows MUST read their paths and sizes from
this file and must not hardcode any path this file contradicts.

POPULATION_N: 1289

## Notes on the population integer

`POPULATION_N` is the trade count reported by parsing the engine population artifact
`backtest_metrics_full.json`, located at the repo ROOT (not under `research/`). That file is
a metrics summary (a JSON object), not a raw trade ledger; the trade count is the value at
`overall.trade_count`, read out of the parsed object:

```
json.load(open("backtest_metrics_full.json"))["overall"]["trade_count"] == 1289
```

Supporting figures parsed from the same object: `overall.wins == 490`,
`overall.losses == 795`, `overall.scratches == 4` (490 + 795 + 4 = 1289), and provenance
`_provenance.trading_days == 523`, `_provenance.symbol_count == 24`,
`_provenance.date_range_start == "2024-07-31"`, `_provenance.date_range_end == "2026-07-31"`.

Prior docs quote the same artifact as 875, 1,289, 1,982, 2,061, and 63,520 trades. Per the
T1 instruction these are NOT reconciled by argument; the file, when parsed, reports
**1,289**. That is the denominator for the whole version. (The other cited figures are not
reproduced by parsing any single file named here and are not used downstream.)

---

## Artifact 1 — Engine trade population (metrics)

- **Path:** `backtest_metrics_full.json` (repo ROOT)
- **Exists:** yes
- **Byte size:** 5,242 bytes
- **Parsed type:** JSON object (dict)
- **Top-level keys:** `_provenance`, `overall`, `per_signal_type`, `by_grade`,
  `per_anchor_x_direction`, `alert_only`
- **Record count:** 1,289 trades — read from `overall.trade_count` (the file summarizes
  trades; it is not a per-trade array). Cross-check: wins + losses + scratches = 490 + 795
  + 4 = 1,289.

## Artifact 2 — Predicate module

- **Path:** `predicates.py` (repo ROOT)
- **Exists:** yes
- **Byte size:** 11,751 bytes
- **Line count:** 324 lines
- **Record count:** 5 top-level predicate functions:
  `is_break_and_retest`, `is_order_block`, `is_84_reentry_opportunity`, `is_chop_market`,
  `is_x_signal`. (There are also 6 nested `@property` defs on a Candle dataclass —
  `body_size`, `upper_wick`, `lower_wick`, `range_size`, `is_bullish`, `is_bearish` — for
  11 total `def` statements. The population-relevant "records" are the 5 predicates.)
- **How counted:** `grep -nE '^def ' predicates.py` → 5 top-level definitions.

## Artifact 3 — 1-minute bar material: `backtest_charts.json`

- **Path:** `backtest_charts.json` (repo ROOT)
- **Exists:** yes
- **Byte size:** 2,693,799 bytes
- **Parsed type:** JSON array of trade objects
- **Record count:** 793 trade records. Each record is a trade dict with fields
  `symbol, day, setup, direction, grade, alert_only, outcome, htf_bias, entry, stop,
  target, exit_price, pnl, scaled, scale_level, runner_target, entry_i, exit_i, reason,
  levels, candles` — i.e. the embedded `candles` field carries that trade's 1-minute bars.
- **How counted:** `len(json.load(open("backtest_charts.json"))) == 793`.

## Artifact 4 — 1-minute bar material: `backtest_charts_12mo.json`

- **Path:** `backtest_charts_12mo.json` (repo ROOT)
- **Exists:** yes
- **Byte size:** 3,292,869 bytes
- **Parsed type:** JSON array of trade objects (same schema as Artifact 3)
- **Record count:** 974 trade records.
- **How counted:** `len(json.load(open("backtest_charts_12mo.json"))) == 974`.

## Artifact 5 — 1-minute bar material: `.cache/` (per-symbol pickle caches)

- **Path:** `.cache/` directory (repo ROOT), containing `*.pkl` files of the form
  `<SYMBOL>_29d_<YYYY-MM-DD>[_v2].pkl`
- **Exists:** yes
- **Byte size:** 32,748,330 bytes total across the directory
- **File count:** 61 pickle files
- **Parsed structure:** each pkl unpickles to a dict `{ "days": dict[day -> DataFrame],
  "hourly": list, "premkt": dict[day -> DataFrame] }`. The 1-minute bar rows live in the
  per-day DataFrames under `"days"`.
- **Record count (1-minute bars):** 435,234 minute bars total, summed across all 61 pkls by
  summing `df.shape[0]` over every day's DataFrame. (Example per-file: NVDA 29d 2026-07-05
  = 7,020 bars; AMD 29d 2026-07-07_v2 = 7,410 bars.)
- **How counted:** unpickled each of the 61 files and summed the row counts of every
  DataFrame in the `"days"` sub-dict. (Counting required `pandas`, which was installed to
  unpickle the DataFrames.)

## Artifact 6 — Hand-marked corpus

- **Path:** `research/blind_marks_all.jsonl`
- **Exists:** yes
- **Byte size:** 49,719 bytes
- **Parsed type:** JSON Lines (one JSON object per line)
- **Record count:** 260 records (260 non-blank lines, all 260 parse as valid JSON objects).
- **How counted:** iterate lines, skip blank, increment; `json.loads` each — 260 valid.

---

## MISSING

No file named in the T1 instruction is missing from the checked-out repo. Every path
named in this note resolves to an existing file:

- `backtest_metrics_full.json` — exists at ROOT
- `predicates.py` — exists at ROOT
- `backtest_charts.json` — exists at ROOT
- `backtest_charts_12mo.json` — exists at ROOT
- `.cache/` — exists at ROOT, 61 pkl files
- `research/blind_marks_all.jsonl` — exists

(The engine population summary is at the repo ROOT, not under `research/` — flagged here
because earlier work has looked for it under `research/` and not found it.)
