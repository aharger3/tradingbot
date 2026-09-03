# G7.1 / losshaltverify — adversarial verify of the `losshalt` claim

**Date** 2026-08-29 · **Script** `research/g71_losshaltverify_edge.py` (seed 7) ·
**Data** `research/bt2y_trades.json` (meta: 500 sessions, 2024-08-21..2026-08-21,
`traded=2437`, `halted=857`) · **Diagnosis only — no engine file touched.**

## Verdict: **REFUTED**

The claim is one true half welded to two false halves, and the false halves are the
load-bearing ones.

| sub-claim | verdict |
|---|---|
| A. No daily-R floor in `loss_halt.py` / `backtest_2y.py` / `live_scanner._tier()` | **true** (uncontested) |
| B. "The only day governor is the consecutive-loss streak" | **false** — at least five others, reachable |
| C. "the conditional-edge table shows [the streak] is the weaker of the two variables" | **false — it is the stronger, on that exact table** |

---

## 1. Sub-claim A survives: there really is no day-R floor

`grep -rniE "DAY_R_FLOOR|daily_r_floor|MAX_DAILY_LOSS|daily_limit|day_r_stop"` over
`*.py`/`*.yaml` returns nothing outside `.claude/worktrees` and the prior agent's own
`research/g71_losshalt*`. Confirmed by reading:

- `loss_halt.py:46-50` — `HALT_AFTER_CONSECUTIVE_LOSSES` and `LOSS_HALT`, nothing else.
- `loss_halt.py:70-84` — the walk carries `streak` only; no realised-R accumulator.
- `backtest_2y.py:213` — the sole governor call is `loss_halt.apply_to_book(rows)`.
- `live_scanner.py:574-576` — gates on `_account_streak["n"]` only.
- `backtest_week.py` — no `max_trades`, no `day_ended`, no day cap of any kind.

That half stands.

## 2. Sub-claim B is false — `max_trades_per_day = 3` is a second, reachable day governor

`omen_bot.py:885-890`:

```python
def day_ended(self) -> bool:
    return (self.consecutive_losses >= 2
            or self.signals_today >= self.max_signals_per_day)
```

`max_signals_per_day` defaults to 3 (`omen_bot.py:874`) and is overwritten from
`config.yaml:17 max_trades_per_day: 3` at `live_scanner.py:709`. The counter is
incremented at `live_scanner.py:468` and `signal_runner.py:3340`, and `day_ended()` is
enforced twice per scan pass — `live_scanner.py:327` (whole-pass early return) and
`live_scanner.py:458` (`break` out of the per-symbol signal loop). **Reachable, live,
and independent of the loss streak** — three wins in a row ends the day just as hard as
two losses.

Four more day-scoped entry blocks in the same file, none of which is the streak:

| governor | site |
|---|---|
| `STOP_AFTER_WIN` (`consecutive_wins >= 1`) | `live_scanner.py:327` |
| `NEWS_HALT` — news_days.json blocks new entries | `live_scanner.py:355-357` |
| regime `ACTION_STOP` / melt-up + melt-down | `live_scanner.py:346`, `451` |
| `GOVERNOR_S_CAP` per-symbol daily cap (default `None`) | `live_scanner.py:551-556`, `583` |
| `WATCH_DAILY_CAP = 5` (alerts) | `live_scanner.py:557` |

The claim's grep-shaped evidence is real but it only ever looked for the *string*
`daily_loss`/`DAY_R_FLOOR`. It never looked for a day governor by behaviour, so it
walked past a hard 3-trades-per-day cap sitting in `config.yaml`.

## 3. Sub-claim C is backwards — independently re-run

Rebuilt from scratch, causal on the exit clock (a candidate at entry moment `at` sees
only trades that had already CLOSED at or before `at`, matching `loss_halt.py:74-83`).
Base = the ungoverned candidate pool `(status=="fired" and traded) or status=="halted"`
= **3,294 trades, +1,659.2R** — the only base on which streak≥2 rows are observable at
all, since R31 removes exactly those from the shipped 2,437. My table reproduces the
prior report's §3 to 4 d.p., so this is not a data dispute.

**A. streak at entry**

| streak | n | mean R | SE | win% |
|---|--:|--:|--:|--:|
| 0 | 1894 | +0.6003 | 0.0475 | 51.3 |
| 1 | 762 | +0.3910 | 0.0834 | 41.3 |
| 2 | 320 | +0.3080 | 0.1170 | 39.7 |
| 3 | 173 | +0.1930 | 0.1448 | 33.5 |
| 4+ | 145 | +0.6359 | 0.2238 | 40.0 |

