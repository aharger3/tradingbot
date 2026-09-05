# g201 refute #1 — F9's mid-candle $100/day is 73% leakage. REFUTED.

**What is different now:** F9's MID25 arm reproduces to the dollar, but $73 of its $100/day
comes from two look-aheads — a fill bar the harness never manages (so a stop price already
touched is ignored) and a one-trade-a-day pick that rolls forward to a later candidate because
the earlier one's limit turned out never to fill — and once both are removed MID25 pays
**$27/day against the shipped CLOSE's $34**, with a paired 95% interval of [−$112, +$95].
**g90's 2026-09-03 R2 ruling stands; F9's headline does not.**

Scripts: `research/g201_refute1_check.py` (all arms, `research/g201_refute1_check.json`) and
`research/g201_refute1_handcheck.py` (raw-candle walk of the fill-bar leak). Same book
(`research/bt2y_trades_retest_on.json`, 498 sessions), same 8,227-row universe, same
`omen_metrics`-style first-of-day unit, same `signal_runner.min_risk_floor` gate, 1R = $1,000,
stops through the shipped `backtest_week._ladder_bar` / `stop_rule`. Entry fills named per row.

---

## 1. It reproduces exactly — this is not a rerun failure

| arm | g158 published $/day | g201 recomputed $/day | H1 | H2 | green |
|---|---:|---:|---:|---:|---:|
| CLOSE (signal-bar close) | $34 | **$34** | $136 | −$68 | 13/25 |
| MID25 | $100 | **$100** | $164 | $35 | 16/25 |
| MID50 | $90 | **$90** | $180 | $1 | 15/25 |
| MID75 | −$47 | **−$47** | $22 | −$116 | 8/25 |

The categorisation reproduces too (578 / 514 / 7,096). Everything below attacks the *meaning*,
not the arithmetic.

## 2. The attack that FAILED — the harness is not the story

g158's CLOSE row is the book's own `pnl` field (`backtest_2y` / `simulate_day`); its MID rows
come from `g80_ordertype_grid.run_trade`. Two different exit engines, never controlled — the
same shape that killed `stop-placement-routed` last night. So I re-priced CLOSE through
`run_trade` at `fill_i = entry_i`, `entry_px = r["entry"]`:

