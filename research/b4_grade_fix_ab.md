# B4 — GRADE_FIX A/B: corrected A+ grading vs current (2026-07-13)

**Flag:** `GRADE_FIX` env var in `signal_runner.py` (default **OFF** — behavior
unchanged until C10). When ON, per B3's diagnosis
(research/aplus-inversion-audit.md):

1. **Drops the free C→B floor on 84%-rule re-entries** (signal_runner.py, both
   the call and put 84% blocks). The floor's comment "strong-PA gate already
   passed" was stale — `RULE84_LESSON=True` bypasses that gate, so plain
   (ungated) reclaim candles were being handed a B for free. With the fix,
   plain reclaims grade C = alert-only; only reclaims that earn B/A+ on their
   own PA (large wick / hammer) still trade.
2. **Blocks the clear-road B→A promotion for 84% re-entries**
   (`_grade_for_levels`). H2: that promotion added zero edge (37.0% vs 36.6%)
   and contradicts the sourced criterion (entry AT an HTF level, not past all
   levels).

Stale comments at the old :643/:824 floors annotated (B3 fix #4).

**Run:** `backtest_12mo.py 365`, Polygon cache, Python 3.13, 250 sessions,
28 symbols, $1k flat risk. Baseline and variant both completed with full trade
populations (no rate-limit zeros): baseline 9,423 signals / 671 traded;
GRADE_FIX 9,423 signals / 625 traded.

## Headline

| Metric | Baseline (flag OFF) | GRADE_FIX ON | Δ |
|---|---|---|---|
| Traded (A+/A/B) | 671 tr, 37.5%W, +$78,190 | 625 tr, 37.3%W, +$75,819 | −46 tr, −$2,371 |
| **S≥4+[hammer] tier** | **78 tr, 42.3%W, +$21,000/yr ($1,750/mo)** | **78 tr, 42.3%W, +$21,000/yr ($1,750/mo)** | **identical** |
| A-tier (A+ + A) | 58 tr, 32.8%W, −$2,393 | 41 tr, 34.1%W, +$1,000 | inversion GONE |

Tier is bit-for-bit identical — B3 §5 predicted this: 84% signals carry no S
score, so the S≥4+[hammer] tier was never contaminated. The fix is entirely
about grade-label integrity (prerequisite for any grade-based sizing like
GRADE_SIZE_PCT).

## Grade distribution + P&L by grade

| Grade | Baseline n | Base W/L | Base Win% | Base P&L | GRADE_FIX n | Fix W/L | Fix Win% | Fix P&L |
|---|---|---|---|---|---|---|---|---|
| A+ | 11 | 3/8 | 27.3% | −$2,000 | 11 | 3/8 | 27.3% | −$2,000 |
| A | 47 | 16/31 | 34.0% | −$393 | 30 | 11/19 | 36.7% | **+$3,000** |
| B | 613 | 232/380 | 37.9% | +$80,584 | 584 | 219/364 | 37.6% | +$74,819 |
| C (alert-only) | 195 | 55/140 | 28.2% | (−$32,045 if traded) | 226 | 69/157 | 30.5% | (−$25,193 if traded) |

A-tier is no longer a money-loser and no longer inverts vs B on P&L
(A +$3,000 at n=30 vs B's +$74,819 across 584 — win rates now ordered
sanely enough that the grade label stops being anti-signal). A+ (n=11,
break-and-retest full-stack only) is untouched by the fix and stays
unproven-negative at tiny n — that's B3's H3, still underpowered.

## The 84% re-entry subgroup (the laundered trades)

| Grade | Baseline | GRADE_FIX |
|---|---|---|
| A | 18 traded, 27.8%W, −$4,393 | 1 traded, 0%W, −$1,000 |
| B | 33 traded, 45.5%W, +$7,095 | 4 traded, 50.0%W, +$1,330 |
| C (benched) | 25 alerts, 28.0%W | 56 alerts, 37.5%W (+$807 if traded) |
| Traded total | 51 tr, 39.2%W, +$2,702 | 5 tr, 40.0%W, +$330 |

(Baseline here differs from B3's 22 tr / −$8,395 because config moved since
that report's run — A2 symbol drops, 10:30 cutoff, QQQ S-input. Same
mechanism, same shape: 84%-A 27.8%W and negative, 84%-B healthy.)

## Verdict

- **Fix does what B3 prescribed:** the grade-laundering path (ungated reclaim
  → free B → clear-road A) is closed. A-tier inversion disappears
  (−$4,393 of 84%-A losses removed; A-tier flips −$393 → +$3,000).
- **Tier impact: zero.** S≥4+[hammer] stays 78 tr / 42.3%W / $21k-yr in both runs.
- **Full-pop cost: −$2,371/yr,** because dropping the C→B floor also benches
  the floored-B 84% group, which was net-profitable (45.5%W, +$7,095). The
  laundering floor was minting both the toxic A group AND a decent B group;
  removing it takes both.
- **For C10:** if grade-based sizing is ever wanted, GRADE_FIX (or stronger)
  is a prerequisite — baseline labels would oversize a 27.8%-win group. If
  only P&L matters and sizing stays flat, a narrower variant worth testing is
  "block B→A promotion only, keep the B floor": it would keep the +$7,095
  B-group trading while still killing the A-label laundering. That overlaps
  C9's strict-spec 84% (A+ entry + same-thesis), which should share this flag.

**Files:** research/b4_baseline_report.md / b4_baseline_charts.json,
research/b4_gradefix_report.md / b4_gradefix_charts.json, analyzer
research/b4_analyze.py. Code: signal_runner.py (GRADE_FIX flag block +
two 84% floors + `_grade_for_levels`). Default behavior unchanged.
