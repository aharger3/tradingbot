# g214 — Hypothesis: "perfect" marks are earlier and higher-leverage

**Question:** Austin's hypothesis (2026-09-05): "the ones where im like 'perfect' or dont have any comments are the higher leverage ones and they likely happen earlier in the day."

**Data:** All S-graded marks across all corpora (austin_marks_v7.jsonl, research/marks/*.jsonl, recovered_reviews.jsonl, etc.), matched to backtest results in research/bt2y_trades_retest_on.json.gz.

## Groups

Marks split into three categories by comment presence and content:

| Category | Count | Index | Single | Traded | Notes |
|---|---:|---:|---:|---:|---|
| **No comment / empty** | 424 | 146 | 278 | 133 | Baseline: no notes at all |
| **"Perfect" / "clean" / "textbook" / "beautiful" / "great"** | 12 | 1 | 11 | 9 | **Too small for verdict** — below 30 rows |
| **All other S marks** | 171 | 18 | 153 | 56 | Descriptive text but no key words |

**Total distinct marks:** 607. **Duplicate symbol-days:** 467 pairs graded multiple times across corpora; 459 agree on category, 8 disagree.

## Time of Day

Entry time recorded in 131/607 marks (21.6%). Only "no comment" group has sufficient cases (88 of 424).

| Category | With times | Range | Median |
|---|---:|---|---|
| No comment | 88 / 424 | 09:33–10:32 | 09:49 |
| Perfect | 2 / 12 | 09:43–09:43 | 09:43 |
| Other | 42 / 171 | 09:36–10:23 | 09:51 |

**Finding:** "Perfect" marks are numerically 6 minutes earlier (09:43 vs 09:49), but only 2 cases have times — not testable.

## Engine Performance on Traded Days

Match each mark's symbol-day to backtest trades and compute mean R-multiple and win rate.

| Category | Mean R | Win Rate | N traded |
|---|---:|---:|---:|
| No comment | −0.003 | 48.9% | 133 |
| **Perfect** | **+0.575** | **66.7%** | **9** |
| Other | −0.021 | 49.1% | 56 |

**Single strongest signal:** The 9 "perfect" marks that appear in the backtest show +0.575R mean (vs −0.003 for no_comment) and 66.7% win rate (vs 48.9%). But n=9 is below the 30-trade threshold.

## Setup Distribution

(Partial — only 67 of 607 marks carry setup labels)

| Setup | No comment | Perfect | Other |
|---|---:|---:|---:|
| BR (Break-and-retest) | 38 | 8 | 71 |
| OCR (Open candle retest) | 28 | 0 | 8 |
| 84% (Reclaim) | 1 | 0 | 18 |

All 8 "perfect" marks with setup are BR — too small to separate the signal.

## Symbol Class

| Class | No comment | Perfect | Other |
|---|---:|---:|---:|
| Index (QQQ/SPY/IWM) | 146 (34%) | 1 (8%) | 18 (11%) |
| Single names | 278 (66%) | 11 (92%) | 153 (89%) |

"Perfect" marks skew heavily toward single names (11 of 12).

## Conclusion

**What this CAN establish:** Marks with no comment or the keyword "perfect" in the note exist as a small, distinct population; the 12 "perfect" marks are 92% single-name stocks and show a marked engine-R jump (+0.575 vs −0.003) on the handful (n=9) that were backtested. The no-comment group (n=424) forms a stable baseline. Time-of-day exists as a numerical correlation (09:43 vs 09:49 median) but affects only the 2 marks with recorded entry times.

**What this CANNOT establish:** Whether the "perfect" label predicts edge or is an ex-post rationalization. The 9 traded cases are below the spec's 30-trade minimum. No statistical test is valid on n=9. Time-of-day correlation rests on 2 data points. Setup analysis is artifact of low count (0 OCR in perfect group). The 467 duplicate symbol-days and their agreement patterns are evidence of corpus depth but do not address the hypothesis.

**One-line answer:** "Perfect" marks show higher engine precision on a too-small sample (n=9 trades); earlier entry time (09:43) is numeric but untestable (n=2 with times). The hypothesis is suggestive, not conclusive. Requires either 21+ more "perfect" traded days or a different measurement unit (e.g., precision on marked S days within the full 607-day pool, not just engine trades).
