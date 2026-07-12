"""Self-check for detect_break_retest against Austin's flagged hallucinations.
Run: python test_break_retest.py"""
from omen_bot import Candle, detect_break_retest


def C(o, h, l, c):
    return Candle("09:40:00", o, h, l, c, 1000)


L = 100.0  # test level

# --- LONG cases ---
# VALID: below -> break up -> leave (low>100) -> come back (low<=100) -> confirm close up
valid_long = [C(99.0, 99.3, 98.8, 99.1), C(99.1, 99.4, 99.0, 99.2),   # below
              C(99.2, 100.4, 99.1, 100.3),                            # BREAK (close>100)
              C(100.3, 100.9, 100.2, 100.7),                          # LEAVE (low>100)
              C(100.7, 100.8, 99.7, 100.05),                          # RETEST (low<=100)
              C(100.05, 100.9, 100.0, 100.6)]                         # CONFIRM close up
assert detect_break_retest(valid_long, L, True), "valid long should fire"

# 08-08 hallucination: break up, LEAVE, but never comes back (no retest)
no_return = [C(99.0, 99.3, 98.8, 99.1), C(99.2, 100.4, 99.1, 100.3),  # break
             C(100.3, 100.9, 100.2, 100.7), C(100.7, 101.3, 100.6, 101.1),
             C(101.1, 101.6, 101.0, 101.4), C(101.4, 101.8, 101.2, 101.6)]  # never back to 100
assert detect_break_retest(no_return, L, True) is None, "no-retest must NOT fire"

# 08-04 chop: oscillates ON the level, no clean leave
chop = [C(100.0, 100.2, 99.8, 100.05), C(100.05, 100.2, 99.9, 99.98),
        C(99.98, 100.15, 99.85, 100.05), C(100.05, 100.2, 99.9, 99.97),
        C(99.97, 100.18, 99.88, 100.06), C(100.06, 100.2, 99.9, 100.04)]
assert detect_break_retest(chop, L, True) is None, "chop-on-level must NOT fire"

# drift: always above, no break event in window
drift = [C(101.0, 101.5, 100.8, 101.2)] * 5 + [C(101.2, 101.6, 101.0, 101.4)]
assert detect_break_retest(drift, L, True) is None, "all-day drift must NOT fire"

# --- SHORT cases ---
# 07-09 hallucination: breaks below, leaves, never comes back up to retest
short_no_return = [C(101.0, 101.2, 100.7, 100.9), C(100.8, 100.9, 99.6, 99.7),  # break down
                   C(99.7, 99.9, 99.2, 99.4), C(99.4, 99.6, 98.9, 99.1),
                   C(99.1, 99.3, 98.7, 98.9), C(98.9, 99.1, 98.5, 98.7)]  # never back to 100
assert detect_break_retest(short_no_return, L, False) is None, "short no-retest must NOT fire"

# VALID short: above -> break down -> leave (high<100) -> back up (high>=100) -> confirm down
valid_short = [C(101.0, 101.2, 100.7, 100.9), C(100.9, 101.0, 99.6, 99.7),   # break
               C(99.7, 99.9, 99.2, 99.4),                                    # leave (high<100)
               C(99.4, 100.3, 99.3, 99.95),                                  # retest (high>=100)
               C(99.95, 100.1, 99.4, 99.6)]                                  # confirm down
assert detect_break_retest(valid_short, L, False), "valid short should fire"

# --- 2026-07-10 review rules ---
# 11-04: break candle closes AT/hair-above the level = no clear break (eps buffer)
marginal = [C(99.0, 99.3, 98.8, 99.1), C(99.1, 99.4, 99.0, 99.2),
            C(99.2, 100.05, 99.1, 100.01),                        # "break" by a hair
            C(100.01, 100.4, 100.02, 100.3),                      # "leave" barely above
            C(100.3, 100.4, 99.7, 100.05),
            C(100.05, 100.9, 100.0, 100.6)]
assert detect_break_retest(marginal, L, True) is None, "hair-break must NOT fire"

# 07-30/10-09: short entry candle with long lower wick = buyers fighting back
wick_short = valid_short[:-1] + [C(99.95, 100.0, 98.8, 99.7)]     # lower wick 0.9 vs body 0.25
assert detect_break_retest(wick_short, L, False) is None, "adverse-wick entry must NOT fire"

# 07-30/10-08/11-06: level broken earlier in session -> LATE tag (kept, downgraded)
early_chop = [C(99.8, 100.3, 99.6, 100.2), C(100.2, 100.4, 99.5, 99.7)]  # earlier break+fail
late_entry = early_chop * 4 + valid_long                          # pad so window excludes chop
note = detect_break_retest(late_entry, L, True, window=6)
assert note and "LATE" in note, f"prior-break session must tag LATE, got {note!r}"
clean_note = detect_break_retest(valid_long, L, True)
assert clean_note and "LATE" not in clean_note, "clean first break must not tag LATE"

print("all break-retest checks passed")
