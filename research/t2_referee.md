# T2 referee (pass 2) — instrument columns — **REFUTED**

Builder commit under review: **`c1261604`** ("T2 repair: fix spread double-count,
break-on-403, mislabeled futures-vs-shares compare, add day margin").
Base at dispatch `1539dd7f` is an ancestor of `c1261604`; `HEAD == origin/main == c1261604`.
Everything below was re-derived by `research/t2_referee.py`, which imports nothing from
`g213_instruments.py` — a bug in the builder's aggregation cannot reproduce itself here.

Run: `python research/t2_referee.py` (offline) and `python research/t2_referee.py --refetch --n 10`
(10 live Polygon calls).

This page and `research/t2_referee.py` **supersede pass 1's** at the same two paths (the
dispatcher names those paths for every pass). Pass 1's write-up and script are not deleted —
they are the committed content of **`04b6db1d`** and can be read with
`git show 04b6db1d:research/t2_referee.md`.

---

## Verdict

**Refuted.** The arithmetic is clean — every published cell reproduces to the cent under an
independent implementation, and 10 of 10 real option rows re-price live from Polygon exactly.
Two things break the row anyway:

1. **The options headline is one unmeasured constant.** 97.4% of the options column is
   `shares R × actual_r_dollars − $0.05 × 100 × contracts`. The −$274/day gap between the
   options column and the shares column is −$281.75/day of that assumed spread — **103% of
   the gap**. No quote data was pulled anywhere in this row. The report makes exactly this
   criticism of the *futures* column ("this column reads as shares R minus commission") and
   does not make it of the *options* column, which is the one carrying the row's headline.
2. **The stated reason for 2.6% real coverage is false.** The report blames "mainly (a)
   Polygon Options Basic has a rolling ~2-year lookback". Only **3 of 769 rows (0.4%)**
   predate a rolling 2-year cutoff from the build date. **Only 22 of 769 rows (2.9%) were
   ever requested from Polygon at all**; 747 were never attempted, and there is no
   `g213_progress.json` checkpoint, so `--stage fetch` never completed a run.

---

## Upheld

| check | result |
|---|---|
| every published cell reproduces | **yes**, independent implementation, to the cent |
| `instrument_source` on every row | **yes**, 769/769, 0 missing |
| real-bar share computed from the field | **yes**, 20/769 = 2.60% counted from `instrument_source` |
| 10 real option rows re-priced live from Polygon | **10 pass, 0 mismatch, 0 fetch error** |
| futures basis insensitivity | **confirmed** — ±10% ratio shock moves $/day by $1.47 total range, green months never move |
| "futures loses to shares by commission alone" | **confirmed** — $2,799 gap = $2,655 commission + $144 sizing residual + $0.38 unexplained |
| no ES/MES/NQ/MNQ bars on disk | **confirmed** — `find data_archive` returns nothing; the spec's "else stated as unverified" fallback is honoured |
| stamp | `meta.git.commit = ee2969f8`, an **ancestor** of `c1261604`; all flags, date, window, script, book_id present |
| dirty tree at build | `dirty_py_count = 2`, `dirty_engine_py = []` — **disclosed** in the report |
| sample-size rule | **respected** — no cell under 30 trades or 12 months (futures whole 99/24, H1 47/12, H2 52/12) |
| no mark file touched | **confirmed** — `git show --name-only c1261604` names only `research/g213_*` and the tape |
| one change per row | **respected** — no engine file touched; 5 files, all this row's |
| verify gate at `c1261604` | **green**, run by me: `regression_gate` 0, `test_runner_stop` 0, `test_universe_single_source` 0 |

### Reproduction, my code vs the published report

All figures: unit `up_to_3_stop_win_or_2loss` (up to 3 fired core-11 signals a day, stop after
the first win or the second loss), fill = close, exit = the shipped 1R stop / ladder, 498
sessions, script `research/t2_referee.py`.

