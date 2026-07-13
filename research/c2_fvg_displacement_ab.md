# C2 — FVG_RETEST displacement-anchored variant A/B: ON vs OFF (2026-07-13)

**Flag:** `FVG_RETEST` module global in `signal_runner.py:62`
(default **OFF**). `True` = break-&-retest entry may retest the displacement
FVG zone (the gap left by the break-leg displacement move) instead of the raw
level — the "displacement-anchored detector" the old 07-05 comment said was
missing. No env var — hardcoded constant, flipped at runtime for the ON run
via module-global mutation (`signal_runner.FVG_RETEST = True` before
`backtest_12mo.main()`), the same mechanism `backtest_12mo.py:94` uses for
`ENTRY_CUTOFF` and the `--dry-run` harness uses at `signal_runner.py:964`.
**No signal-logic edits.** `signal_runner.py` / `omen_bot.py` untouched;
config defaults unchanged (OFF is the shipped default; `BNR_DISPLACEMENT_GATE`
also OFF in both runs).

**Mechanism check (flag actually took effect):** OFF 9,423 sig / 866 charted;
ON 17,623 sig / 2,341 charted — the FVG-retest path fired and nearly doubled
the signal population. Grade distribution shifts (A 47→140, B 613→1,355,
C alerts 195→835) confirm the anchored detector routed a large new set of
FVG-zone retests into A/B grading. 84% re-entry triggers jumped 87→181.

**Run:** `backtest_12mo.py 365`, Polygon 1m cache, `py -3.13`, 250 sessions,
28 symbols, $1k flat risk. Both runs full trade populations (no rate-limit
zeros). Analyzer: `research/c2_analyze.py` (reuses `c1_analyze.py` /
`b4_analyze.py` gstats + tier_sim verbatim). Raw logs `c2_off_run.log` /
`c2_on_run.log`.

## Headline

| Metric | OFF (baseline) | ON | Δ |
|---|---|---|---|
| Traded (A+/A/B) | 671 tr, 37.5%W, +$78,190 | 1,506 tr, 34.7%W, +$51,436 | +835 tr, −2.8%W, −$26,754 |
| **S≥4+[hammer] tier** | **78 tr, 42.3%W, +$21,000/yr ($1,750/mo)** | **63 tr, 38.1%W, +$9,000/yr ($750/mo)** | −15 tr, −4.2%W, −$12,000/yr |

## Grade distribution + P&L by grade

| Grade | OFF n | OFF W/L | OFF Win% | OFF P&L | ON n | ON W/L | ON Win% | ON P&L |
|---|---|---|---|---|---|---|---|---|
| A+ | 11 | 3/8 | 27.3% | −$2,000 | 11 | 3/8 | 27.3% | −$2,000 |
| A | 47 | 16/31 | 34.0% | −$393 | 140 | 48/91 | 34.5% | −$1,547 |
| B | 613 | 232/380 | 37.9% | +$80,584 | 1,355 | 468/877 | 34.8% | +$54,983 |
| C (alert-only) | 195 | 55/140 | 28.2% | (−$32,045 if traded) | 835 | 266/564 | 32.0% | (−$37,163 if traded) |

The FVG variant more than doubles traded volume (671→1,506) by promoting a
flood of gap-retest entries — but the new B-grade cohort wins at 34.8% (vs
the original 37.9% B-grade) and dilutes the book: B-grade P&L falls
+$80,584 → +$54,983 despite +742 trades. A-tier win rate holds (~34%) but the
extra 93 A-grades add only −$1,154. The tier (the thing that actually trades
live) shrinks 78→63 trades and sheds both win rate (−4.2%W) and P&L
(−$12k/yr) — the FVG retest labels rarely carry S≥4+hammer and the ones that
do are weaker.

## Verdict

**Keep OFF.** FVG_RETEST ON doubles trade count but loses on every live
metric: full-pop −$27k (37.5%→34.7%W), tier −$12k/yr (42.3%→38.1%W, −15
trades). The 2026-07-05 evidence still stands — FVG retests dilute B&R — and
the displacement-anchoring guard (gap must be the one left by the break-leg
move) is not enough to make the zone-retest path add edge. C1's lesson
extends: untested gates/variants in this codebase lose, and the
displacement-anchored detector is no exception. Leave `FVG_RETEST = False` as
the shipped default; revisit only if a future variant gates FVG entries on
*sizing* rather than trade selection, or requires an explicit S-score
threshold the current path lacks.

**Files:** research/c2_off_charts.json, research/c2_on_charts.json,
research/c2_off_run.log, research/c2_on_run.log, analyzer
research/c2_analyze.py + research/c2_analyze.log. Code untouched.
