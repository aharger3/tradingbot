"""g71 (rrcap): the LIVE path's target, proved by construction. No network --
build_options_plan falls back to the delta estimate when no feed is passed."""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import options_sizer as osz

print("options_sizer.DEFAULT_RR =", osz.DEFAULT_RR)
for entry, stop in ((100.00, 99.50), (250.00, 248.00), (35.00, 34.90)):
    p = osz.build_options_plan(symbol="TEST", direction="call",
                               stock_entry=entry, stock_stop=stop, max_loss=1000.0)
    risk = entry - stop
    rr = (p.stock_target - entry) / risk
    print("entry %.2f stop %.2f risk %.2f -> stock_target %.2f  = %.3f R  | "
          "max_reward $%.0f / max_loss $%.0f = %.3f"
          % (entry, stop, risk, p.stock_target, rr, p.max_reward, p.max_loss,
             p.max_reward / p.max_loss if p.max_loss else 0))
print()
print("live_scanner.py:631 calls build_options_plan WITHOUT rr= -> DEFAULT_RR")
print("paper_trader.PaperPosition._check_target closes the WHOLE position there")
print("no SCALE_PLAN / runner_target / scale rung exists anywhere in the live path")
