# g202 -- P3 refuter #2 (multiplicity and sampling error): REFUTED

**One sentence:** P3's Trade The Pool result is one start date per row, not eight independent
findings -- re-run from every start date with each plan's own evaluation clock enforced, the
pass rate is **5.7%-32.9%, not 0%**, and the "daily loss limit" mechanism it names is an
artifact of a share-sizing cap that P3 silently dropped; the personal-$10k number reproduces
arithmetically but its 95% bootstrap interval spans zero, **one session is 34% of the entire
total**, and its whole edge is in H1.

**Verdict: REFUTED** (same failure class as P1's `window = min(252, n)` bug, which the morning
report flagged as the reason P3 should be treated as unrefereed).

Fill, unchanged from P3: signal bar CLOSE entry, `stop_rule.stop_fill_price()` stops, size-gated
on `signal_runner.min_risk_floor`, 1R = $1,000 on the personal arm, book
`research/bt2y_trades_retest_on.json` (RETEST_REQUIRED=1), one-trade-a-day unit = g116
`build_arm(keep=lambda r: True)` (A_base, `omen_metrics.first_of_day_arm` semantics), n=495
sessions 2024-09-03..2026-09-02, H1 n=248 / H2 n=247 split at 2025-09-01.
Script: `research/g202_p3_refute2.py` -> `research/g202_p3_refute2.json`. Bootstrap seed 20260905,
10,000 draws.

**Reproduction first.** Every P3 cell reproduces exactly before it is attacked: 4 MAX rows
FAIL(`daily_loss_limit`), 4 FLEX rows FAIL(`trailing_drawdown`), personal $17,601 / $1,760 total
and $21,577 max drawdown. Nothing below is a failure to reproduce.

---

## Attack A -- "never passes on any of 8 rows" is n=1 per row

`g173_shares_personal_refresh.py` calls `pass_day_series(series, ...)` on the **whole book from
day 0**. That replays prefixes of one trajectory: every row is evaluated from **exactly one start
date**. Eight rows are not eight samples -- they are one candidate stream priced eight ways, and
they fail in the first 0-1.2 months, so the verdict is decided by the same handful of early
sessions in all eight.

Re-run from **every** tradable start (495 starts), with each plan's own `max_days` enforced as a
real calendar clock -- which P3's own Caveat says it does **not** enforce, so this is the
*stricter* test, not a looser one:

| firm/plan | P3's answer (1 start) | all-starts pass rate, P3's sizing | all-starts, sizing cap restored (Attack B) |
|---|---|---:|---:|
| TTP 25K MAX day | never passes | **13.54%** (67/495) | **23.03%** (114/495) |
| TTP 50K MAX day | never passes | **10.51%** (52/495) | **19.39%** (96/495) |
| TTP 100K MAX day | never passes | **13.74%** (68/495) | **21.62%** (107/495) |
| TTP 200K MAX day | never passes | **7.27%** (36/495) | **5.66%** (28/495) |
| TTP 25K FLEX day | never passes | **23.23%** (115/495) | **29.09%** (144/495) |
| TTP 50K FLEX day | never passes | **30.30%** (150/495) | **32.93%** (163/495) |
| TTP 100K FLEX day | never passes | **29.09%** (144/495) | **29.49%** (146/495) |
| TTP 200K FLEX day | never passes | **16.16%** (80/495) | **16.16%** (80/495) |

**"Never passes" is false as written.** It is true of the one start date P3 measured. This is the
identical correction the swarm already applied to P1: a single-window statistic reported as a
universal one.

---

## Attack B -- the fail reason P3 names was manufactured by a dropped cap

`g173.pool_series_for_account()` calls

```python
shares = shares_for(r["entry"], r["stop"], account=account)
```

with **no `daily_loss_limit_pct`**. `g120_prop_arms.pool_series()` -- the function P3's own
docstring says its "TTP shares mechanics ... are unchanged from" -- passes it, under a comment
labelled `ADVERSARIAL FIX #2`: cap the share count so one trade's max loss cannot exceed the
firm's own daily loss limit, because *"a real Trade The Pool account could not have taken those
position sizes in the first place."* P3 dropped that fix while claiming to inherit it.

How much it matters, and what it does to the verdict:

| firm/plan | trades sized above the row's own daily loss limit | mean risk/trade, P3 | mean risk/trade, capped | P3 fail reason | fail reason with the cap restored |
|---|---:|---:|---:|---|---|
| TTP 25K MAX day | **305 / 495** | $372 | $227 | `daily_loss_limit` | **`trailing_drawdown`** |
| TTP 50K MAX day | **243 / 495** | $611 | $412 | `daily_loss_limit` | **`trailing_drawdown`** |
| TTP 100K MAX day | **126 / 495** | $800 | $631 | `daily_loss_limit` | **`trailing_drawdown`** |
| TTP 200K MAX day | 38 / 495 | $867 | $788 | `daily_loss_limit` | **`trailing_drawdown`** |
| TTP 25K FLEX day | 114 / 495 | $372 | $328 | `trailing_drawdown` | `trailing_drawdown` |
| TTP 50K FLEX day | 78 / 495 | $611 | $558 | `trailing_drawdown` | `trailing_drawdown` |
| TTP 100K FLEX day | 25 / 495 | $800 | $758 | `trailing_drawdown` | `trailing_drawdown` |
| TTP 200K FLEX day | 7 / 495 | $867 | $855 | `trailing_drawdown` | `trailing_drawdown` |

