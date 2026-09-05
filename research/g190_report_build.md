BLOCKED: not blocked — done. One sentence: `research/build_report_9_0.py` builds
`research/omen-9-0-report.html`, a static, self-contained, phone-readable
summary page (18.3 KB, well under the 8 MB cap) rolling up every phase of the
09-05 overnight swarm (F5/F6/F7/F8/F9, O1/O2, P0-P4, lane slices, the bug
sweep) into summary tables only — no per-trade dump.

## What it contains

- **Lane slices** (full pool vs index-3), one-trade-a-day unit, from
  `research/g174_funding_ladder.json`.
- **Phase F**: all 9 F5 rule-sweep headline arms (script, baseline $/day,
  candidate $/day, H1/H2 deltas, precision before/after, F6 verdict — 8 of 9
  REFUTED 3/3), F7's S_CLASSIFIER v0 arm and its split verdict (money delta
  refuted, "honest zero" precision/recall not refuted), F9's mid-candle arms,
  F8's ML-ceiling null result.
- **Phase O**: the O1 tweak-grid table (40 of its arms; full grid in
  `research/g160_tweak_grid.json`) and the O2 ship-nothing-as-default note.
- **Phase P**: funding-ladder streams (index/S-only/full-pool) with H1/H2,
  the corrected all-starts pass-rate table (replacing P1's refuted 0.0%
  rolling-252 headline), and the "what it would take" drift-to-50% table.
- **Bug sweep**: 71 raw findings, 15 confirmed and fixed.

Every table's fill is named once at the top of the page (signal-bar CLOSE
entry, `stop_rule.stop_fill_price` stops, `signal_runner.min_risk_floor` size
gate, 1R=$1,000, H1/H2 split 2025-09-01, book
`research/bt2y_trades_retest_on.json`) rather than repeated per-row, since
every table on the page shares it; per-arm exceptions (F9's mid-candle fills,
P1's futures-point mapping) are called out in their own section text.

## Known gap

"Core 10" lane slice is listed in the lane table but marked "not measured
this session" — no script tonight produced that specific slice, and the row
does not fabricate a number for it.

## Verify

- `python -c "import html.parser; html.parser.HTMLParser().feed(open('research/omen-9-0-report.html',encoding='utf-8').read())"` — parses clean.
- File size 18.3 KB < 8 MB.
- Every arm named in Phase F (9 of 9 rule slugs), Phase O (baseline + grid
  arms), Phase P (3 streams x H1/H2/full) has a row — confirmed by substring
  search over the rendered HTML.
- Copied to `C:/Users/aharg/Desktop/AI-Outputs/omen-daily/omen-9-0-report-2026-09-05.html`.

Committed: `research/build_report_9_0.py` and this report only (the HTML
output is gitignored per `research/*.html` and intentionally not committed,
per the row's own instruction).
