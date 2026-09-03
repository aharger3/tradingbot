"""G7.1 / track `router` - held-out S recall on the CORRECT router.

THE QUESTION
------------
T23 (commit 145d564e, research/t23_stack.md section 4b) found that the number
this project steers by - held-out S recall on the 100 blind cards of
`research/marks/probe_s_sweep_2026-08-28.jsonl` - is measured through
`research/t4_engine_recall.CaptureRunner._route`, a HAND-ROLLED copy of the
shipped router that never calls `super()`. `backtest_week.BacktestRunner` had
the identical defect and was fixed in omen-5.0 (2026-08-12) with the comment
"every gate the base grew after it was written was therefore INERT in every
backtest ever run". The recall harness never got that fix.

This script scores the same 100 cards TWICE, changing exactly one thing:

  arm `hand_rolled` - t4_engine_recall.CaptureRunner._route as it ships today
                      (the wrong router; the 23/34 = 67.6% number)
  arm `delegating`  - the same class with `_route` replaced by a delegating
                      version that calls `super()._route` and labels the
                      outcome afterwards, byte-for-byte the shape of
                      backtest_week.BacktestRunner._route (the right router)

Nothing else changes: same archive, same window, same 09:30-11:00 cutoff, same
dedupe, same shipped flag defaults (X_LIFT=clean, MIN_STOP_PCT=0.08,
PIVOT_LEVELS=1, AUSTIN_TIER_ENABLED=True, NO_REPEAT_ENTRIES=0,
ENFORCE_NO_REPEAT=False, LEVEL_RETIRE_TOUCHES=0, S_GATE=False,
RULE_710_ENABLED=False, SESSION_EXTREME_FRAC=0.0).

The monkeypatch is applied IN THIS PROCESS ONLY. No engine file is edited.
Mark files are opened read-only.

Recall/precision are scored exactly as research/t0_heldout_recall.py::score_sweep
does - a card counts as a hit if the engine takes ANY entry that day - so the
`hand_rolled` arm must reproduce 23/34 = 67.6% and 39.7% precision.

Usage:
  python research/g71_router_recall.py [--out research/g71_router_recall.json]
"""
from __future__ import annotations
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import research.t4_engine_recall as t4          # noqa: E402
from signal_runner import TradeGrade            # noqa: E402
import signal_runner as sr                      # noqa: E402

SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")

_ORIGINAL_ROUTE = t4.CaptureRunner._route


def _delegating_route(self, signals, sig):
    """The FIX, as backtest_week.BacktestRunner._route already has it.

    The subclass exists to CAPTURE what the base rejects, not to route
    differently: delegate the accept/reject decision to the shipped router and
    label the outcome afterwards.
    """
    before = len(signals)
    # bound to SignalRunner explicitly, not super(): regression_gate imports
    # t4_engine_recall as a TOP-LEVEL module, so there are two distinct
    # CaptureRunner classes in a process that imports both. This call is
    # what `super()._route(...)` resolves to inside the real subclass.
    sr.SignalRunner._route(self, signals, sig)
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
        sig["status"] = "skipped_tight_stop"
    self.captured.append(sig)


