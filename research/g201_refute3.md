# g201 refute #3 — F9's MID25 is REFUTED. R2 stands.

**One sentence:** F9's numbers reproduce byte for byte, but the thing it credits them to does
not exist — a placebo arm that rests its limit at **0%** of the bar's range (i.e. at the very
same close price CLOSE pays) pays **$105/day**, *more* than MID25's $100, and an arm resting at a
deliberately **worse** price than the close pays **$84/day**, so the "25% back toward the level"
price improvement contributes **−$4.8/day, 95% CI [−107.8, +95.8]** — nothing.

Verdict: **REFUTED.** Script `research/g201_refute3.py`, output `research/g201_refute3.json`.
Base commit for the claim: `685b50e5`. Book `research/bt2y_trades_retest_on.json`
(498 sessions, 2024-09-03 → 2026-09-02, `entry_fill=close`, `RETEST_REQUIRED=1`).
Fill: signal-bar CLOSE for the CLOSE arms; a strictly-after-signal resting-limit touch
(`g80_ordertype_grid.limit_touch`) for every other arm; exits `g80_ordertype_grid.run_trade`
(`backtest_week._ladder_bar` + `stop_rule`); size-gated on `signal_runner.min_risk_floor`;
1R = $1,000; one-trade-a-day = first sizeable candidate of the day in signal order.
H1 < 2025-09-01 ≤ H2.

---

## 1. Reproduction — exact

`python research/g158_mid_candle_arms.py` re-run on this box regenerated
`research/g158_mid_candle_arms.json` and `research/g158_mid_candle_arms.md` **byte-identical**
to the committed files (`diff` clean on both). Every published figure stands as arithmetic:
CLOSE $34/day, MID25 $100, MID50 $90, MID75 −$47; 7,096 of 8,227 mid-fillable (86.3%);
578 never-returns; 514 close-only. Nothing below is a reproduction failure. The dispute is
entirely about what those numbers mean.

## 2. The null control — a placebo with zero price improvement beats the headline

Every arm below is priced through the **same** `run_trade` machinery, on the **same** 8,227
candidates, with the **same** one-a-day walk. Only the resting price moves.

