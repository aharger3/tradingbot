# T11 — the stop fill convention, fixed in every rig that books one

Austin, 2026-08-28: *"fix stop out 1.25 max slippage this needs to be fixed now."*

Rule ballot batch 01 q1, his words: *"a 1m candle close below is exit, max slippage
−1.25r which is 1.25k based on current position sizing."*

Produced by `research/t11_stop_fill_fix.py` (the guard) and `research/t11_rescore.py`
(the book), on top of `research/x2_stop_floor_audit.md`, which found the bug and
priced it. Two-year replay, `ON_WATCH=1`, `--days 730`, 28 symbols × 500 sessions,
`data_archive/` only, zero fetches.

Reproduce:

```
python research/t11_stop_fill_fix.py                 # the guard, 64 checks
ON_WATCH=1 python backtest_2y.py --days 730 --out research/t11_arm_ow1_closefill.json
python research/t11_rescore.py --json research/_t11_rescore.json
```

---

## The rule, and what the repo was doing instead

> A stop **triggers** on a candle **CLOSE**. It **fills at that close**. The realised
> loss is **floored at −1.25R**. Wicks stop nothing.

`stop_rule.stop_hit_on_close` already owned the trigger. Nothing owned the fill, and
the repo had forked into two answers:

| rig | trigger | fill | floor |
|---|---|---|---|
| `research/exit_lab.py` | close | the close | −1.25R, live |
| `backtest_week.py` (the shipped book) | close | **`t.stop`** | **unreachable** |
| `paper_trader.py` (the live path) | close | **`stop_premium`** | **unreachable** |

Filling at the stop price is **−1.000R by construction**, so the floor could never
bind. X2 measured what that hid: **458 of the book's 474 stop-outs (96.6%) were
triggered by a candle that had already closed past 1R** — median −1.3500R, worst
−4.3571R — and every one was recorded as exactly −1.000R. `0 of 45,193` rows were
worse than −1.0R.

This is the **6th** instance of this repo's unreachable-rule class, after
`break_then_rejection`, T4(b)'s failed-entry scratch, `before11`, the OCR order-block
demotion, and `hod_only`'s off-by-one.

`stop_rule.py`'s own docstring was the source of the fork — it asserted *"the trigger
moves to the close; the FILL does not… that is why neither caller needs the −1.25R
floor as live code."* It has been rewritten. CLAUDE.md and ballot q1 win; a resting
stop order triggered by a close cannot slip to −1.25R, so the floor's existence is
itself evidence for the close fill.

---

## 1. The fix: one helper, every caller routed through it

`stop_rule.stop_fill_price(close, entry, risk, long, floor_r=MAX_LOSS_R)` — the only
definition of a stop fill in the repo.

```python
if risk <= 0:
    return close
if long:
    return max(close, entry - floor_r * risk)
return min(close, entry + floor_r * risk)
```

`entry` and `risk` are always the trade's **ORIGINAL** pair, never the moved runner
stop: the floor is −1.25R of the whole trade, not −1.25R measured off whichever stop
happened to fire. `MAX_LOSS_R = 1.25` now lives here too and `exit_lab` re-exports it,
so the constant cannot fork either.

### Every site that books a realised R from a stop

