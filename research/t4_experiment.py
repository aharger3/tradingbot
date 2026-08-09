"""T4 experiment harness: for the CURRENT omen_bot.detect_break_retest, replay
t4's detection over all 159 marks and report:
  - S any-signal recall (the number this row must raise)
  - any baseline-fired mark that went SILENT (the regression gate's failure set)
  - which of the 30 S x no_break_retest marks now have ANY signal within +/-2

Fresh process each run so signal_runner picks up edits to omen_bot.
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import t4_engine_recall as t4

BASELINE = os.path.join(HERE, "baseline_3.8.json")
TOL = t4.TOL

# the 30 S x no_break_retest marks (recomputed from miss_autopsy.jsonl)
AUT = os.path.join(HERE, "miss_autopsy.jsonl")
NBR = {(r["symbol"], r["day"], r["entry_i"]) for r in
       (json.loads(l) for l in open(AUT) if l.strip())
       if r.get("tier") == "S" and r.get("miss_reason") == "no_break_retest"}


def mark_key(m):
    return f"{m['symbol']}|{m['day']}|{m['entry_i']}"


def run():
    marks = [json.loads(l) for l in open(t4.MARKS) if l.strip()]
    base = json.load(open(BASELINE))
    base_any = set(base["any_signal_fired"])
    base_s = set(base["s_grade_fired"])

    fired_bars = defaultdict(list)
    sig_bars = defaultdict(list)
    for sym, day in sorted({(m["symbol"], m["day"]) for m in marks}):
        ent, sigs, _raw = t4.run_day(sym, day)
        if ent is None:
            continue
        fired_bars[(sym, day)].extend(e["bar"] for e in ent)
        sig_bars[(sym, day)].extend(s["bar"] for s in sigs)

    any_signal, s_grade = set(), set()
    tier_any = defaultdict(int)
    nbr_hit = set()
    for m in marks:
        pair, key, i = (m["symbol"], m["day"]), mark_key(m), m["entry_i"]
        fired = any(abs(b - i) <= TOL for b in fired_bars[pair])
        sig = any(abs(b - i) <= TOL for b in sig_bars[pair])
        if fired:
            if m["tier"] == "S":
                s_grade.add(key)
        if fired or sig:
            any_signal.add(key)
            tier_any[m["tier"]] += 1
            if (m["symbol"], m["day"], m["entry_i"]) in NBR:
                nbr_hit.add(key)

    dropped_any = sorted(base_any - any_signal)
    dropped_s = sorted(base_s - s_grade)
    gained_s = sorted(s_grade - base_s)

    print(f"S any-signal recall: {tier_any['S']}/77   (A {tier_any['A']}/60, X {tier_any['X']}/22)")
    print(f"any_signal set: {len(any_signal)} (baseline {len(base_any)}); s_grade fired: {len(s_grade)} (baseline {len(base_s)})")
    # precision: of all fired entry-bars on marked days, fraction landing within +/-2 of a mark
    marked_pairs = {(m["symbol"], m["day"]) for m in marks}
    total_fired = 0
    matched_fired = 0
    for p in marked_pairs:
        for b in fired_bars[p]:
            total_fired += 1
            if any(abs(b - m["entry_i"]) <= TOL for m in marks if (m["symbol"], m["day"]) == p):
                matched_fired += 1
    prec = (matched_fired / total_fired) if total_fired else 0.0
    print(f"precision {prec:.3f} ({matched_fired}/{total_fired} fired-entry-bars on marked days)")
    print(f"DROPPED any_signal: {dropped_any}")
    print(f"DROPPED s_grade:    {dropped_s}")
    print(f"GAINED s_grade fired: {gained_s}")
    print(f"no_break_retest S marks now with any signal ({len(nbr_hit)}/30):")
    for k in sorted(nbr_hit):
        print(f"    + {k}")
    ok = not dropped_any and not dropped_s and tier_any['S'] > len(base_s) or tier_any['S'] > 28
    print(f"\nrecall increased vs 28? {tier_any['S'] > 28}   gate would pass? {not dropped_any and not dropped_s}")
    return tier_any['S'], dropped_any, dropped_s


if __name__ == "__main__":
    run()
