# H2 referee — tap-on-chart marking

**Builder commit:** `7eb6aec7e3096918d5ea57a67581a9d140d9eef0`
("H2: tap-on-chart marks -- self-test 3 marks round-trip")
**Referee commit base:** HEAD `1f26cf73` (7eb6aec7 is an ancestor; `1539dd7f` is an
ancestor of HEAD; HEAD == origin/main at check time).
**Referee script:** `research/h2_referee.py` — nothing below is taken from the
builder's own test; every value is re-derived here.

## Verdict: **upheld**, with 3 defects (0 of them move a number)

The spec's H2 verify condition — *"a self-test page round-trips 3 marks"* — is met, and
I reproduced every exported value from the raw candles and the SVG's own scale
attributes without running the builder's test.

## What I re-derived myself

| claim | how I checked it | result |
|---|---|---|
| `entry_i` = tapped bar | inverted `localXY`/`barAt` by hand from `data-padl`/`data-plotw`/`data-n` | **5**, matches |
| `stop_p` = tapped candle's low (long) | computed bar 12's low straight from `build_tap_selftest.make_candles()` — 99.70 — with no SVG involved | **99.7**, matches |
| `pt[0..2]` = three rail taps | computed `lo + (hi-lo)·{0.75,0.85,0.95}` from `data-lo`/`data-hi` | `[100.8399, 101.04186, 101.24382]`, matches to 1e-6 |
| `runner_pct` | slider `input` event → export | **35**, matches |
| every tap writes localStorage synchronously | read `handleTap` → `save(card)` → `localStorage.setItem(...)` inline, no debounce, no timer; then asserted the stored blob carries a `tap` key after phase 1 | confirmed |
| restore rebuilds the **SVG overlay**, not only the data | `restore()` ends `cards().forEach(... paintTap(card))`; my phase-2 check reads the `<text class="tap-*-t">` nodes out of the SVG and compares them, so a data-only restore would fail it | confirmed |
| re-export after reload is identical | second jsdom document over the same storage, byte-compared the two exports | identical |
| the self-test drives the **real** handlers | the page dispatches `pointerdown` on the served `.taphit`/`.railhit` rects; the listener that handles it is the one `probe_page.JS` installs on `document` — there is no copy of the state machine in the driver | confirmed |
| old export/blob without the new fields still loads | seeded localStorage with a pre-H2 card blob (`{picked, notes}`, no `tap`) — page restores, exports, and the row still carries every pre-H2 key (`type, probe, card_id, grade, answers, notes, symbol, date`) | confirmed |
| no `<canvas>`, no external `<script src>`, pointer events present | grep of the served page | confirmed (the only external `<link>`s are the pre-existing Google-Fonts ones from the shell) |

## Verify gate, run by me at HEAD (7eb6aec7 is an ancestor)

- `research/regression_gate.py` — PASS, no baseline-fired mark went silent
- `research/test_runner_stop.py` — PASS, 70 checks
- `research/test_universe_single_source.py` — PASS, 29 symbols, 25 backtested
- `research/test_tap_marks.py` (the builder's) — PASS, 15 checks
- `research/test_omen_test1_page.py` (the other consumer of the shell) — PASS, 97 cards

## Defects

**1. The docstring's "byte-identical" claim is false for `interactive=True` callers.**
`research/probe_chart.py:9-16` says tappable "stays off by default so every existing
caller's SVG is byte-identical". The default call *is* byte-identical, but the new
`data-h="%d"` was added to the shared `if interactive or tappable:` branch, so every
`interactive=True` chart now carries an extra `data-h="330"` attribute it did not before.
Real callers: `research/build_omen_test1.py:490`, `research/daily_homework.py:735`.
Harmless in practice — neither reads `data-h`, and `test_omen_test1_page.py` still passes —
but the sentence in the file is wrong and should say "default callers", not "every existing
caller".

**2. No `touch-action` on the tap surfaces — a scroll gesture that starts on the chart
sets a mark.** `probe_page.py` CSS gives `.taphit`/`.railhit` only `cursor:crosshair`.
The handler calls `e.preventDefault()` on `pointerdown`, but on touch that does not cancel
panning (the event is not cancelable while `touch-action` permits a pan), so a finger swipe
begun anywhere on the 720×330 chart both scrolls the page **and** fires a tap. This is the
phone-first instrument, cards stack vertically, and the chart is the widest thing on the
card — so this will fire in ordinary use. Recovery exists but is awkward: only a rail tap
taken *after* stop and all three targets are set clears the card. Neither the self-test nor
jsdom can catch this. Suggested fix (one line, a follow-up row): `touch-action:none` on the
two hit rects, or gate the mark on a `pointerup` that moved less than a few pixels.

**3. The standalone HTML self-test can print PASS while its first half failed.**
In `research/build_tap_selftest.py`'s driver, `run()` records phase-1 checks into a local
`results` array and then calls `location.reload()` **without reporting them**; only
`{before, row}` is carried across in sessionStorage. After the reload, phase 2 compares the
restored marks to `prev.before` — and if phase 1 had drawn nothing, both sides are `null`
and every comparison passes. So the docstring's *"opening the file IS the test"* overstates
it: opened in a real browser, the page can read PASS with a completely broken tap path.
The Python harness is not exposed to this — `research/test_tap_marks.py` asserts phase 1's
export directly (`entry_i == 5`, `runner_pct == 35`, fixture shape) — which is why the row
still stands. Fix: stash `results` in sessionStorage alongside `before`/`row` and prepend
them in `report()`.

## Notes on the required standard checks

- **Sample size:** not applicable — H2 traded nothing and measured nothing. The only counts
  are instrument counts (1 synthetic 20-bar card, 5 taps, 1 slider move), and no verdict in
  the builder's report or in this one rests on a trade sample.
- **Dollars:** the row publishes none, correctly. Nothing here names a fill because nothing
  here fills.
- **Stamped books:** the row wrote no book, so there is nothing to stamp. `research/tape/`
  is unchanged by `7eb6aec7`.
- **One change per row:** `git show --stat 7eb6aec7` = 5 files, all in `research/`, all the
  one instrument (2 shared-shell files extended, 1 builder, 1 generated page, 1 test). No
  engine file, no flag, no second function.
- **No mark file changed:** none of the mark corpora appear in `git show --stat 7eb6aec7`
  or in `git status`.
- **Plain English:** nothing in this row reaches Austin yet — the page is a self-test with
  no question text. When a real teardown deck uses `tappable=True`, its card copy is that
  deck's job, not H2's.

## What I could not check

A real phone. Everything above ran under jsdom and Python; defect 2 is reasoned from the
pointer-events spec and the absence of `touch-action`, not observed on a handset. Before
this goes in front of Austin, someone should open `research/probes/tap_selftest.html` on
his phone and try to scroll past the chart.
