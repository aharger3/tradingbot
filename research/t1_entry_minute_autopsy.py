"""T1 — why the engine misses 16 of Austin's 34 S days.

Ground truth that has never existed before: on 2026-08-28 he graded 100 blind
cards and gave an exact entry minute for every one of the 34 he called S
(`research/marks/probe_s_sweep_2026-08-28.jsonl`). That lets us ask a question
the recall gate cannot: when the engine is wrong, is it wrong about *whether* or
about *when*?

Three outcomes per S day, and they need different fixes:

  SILENT     the engine produced no signal at all near his minute
             -> a detection problem
  DETECTED   it produced a signal near his minute but never marked it `fired`
             -> a grading problem; the setup was seen and thrown away
  FIRED      it took an entry; report the minute delta
             -> if the delta is systematically positive the engine is LATE,
                which is what an LOD/HOD anchor would do against his stated
                "as candle forming not lod"

Nothing here changes the engine. Read-only.

    python research/t1_entry_minute_autopsy.py
"""
from __future__ import annotations

import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from research.t4_engine_recall import run_day  # noqa: E402

MARKS = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT = os.path.join(HERE, "t1_entry_minute_autopsy.md")

# How close a signal has to sit to his minute to count as "the same idea".
# Two bars either side: he types 9:41 for a candle he watched form from 9:40,
# and the engine stamps the bar it closed on.
NEAR = 2


def mins(hhmm: str) -> int:
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)


def hhmm(v: int) -> str:
    return "%d:%02d" % (v // 60, v % 60)


def bar_minute(ts: str) -> int:
    t = ts[11:16] if "T" in ts else ts[:5]
    return mins(t)


def load_s_marks() -> list[dict]:
    out = []
    with open(MARKS, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r["answers"].get("s") == ["s"] and r["notes"].get("min"):
                out.append(r)
    return out


def main() -> int:
    marks = load_s_marks()
    print("his S days with a stated minute: %d" % len(marks))

    rows = []
    for r in marks:
        sym, day, his = r["symbol"], r["date"], mins(r["notes"]["min"])
        try:
            entries, all_sigs, _raw = run_day(sym, day)
        except Exception as e:                     # a bad archive day is data
            rows.append({"sym": sym, "day": day, "his": his,
                         "verdict": "ERROR", "note": type(e).__name__})
            continue
        if entries is None:
            rows.append({"sym": sym, "day": day, "his": his,
                         "verdict": "NO BARS", "note": "not archived"})
            continue

        fired = sorted(((bar_minute(e["timestamp"]), e) for e in entries),
                       key=lambda x: x[0])
        seen = sorted(((bar_minute(s["timestamp"]), s) for s in all_sigs),
                      key=lambda x: x[0])

        near_fired = [(m, e) for m, e in fired if abs(m - his) <= NEAR]
        near_seen = [(m, s) for m, s in seen if abs(m - his) <= NEAR]

        if near_fired:
            m, e = min(near_fired, key=lambda x: abs(x[0] - his))
            rows.append({"sym": sym, "day": day, "his": his, "eng": m,
                         "delta": m - his, "verdict": "FIRED",
                         "grade": e["grade"], "setup": e["signal_type"]})
        elif near_seen:
            m, s = min(near_seen, key=lambda x: abs(x[0] - his))
            rows.append({"sym": sym, "day": day, "his": his, "eng": m,
                         "delta": m - his, "verdict": "DETECTED",
                         "grade": s["grade"], "setup": s["signal_type"],
                         "status": s["status"]})
        elif fired or seen:
            # It did something that day, just nowhere near his entry.
            m = min([x[0] for x in (fired or seen)], key=lambda v: abs(v - his))
            rows.append({"sym": sym, "day": day, "his": his, "eng": m,
                         "delta": m - his, "verdict": "ELSEWHERE",
                         "grade": (fired or seen)[0][1]["grade"],
                         "setup": (fired or seen)[0][1]["signal_type"]})
        else:
            rows.append({"sym": sym, "day": day, "his": his,
                         "verdict": "SILENT"})

    # ---- report ----------------------------------------------------------
    order = ["FIRED", "DETECTED", "ELSEWHERE", "SILENT", "NO BARS", "ERROR"]
    by = {k: [r for r in rows if r["verdict"] == k] for k in order}

    L = ["# T1 — the engine against his 34 stated S entry minutes", "",
         "Read-only. Marks: `research/marks/probe_s_sweep_2026-08-28.jsonl`.",
         "A signal counts as 'his idea' when it lands within %d bars of the "
         "minute he typed." % NEAR, "",
         "| verdict | days | what it means |", "|---|---:|---|"]
    meaning = {
        "FIRED": "engine took an entry at his setup",
        "DETECTED": "engine SAW it and refused to fire — a grading problem",
        "ELSEWHERE": "engine active that day but not at his entry",
        "SILENT": "engine produced nothing at all — a detection problem",
        "NO BARS": "day not archived",
        "ERROR": "replay raised",
    }
    for k in order:
        if by[k]:
            L.append("| **%s** | %d | %s |" % (k, len(by[k]), meaning[k]))
    print()
    for k in order:
        if by[k]:
            print("%-10s %2d   %s" % (k, len(by[k]), meaning[k]))

    deltas = [r["delta"] for r in rows if r["verdict"] in ("FIRED", "DETECTED")]
    if deltas:
        med = statistics.median(deltas)
        late = sum(1 for d in deltas if d > 0)
        early = sum(1 for d in deltas if d < 0)
        L += ["", "## Is it late?", "",
              "On the %d days the engine reached his setup, engine minute minus "
              "his minute:" % len(deltas), "",
              "- median **%+.1f bars**, mean %+.2f" % (med, sum(deltas) / len(deltas)),
              "- **%d late**, %d early, %d exact"
              % (late, early, len(deltas) - late - early), ""]
        print()
        print("delta (engine - his) on %d reached days: median %+.1f  mean %+.2f"
              % (len(deltas), med, sum(deltas) / len(deltas)))
        print("  late %d | early %d | exact %d"
              % (late, early, len(deltas) - late - early))

    L += ["", "## Every day", "",
          "| symbol | date | his | engine | delta | verdict | grade | setup |",
          "|---|---|---|---|---:|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["verdict"], r["sym"])):
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["sym"], r["day"], hhmm(r["his"]),
            hhmm(r["eng"]) if r.get("eng") is not None else "—",
            ("%+d" % r["delta"]) if r.get("delta") is not None else "—",
            r["verdict"], r.get("grade", "—"), r.get("setup", "—")))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print()
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
