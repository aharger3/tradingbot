# W6 — TradeZella recall, and the odds question

Two separate answers in one file, because they were dispatched together
(OMEN 6 H2 master spec §3 W6 and §5 item 1).

Every number below names the script that produced it. Both scripts are committed
alongside this file, both are read-only against the engine, neither changes a
default, and neither can fetch a bar — so neither can touch `POLYGON_API_KEY`.

| section | script | selfcheck |
|---|---|---|
| W6 recall | `research/w6_tz_recall.py` | `--selfcheck`, 5 assertions + 170 real rows |
| the odds | `research/w6_close_beyond_stop.py` | `--selfcheck`, 5 cases |

---

## 0. First: `research/corpus_tz_recall.md` is not about TradeZella

The spec says to read it first because it "may already be done or half-done". It
is neither — **it is a different file about a different thing.** The `tz` in its
name is **timezone**, not TradeZella.

What it actually establishes (T2, chat-corpus recall with UTC timestamps):

- Snowflake proof that the stored `ts` on Discord messages is naive UTC: 50 of 50
  random rows decode to within 2 s of the stored value.
- Over five trader channels (`futures-alerts`, `jdub-alerts`, `premarket-charts`,
  `scarface-alerts`, `swing-ideas`), 10,379 ticker instances → 7,319 in trader
  channels → 3,753 inside the 09:30–11:00 ET scan window → 998 ticker-days.
- The engine fires on 134 of those 998 ticker-days: **13.4% chat-corpus recall**,
  correcting a previously claimed 0.0%. Direction agrees on 36 of 48.

Useful, and unrelated. **It contributes nothing to W6 and W6 does not supersede
it.** Nothing about the TradeZella book had been done before this file.

---

## 1. The CSV was found. It was in git history, not on disk.

The spec (§5 item 2) says "The TradeZella CSV is not on this machine" and W6 is
blocked on it. That was true of the working tree and of `Desktop\`. It was not
true of the repository.

```
git log --all --diff-filter=A --name-only --pretty=format: | grep -i zella
  -> data/tradezella_trades.csv
git log --all --oneline -- data/tradezella_trades.csv
  -> ce2a98d6  "v2.8: commit loose work from v2.8 run"     (added; deleted later)
