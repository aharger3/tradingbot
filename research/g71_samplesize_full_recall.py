"""SUPERSEDED 2026-08-29 by research/g72_recall278_paired.py (key recall278).

Two reasons, both fatal to the numbers this file wrote:
  1. It scored through t4_engine_recall.CaptureRunner._route while that was a
     hand-rolled copy of the shipped router, so its `calibration_100_card_sweep`
     recall of 23/34 was the copy's answer, not the engine's. The engine's answer
     is 22/34. The copy is gone; re-running this file now gives different numbers
     from the ones quoted in research/g71_samplesize.md and g71_ssverify.md.
  2. Its corpus-wide read is unpaired and single-arm. Recall comparisons must run
     PAIRED across all 278 bar-backed S days -- g72_recall278_paired.py does that
     and reports McNemar plus the Wilson interval.

Kept, unedited below, so the g71 reports that cite it still resolve. Do not
re-run it to produce a published number.
"""
"""G71/samplesize -- day-level S recall over the WHOLE judged corpus, not 34 cards.

Scores every Austin-graded symbol-day that has archived bars exactly the way
research/t0_heldout_recall.py::score_sweep scores its 100: replay the day with
research.t4_engine_recall.run_day (the shipped harness, untouched) and count the
card as a hit if the engine takes ANY entry that day.

The 34-card sweep is re-scored inside the same process so the corpus-wide number
is calibrated against the published held-out figure.

Read-only: no mark file is written, no engine file is edited.

Usage: python research/g71_samplesize_full_recall.py --out research/g71_samplesize_full_recall.json
"""
from __future__ import annotations
import argparse, json, os, sys, time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import research.t4_engine_recall as t4  # noqa: E402

AUDIT = os.path.join(HERE, "g71_samplesize_corpus.json")
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")


def top_austin(r):
    for g in ("S", "A", "C", "none"):
        if r["austin"].get(g):
            return g
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g71_samplesize_full_recall.json"))
    a = ap.parse_args()

    audit = json.load(open(AUDIT, encoding="utf-8"))
    rows = [r for r in audit["rows"] if r["bars"] and r["austin"]]
    sweep_keys = set()
    for line in open(SWEEP, encoding="utf-8"):
        line = line.strip()
        if line:
            j = json.loads(line)
            sweep_keys.add("%s_%s" % (j["symbol"], j["date"]))

    t0 = time.time()
    fired = {}
    errs = []
    for i, r in enumerate(rows):
        try:
            ent, sigs, _ = t4.run_day(r["symbol"], r["day"])
        except Exception as e:
            errs.append({"key": r["key"], "error": type(e).__name__ + ": " + str(e)[:120]})
            continue
        if ent is None:
            errs.append({"key": r["key"], "error": "no archived bars"})
            continue
        fired[r["key"]] = {"entries": len(ent), "signals": len(sigs)}
        if i % 100 == 0:
            print("  %d/%d  %.0fs" % (i, len(rows), time.time() - t0), flush=True)
    elapsed = time.time() - t0

    by_grade = defaultdict(lambda: {"n": 0, "fired": 0, "detected": 0})
    for r in rows:
        f = fired.get(r["key"])
        if f is None:
            continue
        g = top_austin(r)
        by_grade[g]["n"] += 1
        by_grade[g]["fired"] += int(f["entries"] > 0)
        by_grade[g]["detected"] += int(f["signals"] > 0)

    def pct(d):
        return {**d,
                "recall_pct": round(d["fired"] / max(1, d["n"]) * 100, 1),
                "detect_pct": round(d["detected"] / max(1, d["n"]) * 100, 1)}

    # calibration: the same scoring restricted to the 100-card blind sweep
    sw = [r for r in rows if r["key"] in sweep_keys]
    sw_s = [r for r in sw if top_austin(r) == "S"]
    sw_no = [r for r in sw if top_austin(r) != "S"]
    tp = sum(1 for r in sw_s if fired.get(r["key"], {}).get("entries"))
    fp = sum(1 for r in sw_no if fired.get(r["key"], {}).get("entries"))

    # corpus-wide precision on the same day-level definition
    all_s = [r for r in rows if top_austin(r) == "S" and r["key"] in fired]
    all_no = [r for r in rows if top_austin(r) == "none" and r["key"] in fired]
    TP = sum(1 for r in all_s if fired[r["key"]]["entries"])
    FP = sum(1 for r in all_no if fired[r["key"]]["entries"])

    out = {
        "replayed_days": len(fired),
        "replay_errors": len(errs),
        "elapsed_sec": round(elapsed, 1),
        "sec_per_day": round(elapsed / max(1, len(fired)), 3),
        "by_austin_grade": {k: pct(v) for k, v in sorted(by_grade.items(), key=lambda kv: str(kv[0]))},
        "calibration_100_card_sweep": {
            "n_cards_replayed": len(sw), "n_S": len(sw_s),
            "fired_on_S": tp, "fired_on_no": fp,
            "recall_pct": round(tp / max(1, len(sw_s)) * 100, 1),
            "precision_pct": round(tp / max(1, tp + fp) * 100, 1),
        },
        "corpus_wide": {
            "S_n": len(all_s), "S_fired": TP,
            "none_n": len(all_no), "none_fired": FP,
            "recall_pct": round(TP / max(1, len(all_s)) * 100, 1),
            "precision_vs_none_pct": round(TP / max(1, TP + FP) * 100, 1),
        },
        "errors": errs[:40],
    }
    print(json.dumps({k: v for k, v in out.items() if k != "errors"}, indent=2))
    json.dump({**out, "fired": fired}, open(a.out, "w", encoding="utf-8"), indent=2)
    print("wrote " + a.out)


if __name__ == "__main__":
    main()
