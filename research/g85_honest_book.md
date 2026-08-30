# The two-year book, rebuilt on a fill he can actually pay

**2026-08-30.** `research/bt2y_trades.json` — the canonical book, the one 40+ scripts read —
has been rebuilt with the entry filled at **the signal minute's close** instead of at the
level. The old book is preserved, unchanged, at `research/bt2y_trades_published_fill.json`.

**The headline, in dollars: taking one trade a day, the book makes $28 a day. His bar is $397.
That is 7% of it, and it is short by $369 a day.** Taking every signal the engine fires, it
**loses $283 a day**. And the gate OMEN was passing — every month green — **fails**: 11 of 25
months one-a-day, 8 of 25 taking everything.

The old figure was $721 a day, 25 of 25 green. **The difference is entirely the price paid to
get in.** Trade count barely moved (4,508 → 4,329, −4%); the per-trade result went **+$584 →
−$33**.

---

## The whole table

Two years, 500 sessions, 28 symbols, 1R = $1,000, same detection and same exits in every row.
Only the price paid to enter changes. Bands are 95%, bootstrapped over **days**, not trades.

### One trade a day — his stated rule

| fill | trades | win | mean R | **$ / day** | 95% band | % of $397 | short by | risk/trade that reaches $397 | months green | weeks green | worst drawdown |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| **close — the new default** | 500 | 45.5% | +0.028R | **$28** | −$73 to $130 | **7%** | $369 | $14,179 | **11 / 25** | 49 / 105 | $25,570 |
| next open | 500 | 47.5% | +0.086R | **$86** | −$43 to $229 | 22% | $311 | $4,616 | 13 / 25 | 51 / 105 | $14,842 |
| chase once | 500 | 39.3% | −0.016R | **−$16** | −$119 to $88 | 0% | $413 | never | 11 / 25 | 41 / 105 | $27,988 |
| *published fill — **NOT OBTAINABLE*** | *499* | *66.7%* | *+0.722R* | ***$721*** | *$571 to $867* | *182%* | *at the bar* | *$551* | *25 / 25* | *87 / 105* | *$5,993* |

### Taking every signal

| fill | trades | win | mean R | **$ / day** | 95% band | % of $397 | short by | months green | weeks green | worst drawdown |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| **close — the new default** | 4,329 | 44.3% | −0.033R | **−$283** | −$577 to $13 | 0% | $680 | **8 / 25** | 35 / 105 | $194,012 |
| next open | 4,287 | 45.5% | −0.016R | **−$136** | −$477 to $197 | 0% | $533 | 10 / 25 | 42 / 105 | $145,293 |
| chase once | 3,499 | 38.8% | −0.020R | **−$142** | −$487 to $203 | 0% | $539 | 11 / 25 | 41 / 105 | $129,465 |
| *published fill — **NOT OBTAINABLE*** | *4,508* | *59.4%* | *+0.584R* | ***$5,268*** | *$4,578 to $5,919* | *1,327%* | *at the bar* | *25 / 25* | *100 / 105* | *$11,105* |

Two-year totals, same order: one-a-day **+$13,893 / +$42,977 / −$7,804** honest, against
*$360,380* on the fill nobody can send. Taking everything: **−$141,561 / −$67,839 / −$70,892**
honest, against *$2,633,850*.

### The three obtainable fills are a tie. The unobtainable one is the whole book.

Paired day by day — same 500 sessions, same signals, only the way in differs:

| arm | policy | $ / day vs close | 95% band | verdict |
|---|---|---:|---|---|
| next open | one a day | +$58 | −$15 to $153 | **TIE** — the band straddles zero |
| chase once | one a day | −$43 | −$136 to $51 | **TIE** |
| next open | every signal | +$147 | −$62 to $362 | **TIE** |
| chase once | every signal | +$141 | −$239 to $527 | **TIE** |
| *published* | one a day | *+$693* | *$540 to $823* | **separates from zero** |
| *published* | every signal | *+$5,551* | *$4,927 to $6,155* | **separates from zero** |

That reproduces last night's order-type grid from a completely different direction: B/C/D/E
were a four-way tie there and the obtainable fills are a tie here. **Do not pick a winner out
of that block on money** — next open's $86 a day looks like twice close's $28, and the paired
band on the difference runs from −$15 to +$153.

The one comparison that clears its band is **the head start itself: +$693 a day**. Last night's
independent estimate was +$613 [$497, $731]. Two rigs, same answer.

