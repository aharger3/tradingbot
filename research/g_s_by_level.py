"""g_s_by_level.py -- Austin's S marks split by the LEVEL named, priced against
the honest committed book.

Austin: "REALLY ANALYZE MY S MARKS." He named PMH/PML and PDH/PDL as his top
six level types (with ORH/ORL) -- this checks that against his own marks and
against the engine's own EV/R per level.

Two views, joined on (symbol, date, entry_i):

  1. HIS S-RATE PER LEVEL -- of every mark row that carries a resolvable
     level (i.e. its (symbol, date, entry_i) matches a candidate in the
     committed book), what fraction did he grade S? This is a per-candidate
     read, not a per-day read: marks_pool.canonical_pool() collapses to one
     opinion per symbol-day, which throws away exactly the entry_i-level
     granularity this question needs, so this script re-derives grade
     opinions from the raw mark rows directly (same precedence rule
     marks_pool.row_grade uses) and keys them by (symbol, date, entry_i)
     instead of (symbol, date).

  2. ENGINE EV/R PER LEVEL -- ev_r_scoreboard() on the book's own
     traded==True rows, grouped by `level`, gated on min_risk_floor exactly
     like every other number in this repo (research/omen_metrics.py).

Every count is reported with its denominator. Levels with n<20 are flagged
low-n and must not be read as a verdict.

    python research/g_s_by_level.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd            # noqa: E402
import marks_pool as mp            # noqa: E402
import omen_metrics as om          # noqa: E402

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")

# level names as they appear on the committed book -> the six-plus-other
# taxonomy the question asks for (PDH/PDL/PMH/PML/ORH/ORL/pivot/other)
LEVEL_CANON = {
    "PDH": "PDH", "PDL": "PDL",
    "PMH": "PMH", "PML": "PML",
    "OR high": "ORH", "OR low": "ORL",
    "pivot high": "pivot high", "pivot low": "pivot low",
    "other": "other",
}

_ID_TAIL_RE = re.compile(r"_(\d+)$")


def _row_entry_i(row):
    """entry_i off the row itself, or parsed off its id/card_id's numeric tail."""
    ei = row.get("entry_i")
    if ei is not None:
        try:
            return int(ei)
        except (TypeError, ValueError):
            pass
    ident = row.get("card_id") or row.get("id") or row.get("card")
    if ident:
        m = _ID_TAIL_RE.search(str(ident))
        if m:
            return int(m.group(1))
    return None


def raw_candidate_opinions():
    """Every (symbol, date, entry_i) -> best grade, re-derived from the raw
    mark rows (not the day-collapsed canonical_pool), same precedence rule
    marks_pool.row_grade applies. Rows with no resolvable entry_i are
    counted separately and reported, not silently dropped."""
    by_key = defaultdict(list)   # (sym,date,entry_i) -> [grade,...]
    n_rows_total = 0
    n_rows_no_entry_i = 0
    for path in bd.mark_sources():
        for row in bd._rows(path):
            key = bd._judgement_key(row)
            if not key:
                continue
            g = mp.row_grade(row)
            if g is None:
                continue
            n_rows_total += 1
            symbol, date = key.split("_", 1)
            ei = _row_entry_i(row)
            if ei is None:
                n_rows_no_entry_i += 1
                continue
            by_key[(symbol, date, ei)].append(g)

    _RANK = {"S": 0, "A": 1, "B": 2, "C": 3, "none": 4, "X": 4}
    resolved = {}
    for k, grades in by_key.items():
        best = min(grades, key=lambda g: _RANK.get(g, 5))
        resolved[k] = best
    return resolved, n_rows_total, n_rows_no_entry_i


def load_book():
    d = json.load(open(BOOK_PATH, encoding="utf-8"))
    return d["trades"], d.get("meta", {})


def book_candidate_level_index(trades):
    """(symbol, date, entry_i) -> canonical level, for EVERY candidate the
    book ever produced (fired or not) -- marks are graded on cards drawn
    from the full candidate list, not only the traded subset."""
    idx = {}
    for t in trades:
        k = (t.get("sym"), t.get("day"), t.get("entry_i"))
        lvl = LEVEL_CANON.get(t.get("level"), "other")
        idx[k] = lvl
    return idx


def section_his_s_rate_per_level(resolved_opinions, level_idx):
    matched = 0
    unmatched = 0
    per_level_total = Counter()
    per_level_s = Counter()
    for (sym, date, ei), grade in resolved_opinions.items():
        lvl = level_idx.get((sym, date, ei))
        if lvl is None:
            unmatched += 1
            continue
        matched += 1
        per_level_total[lvl] += 1
        if grade == "S":
            per_level_s[lvl] += 1

    print("\n=== 1. HIS S-RATE PER LEVEL (per-candidate, entry_i-matched to book) ===")
    print("mark rows carrying a resolvable grade: n=%d (of those, %d had no "
          "entry_i and are excluded from this view, reported separately)"
          % (len(resolved_opinions) , 0))
    print("of graded candidates, matched to a book candidate at the same "
          "(symbol,date,entry_i): n=%d matched, n=%d unmatched (no candidate "
          "in the book at that entry_i -- stale deck / off-by-one / bar "
          "reindex between snapshots)" % (matched, unmatched))
    print()
    rows = []
    for lvl in sorted(per_level_total, key=lambda l: -per_level_total[l]):
        tot = per_level_total[lvl]
        s = per_level_s[lvl]
        rate = s / tot if tot else None
        rows.append((lvl, tot, s, rate))
    print("%-12s %8s %6s %9s" % ("level", "n_graded", "n_S", "S_rate"))
    for lvl, tot, s, rate in rows:
        flag = "  (low n)" if tot < 20 else ""
        print("%-12s %8d %6d %8.1f%%%s" % (lvl, tot, s, rate * 100, flag))
    return rows


