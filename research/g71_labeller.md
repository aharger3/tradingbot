# G7.1 / labeller — "tell me what setup you think it is"

> *"so in homework also tell me what setup you think it is"*
> *"remember BR and OCR is also a setup when both of them are together."*
> — Austin, 2026-08-29

**Diagnosis pass. Nothing in the engine was edited.** Scripts:
`research/g71_labeller_label.py`. Sample: `research/g71_labeller_sample.json`
(2,437 traded rows of the 2-year book, `research/bt2y_trades.json`, generated
2026-08-29T03:14, 500 sessions, 76,019 signals).

---

## Answer in one line

**All three labels already exist inside the engine and are thrown away at exactly
one line — `backtest_week.py:861-868`.** Nothing new has to be computed. The
book has been calling **1,454 of its 2,437 traded rows (59.7%) by the wrong
setup name** because the field that holds the right one is never copied onto
`SimTrade`.

---

## 1. Setup — the field exists, the boundary drops it

`signal_runner.OMENSignalRunner._label_confluence` (signal_runner.py:2392-2427)
already stamps **every** signal:

```
sig["setup_type"] = SignalType.BR_OCR_CONFLUENCE     # :2421
sig["br_ocr"] = True                                  # :2422
sig["reason"] += " [brocr]"                           # :2423
```

The test is `research/downgrade.py::has_confluence` (downgrade.py:450-468) — the
one definition, not a re-implementation. `SignalType.BR_OCR_CONFLUENCE` has
existed since P3/G8 (omen_bot.py:41-52).

`backtest_week.SimTrade` (backtest_week.py:251-280) has **no `setup_type`
field**, and the constructor at backtest_week.py:861-868 passes
`signal_type=sig["signal_type"].value` only. `setup_type` dies there.
`backtest_2y.py:165` then writes `"setup": t.signal_type` — the base detector,
never the confluence class.

What survives is the **`[brocr]` tag in the reason string**, harvested into
`row["tags"]` by `backtest_2y.py:189`. That is the shadow this diagnosis reads.
It is exact: over all 76,019 rows the tag and the book's own `confluence`
column agree on 75,781; the 238 disagreements are all `reentry_84_rule`, which
is deliberately excluded from `CONFLUENCE_BASE_SETUPS` (signal_runner.py:852).

### What the book actually trades, once labelled

| setup | trades | share | win | mean R |
|---|---:|---:|---:|---:|
| **BR+OCR** | **1,454** | **59.7%** | 52.2% | +0.5519R |
| break-and-retest (alone) | 753 | 30.9% | 50.7% | +0.5686R |
| other — 84% re-entry | 123 | 5.0% | 25.2% | −0.0824R |
| one-candle-rule (alone) | 107 | 4.4% | 24.3% | +1.1089R |
| all | 2,437 | | 49.2% | +0.5495R |

Austin's third setup class is the **majority of the book** and has never
appeared under its own name in any report. Note the one-candle-rule alone: 107
trades, 24.3% win, **+1.1089R** — the highest mean R of any class, and the
smallest sample. It is invisible today because 272 of the 379 OCR detections get
absorbed into `one_candle_rule` alongside the confluence ones.

---

## 2. Level — the field exists, and a regex is used instead

`stop_level_name` is stamped at every emit site: signal_runner.py:2819 / 2912 /
2936 / 3090 / 3163 / 3184 (and `level_price`, backtest_week.py:280, already
carries the price). It too dies at backtest_week.py:861-868.

`backtest_2y.py:27,153,187` therefore **re-derives the level with a regex over
the reason prose**:

```python
LEVEL_RE = re.compile(r"(?:above|below) (PDH|PDL|PMH|PML|OR high|OR low|pivot high|pivot low)")
...
"level": lv.group(1) if lv else "other",
```

The order-block and 84%-rule reason strings do not contain the words
"above <LEVEL>", so the regex cannot match them. Result, and it is exact:

> **"other" in the book = 5,782 rows = 5,394 one-candle-rule + 388 84%-rule.
> Every single one-candle-rule signal in two years is filed as "other".**

### Against his six

> *"you know the 6 levels i watch thats it."* — Austin, 2026-08-29
> (`Projects/omen-rulebook.md`, "The six levels are closed")

