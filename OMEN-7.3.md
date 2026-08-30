# OMEN 7.3 — MASTER SPEC

Written overnight 2026-08-30 from Austin's session message. Supersedes `OMEN-7.2.md` as the
dispatch board. `DIRECTION.md` holds the invariants; `CLAUDE.md` holds the things you must
not break; `Austin's Vault/Projects/omen-rulebook.md` section "Session 2026-08-30" holds his
words.

**Plain English throughout.** No track IDs, no T-numbers, no phase codes. He said it straight:
*"dont speak in code."*

**Findings land in section 4 as they finish.** Anything still running is marked so. Every figure
names the script that made it, and every figure was handed to a second agent told to refute it.

---

## 1. The $700-a-day thing, answered first

> *"Pretty confused by your 700 a day to 100 a day metric."*

Fair. Here is the whole of it.

The two-year book said **$721 a day** taking one trade a day. Then someone read the line that
decides what price a trade gets filled at — `signal_runner.py:1330` —

```python
return min(max(level, candle.low), candle.high)
```

The engine only knows a signal exists once the minute **closes**. But that line fills the trade
at **the level**, which on 85% of trades is a price that printed *earlier in that same minute* —
before the signal existed. On HOOD, 2 July 2025, the book buys at 93.38 when the signal did not
exist until 93.78 printed at the end of the minute. **The trade was already 1.74R in profit at
the instant it came into being**, and it books +$10,074.

Split the book on that one fact and there is nothing left to argue about:

| | trades | mean | win rate |
|---|---:|---:|---:|
| filled at a price the minute had already traded | 3,841 | **+0.70R** | 64.2% |
| filled at the price you could actually see | 667 | **−0.07R** | 31.8% |

So $100 is not a different opinion about the same book. It is **the same book with the head start
taken out**. Whether it lands at $0, $86 or $114 depends entirely on the order type — which is
exactly what you asked for tonight, so it is being measured rather than guessed.

**One honest caveat, and it is why this is not being treated as settled.** A limit order resting
at a level you drew *before the open* is a legitimately fillable price — that is not look-ahead,
it is how a resting order works. How much of the 85% is a knowable premarket level versus a price
the engine could only have reached by time travel is **the single most important open number in
this project**. It is running now.

*(Source: `research/g76_rebuild_verdict.md`, being adversarially re-checked by
`research/g80_lookahead_refute.md` and `research/g80_dollar_reconcile.md`.)*

---

## 2. What you asked for tonight

| # | your ask | where it lands |
|---|---|---|
| 1 | Explain the $700 → $100 number | Section 1 |
| 2 | **Higher-timeframe thesis as a selector** — *"a better S trade 20 minutes later if I knew the longer time frame"* | Section 4, Accuracy |
| 3 | Use the corpus more, **Scarface and Jdub specifically** | Section 4, Corpus |
| 4 | **Stops on the candle close — show the metrics**, and scale-outs are intrabar | Section 4, Stops |
| 5 | **Market orders, limit orders, options in the backtest** | Section 4, Money |
| 6 | Clean the artifact — random repeats, unclean metrics | Section 4, Artifact |
| 7 | **Master homework of variety**, not just S-grade accuracy | Section 4, Homework |
| 8 | Grill you on burning questions and blockers | Sections 5 and 6 |

Two things you said that are now standing rules, recorded in the rulebook:

- **Mentor material is evidence and bug reports, never a rule.** Your words: *"it's hard to trust
  corpus, but you're welcome to take recommendations that fix bugs."*
- **Keep the artifact's format.** You like the shape. Fix the repeats, do not redesign it.

---

## 3. Your grades are all accounted for

Checked four ways at your request. **Nothing is missing.** Every judgement file on disk is tracked
in git. The one untracked file was `research/decks/g75-deck2-manifest.jsonl`, a *build record* of
which 39 cards were selected — not a grade. Now committed, because being **served** a card counts
for the no-repeat guarantee, not just being graded. Zero of its 39 overlap anything you have judged.

Full tracked inventory: 24 mark files plus 2 ballots, 2,715 rows of judgement.

The thirty from last night are `88cad496` — **21 yes, 9 no**, ten cards each of the 84% rule, the
one-candle rule and break-and-retest. They were already saved and already staged; committing them
was hygiene, not a rescue.

Two things make that batch the most valuable data this project has:

