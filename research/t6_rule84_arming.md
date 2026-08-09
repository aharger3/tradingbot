# T6 — 84% arming widening (2026-08-09)

Replay of `backtest_week.simulate_day` over the 159 marks' 151 (symbol, day)
pairs, once with the old arming rule (break-and-retest losers only) and once
with the new rule (break-and-retest OR one-candle-rule losers). FVG and flag
losers arm neither. Other 84% config (RULE84_STRICT, RULE84_OFF, RULE84_LESSON)
is held constant, so the delta is the arming widening alone.

armed_84_entries: 0 -> 0
