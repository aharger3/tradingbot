# G7.1 adversarial verify — track `faraway`, claim 2 (the runner TARGET DEGRADATION)

Scripts: `research/g71_farawayadv_verify.py`, `research/g71_farawayadv_bind.py`.
Both rebuild pdh/pdl/pmh/pml the way `backtest_2y.py::main` does (prev archived
day's RTH hi/lo, chained inside the `>= start` window; `pf.premarket_hi_lo` on the
full day) — **not** via `research/p21_target_availability.py::_pdh_pdl`, which the
claim's script used. Nothing from `research/g71_faraway.py` is reused.

## Verdict: REFUTED on "binding". Mechanism and headline count CONFIRMED.

| sub-claim | status | mine |
|---|---|---|
| `cands.append(math.floor(scale_level)+1.0)` unconditional, then `min()`/`max()` | **CONFIRMED** | `backtest_week.py:848-859` (claim cites 851-858; the short-side `runner_tgt = max(cands)` is at **859**, outside the cited range) |
| fires on 2,135 of 2,437 traded rows (87.6%) | **CONFIRMED exactly** | 2,135 / 2,437 = 87.6%, 0 rows dropped |
| 964 of those had a real PDH/PDL/PMH/PML out there | **NOT reproduced — 962** | −2 rows; p21's `_pdh_pdl` reads the whole archive, so it hands each symbol's **first window day** a PDH that `backtest_2y` had as `None` |
| "the runner can never aim more than $1 past the session extreme" | true in dollars, **inverted in R** | see §3 |
| right book | **YES** | `meta.traded=2437`, generated 2026-08-29T03:14:29, 500 sessions 2024-08-21→2026-08-21. 2,595 is the superseded T0 book (`research/g71_advscanners.md:89`, `g71_artifacts.md:27`); 1,017 is the dead `backtest_week` book. The prompt's premise that 2,437 is the wrong book is itself wrong. |
| look-ahead | **NONE** | `scale_level = max(cd.high for cd in candles[:i+1])` (`backtest_week.py:851`) is causal; pdh/pdl are prior-session, pmh/pml are premarket |

## 1. It is not in the live path at all

`grep -rn "runner_target"` over non-`research/` `.py` hits **only** `backtest_week.py`
and `backtest_12mo.py`. `signal_runner.py`, `omen_bot.py`, `live_scanner.py` contain
no `math.floor`/`math.ceil` psych-dollar target and no runner leg.

The report's §1 closing sentence — *"Site 4 is the whole of the **live** far-level
penalty"* — is contradicted by its own §1 row 9: *"the live path has no runner at all,
so sections 4-6 describe an exit the live book does not run."* Site 4 is a property of
the measurement rig, not of the engine. A backtest-rig line cannot be "the real
far-level penalty" of a live system.

## 2. Reachability: the branch is read on half the rows it "fires" on

`backtest_week.py:521` — `_ladder_bar` opens `if not t.scaled:` and every path in that
block `return`s. `runner_target` is read only at `:579` and `:604`, i.e. **after** the
trade has scaled. Counted over the same 2,437 rows:

| | rows | % of traded |
|---|---:|---:|
| psych won the min()/max() | 2,135 | 87.6% |
| …and the trade **scaled**, so `runner_target` was ever read | **1,081** | **44.4%** |
| …and the exit price **equals** that target | **755** | **31.0%** |

So 1,054 of the 2,135 (49.4%) never consulted the value at all. The 87.6% is a count of
branch arithmetic, not of effect; the effect population is 31.0%.

Mean R on the 755 rows the degraded target actually closed: **+2.7305R** — above the
2.0R money gate.

## 3. In R — the project's own unit — the "$1 cap" is a 3.26R target

Distance of the degraded target from entry, over all 2,135 degraded rows:

| p10 | p25 | med | p75 | p90 | mean | ≥ 2.0R | < 1.0R |
|---:|---:|---:|---:|---:|---:|---:|---:|
| +1.35R | +2.06R | **+3.26R** | +5.36R | +8.28R | +4.36R | **76.2%** | 4.7% |

"Never more than $1 past the session extreme" is arithmetically true (measured spread
past the extreme: min $0.01, med $0.49, max $1.00) and economically misleading. Risk on
this book is small in dollars, so a whole dollar past the extreme is a median **3.26R**
target and clears 2.0R on 76.2% of the degraded rows. That is not a level being
"degraded away for distance" in any sense the money gate can see.

## 4. The claim's own report already measures "binding" as null

`research/g71_faraway.md` §4c, `uncapped` — the arm that **removes exactly this
mechanism**: whole-book mean R **+0.0171R against a ±0.0333R bar (null)**, and weeks
green fall 90/105 → **87/105**. Removing the allegedly binding penalty is a measured
null that costs three green weeks. Per `omen-error-bar-exceeds-arms`, that is the
signature of a non-lever.

The one arm that does move (`or_mmove`, +0.0228R vs ±0.0183R) does **not** remove the
psych append — it keeps the shipped target and pushes it out only when the measured
move is further. That is a different mechanism from the one this claim names as binding.

## 5. What survives

- The code site is real, unconditional, reachable, causal, and counted correctly at
  2,135/2,437.
- Everything the claim builds on top of that — "the real far-level penalty", "the
  binding one" — does not survive: the site is not live code, is read on 44.4% not
  87.6% of the book, determines 31.0% of exits, aims at a median 3.26R, and its removal
  measures null in the claim's own table.

No fix is proposed. Nothing here justifies a diff against `backtest_week.py:848-859`.
