# G3 / T3 — ON WATCH on the 2-year book

> **CORRECTED 2026-08-28 — the wide error bar is retired and this delta is READABLE.** This file's headline used to say the +0.1135 R delta was 14× smaller than a ±1.5799 R bar and "not resolved". That bar existed only because nobody had ruled on whether a stop resting inside the entry bar could have fired before the back-dated fill. **Austin ruled on 2026-08-28: "Out on that same close."** A stop is triggered by a candle CLOSE and nothing else; the entry candle's own close counts; there is exactly one close per bar. So a stop cannot fire *inside* the entry bar ahead of the fill, the `intrabar_stop` class is not ambiguous, and **the bar this file carries is the narrow one — ±0.0095 R shipped, ±0.0088 R on the off arm.** The +0.1135 R delta **clears it by 12×**. Every wide figure below is kept as history — it was the honest pessimistic price of a genuinely open question — but must not be quoted as a live interval.

**Flipping `ON_WATCH` moves mean R by +0.1135 R on the whole traded book (+0.2023 R on S) and costs a green month. That delta clears the ±0.0095 R error bar this book carries on its fill assumption by 12×, so its sign is readable — it is small, not unresolved.** The flag also does not do what its name suggests: it changes **0** of 45,193 signals and leaves **74.7% of traded fills still intrabar** when switched off. *(Retired framing, kept for the record: measured against the wide ±1.5799 R bar this delta was 14× smaller and was reported as unresolved.)*

`ON_WATCH=1` is **the shipped default today** (`signal_runner.py:368`, `os.getenv("ON_WATCH", "1")`). Nothing here changes it. Both arms were replayed at _this commit_ by `research/g3_onwatch_2y.py`, which shells `backtest_2y.py` once per arm with the flag forced in the child's environment.

One result cuts the other way and is the most useful thing in this file. The error bar was **not a property of the tape** — it was a property of one unanswered question. 791 of the 793 ambiguous traded rows on the shipped arm are the stop sitting on the entry bar's own extreme, and this file said that if Austin ruled those unreachable inside the bar he was filled on, the bar would collapse from ±1.5799 R to ±0.0095 R — **167× narrower** — and the delta would clear it comfortably. **He ruled exactly that on 2026-08-28, and it did.** The A/B was never blocked by missing data; it was blocked by an open rules question, and the question is closed.

## The table

`n` is the traded book — the population the 2.0R money gate reads. Win rate is of DECIDED trades (scratches excluded), the same convention `research/a2_bt2y_summary.py` prints and this table imports. `months green` is months with positive total R; the durability gate is EVERY month green. Entry match is any signal within ±3 bars of one of Austin's 64 marked entries on the same symbol-day. The error bar column is stated on each arm's own book, **retired wide bar first and the carried narrow bar in brackets** — read the bracketed figure; see §the error bar.