Monotone on 3 of 4 adjacent pairs. 0-vs-2 = **2.31 SE**, 0-vs-3 = **2.67 SE**.

**B. realised day R at entry**

| day R | n | mean R | SE | win% |
|---|--:|--:|--:|--:|
| ≤ −3R | 254 | +0.3767 | 0.1419 | 37.0 |
| −3..−2R | 227 | +0.4806 | 0.1475 | 45.4 |
| −2..−1R | 444 | +0.2882 | 0.0916 | 43.9 |
| −1..0R | 1001 | +0.6251 | 0.0628 | 52.7 |
| green | 1368 | +0.5122 | 0.0620 | 44.6 |

Monotone on **2 of 4** — the ordering is scrambled. The deepest hole (≤ −3R, +0.3767R)
**out-earns** the shallow one (−2..−1R, +0.2882R), and green under-earns −1..0R.
green-vs-≤−3R = **0.88 SE**. −1..0-vs-≤−3R = 1.60 SE. Nothing here separates.

**C. discriminating power, same rows, permutation null (2,000 shuffles of the bucket
labels, seed 7)**

| variable | eta² | permutation p |
|---|--:|--:|
| **streak** | **0.00386** | **0.0115** |
| day R | 0.00261 | 0.0720 |

**The streak explains ~1.5× more of trade-level R variance than realised day R, and it
is the only one of the two that clears a permutation null at 0.05.** On the claim's own
table, by every read available — monotonicity, extreme-bucket contrast, eta², p —
the streak is the **stronger** variable, not the weaker.

**D. and the floor cuts *better* trades than the halt does**

| conditioning set | n | mean R | SE | SE from 0 |
|---|--:|--:|--:|--:|
| entered with day R ≤ −2R (what a −2R floor blocks) | 481 | **+0.4257** | 0.1022 | 4.16 |
| entered with streak ≥ 2 (what R31 blocks) | 638 | **+0.3514** | 0.0871 | 4.03 |

Both sets are strongly profitable, so neither variable justifies a halt on edge grounds
— that part of the prior report is right and I confirm it. But the −2R floor's victims
are the *more* profitable of the two populations (+0.4257R vs +0.3514R). The claim's
implied conclusion — swap toward a day-R floor because the streak is the weak variable —
points at the more expensive cut, not the cheaper one. Whatever case exists for the
floor is a tail case (worst day, DD), which is exactly what the prior report's §2c
bootstrap actually shows and what its headline sentence then over-reaches past.

## 4. Book provenance — a real discrepancy, though it does not rescue the claim

`DIRECTION.md:20` and `:27` state the post-T0 book as **2,595 trades / +1,422R /
43.1% / +0.5481R**. The file on disk, regenerated 2026-08-29 03:14, carries
`traded=2437`, `halted=857`, ungoverned pool **3,294 / +1,659.2R**. `2,595 + 857 = 3,452
≠ 3,294`, so DIRECTION's headline book cannot be reconciled with `bt2y_trades.json` by
the R31 halt alone — one of the two is stale. The analysis under review used the current
file (correct, and definitively not the 1,017-trade `backtest_week` book), but the
"2,595" figure anyone quotes off DIRECTION.md no longer matches the artifact.

## 5. Corrected claim

> No daily-R floor exists anywhere in the engine — `loss_halt.py:46-50`,
> `backtest_2y.py:213`, `live_scanner.py:574-576` — and that part of the diagnosis
> holds. But the consecutive-loss streak is **not** the only day governor: a hard
> `max_trades_per_day = 3` (`config.yaml:17` → `omen_bot.py:874,885-890`, enforced at
> `live_scanner.py:327,458`) plus `STOP_AFTER_WIN`, `NEWS_HALT`, regime `ACTION_STOP`
> and `GOVERNOR_S_CAP` also end or throttle the live day. And on the conditional-edge
> table the streak is the **stronger** of the two variables, not the weaker: eta²
> 0.00386 (permutation p = 0.0115) vs 0.00261 (p = 0.0720), monotone 3/4 vs 2/4,
> extreme-bucket contrast 2.31 SE vs 0.88 SE. Adding a day-R floor may still be right,
> but the justification is tail control (worst day, max DD), not edge — the trades a
> −2R floor blocks average **+0.4257R at 4.16 SE above zero**, more than the +0.3514R
> the streak halt blocks.
