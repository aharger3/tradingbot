# Your six levels, measured — PDH · PDL · PMH · PML · HOD · LOD

**Short version.** Two of the three changes you asked for cost you nothing in money and
cost you a *lot* in the thing OMEN is actually failing at — finding your S days. The third
one is free money and free recall, and it is the one nobody has ever switched on properly.

| what | money | your S days found |
|---|---|---|
| **Add HOD and LOD properly** | **+$9 a day, +$338,000 over two years, win rate 55.9% → 57.4%** | **166 → 173 of 278. Seven gained, none lost.** |
| Take the opening range out | +$81 a day | **166 → 124.** Forty-two lost. |
| Stop pivots gating | −$13 a day | **166 → 136.** Thirty lost. |
| **All three together (your roster, literally)** | +$8 a day, drawdown **halved** | **166 → 120.** Forty-six lost. |

So: **take the HOD/LOD half of your sentence today. Do not take the other half without
looking at the price on it**, because the opening range and the pivot structure — the two
things you said you do not watch — are between them carrying about a third of the S days
the engine currently finds.

Everything below was measured today on the two-year book, 500 sessions, 2024-08-21 to
2026-08-21, 1R = $1,000. Scripts: `research/g72_sixlevels_book.py` (the arms),
`research/g72_sixlevels_recall.py` (the S-day scoring),
`research/g72_sixlevels_compare.py` (the tables).

---

## 1. The one that is free: HOD and LOD were switched on to a setting that does nothing

The engine has had a HOD/LOD level in it since July, switched off. Flipping the switch as
it stands is **a no-op** — 85 trades out of 6,248, and not one extra S day.

The reason is a rule buried in the qualifying test. To count, the session high has to be
**at least thirty minutes old**, and the day has to be at least **forty-three minutes**
in — so the engine's "HOD" cannot exist before 10:13, and by the time it does it is a
half-hour-stale price. That rule was written in July for one reason: to stop the HOD
being *the opening-range high under a different name*.

That reason is Austin's own sentence away from being obsolete. Relaxing the two staleness
numbers — the day must be 20 minutes in, the high must be 12 minutes old — is what turns
your HOD into the HOD you actually watch. (Twelve minutes is not a taste choice: a level
you are going to break *and retest* has to have been set before the retest window, or the
pattern cannot exist. Below twelve it is not a level, it is the current bar.)

With that done:

| | shipped today | HOD/LOD added properly |
|---|---:|---:|
| trades in two years | 6,170 | 6,964 |
| win rate | 55.9% | **57.4%** |
| per trade | $539 | $527 |
| **two-year total** | $3,328,654 | **$3,667,109** |
| months green | 25/25 | **25/25** |
| weeks green | 103/105 | **103/105** |
| worst drawdown | $19,980 | $19,980 |
| one trade a day | $722/day | **$731/day** |
| **your S days found (of 278)** | 166 | **173** |

The 794 extra trades earn **$426 each**. Nothing that was already in the book changed —
paired against the old book on the 5,980 trades both take, the difference is
+0.0004R ± 0.0008R, i.e. zero. It only *adds*.

The seven S days it picks up, and it loses none:
MARA 2 Mar 2026 · MSFT 11 Mar 2026 · QQQ 30 Jun 2026 · SPY 4 Aug 2026 · TSLA 8 Apr 2026 ·
TSM 11 Feb 2026 · UBER 11 Sep 2025.

The honest cost: it fires on more of the days you *refused* too — 51.3% of those 534 days
becomes 53.0%, about nine extra days — and precision on the held-out sample goes
39.7% → 37.1%. You are buying seven of your own S days for roughly nine alerts on days you
would have passed on.

**This is the one change on this ticket that improves the gate OMEN is failing.**

---

## 2. The opening range: you do not watch it, and it is finding your trades anyway

Out of every trade the book takes, **1,432 (23%) are keyed to the opening-range high or
low**. Taking it out of the gating set — still drawn on every chart, still used for chop
grading, just not allowed to *generate* a trade:

| | shipped | opening range out |
|---|---:|---:|
| trades | 6,170 | 5,033 |
| per trade | $539 | $552 |
| one trade a day | $722/day | **$803/day** |
| worst drawdown | $19,980 | **$17,936** |
| months green | 25/25 | 25/25 |
| **your S days found** | 166/278 | **124/278** |
| held-out sample | 23 of 34 | **18 of 34** |

**It is the best money arm on the whole board and the second-worst recall arm.**
Five of the held-out S days it drops: BABA 5 Feb 2025, CRM 19 Sep 2025, HOOD 6 Nov 2024,
NVDA 29 Apr 2025, QQQ 23 Sep 2025.

And precision falls too (39.7% → 36.0%), which is the part that matters: the opening range
is not a firehose that fires on everything. On your S days specifically it is doing real
work. It is finding the trades you take without you calling it by that name.

## 3. The pivots: gating on them costs nothing and finds thirty of your S days

| | shipped | pivots gate nothing |
|---|---:|---:|
| trades | 6,170 | 4,272 |
| per trade | $539 | $538 |
| one trade a day | $722/day | $709/day |
| worst drawdown | $19,980 | **$13,338** |
| months green | 25/25 | 24/25 |
| **your S days found** | 166/278 | **136/278** |
| held-out sample | 23 of 34 | 18 of 34 |
| precision | 39.7% | **47.4%** |

This one is a genuine trade, not a loss: precision jumps eight points because pivots fire
on days you refused more than they fire on days you liked. Money is flat to the dollar.
Drawdown improves by a third.

Note this **contradicts the board's "pivot levels carry zero of your S days"** — that check
was run on five specific cards from the 34-card sample. Measured across all 278 of your
bar-backed S days, pivots carry **thirty**.

