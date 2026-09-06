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

---

# H2 referee — pass 2 (second model, told to refute)

**Builder commit under review:** `7eb6aec7e3096918d5ea57a67581a9d140d9eef0`
("H2: tap-on-chart marks -- self-test 3 marks round-trip").
**Pass-1 referee:** `7a9defa4` (upheld, 3 defects). Nothing of pass 1 is reused below.
**Base at check time:** HEAD `ccd7fa0683ef7ebf10a539228d8a4a5b8a571d64` == `origin/main`;
`1539dd7f` and both H2 commits are ancestors.
**Pass-2 script:** `research/h2_referee_pass2.py`.

## Verdict: **refuted** — narrowly, and the code should be kept

The spec's own verify condition (`omen-10-0-spec.md`, H2: *"a self-test page round-trips
3 marks"*) **holds and reproduces independently.** What is refuted is (a) a factual claim
in the builder's report about what its test does, and (b) the row's fitness for the one
thing it exists for — Austin marking a chart on a phone. Nothing here says revert.

### Why pass 2 exists at all

`build_tap_selftest.py` drives itself, and `test_tap_marks.py` drives that page. Both
therefore inherit one script's idea of what a tap means, and pass 1 read the same pair.
`h2_referee_pass2.py` strips the self-driver off the built page — keeping the real shell
CSS/JS and the real `tappable=True` SVG byte-for-byte — and drives the handlers from
outside, so nothing the builder wrote decides what "correct" is.

### What reproduces (independently re-derived, not read off the page)

Candles re-derived from `build_tap_selftest.make_candles()` in Python; expected stop
computed by hand before the browser ran.

| check | result |
|---|---|
| one tap writes `localStorage` **in the same tick** as the dispatch (no timer) | holds — 1 key, already carrying `entry_i` |
| stop from a candle tap = that candle's low when the tap sits below the entry close | holds — tapped bar 3, hand-derived low **99.67**, page drew `STOP 99.67` |
| entry bar index from the x of the tap | holds — tapped bar 7 centre, exported `entry_i: 7` |
| three rail taps fill PT1/PT2/PT3 in order | holds |
| a 4th rail tap resets the card | holds |
| a fresh document over the same storage rebuilds the **SVG overlay**, not just the data | holds — the five `<text>` nodes inside the chart come back identical |
| second export byte-identical to the first | holds |
| runner slider restores its value (42) | holds |
| export keeps every pre-H2 field | holds — `type, probe, card_id, grade, answers, notes, symbol, date` all still present |
| export adds `entry_i, stop_p, pt[], runner_pct` | holds |
| cleared storage → no overlay, no data row, slider back to its 10 default | holds |
| a pre-H2 blob with **no `tap` key** restores without throwing and draws no overlay | holds |
| no `<canvas>`, no external `<script src>`, `pointerdown` present | holds |

Verify gate re-run by me at `ccd7fa06`: `regression_gate.py` PASS (no baseline-fired mark
went silent), `test_runner_stop.py` PASS (70 checks), `test_universe_single_source.py`
PASS (29 symbols, 25 backtested), `test_tap_marks.py` PASS (15 checks). No mark corpus
appears in either commit's `--name-only` (`test_tap_marks.py` matches a naive `marks`
grep and is not a corpus). The row wrote no book, correctly — it measures nothing, and
there is no dollar figure anywhere in it to name a fill for.

## Defect 1 (blocking the "works on a phone" claim) — a mis-tap cannot be corrected

`probe_page.py:410` and `:417-420`. The state machine has no undo, no clear control, and
no way back to a wrong first tap. Measured, not argued (phase F of the pass-2 script):

- tap the wrong candle → `ENTRY i=9`, committed;
- tap the *right* candle → does not fix the entry, it becomes the **stop** (`STOP 100.85`);
- tap the rail to escape → becomes **PT1**;
- further candle taps are explicit no-ops (`:410`);
- the only reset is the 4th-rail-tap branch at `:417`, which requires `pt.length >= 3` —
  **3 more junk rail taps** before the card clears.

So one fat-finger costs five taps and three fabricated price targets to undo. Austin does
this homework on a phone, away from this machine; the row's stated purpose is that he can
mark a chart there. `research/probes/README.md`-grade instruments are judged on whether he
can actually use them, and this one punishes the most likely gesture on the device it was
built for. Fix is small and local: a per-card clear control, or make the reset branch
unconditional on a long-press / a second tap on an already-set mark.

