# G71 / rule84ocr — the 84% rule and the one-candle rule, audited against Austin's sentences

**Austin's ask:** *"84 percent and ocr need to be higher in the batch because those are
probably broken"* and *"remember BR and OCR is also a setup when both of them are together."*

**Verdict: he is right on both, and for reasons that are mechanical, not tuning.** Neither
rule is broken at its core predicate — both cores match his sentence. Both are strangled by
gates nobody in the corpus ever stated, and every one of those gates sits upstream of the
part that works. `BR+OCR together` **does** exist as a distinct class in the detector and is
**thrown away at the `SimTrade` boundary**, so it has never appeared in a book, a report or a
number.

Scripts that made every figure below (all read-only, none touches an engine file):

| script | what it measures |
|---|---|
| `research/g71_rule84ocr_counts.py` | fire counts / R / grade over the 2-year book + the 100-card sample |
| `research/g71_rule84ocr_funnel.py` | the funnel *inside* `detect_order_block_setup`, plus the dead-clause proof |
| `research/g71_rule84ocr_isolation.py` | the two contradictory `isolated` tests for the same rule |
| `research/g71_rule84ocr_confluence_level.py` | is the confluence label ruined by the stop-as-level proxy? (**no** — negative result) |

Book: `research/bt2y_trades.json`, 2024-08-21 → 2026-08-21, 500 sessions, 76,019 signals,
2,437 traded. Graded sample: `research/marks/probe_s_sweep_2026-08-28.jsonl`, 100 cards.

---

## Fire counts

| setup | detections | fired | traded | mean R | win | share of signals |
|---|---:|---:|---:|---:|---:|---:|
| `break_and_retest` | 70,237 | 2,880 | 1,935 | **+0.5617** | 52.9% | 92.4% |
| `one_candle_rule` | 5,394 | 484 | **379** | **+0.6924** | 37.7% | 7.1% |
| `reentry_84_rule` | 388 | 123 | **123** | **−0.0824** | 25.2% | 0.5% |

Two corrections to numbers still quoted in the vault:

- `omen-rulebook.md` batch 03 says *"84 PERCENT RULE FIRES 3 times and BR 60 TIMES"* and
  *"B&R 947, OCR 67, 84% rule 3"*. **Stale.** On the current book it is **1,935 / 379 / 123**
  traded. R3 (the OCR `B→C` demote lift) and R4 (the flat `$0.50` min-stop deletion) already
  fixed the two mechanical causes named there. The remaining OCR suppression is a *different*
  pair of gates (below).
- The 84% rule now arms and fires on **10.1% of the 1,222 full stop-outs** in the book, not
  5-of-434.

**The 84% rule is the only setup in the book with a negative expectancy** (−0.0824 R over 123
trades, 25.2% win). It is not under-firing any more; it is firing on the wrong bars.

### On the 100-card graded sample

- 0 of 100 cards carry an OCR tag; 1 of 100 mentions the 84% rule (`AMZN 2025-06-12`).
- This is **not** evidence of absence and must never be read as such — `omen-rulebook.md`:
  *"i think both BR and OCR are common together, but i'll only mark it if the OCR is isolated,
  hard to dispute, and can clearly be used to mark a stop."* The sample is a blind S/no sweep
  (`answers.s` = 34 `s` / 66 `no`); it was never asked to name setups.
- **The 100-card sample cannot measure either rule's fire rate.** Any track that reports one
  from it is reporting the page, not him.

---

## (a) The 84% rule

### His sentences

> **modifier, not standalone**; it re-enters **"the price you entered on"**, not merely the
> level; reclaim = a **candle close**, *"as long as the close is not too far from original
> entry"*; **two attempts**; armed by a **stop-out**, and the candle must **match the trend**.
> — `omen-rulebook.md` §"The 84% rule", ballot q12–q15

> *"84 percent rule can fire on **S A or C**, but we only will trade S of course."* — batch 03

