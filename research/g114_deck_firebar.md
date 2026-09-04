# g114 — fire-bar truncation on the mixed deck

Row S5. Austin, 2026-09-04: fill = market order at candle close.

## What changed

`research/build_deck.py`:

- Added `CARD_CUTOFF = "09:50"` (line 54, next to `SESSION_START`/`SESSION_END`).
- Added `truncate_to_reference_bar(candles)` (lines 57-65): walks a card's
  candle list and stops (break, not filter) at the first bar whose `HH:MM` is
  past `09:50`, so it returns every bar from `09:30` through `09:50` inclusive
  and no further.
- `pick()` (the fire/silent bucket-append site, was line ~383): the dict
  appended to `bucket` now stores `truncate_to_reference_bar(candles)` under
  `"candles"` instead of the raw `candles` list. Detection (`day_fires`,
  the T21 pre-filter, `orh`/`orl`) still runs on the untruncated
  09:30-11:00 `session_candles()` result earlier in the same loop iteration —
  only what gets written into the card (and therefore into `DAY_DATA` in the
  HTML) is cut.

No change to `session_candles`, `day_fires`, `card_filter`, or `write_deck` —
the cut happens once, at the point a card's candles are captured, which is the
minimal surgical spot.

## How the deck was rebuilt

Command (from the file's own docstring, `research/build_deck.py:17-18`):

```
python research/build_deck.py --name g114_firebar_test --n 60 --seed 7
```

Run from repo root. This exercised the real pipeline against the archived data
already on this machine (`data_archive/`, present, ~17k symbol-days).

Tail of the run's own report line (before the pre-existing final assert — see
"Anything missing" below):

```
probed 50  fire=25 silent=24 prefilter-dropped=1
T21 pre-filter: 1 of 61 probed days dropped (1.6%), 60 kept
    reach         1
Traceback (most recent call last):
  ...
AssertionError: deck repeats already-judged days: ['AAPL_2024-05-01', ...]
```

The HTML and manifest are written by `write_deck()` *before* that assert, so
the deck itself is a real artifact of the run — the assert fires afterward on
an unrelated pre-existing bug (below). Verified by reading it back
programmatically, then deleted the throwaway test deck
(`research/decks/g114_firebar_test.html` /
`research/decks/g114_firebar_test-manifest.jsonl`) rather than leaving a stray
file in `research/decks/`.

## Bar counts after the change

Loaded the written deck's `DAY_DATA` and joined it against the manifest's
`engine_fires_that_day` to split fire vs. silent:

```
fire    count=30  bar-counts={21}  last-timestamp={'09:50'}
silent  count=30  bar-counts={21}  last-timestamp={'09:50'}
```

All 60 cards (30 fire, 30 silent) end at exactly 21 bars (09:30-09:50
inclusive, minute bars), same count, same last timestamp, both buckets. No
length or endpoint tell between fire and silent cards.

Unit-level check on a synthetic frame (no archive data required), confirming
`truncate_to_reference_bar` in isolation:

```python
candles = [90 synthetic 1-min bars, 09:30 .. 10:59]
out = truncate_to_reference_bar(candles)
# len(out) == 21, out[-1].timestamp[11:16] == "09:50"
```
Passed.

## Verify

1. `grep -q "09:50" research/build_deck.py` — exit 0 (the string appears at
   the `CARD_CUTOFF` definition and its comment).
2. Rebuild command above ran end to end against real archived data on this
   machine and produced a real 60-card deck HTML + manifest; confirmed above.

## Anything missing / pre-existing issue found (not part of this row)

`main()` in `build_deck.py` calls `write_deck()` (which writes
`<name>-manifest.jsonl`) and only afterward computes
`repeats = set(ids) & seen_card_ids()` — but `seen_card_ids()` is called with
no `exclude` argument, so it globs `<name>-manifest.jsonl` (the file the same
run just wrote) into "already served" and every fresh deck name trips its own
repeat assertion. This reproduces on the unmodified file too (not introduced
by this change) — the deck HTML/manifest still get written correctly before
the crash, which is how this row's rebuild and bar-count check above were
verified, but `python research/build_deck.py` as documented does not exit 0
on this machine today. Flagging rather than fixing, since it's out of scope
for S5 (fire-bar truncation only) and touches the no-repeat guard, which
SWARM.md calls the most sensitive code in the repo.