def rows(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def bar_minute(ts):
    t = ts[11:16] if "T" in ts else ts[:5]
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def replay(pairs):
    out = {}
    for sym, day in sorted(pairs):
        try:
            entries, sigs, _raw = t4.run_day(sym, day)
        except Exception as e:                       # noqa: BLE001
            out[(sym, day)] = {"error": type(e).__name__}
            continue
        if entries is None:
            out[(sym, day)] = {"error": "no archived bars"}
            continue
        out[(sym, day)] = {
            "fired": sorted(bar_minute(e["timestamp"]) for e in entries),
            "n_fired": len(entries),
            "n_seen": len(sigs),
            "fired_grades": sorted({e["grade"] for e in entries}),
        }
    return out


def score(cards, rep):
    his_s = [r for r in cards if r["answers"]["s"] == ["s"]]
    his_no = [r for r in cards if r["answers"]["s"] != ["s"]]

    def fired(r):
        return bool(rep.get((r["symbol"], r["date"]), {}).get("fired"))

    tp = [r for r in his_s if fired(r)]
    fp = [r for r in his_no if fired(r)]
    return {
        "n_cards": len(cards), "n_S": len(his_s), "n_no": len(his_no),
        "fired_on_S": len(tp), "fired_on_no": len(fp),
        "recall_pct": round(len(tp) / len(his_s) * 100, 1) if his_s else 0.0,
        "precision_pct": (round(len(tp) / (len(tp) + len(fp)) * 100, 1)
                          if (tp or fp) else 0.0),
        "unreplayable_days": len([k for k, v in rep.items() if "error" in v]),
        "hit_S": sorted(r["card_id"] for r in tp),
        "missed_S": sorted(r["card_id"] for r in his_s if not fired(r)),
        "false_fire_no": sorted(r["card_id"] for r in fp),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g71_router_recall.json"))
    a = ap.parse_args()

    cards = [r for r in rows(SWEEP) if r["answers"].get("s")]
    pairs = {(r["symbol"], r["date"]) for r in cards}

    flags = {
        "X_LIFT": sr.X_LIFT, "MIN_STOP_PCT": sr.MIN_STOP_PCT,
        "PIVOT_LEVELS": sr.PIVOT_LEVELS, "AUSTIN_TIER_ENABLED": sr.AUSTIN_TIER_ENABLED,
        "NO_REPEAT_ENTRIES": sr.NO_REPEAT_ENTRIES,
        "ENFORCE_NO_REPEAT": sr.ENFORCE_NO_REPEAT,
        "LEVEL_RETIRE_TOUCHES": sr.LEVEL_RETIRE_TOUCHES,
        "S_GATE": sr.S_GATE, "RULE_710_ENABLED": sr.RULE_710_ENABLED,
        "SESSION_EXTREME_FRAC": sr.SESSION_EXTREME_FRAC,
        "HODLOD_PAIR": sr.HODLOD_PAIR,
        "DEDUPE_BARS": t4.DEDUPE_BARS, "ENTRY_CUTOFF": t4.ENTRY_CUTOFF,
    }

    res = {"flags": flags, "n_days": len(pairs)}

    t0 = time.time()
    t4.CaptureRunner._route = _ORIGINAL_ROUTE
    rep_a = replay(pairs)
    res["hand_rolled"] = score(cards, rep_a)
    print("hand_rolled  %.0fs" % (time.time() - t0))

    t0 = time.time()
    t4.CaptureRunner._route = _delegating_route
    rep_b = replay(pairs)
    res["delegating"] = score(cards, rep_b)
    t4.CaptureRunner._route = _ORIGINAL_ROUTE
    print("delegating   %.0fs" % (time.time() - t0))

    # card-by-card delta
    changed = []
    for r in sorted(cards, key=lambda x: x["card_id"]):
        k = (r["symbol"], r["date"])
        a_f = bool(rep_a.get(k, {}).get("fired"))
        b_f = bool(rep_b.get(k, {}).get("fired"))
        if a_f != b_f:
            changed.append({
                "card_id": r["card_id"], "symbol": r["symbol"], "date": r["date"],
                "his_grade": "S" if r["answers"]["s"] == ["s"] else "no",
                "hand_rolled_fired": a_f, "delegating_fired": b_f,
                "hand_rolled_entries": rep_a.get(k, {}).get("n_fired", 0),
                "delegating_entries": rep_b.get(k, {}).get("n_fired", 0),
                "hand_rolled_minutes": rep_a.get(k, {}).get("fired", []),
                "delegating_minutes": rep_b.get(k, {}).get("fired", []),
            })
    res["cards_changed"] = changed

    # entry-count deltas even where the card verdict did not flip
    ecount = []
    for r in sorted(cards, key=lambda x: x["card_id"]):
        k = (r["symbol"], r["date"])
        na = rep_a.get(k, {}).get("n_fired", 0)
        nb = rep_b.get(k, {}).get("n_fired", 0)
        if na != nb:
            ecount.append({"card_id": r["card_id"],
                           "his_grade": "S" if r["answers"]["s"] == ["s"] else "no",
                           "hand_rolled_entries": na, "delegating_entries": nb})
    res["entry_count_changed"] = ecount

    summary = {
        "recall": "%d/%d = %.1f%%  ->  %d/%d = %.1f%%" % (
            res["hand_rolled"]["fired_on_S"], res["hand_rolled"]["n_S"],
            res["hand_rolled"]["recall_pct"],
            res["delegating"]["fired_on_S"], res["delegating"]["n_S"],
            res["delegating"]["recall_pct"]),
        "precision": "%.1f%%  ->  %.1f%%" % (
            res["hand_rolled"]["precision_pct"], res["delegating"]["precision_pct"]),
        "false_fires_on_his_no": "%d  ->  %d" % (
            res["hand_rolled"]["fired_on_no"], res["delegating"]["fired_on_no"]),
        "cards_flipped": len(changed),
        "cards_with_entry_count_change": len(ecount),
    }
    res["summary"] = summary
    print(json.dumps(summary, indent=2))
    for c in changed:
        print("  %-18s his=%-2s  %s -> %s  (entries %d -> %d)" % (
            c["card_id"], c["his_grade"],
            "FIRE" if c["hand_rolled_fired"] else "silent",
            "FIRE" if c["delegating_fired"] else "silent",
            c["hand_rolled_entries"], c["delegating_entries"]))

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print("wrote " + a.out)


if __name__ == "__main__":
    main()
