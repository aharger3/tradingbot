"""ADVERSARIAL VERIFY of research/g71_drawdown_concurrency.py.

Re-derives max concurrency, worst-case open risk and intraday excursion
counts from research/bt2y_trades.json, and separates BOOK ROWS from
DISTINCT POSITIONS (same sym+day+minute fired off different named levels
is one trade in an account, N rows in the book).

Read-only. No engine file touched.
"""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def mins(et):
    h, m = et.split(":")
    return int(h) * 60 + int(m)


def conc(rows_by_day, keyfn):
    best, bday, bmin = 0, None, None
    hist = Counter()
    for day, rows in rows_by_day.items():
        span = defaultdict(set)
        for t in rows:
            a = mins(t["et"])
            b = a + max(1, int(t.get("bars") or 1))
            for m in range(a, b):
                span[m].add(keyfn(t))
        for m, s in span.items():
            n = len(s)
            hist[n] += 1
            if n > best:
                best, bday, bmin = n, day, m
    return best, bday, bmin, hist


def main():
    d = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
    meta = d["meta"]
    tr = [t for t in d["trades"] if t.get("traded")]
    print("book meta: traded=%d sessions=%d loss_halt=%s halted=%s"
          % (meta["traded"], meta["sessions"], meta.get("loss_halt"), meta.get("halted")))
    print("traded rows recounted: %d" % len(tr))

    byday = defaultdict(list)
    for t in tr:
        byday[t["day"]].append(t)
    print("days with >=1 traded row: %d  (meta sessions %d)" % (len(byday), meta["sessions"]))

    # ---- duplicate census -------------------------------------------------
    k = Counter((t["day"], t["sym"], t["et"], t["dir"]) for t in tr)
    dup_rows = sum(v - 1 for v in k.values() if v > 1)
    exact = Counter((t["day"], t["sym"], t["et"], t["entry"], t["stop"],
                     t["target"], t["exit"], t["bars"]) for t in tr)
    exact_dupes = sum(v - 1 for v in exact.values() if v > 1)
    print("\nDUPLICATE CENSUS over %d traded rows" % len(tr))
    print("  (day,sym,et,dir) groups: %d   surplus rows: %d (%.1f%% of book)"
          % (len(k), dup_rows, 100 * dup_rows / len(tr)))
    print("  byte-identical (entry,stop,target,exit,bars) surplus rows: %d (%.1f%%)"
          % (exact_dupes, 100 * exact_dupes / len(tr)))

    # ---- concurrency, three definitions -----------------------------------
    for name, fn in (("BOOK ROWS  (claim's definition)", lambda t: id(t)),
                     ("distinct SYMBOL+dir", lambda t: (t["sym"], t["dir"])),
                     ("distinct SYMBOL", lambda t: t["sym"])):
        b, bd, bm, hist = conc(byday, fn)
        print("\nmax concurrent %-32s : %2d  (%s %02d:%02d ET)"
              % (name, b, bd, bm // 60, bm % 60))
        print("  worst-case open risk at floor: %.2fR" % (1.25 * b))
        tot = sum(hist.values())
        big = sum(hist[n] for n in hist if n >= 6)
        print("  minutes with >=6 open: %d / %d (%.2f%%)" % (big, tot, 100 * big / tot))

    # ---- 2025-08-22 10:03 forensics ---------------------------------------
    day = [t for t in tr if t["day"] == "2025-08-22"]
    m = 10 * 60 + 3
    op = [t for t in day if mins(t["et"]) <= m < mins(t["et"]) + max(1, int(t["bars"] or 1))]
    syms = Counter(t["sym"] for t in op)
    print("\n2025-08-22 10:03 ET: %d book rows open across %d distinct symbols"
          % (len(op), len(syms)))
    print("  per-symbol row counts: %s" % dict(sorted(syms.items())))
    print("  outcome of those rows: %s" % dict(Counter(t["out"] for t in op)))
    print("  sum realised R of those rows: %+.2fR" % sum(t["r"] for t in op))

    # ---- intraday excursion, both denominators ----------------------------
    def excursions(keydedupe):
        out = {}
        for day_, rows in byday.items():
            if keydedupe:
                seen, keep = set(), []
                for t in sorted(rows, key=lambda x: (mins(x["et"]), -abs(x["r"]))):
                    kk = (t["sym"], t["et"], t["dir"])
                    if kk in seen:
                        continue
                    seen.add(kk)
                    keep.append(t)
                rows = keep
            seq = sorted(rows, key=lambda t: mins(t["et"]) + max(1, int(t.get("bars") or 1)))
            run = lo = 0.0
            for t in seq:
                run += t["r"]
                lo = min(lo, run)
            out[day_] = lo
        return out

    for lbl, dedupe in (("book rows", False), ("sym-deduped", True)):
        ex = excursions(dedupe)
        for thr in (3.0, 4.0):
            c = sum(1 for v in ex.values() if v <= -thr)
            print("  [%s] <= -%.2fR : %3d of %d trading days (%.1f%%) "
                  "| of %d book sessions (%.1f%%)"
                  % (lbl, thr, c, len(ex), 100 * c / len(ex),
                     meta["sessions"], 100 * c / meta["sessions"]))


if __name__ == "__main__":
    main()
