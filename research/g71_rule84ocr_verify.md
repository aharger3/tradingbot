# G71 / rule84ocr — adversarial verify of the "BR+OCR label dies at SimTrade" claim

**Verdict: REFUTED.** The mechanical half of the claim reproduces exactly. Its
operative conclusion — *"so no book, report or A/B can group by it"* — is false,
and I ran the A/B it says is impossible.

Script: `research/g71_rule84ocr_verify_brocr.py` (read-only, no engine file touched).

## What reproduces (claim is right about the plumbing)

| assertion | verified |
|---|---|
| `SignalType.BR_OCR_CONFLUENCE` exists | `omen_bot.py:52` — exact |
| `_label_confluence` stamps `setup_type` + `br_ocr` | `signal_runner.py:2394-2426` (claim said 2392; def is at 2394) |
| called on every signal before routing | `signal_runner.py:2438` inside `_emit`, ahead of the veto |
| `SimTrade` has no such field | `backtest_week.py:252-283` — 20 fields, none is `setup_type`/`br_ocr` |
| constructor passes `signal_type` only | `backtest_week.py:861-869` — `signal_type=sig["signal_type"].value` |
| `backtest_2y.py:165` writes `"setup": t.signal_type` | exact |
| book `setup` has exactly 3 values, no `setup_type`/`br_ocr` key | 70,237 BR / 5,394 OCR / 388 R84; both columns absent |
| `CONFLUENCE_SETUP_ROUTES` defaults OFF | `signal_runner.py:847` — exact |

Book identity checked: `research/bt2y_trades.json`, gen 2026-08-29T03:14, 2024-08-21→2026-08-21,
500 sessions, 76,019 signals, **2,437 traded**. This is the newest book in the tree. The
orchestrator's "2,595-trade post-T0 book" does not exist here — `g71_drawdown_verify.md:108`
and `g71_advcapture.md:80` independently reached the same finding. The count was taken on the
right (only) book.

Reachability: `python research/test_confluence_setup.py` passes 26/26, including
`bar 5..11: detection-time label == dg.score on the full day` — the branch is live and
carries **no look-ahead**; `has_confluence` reads only bars ≤ i.

## Why the conclusion is false

The book already carries the label under a different column name.

- `backtest_2y.py:198` writes `"confluence": "yes" if (rec or {}).get("confluence") else "no"`.
- `research/downgrade.py:524-540`: `confl = confl_br_ocr or confl_ml`.
- `research/downgrade.py:91`: `ENABLE_MULTI_LEVEL_CONFLUENCE = False`, and `score()` only
  calls `multi_level_confluence` when it is on — so `confl ≡ confl_br_ocr ≡ has_confluence(...)`.
- `has_confluence` is the *same predicate* `_label_confluence` applies
  (`signal_runner.py:2410-2421`), on the *same inputs*: `t.stop` as the level proxy
  (`backtest_week.py:866` sets `stop=sig["stop"]`, never rewritten), same direction, same bar
  (`_dg_bars()` is truncated to the emit bar, so `len(bars)-1 == t.entry_idx`). The docstring
  at `signal_runner.py:2398-2401` states this equality; `test_confluence_setup.py` tests it.

So the class reconstructs exactly:

```python
BASE = {"break_and_retest", "one_candle_rule"}          # CONFLUENCE_BASE_SETUPS, signal_runner.py:852
is_brocr = lambda r: r["setup"] in BASE and r["confluence"] == "yes"
```

**Reconstructed detections: 50,272 / 76,019 (66.1%).** The naive `confluence == "yes"` filter
over-counts by 238 rows, all `reentry_84_rule` — the detector refuses to label it, and the
setup gate above fixes that. This is the one real trap in the reconstruction, and it is
2-line-fixable, not a dead end.

### The A/B the claim says cannot be run (traded rows, 2,437)

| class | n | mean R | win | symbol-days |
|---|---:|---:|---:|---:|
| BR+OCR | 1,454 | +0.5519 | 52.2% | 1,377 |
| not BR+OCR | 983 | +0.5460 | 44.7% | 888 |

Per base setup (detections / traded confluence rate): BR 67.2% / 61.1%, OCR 57.5% / 71.8%.

The separation is +0.0059R in mean R — far inside the ±1.5799R error bar — and +7.5pp in win
rate. That is the finding the claim should have carried instead of "cannot be grouped".

## The claim's own evidence contradicts it

`research/g71_rule84ocr_counts.py` block `"BR+OCR together: the `confluence` column
(downgrade.has_confluence)"` performs this exact grouping and prints
`BR+OCR (conf=yes)` vs `BR only (conf=no)` mean R and win rate off the same book — while its
next `print` asserts the grouping is unavailable. The claimant ran the refutation and filed
it as supporting evidence.

## What is actually true, and is worth carrying forward

`setup_type`/`br_ocr` are not *persisted*, so the book's own `setup` column cannot show a
4th class and `CONFLUENCE_SETUP_ROUTES=1` is the only way to make it do so. That is a
plumbing gap worth closing for readability — 3 lines, no behaviour change:

```diff
--- a/backtest_week.py
+++ b/backtest_week.py
@@ class SimTrade:
     level_price: float = 0.0
+    # P3/G8: the detector's confluence label, so the book can name a 4th setup
+    # class without CONFLUENCE_SETUP_ROUTES rewriting the routing key.
+    setup_type: str = ""
+    br_ocr: bool = False
@@ t = SimTrade(symbol=symbol, day=day_iso,
                          be_level=be_level, scale_level=scale_level,
-                         runner_target=runner_tgt)
+                         runner_target=runner_tgt,
+                         setup_type=getattr(sig.get("setup_type"), "value",
+                                            sig["signal_type"].value),
+                         br_ocr=bool(sig.get("br_ocr")))
```

```diff
--- a/backtest_2y.py
+++ b/backtest_2y.py
@@
                     "setup": t.signal_type, "dir": t.direction,
+                    "setup_type": t.setup_type, "br_ocr": bool(t.br_ocr),
```

Not applied — this is a diagnosis pass. And it is a convenience, not an unblock: every number
in the table above was produced without it.