1. **Twenty of the thirty carry a stated entry MINUTE** — *"9:47"*, *"9:38 is the entry"*,
   *"10:09 would never trade."* First time entry timing has come from you directly on a held-out
   sample instead of being inferred from bars.
2. **You named displacement in four of the nine refusals, unprompted** — and once as a downgrade
   that the confluence +1 carried back to S. Displacement is not currently one of the eight
   variables. It is now a ballot line (question 3 below).

**One genuinely open item:** deck two was *built* at 23:04 on 29 August but **no answers for it
exist on this machine**. If you remember grading a second deck, that export never came back.

---

## 4. Findings

*Filling as the overnight work lands.*

### Money — order types, options, tradability — **LANDED 2026-08-30 02:37**

Nine agents, 1.04M tokens, 54 minutes. Every number below was recomputed from scratch by a second
agent that imported nothing from the first.

**The one-line answer: on a fill you can actually get, shares make about $50 a day and options make
about $250 to $350 a day — against your $397 bar. Options are the only route that gets close, and a
five-cent option spread kills it.**

#### 1. The look-ahead is real, and worse than the earlier report said

The claim survived refutation at high confidence, but the *mechanism* was wrong and the corrected
one is harsher. It is not that the level is unknowable — the level was fixed by an earlier bar on
**3,796 of 3,841 (98.8%)**, and the setup completed a median **5 bars** before entry. A resting
order was genuinely placeable. It still does not get you the money:

- **2,067 of 3,841 (53.8%, $1,504,056)** are filled at the minute's own low (long) or high (short)
  with **the level outside the bar entirely**. A resting order at the level would not have filled at
  a worse price — **it would not have filled at all.**
- Of the 1,769 genuinely at the level, the level was first touched on an **earlier minute in 96.9%**
  of traced cases. The order was already filled minutes before, holding a different position.
- **Only 105 trades — 2.3% of the book, $111,556 — are genuinely obtainable at the book's price.**

Held fixed on the same 3,841 trades, changing only the price paid, the mean drops **+0.698R →
+0.022R**. Selection explains about +0.09R of that; the fill explains the rest.

#### 2. The order-type grid — what you asked for

Same 4,508 setups, same stops, same shipped exits. Only the way in changes. One trade a day:

| how you get in | days traded | days missed | win | **$ / day** | 95% range | months green |
|---|---:|---:|---:|---:|---|---:|
| the book's fill *(control — not obtainable)* | 499 | 0 | 64.5% | **$683** | $536 to $835 | 24 / 25 |
| **D · limit one bar, then market (chase once)** | 499 | 0 | 52.0% | **$68** | −$26 to $165 | 14 / 25 |
| **B · market at the signal minute's close** | 499 | 0 | 50.6% | **$48** | −$42 to $141 | 13 / 25 |
| **E · limit at the level, 3-bar expiry** | 467 | 32 | 33.9% | **$46** | −$95 to $197 | 16 / 25 |
| **C · market at the next minute's open** | 499 | 0 | 52.4% | **$33** | −$51 to $117 | 12 / 25 |
| A · resting limit at the level | 479 | 20 | 19.2% | −$252 | −$404 to −$89 | 6 / 25 |

**B, C, D and E are a four-way tie** — every range straddles zero, and the spread between them is
far inside the error bar. **Do not pick a winner out of that block.** What is not ambiguous: a
paired per-day bootstrap puts control-minus-chase-once at **$613 a day, 95% [$497, $731]**. The
head start *is* the book.

**Row A is refuted and must not be acted on.** The verifier found the −$252 is an artifact of the
arming model, which let the order rest *before the signal existed* (5,472 of 5,714 fills landed
ahead of the signal bar, median 3 minutes early) — and found look-ahead in that arming trace in two
places. Re-run honestly, a limit resting from the bar *after* the signal makes **+$92/day, 95%
[−$87, $290]** — a tie with zero, not a loss. **The resting-limit path is still open.**

#### 3. Options beat shares — and then the spread eats it

Market order at the signal minute's close, one trade a day:

| | $ / day | $ / month | win | months green |
|---|---:|---:|---:|---:|
| shares *(the control)* | $187 | $3,735 | 43.1% | 17 / 25 |
| **options, tape-matched volatility** | **$346** | **$6,915** | 42.3% | 21 / 25 |
| options, the repo's inherited 1.2× volatility | $242 | $4,831 | 41.7% | 20 / 25 |
| published unobtainable fill *(control)* | $1,011 | — | 64.5% | 25 / 25 |

