# T4 — Index parity (R7)

**R7 (ratified):** *"Should be firing more..."* — indices (QQQ/SPY/IWM) traded 18 of 1,017
pre-T0. Not landed by T0 (deliberately). His index cards: 3 S of 15 — indices genuinely
set up less than stocks, so the target is *more*, not equal.

## Q1 — where is the index signal actually lost?

Re-ran `research/t51_index_funnel.py` (unmodified — it imports the committed engine and
instruments it by wrapping, not rewriting) against the **current, post-T0 ratified engine**
(HEAD at the time of this run) to confirm the pre-T0 diagnosis still holds, rather than
assume it. Window: 2024-08-12..2026-08-11, 500 trading days x 3 index symbols = 1500 cells,
TSLA as the equity control.

| stage | QQQ | SPY | IWM | INDEX_POOL | TSLA (control) |
|---|---|---|---|---|---|
| ran cells | 500 | 500 | 500 | 1500 | 500 |
| days with a level | 500 | 500 | 500 | 1500/1503 | 500 |
| days with a setup | 489 | 474 | 488 | 1451 | 494 |
| days with a signal | 489 | 474 | 488 | 1451 | 494 |
| **days traded (counted)** | **7** | **4** | **6** | **17** | **60** |

(Validation note: the pre-T0 t51 run counted 18 — QQQ 7/SPY 5/IWM 6. Re-run on the ratified
engine counts 17 — QQQ 7/SPY 4/IWM 6. The one-trade move on SPY is expected: R1-R6 changed
grading and stop-fill behavior on `main` since that run. TSLA's control count also moved,
1,017-book's 66 to 60 here for the same reason. Both numbers are freshly measured, not
copied from the earlier report.)

**Loss is not upstream of the gates.** Levels are found on effectively every index cell and
a break-and-retest/order-block setup forms on 96.7% of them (1451/1500) — the engine is not
blind to index structure. Attributing each no-trade cell to the gate that stopped its best
signal:

| killer gate | INDEX_POOL cells | TSLA cells |
|---|---|---|
| **`_SKIP_GRADES`** (D-grade skip) | **1419** | 392 |
| no_setup_formed | 49 | 6 |
| displacement | 15 | 42 |
| traded | 17 | 60 |

`_SKIP_GRADES` still kills 97.8% of the index loss after setups form, unchanged in kind from
the pre-T0 measurement. Splitting the D-grades by cause:

| symbol | D via tight-stop rule | D via PA pattern | tight-stop share |
|---|---|---|---|
| QQQ | 4391 | 228 | 95.1% |
| SPY | 4290 | 131 | 97.0% |
| IWM | 4649 | 343 | 93.1% |
| TSLA | 3981 | 1412 | 73.8% |

**The mechanism is `signal_runner.min_risk_floor()`**: `max(0.10, 0.0015 x close)`, applied
to every B&R entry's post-fill `entry - stop`. It is a **price-level** floor, not a
volatility floor. At QQQ's ~$570-700 range that is a $0.85-$1.05 minimum stop distance in
dollars, regardless of how far the symbol actually moves in a session — and index retest
stops are almost always narrower than that in dollars, because indices trade at a high
absolute price with a low *relative* range. TSLA clears the same rule far more often (74% vs
93-97% tight-stop share) simply because it is lower-priced with a wider relative range, not
because its setups are structurally better. This confirms — not merely repeats — the pre-T0
finding: the loss is a grading/stop-distance rule, not level geometry, and it is exactly
where the spec said to check first.

## Q2 — scale the floor to the symbol's own prior-20-session range

### The change

`signal_runner.min_risk_floor()` now accepts an optional `scaled_dollars` override, gated
behind a new flag `ENABLE_ATR_SCALED_MIN_RISK` (default OFF — the flag-off engine is
byte-identical to the shipped default, same pattern as `ENABLE_STRUCTURAL_RISK_FLOOR` and
`ENABLE_MIN_RISK_FILL_CLAMP`):

```
ENABLE_ATR_SCALED_MIN_RISK=0 (default): max(0.10, 0.0015 * close)   -- unchanged
ENABLE_ATR_SCALED_MIN_RISK=1:            max(0.10, MIN_RISK_ATR_MULT * prior20_avg_range)
```

