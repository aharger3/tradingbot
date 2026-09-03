# Re-scored on all 30 answers — and the ranking does not survive

*2026-08-29. Every number here comes from `research/g74_rescore30_score.py`, which reads
your 30 answers, the answer key for the same 30 cards, and the 2-year book. It changes no
engine code and touches no mark file. Re-runnable.*

---

## The short version

**Do not rank the three setups. You cannot tell them apart yet.**

The one-candle rule looks best at 8 out of 10. But at ten cards each, "8 out of 10" and
"6 out of 10" are the same answer wearing different clothes. To actually separate 80% from
60% you would need **82 cards per setup — about 216 more than you have graded.**

What *did* survive is bigger than the ranking, and it is new:

1. **The engine is on time on break-and-retest and about 40 minutes late on the other
   two.** Measured against your own entry minutes, for the first time ever.
2. **There is no such thing as a "BR+OCR" setup in the engine.** The label is on 70% of
   every row in the book and on 29 of your 30 cards. It is not a setup, it is a flag that
   is almost always on.
3. **Nine times out of twelve, the reason you rejected a card is a reason the engine
   cannot compute at all, or computed and got wrong.**

---

## 1. The three setups, scored honestly

| Setup | You said yes | Precision | The honest range |
|---|---|---:|---|
| One-candle rule | 8 of 10 | 80% | somewhere between **49% and 94%** |
| Break-and-retest | 7 of 10 | 70% | somewhere between **40% and 89%** |
| 84% re-entry | 6 of 10 | 60% | somewhere between **31% and 83%** |
| **All 30 cards** | **21 of 30** | **70%** | **52% to 83%** |

Every one of those ranges is 45 to 52 points wide. They all overlap each other almost
completely. Head to head:

| Comparison | Gap | The honest range on the gap |
|---|---:|---|
| One-candle rule vs 84% | +20 points | −19 to +52 |
| One-candle rule vs break-and-retest | +10 points | −26 to +44 |
| Break-and-retest vs 84% | +10 points | −28 to +45 |

Every one of those ranges crosses zero. The one-candle rule being ahead of the 84% rule is
as likely as a coin landing heads twice. **This is one sample of noise, not a ranking.**

**But the premise the batch was built on is still overturned, and that part is solid.**
You suspected the one-candle rule and the 84% rule were broken. Across all 30 cards the
engine got 70% of its S calls right, and the two "broken" setups sit at 80% and 60% —
inside the same band as break-and-retest. **Nothing here says either of them is broken at
finding the setup.** That was the question, and it is answered.

**What would settle the ranking:** 82 cards per setup, so about 216 more than the 30 you
have done. That is seven more homework batches. Before committing to that, read section 3
— there may be a much cheaper measurement worth doing first.

---

## 2. "BR + OCR together" is not a setup, and that is why the combined class looks wrong

You expected the combination to be your strongest class. It scored 6 of 9 — below the
one-candle rule alone. Here is why, and it is not about your eye.

**The label is nearly always on.** In the whole 2-year book:

| | Rows | Carry the BR+OCR flag |
|---|---:|---:|
| Every signal the engine looked at | 134,012 | **93,675 — 70%** |
| Your 30 homework cards | 30 | **29** |

A label on 70% of everything cannot tell two things apart. The 6-of-9 "combined" class
is simply *the break-and-retest cards*, relabelled. The one card in the batch that did
**not** carry the flag was the only card labelled plain "BR". So the comparison you were
shown — 6 of 9 combined versus 8 of 10 one-candle — was break-and-retest versus
one-candle rule the whole time. It was never a combination.

**And you were right about displacement.** On NVDA, 24 June 2025 you wrote:

> *"technically it is an OCR and BR just neither of the parts have displacement"*

That sentence says displacement is required of **each leg**. The engine's combination test
checks three things: did a candle close through the level, is there a lone
opposite-coloured candle nearby, and does its far edge sit on the right side to hold a
stop. **It never checks displacement on either leg.** Not on the break, not on the
one-candle. The word does not appear anywhere in that test.

Displacement *is* checked — once, on the break candle only, as a separate mark against the
trade. Which brings us to the thing that actually matters:

### The flag is not a label. It is a get-out-of-jail card.

The way the grade is built: count the marks against a setup, subtract one if the
combination flag is on, and it is an S if the total lands at zero or below. **So the flag
forgives exactly one fault.**

That is not a footnote. It is how nearly every S gets made:

| | Rows in the book | Reached S |
|---|---:|---:|
| Break-and-retest, flag on | 89,724 | 16,317 (18%) |
| Break-and-retest, flag off | 36,892 | **95 (0.3%)** |
| One-candle rule, flag on | 3,951 | 1,395 (35%) |
| One-candle rule, flag off | 2,858 | **0** |
| 84% re-entry, flag on | 367 | 70 (19%) |
| 84% re-entry, flag off | 220 | **0** |

