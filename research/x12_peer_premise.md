# X12 — Is the 2R premise even right? What Scarface and Jdub actually do

**Date:** 2026-08-28 · **HEAD at measurement:** `c089b26b` · **Substrate:**
`research/g3_arm_ow1.json` (1,017 traded rows, 2024-08-21..2026-08-21, 500 sessions)
plus `discord_data/*.json` (15,749 messages authored by TonyMontana/Scarface and Jdub)
and `research/scarface-rules-videos.md` / `-coaching-bonus.md` (TRADER_SAID corpus rows).

**Scripts that produced every number here** (all read-only, stdlib only):

| script | what it answers |
|---|---|
| `research/x12_mine_peers.py` | pattern census over the scraped channels |
| `research/x12_peer_stats.py` | peer exit/entry behaviour taxonomy |
| `research/x12_weekly_durability.py` | OMEN green weeks / green days / tail concentration / sizing |
| `research/x12_target_math.py` | fixed-target-vs-mean arithmetic; engine's planned R:R |
| `research/x12_selectivity.py` | selectivity arms + Scarface's own day rules on the book |
| `research/x12_scarface_exit.py` | Scarface's published scale ladder applied to OMEN's book |

---

## VERDICT IN ONE LINE

**Scarface's "2R" is a TARGET, not a mean.** He states his own operating point in his own
words as **"50 to 60% win rate… but my risk to reward went down to 2R"** — and OMEN is at
53.4% win rate with a planned R:R of exactly **2.000** on every trade. On the arithmetic,
**a fixed 2R target cannot produce a mean R of 2.0 at any win rate below 100%**, so the
money gate as written (`mean R >= 2.0`) is not a description of what these two traders do.
It is unreachable by their method, and applying **their own published exit ladder to OMEN's
own book cuts the mean from +0.9551R to +0.5205R.**

---

## 1. THE PRIMARY SOURCE — Scarface says the number out loud

`research/scarface-rules-videos.md:8859` (mastermind-5-0 Lesson 4, [5239s–5276s]):

> "In the beginning stages, I would never take the high of day scale, right? I would take
> whatever my main profit target was. And my win rate was pretty low, right? **My win rate
> went down to like 40%. But my risk to reward increased to 2.5 to 3R…** However, when I
> implemented selling at the actual high of day, **my win rate increased to 50 to 60%,
> right? But my risk to reward went down to 2R.**"

That single sentence settles the lane. He **chose** the 50–60% / 2R operating point over
the 40% / 2.5–3R one. His "2R" is the **reward:risk of the scale**, and it is the number he
traded *down* to.

Supporting rows, all `TRADER_SAID` class:

| where | quote | what it establishes |
|---|---|---|
| `scarface-rules-videos.md:9100` | "our profit target **needs to be at least a two or [2R] multiple**" | 2R is an entry-side **requirement on the target**, not an outcome |
| `scarface-rules-videos.md:8834` | "When I take my first scale, **my first high of day scale may not be two R**… And that's fine" | he *breaks* the 2R rule routinely on the scale |
| `scarface-rules-videos.md:9097` | "nobody listens to me because they're like oh the risk to reward is off on high day scale tony **it's not two r** so therefore i can't take high day scale… **I know it's not a two r risk reward but here's the thing**…" | he argues *against* treating 2R as a hard gate |
| `scarface-rules-videos.md:9099` | "does this mean we're limiting our potential profit factor here sure we're limiting it a little bit but **at the same time we're increasing our win rate**" | explicit: he trades mean-R away to buy win rate |
| `scarface-rules-coaching-bonus.md:68` | "**2R must be achievable within the stock's average daily range.** If target is $15 but stock moves $2/day — skip." | 2R is a **pre-trade feasibility filter** on the distance to the level |
| `scarface-rules-videos.md:2611` | "If you take the immediate retest and there isn't a high of day point to actually go off of **usually 2R is a good rule of thumb**" | 2R is the *fallback target* when no level exists |

**Nowhere in 5,460 provenance-tagged corpus rows or 15,749 peer Discord messages does
either trader state a per-trade mean R.** Not measured by them; not claimable by us.

---