`prior20_avg_range` is the symbol's own trailing 20-session average daily RTH range
(high - low), computed strictly from days *before* the trading day being graded — no
look-ahead. `MIN_RISK_ATR_MULT = 0.05` (`research/t4_index_parity.py` calibrates it — see
below). `SignalRunner.min_risk_dollars` carries the value; the backtest driver
(`backtest_week.simulate_day`) sets it per symbol/day, `live_scanner` never sets it so the
live path is untouched by this track. Both B&R grading call sites (long and short) now read
`min_risk_floor(current.close, self.min_risk_dollars)` instead of inlining the constant
twice — the floor and its two call sites cannot drift apart, same discipline as the existing
`clamp_fill_to_min_risk`.

### Calibration

`0.0015 x close` and `0.05 x prior20_range` are answering different questions (price level
vs. actual movement), so they cannot be made to agree everywhere by construction. Checked
against 24 trailing sessions per symbol:

| symbol | avg close | avg daily range | old floor ($) | new floor ($) | new/old |
|---|---:|---:|---:|---:|---:|
| QQQ | 703.14 | 11.71 | 1.055 | 0.585 | 0.55x |
| SPY | 750.10 | 7.19 | 1.125 | 0.359 | 0.32x |
| IWM | 294.93 | 3.84 | 0.442 | 0.192 | 0.43x |
| AAPL | 321.85 | 7.28 | 0.483 | 0.364 | 0.75x |
| NVDA | 206.30 | 7.22 | 0.309 | 0.361 | 1.17x |
| TSLA | 353.22 | 12.47 | 0.530 | 0.624 | 1.18x |
| COIN | 158.88 | 9.44 | 0.238 | 0.472 | 1.98x |
| MU | 900.78 | 64.85 | 1.351 | 3.242 | 2.40x |

All three indices loosen (0.32-0.55x the old floor) — the intended effect. Some equities
loosen slightly (AAPL 0.75x), a few tighten (NVDA/TSLA ~1.18x, COIN ~2.0x, MU ~2.4x) because
those names carry a genuinely wide *relative* range the flat 0.15%-of-price rule never
priced in either direction. This is the honest shape of a rule that switches from "percent
of price" to "percent of the symbol's own movement" for every symbol, not a side effect
scoped to indices alone — it is reported here rather than hidden or hand-tuned away.

### A/B result

Ran the full ratified engine (`backtest_week.simulate_day`, same trade definition as T0's
book: `status=="fired" and grade!="C"`) over INDEX_POOL + MAJOR_15, 2024-08-xx..2026-08-xx
(730-day window, all archived sessions in range). OTHER_POOL symbols are excluded from this
run only to cut runtime — they never land in the `index` or `equity` aggregation bucket
(`universe.pool_for`), so nothing measured here changes by excluding them.

`research/t4_index_parity.py --arm off --pools index_equity` (baseline, byte-identical to
the shipped default) vs `--arm on --pools index_equity` (flag on, floor scaled for **every**
symbol) vs `--arm on --pools index_equity --index-only` (flag on, floor scaled **only** for
QQQ/SPY/IWM — MAJOR_15 always passes `min_risk_dollars=None`, so its gate cannot move):

| | OFF (baseline) | ON, universal | ON, **index-only** |
|---|---:|---:|---:|
| **index n** | 18 | 127 | **127** |
| index mean R | 0.7086 | 0.4075 | 0.4075 |
| index win rate | 77.78% | 55.91% | 55.91% |
| index months green | 7/10 traded | 16/25 | 16/25 |
| index median stop_pct | 0.186% | 0.095% | 0.095% |
| **equity n** | 622 | 567 | **622** |
| equity mean R | 0.7857 | 0.5079 | **0.7857** |
| equity win rate | 53.86% | 51.68% | **53.86%** |
| equity months green | 23/25 | 22/25 | **23/25** |
| equity pct stops <0.15% | 2.09% | 22.40% | **2.09%** |

Two findings, and they point in different directions:

