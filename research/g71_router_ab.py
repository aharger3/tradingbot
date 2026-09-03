"""g71 ADVERSARIAL VERIFY (track: router).

Question: at TODAY's flag defaults, what actually differs between
`signal_runner.SignalRunner._route` (the live door) and
`research/t4_engine_recall.CaptureRunner._route` (the hand-rolled copy the
recall metric is scored through)?

Method: replay every marked symbol-day twice through t4.run_day.
  arm A (control) = CaptureRunner._route as committed
  arm B (delegate) = CaptureRunner._route replaced by a BacktestRunner-style
                     `super()._route(...)` + status labelling
Then diff the fired sets and attribute every divergence to the reason string
the base wrote.  No engine file is edited; the patch is applied in-process.
"""
from __future__ import annotations
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import signal_runner as sr
import t4_engine_recall as t4

CR = t4.CaptureRunner
_ORIG = CR._route


def delegating_route(self, signals, sig):
    before = len(signals)
    sr.SignalRunner._route(self, signals, sig)
    sig["status"] = "fired" if len(signals) > before else "skipped"
    self.captured.append(sig)


def replay(marks_pairs):
    out = {}
    for sym, day in marks_pairs:
        ent, sigs, raw = t4.run_day(sym, day)
        if ent is None:
            continue
        out[(sym, day)] = {
            "fired": sorted(e["bar"] for e in ent),
            "raw": [(r["bar"], r["signal_type"], r["direction"], r["grade"],
                     r["status"], round(r["entry"] or 0, 4), round(r["stop"] or 0, 4))
                    for r in raw],
        }
    return out


def main():
    marks = [json.loads(l) for l in open(t4.MARKS) if l.strip()]
    pairs = sorted({(m["symbol"], m["day"]) for m in marks})
    print("flags: MIN_STOP_PCT=%s NO_REPEAT_ENTRIES=%s LEVEL_RETIRE_TOUCHES=%s "
          "ENFORCE_NO_REPEAT=%s S_GATE=%s RULE_710=%s AUSTIN_TIER=%s X_LIFT=%s "
          "SAC_LADDER=%s ARRIVAL_LADDER=%s"
          % (sr.MIN_STOP_PCT, sr.NO_REPEAT_ENTRIES, sr.LEVEL_RETIRE_TOUCHES,
             sr.ENFORCE_NO_REPEAT, sr.S_GATE, sr.RULE_710_ENABLED,
             sr.AUSTIN_TIER_ENABLED, sr.X_LIFT, sr.ENABLE_SAC_LADDER,
             sr.ARRIVAL_LADDER))
    print("symbol-days: %d" % len(pairs))

    CR._route = _ORIG
    A = replay(pairs)
    CR._route = delegating_route
    B = replay(pairs)
    CR._route = _ORIG

    only_A = only_B = same = 0
    diff_days = []
    for k in A:
        fa, fb = A[k]["fired"], B.get(k, {}).get("fired", [])
        ca, cb = collections.Counter(fa), collections.Counter(fb)
        d_a = list((ca - cb).elements()); d_b = list((cb - ca).elements())
        only_A += len(d_a); only_B += len(d_b); same += sum((ca & cb).values())
        if d_a or d_b:
            diff_days.append((k, d_a, d_b))
    print("deduped fired bars: shared=%d  A-only(capture fires, base would not)=%d  "
          "B-only(base fires, capture does not)=%d" % (same, only_A, only_B))
    print("days differing: %d / %d" % (len(diff_days), len(A)))
    for k, da, db in diff_days[:25]:
        print("  %s %s  A-only=%s  B-only=%s" % (k[0], k[1], da, db))

    # attribution over the RAW (undeduped) capture stream
    ra = collections.Counter(); rb = collections.Counter()
    for k in A:
        for r in A[k]["raw"]:
            ra[r[:5]] += 1
    for k in B:
        for r in B[k]["raw"]:
            rb[r[:5]] += 1
    print("\nraw signal rows: A=%d B=%d" % (sum(ra.values()), sum(rb.values())))
    fa = sum(v for kk, v in ra.items() if kk[4] == "fired")
    fb = sum(v for kk, v in rb.items() if kk[4] == "fired")
    print("raw FIRED rows: A=%d  B=%d  delta=%d" % (fa, fb, fb - fa))
    ga = collections.Counter(kk[3] for kk, v in ra.items() for _ in range(v) if kk[4] == "fired")
    gb = collections.Counter(kk[3] for kk, v in rb.items() for _ in range(v) if kk[4] == "fired")
    print("fired-by-grade A: %s" % dict(ga))
    print("fired-by-grade B: %s" % dict(gb))


if __name__ == "__main__":
    main()