Options minus shares: **+$154/day [+$103, +$205]** at tape-matched volatility. Then:

| option spread vs 1¢ stock spread | options | shares | verdict |
|---|---:|---:|---|
| 2¢ | $162 | $166 | dead even |
| **5¢** | **$44** | $166 | **−$123 — shares win** |
| 10¢ | −$154 | $166 | −$321 — shares win decisively |

**The whole options case rests on getting filled inside a two-cent spread.** That is a data question
you can settle by buying the tape, not a strategy question. Also found: the repo's volatility
multiplier prices options **33% too expensive** against the only real option tape on disk, and the
earlier report called the pricer unbiased only because its filter dropped the 124 rows where it was
worst.

Two more contract facts: **1,337 of 4,472 rows (29.9%) lose more than −1.25R on the contract** —
worst is −5.93R where the worst stock row is exactly −1.25R — and carrying $1,000 of risk needs
**$5,035 to $8,605 of capital**.

#### 4. Tradability is a non-issue

**19 of 4,508 trades (0.42%)** fail the two-times-spread bar. Removing them costs $117/day and
changes nothing — 25/25 green months either way. Median stop is 48¢; 182 trades (4.0%) have a stop
under 10¢. *The tight-stop worry was real in principle and is small in fact.*

#### 5. One open conflict, and it is worth $139 a day

Two agents both measured "market order at the signal minute's close, one trade a day" and got
**$48** (`g80_ordertype_grid`) and **$187** (`g80_dollar_reconcile`). Both reproduced under
independent verification. The difference is the exit: the reconcile used its own flat-2R simulator,
which is 1.19× more generous than the shipped ladder, and did not apply the 687-row size gate.
**Neither is wrong; they answer slightly different questions.** Until this is reconciled, quote the
range **$48 to $187 a day**, not a point.

#### 6. Against your $397/day bar

| route | $ / day | % of six figures a year |
|---|---:|---:|
| shares, market at close | $48 – $187 | 12% – 47% |
| **options, market at close, tight spread** | **$242 – $346** | **61% – 87%** |
| the published book *(not obtainable)* | $683 | 172% |

**Nothing measured tonight reaches $397 a day.** Options at a tape-matched volatility and a
two-cent spread gets to 87% of it, and that is the only route in sight.

*Reports: `research/g80_lookahead_refute.md` · `research/g80_dollar_reconcile.md` ·
`research/g80_ordertype_grid.md` · `research/g80_options_honest.md` · `research/g80_tradability.md`*

*Failed to run: the DeepSeek number-provenance sweep — the model is not reachable from this account
(`deepseek/deepseek-chat` returned no-access). Re-queued on Sonnet.*

### The free 278 — **LANDED, and it reframes the accuracy problem entirely**

You picked this over grading more cards. It cost under four minutes and it is the most
clarifying result of the night.

> **The engine is not blind. It is undiscriminating.**
>
> It produces a signal on **97.4% of the days you graded S** — and on **97.6% of the days you
> looked at and refused.** Those are the same number.

| | days | engine takes a trade | 95% band |
|---|---:|---:|---|
| days you graded **S** | 303 | **59.1%** | 53.5 – 64.5 |
| days you **refused** | 542 | **50.6%** | 46.4 – 54.7 |
| days you graded A | 228 | 49.1% | 42.7 – 55.6 |
| days you graded C | 58 | 65.5% | 52.7 – 76.4 |

**Separation is +8.5 points, 95% band [1.5, 15.4]** — it clears zero, and only just. Precision is
**39.5%**: of every 100 days it trades, 40 are yours and 60 are days you refused. Against the 90%
gate it is **30.9 points short**, and the odds of seeing 179 of 303 if the true rate were 90% are
about 1 in 10⁴⁴.

**It fires on your C days more often than your A days.** Whatever it sorts on, it is not your grade.

*Legacy ladder, side by side: of the entries it takes on your S days, 205 are graded B, 83 C, 3 A,
and **zero A+**. The live scanner promotes to TRADE only on A+. **The live path would trade none of
this.*** That is blocker 2 confirmed from a second direction.

**What the bigger sample bought:** the answer went from **±15.7 points to ±5.5**, and the chance of
spotting a real 10-point improvement went from **0.33 to 0.996**. Before today, a genuine
improvement had a two-in-three chance of looking like nothing. *This is why you no longer have to
grade to steer.*

