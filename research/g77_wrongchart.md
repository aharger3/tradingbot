# Was the homework showing you the wrong chart?

*2026-08-29. The question: if a chart carries two signals and the deck hands you the one the
engine never traded, then your grading has been measuring something other than the trades the
engine takes.*

**Yes. It is worse than "sometimes", and it is not a coincidence — it is the rule the deck
builder uses to pick which signal a card is about.**

Here is the whole answer in four lines:

| | |
|---|---:|
| Cards that were a trade the engine actually took | **5 of 30** |
| Cards where the engine traded something else on that same chart | **10 of 30** |
| Cards where the engine refused the whole chart, all morning | **15 of 30** |
| Cards that would survive unchanged if the deck showed the real trade | **1 of 30** — and it is one you said no to |

---

## 1. What the deck did

Every card is a symbol-day. The engine had between **4 and 20 signals** on each of those
mornings. The deck picked one to build the card from, and the rule it used was:

1. throw away every signal that is not an **S on your ladder**;
2. keep only the setups in one bucket — 84% rule beats one-candle rule beats break-and-retest,
   because you asked for the first two to be over-weighted;
3. of what is left, take the one with **fewest downgrades**, then the **earliest minute**.

That is a rule about how much the engine *believed* a signal. It never once asks whether the
engine **took** it. The word `traded` does not appear anywhere in the selection.

`research/g71_homework_build.py`, function `load_s_days`:

- **line 277** — `rows = [r for r in book["trades"] if r.get("sgrade") == "S"]`
- **line 289** — `bucket = next(b for b in BUCKETS if b in setups)`  (84 > OCR > BR)
- **line 291** — `pool = [r for r in rs if SETUP_OF.get(r["setup"]) == bucket]`
- **line 313** — `min(keep, key=(tripped, et))` — fewest downgrades, then earliest

*(Line numbers are after this pass added the guard import; before it they were 276, 288,
290, 312.)*

The manifest even says out loud that the traded flag is "answer key — deliberately NOT in the
HTML". It was treated as the thing being tested. It was actually the thing that had to be
selected on.

**That first line alone is fatal.** Across the two-year book the engine put money on **3,740
symbol-days**, and on **3,228 of them — 86% — its own trade is not an S on your ladder.** On
those days the builder could not have picked the real trade *even by accident*, because the
first line of the rule had already deleted it.

And the bucket rule finishes the job. Fifteen of the 30 card-days had a trade on them, and on
**14 of those 15 the engine's trade was a break-and-retest**. The deck was deliberately
weighted towards the other two arms, so the card was steered away from the trade by design.

## 2. What that looked like on the actual cards

Fourteen cards were built from a signal on a chart where the engine's real trade was a
different signal:

| card | what the card said | what the engine actually traded |
|---|---|---|
| NVDA 11 May | OCR 10:32 **short** at PDH | BR 09:44 **long** at PDH, +3.43R |
| MSFT 29 Aug | OCR 10:19 **long** at PDL | BR 09:40 **short** at PML, +1.26R |
| AMD 8 Sep | BR 10:37 **long** at PMH | BR 09:58 **short** at PDL, −1.00R |
| TSM 26 Nov | BR 10:39 **long** at PMH | BR 10:01 **short** at a pivot low, +0.68R |
| META 22 Jun | 84% 10:15 short at PML | BR 09:40 short at PML, −1.00R |
| INTC 24 Mar | 84% 10:21 short at PDL | BR 09:48 short at PDL, −1.00R |
| TSM 7 Jul | 84% 09:50 short at PML | BR 09:38 short at PML, −1.00R |
| COIN 10 Jul | 84% 10:40 long at PDH | BR 10:22 long at PDH, −1.00R |
| AAPL 17 Apr | 84% 10:14 long at PMH | BR 10:01 long at PMH, −1.00R |
| HOOD 28 Nov | 84% 10:21 long at PDH | BR 10:08 long at PDH, −1.00R |
| GOOGL 29 Oct | OCR 10:59 long at PDH | BR 10:04 long at a pivot high, −1.00R |
| NFLX 8 Jul | OCR 10:01 short at PDL | BR 10:25 short at a pivot low, +0.43R |
| AMZN 11 Dec | BR 09:39 long at PMH | BR 09:42 long at the opening-range high, −1.00R |
| ACHR 16 Jun | BR 09:56 short at PML | BR 10:03 short at a pivot low, +2.09R |

