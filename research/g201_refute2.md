# g201 refuter #2 — F9's mid-candle $100/day is 92% candidate re-selection, and the rest is noise

**Verdict: REFUTED.**

**What is different now:** F9's arithmetic reproduces to the dollar, but the $100/day is not an
entry-price result — hold the day's trade fixed and let *only* the entry price change, and MID25
pays **+$5.3/day over CLOSE with a 95% paired-bootstrap interval of [−$95.5, +$105.7]**, and the
"+3 green months" goes to **zero (13/25 both)**. $60.5 of the $65.8/day headline gap comes from the
arm silently rolling to a *different* candidate on 129 of 497 days, using information — that the
first candidate's resting order will never fill — that is not available at the moment it rolls.
Fill: signal-bar CLOSE for CLOSE, strictly-after-signal resting-limit touch for the MID arms, exits
through `g80_ordertype_grid.run_trade` (`stop_rule`-consistent), size-gated on
`signal_runner.min_risk_floor`, 1R = $1,000, book `research/bt2y_trades_retest_on.json` (498
sessions), one-trade-a-day pick. Script: `research/g201_refute2.py`, data
`research/g201_refute2.json`.

---

## 1. F9 reproduces exactly — the attack is not on the arithmetic

| arm | g158 published $/day | g201 re-run $/day |
|---|---:|---:|
| CLOSE | $34 | $33.9 |
| MID25 | $100 | $99.7 |
| MID50 | $90 | $90.3 |
| MID75 | −$47 | −$46.9 |

Same book, same helpers, same size gate. Nothing below is a coding disagreement.

## 2. Paired bootstrap over sessions: every arm's interval covers zero

F9 compares two unpaired totals. Paired by session (20,000 resamples, seed 20260905):

| arm vs CLOSE | obs $/day | 95% CI | P(diff ≤ 0) |
|---|---:|---|---:|
| MID25 | **+$65.8** | **[−$43.0, +$174.0]** | 0.114 |
| MID50 | +$56.4 | [−$97.4, +$213.5] | 0.245 |
| MID75 | −$80.8 | [−$250.2, +$96.2] | 0.823 |
| **MATCHED25** (same trade, better entry) | **+$5.3** | **[−$95.5, +$105.7]** | 0.460 |
| **MATCHED50** (same trade, better entry) | **−$28.2** | [−$146.3, +$87.7] | 0.683 |

Not one interval excludes zero. The headline is inside the error bar of a 498-session sample.

## 3. Multiplicity: the headline is the max of three correlated arms, and the null max is bigger

F9's report text takes `best_mid = max(FRACS, ...)` — the winner of three arms chosen on the
**combined** number. Sign-flip null (flip the sign of each session's paired diff jointly across all
three arms, preserving their correlation; 20,000 draws):

| statistic | value |
|---|---:|
| observed max-arm gap | +$65.8/day |
| **P(null max ≥ observed)** | **0.389** |
| null 95th percentile of the max | +$161.4/day |
| null median of the max | +$47.9/day |

Under the null that no MID arm differs from CLOSE, the best of three beats +$65.8/day **39% of the
time**, and its median is +$47.9/day. F9's headline is smaller than the noise this family routinely
produces. And this counts only g158's own three arms — the entry-fill axis on this same book has
now been swept by `g80_ordertype_grid` (6 order-type policies), `g87_retest_tol`, `g88_level_limit`,
`g90_fill_arms` (6 arms including `mid_candle`) and `g158` (3). At that arm count, one $100/day
reading is the expected outcome, not a finding.

## 4. H1 was not held out — and the arm that wins H1 is worth $0.8/day in H2

F9 picked MID25 on the **combined** number, so both halves were used to select.

