"""omen-3.8 T0: recall regression gate.

Re-runs `t4_engine_recall.py`'s detection (imported, not reimplemented) over the
same 159 marks in `austin_marks_v2.jsonl`, rebuilds the set of mark keys the
engine currently fires on, and diffs it against the locked baseline in
`research/baseline_3.8.json`.

Exits non-zero, printing the exact dropped mark keys, if any baseline-fired key
is no longer fired. New fires are FINE — recall going up never fails the gate;
only a previously-fired mark going silent does.

Mark key: "symbol|day|entry_i". Join tolerance: t4_engine_recall.TOL (+/-2 bars).

Two locked sets:
  any_signal_fired - every mark (any tier) the engine lands on within +/-2, by a
                     fired entry OR any captured signal (incl. X/tight-stop
                     skips). This is the detection set: it protects everything
                     the engine currently sees.
  s_grade_fired    - the tier-S marks the engine actually takes an entry on
                     (fired, deduped — i.e. the rows in engine_entries.jsonl).
                     This is the S recall omen-3.8 is trying to raise.

Usage:
  python research/regression_gate.py                  # check (exit 1 on regression)
  python research/regression_gate.py --write-baseline # lock the current state (T0 only)
"""

from __future__ import annotations
import json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import t4_engine_recall as t4   # reuse the harness's own detection replay

BASELINE = os.path.join(HERE, "baseline_3.8.json")
RECALL_MD = t4.OUT_MD
ENTRIES = t4.OUT_ENTRIES


def mark_key(m) -> str:
    return f"{m['symbol']}|{m['day']}|{m['entry_i']}"


def load_marks():
    return [json.loads(l) for l in open(t4.MARKS) if l.strip()]


def current_sets(marks):
    """Replay t4's detection over every marked (symbol, day) and join marks to
    engine bars with t4's +/-TOL tolerance. Returns (any_signal, s_grade,
    fired_all, by_tier)."""
    fired_bars = defaultdict(list)
    sig_bars = defaultdict(list)
    for sym, day in sorted({(m["symbol"], m["day"]) for m in marks}):
        ent, sigs, _raw = t4.run_day(sym, day)
        if ent is None:          # no archived bars -> engine cannot run
            continue
        fired_bars[(sym, day)].extend(e["bar"] for e in ent)
        sig_bars[(sym, day)].extend(s["bar"] for s in sigs)

    any_signal, s_grade, fired_all = set(), set(), set()
    by_tier = defaultdict(lambda: {"fired": 0, "any_signal": 0, "total": 0})
    for m in marks:
        pair, key, i = (m["symbol"], m["day"]), mark_key(m), m["entry_i"]
        fired = any(abs(b - i) <= t4.TOL for b in fired_bars[pair])
        signalled = any(abs(b - i) <= t4.TOL for b in sig_bars[pair])
        by_tier[m["tier"]]["total"] += 1
        if fired:
            fired_all.add(key)
            by_tier[m["tier"]]["fired"] += 1
            if m["tier"] == "S":
                s_grade.add(key)
        if fired or signalled:
            any_signal.add(key)
            by_tier[m["tier"]]["any_signal"] += 1
    return any_signal, s_grade, fired_all, dict(by_tier)


def fired_from_entries_file(marks):
    """The same fired-mark set derived from the harness's engine_entries.jsonl
    dump, used only to cross-check the in-process replay when locking."""
    bars = defaultdict(list)
    with open(ENTRIES) as f:
        for line in f:
            if line.strip():
                e = json.loads(line)
                bars[(e["symbol"], e["day"])].append(e["bar"])
    return {mark_key(m) for m in marks
            if any(abs(b - m["entry_i"]) <= t4.TOL
                   for b in bars[(m["symbol"], m["day"])])}


def precision_from_md():
    """Parse `Precision: **25/65 = 38.5%**` out of engine_recall.md."""
    txt = open(RECALL_MD).read()
    mt = re.search(r"Precision: \*\*(\d+)/(\d+) = ([\d.]+)%\*\*", txt)
    if not mt:
        raise SystemExit(f"cannot parse precision from {RECALL_MD}")
    hit, tot = int(mt.group(1)), int(mt.group(2))
    return hit / tot, hit, tot


def write_baseline():
    marks = load_marks()
    any_signal, s_grade, fired_all, by_tier = current_sets(marks)
    from_file = fired_from_entries_file(marks)
    if from_file != fired_all:
        raise SystemExit(
            "in-process replay disagrees with engine_entries.jsonl — refusing "
            f"to lock. only-in-file={sorted(from_file - fired_all)} "
            f"only-in-replay={sorted(fired_all - from_file)}")
    precision, hit, tot = precision_from_md()
    doc = {
        "any_signal_fired": sorted(any_signal),
        "s_grade_fired": sorted(s_grade),
        "precision": precision,
        "precision_detail": {"matched": hit, "engine_entries_on_marked_days": tot},
        "fired_entry_marks": sorted(fired_all),
        "by_tier": by_tier,
        "tolerance_bars": t4.TOL,
        "marks_file": os.path.basename(t4.MARKS),
        "n_marks": len(marks),
    }
    with open(BASELINE, "w") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"locked {BASELINE}")
    print(f"  any_signal_fired: {len(any_signal)}")
    print(f"  s_grade_fired:    {len(s_grade)}")
    print(f"  fired_entry_marks:{len(fired_all)}")
    print(f"  precision:        {precision:.4f} ({hit}/{tot})")
    print(f"  by_tier:          {by_tier}")
    return 0


def check():
    if not os.path.exists(BASELINE):
        print(f"FAIL: no baseline at {BASELINE} — run --write-baseline first")
        return 2
    base = json.load(open(BASELINE))
    marks = load_marks()
    any_signal, s_grade, fired_all, by_tier = current_sets(marks)

    dropped_any = sorted(set(base["any_signal_fired"]) - any_signal)
    dropped_s = sorted(set(base["s_grade_fired"]) - s_grade)
    gained_any = len(any_signal - set(base["any_signal_fired"]))
    gained_s = len(s_grade - set(base["s_grade_fired"]))

    print(f"baseline: any_signal {len(base['any_signal_fired'])}, "
          f"s_grade {len(base['s_grade_fired'])}")
    print(f"current:  any_signal {len(any_signal)}, s_grade {len(s_grade)}")
    print(f"new fires (not a failure): any_signal +{gained_any}, s_grade +{gained_s}")
    print(f"by_tier: {by_tier}")

    if dropped_any or dropped_s:
        print("\nREGRESSION — baseline-fired marks that went silent:")
        for k in dropped_any:
            print(f"  DROPPED any_signal: {k}")
        for k in dropped_s:
            print(f"  DROPPED s_grade:    {k}")
        print(f"\nFAIL: {len(dropped_any)} any_signal + {len(dropped_s)} s_grade "
              "mark(s) no longer fired.")
        return 1

    print("\nPASS: no baseline-fired mark went silent.")
    return 0


if __name__ == "__main__":
    sys.exit(write_baseline() if "--write-baseline" in sys.argv[1:] else check())
