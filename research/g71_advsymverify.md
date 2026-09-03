# G71 adversarial verify — track `symbols`, HIGH claim "the silent half runs out after one deck"

**Verdict: REFUTED.** The arithmetic reproduces exactly; the *definition of a fire* does not.

## The claim

> fresh never-served silent days inside the book window are SPY 23, AAPL 12, TSLA 3, NVDA 6,
> MU 8 — 38 for SPY+TSLA+AAPL, 32 for SPY+TSLA+NVDA. FIRE cards are plentiful (1,175).

`research/g71_symbols_trio.json` does say `SPY+TSLA+AAPL fresh_silent=38, fresh_fire=1175` and
`SPY+TSLA+NVDA fresh_silent=32`. The claim reports its script faithfully. The script is wrong.

## The defect

`research/g71_symbols_trio.py:124-125`

```python
for t in b["trades"]:
    fire[t["sym"]].add(t["day"])          # EVERY row, not the fired ones
```

`research/bt2y_trades.json` holds 76,019 rows with `status` =
`skipped_d` 69,624 / `fired` 3,487 / `skipped_tight_stop` 2,051 / `halted` 857. All 69,624
`skipped_d` rows are `grade: "X"`, and **X is not a grade — it means the engine should not have
fired.** So `fire[sym]` is "the engine emitted a rejected candidate", which is true on almost
every session: SPY has a book row on 468 of its 494 in-window archived days but only **62**
`fired` days. `fresh_sil` (`:139`) is therefore the count of days on which the detector produced
*literally zero objects of any grade* — a rarity, not a silent day.

The deck does not use that definition. `build_deck.pick():316` buckets on
`day_fires()` → `research/t4_engine_recall.py:run_day()[0]`, which is entries with
`status == "fired"` only (`t4_engine_recall.py:150-158`). A day whose only book rows are
`skipped_d` is a **SILENT deck card**.

## Recount (`research/g71_advsymverify_silent.py`)

seen = `build_deck.seen_card_ids()` = 1,578 judged-or-served symbol-days.

| sym | archived | in-window | book-days | fired-days | trio frSILENT | deck-def fresh SILENT (in-window) | fresh out-of-window |
|---|---:|---:|---:|---:|---:|---:|---:|
| SPY | 654 | 494 | 468 | 62 | 23 | **364** | 152 |
| AAPL | 658 | 498 | 483 | 84 | 12 | **361** | 156 |
| TSLA | 658 | 498 | 493 | 199 | 3 | **219** | 142 |
| NVDA | 658 | 498 | 490 | 108 | 6 | **351** | 153 |
| MU | 657 | 497 | 488 | 159 | 8 | **313** | 156 |
| QQQ | 660 | 500 | 489 | 71 | 7 | **340** | 146 |

SPY+TSLA+AAPL: 38 → **944**. SPY+TSLA+NVDA: 32 → **934**. Plus ~450 fresh archived days per trio
that sit *outside* 2024-08-21..2026-08-21, which the script excludes on principle
(`:137-139`) but `build_deck` can use — it runs the engine live and never reads the book.

## Live-engine spot check (`research/g71_advsymverify_live.py`)

The book-vs-replay gap is real but small. 30 random fresh in-window days per symbol that the
trio script calls FIRE and the fired-row test calls SILENT, run through `build_deck.day_fires()`:

| sym | disputed pool | deck-SILENT | deck-FIRE | <60 candles |
|---|---:|---:|---:|---:|
| SPY | 341 | 22/30 | 8 | 0 |
| TSLA | 216 | 18/30 | 12 | 0 |
| AAPL | 349 | 24/30 | 6 | 0 |

64 of 90 (71%) of the days the script discarded are silent by the deck's own function.
Extrapolated: 341·.73 + 216·.60 + 349·.80 ≈ 659, plus the 38 zero-row days ≈ **~700 usable
fresh silent cards for SPY+TSLA+AAPL — about 23 decks of 30-card silent halves, not one.**
No `<60`-candle attrition appeared in 90 draws, so `pick()`'s length filter is not a hidden tax.

## Checks that came back clean

- **Book identity:** the script reads the current 2,437-trade book (`meta.traded=2437`,
  generated 2026-08-29T03:14), which supersedes the 2,595-trade T0 book — see
  `research/g71_advscanners.md:89`. Not the 1,017-trade book. No defect.
- **Look-ahead:** none. Both counts are over archived sessions and a completed book; nothing
  peeks forward.
- **Reachability:** `fresh_sil` is reached and produces the reported numbers.
- **FIRE side:** 1,175 fresh FIRE for SPY+TSLA+AAPL is also inflated by the same bug (true
  fired-day figure is 49+149+71 = 269 fresh), but that half was never the claim's load-bearing
  half and 269 is still plentiful.

## Fix (not applied — diagnosis pass)

```diff
--- a/research/g71_symbols_trio.py
+++ b/research/g71_symbols_trio.py
@@
     for t in b["trades"]:
-        fire[t["sym"]].add(t["day"])
+        # build_deck.pick():316 buckets on day_fires() -> run_day()[0], which is
+        # entries with status "fired". A grade-X skipped_d row is NOT a fire --
+        # 69,624 of the book's 76,019 rows are exactly that, and counting them
+        # made SPY look like it had 23 silent days instead of 364.
+        if t["status"] == "fired":
+            fire[t["sym"]].add(t["day"])
         if t.get("traded"):
```

`fresh_fire`/`fresh_silent` should also carry a note that out-of-window archived days
(~150/symbol) are deck-eligible even though their silence is unmeasured in the book.