## Defect 2 (real, latent) — a partial `tap` blob throws and aborts the whole restore

`probe_page.py:485` assigns a stored blob verbatim with no merge against `defaultTap()`;
`:367` then reads `st.pt.length`. Seed storage with `{"tap": {"entry_i": 2}}` and the load
throws `TypeError: Cannot read properties of undefined (reading 'length')` **inside
`restore()`**, caught here off jsdom's `jsdomError` sink (a `window` `error` listener
cannot see it — `restore()` runs during parse). Observed consequences: the entry line
draws, the readout never updates (still reads `tap a candle for entry`), and because the
throw escapes `restore()`'s `forEach`, **every card after the bad one on a multi-card deck
never restores at all** — chips and notes included. The exported row then omits `stop_p`,
`pt` and `runner_pct` entirely, silently violating the contract `test_tap_marks.py`
asserts.

Today's writer always emits a complete blob, so this is reachable only via a corrupted or
truncated `localStorage` entry or a future schema change — but the blast radius is a whole
deck of Austin's answers, which is the one thing this repo is not allowed to lose. One
line fixes it: merge over `defaultTap()` at `:485`.

## Defect 3 (confirms pass 1) — no `touch-action` on the hit surfaces

`probe_page.py:172` sets only `cursor:crosshair`. Grepping the served page finds
**zero** occurrences of `touch-action`. `preventDefault()` on `pointerdown` does not
reliably cancel a touch scroll; `touch-action` is the mechanism that does. A scroll gesture
begun on the chart can therefore both pan the page and drop a mark. Independently
confirmed, still unfixed, still one line.

## Defect 4 — the builder's report describes a test that does not exist

