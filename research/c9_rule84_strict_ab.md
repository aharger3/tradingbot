# C9 — 84% rule strict-spec A/B (2026-07-13)

**Question (task C9):** is there a STRICT version of the 84% rule worth keeping,
vs the current de-martingaled detector, vs killing it entirely?

**Flags** (`signal_runner.py`, both env-overridable, **default OFF**, shipped
defaults + config.yaml untouched):

- `RULE84_STRICT` — rulebook spec *"you need an A+ entry"*
  (bonus_How_To_Read_Trend_Structure 543s) + same thesis / same level / same
  direction. Same-thesis (BNR-only), same-level (reclaim of the original entry
  price) and same-direction are **already** enforced by the current arming
  (`RULE84_ARM_BNR_ONLY` + the entry_price/entry_direction gate in the 84%
  blocks). STRICT adds the one missing requirement: **arm only when the ORIGINAL
  stopped-out entry graded A+ or A.** The current version arms off *any* counted
  B&R stop-out regardless of grade.
- `RULE84_OFF` — disable the detector entirely (never arm) = the "84% off" arm.

Gate lives at the single arm chokepoint `backtest_week._arm_84` (both the
binary-2R and ladder stop-out paths now route through it; previously the
binary path duplicated the arm logic inline — refactored to share, behavior-
neutral with flags off: baseline re-ran to an identical 671/51).

**Run:** `backtest_12mo.py 365`, Polygon cache, Python 3.13, 250 sessions,
28 symbols, $1k flat risk, 9,423 signals/run. All three arms completed with
full populations (no rate-limit zeros). Real backtest matched the frozen-json
cross-check (`research/c9_rule84_strict.py` on c1_off_charts.json) to the dollar.

## A/B table — full-pop + tier

| Arm | Full-pop tr | Win% | Full-pop P&L | Δ vs OFF | 84% re-entries | re84 Win% | re84 P&L | Tier tr | Tier Win% | Tier P&L |
|---|---|---|---|---|---|---|---|---|---|---|
| **current de-martingaled** (flags OFF) | 671 | 37.4% | +$78,190 | +$2,702 | 51 | 39.2% | +$2,702 | 78 | 42.3% | $21,000 |
| **strict-spec** (`RULE84_STRICT`) | 624 | 37.5% | **+$79,651** | **+$4,162** | 4 | 75.0% | **+$4,162** | 78 | 42.3% | $21,000 |
| **detector OFF** (`RULE84_OFF`) | 620 | 37.3% | +$75,489 | — | 0 | — | $0 | 78 | 42.3% | $21,000 |

**Tier is bit-for-bit identical across all three arms** — 84% re-entries carry
no S-score, so they never enter the S≥4+[hammer] tier (B3 §5, B4 "tier
identical"). Every 84% question is a **full-pop-only** question; the live tier
strategy is untouched whichever arm is chosen.

## The origin-grade split (why strict wins)

Of the 51 re-entries the current version fires, only **4 originate from an A+/A
B&R entry**; the other **47 originate from a B-graded entry**:

| Origin grade of the stopped-out B&R | re-entries | Win% | P&L |
|---|---|---|---|
| A+ / A (strict keeps these) | 4 | 75.0% | **+$4,162** |
| B (strict drops these) | 47 | 36.2% | **−$1,461** |
| **All (current)** | 51 | 39.2% | +$2,702 |

The rulebook's *"you need an A+ entry"* is directionally **confirmed**: the
A+/A-origin re-entries are the profitable ones; the B-origin re-entries the
current version also takes are net-negative and drag the detector from +$4,162
down to +$2,702. Strict strictly dominates current on both P&L (+$4,162 vs
+$2,702) and win rate (75% vs 39%), and dominates OFF outright.

## Verdict — ADOPT STRICT (do not kill)

- **Not flat, and not a killer.** Strict is the best of the three arms:
  +$4,162/yr over OFF vs current's +$2,702, by removing the 47 net-negative
  B-origin re-entries (also the grade-laundering fuel B3 flagged). "Kill the
  detector" (OFF) is the *worst* arm — it leaves +$4,162 on the table.
- **Recommendation for C10:** flip `RULE84_STRICT` ON (replaces the current
  de-martingaled arming). `RULE84_OFF` stays the kill switch; both default OFF
  so shipped behavior is unchanged until C10.
- **Caveats, load-bearing:**
  1. **n = 4 re-entries/yr.** The 75%W edge is 3 wins / 1 loss — statistically
     meaningless; the +$4,162 is not a robust number. F1 walk-forward must
     validate before this is trusted.
  2. **Tier no-op.** Whatever C10 picks, the live S≥4+[hammer] tier is
     unaffected. This is a full-pop refinement only — it matters if/when the
     full B&R population is traded, not for the current tier config.
  3. Strict is rulebook-faithful and *removes* risk (fewer, higher-quality
     re-entries) rather than adding it, so adopting it is low-downside even at
     n=4 — worst case it reverts to a 4-trade near-no-op.

**Bottom line:** keep the detector, adopt the strict spec. It is the correct
reading of the rulebook and the best-measured arm, but it is a small, unproven,
full-pop-only refinement — treat +$4,162 as a hypothesis for F1, not a banked win.

**Files:** `research/c9_baseline_report.md`/`_charts.json`,
`research/c9_strict_report.md`/`_charts.json`, `research/c9_off_report.md`/`_charts.json`,
analyzers `research/c9_analyze.py` (real runs) + `research/c9_rule84_strict.py`
(frozen-json cross-check). Code: `signal_runner.py` (RULE84_STRICT/RULE84_OFF
globals) + `backtest_week.py` (`_arm_84` gate + inline-path refactor). Defaults
unchanged.
