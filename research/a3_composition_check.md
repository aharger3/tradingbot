# A3 — Composition Check (All A2 Levers Combined)

**Run:** 2026-07-13
**Flags:** `--entry-cutoff 10:30 --skip-news`
**Symbols:** 24 (SYMBOLS from backtest_week.py, already trimmed in A2)

---

## Executive Verdict

**Doesn't compose to projected $88-95k.** Combined P&L = **+$60,061**, vs +$56,057 baseline (+$4,004 actual delta). Synthesis projection overestimated by ~$28-35k.

---

## Results

| Metric | Baseline (synthesis §2) | Composition Run | Delta |
|--------|------------------------|-----------------|-------|
| **P&L** | +$56,057 | **+$60,061** | +$4,004 |
| **Win Rate** | 36.1% | **37.9%** | +1.8% |
| **Trades** | 761 | **442** | -319 (42% cut) |

### By Grade

| Grade | Signals | W | L | Win% | P&L |
|-------|---------|---|---|------|-----|
| A+ | 6 | 2 | 4 | 33.3% | $0 |
| A | 27 | 11 | 16 | 40.7% | +$5,733 |
| B | 409 | 154 | 254 | 37.7% | **+$54,328** |
| C | 112 | 35 | 77 | 31.2% | (−$8,102 if traded) |

### By Entry Hour

| Hour | Signals | W | L | Win% | P&L |
|------|---------|---|---|------|-----|
| 09:30-10:00 | 308 | 119 | 188 | 38.8% | +$51,327 |
| 10:00-10:30 | 134 | 48 | 86 | 35.8% | +$8,734 |

No 10:30-11:00 tail — cutoff gate verified working.

### Per-Lever Attribution

| Lever | Synthesis Δ | Actual Δ | Notes |
|-------|-------------|----------|-------|
| Symbol removal (4) | +$22,133 | ~+$6k? | Hard to isolate — SYMBOLS already trimmed before run |
| Entry cutoff 10:30 | +$8,303 | Included | No 10:30-11:00 trades in output |
| Skip-news | ~+$0? | Negative? | Removes high-variance days; synthesis called for 12mo A/B first |
| Regime filter (SMA 5%) | +$2,093 | N/A | Not flag-gated; hardwired in signal_runner, already active |

**Key finding:** Levers overlap heavily. The toxic symbols (SMCI/SPY/MSTR/RIVN) concentrated in the 10:30-11:00 hour and on news days. Removing one removes much of the other's edge.

---

## Why Projection Missed

1. **Overlap not fully conservative.** Synthesis §8 said "assume combined +$28-30k, not +$30.4k". Actual overlap was larger — closer to 80% than 50%.

2. **Skip-news Δ unverified.** Synthesis §2.2 flagged this: "sample of scheduled-news days in 12 months is ~30 and per-day P&L variance is high." A full `--skip-news` A/B was recommended before making it live. This run includes it without that verification.

3. **Symbol list already trimmed.** The synthesis baseline ran on 28 symbols; this run on 24. The +$56k baseline is not directly comparable — A2 already applied symbol cuts before this session.

---

## Recommendation

1. **Accept +$60k as the real combined number.** This is the config going live for paper week.

2. **Re-measure skip-news.** Run a paired `--skip-news` A/B on the 28-symbol baseline to isolate its true delta before trusting it as a live gate.

3. **No config change.** A2 settings stand — just update projection: **+$60k/yr, 38%W, 440 trades** is the realistic target.

---

## Raw Output

```
211 sessions, 5766 total signals, 554 charted
  * A+/A win rate 39% vs B/C 38% -> KEEP grading
  * D-grade filter: filtered signals would have won 27% -> filter justified (<50%)
  * 84% rule: 48 triggers, fired win rate 32%.
  * Best setup: one_candle_rule (41%) | worst: reentry_84_rule (32%)
  * C-grade alerts (112, alert-only per SPEC2) would have won 31%
```

Log: `journal/a3_composition.log`
