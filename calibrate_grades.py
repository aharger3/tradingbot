"""Grading calibration from labeled trades.

Positives = signals the bot captured within +/-5 min (same direction) of a
trade Scarface alerted (128 replayable) or Austin charted (2026-07-06, 5).
Negatives = every other capture on those same days (the spray he didn't take).
Extract features per capture, fit a shallow decision tree, print the rules
that separate TAKEN from SPRAY. Writes features to calibration_features.csv
so reruns and follow-up analysis skip the replay.

    python calibrate_grades.py            # build csv (if missing) + fit
    python calibrate_grades.py --refit    # refit from existing csv only
"""
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

from backtest_week import BacktestRunner, SYMBOLS
from replay_scarface import parse_entries, _polygon_day

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CSV = Path("calibration_features.csv")

# Austin's labeled charts, 2026-07-06 (weight as strong evidence, not gospel)
AUSTIN = [
    {"symbol": "META", "day": "2026-07-06", "time": "09:47", "direction": "put", "text": "austin chart"},
    {"symbol": "NVDA", "day": "2026-07-06", "time": "09:50", "direction": "call", "text": "austin chart"},
    {"symbol": "AMD", "day": "2026-07-06", "time": "09:38", "direction": "call", "text": "austin chart"},
    {"symbol": "AMD", "day": "2026-07-06", "time": "09:40", "direction": "call", "text": "austin chart"},
    {"symbol": "GOOGL", "day": "2026-07-06", "time": "09:46", "direction": "put", "text": "austin chart"},
    {"symbol": "TSLA", "day": "2026-07-06", "time": "09:54", "direction": "call", "text": "austin chart"},
]

FEATURES = ["min_since_open", "stop_pct", "dist_nearest_level_pct", "levels_in_2r_path",
            "clear_road", "capture_rank_dir", "body_ratio", "displacement",
            "open_pos_in_pd_range", "with_day_trend", "is_first_5min", "risk_reward_room"]


def _features(candles, i, sig, levels):
    """Feature vector for a capture at bar i (candles[:i+1] known)."""
    c = candles[i]
    entry, stop, d = sig["entry"], sig["stop"], sig["direction"]
    risk = abs(entry - stop) or 1e-9
    target = entry + 2 * risk if d == "call" else entry - 2 * risk
    lv = [l for l in levels if l]
    t = datetime.strptime(c.timestamp[:5], "%H:%M")
    mins = (t - datetime.strptime("09:30", "%H:%M")).seconds / 60
    rngs = [x.high - x.low for x in candles[max(0, i - 20):i + 1]]
    avg_rng = sum(rngs) / len(rngs) or 1e-9
    lo, hi = sorted([entry, target])
    in_path = sum(1 for l in lv if lo < l < hi)
    dist = min((abs(entry - l) / entry for l in lv), default=1.0)
    clear = all(l <= entry for l in lv) if d == "call" else all(l >= entry for l in lv)
    body = abs(c.close - c.open) / ((c.high - c.low) or 1e-9)
    leg = candles[max(0, i - 2):i + 1]
    disp = (max(x.high for x in leg) - min(x.low for x in leg)) / avg_rng
    pdh, pdl = levels[0], levels[1]
    pos = ((candles[0].open - pdl) / (pdh - pdl)) if pdh and pdl and pdh != pdl else 0.5
    day_up = c.close >= candles[0].open
    # room to next level beyond target, in R units (capped 5)
    beyond = [l for l in lv if (l > target if d == "call" else l < target)]
    room = min((abs(l - entry) / risk for l in beyond), default=5.0)
    return [round(mins, 1), round(risk / entry * 100, 3), round(dist * 100, 3), in_path,
            int(clear), 0, round(body, 3), round(disp, 2),
            round(pos, 2), int(day_up == (d == "call")), int(mins <= 5), round(min(room, 5.0), 2)]