- **10 of 14** were a different setup entirely.
- **7 of 14** named a level the real trade is not on.
- **4 of 14 pointed the opposite way** — the card claimed a long where the engine was short,
  or the reverse.

## 3. The card marks nothing, so what you graded was the chart

This is the part that decides how much of the 70% survives.

The card draws the session and your six levels and **nothing else** — no entry, no stop, no
arrow, no direction. It says one line underneath, e.g. *"engine claims: OCR — one candle rule,
at: PDL — prior day low — the order block sits on it"*, and asks *"Is this an S trade?"*

So a **yes** cannot mean "I agree with that signal". It can only mean **"there is an S trade on
this chart"** — and when you wrote a minute, the minute is the only thing that says which trade
you meant.

On **19 of the 25 cards where you wrote a minute, a different signal on that chart sat closer
to your minute than the card did.** On 7 of them the closer one is a trade the engine actually
took.

That is the measurement error in one sentence: **precision was scored as if your yes endorsed
the engine's chosen signal, when the page never showed you which signal that was.**

## 4. The two cases from last night

### MSFT, 29 August — this one closes

Your note: *"BR OCB confluence, not perfect because no displacement but you get a +1 9:38 is
the entry"*.

The engine's own description of its 09:38 signal on that chart, written by the engine months
ago, word for word: *"B&R short — prior breakdown below PML $508.23, retest ... [clean]
[**nodisp**] ... [**brocr**]"*, confluence **yes**.

Four separate things in your sentence match that signal and **none of them match the card you
were shown**:

- *"BR"* → the engine calls it B&R.
- *"OCB confluence"* → the engine tags it `brocr`, break-and-retest **plus order block**.
- *"no displacement"* → the engine tags it `nodisp`. The card has zero downgrades and no such
  tag.
- *"you get a +1"* → the confluence bonus, which that signal carries.
- *"9:38 is the entry"* → the signal's minute is 09:38, exactly.

And the tape agrees. Premarket low is 508.23. Price broke under it at 09:35–09:36, wicked back
up to 508.27 at 09:38 and closed 507.87 — back below. Then it fell to 505.60 by 09:45. **The
only trade on that chart at 09:38 is a short off the premarket low.** The engine took it at
09:40 and booked +1.26R.

The card you were handed was the **opposite direction** — a one-candle-rule *long* at 10:19,
41 minutes later, at the bottom of a chart that had been falling all morning.

**Verdict: closed.** Your own words name the engine's trade.

### NVDA, 11 May — this one does not close

Your note is *"9:43"*. That is all of it. No wording, no direction, no level.

What is true: the engine had a break-and-retest **long** on the prior day high at 09:43 and
took it at 09:44 for +3.43R. Every signal between 09:43 and 10:11 is a long on that same level;
the first short anywhere on the chart is at 10:19. The tape shows price breaking above the
prior day high at 09:40, pulling back into it at 09:42–09:43, holding, and running to 220.90
by 09:49. And the card you were shown was a one-candle-rule **short** — built off a block that
did not form until 10:30, so the setup the card claimed **could not have existed** at your
minute.

So: at your minute the chart admits one trade and the engine took it. But **you did not write
a direction, and nothing in the card recovers one.** It stays a strong coincidence.

**Verdict: open. Do not count it as a proof.**

### One honest note on the dollars

Both of those winners fill at the signal bar's *extreme*, not its close — MSFT shorts at the
09:40 bar's high, NVDA buys the 09:44 bar's low. That is exactly the 83%-of-the-book fill
problem another workflow is rebuilding. **The trade being there, and being at your minute, is
real. The +$1,256 and +$3,429 are the book's numbers, not money.**

