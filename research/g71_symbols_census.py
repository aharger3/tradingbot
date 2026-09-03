"""G71/symbols -- per-symbol census: judged supply, S rate, book money, liquidity, fresh supply.

    python research/g71_symbols_census.py            # the ranked table
    python research/g71_symbols_census.py --json OUT

Reads only. Every corpus is opened read-only; nothing is written except the
optional --json dump.

Sources
  marks      research/build_deck.py::mark_sources()  (THE no-repeat corpus list)
  book       research/bt2y_trades.json               (post-T0 2-year book)
  liquidity  data_archive/<SYM>/<DAY>.csv            09:30-11:00 close*volume
  supply     build_deck.seen_card_ids() = judged | served
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd
from universe import CORE_SYMBOLS, EXPERIMENTAL_SYMBOLS, POOL_OF, MIN_SAMPLE_N

ARCHIVE = os.path.join(ROOT, "data_archive")
BOOK = os.path.join(HERE, "bt2y_trades.json")

_GRADE_KEYS = bd._GRADE_KEYS


def _first(ans, key):
    v = ans.get(key)
    if isinstance(v, list):
        v = v[0] if v else None
    return str(v).strip().upper() if v else None


def grade_of(row):
    """Austin's grade for this symbol-day, S/A/C/NONE/X/NO_S, or None.

    The probe pages do NOT all write the grade into ``grade``. Three schemas:

      probe_s_sweep_2026-08-28.jsonl  grade:"none" ALWAYS, the judgement is
          ``answers.s == ["s"|"no"]``. Counting the ``grade`` field there scores
          all 100 cards of the held-out S sweep as a refusal and loses every one
          of the 34 S days the recall gate is measured on.
      probe_master_homework / omen_test1  grade AND answers agree.
      probe_head2head  ``answers.take == ["no"]`` with grade "none".

    So the answers dict outranks the grade field wherever it carries a verdict.
    """
    ans = row.get("answers")
    if isinstance(ans, dict) and ans:
        for k in ("grade", "your_grade"):
            v = _first(ans, k)
            if v:
                return v
        v = _first(ans, "s")
        if v:
            return "S" if v in ("S", "YES", "Y") else "NO_S"
        v = _first(ans, "take")
        if v:
            return "NONE" if v in ("NO", "N") else "S"
    for k in _GRADE_KEYS:
        v = str(row.get(k, "") or "").strip()
        if v:
            return v.upper()
    if row.get("_no_trade"):
        return "NONE"
    return None


# ---------------------------------------------------------------- 1. marks
def marks_census():
    """symbol -> {grade: set(days)}. One symbol-day counted once; a later
    non-empty grade overwrites an earlier one, matching build_deck's union."""
    day_grade = {}
    per_source = {}
    for path in bd.mark_sources():
        n = 0
        for row in bd._rows(path):
            key = bd._judgement_key(row)
            if not key:
                continue
            n += 1
            g = grade_of(row)
            if key not in day_grade or (g and not day_grade[key]):
                day_grade[key] = g
            elif g:
                day_grade[key] = g
        per_source[os.path.relpath(path, ROOT)] = n
    out = defaultdict(lambda: defaultdict(set))
    for key, g in day_grade.items():
        sym, _, day = key.rpartition("_")
        out[sym]["ALL"].add(day)
        out[sym][g or "UNGRADED_ANSWER"].add(day)
    return out, per_source, day_grade


# ---------------------------------------------------------------- 2. book
def book_census():
    b = json.load(open(BOOK, encoding="utf-8"))
    meta = b["meta"]
    per = defaultdict(lambda: {"sig": 0, "r": [], "wins": 0, "stop_pct": [],
                               "drange_pct": [], "bars": [], "sgrade_S": 0,
                               "grade_Aplus": 0, "days": set()})
    fired = defaultdict(set)      # (sym) -> days the engine produced ANY signal
    nonx = defaultdict(set)       # (sym) -> days it produced a non-X grade
    trd = defaultdict(set)        # (sym) -> days a trade was actually taken
    for t in b["trades"]:
        s = per[t["sym"]]
        fired[t["sym"]].add(t["day"])
        if t.get("grade") != "X":
            nonx[t["sym"]].add(t["day"])
        if t.get("traded"):
            trd[t["sym"]].add(t["day"])
        s["sig"] += 1
        s["days"].add(t["day"])
        if t.get("sgrade") == "S":
            s["sgrade_S"] += 1
        if t.get("grade") == "A+":
            s["grade_Aplus"] += 1
        if t.get("traded"):
            s["r"].append(t["r"])
            if t["r"] > 0:
                s["wins"] += 1
            s["stop_pct"].append(t["stop_pct"])
            s["bars"].append(t["bars"])
            if t.get("entry"):
                s["drange_pct"].append(100.0 * t.get("drange", 0.0) / t["entry"])
    return meta, per, fired, nonx, trd


