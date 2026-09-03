"""g71 adversarial verify of the 'capture' T11 claim. Read-only, synthetic."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import stop_rule, signal_runner as sr

print("BNR_STOP_MODE =", sr.BNR_STOP_MODE)
print("DISASTER_STOP_R =", stop_rule.DISASTER_STOP_R, " MAX_LOSS_R =", stop_rule.MAX_LOSS_R)

# Identity: at stop_r = 1.0 the resting order IS the stop price, for ANY stop
# placement -- risk is defined as abs(entry-stop), so the mode cannot matter.
cases = [(100.50, 100.00, True, "level-mode B&R (t11 fixture)"),
         (100.50,  99.87, True, "buffer-mode stop, 0.63 risk"),
         (100.50,  99.60, True, "retest-candle-low stop"),
         ( 99.50, 100.00, False, "short, level"),
         ( 99.50, 100.40, False, "short, wide")]
for entry, stop, long, note in cases:
    risk = abs(entry - stop)
    px = stop_rule.disaster_stop_price(entry, risk, long, stop_rule.DISASTER_STOP_R)
    print("  %-32s entry %.2f stop %.2f -> disaster %.4f  equal=%s"
          % (note, entry, stop, px, abs(px - stop) < 1e-9))

# Can a close-triggered stop ever book worse than -1.0R while the stop is
# unmoved?  disaster_stop_hit is low<=px (long): any bar whose CLOSE is past the
# stop necessarily has low <= close <= px, so the disaster fires first, always.
print("\nreachability of the -1.25R floor on the unmoved-stop path:")
for r_past in (1.001, 1.1, 1.6, 4.0, 40.0):
    entry, stop, risk = 100.50, 100.00, 0.50
    close = entry - r_past * risk
    px = stop_rule.disaster_stop_price(entry, risk, True, 1.0)
    hit = stop_rule.disaster_stop_hit(high=entry, low=close, price=px, long=True)
    booked = (px - entry) / risk if hit else (stop_rule.stop_fill_price(close, entry, risk, True) - entry) / risk
    print("   close %.2fR past -> disaster_hit=%s booked %+.4fR" % (r_past, hit, booked))