The report states the self-test *"exports, **clears state, re-imports**, asserts
equality"*. It does neither. `build_tap_selftest.py` reloads with `localStorage`
**intact** and asserts the restore; nothing is cleared, and **the shell has no import path
at all** — the export drawer is one-way copy/download (`probe_page.py:737`), there is no
`type="file"` input and no import button anywhere in `probe_page.py`. Two of the four
row-specific referee checks handed to this pass ("asserts equality after a clear +
re-import", "an old export without the new fields still imports") are therefore not
merely unmet, they are untestable against this design. Pass 2 substituted the strongest
available equivalents — a genuine cleared-storage load (phase C) and a genuine pre-H2 blob
with no `tap` key (phase D) — and both hold. The spec never asked for import, so the code
is not at fault; the report is.

## What is NOT a defect (two pass-2 false starts, recorded so nobody re-runs them)

- Cleared storage exports the literal string `(nothing answered yet)` rather than nothing.
  That is the shell's pre-H2 placeholder (`probe_page.py:574`), not an H2 regression.
- `d.scrollIntoView is not a function` appears on every export click. That is jsdom's
  missing `Element.scrollIntoView` (`probe_page.py:576`), a harness artifact, discounted.

## Scope and sample size

One change per row respected: `git show --stat 7eb6aec7` = `probe_chart.py`,
`probe_page.py` and three new files, all one feature, and the spec row names both shell
files explicitly. No trades, no book, no month — the sample-size rule has nothing to bite
on here and no cell in this write-up carries a verdict about money.

## The thing neither pass caught until now

`tappable=True` has exactly **one caller in the whole tree** — the self-test page itself.
No deck, no daily homework page, nothing Austin is ever served, calls it. The instrument
is built and proven in a lab and is currently unreachable by the person it was built for.
That is arguably the next row rather than this one's failure, but "works on a phone" has
not been demonstrated on any page he will actually open, and defect 1 says what will
happen when it is.

## What I could not check

A handset. Everything above is jsdom and Python. Defects 1 and 3 both need someone to open
`research/probes/tap_selftest.html` on Austin's phone: try to scroll past the chart, then
deliberately tap the wrong candle and try to fix it.

---

# H2 referee — pass 3 (the repair round, third model, told to refute)

**Repair commit under review:** `a32eacd8867bbecbe5610bedeeab83e28d46f917`
("H2 repair: one-click undo/clear control on the tap readout, restore() merges stored
tap blobs over defaultTap() instead of assigning verbatim, touch-action:none on tap
hit surfaces"). It answers pass 2 (`90a3f9dd`), which refuted the original build
`7eb6aec7`.
**Base at check time:** HEAD `2eaa50bd`; `a32eacd8` and `1539dd7f` are both ancestors;
HEAD is an ancestor of `origin/main`.
**Pass-3 script:** `research/h2_referee_pass3.py` — a new jsdom harness that **strips the
self-test page's own driver script** and drives only the shared shell as served. It shares
no code with `build_tap_selftest.py`'s driver, with the builder's `h2_repair_verify.py`, or
with either earlier referee script. Every expected value (entry bar, stop price, the three
rail prices) is computed in Python from the served SVG's `data-ohlc` / `data-lo` / `data-hi`
before the browser runs. **34 of 34 checks pass.**

## Verdict: **upheld** — all three pass-2 defects are genuinely repaired; 4 open defects, none blocking

## The three pass-2 defects, re-tested from scratch

| pass-2 defect | pass-3 result |
|---|---|
| **1 (blocking)** no undo — a mis-tapped entry cost 5 taps and 3 fabricated price targets | **fixed.** One click on the readout clears the card: overlay all hidden, readout back to `tap a candle for entry`, stored `entry_i`/`stop_p` null and `pt` empty **in the same tick**, a second click on an already-clear card is a byte-for-byte no-op, and the card is immediately markable again (re-tapped bar 3 straight after, `entry bar 3`). |
| **2 (latent)** a partial stored blob threw inside `restore()` and killed every later card | **fixed, and I tested the blast radius pass 2 could only infer.** I cloned the card into a genuine **two-card** deck, seeded card 1 with `{"tap":{"entry_i":2}}` and card 2 with a complete blob. No jsdom error; card 1 renders `entry bar 2`; **card 2 still restores in full** — `ENTRY i=5`, `STOP 99.70`, `PT1 101.00`, runner slider back to 33. On the pre-repair code that second card was dead. |
| **3** no `touch-action` on the hit surfaces | **fixed.** The served rule is `.chart .taphit, .chart .railhit{cursor:crosshair; touch-action:none}`. Still unobservable without a handset — the CSS is now correct, the gesture is not proven. |

## The rest of the row, independently re-derived (nothing read off the builder's test)

| check | result |
|---|---|
| one tap writes `localStorage` synchronously, no timer | holds — exactly 1 key exists the instant `dispatchEvent` returns, already carrying `entry_i: 7` |
| entry bar index from the tap's x | holds — tapped bar 7, drew `ENTRY i=7` |
| stop = the tapped candle's **low** when the tap sits below the entry close | holds — bar 3's low, hand-computed **99.67** in Python, page drew `STOP 99.67` |
| three rail taps → PT1/PT2/PT3 at the tapped prices | holds — 100.5370 / 100.7793 / 101.1024, stored values match to 1e-6 |
| restore rebuilds the **SVG overlay**, not only the data | holds — a fresh document over the same storage returns the five `<text>` nodes identical; a data-only restore would fail this |
| second export byte-identical to the first | holds |
| runner slider restores (42) | holds |
| export keeps every pre-H2 field **and** adds the new ones | holds — `type, probe, card_id, grade, answers, notes, symbol, date` plus `entry_i, stop_p, pt, runner_pct` |
| a pre-H2 blob with no `tap` key loads without throwing and draws no overlay | holds |
| no `<canvas>`, no external `<script src>`, pointer events present | holds — 0 canvas, 0 script src, 3 `pointerdown` |
| the served page is exactly what its generator produces | holds — re-ran `build_tap_selftest.build()` in memory: byte-identical to the committed 42,591-byte page, so nothing was hand-edited into the HTML |

**"asserts equality after a clear + re-import" is still untestable, and correctly so.** Pass 2
established there is no import path anywhere in the shell; I re-confirmed it (`type="file"`
occurrences in the served page: **0**). The spec never asked for import. The strongest
available equivalents — a real cleared-storage load, a real pre-H2 blob, and now a real
one-click clear followed by a re-mark — all hold.

## Verify gate, run by me at HEAD `2eaa50bd` (`a32eacd8` is an ancestor)

- `research/regression_gate.py` — **PASS**, no baseline-fired mark went silent
- `research/test_runner_stop.py` — **PASS**, 70 checks
- `research/test_universe_single_source.py` — **PASS**, 29 symbols, 25 backtested
- `research/test_tap_marks.py` — **PASS**, 15 checks
- `research/h2_repair_verify.py` (the builder's) — **PASS**, 8/8
- `research/h2_referee_pass2.py` (pass 2's, rerun unmodified) — all blocking checks pass; its
  two prose notes ("no clear control", "3 rail taps to escape") are **stale** — that script
  looks for a button and never simulates the new click, and my phase C proves the control works
- `research/h2_referee_pass3.py` (mine) — **34/34**

## Defects (4, none blocking)

**1. Nothing in the test suite guards the undo.** `a32eacd8` touched three files and
`research/test_tap_marks.py` is not one of them — it still runs the same 15 checks it ran
before the repair, none of which exercise the clear path. The only committed coverage is
`h2_repair_verify.py` and this file's `h2_referee_pass3.py`, neither of which is in the
`verify:` line. The next edit to the shell's JS can silently remove the one-click undo and
every gate stays green. The fix is three lines in `test_tap_marks.py`.

**2. Clearing the marks also silently resets the runner percentage.** Measured: with the
slider at 42%, one click on the readout puts it back to 10%. `defaultTap()` owns
`runner_pct`, so the clear takes it with everything else. The runner % is a *separate*
judgement from where the entry and stop go, and the control's own label — "(tap here to
clear)" — reads as clearing the marks, not the slider. Small, but it is a silent loss of an
answer he gave, in a repo whose first rule is never to lose one.

**3. The clear control's markup lives outside the shared shell.** `probe_page.py` owns the
CSS and the click handler, both keyed to `[data-role="tapout"]`, but the
`<div class="tapout" data-role="tapout">` itself is emitted only by
`build_tap_selftest.py:232`. A future deck that turns on `tappable=True` and does not
hand-write that div gets tap marking with **no undo at all** — pass-2 defect 1, reintroduced
silently, with nothing to catch it. Either the shell should emit the readout whenever a card
has a tappable chart, or a test should assert its presence.

**4. The undo is all-or-nothing, and is itself a small target.** Correcting only a wrong
entry destroys a correct stop and three correct targets. And the recovery affordance for a
fat finger is a single line of 12.5px monospace text with `padding:8px 16px 0`, no
`min-height`, no `role="button"` and no keyboard focus. Reasoned from the CSS, not observed
on a handset.

**Two pass-1 defects are still open and were not in scope for this repair round.**
`research/probe_chart.py:16` still claims `tappable` "stays off by default so every existing
caller's SVG is byte-identical" — re-confirmed false: `data-h="%d"` sits in the shared
`if interactive or tappable:` branch at `:152-155`, so `build_omen_test1.py` and
`daily_homework.py` both emit an attribute they did not before (harmless, the sentence is
wrong). And `build_tap_selftest.py` still drops its phase-1 `results` array across the
reload (`:169` carries only `{before, row}`), so the standalone HTML page can print PASS with
a completely broken first phase; the Python test is not exposed to this.

**Pass-2's scope note still stands and is not a defect of this row:** `tappable=True` has
exactly one caller in the tree, the self-test page itself. No deck Austin opens uses it yet.

## The required standard checks

- **Sample size:** nothing to apply it to. This row trades nothing and measures nothing; the
  only counts are instrument counts (1 synthetic 20-bar card, 2 cards in my cloned deck, 34
  checks). No cell anywhere in the row or in this write-up carries a verdict about money.
- **Dollars:** the row publishes none — correctly, since nothing here fills. There is no
  figure to name a fill, an exit or a unit for. The repair commit message contains zero `$`.
- **Stamped books:** the row wrote none. `git show --name-only a32eacd8` touches nothing under
  `research/tape/`.
- **One change per row:** `a32eacd8` = 3 files, all under `research/`, no engine file, no flag.
  It does carry three code edits rather than one — but they are exactly the three defects pass 2
  named, in one instrument, and the rule exists so that a *book* cannot move for two reasons.
  This row has no book, so there is nothing to confound. Noted, not charged.
- **No mark file changed:** none of the mark corpora appear in `git show --name-only a32eacd8`
  or in `git status`.
- **Plain English:** the one string this row puts in front of Austin is the readout's
  "(tap here to clear)". Plain English, no jargon, no flag name.

## What I could not check

A phone. Everything above is jsdom and Python. Defect 4 and the `touch-action` fix both need
someone to open `research/probes/tap_selftest.html` on Austin's handset: try to scroll past the
chart, then deliberately tap the wrong candle and tap the line of text underneath to undo it.
