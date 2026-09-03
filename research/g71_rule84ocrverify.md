# G71 / rule84ocrverify — adversarial re-check of the "accidental 0.2R reclaim tolerance"

**Verdict: NOT REFUTED.** Every element reproduces independently.

Scripts (read-only, no engine file touched):
`research/g71_rule84verify_tol.py`, `research/g71_rule84verify_d.py`.

## What reproduced

| assertion | check | result |
|---|---|---|
| `RULE84_RECLAIM_TOL = None` default | `signal_runner.py:350-351`; import prints `None` | confirmed |
| `_reclaim_tol_ok` is a no-op | `:354-369`; `(999,100,99)` → True, `(-999,100,99)` → True | confirmed |
| ratified unit (25% of prev candle range) unwired | `BAR_EXTREME_FRAC` (`:499`) appears only at `:1272-3`, `:1355`, `:2309` — entry-extreme veto, fill band, S→A demote. Never in the 84% branch (`:2943-2967` long, `:3190-3214` short) | confirmed |
| algebra d ≤ 0.2R | tgt=E+2R, stop_chk=E−R, close=E+d ⇒ 2R−d ≥ 1.5(d+R) ⇒ d ≤ 0.2R. Numeric flip at exactly d=0.2000 | confirmed |
| `stop_chk` really is the original stop | `RULE84_LESSON = True` (`:112`) and `_arm_84` sets `entry_stop = t.stop`, `entry_target = t.target` (`backtest_week.py:470-472`) | confirmed |
| 815 / 1,018 traded BR-long rows at 2.0000 R:R | reproduced exactly | confirmed |
| short mirror identical | `:3204-3206` is the sign-flipped same test ⇒ same 0.2R | confirmed |
| look-ahead | `tgt`/`stop_chk` are the *original* trade's, `close` is the live bar. None | clean |
| branch reachable | 388 detections, 123 traded, mean R −0.0824 | reachable |
| right book | 2,437 traded / 76,019 signals / 500 sessions, `first 2024-08-21 last 2026-08-21` — the current post-T23 book. The 2,595 book no longer exists on disk (`g71_advcapture.md:80`, `g71_sigfireverify.md:19`); the "1,017-trade book" matches nothing. 1,018 is a *subset* (BR ∩ dir=call ∩ traded), not a book | correct book |

## Measured on the correct denominator (the arming pool, not BR-longs)

`traded ∧ out=loss ∧ setup ∈ {BR, OCR}` — n = **1,130**, the rows that actually set
`entry_target`/`entry_stop`:

- planned R:R exactly 2.0000 on **888 / 1,130 = 78.6%**
- implied cap `d_max = (k − 1.5) / 2.5` where k = planned R:R: **min 0.0000, median 0.2000,
  max 0.6000**; exactly 0.2000 on 78.6%; 1 row has `d_max ≤ 0` (rr_ok unpassable)
- symmetric by side: 459/583 calls and 429/547 puts at 2.0000

This is a *sharper* form of the claim, not a contradiction: the cap is 0.2R on 78.6% of arms
and target-ratio-dependent on the rest — i.e. it is manufactured by the target policy, exactly
as claimed, and moves with it.

## Two corrections that do not overturn the claim

1. **Attribution.** The flat-2R target is **P32** (`PHASES.md:139`); **P21** (`:69`) is the
   level-availability prerequisite P32 names. The claim says "when P21 replaces the 2R target".
   Right mechanism, wrong ticket label.
2. **"Binding" is unmeasured.** rr_ok rejections emit no row — all 388 detections are already
   post-rr_ok — and the book carries no reclaim-bar close (`cls` is the asset class, `"stock"`,
   not a price), so the rejection count cannot be recovered from `bt2y_trades.json`. rr_ok is
   the *only* in-force cap on reclaim distance, so it is the operative tolerance by
   construction; how often it fires needs an instrumented replay.

Stale comment at `:344` (*"DO NOT INVENT A NUMBER … until Austin picks one"*) is confirmed
stale: `omen-rulebook.md:723,937` records the pick on 2026-08-28.
