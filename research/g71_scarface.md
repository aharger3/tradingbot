# G7.1 / scarface — the Scarface corpus, inventoried

Austin: *"it has trade reviews from scarface years of data, it could pool all of those and
then those backtest results would be astronomical."*

**The idea is good and the data is real. But the trade reviews are videos, not text, and
the alert text carries the option strike, not the chart level.** Both are solvable. What
is *not* solvable by pooling is the money gate — these are Scarface's judgements, and the
scarce input OMEN is short of is Austin's.

Scripts: `research/g71_scarface_inventory.py`, `research/g71_scarface_seq.py`,
`research/g71_scarface_candidates.py`, `research/g71_scarface_validate.py`,
`research/g71_scarface_recall.py`. Candidates: `research/g71_scarface_candidates.jsonl`.

---

## 1. Inventory — all 13 named files

Counts are messages; `sym/dir/lvl/out` are messages matching a symbol / direction /
numeric level / outcome word; `chart` counts messages with an image attachment or embed;
`vidlink` counts Zoom/YouTube/Vimeo links. From `research/g71_scarface_inventory.py`.

| file | msgs | from | to | sym | dir | lvl | out | all 4 | chart | vidlink |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| futures-trade-reviews.json | 152 | 2025-03-04 | 2026-07-21 | 72 | 8 | 62 | 87 | 1 | 11 | **79** |
| options-trade-reviews.json | 389 | 2025-02-19 | 2026-08-19 | 52 | 10 | 188 | 68 | 2 | 46 | **357** |
| scarface-alerts.json | **6692** | 2024-04-01 | 2026-08-21 | 3927 | 720 | 1260 | 1141 | 71 | **5066** | 97 |
| jdub-alerts.json | 4274 | 2024-04-02 | 2026-08-21 | 1801 | 183 | 644 | 596 | 88 | 2380 | 780 |
| trade-feedback.json | 4101 | 2024-04-01 | 2026-08-20 | 724 | 588 | 833 | 1157 | 78 | 944 | 26 |
| backtesting.json | 816 | 2024-08-13 | 2026-07-11 | 74 | 49 | 107 | 157 | 4 | 96 | 7 |
| live-sessions.json | 357 | 2024-03-31 | 2026-08-19 | 1 | 0 | 8 | 348 | 0 | 0 | **354** |
| pre-market-live.json | 535 | 2024-05-14 | 2026-08-21 | 4 | 0 | 3 | 4 | 0 | 8 | **518** |
| premarket-charts.json | 591 | 2024-04-02 | 2026-08-21 | 1 | 0 | 360 | 0 | 0 | **591** | 0 |
| swing-ideas.json | 2238 | 2024-09-09 | 2026-07-31 | 390 | 329 | 601 | 378 | 18 | 382 | 0 |
| trading-floor.json | **39527** | 2024-03-31 | 2026-08-21 | 4358 | 2778 | 5108 | 5105 | 114 | 3175 | 231 |
| youtube.json | 274 | 2024-03-19 | 2026-08-18 | 1 | 2 | 107 | 119 | 0 | 0 | **244** |
| futures-alerts.json | 4789 | 2025-02-28 | 2026-08-21 | 1195 | 470 | 755 | 964 | 57 | 1711 | 0 |
| *scarface-trade-reviews.json* | 267 | 2024-03-31 | 2026-04-08 | 253 | 1 | 68 | 265 | 1 | 2 | **264** |
| *jdub-trade-reviews.json* | 129 | 2024-03-31 | 2026-06-10 | 0 | 0 | 39 | 126 | 0 | 0 | **128** |

Authorship is clean and single-source where it matters: `scarface-alerts` is
**6691/6692 TonyMontana**; `jdub-alerts` is 4273/4274 Jdub; `futures-trade-reviews` is
151/152 MambaTrades. `options-trade-reviews` is Neto Moreno (234) + Hayden (127).

### Finding 1 — the "trade review" channels contain no trade reviews

They contain **links** to them. 357/389 options, 79/152 futures, 264/267
scarface-trade-reviews, 128/129 jdub, 354/357 live-sessions, 244/274 youtube. A typical
row is a Zoom share URL and a passcode (`discord_data/options-trade-reviews.json` id
`1341885333280784478`). The `all 4` column — messages carrying symbol + direction + level
+ outcome together — is **1 or 2** in every review channel. Any pipeline pointed at these
files for text will return nothing.

### Finding 2 — the alert text carries the option STRIKE, not the chart level

This is the one that would have silently poisoned a backtest. In `scarface-alerts.json`:

- **481** messages match `<number> calls|puts` — an option strike.
- **49** messages state a level in context (`level|retest|reclaim|pdh|pdl|hod|lod ... <price>`).
- 17 carry both.

`TOOK 227.5 AAPL calls looking for HOD` — 227.5 is the contract, not the retest level. A
strike is typically slightly OTM at entry, so it sits *just outside* the day's range. My
first pass scraped any decimal as a level and got 22.6% "wrong" against real bars; the
misses were near-misses with `.5` endings — NVDA 172.5 vs day high 172.40, AAPL 257.5 vs
257.34, NVDA 187.5 vs 187.23. Those are correctly-read strikes, not extraction errors.
`research/g71_scarface_candidates.py:34-39` now splits `option_strikes` from
`level_in_context`, and T1 correctly collapses **207 → 94 rows**.