| control | $/day | H1 | H2 |
|---|---:|---:|---:|
| CLOSE, book pnl (g158's row) | $34 | $136 | −$68 |
| **CLOSE_RT, same harness as the MID arms** | **$37** | $140 | −$65 |

$3/day apart. **The comparison is like-for-like.** This arm of the attack is dismissed.

## 3. LEAK 1 — the fill bar is never managed, so a stop already touched is free

`run_trade` manages bars `fill_i+1 … EOD`. g158 passes `j`, the bar the limit filled on, as
`fill_i`. So **the bar the trade entered on is never managed at all.** That is harmless for a
close entry (nothing happens after the close of its own bar) and fatal for a resting limit
(the fill happens mid-bar and the rest of the bar is thrown away).

The shipped rules make it concrete. `DISASTER_STOP` is a resting order at exactly
1R = `entry − risk` filling on an intrabar **touch** (`backtest_week._disaster_hit` →
`stop_rule.disaster_stop_hit`), and for a non-collapsed MID row that price *is* the structural
stop. For a long, the limit at `close − 0.25 × range` can only fill on the way down, so if the
fill bar's low is at or below the stop, the low is reached at or after the fill — the disaster
order was touched, always.

**944 of 7,609 MID25 fills (12.4%) are in exactly that state.** g158 books them at −$568,986;
the shipped rule books them at −$944,000.

Raw-candle example from `g201_refute1_handcheck.py` (NVDA 2024-09-04, call, signal bar 37):

```
limit 106.7500  fill 106.7500  stop / disaster 106.3000
fill bar (i=45)  O 107.8400  H 108.1800  L 106.0100  C 107.8400
g158 books: WIN  +$4,317
```

Price fills the limit at 106.75, trades to 106.01 — **29 cents through the disaster order** —
and g158 pays it $4,317 because bar 45 is unmanaged.

| arm | g158 | forcing those picks to the shipped −1R | H2 |
|---|---:|---:|---:|
| MID25 | $100 | **$62** | $35 → $2 |
| MID50 | $90 | $74 | $1 → −$17 |
| MID75 | −$47 | −$184 | −$116 → −$277 |

**Cost of leak 1 on MID25: −$38/day.** (The related `intrabar_stop` collapse the repo already
flags is *not* MID25's problem — only 4 of 7,609 rows collapse. It is MID75's: 846 rows, and
dropping them lifts MID75 from −$47 to +$5.)

## 4. LEAK 2 — the day's pick is chosen with 11:00 information

`oneaday_for` walks a day's candidates in signal-time order and takes the first one that **has
a priced result**. A MID candidate has no priced result precisely when its limit never filled —
a fact not knowable until the 11:00 cutoff. So on those days the arm quietly moves on to a
later candidate. In real time you have a resting order out on candidate #1 and no way to know
it will die.

**On 34 of 498 sessions the day's first sizeable candidate never filled and g158 rolled
forward.** Requiring the day to be spent on its first candidate (no fill ⇒ no trade):

| arm | g158 | NOSKIP | H1 | H2 | green |
|---|---:|---:|---:|---:|---:|
| MID25 | $100 | **$65** | $161 | **−$31** | 13/25 |
| MID50 | $90 | $19 | $123 | −$85 | 12/25 |
| MID75 | −$47 | −$69 | −$13 | −$126 | 8/25 |

**Cost of leak 2 on MID25: −$35/day, and it flips H2 negative.**

## 5. Both corrections together — the claim is gone

| arm | $/day | H1 | H2 | mean R | win | green | paired vs CLOSE (95%) |
|---|---:|---:|---:|---:|---:|---:|---|
| **CLOSE (shipped)** | **$34** | $136 | −$68 | +0.034 | 46.5% | 13/25 | — |
| MID25 as published | $100 | $164 | $35 | +0.100 | 47.2% | 16/25 | +$65.8 [−$44, +$177] |
| MID25 fill-bar fixed | $62 | $122 | $2 | +0.062 | 45.8% | 15/25 | +$27.9 [−$80, +$131] |
| MID25 selection fixed | $65 | $161 | −$31 | +0.071 | 45.8% | 13/25 | +$31.1 [−$78, +$139] |
| **MID25 both fixed** | **$27** | $118 | **−$64** | +0.030 | 44.3% | **12/25** | **−$6.8 [−$112, +$95]** |
| MID50 both fixed | $3 | $109 | −$103 | +0.004 | 33.6% | 12/25 | −$31.2 [−$172, +$112] |

Corrected MID25 is **below** the shipped close, below it in H2, and one green month worse.
5,000-resample paired day-level bootstrap, whole sessions, seed 20260905.

**And the headline was never separable from noise in the first place:** even uncorrected, the
paired MID25−CLOSE interval is [−$44, +$177]. F9 published a point estimate whose own error bar
covers "worse than shipped".

## 6. So which of g90 and g158 was wrong — and were they even in conflict?

Two different questions were being answered, and only one of them conflicts.

**Reachability: no conflict at all.** g90 said the bar's midpoint never returns for ~20% of
signals *within 12 bars*. g158 said 86% are mid-fillable *by the 11:00 cutoff* — a much longer
clock. On this book, 1,092 of 8,227 (13.3%) never touch the 50% checkpoint by 11:00. Same fact,
different window. g158's categorisation table survives intact; it just does not license the
money claim stacked on top of it.

**Money: real conflict, and g90 wins.** g90's paired finding was that the midpoint arm pays
0.2458R *less* than the close on the signals where both fill. g158's MID50 — the comparable arm —
pays $3/day against the close's $34 once the two leaks are removed, a paired −$31.2/day. Same
sign, same story. **g90's R2 ruling stands unamended.**

## 7. What I could not knock down

Under leak 1 alone, MID25 still reads $62/day against CLOSE's $34–$37. Leak 1 is a mechanical
bug and not arguable; leak 2 is a modelling judgement — a trader who can hold two resting
orders at once could in principle keep candidate #1's limit alive *and* take candidate #2, in
which case some of that $35 is recoverable. It is not recoverable under the one-trade-a-day unit
THE LAW names, which is the unit F9 reported in. Anyone who wants to rescue this arm has to
re-run it as a multi-order arm with an explicit cancel time, and fix the fill-bar management
first.

**Verdict: REFUTED.** Do not quote $100/day, and do not quote "MID25 beats CLOSE".

---

# Second independent pass (same row, different agent, 2026-09-05 ~06:00)

**Same verdict, reached without reading the above until after the numbers were in: REFUTED.**
This pass built its own harness (`research/g201_refute1.py`, data `research/g201_refute1.json`)
over the same book, same 8,227 candidates, same size gate, 1R = $1,000. It confirms sections 2,
4 and 6 independently, tightens the selection-leak number, adds a fill-price census, and finds one
arithmetic error in F9's published table. It does **not** re-derive section 3's fill-bar leak —
that finding is the other pass's, and this pass had wrongly assumed the unmanaged fill bar was
symmetric between arms. It is not; section 3 stands and is the stronger of the two mechanical
attacks.

## A. Harness control — confirmed, and it exonerates F9 here

Independently re-derived: CLOSE routed through the identical `g80.run_trade` at
`fill_i = entry_i`, `entry_px = r["entry"]` pays **$37/day** against the book's own **$34**.
Same $3 as section 2. The two-exit-engine confound is real but is not the story.

## B. The selection leak is bigger than section 4 measured

Section 4 counted 34 sessions where the day's first sizeable candidate never filled. Scoring
every arm on the **same** candidate — the day's first *close*-sizeable candidate, so the arms are
answering for one identical trade — the pick diverges far more often, because F9's picker also
rolls forward on `filled_on_last_bar` and `risk_collapsed`:

| arm | sessions where F9's picker took a different candidate than CLOSE |
|---|---:|
| MID25 | **129 of 498** (26%) |
| MID50 | 268 of 498 |
| MID75 | 333 of 498 |

Forcing the identical pick, unfilled day books $0:

| arm | F9's picker | **matched pick** | H1 | **H2** | mean R | trades | green |
|---|---:|---:|---:|---:|---:|---:|---:|
| CLOSE_RT (control) | $37 | $37 | $140 | −$65 | +0.037 | 498 | 12/25 |
| **MID25** | $100 | **$39** | $146 | **−$68** | +0.053 | 368 | 13/25 |
| MID50 | $90 | $6 | $80 | −$68 | +0.013 | 222 | 12/25 |
| MID75 | −$47 | −$8 | $35 | −$50 | −0.034 | 116 | 10/25 |

**+$66/day becomes +$2/day on the selection leak alone**, and MID25's H2 goes from +$35 to
−$68 — the exact −$68 the shipped CLOSE arm books. The one credential that made MID25 look like
a live edge rather than an H1 artifact is entirely the picker. Matched MID25 also trades on only
368 of 498 sessions: **130 days (26%) end with a resting order that never filled and no trade at
all** — g90's reachability objection, measured on the shipped ladder instead of a blind 2R exit.

## C. Fill-price census — penny-exact and sub-cent fills exist but are not load-bearing

`g80.limit_touch` fills on `low <= lvl + EPS`, `EPS = $0.005`. So a bar whose low never reached a
buy limit can still fill, and a bar that kisses the limit to the penny and turns fills in full —
the class that killed `scale-before-the-level` in the morning report.

| arm | fills | traded a full cent through | touched to the penny, no further | **never reached the limit (EPS only)** |
|---|---:|---:|---:|---:|
| MID25 | 7,610 | 6,853 | 489 | **268** |
| MID50 | 7,096 | 6,228 | 606 | 262 |
| MID75 | 6,539 | 5,693 | 538 | 308 |

Requiring a full cent through the limit moves matched MID25 to $36/day (H1 $182, H2 −$110). Real,
but it is not what produced the $100.

## D. One arithmetic error in F9's published table

F9's category table reports `ALL` never-returns = **578**, but its own H1 (286) + H2 (331) =
**617**, and 578 + 514 + 7,096 = 8,188 against 8,227 candidates. `cat_counts["ALL"]` is not
incremented in the `if rng <= 0 or i + 1 >= min(cutoff, len(bars) - 1)` branch of
`g158_mid_candle_arms.py`, so 39 rows are missing from that row only. The 86% mid-fillable figure
(7,096 of 8,227) itself reproduces exactly, as section 1 says.

## E. Where the two passes disagree, and why it does not matter

Conditioning on the same candidate filling in both arms, this pass measures F9's MID25 paying
**+0.1218R MORE** than CLOSE_RT (95% CI [+0.0923, +0.1503], n = 4,733) — the opposite sign to
g90's −0.2458R. That is not a contradiction of g90: F9 rests at a fraction of the bar's range
measured back from the **close**, g90 rests at the **midpoint of the bar's range**; different
exits (shipped ladder vs blind 2R), different books, different windows. Section 3's fill-bar leak
also inflates exactly this statistic, since it is computed on F9's own unfixed rows. Whichever way
that paired number lands, it is conditioned on a fill you cannot know you will get, and the unit
that pays — one trade a day — says **$39 against $37**, or **$27 against $34** with both
mechanical leaks fixed. Two independent harnesses, same conclusion.

**Verdict, second pass: REFUTED.** The vault lines in `Projects/omen-blockers.md` (line 95) and
`Projects/omen-brief-2026-09-03.md` (line 45) — *"mid-candle … never happens for ~20% of signals
… R2 mid-candle entry: Dead"* — should be closed as **correct again**, with a pointer to this row
for the shipped-ladder measurement.

Nothing shipped. `signal_runner.py`, `entry_fill.py`, `g80_ordertype_grid.py` and
`g158_mid_candle_arms.py` were read, never edited. No mark corpus was touched.
