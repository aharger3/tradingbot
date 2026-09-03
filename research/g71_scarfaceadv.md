# G7.1 / scarface — ADVERSARIAL VERIFY of Finding 2 ("the text carries the STRIKE, not the level")

**Verdict: REFUTED.** Every headline count reproduces exactly. The *conclusion drawn from
them* does not survive: the shipped fix does not remove strikes from T1, its stated
mechanism is inert, and the post-fix level accuracy is unchanged from the number the fix
was written to cure. The real poisoning mechanism is symbol carryover, and it is still live.

Scripts (mine, read-only): `research/g71_scarfaceadv_recount.py`,
`g71_scarfaceadv_t1ab.py`, `g71_scarfaceadv_barcheck.py`, `g71_scarfaceadv_carryover.py`.

## What reproduces

| claim | mine | verdict |
|---|---|---|
| 481 msgs match `<n> calls\|puts` | 481 | exact |
| 49 msgs state a level in context | 49 | exact |
| 17 carry both | 17 | exact |
| T1 collapses 207 → 94 | 207 → 94 | exact |
| NVDA 172.5 / AAPL 257.5 / NVDA 187.5 are strikes | yes, verbatim in raw text | correct |

Authorship also clean: 6691/6692 TonyMontana.

## R1 — the fix leaks strikes into T1, 27% of the time

`LVLCTX` requires a keyword *before* the number, which is exactly how Scarface writes a
strike. 10 scarface messages have LVLCTX capture a number immediately followed by
`calls|puts`:

```
TSLA IF IT CAN RETEST 172.50 puts
AAPL retesting OB here, 252.50 calls in play if we get buyers stepping in
AAPL if we can get strong reclaim 202.5 calls is what I'll be looking for
Keeping a close eye on TSLA PDH reclaim for 427.5 calls
TSLA i want more of a retest 437.50 calls is what im looking for
```

In the shipped `research/g71_scarface_candidates.jsonl`:

- **31 of 94** surviving T1 rows have a `level_in_context` value that the same script
  also parsed as an `option_strike`.
- **25 of 94 (27%)** have *no other* level — their only level **is** the strike. All 25
  are `in_backtest_universe`. `AAPL_2024-08-21 lvl [227.5] strk [227.5]` is the report's
  own canonical poison example, and it survived the fix.

## R2 — the stated mechanism is inert

`g71_scarface_candidates.py:99` — `tier = "T1" if (direction and lvlctx) else …`.
`strikes` is never consulted for tiering; it only filters the unused `bare_numbers`
field. Delete the `STRIKE` regex entirely and T1 is still 94. There is no "STRIKE vs
LVLCTX split" gating anything — there is a keyword gate, and it is credited to the wrong
half of line 34-39.

## R3 — the collapse is mostly not about strikes

Of the 113 rows demoted out of T1 (`g71_scarfaceadv_t1ab.py`):
**44** have every decimal parsed as a strike; **64** contain no strike decimal at all.
57% of the 207→94 collapse is unrelated to option strikes — it is the keyword gate
throwing away rows for lacking a magic word.

## R4 — 481 vs 49 is a rigged denominator

`LEVEL = \b(\d{2,4}\.\d{1,2})\b` requires a decimal. Of the 481 strike messages,
**337 are integer-only** (`230 calls`) and could never have been scraped as a level. The
actual collision surface is **144**, not 481 — 3:1 over the 49, not 10:1.

## R5 — the post-fix validation was never run, and when run it shows no improvement

`research/g71_scarface_validate.py:22` reads `r["levels_text"]`, a field the current
schema does not emit. It dies `KeyError: 'levels_text'`. The published "22.6% wrong" is
a **pre-fix** number; nothing measured the fix.

I measured it (`g71_scarfaceadv_barcheck.py`, real polygon RTH bars, 65 T1 rows in the
backtest universe):

| slice | checked | level inside day's RTH range | MISS |
|---|---:|---:|---:|
| T1 whose only level is a strike | 25 | 20 (80%) | 5 |
| T1 rest | 40 | 30 (75%) | 10 |
| **all T1** | **65** | **50 (77%)** | **15 (23%)** |

