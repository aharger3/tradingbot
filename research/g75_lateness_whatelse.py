"""g75_lateness_whatelse.py -- at Austin's own minute, what did the WHOLE
engine see on that chart, of any setup and any status?

The case-study script (g75_lateness_cases.py) answers the narrow question --
why the one-candle-rule detector was silent. This one answers the wide one:
was ANY signal, of any kind, available on that bar, and if so what killed it?
That is the difference between "the setup was absent", "detected and vetoed"
and "detected and suppressed", and it is what decides whether his trade is
reachable at all.

Runs the shipped engine bar-by-bar through research/t4_engine_recall.run_day
(the same replay the regression gate uses), then reports every signal inside
+/-4 bars of his stated minute.

Read-only. Writes research/g75_lateness_whatelse.json.
"""
from __future__ import annotations
import json, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as T4

MARKS = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29_complete.jsonl")
MANI = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
OUT = os.path.join(HERE, "g75_lateness_whatelse.json")
TOL = 4

TOK = re.compile(r"\b(\d{1,2})[:;.](\d{2})\b")


def his_minute(note):
    m = TOK.search(note or "")
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h < 9 or h > 11:
        return None
    t = (h - 9) * 60 + mi - 30
    return t if 0 <= t <= 95 else None


def clock(off):
    return "%d:%02d" % (9 + (30 + off) // 60, (30 + off) % 60)


marks = [json.loads(l) for l in open(MARKS, encoding="utf-8")]
mani = {json.loads(l)["card_id"]: json.loads(l) for l in open(MANI, encoding="utf-8")}
cards = []
for m in marks:
    r = dict(mani[m["card_id"]])
    r["yes"] = m["answers"]["is_s"][0] == "yes"
    r["note"] = " ".join(str(v) for v in (m.get("notes") or {}).values())
    r["his"] = his_minute(r["note"])
    r["eng"] = (int(r["et"][:2]) - 9) * 60 + int(r["et"][3:]) - 30
    cards.append(r)

TARGET = [c for c in cards if c["yes"] and c["his"] is not None
          and c["bucket"] in ("OCR", "BR")]
TARGET.sort(key=lambda c: (c["bucket"] != "OCR", c["card_id"]))

J = {"cards": [], "verdict": {}}
tally = Counter()
print("=" * 96)
print("AT HIS MINUTE (+/- %d bars), EVERYTHING THE SHIPPED ENGINE PRODUCED ON THAT CHART" % TOL)
print("=" * 96)
for c in TARGET:
    entries, all_sigs, raw = T4.run_day(c["symbol"], c["date"])
    near = [r for r in (raw or []) if abs(r["bar"] - c["his"]) <= TOL]
    print()
    print("%-20s [%s]  he %s -> engine %s  (+%d)"
          % (c["card_id"], c["bucket"], clock(c["his"]), clock(c["eng"]),
             c["eng"] - c["his"]))
    if not near:
        print("     NOTHING. Not a signal of any setup, any grade, any status, "
              "on that bar or the four either side.")
        verdict = "absent"
    else:
        for r in sorted(near, key=lambda r: r["bar"]):
            print("     %s  %-18s %-4s  grade %-2s  status %-22s  stop %s"
                  % (r["timestamp"][:5], r["signal_type"], r["direction"],
                     r["grade"], r["status"], r["stop_level"]))
        fired = [r for r in near if r["status"] == "fired"]
        verdict = "fired" if fired else "detected_then_vetoed"
    tally[(c["bucket"], verdict)] += 1
    J["cards"].append({"card_id": c["card_id"], "bucket": c["bucket"],
                       "his": c["his"], "eng": c["eng"], "late": c["eng"] - c["his"],
                       "verdict": verdict,
                       "near": [{k: r[k] for k in ("timestamp", "signal_type",
                                                   "direction", "grade", "status",
                                                   "stop_level")} for r in near]})

print()
print("=" * 96)
print("VERDICT COUNT")
print("=" * 96)
for (b, v), n in sorted(tally.items()):
    print("  %-4s  %-24s %d" % (b, v, n))
J["verdict"] = {"%s|%s" % k: v for k, v in tally.items()}
json.dump(J, open(OUT, "w"), indent=1)
print()
print("wrote", OUT)
