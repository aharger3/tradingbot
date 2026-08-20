# Trend gate vs Austin's day_type labels (T4)

Gate: `research/trend_gate.py :: is_trending(symbol, date, entry_i, side)` — trending = >= 2 of 3 components (index alignment, structure, earliness), computed only from RTH bars at or before `entry_i`. Thresholds documented at the top of that file.

Scoring set: every marked day whose `day_type` is in {trend, chop, range} and which carries a trade mark, evaluated at the day's first (earliest) trade. `trend` -> trending, `chop`/`range` -> not trending, `reversal` and blank day_type are excluded from the agreement count (no directional expectation / no entry to gate on).

Scored days: 7. Agreement: 6/7.

```
gate_vs_austin_agreement: 0.8571
```

## Disagreements (gate != day_type expectation)

| symbol date | side | entry_i | index | structure | earliness |
|---|---|---|---|---|---|
| QQQ 2026-07-14 | S | 38 (10:08) | T(-47.3bps) | T(LH/LL) | F(10:08) |
