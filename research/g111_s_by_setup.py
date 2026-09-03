"""g111_s_by_setup.py -- split the 347 S symbol-days by setup family.

Austin, 2026-09-03: "REALLY ANALYZE MY S MARKS." Two independent lenses,
neither substituting for the other:

  1. CLAIMED family -- Austin's own free-text "setup" field, present only in
     austin_marks_v7.jsonl (479 rows, 284 non-blank). This is what HE says he
     was looking at when he graded the card.
  2. STRUCTURAL family -- the engine's own setup_label on its first traded
     candidate of that symbol-day, from the committed book
     (bt2y_trades_retest_on.json). This is what the ENGINE says fired.

For each family: n_S, n_refusal (canonical grade "none"), his S-rate among
rows he tagged with that claimed setup (claimed lens only, since only v7
carries the tag), and engine EV/R on the book's trades for those symbol-days
(ev_r_scoreboard, size-gated on signal_runner.min_risk_floor per CLAUDE.md).

Read-only. No mark file, no engine file touched.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import marks_pool as mp
import omen_metrics as om

FAMILIES = ["break_and_retest", "one_candle_rule", "br_ocr_confluence",
            "order_block", "reentry_84", "other"]


def normalize_claimed(raw):
    if raw is None:
        return None
    text = raw.strip().lower()
    if text in ("", "none"):
        return None
    has_br = bool(re.search(r"break\s*&?\s*retest|break_and_retest|\bbr\b", text))
    has_ocr = bool(re.search(r"\bocr\b|one candle rule|one_candle_rule", text))
    has_84 = bool(re.search(r"84", text))
    has_ob = bool(re.search(r"order block", text))
    if has_br and has_ocr:
        return "br_ocr_confluence"
    if has_ob:
        return "order_block"
    if has_84:
        return "reentry_84"
    if has_br:
        return "break_and_retest"
    if has_ocr:
        return "one_candle_rule"
    return "other"


def load_claimed_setup():
    path = os.path.join(HERE, "austin_marks_v7.jsonl")
    out = {}
    raw_out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            sym = row.get("symbol")
            day = row.get("day")
            if not (sym and day):
                continue
            key = "%s_%s" % (sym, day)
            fam = normalize_claimed(row.get("setup"))
            if fam is None:
                continue
            out[key] = fam
            raw_out[key] = row.get("setup")
    return out, raw_out


STRUCT_LABEL_TO_FAMILY = {
    "break-and-retest": "break_and_retest",
    "one-candle-rule": "one_candle_rule",
    "BR+OCR": "br_ocr_confluence",
    "other (84% re-entry)": "reentry_84",
}


def load_book():
    with open(om.BOOK_PATH, encoding="utf-8") as f:
        d = json.load(f)
    return d["trades"]


def first_traded_per_day(trades):
    by_day = defaultdict(list)
    for t in trades:
        if not t.get("traded"):
            continue
        key = "%s_%s" % (t["sym"], t["day"])
        by_day[key].append(t)
    out = {}
    for key, rows in by_day.items():
        rows.sort(key=lambda r: (r.get("et") or "", r.get("entry_i") or 0))
        out[key] = rows[0]
    return out


def main():
    pool = mp.canonical_pool()
    s_days = {k for k, v in pool.items() if v.grade == "S"}
    none_days = {k for k, v in pool.items() if v.grade == "none"}
    print("canonical pool: %d symbol-days, %d S, %d none(refusal)" %
          (len(pool), len(s_days), len(none_days)))

    claimed, claimed_raw = load_claimed_setup()
    print("v7 claimed-setup coverage: %d symbol-days carry a non-blank setup tag" %
          len(claimed))

    trades = load_book()
    first_traded = first_traded_per_day(trades)
    print("book: %d rows, %d symbol-days have >=1 traded candidate" %
          (len(trades), len(first_traded)))

    print("")
    print("=== LENS 1: STRUCTURAL family (engine's own setup_label), all S days ===")
    struct_bucket = defaultdict(list)
    no_traded_candidate = []
    for key in s_days:
        row = first_traded.get(key)
        if row is None:
            no_traded_candidate.append(key)
            continue
        fam = STRUCT_LABEL_TO_FAMILY.get(row.get("setup_label"), "other")
        struct_bucket[fam].append(key)
    print("S days with NO traded candidate in the book: %d / %d"
          % (len(no_traded_candidate), len(s_days)))

    for fam in ["break_and_retest", "one_candle_rule", "br_ocr_confluence", "reentry_84", "other"]:
        keys = struct_bucket.get(fam, [])
        n_s = len(keys)
        keyset = set(keys)
        book_rows = [t for t in trades if t.get("traded") and ("%s_%s" % (t["sym"], t["day"])) in keyset]
        sc = om.ev_r_scoreboard(book_rows, sessions=n_s if n_s else None)
        print("  %-20s n_S=%3d  n_trades=%3d(n_dropped_gate=%d)  ev_r=%7s  win=%s  avg_win_R=%s  avg_loss_R=%s  yearly_R=%s"
              % (fam, n_s, sc["n"], sc["n_dropped_size_gate"],
                 ("%.4f" % sc["ev_r"]) if sc["ev_r"] is not None else "None",
                 ("%.3f" % sc["win_rate"]) if sc["win_rate"] is not None else "None",
                 ("%.3f" % sc["avg_win_R"]) if sc["avg_win_R"] is not None else "None",
                 ("%.3f" % sc["avg_loss_R"]) if sc["avg_loss_R"] is not None else "None",
                 ("%.2f" % sc["yearly_R"]) if sc["yearly_R"] is not None else "None"))

    print("")
    print("=== LENS 2: CLAIMED family (his own 'setup' text field, v7 only, n=%d tagged) ===" % len(claimed))
    claimed_grade_bucket = defaultdict(list)
    untagged_in_pool = 0
    for key, fam in claimed.items():
        entry = pool.get(key)
        if entry is None:
            untagged_in_pool += 1
            continue
        claimed_grade_bucket[fam].append((key, entry.grade))
    print("claimed-tagged symbol-days not found in canonical_pool: %d" % untagged_in_pool)

    print("%-20s %6s %6s %6s %6s %8s | %8s %6s %8s %8s" %
          ("family", "n_tag", "n_S", "n_none", "n_X", "S-rate", "ev_r", "n_tr", "win", "yearlyR"))
    claimed_summary = []
    for fam in ["break_and_retest", "one_candle_rule", "br_ocr_confluence", "order_block", "reentry_84", "other"]:
        items = claimed_grade_bucket.get(fam, [])
        n_tag = len(items)
        grades = Counter(g for _, g in items)
        n_s = grades.get("S", 0)
        n_none = grades.get("none", 0)
        n_x = grades.get("X", 0)
        s_rate = (n_s / n_tag) if n_tag else None
        s_keys = set(k for k, g in items if g == "S")
        book_rows = [t for t in trades if t.get("traded") and ("%s_%s" % (t["sym"], t["day"])) in s_keys]
        sc = om.ev_r_scoreboard(book_rows, sessions=len(s_keys) if s_keys else None)
        claimed_summary.append((fam, n_tag, n_s, n_none, n_x, s_rate, sc))
        print("%-20s %6d %6d %6d %6d %8s | %8s %6d %6s %8s" % (
            fam, n_tag, n_s, n_none, n_x,
            ("%.1f%%" % (s_rate * 100)) if s_rate is not None else "n/a",
            ("%.4f" % sc["ev_r"]) if sc["ev_r"] is not None else "None",
            sc["n"],
            ("%.3f" % sc["win_rate"]) if sc["win_rate"] is not None else "None",
            ("%.2f" % sc["yearly_R"]) if sc["yearly_R"] is not None else "None"))

    print("")
    print("full grade breakdown per claimed family (n_tag denominators):")
    for fam in ["break_and_retest", "one_candle_rule", "br_ocr_confluence", "order_block", "reentry_84", "other"]:
        items = claimed_grade_bucket.get(fam, [])
        grades = Counter(g for _, g in items)
        print("  %-20s %s  (n=%d)" % (fam, dict(grades), len(items)))

    out = {
        "pool_total": len(pool),
        "s_total": len(s_days),
        "none_total": len(none_days),
        "structural_lens": {fam: {"n_S": len(struct_bucket.get(fam, []))}
                             for fam in ["break_and_retest", "one_candle_rule",
                                         "br_ocr_confluence", "reentry_84", "other"]},
        "s_days_no_traded_candidate": len(no_traded_candidate),
        "claimed_lens": [{"family": f, "n_tag": nt, "n_S": ns, "n_none": nn, "n_X": nx,
                           "s_rate": sr, "ev_r": sc["ev_r"], "n_trades": sc["n"],
                           "win_rate": sc["win_rate"], "yearly_R": sc["yearly_R"]}
                          for f, nt, ns, nn, nx, sr, sc in claimed_summary],
    }
    out_path = os.path.join(HERE, "g111_s_by_setup.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("")
    print("wrote " + out_path)


if __name__ == "__main__":
    main()