## 5. What is left of the 70%

| what is being measured | score |
|---|---|
| all 30 cards — *does the engine nominate days you like?* | 21/30 = **70%** (honestly 52–83%) |
| the 5 cards that were a trade the engine took | 4/5 = **80%** (honestly 38–96%) |
| the 1 card that was the day's **first** trade — the one the book books | **0/1** |

All five of the traded cards are **84%-rule** re-entries — the only arm that loses money in the
book (−$27,815 over two years). Not one break-and-retest card and not one one-candle-rule card
was a trade.

So the honest read: **the 70% is a real number about the engine's nominations and says nothing
about whether the engine trades well.** Nothing of it survives as a statement about trading —
the surviving sample is four cards, then one.

## 6. The fix

The rule a precision card must use: **the engine's first booked trade on that chart.** That is
the row the one-trade-a-day book books, and if there is no booked trade the day does not belong
in a precision deck at all.

Three things are now in place:

1. **`research/g77_realtrade_pick.py`** — the shared rule (`day_trade`) and a guard
   (`guard`) that refuses to publish a precision deck whose cards are not booked trades.
2. **`research/g71_homework_build.py`** now calls that guard. Run it as it stands and it stops
   with *"25 of 30 cards are signals the engine REFUSED to trade"*. Reproducing the deck that
   was actually served now needs an explicit `--allow-untraded`. Nothing warned last time; it
   warns now.
3. **The 39-card deck built last night already complies** — `g75_deck2_build.py::candidate_days`
   takes only booked trades and picks the day's first one. Checked: **39 of 39 are real trades.**
   Its cards grade C 20 / A 10 / S 9 on your ladder — meaning **30 of those 39 charts were
   invisible to the old rule**, which is the 86% above, showing up in the next batch.

### If the 30 cards had been built the right way

- **15 of 30** would not have been cards at all — the engine refused those charts all morning.
- **14 of 30** would have been a different signal on the same session.
- **1 of 30** is unchanged: AVGO, 3 December, and you said **no** to it.

The chart itself would also have looked different on 7 of those 10 sessions, because the
high-of-day and low-of-day lines are drawn where they stood **at the card's signal minute**.
Pick a different signal, the lines move. On MSFT 29 August the low-of-day line was drawn at
504.49 — where it stood at 10:19. Anchored on the trade the engine really took at 09:40 it
would have read **507.00**, two and a half dollars higher, right where the setup was.

---

## What this does not say

- It does not say the 30 cards were wasted. They measure whether the engine's *nominations*
  land on days you like, and 70% is a real answer to that question.
- It does not say your yes/no was wrong on any card. It says the yes/no was attached to the
  wrong object.
- It does not move a dollar. Every number here is about which chart went on the page.
- NVDA 11 May stays unproven, and the two dollar figures stay inside the fill problem.

---

*Re-runnable, none of it touching engine code, your mark files or the book:*
`research/g77_wrongchart_extract.py` (pulls every signal on the 30 card-days out of the
two-year book) → `research/g77_wrongchart_census.py` (per-card ledger) →
`research/g77_wrongchart_table.py` (prints it) → `research/g77_wrongchart_counterfactual.py`
(the re-pick and the book-wide 86%) and `research/g77_wrongchart_anchor.py` (the moving
high/low lines and the tape). The rule and its guard are `research/g77_realtrade_pick.py`,
tested by `research/g77_realtrade_pick_test.py`, which replays the two existing manifests
rather than rebuilding a deck — rebuilding g71 would consume unjudged symbol-days.

*Guardrails: the mark file was opened read-only and is unmodified (unchanged since 21:43,
before this pass); nothing committed or pushed; the six confluence levels and `HODLOD_PAIR`
untouched; no API key printed. All four protected tests re-run and green after the edit —
the recall gate (PASS, 83 fires against a baseline of 75, none went silent), the single-source
universe test (29 symbols), the stop-fill test (80 checks) and the runner-stop test (18
laddered results, floored at −1.25R).*
