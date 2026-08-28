#!/usr/bin/env python3
"""X12: the OMEN 2-year book measured the way Scarface and Jdub report themselves --
per WEEK and per DAY, not only per trade and per month. Plus two mean-R levers that
are not scale-in: selective sizing by sgrade, and tail concentration.

Substrate: research/g3_arm_ow1.json (shipped 2-year book, ON_WATCH=1).
Read-only. Usage: python research/x12_weekly_durability.py
"""
import json, os, sys, datetime, collections, statistics

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, "research", "g3_arm_ow1.json")


def load():
    with open(BOOK, encoding="utf-8") as f:
        d = json.load(f)
    return d["meta"], [t for t in d["trades"] if t.get("traded")]


def iso_week(day):
    y, m, dd = (int(x) for x in day.split("-"))
    iy, iw, _ = datetime.date(y, m, dd).isocalendar()
    return "%04d-W%02d" % (iy, iw)


def bucket_report(rows, keyfn, label):
    b = collections.defaultdict(list)
    for t in rows:
        b[keyfn(t["day"])].append(t["r"])
    tot = len(b)
    green = sum(1 for k in b if sum(b[k]) > 0)
    flat = sum(1 for k in b if abs(sum(b[k])) < 1e-9)
    red = tot - green - flat
    worst = min(((sum(v), k) for k, v in b.items()))
    print("%-8s buckets=%d  green=%d (%.1f%%)  red=%d  flat=%d  worst=%s %+.2fR"
          % (label, tot, green, 100.0 * green / tot, red, flat, worst[1], worst[0]))
    return b, green, tot


def main():
    meta, tr = load()
    n = len(tr)
    wins = sum(1 for t in tr if t["out"] == "win")
    rs = [t["r"] for t in tr]
    mean = sum(rs) / n
    print("BOOK  %s..%s  sessions=%d  traded=%d" % (meta["first"], meta["last"],
                                                    meta["sessions"], n))
    print("per-trade: WR %.1f%% (%d/%d)   mean R %+.4f   total %+.1fR"
          % (100.0 * wins / n, wins, n, mean, sum(rs)))
    print("outcomes:", dict(collections.Counter(t["out"] for t in tr)))
    print()

    print("--- DURABILITY, three grains ---")
    wk, wg, wt = bucket_report(tr, iso_week, "WEEK")
    dy, dg, dt = bucket_report(tr, lambda d: d, "DAY")
    mo, mg, mt = bucket_report(tr, lambda d: d[:7], "MONTH")
    print()

    # how Scarface reports: green DAY rate, and best/worst month by green-day rate
    print("--- DAILY WIN RATE (the number Scarface quotes) ---")
    print("green days %d of %d traded days = %.1f%%" % (dg, dt, 100.0 * dg / dt))
    bym = collections.defaultdict(lambda: [0, 0])
    for day, v in dy.items():
        bym[day[:7]][1] += 1
        if sum(v) > 0:
            bym[day[:7]][0] += 1
    rates = sorted(((100.0 * g / t, m, g, t) for m, (g, t) in bym.items()))
    print("worst month by green-day rate: %s %d/%d = %.0f%%" % (rates[0][1], rates[0][2], rates[0][3], rates[0][0]))
    print("best  month by green-day rate: %s %d/%d = %.0f%%" % (rates[-1][1], rates[-1][2], rates[-1][3], rates[-1][0]))
    print("months at 100%% green days: %d of %d" % (sum(1 for r in rates if r[0] >= 100.0), len(rates)))
    print()

    # tail concentration -- Scarface: "trailers made 3x more than original scale"
    print("--- TAIL CONCENTRATION (is the book's R already runner-shaped?) ---")
    srt = sorted(rs, reverse=True)
    total = sum(srt)
    for pct in (1, 5, 10, 20):
        k = max(1, int(round(n * pct / 100.0)))
        print("top %2d%% of trades (n=%3d) carry %+7.1fR = %5.1f%% of total %+.1fR"
              % (pct, k, sum(srt[:k]), 100.0 * sum(srt[:k]) / total, total))
    print("best trade %+.2fR   worst %+.2fR   median %+.3fR"
          % (srt[0], srt[-1], statistics.median(rs)))
    winrs = [r for r in rs if r > 0]
    losrs = [r for r in rs if r <= 0]
    print("avg win %+.3fR (n=%d)  avg loss %+.3fR (n=%d)  win/loss size ratio %.2f"
          % (sum(winrs) / len(winrs), len(winrs), sum(losrs) / len(losrs), len(losrs),
             abs((sum(winrs) / len(winrs)) / (sum(losrs) / len(losrs)))))
    print()

    # selective sizing -- a mean-R lever that is NOT scale-in
    print("--- SELECTIVE SIZING by Austin's sgrade (risk-weighted mean R) ---")
    bg = collections.defaultdict(list)
    for t in tr:
        bg[t.get("sgrade")].append(t["r"])
    for g in ("S", "A", "C", "none", None):
        if g in bg:
            v = bg[g]
            w = sum(1 for x in v if x > 0)
            print("  sgrade %-5s n=%4d  WR %5.1f%%  mean %+0.4fR  total %+8.1fR"
                  % (g, len(v), 100.0 * w / len(v), sum(v) / len(v), sum(v)))
    print()
    schemes = {
        "flat 1x (shipped)":      {"S": 1.0, "A": 1.0, "C": 1.0, "none": 1.0},
        "S2 A1 C.5 none.5":       {"S": 2.0, "A": 1.0, "C": 0.5, "none": 0.5},
        "S2 A1 C0 none0":         {"S": 2.0, "A": 1.0, "C": 0.0, "none": 0.0},
        "S3 A1 C0 none0":         {"S": 3.0, "A": 1.0, "C": 0.0, "none": 0.0},
        "S1 A1 C0 none0 (filter)":{"S": 1.0, "A": 1.0, "C": 0.0, "none": 0.0},
    }
    base = None
    for name, w in schemes.items():
        num = sum(w.get(t.get("sgrade"), 0.0) * t["r"] for t in tr)
        den = sum(w.get(t.get("sgrade"), 0.0) for t in tr)
        if den == 0:
            continue
        m = num / den
        if base is None:
            base = m
        print("  %-26s mean R per unit risk %+0.4f   delta %+0.4f   risk units %.0f"
              % (name, m, m - base, den))
    print("  (standing A/B error bar on this book: +/-0.0095R)")


if __name__ == "__main__":
    main()
