# C1 — BNR_DISPLACEMENT_GATE A/B: gate ON vs OFF (2026-07-13)

**Flag:** `BNR_DISPLACEMENT_GATE` module global in `signal_runner.py:132`
(default **OFF**). `True` = B&R break-legs without displacement cap at C
(alert-only); only displaced breaks keep A/B grading. No env var exists —
flag is a hardcoded constant, flipped at runtime for the ON run via the same
module-global mutation the `--dry-run` harness uses (`signal_runner.py:964`).
**No signal-logic edits.** `signal_runner.py` / `omen_bot.py` untouched;
config defaults unchanged (OFF is the shipped default).

**Mechanism check (flag actually took effect):** OFF 9,423 sig / 866 charted;
ON 9,425 sig / 873 charted. Grade distribution shifts (A 47→32, B 613→634,
C 195→196) confirm the nodisp-cap path fired in the ON run.

**Run:** `backtest_12mo.py 365`, Polygon 1m cache, Python 3.13, 250 sessions,
28 symbols, $1k flat risk. Both runs full trade populations (no rate-limit
zeros). Analyzer: `research/c1_analyze.py` (reuses `b4_analyze.py` gstats +
tier_sim). Raw logs `c1_off_run.log` / `c1_on_run.log`.

## Headline

| Metric | OFF (baseline) | ON | Δ |
|---|---|---|---|
| Traded (A+/A/B) | 671 tr, 37.5%W, +$78,190 | 677 tr, 37.3%W, +$75,190 | +6 tr, −$3,000 |
| **S≥4+[hammer] tier** | **78 tr, 42.3%W, +$21,000/yr ($1,750/mo)** | **83 tr, 39.8%W, +$16,000/yr ($1,333/mo)** | +5 tr, −2.5%W, −$5,000/yr |

## Grade distribution + P&L by grade

| Grade | OFF n | OFF W/L | OFF Win% | OFF P&L | ON n | ON W/L | ON Win% | ON P&L |
|---|---|---|---|---|---|---|---|---|
| A+ | 11 | 3/8 | 27.3% | −$2,000 | 11 | 3/8 | 27.3% | −$2,000 |
| A | 47 | 16/31 | 34.0% | −$393 | 32 | 10/22 | 31.2% | −$3,393 |
| B | 613 | 232/380 | 37.9% | +$80,584 | 634 | 239/394 | 37.8% | +$80,584 |
| C (alert-only) | 195 | 55/140 | 28.2% | (−$32,045 if traded) | 196 | 56/140 | 28.6% | (−$30,045 if traded) |

Gate demotes 15 nodisp A→C and 21 displaced signals land at B (net +6 traded,
+1 C alert). B-grade P&L is bit-identical (+$80,584) — the displaced B&R set
that still trades is unchanged; only the non-displaced tail gets benched into
C alerts. The 15 demoted A signals were a net −$3,000 drag at A (A-tier flips
−$393 → −$3,393), partially offset by +$2,000 of would-be C losses avoided.

## Verdict

**Keep OFF.** Gate ON costs −$3,000/yr full-pop AND −$5,000/yr at the live
S≥4+[hammer] tier (win rate 42.3%→39.8% despite +5 trades). Capping
non-displaced B&R at C removes a few toxic A-grade labels but does not add
edge — the displaced-vs-nodisp split is not predictive enough to gate on, and
the tier (the only thing that actually trades live) gets worse. B4's lesson
holds: untested gates in this codebase lose. Leave `BNR_DISPLACEMENT_GATE =
False` as the shipped default; revisit only if a future variant gates
displacement on entry *sizing* rather than trade selection.

**Files:** research/c1_off_charts.json, research/c1_on_charts.json,
research/c1_off_report.md, research/c1_on_report.md, analyzer
research/c1_analyze.py, logs c1_{off,on}_run.log. Code untouched.
