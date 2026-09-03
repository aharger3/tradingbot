# G71 / sigfire — signal vs fire: the full pipeline, counted

**Austin asked:** *"i think the amount of signals detected is crazy... what causes
signals vs firing because i feel like engine firing is the only items that should be
seen. is on watch creating a signal detection large pool error?"*

**Answer in one line: no, ON WATCH is not the pool. The number labelled "signals" is the
count of times the engine LOOKED at a candidate and mostly said no — 91.6% of it is grade
`X`, which means "should not have fired". Nothing is broken; the label is wrong.**

Scripts: `research/g71_sigfire_funnel.py` (the stages the book can see),
`research/g71_sigfire_upstream.py` (instrumented replay for the stages above the book).
Book: `research/bt2y_trades.json`, generated 2026-08-29 03:14, 500 sessions, 28 symbols,
2024-08-21 → 2026-08-21, 11,808 symbol-days.

---

## 1. The funnel, stage by stage, over the 2-year book

Every count below is exact, not scaled: `research/g71_sigfire_upstream.py --stride 1`
replayed all 500 sessions and reproduced the shipped book row for row (76,019 / 4,344 /
3,294 / 1,050).

| # | stage | where it happens | count | % of stage 1 |
|---|---|---|---:|---:|
| 1 | **bar scans** — `detect_signals()` once per 1-min bar in 09:30–11:00, per symbol-day | `backtest_week.py:820` | **1,024,103** | 100.000% |
| 2 | **raw candidates** — a detector's pattern matched and posted a signal dict | `signal_runner.py:2428` `_emit`, 11 call sites | **137,587** | 13.435% |
| 2b | pre-route vetoes: retired setup (FVG/flag), session-extreme veto | `signal_runner.py:2440–2447` | **0** — both ship off | 0% |
| 3 | **routed** — reached `_route` | `signal_runner.py:2491` | **137,587** | 13.435% |
| 4 | **accepted at `_route`** (pre-dedupe) | `signal_runner.py:2623` | **10,173** | 0.993% |
| 5 | **book rows after R16 dedupe** — **this is what is reported as "signals"** | `backtest_week.py:830`, captured `:644` | **76,019** | 7.423% |
| 6 | └ **graded `X`** — the engine's own verdict "should not have fired" | `omen_bot.py:243/262/272/275/285` | **69,624** | 91.59% of row 5 |
| 7 | └ skipped: tight stop / min-stop-pct | `signal_runner.py:2595–2625` | **2,051** | 2.70% of row 5 |
| 8 | └ **fired** (pre-halt) | `backtest_week.py:633` | **4,344** | 5.71% of row 5 |
| 9 |   └ **`C` = ALERT**, never auto-traded (SPEC2) | `backtest_week.py:288` `is_alert` | **1,050** | 1.38% of row 5 |
| 10 |   └ **WANTED TO TRADE** — fired and grade ≠ `C` | `backtest_week.py:283` `counted` | **3,294** | 4.33% of row 5 |
| 11 | **halted** by R31's two-consecutive-loss governor, after the fact | `loss_halt.py:110` | **857** | 1.13% of row 5 |
| 12 | **BOOKED** | `meta["traded"]` | **2,437** | 3.21% of row 5 |
| 13 | └ what the **LIVE path** would take (`grade == "A+"`) | `live_scanner.py:579` | **4** | 0.005% of row 5 |

Raw candidates by setup: `break_and_retest 130,209 · one_candle_rule 6,990 ·
reentry_84_rule 388`. Book rows by setup: `break_and_retest 70,237 · one_candle_rule
5,394 · reentry_84_rule 388`.

Engine grade over all 76,019 routed rows: `X 69,624 · B 3,191 · C 3,053 · A 144 · A+ 7`.
Austin's ladder over the same rows (measured only, never wired):
`C 48,457 · A 17,639 · S 9,923`; over the 2,437 booked trades: `C 1,614 · A 525 · S 298`.
2,154 of 11,808 symbol-days (18.2%) produce at least one booked trade; 496 of 500 sessions
do, at **4.91 booked trades per trading session**.

### 1a. Three structural reads from that table

1. **`_emit` → `_route` survival is 100.00%** (137,587 → 137,587). Both pre-route vetoes
   ship OFF (`SESSION_EXTREME_FRAC = 0.0`, `signal_runner.py:1060`; the FVG/flag detectors
   are retired and never emit). There is no hidden inflating stage — and equally, no
   filter above `_route` to blame.
2. **R16 dedupe removes 45% of routed candidates before a book row exists**
   (`backtest_week.py:830`, `DEDUPE_CONTIG = 2`): 137,587 routed → 76,019 rows. **The
   76,019 Austin sees is already post-dedupe** — the engine actually looks at 137,587
   candidates over a million bar-scans. The book *under*-reports the search, not over.
