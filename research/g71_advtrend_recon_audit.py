"""Strict audit of the arrival_first reconstruction used by
research/g71_advtrend_livegap_verify.py, plus the entry-price variant of the
consequence count. Fired rows only, current 2,437-trade book."""
from __future__ import annotations
import csv, json, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(os.path.dirname(HERE), "data_archive")
FLOOR = "floor B: first with-trend signal of the day"


def bars(sym, day):
    p = os.path.join(ARCHIVE, sym, "%s.csv" % day)
    if not os.path.exists(p):
        return None
    o, c = {}, {}
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            h = row["Datetime"][11:16]
            if "09:30" <= h < "16:00":
                o[h], c[h] = float(row["Open"]), float(row["Close"])
    return (o, c) if o else None


def main():
    book = json.load(open(os.path.join(HERE, "bt2y_trades.json"), encoding="utf-8"))
    fired = sorted((r for r in book["trades"] if r.get("status") == "fired"),
                   key=lambda r: (r["sym"], r["day"], r["et"], r.get("seq", 0)))
    seen, cache, a = set(), {}, Counter()
    for r in fired:
        k = (r["sym"], r["day"])
        cache.setdefault(k, bars(*k))
        o, c = cache[k]
        fk = (r["sym"], r["day"], r["dir"])
        first = fk not in seen
        seen.add(fk)
        m = int(r["et"][:2]) * 60 + int(r["et"][3:])
        d0, ref = o["09:30"], o["%02d:%02d" % (max(570, m - 60) // 60, max(570, m - 60) % 60)]
        has_floor = FLOOR in r["reason"]
        for lab, px in (("entry", r["entry"]), ("close", c[r["et"]])):
            wb = (px >= d0) == (r["dir"] == "call")
            wl = (px >= ref) == (r["dir"] == "call")
            ab, al = wb and first, wl and first          # 0<=mins<=90 always true (max et 10:59)
            if lab == "close":
                if has_floor and not ab:
                    a["recon_FLOOR_but_not_arrival"] += 1
                if (not has_floor) and ab and r["grade"] == "C":
                    a["recon_arrival_but_C"] += 1
            if has_floor and ab and not al:
                a[lab + "_LOSES"] += 1
            if r["grade"] == "C" and al and not ab:
                a[lab + "_GAINS"] += 1
    for k in sorted(a):
        print("%-28s %d" % (k, a[k]))


if __name__ == "__main__":
    main()