> *"a trade 9:49 with 84 percent rule. candle closes way away from it but **as long as get in
> is reclaim and close to original entry**"* — AMZN 2025-06-12, batch 05

> **The 84% reclaim tolerance is the one tolerance unit, 25% of the previous candle's range —
> `STRONG_PA_MULT = 1.5` dies.** — batch 04, 2026-08-28

Source corpus (`research/84rule-sizing-dossier.md`, quotes 8–9): *"Requires A+ entry. Same
setup, same stop, same profit target."* / *"same break, same retest, same hammer, same stop,
same target."*

### The code

`signal_runner.py:2943-2967` (long; the short mirror is `:3190-3214`):

```python
if (self.session.entry_price is not None
        and self.session.entry_direction in (None, "call")
        and current.close >= self.session.entry_price
        and _reclaim_tol_ok(current.close, self.session.entry_price, self.session.entry_stop)
        and (RULE84_SOURCE or current.is_bullish)
        and (RULE84_LESSON or RULE84_SOURCE or self._strong_pa(current))):
    day_range = hod - lod
    stop_chk = (self.session.entry_stop if RULE84_LESSON
                and self.session.entry_stop is not None else current.low)
    tgt = self.session.entry_target
    rr_ok = RULE84_SOURCE or (
        tgt is not None and stop_chk < current.close
        and (tgt - current.close) >= 1.5 * (current.close - stop_chk))
    near_hod = day_range > 0 and (hod - current.close) / day_range <= 0.2
    ...
    if (RULE84_SOURCE or not near_hod) and rr_ok and caps_ok:
```

### Does it implement the sentence?

| his clause | code | verdict |
|---|---|---|
| re-enter **the price you entered on** | `session.entry_price`, `order_fill(entry_price, …)` | **YES** |
| reclaim = **candle close** | `current.close >= entry_price` | **YES** |
| **two attempts** | `RULE84_MAX_ATTEMPTS = 2`, `_attempts_84` keyed on (side, price) | **YES** |
| armed by a **stop-out** | `_arm_84`: `if t.outcome != "loss": return` | **YES** |
| candle **matches the trend** | `current.is_bullish` | **YES** |
| **same stop, same target** | `RULE84_LESSON=True` → original stop; `target = entry_target` | **YES** |
| fires on **S, A or C** | `grade_ok = True` on defaults | **YES** (via a dead gate, below) |
| *"close not too far from original entry"* = **25% of the previous candle's range** | `_reclaim_tol_ok` is a **no-op** | **NO** |

### Divergence 1 — the ratified tolerance is unwired, and an accidental one is binding

`signal_runner.py:350-351`

```python
_RULE84_RECLAIM_TOL_RAW = os.getenv("RULE84_RECLAIM_TOL", "").strip()
RULE84_RECLAIM_TOL = float(_RULE84_RECLAIM_TOL_RAW) if _RULE84_RECLAIM_TOL_RAW else None
```

`_reclaim_tol_ok(999.0, 100.0, 99.0)` returns **`True`** — a reclaim close 899 points away
passes. The docstring at `:344` says *"DO NOT INVENT A NUMBER … stays OFF until Austin picks
one."* **He picked one, on 2026-08-28** (batch 04, and `omen-rulebook.md` §"One tolerance,
everywhere", clause 2). The comment is one day stale and the ratified rule is unimplemented.

The units are wrong even if the flag were switched on: `RULE84_RECLAIM_TOL` is denominated in
**R** (`abs(close − entry) / |entry − stop|`); his unit is **25% of the previous candle's
range** — `BAR_EXTREME_FRAC` (`signal_runner.py:410`), already the constant behind the other
two uses of the same tolerance.

**And a tolerance he never stated is binding right now.** `rr_ok` demands
`(target − close) ≥ 1.5 × (close − stop)`. Every book row plans exactly `2.000 R:R` (verified:
815 of 1,018 traded BR-long rows are 2.0000 to four places, the rest round off a tick).
Substituting `target = E + 2R`, `stop = E − R`, `close = E + d`:

