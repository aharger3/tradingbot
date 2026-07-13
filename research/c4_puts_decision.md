# C4 — Puts problem A/B/C decision (2026-07-13)

**Verdict: (c) status quo — no puts gate. To be applied at C10 (i.e. nothing changes).**
Config untouched per paper-week freeze; no omen_bot.py / signal_runner.py edits.

Sim: `research/c4_puts_sim.py` on the clean 12mo baseline `research/c1_off_charts.json`
(866 signals / 671 traded / 78 tier; direction + [qqqA]/[qqqX] tags carried per trade).
Tier = S>=4 + [hammer], max 2/day, stop-when-green; arm-filtered puts are refused at the
tier gate so freed slots roll to later signals (same mechanics as c3_tag_split).

## Cross-check: is the −$21k/24mo bleed still present?

**No.** The −$21k/24mo figure (unified_backtest_synthesis.md, 07-12: "Puts structurally
−$21k/24mo in every regime mode") was driven by year-1 (2024-07→2025-07 bull regime —
vault doc: "24mo flat, year-1 bull regime bled puts"). In the current 12mo window
(2025-07→2026-07) puts are the *stronger* side:

| direction | trades | win% | P&L |
|---|---|---|---|
| calls | 322 | 37.3% | +$34,907 |
| **puts** | **349** | **37.6%** | **+$43,284** |

The bleed is regime-dependent, not structural. Nothing to fix in the current window;
the A2 recommended config's SMA Directional 5% regime filter is the correct hedge for a
future bull-regime flip, not a direction ban.

## The three arms

Full population (traded A+/A/B):

| arm | trades | win% | P&L/yr |
|---|---|---|---|
| (c) status quo | 671 | 37.5% | **+$78,190** |
| (a) puts off entirely | 322 | 37.3% | +$34,907 (−$43k) |
| (b) puts only if [qqqA] | 460 | 38.9% | +$73,907 (−$4.3k) |

Tier (S>=4+[hammer], max 2/day, stop-green):

| arm | tier tr/yr | win% | $/yr | puts in tier |
|---|---|---|---|---|
| (c) status quo | 78 | 42.3% | **+$21,000** | 34 tr 16W/18L +$14,000 |
| (a) puts off entirely | 45 | 37.8% | +$6,000 | 0 |
| (b) puts only if [qqqA] | 59 | 40.7% | +$13,000 | 15 tr 7W/8L +$6,000 |

Both gates lose on BOTH axes at tier. Puts carry $14k of the tier's $21k. Arm (a) is
catastrophic (−$15k/yr tier, −71%). Arm (b) costs −$8k/yr tier: it drops 19 counter-QQQ
tier puts that were actually 47.4%W +$8,000, and slot-refill doesn't recover them.

## Why puts "lose" — they don't, but the splits are informative

Puts by QQQ alignment (full-pop):

| group | trades | win% | P&L |
|---|---|---|---|
| puts [qqqA] (aligned bearish) | 138 | 42.8% | +$39,000 |
| puts [qqqX] (counter-QQQ) | 166 | 33.9% | +$4,489 |
| puts no-qqq-tag | 45 | 35.6% | −$205 |
| calls [qqqA] (context) | 153 | 39.9% | +$30,000 |
| calls [qqqX] (context) | 117 | 32.5% | −$3,000 |

QQQ alignment is real full-pop signal — but it's **direction-symmetric** (counter-QQQ
calls are worse than counter-QQQ puts). It's already priced into the S-score (qqqA-S+1),
and within the tier the effect vanishes (tier puts [qqqX]: 19 tr, 47.4%W, +$8,000 —
the hammer+S filter already selects the good counter-QQQ puts). A puts-only QQQ gate is
the wrong shape; if anything it would be a both-directions full-pop lever, and C1/C2/C5
all showed such broad gates cut net-positive trades.

Puts by symbol (losers): MARA −$7k (0/7), AAPL −$6k (1W/8L), IREN −$4k, MSFT −$3k,
CRM −$3k, NVDA −$2k. Winners: COIN +$16k, ORCL +$8.2k, TSM +$8k, UBER +$6.6k, INTC +$6.5k,
MU +$6.2k, GOOGL +$6k. Same overfit-prone per-symbol story as C6 (small n) — belongs to
C6's whitelist proposal + F1 walk-forward, not a puts decision. Puts by grade mirrors the
B3 story (A+ puts 1W/6L −$4k = the grade-laundering cohort, fixed by B4's GRADE_FIX),
B puts 38.0%W +$44k healthy.

## Decision

**C4 verdict: (c) status quo, to be applied at C10** — which means no change at all.
- The −$21k/24mo premise is stale: current 12mo baseline shows puts +$43k full-pop,
  +$14k of the $21k tier. Killing or QQQ-gating puts destroys the tier (−71% / −38%).
- No live plumbing needed. (If a future regime flip revives the bleed, A5's
  `compute_qqq_breaks` already provides live QQQ state for an arm-(b) style gate —
  D-phase/F-phase task, and F1's walk-forward should watch per-segment puts P&L as the
  regime canary.)

Puts sample sizes per arm: (c) 349 full-pop / 34 tier · (b) 138 full-pop / 15 tier ·
(a) 0.