Surfacing `stop_level_name` alone gets 51.0% of traded rows onto a named level
of his six. Snapping the rest onto the six-level roster — using
`research/p21_target_availability.py::levels_for_entry` and the engine's own
tolerance `signal_runner.PIVOT_DEDUPE_FRAC = 0.001`, which already rules that "a
pivot within `PIVOT_DEDUPE_FRAC` of a named level is that level having a second
name" (signal_runner.py:2703-2706) — gets it to **64.1%**.

| level | trades | win | mean R |
|---|---:|---:|---:|
| ORH | 400 | 52.0% | +0.5862R |
| ORL | 388 | 53.6% | +0.6249R |
| PMH | 276 | 50.0% | +0.5458R |
| PML | 244 | 46.7% | +0.3750R |
| PDH | 138 | 47.1% | +0.5161R |
| PDL | 117 | 45.3% | +0.4598R |
| **his six** | **1,563 (64.1%)** | 50.3% | +0.5401R |
| not-his: pivot high | 321 | 54.5% | +0.5779R |
| not-his: pivot low | 262 | 50.8% | +0.6216R |
| not-his: order block | 236 | 37.7% | +0.6224R |
| not-his: prior entry (84%) | 55 | 27.3% | −0.0050R |
| **not his** | **874 (35.9%)** | 47.1% | +0.5663R |

**583 traded rows (23.9%) broke a T10 pivot** — a level Austin does not watch,
already deduped against his six by the engine, so these are genuinely a seventh
and eighth level. The rulebook calls that pollution and says to trace and
remove. **This is a separate ticket; it is not what this labeller changes.**

---

## 3. Timeframe — it is a constant, and the book never says so

