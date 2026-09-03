# After the fix pass — what the book says now

*2026-08-29. Book rebuilt end to end today at 18:38: 500 sessions, 134,012 setups looked
at, 4,508 trades taken. 1R = $1,000. Every number below comes from
`research/g72_after_headline.py`, which reads that book and reuses the exact same
arithmetic the earlier reports used, so the comparison is honest and not re-typed.*

---

## The money

**Taking every signal the engine fires:**

| | Before the pass | Now | Change |
|---|---:|---:|---:|
| Trades in two years | 2,437 | **4,508** | +2,071 |
| Win rate | 49.5% | **59.4%** | +9.9 pts |
| Dollars a day | $2,700 | **$5,268** | +$2,568 |
| Months green | 25 of 25 | **25 of 25** | held |
| Weeks green | 91 of 105 | **100 of 105** | +9 |
| Worst drawdown | $14,714 | **$11,105** | −$3,609 |
| Two-year total | — | **$2,633,850** | — |

**One trade a day — the way you would actually run it:**

| | Before the pass | Now | Change |
|---|---:|---:|---:|
| Trades | 496 | **499** | +3 |
| Win rate | 54.9% | **66.7%** | +11.8 pts |
| Dollars a day | $611 | **$721** | +$110 |
| Months green | 22 of 25 | **25 of 25** | +3 |
| Weeks green | 77 of 105 | **87 of 105** | +10 |
| Worst drawdown | $20,100 | **$5,993** | −$14,107 |
| Two-year total | — | **$360,380** | — |

Nothing got worse. Nothing needs reverting.

### But be careful which half of this you believe

The extra $110 a day under one-trade-a-day **is inside the noise**. When it was measured
properly — same 500 days, paired, resampled ten thousand times — the honest answer was
"somewhere between losing $24 a day and making $250 a day". Do not spend that money.

What is **not** noise, and is the real prize:

- **Months green went from 22 of 25 to 25 of 25.** Every month green is one of your three
  gates, and one-trade-a-day used to break it. It no longer does.
- **Worst drawdown fell from $20,100 to $5,993.** That is a two-thirds cut in the worst
  hole you would ever have been in.

### The gate you are still failing

Average result per trade is **0.58R** taking everything, **0.72R** one-trade-a-day. The
money gate is **2.0R**. This pass did not move you meaningfully closer to it, and no
honest reading of these numbers says otherwise. You make more money now because you take
**1.85 times as many trades**, not because each trade got better — per trade it went
$549 to $584, which is noise.

---

## Why the numbers moved — all of it is one fix

Ten separate things were fixed. **Only one of them touches the book at all.**

**The one that moved everything:** when the engine looked at a setup and said *no*, the
backtest wrote that refusal down as "this price level is used up" and threw away the
real, tradeable setup that showed up on the same level a minute or two later. Nearly
seven in ten of the trades being thrown away were killed by a refusal that the engine
itself had flagged as *"I should not have fired at all"* — a bug report was being given a
veto over a real trade standing right behind it. Your own rule that two signals on
back-to-back minutes are one idea is untouched.

That single fix accounts for **every difference in both tables above**. I checked this
rather than assumed it:

- The change that took the live options target from 2R to 2.5R **cannot** reach the book —
  the backtest never loads the live sizing code at all. Verified by reading the imports.
- The live sell-half-and-let-it-run port is behind a switch that is **off**.
- The six-levels change is behind a switch that is **off**.
- The recall work, the grade-spelling work and the disaster-order pricing changed
  **no engine code whatsoever** — they are measurements.
- The setup and level names added to every trade row are two extra labels; they moved no
  money, and they now cover **100% of all 4,508 rows**.

I re-ran the 2.5R target pricing on this freshly built book to be sure it still holds up:
**+$33 a trade, and the error bar is +$9 to +$56** — so it clears its own noise. Confirmed,
not assumed.

---

## The alarm I chased down, and cleared

Every single losing trade in the book books **exactly −$1,000**. Not one loss is bigger.
The −$1,250 slippage floor you asked for never once comes into play across 1,828 losses.

That is the exact fingerprint of a bug this project has been burned by before, and one
of the safety tests (`research/t11_stop_fill_fix.py`) is **red right now**, saying so.

**It is not a bug, and the engine is right.** Two of your rules stack, and the order they
stack in is the whole answer:

1. A resting order sits at −$1,000 the whole time. A resting order that gets *touched*
   fills right there — so it books exactly −$1,000, off the wick, intraday.
2. The −$1,250 floor only applies to the *other* kind of exit, the one that waits for a
   candle to close past your stop.

The resting order always gets there first. So while it is switched on, −$1,250 is
**unreachable by design, not by mistake**.

The test is red because it never switches that resting order off before checking the
close-based path. I proved this rather than argued it: with the resting order off, the
test goes **64 checks, zero failures, green**. With it on, the same unchanged code gives
12 failures. Script: `research/g72_after_stopfloor.py`.

