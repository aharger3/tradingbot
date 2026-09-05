# g201 mid-candle referee ruling — F9 REFUTED, R2 STANDS. No flag ships.

**What is different now:** three independent referees each reproduced F9's arithmetic to the
dollar and each found the same underlying defect from a different angle. F9's "MID25 pays
$100/day vs the shipped $34/day" is retired. The honest mid-candle number, after both defects
are corrected on the identical book, is **$27/day — *below* the shipped close's $34-37/day**,
with a paired 95% interval of **[−$112, +$95]** that straddles zero. **R2's 2026-09-03 ruling
(mid-candle entry pays 0.2458R *less* than close, CI excluding zero) stands unamended.** No
`ENTRY_FILL=mid25` flag is being added to `signal_runner.py`.

Referee reports: `research/g201_refute1.md` (+ `g201_refute1_check.py`,
`g201_refute1_handcheck.py`), `research/g201_refute2.md` (+ `g201_refute2.py`),
`research/g201_refute3.md` (+ `g201_refute3.py`). Base claim: `research/g158_mid_candle_arms.md`
/ `.py`, commit `685b50e5`. Book `research/bt2y_trades_retest_on.json`, 498 sessions
(2024-09-03 → 2026-09-02), `entry_fill=close`, `RETEST_REQUIRED=1`. All three referees'
`.json` outputs re-verified in this pass by re-running `research/g201_refute3.py` against the
committed book; combined output matches the committed `research/g201_refute3.json` to the
dollar (CLOSE $34/H1 $136/H2 −$68, CLOSE_RT $37, MID00 $105, MID25 $100, MID25_PAIRED $39,
ANTI25 $84).

---

## 1. Which definition was wrong

**F9's was wrong. R2's was right.** They were never actually measuring the same thing, and once
that's made explicit F9's number evaporates rather than reconciles:

| | R2 (`g90_fill_arms.md`, 2026-09-03) | F9 (`g158_mid_candle_arms.md`) |
|---|---|---|
| resting price | confirm bar's **midpoint** (high/low mid) | close **minus 25% of the bar's range**, toward the level |
| fill window | 12 bars | open until the 11:00 cutoff |
| population | 925 traded signals | 8,227 candidates, unfiltered |
| exit model | blind 2R, `LADDER_MODE=None` | shipped F1 ladder via `g80_ordertype_grid.run_trade` |
| comparison unit | **paired**: same signal, close-fill vs mid-fill | **unpaired**, one-trade-a-day, candidate free to change |
| position management | full life of the trade | `run_trade` never manages the bar the limit filled on |

F9's fill definition itself is fine (a resting order strictly after the signal bar is real and
implementable). What was wrong was crediting its $/day gain to *that* price, when three
independent checks show the gain has almost nothing to do with price and almost everything to
do with two look-aheads baked into the harness:

- **The fill bar is never risk-managed.** `run_trade` manages bars `fill_i+1 … EOD`; g158 passes
  the bar the limit filled on as `fill_i`, so a stop already touched inside that same bar is
  invisible to the book. 944 of 7,609 MID25 fills (12.4%) are in exactly that state — filled,
  then immediately through the shipped `DISASTER_STOP` (a resting order at exactly 1R,
  `stop_rule.disaster_stop_hit`) inside the same bar — and g158 pays them as wins.
- **The one-trade-a-day pick is chosen with information from the future.** `oneaday_for` walks a
  day's candidates in signal order and skips to the next one whenever the current candidate's
  limit never fills — a fact not knowable in real time until the 11:00 cutoff. On 34 of 498
  sessions this reshuffles which trade the day "took." A same-candidate control that books a
  no-fill as $0 (`MID25_PAIRED`) settles this cleanly: paired against the like-for-like
  `CLOSE_RT` control, the gap is **+$1.9/day, CI [−$99.9, +$101.3]** — nothing.
- **A placebo kills the price story outright.** `MID00`, a control that rests the limit at 0%
  of the bar's range — i.e. at the exact close price `CLOSE` already pays, zero price
  improvement — fills 8,150 of 8,227 candidates and pays **$105/day, more than MID25's $100**.
  The 25%-back-toward-the-level quantity F9 actually names is worth, paired against MID00,
  **−$4.8/day, CI [−$107.8, +$95.8]**. The entire gain is from *waiting* (the trade skips bars
  where it would otherwise have been stopped out), not from *price*.