| arm | resting price | $/day | % of $397 bar | H1 | H2 | mean R | win% | green | max DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CLOSE | book's own pnl (F9's control) | $34 | 8.6% | $136 | −$68 | +0.034 | 46.5% | 13/25 | $21,405 |
| CLOSE_RT | signal-bar close, **run_trade** | $37 | 9.3% | $140 | −$65 | +0.037 | 46.4% | 12/25 | $21,446 |
| **MID00 (placebo)** | **0% back — the close itself** | **$105** | **26.4%** | $151 | $58 | +0.104 | 51.7% | 13/25 | $13,953 |
| **ANTI25 (adversarial)** | **25% the WRONG way — a worse price** | **$84** | **21.2%** | $144 | $24 | +0.084 | 57.9% | 15/25 | $11,490 |
| MID25 (F9's headline) | 25% back toward the level | $100 | 25.2% | $164 | $35 | +0.100 | 47.2% | 16/25 | $27,488 |
| MID25_STRICT (adversarial) | MID25, must trade a **cent through** | $96 | 24.2% | $160 | $32 | +0.096 | 46.8% | 17/25 | $26,628 |
| **MID25_PAIRED (adversarial)** | **MID25 on the SAME day-pick as CLOSE_RT** | **$39** | **9.8%** | $146 | −$68 | +0.053 | 45.0% | 13/25 | $27,976 |

MID00 fills 8,150 of 8,227 candidates (only 38 limits never touched), so it is not a thin
sample — it is the same book, entered at the identical price, and it pays **$5/day more than
MID25**.

## 3. Paired bootstrap over the 498 sessions ($/day, 10,000 resamples, seed 20260905)

| comparison | mean diff | 95% CI | reads |
|---|---:|---|---|
| MID25 − CLOSE (**F9's headline gain**) | +$65.8 | **[−44.8, +175.9]** | **straddles zero** |
| MID25 − MID00 (**the 25% price improvement itself**) | **−$4.8** | **[−107.8, +95.8]** | **zero, and negative** |
| MID25_PAIRED − CLOSE_RT (same candidate, no-fill = $0) | +$1.9 | [−99.9, +101.3] | zero |
| MID00 − CLOSE (placebo vs shipped) | +$70.6 | [+7.3, +134.7] | the whole gain is here |
| ANTI25 − CLOSE (a *worse* price vs shipped) | +$49.9 | [−22.8, +123.8] | a worse price still "wins" |
| CLOSE_RT − CLOSE (harness only, price identical) | +$3.4 | [+1.3, +5.8] | F9's control is mismeasured |

**F9's own headline gain does not clear zero at 95% even taken at face value.** And the quantity
F9 actually names — resting at 25% of the bar's range rather than at the close — is worth
**−$4.8/day**.

## 4. What the money actually is

Three separate defects, in order of size.

**(a) The gain is the wait, not the price.** MID00 and MID25 differ only in where the limit
rests; they pay the same. ANTI25 rests at a strictly worse price and still pays $84. What all
three share, and CLOSE does not, is that the position **is not open** between the signal bar and
the fill bar — `run_trade` starts management at `fill_i + 1`. The trade gets a free look at the
bars in between and re-enters afterward at a price it could have had immediately. MID00's max
drawdown is **$13,953 against CLOSE_RT's $21,446** on the identical entry price: it is dodging
losses, not buying better. That is the whole $70/day.

**(b) F9's control is a different exit engine from its arms.** `g158_mid_candle_arms.py` scores
CLOSE off the **book rows' own `pnl` field** (`close_rows = {k: universe[k] ...}`) and every MID
arm through `g80_ordertype_grid.run_trade`. Priced like-for-like, the shipped close is $37, not
$34 — +$3.4/day, CI [+1.3, +5.8], the one interval here that excludes zero. Small, but it means
the published "$100 vs $34" was never a like-for-like comparison. This is the same failure class
that killed `stop-placement-routed` in F5: a different exit model reported as a different entry.

**(c) The one-a-day walk promotes candidates on information it cannot have.** MID25's day-pick
differs from CLOSE_RT's on **130 of 498 sessions**. On **129 of those 130** the promoted
candidate fired while the skipped candidate's limit was still live to the 11:00 cutoff — so the
walk takes the second setup only because it already knows the first one will never fill. Booked
honestly (MID25_PAIRED: same candidate, a no-fill books $0), the arm pays $39/day against
CLOSE_RT's $37. Note this defect happens to run **against** F9 here: the reshuffled days lose
$17,432 while the same-pick days gain $48,500. It flatters nothing; it is still not a
real-time-implementable rule.

**(d) MID25_STRICT** — requiring price to trade a full cent through the limit rather than merely
touch it — costs only $4/day ($100 → $96). Unlike `scale-before-the-level`, this arm is **not**
riding bar-extreme-equals-limit fills. That one attack fails; the claim dies on (a) regardless.

## 5. Is R2 wrong? No — and there is no contradiction to resolve

The claim frames this as "one of the two is wrong". Both are right about what each measured;
they measured different things.

| | R2 (`g90_fill_arms.md`) | F9 (`g158_mid_candle_arms.md`) |
|---|---|---|
| price | the confirm bar's **midpoint** (high/low mid) | 25% of the bar's range **back from the close** |
| window | 12 bars | to the 11:00 cutoff |
| population | 925 traded signals | 8,227 candidates |
| exits | blind 2R, `LADDER_MODE=None` | shipped F1 ladder via `run_trade` |
| unit | per-signal, **paired** close-vs-mid | one-trade-a-day, **unpaired**, with candidate promotion |
| comparator | the engine's own `fill_price()` output | the book's `pnl` field vs a different engine |

R2's headline finding is the **paired** one: on the signals where both fill, mid pays 0.2458R
*less* than close, CI [+0.1538, +0.3378] excluding zero, robust across 6/12/24-bar windows.
F9's headline is unpaired and lets the arm re-pick the day's trade. **When F9's own harness is
made paired (MID25_PAIRED), it agrees with R2: no gain, +$1.9/day, CI straddling zero.** R2's
~20% never-returns and F9's 86.3% mid-fillable are also not in conflict — they are different
prices over different windows, and both reproduce.

**R2's ruling stands. F9's money claim does not.**

## 6. What survives F9

The **categorization** — 578 never-returns, 514 close-only, 7,096 mid-fillable out of 8,227 —
reproduces exactly and is descriptive, not a money claim. Keep it. The `near_session_extreme` /
ON WATCH paragraph is a code reading and is unaffected. Delete the arms table's headline from
circulation: **MID25 does not pay $100/day against the shipped close.**
