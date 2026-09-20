# R4 — step-7/10 11% gap: closed, cause = LOSS_HALT

**Verdict: LOSS_HALT confirmed as the cause** — the gap closes to <1% once its
blocked trades are excluded from the comparison population.

## The gap, recomputed
- `research/tape/reconcile_fwd_4_switch_fill_close.json.gz`, windowed to
  bt2y's own `2024-09-03..2026-09-02`: 14,647 rows, **−$748.67/day** (doc's
  cited −$750.17, same order).
- `research/bt2y_trades_retest_on.json`, `status=='fired'` any grade / 498
  sessions: **−$675.25/day** (matches g211's cited figure exactly).
- Gap = 10.9%, matching the doc's cited "11.1%".

## LOSS_HALT is live in one book, absent from the other
- `bt2y_trades_retest_on.json` meta: `loss_halt: true, halted: 4205` (of
  127,152 signals), applied by `backtest_2y.py:334` (`loss_halt.apply_to_book`),
  flipping blocked rows to `status="halted"`.
- `research/g211_reconcile_ladder.py` never imports/calls `loss_halt` in its
  sim path (grep: only hits are report prose reading `retest_meta['halted']`)
  — its books keep every fired trade, halted or not.

## Direct trade match
Key-matched bt2y's 4,205 halted rows against fwd4's windowed population by
`(sym, day, entry-time-to-the-minute)`: **3,535/4,205 (84%) match exactly**,
pnl −$33,818. Removing those 3,535 rows leaves 11,112 rows, **−$680.76/day —
0.8% from bt2y's −$675.25**, inside the 1% bar g211 uses elsewhere.

## Residual (noise, not a second cause)
670 unmatched halted rows + 491/591 missing/extra fwd4 sym-days — consistent
with already-disclosed build/commit drift and C-grade/correlation mismatches
g211 documents elsewhere; doesn't move $/day beyond the 0.8% residual.
## Reproduce
```python
fwd4 = json.load(gzip.open('research/tape/reconcile_fwd_4_switch_fill_close.json.gz'))['trades']
w = [r for r in fwd4 if '2024-09-03' <= r['day'] <= '2026-09-02']
bt = json.load(open('research/bt2y_trades_retest_on.json'))['trades']
halted = {(r['sym'], r['day'], r['et'][:5]) for r in bt if r['status']=='halted'}
kept = [r for r in w if (r['sym'], r['day'], r['entry_time'][:5]) not in halted]
print(sum(r['pnl'] for r in kept)/498)  # -680.76
```
