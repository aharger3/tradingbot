# G7.1 adversarial verify — track `trend`, the "two `htf_bias` functions" claim

**Verdict: NOT REFUTED.** Every structural claim holds and every number reproduces
independently, within 0.1–0.5pp. Four descriptive errors found; none of them touch the
conclusion.

Scripts written this pass (nothing shared edited):
`research/g71_trendverify_agree.py`, `research/g71_trendverify_scards.py`,
`research/g71_trendverify_closebug.py`. Raw output: `research/g71_trendverify_agree.txt`.
Book: `research/bt2y_trades.json` (`meta.generated 2026-08-29T03:14:29`, 500 sessions,
76,019 signals, **2,437 traded**).

## 0. Book identity — the right book

2,437 is the CURRENT book; the 2,595-trade book is the superseded T0 one and
`DIRECTION.md:20,27` is the stale line (already established in
`research/g71_advscanners.md:13`, `research/g71_advcapture.md:80`). The claim used 2,437.
Not the 1,017 book either.

## 1. Structural claim — verified

| link | file:line | verified |
|---|---|---|
| the veto | `omen_bot.py:240-243` `opposed = ...` / `if opposed and HTF_BIAS_VETO: return TradeGrade.D` | yes; `TradeGrade.D is TradeGrade.X` (`omen_bot.py:100-101`) |
| veto is ON | `omen_bot.py:29` `os.getenv("HTF_BIAS_VETO","1")` | yes |
| veto is REACHABLE and live | book: **35,628 / 76,019 (46.9%) opposed, 35,075 → `X`**, 553 escape via `[x-lift]`, 445 of those traded | yes |
| money book feeds it hourly | `backtest_2y.py:129` → `backtest_week.py:739` `runner.htf_bias = bias` | yes |
| recall gate feeds it daily | `research/t4_engine_recall.py:179` `runner.htf_bias = htf_bias(symbol, day)` | yes |
| that harness IS the gate | `research/regression_gate.py:34,57` imports `t4.run_day`; `research/t0_heldout_recall.py:36` likewise | yes |
| gate is bias-sensitive | `regression_gate.current_sets` builds `s_grade` from `ent` (status `fired`), which the veto gates. (`any_signal` is NOT — `CaptureRunner._route` appends `skipped_d` rows to `captured` too, so the 75-key detection set is bias-blind. The 5-key `s_grade_fired` set is not.) | yes, partially |
| **look-ahead: none in either function** | `htf_bias_for` filters `ts.date() < day_iso` (`backtest_week.py:715`); `t4.htf_bias` slices `names[max(0,i-40):i]`, excluding the day | clean |

## 2. Numbers — reproduced from the real functions

`research/g71_trendverify_agree.py` recomputes BOTH shipped functions from `data_archive`
and cross-tabs them over all 76,019 rows. Two sanity locks first:

* my hourly reconstruction vs the book's own `bias` column: **76,003 / 76,019 match (99.98%)**
  — the `bias` column IS `htf_bias_for`.
* my daily reimplementation vs the **real** `t4_engine_recall.htf_bias`, 120 random
  (sym, day) pairs: **0 mismatches**.

| | claimed | **reproduced** |
|---|---|---|
| all signals, both directional | 47,503 same / 22,880 flip = 67.5% | **47,629 same / 22,807 flip = 67.6%** (n=70,436) |
| traded rows, both directional | 1,515 same / 713 flip = 68.0% | **1,504 same / 724 flip = 67.5%** (n=2,228) |
| 34 held-out S days | 18/34, 13 inverted (bull\|bear 7, bear\|bull 6) | **18/34 = 52.9%, 13 inverted, bull\|bear 7, bear\|bull 6 — exact** |

The S-day result is exact card-for-card and is robust to the lookback window
(their `hourly_bias` uses the last 8 sessions, mine 12; same 34 labels).

## 3. Four errors in the evidence — none fatal

1. **`t4_engine_recall.htf_bias` does not read RTH closes.** `levels.load_rth_bars`
   (`research/levels.py:64`) filters `>= "09:30"` with **no upper bound**, and the archive
   CSVs run `04:00 → 19:59`, so `bars[-1]["c"]` is the **post-market** close on 98–100% of
   days. The function's own docstring (`research/t4_engine_recall.py:110-111`) and
   `research/g71_trend.md` table row #4 both say "daily **RTH** close". Measured
   (`research/g71_trendverify_closebug.py`, 8 symbols, 5,224 day-labels): the anchor moves
   the bias label on **183 days = 3.5%**. So it is not what drives the 32.4% disagreement —
   the 3-vs-20-session window is — but the claim's own description of definition #4 is
   wrong, and the proposed remediation diff in `research/g71_trend.md:230+` copies that
   wrong docstring forward.
2. **The traded-row figure came from a proxy, not the function.** `68.0% / 713` is
   `g71_trend.json["agreement"]["htf_h1sma20|dsma20"]`, and `dsma20` is
   `g71_trend_cache.py`'s own 16:00-anchored SMA20, not `t4.htf_bias`. Against the real
   function it is **67.5% / 724**. Error 1 fully explains the 11-row delta.
3. **The all-signal figure has no committed maker.** `g71_trend.py`'s agreement matrix is
   computed on `tr = [r for r in rows if r["traded"]]` only; `g71_trend_scards.py` covers
   only the 34 S cards. Nothing in the tree produces `{same 47503, flip 22880}`. That is a
   CLAUDE.md violation ("if you publish a number, commit the script that made it").
   `research/g71_trendverify_agree.py` is now such a script.
4. **"67.5% of the 76,019-signal book" overstates the denominator.** The true denominator
   is **70,436** rows where both definitions are directional; 4,206 are neutral on one side
   and 1,377 uncomputable. On strict exact-string agreement including `neutral`/`None` the
   two functions agree on **63.9%** (47,659 / 74,642) of all signals and **62.7%**
   (1,507 / 2,405) of traded rows — *lower* than claimed, so the correction cuts against
   the claim's own understatement, not for it.

Also omitted (not an error, but relevant to any fix): a **fourth** daily-trend function,
`signal_runner.daily_trend_bias` (`signal_runner.py:1776`) — SMA20 of daily closes with
**no dead band**, so it never returns `neutral`. It feeds `self.daily_bias` /
`HTF_BIAS_GATE`, a different attribute on a different gate, **OFF by default**. Unifying
`htf_bias` should not accidentally unify this one.

## 4. Consequence

Both metrics OMEN steers on are computed on differently-vetoed engines: the money gate
(`backtest_2y` → mean R / win rate / months green) on the ~3-session hourly bias, the
recall gate (`regression_gate.py`, `t0_heldout_recall.py` → 18/34) on the 20-session
post-market-anchored daily bias, and they disagree on **one signal in three** and on
**16 of Austin's 34 held-out S days**. The claim's framing — "the recall gate and the money
book are grading different engines" — is supported.

Do not apply the `research/g71_trend.md` diff as written: it carries error 1 into the new
docstring, and it changes the input to the veto that produces every published recall figure.
