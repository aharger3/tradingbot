# Displacement is already a variable — and the shipped version is a pure recall tax

Measured 2026-08-30. Script: `research/g81_displacement.py`. Full machine-readable output:
`research/g81_displacement.json`. Run it with `python research/g81_displacement.py`
(about six minutes; it replays all 134,012 signals in `research/bt2y_trades.json`
against the archive bars).

**Read-only over every mark corpus.** The 30 fresh judgements and all nineteen other
mark files were opened for reading only, through `research/marks_pool.py`. Nothing under
`research/marks/` was written, and `research/downgrade.py` is untouched — every change
below is proposed, none applied.

---

## The headline

Displacement is **not a new rule and must not be built as one.** It is already variable
number one of the eight in `research/downgrade.py`, ratified over a year of ballots
(rule ballot batch 01, question 18, `br-needs-displacement`, answer "tweak"). So the
question is not whether to add it. The question is whether the shipped code measures the
thing Austin means by the word, and the answer is no:

> **The shipped displacement check fires on half the book (49.8%), removes 13.4 points of
> recall on Austin's own S days, removes exactly the same 12.0 points on the days he
> refused, and buys +0.0136R. It is the single most expensive downgrade in the ladder and
> it separates nothing.**

The trip rate is 49.8% — inside the 2%–60% band this project screens on, but at the top of
it, and that number alone is not the problem. The problem is what it costs:

| | days he graded S | days he refused | gap |
|---|---|---|---|
| the book contains an S-graded signal, **displacement check off** | 76.6% (206/269) | 75.2% (358/476) | +1.4 pp |
| the book contains an S-graded signal, **shipped check on** | **63.2% (170/269)** | **63.2% (301/476)** | **−0.0 pp** |

Switching it on takes 36 of his S days off the board and 57 of his refusals, and moves the
gap between the two groups from +1.4 points to zero. The money it buys for that:
the traded S bucket goes from +0.4702R to +0.4838R, **+0.0136R**, against a standing error
bar of ±1.5799R. That is not a small win, it is no win.

---

## What the shipped code actually does, and what he actually says

```python
def no_displacement(bars, i, level, is_long):
    br = _break_bar(bars, i, level, is_long)   # last close through the level, 30 bars back
    if br is None: return True                 # "never broke with conviction"
    avg = mean body of the 10 bars before the break
    return _body(bars[br]) < 1.5 * avg         # DISP_BODY_MULT
```

It compares the **body size** of the breaking candle to the bodies just before it. After it
finds the break bar it never looks at the level again.

Austin used the word six times on 2026-08-29, and every one of his references is to
*distance from structure*, never to a candle's size:

> **AMD 2025-09-08** (refused): *"10:37 but really no displacement from the original candles
> so i have to downgrade"*
>
> **NVDA 2025-06-24** (refused): *"really good a trade i wish it was an S but it didnt
> displace from that wick, but technically it is an OCR and BR just neither of the parts
> have displacement"*
>
> **QQQ 2025-12-22** (refused): reason filed as `no_displacement`, `chop`
>
> **MSFT 2025-08-29** (took it): *"BR OCB confluence, not perfect because no displacement
> but you get a +1 9:38 is the entry"*
>
> **SPY 2026-06-17** (took it): *"your s is good too but its tight on if theres displacement"*
>
> **QQQ 2024-08-26** (took it): *"a break retest with no dispacement happens at 9:45, its
> not of the level just the wicks at the beginning of the day"*

"from the original candles" · "from that wick" · "not of the level just the wicks". Three
separate references, all to separation between price and a structure.

The mentor corpus gives the same definition in one sentence, and it is a distance
(`research/corpus_sf/mentor_rules.jsonl`, cluster SF063, already cross-referenced in that
file to *"ballot q18 — no displacement is a downgrade"*):

> **Neto:** *"We usually are looking for a break of a key level, some displacement
> (**actual separation from the candles to the key level**), then the retest and lastly
> strong reaction on the key level"*

and two more that agree:

> **Neto** (SF055): *"I'm not a big fan of immediate retest because I like to have
> displacement and then the retest of my key level or relevant area"*
>
> **Lauren** (SF050): *"I only took the trades when there was strong displacement and strong
> price action above/below the range"*

**Nobody in the corpus defines displacement as a fat candle.** Four independent statements
define it as separation from the level. The shipped implementation cannot see separation.

---

## The four definitions measured