**The break-and-retest level is drawn on the chart image, not written in the text.**

### Finding 3 — the outcome is almost never stated, and does not need to be

Of 1,129 scarface (day, symbol) sequences, **83** carry an outcome word. That is not a
blocker: given symbol + date + direction + level, the outcome is *computed* by replaying
bars through `stop_rule.stop_fill_price()`, exactly as `align_reviews_v2.py` already does.
Never take the claimed outcome — a coach's posted review is survivorship-curated.

---

## 2. What already exists — do not rebuild

| script | what it does | state |
|---|---|---|
| `_mine_trade_reviews.py` | keyword-scores discord for judgement language | **stale path** (`C:\Users\aharg\tradingbot\...`, pre-Desktop move); scoring only, no structure |
| `parse_reviews.py` | title → date/ticker/PnL from **transcripts** | works; 181 hits |
| `extract_reviews.py` | DeepSeek LLM → ticker/dir/entry/target/stop/outcome from transcript bodies | works; 181 rows in `reviews_extracted.json` |
| `align_reviews.py` | first-touch entry, guesses the year | superseded (23% win = "buy every touch") |
| `align_reviews_v2.py` | runs the real `BreakAndRetestDetector` state machine | correct approach; **only 22 rows survive** |

**The existing pipeline targets video transcripts, not Discord.** `youtube_data/` holds
**820** transcripts and `circle_data/transcripts_text/` **294** — 1,114 on disk, of which
**181** are titled "trade review". That is Austin's "years of data", and it is already
downloaded.

### Finding 4 — the transcript pipeline loses 88% of its input, to three fixable bugs

181 extracted → 22 aligned. Where it goes (from `reviews_extracted.json`):

| loss | rows | cause |
|---|---:|---|
| entry_level null | 37 | LLM found no entry |
| stop_level null (entry ok) | 52 | stop is spoken structurally ("under the pivot"), not as a number |
| **entry == stop** | **26** | prompt bug — collapses the two; `align_reviews_v2.py:64` then rejects as `bad_stop` |
| usable distinct risk | 66 | |
| **survive alignment** | **22** | the rest die in year-guessing |

`align_reviews.py:31` scans `YEARS=[2025,2024,2023,2022]` and resolves the year by testing
whether the level falls in that day's range. **The year is not unknown.** The Discord post
that carries the video link is timestamped.

### Finding 5 — the date join works, and it is free

Transcript filenames *are* YouTube video ids (`youtube_data/0aoKhSUs-LM_transcript.txt`).
Discord posts across the review/youtube/live channels carry **1,309 distinct video ids**.

- **662** of 820 youtube transcripts join to a dated Discord post.
- **119 of the 181** trade-review transcripts join.

The post date is consistently **the trade date + 1** (post `2024-10-05`, LLM read
"October 4"; post `2025-03-18`, "March 17"), and the LLM's own `date_str` cross-validates
it. Year-guessing can be deleted outright.

---

## 3. Finding 6 — the payoff is recall, not the backtest

`research/g71_scarface_recall.py`. Scarface's in-window alert days are an **independent
second labeller** asserting a tradeable setup existed. Austin's recall sample is 34
S-days; this is 365. Replaying them through `research.t4_engine_recall.run_day`:

| on 200 Scarface T1+T2 in-universe days | n | % |
|---|---:|---:|
| OMEN fired at least once | 93 | 46.5% |
| **OMEN silent** | **107** | **53.5%** |
| fired in Scarface's direction | 72 | 36.0% |
| fired **only** in the opposite direction | 21 | 10.5% |

46.5% sits right alongside the 52.9% S-day recall in `DIRECTION.md` — an independent
corroboration of the recall wound at **6x the sample size**, from a labeller who has never
seen the engine.

**This flags a conflict with T1.** `research/t1_entry_minute_autopsy.md` reports the engine
is *never* silent on Austin's S days (0 of 34) and only mis-grades them `X`. Here silence
is the dominant failure at 53.5%. The two samples are built differently — Austin's cards
come from decks the engine had data for, this set does not — so the likely reading is
**selection bias in the graded deck**, and T1's "never silent" may not generalise. Worth
one agent-hour to confirm before any recall work is scoped off T1's conclusion.

---

## 4. How many NEW usable reviews

`research/g71_scarface_candidates.py` keys on (day, symbol) inside 09:30–11:00 ET
(UTC−4/−5 by month) and diffs against `build_deck.marked_card_ids()` = **1,147**.

**1,901 distinct symbol-days; 1,720 NEW; 181 overlap Austin.**

| tier | definition | rows | distinct NEW | needs |
|---|---|---:|---:|---|
| **T1** | direction + level in context | 94 | 83 | nothing — usable today |
| **T2** | direction + chart, level on the image | 587 | 482 | vision |
| **T3** | chart only, no direction in text | 937 | 778 | vision + direction inference |
| **T4** | text only, no chart, no direction | 730 | 655 | low value, mostly commentary |

