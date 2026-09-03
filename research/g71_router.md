# G7.1 adversarial verify — track `router` dedupe claim

**Verdict: REFUTED as stated.** The underlying mechanism is real and large, but three
of the four evidence cites are wrong or misleading and "ROOT CAUSE" is not established.

Rig: `research/g71_router_dedupe_count.py` (replicates `simulate_day`'s detection+dedupe
loop, `backtest_week.py:751,818-833`; 28 symbols, 500 sessions, 2024-08-21..2026-08-21).
Probe used to find the flaw in the first instrument: `research/g71_router_dedupe_probe.py`.

## Point by point

| claim | status |
|---|---|
| dedupe applied at `backtest_week.py:864-870` | **FALSE**. 861-869 is the `SimTrade(...)` constructor + `trades.append(t)`. The dedupe is **830-833**. No `continue` exists in 864-870. |
| "an X row is **dropped from the book**" | **FALSE**. X rows are appended to `trades` at :869 and land in the book: `research/bt2y_trades.json` = 76,019 rows, **69,624 grade `X` / status `skipped_d`**, 3,487 `fired`. The `continue` at :832 drops only *deduped* rows, of any status. |
| "an X row arms the window, each later X re-arms" | **TRUE**. :833 writes `seen[key]=i` for every status; :831 extends. |
| docstring at :88 says "after a fire" | **TRUE** (lowercase, not "FIRE"). But it is one stale line under an 8-line design comment at :77-84 that describes the intent as suppressing *the detector re-firing on every bar while the setup is still standing there* — detection, not fires. The claim elevates the docstring over the comment without arguing it. |
| `t4_engine_recall.py:206-216` "does it the documented way: a separate `seen` map written only when status == 'fired'" | **MISLEADING**. t4 keeps **two** maps. 206-210 is `seen_any`, written for **every** captured signal — the exact all-status arming the claim calls the bug. Only 211-216 is fired-only, and it uses **`DEDUPE_BARS`=30**, not `dedupe_window()`=2. t4 is not a like-for-like reference. |
| window is 2 bars, `DEDUPE_MODE='level'` -> `DEDUPE_CONTIG=2` | **TRUE**, confirmed at runtime (`DEDUPE_MODE=level`, `dedupe_window()==2`). Cite `82-90` is right (82/84/87-90). |

## The numbers (28 syms, 500 sessions, 137,242 captured signals, 9,853 with status `fired`)

| arm | rule | entries |
|---|---|---:|
| A — as shipped | all-status map, 2-bar | **4,022** |
| B — claimed fix | fired-only map, 2-bar | **8,253** |
| C — actual t4 shape | fired-only map, **30-bar** | **7,514** |

- Fired signals arm A loses to a **non-fired** predecessor: **4,231** (killer `skipped_d` 3,797,
  `skipped_tight_stop` 434). Grade mix: B 2,684, C 1,519, A 20, A+ 8.
- Arm B loses zero that arm A keeps. Branch is reachable; no look-ahead in either arm.
- Caveat: this rig is detection-only, so `_arm_84` re-entries never arm. It reproduces 4,022
  vs the book's 3,487 `fired` + 857 `halted` = 4,344; the ~322 gap is the missing 84%
  re-entries. 4,231 is therefore a **lower bound**, and it moves the same way in both arms.

## Why "root cause" fails

The harness and the book differ on **two** axes — map arming *and* window (2 vs 30). The claim
names one. Fixing only the arming (A→B) does not land on the harness: it **overshoots C by 739
entries**. And the direction of the "fix" is to more than double the book (4,022 → 8,253) by
re-admitting a level that emits `X` at bar *i* and `B` at bar *i+1* as two trades — precisely
the "one idea, not twenty" case :77-84 says the window exists to collapse. Whether that is a
bug or the design is a question the claim asserts rather than answers.

Counted on the current book (`meta.generated 2026-08-29T03:14`, post-`35db9256` 02:57), not
an older one. The claim itself carries **no count at all**, so it cannot have been taken on
any book.