## 2. HOW THEY ACTUALLY EXIT — scale most off at the level, ride a small runner

`research/scarface-rules-videos.md:2599–2606` (boot-camp Day 8, "Scaling With Options") is
the published ladder:

- "Taking partial profits at key levels and then **using the rest as a trailer position**"
- "**75% of your contracts as a day trade**, your initial scale, just rule of thumb…
  **about 25% of the position is going to be letting it ride**"
- First scale minimum **1.5 R:R**; then **1.50–1.75R → 60% off · 1.75–2.00R → 70% off ·
  ≥2.00R → 80% off**
- Runner stop: "as the trailer keeps running up… where that market structure would break"
- "**Your trailers will end up making way more money than the original position**… this is
  mostly true for me as well" (`:8836`)

Discord confirms this is what he does live, not just what he teaches
(`x12_peer_stats.py tax`, over 8,753 Scarface / 6,996 Jdub messages):

| behaviour | SCARFACE | JDUB |
|---|---:|---:|
| trailer / runner language | **144** | 25 |
| partial scale-out | 71 | 15 |
| full exit at target | 35 | 10 |
| stopped out | 76 | 7 |
| add to position | 23 | 9 |
| explicit min-R:R filter at entry | 2 | 0 |
| **no trade / skip** | **145** | 2 |

Live examples of the tail (`discord_data/scarface-alerts.json`): "25R on last trailers"
(2024-10-24), "45R trade on 5 trailers left" (2025-03-10), "12R trade for trailers"
(2025-08-06), "14R trade for final trailers" (2025-08-07), "aapl solid trade around a 9r
multiple for our trailers" (2025-09-16), and the clearest one (2026-04-22):

> "APPL majority of these profits came from **40 cons rather than a 150 position size**.
> Goes to show how important trailers can be, in this example **they made 3x more than
> original scale**."

**How they exit:** scale 60–80% off at the first key level (HOD/LOD/PMH), hold 20–25% as a
structure-trailed runner, cut the runner on a market-structure break. **How long:** Scarface
routinely posts "calling it a day, less than 30 minutes" — the base trade is minutes; the
runner can go overnight or multi-day. **How many:** `:8861–8863` — *"I'm able to take three
trades maximum per day"*, *"75 to 80% of the time… I'll only be taking one trade a day"*,
*"if I lose two trades in a row, call it quits… on that day."*

---

## 3. THE SCALE-IN QUESTION — Austin is right, with one asterisk

`x12_mine_peers.py --dump scale_in` and the full add-to-position dump find **32 messages in
15,749** that mention adding to a position. Classified by hand, every single genuine one is
a **SWING** trade on the 1-hour / 4-hour / daily timeframe with the same structure:
**"starter position → add on dips."** That is **averaging DOWN into drawdown**, the exact
opposite of W13's scale-in-to-a-winner arm.

> "REMEMBER **HOW WE SWING TRADE IS DIFFERENT THAN NORMAL TRADES**. You must start with
> starter position, than size up as trade either works or develops. You must be able to
> allow **drawdown 50–60%**." — Scarface, 2024-09-12

> "I have a starter in TSLA. Very small size **will look to add on major dips**. As I
> mentioned this is based off the **higher timeframes**." — Jdub, 2024-11-12

> "Took a starter on MSFT… **Will add on all dips**. Down towards 446. **This is a 1 hour
> setup**." — Jdub, 2024-12-16

**Intraday adds to a winner: zero executed instances found.** The only intraday candidate is
one unexecuted musing — *"Potentially could add more if we break and retest hod"*
(2024-10-22) — and no follow-up alert confirms it.

**So: Austin's objection to W13 is factually correct on the 09:30–11:00 instrument.**

**What they do instead — and W13's arm was proxying for it.** W13's scale-in wins by
concentrating exposure into the trades that keep going. Scarface gets the same tail exposure
by **shrinking the base instead of growing the position**: 75–80% comes off at the first
level, and the surviving 20–25% is the only thing left when the move extends. Same
asymmetry, opposite mechanism, and it costs mean R rather than buying it (§5).

The other two candidate levers from the brief:

- **(a) higher win rate from better entries** — *partly*, and he says so: the HOD scale
  moved him from 40% to 50–60%. But 50–60% is **where OMEN already is** (53.4%).