By source: Scarface 967 in-window (T1 113 / T2 294 / T3 535), trading-floor 1,013
(members, mixed quality), members 135, Jdub 111, futures 60, swing 55.

T1 validated against real bars (`research/g71_scarface_validate.py`, n=88 in universe):
**77.3% of levels sit in the day's actual range** (66 direct, 2 after 10:1 NVDA split
adjustment). The residual 22.7% is the symbol carry-forward heuristic attributing a level
to the wrong ticker in multi-symbol messages — fixable, not fundamental.

### Realistic yield

| source | new records | vision? |
|---|---:|---|
| Scarface T1+T2 as **recall labels** (symbol+day+direction, no level needed) | **365** | no |
| Transcript reviews after the 3 fixes (date join, entry/stop prompt, structural stop) | ~150 | no |
| Scarface T2+T3 level extraction from charts | ~600 | **yes** |
| **total** | **~1,100** | |

`discord_data/images/` already holds **9.5 GB**: 5,518 scarface, 7,294 jdub, 1,187
trade-feedback PNGs. No re-scrape needed.

### Corpus size

- Austin's judged symbol-days today: **1,147** — unchanged, untouched.
- Scarface/coach candidates: **~1,100 usable of 1,720 new**, in a segregated file.
- Combined addressable pool: **~2,250 symbol-days**, in **two corpora that must never merge**.

---

## 5. The pipeline

```
A1  discord video-id -> post-date index        (1,309 ids; 662 transcripts join)   2h
A2  re-run extract_reviews.py with the date supplied and a fixed prompt
      - forbid entry == stop (26 rows lost to this)
      - when the stop is structural, emit stop_basis:"pivot" not null (52 rows)     2h
A3  align via align_reviews_v2.py with EXACT date; delete the YEARS scan            1h
A4  alert-channel recall labels - scripts written, just run                         1h
    -> first real number here: ~515 new labelled records, no vision
B1  vision pass over 5,518 scarface PNGs: read the drawn level + direction          6h
B2  compute outcomes: replay bars through stop_rule.stop_fill_price(), never the
      claimed outcome (survivorship)                                                3h
B3  dedup vs marked_card_ids(), validate level-in-range, write report               2h
```

**~16 agent-hours total; the first useful number at ~4h (A1–A4).** B1's real cost is the
vision API over 5.5k images, not agent time.

### Fix for `align_reviews.py` — the exact diff

```diff
--- a/align_reviews.py
+++ b/align_reviews.py
@@ -13,7 +13,10 @@
 MONTHS = {m.lower(): i for i, m in enumerate(month_name) if m}
-YEARS = [2025, 2024, 2023, 2022]
+# The year is NOT unknown: the discord post carrying the video link is timestamped,
+# and 662 of 820 transcripts join to one by video id. Scanning years and accepting
+# whatever year happens to bracket the level is how 159 of 181 reviews were lost.
+YEARS = [2025, 2024, 2023, 2022]   # fallback only, when no discord post joins
 SKIP = {"SPX", "ES", "NQ", "MNQ", "MES", "RTY", "YM"}  # not on Polygon equity API
```

with `resolve_and_score()` taking an optional `trade_date` (post date − 1 business day,
cross-checked against the LLM's `date_str`) and skipping the `for yr in YEARS` loop
entirely when it is present.

---

## 6. The boundary — and why "pool it" is the one thing not to do

`research/g71_scarface_candidates.jsonl` carries `judged_by:
"scarface_or_coach_NOT_austin"` on every row. It is **not** a mark corpus, is not in
`LEGACY_MARK_FILES`, and must not be added to `marked_card_ids()`.

Per `CLAUDE.md`, the scarce input is *Austin's* judgement, and the grade ladders are
already a live hazard. Scarface's calls are a **third** ladder. Pooling them would:

1. Contaminate the S/A/C ladder with a different trader's risk tolerance;
2. Break the no-repeat guarantee — 181 of these symbol-days Austin has already judged, and
   serving them back to him as fresh cards is the failure mode that has already fired
   three times;
3. Not move the money gate anyway. Mean R is bounded by `wT − (1−w)`; more rows from a
   different trader change `w` and `T` toward *his* system, not toward the gate.

**What this corpus is actually for: recall and precision, as a second opinion.** 365 days
where a professional traded and OMEN was silent 53.5% of the time is the largest
engine-independent recall signal in the repo. That is worth having. It is not a bigger
backtest.

### .gitignore note

`research/g71_scarface_candidates.jsonl` is swallowed by `.gitignore:40`
(`research/*.jsonl`) — confirmed with `git check-ignore -v`. **This one is fine and needs
no un-ignore rule**: it holds no human judgement that cannot be recreated, and
`research/g71_scarface_candidates.py` regenerates it byte-for-byte from `discord_data/`.
Flagged only because the trap has fired twice and the next agent should not add an
un-ignore rule reflexively — the rule protects *irreplaceable* files, and this is not one.
The judgements it derives from live in `discord_data/*.json`, which are committed.
