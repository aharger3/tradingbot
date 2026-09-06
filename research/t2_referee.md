# T2 referee — instrument columns — **REFUTED**

Builder commit: **ccd7fa0683ef7ebf10a539228d8a4a5b8a571d64** (the T2 files actually landed
across **07c35df8** — `g213_instruments.py/.md`, `g213_verify.py`, the book — and
**ccd7fa06** — the verify md and a book rebuild; both are `wip: auto-commit` messages, so
neither names the row or the number that moved).
Referee script: `research/g213_instruments.py` was **not** imported — every figure below is
re-derived from `research/tape/instruments_2026-09-05.json.gz` and
`research/tape/baseline_2026-09-05.json.gz` by `research/t2_referee.py`, which carries its
own `stats()` and its own futures re-pricer.

Referee base: HEAD `b4491963`, `1539dd7f` is an ancestor, HEAD == `origin/main`.

**Verdict: refuted.** The arithmetic is right and the 20 real option prices are real. The
two headline readings the report invites — "futures makes money where shares does not" and
"options lose $607/day" — do not survive. One is a subset artifact, the other is 90% an
unvalidated fee assumption charged at twice the standard convention. And the futures column
cannot answer the question this row was asked to answer, because its output is structurally
insensitive to the futures mapping.

---

## What is upheld

**The published arithmetic reproduces to the cent.** My independent recompute of all nine
cells (`t2_referee.py` section A) matches `research/g213_instruments.md` exactly:

| instrument | window | $/day | mean R | win | green | n |
|---|---|---:|---:|---:|---:|---:|
| shares | whole | −52 | −0.034 | 45.0% | 11/25 | 769 |
| shares | H1 / H2 | 9 / −112 | 0.006 / −0.072 | 43.7% / 46.3% | 6/12 / 5/13 | 382 / 387 |
| futures | whole | 12 | 0.058 | 52.5% | 12/24 | 99 |
| futures | H1 / H2 | 71 / −48 | 0.375 / −0.229 | 63.8% / 42.3% | 9/12 / 3/12 | 47 / 52 |
| options | whole | −607 | −0.393 | 31.8% | 2/25 | 769 |
| options | H1 / H2 | −632 / −583 | −0.410 / −0.377 | 28.9% / 34.6% | 1/12 / 1/13 | 382 / 387 |

