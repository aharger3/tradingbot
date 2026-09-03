# G7.1 / drawdown — ADVERSARIAL VERIFY: the concurrency claim is REFUTED

Script: `research/g71_verify_drawdown_concurrency.py` (read-only, no engine file touched).
Target: `research/g71_drawdown_concurrency.py` + `research/g71_drawdown.md`.

## Verdict

The **arithmetic reproduces exactly** — I re-ran `g71_drawdown_concurrency.py` and got
18 / 22.50R / 9 of 496 / 44 of 496, character for character. The **interpretation does not
survive**. Two independent errors compound in the headline number, and a third breaks the
Apex sentence.

Corrected headline: **12 distinct symbols open at 2025-08-22 10:03 ET, 12.00R = $12,000 of
worst-case simultaneous open risk on this book's own stop rules.** The claim's 22.50R /
$22,500 is an **87.5% overstatement**.

---

## 1. The -1.25R floor is UNREACHABLE in this book (0 of 2,437 rows)

`backtest_week.py:199` ships `DISASTER_STOP=1` at `DISASTER_R=1.0` — a resting order at
entry ∓1.00×risk that fills on an intrabar **touch** (`backtest_week.py:378-391`,
`"a stop order that is touched fills there — so a disaster stop-out books exactly
-DISASTER_R, comfortably inside MAX_LOSS_R"`). It always fires before a close can slip
past -1.25R.

Measured on the book on disk:

| statistic | value |
|---|---:|
| rows with `r <= -1.20` | **0** of 2,437 |
| `min(r)` over the whole book | **-1.000** |
| losses booked at exactly -1.000 | **1,207** of 1,225 |

The claim multiplies concurrency by **1.25R per position**. The book's own maximum
per-position loss is **1.00R**. This is the `rules-unreachable-in-code` bug class turned
inside out: a real rule (the -1.25R slippage floor) that a *later* rule (the -1.00R
disaster order, ratified 2026-08-29) made dead again — and the drawdown track then priced
risk off the dead one.

## 2. "18 positions" is 18 BOOK ROWS across 12 SYMBOLS

At 2025-08-22 10:03 ET the 18 open rows are:

```
AMD 1, AMZN 1, AVGO 1, COIN 1, HOOD 1, INTC 4, META 2, MU 3, NVDA 1, PLTR 1, TSLA 1, TSM 1
```

Six of the eighteen are level-collision duplicates of one physical entry:

| sym | rows | entry | stop | exit | bars | differs only in |
|---|---:|---:|---:|---:|---:|---|
| MU  | 3 | 117.75 / 117.73 / 117.70 | **117.18 all three** | **120.00 all three** | 7 | `level` = OR high / PDH / PMH |
| INTC | 4 | 24.14 / 24.28 / **24.28** / 24.27 | **23.97 all four** | — | 207/116/**116**/207 | seq 2 and seq 3 are **byte-identical** (pnl 425.39 both) |
| META | 2 | **748.35 both** | 745.50 / 744.10 | 751.00 both | 6 | `level` = PDH / pivot high |

An account holds 12 tickets there, not 18. Deduped on `(sym, dir)`:

| metric | claim (book rows) | deduped (positions) |
|---|---:|---:|
| max concurrency | 18 | **12** |
| minutes with ≥6 open | 374 / 28,450 = **1.31%** | 42 / 28,450 = **0.15%** |
| worst-case open risk at -1.25R | 22.50R | 15.00R |
| worst-case open risk at the book's real -1.00R | 18.00R | **12.00R = $12,000** |

The "how often is the book deep" figure is overstated **8.7×**.

## 3. The Apex sentence is wrong at the risk unit, not the floor

`g71_drawdown_concurrency.py:102` prints *"the whole Apex $150K EOD floor at $1,000/R"*.
`research/g4_prop_fit.md:23` does give the Apex $150K EOD trailing DD as **$4,000** — that
part is right. But `g4_prop_fit.md:49` and `:130` set that plan's **risk unit at $250 flat**
(43%W), not $1,000:

> *"Firm: Apex Trader Funding, $150K EOD plan. **Risk unit: $250 flat**"* — `g4_prop_fit.md:130`

A -4.00R session on that plan is **-$1,000 = 25% of the $4,000 floor**, not the whole thing.
"Consuming an entire Apex EOD floor in one session" requires sizing 4× above what the
project's own prop-fit doc prescribes for the account being blown. $1,000/R is the OMEN
backtest's sizing skin (`bt2y_trades.json:meta.risk_dollars`), not Apex's.

