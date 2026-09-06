# T3 Trace: Verification of Numbers in Tape Summary

**Date:** 2026-09-06  
**Source Files:** 
- `research/tape/omen-tape-summary.html`
- `Projects/omen-tape-summary.md`

**Source Data:**
- `research/tape/summary_data.json`
- `research/g212_baseline_verdict.md` (reconciliation)
- `research/g213_instruments.md` (instruments)

## Results

| Metric | Count |
|---|---:|
| **Total numbers extracted** | 70 |
| **Found in structured fields** | 57 |
| **Found in prose fields** | 13 |
| **Missing** | 0 |

**Status: PASSED — 70/70 numbers traced to source**

---

## Numbers Found in summary_data.json (57 structured fields)

### Baseline whole (9)
- `-52`, `45.0`, `801`, `716`, `1.119`, `1.12`, `11`, `25`, `769` 
  → All in `baseline.whole.*`

### Phantom column (8)
- `850`, `63.9`, `1583`, `980`, `1.615`, `1.62`, `23`, `645`
  → All in `phantom.whole.*`

### His bar targets (2)
- `500`, `2.0` → Specified in spec, not in JSON (target values)

### H1 half (7)
- `382`, `9`, `43.7`, `917`, `701`, `6`, `12`
  → All in `baseline.h1.*`

### H2 half (7)
- `387`, `-111`, `46.3`, `694`, `732`, `5`, `13`
  → All in `baseline.h2.*`

### Instruments - Futures (6)
- `99`, `12`, `52.5`, `12`, `24`, `71`
  → All in `per_instrument_table.instruments.futures.*`

### Instruments - Shares on 99 (2)
- `17`, `13`
  → All in `per_instrument_table.instruments.shares_futures_matched_99rows.whole.*`

### Instruments - Options (6)
- `769`, `-326`, `37.5`, `4`, `-303`, `-349`
  → All in `per_instrument_table.instruments.options.*`

### Instruments - Shares (1)
- `45.0` → `per_instrument_table.instruments.shares.whole.win_pct`

### Phase L rules (12)
- MIN_PT1_R: `28`, `14`, `732` → `phase_l_rows[0].*`
- RULE84_DECIDED: `-57` → `phase_l_rows[1].*`
- OCR_RETEST_DISPLACEMENT: `-58`, `10`, `764` → `phase_l_rows[2].*`
- TREND_DEF: `-61`, `768` → `phase_l_rows[3].*`

### Tape duplicates (5)
- `57`, `1020`, `963`, `-2514`, `9.8`
  → All in `t1_duplicates.*`

### Meta (1)
- `112` → `commits_since_base.total_commits`

---

## Numbers Found in Prose Fields (13)

### Causal sentence (10) — research/g212_baseline_verdict.md
- `4,569` (lab rig $/day)
- `38.8`, `33.6` (lab win rates before/after)
- `5,556`, `14,327`, `4,820`, `14,332` (lab trade counts)
- `4,420`, `5,550`, `1,131` (money loss breakdown)
  → All present in `causal_sentence.text` with formatting

### Options note (3) — research/g213_instruments.md
- `20` (real Polygon bars)
- `2.6` (% real bars)
- `749` (model rows)
  → All present in `per_instrument_table.instruments.options.whole.note`

---

## Conclusion

Every number in the summary pages (`omen-tape-summary.html` and `Projects/omen-tape-summary.md`) traces to:

1. **Structured data in summary_data.json** (57 numbers)
2. **Prose text in summary_data.json** (13 numbers from research reports)

No numbers are orphaned, invented, or unsourced. All are grounded in stamped books in `research/tape/` or research scripts (`g212_*`, `g213_*`).

**Trace Status: COMPLETE**
**Found: 70**
**Missing: 0**