| | what it measures | no break found |
|---|---|---|
| **shipped** | break candle body ≥ 1.5× the average body of the 10 bars before it | trips |
| **separation** | furthest price got past the level between the break and the entry bar, in average candles (ATR) | trips |
| **separation, neutral** | same, but "no break found" is not a failure | does not trip |
| **both parts** | separation on the break leg **and** on the one-candle-rule candle's own edge — his *"neither of the parts have displacement"* | trips |

The separation threshold is a guess, exactly like every constant in `downgrade.py`. It was
picked **before** looking at any result, not fitted: this project's one tolerance unit is a
quarter of a candle's range, so "actual separation" has to clear the noise by a clear
margin, and one whole average candle of clear air is the defensible pick. The whole
0.25–3.0 range is reported below so the sensitivity is visible.

### Trip rates first, as this project has learned to

Over all 134,012 signals:

| definition | trips |
|---|---:|
| **shipped** | **49.8%** |
| — of which the "no break bar found" branch | 1.7% |
| — of which genuinely a thin break candle | 48.1% |
| separation @ 1.0 candle | 16.1% |
| separation, neutral @ 1.0 | 14.4% |
| both parts @ 1.0 | 25.8% |

No red flag at either end: nothing here is a branch that can never be true, and nothing
trips on everything. For scale, the current book's other variables run
`counter_trend_not_respected` 89.8%, `level_not_respected` 67.0%, `stale_retest` 0.4%.
**Shipped displacement is the third-most-trigger-happy of the eight.**

The separation sweep, so the threshold choice is not hidden:

| separation required | trips | neutral | both parts |
|---|---:|---:|---:|
| 0.25 candles | 1.8% | 0.1% | 1.8% |
| 0.50 | 3.2% | 1.5% | 3.4% |
| 0.75 | 7.4% | 5.6% | 10.5% |
| **1.00** | **16.1%** | **14.4%** | **25.8%** |
| 1.25 | 29.5% | 27.7% | 45.1% |
| 1.50 | 45.7% | 43.9% | 62.5% |
| 2.00 | 74.1% | 72.4% | 84.9% |
| 3.00 | 96.4% | 94.7% | 98.3% |

---

## Does any of them separate his S days from his refusals? No.

Scored against the canonical pool built by `research/marks_pool.py` — 1,178 judged
symbol-days, 309 S and 560 refusals, of which the book has signals on **269 S days and 476
refusals**. Full pooled corpus, not the 30 cards.

At one candle of separation, day-level (does the day contain any signal with displacement
present):

| definition | his S days | his refusals | gap | 95% CI | Fisher p |
|---|---:|---:|---:|---|---:|
| shipped | 93.7% | 94.7% | **−1.1 pp** | [−4.6, +2.4] | 0.620 |
| separation | 99.6% | 99.6% | **+0.0 pp** | [−0.9, +0.8] | 1.000 |
| separation, neutral | 100.0% | 99.8% | **+0.2 pp** | [+0.0, +0.6] | 1.000 |
| both parts | 99.3% | 98.5% | **+0.7 pp** | [−0.9, +2.1] | 0.500 |

Signal-level, the same story: the trip rate on his S days is 46.5% and on his refusals
48.1% for the shipped check — a 1.6-point gap on 269 versus 476 days.

Swept across every threshold, 27 cells, exactly **one** lands under p = 0.05 (separation at
2.0 candles, +5.9 points, p = 0.041) and its two neighbours at 2.5 and 3.0 both go
*negative*. One significant cell in 27 is what chance produces. **It is a fishing artefact
and must not be quoted as a result.**

The grade-level version — which is the one that matters, because the variable is not the
product, the grade is:

| definition | S-graded signal on his S days | on his refusals | gap | Fisher p |
|---|---:|---:|---:|---:|
| **displacement off entirely** | **76.6%** (206/269) | 75.2% (358/476) | **+1.4 pp** | 0.722 |
| shipped | 63.2% (170/269) | 63.2% (301/476) | −0.0 pp | 1.000 |
| separation | 74.3% (200/269) | 74.4% (354/476) | −0.0 pp | 1.000 |
| separation, neutral | 74.7% (201/269) | 74.4% (354/476) | +0.4 pp | 0.931 |
| both parts | 73.2% (197/269) | 71.0% (338/476) | +2.2 pp | 0.553 |

Every gap is inside its own noise. The only column that moves is the recall column, and it
moves **down**.

---

## The money, and it is a tie four ways

Over the 4,508 traded signals, mean R of trades where displacement is present versus where
it trips, at one candle of separation:

