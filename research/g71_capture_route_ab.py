"""G7.1 / track `capture` -- is the recall harness's router the shipped router?

`research/t4_engine_recall.CaptureRunner._route` is a hand-rolled copy of
`signal_runner.SignalRunner._route` that never calls `super()`. Every gate the
base router grew after it was written is therefore INERT in the one rig that
scores held-out recall (`regression_gate.py`, `t0_heldout_recall.py`,
`t23_stack.py`, `build_deck.py`, and ~30 other research modules import it).

`backtest_week.BacktestRunner` had the identical bug and it was fixed in
omen-5.0 by delegating to `super()._route` and labelling the status afterwards.
The recall harness never got that fix (commit 145d564e named it and left it).

This script MEASURES the gap. It does not modify any engine file.

  A (incumbent)  = t4_engine_recall.CaptureRunner as shipped
  B (delegating) = the same class with backtest_week.BacktestRunner's router

Both arms replay the same bars over the same marked (symbol, day) pairs.

Usage:  python research/g71_capture_route_ab.py [--limit N]
"""
from __future__ import annotations
import argparse, inspect, json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import signal_runner as sr                    # noqa: E402
from omen_bot import TradeGrade               # noqa: E402
import t4_engine_recall as t4                 # noqa: E402


# ---------------------------------------------------------------- static diff
# Named gates in SignalRunner._route, with the module-global that arms each and
# whether that global is ON at import time with the shipped defaults.
BASE_GATES = [
    ("S_GATE cap-to-C",            "S_GATE"),
    ("RULE_710 cap-to-C",          "RULE_710_ENABLED"),
    ("austin_tier compute",        "AUSTIN_TIER_ENABLED"),
    ("mesh_blocked stamp",         None),
    ("LEVEL_RETIRE skip",          "LEVEL_RETIRE_TOUCHES"),
    ("_apply_x_lift",              "X_LIFT"),
    ("ENFORCE_NO_REPEAT skip",     "ENFORCE_NO_REPEAT"),
    ("MIN_STOP_PCT skip",          "MIN_STOP_PCT"),
    ("C tight-stop skip",          None),
    ("NO_REPEAT_ENTRIES skip",     "NO_REPEAT_ENTRIES"),
    ("_fired_ideas bookkeeping",   None),
    ("_fired_levels bookkeeping",  None),
]

# What the incumbent CaptureRunner._route body actually contains.
CAPTURE_HAS = {
    "S_GATE cap-to-C": False,
    "RULE_710 cap-to-C": False,
    "austin_tier compute": False,
    "mesh_blocked stamp": False,
    "LEVEL_RETIRE skip": False,
    "_apply_x_lift": True,
    "ENFORCE_NO_REPEAT skip": False,
    "MIN_STOP_PCT skip": False,
    "C tight-stop skip": True,
    "NO_REPEAT_ENTRIES skip": False,
    "_fired_ideas bookkeeping": False,
    "_fired_levels bookkeeping": False,
}


def armed(flag):
    if flag is None:
        return "always"
    v = getattr(sr, flag, None)
    if isinstance(v, str):
        return "ON (%s)" % v if v not in ("off", "", "0") else "off"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return "ON (%s)" % v if v > 0 else "off"
    return "ON" if v else "off"


def static_report():
    src = inspect.getsource(t4.CaptureRunner._route)
    print("== static gate inventory: SignalRunner._route vs "
          "t4_engine_recall.CaptureRunner._route ==")
    print(f"{'gate':<28}{'armed by default':<18}{'in CaptureRunner'}")
    missing_live = []
    for name, flag in BASE_GATES:
        a = armed(flag)
        have = CAPTURE_HAS[name]
        print(f"{name:<28}{a:<18}{'yes' if have else 'NO'}")
        if not have and a != "off":
            missing_live.append((name, a))
    # the docstring MENTIONS super()._route; only a real call counts.
    body = "\n".join(l for l in src.splitlines()
                     if not l.strip().startswith("#"))
    body = body.split('"""')[-1] if body.count('"""') >= 2 else body
    print("\ndelegates to super()._route:",
          "yes" if "super()._route(" in body else "NO")
    print("LIVE gates missing from the recall router (armed, not executed):")
    for n, a in missing_live:
        print(f"   - {n}   [{a}]")
    return missing_live


