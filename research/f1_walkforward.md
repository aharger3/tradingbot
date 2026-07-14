# F1 — Walk-forward validation of tier v2 + C10 flag choices (2026-07-13)

**Model:** Fable · **Script:** `research/f1_walkforward.py` (analysis only, no signal-path
or config edits, no commits) · **Data:** frozen `research/c1_off_charts.json`
(2025-07-14..2026-07-10, 222 sessions, 671 traded) — no new fetches, zero rate-limit exposure.
RoR add-on reuses `research/d3_risk_of_ruin.py` model (seed 84).

## Verdict (one line)

**Tier v2's rules survive walk-forward (every C10 flag choice holds or is correctly
not-shipped; C6 whitelist and C7 weekday confirmed overfit) — but the 50.6%W is
in-sample: the honest OOS win-rate estimate is ~43–46% (pooled walk-forward 43.0%W,
Wilson95 [35.7%, 50.7%]; pure-forward quarter 45.5%W), which is BELOW the 55% RoR
threshold, and flat-$1k funded-phase ruin at that level is 14–21%, not <5%.
Config stands; real money does not clear F3 on backtest evidence alone — F2 live
shadow is now the deciding gate.**

## 0. Data constraint — what a "walk-forward" can honestly mean here

The task spec asks rolling train-12mo / test-3mo. That needs ≥24mo of intraday data;
the repo has exactly ONE 12mo window (yfinance/Polygon intraday history limit).
**A true rolling walk-forward is impossible on this data — this report does not fake one.**
What was done instead:

1. **Leave-one-quarter-out (LOQO) walk-forward of the C10 selection process** — the
   full 3,072-config tier sweep re-run on 3 quarters (~9.7mo train), winner selected by
   C10's stated criterion (WR≥50%, min trades scaled from ≥20/yr, max $/yr), evaluated
   on the held-out quarter. 4 folds. Only fold 4 (train Q1–Q3 → test Q4) is a pure
   forward fold; folds 1–3 train partly on future data (stated, unavoidable at n=1 year).
2. **Fixed-v2 stability**: per-quarter / per-month / half-split tables.
3. **Per-flag sign-stability**: v2 vs v2-with-each-lever-flipped, per quarter.
4. **C6 / C7 dedicated overfit tests** (cross-half symbol selection; weekday replication).

Sanity checks passed: v2 on full sample reproduces C10 exactly (156 tr, 50.6%W, $81,000);
v2 tier on the RULE84_STRICT arm (`c9_strict_charts.json`) is bit-identical (84% re-entries
carry no S-score → tier no-op), so tier analysis on the baseline json is valid for the
final strict-ON config.

## 1. Walk-forward table (LOQO, 3,072-config sweep re-selected per fold)

