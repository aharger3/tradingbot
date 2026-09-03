# G7.1 / homework — "the 3 stocks I believe are S trades"

Austin, 2026-08-29:

> "next homework is the 3 stocks that you believe are s trades, dont mark just timeframe
> and 6 levels, and i say yes or no and mark what you need and if not s i say why. but 84
> percent and ocr need to be higher in the batch because those are probably broken."

Built, not served.

| artifact | path |
|---|---|
| builder | `research/g71_homework_build.py` |
| page | `research/g71_homework.html` (516,350 bytes, 30 cards) |
| served record + answer key | `research/decks/g71-homework-s3-manifest.jsonl` |

Rebuild: `python research/g71_homework_build.py --seed 71 --slates 10`

---

## What this instrument is

Every deck we have built until now measures **recall** — did the engine find the day he
would have traded. This is the mirror: **precision**. Every card is a symbol-day the
engine *claims* is an S, and the only question is whether he agrees.

"I believe this is an S" means `sgrade == "S"` on the two-year book
(`research/bt2y_trades.json`, 76,019 signals, generated 2026-08-29) — i.e.
`research/downgrade.py`, **his** ladder. Not the legacy `A+/A/B/C/X`, which is not a
grade and cannot answer this question.

That is the point of the card. **17 of the 30 cards are graded `X` by the legacy
engine** — the engine would have stayed silent on more than half of what
`downgrade.py` calls S. Only 3 of 30 were actually traded. A YES on an `X` card is a
direct measurement of the wound in `DIRECTION.md`: *zero of his 34 held-out S days were
graded S by the engine.*

## Card contents — what is on it, and what is deliberately not

- The chart: **1-minute, 09:30–11:00 ET, 90 bars**, static SVG rendered in Python by
  `research/probe_chart.py` (`marks=[]`). Verified: **0 entry lines, 0 stop lines, 0
  `usermark` placeholders** in the served HTML.
- **His six levels**, PDH/PDL (blue), PMH/PML (purple), ORH/ORL (teal). `probe_chart`
  only lets a level widen the frame by 25% of the session range, so far levels drop off
  the picture; the card names those below the chart with price and side (`off this
  chart: PDH 417.16 above`). **All 30 cards account for all six levels** — 0 cards with
  a silently missing level.
- Under the chart, one line: **`engine claims:` BR / OCR / BR+OCR / 84% rule**. Label
  strings are `deck_ui.SETUPS`'. An 84% card is unreadable unless he is told it is a
  re-entry, so that label is required, not a leak.
- **Kept out of the page entirely**: legacy grade, traded flag, outcome, R, entry price,
  stop price, downgrade list. All of it is in the manifest. `data-export` on each card
  carries only `symbol / date / claimed_setup / bucket`.

## His inputs

1. **`is_s`** (required, single) — `YES — this is an S` / `NO — not an S`, plus an
   optional free-text note *"if yes: anything you'd mark here (entry, stop, level)"* —
   his "and mark what you need", as typing, not as pointer gestures (phone contract).
2. **`why_not`** (optional, multi-select) — the **eight downgrade variables in his own
   rulebook wording**, plus `chase`, `chop`, `too late in the window`, `not a trade at
   all — wrong chart to show me`, `other`, and a free-text box.

`why_not` is deliberately **not required**, or the progress counter would never
complete on a YES card. Progress counts `is_s` only.

A NO naming a variable says which `downgrade.py` check is blind. A NO naming
`chop` / `late` / `not a trade` says the card should never have reached him — that is a
T21 pre-filter failure, a different bug.

## Batch composition, and why

Natural setup mix of the 9,923 S-graded signals in the book:

| setup | signals | share |
|---|---:|---:|
| `break_and_retest` | 8,771 | 88.4% |
| `one_candle_rule` | 1,111 | 11.2% |
| `reentry_84_rule` | 41 | 0.4% |

Shipped batch — **10 slates of 3** (his "3 stocks"), one of each bucket per slate,
order shuffled inside the slate:

| bucket | cards | share | over-weight vs population |
|---|---:|---:|---|
| 84% re-entry | 10 | 33.3% | **~80x** |
| OCR | 10 | 33.3% | **~3x** |
| BR | 10 | 33.3% | control arm (0.38x) |

By the label actually printed on the card: `84% rule` 10, `OCR` 10, `BR+OCR` 9, `BR` 1
— nearly every S-grade B&R carries confluence (9,861 of 9,923 S rows have
`confluence: yes`), because that +1 is how a one-downgrade setup reaches S at all.

**BR is not padding.** Without a control arm, a low yes-rate on OCR/84% cannot be
separated from a low yes-rate on "the engine thinks anything is S", which is the open
question. A symbol-day is filed in exactly **one** bucket, priority 84% > OCR > BR, so
the BR arm is pure: no OCR-S and no 84%-S signal anywhere in its session.

Batch size: 30. Judgement cost is one tap plus an occasional reason — far cheaper per
card than a 60-card grading deck, and 10 per arm is the smallest number that separates
"mostly yes" from "mostly no" on each suspect.

## Guards

| guard | result |
|---|---|
| `build_deck.seen_card_ids()` — judged ∪ ever-served | **1,548** symbol-days excluded (1,147 judged + 401 served-only) |
| **repeat check** | **0 of 30 cards collide. PASS** (asserted in `main()`, build aborts otherwise) |
| duplicate inside the batch | 0 (asserted) |
| `t21_card_filter` reach ≤ 8R | 14 candidates dropped (`reach`) across the OCR and BR arms; 0 in the 84% arm |
| session length | ≥ 60 bars; all 30 cards are the full 90 |
| symbol concentration | 19 distinct symbols, max 2 cards each |
| recall regression gate | `python research/regression_gate.py` → **PASS**, exit 0 |

Eligible pool after the no-repeat guard: 84% **39**, OCR **810**, BR **4,140** — so the
84% arm is 10 of only 39 available days in two years. That arm cannot be made much
bigger without re-serving.

Selection inside a bucket: seeded shuffle, then stable-sorted by downgrades tripped
ascending, so the strongest claims go first. **25 of 30 cards trip zero downgrade
variables** — these are not marginal S calls.

## Delivery contract

Shell is `research/probe_page.py` unchanged — no new page shell was written. That gives
localStorage save on every tap, restore on load, the visible `saved` indicator, the
mobile flush on `visibilitychange`/`pagehide`/`blur`, Export → Copy all / Download
`.jsonl`, and the beforeunload guard. Chart is static SVG from `probe_chart.py`, no
canvas, no pointer marking.

HTML validated: tags balanced, 30 `<article class="card">`, 30 `<svg class="chart">`,
30 `is_s` / 30 `why_not` question blocks, all 30 `data-export` attributes parse as JSON.

## When the answers come back

**Save the exported `.jsonl` into `research/marks/` before anything else.** Card ids are
`SYMBOL_YYYY-MM-DD` and rows carry `answers`, so
`build_deck._judgement_key()` will register them and these 30 days become
permanently ineligible for future decks — the no-repeat guarantee only holds if the file
lands in a directory `mark_sources()` reads.

Note for whoever files it: `.gitignore:40` swallows `research/*.jsonl`;
`!research/*marks*.jsonl` (line 83) and `!research/probe_*.jsonl` (line 88) un-ignore it
only if the filename matches. Run `git status` and **look**.

The page itself is at `research/g71_homework.html`, which `.gitignore:44`
(`research/*.html`) does swallow. The page is regenerable from the builder and the
manifest is not, so this is acceptable — but if it should be committed, the one-line fix
is in the report body below.