Two honesty checks passed: scored on the same 100 blind cards this run returns **22 of 34** — the
post-router-fix figure, not the 23 the old photocopy reported — and the pool is **303** bar-backed
S days, not 278, because the canonical reader found a ninth spelling of "S" and picked up last
night's 30.

*Report: `research/g83_recall278.md`. Canonical mark reader: `research/marks_pool.py`.*

### Accuracy — higher timeframe, displacement, the rare setups
*Running.* `research/g81_marks30_score.md` · `research/g81_marks_pool.md` ·
`research/g81_htf_thesis.md` · `research/g81_displacement.md` · `research/g81_rare_setups.md` ·
`research/g81_rulebook_audit.md`

### Sizing — **six figures is not reachable, and sizing cannot fix it**

The direct answer to your question 1, and it is a hard no.

> **No. Six figures a year is not reachable on the current engine — not at any risk size — and the
> thing that stops it is not the money, it is the green months.**

One trade a day, honest fill, $1,000 risk, 500 sessions. Every dollar figure scales linearly.

| instrument | days traded | **$/day** | 95% range | **% of $397** | risk that reaches $397 | **green months** |
|---|---:|---:|---|---:|---:|---:|
| **options, same-day ATM, before spread** | 499 | **$346** | $180 – $508 | **87%** | $1,148 | **21 / 25** |
| shares, after a penny round trip | 499 | $167 | $33 – $304 | 42% | $2,382 | 16 / 25 |
| options, after a nickel round trip | 499 | $145 | −$20 – $310 | 37% | $2,738 | 15 / 25 |
| index futures, SPY/QQQ/IWM only | 230 | $51 | −$42 – $143 | 13% | $7,819 | 13 / 25 |
| *published fill, shares — control, not obtainable* | *499* | *$830* | *$696 – $963* | *209%* | *$478* | *25 / 25* |

**The money half is closer than expected — 87% of the bar, and $1,148 of risk lands on $397 exactly.**
The durability half is what fails, and it fails in a way sizing structurally cannot touch:
**multiplying every day of a month by a positive constant cannot change the sign of that month's
total.** Green months are scale-invariant. You ratified that green months win, so this is a fail,
not a trade-off.

**The biggest risk number that preserves 25 of 25 green months is $0.** Not "small" — there is not
one. No honest-fill instrument in this book holds 25 of 25 at any size. The only arms that do are
the published-fill controls, and that fill is a price nobody can send.

*What this does NOT say: that the idea is dead. It says the current engine cannot get there, and
the reason is now precisely located — the engine trades your refusals as often as your S days.
Fixing discrimination is the only lever that moves both gates at once.*

*Report: `research/g83_sizing.md` · dark interactive version: `research/g83_sizing.html`,
published as a private artifact.*

### Instruments — all three, side by side

Options is closest at **$242–$346/day (61–87% of the bar)**; shares **$167–$187 (42–47%)**;
index futures **$51–$55 (13–14%)**.

**One stale number corrected:** `g71_propfirm.md` said a futures-only account sees an index signal
on **139 of 500 sessions (27.8%)**. It is **230 of 500 (46.0%)**. Futures is less starved than
believed — and still last, by a wide margin, because index setups simply carry less range.

*Report: `research/g83_futures_arm.md`*

### Scale-outs — **ratified, and there was no bug**

You ratified that a profit target fills on touch. The code already does it, everywhere: the
committed `backtest_week.py` compares against bar high/low at lines 562, 579 and 789, and
`paper_trader.py` takes (high, low) at seven sites and never the close.

So this became a guard instead of a fix. `research/test_scaleout_touch.py`, **34 checks, all
green** — and mutation-verified: forcing close-based targets turns **10 of the 34 red**, so the
test can genuinely fail rather than passing vacuously.

**Priced anyway, because it had never been:** filling on touch rather than waiting for the close is
worth **+$188/day and four green months**. Quote the $188 *difference*, not the level — both arms
carry the entry-fill head start from section 1.

*Report: `research/g83_scaleout_touch.md`*

### Homework — the deep batch is built

**60 dark charts**, one question ("is this an S?"), **an entry-minute box on every card** — because
the minutes you wrote unprompted on twenty of last night's thirty turned out to be the most
valuable field in the batch.

