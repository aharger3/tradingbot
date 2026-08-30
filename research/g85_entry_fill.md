# One entry fill, and the default is now a price he can actually pay

**2026-08-30.** `entry_fill.py` is the entry-price twin of `stop_rule.py`. There is now one
definition of what a trade pays to get in, every rig routes through it, and **the shipped
default changed from a price nobody could get to the signal minute's close.**

One environment variable puts the old book back, exactly:

```
ENTRY_FILL=published python backtest_2y.py      # reproduces every pre-2026-08-30 number
```

---

## The headline, in dollars

Two full two-year runs off the same tree, same stops, same exits, same detection — only the
price paid to get in changes. 1R = $1,000. Austin's bar is **$397 a day**.

| | published fill *(the old default — unobtainable)* | **close fill (the new default)** |
|---|---:|---:|
| **one trade a day, $ / day** | **$721** | **$28** |
| against his $397 bar | 182% | **7%** |
| one-a-day win rate | 66.7% | 45.5% |
| **one-a-day green months** | **25 / 25** | **11 / 25** |
| one-a-day worst drawdown | $5,993 | $25,570 |
| every trade, $ / day | $5,268 | **−$283** |
| every trade, per trade | +$584 (+0.584R) | **−$33 (−0.033R)** |
| every trade, win rate | 59.4% | 44.3% |
| **every trade, green months** | **25 / 25** | **8 / 25** |
| trades booked | 4,508 | 4,329 |

**The whole book was the head start.** Taking every signal, the strategy does not merely earn
less on an honest fill — it loses money, and it is green in 8 months of 25. One trade a day
survives at **$28 a day, 7% of the bar, 11 of 25 green months**.

Two things to hold onto:

1. **The `published` arm reproduces the committed book to the trade** — 4,508 traded,
   $5,268/day, 25/25 months, $721/day one-a-day, identical to `research/g72_after_headline.md`.
   That is the control, and it says the only thing that moved here is the price paid.
2. **$28/day is not in conflict with last night's $48–$187/day** for "market at the signal
   minute's close". The order-type grid held one fixed set of trades and re-priced them; this
   run lets the changed geometry change *which* trades exist (4,508 → 4,329) and puts the full
   shipped stack back on top — the two-loss halt, the size gate, the scale-out ladder. Same
   order of magnitude, same verdict: **nothing here is near $397 a day.**

Under the ratified rule that **green months win**, the honest-fill book is a **FAIL** at every
size, and sizing cannot fix it: multiplying a red month by a positive number leaves it red.

*Books: two 2-year runs written to the session scratchpad, priced with the committed
`research/g72_after_headline.py --book <path>`. The canonical `research/bt2y_trades.json` was
**not** overwritten — it is still the published-fill book, and it is now the only book in the
repo whose fill is not named in its own metadata.*

---

## What was actually wrong

`signal_runner.fill_price` booked the entry at

```python
min(max(level, candle.low), candle.high)
```

— the level, clamped into the signal bar's own range. The engine is bar-close driven: the
signal does not exist until that minute closes, so this pays a price the minute had already
traded before there was anything to react to. `research/g80_lookahead_refute.md` counted it:
**105 of 4,508 trades (2.3%) are obtainable at the book's price**, and 53.8% of the intrabar
fills sit at the bar's own extreme with the level outside the bar entirely, where a resting
order fills nothing at all.

It is the same failure shape as the stop fill in `research/x2_stop_floor_audit.md`: a fill
convention forked across rigs, nobody owned it, every number downstream was flattered. So it
gets the same cure.

---

## The five modes

`entry_fill.entry_fill_price(...)` is the single function. Nothing re-implements an entry price
anywhere — that mistake has already been made once with stops and it cost this project a
published book.

| mode | what it is |
|---|---|
| `published` | the old clamp. **Unobtainable.** Kept ONLY so pre-2026-08-30 numbers reproduce |
| **`close`** | **the signal minute's close — the price he can see when the signal exists. THE DEFAULT** |
| `next_open` | the next minute's open: what a robot reacting to a closed bar really pays |
| `chase_once` | a limit at the level for one bar, then market at the following open |
| `limit_level` | a limit at the level resting from the bar AFTER the signal, expiring 11:00 |

A `limit_level` no-fill is a **NO TRADE, not a free option**. The result carries
`filled=False`, a price of `None` and a plain-English reason, it is falsey so `if not fill:`
is the natural spelling, and `backtest_week.ENTRY_FILL_MISSES` collects every one of them so a
caller counts missed days instead of silently dropping them. `backtest_2y` prints the count and
writes it into the book's metadata next to the fill's name.

**The look-ahead assert.** An order cannot rest before the order exists. The first resting-limit
arm let it: 5,472 of 5,714 fills landed ahead of the signal bar, median 3 minutes early, and it
turned a +$92/day arm into a fabricated −$252/day. `future_bars` now means bars *strictly after*
the signal bar, it is asserted rather than trusted, and a violation raises `LookAheadError`
instead of returning a number. The signal bar itself is never scanned for a limit fill, however
far through the level it traded.

### What the limit arms actually look like once they cannot cheat

Smoke-run over 25 sessions, all symbols:

| mode | setups that never became trades |
|---|---:|
| `limit_level` | 3,355 |
| `chase_once` | 1,376 |
| `next_open` | 135 |
| `close` | **0** |

