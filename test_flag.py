"""Self-check for detect_flag_setup. Run: python test_flag.py"""
from omen_bot import Candle, detect_flag_setup


def C(o, h, l, c):
    return Candle("09:40:00", o, h, l, c, 1000)


# Bull flag: 5-bar pole 100->101 (1%), 3-bar tight pause near 101, breakout up.
pole = [C(100.0, 100.25, 99.95, 100.2), C(100.2, 100.45, 100.15, 100.4),
        C(100.4, 100.65, 100.35, 100.6), C(100.6, 100.85, 100.55, 100.8),
        C(100.8, 101.05, 100.75, 101.0)]
flag = [C(101.0, 101.1, 100.9, 100.95), C(100.95, 101.08, 100.9, 101.0),
        C(101.0, 101.1, 100.92, 101.05)]
breakout = C(101.05, 101.4, 101.0, 101.3)
bull = pole + flag + [breakout]

info, note = detect_flag_setup(bull, "bullish")
assert info is not None, f"bull flag should fire, got: {note}"
assert info["flag_hi"] < breakout.close, "breakout must close above flag high"
print("bull flag fires:", note)

# Chop: flat throughout (no pole anywhere), tiny up-close last bar -> no fire.
chop = [C(100.0, 100.08, 99.92, 100.0)] * 8 + [C(100.0, 100.09, 99.95, 100.05)]
info2, note2 = detect_flag_setup(chop, "bullish")
assert info2 is None, f"chop should NOT fire, got: {note2}"
print("chop rejected:", note2)

# Bull flag fed to bearish detector -> no fire.
info3, _ = detect_flag_setup(bull, "bearish")
assert info3 is None, "bull flag must not fire as bear flag"
print("direction guard OK")

print("all flag checks passed")