R2's paired, in-window, same-signal design was already immune to all three of these: it compares
close-fill against mid-fill on the same trade, with no candidate-substitution and no unmanaged
bar. That is why it found mid *worse* (−0.2458R, CI excluding zero) while F9's unpaired
day-substitution design found mid *better*. Nothing about the categorisation is in conflict —
78/86.3% mid-fillable (F9) and ~20% non-reachable-in-12-bars (R2) are different windows over the
same fact and both stand. Only the money claim was wrong, and it was F9's.

## 2. The honest mid-candle number, both defects corrected

Corrected on the identical 498-session book, same `run_trade` harness, same
`signal_runner.min_risk_floor` gate, 1R = $1,000 (`research/g201_refute1.md` §5, re-verified
this pass):

| arm | $/day | H1 | H2 | mean R | win% | green months | paired vs CLOSE_RT (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---|
| CLOSE (book's own pnl, F9's control) | $34 | $136 | −$68 | +0.034 | 46.5% | 13/25 | — |
| **CLOSE_RT** (like-for-like `run_trade` control) | **$37** | $140 | −$65 | +0.037 | 46.4% | 12/25 | — |
| MID25 as F9 published it | $100 | $164 | $35 | +0.100 | 47.2% | 16/25 | +$65.8 [−$44, +$177] (straddles 0) |
| MID25, fill-bar-managed fix only | $62 | $122 | $2 | +0.062 | 45.8% | 15/25 | +$27.9 [−$80, +$131] |
| MID25, day-pick fix only (=`MID25_PAIRED`-equivalent) | $65 | $161 | −$31 | +0.071 | 45.8% | 13/25 | +$31.1 [−$78, +$139] |
| **MID25, both defects fixed — the honest number** | **$27** | $118 | **−$64** | **+0.030** | 44.3% | **12/25** | **−$6.8 [−$112, +$95]** |
| MID50, both defects fixed | $3 | $109 | −$103 | +0.004 | 33.6% | 12/25 | −$31.2 [−$172, +$112] |

The honest corrected MID25 ($27/day) is **below** the shipped CLOSE ($34-37/day), worse in H2
(−$64 vs −$65 to −$68 is a wash, but MID25's H1 also drops from $164 to $118), and one green
month worse (12/25 vs 13/25). Its own 95% interval covers zero and covers negative. There is no
version of "enter at 25% back into the bar" that survives both look-aheads and clears the noise
floor on this book.

## 3. What is retired

**Retired, do not quote:** "$100/day" and "MID25 beats the shipped CLOSE" from
`research/g158_mid_candle_arms.md`. Both reproduce arithmetically — the referees confirmed that
three times independently — but the number is 73% look-ahead (fill-bar management + day-pick
substitution) and the residual 27% does not clear a paired 95% interval. `g158_mid_candle_arms.md`
stays committed as the record of what was claimed and why it failed review; it is superseded by
this file for any future citation of a mid-candle money number.

**Stands, cite freely:** the categorisation (578 never-return, 514 close-only, 7,096
mid-fillable of 8,227 by the 11:00 cutoff), and R2's 2026-09-03 ruling that a mid-fill entry pays
0.2458R less than a close entry on paired signals (CI excludes zero) — `research/g90_fill_arms.md`.

## 4. Ship decision

No flag. `signal_runner.py` is untouched by this row. `ENTRY_FILL=close|mid25` is not being
added — there is no honest mid-candle number that beats the shipped close to justify carrying a
second selection-time fill model behind a flag. If someone wants to revisit resting-limit entries
later, the fill-bar-management bug in `g80_ordertype_grid.run_trade` (bars `fill_i+1..EOD` should
be `fill_i..EOD` for any non-close entry) is a real, mechanical, one-line-scoped bug independent
of this claim and worth fixing before the next arm is priced through that harness — flagged here,
not fixed here, since this row only owns referee synthesis.