And the dominant reason is not "price never came back". It is **"filled at X, at or through the
stop"**. For a break-and-retest the level *is* the stop, so a limit resting at the level is an
order sitting on your own stop: there is no risk left in it and therefore no trade. That is a
structural fact about the setup, not a tuning problem, and it is the honest shape of the
resting-limit path that OMEN-7.3 §4 left open.

---

## The gates

**Runner-stop selftest: GREEN.** One assertion in it had to change and it is worth stating
loudly rather than burying. `STOP_FILL_ORDER=as_booked` means "whatever `fill_price` ships", and
what `fill_price` ships is exactly what changed — so `as_booked` and `market_on_close` now agree,
because both are the close. The distinctness check the file exists to make now runs under
`ENTRY_FILL=published`, where the two conventions genuinely differ, and a **new** check asserts
the shipped entry fill is the close, so nobody can quietly put the unobtainable clamp back as
the default without that test going red.

**Recall gate: PASS. No mark went silent, and nothing was re-locked.**
`research/baseline_3.8.json` is untouched.

| | published fill | close fill |
|---|---:|---:|
| baseline-locked fires still firing | all | **all** |
| S-tier marks the engine takes an entry on (of 77) | 12 | **25** |
| A-tier (of 60) | 11 | 17 |
| marks the engine produces any signal on | 83 | 80 |

**Recall went UP, and the reason is mechanical, not lucky.** The close sits further from the
level than the level does, so `entry − stop` is bigger, so the minimum-risk floor and the
tight-stop skip stop throwing setups away. The old fill collapsed a break-and-retest's risk onto
its own stop and then discarded the trade for having no risk in it.

**The three that moved the other way are one-bar shifts, not silences**, and none of them is in
the locked baseline:

| mark | published | close | what it is |
|---|---|---|---|
| `QQQ 2025-12-05` bar 35 | entry at 33 | entry at 32 | one bar earlier, now 3 from his mark — outside the gate's ±2 join |
| `TSLA 2024-03-27` bar 13 | entries at 11 | entries at 10, plus a new one at 33 | same one-bar shift |
| `MU 2025-12-08` bar 12 | entries at 8 and 10 | entry at 8 | the second entry is gone; the day is still traded, 4 bars from his mark |

This is the same class of movement the `RETEST_TOL_FRAC` comment in `signal_runner.py` already
documents: the engine gets in *earlier* and the ±2-bar join loses the mark. **Diagnosis: not a
regression, and not a stale baseline either — a timing shift caused by trades becoming sizeable
one bar sooner.** Nothing to re-lock, so nothing was re-locked.

---

## The test

`research/test_entry_fill.py` — 38 assert-based checks, written before `entry_fill.py` existed
and red until it did. It covers all five modes on both sides, the no-fill case, the expiry at
11:00, the look-ahead assert, and — in an isolated child process with `ENTRY_FILL` popped from
the environment — that the **shipped default really is `close`** and that `signal_runner`
delegates instead of keeping its own copy.

**Mutation-verified twice, because a test that cannot fail is not a test:**

| mutation | result |
|---|---|
| let the resting limit see the signal bar (the −$252/day bug, put back) | **5 of 38 red** |
| put the default back to `published` | **3 of 38 red** |

---

## What is NOT done, and one thing to decide

1. **This test is not wired to any gate.** `CLAUDE.md`'s `verify:` line runs the recall gate and
   the runner-stop selftest. `research/g72_stoptest_wiring.md` is the record of what happens to a
   test nobody runs, and this is the second one. Adding `&& python research/test_entry_fill.py`
   to that line is a one-word change to `CLAUDE.md` and it is **left for Austin**, because that
   line configures the harness, not the engine.
2. **`research/bt2y_trades.json` is still the published-fill book.** Every downstream report
   reads it. It should be re-run on the honest default and re-published — that moves a lot of
   quoted numbers at once, which is why it is flagged rather than done silently.
3. **`research/g76_rebuild_engine.py` still monkey-patches its own fill model** over
   `signal_runner.fill_price`. That is now a second entry-fill definition living in a research
   rig, and it should be retired onto `entry_fill` before it is cited again.
4. **A missed limit still claims the level for the dedupe window.** Arguably right — the order
   was placed and it rested — but it is a decision, and it is written down here rather than
   assumed.
5. **`research/g3_onwatch_2y.py` asserts a `fill_price(` call-site count that was already stale**
   against the committed tree (it expects 11, HEAD has 9). This change adds exactly one
   occurrence. Not a gate, not caused here, but it will mislead the next reader.

---

## Files

| file | what |
|---|---|
| `entry_fill.py` | **new.** The one entry fill, five modes, the no-fill result, the look-ahead assert |
| `research/test_entry_fill.py` | **new.** 38 checks, mutation-verified |
| `signal_runner.py` | `fill_price` delegates and computes nothing; the old bad-fill test is now `close_is_bad_fill`, a verdict rather than a price |
| `backtest_week.py` | re-prices the forward modes once, at the trade-creation site, with the bars after the signal; counts every no-fill; will not manage a position before it is filled |
| `backtest_2y.py` | the book now names its fill and its missed days in its own metadata |
| `research/test_runner_stop.py` | the two order-type conventions are checked where they differ, and the new default is asserted |
