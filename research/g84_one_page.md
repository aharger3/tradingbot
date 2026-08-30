# G8.4 — one page, everything outstanding

Three homework instruments were built and sent, and Austin could not mark any of them:
they opened read-only in a viewer panel. Three links, zero marks back. This is one page
holding all three, re-rendered so the taps work and the answers come out.

    research/g84_one_page.py                    the builder
    research/probes/omen-all-in-one.html        the page          2.33 MB
    research/decks/g84-all-in-one-manifest.jsonl  the answer key  154 rows

**Nothing new was selected.** No symbol-day was re-picked, no deck builder's selection
logic ran. The three manifests already on disk are read and re-rendered card for card,
each item keeping its own question, its own answer options and its own section label.

## What is on it — 154 items in 9 collapsible sections

| section | n | source deck | question |
|---|---:|---|---|
| `mentor_ballot` | 15 | omen-master-homework | is this a rule of yours — yes / no / skip |
| `is_this_an_s` | 8 | omen-master-homework | is this an S — yes / no, + why-not (multi) |
| `which_signal` | 6 | omen-master-homework | which dot is the trade — A / B / neither |
| `what_minute` | 6 | omen-master-homework | long / short / no trade, + the minute |
| `htf_agree` | 6 | omen-master-homework | agrees / disagrees / can't tell (1-min + daily) |
| `displacement` | 8 | omen-master-homework | yes / no / can't tell, + what from |
| `where_is_the_stop` | 6 | omen-master-homework | A / B / C / D / none of these |
| `take_the_trade` | 39 | g75-deck2 | would you take it — yes/no, minute, why-not (multi) |
| `deep_is_s` | 60 | g83-deep-batch | is this an S, + the minute |
| **total** | **154** | | |

Sections are ordered fastest-and-most-unblocking first: the 15 chartless ballot lines,
then the seven-section variety batch, then the two long chart sittings.

Each exported row carries `source_deck`, `section` and the manifest's own `card_id`, so
an export drops straight back onto the manifest it came from. The card_id is the source
manifest's verbatim id (`COIN_2024-10-29`, `rule_01`), not a re-prefixed one.

## No repeats

`build_deck.marked_card_ids()` and `build_deck.served_card_ids()` were both called.

| | count |
|---|---:|
| judged symbol-days (`marked_card_ids`) | 1,178 |
| `served_card_ids()` as-is | 980 |
| served, the three source manifests excluded | 841 |
| items read from the three manifests | 154 |
| distinct `card_id` | 154 |
| distinct symbol-days | 139 |
| **card_id repeated across the three sources** | **0** |
| **collides with a judged symbol-day** | **0** |
| **collides with a served symbol-day** | **0** |
| **dropped** | **0** |

Nothing was dropped. If anything had collided the builder would have removed it and
printed the ids.