| definition | present | tripped | delta | 95% CI | verdict |
|---|---|---|---:|---|---|
| shipped | n=2140, +0.5568R, 60.8% win | n=2368, +0.6091R, 58.2% win | **−0.0522R** | [−0.162, +0.051] | **inside the error bar — a TIE** |
| separation | n=4091, +0.5876R, 61.5% win | n=417, +0.5517R, 38.6% win | **+0.0359R** | [−0.221, +0.280] | **TIE** |
| separation, neutral | n=4295, +0.5992R, 60.7% win | n=213, +0.2834R, 34.3% win | **+0.3158R** | [+0.018, +0.588] | **TIE** (inside ±1.5799R) |
| both parts | n=3708, +0.5986R, 62.8% win | n=800, +0.5177R, 43.9% win | **+0.0809R** | [−0.092, +0.247] | **TIE** |

Every arm is inside the ±1.5799R error bar. **All four are ties. There is no money finding
here.**

### But there is one real, very large effect, and it nets to zero

Look at the win rates. The separation definition sorts them hard and the shipped one does
not:

| definition | win rate, displacement present | tripped | gap | Fisher p |
|---|---:|---:|---:|---:|
| **shipped** | 60.8% | 58.2% | +2.6 pp | 0.073 |
| **separation** | 61.5% | 38.6% | **+22.9 pp** | 3.1 × 10⁻¹⁹ |
| separation, neutral | 60.7% | 34.3% | +26.4 pp | 5.4 × 10⁻¹⁴ |
| both parts | 62.8% | 43.9% | +18.9 pp | 1.8 × 10⁻²² |

A 23-point win-rate difference at p = 3 × 10⁻¹⁹ is not noise. And it earns nothing, because
of the arithmetic this project already knows — mean R = w·T − (1−w):

| separation @ 1.0 | n | win rate | mean **winner** | mean **loser** | mean R |
|---|---:|---:|---:|---:|---:|
| present | 4,091 | 61.5% | **+1.562R** | −0.971R | +0.5876 |
| tripped | 417 | 38.6% | **+3.010R** | −0.994R | +0.5517 |

Trades that never separated from the level win far less often and, when they win, win
nearly twice as big. **Displacement measured as separation is a style dial, not an edge:**
it trades win rate against winner size at a fixed expectancy. That is a real finding and it
is exactly the shape the mean-R arithmetic predicts.

One confound to name honestly: the low-separation bucket is heavily enriched in one-candle-rule
entries (94 of 417, 22.5%, against 47 of 4,091, 1.1% in the other bucket). For a
one-candle-rule trade the stop is the candle's own wick, not a broken key level, so
"separation from the level" is measuring something different there. Part of that 23-point
win-rate gap is the separation check quietly acting as a setup-type detector.

---

## The six cards, one at a time — this is where the implementation fails outright

Each row is the engine signal nearest the minute he named, at one candle of separation.

| card | he said | his minute | engine's signal | separation | shipped says | book grade |
|---|---|---|---|---:|---|---|
| **AMD 2025-09-08** | **no — no displacement** | 10:37 | **10:37, exact** | 1.18 | **displacement present** | **S, zero downgrades** |
| NVDA 2025-06-24 | no — no displacement | — | 10:13 | 2.07 | present | S, zero downgrades |
| QQQ 2025-12-22 | no — no displacement | — | 09:57 | 1.02 | present | S |
| MSFT 2025-08-29 | **yes**, *"no displacement but you get a +1"* | 9:38 | **9:38, exact** | 0.97 | **trips — correct** | C |
| SPY 2026-06-17 | yes, *"tight on if theres displacement"* | 9:48 | 9:48, exact | 1.60 | present | S |
| QQQ 2024-08-26 | yes, *"no dispacement... at 9:45"* | 9:56 | 09:52 | 1.80 | present | S |

**On the three cards he refused *for no displacement*, the shipped check trips on none of
them — and neither does the separation version.** The one card it does trip on is the one
he took.

The cleanest head-to-head in the set is **AMD 2025-09-08**. He named 10:37. The engine has a
signal at exactly 10:37, and grades it a clean **S with zero downgrades tripped**. He looked
at the same minute and wrote *"really no displacement from the original candles so i have to
downgrade."* By the code's own measure that break put 1.18 average candles of clear air above
the level. **He and it are looking at different reference points**, and his phrase names his:
"the original candles" — the candles at the start of the day, not the level the setup broke.

