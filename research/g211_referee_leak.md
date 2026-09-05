# W9 referee — the 100-card blind deck is not blind. REFUTED.

**One sentence: every one of the 34 S cards is drawn wider than every one of the 66 "no" cards
and says a different cut time in its title, so a reader can score the deck 100 out of 100 without
looking at a single candle.**

Refereed: `research/g210_render_cards.py`, `research/g210_cards/` (100 PNGs + `index.json`),
against the source marks `research/marks/probe_s_sweep_2026-08-28.jsonl` (read-only, never
modified by this row). Ten PNGs opened by eye (5 S, 5 "no", seed 9211): AVGO_2025-05-02,
BABA_2025-08-28, MU_2025-06-25, MSFT_2025-03-13, NVDA_2025-04-29, AAPL_2024-11-04,
AMD_2024-10-24, NFLX_2026-07-02, MARA_2026-06-02, ACHR_2025-03-17. All 100 checked in code
(`research/g211_referee_leak.md` records the counts; the checks are the four rows below).

## Verdict per axis

| axis the row asked me to check | result |
|---|---|
| no candle drawn after the cut | **PASS** — 0 of 100 cards draw a bar past the cut; `bars_up_to` filters `timestamp <= cut` and the last drawn bar is the cut bar on all 100 |
| the cut equals his entry bar, or 10:00 | **PASS** — 0 of 100 mismatched; every card with `notes.min` cuts at that exact minute, every card without one cuts at 10:00:00 |
| no grade or engine field on the image | **PASS on text** — no S/A/C letter, no `A+/B/X`, no `signal_runner` field is drawn; the only text is symbol, date, "cut HH:MM", and the six structural level labels PMH/PML/PDH/PDL/ORH/ORL |
| **the deck is blind to his grade** | **FAIL — total leak, 100 of 100 cards** |

## The leak

His grade is a **deterministic function of the cut time**, and the cut time is drawn on the image
twice — in the title, and in the width of the chart.

| his grade | cards | cut time | 1-min bars drawn |
|---|---:|---|---:|
| S | 34 | 09:34 … 10:19, **never 10:00** | 5 … 50, **never 31** |
| none | 66 | **10:00:00, all 66** | **31, all 66** |

Zero overlap in bar count between the two classes. Zero overlap in cut time.

The cause is at the source, not in the drawing. In
`research/marks/probe_s_sweep_2026-08-28.jsonl`, `notes.min` — the minute he said he would have
entered — is present on **34 of 34** S cards and **0 of 66** "no" cards.
`g210_render_cards.py::entry_time_from_notes` returns non-`None` exactly when
`answers.s == ["s"]`, so `cut_t = entry_t if entry_t else "10:00:00"` copies the label straight
onto the x-axis. The script's own docstring anticipates the correlation — *"Cards graded 'no'
rarely carry a min"* — but "rarely" is in fact "never", and the deck was built on it anyway.

A reader given these PNGs scores 34/34 on S and 66/66 on "no" by reading the title. Any eye-test
number measured on this deck measures the title, not the chart. **Do not run a vision eye test on
`research/g210_cards/` as rendered, and do not quote a score from it.**

## The fix, in one line

Cut every card at the same clock time — a fixed 10:00, or a fixed per-card time drawn from
something that is not his answer — and drop `cut HH:MM` from the title. That costs the S cards
their "cut at his entry" framing; if that framing is wanted, the cut must come from an
engine-side or fixed rule that also fires on the "no" cards, so the two classes share a cut
distribution.

## One secondary flaw, not a leak

The final 5-minute bar is a **partial bucket on 91 of 100 cards** — `resample_5m` groups the
already-truncated 1-minute bars, so a cut at 09:44 draws a "09:40" 5-minute candle built from
five minutes but a cut at 10:00 draws a "10:00" candle built from one. It is drawn the same width
and weight as a complete bar. It does not leak the grade (it is identical across all 66 "no"
cards) but it misrepresents the last 5-minute candle on nearly every card. Drop the trailing
incomplete bucket.

## What was not touched

No mark file was written. `research/g210_cards/` is gitignored and was not committed or altered.
No shared module was edited.