3. **Inside the surviving pool the same idea still repeats.** 76,019 rows collapse to
   **32,064 distinct `(symbol, day, setup, direction, level)` ideas — 2.37 rows per idea,
   worst single idea 22 rows.** Density: **152.0 rows per session, 6.4 per symbol-day.**

### 1b. The number Austin quoted is out of date, and it went UP

`DIRECTION.md` says 45,193. That is the pre-T0 engine. T0 landed R1–R27 on 2026-08-29 and
the same count is now **76,019** (`research/t0_ratified_rebaseline.md` §1: 45,193 →
75,953; the shipped book re-ran at 76,019). So the pool he is reacting to is 68% larger
than the figure he had.

### 1c. He sees the same thing live, and there it is worse

The live scanner constructs its runner with `log_signals` defaulting to True
(`signal_runner.py:1798`), and `_log_record` writes a row for **every skip**
(`signal_runner.py:2268`). Recent `journal/signal_log_*.jsonl`:

| file | rows | breakdown |
|---|---:|---|
| `journal/signal_log_2026-08-14.jsonl` | 34 | `skipped/X` 34 |
| `journal/signal_log_2026-08-17.jsonl` | 37 | `skipped/X` 37 |
| `journal/signal_log_2026-08-18.jsonl` | 25 | `skipped/X` 25 |

Three consecutive sessions, 96 log rows, **zero fires**. That is exactly his sentence:
"engine firing is the only items that should be seen."

---

## 2. (a) What makes something a "signal" vs a "fire"

Two different lines of code, ~130 lines apart in the same function.

**"Signal"** = anything that reaches `SignalRunner._route` (`signal_runner.py:2491`).
`backtest_week.BacktestRunner._route` (`backtest_week.py:619–644`) delegates to the base,
labels the outcome, then appends **unconditionally**:

```
backtest_week.py:644            self.captured.append(sig)
```

Its docstring says so outright: *"Capture ALL signals including D-grade and tight-stop
skips."* `backtest_2y.py:222` then publishes `len(rows)` under the key `"signals"`, and
`research/build_bt2y_report.py:777` prints it in the report header as "76,019 signals".
**That number is the size of the engine's search, not its opinion.**

**"Fire"** = the base `_route` reached its one accept statement:

```
signal_runner.py:2623                signals.append(sig)
```

To get there a candidate must survive, in order: `_grade_for_levels` →
`_calibration_grade` → `S_GATE` → `RULE_710` → level retirement → `_apply_x_lift` →
**`grade not in ("X","D")`** → `ENFORCE_NO_REPEAT` → `MIN_STOP_PCT` → `_min_viable_stop`
(C only) → `NO_REPEAT_ENTRIES`. Every other exit from `_route` calls
`_log_record(..., status="skipped")` and returns.

**The single dominant reason a signal is not a fire is grade `X`, and `X` has two
sources, both in `omen_bot.py`:**

| source | line | share of the 69,624 X rows |
|---|---|---:|
| **HTF bias opposed** — higher-timeframe trend against the trade | `omen_bot.py:242–243` | **35,075 (50.4%)** |
| **`_grade_pa` candle shape / not at level** — wrong candle colour, or the close never came back to the level | `omen_bot.py:262, 272, 275, 285` | 34,549 (49.6%) |

Only **553** of the book's 35,628 HTF-opposed rows escape `X`. `_grade_pa` is a
candle-shape grader: its first line for a long is `if not candle.is_bullish: return
TradeGrade.D` (`omen_bot.py:261–262`).

Three further states exist and are **not** fires:

- **ALERT** — fired but graded `C`: `counted` False, `is_alert` True
  (`backtest_week.py:283–289`). SPEC2 makes `C` manual-review-only. 1,050 rows.
- **HALTED** — fired and tradeable, then blocked after the fact by R31
  (`loss_halt.py:110`). 857 rows: `B 783 · A 71 · A+ 3`.
- **WATCH (live only)** — `live_scanner._tier()` returns `"WATCH"` for everything that is
  not `A+` (`live_scanner.py:579`). **This is a different "watch" from ON WATCH.**

---

## 3. (b) Is ON WATCH creating the giant pool? **No. Categorically no.**

`ON_WATCH` is defined at `signal_runner.py:501–503` and **read at exactly one place in
the repo**:

```
signal_runner.py:1323-1329   (inside fill_price)
    if not (bar_extreme_veto(probe, candle)
            or (ON_WATCH and near_session_extreme(candle, is_long,
                                                  session_hi, session_lo))):
        return candle.close
    return min(max(level, candle.low), candle.high)
```