| file:line | was | now |
|---|---|---|
| `stop_rule.py:61` | — | **`stop_fill_price`, the one guard** (new) |
| `stop_rule.py:40` | docstring said the fill stays at the level | rewritten; it owns the trigger only |
| `backtest_week.py:31` | `import stop_hit_on_close, stop_hit_on_wick` | `+ stop_fill_price` |
| `backtest_week.py:289` | — | **`_stop_fill_px(t, c, long)`**, the Candle-shaped wrapper (new) |
| `backtest_week.py:444` (`_ladder_bar`, pre-scale) | `"loss", t.stop, i` | `"loss", _stop_fill_px(t, c, long), i` |
| `backtest_week.py:459` (`_ladder_bar`, runner) | `t.stop if (PESSIMISTIC_FILL and hit_target) else stop_lv` | `_stop_fill_px(...)`, then `min(fill, t.stop)` when `PESSIMISTIC_FILL and hit_target` |
| `backtest_week.py:649` (non-ladder) | `"loss", t.stop, i` | `"loss", _stop_fill_px(t, c, long), i` |
| `research/exit_lab.py:173` (`_stop_fill`) | its own `max(close, entry − 1.25*risk)` | delegates to `stop_fill_price` (behaviour identical, definition no longer private) |
| `research/exit_lab.py:55` (`MAX_LOSS_R`) | `= 1.25` | imported from `stop_rule`, re-exported |
| `research/g10_arming_funnel.py:401` | `"loss", stop, i` | `"loss", _stop_fill_px(t, c, is_long), i` |
| `paper_trader.py:84` | — | **`_stop_fill_premium(close)`** (new): the close through `stop_fill_price`, mapped to a premium by the plan's own delta |
| `paper_trader.py:124` (`_check_stop`) | `self.stop_premium` | `self._stop_fill_premium(close)` |
| `paper_trader.py:194` (runner, BE stop) | X2's `self.entry_premium` | `self._stop_fill_premium(close)` |

**Already correct, verified and pinned, not changed:** every `exit_lab` policy
(`flat_target`, `flat_2r`, `hod_only`, `policy_30_30_30_10`, `policy_50_20_20_10`)
and the ~10 research rigs that call `xl._stop_fill` (`w13_scaling`, `w2_time_ladder`,
`x1_exit_attribution`, `p10_structure_trail`, `r9_simple_book`, `h1_2y_nowatch`,
`w14_hod_only_fix`, `p26_intrabar_ambiguity`) — they route through the one helper by
construction now.

**Found and deliberately left:**

- `backtest_week._entry_scratch:388` still clamps at `max(c.close, t.stop)`. That is
  Austin's clause-2 *scratch*, a live fill correction, not a stop — it keeps the
  resting-order price. `ENTRY_SCRATCH` is default OFF. T11 makes the scratch and the
  stop-out diverge for the first time (the scratch is now strictly the better of the
  two on a bar that closes past the stop), which is the point of the flag.
- `backtest_week.SimTrade.pnl`'s Rule 6 branch (`be_taken`) hard-codes the runner at
  `0.0` on a loss and never reads `exit_price`. `RULE6_ENABLED = False`, so it is
  unreachable in the shipped rig, but it is a **7th** unreachable-rule candidate and
  it will re-hide the floor on that path the day the flag is turned on. **Not fixed —
  flagged.**
- `backtester.py` books stops on the WICK at `exit_price=stop_loss` in six places.
  Nothing in the repo imports it; it is a dead pre-OMEN rig. **Not fixed — flagged.**
- `OMEN_SSCORE_SIZING=1` still writes `r` against a fixed $1,000 and can print
  −1.500R. That is position size, not slippage, and no fill floor can reach it
  (X2 §3.4). Default OFF. Unchanged.

---

## 2. The test: red before, green after

`research/t11_stop_fill_fix.py`, 64 checks, synthetic bars, no archive and no network.
The fixture is `test_entry_scratch.py`'s `long_day` — a B&R the detector really fires
on, entry 100.50 / stop 100.00 / risk 0.50 exactly — so every R below is a real
engine trade, not a hand-set `SimTrade`.

It asserts, per side, in `backtest_week`'s ladder path, `backtest_week`'s non-ladder
path, all four `exit_lab` policies, and the live `paper_trader`:

