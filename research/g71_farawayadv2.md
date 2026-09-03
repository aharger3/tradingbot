# G7.1 / adversarial verify — track `faraway`, the SCOPE LIMIT claim

**Verdict: NOT REFUTED.** Every load-bearing element reproduced independently.
Script: `research/g71_farawayadv2_scope.py` (read-only; AST + live arithmetic).

## What was checked, and what came back

| element of the claim | independent result |
|---|---|
| `options_sizer.py:25 DEFAULT_RR = 2.0` | exact, verbatim; **not env-overridable** (no `getenv` on that name) |
| consumed at `:202/:223/:228/:291/:307` | all five verbatim: param default, `stock_target` call/put, `target_premium`, `max_reward` |
| `live_scanner.py:631` passes no `rr=` | AST: `kwargs=[direction, max_loss, stock_entry, stock_stop, symbol, tasty_feed]`, `rr` absent |
| every other live call site | `live_scanner.py:494 build_futures_plan` no `rr=`; `backtest_window.py:79` no `rr=`. No caller anywhere passes `rr` |
| "exactly 2R" | reproduced on 4 entry/stop pairs, both sides: `stock_target` = 2.0000R, premium `(tgt−entry)/(entry−stop)` = 2.0000, `max_reward/max_loss` = 2.0000 |
| "no runner at all" | `paper_trader.py:39 RULE6_ENABLED = False`, not env-overridable; and even the post-BE runner leg exits at `self.stock_target` (`paper_trader.py:201`), so **no live path can book >2R**, BE on or off |
| "sell all at 2R" is literal | `options_sizer.py:120` prints exactly that string on the Discord card |
| "no arm can move held-out S recall" | `research/t0_heldout_recall.py:92-94 score_sweep` scores a card purely on `d["fired"]` — detection only, no exit, no P&L, no `LOSS_HALT`. An exit-only arm is mathematically inert on it |
| faraway's own diff stays exit-side | `research/g71_faraway.md §7` patches `backtest_week.py:846-858` + a new `RUNNER_MEASURED_MOVE` flag. `signal_runner.py` untouched, so no entry moves |

## Three notes that do not refute

1. **Book identity — the challenge's premise is the wrong one.** `research/bt2y_trades.json`
   meta: generated `2026-08-29T03:14:29`, 500 sessions 2024-08-21→2026-08-21, 76,019 signals,
   **traded 2437**, `loss_halt` on, 857 halted. 2,595 is the *superseded* T0 book
   (`g71_advscaleladder.md:83`, `g71_advcapture.md:80` — "No 2,595-trade book exists in the
   tree"); 1,017 is the dead `research/g3_arm_ow1.json`. `faraway` used the current book.
2. **The human-facing card is not quite silent about scaling.** `signal_runner.py:1975`
   appends `[path level $X: scale target]` to `sig["reason"]`, which `live_scanner.py`
   prints in the alert. `path_target` has **no consumer** outside `signal_runner.py` —
   `options_sizer` and `paper_trader` never read it. Cosmetic; the sizing and the exit are
   still flat 2R.
3. **Sections 4-6 are weaker than the claim admits, not stronger.** The arms are a paired
   replay on a *fixed* trade set (`g71_faraway.py:32` "Entry, stop, side and entry bar are
   FIXED"). `LOSS_HALT` is ON in the book (857 blocked) and is a function of realized P&L,
   so a shipped `RUNNER_MEASURED_MOVE` would move the *traded set* too — the +0.0228R is a
   ceteris-paribus number, not a ship-through number. This does not touch recall, which is
   measured without `LOSS_HALT`.

## Missing from the claim (additive, not corrective)

`options_sizer.py:373 build_futures_plan(rr=DEFAULT_RR)` is the same cap on the futures live
path (`live_scanner.py:489-494`, `runner.futures_mode`). The claim says "the live path has no
runner"; both live paths have none.