---

## What this does to the three gates

| gate | target | on the published fill | **on the honest fill** |
|---|---|---|---|
| Money | mean R ≥ 2.0, win ≥ 55% | 0.58R, 59.4% | **−0.033R, 44.3%** (one-a-day +0.028R, 45.5%) |
| Durability | every month green | **25 / 25 — MET** | **11 / 25 one-a-day, 8 / 25 all — FAIL** |
| Recall | ≥90% of his S days | 59.1% | unchanged by the fill in kind, and measured separately today (`research/g85_recall_honest.md`) |

**The only gate OMEN passed, it passed on a price nobody could send.** That is the finding.

Sizing cannot rescue it and this is arithmetic, not opinion: multiplying every day of a red
month by a positive number leaves it red. Green months are scale-invariant, he ratified that
green months win, so **the honest book is a FAIL at every risk size** — the same conclusion
`research/g83_sizing.md` reached from the money side, now true of the shipped default itself.

The dollar gap is smaller than it looks and the durability gap is bigger. $397 a day at one
trade a day needs **$14,179 of risk per trade** on the close fill, $4,616 on next open —
against the $1,000 unit this project sizes on, and against a $50k prop account.

---

## What moved, figure by figure

Everything below was published off the old fill and is now superseded. The old value stays
reproducible: it is in `research/bt2y_trades_published_fill.json`, byte-identical.

| where | figure | was | **is** |
|---|---|---:|---:|
| `DIRECTION.md` money row | trades | 4,508 | **4,329** |
| | win rate, all trades | 59.4% | **44.3%** |
| | mean R, all trades | 0.58 | **−0.033** |
| | two-year dollars, all trades | $2,633,850 | **−$141,561** |
| | one-a-day trades / win / mean R | 499 · 66.7% · 0.72 | **500 · 45.5% · 0.028** |
| | one-a-day dollars | $360,380 | **$13,893** |
| `DIRECTION.md` durability row | months green, all trades | 25 / 25 | **8 / 25** |
| | months green, one-a-day | 25 / 25 | **11 / 25** |
| | weeks green | 100 / 105 · 87 / 105 | **35 / 105 · 49 / 105** |
| | worst drawdown | $11,105 · $5,993 | **$194,012 · $25,570** |
| `OMEN-7.3.md` §4 | $ per session, working tree | $5,268 | **−$283** |
| | one-a-day $/day | $721 | **$28** |

And a whole class of numbers is now **stale rather than wrong**: 40+ research scripts read
`research/bt2y_trades.json` by that name — `g83_sizing.py`, `g83_futures_arm.py`,
`g80_options_honest.py`, `g82_stop_ab.py`, `build_bt2y_report.py`, the verdict-page generator
and the homework builders among them. Every one of them now reads the honest book. **Their
already-published outputs came from the other file and have to be re-run before being quoted
again** — including the options and futures instrument rows, whose *levels* were all built on
the published fill. (Their *differences* survive: both arms shared one fill.)

---

## The book now says who it is

Four files were called `research/bt2y_trades.json` in four days and no reader could tell which
figure came from which. That stops here. `research/book_stamp.py` writes an identity block into
the book's own JSON:

```
"stamp": {
  "built_at": "2026-08-30T10:59:54",  "python": "3.11.15",
  "book_id":  "f76361ae47e9a3b2",          # sha256 of every trade at its price
  "git": {"commit": "3dfb0865…", "commit_subject": "…",
          "dirty_engine_py": ["research/downgrade.py"], "dirty_py_count": 347},
  "flags": { …57 behaviour-changing engine flags, effective values… },
  "entry_fill": "close", "entry_misses": 0, "rows": 127188 }
```

The flags are read **off the modules**, not out of the environment, so a default that nobody
set is captured exactly like a flag that was. `dirty_engine_py` names only the files that can
change a trade — OMEN-7.3 §4 records a night when every published figure sat on eight
uncommitted engine files and a fresh clone earned half as much; that is now visible in the
book itself, not discoverable only by an audit.

**And any report can check itself before it quotes a dollar:**

```python
from research.book_stamp import assert_book, assert_figure
assert_book(BOOK, entry_fill="close", traded=4329, book_id_="f76361ae47e9a3b2")
assert_figure(BOOK, "one_a_day", "per_day", 28)     # BookMismatch if the book moved
```

This report does exactly that for all fourteen of its own headline figures:

