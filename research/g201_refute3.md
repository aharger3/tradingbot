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


---

# Second pass — an independent re-derivation (2026-09-05, wave 2)

Everything above was re-derived from scratch by a second script,
`research/g201_refute3b.py` (output `research/g201_refute3b.json`), written without reusing
`g201_refute3.py`. Same book, same fill statement as the header. **It lands on the same verdict
and the same numbers**, and adds four things the first pass did not measure.

## 7. Corroboration — the independent script agrees to the dollar

| arm | first pass | **second pass** |
|---|---:|---:|
| CLOSE (book rows, F9's control) | $34/day | **$34/day** |
| CLOSE_RT (same entry, `run_trade`) | $37/day | **$37/day** |
| MID00 placebo (0% back) | $105/day | **$105/day** |
| MID25 (F9's headline) | $100/day | **$100/day** |
| MID25, day-pick held fixed | $39/day | **$39/day** |

The second pass also confirms the whole depth ladder is **monotonically backwards**: with the
day's pick held fixed and a no-fill booked at $0, **MID00 $79 → MID25 $39 → MID50 $6**. More
"mid-candle" is strictly worse. A variable whose claimed effect reverses sign when you turn it up
is not the mechanism.

## 8. Where MID25's $100 physically comes from — the substitution ledger

Counting, day by day, how often each arm abandons the book's first sizeable candidate because its
own limit never filled, and how many dollars it books on exactly those days:

| arm | days it kept the same pick | **days it substituted** | $ booked on substituted days | share of the arm's total |
|---|---:|---:|---:|---:|
| MID00 | 484 | 14 | +$12,806 | $26/day of $105 |
| **MID25** | 368 | **129 of 498 (26%)** | **+$30,111** | **$60/day of its $100** |
| MID50 | 222 | **268 of 498 (54%)** | +$42,129 | $85/day of its $90 |

MID50 changes the day's trade on **more than half of all sessions**. These arms are day filters
wearing an entry rule's clothes. And the rule is not even self-consistent: candidate 1's limit is
still working to the 11:00 cutoff when candidate 2 fires, so on every one of those 129 days the
policy holds **two** positions, not the one the unit is defined on.

## 9. The residue after the substitution is removed is a handful of sessions

Delta versus CLOSE_RT on the fixed-pick walk, by session:

| arm | delta, 2 years | delta $/day | top-1 session's share of it | top-5 |
|---|---:|---:|---:|---:|
| MID00 | +$20,654 | +$41 | 24.2% | **106.7%** (5 of 498 sessions are the entire effect) |
| **MID25** | **+$957** | **+$2** | **627.3%** (2024-09-06 alone) | 2,637.6% |
| **MID50** | **−$15,753** | **−$32** | 38.1% | 160.8% |

**MID25's honest edge over the shipped close is $957 across two years**, and one session is 627%
of it — the rest of the book is net negative against it. This is the same concentration test that
killed F7's classifier (one day = 50.1% of the gain), applied here and failed worse.

## 10. Two things this pass adds against F9, and one correction to the first pass

**(a) MID50 — the depth closest to R2's midpoint — is NEGATIVE, so F9's own harness reproduces
R2's sign.** −$32/day against the close, H1 $80 / H2 −$68, 12/25 green. R2 said mid-candle pays
less than the close; run F9's machinery at R2's depth with an honest day rule and it says the
same thing. **There was never a contradiction to referee.**

**(b) The risk denominator shrinks by construction, and it is what inflates the paired R.** Mean
risk per share falls **$0.7289 → $0.5488** (median $0.54 → $0.41) from CLOSE_RT to MID25, and
`run_trade` re-derives the 2R target off that smaller risk — a mechanically closer target on a
fixed $1,000 R, exactly the arithmetic `CLAUDE.md` warns about. Paired per-trade R over the
candidates both arms priced, before and after the size gate:

| pair | ungated | n | **size-gated** | n |
|---|---:|---:|---:|---:|
| MID25 − CLOSE_RT | +0.1534R | 7,609 | **+0.1218R** | 4,733 |
| MID50 − CLOSE_RT | **+0.5822R** | 7,076 | **+0.1664R** | 2,756 |
| MID00 − CLOSE_RT (placebo) | +0.0511R | 8,150 | +0.0392R | 6,642 |

71% of MID50's ungated per-trade "edge" is rows `min_risk_floor` exists to throw out. And note
the placebo carries a third of the gated effect at **zero** price improvement — the same tell as
section 2, in R rather than dollars. These paired numbers are also conditioned on "the limit
filled", which is only knowable after the fact; MID50 is positive here and **−$32/day** in
section 9 on the same rows. A positive paired R beside a negative $/day is the signature of that
conditioning, not of an edge.

**(c) Correction to section 4(b) above.** The first pass reported CLOSE_RT − CLOSE at +$3.4/day,
CI [+1.3, +5.8], and called F9's control "mismeasured". Measured per-candidate rather than on the
498 one-a-day picks, **CLOSE_RT − BOOK = −0.0012R, CI95 [−0.0031, +0.0008] over all 8,227
candidates — indistinguishable from zero** (size-gated: +0.0005R, CI [−0.0007, +0.0018]). So
F9's book-rows-vs-`run_trade` asymmetry is real bookkeeping sloppiness but it is **not** a
`stop-placement-routed`-class defect and it explains none of the $66 gap. F9's control was fair.
The claim dies on the placebo and the substitution, not on the harness.

**(d) A minor reporting defect, for the record.** `g158_mid_candle_arms.py` increments
`cat_counts["ALL"]` in every branch except `no_bars_after_signal`, so its category table's ALL row
sums to 8,188 rather than 8,227 and understates never-returns by 39 (**578 printed, 617 actual**).
The 7,096 / 8,227 = 86.3% mid-fillable headline is unaffected and still stands.

## 11. Second-pass verdict

**REFUTED, independently and by a different route.** The vault is already correct: retire the
"reopened until someone referees it" line against `Projects/omen-blockers.md` line 95 and
`Projects/omen-brief-2026-09-03.md` line 45, and mark mid-candle entry **dead** again. F9's
categorization survives; F9's arms table does not.

Reads only. No engine file and no mark corpus was opened for writing.