**`served_card_ids()` needed a wider exclusion than it takes.** It globs every
`*manifest*.jsonl` under `research/`, which now includes the three manifests this page
re-renders — so left alone it reports all 139 symbol-days as already served, by
themselves, and the guard becomes noise. `g84_one_page.served_excluding()` is the same
glob, the same `_ID_RE`, the same `_rows` reader, with a four-path skip list (the three
sources plus this page's own manifest). Both numbers are printed so the difference is
visible rather than hidden.

The three sources were also checked **against each other** — they were each built
no-repeat, but independently. No overlap: 154 distinct card_ids, 139 distinct
symbol-days (the 15 ballot rows carry no symbol).

## The probe_chart trap

`probe_chart.LEVELS` grew HOD/LOD on 2026-08-29 and its comment claims every existing
caller's SVG stays byte-identical. **That is false.** The frame-widening loop walks
`LEVELS`, so any caller whose `levels` dict carries `hod`/`lod` gets a different frame
*and* two more lines. The three sources do not draw the same six:

* g75-deck2 and g83-deep-batch draw PDH/PDL/PMH/PML/**ORH/ORL**
* master `is_this_an_s`, `displacement`, `htf_agree`, `where_is_the_stop` draw
  PDH/PDL/PMH/PML/**HOD/LOD**
* master `which_signal` and `what_minute` draw **four** — no HOD/LOD, because on those
  cards the running high/low is the answer

So every card is passed **exactly the `drawn_levels` dict its own manifest recorded**,
never a reconstructed one, and the legend under each chart is generated from the keys
actually present. Nothing is added and nothing is dropped.

## Reading six lines apart

`probe_chart` gives both members of a pair the same class (`lvl-pd` for PDH *and* PDL),
so four hues cannot tell six lines apart. `key_levels()` post-tags each emitted
line/label pair with its own key (`lk-pdh`) off the label the renderer already wrote,
and CSS dashes the highs long and the lows short — **hue says which pair, dash says
high or low**. It asserts that the number of tagged pairs equals the number of level
lines in the SVG, so if that markup ever changes shape the build fails instead of
quietly losing the distinction.

Font sizes inside the SVG are viewBox units: a 720-unit chart lands near 390 CSS px on a
phone, so the source decks' 9px gutter label renders at ~5px on the device he actually
uses. Level, dot and rail labels are sized up to survive that, the level labels lost
their halo (a 3-unit stroke on a 13-unit glyph closes the counters into a smear at half
scale), and **the legend under every chart now repeats each drawn level's price in page
text**, which does not shrink. Levels the frame could not fit are named in an
"off this chart" line on every chart card.

## What the artifact sandbox breaks, and what was done

* **Downloads are inert.** Copy all is the export: in the sticky bar, in a bordered
  panel directly under the masthead, and again at the foot. It tries
  `navigator.clipboard.writeText`, falls back to `execCommand('copy')` on a selected
  textarea, and if both fail it says *"the text is selected below — long-press it and
  tap Copy"*. Download is present, labelled "usually blocked", and reports honestly.
  The raw `.jsonl` lives in a visible, editable, non-readonly `<textarea>` that
  repaints on every answer, so a manual long-press always works.
* **No external resources.** 0 occurrences of `http` in the 2.33 MB file. System font
  stack only. The shared `probe_page.shell` links fonts.googleapis.com, so this page
  does not use that shell — it carries its own CSS and JS.
* **localStorage can throw.** Probed at boot inside `try/catch`; every read and write is
  wrapped. If storage is dead a red banner appears at the top of the page and the save
  indicator reads `NOT SAVING - COPY OUT NOW` instead of `saved`. Notes are debounced
  400 ms and flushed on `blur`, `visibilitychange` and `pagehide`.
* **Dark.** `html` and `body` both painted `#0a0f0e` explicitly; there is no light
  palette in the file at all.
* **Phone first.** 48 px minimum chip height, 56 px section headers, no hover-only
  interaction, no pointer drawing. Charts scroll inside their own `overflow-x:auto` box;
  the page body's `scrollWidth` equals its `clientWidth` at 390 px.
* **Resumable.** Nine `<details>` sections, each showing its own `n / N`. The page opens
  the section holding the first unanswered item and scrolls to it; "Next unanswered"
  does the same on demand.
* **Minute nag carried forward.** A yes / S with no minute in the box is not counted
  answered and wears a warning, exactly as g75 and g83 did — the minute is where every
  hard finding has come from.

## Verified, not assumed

`research/g84_one_page.py` self-checks at build time (answer key leak, external
resource, canvas, card count, duplicate `data-cid`, page/manifest agreement). The page
was then **loaded in a real Chrome at 390 × 844 with touch** and 28 behavioural checks
run against it — all pass:

no JS errors · no external requests · 154 cards · 9 sections · body computed
`rgb(10,15,14)` · no sideways body scroll · opens at the first unanswered · counter
0→3 · per-section counts · minute nag blocks done · 3 keys in localStorage · export has
3 rows carrying `source_deck` + `section` · minutes parsed to `09:42` / `10:07` ·
card_ids match the source manifests · **clipboard actually holds the jsonl** · copy
reports success · textarea visible and not readonly · **restores after reload**
(counter, chips and typed text) · reopens at the first unanswered · **loud banner and
still usable when `localStorage` throws**.

Both repo gates green: `regression_gate.py` PASS, `test_runner_stop.py` ok.

## Files

None committed. All three show as untracked (`??`) in `git status`, not ignored — the
`!research/probes/*.html` and `!research/decks/*-manifest.jsonl` un-ignore rules cover
them. Nothing under `research/marks/` was opened for writing.

**Answer key stays off the page.** `sgrade`, `legacy_grade`, `outcome`, `r`, `role`,
`downgrades`, `tripped`, `htf_score`, `sep_atr`, `shipped_check_trips`,
`prefilter_reach_r` and the rest go to `research/decks/g84-all-in-one-manifest.jsonl`
and are asserted absent from the HTML. What each source deliberately *did* disclose is
preserved: `is_this_an_s` still shows "engine claims: BR+OCR at PDH", `where_is_the_stop`
still prints the four candidate stop prices, `which_signal` still gives the two dot
times — and g75 still shows no setup name at all, because naming it invites him to
answer the name instead of the chart.