The second cleanest is **MSFT 2025-08-29**, and it is the best-calibrated single data point
this project has ever collected, because he named the downgrade, the offset, and the grade
in one sentence. The engine at his exact minute agrees on displacement — it trips — and
still lands on C, because it *also* tripped `level_not_respected` and
`counter_trend_not_respected`, which he did not see. Three tripped minus one confluence is
two, which is C. His arithmetic was one minus one, which is S. **The displacement call was
right and the grade was wrong, and the two variables that broke it are the two that already
trip on 67% and 90% of the book.**

---

## What this changes about ballot question 18

The rulebook (`Austin's Vault/Projects/omen-rulebook.md`, line 43) still records:

> Three exemptions forgive a missing displacement outright (ballot q18): BR+OCR confluence ·
> a bull/bear flag to start the day · a longer-timeframe thesis.

His MSFT sentence overrides the first of the three. *"BR OCR confluence, not perfect because
no displacement but you get a +1"* is not an exemption — it is a downgrade that trips,
offset by the confluence bonus. That is what the shipped `score()` already does. **On this
one point the code is right and the rulebook line is stale**, and the difference is real:
an exemption leaves the +1 available to cancel a *different* downgrade, an offset spends it.

The other two exemptions — a flag to open the day, a longer-timeframe thesis — are still
implemented nowhere.

---

## Proposed changes. Nothing is applied.

Ranked by how much evidence stands behind each.

**1. Replace the body-size test with the separation test — strictly better, changes nothing
about the money.** It is what he says, what all three mentors say, and it recovers 11 of the
13.4 recall points the shipped version costs (63.2% → 74.3% of his S days), at a money delta
of +0.0359R, well inside the error bar. It does not make the variable *discriminate* — no
version does — but if a variable is going to be in the ladder, it should be the version that
means what he means.

```python
# research/downgrade.py
DISP_SEP_ATR = 1.0   # GUESS, like every other constant here. Separation past the
                     # level, in ATR at the entry bar. Neto: "actual separation
                     # from the candles to the key level".

def no_displacement(bars, i, level, is_long):
    br = _break_bar(bars, i, level, is_long)
    if br is None:
        return True                       # nothing broke -- unchanged
    a = _atr(bars, i)
    if a <= 0:
        return False                      # cannot judge; do not invent a downgrade
    far = (max(b["h"] for b in bars[br:i + 1]) if is_long
           else min(b["l"] for b in bars[br:i + 1]))
    d = (far - level) if is_long else (level - far)
    return (d / a) < DISP_SEP_ATR
```

**2. Ask him the reference-point question before shipping either version.** Both
definitions fail his three refusals identically, which means neither is his rule yet. The
AMD card says why: he measures displacement *from the original candles*, and both
implementations measure it from the level. That is a ballot line, below — **not** something
to guess at in code.

**3. Do not touch `DISP_BODY_MULT` or `DISP_SEP_ATR` on the strength of the p = 0.041 cell
in the sweep.** One cell in 27 is chance, and its neighbours go the other way.

**4. Fix the stale rulebook line** about the BR+OCR confluence exemption — his 2026-08-29
sentence settles it as a +1 offset, which is what the code does. Markdown only, in the vault.

**5. Leave the "no break found" branch alone.** It fires on 1.7% of the book and is the only
part of the shipped check that is not the thing under dispute.

**What is explicitly *not* proposed:** turning displacement off. Switching it off is the
measured-best setting on both gates — recall on his S days goes 63.2% → 76.6% and the money
cost is −0.0136R, invisible against the error bar. But it is **his** ratified variable from
ballot question 18, and killing a rule he stated is a decision only he makes.

---

## Ballot lines for Austin

Five questions this measurement produced. None is a change to make without him.

1. When you say displacement, is the gap you are looking at between price and **the level it
   broke**, or between price and **the candles it came from**? The code measures it from the
   level, and on AMD 2025-09-08 at 10:37 that gave it 1.18 average candles of clear air and
   a clean S — where you said no displacement.
2. Ballot question 18 says BR+OCR confluence forgives missing displacement outright. On
   MSFT 2025-08-29 you wrote *"no displacement but you get a +1."* Which one is it —
   the downgrade never trips, or it trips and the +1 cancels it?
3. *"Neither of the parts have displacement"* — on a BR+OCR, does each part need its own
   displacement, so a setup can fail on the one-candle-rule leg alone even when the break
   was strong?
4. Does the displacement have to be there **before** the retest, or does the move after the
   entry count?
5. Trades that never separated from the level win 38.6% of the time but their winners
   average 3.01R against 1.56R — same expectancy, half the hit rate. Is a lower-hit-rate,
   bigger-winner trade something you want the engine to keep taking, or to refuse?

---

## Caveats

