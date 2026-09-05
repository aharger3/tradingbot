# g160 refuter #2 (multiplicity + sampling error) — REFUTED on the evidence, UPHELD on the decision

**What is different now:** every number in `research/g160_tweak_grid.md` reproduces byte for byte on
this box, and its ship decision ("O2 ships nothing, defaults unchanged") is the right one — but the
evidence chain it rests on does not hold. The grid's `VETO_1D` lever, which the report singles out as
"the one lever that consistently helps", is built on `spy_trend`, a field computed from **the day's own
RTH close** and already blacklisted as lookahead in four other scripts in this repo; 8 of the 16 arms
(every `veto1d=on` row, including the named "best full-book arm") therefore carry a field that reads
past the entry bar, and their numbers change materially when the field is made causal. Separately, the
claim swaps O2's stated gate ("improved both halves") for a stricter one ("positive in both halves") —
under the spec's own wording the arm the claim names as best *does* improve both halves, and the honest
reason not to ship it is that it makes **one third the total R of the baseline** and that no difference
in the grid is distinguishable from zero.

Fill contract, unchanged from the arm under review: signal-bar CLOSE entry, `stop_rule.stop_fill_price`
stops, rows size-gated at book-build time on `signal_runner.min_risk_floor`, 1R = $1,000,
`research/omen_metrics.ev_r_scoreboard` / `first_of_day_arm`. Book
`research/bt2y_trades_retest_on.json`, 498 sessions, H1 = 249 sessions before 2025-09-01, H2 = 249 on
or after. Every number below: `python research/g160_refute2_multiplicity.py`.

## 0. Reproduction — clean

`python research/g160_tweak_grid.py` re-run on this box regenerates all 33 arms with every cell
identical to the committed `.md` and `.json`. Baseline `first_of_day_arm`: n=498, ev_r **0.034**
(H1 **+0.136** / H2 **-0.068**), **$33.9/day**, 13/25 green, win 46.4%. Best full-book arm
(`one_and_done` / 09:45 / `s_only` / `veto1d=on`): n=88, ev_r **0.064** (H1 +0.236 / H2 -0.062),
**$11.2/day**, win 51.1%, 15/23 green. The `fire_A_when_no_S_by_10` inertness at the 09:45 window is
real and correctly explained (10:00 cannot occur inside a window that ends at 09:45). The
`S_CLASSIFIER` delta is at most 3 trades per matched pair (406→405, 856→856, 569→567, 723→720), as
claimed. Nothing in the arithmetic is wrong.

## 1. LOOKAHEAD — `VETO_1D` reads the day's own close

`backtest_2y.spy_context()` sets `spy_trend = "bull" if closes[i] >= sma`, where `closes[i]` is
**day i's own RTH closing price** and the SMA window is `closes[i-19:i+1]` — it includes today. A
signal firing at 09:31–11:00 cannot know either. Vetoing puts on days SPY closed above its trend and
calls on days it closed below is, mechanically, "drop the trades that fought the day's own outcome."

This repo already knows: `research/g110_time_of_day.py:76`
`EXCLUDED_LOOKAHEAD = ("rangeb", "dret", "spy_trend", "vol_regime", "drange", "gap")`, with the same
exclusion repeated in `g114_regime_sweep.py:31`, `g114adv_2_westfall_young.py:15` and
`g114adv_4_dedup_family.py:22`. g160 discloses `spy_trend` as a *proxy* for a 1D veto; it never
discloses that the proxy is a lookahead field.

Re-running the veto with a causal field (prior day's close vs the SMA through the prior day; the two
labels disagree on **10.6%** of the 667 days — exactly the days SPY crossed its trend):

| arm | veto | n | ev_r | H1 | H2 | $/day | win% |
|---|---|---:|---:|---:|---:|---:|---:|
| one_and_done 09:45 | off | 151 | +0.006 | +0.083 | -0.061 | $2.0 | 45.7% |
| one_and_done 09:45 | **on, as shipped (lookahead)** | 88 | +0.064 | +0.236 | -0.062 | $11.2 | 51.1% |
| one_and_done 09:45 | on, causal | 82 | **+0.108** | +0.275 | -0.029 | $17.8 | 53.7% |
| first3 09:45 | off | 193 | +0.014 | +0.090 | -0.047 | $5.3 | 46.6% |
| first3 09:45 | **on, as shipped (lookahead)** | 109 | +0.057 | +0.208 | -0.054 | $12.4 | 51.4% |
| first3 09:45 | on, causal | 101 | **+0.105** | +0.239 | -0.007 | $21.4 | 54.5% |
| one_and_done 11:00 | off | 406 | -0.057 | -0.019 | -0.095 | -$46.6 | 44.1% |
| one_and_done 11:00 | **on, as shipped (lookahead)** | 333 | -0.039 | +0.024 | -0.102 | -$26.1 | 43.2% |
| one_and_done 11:00 | on, causal | 313 | **+0.001** | +0.047 | -0.043 | $0.7 | 44.7% |
| first3 11:00 | off | 856 | -0.053 | -0.033 | -0.071 | -$90.4 | 42.4% |
| first3 11:00 | **on, as shipped (lookahead)** | 569 | -0.044 | +0.024 | -0.107 | -$50.1 | 41.1% |
| first3 11:00 | on, causal | 532 | **-0.006** | +0.051 | -0.058 | -$6.2 | 43.4% |

