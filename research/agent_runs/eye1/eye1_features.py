"""eye1: signal-time features for the S classifier.

Every feature is computable from 1-min bars at the signal bar (no outcome
columns), so the same code can score a live MNQ/NQ candidate.
"""
import math

# (name, source) - 10 features, all bar-derived
FEATURES = [
    "trig_body_frac",         # trigger candle body / range
    "trig_close_vs_lvl_atr",  # trigger close distance past the level, in ATR
    "trig_rej_wick_frac",     # rejection wick / range
    "disp_atr",               # break displacement, ATR
    "retest_depth_atr",       # retest depth vs level, ATR (neg = through)
    "log_bars_break_to_sig",  # log1p(bars from break to signal)
    "min_after_open",         # minutes after 9:30
    "spy_trend_with",         # 1 if SPY/ES trend agrees with trade side
    "closed_thru",            # 1 if a bar closed back through the level
    "vs_open_atr",            # price vs day open, ATR
]


def featurize(c):
    """Map a candidate dict (s_trades.csv column names) to the feature vector.

    Missing / NaN values come back as None; the model imputes train medians.
    """
    def num(k):
        v = c.get(k)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(v) else v

    b = num("bars_break_to_sig")
    side = str(c.get("side", "")).upper()
    trend = str(c.get("spy_trend", "")).lower()
    if side in ("L", "S") and trend in ("bull", "bear"):
        spy_with = 1.0 if (side == "L") == (trend == "bull") else 0.0
    else:
        spy_with = None
    out = {
        "trig_body_frac": num("trig_body_frac"),
        "trig_close_vs_lvl_atr": num("trig_close_vs_lvl_atr"),
        "trig_rej_wick_frac": num("trig_rej_wick_frac"),
        "disp_atr": num("disp_atr"),
        "retest_depth_atr": num("retest_depth_atr"),
        "log_bars_break_to_sig": None if b is None else math.log1p(max(b, 0.0)),
        "min_after_open": num("min_after_open"),
        "spy_trend_with": spy_with,
        "closed_thru": num("closed_thru"),
        "vs_open_atr": num("vs_open_atr"),
    }
    return [out[f] for f in FEATURES]
