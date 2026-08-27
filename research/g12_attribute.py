"""G12: attribute each dropped s_grade mark to the condition that rejected it.

`research/regression_gate.py` fails at HEAD: 10 of Austin's S marks used to be
fired, 5 are. This script replays the SAME detection the gate replays
(t4_engine_recall.run_day, so the CaptureRunner routing is identical) and dumps
every raw signal the engine produced within +/-N bars of each dropped mark,
carrying the full `reason` annotation string.

`reason` is where every cap / demote / veto in the routing path writes its
tag, so diffing the reason strings between two commits names the branch that
changed — the same technique as research/t62_veto_autopsy.md and
research/g4_dropped_s.md.

Usage:
  python research/g12_attribute.py --out research/_g12_head.json
  git checkout <parent> && python research/g12_attribute.py --out research/_g12_parent.json
  python research/g12_attribute.py --diff research/_g12_parent.json research/_g12_head.json
"""

from __future__ import annotations
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# The six marks regression_gate.py reports as DROPPED s_grade at HEAD.
DROPPED = [
    ("GOOGL", "2024-10-15", 32),
    ("IWM",   "2025-04-10", 16),
    ("IWM",   "2025-12-01", 11),
    ("IWM",   "2025-12-04", 56),
    ("QQQ",   "2025-02-25", 16),
    ("UBER",  "2025-09-11", 15),
]
WINDOW = 4          # bars either side of the mark to dump (gate tolerance is 2)


def collect(window: int = WINDOW) -> dict:
    import t4_engine_recall as t4

    rich: list = []
    base = t4.CaptureRunner

    class RichRunner(base):
        """Same routing as the gate's CaptureRunner; also records `reason`."""
        def _route(self, signals, sig):
            super()._route(signals, sig)
            rich.append({
                "bar": len(self.candles) - 1,
                "timestamp": self.candles[-1].timestamp,
                "signal_type": sig["signal_type"].value,
                "direction": sig["direction"],
                "grade": sig["grade"],
                "status": sig["status"],
                "entry": round(float(sig["entry"]), 4),
                "stop": round(float(sig["stop"]), 4),
                "risk": round(abs(float(sig["entry"]) - float(sig["stop"])), 4),
                "stop_level": sig.get("stop_level_name"),
                "level_kind": sig.get("level_kind"),
                "austin_tier": sig.get("austin_tier"),
                "reason": (sig.get("reason") or "").strip(),
            })

    t4.CaptureRunner = RichRunner
    out = {}
    try:
        for sym, day, entry_i in DROPPED:
            rich.clear()
            ent, sigs, _raw = t4.run_day(sym, day)
            key = f"{sym}|{day}|{entry_i}"
            if ent is None:
                out[key] = {"error": "no archived bars"}
                continue
            near = [r for r in rich if abs(r["bar"] - entry_i) <= window]
            out[key] = {
                "near_signals": near,
                "fired_bars_all_day": sorted({e["bar"] for e in ent}),
                "fired_within_tol": sorted(
                    {e["bar"] for e in ent if abs(e["bar"] - entry_i) <= t4.TOL}),
                "n_signals_day": len(rich),
            }
    finally:
        t4.CaptureRunner = base
    return out


def _sig_id(r: dict) -> str:
    return f'{r["bar"]}|{r["signal_type"]}|{r["direction"]}|{r["stop_level"]}'


