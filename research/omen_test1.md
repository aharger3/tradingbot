# OMEN Test 1 — the design note

Built by `research/build_omen_test1.py`. Instrument: `research/probes/omen-test-1.html`.
Answer key: `research/probes/omen-test-1-manifest.jsonl` (outside the HTML, as with decks).
Page behaviour verified by `research/test_omen_test1_page.py` — 34 checks, all green.

Austin, 2026-08-26:

> I'm looking for a 100 question multiple choice test of 9:30 to 11 candles with the
> levels I watch, me marking the entry and stop loss, and grading S A C X and optional
> comments. You can mix all types of trades in there including ones that the engine
> doesn't have in its roster. The goal is for me to match with 95 percent of the S calls,
> so if you want to change the size of the test for results to match that denominator
> easier, go for it.

---

## 1. Size, and the arithmetic that picked it

**100 cards, 5 parts of 20.** The deck standard (`Projects/omen-decks.md`) caps a deck at
60 and `build_deck.py` enforces it with a `SystemExit` because two 120-card decks sat
ungraded for a week. **That cap is not touched** — `build_deck.py` still refuses `--n 61`.
This is a different instrument, and the thing that sets its size is the target Austin
attached to it.

"95% of the S calls" is a fraction. Its denominator is the S subset, and **one
disagreement costs `1 / N_S`**:

| N_S | one disagreement | 95% survives | verdict |
|---:|---:|---:|---|
| 20 | 5.0 pts | 0 misses | one card decides the whole test |
| 24 | 4.2 pts | 1 miss | a 60-card test at this mix — still a knife edge |
| 30 | 3.3 pts | 1 miss | |
| **50** | **2.0 pts** | **2 misses** | **this test** |

At 50, `48/50 = 96.0%` passes and `47/50 = 94.0%` fails. Two disagreements are absorbed;
three are a real result. At 24 the first disagreement is fatal, which measures noise
rather than agreement — and getting this wrong makes the whole test unreadable, so the
arithmetic is printed at the top of the page in a bordered panel Austin reads before
card 1. The page derives that paragraph from the number the build actually measured;
`scorebox()` takes it as an argument rather than carrying a hardcoded figure.

### How many are S-eligible: 50 of 100

The denominator is the **union** — cards where Austin says S *or* the engine's S/A/C
grader (`research/downgrade.py`) says S. Half of that union is knowable before he marks
anything, and that half is what the build sizes:

| stratum | cards | grader-S |
|---|---:|---:|
| `s_dropped` — grader S, engine traded nothing | 28 | 28 |
| `s_traded` — grader S, engine took the trade | 12 | 12 |
| `offroster` — off-roster structure, engine traded nothing | 25 | 10 |
| `silent` — no engine signal on the day at all | 15 | 0 |
| `low` — best signal on the day grades C | 20 | 0 |
| **total** | **100** | **50** |

Anything Austin grades S in the other 50 cards *grows* the denominator, which only makes
the target easier to read. 50 is the floor, not the estimate.

### What the 60-card cap was actually protecting

Finishability, and that is bought back a different way rather than ignored:

- **Five numbered parts of 20**, each with its own progress bar, each about ten minutes.
  One export covers the whole page, so stopping after part 2 costs nothing.
- **Grade is the only required control.** Entry, stop and setup appear only when the
  grade is tradeable — the deck standard's own "what done means on a card" rule. Of the
  100 cards, the ones he X's cost **one tap**.
- The page saves on every tap, so "one sitting" was never the real requirement.

**This override should be ratified.** The standard says a new deck kind needs a reason
written down first; this is that reason, and if Austin disagrees the honest fallback is
60 cards with the S bias pushed to ~30, not 60 cards drawn at random.

---

## 2. What is on a card

09:30–11:00, **one-minute candles, exactly 90 bars**, rendered to **static SVG in
Python** by `probe_chart.py` — never canvas. The levels are the ones
`build_probes.py` / `probe_chart.py` already draw, same colours, same labels, same
legend text, so there is one visual language across every instrument:

- **PDH / PDL** prior day, blue-violet
- **PMH / PML** premarket 04:00–09:29, purple
- **ORH / ORL** first 5 RTH bars, teal

Four controls, in the deck standard's order and vocabulary:

| control | values | required |
|---|---|---|
| **grade** | `S` `A` `C` `X` | yes — and it is the only one |
| **entry** | quarter-hour block, then minute | no |
| **stop** | structural price from a rail, or typed | no |
| **setup** | `BR` `OCR` `BR+OCR` `84` `other` + note | no |
| *why not* | shown only on `X` — no level / chop / too extended / … | no |
| *comment* | free text, one line | no |

### What X means here, spelled out on the page

On the engine ladder `X` is **not a grade** — it means the engine should not have fired
(`DIRECTION.md`). Austin is grading a **chart** here, not an engine output, so the page
defines it explicitly in the legend panel and again in the grade hint:

> **X — no trade here at all.** You would not have taken anything in this window.

In the export that is `"grade":"X"` **plus** `"grade_std":"none"`, so the letter he tapped
is preserved verbatim and the historical corpus's word for the same judgement is carried
alongside. One parser reads this file and every older one; nothing has to guess.

---

## 3. Entry and stop, by touch

Chart-click marking is pointer-designed and has never been phone-tested
(`omen-decks.md`, "Mobile is unproven, and it is now a hard contract"). It is not used
here. Both marks are taps on ordinary chips, and both are **static in the served markup**
— which is exactly why they survive a reload when canvas marking never has.

**Entry — two taps, no typing.** Six quarter-hour blocks (`09:30–09:44` … `10:45–10:59`),
then fifteen minute chips inside the chosen block. Entry price is that candle's close, the
deck standard's definition. Three things make it precise rather than blind:

1. tapping the block **shades that 15-minute band on the chart**;
2. tapping a minute **drops the entry line and a vertical marker on that exact bar**, so
   he can re-tap minutes and watch it walk;
3. a readout under the chart says `entry 10:07 @ 31.41 · stop 32.75 · risk 1.34 · long`.

Why not a 90-chip rail of every bar: 9,000 buttons across the page, and the two-level
picker is 21. The minute chips carry `+0…+14` in the markup — the offset, not a clock
time, so the same 15 chips work under any block and persistence never sees a rewrite —
and the page **relabels them to the real clock** (`10:07`) the moment a block is chosen.

**Stop — one tap on a structural price.** The rail is built in Python at build time from
the chart's own structure: the six levels, every 5-bar fractal swing high and low, and
the session extremes; deduped to distinct prices and capped at 18. Each chip shows the
price, what it is (`214.32 · swing low 10:23`), and — once the entry is set — the
resulting risk and which side it implies. **Side is inferred, not asked**: a stop below
the entry is a long, above is a short. That is one control saved on every tradeable card.

A price *field* was rejected on purpose: a number input on a phone is a keyboard, and a
keyboard is the thing that stops a card getting finished. The free-text box on the same
question is the escape hatch for a stop none of the 18 express, and a number typed there
**overrides** the rail and exports as `"stop_src":"typed"`.

**No nested scroller anywhere.** An early draft gave the stop rail `overflow-y:auto`; a
scroll container inside a scrolling page is the most reliable way to lose a tap on a
phone, so the rail is two-up and simply tall.

---

## 4. Card mix, and the off-roster cards

The engine's roster is break-and-retest, one-candle-rule, their confluence, the 84%
re-entry, and the retired FVG/flag detectors. Austin asked for setups it has no detector
for, because those cards are the only way to find a rule that does not exist yet.

**25 cards, five patterns, five each.** All 25 are days the engine's own 2-year replay
took **zero** trades on. The pattern is a *selection* label computed by `classify()` from
bars and levels — it is never printed on a card, never named to him, and lives only in
the manifest:

| pattern | what it is | why the roster cannot see it |
|---|---|---|
| `gap_fill` | opens ≥0.4% from the prior close and walks back through it | PDC is not even in the level set the engine draws |
| `or_reversal` | closes through one side of the opening range, then the other | `break_then_rejection` is unreachable in `downgrade.py` — 10 hits in 45,175 signals (`p2_threshold_sweep.md`) |
| `no_retest` | breaks a level with a real body and never comes back to it | B&R needs the retest by construction |
| `range_fade` | the whole window sits inside the premarket range, both ends worked twice | nothing in the roster fades a range |
| `double_tap` | two touches of the session extreme ≥8 bars apart with a real pullback | Austin, rulebook card 14: a two-candle version "is not an OCR — that is a pivot structure break" |

