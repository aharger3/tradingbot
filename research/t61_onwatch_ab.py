"""t61_onwatch_ab.py -- does ON WATCH actually close the recall gap?

The whole justification for the ON WATCH state is Austin's claim that the engine
misses entries because it waits for the candle to close. That is a testable
claim, and this is the test: replay his 120 graded day-cards through the engine
with the state on and off, and count how many of his S-days it finds.

    ON_WATCH=0 python research/t61_onwatch_ab.py off.json
    ON_WATCH=1 python research/t61_onwatch_ab.py on.json
    python research/t61_onwatch_ab.py --compare off.json on.json

Two processes because ON_WATCH is read once at import.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)


def measure(out_path):
    from research.t4_engine_recall import run_day
    from research.t60_baseline import load_day_cards
    import signal_runner

    days, marks = load_day_cards()
    by_day = {}
    for m in marks:
        by_day.setdefault((m["symbol"], m["date"]), []).append(m)

    rows = []
    for (sym, date), card in sorted(days.items()):
        grade = (card.get("grade") or "").strip()
        try:
            entries, _sigs, _raw = run_day(sym, date)
        except Exception as exc:                      # a bad archive day is not a miss
            rows.append({"symbol": sym, "date": date, "grade": grade,
                         "error": str(exc)[:80]})
            continue
        entries = entries or []
        mine = by_day.get((sym, date), [])
        matched = 0
        for m in mine:
            if m.get("entry_i") is None:
                continue
            # run_day's entries carry "bar", the index into the RTH candle list
            bars = [e.get("bar") for e in entries if isinstance(e, dict)]
            if any(b is not None and abs(b - m["entry_i"]) <= 3 for b in bars):
                matched += 1
        rows.append({"symbol": sym, "date": date, "grade": grade,
                     "n_fires": len(entries), "n_marks": len(mine),
                     "n_entry_match": matched})

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"on_watch": signal_runner.ON_WATCH, "rows": rows}, f)
    summarise(out_path, json.load(open(out_path, encoding="utf-8")))


def score(blob):
    rows = [r for r in blob["rows"] if "error" not in r]
    s_days = [r for r in rows if r["grade"] == "S"]
    trade_days = [r for r in rows if r["grade"] not in ("", "none")]
    none_days = [r for r in rows if r["grade"] == "none"]
    return {
        "on_watch": blob["on_watch"],
        "days": len(rows),
        "errors": len(blob["rows"]) - len(rows),
        "s_total": len(s_days),
        "s_found": sum(1 for r in s_days if r["n_fires"] > 0),
        "trade_total": len(trade_days),
        "trade_found": sum(1 for r in trade_days if r["n_fires"] > 0),
        "false_fires": sum(1 for r in none_days if r["n_fires"] > 0),
        "none_total": len(none_days),
        "entry_matches": sum(r["n_entry_match"] for r in rows),
        "marks": sum(r["n_marks"] for r in rows),
        "total_fires": sum(r["n_fires"] for r in rows),
    }


def summarise(path, blob):
    s = score(blob)
    print("%s  ON_WATCH=%s" % (os.path.basename(path), s["on_watch"]))
    print("  S-day recall     %d/%d = %.3f" % (s["s_found"], s["s_total"],
                                               s["s_found"] / max(s["s_total"], 1)))
    print("  day recall       %d/%d" % (s["trade_found"], s["trade_total"]))
    print("  false fires      %d/%d refused days" % (s["false_fires"], s["none_total"]))
    print("  entry matches    %d/%d marks (+/-3 bars)" % (s["entry_matches"], s["marks"]))
    print("  total signals    %d" % s["total_fires"])


def compare(a_path, b_path):
    a = score(json.load(open(a_path, encoding="utf-8")))
    b = score(json.load(open(b_path, encoding="utf-8")))
    print("| metric | ON_WATCH off | ON_WATCH on | delta |")
    print("|---|---:|---:|---:|")
    for key, label in (("s_found", "S-days found (of %d)" % a["s_total"]),
                       ("trade_found", "trade-days found (of %d)" % a["trade_total"]),
                       ("entry_matches", "entry matches +/-3 (of %d)" % a["marks"]),
                       ("false_fires", "false fires (of %d refused)" % a["none_total"]),
                       ("total_fires", "total signals")):
        d = b[key] - a[key]
        print("| %s | %d | %d | %+d |" % (label, a[key], b[key], d))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--compare"]:
        compare(sys.argv[2], sys.argv[3])
    else:
        measure(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "t61.json"))