- **(b) selective sizing** — he sizes by conviction, but the corpus does not give a
  reproducible ladder. Measured on OMEN's book (`x12_weekly_durability.py`), risk-weighting
  by Austin's `sgrade` moves mean R per unit risk from +0.9551 (flat) to **+1.1693**
  (S 3x / A 1x / C 0x). Real, well outside the ±0.0095R A/B bar — **and still under 2.0.**
- **(c) they do not measure mean R the way this project does** — **CONFIRMED.** They report
  a **daily** win rate and a **risk-to-reward**, never a per-trade mean R.

---

## 4. THE 52-GREEN-WEEKS POINT — and OMEN's weekly durability

**"52 green weeks" does not appear anywhere in the scrape.** What does appear:

- Jdub, 2025-02-25: *"Ended in over $6K in drawdown last week and had **my first red week
  in over 6 months**."*  (≈26 green weeks in a row, not 52)
- Jdub, 2026-03-25 (video title): *"How I Lost $7800 This Week (**FIRST RED WEEK OF THE
  YEAR**)"*
- Jdub, 2025-10-22: *"**Red week for me so far.**"*
- Scarface, 2024-07-25: *"**Tougher week for me**… probabilities not being in my favour"*

So the honest version of Austin's memory is: **Jdub has claimed one red week per ~6–12
months.** Scarface makes no weekly-streak claim at all; his claims are **monthly dollars and
a DAILY win rate.**

**OMEN's book at all three grains** (`x12_weekly_durability.py`):

| grain | green | total | rate | worst bucket |
|---|---:|---:|---:|---|
| **WEEK** | **89** | **105** | **84.8%** | 2025-W37, −6.60R |
| **DAY** | 278 | 415 | 67.0% | 2026-03-30, −4.30R |
| MONTH | 23 | 25 | 92.0% | 2025-06, −5.63R |

A weekly gate is **harder**, not easier: 16 red weeks against 2 red months. The engine
survives monthly durability partly because a month absorbs a bad week.

**And the number Austin has been comparing against is the wrong one.** Scarface's headline
"88% daily winrate", "100% daily winrate", "85% daily win rate" are **DAILY** figures.
OMEN's daily figure is **67.0%** (278/415), and **0 of 25 months** are 100% green-day.
OMEN's per-trade 53.4% has been being compared to a peer *daily* rate — apples to oranges in
both directions.

**Their per-trade win rates, where they state them, are not above 60%:**

- Jdub, YouTube title 2024-10-02: *"I made $30K in one month trading with a **47% win
  rate**…here's how"*
- Scarface, 2025-05-30: *"This week took 4 trades in total. 2 winners, 2 losers. Winners =
  $37k, Losers = $6.7k, Total = $30k… even in a choppy market with a **50% win rate** this
  week was able to come out green."* — win/loss size ratio **5.5 : 1**
- Scarface, 2024-11-30 (his best month ever): *"$220,000 Month. 16 total trading days, 2 red
  days, 14 green days. **79% win rate with a 3.4R multiple.** In full transparency these
  results are the BEST I've ever had. **On average my winrate is lower.**"*
- Scarface, 2025-11-28: *"$238,000 / **88% daily winrate** / **3.5 R/R**"* — note he labels
  it **R/R**, a ratio, next to a **daily** win rate.

**Austin's hypothesis — "it might be because their winrate is significantly above 60
percent" — is refuted by their own posts.** Their per-trade win rate is 47–60%. The mean-R
they claim comes from the **runner tail**, not the hit rate.

---

## 5. THE ARITHMETIC THAT KILLS THE GATE

With a **fixed target T** and a 1R stop, mean R = `p·T − (1−p)` (`x12_target_math.py`):

| fixed target | win rate needed for mean R = 2.0 |
|---|---|
| 2.0R | **100.0% — impossible** |
| 3.0R | 75.0% |
| 4.0R | 60.0% |
| 5.0R | 50.0% |

And at Austin's own ≥55% win-rate floor: **T=2R → mean +0.65R**, T=3R → +1.20R,
T=4R → +1.75R, T=5R → +2.30R.

