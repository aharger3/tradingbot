# FABLE session 2026-07-11/12 — structural levers (fable-spec-2026-07-12)

Baseline (verified, matches brief): 760 tr, 36.0%W, +$61,489 (win→$2k convention;
raw pnl-field sum $54,057 — 84% wins carry original targets <2R, hence gap).
Tier S≥4+hammer max2/day stop-green: 83 tr, 43.4%W, $25,000/yr.

All comparisons below use the pnl-field convention (apples-to-apples both runs).

## Infra fix (behavior-neutral, verified)
Dedupe key was (setup, dir, round(stop,2)) — under variable stops (F2) the same
trade idea re-fired every bar (760 tr → 1811 phantom). Key is now the broken
LEVEL NAME for B&R, stop price for everything else. Sanity run at
BNR_STOP_MODE="level": byte-identical to baseline (760/36.0/$54,057, same S-dist).

## F2 stop-placement A/B — VERDICT: KEEP stop-at-level
Interaction (as spec warned): wider stops inflate S (+2 structural ≥0.3%) and
un-D-gate signals with risk < max($0.10, 0.15%) → population balloons.

**Variant A (retest-candle low/high):**
- Full-pop 1246 tr, 33.5%W, +$2,430 (baseline 760 / 36.0% / $54,057)
- Tier 153 tr, 31.4%W, −$5,233/yr (baseline 83 / 43.4% / +$25,000)
- S-dist B&R: baseline 651 tr S4+:269 → variant 1114 tr S4+:515 (tier flooded)
- Matched-pairs (same 627 B&R entries in both runs, only stop differs):
  baseline 35.1%W $35,489 vs retest-stop 33.8%W $10,960.
  Flips: 28 losses saved from zone-wiggle, 37 wins LOST because the 2R target
  moved further out with the wider risk. Net −$24.5k on identical entries.
- Mechanism: with target = entry ± 2×risk, widening the stop also moves the
  target. The wiggle it saves (28) costs more wins (37). Source's advice assumes
  ladder/level exits, not 2R-of-risk targets. Re-test stop placement only if F1
  ladder exits ever replace blind-2R.

**Variant B (level ∓ max($0.10, 10% avg 1-min range)):**
- Full-pop 1288 tr, 35.5%W, **+$77,962** (population expansion artifact — see below)
- Tier 166 tr, 34.3%W, +$7,300/yr — collapses vs baseline 43.4%/$25,000
- Matched-pairs (629 shared entries): baseline 35.2%W $36,489 vs buffer 34.0%W
  $14,937. Flips: 31 saved / 38 hurt. Net −$21.6k on identical entries.

**F2 verdict: KEEP stop-at-level.** Both variants lose on identical entries
(the further 2R target costs more wins than zone-wiggle protection saves) and
both flood the S≥4 tier via the structural-stop S component (S4+ population:
269 → 515/559), halving tier win rate. `BNR_STOP_MODE = "level"` restored.

**Observation (NOT acted on — threshold territory):** the ~520 extra full-pop
trades in Variant B (signals whose at-level risk failed the min-risk D-gate but
passed with a wider stop) were net +$40k blind. The min-risk D-gate may be
over-aggressive; parking this — no threshold sweeping per spec.

## F1 liquidity-ladder exits
Entry population held perfectly constant (651 B&R, identical S-dist; 746 vs 760
total = fewer 84% re-entries since scaled trades no longer arm one).

**Variant A (50% at HOD/LOD touch, runner to first key level beyond, stop
unchanged):**
- Full-pop 746 tr, 37.9%W(green), **−$12,077** (baseline +$54,057)
- Tier: same 83 trades, 42.2%W, **$5,928/yr** (baseline $25,000)
- 366/746 scaled. W% up but $ collapses: the "first key level beyond" is
  usually the next PSYCH WHOLE DOLLAR, frequently <1R from entry — wins cap at
  fractions of 1R while losses stay −1R. Literal canonical reading fails.

**Variant B (A + stop→BE after first scale):**
- Full-pop 746 tr, 48.8%W(green), −$2,793. Tier 81 tr, **58.0%W, $5,694/yr**.
- Geometry (366 scaled trades): scale fill at median **0.66R** (p25 0.21),
  runner target median 1.64R, 30% of runner targets <1R from entry.
- BE stop converts losses to small greens → W% soars, expectancy doesn't.

## F3 HOD/LOD break-retest detector — VERDICT: OFF
New level pair from rolling session extremes (established ≥30 min, predating
the 12-bar FSM window, deduped 0.1% vs existing levels).
- Standalone: **19 tr/yr, 33.3%W, −$228.** Population tiny by construction:
  extreme ≥30 min old + retest + confirm before the 11:00 cutoff leaves a
  ~45-min firing window.
- Tier impact: 87 tr 42.5%W $24,000 vs baseline 83/43.4%/$25,000 — slight drag.
- HODLOD_PAIR=False restored. Code stays for re-test if the entry cutoff ever
  moves (a later cutoff is exactly where this setup would live).

## F4 QQQ Rule-4 alignment — ENCODED as S-input (+1)
Proxy: QQQ's first RTH close through its PDH/PMH (up) or PDL/PML (dn), from
Polygon cache; signal aligned when the break in its direction happened before
entry. NOT the refuted OR-break proxy.
- Full-pop split (blind-2R exits, F3 run): **[qqqA] 345 tr 38.6%W +$54,000 vs
  [qqqX] 323 tr 33.0%W −$1,739** — essentially all system profit is in
  QQQ-aligned trades. Direction consistent across every run tonight.
- Tier as HARD GATE: 38 tr 47.4%W $16,000/yr — best W% seen, but halves trades.
- Tier with S+1 for aligned: **90 tr 44.4%W $30,000/yr ($2,500/mo)** — beats
  baseline on both axes. ENCODED (both B&R sides; S max now 10, regexes fixed
  in analyze_aplus/daily_review/compare_runs).
- Live scanner does NOT compute qqq_breaks yet → live cards get no +1 until
  plumbed (follow-up).
- Verification run: full-pop byte-identical to baseline (760/36.0%/$54,057 —
  S is annotation-only), tier exactly as offline sim: **90 tr 44.4%W $30,000/yr**.
  S-dist shifted up as expected (S4+: 269 → 347; S8 tier appears).

## Net session outcome
Take-tier: 83 tr 43.4%W $2,083/mo → **90 tr 44.4%W $2,500/mo** (F4 encode; F2/F1/F3
honestly refuted and reverted). Candidate stack for Austin: qqqA-S+1 + news-skip
+ <10:30 cutoff — each measured positive separately, combined effect unmeasured.

**F1 verdict: KEEP blind 2R.** Both variants lose 75%+ of tier P&L. The 55%W
goal is REACHED by Variant B (58%) but at $474/mo vs $2,083 — win rate was
never the objective, expectancy is. MFE stat ("25% of losses touched +1R")
is real but scale-at-HOD gives back more on winners than it saves on losers:
median HOD is only 0.66R away at entry. LADDER_MODE=None restored. Re-visit
only with a smarter runner (e.g. skip whole-dollar targets closer than 2R —
that's threshold territory, parked).
