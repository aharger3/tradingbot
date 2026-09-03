"""g99_s_by_time.py -- AREA: s_by_time.

Split every S mark and every refusal ("none") by the entry minute Austin
named (or, when he did not name one, the card's own time) into 5-minute bins
covering the 09:30-11:00 session. Report his S-rate per bin next to the
engine's honest-book EV/R per bin (research/bt2y_trades_retest_on.json,
size-gated on signal_runner.min_risk_floor via research/omen_metrics.py).

R3: "We have to measure best s trades based on time which is most important
factor" -- this is that measurement, run against HIS labels, not just P&L.

Read-only. No mark file, no book file is written.

    python research/g99_s_by_time.py
    python research/g99_s_by_time.py --out research/_g99_s_by_time.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd          # noqa: E402
import grade_read as gr          # noqa: E402
import omen_metrics as om        # noqa: E402

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")

BIN_START_MIN = 9 * 60 + 30   # 09:30
BIN_END_MIN = 11 * 60         # 11:00
BIN_WIDTH = 5

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})")

# fields to try, in order, when the row does not carry a usable entry_minute
_TIME_FALLBACK_FIELDS = ("entry_t", "entry_time", "et", "entry_et", "setup_et", "eng_et")


def _parse_hhmm(text):
    """'9:37', '09:37:00', '9:37 A trade ...' -> minutes-since-midnight, or None."""
    if text is None:
        return None
    m = _TIME_RE.match(str(text).strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h < 6 or h > 20 or mi > 59:
        return None
    return h * 60 + mi


def _row_time_minutes(row):
    """Best time for this row: his named entry_minute first, else a card-time
    fallback field, else None (unbucketable)."""
    if row.get("entry_minute_given") and row.get("entry_minute"):
        mins = _parse_hhmm(row["entry_minute"])
        if mins is not None:
            return mins, "entry_minute(named)"
    # entry_minute may be present without the _given flag on older corpora
    mins = _parse_hhmm(row.get("entry_minute"))
    if mins is not None:
        return mins, "entry_minute(named)"
    for field in _TIME_FALLBACK_FIELDS:
        mins = _parse_hhmm(row.get(field))
        if mins is not None:
            return mins, f"{field}(card)"
    return None, None


def _bin_label(minutes):
    if minutes is None:
        return None
    clipped = min(max(minutes, BIN_START_MIN), BIN_END_MIN - 1)
    idx = (clipped - BIN_START_MIN) // BIN_WIDTH
    start = BIN_START_MIN + idx * BIN_WIDTH
    return f"{start // 60:02d}:{start % 60:02d}"


def _all_bin_labels():
    labels = []
    m = BIN_START_MIN
    while m < BIN_END_MIN:
        labels.append(f"{m // 60:02d}:{m % 60:02d}")
        m += BIN_WIDTH
    return labels


# --------------------------------------------------------------------- marks

def collect_mark_rows():
    """Every row across every mark source carrying S or refusal (none), with
    a usable time. Returns list of dicts: symbol, date, grade, minute, bin,
    time_source, card_id, source."""
    out = []
    n_seen = 0
    n_graded_s_or_none = 0
    n_no_time = 0
    for path in bd.mark_sources():
        base = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
        except OSError:
            continue
        if not raw.strip():
            continue
        # austin_verdicts.json is a JSON list, not jsonl -- skip, it carries
        # no time field per the g99 field survey and would need special
        # handling; every other source is jsonl.
        if path.endswith(".json") and not path.endswith(".jsonl"):
            continue
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            n_seen += 1
            grade = gr.read_grade(row)
            if grade not in ("S", "none"):
                continue
            n_graded_s_or_none += 1
            minutes, tsrc = _row_time_minutes(row)
            if minutes is None:
                n_no_time += 1
                continue
            key = bd._judgement_key(row) if hasattr(bd, "_judgement_key") else None
            symbol, date = None, None
            if key and "_" in key:
                symbol, date = key.rsplit("_", 1)
            out.append({
                "symbol": symbol or row.get("symbol"),
                "date": date or row.get("date") or row.get("day"),
                "grade": grade,
                "minute": minutes,
                "bin": _bin_label(minutes),
                "time_source": tsrc,
                "card_id": row.get("card_id"),
                "source": base,
            })
    return out, {"n_rows_seen": n_seen, "n_s_or_none": n_graded_s_or_none, "n_no_time": n_no_time}


# --------------------------------------------------------------------- book

def load_book():
    with open(BOOK_PATH, encoding="utf-8") as f:
        return json.load(f)


def bin_book_rows(book):
    """Every fired-and-traded book row bucketed by its `et` (entry minute)."""
    buckets = defaultdict(list)
    n_traded = 0
    n_no_et = 0
    for t in book["trades"]:
        if not t.get("traded"):
            continue
        n_traded += 1
        minutes = _parse_hhmm(t.get("et"))
        if minutes is None:
            n_no_et += 1
            continue
        buckets[_bin_label(minutes)].append(t)
    return buckets, {"n_traded": n_traded, "n_no_et": n_no_et}


# --------------------------------------------------------------------- main

def build_report():
    mark_rows, mark_meta = collect_mark_rows()
    book = load_book()
    book_buckets, book_meta = bin_book_rows(book)

    by_bin_marks = defaultdict(lambda: {"S": 0, "none": 0})
    for r in mark_rows:
        by_bin_marks[r["bin"]][r["grade"]] += 1

    rows = []
    for label in _all_bin_labels():
        s = by_bin_marks[label]["S"]
        refuse = by_bin_marks[label]["none"]
        total_marks = s + refuse
        s_rate = (s / total_marks) if total_marks else None

        book_rows = book_buckets.get(label, [])
        scoreboard = om.ev_r_scoreboard(book_rows, sessions=book["meta"]["sessions"])

        rows.append({
            "bin": label,
            "his_S": s,
            "his_refusal": refuse,
            "his_total_marks": total_marks,
            "his_S_rate": round(s_rate, 4) if s_rate is not None else None,
            "engine_n_fired_traded": len(book_rows),
            "engine_n_scored": scoreboard["n"],
            "engine_n_dropped_size_gate": scoreboard["n_dropped_size_gate"],
            "engine_ev_r": round(scoreboard["ev_r"], 4) if scoreboard["ev_r"] is not None else None,
            "engine_win_rate": round(scoreboard["win_rate"], 4) if scoreboard["win_rate"] is not None else None,
        })

    total_s = sum(r["his_S"] for r in rows)
    total_refuse = sum(r["his_refusal"] for r in rows)

    return {
        "meta": {
            "mark_collection": mark_meta,
            "book_collection": book_meta,
            "book_sessions": book["meta"]["sessions"],
            "book_traded_total": book_meta["n_traded"],
            "n_S_bucketed": total_s,
            "n_refusal_bucketed": total_refuse,
            "n_S_or_refusal_total": mark_meta["n_s_or_none"],
            "n_S_or_refusal_no_time": mark_meta["n_no_time"],
        },
        "bins": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    report = build_report()
    m = report["meta"]
    print(f"Mark rows scanned: {m['mark_collection']['n_rows_seen']}")
    print(f"S or refusal ('none') rows: {m['n_S_or_refusal_total']} "
          f"(S={m['n_S_bucketed']}, refusal={m['n_refusal_bucketed']}, "
          f"no usable time={m['n_S_or_refusal_no_time']})")
    print(f"Book: {m['book_sessions']} sessions, {m['book_traded_total']} fired-and-traded rows\n")

    print(f"{'bin':>6} | {'his S':>6} {'refuse':>7} {'S-rate':>7} | "
          f"{'eng n':>6} {'eng gated':>10} {'ev_r':>8} {'win%':>7}")
    print("-" * 72)
    for r in report["bins"]:
        s_rate = f"{r['his_S_rate']*100:5.1f}%" if r["his_S_rate"] is not None else "   n/a"
        ev_r = f"{r['engine_ev_r']:8.4f}" if r["engine_ev_r"] is not None else "     n/a"
        win = f"{r['engine_win_rate']*100:6.1f}%" if r["engine_win_rate"] is not None else "    n/a"
        print(f"{r['bin']:>6} | {r['his_S']:6d} {r['his_refusal']:7d} {s_rate:>7} | "
              f"{r['engine_n_fired_traded']:6d} {r['engine_n_scored']:10d} {ev_r} {win}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
