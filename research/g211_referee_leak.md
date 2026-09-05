# g211 — referee W9: is the g210 vision deck actually blind?

**No. The deck is not blind, and the leak is total.** The chart's cut time *is* Austin's grade: all
34 cards he graded **S** are cut at his entry minute, all 66 he graded **none** are cut at exactly
**10:00**. The cut is printed in every title (`(1-min, cut 09:47)`), and it is also readable off the
last x-axis tick and off the candle count. A reader that never looks at a candle and answers
"**S** if the title does not say 10:00" scores **100% precision and 100% recall** on this deck
against a 30.5% baseline. Any W9 result above baseline is therefore uninterpretable — it measures
whether the reader can read a clock, not whether the S signal is visual.

`refuted = true`. The W9 eye-test must not be scored on the current PNGs.

---

## What I checked, and what passed

Ten PNGs opened at random (seed 9): `AVGO_2025-10-10`, `PLTR_2025-05-08`, `SOFI_2024-11-07`,
`IWM_2026-05-01`, `BABA_2025-08-28`, `TSM_2026-02-02`, `COIN_2026-04-07`, `CRM_2025-09-19`,
`AMZN_2025-06-12`, `NFLX_2026-07-02` — plus `research/g210_cards/index.json` (100 rows) and a full
read of `research/g210_render_cards.py`.

| check | verdict |
|---|---|
| any candle drawn after the cut | **clean** — on all 10, the last 1-min candle is the cut minute; `bars_up_to()` filters `timestamp <= cut_t` and nothing else reads `bars_full` |
| grade / engine field on the image | **clean** — only symbol, date, `1-min, cut HH:MM`, price axis, time axis, and the level labels PMH/PML/PDH/PDL/ORH/ORL appear; no grade, no R, no outcome, no signal marker |
| filename leaks a grade | **clean** — `<SYMBOL>_<YYYY-MM-DD>.png` only |
| y-axis range leaks the future | **clean** — limits come from pre-cut candles plus prior-day/premarket levels, all knowable at the cut |
| **cut equals his entry bar** | **fails as a blind design** — it equals his entry bar exactly when he graded S, and 10:00 exactly when he did not |

## The leak, in one table

`research/marks/probe_s_sweep_2026-08-28.jsonl`, read-only, 100 rows:

| his grade | rows | carries `notes.min` | cut used |
|---|---:|---:|---|
| S (`answers.s == ["s"]`) | 34 | **34 / 34** | his entry minute — 09:34 … 10:19, **never 10:00** |
| none (`answers.s == ["no"]`) | 66 | **0 / 66** | `DEFAULT_CUT` = **10:00:00**, all 66 |

`notes.min` present ⟺ graded S, with no exceptions in either direction. The renderer turns that
field into the cut, so the cut carries the label with perfect fidelity.

### The trivial reader

| rule | precision | recall | vs W9 baseline |
|---|---:|---:|---|
| "S if the title's cut ≠ 10:00" | **100.0%** (34/34) | **100.0%** (34/34) | baseline 30.5% |
| bar-count variant: "S if the 1-min panel does not hold exactly 31 candles" | **100.0%** | **100.0%** | title text is not even needed |

Every `none` card holds 31 candles (09:30–10:00). S cards hold 5 to 50. Cropping the title does not
fix this.

## Where it enters the code

`research/g210_render_cards.py`, three lines acting together:

- `entry_time_from_notes(card)` — returns a time only when `notes.min` exists, which in this deck
  only S cards have.
- `cut_t = entry_t if entry_t else DEFAULT_CUT` in `render_card()` — makes the cut a function of the
  grade.
- `ax1.set_title("%s  %s  (1-min, cut %s)" % (symbol, day, cut_t[:5]))` — prints it.

The docstring's claim — *"blind — nothing after the cut"* — is true and beside the point. Nothing
after the cut is drawn; **the cut is the answer**.

## Two smaller defects found in passing

1. **The last 5-minute candle is a partial bucket drawn as a closed bar.** `resample_5m()` groups
   whatever bars survive the cut, so `AVGO_2025-10-10` (cut 09:47) shows the 09:45 bucket built from
   three minutes as if it had closed. Not lookahead — but a reader is being shown a 5-min candle
   that does not exist.
2. **The opening range can be incomplete and is still labelled ORH/ORL.** `opening_range()` runs on
   the post-cut bars with `< 09:35`, so the one S card cut at 09:34 gets an "ORH/ORL" drawn from
   four minutes, not five.

Also factual, not a leak: `research/g210_render_cards.md` says the card directory is *gitignored*.
It is not — all 100 PNGs and `index.json` (which carries `his_grade`) are tracked and committed, so
the answer key ships inside the folder a reader would be pointed at.

## What has to change before W9 can be scored

The cut must be drawn from a distribution that does not depend on his grade.

1. **Sample each `none` card's cut from the S cards' cut distribution** (09:34–10:19, the 34 observed
   minutes) rather than pinning it at 10:00. This keeps "decide at a plausible early minute" and
   destroys the correlation. Record the drawn cut in the index only.
2. **Drop the cut from the title.** Keep symbol and date if a card id is wanted; the cut belongs in
   `index.json`, never on the pixels.
3. **Re-render, then re-run this referee** on a fresh random 10 plus a check that cut-time and
   bar-count are independent of `his_grade` (a chi-square or a simple "does any cut value appear in
   only one grade class" test).
4. Move `index.json` out of `research/g210_cards/`, or hand readers an explicit file list, so the
   answer key is never in the directory being read.

Until 1–3 land, no vision-reader score from this deck may be quoted, and the W9 conclusion
("the signal is visual") cannot be reached from it either way.
