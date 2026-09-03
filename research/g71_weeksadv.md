# G7.1 / `weeksadv` — adversarial verify of the `weeks` track's **W1** claim

**Verdict: REFUTED — not on arithmetic, on inference.** Every number in the claim
reproduces digit-for-digit from `research/bt2y_trades.json` with an independent
walker. But the load-bearing sentence — *"McNemar p = 0.0034 vs P0 — a rare A/B in
this project that clears its own error bar"* — is **vacuous**: W1's green-week win is
guaranteed by construction, the test is one-sided by construction, and it fires at
p < 0.01 on a book with **zero edge**. Three of the four advertised costs are also
mis-attributed: they belong to the P0→P0seq concurrency change, not to the weekly stop.

Scripts: `research/g71_weeksadv_w1.py`, `research/g71_weeksadv_attrib.py`.

## 1. Reproduction — all clean

Independent re-implementation (does not import `g71_firsts_policy`, does not read
`_g71_weeks.json`), on `research/bt2y_trades.json` (meta `generated 2026-08-29T03:14:29,
signals 76019, traded 2437, halted 857`):

| arm | n | t/wk | green | totalR | worstR | medR | recov | $/wk | mo |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 shipped | 2437 | 23.21 | 91/105 | +1339.09 | −7.66 | 11.08 | 0.69 | $12,753 | 25/25 |
| **P0seq** (the real control) | 1865 | 17.76 | **93/105** | +930.20 | **−9.69** | 6.59 | 1.47 | $8,859 | **24/25** |
| **W1** | 319 | 3.04 | **102/105** | +184.47 | −9.69 | 1.47 | 6.62 | $1,757 | 24/25 |
| W2-8 | 304 | 2.90 | 101/105 | +177.05 | −8.45 | 1.47 | 5.76 | $1,686 | 23/25 |
| W2-5 | 264 | 2.51 | 98/105 | +156.98 | −5.45 | 1.44 | 3.79 | $1,495 | 20/25 |
| W2-3 | 209 | 1.99 | 89/105 | +127.23 | −3.44 | 1.23 | 2.81 | $1,212 | 20/25 |

McNemar `P0 vs W1` = a_only 1 / b_only 12 / p = **0.00342**. Matches
`research/_g71_weeks.json::paired_weekly_mcnemar` exactly.

**Book identity: fine.** 2,437 is the current post-T23 book (`145d564e`); the 2,595 figure
in `DIRECTION.md:20,27` is the superseded post-T0 book and no 2,595-row book exists on disk.
**Look-ahead: none.** `walk_week` (`research/g71_weeks.py:203-232`) evaluates
`decide` before each candidate on `cum` that contains only trades whose `xkey` precedes
the next `ekey`, so no unclosed R enters the decision. **Branch reachable:** trivially —
319 trades, 102 stops.

## 2. Why the p-value is vacuous

**W1 green ⟺ the P0seq week path ever touches >0.** W1 takes exactly the P0seq sequence
and truncates it at the first positive cumulative. Measured: weeks whose P0seq running
path ever goes >0 = **102**; W1 green weeks = **102**. Identical. W1 is a *re-description*
of the P0seq path, not a different selection of trades.

Therefore **W1 ⊇ P0seq on green weeks by construction**: any week P0seq ends green must
have been positive at its last trade, so W1 also stopped green. Measured: weeks P0seq
green and W1 not = **0**. McNemar `P0seq vs W1` = **a_only 0 / b_only 9 / p = 0.00391** —
`a_only` is structurally pinned at zero. A test whose discordance can only point one way
has no null distribution, and Holm-adjusting it (as `g71_weeksverify.md §3a` does, 0.00342
→ 0.041) does not repair that.

**The null test.** Same schedule, same overlap keys, same weeks, every trade's R replaced
by a demeaned bootstrap draw (**zero edge**, `g71_weeksadv_w1.py`, 500 draws):

| | P0seq | W1 |
|---|---:|---:|
| green weeks, median [p05,p95] | 49 [41, 57] | **85 [80, 92]** |
| total R, median | +4.30 | +2.48 |
| McNemar p < 0.01 | — | **500 / 500 draws** |
| `a_only` (P0seq wins) over all 500 draws | — | **0, always** |

**On a book with no edge whatsoever, W1 "significantly beats" the control at p < 0.01 in
100% of draws.** The 0.0034 measures the stopping rule, not the market.

**Second null, W1 against itself.** Shuffling W1's *own* 319 realised R values across its
own week slots (counts held) gives green weeks **median 63 [57, 69]**; observed 102. The
39-week gap is path-dependent optional stopping, nothing else.

## 3. Three of the four costs are mis-attributed

The claim charges W1 with costs that the concurrency change already causes. Correct control
is **P0seq**, not P0 (P0 is concurrent + R31 on; W1 is sequential + R31 off — two changes at once):

| advertised cost | vs P0 (claim) | vs P0seq (correct) | verdict |
|---|---|---|---|
| worst week worse | −$9,694 vs −$7,657 | **−$9,694 vs −$9,694, same week 2025-W36** | **wrong** — the tail is a concurrency artefact; W1 ≡ P0seq in any week that never goes green, so W1 *cannot* move the worst week |
| months green 25/25 → 24/25 | 25 → 24 | **24 → 24, same month 2025-09** | **wrong** — the lost month is P0seq's, not the weekly stop's |
| worst/median 0.69 → 6.62 | 0.69 → 6.62 | **1.47 → 6.62** | overstated; and the move is division by a 1.47R median (3.04 trades/wk), not a fatter tail — the numerator is unchanged |
| income −86% ($12,753 → $1,757) | −86% | **−80% ($8,859 → $1,757)**; totalR 930 → 184 | direction right, magnitude vs the wrong baseline |

W1's per-trade edge is *not* degraded: mean R **0.5783** (n=319) vs P0seq **0.4988** (n=1,865).
It simply takes 5.8× fewer trades.

## 4. Two smaller falsehoods in the claim as worded

- **"The only arm that buys green weeks."** False by the track's own table: **W2-8** reaches
  101/105 at p = 0.013 vs P0 (0.021 vs P0seq), W2-5 98/105. The claim's own evidence line
  lists them.
- **"A 100% weekly gate would select exactly this shape."** W1 is 102/105 = 97.1%, not 100%.
  A 100% gate selects nothing in the table except the look-ahead ORACLE.

## 5. What survives

The *descriptive* facts survive and should be kept: W1 = 319 trades, 3.04/wk, 102/105 green
weeks, worst week −9.69R, median week +1.47R, +184.47R total, $1,757/wk, 24/25 months.
What does not survive is calling it a validated edge. It is an optional-stopping artefact
that trades 86% of the income for a metric it satisfies by definition, and it leaves the
tail exactly where it found it.

**Do not put W1 in front of Austin as "the one A/B that cleared its error bar."**