**A one-candle-rule setup has never once reached S without that flag. Not in 2,858
chances.** Same for the 84% rule. 99.5% of every S the engine has ever called was made
possible by a flag that is on 70% of the time and does not check the thing you said
matters.

**And it shows in your answers.** Splitting your 30 cards by whether the S was clean or
bought with that forgiveness:

| | You said yes |
|---|---:|
| Clean S — no faults at all | **17 of 22 (77%)** |
| S bought by forgiving one fault | **4 of 8 (50%)** |

The gap is 27 points, and at this sample size it is *still* not separable (the honest range
is −8 to +58). But it points the same way as everything else on this page, and it includes
the single most embarrassing card in the batch:

> **AVGO, 3 December 2025.** You rejected it because the retest never happened. The engine
> *agreed* — it raised "no retest" on that exact card, the only one of your twelve reasons
> it got right all day. Then the combination flag forgave it, and the engine called it an
> S anyway.

**In money, though, the flag is free.** Across the book, S trades bought with the
forgiveness made $482 a trade; clean ones made $480. Identical. **So this is a precision
problem, not a dollars problem** — the flag is not costing you money today, it is costing
you the ability to trust the word "S". Fixing it will change which days the engine puts in
front of you, not what the current book earns.

---

## 3. The clock — measured against you, for the first time

You wrote an entry minute on 26 of the 30 cards. Four had none. One, IWM 6 August, reads
"9:%5" — that is a typo and it is left unread rather than guessed.

Taking only the cards you said **yes** to, where the minute is unambiguously the one you
would have entered — 20 cards:

**The engine enters a median of 26 minutes after you would.**

Which sounds bad until you split it by setup, and then it stops being one problem and
becomes a very specific one:

| Setup | How late the engine is | Engine's typical entry | Cards within 4 minutes of you |
|---|---:|---|---:|
| **Break-and-retest** | **median 0 minutes** | 10:08 | **4 of 7** |
| 84% re-entry | median +31 minutes | 10:20 | 0 of 6 |
| **One-candle rule** | **median +41 minutes** | 10:33 | **0 of 7** |

Read that again. **On break-and-retest the engine and you agree on the minute** — three
cards land within one minute, one lands exactly on it. On the other two setups the engine
is *never* on time. Not once. The best it manages on a one-candle-rule card is 12 minutes
late; the worst is 54.

This is the mechanical cause behind the thing that prompted this whole investigation. The
one-candle rule is your most-accepted setup and it barely trades. Now we know one reason:
**by the time the engine finds it, your trade is 40 minutes old.** You enter at 9:38 and
9:43 and 9:45. The engine enters at 10:19 and 10:32 and 10:33.

Two honest caveats:

- **It is not just picking the wrong row.** The engine fires several times on most of
  these days. Even taking the *closest* S signal it printed all day, the median gap to your
  minute is still 16 minutes, and only 8 of 25 cards have an engine signal within 2 minutes
  of you. On two one-candle cards it did print an S at your minute and the card was built
  off a later one — so a little of this is row selection, but most of it is real lateness.
- **The card did not show you an entry.** You were given the chart, the timeframe and your
  six levels, nothing else. So these are your minutes, independently arrived at. That is
  what makes this the first honest read of the engine's timing against you rather than
  against itself.

**This is the cheapest measurement on the board.** You have already produced the ground
truth. Nobody has to grade anything more to find out why the one-candle detector cannot
see a 9:40 setup until 10:20.

---

## 4. Why you said no — and what the engine literally cannot see

Nine cards were rejected, with twelve reasons between them. **The engine agreed with one
of the twelve.**

### The reasons the engine has no way to compute — name these first

| Your reason | Times | The engine's position |
|---|---:|---|
| **Chop** | 3 | **No check exists in the grading path.** |
| **Late** | 2 | **No check exists. There is no clock rule at all.** |
| "A pivot was created, hard to break" | 1 | No check exists |
| "It took too long for the entry" | 1 | Nearest thing counts candles since the break, not clock time — and it did not fire |

**Five of your twelve reasons — chop and late — are things the grader is structurally
blind to.** They are not mis-tuned. They are absent.

**And chop is the worse of the two, because it is already written.** There is a chop rule
in this codebase, built to your own number — *"10 or 11 chop candles is the threshold"*.
It sits in a file the engine never opens. It has been measured, never wired. That is the
same failure this project has hit before: a real rule of yours that exists as code no path
can reach.