**23% miss, versus the 22.6% the fix was written to cure.** No improvement. And the
strike-only slice is *more* accurate than the rest — the opposite of the claim's premise.

## R6 — the real mechanism: symbol carryover (`:82-84`), still live

```python
hit = TICK.findall(c)
sym = hit[0].upper() if hit else last.get(day)   # inherits the day's LAST ticker, unbounded
```

- 34% of in-window scarface messages (1909/5631) carry an inherited ticker.
- **225 of 362** days name more than one distinct ticker, so carryover crosses symbols.
- **51 of 55 (93%)** Scarface T1 rows aggregate at least one carried message.

The worst bar-check misses are exactly this, not strikes:

| row | level | actual RTH range |
|---|---:|---|
| QQQ_2024-07-05 | 167.5 | 491.59 – 496.60 |
| QQQ_2025-07-25 | 312.5 / 314.5 | 564.27 – 567.70 |
| QQQ_2025-03-21 | 242.96 | 472.90 – 481.61 |
| QQQ_2026-06-26 | 263.62 | 702.81 – 715.55 |

Another symbol's number stamped onto QQQ. No strike filter can touch this.

## R7 — second live mechanism: split adjustment

`NVDA_2024-05-10 level 910.42` vs polygon RTH `89.23 – 91.40`; `NVDA_2024-04-05 871.49`
vs `85.93 – 88.48`. Pre-June-2024 NVDA text prices are unadjusted; polygon bars are
split-adjusted. Nothing reconciles them.

## Not refuted / not found

- **Look-ahead: none in the extraction.** Window filter uses message `ts`; outcome is
  deliberately not taken from text (`docstring:11-13`) and is computed by replay. Sound.
- **Book contamination: none.** `grep -rl scarface_candidates --include=*.py` returns only
  the g71 scarface scripts. Nothing in `backtest_2y.py` or `signal_runner.py` consumes the
  jsonl. The "would have silently poisoned the backtest" is hypothetical — the 2,595-trade
  post-T0 book never saw a scarface level, before or after the fix.
- Minor: `in_window` DST guess `off = 4 if 3 <= month <= 10 else 5` (`:61`) is wrong for
  early March and late Oct/Nov. Affects unit membership, not look-ahead.

## Fix (NOT applied — diagnosis pass)

```diff
--- a/research/g71_scarface_candidates.py
+++ b/research/g71_scarface_candidates.py
@@ -36,7 +36,10 @@
 STRIKE=re.compile(r'(\d{2,4}(?:\.\d{1,2})?)\s*(?:strike\s*)?(?:calls?|puts?)\b',re.I)
-LVLCTX=re.compile(r'(?:level|retest|reclaim|pdh|pdl|hod|lod|above|below|holds?|break)\D{0,18}(\d{2,4}\.\d{1,2})',re.I)
+# A number followed by calls/puts is a STRIKE no matter what keyword precedes it.
+LVLCTX=re.compile(r'(?:level|retest|reclaim|pdh|pdl|hod|lod|above|below|holds?|break)'
+                  r'\D{0,18}(\d{2,4}\.\d{1,2})(?!\s*(?:strike\s*)?(?:calls?|puts?)\b)',re.I)
@@ -80,8 +83,11 @@
-            hit = TICK.findall(c)
-            sym = hit[0].upper() if hit else last.get(day)
-            if hit: last[day] = sym
+            hit = TICK.findall(c)
+            if hit:
+                sym = hit[0].upper(); last[day] = (sym, ts)
+            else:                       # inherit only within 10 minutes of the last named ticker
+                prev = last.get(day)
+                sym = prev[0] if prev and (et(ts)-et(prev[1])).total_seconds() <= 600 else None
@@ -92,7 +98,9 @@
             lvlctx  = sorted({float(x) for x in LVLCTX.findall(txt)})
+            lvlctx  = [x for x in lvlctx if x not in strikes]   # belt and braces
```

Then rewrite `g71_scarface_validate.py:22` to read `level_in_context`, and re-measure.
Do not quote the 22.6% or the 481:49 ratio again without it.