Deliberate quota, stated on the page: **20 traded · 20 fired-and-refused · 20 engine-silent.** That
mix exists because the old builder never asked whether the engine took the signal, so every
precision number it produced measured the wrong object.

**Zero repeats against a 1,617-symbol-day exclusion set.**

*`research/probes/omen-deep-batch.html` · manifest `research/decks/g83-deep-batch-manifest.jsonl`
(carries the answer key, kept out of the page).*

### Dark theme

Audited — all three target pages were already dark-correct. No changes needed.
*Record: `research/g83_dark_theme.md`*

### Corpus — Scarface and Jdub entry timing
*Running.* `research/g81_mentor_timing.md`

### Stops — **you did settle it, and the code has never run the rule you settled**

Two answers, and they point opposite ways.

**On whether you agreed: you did. `CLAUDE.md` was right and the agent that doubted it was wrong.**
The first pass claimed the "settled five times" citation was wrong and offered eight statements on
a date it invented. The verifier could not reproduce any of it: counting every note in the
80-card sitting that ties a close to a stop gives **exactly five** — lines 343, 357, 363, 367, 374
of `austin_marks_v7.jsonl`. The claimed date appears in no mark file (`marked_at` is empty on all
479 rows), and the report quoted a line of `backtest_week.py` that does not exist. **That report is
refuted; do not cite it.** You settled close-only stops five times, plus two ballot answers, plus a
ratification on 29 August.

**On what the code does: it has never run that rule.** This is the finding.

> The `-1R` "disaster stop" rests at **exactly the same price as your level stop** — risk is
> entry minus stop, so entry minus one times risk *is* the stop — it is tested **first**, and it
> is tested on a **touch**. A wick alone ends the trade. Close-only has therefore never been
> measured, and the **−1.25R floor is unreachable dead code for the second time in this project.**

The fingerprint is in the committed book: **0 of 1,225 losses are worse than −1.000R, and 1,207 are
at exactly −1.0000R.** Losses are −1R by construction, exactly as they were before the last fill fix.

Run properly, paired trade-by-trade on the 4,363 entries common to both books:

| arm | vs shipped, per trade | 95% interval |
|---|---:|---|
| **close-only + the −1.25R floor** | **+$74.8** | +$51 to +$100 — excludes zero |
| making profit legs wait for a close | **−$159.3** | −$177 to −$142 — excludes zero |

**Your rule is the better arm, and your instinct on scale-outs was right twice over.** But the
honest answer to the question you actually asked is **TIE**: +0.0843R a trade against the ±1.5799R
bar. Take it because it is your rule and it is free, not because it is proven.

**Nothing was switched on.** `DISASTER_STOP` still defaults to 1. Changing a shipped default is
red-lane and it is yours to call.

*Reports: `research/g82_stop_ab.md` (survived) · `research/g82_stop_provenance.md` (**refuted**).*

### ⚠ The integrity finding — every number tonight sits on an uncommitted engine

The verifier caught this and it outranks the rest of this section.

**Eight engine files are modified and uncommitted in the working tree**, carrying three different
agents' changes across several sessions:

```
signal_runner.py · backtest_week.py · backtest_2y.py · omen_bot.py
paper_trader.py · options_sizer.py · stop_rule.py · live_scanner.py
```

One of them changes behaviour **by default**: `DEDUPE_FIRES_ONLY`, defaulting to on.

| | committed engine | working tree |
|---|---:|---:|
| trades | **2,437** | **4,508** |
| $ per session | **$2,678** | **$5,268** |

**A fresh clone of this repo earns half what every number published tonight says.** The A/B
comparisons are unharmed — all arms shared the same base, so directions and differences hold — but
every *level* is roughly double the committed engine's.

**The change itself is legitimate and already priced.** `research/g72_suppress_report.md` documents
it: when the engine looked at a setup and said no, the backtest wrote that refusal down as "this
level is taken" and then threw away the real trade that appeared on the same level a minute later.
`signal_runner._route` already got this right for its own registry. It is a genuine bug fix worth
$549 → $584 a trade, and it doubles the book because it stops discarding real trades.

**It has simply never been committed**, and it has been silently underpinning published figures for
a day. *This is the same failure shape as the mark-file trap: real work, correct work, invisible to
anyone who looks at the repo instead of the disk.*

**Recommended, and left for you because a shipped default is red-lane:** commit the dedupe fix with
its report, then re-run and re-publish the headline figures against a clean tree. Nothing else in
the tree should be committed without review.

