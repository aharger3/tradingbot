"""omen-3.8 T0: regression gate on the 3.8 baseline.

Re-runs `t4_engine_recall.py`'s detection (imported, not reimplemented) over the
same 159 marks in `austin_marks_v2.jsonl`, rebuilds the fired-mark-key sets the
same way the harness scores recall, and diffs them against
`research/baseline_3.8.json`.

Mark key: `symbol|day|entry_i`. Join: the harness's own +/-2 bar tolerance
(`t4_engine_recall.TOL`).

Two sets are locked:
  * `any_signal_fired` - marks (any tier) with ANY engine signal within +/-TOL
    bars, any grade, fired or skipped (the harness's "any-sig" column, built
    from its deduped all-signals stream). This is detection.
  * `s_grade_fired`    - S-tier marks with a FIRED engine entry within +/-TOL
    bars (the harness's "fired" S column / `engine_entries.jsonl`). These are
    the S setups the engine actually takes.

Exit 0 if every baseline key still fires. Exit 1 (printing the dropped keys) if
any baseline key went silent. New fires are fine - recall going up never fails.

  python research/regression_gate.py                 # check against baseline
  python research/regression_gate.py --write-baseline  # (re)lock the baseline
"""

from __future__ import annotations
import json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import t4_engine_recall as t4

BASELINE = os.path.join(HERE, "baseline_3.8.json")


def mark_key(m) -> str:
    return f"{m['symbol']}|{m['day']}|{m['entry_i']}"


def compute():
    """Returns (any_signal_fired, s_grade_fired, by_tier) using t4's detection."""
    marks = [json.loads(l) for l in open(t4.MARKS) if l.strip()]
    pairs = sorted({(m["symbol"], m["day"]) for m in marks})

    entry_bars = defaultdict(list)   # (sym, day) -> fired entry bar indexes
    sig_bars = defaultdict(list)     # (sym, day) -> any-signal bar indexes (deduped)
    for sym, day in pairs:
        # A change under test that makes detection raise on one day must not abort the
        # sweep with a traceback - that hides WHICH marks went silent, which is the only
        # thing this gate exists to print. Treat the day as no-signal and keep going; its
        # baseline marks then show up as dropped keys, which is the truthful reading.
        try:
            ent, sigs, _raw = t4.run_day(sym, day)
        except Exception as e:
            print(f"WARN: detection raised on {sym} {day}: {type(e).__name__}: {e}")
            continue
        if ent is None:              # no archived bars -> engine cannot run
            continue
        entry_bars[(sym, day)] = [e["bar"] for e in ent]
        sig_bars[(sym, day)] = [s["bar"] for s in sigs]

    any_signal, s_grade = [], []
    by_tier = {"any_signal": defaultdict(int), "fired": defaultdict(int)}
    for m in marks:
        pair, i = (m["symbol"], m["day"]), m["entry_i"]
        hit = any(abs(b - i) <= t4.TOL for b in entry_bars.get(pair, []))
        any_hit = any(abs(b - i) <= t4.TOL for b in sig_bars.get(pair, []))
        if any_hit:
            any_signal.append(mark_key(m))
            by_tier["any_signal"][m["tier"]] += 1
        if hit:
            by_tier["fired"][m["tier"]] += 1
            if m["tier"] == "S":
                s_grade.append(mark_key(m))
    return (sorted(set(any_signal)), sorted(set(s_grade)),
            {k: dict(v) for k, v in by_tier.items()})


def precision_from_report():
    """The precision line t4 wrote into engine_recall.md, as an exact float."""
    md = open(t4.OUT_MD).read()
    m = re.search(r"Precision: \*\*(\d+)/(\d+) = ", md)
    if not m:
        raise SystemExit("could not read precision from engine_recall.md "
                         "- run t4_engine_recall.py first")
    num, den = int(m.group(1)), int(m.group(2))
    return num / den if den else 0.0


def write_baseline():
    any_signal, s_grade, by_tier = compute()
    data = {"any_signal_fired": any_signal,
            "s_grade_fired": s_grade,
            "precision": precision_from_report(),
            "by_tier": by_tier}
    with open(BASELINE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"wrote {BASELINE}: any_signal {len(any_signal)}, "
          f"s_grade {len(s_grade)}, precision {data['precision']:.4f}")
    print(f"by_tier {by_tier}")


def check():
    if not os.path.exists(BASELINE):
        print(f"FAIL: {BASELINE} missing - baseline not locked")
        return 1
    base = json.load(open(BASELINE))
    any_signal, s_grade, by_tier = compute()

    dropped_any = sorted(set(base["any_signal_fired"]) - set(any_signal))
    dropped_s = sorted(set(base["s_grade_fired"]) - set(s_grade))
    new_any = len(set(any_signal) - set(base["any_signal_fired"]))
    new_s = len(set(s_grade) - set(base["s_grade_fired"]))

    print(f"any_signal: {len(any_signal)} now vs {len(base['any_signal_fired'])} "
          f"baseline (+{new_any} new, -{len(dropped_any)} dropped)")
    print(f"s_grade:    {len(s_grade)} now vs {len(base['s_grade_fired'])} "
          f"baseline (+{new_s} new, -{len(dropped_s)} dropped)")
    print(f"by_tier {by_tier}")

    if dropped_any or dropped_s:
        print("REGRESSION: baseline marks no longer fire")
        for k in dropped_any:
            print(f"  dropped any_signal: {k}")
        for k in dropped_s:
            print(f"  dropped s_grade:    {k}")
        return 1
    print("PASS: no baseline mark went silent")
    return 0


if __name__ == "__main__":
    if "--write-baseline" in sys.argv:
        write_baseline()
    else:
        sys.exit(check())
