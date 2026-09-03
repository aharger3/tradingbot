# G7.1 `firstsverify` — adversarial verify of the `firsts` sgrade-S claim

**Verdict: REFUTED.** The arithmetic reproduces byte-for-byte; the two load-bearing
words do not. "Only" is false, and "significant" survives exactly one of the four
ways it can be cut.

Script: `research/g71_firstsverify_sgrade.py` (reads `research/bt2y_trades.json`, writes nothing).

## What reproduces

`python research/g71_firsts_isfirstspecial.py` reprints the claim's numbers exactly:
sgrade S n=426 +0.2721R (se 0.0827), A n=728 +0.5517, C n=2140 +0.5335;
S − non-S = −0.2659R, se 0.0924, t −2.88. Decided win rates 46.8 / 48.0 / 46.3 — flat,
as claimed; mean winner +1.687 (S) vs +2.173 (A) / +2.266 (C). The effect is payoff size.

**Book identity is fine.** `research/bt2y_trades.json` meta: 76,019 signals, 2,437 traded,
857 halted, `loss_halt: true`, 500 sessions, generated 2026-08-29 03:14. That is the
current post-T23 book (`145d564e`). The prompt's "2,595" is the *superseded* T0 book —
`research/g71_ddverify.md:33`, `research/g71_advscanners.md:89`. No wrong-book error.

## Refutation 1 — "the ONLY available S proxy" is false

`predicates.py:336 is_s_gate` is a second S proxy, fit directly from Austin's S/A/X
verdicts and **pre-registered before any backtest** (`research/s_gate_spec.md`,
`accept <=> displacement >= 0.888`, chosen as the one feature holding sign on both the
S/X and S/A contrasts). It is reachable — `signal_runner.py:2498`
`if S_GATE and sig["grade"] in ("A+","A","B") and not is_s_gate(...)` — behind the
default-off flag at `signal_runner.py:380`, the same convention as
`BNR_DISPLACEMENT_GATE`. Flag-gated is not unavailable.

Its stand-in in the book (`"no_displacement" not in row["downgrades"]`) reads
**+0.4811R in vs +0.5234R out, diff −0.0423R, t −0.57** — flat, not anti-predictive.
So the claim's own premise ("the only proxy is anti-predictive, therefore the restriction
cannot be honestly run") fails at both halves.

## Refutation 2 — the significance is an artefact of the ninth downgrade variable

`downgrade.py:499-501`: R22 `chase` became a downgrade variable on **2026-08-29** — the
same day this book was generated — and `enable_chase` "defaults ON… pass False to
reproduce the eight-variable ladder **every sgrade number before 2026-08-29 was measured
on**". Recomputing the ladder without `chase` on the identical rows:

| S definition | n_S | mean S | mean non-S | diff | naive se | t |
|---|---:|---:|---:|---:|---:|---:|
| 9-var, chase ON (claim's) | 426 | +0.2721 | +0.5381 | **−0.2659** | 0.0924 | **−2.88** |
| 8-var, chase OFF (pre-R22) | 563 | +0.4156 | +0.5218 | −0.1062 | 0.0864 | **−1.23** |
| zero downgrades tripped, raw | 54 | +0.4236 | +0.5050 | −0.0814 | 0.2072 | −0.39 |

137 rows are S under the eight-variable ladder and not under the nine. The claim is not a
statement about "the S proxy"; it is a statement about `chase`, one day old.

## Refutation 3 — significance needs 857 trades that were never taken

The prior agent's row filter is `(fired and traded) or status == "halted"` — 3,294 rows.
The 857 halted rows are candidates **R31 blocked** (`loss_halt.py`: two consecutive
closed losses ends the day); they were never entered and carry no P&L. They are 26% of
the sample and they do the significance lifting. Cluster bootstrap (4,000 draws,
resampling whole clusters):

| row set | N | S − non-S | day-clustered 95% CI | |
|---|---:|---:|---|---|
| prior agent's (fired+traded ∪ halted) | 3,294 | −0.2659 | [−0.4505, −0.0730] | SIG |
| **traded only — the money book** | **2,437** | **−0.2219** | **[−0.4444, +0.0029]** | **NOT SIG** |
| halted only (never taken) | 857 | −0.3452 | [−0.6924, +0.0192] | NOT SIG |

Clustering by symbol or by symbol-day gives the same picture (traded-only:
[−0.4890, +0.0385] and [−0.4397, +0.0011]). On the book that actually made money the
effect does not clear its own error bar.

## Refutation 4 — not significant on 73% of the book, and fat-tail fragile

Within-setup (controls the mix; S is 58% B&R vs 78% for C):

| setup | S | non-S | diff | t |
|---|---|---|---:|---:|
| break_and_retest (2,403 rows, 73%) | n=247 +0.3529 | n=2156 +0.5595 | −0.2066 | **−1.93** |
| one_candle_rule (570) | n=144 +0.1956 | n=426 +0.7111 | −0.5155 | −2.29 |
| reentry_84_rule (321) | n=35 +0.0168 | n=286 +0.1189 | −0.1021 | −0.34 |

And it lives in a tail the S arm is too small to sample: max R is +11.80 (S) against
+24.35 (C). Trimming the top winners in each arm symmetrically —
0.5% → −0.2466, 1% → −0.2342, 2% → −0.2077, 5% → −0.1685 — bleeds 37% of the effect by
dropping 21 S and 143 non-S rows.

## Look-ahead: none found

`downgrade.score(bars, i, level, is_long, …)` (`research/downgrade.py:475`) is bounded at
bar `i`; `sequence_gate`'s `entry_seq` is documented causal at `downgrade.py:~100`
("only ever counts entries with an EARLIER bar index"), and it is OFF by default. The
attach point `backtest_2y.py:152` passes `t.entry_idx` and `t.stop`. Look-ahead would
push the proxy toward *predictive*, not away, so it is not the explanation either way.

## What survives

Only the weak form: **the downgrade-ladder S proxy is not demonstrated to be predictive**
(diff −0.11R, t −1.23 on the pre-R22 ladder; −0.22R with a CI touching zero on the traded
book). "Significantly ANTI-predictive" and "the only available S proxy" are both wrong,
and P5's numbers cannot be dismissed as "measuring the broken proxy" on this evidence.