The `setup` question is where these pay off. If he taps **"Something else"** and writes
one line, that line is a rule the project does not have. This is the only control on the
card whose purpose is to be answered with prose.

**A precision the note owes you:** B&R *detects* something on 95% of archived days, so
"the engine has no detector" cannot mean "no signal". It means the engine produced **no
tradeable signal** on that day and the structure present is one nothing in the roster
expresses. Ten of the 25 still carry a grader-S, which is why the off-roster stratum
contributes to the S denominator.

### Why the other 75 are what they are

Biased toward disagreement, per the brief and the two findings behind it:

- **`s_dropped`, 28 cards — the wound.** `research/g4_dropped_s.md`: the grader scores
  7,485 signals S over two years and the engine trades 128; 96.5% are thrown away by
  `_grade_pa`, and the real entry rule is arrival order, not grade. These are the days
  the two are most likely to disagree on.
- **`silent`, 15 cards.** No engine signal at all. Recall in the direction the OMEN 6
  gate is actually measured in.
- **`s_traded`, 12 · `low`, 20 — the easy end.** `research/p2_threshold_sweep.md`:
  agreement is 21 of 58 cards and S recall is 12/28. A test made only of hard cards
  cannot measure 95% of anything, so 32 cards come from the engine's own traded S book
  and from days whose best signal grades C.

**Spread:** 27 distinct symbols, at most 8 on any one; 20 distinct months, 2025-01-07 to
2026-08-17. Drawn from 2025-01-01 onward to keep the regime next to the corpus he already
graded, and restricted to the 28 symbols in the 2-year replay so "the engine fired / was
silent" in the manifest is a true statement rather than an artefact of a symbol that was
never scanned.

---

## 5. The no-repeat proof — and the hole this build closed

**Against history.** `build_deck.marked_card_ids()` reads every mark corpus
(`research/marks/*.jsonl` by glob plus `LEGACY_MARK_FILES`) and the pool is filtered
behind it before the draw. **658 already-judged symbol-days excluded**, 6,424 days
probed, 0 of the 100 cards appears in that set. Asserted in `verify()`.

**Within the document.** The G12 failure — the master homework asked QQQ 2026-07-20 and
QQQ 2026-07-24 twice each, as both a `cal_` and an `au_` card, because it deduped only
against history. Fixed two ways here: every stratum draws behind a shared `used_days`
set, and `verify()` fails the build if any `SYMBOL_DATE` appears on two cards.

### `marked_card_ids()` was blind to the newest corpus. It is not now.

The brief asked me to confirm the guard picks up
`research/marks/probe_master_homework_2026-08-26.jsonl`. **It did not.** The file was
globbed, but `_judgement_key()` mis-read it in two independent ways:

1. **Prefixed card_ids parsed to garbage.** `cal_QQQ_2026-06-29_b10` was split on `_` and
   the first two parts taken, yielding the key `cal_QQQ`. All 51 rows collapsed to six
   useless keys — `cal_QQQ`, `au_TSLA`, `h2_TSLA`, `sr_QQQ`, `sr_TSLA`, `au_QQQ` — so
   every day on that page was still eligible for a future deck.
2. **A probe answer is a judgement even with no grade.** The 25 `sr_` S-recall rows carry
   `"grade": null` and `"answers": {"s_call": [...]}`. Austin looked at 25 fresh charts
   and said yes-or-no on each — six of them S — and the guard could not see any of it.

Both fixed in `build_deck.py::_judgement_key()`: the SYMBOL_DATE pair is now pulled out
of a card_id wherever it sits (`_ID_RE`), and a row with any non-empty answer counts as a
judgement. The change is strictly additive — it can only ever exclude more days.

| | before | after |
|---|---:|---:|
| judged symbol-days | 633 | **658** |
| from `probe_master_homework_2026-08-26.jsonl` | 6 (all garbage) | **49** |

49 and not 51 because two of the 51 rows *are* the G12 duplicates — QQQ 2026-07-20 and
QQQ 2026-07-24, each asked twice.