**OMEN already plans exactly 2R.** Over 1,017 traded rows the planned R:R from
`entry/stop/target` is **mean 2.000, median 2.000, p10 1.988, p90 2.000** — every trade is
laid out at a 2R target. The engine is not failing the 2R rule; it is **passing** it, and the
gate is then asking the *mean* to equal the *target*.

**What would actually be required.** At the book's own 53.4% win rate and its −1.000R
average loss, the average **winner** must rise from **+2.662R to +4.619R** (a 74% increase)
for mean R to reach 2.0. Even at a 70% win rate the average winner must be +3.29R. Selection
does not move the average winner; only holding longer does.

**Scarface's own ladder, applied to OMEN's own book** (`x12_scarface_exit.py`):

| arm | WR | mean R | total | green wk | green mo |
|---|---:|---:|---:|---:|---:|
| **A — shipped OMEN (100% rides to exit)** | 53.4% | **+0.9551** | +971.4R | 89/105 | 23/25 |
| B — Scarface ladder, scale at 1.50R | 53.4% | **+0.5205** | +529.4R | 81/105 | 22/25 |
| B — Scarface ladder, scale at 2.00R | 53.4% | +0.5061 | +514.7R | 84/105 | 22/25 |
| C — hard exit at the 2R target, no runner | 53.4% | +0.3939 | +400.6R | 78/105 | 22/25 |

*(Caveat, stated in the script: `g3_arm_ow1.json` carries no max-favourable-excursion, so a
scale is only assumed filled on trades whose final r already exceeded the scale level.
Trades that finished below it are left untouched, which understates arm B's win rate.)*

To remove that caveat entirely, the **physically impossible ceiling** — assume all 1,017
trades touched a 2R scale, giving a 100% win rate — yields **mean R +1.7910**. **Still below
2.0.** Because 80% of the position is capped at 2R by construction, the 80/20 ladder can only
average 2.0R if the 20% runner leg *also* averages exactly 2.0R with zero losers.

**Selectivity cannot rescue it either** (`x12_selectivity.py`, same book, flat 1R risk):

| arm | n | WR | mean R | green wk | green mo |
|---|---:|---:|---:|---:|---:|
| A0 shipped, all trades | 1017 | 53.4% | +0.9551 | 89/105 | 23/25 |
| A1 first trade of the day only | 415 | 58.1% | +1.0527 | 81/105 | 23/25 |
| A3 sgrade S or A only | 379 | 58.8% | +1.0926 | 85/99 | 22/25 |
| **A4 sgrade S only** | 128 | **66.4%** | **+1.2829** | 55/73 | 23/25 |
| A6 09:30 slot only | 564 | 59.6% | +1.0635 | 86/101 | **24/25** |
| S1 max 3 trades/day *(his rule)* | 883 | 54.5% | +0.9514 | 87/105 | 23/25 |
| S2 two losses in a row → done *(his rule)* | 960 | 54.0% | +0.9650 | 87/105 | 23/25 |

The best arm on the board — S-grade only, 128 trades — is **+1.2829R with a 95% CI of
[+0.926, +1.640]**. Its **upper bound is below 2.0**. Scarface's own day-management rules
move the mean by ≤ +0.01R. Nothing on the selection side reaches the gate.

*(Note on error bars: the ±0.0095R figure is the paired A/B bar on this book. The CIs above
are on an absolute subset mean, which is legitimately wider — `sd/√n` is printed per arm by
the script.)*

---

## 6. WHERE THE 2.0R GATE ACTUALLY CAME FROM

`Austin's Vault/Projects/omen-rulebook.md:207–216`, in Austin's own words:

> "Scarface and Jdub every single week are green, but **I'm not sure how accurate they are**
> … How about every month green? … **I think** the six figures **should be a correlation
> with** average trade at 2R, **which may or may not correlate to the winrate number**"

The gate was Austin's own inference from a six-figure month, hedged twice in the sentence
that created it. Neither trader ever said "my mean R is 2.0." What Scarface said is *"our
profit target needs to be at least a two R multiple"* — a target — and *"my risk to reward
went down to 2R"* at a 50–60% win rate.

Austin's own rulebook already contains the corrected version, at `:530` and `:537`:

> **b4.** "its about **sizing for the mean 2rr**, so if there are no other levels to target,
> or its not an s trade to begin with, harder to trade."
>
> **c7.** "no more looking, only managing a **10 percent position** most of the time"

A 10% runner is Scarface's 20–25% runner. The rulebook is already describing the peer method
correctly; only the *gate* mistranslated it.

---

## 7. THE PARAGRAPH FOR AUSTIN

Your 2.0R gate is a **mean** and their 2R is a **target** — that is the whole discrepancy,
and it is not close. Scarface says it in his own words: *"my win rate increased to 50 to 60%,
but my risk to reward went down to 2R"* — he **traded away** the 2.5–3R multiple to buy the
higher hit rate, and 50–60% is exactly where OMEN already sits (53.4%). Their published win
rates are 47% (Jdub) and 50% (Scarface's own choppy week), not "significantly above 60";
their headline 85–100% figures are **daily**, and OMEN's daily figure is 67.0% (278 of 415
days). They never state a per-trade mean R anywhere in 15,749 messages — they state a
risk-to-reward and a daily win rate. And the arithmetic is closed: with a 1R stop and a fixed
2R target, mean R = 3p−1, so **mean R 2.0 requires a 100% win rate.** OMEN already plans
exactly a 2.000 R:R on all 1,017 trades and realizes +0.9551R — those two facts are
consistent, not a failure. Applying **their** ladder (60–80% off at the first level, 20–25%
runner) to **your** book cuts the mean to **+0.5205R**, and even the impossible ceiling where
every trade touches a 2R scale and nothing loses tops out at **+1.7910R**. To hit a true mean
of 2.0 at your current win rate the average winner must go from +2.662R to **+4.619R**, which
is not a grader problem and not a selection problem — the best selection arm on the book
(S-grade only) is +1.2829R with a 95% CI topping out at +1.640. So: **you were right that
W13's scale-in is not what they do** (32 add-mentions in the scrape, every genuine one a
swing "starter → add on dips", i.e. averaging *down* on the 1H/4H — zero intraday adds to a
winner), and you are right that adding money is a different system. But the thing they do
instead is not a mean-R lever either: it is a **win-rate and smoothness lever** that costs
mean R. The honest gate that matches what these two actually produce is **"≥60% win rate at a
≥2R planned target, every week green"** — which reframes the work as *raise the hit rate and
tighten the weekly tail*, not *raise the mean to 2.0*. On that gate OMEN today reads 53.4% /
2.000 planned / 84.8% green weeks, and the S-only slice reads 66.4%. **Changing the money
gate is a RED action in `DIRECTION.md` — it needs you, not an agent.**

