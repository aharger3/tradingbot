# Adversarial rechecks, 2026-09-03

Sixteen scripts written on 2026-09-03 to attack the numbers that went into
`research/MASTER_SPEC.md` and `research/MORNING_REPORT.md`. Each one recomputes a
published figure **without importing the module that published it**, so a bug in
the original rig cannot reproduce itself in the check. They lived in a scratchpad
and were orphaned; omen-8 ticket 12(c) says commit them, because
`CLAUDE.md`'s rule is: *if you publish a number, commit the script that made it.*

They are historical artifacts, not a maintained suite. Several hardcode the repo
path and one pair writes/reads `zz_tl.pkl` in the working directory. They are kept
for provenance — do not wire them into `verify:`.

| script | what it refutes or confirms |
|---|---|
| `adv.py` | The stop-placement sweep. Reads `data_archive` CSVs directly, re-derives `min_risk_floor`, and reimplements the resim from the stated rules with no engine import. |
| `adv2.py` | That the stop-placement arms are actually distinct — resims every arm keyed by row index so the arms can be intersected instead of compared as aggregates. |
| `adv3.py` | The claimed −1R stop fill. Runs three fill models side by side (`claim` = close-triggered capped at −1R, `honest` = filled at the close uncapped, `touch` = intrabar touch filled at the level) to show which one the book actually matches. |
| `adv4.py` | The same three fill models carried through `omen_metrics.evaluate_prop_challenge` / `first_of_day_arm`, i.e. whether the fill model changes the prop-eval pass/fail verdict, not just the mean R. |
| `adv5.py` | The 1D-level veto's economics on the first-size-gated-candidate arm — n, EV, total R, $/day over 498 sessions, and months green, base vs `level_tf != "1D"`. |
| `adv6.py` | The same veto with the Thursday effect stacked on it, plus max drawdown / profit factor / win rate — a check that the 1D lift is not a day-of-week artifact wearing a level label. |
| `adv113.py` | The g113 ladder-shape table. Independent bar-walk against the book, no `g113` import. |
| `adv113b.py` | R1's "max loss is −1R hard": min R per ladder arm, and counts of rows below −1.0 and below −1.0001. Also whether the four-rung arms are per-row identical (i.e. whether the table has fewer real arms than rows). |
| `adv113c.py` | Start-date robustness of the ladder arms — rolling 12-month-plus windows at $200 and $100 per trade, so an arm that only passes from one lucky start date shows up. |
| `adv113d.py` | Position-size robustness of the same arms: pass rate across eight risk sizes ($75–$300) crossed with every rolling start date, on the $50k eval. |
| `adv_targets.py` | `research/sweep_targets_flat.py`. Nothing imported from it; bars from `polygon_feed`, `min_risk_floor` re-derived from `signal_runner` *and* cross-checked against the literal formula. |
| `zz_tl_adv.py` | The level-snapping target rule: for each tolerance, compares snap-to-named-level against a constant-distance control set at the same mean distance, so the credit goes to the level rather than to the extra distance. Writes `zz_tl.pkl`. |
| `zz_tl_adv2.py` | Whether the snap's edge is concentrated in a handful of rows — sign counts and concentration of the paired differences, split at the 2025-09-01 out-of-sample cut. |
| `zz_tl_adv3.py` | The same tolerances against Austin's actual bar (pass one $50k eval inside 12 months), rather than against mean R. |
| `zz_tl_adv4.py` | Significance of the snap edge: 20,000-sample bootstrap and paired sign-flip permutation p-values per tolerance, plus year-1/year-2 sign agreement. |
| `tgtadv_unique_9f3.py` | The target sweep on a fresh, independently rebuilt first-of-day set (bars from `polygon_feed`, floor from `signal_runner.min_risk_floor`), split in half by date to check the winner is the same in both halves. |
