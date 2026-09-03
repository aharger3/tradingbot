# G7.1 adversarial verify — track `exitfam`, T8 crash claim

**Verdict: CLAIM UPHELD on the working-tree book; the crash is BOOK-CONDITIONAL
and does NOT occur on the T0-ratified 2,595-trade book the script itself pins.**

## What was independently reproduced

`python research/t8_strike_sweep.py` — exact traceback, same frames:

```
research/t8_strike_sweep.py:230 priced -> :204 __init__ -> :215 px
black_scholes.py:66 price -> black_scholes.py:53 d1_d2
    d1 = (math.log(S / K) + ...) / vt
ZeroDivisionError: float division by zero
```

Offending row isolated (`research/g71_exitfam_verify_t8.py` companion check):

| sym | day | entry | nearest_strike | inc | k | K | dir |
|---|---|---|---|---|---|---|---|
| ACHR | 2024-10-15 | 3.08 | 2.50 | 2.50 | −1 | **0.00** | call |

Exactly **1 of 2,437** traded rows. Every element of the claim's evidence is
confirmed verbatim.

## The missing guard is real and unconditional

`research/t8_strike_sweep.py:186` `self.K = base + strike_k * inc` — no positivity
check anywhere in `Contract.__init__` (lines 180–212). The `self.ok` filter at
:211 tests `sigma`, `risk_u`, `premium_risk` — never `K` — and it is evaluated at
:211, *after* the pricing call at :204 that raises. `self.ok` can therefore never
suppress this row. `black_scholes.d1_d2`'s docstring (`black_scholes.py:51`)
contracts only `T > 0, sigma > 0`; K>0 is the caller's obligation and t8 does not
discharge it.

## Where the claim is materially wrong: the book

`research/bt2y_trades.json` on disk right now: **2,437 traded / 76,019 signals,
generated 2026-08-29T03:14**. The script prints its own alarm on that file:

```
book fingerprint: n=2437 mean_r=+0.5495  *** NOT THE PINNED BOOK ***
```

`PINNED_N = 2595` / `PINNED_MEAN_R = 0.5481` (t8:123–124), matching
`research/t0_ratified_rebaseline.md:24` (75,953 signals, 2,595 traded).

Re-ran the **unmodified** t8 sections against the T0-ratified book
(`.claude/worktrees/wf_a5cd199d-944-2/research/bt2y_trades.json`, n=2,595,
mean R +0.5481, fingerprint PINNED):

```
book fingerprint: n=2595 mean_r=+0.5481  PINNED (T0-ratified)
... sweep, cards, assumptions all render ...
COMPLETED WITHOUT EXCEPTION
```

- **K≤0 rows in the 2,595 book: 0.** Lowest entry in the whole book is ACHR
  2026-07-02 at **5.12** → base 5.00, ATM−1 = 2.50 > 0.
- **ACHR 2024-10-15 does not exist as a traded row in the 2,595 book** — it is
  introduced only by the newer 2,437-row regeneration another track wrote at
  03:14 (which *lost* 158 trades relative to T0 while gaining 66 signals).

So the claim's headline, "CRASHES on the current book", is true of the file on
disk and false of the ratified book. A reader who takes it as "T8 is broken"
will draw the wrong conclusion: T8 was and is green on the book it pins.

## Other adversarial checks

- **Look-ahead**: none in the crash path. `prior_session_range` (t8:144) filters
  `f[:-4] < day` — strictly prior session; sigma is ex-ante by construction.
- **Reachability in production**: nil. `Contract` is local to this research rig.
  `options_sizer.nearest_strike` (options_sizer.py:151) cannot itself return ≤0;
  only t8's `+ strike_k * inc` offset can. No detection/live path touches it.
- **Blast radius**: total for the rig — the crash is inside a list comprehension
  at :230 in the first arm, so all six arms and sections 2–3 are lost. That part
  of the claim is right.

## Fix (NOT applied — diagnosis pass)

```diff
--- a/research/t8_strike_sweep.py
+++ b/research/t8_strike_sweep.py
@@ -211,7 +211,11 @@ class Contract:
-        self.ok = (self.sigma > 0 and self.risk_u > 0
-                   and self.premium_risk is not None and self.premium_risk > 1e-9)
+        self.ok = (self.K > 0 and self.sigma > 0 and self.risk_u > 0
+                   and self.premium_risk is not None and self.premium_risk > 1e-9)
```

That alone is insufficient — `:204` raises before `:211` runs. The guard must
short-circuit the pricing:

```diff
--- a/research/t8_strike_sweep.py
+++ b/research/t8_strike_sweep.py
@@ -191,6 +191,11 @@ class Contract:
         self.strike_k = strike_k
 
+        # A sub-$inc underlying can push the ATM-1 arm to a non-positive strike
+        # (ACHR 2024-10-15 at 3.08: base 2.50, inc 2.50, k=-1 -> K=0.00).
+        # No such contract is listed; drop the row from THIS arm rather than
+        # asking Black-Scholes for log(S/0). Same treatment as a row with no
+        # prior session: dropped, and the drop is reported.
         pr = prior_session_range(row["sym"], row["day"])
         self.sigma = bs.parkinson_sigma(pr, self.S0) * iv_mult if pr else 0.0
@@ -201,10 +206,13 @@ class Contract:
         self.T1 = self.min1 / (RTH_MIN * SESSIONS_YR)
 
-        self.p0 = self.px(self.S0, self.T0) if self.sigma > 0 else None
-        self.pstop = self.px(self.stop, self.T0) if self.sigma > 0 else None
+        priceable = self.sigma > 0 and self.K > 0
+        self.p0 = self.px(self.S0, self.T0) if priceable else None
+        self.pstop = self.px(self.stop, self.T0) if priceable else None
         raw_risk = (self.p0 - self.pstop) if self.p0 is not None else None
         self.premium_risk = (max(raw_risk, MIN_TICK) if raw_risk is not None else None)
         self.tick_floored = raw_risk is not None and raw_risk < MIN_TICK
-        self.ok = (self.sigma > 0 and self.risk_u > 0
+        self.ok = (priceable and self.risk_u > 0
                    and self.premium_risk is not None and self.premium_risk > 1e-9)
```

Note the consequence the fix must disclose: the ATM−1 arm then carries n=2,436
against 2,437 in the other arms on the 2,437-row book. t8's section 3 already
discloses the analogous "2 of 2595 rows have no earlier archive session and are
DROPPED"; the K≤0 drop belongs in the same sentence.

## The larger finding this claim buries

`research/bt2y_trades.json` was overwritten at 2026-08-29T03:14 with a book that
is **158 trades short of T0** (2,437 vs 2,595) at a different mean R (+0.5495 vs
+0.5481). Every rig reading that path is now measuring a book nobody ratified.
t8 is the only one that noticed, because it is the only one carrying a
fingerprint pin. That is the defect worth escalating, not the K=0 crash.

Scripts: `research/g71_exitfam_verify_t8.py` (runs unmodified t8 against the
pinned book without editing it).
