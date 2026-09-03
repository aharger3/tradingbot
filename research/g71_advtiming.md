# G71/adv-timing — adversarial verify of the T12-section-4 swap null

**Verdict: the claim is NOT refuted.** The headline reproduces to 4 decimals on an
independently-computed baseline, and survives every robustness check below.

Scripts (written, not committed): `research/g71_advtiming_swap.py`,
`research/g71_advtiming_split.py`, `research/g71_advtiming_cachecheck.py`,
`research/g71_advtiming_bookeffect.py`. Read-only on every mark file; no engine file edited.

## 1. Reproduction

Baseline is the BOOK's own `r` (`research/bt2y_trades.json`), not `g71_timing.py`'s k=0
re-run, so the two numbers are not the same computation.

| | claim (`g71_timing_out.txt`) | this re-run |
|---|---:|---:|
| support (buildable at all k) | 2401 / 2437 | 2401 / 2437 |
| rows with a takeable earlier candidate | 203 (8.5%) | 203 (8.45%) |
| engine took, mean R | +0.4737 | +0.4737 |
| swapped, mean R | +0.5074 | +0.5074 |
| delta | +0.0337 | +0.0337 |
| 95% boot CI | [−0.3051, +0.3516] | [−0.3159, +0.3577] (own seed, 20k reps) |

Bootstrap is paired on the per-row delta (`g71_timing.py:684-685`) — correctly paired, not
two independent arms.

## 2. Checks that could have broken it, and didn't

- **Right book.** `bt2y_trades.json` meta: 76,019 signals, 2,437 traded, `loss_halt: true`,
  generated 2026-08-29T03:14. `research/t23_stack.md:76` records 2,595 → 2,437 (−158) when
  R31 landed, so this is the current post-T0/post-T23 book, not the 1,017-trade one.
- **Cache fidelity.** `g71_timing_params.json` is validated only on `n_rows`, so a stale
  cache would be silent. 12 random swap rows rebuilt from a live `sim_day` replay:
  0 mismatches on offset/entry/stop/status/grade/sgrade. Every engine file predates the cache.
- **Look-ahead.** None in the blanket arm. Candidate choice is "nearest earlier", no future
  input; the swapped trade carries the candidate's own emitted entry/stop/target
  (`build(..., k=0)` ⇒ translation `d = 0`); scale rung is `max(high for rth[:i+1])`, causal;
  management is the shipped `backtest_week._ladder_bar`.
- **Denominator confound.** Swapped 1R is 0.82x the taken 1R at the median. Re-priced at the
  engine row's position size, the delta is **−0.0790 R [−0.3077, +0.1433]** — still null,
  and the sign flips against the swap.
- **Clustering.** 203 rows sit on 186 symbol-days; day-clustered bootstrap [−0.3106, +0.3441].

## 3. Two real defects in the evidence — neither changes the verdict

1. **60 of the 203 picks (29.6%) are trades the book ALREADY holds** (`status: fired`,
   same sym/day/entry_i/dir). For those a "swap" is not a swap: the engine took both, so the
   policy deletes the later row rather than replacing it. Priced properly, the book-level
   total is **−17.5R, not the report's +6.8R** (143 replaced +8.8R; 60 deleted, forfeiting
   +26.3R already booked). Per trade that is still nothing: 2,437 rows / +0.5495 →
   2,377 rows / +0.5560, **+0.0065 R/trade**.
2. **141 of the 203 picks are `skipped_d` / grade `X`** — the engine graded them D and
   `_route` refused them (`backtest_week.py:634`, floor at `signal_runner.py:2778`). The
   report's §1 sentence *"could legally have taken"* is wrong for 69% of the population;
   the branch needs a grader change, not a clock change. The claim's own wording
   ("the engine already emitted") is accurate.

Splits, all nearest-candidate, paired boot: not-already-traded n=143 +0.0617 [−0.2888,+0.4106];
already-traded n=60 −0.0330; `skipped_d` picks n=141 +0.0854; `fired` picks n=62 −0.0840;
1–2 bars back n=82 +0.1241 [−0.3477,+0.5938]. Every one straddles zero.

The only arms whose CI excludes zero are the S-on-Austin's-ladder ones (n=42 +0.5291
[+0.0453,+1.0671]; n=16 and off ≥ −2, +0.8107 [+0.2933,+1.3887]) — which the claim does not
dispute, because it is scoped to the blanket reading. The blanket average is a mixture that
buries that subgroup; that is a framing limit, not an error.