> **Side effect worth knowing about.** Because the guard now sees those 49 days,
> `build_master_homework.py` no longer draws the same 25 fresh S-recall cards it drew on
> 2026-08-26 — it correctly refuses to re-ask days Austin has now answered, and picks 25
> different ones. **The five committed probe HTMLs were therefore left at their committed
> versions**, not regenerated: `omen-master-homework.html` is the document he actually
> graded, and quietly replacing its card set would orphan
> `probe_master_homework_2026-08-26.jsonl`. Rebuild it deliberately when a new sitting is
> wanted; the new draw is correct, it is just a *new* page.

---

## 6. Delivery contract

`probe_page.py` owns persistence and export, unchanged in substance. It does **not** use
the claude.ai artifact runtime to save answers; that was tried 2026-08-22 and nothing
persisted.

- localStorage per card on every tap, deck-scoped key, restore on load
- visible `saved HH:MM:SS` indicator that turns red and says so if storage is blocked
- touch targets, no hover dependence, one card per screen
- Export → **Copy all** (into an editable textarea, so ctrl/cmd+A works where the
  clipboard API is blocked) / **Download .jsonl**
- `content-visibility:auto` on every card — 100 charts is ~20,000 SVG elements, and
  without it a mid-range phone stutters on every scroll

Two additive extension points were added to `probe_page.py` so this page did not have to
hand-roll a second front-end (the exact drift the deck standard exists to prevent). Both
are no-ops on a page that does not use them — every other probe rebuilds with these ~20
lines as its only front-end change:

- `data-export` on a card — static JSON merged into its export row
- `window.probeRow(card, row)` — a hook for fields derived from the taps

### Export row

```json
{"type":"probe","probe":"omen-test-1","card_id":"t1_IREN_2025-09-10",
 "symbol":"IREN","date":"2025-09-10","part":1,
 "grade":"S","grade_std":"S","setup":"BR+OCR","side":"L",
 "entry_i":37,"entry_t":"10:07","entry_p":31.41,
 "stop_p":30.07,"stop_src":"swing low 09:52",
 "answers":{"grade":["S"],"eblock":["2"],"emin":["7"],"stop":["30.07"],"setup":["BR+OCR"]},
 "notes":{"comment":"reclaimed PDH then held it"}}
```

`type` / `probe` / `card_id` / `grade` / `answers` / `notes` are exactly the shape of
`research/marks/probe_master_homework_2026-08-26.jsonl`; everything else is additive, so
one parser reads both. `card_id` is `t1_SYMBOL_DATE`, which the repaired `_ID_RE` reads,
so **this test's own export will feed the no-repeat guard the moment it lands.**

### Verified, not assumed

`python research/test_omen_test1_page.py` drives the real file in jsdom and checks 34
things. The load-bearing ones:

- 100 cards, 100 `<svg>`, **0 `<canvas>`**, 20,206 SVG child elements in the markup
- grade / block+minute / stop chip / typed stop all register, and the entry line, the
  bar marker, the block band and the stop line move on the served SVG
- an X card counts as done on one tap and draws nothing
- **a fresh document over the same localStorage restores every mark**, repaints the
  chart, restores progressive disclosure, and exports byte-identical text
- export is one valid JSON object per line carrying card id, symbol, date, grade, entry
  bar / time / price, stop, side, setup and comment

---

## 7. Things Austin should ratify

1. **100 cards over the standard's 60.** Section 1 is the argument. If he says no, the
   fallback is 60 with the S bias raised, not 60 drawn at random.
2. **X = "no trade here at all."** It is his `none` under a different letter, because he
   asked for the letter. Exported as both.
3. **Side is inferred from which side of the entry the stop sits.** No long/short button.
4. **Stops come from a rail of structural prices, not a free field.** The typed escape
   hatch exists; if he uses it on most cards, the rail is wrong and should be rebuilt.
5. **SPY is in the pool.** He trades it and the rulebook says put it back in the
   universe, but `INCLUDE_SPY_IN_BACKTEST` is still R4 and still open.
6. **Draw starts 2025-01-01, 28 replay symbols only.** Both narrow the pool; both were
   chosen so the manifest's engine claims are true.

## Rebuild

```bash
python research/build_omen_test1.py      # -> probes/omen-test-1.html + -manifest.jsonl
python research/test_omen_test1_page.py  # 34 checks in jsdom
```

Deterministic: `SEED = 1`, same pool, same 100 cards.