---

## What is NOT measured here

- **Their true per-trade distribution.** Neither trader publishes a trade log. Everything in
  §4 is their self-report, and self-reports on a paid community are marketing-adjacent. The
  47% and 50% figures are the *low* ones they chose to publish, which makes them the more
  credible ones; the 100%-daily-winrate months are the least credible.
- **What OMEN's mean R would be with a real runner.** `g3_arm_ow1.json` has no
  max-favourable-excursion field, so the 244 sub-target wins (avg +1.134R, 17.1 bars) cannot
  be re-simulated as "held longer". That needs a bar-level replay, not this book.
- **Whether a ≥2R-level-distance entry filter helps.** Rulebook b4 names it; every trade in
  this book already has a 2.000 planned R:R, so the filter is already binding and cannot be
  A/B'd on this substrate.

---

## Reconciling with the standing numbers

The standing fact reads "money 53.2% and +0.957R" on 1,016 traded rows. `g3_arm_ow1.json`
carries **1,017**. Three defensible win rates come off the same file and all are reported
above so nothing here silently contradicts a published figure:

| definition | value |
|---|---|
| `out == "win"` / all traded (538/1017) | 52.9% |
| `win / (win + loss)`, scratches excluded (538/1012) | **53.2%** — matches the standing figure |
| `r > 0` / all traded (543/1017) | 53.4% — used in the arm tables above |

Mean R over all 1,017 traded rows is **+0.9551**; the standing +0.957 is the same book at
1,016 rows. No contradiction, one extra row.