```
2R − d ≥ 1.5(R + d)   ⇔   d ≤ 0.2R
```

Confirmed numerically in `g71_rule84ocr_counts.py` — `rr_ok` flips False at `d = 0.20R`. So the
shipped reclaim window is **`[entry, entry + 0.2R]`**, an emergent side-effect of a 1.5:1 RR
floor added 2026-07-10, not a rule anyone stated. It is the wrong shape twice over: it is
**one-sided** (a close *below* entry is already rejected by `close >= entry_price`, so his
*"not too far from original entry"* has no lower guard at all), and its width is set by the
**target policy** — the moment P21 replaces the flat 2R target with the next structural level,
**this tolerance silently changes and nobody will connect the two.**

### Divergence 2 — `near_hod` vetoes exactly the entries he asks for

`signal_runner.py:2962`: `near_hod = (hod − close) / day_range <= 0.2` → skip. Not in any
sentence in the rulebook or the dossier. It is the mirror image of ballot q7 (*"We miss out on
entries near HOD because they close too high for our entry risk-to-reward"*) — the complaint
ON WATCH exists to fix.

### Divergence 3 — the source's own disqualifiers are absent

`84rule-sizing-dossier.md` quote 5: *"Disqualified when: broke structure the other way, no
displacement, multiple touches, weak/no confluences."* None of the four is an arm gate. What
**is** gated is `near_hod` + a 1.5 RR floor, neither of which appears in any source.

### The unreachable-branch bug class — five hits, all in the 84% path

1. **`setup_ok` can never be False.** `signal_runner.py:130`: `RULE84_ARM_ON = frozenset(SignalType)`.
   `backtest_week.py:435-437`:
   ```python
   # Austin 2026-08-09: arm when the stopped trade's setup is in RULE84_ARM_ON
   # (B&R or the one candle rule). FVG / flag losers do NOT arm it.
   setup_ok = SignalType(t.signal_type) in RULE84_ARM_ON
   ```
   `RULE84_ARM_ON` is **every** `SignalType`. The comment is false, the gate is a tautology,
   and `ARM84_FUNNEL["arming_setup"]` (`backtest_week.py:462`) is a funnel stage that **can
   never differ from `stopouts_counted`** — a counter that measures nothing. The widening is
   intentional (R6, `fact_rule84_arm_setups → any`); the false comment and the dead funnel
   stage are not.
2. **`grade_ok` can never be False** on defaults — `RULE84_STRICT` / `ARM_SGRADE` / `ARM_NOGATE`
   are all off, so `else: grade_ok = True` is the only reachable branch and
   `ARM84_FUNNEL["grade_gate"]` is a second dead stage. Correct per batch 03 (*"can fire on
   S A or C"*), but the funnel now reports two constants as if they were filters.
3. **`RULE84_ARM_BNR_ONLY` (`:131`) is a constant `False`** by construction.
4. **`_strong_pa` is dead in this path.** `:2948` / `:3195` short-circuit on `RULE84_LESSON`
   (True). Its only other call site is `_aplus_stack` (`:1948`), on the legacy `A+` ladder
   Austin deleted. So `STRONG_PA_MULT = 1.5` (`:99`) — the constant batch 04 says *"dies"* — is
   already unreachable in every shipped path; only the copy `OCR_STRONG_PA_MULT`
   (`omen_bot.py:472`) is live, and only under `OCR_STRICT` (off).
5. The `C → B` floor at `:2990` / `:3233` is **live** (`GRADE_FIX=False`), and its own inline
   comment says it is wrong: *"NOTE: comment 'strong-PA gate already passed' is STALE — under
   `RULE84_LESSON=True` the strong-PA gate is bypassed, so this floor grants a free B to plain
   reclaims."* 275 of 388 `reentry_84_rule` detections carry legacy grade `B`. On the ladder
   Austin deleted, this floor is the only reason the 84% rule is tradeable at all — and it is
   the most likely cause of the **−0.0824 R**.

---

## (b) OCR — the one-candle rule

### His sentences

> *"i forgot my OCR definition is simple, it's in the name 'one candle' — **one candle that's
> the opposite color of the way it's trending**."*
>
> *"it's the up close candle in a down trend or vice versa, **and we want price to respect it
> and break and retest it**."* — `omen-rulebook.md` §"OCR — defined at last"

| qualifier | his rule | source |
|---|---|---|
| when he counts it | *"would the candle be good to use as the stop?"* | card 11, ratified round two |
| standalone? | **standalone** — *"NO LEVEL BR JUST OCR … it's a classic S setup"* | card 2 |
| distance from entry | **any** — one card has the OCR 9 candles back | card 15 |
| two candles | **not an OCR** | card 14 |
| no displacement | a **downgrade**, and **BR+OCR confluence forgives it outright** | ballot q18 |

### The code — there are TWO implementations and they disagree

| file | what it is | wired into |
|---|---|---|
| `research/downgrade.py::find_ocr` (`:280-314`) | **colour** isolation: counter-coloured candle whose **both neighbours are trend-coloured** | grading only (`has_confluence`, `ocr_not_respected`) — never detection |
| `omen_bot.py::detect_order_block_setup` (`:403-431`) | **price** isolation: the block's body overlaps ≤1 of the prior 4 bars' ranges (`_is_isolated`, `:388-400`) | **the shipped detector** |

`research/g71_rule84ocr_isolation.py`, 10,143 order-block candidates over 6 symbols × 25 sessions:

```
price_isolated=False colour_isolated=False   3257  32.11%
price_isolated=False colour_isolated=True    4957  48.87%   <- discarded, clean OCR by his rule
price_isolated=True  colour_isolated=False    893   8.80%
price_isolated=True  colour_isolated=True    1036  10.21%
AGREE 42.3%   DISAGREE 57.7%
price test passes 19.0% ; colour test passes 59.1%
```

**The two tests for the same word disagree on 57.7% of candidates**, and the one carrying his
sentence is the one not wired into detection. **48.9% of all candidates are a clean one-candle
rule by his definition and are discarded by a price-overlap heuristic with no source.**

### The upstream funnel — `research/g71_rule84ocr_funnel.py`

20,880 candidate (bar × direction) evaluations, 6 symbols × 25 sessions, 09:30–11:00:

```
0 candidate bars                                 20880  100.00%
1 no valid order block                           10867   52.05%
2 block exists                                   10013   47.95%
3 KILLED by _is_isolated                          8111   38.85%   <- 81.0% of all blocks
3 passed isolation                                1902    9.11%
4 KILLED by _has_displacement                      751    3.60%   <- 39.5% of survivors
4 passed displacement                             1151    5.51%
5 not retesting                                    799    3.83%
5 retest=wick_only                                 107    0.51%
5 retest=partial_body                              139    0.67%
5 retest=full_body                                 106    0.51%
6 KILLED by OB_RETEST_TYPES (not wick_only)        245    1.17%   <- 69.6% of retests
7 OCR SIGNAL                                       107    0.51%
```

**107 signals survive out of 10,013 order blocks — 1.07%.** Three gates do it, and none is in
a sentence Austin has said:

1. **`_is_isolated` kills 81.0% of all blocks.** Not his rule (see above).
2. **`_has_displacement` kills a further 39.5% of survivors** — and ballot q18 lists a missing
   displacement as a **downgrade with BR+OCR confluence as an explicit exemption**. The engine
   has it as a hard veto with no exemption, so the confluence setup he calls his best is the
   one this gate removes most aggressively. A ratified exemption is inverted, not merely absent.
3. **`OB_RETEST_TYPES = ("wick_only",)`** (`signal_runner.py:51`) discards 245 of 352 retests.
   He never restricted the retest type; `partial_body` / `full_body` are the engine's own
   invention (SPEC3).

### The stop-width gate benches OCR structurally

`signal_runner.py:2903`: `if stock_risk / current.close > 0.004: grade = TradeGrade.D`.

- OCR risk is `entry − block.low` — **the whole OCR candle**. B&R risk is entry-to-level.
- Median `stop_pct`: **OCR 0.201% vs B&R 0.057% — 3.5×.**
- 964 of 5,394 OCR detections (**17.9%**) exceed 0.4%, and **100% of them grade `X`**.
- Same defect T4 fixed for B&R (*"scale the B&R min-risk floor to the symbol's own range"*),
  left unfixed on the OCR side, and the mechanical successor to the `$0.50` flat minimum R4
  deleted.

### The dead clause — the bug class, sixth hit

`signal_runner.py:2880-2881` (short mirror `:3142-3143`):

```python
if (block is not None and retest in OB_RETEST_TYPES
        and current.close > block.high and _volume_ok(self.candles)):
```

`retest == "wick_only"` already requires `min(open, close) > block.high`
(`omen_bot.check_retest_type:355`), and `close >= min(open, close)`. **`current.close > block.high`
can never be False.** Proven empirically: 107 of 107 wick_only retests satisfy it, 0 violations
(`g71_rule84ocr_funnel.py` tail). Harmless today, but the same shape as the four unreachable-rule
bugs already on the board — a line that reads like a gate and is a tautology.

### What OCR is worth once it gets through

- 379 traded, mean **+0.6924 R** — **the best mean R of the three setups**, above B&R's
  +0.5617 R — at a 37.7% win rate. A low-frequency, high-payoff setup throttled by precision
  gates.
- **1,111 OCR detections score `S` on Austin's ladder; 912 of them are `X` on the legacy
  ladder** (`sgrade × grade` cross-tab). That is the recall cost of the letters he deleted,
  concentrated on the setup he says should be as common as B&R.

---

## (c) Is BR+OCR-together a distinct setup class?

**Half of one.** It exists at the detection layer and is destroyed one function call later.

**What exists:**

- `omen_bot.py:52` — `BR_OCR_CONFLUENCE = "br_ocr_confluence"`, a real `SignalType`.
- `signal_runner.py:2392-2426` — `_label_confluence` stamps `sig["setup_type"]`,
  `sig["br_ocr"] = True` and a `" [brocr]"` tag on **every** qualifying signal, and it runs
  from `_emit`, so even vetoed signals are labelled.
- `research/downgrade.py:450-468` — `has_confluence`, the one definition (break bar at the
  level + isolated OCR whose far edge could hold the stop + OCR still respected).

**What is missing — this is the break:**

- `backtest_week.py:255-280` — `SimTrade` has **no `setup_type` and no `br_ocr` field**.
- `backtest_week.py:861-869` — the constructor copies `sig["signal_type"]` and never reads
  `sig["setup_type"]` or `sig["br_ocr"]`. **The label dies here.**
- `backtest_2y.py:165` writes `"setup": t.signal_type`, so the 2-year book carries exactly
  three setups and no confluence *class*.
- `research/build_bt2y_report.py:20-33` has one facet, `("confluence", "BR+OCR confluence")`,
  which is the **grade-time `dg.score` boolean** — a different computation on a different input
  at a different moment, not the detector's label.
- `signal_runner.py:847` — `CONFLUENCE_SETUP_ROUTES` defaults OFF, so `signal_type` itself
  never becomes `BR_OCR_CONFLUENCE`.

So *"BR and OCR is also a setup when both of them are together"* is implemented as a **string
tag no measurement rig can group by**, and his request has effectively never been answered with
a number.

### What the grade-time proxy already says, and one negative result

Using the book's `confluence` column (`dg.has_confluence` at grade time):

| | detections | traded | mean R | win |
|---|---:|---:|---:|---:|
| confluence = **yes** | 50,510 (**66.4%**) | 1,528 | **+0.5205** | **51.0%** |
| confluence = **no** | 25,509 | 909 | **+0.5982** | 46.1% |

- The 66.4% confirms the rulebook line (*"confluence is currently handed to 66.0% of all
  detections, so as implemented it cannot discriminate at all"*).
- **The `+1` upgrade points the wrong way on the money gate** (−0.0777 R) while pointing the
  right way on win rate (+4.9 pts). Austin's arithmetic (`score = tripped − confluence`, and
  batch 03's *"BR and OCR as +1 upgrade"*) is currently spending a bonus on a flag that costs
  mean R.
- **Negative result, recorded so nobody re-runs it:** the obvious suspect — `_label_confluence`
  and `backtest_2y.py:151` both pass **`stop`** as the level proxy while every detection site
  already emits `sig["level_price"]` (`:2827, 2913, 3010, 3091, 3164, 3251`) — **is not the
  cause.** `research/g71_rule84ocr_confluence_level.py`, 338 real signals over 8 symbols × 30
  sessions: `has_confluence(stop)` and `has_confluence(level_price)` **agree 99.4%** (75.1% vs
  75.7% yes-rate). The proxy is fine. The 66% comes from `find_ocr`'s 20-bar lookback: a
  colour-isolated counter-candle inside 20 bars is simply common.

---

## Diffs (NOT applied — this is a diagnosis pass)

### D1 — label BR+OCR end-to-end so it can be counted (answers his ask directly)

```diff
--- a/backtest_week.py
+++ b/backtest_week.py
@@ -277,6 +277,13 @@ class SimTrade:
     # block (stop = the far side of the block) or when intrabar_stop() collapsed
     # the stop onto the entry bar's own extreme. Read only by ENTRY_SCRATCH.
     level_price: float = 0.0
+    # G71/rule84ocr: Austin -- "remember BR and OCR is also a setup when both of
+    # them are together." signal_runner._label_confluence stamps sig["setup_type"]
+    # = SignalType.BR_OCR_CONFLUENCE and sig["br_ocr"] on EVERY qualifying signal,
+    # but SimTrade never carried them, so the label died here and no book, report
+    # or A/B has ever been able to group by it. Carrying it changes no routing:
+    # `signal_type` is untouched (CONFLUENCE_SETUP_ROUTES stays the routing flag).
+    setup_type: str = ""
+    br_ocr: bool = False
 
     @property
     def counted(self) -> bool:
@@ -866,6 +873,9 @@ def simulate_day(
                          reason=sig["reason"], entry_idx=i, exit_idx=len(candles) - 1,
                          be_level=be_level, scale_level=scale_level,
                          runner_target=runner_tgt)
+            _st = sig.get("setup_type")
+            t.setup_type = getattr(_st, "value", _st) or t.signal_type
+            t.br_ocr = bool(sig.get("br_ocr"))
             trades.append(t)
```

```diff
--- a/backtest_2y.py
+++ b/backtest_2y.py
@@ -163,7 +163,10 @@ def main():
                     "day": d, "ym": d[:7], "yr": d[:4], "dow": dow,
                     "setup": t.signal_type, "dir": t.direction,
+                    # G71/rule84ocr: the detector's own BR+OCR label, carried
+                    # through SimTrade. `setup` stays the routed type.
+                    "setup_type": t.setup_type or t.signal_type,
+                    "br_ocr": "yes" if t.br_ocr else "no",
                     "grade": t.grade, "status": t.status,
```

```diff
--- a/research/build_bt2y_report.py
+++ b/research/build_bt2y_report.py
@@ -25,7 +25,9 @@ FACETS = [
     ("cls", "Asset class"), ("pool", "Pool"), ("tier", "Watchlist tier"),
-    ("sym", "Symbol"), ("setup", "Setup"), ("dir", "Direction"),
+    ("sym", "Symbol"), ("setup", "Setup"),
+    ("setup_type", "Setup incl. BR+OCR"), ("br_ocr", "BR+OCR at detection"),
+    ("dir", "Direction"),
```

### D2 — wire the ratified 84% reclaim tolerance, in his unit, and unbind it from the target policy

```diff
--- a/signal_runner.py
+++ b/signal_runner.py
@@ -340,6 +340,12 @@
-# T-84: the reclaim-tolerance question ballot b01 q12-q15 never answered.
-# Austin: "as long as the close is not too far away from original entry" -- no
-# number given. ... DO NOT INVENT A NUMBER ... stays OFF ("" = unbounded,
-# current shipped behaviour, byte-identical) until Austin picks one.
+# T-84 / G71: ANSWERED. omen-rulebook.md batch 04, 2026-08-28 -- "The 84% reclaim
+# tolerance is the one tolerance unit, 25% of the previous candle's range."
+# The R-denominated env override is kept for the sweep, but the DEFAULT is now
+# his unit (BAR_EXTREME_FRAC x the previous candle's range), not "unbounded".
+# NOTE what this replaces: with a flat 2.000 R:R target, the `rr_ok` floor at
+# :2957 is algebraically equivalent to `close <= entry + 0.2R` -- an accidental,
+# one-sided tolerance whose width is set by the TARGET POLICY. P21 changes that
+# policy, so the accidental tolerance must not be what ships.
 _RULE84_RECLAIM_TOL_RAW = os.getenv("RULE84_RECLAIM_TOL", "").strip()
 RULE84_RECLAIM_TOL = float(_RULE84_RECLAIM_TOL_RAW) if _RULE84_RECLAIM_TOL_RAW else None
 
 
-def _reclaim_tol_ok(close: float, entry_price: float, entry_stop) -> bool:
-    if RULE84_RECLAIM_TOL is None:
-        return True
+def _reclaim_tol_ok(close: float, entry_price: float, entry_stop, prev=None) -> bool:
+    """Ratified default: |close - entry| <= BAR_EXTREME_FRAC x previous bar range.
+    RULE84_RECLAIM_TOL (R units) still overrides it, for the sweep."""
+    if RULE84_RECLAIM_TOL is None:
+        if prev is None:
+            return True                      # no previous bar -> unbounded
+        rng = prev.high - prev.low
+        return rng <= 0 or abs(close - entry_price) <= BAR_EXTREME_FRAC * rng
     if entry_stop is None:
         return True
```

both call sites (`:2946`, `:3193`) pass the previous bar:

```diff
-                and _reclaim_tol_ok(current.close, self.session.entry_price, self.session.entry_stop)
+                and _reclaim_tol_ok(current.close, self.session.entry_price,
+                                    self.session.entry_stop,
+                                    self.candles[-2] if len(self.candles) > 1 else None)
```

**Ship behind a flag and A/B it.** It is a detection change on a setup currently booking
−0.0824 R, and the accidental `d ≤ 0.2R` window it replaces is *narrower*, so recall moves
first. The `rr_ok` floor at `:2957-2959` should move behind the **same** flag (it is what
manufactured the accidental tolerance) rather than being deleted outright — deleting both at
once makes the arms uninterpretable.

### D3 — the OCR stop-width gate

Not proposed as a diff yet: `0.004` is a real constant with a real 2R rationale, and the honest
fix is T4's shape (scale it to the symbol's own range), not a second magic number. Flagged as
the next measured lever, sized at **964 detections, 17.9% of OCR, 100% of them killed**.

---

## Recommended order

1. **D1** — costs nothing, changes no routing, and is literally what he asked for. Until it
   lands, nobody can answer *"how does BR+OCR do?"* with a number.
2. **Wire `find_ocr`'s colour isolation into detection behind a flag and A/B it against
   `_is_isolated`.** 48.9% of candidates are a clean OCR by his rule and are discarded by one
   with no source. Largest OCR recall lever on the board.
3. **Exempt BR+OCR confluence from `_has_displacement` in `detect_order_block_setup`**, per
   ballot q18 — a ratified exemption currently inverted into a hard veto.
4. **D2**, flagged and A/B'd.
5. Delete the dead clause at `:2881` / `:3143`, the two dead `ARM84_FUNNEL` stages, and fix the
   false comment at `backtest_week.py:436`. Zero behaviour change; removes four future
   false-confidence reads.