| arm | population | signals | n traded | mean R | median R | win rate | months green | entry match ±3 | error bar (wide RETIRED / narrow CARRIED) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ON_WATCH=0` | whole book | 45,193 | 1,091 | +0.8416 | +0.4120 | 54.1% | **24 / 25** | 35 / 64 | ±1.3388 (±0.0088) |
| `ON_WATCH=1` (shipped) | whole book | 45,193 | 1,017 | +0.9551 | +0.5660 | 53.2% | **23 / 25** | 35 / 64 | ±1.5799 (±0.0095) |
| `ON_WATCH=0` | S subset | 7,296 | 144 | +1.0806 | +0.9135 | 68.1% | **23 / 25** | 6 / 64 | ±0.9967 (±0.0668) |
| `ON_WATCH=1` (shipped) | S subset | 7,454 | 128 | +1.2829 | +1.1290 | 66.4% | **23 / 25** | 8 / 64 | ±1.2573 (±0.0751) |

| delta (`ON_WATCH=1` − `ON_WATCH=0`) | signals | n traded | mean R | median R | win rate | months green | entry match ±3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| whole book | +0 | -74 | **+0.1135** | +0.1540 | -0.9 pts | -1 | +0 |
| S subset | +158 | -16 | **+0.2023** | +0.2155 | -1.7 pts | +0 | +2 |

**Neither arm passes the money gate and neither is durable.** The gate is mean R = 2.0 and EVERY month green. `ON_WATCH=1` books +0.9551 R with 23 of 25 months green; `ON_WATCH=0` books +0.8416 R with 24 of 25. Both are roughly half the gate and both have a red month, so the flag is not what stands between this book and the gate — and the two arms trade against each other: the shipped arm buys +0.1135 R of mean R and gives back a green month.

Two structural reads from the same table, and they are the load-bearing ones. **Signals are identical to the row: 45,193 in both arms.** ON WATCH creates and suppresses nothing — it is a price rule, exactly as `fill_price` says. What it moves is the traded count, by -74: a fill back-dated to the level lands on or through the level-stop, and the trade is either re-stopped on the entry bar by `signal_runner.intrabar_stop` or dropped by the minimum-risk gate. The S subset moves too (+158 signals) because `research/downgrade.py` grades off the STOP, and the stop moved.

## What `ON_WATCH` actually controls — and what it does not

**It does not produce a fill-at-the-close arm, and this comparison is not "close fill vs intrabar fill".** `signal_runner.fill_price` back-dates a fill to the level when EITHER predicate is true:

| predicate | measures | gated by `ON_WATCH`? | reachable from |
|---|---|---|---|
| `bar_extreme_veto` | the close sits in the top/bottom `BAR_EXTREME_FRAC` of the SIGNAL BAR's own range | **no — always live** | all 10 `fill_price` call sites |
| `near_session_extreme` | the close sits within `BAR_EXTREME_FRAC` of the SESSION range from the day's high (long) / low (short) | **yes — this is the whole flag** | 2 of 10: the long and short break-and-retest fills (`signal_runner.py:1638`, `:1878`) |

The other 8 call sites — FVG, order block, flag and the 84% re-entry, both sides each — call `fill_price(level, candle, is_long)` with no session extremes, so `near_session_extreme` returns False there by construction. So the arms are:

| arm | what back-dates a fill |
|---|---|
| `ON_WATCH=0` | `bar_extreme_veto` only |
| `ON_WATCH=1` | `bar_extreme_veto`, plus break-and-retest bars closing jammed against the session extreme without sitting at their own bar's extreme |

Measured on the traded book, that is what survives the switch:

| arm | traded | intrabar fills | of traded | ambiguous | **of intrabar** | signals ON WATCH alone could move |
|---|---:|---:|---:|---:|---:|---:|
| `ON_WATCH=0` | 1,091 | 815 | 74.7% | 722 | **88.6%** | 175 |
| `ON_WATCH=1` | 1,017 | 913 | 89.8% | 793 | **86.9%** | 90 |

The *ambiguous / of intrabar* column is T2's headline recomputed on each arm rather than quoted: **86.8% of traded intrabar fills sit on a bar whose range also contains the stop** on T2's book, and 88.6% / 86.9% here on the off / on arms. Turning the flag off does not meaningfully dilute it, because the class it removes is ambiguous for the same reason as the class it leaves.

**Turning the flag off leaves 74.7% of traded fills still intrabar.** Only the last column is the flag's reach: signals whose entry bar trips `near_session_extreme` and does NOT trip `bar_extreme_veto`, so ON WATCH is the only rule that could have moved the price. Everything else fills identically in both arms. A clean close-fill arm is **not expressible through this flag** — it would need `fill_price` itself changed, which this ticket does not do.

That last column is 175 on the off arm and 90 on the on arm, and the drop is the mechanism, not an inconsistency: in the off arm those rows fill at the close, keep their structural risk and stay in the traded book; in the on arm most are back-dated to the level, land on the level-stop, and leave the traded book through `intrabar_stop` and the minimum-risk gate. It is the same -74 trades the traded count lost, seen from the other side.

This is also why `research/t61_onwatch_ab.py` measured +0 on every metric over the 120 day-cards and was right to: ON WATCH creates and suppresses no signal, so a recall harness cannot see it at all. The effect it has is on price, and price only shows up in R.

## The error bar, and which one this file carries

From `research/p26_intrabar_ambiguity.py` (T2): when a fill is back-dated into the entry bar, that bar's own range usually also contains the trade's stop, and OHLCV cannot say which price traded first. The engine assumes fill-then-stop every time. Repricing the other order is the error bar, and it is **one-directional** — the booked mean R is a ceiling, never a midpoint.

T2's load-bearing split is that **790 of that book's 792 ambiguous traded bars are the stop sitting ON the entry bar's own extreme**, put there by `signal_runner.intrabar_stop`; only 23 (2.5% of intrabar fills) have a stop clear of both wicks. That gave two candidate bars. **This report carried the WIDE one until 2026-08-28; it now carries the NARROW one.**

| bar | which ambiguous rows are repriced to −1.0R | `ON_WATCH=1` whole book | `ON_WATCH=0` whole book | status |
|---|---|---:|---:|---|
| **narrow — CARRIED** | only rows whose stop is NOT the entry bar's own extreme | **±0.0095 R** | **±0.0088 R** | the interval on every number here |
| wide — RETIRED | all of them, the `intrabar_stop` class included | ±1.5799 R | ±1.3388 R | history, 2026-08-28 |

**Why the wide one was carried.** The `intrabar_stop` class is manufactured by a stop rule rather than found in the tape, but manufactured is not resolved. A stop resting on the entry bar's own low is a price that bar demonstrably traded, and on a long break-and-retest bar that closes near its high the low very often traded first — so on a *price* argument that class looked if anything MORE likely to have fired than the residual, not less. Whether such a stop should be modelled as reachable inside its own entry bar was **Austin's call and he had not made it**; excluding the class would have been assuming his answer, and this file would not assume it in order to make its own delta look significant.

**What retired it, 2026-08-28.** The price argument above was the wrong frame, and only he could say so. A stop in this system is not triggered by a price being *traded* — it is triggered by a candle **closing** beyond it. Asked whether a mid-candle entry whose own candle then closes beyond the stop is out on that close, he said: **"Out on that same close."** One close per bar, and the fill is already priced against it. So the `intrabar_stop` class cannot have fired ahead of the fill, is not ambiguous, and does not belong in the bar. **The narrow bar is the right one and the wide bar is retired.**

**The delta above (+0.1135 R) clears the carried ±0.0095 R bar by 12×.** The A/B was never blocked by the data and it is no longer blocked by the rules question either. It is readable — and small: +0.1135 R against a book 1.0449 R short of the money gate, bought by giving back a green month, and buying zero held-out S recall.

| arm | population | traded | ambiguous | stop IS the entry bar's extreme | residual | T2's "clear of both edges" |
|---|---|---:|---:|---:|---:|---:|
| `ON_WATCH=0` | whole book | 1,091 | 722 | 720 | 2 | 22 |
| `ON_WATCH=1` | whole book | 1,017 | 793 | 791 | 2 | 23 |
| `ON_WATCH=0` | S subset | 144 | 62 | 60 | 2 | 2 |
| `ON_WATCH=1` | S subset | 128 | 67 | 65 | 2 | 2 |

The last two columns look like they disagree and they do not — they are two different tests and this is a refinement of T2, not a contradiction of it. *Residual* asks whether the stop equals the entry bar's own extreme; T2's *clear of both edges* asks whether the stop clears the half-cent band the book's 2dp rounding leaves. **21 of the shipped arm's 23 "clear" rows are also at the bar's extreme**, because a bar extreme priced at a half cent satisfies both — e.g. a short whose entry bar high is `216.045`, stored as a stop of `216.04`, which clears the band by construction while still BEING the high. Netting those out, the genuinely residual ambiguity on the traded book is **2 rows of 913**, 0.2% of intrabar fills. T2's 2.5% is a ceiling on it.

## The verdict

| question | answer |
|---|---|
| mean R delta, whole book | **+0.1135 R** (`ON_WATCH=1` − `ON_WATCH=0`) |
| mean R delta, S subset | **+0.2023 R** |
| does it clear the CARRIED error bar (±0.0095 R, narrow)? | **yes — by 12×.** A stop on the entry bar's own wick is ruled unreachable inside that bar: Austin, 2026-08-28, "out on that same close" |
| does it clear the WIDE bar (±1.5799 R)? | no — 14× smaller. **That bar was retired 2026-08-28** and this row is kept only so the old verdict is traceable |
| what does `ON_WATCH` actually control? | one of the two predicates in `fill_price`, at 2 of its 10 call sites. Not detection (0 signals moved), not "fill at close" (74.7% of traded fills stay intrabar with it off) |
| is +0.9571R understated by the fill assumption? | **No — it is OVERstated.** The assumption is optimistic in one direction, so the booked number is a ceiling, not a midpoint. |
| shipped default | `ON_WATCH=1`, unchanged by this ticket |

The question this ticket was set to answer — *is +0.957R understated by the fill assumption, and by how much* — has an answer, and the sign is the opposite of the one the question assumes. The fill assumption is not conservative. Every back-dated fill assumes the trigger beat the stop inside a minute nobody can see, so **+0.9551 R is a ceiling**, and resolving the ordering can only move it down. ON WATCH is one contributor to how many fills get back-dated at all; switching it off moves mean R by +0.1135 R and still leaves 74.7% of traded fills intrabar. So this flag is not the lever that moves the fill assumption. *(This paragraph used to end "it is worth up to ±1.5799 R". Since 2026-08-28 the residual doubt is worth ±0.0095 R — the ceiling claim survives, the magnitude does not.)*

**The one thing worth doing next was not a flag, and it has been done.** It was asking Austin a single question: *when your fill is back-dated to the level and the stop goes on the entry bar's own wick, could that wick have printed before you were filled?* **He answered no on 2026-08-28** — a stop needs a close, and the entry bar has exactly one, so "out on that same close" is the whole rule. That collapsed the error bar from ±1.5799 R to ±0.0095 R and made this A/B, and every other sub-1R ranking in the book, readable. Nothing in the data could have answered it.

## What this does not say

- It does not ship, retire or re-tune the flag. `ON_WATCH` stays at its default of `1` and no line of `signal_runner.py` was edited.
- It does not re-open the stop rule. Stops trigger on the candle CLOSE, fill at that close, floored at −1.25R; wicks stop nothing out.
- It does not claim the delta is large. Since 2026-08-28 the delta clears the carried bar by 12× and its sign is readable, but +0.1135 R is a tenth of an R on a book that is 1.0449 R short of the gate, and it costs a green month. *(This bullet used to say the delta was smaller than the error bar on the number it is a delta of and that the rig could not show its sign. That was the wide bar's verdict and it is retired.)*
- The intrabar marker can only UNDER-count: `backtest_2y.py:169` stores entry at 2dp, so a clamped level that rounds into the close's own cent is recorded as a close fill. The naive `entry != close` test over-reports by ~11 points; T2's corrected marker is imported here, not re-derived.
- 0 signals were dropped for a missing archived day and 0 for an entry minute with no bar. Cache misses are never fetched, on purpose.

## Provenance

Both arms: `2024-08-21` → `2026-08-21`, 500 sessions, 28 symbols, replayed at _this commit_ by `research/g3_onwatch_2y.py`. Reproduce with `python research/g3_onwatch_2y.py run --arm off` then `--arm on`, then `python research/g3_onwatch_2y.py report`; verify the rig with `python research/g3_onwatch_2y.py --selfcheck`.

**The two arms were replayed against the same engine, and that is not an assumption here.** Both processes started within 2 seconds of each other and both books were written within 1.3 seconds of each other, so each imported `signal_runner.py` and `backtest_week.py` from the same working tree in the same second; the identical 45,193-signal count on both arms is the check on it. A concurrent session edited `backtest_week.py`, `live_scanner.py` and `paper_trader.py` (ticket G11, the `stop_rule.py` extraction) TEN MINUTES after both books were written — `stop_rule.py` did not exist while either arm ran, and `backtest_week.py` could not have imported it. `signal_runner.py`, where `ON_WATCH` lives, was untouched throughout.

Two repo gates are RED and neither is caused by this ticket, which adds only new files under `research/`:

- `python research/regression_gate.py` fails on 6 dropped `s_grade` marks. Its whole import closure — `signal_runner.py`, `levels.py`, `omen_bot.py`, `universe.py`, `research/t4_engine_recall.py`, `research/baseline_3.8.json`, `research/austin_marks_v2.jsonl` — is clean at HEAD, so the regression is in a commit, not in a working-tree edit, and predates this file.
- `python research/test_provenance.py` fails on `a1_threshold_sweep.md`, `g10_arming_funnel.md` and `p26_intrabar_ambiguity.md`. All three are committed and clean; each names its script but no commit. This report is not among them.