Fill = close (the baseline book's `entry_fill.ENTRY_FILL`), exit = the shipped 1R
stop + 30/30/30/10 ladder, unit = `up_to_3_stop_win_or_2loss` on `universe.CORE_SYMBOLS`,
denominator = all 498 sessions in the unit book (H1 248, H2 250),
script = `research/g213_instruments.py` re-derived by `research/t2_referee.py`.

**The stored option prices are real.** I re-pulled 10 of the 20 real rows straight from
Polygon myself (`t2_referee.py --polygon`, section H): **9 pass to the cent, 1 unre-checkable**
(TSLA 2024-09-05 now returns 403 — see below). One row, PLTR 2026-08-05, was priced off a bar
1 minute away from the requested clock via the ±5-minute `nearest_minute` fallback; the other
eight were exact-minute.

**`instrument_source` is honest.** Every one of the 769 rows carries it; the 2.60% real share
is a census of the field (`{'model': 749, 'real': 20}`), not an assumption.

**Contract rounding is honest, and small.** Realised 1R as a fraction of the nominal $1,000:
futures median 1.000, mean 0.9975, sd 0.0202, range 0.917–1.064, 5 of 99 rows off by more
than 5%, none by more than 20%. Options median 1.003, mean 1.0021, sd 0.0145, range
0.904–1.076, 8 of 769 off by more than 5%, none by 20%. Futures contract counts run 5 → 67,
median 21; no row is floored at 1 contract, so the rounding floor never bites. The docstring's
claim that integer sizing "makes R noisy trade to trade" is true but the noise is ±2%.

**Sample-size rule respected.** No published cell is under 30 trades or 12 months (futures
whole 99/24, H1 47/12, H2 52/12). **No mark file touched** in either commit or in the working
tree. **The verify gate is green** — I ran `regression_gate.py` (exit 0, "no baseline-fired
mark went silent"), `test_runner_stop.py` (exit 0, 70 checks) and
`test_universe_single_source.py` (exit 0, 29 symbols, no private lists) at HEAD `b4491963`,
which contains `ccd7fa06`. **One change per row** holds by content: both commits touch only
the four g213 files and the one tape book.

---

## Defect 1 — the futures column is structurally insensitive to the mapping it is built on

This is the refutation the row asked for, and it is stronger than "the basis assumption is
wrong". It is: **the basis assumption cannot matter, because the model contains no futures
information.**

`price_futures` computes `pnl = r × actual_r_dollars − commission`, where `r` is the shares
book's own R-multiple and `actual_r_dollars = contracts × risk_per_contract` with
`contracts = round(1000 / risk_per_contract)`. Integer sizing pins `actual_r_dollars` to
within ±2% of $1,000 **whatever the ratio is** — a wrong ratio scales `risk_per_contract`
and the contract count inverses it. Tick rounding, basis, dividends and roll all land inside
that same ±2%.

Measured (`t2_referee.py` section D — I re-priced all 99 rows at shocked ratios; the SPY/SPX
and QQQ/NDX ratios drift by order 1–2% over two years from dividends and carry, so ±5% and
±10% are stress rows):

| ratio shock | $/day | total | mean R | win | green |
|---:|---:|---:|---:|---:|---:|
| −10% | 11 | $5,478 | 0.0553 | 51.5% | 12/24 |
| −2% | 12 | $5,935 | 0.0599 | 52.5% | 12/24 |
| 0 (published) | 12 | $5,731 | 0.0579 | 52.5% | 12/24 |
| +2% | 12 | $5,915 | 0.0598 | 52.5% | 12/24 |
| +10% | 13 | $6,250 | 0.0631 | 52.5% | 12/24 |

**No headline cell flips at any shock.** Green months are 12/24 at every point; $/day moves
$1 across a ±10% band. So: the basis error cannot flip anything, and the report's "UNVERIFIED"
caveat is honest but beside the point. The real finding is that the futures column is
**"shares R, minus futures commission, plus ±2% of rounding noise"** — a commission haircut
wearing a futures label. It cannot tell Austin whether MES/MNQ is tradable for his setups,
because nothing about MES/MNQ reaches its output.

**The row's own spec item is missing.** T2 says "tick rounding, **day-margin** and
commission". `day-margin` appears nowhere in `g213_instruments.py` (grep: no `margin`). A
median 21 MES contracts is roughly $630k of notional and several thousand dollars of day
margin — the one number that decides whether the futures lane is fundable at all, and it is
not modelled.

## Defect 2 — the futures headline is a subset artifact, and the table invites the wrong read

The report prints "Futures $12/day" directly under "Shares −$52/day". Those are **not the
same trades**: futures is 99 SPY/QQQ rows, shares is all 769 including 670 single names.
The matched comparison (`t2_referee.py` section B, same 99 rows, same denominators):

| on the SAME 99 futures-eligible rows | $/day (all 498 days) | mean R | win | green |
|---|---:|---:|---:|---:|
| shares | **17** | **+0.086** | 55.6% | 13/24 |
| futures | **12** | **+0.058** | 52.5% | 12/24 |
| options | −50 | −0.254 | 34.7% | 5/24 |

Futures is **worse than shares on its own trades** — the $0.62/side × 21 contracts is the
whole gap. SPY and QQQ were simply the profitable corner of the book in shares too. The
report never states this and the layout reads the other way.

## Defect 3 — 90% of the options headline is one unvalidated fee, charged twice

`price_options` charges model rows `2 × $0.05 × 100 × contracts` and charges real rows
**nothing**. Measured (section E):

- model spread cost: median **$340**/trade, mean $374, total **$280,620** across 749 rows.
- model total P&L: **−$310,248**. **90% of it is the spread line.**
- real rows carrying a `spread_cost` field: **0 of 20**. Model rows: 749 of 749.

Two consequences.

**(a) The two sources are not on one ruler.** The 2.6% of rows priced from real Polygon bars
pay zero transaction cost (a 1-minute aggregate close is a traded print, neither side of a
quote); the 97.4% priced by model pay two full quoted widths. So the only rows anyone
verified are the only rows exempt from the assumption that produces the answer.

**(b) The charge is 2× the standard convention.** Crossing a $0.05-wide market from mid costs
$0.025 each way — $5 per contract round trip, not $10. Re-running the whole book at that
convention and at zero:

| options, whole window | $/day | mean R | win | green |
|---|---:|---:|---:|---:|
| as published (two full widths) | −607 | −0.393 | 31.8% | **2/25** |
| one full width (mid-to-mid crossing) | −326 | −0.211 | 37.5% | **4/25** |
| no spread | **−44** | **−0.028** | 44.5% | **11/25** |

The zero-spread row is statistically the same book as shares (−$52/day, −0.034R, 11/25). So
"options are catastrophically worse than shares" is entirely a statement about the $0.05
assumption and how many times it is charged — not a measurement. Nothing in this row
validates that assumption, and the option data that could have validated it was exempted
from it.

## Defect 4 — the stated cause of the 2.6% coverage is not what happened

`research/g213_instruments.md` says the model fallback fires "because the wall-clock fetch
cap (110 min) was reached, a contract/expiry was not listed, or Polygon returned 403/no data".
What is on disk (section G):

- **22** aggregate files cached, of **769** unit rows. So **at most 22 rows (2.9%) were ever
  attempted.** 110 minutes at the paced 5 calls/min is ~550 calls; 23 catalog pulls plus 22
  aggregate pulls is roughly 110 calls, ~22 minutes.
- **`data_archive/options/g213_progress.json` does not exist.** `stage_fetch` writes it
  unconditionally after the loop, so the documented resumable-checkpoint path has no evidence
  of having completed a run.
- Two cached files are `403`: `O:SPY240904C00552000` and `O:MSFT240906C00407500`, both on
  **2024-09-04** — the first two sessions of the book.

I probed Polygon live (section I):

| contract | day | today |
|---|---|---|
| O:SPY240904C00552000 | 2024-09-04 | **403** |
| O:MSFT240906C00407500 | 2024-09-04 | **403** |
| O:TSLA240906C00230000 | 2024-09-05 | **403** (was 200 last night — 390 bars are cached) |
| O:SPY250130C00605000 | 2025-01-30 | 200, 405 bars |

TSLA 2024-09-05 fetched fine at 22:41 last night and 403s now. That is a **rolling ~2-year
lookback** on this Options plan, and the boundary moved one day overnight. Combined with
`g213_instruments.py:341-343` — the fetch loop `break`s on the **first** 403 — one
out-of-window row in the shuffled order kills the entire pass. The 97.4% model share is a
plan limit plus a control-flow bug, not a clock. The row's spec premise ("plan confirmed:
historical option aggregates return") is only true for roughly the most recent two years, and
the two-year book starts exactly at the edge.

## Defect 5 — a "real" option row does not price the trade the shares row booked

The shares row is a 30/30/30/10 ladder with up to four exits (`backtest_week.SCALE_PLAN =
hod_then_runner_be`, `LADDER_WEIGHTS (0.3, 0.3, 0.3, 0.1)`). The option row is one entry
close → one exit close, with the exit clock set to `et + bars`, and `bars` is
`backtest_2y.py:244` `exit_idx − entry_idx`, i.e. the **last** leg's minute. So a trade that
scaled out three times at rising prices is priced as if the whole position sat until the final
exit (section F):

- **14 of the 20 real rows** are `scaled=True` in the baseline book.
- **4 of 20** flip P&L sign against the shares row.
- TSLA 2024-09-05 09:53: shares +0.272R / +$272 (scaled), option 3.92 → 3.85 × 38 = **−$266**.
- SPY 2025-01-30 09:46: shares +0.230R / +$230 (scaled), option 1.40 → 1.67 × 48 = **+$1,296**.

Over the 20 real rows the shares book totals +$4,124 and the option column totals +$7,753 —
the divergence is exit modelling, not option convexity, and the report reads it as the latter
("the same-shaped trades landing both ways").

## Defect 6 — stamp and report hygiene

- The book's stamp records `dirty_py_count: 3` at build time (`dirty_engine_py: []`, so no
  engine file). **The tree was dirty when the book was built and neither the report nor the
  builder's summary says so.** The stamp's commit `380667a6` is an ancestor of `ccd7fa06`, so
  that part is in order.
- `g213_instruments.md` says "the **15** real-bar rows **above**". There are **20**, and no
  rows appear above that sentence in the file. Its bracketing figures ("wins to +$4,895,
  losses to −$1,700") are correct.
- `g213_verify.py` sets `N_CHECK = 20` against a population of exactly 20 real rows, so "20
  sampled" is the whole population, not a sample. What it verifies is that the cached price
  equals Polygon's price — cache integrity. It cannot catch the wrong contract, the wrong exit
  clock, the ladder mismatch, or anything at all about the 749 model rows. Calling it the
  row's verify clause overstates what it covers.
- Both commits are `wip: auto-commit`. Neither names the row nor the number that moved, so
  T2 is not findable from the log.
- Minor: IWM is not in `universe.py` **at all** (one mention, not a traded symbol), so
  SPY→MES/QQQ→MNQ is the whole map; "IWM is not in CORE_SYMBOLS" understates it.

---

## What would make T2 land

1. Publish the **matched** shares-vs-futures row (same 99 trades) as the headline, and label
   the futures column what it is: shares R minus $1.24/contract, with a ±2% sizing wobble.
   Add day-margin, or drop the claim that this row prices the futures venue.
2. Charge the spread the **same way on every row** — either model both sides on the real rows
   too, or strip it from the model rows and publish the spread as a separate sensitivity
   column. Publish the −$44 / −$326 / −$607 ladder so the reader sees the fee is the result.
3. Fix the fetch loop: `continue` past a 403 instead of `break`, record the out-of-window
   boundary date, and state the honest coverage ceiling (roughly the most recent 24 months of
   the book, not 2.6%).
4. Price the option leg against the ladder — one option P&L per scale-out leg — or state on
   every real row that it is a single-exit approximation of a laddered trade.

## Referee's own numbers, named

Every figure in this page comes from `research/t2_referee.py` reading
`research/tape/instruments_2026-09-05.json.gz` (stamp: commit `380667a6`, dirty_py_count 3,
built 2026-09-05T22:41:36) and `research/tape/baseline_2026-09-05.json.gz` (book_id
`2c39ced2697c26cc`). Fill = close, exit = shipped 1R stop + 30/30/30/10 ladder, unit =
`up_to_3_stop_win_or_2loss`, universe `CORE_SYMBOLS` (11), 769 rows over 498 sessions,
2024-09-04 → 2026-09-04. Raw output: `research/t2_referee_out.txt`.