On the 25K MAX row **62% of all trades are sized larger than the firm's daily loss limit allows**,
and the arm is then failed for breaching that limit. The claim's stated mechanism -- *"daily loss
limit breached"* -- is **circular on 4 of 8 rows**. Restoring the cap also lifts the all-starts
pass rate on 7 of 8 rows (table in Attack A).

---

## Attack C -- "net -$97 to -$1,100" carries no information

On a FAIL, `ttp_row_result()` sets `net_after_cost = -fee` unconditionally. The reported range is
therefore **exactly the fee schedule** -- 97 / 230 / 435 / 1100, twice -- and is identical in the
full-book, H1 and H2 tables for that reason. It is not a measured loss; it is the entry ticket
re-printed. It should not be quoted as an outcome.

---

## Attack D -- the personal-$10k number is not distinguishable from zero

Paired bootstrap over sessions (resample the 495 sessions with replacement; the same resampled
set drives both sizings so they stay paired), 10,000 draws:

| slice | sizing | $/day (P3's number) | 95% CI | P($/day <= 0) |
|---|---|---:|---:|---:|
| full | $1,000/trade | **$35.56** | **[-$60.91, +$129.97]** | **23.3%** |
| full | $100/trade (1%) | **$3.56** | **[-$6.09, +$13.00]** | **23.3%** |
| H1 | $1,000/trade | $140.29 | [-$1.92, +$293.38] | 2.8% |
| H2 | $1,000/trade | **-$69.60** | [-$184.66, +$52.49] | **87.8%** |

Both headline figures reproduce to the cent and **neither is separable from zero**. The
one-in-four chance the true rate is negative is on the same book that P3 used to state it as a
fact.

**One session is a third of the whole result.** Leave-one-day-out on the $1,000 arm:

| slice | dominant session | its share of the total | $/day with it | $/day without it |
|---|---|---:|---:|---:|
| full | **2024-09-06 MU** | **34.09%** | $35.56 | **$23.48** |
| H1 | 2024-09-06 MU | 17.24% | $140.29 | $116.57 |
| H2 | 2025-09-04 NFLX | 5.82% | -$69.60 | -$65.82 |

2024-09-06 is the **fourth session in the book**. It is also inside the window that decides all
eight TTP verdicts in Attack A.

**And the whole edge is in the half that is already spent.** $35.56/day full-book = +$140.29/day
H1 and **-$69.60/day H2**. P3 does print the H1/H2 personal totals, but the funding-ladder row it
feeds (`research/g174_funding_ladder.md`, morning report section 3, rung 4) quotes the full-book
$35.56/day as the operable rate. There is no held-out half here: the book's last twelve months
lose money.

**The 216%-drawdown headline is peak-relative and order-dependent.** $21,577 is measured off a
peak of ~$25.4k that the account had to reach first; `g120.personal_arm_result()` carries an
explicit caveat and the fields to see it, and P3's markdown dropped both:

| sizing | max DD (P3's number) | min equity **ever** | on |
|---|---:|---:|---|
| $1,000/trade | $21,577 (215.8% of a $10k account) | **$3,820 (38.2%)** | 2025-01-27 |
| $100/trade | $2,158 (21.6%) | $9,382 (93.8%) | 2025-01-27 |

A $10,000 account cannot lose $21,577; the number is only reachable because this particular
trade *order* front-loaded the wins. Reordering the same trades changes it without changing a
single P&L.

---

## Multiplicity bookkeeping

- **8 TTP rows are not 8 tests.** One candidate stream, one start date, eight price scalings of
  the same 495 R-multiples. The eight verdicts are near-perfectly correlated; the report presents
  them as eight confirmations.
- **The all-starts rates in Attack A are themselves a 495-start search per row** and should be
  read as "how often a start date works", not as evidence any particular start will. They refute
  "never", they do not establish "fundable".
- **H1/H2 were reported, not used as select/validate.** P3 picks nothing, so no half is burned by
  selection -- but the ladder that consumes it quotes the full-book figure, which is H1's.

---

## What survives, and what has to be restated

| P3 statement | verdict |
|---|---|
| "Trade The Pool never passes on any of 8 account/plan rows" | **REFUTED.** True of one start date. All-starts, clock enforced: 5.7%-32.9% |
| "daily loss limit breached inside 0-1.2 months" | **REFUTED on the 4 MAX rows.** The limit was not enforced at sizing time; 305/495 trades oversized on 25K MAX. With g120's cap the reason is `trailing_drawdown` |
| "net -$97 to -$1,100" | **vacuous.** Identically the eval fee schedule on any FAIL |
| "personal $10k at 1% risk pays $3.56/day" | **not separable from zero.** CI95 [-$6.09, +$13.00], P(<=0) = 23.3% |
| "$1,000/trade pays $35.56/day" | **not separable from zero**, 34% of it is one session (2024-09-06 MU), and H2 is **-$69.60/day** |
| "$21,577 drawdown, 216% of account" | reproduces, but peak-relative and order-dependent; min equity ever is $3,820 (38.2%) |
| **rung 2 is not fundable** | **UPHELD, on different grounds.** A 5.7-32.9% start-date pass rate against a $97-$1,100 fee, on a stream whose last twelve months are negative, is still not a funding plan -- but the reason is "the pass is a coin toss you mostly lose and the funded account then bleeds", not "it never passes" |

**Direction of the correction, stated plainly:** as with P1, this refutation makes the arm look
*better* than P3 said and it still fails. The conclusion in the morning report's section 3 stands;
its sentence does not.