def diff(pa: str, pb: str) -> int:
    a, b = json.load(open(pa)), json.load(open(pb))
    for key in sorted(set(a) | set(b)):
        print(f"\n### {key}")
        ra, rb = a.get(key, {}), b.get(key, {})
        print(f"  fired within tol:  before={ra.get('fired_within_tol')}  "
              f"after={rb.get('fired_within_tol')}")
        ia = {_sig_id(r): r for r in ra.get("near_signals", [])}
        ib = {_sig_id(r): r for r in rb.get("near_signals", [])}
        for sid in sorted(set(ia) | set(ib), key=lambda s: (int(s.split("|")[0]), s)):
            x, y = ia.get(sid), ib.get(sid)
            if x and y and (x["status"], x["grade"], x["reason"]) == \
                           (y["status"], y["grade"], y["reason"]):
                continue
            print(f"  - {sid}")
            for lbl, r in (("before", x), ("after ", y)):
                if r is None:
                    print(f"      {lbl}: (absent)")
                    continue
                print(f"      {lbl}: {r['status']:<12} {r['grade']:<3} "
                      f"entry={r['entry']:<10} stop={r['stop']:<10} "
                      f"risk={r['risk']}")
                print(f"              {r['reason']}")
    return 0


def floor_table(path: str) -> int:
    """The arithmetic proof: signal_runner.py's minimum-risk floor is
    `stock_risk < max(0.10, 0.0015 * current.close) -> TradeGrade.D`. Print
    each mark's post-fill risk against its own floor."""
    data = json.load(open(path))
    print(f"{'mark':<24} {'bar':>4} {'entry':>9} {'stop':>9} {'risk':>7} "
          f"{'floor':>7}  under?")
    for key in sorted(data):
        entry_i = int(key.split("|")[2])
        for r in data[key].get("near_signals", []):
            if r["bar"] != entry_i and abs(r["bar"] - entry_i) > 2:
                continue
            floor = max(0.10, 0.0015 * r["entry"])
            print(f"{key:<24} {r['bar']:>4} {r['entry']:>9} {r['stop']:>9} "
                  f"{r['risk']:>7} {floor:>7.4f}  "
                  f"{'YES -> D' if r['risk'] < floor else 'no'}")
    return 0


def ab_close_fill() -> int:
    """A/B: put the pre-T3(b) fill back (entry = bar close) and re-run the
    regression gate. If the gate passes, fill_price() is the whole cause."""
    import regression_gate as rg    # imports t4, which puts ROOT on sys.path
    import signal_runner as sr

    def close_fill(level, candle, is_long, **kw):   # pre-5e3677ea behaviour
        return candle.close if candle is not None else level

    sr.fill_price = close_fill
    print("A/B: fill_price() forced back to the bar close (pre-T3(b))\n")
    return rg.check()


def ab_stop_on_entry_bar() -> int:
    """A/B the candidate minimal fix: intrabar_stop() today fires only when the
    fill fully COLLAPSES onto the stop (`entry <= stop`). Widen its trigger to
    the same minimum-risk floor the grader uses, so a fill that merely SQUEEZES
    the risk under the floor also moves the stop to the entry bar's own extreme
    — which is what Austin says the stop is ("stop loss at the bottom of the
    wick you entered")."""
    import regression_gate as rg
    import signal_runner as sr

    def widened(entry, stop, candle, is_long):
        if candle is None:
            return stop
        if abs(entry - stop) >= max(0.10, 0.0015 * candle.close):
            return stop                       # floor already satisfied
        bar_stop = candle.low if is_long else candle.high
        if (bar_stop < entry) if is_long else (bar_stop > entry):
            return bar_stop
        return stop

    sr.intrabar_stop = widened
    print("A/B: intrabar_stop() trigger widened from collapse to the "
          "minimum-risk floor\n")
    return rg.check()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    ap.add_argument("--floor", metavar="JSON")
    ap.add_argument("--ab-close-fill", action="store_true")
    ap.add_argument("--ab-stop-on-entry-bar", action="store_true")
    args = ap.parse_args()
    if args.diff:
        return diff(*args.diff)
    if args.floor:
        return floor_table(args.floor)
    if args.ab_close_fill:
        return ab_close_fill()
    if args.ab_stop_on_entry_bar:
        return ab_stop_on_entry_bar()
    data = collect()
    dest = args.out or os.path.join(HERE, "_g12_signals.json")
    with open(dest, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    for key, v in sorted(data.items()):
        print(f"{key}: fired_within_tol={v.get('fired_within_tol')} "
              f"near={len(v.get('near_signals', []))}")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
