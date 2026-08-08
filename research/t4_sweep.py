"""T4 sweep: monkeypatch detect_break_retest's (window, max_confirm_gap) defaults
and run the FULL t4 recall harness, for each candidate geometry. Reports S
any-signal recall, fired-S, precision, and any dropped baseline marks. No source
edit needed per config — picks the best geometry before we touch omen_bot.py."""
from __future__ import annotations
import json, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import t4_engine_recall as t4
import omen_bot
from signal_runner import SignalRunner

BASE = json.load(open(os.path.join(HERE, "baseline_3.8.json")))
BASE_ANY = set(BASE["any_signal_fired"])
BASE_S = set(BASE["s_grade_fired"])
TOL = t4.TOL


def mark_key(m): return f"{m['symbol']}|{m['day']}|{m['entry_i']}"


def evaluate(window, gap):
    # patch defaults: (window, max_confirm_gap, out, retest_tol_mult)
    omen_bot.detect_break_retest.__defaults__ = (window, gap, None, 0.0)
    marks = [json.loads(l) for l in open(t4.MARKS) if l.strip()]
    fired_bars = defaultdict(list); sig_bars = defaultdict(list)
    on_marked = 0; matched = 0
    day_marks = defaultdict(list)
    for m in marks: day_marks[(m["symbol"], m["day"])].append(m)
    marked_days = set(day_marks)
    for sym, day in sorted({(m["symbol"], m["day"]) for m in marks}):
        ent, sigs, _ = t4.run_day(sym, day)
        if ent is None: continue
        fired_bars[(sym, day)].extend(e["bar"] for e in ent)
        sig_bars[(sym, day)].extend(s["bar"] for s in sigs)
        on_marked += len([e for e in ent if (e["symbol"], e["day"]) in marked_days])
        for e in ent:
            if (e["symbol"], e["day"]) in marked_days:
                ms = day_marks[(e["symbol"], e["day"])]
                if any(abs(e["bar"] - m["entry_i"]) <= TOL for m in ms):
                    matched += 1
    any_sig = set(); s_fired = set()
    tier_any = defaultdict(int); tier_fired = defaultdict(int)
    for m in marks:
        pair, i = (m["symbol"], m["day"]), m["entry_i"]
        f = any(abs(b - i) <= TOL for b in fired_bars[pair])
        s = any(abs(b - i) <= TOL for b in sig_bars[pair])
        if f or s:
            any_sig.add(mark_key(m)); tier_any[m["tier"]] += 1
        if f:
            tier_fired[m["tier"]] += 1
            if m["tier"] == "S": s_fired.add(mark_key(m))
    dropped_any = BASE_ANY - any_sig
    dropped_s = BASE_S - s_fired
    prec = matched / on_marked if on_marked else 0
    return dict(S_any=tier_any["S"], A_any=tier_any["A"], X_any=tier_any["X"],
                S_fired=tier_fired["S"], prec=prec, matched=matched, on_marked=on_marked,
                dropped_any=sorted(dropped_any), dropped_s=sorted(dropped_s),
                any_n=len(any_sig), s_fired_n=len(s_fired))


CONFIGS = [(12, 3), (20, 3), (20, 6), (24, 6), (30, 6), (30, 9), (40, 9), (30, 12), (20, 9)]
print(f"baseline: S_any=27, S_fired=10, prec=25/65=38.5%, any_signal=60, s_grade=10\n")
for w, g in CONFIGS:
    r = evaluate(w, g)
    flag = "  <-- REGRESSION" if (r["dropped_any"] or r["dropped_s"]) else ""
    print(f"w={w:2d} g={g:2d}: S_any={r['S_any']:2d}/77 S_fired={r['S_fired']:2d} "
          f"prec={r['matched']}/{r['on_marked']}={r['prec']:.1%} anyN={r['any_n']} sFiredN={r['s_fired_n']}{flag}")
    if r["dropped_any"] or r["dropped_s"]:
        print(f"        dropped_any={r['dropped_any']} dropped_s={r['dropped_s']}")