## 4. The -3.00R count is a tie-order artefact (44 vs 45)

`g71_drawdown_concurrency.py:57` does `tr.sort(key=(day, et))` before bucketing, then
re-sorts each day by exit minute. Python's sort is stable, so **the within-exit-minute
order is load-bearing on the running minimum**. Drop the initial sort and the same code
returns 45, not 44:

| variant | ≤ -3.00R | ≤ -4.00R |
|---|---:|---:|
| as published (pre-sorted by day,et) | 44 | 9 |
| same code, no pre-sort | **45** | 9 |
| symbol-deduped positions | **42** | **8** |

The 9 / 1.8% at -4.00R is the one figure that survives all three variants. The 44 / 8.9%
at -3.00R does not.

## 5. What DOES hold up

- `bars` really is minutes. `backtest_2y.py:173` writes `"bars": max(0, exit_idx - entry_idx)`
  and the archive is 1-minute (`data_archive/NVDA/2025-08-22.csv` → `04:00`, `04:01`, …).
  `et` is the entry minute (`entry_i=33` ↔ `10:03`, RTH index 0 = 09:30). No unit error.
- **No look-ahead.** The reconstruction reads only `(day, et, bars, r)` off already-closed
  trades and never re-implements a fill.
- 206 of 2,437 rows exit after 11:00 ET (max 15:59) — runners held past the entry window,
  which is by design, not a leak.
- The right book was used: 2,437 traded, `loss_halt: true`, generated 2026-08-29T03:14.
  The prompt's 2,595 figure is the **pre-T23** book; `g71_drawdown.md:211` already flags
  `DIRECTION.md:20,27` as stale for exactly this reason. Not a wrong-book error.
- Denominator quibble is immaterial: 496 days-with-a-trade vs 500 `meta.sessions` moves
  1.81% → 1.80%.

## 6. Rhetorical note

The instant chosen as the peak-risk exhibit, 2025-08-22 10:03 ET, is a day on which
**all 18 open rows won, +36.06R**. It is a legitimate maximum for concurrency; it is a
poor exhibit for "worst-case open risk".

## 7. Fix (NOT applied — diagnosis pass)

```diff
--- a/research/g71_drawdown_concurrency.py
+++ b/research/g71_drawdown_concurrency.py
@@
-RISK = 1000.0
+RISK = 1000.0
+# The book's real per-position worst case. backtest_week.py:199 ships
+# DISASTER_STOP=1 at DISASTER_R=1.0 -- a resting intrabar-touch order that
+# fires before any close can slip to stop_rule.MAX_LOSS_R. Measured: 0 of
+# 2,437 traded rows reach -1.20R; min(r) = -1.000; 1,207 of 1,225 losses are
+# exactly -1.000. Using 1.25 here prices risk off dead code.
+PER_POS_R = 1.00
@@
         span = defaultdict(list)
         for t in rows:
             a = mins(t["et"])
             b = a + max(1, int(t.get("bars") or 1))
             for m in range(a, b):
-                span[m].append(t)
+                span[m].append(t)
+        # One account ticket per (sym, dir): MU/INTC/META fire the same physical
+        # entry off two or three named levels and the book keeps a row for each.
+        span = {m: {(t["sym"], t["dir"]) for t in v} for m, v in span.items()}
@@
-            risk = 1.25 * n
+            risk = PER_POS_R * n
@@
-    print("  worst-case open risk at that moment: %.2fR = %s"
-          % (1.25 * best_conc, usd(1.25 * best_conc * RISK)))
-    print("  (every open position at the -1.25R stop floor, all at once)")
+    print("  worst-case open risk at that moment: %.2fR = %s"
+          % (PER_POS_R * best_conc, usd(PER_POS_R * best_conc * RISK)))
+    print("  (every open position at the -1.00R disaster stop, all at once)")
@@
-    print("  which is the whole Apex $150K EOD floor at $1,000/R in one session.")
+    print("  = -$1,000 at the Apex $150K plan's own $250 risk unit")
+    print("  (g4_prop_fit.md:130), i.e. 25%% of its $4,000 EOD floor -- not all of it.")
```

Plus: drop the `tr.sort(key=(day, et))` at line 57 or make the exit-minute sort total
(`key=(exit_min, sym, seq)`), so the -3.00R count stops depending on tie order.
