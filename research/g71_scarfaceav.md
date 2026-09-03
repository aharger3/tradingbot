# G7.1 adversarial verify — track `scarface`, the "conflict with T1"

**Verdict: REFUTED.** The conflict is a definitional artifact. Two scripts use the word
"silent" for two different things; on a common definition the two samples agree.

Script: `research/g71_scarfaceav_defs.py` (read-only, replays both sets through
`research.t4_engine_recall.run_day`). Raw: `research/_g71_scarfaceav_defs.json`.

## The two definitions

| script | line | "silent" means |
|---|---|---|
| `research/t1_entry_minute_autopsy.py` | the final `else:` of the verdict chain (`elif fired or seen:` … `else: SILENT`) | **no signal at all, all day** — union of fired entries *and* `all_sigs` (every grade, incl. `X`/D-skips and tight-stop-C skips) |
| `research/g71_scarface_recall.py:31` | `entries, _s, _raw = run_day(...)` … `else: C["silent"] += 1` | **no FIRED entry** — `all_sigs` is bound to `_s` and thrown away |

`t4_engine_recall.run_day` returns `(entries, all_sigs, raw_sigs)`. The scarface script
discards the middle element, so the T1-comparable quantity is never computed.

## Both definitions, both sets (reproduced at HEAD)

| set | n | fired-day | silent, scarface def (no fire) | silent, **T1 def** (no signal at all) |
|---|---:|---:|---:|---:|
| Austin's 34 stated-minute S days | 34 | 23 (67.6%) | 11 (32.4%) | **0 (0.0%)** |
| Scarface T1+T2 in-universe | 200 | **93 (46.5%)** | **107 (53.5%)** | **1 (0.5%)** |

- The prior agent's 93/107/200 reproduces **exactly**. The numbers are not wrong; the
  comparison is.
- On T1's own definition the Scarface set is silent on **1 of 200** days
  (`TSLA 2025-09-12`, 0 entries / 0 signals). That is not a conflict with 0 of 34 — it is
  an independent corroboration at 6x sample size.
- 106 of the 107 "silent" Scarface days produced signals the router refused to fire
  (median 4, mean 5.3, max 20 signals per day). Same failure mode T1 named: a **grading**
  problem, not a detection problem.

## Why the selection-bias story does not survive

The claim needs Austin's deck to be *easier* in a way that hides silence. Measured on the
one metric both scripts can share:

- T1 def: Austin 0.0% silent vs Scarface 0.5% — indistinguishable.
- Scarface def: Austin 32.4% no-fire vs Scarface 53.5%. Austin's set is easier on
  *firing*, but T1 never made a firing claim; T1's 6 FIRED / 9 DETECTED / 19 ELSEWHERE
  table already says the engine fails to take these trades. The conclusion the claim
  attacks ("never silent → grading not detection") is the one that generalises.

## Other checks

- **Right book?** Moot. Neither number comes from a trade book. Both are
  `run_day` replays over `data_archive/`; `g71_scarface_recall.py` imports nothing from
  `backtest_2y`/`backtest_week` except `dedupe_window` via `t4_engine_recall`. The
  2,595-vs-1,017 trade question does not apply.
- **Look-ahead?** None on the engine side: `run_day` feeds `candles[:i+1]`, PDH/PDL from
  the prior archived day, PMH/PML from 04:00–09:29 of the same day, HTF bias from prior
  closes, 11:00 cutoff. Label side is contemporaneous Discord alerts.
- **Branch reachable?** Yes — 107/200 hit the scarface `silent` branch, 1/200 hits T1's.

## Stale numbers found in passing (not part of the claim)

`research/t0_heldout_recall.json` (`fired_on_S: 18/34`, 52.9%) and the recall row in
`DIRECTION.md` are **stale at HEAD**: fired-day recall on the same 34 cards is now
**23/34 = 67.6%**. Five of the 16 stored `missed_S` now fire: `ACHR_2026-02-05`,
`ARM_2024-10-28`, `HOOD_2024-11-06`, `PLTR_2025-07-01`, `QQQ_2025-09-23`.
`research/t1_entry_minute_autopsy.md` is stale for the same reason (its FIRED/DETECTED
split predates T4/T11/T23); its 0-of-34 SILENT line still holds.

## Fix (not applied — diagnosis pass)

```diff
--- a/research/g71_scarface_recall.py
+++ b/research/g71_scarface_recall.py
@@
 C = Counter(); silent = []
 for r in cand:
     try:
-        entries, _s, _raw = run_day(r["symbol"], r["day"])
+        entries, sigs, _raw = run_day(r["symbol"], r["day"])
     except Exception as e:
         C["error"] += 1; continue
     entries = entries or []
+    sigs = sigs or []
     C["tested"] += 1
     if entries:
         C["fired"] += 1
@@
     else:
-        C["silent"] += 1; silent.append(r["card_id"])
+        # NOT the same as T1's SILENT: T1 requires no signal at all.
+        C["no_fire"] += 1; silent.append(r["card_id"])
+        if not sigs:
+            C["silent_no_signal"] += 1
 n = C["tested"]
 print(f"tested={n} errors={C['error']}")
 print(f"  OMEN fired at least once : {C['fired']}  ({C['fired']/max(1,n)*100:.1f}%)")
-print(f"  OMEN SILENT              : {C['silent']}  ({C['silent']/max(1,n)*100:.1f}%)")
+print(f"  OMEN did not FIRE        : {C['no_fire']}  ({C['no_fire']/max(1,n)*100:.1f}%)")
+print(f"  OMEN SILENT (T1 def)     : {C['silent_no_signal']}  ({C['silent_no_signal']/max(1,n)*100:.1f}%)")
```

And in `research/g71_scarface.md`, the paragraph "**This flags a conflict with T1**"
(lines 143-148) should be replaced with: no conflict — on T1's definition the Scarface set
is silent 1/200; the 53.5% is a no-fire rate and corroborates the *grading* wound.