It decides **what price a signal that already exists gets filled at** — the close, or back
at the level. It sits downstream of every detector and has no path to `_emit` or `_route`.
Its own comment: *"It is a FILL rule -- see near_session_extreme()."*
**An ON WATCH state does not exist as an engine state and emits no signal record.**

Measured on the post-T0 engine, same 20-session sample, both arms:

| arm | raw candidates | routed | book rows | fired | booked |
|---|---:|---:|---:|---:|---:|
| `ON_WATCH=1` (shipped) | 5,468 | 5,468 | 2,981 | 160 | 138 |
| `ON_WATCH=0` | 5,469 | 5,469 | 2,982 | 184 | 156 |
| **delta** | **+1 = 0.02%** | +1 | +1 | +24 | +18 |

ON WATCH moves **1 candidate in 5,468** — a second-order effect where a different fill
changes what the 84% re-entry arms on. It moves the *fired* count by 15%, **downward**,
because a fill back-dated to the level collapses `entry − stop` under `min_risk_floor`,
which grades the row `X`. That is the pre-existing G12/G13 finding, unchanged.

This reproduces `research/g3_onwatch_2y.md` on the pre-T0 engine, where the flag moved
**0 of 45,193 signals**. ON WATCH is not the pool, was never the pool, and turning it off
makes the number very slightly *bigger*.

**Where the confusion is real, and it is a naming collision in the code:**
`live_scanner._tier()` (`live_scanner.py:571–585`) returns the string `"WATCH"` for every
signal that is not `A+` — 99.9% of them. Two unrelated things are called "watch": a fill
rule and the live scanner's demotion bucket. Neither creates signals.

---

## 4. (c) The one number that means "the engine wanted to trade this"

| number | definition | 2-year value | means |
|---|---|---:|---|
| candidates | `len(rows)` — reached `_route` | 76,019 | **"the engine looked at this"** — reported today as "signals" |
| fires | `status == "fired"` before the R31 halt | 4,344 | the engine said yes |
| **WANTED** | fired **and** grade ≠ `C` (`SimTrade.counted`) | **3,294** | **"the engine wanted to TRADE this"** ← this one |
| booked | wanted minus the 857 R31 halts | 2,437 | what the book took |
| live | booked and `grade == "A+"` | 4 | what the live path would have taken |

**Ship this definition:**

```
wanted = status in ("fired", "halted") and grade != "C"
```

`C` is out because SPEC2 makes it alert-only — the engine is explicitly *not* asking to
trade a `C`. The halt is out of `wanted` because R31 is a risk governor acting *after* the
engine wanted the trade; it belongs on the `booked` line. `status` must include `"halted"`
because `loss_halt.apply_to_book` overwrites `"fired"` in place (`loss_halt.py:110`).

**3,294 is 4.3% of what is currently called "signals"** — and it reads as a workload:
**6.6 trade requests per session across 28 symbols, 4.9 surviving the loss halt.**

Show one more number beside it: **4**. That is how many of the 2,437 booked trades the
live path would have taken, because `live_scanner.py:579` promotes to `TRADE` only on
`grade == "A+"`. 2,437 vs 4 is the real-money blocker `DIRECTION.md` already names, and it
is a different problem from the 76,019.

---

## 5. The diff

Two files. `backtest_2y.py` publishes the funnel instead of one ambiguous count;
`research/build_bt2y_report.py` leads the header with what the engine wanted. **No engine
file is touched: no book row moves, no trade moves, no gate moves.** The three existing
readers of `meta["signals"]` (`research/build_bt2y_report.py:777`,
`research/g4_dropped_s.py:364`, `research/x8_time_blocks.py:219`) are display-only, so
redefining the key is safe, and the old value is preserved under `candidates` so every
historical A/B figure (45,193, 76,019) stays checkable.