**This corrects the board.** That item was written up as "the stop fill fix is broken".
The fill code is correct and does route through the single shared definition. What is
actually broken is the test's blind spot. Nobody was assigned that item this pass, so it
is still red and still needs an owner.

---

## Nothing was fudged — the things I checked by hand

- **Not one of your judgement files was touched.** All 32 of them — every graded deck,
  every blind pass, every recovered review, every ballot — are byte-for-byte identical to
  the last commit. I checked this against the committed copies directly, not just with
  `git status`, because those files are hidden from `git status` by an ignore rule and
  that trap has already fired twice on this project. I also confirmed nobody had set the
  flags that hide a file from git.
- **The count went up, never down:** 1,148 judged symbol-days and 288 of your S days, up
  one from where the pass started. Nothing was lost.
- **The pass/fail baseline was not quietly re-locked.** It still dates from 28 August and
  matches its commit exactly. The gate passes honestly: the engine now fires on *more*
  of your marks than the baseline recorded (83 against 75), and none went silent.
- **Both gates are green**, and there are now two of them instead of one — the second was
  wired in this pass after being found sitting unrun, which is the same failure that once
  let the first gate sit red for sixteen days.
- Five other safety tests were run and all pass.
- **No test was weakened to make anything pass.** Two were strengthened. One check was
  loosened, and I read it: it used to demand the recall rig name a helper function by
  hand, and now accepts it inheriting the real thing instead. That is stricter in
  practice, not looser.

---

## The one number that got worse, and it is the truth

Held-out recall now reads **22 of 34 cards, not 23**, and the honest full-corpus read is
**163 of 278 of your S days — 58.6%**.

Nothing broke. The rig that scores recall had been carrying its own hand-written copy of
the engine's decision logic, so every gate the real engine grew after that copy was made
was invisible to the only test that measures recall. It now calls the real engine. The
copy had been flattering the score — by three days out of 278, and **always upward, never
downward**.

The upside is that recall is now measured on 278 days instead of 34. The error bar shrank
from roughly ±16 points to ±6, which means a change that genuinely helps can no longer
hide in the noise — and it saves you grading 107 more cards to get there.

You are **31 points short of the 90% recall gate**, not the 22 points the old number
implied.

---

## Two changes nobody claimed

Both are harmless. Flagging them because unattributed edits are how bad things enter.

1. **`research/probe_page.py`** — the homework page shell — was edited by something that
   did not report it. The change adds a phone-friendly layout tag and a safer export path.
   I checked the risky part: it cannot break your export button, because the fallback it
   depends on is properly declared. Safe, but unexplained.
2. **`.claude/settings.json`** — a new file enabling an unrelated plugin. Not from any of
   the ten fixes. Worth a glance from you.

---

## Waiting on you

1. **Switch on the levels you actually watch.** Turning on high-of-day / low-of-day
   *properly* is measured at **+$338,455 over two years**, win rate 55.9% → 57.4%, all 25
   months still green, drawdown unchanged, and it finds **7 more of your S days while
   losing none**. Turning it on the way the flag stands today does nothing at all, because
   a buried rule makes the engine's "high of day" unavailable before 10:13 on a session
   that ends at 11:00. The one-line change is written and waiting.
2. **The opening range and pivot levels.** You said you do not watch them. Taken out, they
   are the best money on the board — but they are quietly carrying **46 of the 166 S days
   the engine currently finds**, and removing the opening range makes the engine *worse* at
   picking your days, not just quieter. Your call, and it is a real trade-off, not a
   free win.
3. **The resting −$1,000 order.** Deleting it is worth **+$154 a day** under your
   first-trade rule and **+$149 a day** under keep-going-until-green — and unusually for
   this project, both clear their own error bar. It costs you a bigger worst day
   (−$2,000 → −$2,500). The recommendation is delete it *and* turn on your −$2,000 daily
   floor, which gets you $1,012 a day, 24 of 25 months green and a $10,520 drawdown. The
   middle option you were offered — moving the order to −$1,250 — is the **worst** of the
   three and should be dropped.
4. **The sell-half-and-let-it-run exit is built for live but switched off.** It is worth
   about **$306 a day**. It needs two small wiring changes in the scanner before the switch
   does anything, and those live in a file nobody owned this pass.
5. **35 of your 288 S days are contested** — graded S in one sitting and not-S in another.
   Only one is genuinely you-versus-you. That is a judgement call only you can make.
6. **1,233 candidate rules** were mined out of 107 course transcripts that had never been
   read for rules. They are candidates, not your rules, and want your yes/no.

---

## Two housekeeping hazards

- **654 MB of measurement files** in `research/` are not covered by the ignore rules.
  Do not run a blanket `git add` in this repo until they are cleared. They rebuild from
  committed scripts in about five minutes each.
- **The stop-fill test is still red** and, as shown above, red for the wrong reason.
  Whoever picks it up should make it control the resting order rather than change any
  engine code.

---

*Scripts behind every number here: `research/g72_after_headline.py` (the two tables, the
book comparison, the label coverage) and `research/g72_after_stopfloor.py` (the −1R
finding and the red-test proof). Both re-runnable; neither touches the book.*