The surprise cuts the other way: the causal veto is *better* than the contaminated one on every arm.
So the lever itself is not killed by the fix — but **every published `veto1d=on` cell in g160 is the
wrong number**, and the claim's headline arm is $11.2/day when the honest field says $17.8/day. A
result that only becomes correct after you fix it is still a result that was not correct as published.
H2 stays negative under the causal field on all four (-0.029, -0.007, -0.043, -0.058), so the ship
decision is unaffected.

## 2. LOOKAHEAD — the loss-halt consumes a result it does not have yet

`build_arm`'s `first3_loss_halt` branch reads `r["r"] < 0` on pick *k* to decide whether pick *k+1* is
allowed. Using `entry_i + bars` as the exit bar, **134 of 529 (25.3%)** follow-on picks in the
`first3` / `s_only` / full-window arm were taken while the prior pick was **still open** — its win or
loss was not knowable at that moment. All 16 `first3` rows inherit this. It does not change any
ranking (`first3` never beats `one_and_done` in a matched cell), but those eight arms are not honest
either, and the report does not flag it.

## 3. MULTIPLICITY — the gate is passed by noise 4 times out of 5

Null model: 16 arms that each pick a *random* eligible candidate per day at the winner's own fire rate
(0.18/day), scored against the baseline's halves (H1 +0.136, H2 -0.068). Over 400 simulated grids,
**318 (79.5%)** contained at least one arm beating the baseline in **both** halves.

At these fire rates a 16-arm grid has essentially no discriminating power. Two consequences:

- O2's stated gate — "improved both halves" — is worthless as written; it is a coin flip weighted
  toward "pass". The report's substitution of "positive in both halves" is stricter and, by accident,
  the more defensible test, but it is **not the gate the spec names** and the claim does not say it
  changed it.
- Under the spec's actual gate, the claim's own best arm **passes**: H1 +0.236 > +0.136 and
  H2 -0.062 > -0.068. The sentence "no arm ... so O2 has no winner" does not follow from O2's gate. The
  g160 report visibly trips over this in its own prose ("worse than the baseline's H2 of -0.068 is
  *not* actually worse (it's a smaller negative)") and then draws the conclusion anyway.

## 4. SAMPLING ERROR — paired session bootstrap, best arm vs baseline

Paired on all 498 sessions (each session contributes the arm's R and the baseline's R, 0 where no
trade), 20,000 resamples, `random.Random(7)`:

| half | R/session, arm − baseline | 95% CI | P(diff <= 0) |
|---|---:|---|---:|
| ALL | **-0.0236** | [-0.1156, +0.0683] | 0.692 |
| H1 | **-0.0985** | [-0.2370, +0.0363] | 0.920 |
| H2 | **+0.0513** | [-0.0692, +0.1714] | 0.193 |

Every interval spans zero. And the point estimate is *negative* in H1 — the opposite sign to the
ev_r comparison the report leads with. The reason is a unit switch: **ev_r is per trade, the project's
unit is per day.** The arm's ev_r of 0.064 beats the baseline's 0.034 only because it trades 88 times
instead of 498. On the one-trade-a-day unit that CLAUDE.md and this spec both name:

- total R over the same 498 sessions: **arm 5.14 R vs baseline 16.90 R**
- $/day: **$11.2 vs $33.9**

The "best arm" delivers less than a third of the baseline's R and one third of its dollars. Against
his $397/day bar, both are noise.

## 5. Two smaller defects

- **S recall = 100.0% is a tautology, not a measurement.** In 24 of the 32 rows the tier policy is
  `s_only` (or `fire_A` at a window where it is inert), so if any S candidate survives the filters the
  arm's first pick *is* an S by construction — numerator equals denominator by definition. Reading
  that column as "these arms cost no recall" is exactly backwards: the `s_only`+veto arm is live on
  **88 of 498 days**, i.e. it declines to trade on 82% of sessions.
- **The green-months denominator moves.** "15/23" vs the baseline's "13/25" is not a like-for-like
  count: the arm places no trade at all in 2024-10 and 2025-05, so two months leave the denominator
  rather than scoring red. Ratio-wise 15/23 flatters a book that made 5.14 R.

## Verdict

**REFUTED as stated; the ship decision is UPHELD and now rests on better ground.**

Refuted: the grid's headline lever is lookahead (`spy_trend` = today's close, blacklisted elsewhere in
this repo), so 8 of 16 arms publish wrong cells; the `first3` arms consume 25% of their halt decisions
before the result exists; the stated gate is not O2's gate, and under O2's actual gate the named best
arm passes; the "both halves" test over 16 arms is cleared by pure noise 79.5% of the time; and the
per-trade ev_r ranking reverses sign on the per-session unit the project actually uses.

Upheld: **O2 must still ship nothing.** No arm is positive in both halves even after the lookahead is
removed, no paired-bootstrap difference is distinguishable from zero, and the best arm makes one third
of the baseline's R. The correct one-line reason for the morning report is *"the best arm makes 5.1 R
where the baseline makes 16.9 R over the same 498 sessions, and no difference in the grid clears its
own error bar"* — not *"H2 is negative"*.

One thing worth keeping: the **causal** 1D veto (prior-day close vs prior-day SMA) is the only lever
here that survives its own de-biasing and improves every arm it touches (11:00 one_and_done goes
-$46.6/day → +$0.7/day). That is a candidate for a real measurement with a genuine daily field — it is
not a candidate for a flag default.

Scripts: `research/g160_refute2_multiplicity.py` (this file's numbers),
`research/g160_tweak_grid.py` (the arm under review). Causal field:
`research/g160_refute2_spy_causal.json`.
