"""G7.1 adversarial verify (track: capture-refute).

Measures whether research/t4_engine_recall.CaptureRunner._route not calling
super() actually changes the harness's fired set, by re-running the SAME
symbol-days twice: once with the shipped hand-rolled router, once with a router
that delegates to SignalRunner._route (the backtest_week.BacktestRunner fix).

No engine file is edited; the delegating router is monkeypatched in-process.
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import t4_engine_recall as t4
from omen_bot import TradeGrade
from signal_runner import SignalRunner


def delegating_route(self, signals, sig):
    """backtest_week.BacktestRunner._route, verbatim in behaviour."""
    before = len(signals)
    SignalRunner._route(self, signals, sig)
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
    elif sig["grade"] == "X":
        sig["status"] = "skipped_x"
    else:
        sig["status"] = "skipped_tight"
    self.captured.append(sig)


def pairs_from_marks():
    marks = [json.loads(l) for l in open(t4.MARKS) if l.strip()]
    return sorted({(m["symbol"], m["day"]) for m in marks}), marks


def run(pairs):
    fired, allsig, grades = defaultdict(list), defaultdict(list), defaultdict(int)
    for sym, day in pairs:
        ent, sigs, raw = t4.run_day(sym, day)
        if ent is None:
            continue
        fired[(sym, day)] = [e["bar"] for e in ent]
        allsig[(sym, day)] = [s["bar"] for s in sigs]
        for r in raw:
            grades[(r["grade"], r["status"])] += 1
    return fired, allsig, grades


def main():
    pairs, marks = pairs_from_marks()
    print(f"pairs: {len(pairs)}  marks: {len(marks)}")

    stock_route = t4.CaptureRunner._route
    f_a, s_a, g_a = run(pairs)
    t4.CaptureRunner._route = delegating_route
    f_b, s_b, g_b = run(pairs)
    t4.CaptureRunner._route = stock_route

    na = sum(len(v) for v in f_a.values()); nb = sum(len(v) for v in f_b.values())
    print(f"FIRED entries  hand-rolled={na}  delegating={nb}  delta={nb-na}")
    print(f"ALL signals    hand-rolled={sum(len(v) for v in s_a.values())}"
          f"  delegating={sum(len(v) for v in s_b.values())}")

    # per-mark recall join, exactly regression_gate.current_sets
    def sets(fired, allsig):
        any_s, s_g, f_all = set(), set(), set()
        for m in marks:
            pair = (m["symbol"], m["day"]); key = f"{m['symbol']}|{m['day']}|{m['entry_i']}"
            i = m["entry_i"]
            fi = any(abs(b - i) <= t4.TOL for b in fired[pair])
            si = any(abs(b - i) <= t4.TOL for b in allsig[pair])
            if fi:
                f_all.add(key)
                if m["tier"] == "S":
                    s_g.add(key)
            if fi or si:
                any_s.add(key)
        return any_s, s_g, f_all
    a_any, a_s, a_f = sets(f_a, s_a)
    b_any, b_s, b_f = sets(f_b, s_b)
    print(f"any_signal  A={len(a_any)} B={len(b_any)}")
    print(f"s_grade     A={len(a_s)}   B={len(b_s)}   dropped={sorted(a_s-b_s)}")
    print(f"fired_all   A={len(a_f)}   B={len(b_f)}   dropped={len(a_f-b_f)} gained={len(b_f-a_f)}")

    print("\nstatus/grade census (hand-rolled):")
    for k, v in sorted(g_a.items(), key=lambda x: -x[1])[:12]:
        print(f"  {k}: {v}")
    print("status/grade census (delegating):")
    for k, v in sorted(g_b.items(), key=lambda x: -x[1])[:12]:
        print(f"  {k}: {v}")

    json.dump({"fired_handrolled": na, "fired_delegating": nb,
               "s_grade_A": len(a_s), "s_grade_B": len(b_s),
               "fired_all_A": len(a_f), "fired_all_B": len(b_f)},
              open(os.path.join(HERE, "g71_capture_ab.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