```diff
--- a/backtest_2y.py
+++ b/backtest_2y.py
@@ -205,8 +205,12 @@
                     "reason": t.reason,
                 })
             prev = d
-        print("[%s] %d sessions, %d signals" % (sym, len(day_bars), len(rows) - n0))
+        mine = rows[n0:]
+        print("[%s] %d sessions, %d candidates, %d wanted"
+              % (sym, len(day_bars), len(mine),
+                 sum(1 for r in mine
+                     if r["status"] == "fired" and r["grade"] != "C")))
 
     # R31 — the two-consecutive-loss halt, account-wide, causal on the exit.
     # It has to run here and not inside simulate_day: the halt is a statement
@@ -217,12 +221,38 @@
     out = ROOT / args.out
     out.parent.mkdir(parents=True, exist_ok=True)
+    # G71/sigfire. "signals" used to mean len(rows) -- every candidate that
+    # reached signal_runner._route, 91.6% of which the engine itself graded X
+    # ("should not have fired"). Austin, 2026-08-29: "i feel like engine firing
+    # is the only items that should be seen." So the headline number now means
+    # THE ENGINE WANTED TO TRADE THIS, and the search-space count keeps its own
+    # key rather than being deleted.
+    #
+    #   candidates : reached _route                        (the engine LOOKED)
+    #   graded_x   : of those, the engine's own "do not fire" verdict
+    #   fires      : _route accepted, C alert-only included (the engine said yes)
+    #   alerts     : fired at grade C -- SPEC2 manual review, never auto-traded
+    #   signals    : fired and grade != C          (the engine WANTED TO TRADE)
+    #   halted     : wanted, then blocked by R31 after the fact
+    #   traded     : booked
+    #   live_trade : what live_scanner._tier() would promote (grade == "A+")
+    #
+    # loss_halt.apply_to_book overwrites status "fired" -> "halted" in place, so
+    # every pre-halt count must read status in ("fired", "halted").
+    _fired = [r for r in rows if r["status"] in ("fired", "halted")]
+    _wanted = [r for r in _fired if r["grade"] != "C"]
     meta = {"generated": datetime.now().isoformat(timespec="seconds"),
             "first": min(sessions), "last": max(sessions),
             "sessions": len(sessions), "symbols": syms,
-            "risk_dollars": RISK_DOLLARS, "signals": len(rows),
+            "risk_dollars": RISK_DOLLARS,
+            "signals": len(_wanted),
+            "candidates": len(rows),
+            "graded_x": sum(1 for r in rows if r["grade"] == "X"),
+            "fires": len(_fired),
+            "alerts": sum(1 for r in _fired if r["grade"] == "C"),
+            "live_trade": sum(1 for r in rows
+                              if r["traded"] and r["grade"] == "A+"),
             "loss_halt": bool(loss_halt.LOSS_HALT), "halted": halted,
             "traded": sum(1 for r in rows if r["traded"])}
     out.write_text(json.dumps({"meta": meta, "trades": rows}, separators=(",", ":")),
                    encoding="utf-8")
-    print("wrote %s (%.1f MB) — %d signals, %d traded, %d sessions"
-          % (out, out.stat().st_size / 1e6, len(rows), meta["traded"], meta["sessions"]))
+    print("wrote %s (%.1f MB) — %d sessions"
+          % (out, out.stat().st_size / 1e6, meta["sessions"]))
+    print("  looked at %d candidates (%d graded X) -> wanted to trade %d"
+          " -> booked %d -> live path would take %d"
+          % (meta["candidates"], meta["graded_x"], meta["signals"],
+             meta["traded"], meta["live_trade"]))
```

```diff
--- a/research/build_bt2y_report.py
+++ b/research/build_bt2y_report.py
@@ -239,7 +239,10 @@
     detection) and the engine&rsquo;s legacy A+/A/B/C/X. Filter anything; the numbers,
     the curve and the edge scanner all recompute against what is left.</p>
   </div>
-  <div class="stamp mono">built __GEN__<br>__NSIG__ signals &middot; __NTRADED__ traded<br>1R = $__RISK__</div>
+  <div class="stamp mono">built __GEN__<br>__NSIG__ the engine wanted to trade &middot;
+  __NTRADED__ booked<br><span style="opacity:.55">of __NCAND__ candidates looked at
+  (__NX__ graded X &mdash; should not have fired)</span><br>1R = $__RISK__</div>
 </header>
 
 <div class="wrap">
@@ -774,7 +777,12 @@
             .replace("__GEN__", meta["generated"].replace("T", " "))
             .replace("__NSIG__", "{:,}".format(meta["signals"]))
+            # G71/sigfire: meta["signals"] now means "fired and not alert-only".
+            # A book written before that change carries the old meaning and has
+            # neither new key, so fall back rather than KeyError on an old file.
+            .replace("__NCAND__", "{:,}".format(meta.get("candidates", meta["signals"])))
+            .replace("__NX__", "{:,}".format(meta.get("graded_x", 0)))
             .replace("__NTRADED__", "{:,}".format(meta["traded"]))
```

**Done-check** (no re-backtest needed for the first line):

```
python research/g71_sigfire_funnel.py    # candidates 76,019 / fired 4,344 / wanted 3,294 / booked 2,437 / A+ 4
python research/regression_gate.py       # recall gate stays green
```

---

## 6. What this does NOT fix

The 76,019 is a labelling problem. The two real problems it was hiding are unchanged:

1. **The live gate would take 4 of 2,437 booked trades** — `live_scanner.py:579` promotes
   only `A+`.
2. **`_grade_pa` grades candle shape, not structure**, and says `X` to 91.6% of
   everything — including, per `research/t1_entry_minute_autopsy.md`, all 34 of Austin's
   S days that the engine reached on the exact bar.
