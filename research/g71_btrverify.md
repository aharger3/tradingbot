# G7.1 / btrverify — adversarial verify of the `break_then_rejection` "dead branch" claim

**Verdict: REFUTED.** The count is right, the diagnosis is wrong.

The scanners track claimed `break_then_rejection` is *"structurally unreachable and has
never returned True"*, and offered a "structural proof" that
`research/downgrade.py:265`'s scan is *"vacuous by construction"*. The trip count
reproduces exactly. The reachability argument does not survive a counterexample, and the
same predicate on the same real bars **has** returned True.

## 1. The count reproduces (`research/g71_btrverify_census.py`)

Read straight off the committed book's own `downgrades` field — the same population the
scanners census used. Book meta: `signals=76019 traded=2437 generated=2026-08-29T03:14:29`
(the post-T0 / post-T23 book at `145d564e`, **not** the old 45,175 / 1,016 one — that part
of the claim is clean).

| variable | trips | % of 76,019 |
|---|---:|---:|
| `counter_trend_not_respected` | 69,537 | 91.47% |
| `level_not_respected` | 49,989 | 65.76% |
| `no_displacement` | 38,263 | 50.33% |
| `ocr_not_respected` | 20,021 | 26.34% |
| `no_retest` | 10,356 | 13.62% |
| `exhausted` | 9,150 | 12.04% |
| `chase` | 5,720 | 7.52% |
| `stale_retest` | 490 | 0.64% |
| **`break_then_rejection`** | **0** | **0.00%** |

Re-grading 5,437 rows from archived bars (`research/g71_btrverify_book.py 3000`, all 2,437
traded + 3,000 sampled) gives the same answer: **0 of 5,437** at the shipped call.

## 2. The branch is reachable — counterexample (`research/g71_btrverify_reach.py`)

Nine synthetic 1-minute bars, level = 100, long. Bar 4 closes up through the level, bar 5
closes back below it, bars 6–8 stay below, so no newer up-cross exists and `_break_bar`
still returns 4:

```
LONG  _break_bar(i=8) = 4
LONG  break_then_rejection = True
SHORT break_then_rejection = True          (mirrored bars)
score().tripped = ['break_then_rejection']
re-cross case (bar 6 closes back above): _break_bar = 6 | btr = False
```

The predicate is not vacuous. The real exclusion is narrower than the claim states: a
rejection is only hidden if price **re-crosses forward before bar `i`**, which promotes the
later cross to `br`. Without a re-cross the rejection is fully visible.

## 3. Where the "structural proof" breaks

`research/g71_scanners_deadprobe.py:60-68` argues: *"If any bar after it closed BACK through
the level, price must cross forward again before bar i (bar i closes on the break side)."*
The parenthetical is the whole argument, and it is **an empirical property of this book's
entry construction, not a property of the code**. `break_then_rejection` returns True
exactly when the entry bar closes on the wrong side of its own level; the engine never
builds such an entry, because for a B&R the level it is handed **is the trade's stop**
(`backtest_2y.py:151` → `dg.score(dbars, t.entry_idx, t.stop, ...)`), and a long entered
below its own stop would be instantly stopped out. Confirmed: **entry price on the wrong
side of its own stop = 0 of 76,019**.

The deadprobe's two supporting zeroes are also a 1,500-row sample artifact. On 5,437 rows:

```
B. entry-bar CLOSE on the wrong side of the stop: 3 of 5437   (deadprobe reported 0)
```

## 4. It has fired on real bars

`research/a1_threshold_sweep.md:28`, at committed defaults, over the then-current book:

| variable | 120 cards | held-out 100 | 2-yr book |
|---|---|---|---|
| `break_then_rejection` | 0/1250 | 0/926 | **10/45,175** |

That number was produced by `research/p2_threshold_sweep.py::features` (lines 262, 272-278)
+ `trips_of` (line 373) — logically identical to `downgrade.break_then_rejection`
(cap-at-`br+2`-and-return vs. find-first-gap-then-compare-to-`REJECT_BARS` are the same
predicate), on a byte-identical `_break_bar` (`p2_threshold_sweep.py:170` vs
`downgrade.py:180`), at the same level proxy `r["stop"]` (`p2_threshold_sweep.py:681`).
`git diff 1e787a6b HEAD -- research/downgrade.py` shows **neither function changed** since
that report. So the same code, on real bars, returned True 10 times.

p2's own prose was honest about this — *"by construction there is **almost never** anything
for `break_then_rejection` to find"* (`p2_threshold_sweep.py:1095`). The scanners track
escalated "almost never" to "never / unreachable by construction".

## 5. The branch fires 11.6% of the time on the same bars, at other levels

`research/g71_btrverify_book.py 3000`, sweeping candidate level prices (distinct closes in
the prior 30 bars) on the **same real bars as the book rows**:

```
rows with >=1 level where the branch is TRUE : 4227 of 5437 (77.7%)
candidate (row, level) pairs true            : 15241 of 131781 (11.57%)
e.g. AAPL 2024-08-22 09:59 L stop=227.80 -> fires at level 228.21
e.g. AAPL 2024-10-09 10:15 L stop=225.82 -> fires at level 226.09 (6 of 27 levels)
```

The function is a live discriminator. It sees nothing only because of **which price it is
handed**.

## 6. What the corrected finding is

`break_then_rejection` is a **wiring / level-argument defect**, not an unreachable branch.
The grader is handed the trade's **stop** as `level`; Austin's rule is about the **level
that was broken**, which for a B&R is the same number *by the time the entry is confirmed*
and therefore has zero information left. Same failure family as `level_not_respected`
(`research/p15_level_respect.md:38-46`, which says "**effectively** unreachable") — the
post-entry population has no violations left because entry construction already excluded
them.

This changes the fix. Re-anchoring `_break_bar` on the **session's first** break
(`PHASES.md:146`, P39, and `research/g71_scanners.md:281`) is directionally right but is
being justified by a false premise; a fix aimed at "the scan range is empty" would be
aimed at a bug that does not exist. The scan range is not empty — `br` is not `i` on this
book (the deadprobe's own distribution shows the scan CAN run), the test inside it is just
always False at this level.

**Do not quote "0 trips ⇒ unreachable branch" in the ruleaudit.** `research/g71_ruleaudit.md:139`
and `:188` and `research/build_omen_test1.py:59` all carry the escalated wording and should
be corrected to "reachable, but blind at the level the grader is handed".

## Scripts

| file | what it produced |
|---|---|
| `research/g71_btrverify_census.py` | §1 trip census, entry-vs-stop geometry |
| `research/g71_btrverify_reach.py` | §2 synthetic counterexample |
| `research/g71_btrverify_book.py` | §1/§3/§5 real-bar re-grade, wrong-side count, level sweep |