- a close **1.6R** past books **−1.2500R** — not −1.000R, not −1.6R;
- a close **1.1R** past books **−1.1000R exactly** — the floor is a clamp, not a constant;
- a **wick** through the stop with the close inside books **nothing**;
- after a 50% scale-out the runner floors at **−1.25R of the ORIGINAL `|entry−stop|`**
  (scale leg +2.20R on 50%, runner −1.25R on 50%, book **+0.4750R** — it was **+1.1000R**,
  because the runner's break-even stop filled at break-even);
- no rig keeps a private fill convention.

**RED**, run against `HEAD` (`c089b26b`) extracted with `git archive` — the working
tree was never reverted, another swarm is live in it:

```
T11 STOP-FILL SELFTEST FAILED: 22 of 56 checks are wrong.     exit 1
  - stop_rule.stop_fill_price exists — one fill definition, not one per rig
  - long: close 1.6R past the stop -> the FLOOR, not the stop price  (got -1.0000R, want -1.2500R)
  - long: close 1.1R past books -1.1R exactly — the floor does not bind  (got -1.0000R, want -1.1000R)
  - short: close 1.6R past the stop -> the FLOOR, not the stop price  (got -1.0000R, want -1.2500R)
  - short: close 1.1R past books -1.1R exactly — the floor does not bind  (got -1.0000R, want -1.1000R)
  - long: close 1.6R past -> -1.25R on the binary path too  (got -1.0000R, want -1.2500R)
  - long: close 1.1R past -> -1.1R on the binary path too  (got -1.0000R, want -1.1000R)
  - short: close 1.6R past -> -1.25R on the binary path too  (got -1.0000R, want -1.2500R)
  - short: close 1.1R past -> -1.1R on the binary path too  (got -1.0000R, want -1.1000R)
  - long: scale leg +2.20R, runner floored at -1.25R against the ORIGINAL |entry-stop|  (got +1.1000R, want +0.4750R)
  - long: the runner is not booked at 0R just because its stop sat at break-even
  - short: scale leg +2.20R, runner floored at -1.25R against the ORIGINAL |entry-stop|  (got +1.1000R, want +0.4750R)
  - short: the runner is not booked at 0R just because its stop sat at break-even
  - paper_trader call: stock close 1.6R past books -1.25R on the premium  (got -1.0000R, want -1.2500R)
  - paper_trader call: stock close 1.1R past books -1.10R on the premium  (got -1.0000R, want -1.1000R)
  - paper_trader put: stock close 1.6R past books -1.25R on the premium  (got -1.0000R, want -1.2500R)
  - paper_trader put: stock close 1.1R past books -1.10R on the premium  (got -1.0000R, want -1.1000R)
  - backtest_week.py routes its stop fill through stop_rule.stop_fill_price
  - paper_trader.py routes its stop fill through stop_rule.stop_fill_price
  - research/exit_lab.py routes its stop fill through stop_rule.stop_fill_price
  - research/g10_arming_funnel.py routes its stop fill through stop_rule.stop_fill_price
  - backtest_week.py no longer books a stop-out AT t.stop
```

(56 checks, not 64: the helper's 8 sub-assertions are skipped when
`stop_rule.stop_fill_price` does not exist.)

**GREEN**, after:

```
t11 stop-fill selftest ok: 64 checks. Stops trigger on the close, fill at that
close, floored at -1.25R; wicks stop nothing.                  exit 0
```

### Every other guard in the repo, re-run

| test | result |
|---|---|
| `research/t11_stop_fill_fix.py` | **green**, 64 checks |
| `research/test_runner_stop.py` | green, unchanged, 18 laddered results |
| `research/test_universe_single_source.py` | green, unchanged |
| `research/test_sizing.py` | green, unchanged |
| `research/test_x2_stop_floor.py` | green, **3 assertions updated** |
| `research/test_paper_trader_stop.py` | green, **1 assertion updated** |
| `research/test_entry_scratch.py` | green, **2 assertions updated** |
| `paper_trader.py` self-test | green, **1 assertion updated, 1 added** |

The updated assertions all encoded the OLD convention and are named honestly rather
than quietly relaxed:

- `test_paper_trader_stop.check_cases` asserted `exit_premium == stop_premium` on
  every stop-out ("the trigger moved to the close but the FILL stays at the stop
  level"). It now asserts the close mapped through the plan's delta and floored, and
  additionally that the fill is never **better** than `stop_premium`.
- `test_x2_stop_floor.check_be_stop_fill` asserted the break-even runner fills at
  `entry_premium` and books exactly $0. That was **X2's own fix, and T11 supersedes
  it**: `entry_premium` was still a resting-order fill, right only for a close landing
  exactly on break-even. It now asserts the close fill, that the R sits in
  `[−1.25R, 0R]`, and — unchanged, this is X2's actual finding — that it is never the
  ORIGINAL stop's premium.
- `test_x2_stop_floor.check_backtest_fill_convention` was a characterization of the
  old convention. It hand-assigns `exit_price = t.stop`, so it still passes; its
  docstring was rewritten to say what it now owns (the `SimTrade.pnl` arithmetic, not
  the fill).
- `test_entry_scratch` asserted the scratch and the stop-out book the identical R.
  They now diverge, which is the flag's whole point, and the check says so.

**Pre-existing red, not mine, not touched:** `research/test_w12_grade_gates.py`
(`research.downgrade` has no `break_then_rejection` — OMEN 7.0 wave 1 is editing that
file) and `research/g3_onwatch_2y.py --selfcheck` (`fill_price` call-site count moved
10 → 13 in `signal_runner.py` — same swarm). Both are red at `HEAD` as well; verified
against the `git archive` extract.

---

## 3. The book, re-scored

`python research/t11_rescore.py`. Same engine, same detection, same 45,193 signals and
1,017 traded rows — the only thing that moved is the price a stop-out books.

| | BEFORE `g3_arm_ow1.json` | AFTER `t11_arm_ow1_closefill.json` | delta |
|---|---:|---:|---:|
| signals | 45,193 | 45,193 | 0 |
| traded rows | 1,017 | 1,017 | 0 |
| **mean R** | **+0.9551** | **+0.8341** | **−0.1210** |
| total R | +971.38 | +848.33 | −123.05 |
| **win rate** | **52.9%** | **52.8%** | −0.1 pt |
| win / loss / scratch | 538 / 474 / 5 | 537 / 475 / 5 | one flip |
| **months green** | **23 / 25** | **23 / 25** | **0** |
| **max drawdown** | **11.44 R** over 17 trades | **14.94 R** over 26 trades | **+3.50 R** |
| longest losing streak | 7 | 7 | 0 |
| min R | −1.0000 | **−1.2500** | −0.2500 |
| **rows worse than −1.0R** | **0** | **460** | **+460** |
| rows worse than −1.25R | 0 | **0** | 0 |
| rows at exactly −1.000R | 474 | 14 | −460 |
| distinct negative R values | **1** (`[-1.0]`) | **120** | +119 |
| **rows the −1.25R floor CLAMPS** | **0** | **22,457** (303 traded) | **+22,457** |

**The floor binds.** 303 of the 475 traded losses (63.8%) now sit exactly on
−1.2500R, and 22,457 of all 45,193 signals do. Before the fix it clamped **0 of
45,193**. The left tail is no longer a point mass: 120 distinct negative values, min
−1.2500R, median −1.2500R, mean −1.1925R, worst-case none past the floor.

That 63.8% is the independent confirmation of X2's tape scan, which found **301 of
474 (63.5%)** stop-outs closing past 1.25R by replaying the archive directly rather
than by re-running the engine. Two different methods, same number.

The two red months are the same two: **2025-06 and 2025-09**, before and after.
Durability did not move.

Per Austin's grade — the edge survives, the ordering survives:

| sgrade | n | before | after | delta |
|---|---:|---:|---:|---:|
| S | 128 | +1.2829 | **+1.1878** | −0.0951 |
| A | 251 | +0.9956 | +0.8830 | −0.1126 |
| C | 638 | +0.8735 | +0.7440 | −0.1295 |

The gap to the 2.0R money gate widens from **1.0449 R to 1.1659 R**.

---

## 4. Against X2's published figures — we agree, and here is why the totals differ

X2 predicted **−0.0907 R** of book mean and max DD **11.44 → 14.49 R**. I measured
**−0.1210 R** and **11.44 → 14.94 R**. That is a 33% larger cost, which is material,
so it was decomposed rather than published over.

Matching all 1,017 traded rows between the two books by `(sym, day, et, side)` —
1,017 of 1,017 match, no row appeared or vanished:

| what moved | rows | sum R | per book row |
|---|---:|---:|---:|
| **X2's matched set** — full stop-outs repriced at their own close | 460 | **−92.32** | **−0.0908** |
| **scaled rows** — the runner leg now books a real loss instead of break-even | 142 | −30.73 | −0.0302 |
| **TOTAL** | 602 | **−123.05** | **−0.1210** |

**X2's −0.0907 R is reproduced to the fourth decimal: −0.0908 R.** Neither report is
wrong. X2 said so itself, in §5:

> *"A real close-fill replay would also change which trades exist… so treat −0.0907 R
> as **a lower bound on the cost, priced on a matched row set**, not as the arm's
> mean."*

The extra **−0.0302 R** is exactly the class X2 excluded: 142 laddered trades whose
50% runner had its stop raised to break-even, filled at break-even (0R on that half),
and now fills at the bar's own close. Same reason max DD lands at 14.94 R rather than
14.49 R — X2's drawdown curve repriced only the 474.

X2's tape scan found **458** stop-outs past 1R; the replay books **460**. The two rows
are the half-cent artefact X2 already named (`NVDA 2025-04-24`, `NFLX 2025-01-21` —
the book stores entry/stop at 2 dp while the engine runs at full precision), plus one
outcome flip (538 → 537 wins) where a scaled row's runner turned a marginal win into a
loss.

---

## 5. What this does not say

- **It does not re-litigate the cost.** Austin saw X2's numbers and asked for the fix
  anyway. The −0.1210 R is reported, not weighed.
- **It does not change a single entry.** Austin: *"the risk floor shouldnt cause false
  fires it just stops losers from running past 1-1.25."* Correct — 45,193 signals
  before, 45,193 after, 1,017 traded both ways, and nothing in `stop_fill_price`
  reaches detection.
- **It does not model options slippage.** Everything here is the stock tape. On an
  options book a −1.25 R stock close is worse still, and 1-minute OHLCV cannot say
  what the spread was. `paper_trader` maps the stock close to a premium through the
  plan's **own** delta, linearly, which is what `options_sizer` already assumes —
  consistent with the sizer, not a second model.
- **It does not re-run any published report.** `research/g3_arm_ow1.json` is untouched
  and every BEFORE column is read from it as committed. Every report in the repo that
  quotes a mean R off `backtest_2y`, `backtest_12mo` or `g3_onwatch_2y` is now stale by
  roughly a tenth of an R **in one direction**, and re-running them is a separate
  ticket.
- **The 84% arm gate reads outcomes.** `_arm_84` fires off a full stop-out; the fill
  price changed, the *outcome* did not (a stop-out is still a stop-out), so the arming
  population is unchanged. Not separately measured.
- **`RULE6_ENABLED` and `OMEN_SSCORE_SIZING` remain unfixed**, flagged in §1.

---

## 6. Provenance

| artefact | what it is |
|---|---|
| `stop_rule.py` | `stop_fill_price` + `MAX_LOSS_R` — the one definition |
| `research/t11_stop_fill_fix.py` | the guard, 64 checks, red at `c089b26b` and green after |
| `research/t11_rescore.py` | the before/after table and the delta attribution |
| `research/t11_arm_ow1_closefill.json` | the re-scored book, `backtest_2y.py --days 730`, `ON_WATCH=1` |
| `research/_t11_rescore.json` | every number in §3 and §4, machine-readable |
| `research/g3_arm_ow1.json` | the BEFORE book, `g3_onwatch_2y.py` at `47e60796`, untouched |
| `research/x2_stop_floor_audit.md` | the audit this fix implements |
| baseline commit | `c089b26b` |
