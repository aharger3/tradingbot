"""T4 geometry sweep v3: test PURE supersets and fallbacks for non-regressing S
recall gain. A fallback retries a wider window ONLY when the primary (12-bar)
window returns None, so it can never replace a fire that succeeded (strict
superset of detection events; dedupe edge cases are caught by the gate)."""
from __future__ import annotations
import json, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import t4_engine_recall as t4
import omen_bot, signal_runner

BASE = json.load(open(os.path.join(HERE, "baseline_3.8.json")))
BASE_ANY = set(BASE["any_signal_fired"]); BASE_S = set(BASE["s_grade_fired"])
TOL = t4.TOL


def _run(candles, level, is_long, window, max_confirm_gap, leave_mode, retest_tol_mult=0.0):
    """Single FSM pass. Returns note-or-None."""
    if len(candles) < 4: return None
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level: return None
    if not is_long and cur.close >= level: return None
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = 0.10 * avg_rng; rtol = retest_tol_mult * avg_rng
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size: return None
    state, retest_idx = "seek_break", None
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long else (p.close >= level and c.close < level - eps)
            if crossed: state = "seek_leave"
        elif state == "seek_leave":
            if leave_mode == "close":
                left = (c.close > level + eps) if is_long else (c.close < level - eps)
            else:
                left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left: state = "seek_retest"
            elif failed: state = "seek_break"
        elif state == "seek_retest":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back: retest_idx, state = i, "hold"
        elif state == "hold":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back: retest_idx = i
    if retest_idx is None: return None
    if (len(w) - 1) - retest_idx > max_confirm_gap: return None
    prior = candles[:-window]
    late = sum(1 for a, b in zip(prior, prior[1:]) if (a.close - level) * (b.close - level) < 0)
    tag = f" | LATE({late} prior breaks)" if late else ""
    return f"break {'up' if is_long else 'down'} -> retest{tag}"


def make_detect(window=12, max_confirm_gap=3, leave_mode="wick",
                fb_window=None, fb_gap=None, fb_leave=None):
    fb_window = window if fb_window is None else fb_window
    fb_gap = max_confirm_gap if fb_gap is None else fb_gap
    fb_leave = leave_mode if fb_leave is None else fb_leave
    def detect_break_retest(candles, level, is_long, window=window,
                            max_confirm_gap=max_confirm_gap, out=None, retest_tol_mult=0.0):
        note = _run(candles, level, is_long, window, max_confirm_gap, leave_mode, retest_tol_mult)
        if note is not None:
            return note
        if fb_window != window or fb_gap != max_confirm_gap or fb_leave != leave_mode:
            return _run(candles, level, is_long, fb_window, fb_gap, fb_leave, retest_tol_mult)
        return None
    return detect_break_retest


def mark_key(m): return f"{m['symbol']}|{m['day']}|{m['entry_i']}"


def evaluate(**geo):
    fn = make_detect(**geo)
    omen_bot.detect_break_retest = fn; signal_runner.detect_break_retest = fn
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
                if any(abs(e["bar"] - m["entry_i"]) <= TOL for m in day_marks[(e["symbol"], e["day"])]): matched += 1
    any_sig = set(); s_fired = set()
    ta = defaultdict(int); tf = defaultdict(int)
    for m in marks:
        pair, i = (m["symbol"], m["day"]), m["entry_i"]
        f = any(abs(b - i) <= TOL for b in fired_bars[pair])
        s = any(abs(b - i) <= TOL for b in sig_bars[pair])
        if f or s: any_sig.add(mark_key(m)); ta[m["tier"]] += 1
        if f:
            tf[m["tier"]] += 1
            if m["tier"] == "S": s_fired.add(mark_key(m))
    dropped_any = sorted(BASE_ANY - any_sig); dropped_s = sorted(BASE_S - s_fired)
    prec = matched / on_marked if on_marked else 0
    return dict(S_any=ta["S"], S_fired=tf["S"], prec=prec, matched=matched,
                on_marked=on_marked, dropped_any=dropped_any, dropped_s=dropped_s,
                any_n=len(any_sig), s_fired_n=len(s_fired), A_any=ta["A"], X_any=ta["X"])


CONFIGS = [
    ("baseline",         dict()),
    ("gap6",             dict(max_confirm_gap=6)),
    ("gap9",             dict(max_confirm_gap=9)),
    ("gap12",            dict(max_confirm_gap=12)),
    ("fb_w20",           dict(fb_window=20)),
    ("fb_w30",           dict(fb_window=30)),
    ("fb_w20_g6",        dict(fb_window=20, fb_gap=6)),
    ("fb_w30_g6",        dict(fb_window=30, fb_gap=6)),
    ("fb_w30_g9",        dict(fb_window=30, fb_gap=9)),
    ("fb_w30_close",     dict(fb_window=30, fb_leave="close")),
    ("fb_w30_g9_close",  dict(fb_window=30, fb_gap=9, fb_leave="close")),
    ("fb_w20_close",     dict(fb_window=20, fb_leave="close")),
    ("gap6_fb_w30",      dict(max_confirm_gap=6, fb_window=30, fb_gap=9)),
]
print("baseline target: S_any=27 S_fired=10 prec=25/65=38.5%\n")
for name, geo in CONFIGS:
    r = evaluate(**geo)
    flag = "  <-- REGRESSION" if (r["dropped_any"] or r["dropped_s"]) else ("  *** GAIN" if r["S_any"] > 27 else "")
    print(f"{name:18s}: S_any={r['S_any']:2d}/77 S_fired={r['S_fired']:2d} "
          f"A_any={r['A_any']} X_any={r['X_any']} prec={r['matched']}/{r['on_marked']}={r['prec']:.1%}{flag}")
    if r["dropped_any"] or r["dropped_s"]:
        print(f"   dropped_any={r['dropped_any']} dropped_s={r['dropped_s']}")
