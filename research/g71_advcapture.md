# G7.1 — adversarial verify of track `capture`'s "book-reachable recall 15/34 = 44.1%"

**Verdict: REFUTED.** The console line reproduces byte-for-byte. The *claim built on it*
is wrong twice over, and the two errors are independent.

Script: `research/g71_advcapture_universe_check.py` (reads only; no engine or mark file touched).

## Reproduction (clean)

`python research/g71_capture_heldout_ab.py`, re-run at HEAD:

```
== B: delegating router (BacktestRunner shape) ==
  S cards: 34   recall: 22/34 = 64.7%
  of those hits, in universe.BACKTEST_SYMBOLS: 15/22  -> book-reachable recall 15/34 = 44.1%
  hits on symbols the book never trades: {'ARM': 2, 'MSTR': 2, 'SMCI': 1, 'ACHR': 1, 'SPCX': 1}
```
Arm A = 23/34 (67.6%). A−B = one card, `QQQ_2025-09-23`. All of that stands.

## Defect 1 — wrong universe constant. ACHR and SPCX *are* in the book.

`research/g71_capture_heldout_ab.py:29,60,67` tests membership in `universe.BACKTEST_SYMBOLS`.
That constant is `backtest_week.py`'s list and nothing else's — `backtest_week.py:39-40` is its
only main-tree importer (`omen6_forward.py` is retired per CLAUDE.md; `t70_test1_score.py` /
`w4_recall_sources.py` are reporting).

The money/durability rig is `backtest_2y.py`, and it does **not** import `BACKTEST_SYMBOLS`:

```
backtest_2y.py:20   from universe import (ALL_SYMS, INDEX_POOL, CORE_SYMBOLS, EXPERIMENTAL_SYMBOLS,
backtest_2y.py:92   syms = [s for s in ALL_SYMS if has_archive(s, 100)]
```

`ALL_SYMS` = 29 (`universe.py:84` vs `universe.py:38`), and `SPCX`/`ACHR` are in `MAJOR_15`
(`universe.py:28-31`). Measured against the shipped book `research/bt2y_trades.json`
(meta 2026-08-29T03:14, 500 sessions, 76,019 signals, **2,437 traded**, 28 symbols):

| symbol | traded rows in the book | in `BACKTEST_SYMBOLS` |
|---|---:|---|
| ACHR | **41** | no |
| SPCX | **22** | no |
| IWM | 40 | no |
| SPY | 55 | no |
| ARM | 0 | no |
| MSTR | 0 | no |
| SMCI | 0 | no |

So "symbols the book never trades" is false for 2 of the 5 names and for 2 of the 7 hits.
Genuinely unreachable: `{ARM: 2, MSTR: 2, SMCI: 1}` = **5 hits, not 7**.
(The same bug also mislabels the `IWM 2026-05-01` S card as off-book; it happens not to hit.)

## Defect 2 — mixed denominator. 15/34 divides a cut numerator by an uncut denominator.

`g71_capture_heldout_ab.py:64-66` prints `len(in_uni)/len(his_s)`. `in_uni` is restricted to the
traded universe; `his_s` is all 34 S cards, 7 of which sit on symbols no book can reach. A recall
must restrict both sides or neither. Restricting both:

| framing | value |
|---|---|
| raw held-out S recall, delegating router | 22/34 = **64.7%** |
| claim (numerator cut, denominator uncut) | 15/34 = 44.1% — **invalid** |
| both cut by `BACKTEST_SYMBOLS` (still the wrong list) | 15/24 = **62.5%** |
| both cut by the **actual book's 28 symbols** | **17/27 = 63.0%** |

The real book-reachable held-out S recall for the delegating router is **63.0%**, ~1.7pp below
the 64.7% raw figure and ~4.6pp below arm A's 67.6% — not the 23.5pp collapse the claim asserts.

## Defect 3 — the count was never taken on any book.

The prompt's check ("right book: the post-T0 book, not the old 1,017-trade one") has no purchase,
because `g71_capture_heldout_ab.py` never opens a trade file. It is a static `in`-test against a
list literal. For the record, the books present at HEAD:

| file | traded | generated |
|---|---:|---|
| `research/a2_bt2y_rerun.json` | 1,017 | 2026-08-27T17:27 |
| `research/bt2y_trades.json` | **2,437** | 2026-08-29T03:14 |
| `research/g71_ladder_bt2y_noab.json` | 2,437 | 2026-08-29T14:34 |

No 2,595-trade book exists in the tree. All of them carry the same 28 symbols, ACHR and SPCX included.

## Not defects

- No look-ahead: `score()` (`g71_capture_heldout_ab.py:44-56`) replays via `t4.run_day` per
  (symbol, day) and joins to marks only afterwards; grades never enter the fire test.
- Branch reachability: `DelegatingCaptureRunner._route` (`g71_capture_route_ab.py:139-157`) is
  reached — it is monkeypatched onto `t4.CaptureRunner` at `g71_capture_heldout_ab.py:83` and the
  arm's result differs from A by exactly one card, so it demonstrably ran.
- The 22/34 and the 15/22 sub-counts are arithmetically correct for what they measure.

## Fix (diff, not applied)

```diff
--- a/research/g71_capture_heldout_ab.py
+++ b/research/g71_capture_heldout_ab.py
@@
-from universe import BACKTEST_SYMBOLS             # noqa: E402
+from universe import ALL_SYMS, has_archive        # noqa: E402
+
+# The money/durability book is backtest_2y.py, which iterates
+#   [s for s in ALL_SYMS if has_archive(s, 100)]   (backtest_2y.py:92)
+# NOT universe.BACKTEST_SYMBOLS, which is backtest_week.py's list only.
+BOOK_SYMBOLS = frozenset(s for s in ALL_SYMS if has_archive(s, 100))
@@
-    in_uni = [r for r in tp if r["symbol"] in BACKTEST_SYMBOLS]
+    in_uni = [r for r in tp if r["symbol"] in BOOK_SYMBOLS]
+    s_uni = [r for r in his_s if r["symbol"] in BOOK_SYMBOLS]
@@
-    print(f"  of those hits, in universe.BACKTEST_SYMBOLS: {len(in_uni)}/{len(tp)}"
-          f"  -> book-reachable recall {len(in_uni)}/{len(his_s)} = "
-          f"{len(in_uni)/max(1,len(his_s))*100:.1f}%")
-    off = Counter(r["symbol"] for r in tp if r["symbol"] not in BACKTEST_SYMBOLS)
+    # restrict BOTH sides -- a numerator cut by universe over an uncut denominator
+    # is not a recall.
+    print(f"  of those hits, on book symbols: {len(in_uni)}/{len(tp)}"
+          f"  -> book-reachable recall {len(in_uni)}/{len(s_uni)} = "
+          f"{len(in_uni)/max(1,len(s_uni))*100:.1f}%")
+    off = Counter(r["symbol"] for r in tp if r["symbol"] not in BOOK_SYMBOLS)
```

Also correct `research/g71_capture.md` and `research/g71_capture_heldout_ab.py:12-14`, whose
docstring asserts the off-universe split "is the other half of why 67.6% on the harness is 1/34
on the book". At 63.0% book-reachable it explains ~2pp, not the gap to 1/34.
