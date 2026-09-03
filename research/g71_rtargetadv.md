# G7.1 / rtargetadv — adversarial verify of `g71_rtarget.md` §4b

**Verdict: REFUTED (headline), REPRODUCED (arithmetic).** The number is real;
the sentence it is turned into is not.

Scripts: `research/g71_rtargetV_evalscan.py`, `research/g71_rtargetV_gatearm.py`,
`research/g71_rtargetV_nocap.py`, `research/g71_rtargetadv_retry.py`.
All import `g71_rtarget_model` and reuse `day_series` / `prop_eval` verbatim.

## What survives

| check | result |
|---|---|
| Right book? | **Yes.** `research/bt2y_trades.json` meta = 2026-08-29T03:14:29, 500 sessions, 76,019 signals, **2,437 traded**. 2,595 is the superseded T0 book (`g71_advscanners.md:89`), 1,017 the dead `backtest_week` one. |
| Look-ahead? | **No.** `g71_firsts_policy.py:77-108` walks candidates in `(entry_i, et, sym)` order, one position at a time, `xkey` gating re-entry. Pure causal selection over already-simulated rows. |
| Branch reachable? | **Yes.** `solve_risk_for_fail` returns `None` and the `NONE` print at `g71_rtarget_model.py:471-475` fires. Not a dead branch. |
| The 30-day arm discriminates? | **Yes.** Same gate, same code: money gate 55%/2.0R clears at $1,325 (min p_fail 1.58%), 55%/1.20R at $975 (7.34%), today's 4.91-trade/day headline at $600 (4.26%). Only the 1/day empirical rows return NONE. |
| Non-monotone `p_fail` breaking the solver's early exit? | **No** on the no-time-cap arm — `p_fail` is monotone there and the full-grid maximum equals the solver's: P1 $550, P1-livecap $400, P2 $475, P4 $375. The claim's "$375–$550 with no time cap" reproduces exactly. |
| Mechanism arithmetic | Correct. P1 meanR/**day** = +0.6115 (496 days, 496 trades — 1 trade every day, so per-trade == per-day, no unit error). 21 × 0.6115 = 12.83R; $9,000/12.83R = $701/R; $4,000/$701 = 5.71R. |
| "no unit ≥ $25 clears 10%" on the 30-day arm | **Reproduces.** Full $25→$3,000 grid, 20k trials/point, seed 84: minimum `p_fail` is P1 33.22% @$1,325, P1-livecap 49.18% @$1,975, P2 29.54% @$975, P4 31.49% @$650. Nothing near 10%. |

## What breaks

### 1. `p_fail` fuses two different events, and the claim rides the fusion

`g71_rtarget_model.py:293-300`: a trial is counted as `fail` if it blows the
$4,000 EOD floor **or** if it simply runs out of 21 days without touching
+$9,000 (`expired`). The function already returns them apart as `p_blow` and
`p_expire`; §5 prints only their sum. Expiry is not a blow-up — it costs the
$397 seat and nothing else, and it is the dominant term everywhere the claim
points:

| policy | largest unit with **p_blow ≤ 10%** | p_blow | p_pass | p_expire |
|---|---:|---:|---:|---:|
| P1 | **$650** | 8.45% | 48.74% | 42.81% |
| P1-livecap | **$625** | 8.91% | 10.64% | 80.44% |
| P2 | **$550** | 9.78% | 56.23% | 33.99% |
| P4 | **$450** | 9.78% | 50.22% | 40.01% |

So "no risk unit at or above $25 clears a 10% failure rate" is true only for a
definition of *failure* that counts walking away from a still-alive account as a
failure. Under blow-the-account, every one-trade-a-day policy clears 10% — and
does so at $450–$650/R, a band that brackets `g4_prop_fit.md`'s funded R\* of
$250–$350.

### 2. "NOT passable" is contradicted by the model's own p_pass column

§5 prints `--` for `P(pass)` on every NONE row, so the report never shows what a
single 21-day attempt actually does:

| policy | best $/R | **p_pass per attempt** | E[attempts] | E[seat spend @$397] |
|---|---:|---:|---:|---:|
| P1 | $1,325 | **66.78%** | 1.50× | **$594** |
| P2 | $975 | **70.46%** | 1.42× | **$563** |
| P4 | $650 | **68.52%** | 1.46× | **$579** |
| P1-livecap | $1,975 | 50.82% | 1.97× | $781 |

`g4_prop_fit.md:47` budgets **$1,006 of eval cost per funded account at 43.0%W**
and still names Apex the vehicle. Every one-trade-a-day policy comes in *under*
that budget. Even at the claim's own $700/R the numbers are p_pass 53.39%,
p_blow 12.12% — a coin-flip pass, not an impossibility.

### 3. The gate is imported from the wrong object

`g4_prop_fit.md:40-45` is explicit: the eval is priced as a **retryable expected
cost**, and *"Apex's 30-day expiry forces this — at 0.7 trades/day you get ~13
trades/attempt, so passing +$9,000 needs $1.5–3k eval risk."* g4's own baseline
is **fewer than one trade a day** and it sizes the eval at $1.5–3k/R precisely
to beat the clock. The <5%/<10% tolerance in g4 is attached to **pre-lock funded
ruin**, a different account with a different unit. `g71_rtarget_model.py` gets
this right in §7c (10% applied to P(funded dead in 12mo)); §5's 30-day arm is the
one place the funded-ruin tolerance is pointed at a $397 lottery ticket.

### 4. "Small units expire, large units blow, no middle" — the middle exists

At $650/R P1 blows 8.45% and passes 48.74%. That *is* the middle. What does not
exist is a unit with a ≥90% **single-attempt** pass rate, which is a much
stronger requirement than the one being claimed.

## Minor, non-load-bearing

- `prop_eval`'s "no time cap" arm is actually a 400-trading-day cap
  (`g71_rtarget_model.py:288`) and counts running out as a *fail*. That is why
  $25/R does not appear in the no-cap clearing list for P1 — at $25/R, 400 days
  × 0.6115R × $25 = $6,115 < $9,000, so most paths are marked failed for being
  slow. Cosmetic here; it does not touch the reported $375–$550.
- P2 (1.42 trades/active day) and P4 (1.74) are not literally "one trade a day".
  The report says so; the claim's parenthetical does not.

## Corrected sentence

> A 30-day Apex seat is passable at one trade a day, but only as a **retryable**
> attempt, and only at an eval-only risk unit far above the funded unit. At
> $1,325/R P1 passes a single 21-day attempt 66.8% of the time (P2 70.5% @$975,
> P4 68.5% @$650), for an expected **$563–$594** of seat fees per funded
> account — under `g4_prop_fit.md`'s own $1,006 budget. What is *not* achievable
> is a ≥90% single-attempt pass rate at any unit $25–$3,000; the ≤10% tolerance
> belongs to funded ruin (§7c), not to a $397 seat. Under a blow-the-account
> definition of failure, every one-trade-a-day policy clears 10% at $450–$650/R.

## Suggested diff (NOT applied)

```diff
--- a/research/g71_rtarget_model.py
+++ b/research/g71_rtarget_model.py
@@ -459,7 +459,7 @@
     print("\n--- 5. THE PROP QUESTION: 10% failure tolerance ------------------")
@@
-            got = solve_risk_for_fail(sc, 0.10, min(a.trials, 20_000), rnd,
-                                      max_days=md)
+            # The 30-day arm is a RETRYABLE $397 seat, not a funded account:
+            # gate it on BLOWING the floor, and report p_pass / E[attempts]
+            # beside it. The <=10% ruin tolerance stays on the no-time-cap /
+            # funded arm (see section 7c and g4_prop_fit.md:40-45).
+            key = "p_blow" if md else "p_fail"
+            got = solve_risk_for_fail(sc, 0.10, min(a.trials, 20_000), rnd,
+                                      max_days=md, metric=key)
```
plus `solve_risk_for_fail(..., metric="p_fail")` and `if r[metric] <= tol`, and
adding `E[attempts] = 1/p_pass` and `E[seat $] = 397/p_pass` to the printed row.
