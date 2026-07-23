# Optimization Feasibility — can Omen reach 55%W at 2:1 without overfitting?

**Date:** 2026-07-23 · **Author:** offline reconnaissance run (branch `claude/backtest-offline-opt`)
**Data:** `data_archive/` 1-min bars, fully offline (no network, no `.env`/Polygon key used).
**Scope:** RECON + BASELINE + PLAN. No detector/tier/strategy logic changed. Plumbing only.

## TL;DR

**No — 55%W at 2:1 is not reachable on this evidence without overfitting.** The live "tier
v2" config's headline **50.6%W / $81k** reproduces exactly, but it is an **in-sample** number
from a single favorable year. Running the same config on a genuinely held-out year (2024‑07→
2025‑07, which no prior tuning ever touched) gives **28.1%W and −$10k**. Every config that
reaches ≥55%W in-sample collapses to 17–22%W out-of-sample. The strategy is a real but
**regime-dependent** edge whose win rate swings ~18–23pp year to year; 55% is achievable only
by curve-fitting the good regime. The disciplined path is not more win-rate levers — it is the
already-planned **F2 live shadow** to measure the forward win rate, plus a smaller risk unit
to survive the ~28–46% band.

---

## 1. Reproduced baseline (the real numbers)

Two-layer reproduction, both offline:

**Layer 1 — signal population.** `backtest_12mo.py --archived` replays every archived session
bar-by-bar through the unchanged `SignalRunner` (same detectors, grading, 2R sim, dedupe, 84%
wiring). HTF bias is resampled from the 1‑min bars (existing `hourly_from_1m`), so no yfinance.
Full 2‑year run: **835 traded signals over 361 sessions, 24 symbols.**

**Layer 2 — tier v2 selection** (S≥4, skip `[chase]`, max 2/day, no hammer, no stop-after-win,
skip-news, 9:30–11:00) applied chronologically, reproduced with the exact `c10_tier_sweep`
mechanics.

| Slice | Trades | tr/day | W–L | Win% (of decided) | P&L @ $1k flat |
|---|---|---|---|---|---|
| **Frozen `c1_off_charts.json` (config-comment claim)** | 156 | 0.70 | 79–77 | **50.6%** | **$81,000** |
| **My fresh run, Y2 in-sample (2025‑07→2026‑07, 24 sym)** | 157 | 0.71 | 80–77 | **51.0%** | **$83,000** |
| Full 2yr pooled (both regimes) | 221 | 0.61 | 98–123 | 44.3% | $73,000 |

**Reconciliation of the 50.6% claim:** VERIFIED. Reproducing the tier on the frozen json gives
156 tr / 50.6%W / **$81,000** to the dollar. My independent full-archive rerun lands at 157 tr
/ 51.0% / $83k — the 1-trade/$2k gap is the slightly different window start (frozen json begins
2025‑07‑14 vs my 2025‑07‑11) and `RULE84_STRICT` now defaulting ON (a tier no-op: 84% re-entries
carry no S-score). The claim is real and the offline plumbing is validated end-to-end.

P&L is binary per trade (win +$2,000, loss −$1,000; scratches ≈ 0), so 79W·2000 − 77L·1000 =
$81,000. Break-even at 2:1 is **33.3%W**; the tier clears it comfortably *in this window*.

Per-symbol / per-setup / direction breakdowns are in `research/c6_symbol_attribution.md`,
`research/c4_puts_decision.md`, and the regenerated `backtest_report.md`. Headlines: tier profit
is concentrated (8 of 12 net-positive symbols carry 80%; 10 of 24 are net-negative in tier, only
MU/HOOD with n≥5). Puts and calls are near-symmetric in-sample (puts 54–57%W, calls 45%W in Y2).

## 2. The out-of-sample test the prior F1 report could not run

`research/f1_walkforward.md` states a true train/test split was "impossible — only one 12mo
window exists," because it used the frozen 12mo json. **The archive actually holds a full 2
years for the 10 core symbols** (AAPL, AMD, AMZN, GOOGL, META, MSFT, NVDA, PLTR, QQQ, TSLA);
the 14 experimental symbols start 2025‑07‑11. So year‑1 (2024‑07‑10→2025‑07‑10) is a genuinely
**held-out regime** the entire C-series / C10 / F1 optimization never saw.

Tier v2, unchanged, applied to each year:

| Period | Universe | Trades | Win% | Wilson95 | P&L |
|---|---|---|---|---|---|
| **Y2 in-sample** | 24 sym | 157 | **51.0%** | [43.3, 58.6] | $83,000 |
| Y2 in-sample | core 10 only | 67 | 46.3% | — | $26,000 |
| **Y1 out-of-sample** | core 10 only | 64 | **28.1%** | **[18.6, 40.1]** | **−$10,000** |