**Late has nothing at all.** The session runs 09:30–11:00 and there is no rule anywhere
that says a setup gets less attractive as the morning wears on. Given section 3 — the
engine is systematically 30 to 40 minutes behind you on two of three setups — a "too late"
rule would not just encode a preference. It would catch the timing bug as a side effect.

### The reasons the engine has and got wrong

| Your reason | Times | Engine has the check? | It fired |
|---|---:|---|---:|
| No displacement | 3 | Yes | **0 of 3** |
| Level not respected | 1 | Yes | **0 of 1** |
| No retest | 1 | Yes | **1 of 1** ✓ |

**Displacement is the one to look at.** It is the reason you gave most often, the engine
owns a check for it, and it missed all three. Two of those three cards you described in
your own words as a displacement failure of *both legs* of a combination — which, per
section 2, is a thing the combination test does not look at even in principle.

And the one check that got it right, on AVGO, was overruled by the flag.

---

## 5. Two things for the ballot — questions, not changes

Nothing in this section has been built. Both need your yes or no first.

### (a) Retest tolerance — measured in cents

> *"9:33 can be a great break of pdl but the retest missed by a few cents"* — AVGO,
> 3 December 2025

Measured on that exact chart: the break at 9:33 was real, and the closest price ever came
back to yesterday's low afterwards was **73 cents** — on a $380 stock, so about a fifth of
one percent. The engine's own "close enough to count as a touch" allowance was **46 cents**
at 9:33, and it tightens as the morning settles down — 24 cents by 10:00, 15 cents by 11:00.
Your 73-cent miss is outside it at every point in the session.

So: **the existing unit already covers what you are describing, and it agrees with you.**
73 cents is outside 46 cents, the engine called it "no retest", and you called it "missed
by a few cents". Same verdict, same order of magnitude. **You are not asking for a tighter
tolerance — you are confirming the one that exists.** The bug on that card was never the
tolerance; it was the flag forgiving the correct answer.

One thing worth your ruling, though: **you think in cents and the engine thinks in
percentage of recent range.** On AVGO those happened to land close together. On a $20 stock
they would not. **Ballot question: when you say "a few cents", do you mean actual cents
regardless of the stock's price, or do you mean it in proportion to how much the stock has
been moving?**

### (b) Does "S" mean "I would take it"?

> *"10:09 would never trade because look how the candles are but jsut good for you to
> know"* — ACHR, 13 April 2026. **You graded it yes.**

If S and tradeable are different things, then every recall number this project has ever
published is counting the wrong one.

Scanning all 30 notes, **it happens twice, and in both directions:**

| Card | Grade | What you wrote |
|---|---|---|
| ACHR 13 Apr 2026 | **S** | "would never trade" |
| NVDA 24 Jun 2025 | **not S** | "really good a trade i wish it was an S" |

One card is an S you would not take. The other is a trade you would take that is not an S.
They are the two halves of the same split, and they are only 2 of 30 — so this is a real
distinction you make, but a rare one, not a wholesale problem with the grade.

There is a third case that muddies it and is worth your eye: on **TSM, 26 November 2025**
you wrote *"i see what the entry would be but hard to get past the green candle at 9:35"* —
the same feeling as the ACHR card, the setup is there but you would not take it — and this
time you graded it **no**. So the same thought produced an S on one card and a not-S on
another.

**Ballot question: should the homework ask two questions instead of one — "is this an S?"
and "would you take it?" — or is a trade you would not take simply not an S?** One extra
tap per card, and it would settle whether 2 cards in 30 is the real rate or an artefact of
having only one box to tick.

---

## What is solid and what is not

**Solid:**

- The engine's overall precision on its own S calls: 21 of 30, 70%.
- Neither the one-candle rule nor the 84% rule is broken at finding setups.
- The BR+OCR flag is on 70% of the book and 29 of your 30 cards; no setup except
  break-and-retest has ever reached S without it, in 3,078 chances.
- The flag forgives exactly one fault, and 99.5% of all S grades were made that way.
- The combination test checks no displacement on either leg.
- The engine is a median 0 minutes off you on break-and-retest and 31 to 41 minutes late on
  the other two, never once on time on either.
- Chop and late are not checks the engine has. The chop rule exists in the codebase and no
  path reaches it.

**Not solid — do not spend money on these:**

- The 80 / 70 / 60 ranking between setups. One sample of noise.
- The 77% vs 50% precision gap between clean S grades and forgiven ones. Points the right
  way, but 8 cards cannot carry it.
- Anything about the four cards with no entry minute, and anything about IWM 6 August,
  where the minute is a typo and was left unread.

---

*Script: `research/g74_rescore30_score.py`. Numbers: `research/g74_rescore30.json`.
Mark file read-only and unchanged. The recall gate, the universe test, the stop-fill test
and the runner-stop test were all run after this work and are all green.*
