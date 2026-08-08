"""T4 geometry sweep v2: monkeypatch a CONFIGURABLE detect_break_retest into both
omen_bot and signal_runner, run the full t4 recall harness, and report S recall /
fired-S / precision / dropped-baseline for each geometry. Picks a non-regressing
geometry that lifts S any-signal recall above 27 before we touch omen_bot.py.

Geometry knobs (all GEOMETRY, none is a retest-proximity tolerance band):
  window          : lookback window (12 default)
  max_confirm_gap : retest->entry staleness cap (3 default)
  leave_mode      : "wick" (current: low/high clears level+eps) or "close"
                    (close clears level+eps — same field as the BREAK; fixes the
                    wick-vs-close asymmetry that blocks the seek_leave stalls)
  hold_rearm      : if True, a candle closing back THROUGH the level while we are
                    in seek_retest/hold (a failed/dirty retest) resets the FSM to
                    seek_break, so a LATER clean break→leave→retest can still fire
                    instead of the FSM being stranded on a stale leave (the
                    HOOD-style window-boundary trap).
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import t4_engine_recall as t4
import omen_bot
import signal_runner
from signal_runner import SignalRunner, _retest_tol

BASE = json.load(open(os.path.join(HERE, "baseline_3.8.json")))
BASE_ANY = set(BASE["any_signal_fired"])
BASE_S = set(BASE["s_grade_fired"])
TOL = t4.TOL


def make_detect(window=12, max_confirm_gap=3, leave_mode="wick", hold_rearm=False):
    def detect_break_retest(candles, level, is_long, window=window,
                            max_confirm_gap=max_confirm_gap, out=None,
                            retest_tol_mult=0.0):
        if len(candles) < 4:
            return None
        w = candles[-window:]
        cur = w[-1]
        if is_long and cur.close <= level:
            return None
        if not is_long and cur.close >= level:
            return None
        avg_rng = sum(c.high - c.low for c in w) / len(w)
        eps = 0.10 * avg_rng
        rtol = retest_tol_mult * avg_rng
        adverse = cur.lower_wick if not is_long else cur.upper_wick
        if adverse > 1.5 * cur.body_size:
            return None
        state, retest_idx = "seek_break", None
        for i in range(1, len(w)):
            c, p = w[i], w[i - 1]
            if state == "seek_break":
                crossed = (p.close <= level and c.close > level + eps) if is_long \
                    else (p.close >= level and c.close < level - eps)
                if crossed:
                    state = "seek_leave"
            elif state == "seek_leave":
                if leave_mode == "close":
                    left = (c.close > level + eps) if is_long else (c.close < level - eps)
                else:
                    left = (c.low > level + eps) if is_long else (c.high < level - eps)
                failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
                if left:
                    state = "seek_retest"
                elif failed:
                    state = "seek_break"
            elif state == "seek_retest":
                back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
                if back:
                    retest_idx, state = i, "hold"
                elif hold_rearm:
                    through = (c.close <= level) if is_long else (c.close >= level)
                    if through:
                        state, retest_idx = "seek_break", None
            elif state == "hold":
                back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
                if back:
                    retest_idx = i
                elif hold_rearm:
                    through = (c.close <= level) if is_long else (c.close >= level)
                    if through:
                        state, retest_idx = "seek_break", None
        if retest_idx is None:
            return None
        if (len(w) - 1) - retest_idx > max_confirm_gap:
            return None
        prior = candles[:-window]
        late = sum(1 for a, b in zip(prior, prior[1:])
                   if (a.close - level) * (b.close - level) < 0)
        tag = f" | LATE({late} prior breaks)" if late else ""
        return (f"break {'up' if is_long else 'down'} -> retest{tag}") or "ok"
    return detect_break_retest


def mark_key(m): return f"{m['symbol']}|{m['day']}|{m['entry_i']}"


def evaluate(**geo):
    fn = make_detect(**geo)
    omen_bot.detect_break_retest = fn
    signal_runner.detect_break_retest = fn
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
        for e in ent:
            if (e["symbol"], e["day"]) in marked_days:
                on_marked += 1
                ms = day_marks[(e["symbol"], e["day"])]
                if any(abs(e["bar"] - m["entry_i"]) <= TOL for m in ms):
                    matched += 1
    any_sig = set(); s_fired = set()
    tier_any = defaultdict(int); tier_fired = defaultdict(int)
    for m in marks:
        pair, i = (m["symbol"], m["day"]), m["entry_i"]
        f = any(abs(b - i) <= TOL for b in fired_bars[pair])
        s = any(abs(b - i) <= TOL for b in sig_bars[pair])
        if f or s: any_sig.add(mark_key(m)); tier_any[m["tier"]] += 1
        if f:
            tier_fired[m["tier"]] += 1
            if m["tier"] == "S": s_fired.add(mark_key(m))
    dropped_any = sorted(BASE_ANY - any_sig)
    dropped_s = sorted(BASE_S - s_fired)
    prec = matched / on_marked if on_marked else 0
    return dict(S_any=tier_any["S"], A_any=tier_any["A"], X_any=tier_any["X"],
                S_fired=tier_fired["S"], prec=prec, matched=matched, on_marked=on_marked,
                dropped_any=dropped_any, dropped_s=dropped_s,
                any_n=len(any_sig), s_fired_n=len(s_fired))


CONFIGS = [
    ("baseline",        dict()),
    ("close_leave",     dict(leave_mode="close")),
    ("hold_rearm",      dict(hold_rearm=True)),
    ("close+rearm",     dict(leave_mode="close", hold_rearm=True)),
    ("close+w20",      dict(leave_mode="close", window=20)),
    ("close+rearm+w20",dict(leave_mode="close", hold_rearm=True, window=20)),
    ("rearm+w20",       dict(hold_rearm=True, window=20)),
    ("close+rearm+w20g6",dict(leave_mode="close", hold_rearm=True, window=20, max_confirm_gap=6)),
]
print(f"baseline target: S_any=27, S_fired=10, prec=25/65=38.5%\n")
for name, geo in CONFIGS:
    r = evaluate(**geo)
    flag = "  <-- REGRESSION" if (r["dropped_any"] or r["dropped_s"]) else ""
    print(f"{name:20s}: S_any={r['S_any']:2d}/77 S_fired={r['S_fired']:2d} "
          f"prec={r['matched']}/{r['on_marked']}={r['prec']:.1%} anyN={r['any_n']} sFired={r['s_fired_n']}{flag}")
    if r["dropped_any"] or r["dropped_s"]:
        print(f"   dropped_any={r['dropped_any']} dropped_s={r['dropped_s']}")