| selection | winner | its H2 $/day |
|---|---|---:|
| best on H1 alone (honest, H2 held out) | **MID50** ($179.8/day H1) | **$0.8/day** |
| best on combined (F9's choice) | MID25 | $35.2/day |

The arm you would have picked in September 2025 knowing only H1 pays **$0.8/day** in the twelve
months that followed. The ranking is unstable across the split: MID50 wins H1, MID25 wins combined.

## 5. One-day dominance

Paired MID25 − CLOSE, total gap $32,767 over 498 sessions:

| day | gap | share of total gap | cumulative |
|---|---:|---:|---:|
| 2025-02-06 | $5,521 | 16.8% | 16.8% |
| 2024-10-31 | $4,828 | 14.7% | 31.6% |
| 2025-07-02 | $4,090 | 12.5% | 44.1% |
| 2026-03-02 | $4,032 | 12.3% | 56.4% |
| 2026-06-02 | $3,962 | 12.1% | 68.5% |

**Five days are 68.5% of the gap.** Drop the single best day and MID25 falls to +$54.7/day. MID50
is worse: **four days are 93.2% of its gap**, and the top three alone are 73.6%. The paired diff is
zero on 143 of 498 sessions and *negative* on 146.

## 6. The real mechanism — the arm re-picks which trade the day takes

`oneaday_for` walks the day's candidates in arrival order and takes **the first one that has a
priced row**. For the MID arms, a candidate has no priced row when its limit was never touched. So
when the day's first candidate does not fill, the arm quietly rolls to the second or third.

**MID25's day-pick differs from CLOSE's on 129 of 497 days (26%).**

Holding the candidate fixed (MATCHED25 / MATCHED50: the same trade CLOSE picked, only the entry
price changes, no trade at all if that limit never fills) decomposes the headline:

| component | $/day |
|---|---:|
| MID25 headline gap over CLOSE | **+$65.8** |
| ├ entry price only (MATCHED25 − CLOSE) | **+$5.3** |
| └ candidate re-selection (MID25 − MATCHED25) | **+$60.5 = 92%** |

Green months tell the same story:

| arm | green months |
|---|---:|
| CLOSE | 13/25 |
| MID25 | 16/25 |
| **MATCHED25** | **13/25** |
| MATCHED50 | 12/25 |

**F9's "+3 green months" is entirely the re-selection. On the entry price alone it is +0.**

### The roll is not implementable at the moment it happens

`G.limit_touch(bars, px, long, i + 1, cutoff)` scans to the 11:00 cutoff, so the abandoned
candidate's resting order is **live and unresolved for the entire window in which the rolled-to
candidate fills**. On all 129 re-picked days the arm decides to abandon candidate 1 at a moment when
candidate 1's order might still fill. It is also ordered by *arrival*, not by *fill time*: if
candidate 1 fills at 10:40 and candidate 2 at 10:15, the arm books candidate 1, which is not what a
resting order does in wall-clock time. This is a day-selection rule dressed as a fill rule, and it
is not one a trader can execute.

## 7. Why the fill-conditional subsample looks so good — and why it nets to nothing

On the 368 days where the mid-limit *did* fill CLOSE's own pick, MATCHED25 beats CLOSE by
**+$134.8/day (95% CI [+$34.8, +$236.3], P ≤ 0 = 0.004)** — a genuinely significant subsample. It
does not survive because the arm has to sit out the days it cannot fill:

| slice | days | CLOSE | MATCHED25 |
|---|---:|---:|---:|
| mid-limit filled CLOSE's pick | 368 | **−$30,038** | +$19,554 |
| mid-limit never filled it | 130 | **+$46,937** | $0 (no trade) |
| all sessions | 498 | +$16,899 | +$19,554 |

The limit fills when price comes back to the level — which is what a failing trade does. **CLOSE
makes $46,937 on exactly the 130 days the mid-limit is unreachable, and loses $30,038 on the 368
where it is.** The arm's whole subsample edge is spent buying back the winners it sat out. Net over
all sessions: +$5.3/day, interval covering zero.

The mechanism inside the subsample is also not new edge but leverage. Mean risk per share falls
$0.8704 (CLOSE) → $0.7367 (MID25) → $0.6283 (MID50) → $0.5765 (MID75), so a 2R target sits closer to
a smaller R while a stop-out still books exactly −$1,000. Win rate walks straight down the sweep:
46.5% → 47.2% → 36.5% → 28.1%. This is `CLAUDE.md`'s own size-gate warning (g87's collapsing risk
denominator) in a milder form; `min_risk_floor` bounds it but does not remove it.

## 8. Does this settle the F9 / g90 conflict?

**No, and neither side should be promoted.** They are not the same statistic:

| | g90 R2 | g158 F9 |
|---|---|---|
| price | confirm bar's **midpoint** (50%) | 25/50/75% of the signal bar's range |
| window | 12 bars | to the 11:00 cutoff |
| exits | blind 2R, `LADDER_MODE=None` | shipped ladder via `run_trade` |
| signals | 925, 2024-08-12 → 2026-08-11 | 8,227 candidates, 498 sessions |
| unit | mean R per trade | $/day, one-trade-a-day |
| "reachability" | 80% of 925 traded signals hit the midpoint | 86% of 8,227 candidates hit 50% **or** 75% |

The 80% and 86% are different numerators over different denominators with a looser test; neither
refutes the other. On the closest matched comparison I can run — MATCHED50, the same trade, a limit
at 50% of the bar's own range — the all-sessions sign **agrees with g90** (mid pays less, −$28.2/day)
and the fill-conditional sign disagrees (+$111.3/day, CI [−$68.2, +$301.0], P ≤ 0 = 0.115). Every
interval covers zero.

**The vault line should not be flipped.** `Projects/omen-blockers.md`:95 and
`Projects/omen-brief-2026-09-03.md`:45 say mid-candle is dead. F9 is not evidence to reverse that;
its practical conclusion (mid-candle is not a shippable improvement over the close) is what this
refutation also lands on. What is *not* established either way is g90's specific 0.2458R magnitude,
which was measured on a different book, exit model and unit. Record the vault line as **upheld in
direction, magnitude unverified**, and F9 as **refuted**.

## 9. What survives

- Mid-candle limits are reachable on most candidates. That count is real.
- On the trades where the limit fills, a better entry is worth a lot (+$134.8/day, CI excludes zero).
- **Nothing shippable.** Over all 498 sessions the entry-price effect is +$5.3/day with an interval
  from −$95.5 to +$105.7, +0 green months, and the days the arm cannot reach are the days that pay.
- Any future version of this arm must (a) hold the day's candidate fixed, (b) be selected on H1 and
  read on H2, and (c) report the paired session bootstrap, not two unpaired totals.