| column | n | my $/day | report | my green | report |
|---|---:|---:|---:|---:|---:|
| shares, whole | 769 | −$51.70 | −$52 | 11/25 | 11/25 |
| shares H1 | 382 | $8.84 | $9 | 6/12 | 6/12 |
| shares H2 | 387 | −$111.75 | −$112 | 5/13 | 5/13 |
| futures, whole | 99 | $11.51 | $12 | 12/24 | 12/24 |
| futures H1 | 47 | $71.04 | $71 | 9/12 | 9/12 |
| futures H2 | 52 | −$47.54 | −$48 | 3/12 | 3/12 |
| options, whole | 769 | −$325.67 | −$326 | 4/25 | 4/25 |
| options H1 | 382 | −$302.52 | −$303 | 3/12 | 3/12 |
| options H2 | 387 | −$348.64 | −$349 | 1/13 | 1/13 |
| shares, matched to the 99 futures rows | 99 | $17.13 | $17 | 13/24 | 13/24 |

### Contract rounding — realised R vs 1.0

| column | n | min | p05 | p50 | p95 | max | mean | \|R−1\|>5% | \|R−1\|>10% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| futures | 99 | 0.9175 | 0.9540 | 1.0000 | 1.0220 | 1.0640 | 0.9975 | 5 (5.1%) | 0 |
| options | 769 | 0.9038 | 0.9794 | 1.0025 | 1.0231 | 1.0760 | 1.0021 | 8 (1.0%) | 0 |

Integer sizing is well behaved; no row ever falls to 1 contract (futures min 5, p50 21, max 67;
options min 3, p50 34, max 216). **This is also why the basis cannot matter** — see D-0.

---

## Defects

### D-0 — the basis assumption, refuted as *irrelevant* rather than wrong (the adversarial ask)

The ratios (SPY→MES 10.0, QQQ→MNQ 41.35) are rules of thumb and are genuinely wrong in the
real world: SPX/SPY drifts with dividends, NDX/QQQ has moved several percent over two years,
and the *futures* price is spot plus cost-of-carry, not the index level. **None of it can flip
a headline cell**, and the reason is structural, not lucky:

- A **multiplicative** ratio error scales entry and stop together, so `risk_pts` scales, so
  `contracts = round(1000 / risk_per_contract)` scales inversely, so `actual_r_dollars` stays
  pinned near $1,000. Only tick rounding and integer truncation survive.
- An **additive** basis (futures = index + carry) cancels *exactly*: entry − stop is a
  difference, and the carry term appears in both.

Measured, re-pricing all 99 rows myself at shocks of ±0.5/1/2/5/10%:

| ratio shock | −10% | −5% | −2% | −1% | 0 | +1% | +2% | +5% | +10% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| $/day | 10.95 | 11.42 | 11.71 | 11.78 | 11.37 | 11.51 | 11.94 | 11.70 | 12.42 |
| green months | 12/24 | 12/24 | 12/24 | 12/24 | 12/24 | 12/24 | 12/24 | 12/24 | 12/24 |