# ------------------------------------------------------------------- live A/B
class DelegatingCaptureRunner(sr.SignalRunner):
    """backtest_week.BacktestRunner's router, verbatim in shape: let the BASE
    decide what fires, label the outcome afterwards, capture everything."""

    def __init__(self, symbol):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.captured = []

    def _route(self, signals, sig):
        before = len(signals)
        super()._route(signals, sig)
        if len(signals) > before:
            sig["status"] = "fired"
        elif sig["grade"] == TradeGrade.D.value:
            sig["status"] = "skipped_d"
        elif sig.get("level_retired"):
            sig["status"] = "skipped_level_retired"
        elif "[skip: repeat entry]" in sig.get("reason", ""):
            sig["status"] = "skipped_repeat_entry"
        elif "[skip: repeat idea]" in sig.get("reason", ""):
            sig["status"] = "skipped_repeat_idea"
        elif "[skip: stop under" in sig.get("reason", ""):
            sig["status"] = "skipped_min_stop_pct"
        else:
            sig["status"] = "skipped_tight"
        self.captured.append(sig)


def replay(pairs):
    out = {}
    for sym, day in pairs:
        ent, sigs, raw = t4.run_day(sym, day)
        if ent is None:
            continue
        out[(sym, day)] = {
            "entries": [(e["bar"], e["signal_type"], e["direction"],
                         round(e["stop"], 4)) for e in ent],
            "n_sig": len(sigs),
            "n_raw": len(raw),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    missing = static_report()

    marks = [json.loads(l) for l in open(t4.MARKS, encoding="utf-8") if l.strip()]
    pairs = sorted({(m["symbol"], m["day"]) for m in marks})
    if args.limit:
        pairs = pairs[:args.limit]
    print(f"\n== live A/B over {len(pairs)} marked (symbol, day) pairs ==")

    incumbent = t4.CaptureRunner
    A = replay(pairs)
    t4.CaptureRunner = DelegatingCaptureRunner
    try:
        B = replay(pairs)
    finally:
        t4.CaptureRunner = incumbent

    keys = sorted(set(A) | set(B))
    a_ent = sum(len(A.get(k, {}).get("entries", [])) for k in keys)
    b_ent = sum(len(B.get(k, {}).get("entries", [])) for k in keys)
    days_diff, dropped, added = 0, Counter(), Counter()
    for k in keys:
        ea = set(A.get(k, {}).get("entries", []))
        eb = set(B.get(k, {}).get("entries", []))
        if ea != eb:
            days_diff += 1
            for e in ea - eb:
                dropped[k[0]] += 1
            for e in eb - ea:
                added[k[0]] += 1

    print(f"replayed days with bars: A={len(A)} B={len(B)}")
    print(f"fired entries: A(incumbent)={a_ent}  B(delegating)={b_ent}  "
          f"move={b_ent - a_ent:+d}")
    print(f"days whose fired set differs: {days_diff} of {len(keys)}")
    print(f"entries the shipped router would NOT have taken "
          f"(present in A, absent in B): {sum(dropped.values())}")
    print(f"entries only the shipped router takes "
          f"(absent in A, present in B): {sum(added.values())}")
    if dropped:
        print("  dropped by symbol:", dict(dropped.most_common()))
    if added:
        print("  added by symbol:", dict(added.most_common()))

    # mark-level recall, t4's own join
    def recall(book):
        by_pair = defaultdict(list)
        for m in marks:
            if m.get("entry_i") is None:
                continue
            by_pair[(m["symbol"], m["day"])].append(m)
        hit = Counter(); tot = Counter()
        for k, ms in by_pair.items():
            bars = [e[0] for e in book.get(k, {}).get("entries", [])]
            for m in ms:
                tier = m.get("tier") or m.get("austin_tier") or "?"
                tot[tier] += 1
                if any(abs(b - m["entry_i"]) <= t4.TOL for b in bars):
                    hit[tier] += 1
        return hit, tot

    ha, ta = recall(A)
    hb, tb = recall(B)
    print("\nmark recall by tier (fired entries, +/-%d bars):" % t4.TOL)
    for tier in sorted(set(ta) | set(tb)):
        print(f"  {tier}: A {ha[tier]}/{ta[tier]}   B {hb[tier]}/{tb[tier]}")


if __name__ == "__main__":
    main()
