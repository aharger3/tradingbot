"""
SPEC6 - Rule 6: Position Management with Breakeven Scaling

Austin 2026-07-10 review: "Mgmt: scale HOD / breakeven at post-entry red OB."
Scarface Trades: "scale 25-50% at HOD/first major level, leave a runner."

What this implements
-------------------
Rule 6 changes the binary exit model (full stop = -$1000, full target = +$2000)
to a two-stage model:
  1. When price reaches breakeven (entry + 1R for calls, entry - 1R for puts):
     close 50% of the position at breakeven (0 P&L on that half)
  2. Move remaining position's stop to breakeven (entry level)
  3. Runner continues to the original 2R target

P&L distribution (50% scale at 1R):
  - Both BE and target hit: 0.5 x 1R + 0.5 x 2R = 1.5R (+$1500 at $1k risk)
  - BE hit then stopped at breakeven: 0.5 x 1R + 0.5 x 0R = 0.5R (+$500)
  - Stop hit before BE: -1R (-$1000) -- same as before

Files Modified
--------------
paper_trader.py -- added RULE6_ENABLED, RULE6_SCALE_PCT, RULE6_BE_MULT module-
  level flags; breakeven-level dataclass fields on PaperPosition; two-stage
  exit_for() logic; PaperBook.mark() handles BE_SCALE events before CLOSE events.

backtest_week.py -- added same Rule 6 flags; be_level/be_taken/runner_stop on
  SimTrade; modified pnl property for multi-stage P&L; modified simulate_day
  bar-walk to check BE before stop/target; added "Rule 6: Breakeven Scale
  Analysis" section to backtest_report.md.

Verification
------------
Toggle RULE6_ENABLED = True/False in backtest_week.py and run:
  python backtest_week.py
to compare baseline vs Rule 6 P&L.

Toggle RULE6_ENABLED = True/False in paper_trader.py for live paper trading:
  python live_scanner.py --once --paper

To compare both variants from scratch:
  python compare_rule6.py
"""