def section_engine_ev_per_level(trades):
    print("\n=== 2. ENGINE EV/R PER LEVEL (traded==True book rows, size-gated) ===")
    traded = [t for t in trades if t.get("traded") is True]
    print("traded==True rows in book: n=%d" % len(traded))
    by_level = defaultdict(list)
    for t in traded:
        lvl = LEVEL_CANON.get(t.get("level"), "other")
        by_level[lvl].append(t)

    print("%-12s %8s %8s %8s %8s %8s %10s %8s %6s" % (
        "level", "n", "n_drop", "ev_r", "win%", "avgW_R", "avgL_R", "PF", "grn"))
    out = []
    for lvl in sorted(by_level, key=lambda l: -len(by_level[l])):
        sc = om.ev_r_scoreboard(by_level[lvl])
        out.append((lvl, sc))
        pf = sc["profit_factor"]
        pf_s = ("%.2f" % pf) if isinstance(pf, float) else str(pf)
        print("%-12s %8d %8d %8.4f %7.1f%% %8.3f %8.3f %10s %8s" % (
            lvl, sc["n"], sc["n_dropped_size_gate"], sc["ev_r"] or 0.0,
            (sc["win_rate"] or 0.0) * 100, sc["avg_win_R"] or 0.0,
            sc["avg_loss_R"] or 0.0, pf_s, sc["months_green"] or "n/a"))
    return out


def section_top_six_check(his_rows, engine_rows):
    print("\n=== 3. HIS CLAIMED TOP SIX (PMH/PML, PDH/PDL) VS HIS OWN MARKS ===")
    top_six = {"PMH", "PML", "PDH", "PDL", "ORH", "ORL"}
    his_by_level = {r[0]: r for r in his_rows}
    eng_by_level = {r[0]: r[1] for r in engine_rows}

    print("%-12s %10s %10s %10s %10s" % (
        "level", "his_S_rate", "n_graded", "engine_ev_r", "n_traded"))
    ranked_by_srate = sorted(
        [r for r in his_rows if r[1] >= 20], key=lambda r: -r[3])
    for lvl, tot, s, rate in ranked_by_srate:
        eng = eng_by_level.get(lvl)
        ev = eng["ev_r"] if eng else None
        n_tr = eng["n"] if eng else 0
        tag = " <- claimed top six" if lvl in top_six else ""
        print("%-12s %9.1f%% %10d %10s %10d%s" % (
            lvl, rate * 100, tot, ("%.4f" % ev) if ev is not None else "n/a",
            n_tr, tag))

    print("\nranked by ENGINE ev_r (traded rows, n>=20):")
    ranked_by_ev = sorted(
        [r for r in engine_rows if r[1]["n"] >= 20],
        key=lambda r: -(r[1]["ev_r"] or -99))
    for lvl, sc in ranked_by_ev:
        tag = " <- claimed top six" if lvl in top_six else ""
        his = his_by_level.get(lvl)
        his_rate = his[3] if his else None
        print("%-12s ev_r=%8.4f n=%5d  his_S_rate=%s%s" % (
            lvl, sc["ev_r"], sc["n"],
            ("%.1f%%" % (his_rate * 100)) if his_rate is not None else "n/a",
            tag))


def main():
    trades, meta = load_book()
    print("book: %s, meta=%s" % (BOOK_PATH, json.dumps(meta)[:200]))
    print("min_risk_floor source: %s" % om.MIN_RISK_FLOOR_SOURCE)

    resolved_opinions, n_rows_total, n_rows_no_entry_i = raw_candidate_opinions()
    print("\nraw mark rows carrying a resolvable grade: n=%d" % n_rows_total)
    print("of those, no entry_i field or parseable id tail: n=%d (excluded "
          "from the per-candidate level view)" % n_rows_no_entry_i)
    print("distinct (symbol,date,entry_i) candidates with a resolved grade: n=%d"
          % len(resolved_opinions))
    print("grade distribution over those candidates: %s"
          % dict(Counter(resolved_opinions.values())))

    level_idx = book_candidate_level_index(trades)

    his_rows = section_his_s_rate_per_level(resolved_opinions, level_idx)
    engine_rows = section_engine_ev_per_level(trades)
    section_top_six_check(his_rows, engine_rows)


if __name__ == "__main__":
    main()