# ------------------------------------------------------------ 3. liquidity
def window_dollar_volume(sym, n_days=120):
    d = os.path.join(ARCHIVE, sym)
    if not os.path.isdir(d):
        return None, None, 0
    files = sorted(f for f in os.listdir(d) if f.endswith(".csv"))[-n_days:]
    dv, rng = [], []
    for f in files:
        tot = 0.0
        hi = lo = px = None
        with open(os.path.join(d, f), newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                t = row["Datetime"][11:16]
                if not ("09:30" <= t < "11:00"):
                    continue
                try:
                    c = float(row["Close"])
                    v = float(row["Volume"])
                    h = float(row["High"])
                    lw = float(row["Low"])
                except (TypeError, ValueError):
                    continue
                tot += c * v
                hi = h if hi is None else max(hi, h)
                lo = lw if lo is None else min(lo, lw)
                px = c
        if tot > 0:
            dv.append(tot)
        if hi and lo and px:
            rng.append(100.0 * (hi - lo) / px)
    return (statistics.median(dv) if dv else None,
            statistics.median(rng) if rng else None, len(files))


# --------------------------------------------------------------- 4. supply
def supply_census():
    seen = bd.seen_card_ids()
    judged = bd.marked_card_ids()
    total = defaultdict(int)
    seen_n = defaultdict(int)
    judged_n = defaultdict(int)
    for sym in sorted(os.listdir(ARCHIVE)):
        d = os.path.join(ARCHIVE, sym)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".csv"):
                continue
            key = "%s_%s" % (sym, f[:-4])
            total[sym] += 1
            if key in seen:
                seen_n[sym] += 1
            if key in judged:
                judged_n[sym] += 1
    return total, seen_n, judged_n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--liq-days", type=int, default=120)
    a = ap.parse_args()

    marks, per_source, _ = marks_census()
    meta, book, fired, nonx, trd = book_census()
    total, seen_n, judged_n = supply_census()
    lo, hi = meta["first"], meta["last"]

    syms = sorted(set(list(marks) + list(book) + list(total)))
    rows = []
    for s in syms:
        m = marks.get(s, {})
        graded = len(m.get("ALL", ()))
        nS = len(m.get("S", ()))
        b = book.get(s)
        r = b["r"] if b else []
        dv, rng, _n = window_dollar_volume(s, a.liq_days)
        # engine recall on HIS S days, restricted to the book's own window
        s_in_win = {d for d in m.get("S", ()) if lo <= d <= hi}
        n_win = len(s_in_win)
        rec_fire = len(s_in_win & fired.get(s, set()))
        rec_nonx = len(s_in_win & nonx.get(s, set()))
        rec_trd = len(s_in_win & trd.get(s, set()))
        rows.append({
            "sym": s,
            "pool": POOL_OF.get(s, "-"),
            "tier": ("core" if s in CORE_SYMBOLS else
                     "exp" if s in EXPERIMENTAL_SYMBOLS else "other"),
            "graded_days": graded,
            "S": nS,
            "A": len(m.get("A", ())),
            "C": len(m.get("C", ())),
            "refused": len(m.get("NONE", ())) + len(m.get("X", ())),
            "no_s": len(m.get("NO_S", ())),
            "S_rate": (nS / graded) if graded else None,
            "S_days_in_book_window": n_win,
            "recall_fired": rec_fire,
            "recall_nonX": rec_nonx,
            "recall_traded": rec_trd,
            "signals": b["sig"] if b else 0,
            "traded": len(r),
            "meanR": (sum(r) / len(r)) if r else None,
            "win": (b["wins"] / len(r)) if r else None,
            "sgradeS_sig": b["sgrade_S"] if b else 0,
            "Aplus": b["grade_Aplus"] if b else 0,
            "med_stop_pct": statistics.median(b["stop_pct"]) if r else None,
            "med_drange_pct": (statistics.median(b["drange_pct"])
                               if b and b["drange_pct"] else None),
            "med_bars": statistics.median(b["bars"]) if r else None,
            "med_intraday_range_pct": rng,
            "dollar_vol_930_1100": dv,
            "archive_days": total.get(s, 0),
            "judged_days": judged_n.get(s, 0),
            "seen_days": seen_n.get(s, 0),
            "fresh_days": total.get(s, 0) - seen_n.get(s, 0),
        })

    rows.sort(key=lambda x: -x["graded_days"])
    print("BOOK meta:", json.dumps(meta))
    print("MIN_SAMPLE_N =", MIN_SAMPLE_N)
    print("sym  pool    tier  graded   S   S%   sig  trd    meanR   win%  "
          "stop%  rng%  $vol930-1100  Srec(nonX/fire/n)  arch  seen  fresh")
    for x in rows:
        print("%-5s %-7s %-5s %6d %3d %5s %5d %4d %8s %6s %6s %6s %13s %8s %5d %5d %6d" % (
            x["sym"], x["pool"], x["tier"], x["graded_days"], x["S"],
            ("%.0f%%" % (100 * x["S_rate"])) if x["S_rate"] is not None else "-",
            x["signals"], x["traded"],
            ("%+.4f" % x["meanR"]) if x["meanR"] is not None else "-",
            ("%.1f" % (100 * x["win"])) if x["win"] is not None else "-",
            ("%.3f" % x["med_stop_pct"]) if x["med_stop_pct"] is not None else "-",
            ("%.2f" % x["med_intraday_range_pct"]) if x["med_intraday_range_pct"] else "-",
            ("%.1fM" % (x["dollar_vol_930_1100"] / 1e6)) if x["dollar_vol_930_1100"] else "-",
            "%d/%d/%d" % (x["recall_nonX"], x["recall_fired"], x["S_days_in_book_window"]),
            x["archive_days"], x["seen_days"], x["fresh_days"]))
    print("")
    print("per-source judgement rows:")
    for k, v in sorted(per_source.items(), key=lambda kv: -kv[1]):
        print("  %-62s %5d" % (k, v))
    if a.json:
        json.dump({"meta": meta, "rows": rows, "per_source": per_source},
                  open(a.json, "w", encoding="utf-8"), indent=1)
        print("wrote", a.json)


if __name__ == "__main__":
    main()
