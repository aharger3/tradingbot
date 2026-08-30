"""T0 - held-out S recall, on both of Austin's held-out sets.

Method rule 2: held-out recall governs, not mean R. Two sets, scored the same
way and never mixed:

  1. `research/marks/probe_s_sweep_2026-08-28.jsonl` - 100 never-before-judged
     symbol-days he graded blind. 34 came back S. RECALL = of those 34, on how
     many does the engine take an entry that day. The standing figure before
     this track is 18/34 = 52.9%. Precision on the same 100 cards is reported
     beside it, because a recall number with no precision number can be bought
     by firing on everything.

  2. `research/marks/probe_master_2026-08-29.jsonl`, lane `vetoes` - 40 setups
     the engine DETECTED and then graded X, which he then graded himself:
     5 S, 4 A, 4 C, 27 no. Every one of these was a veto by construction, so the
     engine's recall on them started at 0/5 and the only way it moves is a gate
     coming off. The 27 "no" rows are the false-fire cost of taking those gates
     off, which is the half of the ledger a lift track is tempted to skip.

The engine is replayed by `research/t4_engine_recall.run_day`, the same harness
the regression gate and T1 use. No engine code is touched here. Marks are read,
never written.

Usage:
  python research/t0_heldout_recall.py [--out research/t0_heldout_recall.json]
"""
from __future__ import annotations
import argparse, json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from research.t4_engine_recall import run_day  # noqa: E402
import grade_read  # noqa: E402  the ONE grade reader -- see research/g72_onespelling.md

SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
MASTER = os.path.join(HERE, "marks", "probe_master_2026-08-29.jsonl")

# How close a fire has to sit to the minute he named to count as the same idea.
# Two bars either side, exactly as research/t1_entry_minute_autopsy.py: he types
# 9:41 for a candle he watched form from 9:40, and the engine stamps the bar it
# closed on.
NEAR = 2


def rows(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def mins(hhmm):
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)


def bar_minute(ts):
    t = ts[11:16] if "T" in ts else ts[:5]
    return mins(t)


def replay(pairs):
    """(symbol, day) -> {'fired': [minutes], 'seen': [minutes]} - one replay per
    day however many cards reference it."""
    out = {}
    for sym, day in sorted(pairs):
        try:
            entries, sigs, _raw = run_day(sym, day)
        except Exception as e:
            out[(sym, day)] = {"error": type(e).__name__}
            continue
        if entries is None:
            out[(sym, day)] = {"error": "no archived bars"}
            continue
        out[(sym, day)] = {
            "fired": sorted(bar_minute(e["timestamp"]) for e in entries),
            "seen": sorted(bar_minute(s["timestamp"]) for s in sigs),
        }
    return out


def score_sweep():
    # The S on these 100 cards is spelled `answers.s`, and every row also carries
    # `grade: "none"` -- the page's untouched default. Read it through
    # grade_read.read_grade so the field name can never hide the answer again.
    cards = [r for r in rows(SWEEP) if grade_read.read_grade(r) is not None]
    his_s = [r for r in cards if grade_read.is_s(r)]
    his_no = [r for r in cards if not grade_read.is_s(r)]
    rep = replay({(r["symbol"], r["date"]) for r in cards})

    def fired(r):
        d = rep.get((r["symbol"], r["date"]), {})
        return bool(d.get("fired"))

    tp = [r for r in his_s if fired(r)]
    fp = [r for r in his_no if fired(r)]
    errs = [k for k, v in rep.items() if "error" in v]
    return {
        "set": "probe_s_sweep_2026-08-28 (100 blind cards)",
        "n_cards": len(cards), "n_S": len(his_s), "n_no": len(his_no),
        "fired_on_S": len(tp), "fired_on_no": len(fp),
        "recall_pct": round(len(tp) / len(his_s) * 100, 1) if his_s else 0.0,
        "precision_pct": (round(len(tp) / (len(tp) + len(fp)) * 100, 1)
                          if (tp or fp) else 0.0),
        "unreplayable_days": len(errs),
        "missed_S": sorted(r["card_id"] for r in his_s if not fired(r)),
    }


def score_vetoes():
    cards = [r for r in rows(MASTER)
             if r.get("lane") == "vetoes" and r["answers"].get("grade")]
    rep = replay({(r["symbol"], r["date"]) for r in cards})
    tally = Counter()
    detail = []
    for r in cards:
        # one reader; "none" is his word for a refusal, "no" is this tally's
        g = (grade_read.read_grade(r) or "no").lower()
        g = "no" if g == "none" else g
        d = rep.get((r["symbol"], r["date"]), {})
        his_min = mins(r["et"]) if r.get("et") else None
        near = ([m for m in d.get("fired", []) if abs(m - his_min) <= NEAR]
                if his_min is not None else d.get("fired", []))
        hit = bool(near)
        tally[g] += 1
        tally[g + "_fired"] += int(hit)
        detail.append({"card": r["card_id"], "his_grade": g, "fired": hit,
                       "et": r.get("et"), "error": d.get("error")})
    return {
        "set": "probe_master_2026-08-29 lane=vetoes (40 engine vetoes he graded)",
        "n_cards": len(cards),
        "his_S": tally["s"], "fired_on_his_S": tally["s_fired"],
        "his_A": tally["a"], "fired_on_his_A": tally["a_fired"],
        "his_C": tally["c"], "fired_on_his_C": tally["c_fired"],
        "his_no": tally["no"], "fired_on_his_no": tally["no_fired"],
        "recall_SA_pct": (round((tally["s_fired"] + tally["a_fired"])
                                / max(1, tally["s"] + tally["a"]) * 100, 1)),
        "false_fire_pct": round(tally["no_fired"] / max(1, tally["no"]) * 100, 1),
        "detail": detail,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "t0_heldout_recall.json"))
    a = ap.parse_args()
    res = {"sweep": score_sweep(), "vetoes": score_vetoes()}
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "detail"}
                      for k, v in res.items()}, indent=2))
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print("wrote " + a.out)


if __name__ == "__main__":
    main()