## 4. All three at once — your roster, implemented literally

| | shipped | your six (as the code stands) | your six (staleness relaxed) |
|---|---:|---:|---:|
| trades | 6,170 | 3,042 | 4,387 |
| win rate | 55.9% | 51.0% | **56.9%** |
| per trade | $539 | $528 | $538 |
| one trade a day | $722/day | $746/day | $730/day |
| months green | 25/25 | 25/25 | 25/25 |
| weeks green | 103/105 | 96/105 | 99/105 |
| **worst drawdown** | $19,980 | $10,810 | **$9,938** |
| **your S days found** | **166/278** | 81/278 | 120/278 |
| held-out sample | 23 of 34 | 11 of 34 | 15 of 34 |

**Your roster is money-neutral and drawdown-halving, and it cuts the engine's reach on
your own S days roughly in half.** Per trade it is $539 → $538. One trade a day it is
$722 → $730. Worst drawdown $19,980 → $9,938. And 166 of your S days becomes 120.

The level mix afterwards is exactly what you asked for — HOD 815, LOD 760, PMH 565,
PML 535, PDH 324, PDL 284, plus 799 order-block entries and 305 84%-rule re-entries,
which are setups rather than levels. Zero opening range, zero pivots.

---

## 5. The runner target, and the fallback you asked me to name

You told me to decide the fallback deliberately and state it. Here it is, and there is a
fact in front of it that changes the question.

**Two of your six can never be a target, by construction.** The runner's target has to sit
*beyond* the scale-out point, and the scale-out point **is the session high**
(`backtest_week.py:884` — `scale_level = max(high so far)`). HOD *is* that number. So
"aim at HOD" is arithmetically "aim at where I am already scaling out". Adding HOD and LOD
to the target list is a guaranteed no-op. Restricting the runner target to your six really
means restricting it to **PDH, PDL, PMH, PML** — which is what the code already tries
first, plus one extra candidate: the next whole dollar.

**My decision, stated: when none of PDH/PDL/PMH/PML lies beyond the scale point, keep the
next whole dollar. Do not drop to a flat 2R.** Three reasons:

1. A flat-2R fallback is exactly what made the earlier test look like a loss. With the
   whole dollar kept as the fallback, restricting to your levels measures **flat**
   (+$16 a trade, 25/25 green months, `research/g71_levelsv_book2.py`).
2. A flat 2R target is the arithmetic that makes the money gate unreachable. Every row
   planning exactly 2.000 R:R is why mean R of 2.0 cannot happen.
3. The whole dollar is not a level and should not be described as one. It is a
   placeholder that means "no level of yours is in range" — which is the same thing your
   `default 2r` sentence was reaching for.

**This conflicts with something you said** — *"Pick a level first if no level then default
2r."* I am not overriding it quietly: your sentence, implemented, measures worse. One word
from you settles it, and until then nothing changes. **I did not touch the target code** —
the runner target lives in `backtest_week.py` and belongs to the "runner can never aim more
than $1 past the session high" item on this board, not to this one.

---

## 6. What actually changed on disk

**One shipped file, and it moves no published number.**

`research/downgrade.py` — the level roster your S/A/C grading counts confluence against was
`PDH PDL PMH PML ORH ORL`. It is now `PDH PDL PMH PML HOD LOD`, your set. The feature that
reads it is switched off, so no figure in this repo moves; it was simply naming the wrong
six. One consequence is written into the file rather than hidden: because HOD and LOD are
the session's own extremes, one of that pair is always "on side" and the other never is,
so your "at least 5 of 6" threshold now effectively asks for all four of
PDH/PDL/PMH/PML. Your number, unchanged; what it demands is different.

**Nothing else shipped was edited, and that is deliberate.** All three of the changes this
ticket asks for live in `signal_runner.py`, which another agent owns on this board and is
editing right now. Measuring them did not require writing to it — the rigs read its source,
apply the change to a copy in memory, and run that. The exact diff is sitting ready in
`research/g72_sixlevels_signal_runner.patch`.

New files, all measurement:

| file | what |
|---|---|
| `research/g72_sixlevels_book.py` | the seven two-year books |
| `research/g72_sixlevels_recall.py` | S-day scoring: the 34-card held-out sample **and** all 278 of your bar-backed S days |
| `research/g72_sixlevels_compare.py` | the tables above |
| `research/g72_sixlevels_signal_runner.patch` | the engine change, ready to apply |
| `research/g72_recall_*.json` | the S-day scores, 7 KB each — keep these |
| `research/g72_sixlevels_compare.json` | every number in the tables above |
| `research/g72_arm_*.json` | the seven raw two-year books — **654 MB, and NOT covered by `.gitignore`. Do not `git add -A` in this repo until they are gone.** Each one regenerates in about five minutes from the script above; delete them freely. |

The regression gate passes.

---

## 7. What I would do next, in order

1. **Ship the HOD/LOD half now** — on, with the staleness numbers relaxed. Free money,
   +7 S days, nothing lost. It is the first change on this board that moves the recall gate
   in the right direction.
2. **Leave the opening range and the pivots gating for now**, behind off-by-default
   switches, until you have seen §2 and §3. They are worth about 46 of your S days between
   them and they cost nothing to keep.
3. **The visualisation half of your sentence is not built.** *"You can still visualize
   those pivots"* — nothing in any homework deck or chart draws a pivot today. Turning
   pivot gating off therefore costs no visualisation, but it does not deliver the drawing
   either. That is a chart-builder job, not a level job.
4. **Three more places still carry the old six** and were left alone because they belong to
   the homework instruments, not to the engine: `research/t21_card_filter.py::_levels`,
   `research/build_levels.py`, and the deck builders. They still list ORH/ORL as two of
   your six. Worth one small pass.