1. **The index quota moves.** 18 → 127 traded over the 2-year window — a **7.06x** lift,
   still well under MAJOR_15's per-symbol trade rate (127/3 = 42.3/symbol vs 622/15 = 41.5/
   symbol — almost exactly matched per-symbol once the floor stops discriminating on price
   level, not "more than stocks", consistent with his own 3-S-of-15 index-vs-stock setup
   rate saying they should fire *more*, not *equal*). Every one of the 25 months now carries
   at least one index trade (`months_total` 10 → 25) — the old 18-trade book couldn't even
   be durability-tested on 15 of its 25 months; this one can, and reads 16/25 green (64%).
   Quality per trade is genuinely lower on the *new* index trades (mean R 0.71 → 0.41, win
   77.8% → 55.9%) — expected: the old 18 were an extreme top-slice of a nearly-closed gate,
   opening it lets in real but more marginal setups, same shape as any recall-vs-precision
   trade.

2. **Applied universally, the same change measurably hurts equities** — fewer trades (622 →
   567, **-8.8%**), worse mean R (0.7857 → 0.5079, **-0.278R**), worse win rate (53.9% →
   51.7%), one fewer green month (23 → 22), and — directly answering what this track was
   asked to confirm — **yes, it floods the book with tiny-stop equity trades**: the share of
   equity trades stopped inside 0.15% of price rises from 2.09% to **22.40%**, a 10.7x jump.
   `0.05 x prior20_range` is not neutral for names with a wide relative range relative to
   their price (MU, COIN — see the calibration table above) — it loosens their floor enough
   to admit marginal setups the flat 0.15%-of-price rule was correctly rejecting.

3. **Scoping the flag to INDEX_POOL only removes finding 2 completely, by construction.**
   Equities pass `min_risk_dollars=None` regardless of the flag when `--index-only` is set,
   so `min_risk_floor()` falls back to its unchanged `0.0015 x close` default for every
   MAJOR_15 name — the equity column above is **exactly** the OFF baseline, not
   approximately (same n, same mean R to four decimals, same win rate, same green-month
   count, same tiny-stop share). The index column is unchanged from the universal run
   because the same symbols get the same treatment either way. Index-only gets 100% of
   finding 1's benefit and 0% of finding 2's cost.

### Reachability / flooding check

The explicit ask: *"confirm you have not flooded the book with tiny-stop equity trades."*
**Under the shippable configuration (index-only scoping), no** — equity tiny-stop share is
2.09%, identical to today's committed engine, because equities never read the scaled floor.
**Under the universal (unscoped) configuration, yes** — 22.40% vs 2.09%, and it costs real
mean R and win rate on top of it. The distinction matters: this is not "the mechanism is
safe," it is "the mechanism is safe *once scoped to the pool it was built to fix*." Nothing
in `min_risk_floor()` itself enforces that scope — it is a caller-side decision, same
pattern the codebase already uses for every other flag here (the driver decides who gets
primed, the function just reads what it's given).

## Recommendation

**Ship `ENABLE_ATR_SCALED_MIN_RISK`, default OFF, scoped to INDEX_POOL only** —
`backtest_week.simulate_day`'s caller should prime `min_risk_dollars` only for QQQ/SPY/IWM,
never for MAJOR_15/OTHER_POOL, until a follow-up sweeps `MIN_RISK_ATR_MULT` against held-out
recall for the names it currently tightens (calibration table above: NVDA/TSLA ~1.18x,
COIN ~2.0x, MU ~2.4x the old floor). Scoped this way the change is **purely additive on
indices and a no-op everywhere else** — verified to four decimal places above, not asserted.
This is a research-script finding, not yet wired into the engine's shipped default path:
`backtest_week.simulate_day` and `signal_runner.py` both still leave
`ENABLE_ATR_SCALED_MIN_RISK` OFF and `min_risk_dollars=None` for every caller, so the
committed book is unchanged until someone (Austin, or a follow-up track) decides to scope
and prime it in `backtest_2y.py`/`live_scanner.py`.

## What did not run

- Held-out recall (`probe_s_sweep_2026-08-28.jsonl` / `probe_master_2026-08-29.jsonl`) was
  **not** re-scored against the ON arm — those probe decks are not index-heavy (indices are
  3 of his 15 cards) and this track's gate is the trade-count/greenness measurement the spec
  asks for, not a recall claim. A future track wiring this flag on should re-run the recall
  probes before shipping it live.
- No options/contract/spread scoring — every number is the underlying in R, same scope
  limit as T0.
- `MIN_RISK_ATR_MULT=0.05` is one calibration point, not a swept optimum — the table above
  shows it is not neutral across every equity. A follow-up could sweep it against held-out
  recall the way `research/g13_floor_fix_ab.py` swept the structural floor.

---
