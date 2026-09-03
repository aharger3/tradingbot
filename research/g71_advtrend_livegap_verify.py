"""ADVERSARIAL VERIFY of the g71/trend claim: with_trend live vs backtest.

Independent re-measure on research/bt2y_trades.json (2,437 traded / 3,487 fired,
generated 2026-08-29T03:14 -- the CURRENT book, which supersedes the 2,595 T0 book).

Adds what the original (research/g71_trend_livegap.py) did not measure:
  * uses the entry BAR CLOSE from data_archive as candles[-1].close, not the
    entry fill price, and reports both;
  * scores CONSEQUENCE, not just predicate flips: with COUNTER_TREND_CAP=0
    (signal_runner.py:183 default) `with_trend` reaches a grade only through
    `arrival_first` (signal_runner.py:2026), which is gated on 0 <= mins <= 90.
"""
from __future__ import annotations
import csv, json, os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVE = os.path.join(ROOT, "data_archive")
BOOK = os.path.join(HERE, "bt2y_trades.json")
FLOOR = "floor B: first with-trend signal of the day"


def bars(sym, day):
    p = os.path.join(ARCHIVE, sym, "%s.csv" % day)
    if not os.path.exists(p):
        return None
    o, c = {}, {}
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hhmm = row["Datetime"][11:16]
            if "09:30" <= hhmm < "16:00":
                o[hhmm] = float(row["Open"])
                c[hhmm] = float(row["Close"])
    return (o, c) if o else None


def hhmm(m):
    return "%02d:%02d" % (m // 60, m % 60)


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    fired = [r for r in book["trades"] if r.get("status") == "fired"]
    fired.sort(key=lambda r: (r["sym"], r["day"], r["et"], r.get("seq", 0)))
    seen = set()
    cache = {}
    tally = Counter()
    cons = Counter()
    for r in fired:
        k = (r["sym"], r["day"])
        if k not in cache:
            cache[k] = bars(*k)
        b = cache[k]
        fk = (r["sym"], r["day"], r["dir"])
        first = fk not in seen
        seen.add(fk)
        if not b:
            tally["no_bars"] += 1
            continue
        o, c = b
        m = int(r["et"][:2]) * 60 + int(r["et"][3:])
        mins = m - 570
        ref = o.get(hhmm(max(570, m - 60)))
        d0 = o.get("09:30")
        if ref is None or d0 is None:
            tally["no_bars"] += 1
            continue
        for label, px in (("entry", r["entry"]), ("close", c.get(r["et"]))):
            if px is None:
                continue
            wb = (px >= d0) == (r["dir"] == "call")
            wl = (px >= ref) == (r["dir"] == "call")
            tally["%s_%s" % (label, "flip" if wb != wl else "same")] += 1
            if r.get("traded"):
                tally["%s_traded_%s" % (label, "flip" if wb != wl else "same")] += 1
            if label != "close":
                continue
            ab = wb and first and 0 <= mins <= 90
            al = wl and first and 0 <= mins <= 90
            has_floor = FLOOR in r["reason"]
            cons["recon_ok" if ab == has_floor or r["grade"] != "B" or not has_floor
                 else "recon_mismatch"] += 1
            if has_floor and ab and not al:
                cons["LOSES_trade"] += 1
            if r["grade"] == "C" and al and not ab:
                cons["GAINS_trade"] += 1
            if wb != wl:
                cons["flip_inside_90" if 0 <= mins <= 90 else "flip_outside_90"] += 1
                cons["flip_first" if first else "flip_notfirst"] += 1
    print("fired rows: %d   (%d without bars)" % (len(fired), tally["no_bars"]))
    for lab in ("entry", "close"):
        f, s = tally[lab + "_flip"], tally[lab + "_same"]
        tf, ts = tally[lab + "_traded_flip"], tally[lab + "_traded_same"]
        print("  px=%-5s  fired flips %4d/%d = %.1f%%   traded flips %3d/%d = %.1f%%"
              % (lab, f, f + s, 100 * f / (f + s), tf, tf + ts, 100 * tf / (tf + ts)))
    print("consequence (px = entry-bar close, COUNTER_TREND_CAP=0 default):")
    for k in ("flip_inside_90", "flip_outside_90", "flip_first", "flip_notfirst",
              "LOSES_trade", "GAINS_trade", "recon_mismatch"):
        print("   %-16s %d" % (k, cons[k]))


if __name__ == "__main__":
    main()