git show ce2a98d6:data/tradezella_trades.csv > data/tradezella_trades.csv
```

**350 trades, 48 TradeZella columns, restored to `data/tradezella_trades.csv` and
committed** so the next agent does not have to re-find it. Nothing in the extract
is reconstructed — every row is read from that blob by
`research/w6_tz_recall.py::parse_rows`.

### The one correction the spec needs

W6's premise is that this book is "his real executed trade journal … the only
non-hindsight record in the whole project." **The file does not say that.**

> **All 350 rows carry `Account Name = "Backtesting"`.**

This is Austin replaying the tape by hand and logging what he would have taken.
It is not a broker fill record, and it is **not** non-hindsight — he could see the
day when he logged it.

That does not make it worthless; it makes it a *different* good thing. It is
still a held-out set, because the **engine** has never been shown it and no rule
was fitted to it. And it is the only corpus in the project that carries a real
entry price, a derived stop and a realised R:R on every row. So: **reported as a
held-out engine test, not as live execution.** The project's claim to a
non-hindsight label set does not survive this file, and that should be corrected
wherever it is repeated.

### The stop is derived, and the derivation is checked

TradeZella has no stop column. It has `Trade Risk` (dollars) and `Quantity`, so
risk-per-share is `|Trade Risk| / Quantity` and

```
long   stop = Entry Price − risk_per_share
short  stop = Entry Price + risk_per_share
```

This is not assumed. A losing trade exits *at* its stop, so the derived stop must
reproduce `Exit Price` on every loss. `w6_tz_recall.py --selfcheck` asserts it:
**167 of 170 losses agree to within 2 cents** (3 disagree, 1.8%). The three are
carried, not dropped.

---

## 2. The style difference — this is the finding, not the nuisance

Austin called the TradeZella book "a much simpler omen trading style". The file
agrees, and by more than "simpler" suggests.

`research/w6_tz_recall.py --style-only`:

| | his TradeZella book | the engine's 2-year book |
|---|---:|---:|
| trades | 350 | 1,091 |
| symbols | **2** — NVDA 186, TSLA 164 | ~20 (`universe.BACKTEST_SYMBOLS`) |
| setups | **1** — "Break and Retest , One Candle Rule" on all 350 | 6+ |
| trades per traded day | 1.29 | — |
| entry window (ET) | 09:xx 215 · 10:xx 131 · 11:xx 4 | 09:30–11:00 |
| side | long 202 / short 148 | — |
| span | 2024-01-03 → 2025-01-30 | 2024-08-21 → 2026-08-21 |

It is one setup, on two tickers, roughly one trade a day. The engine is a
twenty-symbol, six-setup machine. These are not the same strategy narrowed; they
are different animals.

### And the simpler book already does the thing goal 0 is chasing

The master spec's §0 is "**raise the median R:R**". His simple book, measured on
its own `Realized RR` column (n = 349; one row has no RR):

| | his TZ book | engine 2y (`research/h1_2y_nowatch.md`, `f5ff006a`, ON WATCH off) |
|---|---:|---:|
| mean R | +0.5887 | +0.8416 |
| **median R** | **+1.4368** | **+0.4120** |
| months green | 10 / 10 traded | 24 / 25 |
| win rate | 179 / 349 = 51% | — |

**His median R is 3.5× the engine's. His mean R is lower.** Both fail the 2.0R
money gate. Different populations, different spans, so this is a statement of two
numbers side by side and not an A/B — but the direction is unambiguous and it is
exactly the question Austin asked about whether a simpler setup would do better.

The mechanism is visible in the shape of his distribution, and it is the exit:

| realised R:R | trades | share |
|---|---:|---:|
| exactly −1.00 R (stopped) | 168 | 48.1% |
| between −1 R and 0 | 2 | 0.6% |
| 0 to +1 R | **3** | **0.9%** |
| +1 to +2 R | 53 | 15.2% |
| +2 to +3 R | **116** | **33.2%** |
| +3 R and up | 7 | 2.0% |

**99% of his book is either a full stop-out or better than +1 R. Three trades out
of 349 land in the 0-to-1R dead zone.** Mean of his winners: **+2.0868 R**. He is
a binary trader — the stop, or roughly a 2R target — which is nearly `flat_2r`,
the policy the spec already records as producing median R = +2.0000 on the engine's
own book. The engine's ladder, by contrast, keeps 21.9% of the +3.8436 R mean MFE
the tape offers.

**The engine does not lose to him on setup selection. It loses on the exit**, and
his book is a worked example of the thing W2 is sweeping for.

Caveat on durability: the export covers 2024-01 … 2024-09 plus 2025-01. Oct–Dec
2024 are absent. "10/10 months green" means *every month he traded was green*, not
a 13-month unbroken run, and it should never be quoted as the latter.

---

## 3. Recall — the same convention as Test 1, imported not reinvented

`research/w6_tz_recall.py` imports `run_day` and `TOL` from
`research/t4_engine_recall`, and `entry_match`, `best_tier`, `maps_to` and
`in_universe` from `research/t70_test1_score`. There is no second definition of
"match" in this project.

- **fired** = the engine produced at least one takeable entry on that symbol-day.
- **entry match** = a fired entry landed within **±2 bars** of his own entry bar,
  bar index into `rth_candles`.

Coverage is complete: 350 of 350 rows scorable — both symbols are in the engine's
universe, every day is archived, every entry minute falls inside the session. No
gaps to discount.

### The numbers

| | value |
|---|---:|
| symbol-days in the set | 271 |
| **day-level recall — engine fired at all on his day** | **129 / 271 = 48%** |
| day-level — engine *saw* a signal, any status | **261 / 271 = 96%** |
| trade-level — engine fired that day | 173 / 350 = 49% |
| **trade-level — entry match within ±2 bars** | **37 / 350 = 11%** |
| trade-level — *signal* match within ±2 bars | 123 / 350 = 35% |
| direction agreement, on the rows that matched | 37 / 37 = **100%** |
| nearest fired entry, median \|bar gap\| | **14 bars** |

### Side by side with Test 1

| | Test 1 (100 held-out cards) | TradeZella (271 symbol-days) |
|---|---|---|
| day recall | 3 / 15 S days = **20%** | 129 / 271 = **48%** |
| entry match | 4 / 58 = **7%** | 37 / 350 = **11%** |
| false fire | 12 / 42 X days = 29% | **no denominator — see below** |

**The asymmetry is structural and must not be smoothed over.** Every TradeZella
row is a trade he took. There are no X rows, no refusals, no days he looked at and
passed. So this set measures **recall only and can never measure precision.** A
change that fires more would score better here and worse on Test 1. Read the two
together or neither.

### Three readings, in order of how much they matter

1. **Detection is not the bottleneck — the gate is.** The engine *sees* a signal
   on **96%** of his days and *takes* one on **48%**. Nearly half of his book is a
   setup the engine already found and then threw away. That is the same shape W5
   found on the 12 silent S days (8 of 12 seen and discarded, 4 never produced),
   and it is a much larger sample of it. Recall work aimed at *detection* is aimed
   at 4% of this gap.

2. **Even when it fires, it is not fifteen minutes from his entry.** Median
   \|bar gap\| to the nearest fired entry is **14 bars**; only 21% of the days it
   fired on (37 of 173) land within ±2. The engine and Austin are trading the same
   symbol on the same morning off the same level and pulling the trigger a quarter
   of an hour apart. Given §1.3's finding that back-dating the fill collapses
   `|entry − stop|` to a median 63%, a 14-bar timing gap is a *risk-unit* gap, not
   only a fill gap.

3. **When it does match, it matches completely.** Direction agrees on 37 of 37.
   The engine has no long/short confusion against his book; it has a *when*
   problem, not a *which way* problem.

Recall is flat across his own outcome — fired on 49% of his winners and 49% of his
losers — so the engine is not selectively missing his good trades. It is missing
half his book at random with respect to the result. On the days it did fire it
graded 154 A and 19 C, and **not one A+ (his S)**.

---

## 4. §5 item 1 — the odds question, answered

> Austin, about a stop resting inside the entry candle's own price range:
> **"yes, but what are the odds of this happening?"**

### The half already published

`research/p26_intrabar_ambiguity.py`:

**86.8% of traded intrabar fills (792 of 912) sit on a bar whose high/low range
also contains the trade's stop.** And 790 of those 792 are not found in the tape —
they are `signal_runner.intrabar_stop` putting the stop **on the entry bar's own
extreme** by construction. Only 23 of 912 (2.5%) have a stop clear of both wicks.

### The half he was actually asking, and it was nowhere

On 2026-08-28 Austin settled that **a close, and only a close, stops you out, and
the entry candle's own close counts** — "out on that same close." That turns the
question from an unanswerable ordering problem into an arithmetic one. The odds he
wants are:

> given that you entered mid-candle, what is the chance that same candle **closes
> against you, past your stop**, and takes you out on the bar you entered on?

`research/w6_close_beyond_stop.py` imports p26's `classify`, `load_day`,
`index_day` and `HALF_CENT` and adds only the close test, over the same
`research/bt2y_trades.json` (45,175 signals / 1,016 traded, 2024-08-21 →
2026-08-21, 500 sessions; 0 archive gaps).

## **0 of 792. 0.00%.**

| population (traded book) | n | close beyond stop | % |
|---|---:|---:|---:|
| all traded | 1,016 | 0 | 0.00% |
| intrabar fills | 912 | 0 | 0.00% |
| **+ stop inside the entry bar (p26's 792)** | **792** | **0** | **0.00%** |
| … of which stop IS the bar's own extreme | 790 | 0 | 0.00% |
| … residual: stop strictly inside the bar | 2 | 0 | 0.00% |
| traded S | 128 | 0 | 0.00% |
| all 45,175 signals | 45,175 | 0 | 0.00% |

Stated the way he asked it: **the stop sits inside the entry candle's range 86.8%
of the time, and 0% of those candles close past it.**

### Why it is zero, and why zero is not a fluke

Two independent reasons, and they cover the whole population between them.

**One — 790 of 792 are structurally impossible.** On those rows the stop *is* the
entry bar's own low (long) or high (short). A bar's close can never fall outside
its own range. The close cannot be beyond the stop; there is nowhere for it to be.
`--selfcheck` asserts this case directly.

**Two — the remaining rows are not near-misses either.** The distance from the
entry bar's close to the stop, in units of the trade's own risk, has a **minimum
of +1.0043 R across all 792 rows** (closest: MU 2026-06-17 09:46). Positive means
the close was on the good side. Not one row is within 1R of flipping. This follows
from the trigger: the fill is back-dated precisely *because* the close sits in the
top (or bottom) 25% of the bar's range, i.e. beyond the entry, so the close is
structurally on the profitable side of both the entry and the stop.

**So the entry candle never closes you out. It closes you at least 1R in profit.**

### Reconciliation with `research/p8_scratch.py` — they agree

`p8_scratch.py` instrumented **43,374 created trades** and found the entry bar's
close on the good side of both the stop and the level **every single time — zero
crossings**, concluding the branch that handles the other case is unreachable.

Different population (every *created* trade, including ones the engine then
skipped; 43,374 vs 45,175) and a wider question (the level as well as the stop),
so this is a genuine independent check rather than the same count twice.
`w6_close_beyond_stop.py` finds **0 closes strictly beyond the stop across all
45,175 classified rows** and prints `AGREE`. Two rigs, two populations, one
answer.

### What this settles

- The odds he asked about are **zero on the book as measured**, and 790 of the 792
  cases are zero by construction rather than by luck.
- p26's `intrabar_stop` class was already declared non-ambiguous by his 2026-08-28
  answer. This is the arithmetic confirming it: not merely "the order does not
  matter", but "the close is never on the wrong side in the first place".
- The ±0.0095 R narrow error bar stands. Nothing here revives ±1.5799 R.
- One honest caveat: a 1-minute bar's close is not a guarantee about what a *tick*
  did. This measures the rule as the engine and Austin have both defined it —
  closes decide — and under that rule the answer is exact.

### One row that is not zero, and it is not his trade

Over all 45,175 signals the *lenient* test (a close sitting exactly **on** the
stop, within the book's half-cent rounding band) counts **1,031 rows (2.28%)**, of
which 51 are intrabar fills. Every one is a skipped row — the
sub-cent-risk population p26 already excludes from any R average, where `entry`,
`stop` and `close` collapse into the same cent. **Zero of them are traded.** The
traded book is 0 at both the strict and the lenient reading.

---

## 5. What this changes, and what it does not

Changed:

- The TradeZella CSV is on disk and committed. §5 item 2 of the master spec is
  closed; W6 was never blocked, only mislocated.
- The project should stop describing the TradeZella book as non-hindsight live
  execution. It is a hand-logged backtest, and it is still a valid held-out
  *engine* test.
- `research/corpus_tz_recall.md` is a timezone file. The spec's W6 entry points at
  it by name and should be corrected before another agent loses an hour to it.
- The odds question has a number: **0 of 792, 0.00%**, reconciled against p8.

Not changed, deliberately:

- No engine default moved. No flag added. `research/omen6_forward.py freeze` not
  run.
- The 48% TZ day recall is **not** comparable to the 20% Test 1 S recall as a
  like-for-like — different sets, and TZ has no precision denominator. Reported
  side by side, never merged.
- The median-R comparison in §2 is two populations stated together, not an A/B.
  The A/B that would settle it is W2's sweep.

## Reproduce

```
git show ce2a98d6:data/tradezella_trades.csv > data/tradezella_trades.csv
python research/w6_tz_recall.py --selfcheck
python research/w6_tz_recall.py --style-only     # §2, seconds
python research/w6_tz_recall.py                  # §3, ~4 min (271 day replays)
python research/w6_close_beyond_stop.py --selfcheck
python research/w6_close_beyond_stop.py          # §4, ~8 min (45,175 rows)
```