Total $/day range across ±10%: **$1.47**. Green months: never move. (My shock-0 rebuild reads
$11.37 vs the book's $11.51 — a 1.2% gap from the book storing `r` at 3 decimals; immaterial.)

The builder reached the same conclusion and says so. **Upheld — but it means the futures
column answers no question the row asked.** It is shares R minus $1.24/contract commission,
and the spec's whole futures clause (ratio, tick rounding, day margin) is decoration on it.

### D-1 — the options headline is a constant nobody measured (material)

97.4% of the column is `r × actual_r_dollars − $0.05 × 100 × contracts`. Decomposed:

| piece | total | $/day | share of the options-vs-shares gap |
|---|---:|---:|---:|
| the flat $0.05 spread on 749 model rows | −$140,310 | −$281.75 | **103%** |
| delta-sizing residual on model rows | +$234 | +$0.47 | −0.2% |
| the 20 real bars vs their own linear R | +$3,691 | +$7.41 | −2.7% |
| **options minus shares** | **−$136,440** | **−$273.98** | 100% |

Sensitivity (model rows only; the 20 real rows keep their real prices):

| assumed width | $0.00 | $0.01 | $0.02 | **$0.05** | $0.10 | $0.20 |
|---|---:|---:|---:|---:|---:|---:|
| $/day | −$43.93 | −$100.28 | −$156.62 | **−$325.67** | −$607.42 | −$1,170.91 |
| green months | 11/25 | 8/25 | 8/25 | **4/25** | 2/25 | 0/25 |

**Every penny of assumed width is $56.35/day.** No Polygon quote endpoint is called anywhere
in this row, so the width has no evidence behind it — and a flat $0.05 across SPY/QQQ ATM
(pennies wide) and META at $5.00 premium (nickels or wider) is a single number standing in for
eleven very different books. The whole reported spread between shares (−$52/day) and options
(−$326/day) is this constant.

The repair correctly halved a genuine double-count. That moved the number without making it
mean anything more.

### D-2 — the coverage explanation is false (material)

| claim in `g213_instruments.md` | what the disk says |
|---|---|
| coverage low "mainly because (a) Polygon has a rolling ~2-year lookback" | **3 of 769 rows (0.4%)** predate 2024-09-06; the book runs 2024-09-04 → 2026-09-04 |
| "(b) the fetch loop used to `break` on the FIRST 403" | 22 aggs cache files exist (20 ok, 2 × 403, both dated 2024-09-04). **747 of 769 rows were never requested.** |
| implied: a pass was made and cut short | **no `data_archive/options/g213_progress.json` exists** — `stage_fetch` writes it unconditionally at the end, so no pass ever finished |

The 20 real rows span 2024-09-05 → 2026-08-05 — a shuffled prefix, not a date cut, which is
exactly what a pass that stopped after 22 attempts looks like. The `continue` fix is right and
worth keeping; the causal story told around it is not, and it is the story used to justify not
re-running.

### D-3 — the two columns being compared carry different frictions

Futures rows are charged $0.62/side. **0 of 769 option rows carry a commission field at all.**
At $0.65/contract/side, the 28,942 option contracts in this book would cost $37,625 =
**another −$75.55/day**; at $1.00/side, −$116.23/day. The report sets the two columns beside
each other without naming the asymmetry.

### D-4 — the only evidence-priced rows are the only frictionless rows

0 of the 20 real rows carry a `spread_cost`; none carry commission. Buying at a 1-minute bar's
close print is not free, and the repair's headline fix ("one full width from mid") applies to
749 rows and not to the 20 verified ones. Referee pass 1 raised exactly this; the repair
halved the model side and left the real side at zero.

### D-5 — the file contradicts itself about the thing this repair changed

`research/g213_instruments.py:57` (module docstring) still documents the pre-repair
convention: *"minus a round-trip `$0.05 x 100 x contracts x 2` spread cost"*. The code at
`:314` charges `SPREAD * MULT * contracts` — one width. Same file, opposite statements, in the
commit whose subject line is the spread fix.

### D-6 — the options column loses more than 1R and nothing says so

**273 of 769 rows** book worse than −1.000R on `pnl / actual_r_dollars`; worst −1.916R (worst
real row −1.701R, MSFT 2024-09-06). `CLAUDE.md`'s "Max loss is −1R hard" is a shares-column
property and does not survive the sizing skin. Neither report mentions it.

### D-7 — "13/24 vs 12/24 green" is one month worth $73

Exactly one month flips sign between shares and futures on the identical 99 rows: 2025-12,
shares +$30.77 vs futures −$41.97, gap $72.74 — the month's commission. Presenting 13/24 vs
12/24 alongside $17 vs $12/day reads as durability evidence for a deterministic $5.62/day
arithmetic difference. No interval appears anywhere in the report, on any cell.

### D-8 — day margin is in the rows but the number that matters is not in the report

Per row: median day margin **$1,700**, max **$3,350**; median notional **$897,240**, max
**$1,956,902**; median 21 contracts, max 67. Against the **$2,500 funded trailing drawdown**
`CLAUDE.md` names, the median futures position in this column needs more day margin than the
whole account, before a single tick of drawdown. The report gives $50/$100 per contract and a
median notional, and stops there.

### D-9 — noted, not charged

The spec's `verify:` clause ("20 option rows hand-checked against Polygon's own aggregates")
is met, but there are exactly 20 real rows, so the check covers the entire real population and
nothing about the 97.4% that carries the number. `g213_verify.md` now says this itself (repair
item 8), so it is disclosed rather than hidden.

---

## What would close this row

One change, not eight: **run `--stage fetch` to completion** (the `continue` fix makes it
possible; ~769 rows × 2 calls at 5 calls/min is a long background pass, and the ~0.4% of rows
outside Polygon's lookback fall to the model as designed). Until the options column is mostly
real bars, or the $0.05 width is replaced by measured quotes, the −$326/day figure is a
restatement of that constant and should not appear in T3's summary as an options result.

Second, smaller: charge the same frictions on both columns, or say in one sentence that
neither column is a venue simulation.

---

*Referee: opus, told to refute. Builder commit `c1261604`. Script `research/t2_referee.py`.*