There is no per-signal entry timeframe. Every entry in this engine is a
**1-minute bar** (`polygon_feed.rth:77`, `omen_bot.Candle:113` "Single 1-minute
candle"), and the only other timeframe in the system is the **1-hour HTF bias**
(`backtest_12mo.hourly_from_1m`). No 5m path exists anywhere;
`omen_bot.py:847`'s "5-minute opening range" is the first 5 × 1m candles.

What *does* vary per signal is the timeframe the **level** was drawn on, and it
is a pure function of the level's name:

| level | drawn on |
|---|---|
| PDH / PDL | 1D — prior session |
| PMH / PML | 1m premarket, 04:00–09:30 |
| ORH / ORL | 5m opening range (first 5 × 1m) |
| pivot high / low | 1m intraday swing (`PIVOT_LOOKBACK=30`, strength 2) |
| order block | 1m single candle |
| prior entry (84%) | 1m — the failed entry price |

So the honest homework line is **"entry 1m · level <TF> · bias 1h"**, not a
single timeframe field.

---

## 20-row sample from the 2-year book

Round-robin across setup classes, oldest first. `eng` = legacy A+/A/B/C/X ladder
(`signal_runner._grade_pa`), `aus` = Austin's S/A/C ladder
(`research/downgrade.py`) — both, never mixed. Reproduce with:

```
python research/g71_labeller_label.py --n 20 --resolve
```

| sym | day | et | side | setup | level | level px | entry TF | level TF | eng | aus | R | out |
|---|---|---|---|---|---|---:|---|---|---|---|---:|---|
| AMD | 2024-08-21 | 09:44 | L | break-and-retest | ORH | 156.21 | 1m | 5m opening range | B | C | −1.000 | loss |
| COIN | 2024-08-21 | 09:49 | S | **BR+OCR** | not-his: pivot low | 196.75 | 1m | 1m intraday swing | B | C | −1.000 | loss |
| AMD | 2024-08-22 | 09:39 | L | **BR+OCR** | PDH | 158.65 | 1m | 1D | B | C | −1.000 | loss |
| TSLA | 2024-08-22 | 09:38 | S | break-and-retest | PML | 223.03 | 1m | 1m premarket | B | A | −1.000 | loss |
| AAPL | 2024-08-23 | 10:04 | L | **BR+OCR** | not-his: pivot high | 226.99 | 1m | 1m intraday swing | B | C | +0.266 | win |
| AMD | 2024-08-23 | 09:43 | L | **BR+OCR** | ORH | 153.82 | 1m | 5m opening range | B | C | +2.161 | win |
| AMZN | 2024-08-23 | 10:52 | S | **BR+OCR** | ORL | 176.62 | 1m | 5m opening range | B | **S** | +0.204 | win |
| MU | 2024-08-23 | 10:06 | L | break-and-retest | ORH | 102.68 | 1m | 5m opening range | B | C | +1.270 | win |
| NVDA | 2024-08-23 | 09:59 | L | break-and-retest | not-his: pivot high | 126.96 | 1m | 1m intraday swing | B | C | +2.115 | win |
| NVDA | 2024-08-23 | 10:06 | L | break-and-retest | not-his: pivot high | 127.22 | 1m | 1m intraday swing | B | C | +4.344 | win |
| META | 2024-08-30 | 10:21 | S | other (84% re-entry) | not-his: prior entry | 519.66 | 1m | 1m failed entry | B | A | −1.000 | loss |
| MSFT | 2024-09-03 | 10:08 | L | one-candle-rule | not-his: order block | 416.74 | 1m | 1m single candle | B | C | −1.000 | loss |
| NFLX | 2024-09-05 | 10:11 | S | one-candle-rule | not-his: order block | 68.14 | 1m | 1m single candle | B | C | −1.000 | loss |
| AVGO | 2024-09-09 | 10:24 | S | other (84% re-entry) | ORL | 137.66 | 1m | 5m opening range | B | **S** | +2.529 | win |
| AAPL | 2024-09-10 | 10:34 | L | one-candle-rule | not-his: order block | 219.52 | 1m | 1m single candle | B | C | −1.000 | loss |
| IWM | 2024-09-18 | 09:39 | L | one-candle-rule | ORH | 219.71 | 1m | 5m opening range | B | C | +0.274 | win |
| NVDA | 2024-09-18 | 10:10 | S | other (84% re-entry) | not-his: prior entry | 115.05 | 1m | 1m failed entry | B | C | −1.000 | loss |
| QQQ | 2024-09-25 | 10:55 | L | one-candle-rule | PDH | 486.62 | 1m | 1D | B | C | −1.000 | loss |
| COIN | 2024-10-07 | 10:11 | L | other (84% re-entry) | not-his: prior entry | 173.87 | 1m | 1m failed entry | B | A | −1.000 | loss |
| COIN | 2024-10-10 | 10:41 | S | other (84% re-entry) | not-his: prior entry | 164.15 | 1m | 1m failed entry | B | **S** | +1.691 | win |

**Three rows to eyeball hardest**, because they are the ones the current book
gets wrong and the labeller changes:

- `AMZN 2024-08-23 10:52` — today this is `one_candle_rule` / level `other`.
  Labelled it is **BR+OCR at ORL**, and it is one of the few Austin-**S** rows in
  the window.
- `QQQ 2024-09-25 10:55` and `IWM 2024-09-18 09:39` — today both are level
  `other`. Snapped, they are a **PDH** break and an **ORH** break.
- `AVGO 2024-09-09 10:24` — an 84%-rule re-entry that reclaimed at **ORL**. The
  84% rows are the ones where "which level" is least certain, because the level
  is the *prior failed entry*, not a level the detector named.

---

## The fix — exact diff, NOT applied

Two files, pure surfacing. Routing, grading, fills and P&L are untouched: only
new columns appear in `research/bt2y_trades.json`. The legacy `"level"` column
is left exactly as it is so every existing report and filter keeps working.

### Hunk 1 — `backtest_week.py`: stop dropping the two fields

```diff
--- a/backtest_week.py
+++ b/backtest_week.py
@@ -277,6 +277,15 @@ class SimTrade:
     # `stop` for a default B&R (BNR_STOP_MODE="level"), NOT equal for the order
     # block (stop = the far side of the block) or when intrabar_stop() collapsed
     # the stop onto the entry bar's own extreme. Read only by ENTRY_SCRATCH.
     level_price: float = 0.0
+    # G7.1/labeller. The two identity fields signal_runner stamps on every sig
+    # and this dataclass used to drop on the floor. `setup_type` is
+    # SignalType.BR_OCR_CONFLUENCE whenever downgrade.has_confluence held on the
+    # entry bar (signal_runner._label_confluence:2421) -- Austin's third setup
+    # class, 59.7% of the traded book. `stop_level_name` is the level the setup
+    # actually broke, spelled ("PDH" / "OR high" / "Order block low").
+    # Carrying them changes nothing: backtest_2y was already re-deriving both
+    # from the reason prose with a regex that cannot see an order block.
+    setup_type: str = ""
+    stop_level_name: str = ""
 
     @property
     def counted(self) -> bool:
@@ -861,7 +870,11 @@ def simulate_day(...):
             t = SimTrade(symbol=symbol, day=day_iso,
                          signal_type=sig["signal_type"].value,
                          direction=sig["direction"], grade=sig["grade"],
                          status=sig["status"], entry_time=c.timestamp,
                          entry=sig["entry"], stop=sig["stop"], target=target,
                          reason=sig["reason"], entry_idx=i, exit_idx=len(candles) - 1,
                          be_level=be_level, scale_level=scale_level,
-                         runner_target=runner_tgt)
+                         runner_target=runner_tgt,
+                         # setup_type is a SignalType when _label_confluence ran,
+                         # absent on a sig built by a research replay -- fall back
+                         # to the base type rather than an empty string.
+                         setup_type=getattr(sig.get("setup_type"), "value",
+                                            sig["signal_type"].value),
+                         stop_level_name=sig.get("stop_level_name", ""))
             trades.append(t)
```

### Hunk 2 — `backtest_2y.py`: surface them as columns

```diff
--- a/backtest_2y.py
+++ b/backtest_2y.py
@@ -27,6 +27,49 @@
 LEVEL_RE = re.compile(r"(?:above|below) (PDH|PDL|PMH|PML|OR high|OR low|pivot high|pivot low)")
 
+# G7.1/labeller. Austin, 2026-08-29: "so in homework also tell me what setup you
+# think it is", "remember BR and OCR is also a setup when both of them are
+# together", "you know the 6 levels i watch thats it."
+#
+# Nothing here is computed -- all three answers are read off SimTrade now that
+# backtest_week carries them. research/g71_labeller_label.py is the same mapping
+# run over the pre-fix book, and research/g71_labeller.md holds the numbers.
+SETUP_LABEL = {"break_and_retest": "break-and-retest",
+               "one_candle_rule": "one-candle-rule",
+               "br_ocr_confluence": "BR+OCR",
+               "reentry_84_rule": "other (84% re-entry)",
+               "fair_value_gap": "other (FVG)", "flag": "other (flag)"}
+# His six, and nothing else (Projects/omen-rulebook.md, "The six levels are
+# closed"). Anything outside it is named honestly as not-his rather than
+# quietly promoted to a seventh level.
+HIS_SIX = {"PDH": "PDH", "PDL": "PDL", "PMH": "PMH", "PML": "PML",
+           "OR high": "ORH", "OR low": "ORL"}
+# The timeframe each level is DRAWN on. The ENTRY timeframe is 1m for every row
+# in this engine (polygon_feed.rth); the HTF bias is 1h
+# (backtest_12mo.hourly_from_1m). There is no other timeframe.
+LEVEL_TF = {"PDH": "1D", "PDL": "1D",
+            "PMH": "1m premarket", "PML": "1m premarket",
+            "ORH": "5m opening range", "ORL": "5m opening range"}
+
+
+def level_label(t):
+    """(his-six name, or 'not-his: <what it really was>'), and its timeframe."""
+    n = (t.stop_level_name or "").strip()
+    if n in HIS_SIX:
+        k = HIS_SIX[n]
+        return k, LEVEL_TF[k]
+    if n.startswith("pivot"):
+        return "not-his: " + n, "1m intraday swing"
+    if n.startswith("Order block"):
+        return "not-his: order block", "1m single candle"
+    if n.startswith(("HOD", "LOD")):
+        return "not-his: " + n, "1m session extreme"
+    if n.startswith(("FVG", "Flag")):
+        return "not-his: " + n, "1m intraday"
+    lv = LEVEL_RE.search(t.reason)      # the 84% re-entry names no level itself
+    if lv and lv.group(1) in HIS_SIX:
+        k = HIS_SIX[lv.group(1)]
+        return k, LEVEL_TF[k]
+    return "not-his: " + (n or "unnamed"), "1m intraday"
+
 
 def archive_days(sym):
@@ -152,6 +195,7 @@
                 risk = abs(t.entry - t.stop)
                 lv = LEVEL_RE.search(t.reason)
+                lvl_name, lvl_tf = level_label(t)
                 sm = S_RE.search(t.reason)
@@ -165,6 +209,11 @@
                     "setup": t.signal_type, "dir": t.direction,
+                    # G7.1: the labeller's three answers, surfaced not derived.
+                    # `setup` above stays the BASE detector so nothing that
+                    # groups on it moves; setup_label is the class Austin names.
+                    "setup_label": SETUP_LABEL.get(t.setup_type or t.signal_type,
+                                                   t.setup_type or t.signal_type),
+                    "entry_tf": "1m", "bias_tf": "1h",
                     "grade": t.grade, "status": t.status,
@@ -187,6 +236,8 @@
                     "level": lv.group(1) if lv else "other",
+                    "level_name": lvl_name,
+                    "level_tf": lvl_tf,
+                    "level_px": round(t.level_price or t.stop, 2),
                     "s": int(sm.group(1)) if sm else -1,
```

### Optional hunk 3 — name the level an order block sits on

Hunks 1–2 leave 236 traded OCR rows (9.7%) as `not-his: order block`, because
the OCR detector genuinely never asks which of his six it is near — it grades at
`block.high` (signal_runner.py:2891 "Grade PA at the block's own level, not the
OR"). The engine already holds the answer one scope up:

```python
self._active_levels = [l for l in (self.pdh, self.pdl, self.pmh,
                                   self.pml, or_high, or_low) if l is not None]   # :2665
```

but as bare floats. Naming them and snapping the block onto them, at the
engine's own dedupe tolerance, is a label and never a gate:

```diff
--- a/signal_runner.py
+++ b/signal_runner.py
@@ -2664,6 +2664,12 @@
         self._active_levels = [l for l in (self.pdh, self.pdl, self.pmh,
                                            self.pml, or_high, or_low) if l is not None]
+        # G7.1/labeller: the same six, keyed by HIS name, so a setup that is not
+        # keyed to a named level (an order block, an 84% reclaim) can still be
+        # REPORTED against the six he watches. Label only -- read by nothing
+        # that routes, grades or vetoes.
+        self._named_levels = {n: v for n, v in
+                              (("PDH", self.pdh), ("PDL", self.pdl),
+                               ("PMH", self.pmh), ("PML", self.pml),
+                               ("ORH", or_high), ("ORL", or_low)) if v is not None}
@@ -2911,6 +2917,7 @@
                     "direction": "call",
                     "grade": grade.value,
                     "stop_level_name": "Order block low",
+                    "level_at": self._at_named(block.high),
                     "level_price": block.high,
```

(mirrored at signal_runner.py:3163 for the short side with `block.low`), plus one
helper beside `_label_confluence`:

```python
    def _at_named(self, px):
        """Which of HIS SIX this price is, or None. PIVOT_DEDUPE_FRAC is the
        engine's own existing rule for 'this price is that level under another
        name' (see the pivot dedupe at :2703) -- not a new tolerance."""
        best, bestd = None, None
        for name, lv in getattr(self, "_named_levels", {}).items():
            if not lv:
                continue
            d = abs(px - lv) / abs(lv)
            if d <= PIVOT_DEDUPE_FRAC and (bestd is None or d < bestd):
                best, bestd = name, d
        return best
```

Measured effect of hunk 3, on the traded book: **his-six coverage 51.0% →
64.1%**, +319 rows named. It changes no grade, no fill and no R.
`research/g71_labeller_label.py --resolve` computes exactly this snap from
outside the engine (via `p21_target_availability.levels_for_entry`) and is what
produced the 64.1% above, so the number is checkable before the hunk lands.

---

## What this does NOT claim

- No money-gate movement. Every number here is a **relabelling** of the same
  2,437 trades; total book R is unchanged.
- The per-class win rates above are descriptive, not an A/B. Every arm in this
  project moves less than its own ±1.5799R error bar
  (`omen-error-bar-exceeds-arms`), and the one-candle-rule-alone cell is n=107.
- The 583 pivot-level trades are a **separate finding** (the seventh level the
  rulebook calls pollution). The labeller only names them honestly; removing
  them is a different ticket with a real recall risk.
