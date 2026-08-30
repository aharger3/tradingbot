# The deep batch — 60 charts, one question, and the minute on every one

*Built 2026-08-30 overnight. Not served. It is sitting on disk waiting for you.*

**The page:** `research/probes/omen-deep-batch.html` (925 KB, 60 cards, dark).
**The build record and answer key:** `research/decks/g83-deep-batch-manifest.jsonl`.
**The script that made both:** `research/g83_deep_batch_build.py` — `python research/g83_deep_batch_build.py`.

This is the second page of the night. The master homework is the variety — seven angles in
one sitting. This one is depth: the same question sixty times, for when you have a longer
stretch.

---

## 1. What is on it

One question per card — **is this an S** — and a free-text box asking **what minute you get
in**. Nothing else. No entry line, no stop, no target, no setup name, no grade, no result.
Just the symbol, the date, the 1-minute 09:30–11:00 session and your six levels
(PDH, PDL, PMH, PML, ORH, ORL).

**The minute is the point.** Twenty of the thirty cards you did the night before carried a
minute you wrote without being asked, and every hard finding out of that batch came from
those lines rather than from the yes/no — seven times out of seven the engine was later than
you, median 41 minutes inside a 90-minute window. So this page asks for it out loud: a box on
every card, a red warning on any card you call S without a minute, and a running count at the
top saying how many of your S cards still have no minute on them.

---

## 2. The quota, and why it is 20 / 20 / 20

| bucket | cards | what it means |
|---|---:|---|
| **Traded** | 20 | the engine booked a trade that morning |
| **Fired, refused** | 20 | it found setups that morning and refused every one |
| **Silent** | 20 | it found nothing at all, all morning |

The quota is **printed on the page** so you know what you are looking at. **Which card is
which is not** — that lives only in the manifest.

The mix exists because of `research/g77_wrongchart.md`: the old builder picked which signal a
card was about by how much the engine *believed* it, and never once read whether the engine
**took** it. 25 of the last 30 cards were signals the engine had refused, so every precision
number measured off them was measuring the wrong object.

The fix there — "only build cards from booked trades" — is right for a precision deck and
wrong for this one, because it can only score the engine on days it already likes. Three
buckets in equal proportion price three different things off one sitting:

- **traded** — do you agree with the days it puts money on (precision);
- **refused** — is the refusal right, or is it throwing away your setups;
- **silent** — the recall hole: days it never even looked at. Recall is the gate that is still
  short (58.6%), and this is the only bucket that can move it.

---

## 3. How the sixty were chosen, and what was thrown away

Random inside each bucket and nothing else. No cleanest-first sort, no grade filter, and
**no card pre-filter**. That last one is deliberate: `t21_card_filter` is the shipped deck
pre-filter and `build_deck.pick` runs it on fire-day candidates while letting silent-day
candidates through untouched. Run here it would filter two of the three buckets and not the
third, and the engine's own days would come out looking better than the days it never saw
**by construction** — which is exactly the comparison this batch exists to make.

At most three cards per symbol. 342 of the 604 silent symbol-days in the two-year book are
SPCX alone; uncapped, the silent bucket would have been an SPCX deck wearing a quota. None
reached the page.

**No repeats.** The exclusion set is `build_deck.seen_card_ids()` — every symbol-day judged in
any mark corpus **or** ever served in any manifest — which is **1,617 symbol-days**, plus the
39 cards of `research/decks/g75-deck2-manifest.jsonl` named explicitly (all 39 were already
inside the 1,617; naming them means a rename of that file cannot silently un-protect them).

**Candidates inspected and rejected before the sixty were filled: 72.**

| bucket | pool | rejected: already judged/served | rejected: symbol cap | rejected: short session | kept |
|---|---:|---:|---:|---:|---:|
| traded | 3,740 | 3 | 3 | 0 | 20 |
| fired, refused | 8,071 | 2 | 1 | 0 | 20 |
| silent | 604 | 6 | 12 | 45 | 20 |
| **total** | **12,415** | **11** | **16** | **45** | **60** |

The 45 short sessions are all in the silent bucket and are the same story as the cap: thin
symbols with half a morning of bars. A chart that is not a full 09:30–11:00 session is not
worth one of your sixty slots.

The two-year grid is 12,415 symbol-days over 500 sessions and 28 symbols. The page spans
2024-09-11 to 2026-08-06 across 26 symbols; no symbol appears more than three times.

---

## 4. Nothing about the engine is on the page

Checked in the build, and the build aborts rather than publishing if it is not true: the
strings `role`, `fired_not_traded`, `engine_signals` and `sgrade` do not appear in the HTML,
no chart carries an entry line, a stop line or an arrow, and the only data the card exports
about itself is `{symbol, date}`.

For the record, what the key says about the twenty traded cards — **none of which you can see
on the page**: the engine's first booked trade won 9 and lost 11; on your ladder it graded C
on 15 and S on 5; on the legacy ladder all 20 are `B`, which is the whole book.

---

## 5. Delivery contract

Same shell every homework page uses — `research/probe_page.py` and `research/probe_chart.py`,
neither modified:

- saves to this browser as you tap, restores on load, with a visible save indicator;
- Export → **Copy all** / **Download .jsonl**, no round trip;
- charts are static SVG rendered in Python, never canvas, so they work on a phone;
- the yes/no exports as `answers.s = ["s"|"no"]` — the spelling `grade_read.py` already reads,
  so these answers feed the no-repeat guarantee the moment they come back;
- `window.probeRow` parses your minute into its own `entry_minute` field, so the next analysis
  does not have to regex prose.

**Dark**, as asked. No palette was invented for it: `probe_page.py` already ships a dark block
behind the viewer's OS setting, and this page pins that exact palette on so it is dark
regardless of what the phone is set to. Nothing in `probe_page.py` changed, so no other page
moved.

---

## 6. What this does not do

- **It publishes no money number.** It is an instrument, not a measurement — there is no
  dollars-a-day figure here to compare against the $397/day bar.
- **It is not served.** Writing the manifest marks these sixty symbol-days as *served*, so no
  later deck can repeat them. If the batch is abandoned rather than sent, delete
  `research/decks/g83-deep-batch-manifest.jsonl` and the days go back in the pool.
- **The manifest is untracked in git.** It is a build record, not a judgement, but being
  *served* a card counts for the no-repeat guarantee — the same lesson as the g75 manifest,
  which spent a day untracked. It needs `git add research/decks/g83-deep-batch-manifest.jsonl`
  in whatever commit lands this page.
- **Eight of the sixty charts fit only three of your six levels in frame.** probe_chart only
  lets a level widen the frame by a quarter of the session's range, or the candles flatten into
  a ribbon. Every level that did not fit is named in text under the chart with its price and
  whether it sits above or below. 50 of 60 cards carry such a note.
- **The page was not opened in a browser.** The Chrome extension was not reachable from this
  session. The markup, the SVG, the export shape and the no-leak checks were all verified in
  the build; the interactive nag/tally script is the one that shipped on `g75_deck2.html` with
  a single selector changed (`data-q="take"` → `data-q="s"`).

*Gates re-run after the edit and green: the recall gate (83 fires against a baseline of 75,
nothing went silent) and the runner-stop selftest (18 laddered results, floored at −1.25R).
No mark file was opened for writing, nothing was committed, nothing pushed, no API key
printed.*