| Fold | Test window | Train-selected config | Train | Test (OOS) | v2 fixed on same test |
|---|---|---|---|---|---|
| 1 | Q1 2025-07-14..10-15 (56d) | S≥4 max2 +skipchase +skipnews +nodisp+1 | 161 tr 50.3%W $82k | **34 tr 44.1%W $11k** | 28 tr 42.9%W $8k (v2 train rank #3) |
| 2 | Q2 2025-10-16..2026-01-09 (56d) | S≥3 max2 +cut10:30 +skipnews +reqqqqA | 88 tr 53.4%W $53k | **45 tr 44.4%W $15k** | 52 tr 51.9%W $29k (rank #6) |
| 3 | Q3 2026-01-12..04-16 (56d) | S≥3 max2 +skipchase +skipnews +wl12 | 105 tr 50.5%W $54k | **25 tr 44.0%W $8k** | 32 tr 62.5%W $28k (unranked — train WR 47.6%) |
| 4 (pure fwd) | Q4 2026-04-20..07-10 (54d) | S≥4 max3 +skipchase +skipnews +nodisp+1 | 156 tr 51.3%W $84k | **61 tr 41.0%W $14k** | 44 tr 45.5%W $16k (rank #14) |

**Pooled held-out:**

| estimate | n | win% | Wilson95 | P&L pace |
|---|---|---|---|---|
| Selected-per-fold (honest anti-selection-bias OOS) | 165 | **43.0%** | **[35.7%, 50.7%]** | $48k/yr |
| v2 fixed (pooled test = full sample → quasi-OOS only) | 156 | 50.6% | [42.9%, 58.4%] | $81k/yr |

Read: **every fold's train winner gave back 6–10pp of win rate out of sample**
(50–53%W train → 41–44%W test), and the selected config was different every fold
(nodisp+1 twice, reqqqqA once, wl12 once, max3 once) — the top of the sweep is
regime-fit. v2 itself was never the train #1 (ranks #3/#6/–/#14), which is consistent
with C10 having picked it for robustness rather than peak $; its per-quarter test
numbers (42.9/51.9/62.5/45.5%W, all profitable) are the best behavior in the table,
but its pooled number is tautologically in-sample. **The defensible forward
expectation for v2 is ~43–46%W, not 50.6%.**

## 2. Fixed tier-v2 stability (vs v1)

| Window | v2 | v1 |
|---|---|---|
| Q1 | 28 tr 42.9%W $8k | 21 tr 28.6%W −$3k |
| Q2 | 52 tr 51.9%W $29k | 21 tr 47.6%W $9k |
| Q3 | 32 tr 62.5%W $28k | 14 tr 42.9%W $4k |
| Q4 | 44 tr 45.5%W $16k | 22 tr 50.0%W $11k |
| H1 / H2 | 48.8% $37k / 52.6% $44k | 37.5% $5k / 47.4% $16k |

- v2 beats v1 on P&L in **4/4 quarters** and is profitable in **4/4 quarters**
  and **12/13 months** (only 2025-09 negative: 8 tr 12.5%W −$5k — that month is the
  realistic worst case: a 12.5%W month inside an overall-healthy year).
- Monthly WR ranges 12.5%–83.3% — at ~12 tr/mo, single-month readings are noise;
  judge v2 on ≥quarter windows (42.9%–62.5%).

## 3. Per-flag walk-forward verdicts (v2 vs lever-flipped, Δ$ per quarter)

| C10 choice | Q1 | Q2 | Q3 | Q4 | Qtrs won | Full Δ$ | ΔW% | **Verdict** |
|---|---|---|---|---|---|---|---|---|
| Hammer req DROPPED (v1 had it) | +5k | +20k | +25k | +5k | 4/4 | +$55k | +2.4 | **VALIDATED** — strongest lever, wins every quarter |
| stop_after_win OFF | +1k | +7k | +6k | +4k | 4/4 | +$18k | +1.4 | **VALIDATED** — consistent, + unsourced in rulebooks (B2) |
| skip-[chase] ON | −15k | +14k | +6k | +7k | 3/4 | +$11.5k | +6.3 | **HOLDS (weak)** — big WR gain, but Q1 chase trades won; expect variance |
| skip-news ON | +6k | −1k | +2k | +1k | 3/4 | +$8k | +4.8 | **HOLDS (weak)** — small $, decent WR, rulebook-adjacent |
| Cutoff reverted → 11:00 | +1k | +4k | +2k | 0 | 3/4, 0 neg | +$7k | +0.3 | **HOLDS (weak)** — never hurts in any quarter |
| S≥4 (vs S≥5) | +3k | +11k | +19k | +9k | 4/4 | +$42k | +4.6 | **VALIDATED** |
| S≥4 (vs S≥3) | −7k | −9k | 0 | +3k | 1/4 | −$13k | +3.3 | **HOLDS as WR-frame choice** — S≥3 makes more $ at lower WR; S≥4 is the 50%-goal pick, costs ~$13k/yr |
| max 2/day (vs 1) | +1k | +15k | +10k | +1k | 4/4 | +$27k | +1.5 | **VALIDATED** |
| max 2/day (vs 3) | +2k | +3k | 0 | +3k | 3/4 | +$8k | +3.0 | **VALIDATED** |
| require-[qqqA] NOT shipped | −1k | +10k | +4k | +9k | 3/4 | +$22k | −2.4 | **CORRECT** — qqqA variant +2.4pp WR but −$22k/yr; also fold-2's selected reqqqqA config degraded 53.4→44.4%W OOS |
| nodisp+1 NOT shipped | −3k | −11k | +2k | 0 | 1/4 | −$12k | +1.4 | **CORRECT (judgment call)** — nodisp+1 makes +$12k in-sample but WF folds 1 & 4 selected nodisp+1 configs and they degraded worst (44.1%/41.0%W OOS). Unstable; leave off |

### C6 12-symbol whitelist — OVERFIT CONFIRMED, do not ship
- Fixed WL12 loses to all-24 in **all 4 quarters** (full: −$36k/yr) and in both halves
  (H1 $27k vs $37k; H2 $18k vs $44k).
- Honest cross-half selection (whitelist = net-positive tier symbols in train half,
  tested on the other half): **H1→H2: 45.1%W $18k vs v2 52.6%W $44k; H2→H1: 45.2%W
  $22k vs 48.8%W $37k** — symbol selection underperforms in BOTH directions, and the
  two half-selected lists share only ~half their names with WL12 and each other.
  Symbol P&L rankings do not persist. C6 stays dead.

### C7 weekday effects — NOISE CONFIRMED, no gate
- Thursday: H1 **88%W $26k** → H2 **43%W $4k** (full inversion).
- Monday: H1 33%W $0 → H2 72%W $21k (opposite inversion).
- Friday is the only sign-stable weekday (35%→25%W, −$3k H2) but n=12–23/half —
  not gate-worthy. C10's "watch only" stands; F1 recommends shipping **no** weekday rule.

### RULE84_STRICT default ON — UNVALIDATABLE at n=4 (stated explicitly)
The strict arm produced 4 re-entries in 12mo: 2026-02-11 UBER put +$1,571,
2026-02-11 TSM call +$1,663, 2026-03-25 AMD call +$1,927, 2026-07-08 NVDA call −$1,000.
3W/1L, Wilson95 **[30%, 95%]** — no walk-forward can validate a 4-trade/yr rule; all 4
are in H2 so there is no split to test. Two mitigating facts: (a) tier no-op (no S-score
→ never enters v2), so it cannot contaminate the tier OOS estimate; (b) exposure is
bounded (~4 tr/yr, ~$4k swing either way). **Keep ON as a rulebook-faithful, bounded
bet — but C9's edge claim remains a hypothesis, and F2/F3 must not count its P&L
as expected.**

## 4. OOS win-rate estimate vs the 55% RoR threshold (the F3 number)

| estimate | win% | Wilson95 | vs 55% |
|---|---|---|---|
| Walk-forward selected-config pooled (harshest honest) | 43.0% | [35.7%, 50.7%] | **entire CI below 55%** |
| v2 pure-forward fold (Q4, only true OOS quarter for a near-v2 rule) | 45.5% (44 tr) | [31.7%, 60.0%] | 55% inside CI but point est. −9.5pp |
| v2 in-sample (upper bound, selection-biased) | 50.6% | [42.9%, 58.4%] | 55% inside CI |

**Best forward estimate: ~43–46%W.** The 43.0% pooled number measures the mechanical
"pick the sweep #1" process (harsher than C10's robustness-filtered pick); v2's own
quarterly worst/median (42.9%/48.6%) brackets the same range. 50.6% should be treated
as the optimistic bound, 55% as **not supported by any estimate**.

**Risk-of-ruin at these levels** (D3 model reused verbatim, flat $1k, seed 84):

| win rate | eval blow | funded-phase ruin | vs F3 <5% gate |
|---|---|---|---|
| 43.0% (pooled OOS) | 33.0% | **20.7%** | FAIL |
| 45.5% (pure-forward) | 22.5% | **14.0%** | FAIL |
| 50.6% (in-sample) | 9.6% | 6.6% | fail (near) |
| 55.0% (threshold) | 3.7% | 2.1% | pass |

Even so, the economics stay positive at OOS estimates: at 45%W × 156 tr × $1k (2R),
expectancy ≈ $350/tr ≈ **$55k/yr**; the pooled-OOS pace was $48k/yr. v2 is very likely
a profitable config — it is the **prop-account trailing-drawdown survival** that fails
at 43–46%W, not the edge itself.

## 5. What this means for F2 / F3

1. **Config: no changes.** Every shipped C10 choice survived its overfit check;
   everything that failed (C6, C7, nodisp+1, reqqqqA) was already correctly not shipped.
2. **F3 cannot pass on backtest evidence.** The <5% ruin gate needs ≥~55%W and no
   in-sample or OOS estimate supports it. **F2's 2-week live shadow (plus the A6 paper
   log) is now the deciding evidence** — target per C10: ~0.7 tr/day at ~50%W; below
   40%W over ≥40 trades = red flag.
3. **D2 S-scaled sizing stays OFF** (D3 condition "flip ON if F1 shows ≥55% OOS" is
   NOT met — F1 shows the opposite direction).
4. If live shadow lands at 43–46%W: the edge is real but the $150k/$7.5k-trailing
   account is the wrong vehicle at $1k risk — options then are smaller risk unit
   (~$600–700 puts funded ruin back near the 50.6% line), a bigger-drawdown account,
   or accepting ~15–20% ruin odds explicitly. F3's checklist should price these.

## 6. What could NOT be validated (honest list)

- **True rolling 12mo-train/3mo-test:** impossible — only one 12mo window exists.
  Folds 1–3 use future data in train; only fold 4 is purely forward-in-time.
- **RULE84_STRICT edge:** n=4/yr, all H2 — unvalidatable at this n by any split.
- **The dropped-4 symbols (SMCI/SPY/MSTR/RIVN):** absent from the frozen json
  (A2 dropped them upstream) — the 24-symbol universe itself is untestable here.
- **Regime coverage:** one year, one broadly-similar market regime; Polygon-cache
  determinism means cross-json agreement is not independent evidence (C10 caveat 2 stands).
- **Live frictions:** slippage/spread/premium capture — F2's job (per D1 routing).
