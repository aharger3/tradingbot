# C10 — Synthesis of C1–C9 + tier-definition grid sweep (2026-07-13)

**Goal frame:** 1–2 trades/day, 50%+ win rate, six-figure year.
**Data:** frozen 12mo baseline `research/c1_off_charts.json` (24 symbols, 11:00 cutoff,
news days in, 671 traded / 866 signals, 222 sessions, $1k flat risk). Sweep:
`research/c10_tier_sweep.py` (3,072 configs). Robustness: `research/c10_robustness.py`.
Interaction run: `research/c10_strict_gradefix_charts.json` (+ report).

---

## 1. Flag verdicts (C1–C9 + B4 rollup)

| Flag / lever | Verdict | Why |
|---|---|---|
| `RULE84_STRICT` (C9) | **ON — default flipped** | Best arm ($79,651 > $78,190 > OFF $75,489); rulebook-faithful; A-tier heals (58tr 32.8%W −$2,393 → 44tr 38.6%W +$6,162). n=4/yr — F1 validates. |
| `GRADE_FIX` (B4) | **OFF** | Conflicts with STRICT: combo run benches all 4 strict re-entries (grades C) and lands exactly on the OFF arm's $75,489. STRICT already removes the 47 laundered B-origin re-entries — the fix's target is gone. |
| `BNR_DISPLACEMENT_GATE` (C1) | OFF | −$3k full-pop, −$5k tier. |
| `FVG_RETEST` (C2) | OFF | −$27k full-pop, −$12k tier. |
| `HTF_BIAS_GATE` (C5) | OFF | −$46k full-pop, −$10k tier; counter-trend retest IS the edge. |
| skip-[chase] (C3) | **ON — in tier v2** | Only both-axes winner; [chase] = 28.2%W −$11.5k full-pop. |
| C6 symbol whitelist | NOT shipped | Overfit (selected in-sample, 8/12 symbols n<5). F1 walk-forward material. |
| C7 weekday gate | NOT shipped | Thu/Tue spread real but n=12–22/weekday; watch only. |
| C8 loss-halt change | None | Rule already wired live; redundant at tier, harmful full-pop. |
| C4 puts gate | Status quo | Puts currently the stronger side. |
| `stop_after_win` (B2/C8) | **OFF — default flipped** | UNSOURCED in all 5 rulebooks (36 groups); sweep: costs v2 tier $18k/yr. |
| Entry cutoff 10:30 (A2) | **Reverted → 11:00** | Full-pop lever; costs v2 tier $7k/yr (A4 saw same direction on v1 tier). Rulebook window is 9:30–11. |
| Skip-news (A2) | Stays ON | Tier-neutral at v1 but +4.7pp W at v2 tier; also rulebook-adjacent. |
| Symbols 24 | Keep | Dropped-4 revert untestable in current data (absent from json); A4's +$4k tier was n=11 on old snapshot. F1 can revisit. |

S-formula: **unchanged.** qqqA+1 already encodes QQQ alignment; `nodisp+1` and require-[qqqA]
variants are marginal/threshold effects — logged as F1 options, not shipped.

## 2. Tier definition v2 (THE deliverable)

**v1 (old):** S≥4 + [hammer], max 2/day, stop-when-green → 78 tr/yr (0.35/day), 42.3%W, $21k/yr.

**v2 (new):** **S≥4, skip [chase] cards, max 2/day. No hammer requirement, no stop-after-win.
News days off (SKIP_NEWS), entries 9:30–11:00.**

| | tr/yr | tr/day | win% | $/yr @$1k | maxDD | neg months | top3-sym conc. |
|---|---|---|---|---|---|---|---|
| v1 baseline | 78 | 0.35 | 42.3% | $21k | −$10k | 4/13 | 76% |
| **v2** | **156** | **0.70** | **50.6%** | **$81k** | **−$6k** | **1/13** | **36%** |
| v2 halves (H1/H2) | 80/76 | — | 48.8/52.6% | $37k/$44k | — | — | — |
| v2 puts / calls | 68/88 | — | 57.4/45.5% | $49k/$32k | — | — | — |

**Why hammer died:** the requirement was the binding constraint (296 S≥4 trades → 78).
Inside the v2 population hammer entries win 52.9% vs 49.5% non-hammer — mildly better,
but requiring it threw away 105 trades worth $51k/yr at ~50%W. Hammer stays a soft
S-point candidate for D2 sizing, not a gate.

**Why stop-green died:** unsourced (B2) + costs $18k/yr at v2 (156→132 tr, 50.6→49.2%W).
It was capping exactly the days that pay.

## 3. Goal math (honest)

$/trade at $1k risk, 2R: `$3k×W − $1k` → 50%W = $500/tr.
- **50%+ AND 1–2/day simultaneously: NOT in this population.** Best ≥1/day config = 47.2%W
  ($105k in-sample, S≥3 max3 — deeper in-sample selection, not shipped).
- v2 at 0.70/day + 50.6%W = $81k in-sample. Six figures closes via D-phase sizing
  (D2 S-scaled sizing, D3 risk-of-ruin at $1.5k) — 156 tr × $500 × 1.28 avg size ≈ $100k —
  NOT via more win-rate levers. C-phase is done; the marginal lever is sized risk.

## 4. Caveats (load-bearing)

1. **In-sample selection over 3,072 configs.** Every lever is independently motivated
   (skip-chase = C3, no-stop-green = B2 unsourced, skip-news = A2 live, hammer-drop =
   measured non-predictive inside v2), and half-split/concentration/drawdown all improve
   vs v1 — but $81k is an upper bound, not forward expectation. **F1 walk-forward is the
   gate before real money; paper week (A6) now validates v2 live.**
2. Cross-json "stability" (identical on 5 charts files) = Polygon-cache determinism,
   not independent evidence.
3. RULE84_STRICT edge = 3W/1L. Hypothesis, not banked.
4. Paper-week expectation: **~0.7 tr/day, ~50%W target, ~$6.7k/mo pace at $1k risk.**
   Even at 45%W the config clears $53k/yr pace. Below 40%W over ≥40 trades = red flag,
   revisit at F2.

## 5. What changed in code (all default flips, env-revertable, uncommitted)

- `signal_runner.py`: `RULE84_STRICT` default 0→1 (C9 verdict; comment documents combo-run conflict).
- `live_scanner.py`: `STOP_AFTER_WIN` default 1→0; `ENTRY_CUTOFF` default 10:30→11:00.
- `config.yaml`: `entry_cutoff: "11:00"`, `stop_after_win: false` (+ comments).
- `daily_review.py`: `_tier_compliance` → v2 rules (S≥4, no [chase], max 2; hammer +
  stop-green checks removed).
- No other signal-logic changes. C1/C2/C5/B4 flags remain OFF as shipped.