```
python research/g85_honest_book.py --check
  -> g85_honest_book.md still matches the book on disk — 14 figures checked
```

Mutation-checked, because a check that cannot fail is not a check: asserting yesterday's
`$721` against today's book raises

```
one_a_day / per_day: published 721, book on disk gives 28.0 (tolerance 1)
  book: bt2y_trades.json — fill close · 4329 traded of 127188 · commit 3dfb0865 · id f76361ae…
```

and asserting `traded=4508` or `entry_fill="published"` raises the same way.

---

## Honest notes on how this was run

1. **The published arm reproduces the committed book exactly.** Re-running today's engine with
   `ENTRY_FILL=published` gives 4,508 traded, $5,268/day, 25/25 months, $721/day one-a-day —
   identical to what `DIRECTION.md` publishes. Row for row it is a strict superset of the
   preserved file: same trades, same prices, plus **20 extra non-traded rows** (19 `skipped_d`,
   1 `skipped_tight_stop`, 0.015% of the file). Nothing traded moved. That is the control
   working: the only thing that changed the money is the price paid.
2. **The preserved book is kept byte-identical and is therefore UNSTAMPED.** Its fill is
   declared by the caller, and the tooling says so out loud rather than inventing metadata for
   a file it did not build.
3. **Two of the four books name a different commit** — `3dfb0865` (close, published) and
   `b0c0f927` (chase once, next open), because another agent committed while these were
   running. The diff between those commits is research reports and a file rename; **no engine
   file differs**, so all four arms share one engine. This is exactly the kind of thing that
   used to be invisible, and it is in the stamp.
4. **`research/downgrade.py` was modified-but-uncommitted at build time** and the stamp flags
   it. Its diff is 27 lines of comment explaining why the confluence tally uses a different six
   levels than the six he trades. No behaviour, no trade changed. Flagged rather than assumed.
5. **The limit arms do not fill everything, and a no-fill is a NO TRADE, not a free option.**
   Chase once left **47,430** setups unfilled and next open **4,530** (of ~127,000 candidate
   signals). Every one of the 500 sessions still had something to trade, so days-traded is 500
   in every arm — the misses cost candidates, not days. Why so many: for a break-and-retest the
   level *is* the stop, so an order resting at the level is an order sitting on your own stop
   (`research/g85_entry_fill.md`).
6. **`limit_level` was not run.** It is the fifth mode and, on the smoke run in
   `g85_entry_fill.md`, it fails to fill 3,355 of 3,355-ish opportunities for that structural
   reason. It is worth a run, and it is the open thread from last night's refuted row A.
7. **Bands are bootstrapped over days, not trades**, 2,000 resamples, fixed seed 20260830.
   Days are the independent unit — two trades on one session share the tape, the two-loss halt
   and the regime.

---

## What is NOT done

1. **`DIRECTION.md` and `OMEN-7.3.md` were updated to these figures in the same commit.** Every
   other document that quotes a dollar — `research/omen-71-verdict.html`, `g83_sizing.html`,
   `research/g72_after.md`, the backtest reports — still carries published-fill numbers and
   now names a book that no longer holds them.
2. **The instrument skins have not been re-run.** Options at $242–$346/day and futures at
   $51/day were both computed on the published fill. Their *differences* survive; their levels
   do not. Re-running `g83_sizing.py` and `g80_options_honest.py` against the honest book is
   the next money question, and it is a mechanical re-run.
3. **Nothing was switched on or off.** `ENTRY_FILL=close` was already the shipped default when
   this pass started (`a70f8771`); this pass rebuilt the canonical book on it and stamped it.
4. **`assert_figure` is not wired to any gate.** Like `test_entry_fill.py` before it, it will
   only protect a number if something runs it. One line in `CLAUDE.md`'s `verify:` would do it,
   and that line configures the harness, so it is left for Austin.

---

## Files

| file | what |
|---|---|
| `research/bt2y_trades.json` | **the book.** Close fill, 4,329 traded, id `f76361ae47e9a3b2`, stamped |
| `research/bt2y_trades_published_fill.json` | the old book, byte-identical, so nothing published becomes unreproducible |
| `research/book_stamp.py` | **new.** The stamp, `assert_book`, `assert_figure`, `describe` |
| `research/g85_honest_book.py` | **new.** Every figure above, plus `--check` |
| `research/g85_honest_book.json` | the figures as data, including the per-day series each band was drawn from |
| `backtest_2y.py` | writes the stamp into every book it builds |