- **Same config, same 10 symbols, adjacent year: 46.3%W → 28.1%W.** An ~18pp collapse that is
  NOT a symbol-universe artifact (the core-only Y2 control still sits at 46%). Full-population
  win rate: Y1 **32.2%** (below the 33.3% break-even — the strategy *lost money* in year‑1) vs
  Y2 37.7%.
- Y1 direction split: puts 25.8%W −$7k, calls 30.3%W −$3k — both sides underwater. This
  confirms C4's note that year‑1 was a bull regime that ran over the counter-trend break-&-retest
  population. The edge is **regime-conditional**, not structural.
- Wilson95 on the 28.1% (n=64) is [18.6%, 40.1%] — the entire interval is below break-even's
  comfort zone and nowhere near 55%. This is a real effect, not small-n noise.

This is strictly harsher — and more honest — than F1's quarter-split estimate of ~43–46%W,
because F1 could only resample *within* the favorable year. Across regimes the floor is ~28%.

## 3. Tunable levers and headroom (one-lever flips on the in-sample tier)

All measured on the frozen 12mo json (reproduces C10 exactly). "Δ vs v2" is in-sample.

| Lever | Setting | Trades | tr/day | Win% | P&L | Headroom to 55%? |
|---|---|---|---|---|---|---|
| **S-score cutoff** | S≥4 (v2) | 156 | 0.70 | 50.6% | $81k | baseline |
| | S≥5 | 102 | 0.46 | 46.1% | $39k | ↓ WR and $ |
| | S≥6 | 55 | 0.25 | 50.9% | $29k | +0.3pp, −$52k |
| | S≥3 | 224 | 1.01 | 47.3% | $94k | more $, lower WR |
| **Entry cutoff** | 11:00 (v2) | 156 | 0.70 | 50.6% | $81k | baseline |
| | 10:30 | 145 | 0.65 | 50.3% | $74k | ~0 |
| | 10:00 | 119 | 0.54 | **52.9%** | $70k | +2.3pp — best single lever, still <55% |
| **Max trades/day** | 2 (v2) | 156 | 0.70 | 50.6% | $81k | baseline |
| | 1 | 114 | 0.51 | 49.1% | $54k | ↓ |
| | 3 | 170 | 0.77 | 47.6% | $73k | ↓ |
| **Hammer gate** | off (v2) | 156 | 0.70 | 50.6% | $81k | baseline |
| | on | 58 | 0.26 | 48.3% | $26k | −2.3pp, −$55k (was v1's binding gate) |
| **Stop-after-win** | off (v2) | 156 | 0.70 | 50.6% | $81k | baseline |
| | on | 132 | 0.59 | 49.2% | $63k | ↓ (unsourced; B2) |
| **Skip-[chase]** | on (v2) | 156 | 0.70 | 50.6% | $81k | +6.3pp vs off (already in v2) |
| **News-skip** | on (v2) | 156 | 0.70 | 50.6% | $81k | +4.8pp vs off (already in v2) |
| **Symbol whitelist** | 12 net-pos (C6) | 43 | 0.19 | **60.5%** | $35k | **in-sample only — overfit** |
| **Direction** | puts-only (Y2) | 68 | — | **57.4%** | $49k | **regime-fit — Y1 puts 25.8%W** |

**Reading:** the two levers that "reach 55%" (symbol whitelist 60.5%, puts-only 57.4%) are both
**selection artifacts** — the whitelist is picked from the same run it's tested on with 8/12
symbols at n<5 (`c6`), and puts-only is the favorable-regime side that *bled −$21k in year‑1*
(`c4`). Every *legitimate* single lever tops out at **52.9%** (10:00 cutoff), and buys that
+2.3pp by discarding 37 trades and $11k. There is **no honest single lever with headroom to
55%**, and stacking levers makes OOS worse, not better (§4).

## 4. Overfitting assessment (the load-bearing section)

**"Loop till 55% on a fixed dataset" IS overfitting — and here is the proof on this data.**
Selecting the highest in-sample win-rate config on Y2 and testing on the held-out Y1:

| Selection | In-sample (Y2 core) | Out-of-sample (Y1) |
|---|---|---|
| Best-WR config, n≥30 | 50.0%W / $15k | **22.2%W / −$9k** |
| All 14 configs that hit ≥55%W IS (n≥20) | 55–62%W | **17–22%W** |

The relationship is **inverse**: the configs with the *highest* in-sample win rate (61.9%)
delivered the *lowest* out-of-sample win rate (17–18%). They are memorizing which regime-favored
trades happened to win. This is exactly what F1 found at the quarter level (train winners gave
back 6–10pp OOS and the selected config differed every fold); the cross-year test amplifies it.

**Prior-art corroboration already in the repo:** C6 symbol whitelist (overfit, loses all 4
quarters OOS), C7 weekday gate (full sign-inversion H1→H2), nodisp+1 / require-qqqA (degrade
worst OOS in F1 folds), C1/C2/C5 broad gates (all cut net-positive trades). Every win-rate lever
that was investigated and *not shipped* failed an OOS check. That track record is the strongest
evidence that the remaining "reach 55%" moves are also curve-fits.

### Recommended disciplined search protocol

1. **Fix the split before searching.** Train/select only on Y2 (2025‑07→2026‑07); Y1 core
   (2024‑07→2025‑07) is a locked vault opened once, at the end. Never tune on Y1.
2. **Walk-forward, not single-split.** Use `research/f1_walkforward.py` (LOQO, 3,072-config
   re-selection per fold) as the selection *process* gate — a lever ships only if it wins its
   sign in ≥3/4 quarters AND does not degrade the pure-forward fold (Q4). Cross-year Y1 is the
   final confirmation, not a tuning surface.
3. **Cap the search.** Pre-register ≤~8–12 independently-motivated levers (each with a rulebook
   or mechanism reason), one grid pass, no iterative re-runs against the same test set. The C10
   sweep already burned 3,072 configs on Y2 — treat Y2 as *spent* for win-rate discovery; new
   ideas need Y1 or fresh data as their test set.
4. **Judge on decided-trade CIs, not point estimates.** At ~60–160 tier tr/yr, a 5pp move is
   inside the Wilson band. Require the *lower* CI bound to clear the decision threshold, and
   require ≥40 decided trades per cell (kill n<20 flukes, per C10's own rule).
5. **Real-edge vs curve-fit test:** a lever is real only if (a) it has an ex-ante mechanism,
   (b) its sign holds across both years and ≥3/4 quarters, and (c) its OOS win rate doesn't fall
   more than ~1 CI-width below in-sample. Skip-[chase], S≥4, max-2, hammer-drop pass (a)+(b);
   symbol/weekday/direction fail.
6. **Stop chasing win rate; measure it live.** The binding gate is regime, which no offline
   lever controls. F2's 2-week live shadow + the A6 paper log is the deciding evidence (F1's
   conclusion, reinforced here). Below 40%W over ≥40 live trades = red flag.

## 5. Verdict on 55% at 2:1

**Not reachable without overfitting on current evidence.**

- In-sample best legitimate config ≈ 52.9%W (10:00 cutoff), and that's the *favorable* year.
- Honest forward estimate is ~43–46%W (F1 quarter-split) with a demonstrated cross-year floor
  of **28%** in an unfavorable regime.
- The only configs that print ≥55% are the symbol-whitelist and puts-only selections, both of
  which are proven regime/selection artifacts that collapse to 17–26%W out of sample.
- What *is* true: tier v2 is very likely a **profitable** config across regimes (+$73k over the
  full 2 years at 44.3%W, i.e. ~$36k/yr blended), but "profitable at ~44%W" and "55%W" are
  different claims. At 2:1, 44%W is fine for P&L and **fails** the <5% risk-of-ruin gate on a
  $1k-flat prop account (F1: 14–21% funded-phase ruin at 43–46%W).

**Recommendation (user's call):** do not launch an offline loop toward 55%. Either (a) accept
the ~44%W blended edge and reduce the risk unit (~$600–700) so ruin math survives the OOS band,
or (b) treat F2 live-shadow win rate as the real number and only revisit sizing/whitelist after
≥40 live trades confirm a regime. Any 55% you can produce offline from here is a curve-fit.

---

## Appendix — what plumbing changed (backtest only, no logic touched)

- **`backtest_12mo.py`**: added `archived_days(start, end)` (enumerates dates actually present
  in `data_archive/` instead of anchoring on `date.today()`, which drifts past the cached window
  and forces network) + `--archived/--start/--end` CLI flags. `main()` uses `archived_days()`
  when `--archived` is set; default path unchanged. The engine already read the archive
  cache-first (`polygon_feed.fetch_day`) and resampled HTF bias from 1‑min bars, so no yfinance
  network is hit; `.env`/Polygon key are not required for cached dates.
- No changes to `backtest_week.py`, `signal_runner.py`, `omen_bot.py`, detectors, or tier config.
- Reproduction scripts (analysis only, not committed to logic): `repro_tier.py`,
  `analyze_oos.py`, `overfit_demo.py` in the session scratchpad.
- Fresh 2‑year population snapshot: `research/full_archive_2yr_charts.json` (835 signals).

**Run to reproduce:** `python3 backtest_12mo.py --archived` (fully offline).