### Artifact — **there are no repeats, and that matters**

No generator existed for `omen-71-verdict.html` at all — the page had been hand-assembled. One was
written, so it is reproducible now.

**Zero duplicates.** A stricter scan than the one requested found **0 repeated sentences, 0 repeated
table rows, 0 repeated list items**, and the book behind it has no duplicate trades either — the 67
same-minute pairs are distinct trades off different pivots.

**So the "random repeats" you saw are on a different artifact, and that lead is still open.** Tell
me which page and I will find them; do not assume it was this one.

Two real defects were found and fixed: win rate **49.7% → 49.5%** and index trades **137 → 164**
(137 was a different arm's number pasted into the stack column).

**One thing the fix does not solve:** the page quotes the 29 August book — 2,437 trades, $1,339,000
— while the book on disk now holds 4,508 and $2,634,000. **A $1.29M gap.** The generator hard-reads
a dated snapshot with no freshness check, which is the same failure shape as the bug it just fixed,
one level up. It should either assert the snapshot still matches or print which book it is quoting.

*Report: `research/g82_artifact_cleanup.md`*

### The deck builder — the defect is **five times worse** than reported

The fix landed and survived: selection now carries a stated traded/silent quota per bucket, proved
by `research/test_deck_selection.py`. But the headline number was refuted, and in the harsher
direction.

The report said 5 of your 30 cards were a trade the engine actually took. **That sums to 34 out of
30 — arithmetically impossible.** Recomputed under the report's own rule: **1 of 30.** Four of the
five it counted as "traded" were booked only *after* the engine had already taken a different trade
that session — which is precisely the defect being fixed.

> **One card in thirty showed you the trade the engine actually took.**

*Report: `research/g82_deck_fix.md` — fix survived, numbers refuted.*

### Homework — the master page is built

**55 cards: 40 charts plus 15 mentor-rule ballot lines, across seven sections** — is this an S ·
which signal on this chart · what minute would you enter · does the higher timeframe agree · is
there displacement · where is the stop · the mentor ballot.

**Zero repeats against all 1,677 symbol-days you have judged or been served** — verified the hard
way, by reading card ids out of the shipped HTML rather than trusting the manifest. Save, restore
and export were proven in a real Chrome at phone width, 15 of 15 checks green.

Three caveats worth knowing before you sit down with it:

1. **It links Google Fonts.** Answers and saving are unaffected and it degrades to fallback fonts,
   but it is not fully offline. Being removed.
2. **The entry-minute section shows the whole morning**, including everything after the candidate
   entry. That matches the existing deck standard, but it means those answers carry hindsight and
   cannot later serve as a clean recall baseline.
3. **`probe_chart.py` grew an HOD/LOD rail** whose comment claims every existing caller renders
   byte-identically. That is false — `g71_homework_build.py:264` already passes hod and lod, so
   re-running that builder now draws two extra lines and shifts every candle. Fix before rebuilding
   the older deck.

*`research/probes/omen-master-homework.html` · builder `research/g82_master_homework.py`*

---

## 5. The grill — ANSWERED 2026-08-30, all eight

He answered all eight before bed. **These are ratified decisions, not open questions.** Full record
with his words: `Austin's Vault/Projects/omen-rulebook.md` section "Session 2026-08-30", part 9.

| # | question | his answer |
|---|---|---|
| 1 | The money bar | **Six figures a year.** $100,000 / 252 sessions = **$397 a day, $8,333 a month.** Win rate explicitly demoted: *"our situation has changed, and it's not just about win rate."* |
| 2 | Higher timeframe | **RANK rule.** Of the day's candidates, take the one the higher timeframe likes best, even if it is not first. Not a wait, not a veto. |
| 3 | Displacement | **Measure it, wire only if it separates** his S days from his refusals on the full pooled corpus. Reopens the eight-variable list. |
| 4 | Stops | **Show the number first.** Close-only is NOT re-ratified. It stands only if the A/B supports it. |
| 5 | Instrument | **All three stay open** — shares, options, futures. Trade The Pool shares is the default prop route, but he trades options in his own account. Never present a two-way fork. |
| 6 | Scale-outs | **Fill on touch. RATIFIED.** A profit target is a resting limit order. If the backtest waits for a close, that is a defect to fix, not an arm to measure. |
| 7 | More cards | **Run the free 278 first**, and build more anyway. *"whatever else you want to include on a homework"* — standing permission. |
| 8 | Gate priority | **Green months win.** 25 of 25 is the bar even where a policy makes more money at 22 of 25. |

Two consequences worth stating plainly:

- **The bar moved up 4×.** $397/day against honest fills that may land near $86/day. If the fill
  finding survives its refutation, six figures a year is not reachable on the current engine and
  that becomes the headline of this version.
- **Green months winning makes several "wins" into fails.** Any sizing or policy that reaches
  $397/day at 22 of 25 green months is now a FAIL, not a trade-off. Reports must say so.

Also ratified: **he likes dark artifacts.** Every page he is served is dark-themed from here.

<details>
<summary>The original eight questions with their recommended answers, kept for the record</summary>

**None of these blocked the overnight work.** Every one had a default pre-picked and both arms of
every measurement ran either way.

---

**1. What is the smallest dollars-per-day that makes this worth finishing?**

You have never named one, so there is no way to tell a bad result from a disappointing-but-fine
one. If honest fills land at $100 a day, that is $2,100 a month on a $50k prop account — real
money, small.

- **(a) $100/day — small and real is fine. ← recommended**
- (b) $300/day or the effort is not worth it
- (c) $500/day or stop
- (d) Dollars are the wrong unit; it just has to beat leaving the money alone

*Recommended (a): a prop account funded on a 0% credit line makes small-and-consistent worth more
than large-and-uncertain, and (b) and (c) are both inside the error bar on every measurement this
project has run.*

---

**2. Higher timeframe: a WAIT rule or a RANK rule?** These build completely differently.

- **(a) RANK — of today's setups, take the one the higher timeframe likes best, even if it is not
  first. ← recommended**
- (b) WAIT — skip the 09:30–09:45 signal when the higher timeframe disagrees, take the next one
  that agrees
- (c) VETO — do not trade at all on days the higher timeframe disagrees
- (d) Report it on the card and let me decide in the moment

*Recommended (a): your sentence was "I could have been more selective", which is choosing between
candidates, not refusing a day. (b) is dangerous — 65% of your S entries are before 09:45, so a
wait rule attacks the accuracy gate you are furthest from. (c) is the veto that already ships and
already has no author.*

---

**3. Should displacement become a ninth variable?** You said the eight-variable list was closed.
Then you named displacement in four of nine refusals last night without being asked.

- **(a) Yes — measure it, and if it separates your S days from your refusals, wire it. ← recommended**
- (b) It is already in there as `no_displacement` — check the code matches what I mean before
  adding anything
- (c) No, the list stays closed
- (d) Make it an upgrade (+1) rather than a downgrade

*Recommended (a), but (b) is doing the same work and may be the true answer — `no_displacement`
does exist in the code. If the shipped version does not match your four sentences, that is a bug
report, not a new variable.*

---

**4. If intrabar stops make more money than close-only, do you take it?** The repo says you settled
close-only five times. You said last night you do not remember agreeing.

- **(a) Show me the number, then I decide. ← recommended**
- (b) Close-only regardless of cost — wicks are not evidence
- (c) Take whichever makes more money
- (d) Close-only for stops, intrabar for everything else

*Recommended (a), and the number is being measured now. Note (d) is what you actually described,
and it may simply be right: entries and stops on the close, scale-outs intrabar at market.*

---

**5. Shares or options?** The fork you have not picked, and it costs money either way.

No prop firm on a challenge model allows options — not Topstep, not Apex, not Trade The Pool. The
options-capable desks want $7,500–$12,200 up front. But options are where the best measured numbers
are.

- **(a) Shares, Trade The Pool $50k FLEX Day, $150 risk per trade, 99.6% modelled pass rate.
  ← recommended**
- (b) Options, pay the $7,500 for a real desk
- (c) Index futures via Topstep/Apex — throws away 72% of your trading days
- (d) Wait for the honest-fill numbers, then decide

*Recommended (a) to start: it keeps 100% of your trading days and the entry cost is a challenge fee
rather than five figures. (d) is also fine and costs you a day.*

---

**6. Scale-outs — intrabar at market, confirmed?** You described it clearly and the code may not do
it.

- **(a) Yes — a profit target is a resting limit, it fills the moment price touches it. ← recommended**
- (b) Wait for the candle close on profit-takes too
- (c) First leg intrabar, runner on the close
- (d) Show me the number first

*Recommended (a): it is both what you described and what actually happens with a resting order.
Very likely a straight bug in the backtest.*

---

**7. Do you want to grade about 110 more charts?** The 90% accuracy gate cannot be proved on 30
cards — 34 buys a ±15-point read, and proving 90% needs 141 for ±5 points. But you already have
278 S-days with bars that nobody ever replayed, so the machine half is free.

- **(a) Run the free machine half over all 278 first, then decide. ← recommended**
- (b) Yes, build me 110 more cards
- (c) Lower the gate to something 30 cards can measure
- (d) Stop measuring accuracy, just measure money

*Recommended (a): two minutes of compute, and it may show you do not need to grade at all.*

---

**8. Which gate wins when they conflict?** Taking one trade a day is your stated rule. It breaks
the only gate OMEN currently passes: 25 of 25 green months becomes 22 of 25.

- **(a) Green months win — three red months out of twenty-five fails the prop account regardless of
  the average. ← recommended**
- (b) Dollars win; drawdown is what the risk unit is for
- (c) Green *weeks* is the real gate, not months
- (d) Take more than one trade a day after all

*Recommended (a): a prop challenge is a drawdown test, not a return test, and funding it on a credit
line makes a red month cost more than a flat one.*

</details>

---

## 6. Blockers — ranked by how much real money they hold up

**1. The fill.** If most of the book's edge is a price that printed before the signal existed, every
dollar figure in this repo is void and the honest number may be near zero. Everything else is
downstream. *Being measured now; section 1.*

**2. The live path does not trade this book.** `live_scanner.py:546` promotes to TRADE only on
`grade == "A+"`, and A+ fires **twice in 45,193 signals over two years**. The live system, today,
would trade approximately nothing. Known for days, still there. *Needs a decision, not a
measurement — and it outranks every gate.*

**3. There is no runner in the live path.** The paper trader closes the whole position at 2R.
**94 of your 496 one-a-day trades ran past 2R and those 94 carry 50.1% of every dollar the strategy
makes.** Live books none of it. *One day of work, then a paper week to confirm.*

**4. No prop firm allows options.** The instrument with the best measured numbers has no funded
route under $7,500. *Question 5.*

**5. Accuracy is 53–64% against a 90% gate — and "trade S only" makes it worse.** Restricting to S
collapses green months from 25 to 14, because the engine's S is flat-to-slightly-negative rather
than predictive. The grader is not yet worth routing on.

**6. The legacy A+/A/B/C/X letters were ratified for deletion five sessions ago and are still
there.** The delay is itself the finding.

**7. The deck builder has been showing you the wrong chart.** Of your last 30 cards, 5 were a trade
the engine took, 10 were a different signal on a chart where the engine traded something else, and
15 were charts the engine refused all morning. The selection rule never asks whether the engine took
the signal. *Being fixed now.*

---

## 7. What agents did unattended, and what they did not touch

**Did:** measured, A/B'd, diagnosed, built homework, mined the corpus, wrote reports, proposed
diffs. Every measured claim was handed to a second independent agent instructed to refute it.

**Did not:** grade a chart, invent a rule, merge mentor judgements into your marks, write to any
mark file, commit an engine change, spend money, or serve you a page.

**Model tiering, as you asked** — with one thing that did not work.

The measurement rigs ran on Sonnet. Only the adversarial verification and the design questions ran
on Opus. The cheap mechanical passes were routed to DeepSeek as you asked, **and DeepSeek failed.**

**Your OpenRouter account is out of credit.** Not a broken config — the key is valid, both model
slugs exist, and the account is not rate-limited. It is simply spent:

```
usage $130.14 · request refused 402: "You requested up to 16384 tokens,
but can only afford 12415"
```

You said you had $5 loaded. There is less than a cent of headroom left, which is under one
tool call. Both `deepseek` and `glm` agents are dead until it is topped up at
<https://openrouter.ai/settings/credits>.

Worth knowing about how those agents are wired: `~/.claude/agents/deepseek.md` and `glm.md` carry a
hardcoded OpenRouter key in their frontmatter — the same key as your `OPENROUTER_API_KEY`
environment variable. That is a secret sitting in a file that syncs between your Mac and this box.
Once you top up, move it to an env reference rather than a literal.

Until then the cheap tier is **Haiku 4.5**, which is inside the subscription. It uses fewer credits
than Opus but does not save them the way an outside provider would.