- **The rig is validated against the book, and it disagrees on 876 of 134,012 signals
  (0.65%)** — 466 where this rig trips and the book did not, 410 the other way. The run
  aborts above 1%. The cause is the bar source: this script reads the archive CSVs,
  `backtest_2y.py` used its own fetch path. Every conclusion here survives a 0.65% shift.
- **The level fed to every check is the trade's stop, not always the level it broke.** That
  is the same proxy `backtest_2y.py` and every prior grade measurement use, so the numbers
  are comparable — but for a one-candle-rule entry the stop is the candle's own wick, and
  "separation from the level" means something different there. This is the confound behind
  part of the 23-point win-rate gap.
- **The engine is rarely at his minute.** Three of the six displacement cards have an engine
  signal at the exact minute he named; on the other three the nearest signal is 12 to 40
  minutes away, and on QQQ 2024-08-26 the thing he described at 9:45 has no engine signal at
  all. Comparing a variable's verdict against his on a *different bar* is weak evidence, and
  the three exact-minute cards carry almost all the weight in the card table.
- **269 S days and 476 refusals is the whole pooled corpus with bars, not a held-out
  sample.** Some of those days trained earlier threshold choices in `downgrade.py`.
- **The separation threshold is a guess.** It was fixed before any result was seen, and the
  full sweep is published, but Austin has never given a number for it — same standing as
  every other constant in `downgrade.py`.
- Displacement is measured at each signal's own entry bar. Both the "any signal on the day"
  and the grade-level readings therefore mix a day's good and bad signals; a day with twenty
  signals almost always contains one with displacement present, which is why those columns
  sit at 99%+ and cannot discriminate.
- **No mark file was written.** Every corpus was read through `research/marks_pool.py`.

---

## Verify pass, 2026-08-30 — the headline stands, one proposed change does not

An Opus verifier reproduced the recall table **two independent ways** — once from the book's own
stored `sgrade` and `downgrades` fields, touching no code from this report and reading no bars, and
once by recomputing confluence and the shipped displacement check from the archive bars. Both paths
returned the report's numbers exactly: 49.74% trip rate, S days 206/269 (76.6%) → 170/269 (63.2%),
refusals 358/476 (75.2%) → 301/476 (63.2%), gap +1.4 pp → −0.0 pp, bought for +0.0136R. **Not
refuted.** The headline rests on the shipped body-size check and falls out of stored fields.

**But the verifier broke the separation variant, and it is load-bearing on one section and one diff.**

`separation_atr` reads `bars[br:i+1]` — the entry bar's **own completed high and low**. Its
docstring affirmatively claims *"Causal: reads only bars <= i"*. Bar `i` is the decision bar; its
extreme is not known when the entry is taken, and on a long the bar's high is exactly the quantity a
winning trade produces. **This is the look-ahead bug class again** (see `omen-rules-unreachable-in-code`
and `g80_lookahead_refute.md`), in a variable built to fix a different one.

Re-run with the entry bar excluded:

| | as published | entry bar excluded |
|---|---:|---:|
| tripped bucket, traded signals | 417 | **699** |
| win rate, present vs tripped | 61.5% vs 38.6% (22.9 pt, p=3.1e−19) | **61.0% vs 50.9% (10.1 pt)** |
| winner size, tripped bucket | +3.010R | **+2.393R** |
| money delta | +0.0359R | **−0.1742R (sign flips)** |

The 282 trades that move buckets win at roughly 57% — the signature of look-ahead.

**Consequences.** § "But there is one real, very large effect" is **refuted as written**: same
expectancy at half the hit rate was manufactured by the peek. **Proposed change 1 must not ship** —
its published code diff carries the same `bars[br:i+1]`. Fix the slice, re-measure the whole
separation table, and drop the "strictly better, changes nothing about the money" framing, because
once it is honest the delta goes negative.

**Two smaller things.** (a) A third of the comparison group is not what this report calls it: **161
of the 476 "days he refused" are X-only days** — an engine refusal ("this detection was wrong"),
not a day-level "I would not trade this". `marks_pool.py` names that distinction in its own
docstring; this report never surfaces it, so the 12.0-point figure is measured on a group that is
34% something else. (b) On QQQ 2024-08-26 the verifier gets the nearest signal at 09:55 with
separation 2.15 where this report says 09:52 and 1.80 — not load-bearing (he took that card and
neither variant trips on it), but `his_cards` nearest-signal does not reproduce cleanly.

Cosmetic: the headline calls 13.4 and 12.0 points "identical". They are not. What is identical is
the **63.2%** both arms land on. The table says it correctly.
