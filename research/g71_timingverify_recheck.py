"""Adversarial re-verification of the G71/timing claim about T1's +0.0 bars.

Independent re-implementation: reads the held-out probe marks, replays each day
through research.t4_engine_recall.run_day, and recomputes the split statistic
from scratch. Adds paired tests, window sensitivity, a reachability check on
"can a fired entry precede its own signal", and a cross-check of the 9 FIRED
symbol-days against the committed 2-year book. Read-only on every mark file.
"""
from __future__ import annotations
import json, math, os, sys, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
from research.t4_engine_recall import run_day  # noqa: E402

MARKS = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")


def bar_of(hhmm: str) -> int:
    h, m = hhmm.replace(".", ":").split(":")[:2]
    return (int(h) - 9) * 60 + int(m) - 30


def sign_p(pos: int, neg: int) -> float:
    n = pos + neg
    if not n:
        return float("nan")
    k = min(pos, neg)
    return min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n)


def describe(label, ds):
    if not ds:
        print("%-34s n= 0" % label); return
    late = sum(1 for d in ds if d > 0); early = sum(1 for d in ds if d < 0)
    print("%-34s n=%2d  median %+0.1f  mean %+0.2f  late %d / exact %d / early %d  p=%.4f"
          % (label, len(ds), statistics.median(ds), statistics.fmean(ds),
             late, len(ds) - late - early, early, sign_p(late, early)))


def main():
    cards = []
    for line in open(MARKS, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        ans = [a.lower() for a in ((o.get("answers") or {}).get("s") or [])]
        mn = (o.get("notes") or {}).get("min")
        if "s" in ans and mn:
            cards.append((o["symbol"], o["date"], mn.strip()))
    print("S cards with typed minute: %d" % len(cards))

    recs = []
    for sym, day, mn in cards:
        his = bar_of(mn)
        entries, sigs, raw = run_day(sym, day)
        if entries is None:
            print("NO BARS %s %s" % (sym, day)); continue
        fb = sorted(e["bar"] for e in entries)
        sb = sorted(s["bar"] for s in sigs)
        rb = sorted(s["bar"] for s in raw)
        rfb = sorted(s["bar"] for s in raw if s["status"] == "fired")
        recs.append(dict(sym=sym, day=day, his=his, fired=fb, sigs=sb, raw=rb,
                         rawfired=rfb, raws=raw))

    def near(bars, his):
        return min(bars, key=lambda b: abs(b - his)) if bars else None

    print("\n--- recomputed from scratch (deduped populations, as G71 used) ---")
    for w in (1, 2, 3, 4, 6):
        describe("nearest FIRED, +/-%d" % w,
                 [near(r["fired"], r["his"]) - r["his"] for r in recs
                  if r["fired"] and abs(near(r["fired"], r["his"]) - r["his"]) <= w])
    for w in (2, 6):
        describe("nearest SIGNAL, +/-%d" % w,
                 [near(r["sigs"], r["his"]) - r["his"] for r in recs
                  if r["sigs"] and abs(near(r["sigs"], r["his"]) - r["his"]) <= w])

    print("\n--- same, on RAW (undeduped) signal population ---")
    describe("nearest RAW-FIRED, +/-2",
             [near(r["rawfired"], r["his"]) - r["his"] for r in recs
              if r["rawfired"] and abs(near(r["rawfired"], r["his"]) - r["his"]) <= 2])
    describe("nearest RAW-SIGNAL, +/-2",
             [near(r["raw"], r["his"]) - r["his"] for r in recs
              if r["raw"] and abs(near(r["raw"], r["his"]) - r["his"]) <= 2])

    print("\n--- PAIRED on the 9 FIRED+/-2 days (same days both sides) ---")
    paired = [r for r in recs if r["fired"]
              and abs(near(r["fired"], r["his"]) - r["his"]) <= 2]
    dF = [near(r["fired"], r["his"]) - r["his"] for r in paired]
    dS = [near(r["sigs"], r["his"]) - r["his"] for r in paired if r["sigs"]]
    print("days: %s" % ", ".join("%s %s" % (r["sym"], r["day"]) for r in paired))
    describe("  dF (fired - his)", dF)
    describe("  dS (signal - his)", dS)
    diffs = [a - b for a, b in zip(dF, dS)]
    describe("  dF - dS (paired)", diffs)

    print("\n--- reachability: can a fired entry precede any signal on its day? ---")
    bad = 0
    for r in recs:
        if r["rawfired"] and r["raw"] and min(r["rawfired"]) < min(r["raw"]):
            bad += 1
    print("days where first FIRED bar < first SIGNAL bar: %d of %d" % (bad, len(recs)))
    ded = sum(1 for r in recs if r["fired"] and r["sigs"]
              and near(r["fired"], r["his"]) < near(r["sigs"], r["his"]))
    print("days where nearest FIRED < nearest SIGNAL (dedupe can allow this): %d" % ded)
    early_any = sum(1 for r in recs if r["fired"]
                    and any(b < r["his"] for b in r["fired"]))
    print("days with ANY fired entry strictly before his minute: %d" % early_any)
    print("days with ANY fired entry in [his-6, his-1]: %d"
          % sum(1 for r in recs if any(r["his"] - 6 <= b <= r["his"] - 1
                                       for b in r["fired"])))

    print("\n--- book cross-check: are those 9 entries in the committed 2y book? ---")
    bp = os.path.join(HERE, "bt2y_trades.json")
    if os.path.exists(bp):
        book = json.load(open(bp))
        tr = book["trades"] if isinstance(book, dict) else book
        print("book rows=%d  traded=%d" % (len(tr), sum(1 for t in tr if t.get("traded"))))
        idx = defaultdict(list)
        for t in tr:
            idx[(t["sym"], t["day"])].append(t)
        for r in paired:
            rows = idx.get((r["sym"], r["day"]), [])
            td = [t for t in rows if t.get("traded")]
            print("  %-5s %s his=%d fired=%s | book rows=%d traded=%d bars=%s"
                  % (r["sym"], r["day"], r["his"], near(r["fired"], r["his"]),
                     len(rows), len(td), sorted(t.get("bar") for t in td)))
    else:
        print("bt2y_trades.json missing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
