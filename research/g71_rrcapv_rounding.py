"""Second reachable >2R path in the live sizer: cent-rounding of the premium
legs. With a real Tastytrade mid ((bid+ask)/2 need not land on a cent),
stop_premium and target_premium are each round(...,2) while the R denominator
is the rounded stop, so booked R = (target-entry)/(entry-stop) drifts off rr."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

RR = 2.0
def legs(entry_premium, premium_risk):
    stop = round(max(entry_premium - premium_risk, 0.05), 2)
    tgt = round(entry_premium + RR * premium_risk, 2)
    return stop, tgt, (tgt - entry_premium) / (entry_premium - stop)

hi = lo = None
for mid_c in range(20, 800):           # $0.20 .. $8.00 in half-cent mids
    for half in (0.0, 0.005):
        ep = mid_c / 100.0 + half
        for risk_c in range(5, 300):
            pr = risk_c / 100.0
            if ep - pr < 0.05:
                continue
            s, t, r = legs(ep, pr)
            if hi is None or r > hi[0]:
                hi = (r, ep, pr, s, t)
            if lo is None or r < lo[0]:
                lo = (r, ep, pr, s, t)
print("max booked R from rounding alone: %.4f  (entry $%.3f risk $%.2f -> stop $%.2f tgt $%.2f)" % hi)
print("min booked R from rounding alone: %.4f  (entry $%.3f risk $%.2f -> stop $%.2f tgt $%.2f)" % lo)