def build():
    entries = parse_entries(set(SYMBOLS)) + AUSTIN
    days = {}  # (symbol, day) -> [entries]
    for e in entries:
        days.setdefault((e["symbol"], e["day"]), []).append(e)
    print(f"{len(entries)} labeled entries across {len(days)} symbol-days")

    rows = []
    for n, ((sym, day), labs) in enumerate(sorted(days.items()), 1):
        try:
            got = _polygon_day(sym, day)
        except Exception as ex:
            print(f"[{n}] {sym} {day}: polygon error {ex}")
            continue
        if got is None:
            continue
        candles, pdh, pdl, pmh, pml = got
        runner = BacktestRunner(sym)
        runner.pdh, runner.pdl, runner.pmh, runner.pml = pdh, pdl, pmh, pml
        windows = []
        for e in labs:
            t0 = datetime.strptime(e["time"], "%H:%M")
            windows.append((e["direction"],
                            {(t0 + timedelta(minutes=k)).strftime("%H:%M") for k in range(-5, 6)}))
        orh = max(c.high for c in candles[:5])
        orl = min(c.low for c in candles[:5])
        rank = {"call": 0, "put": 0}
        for i in range(5, len(candles)):
            runner.candles = candles[:i + 1]
            n0 = len(runner.captured)
            runner.detect_signals()
            bar_t = candles[i].timestamp[:5]
            for sig in runner.captured[n0:]:
                levels = [pdh, pdl, pmh, pml, orh, orl]
                f = _features(candles, i, sig, levels)
                rank[sig["direction"]] += 1
                f[5] = rank[sig["direction"]]
                taken = any(d == sig["direction"] and bar_t in w for d, w in windows)
                rows.append([sym, day, bar_t, sig["direction"], sig["grade"], sig["status"],
                             int(taken)] + f)
        print(f"[{n}/{len(days)}] {sym} {day}: {len([r for r in rows if r[0] == sym and r[1] == day])} captures, "
              f"{sum(r[6] for r in rows if r[0] == sym and r[1] == day)} taken")

    with open(CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["symbol", "day", "time", "direction", "bot_grade", "bot_status", "taken"] + FEATURES)
        w.writerows(rows)
    print(f"\nwrote {len(rows)} rows -> {CSV}")


def fit():
    import numpy as np
    from sklearn.tree import DecisionTreeClassifier, export_text
    rows = list(csv.DictReader(open(CSV)))
    X = np.array([[float(r[f]) for f in FEATURES] for r in rows])
    y = np.array([int(r["taken"]) for r in rows])
    print(f"\n{len(y)} captures, {y.sum()} taken ({y.mean():.1%})")

    # how the CURRENT grader treats his trades vs spray
    from collections import Counter
    for lbl, mask in [("TAKEN", y == 1), ("SPRAY", y == 0)]:
        g = Counter(rows[i]["bot_grade"] for i in range(len(rows)) if mask[i])
        s = Counter(rows[i]["bot_status"] for i in range(len(rows)) if mask[i])
        print(f"current grader on {lbl}: grades {dict(g)} status {dict(s)}")

    for depth in (3, 4):
        t = DecisionTreeClassifier(max_depth=depth, class_weight="balanced",
                                   min_samples_leaf=25, random_state=0).fit(X, y)
        print(f"\n=== tree depth {depth} ===")
        print(export_text(t, feature_names=FEATURES))
        imp = sorted(zip(FEATURES, t.feature_importances_), key=lambda x: -x[1])
        print("importances:", [(f, round(v, 3)) for f, v in imp if v > 0.01])
        pred = t.predict(X)
        tp = ((pred == 1) & (y == 1)).sum(); fp = ((pred == 1) & (y == 0)).sum()
        print(f"recall on taken: {tp / max(y.sum(), 1):.1%}  "
              f"precision: {tp / max(tp + fp, 1):.1%}  flags {pred.mean():.1%} of all captures")


if __name__ == "__main__":
    if "--refit" not in sys.argv or not CSV.exists():
        build()
    fit()
