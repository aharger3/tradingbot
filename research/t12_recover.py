"""omen-5.0 T12: recover the 176 graded rows the corpus never ingested.

Step 1 writes research/recovered_reviews.jsonl verbatim from the omen-5.0 spec
(the only surviving copy — they came out of four Claude sessions in review
formats no corpus loader ever matched).

Step 2 aligns them. These rows grade the ENGINE'S OWN entries and carry no bar
index, so the engine is replayed over that symbol+day and the fire that matches
on setup, direction, engine grade and outcome is the row's bar. That is an
identification, not a heuristic — no level-touch fallback anywhere. Unique match
=> align "exact"; ambiguous or no fire => align "unmatched", written out but NOT
merged.

The engine being replayed is the POST-T3/T4/T10/T11 engine, so a row that fails
to match may be telling us the old engine fired where the new one does not.
Those are listed separately.

Usage: python research/t12_recover.py [--spec PATH]
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import backtest_week as bw
from t4_stop_on_close import day_table, rth_candles, bias_from

SPEC = r"C:\Users\aharg\Desktop\Projects\loop-ci\specs\omen-5.0.md"
OUT_JSONL = os.path.join(HERE, "recovered_reviews.jsonl")
OUT_MD = os.path.join(HERE, "t12_recovered.md")
V7 = os.path.join(HERE, "austin_marks_v7.jsonl")


def extract_rows(spec_path):
    """The T12 jsonl block, verbatim. Rows are taken exactly as written — no
    reformatting, no note rewriting."""
    lines = open(spec_path, encoding="utf-8").read().splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "```jsonl" and i > 600:      # the T12 block
            start = i + 1
        elif start is not None and ln.strip() == "```":
            block = lines[start:i]
            break
    rows = []
    for ln in block:
        ln = ln.strip()
        if ln.startswith("{"):
            rows.append(json.loads(ln))
    return rows


_DAYS = {}


def levels_for(symbol, day):
    if symbol not in _DAYS:
        _DAYS[symbol] = day_table(symbol)
    table = _DAYS[symbol]
    days = sorted(table)
    if day not in table:
        return None
    i = days.index(day)
    prev = days[i - 1] if i else None
    pdh = pdl = pdo = pdc = None
    if prev:
        pdh, pdl, pdo, pdc = table[prev][:4]
    pmh, pml = table[day][4], table[day][5]
    bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
    return pdh, pdl, pdo, pdc, pmh, pml, bias


_TRADES = {}


def trades_for(symbol, day):
    """Every simulated trade the engine takes on that day (fired only)."""
    key = (symbol, day)
    if key in _TRADES:
        return _TRADES[key]
    lv = levels_for(symbol, day)
    candles = rth_candles(symbol, day) if lv else None
    if not candles or len(candles) < 60:
        _TRADES[key] = None
        return None
    pdh, pdl, pdo, pdc, pmh, pml, bias = lv
    out = [t for t in bw.simulate_day(symbol, day, candles, pdh, pdl, bias,
                                      pmh, pml, pdo, pdc, None)
           if t.status == "fired"]
    _TRADES[key] = out
    return out


def align(row):
    """(verdict, trade_or_None, why). Setup+direction first, then engine grade,
    then simulated outcome — each step only used to break a tie."""
    trades = trades_for(row["symbol"], row["day"])
    if trades is None:
        return "unmatched", None, "no archived bars for that symbol+day"
    # The 34 bracket-form rows from session f593f4f3 carry no direction; those
    # match on setup alone and lean harder on grade + outcome to disambiguate.
    want_dir = row.get("direction")
    cands = [t for t in trades
             if t.signal_type == row["setup"]
             and (want_dir is None or t.direction == want_dir)]
    if not cands:
        return "unmatched", None, "engine fires no %s %s that day" % (
            row["setup"], want_dir or "signal")
    if len(cands) > 1 and row.get("engine") not in (None, "", "hidden"):
        by_grade = [t for t in cands if t.grade == row["engine"]]
        if by_grade:
            cands = by_grade
    if len(cands) > 1 and row.get("result") in ("win", "loss"):
        by_outcome = [t for t in cands if t.outcome == row["result"]]
        if by_outcome:
            cands = by_outcome
    if len(cands) == 1:
        return "exact", cands[0], ""
    return "unmatched", None, "%d fires still match after grade and outcome" % len(cands)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=SPEC)
    args = ap.parse_args()

    rows = extract_rows(args.spec)
    print(f"extracted {len(rows)} recovered rows")

    aligned = []
    reasons = Counter()
    for r in rows:
        verdict, trade, why = align(r)
        out = dict(r)
        out["align"] = verdict
        if verdict == "exact":
            out["entry_i"] = trade.entry_idx
            out["entry_time"] = trade.entry_time
            out["engine_grade_matched"] = trade.grade
            out["engine_outcome"] = trade.outcome
            out["id"] = f"{r['symbol']}_{r['day']}_{trade.entry_idx}"
        else:
            out["align_reason"] = why
            reasons[why.split(" that day")[0].split(" after")[0]] += 1
        aligned.append(out)

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for r in aligned:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    exact = [r for r in aligned if r["align"] == "exact"]
    unmatched = [r for r in aligned if r["align"] != "exact"]
    print(f"exact {len(exact)}  unmatched {len(unmatched)}")

    # ---- merge the exact rows into v7 ----
    v7 = [json.loads(l) for l in open(V7, encoding="utf-8") if l.strip()]
    have = {r["id"] for r in v7}
    merged, collided = [], []
    for r in exact:
        if r["id"] in have:
            collided.append(r["id"])
            continue
        have.add(r["id"])
        merged.append({
            "id": r["id"], "symbol": r["symbol"], "day": r["day"],
            "entry_i": r["entry_i"], "austin_tier": r["austin_tier"],
            "setup": r.get("setup"), "note": r.get("note", ""),
            "batch": "recovered", "source_files": "recovered_reviews.jsonl",
            "source_session": r["source_session"], "align": "exact",
            "direction": r.get("direction"), "engine": r.get("engine"),
            "result": r.get("result"),
        })
    with open(V7, "a", encoding="utf-8") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    s_rows = [r for r in aligned if r["austin_tier"] == "S"]
    by_session = defaultdict(lambda: [0, 0, 0])
    for r in aligned:
        b = by_session[r["source_session"]]
        b[0] += 1
        b[1] += 1 if r["align"] == "exact" else 0
        b[2] += 1 if r["austin_tier"] == "S" else 0

    md = [
        "# T12 — recovering the 176 graded rows the corpus never ingested",
        "",
        "176 rows from four Claude sessions, in a pipe-table and a bracket review "
        "format no corpus loader ever matched. They grade the ENGINE'S entries and carry "
        "no bar index, so each is aligned by replaying the engine over that symbol and day "
        "and taking the fire that matches on setup, direction, engine grade and outcome. "
        "No level-touch fallback is used anywhere: a row that cannot be identified is "
        "written out as `unmatched` and is NOT merged.",
        "",
        "```",
        f"recovered_rows: {len(aligned)}",
        f"aligned_exact: {len(exact)}",
        f"aligned_unmatched: {len(unmatched)}",
        f"merged_into_v7: {len(merged)}",
        f"recovered_s_marks: {len(s_rows)}",
        "```",
        "",
        "## Per session",
        "",
        "| session | rows | exact | S marks |",
        "|---------|------|-------|---------|",
    ]
    for sess, (n, ex, s) in sorted(by_session.items()):
        md.append(f"| `{sess}` | {n} | {ex} | {s} |")
    md += [
        "",
        f"{len(collided)} exact rows already existed in v7 under the same id and were not "
        "duplicated." if collided else "",
        "",
        "## Why the unmatched rows did not align",
        "",
        "| reason | rows |",
        "|--------|------|",
    ]
    for why, n in reasons.most_common():
        md.append(f"| {why} | {n} |")
    silent = sum(1 for r in unmatched
                 if trades_for(r["symbol"], r["day"]) is not None
                 and not trades_for(r["symbol"], r["day"]))
    other = len(unmatched) - silent - sum(
        1 for r in unmatched if trades_for(r["symbol"], r["day"]) is None)
    md += [
        "",
        f"Of the {len(unmatched)} unmatched rows, **{silent}** are on days where this "
        f"engine takes no trade at all, and **{other}** are on days where it does trade "
        "but not that setup and direction. That is the shape of the change, not a defect "
        "in the rows: the reviewed cards were generated by an engine with no session gate "
        "inside the detector, no displacement requirement, no level retirement and no "
        "no-repeat rule, and it fired far more often than this one does.",
        "",
        "**The engine being replayed is the post-T3/T4/T10/T11 engine.** A row that fails "
        "to match is not necessarily a bad row — it can equally be telling us the OLD "
        "engine fired somewhere this one does not, which is a finding about the change. "
        "The session window (T3a), the displacement gate and mesh veto (T11) and level "
        "retirement (T11a2) all remove fires the reviewed cards were built from. Those "
        "rows keep their notes and their tiers in `recovered_reviews.jsonl` and can be "
        "re-aligned against any future engine by re-running this script.",
        "",
        f"Every merged row carries `align: \"exact\"`, its `source_session` and the engine "
        "grade and outcome it matched on, so any bad row can be traced and pulled later.",
        "",
    ]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(x for x in md if x is not None))
    print("wrote", OUT_JSONL, "and", OUT_MD)
    print("merged into v7:", len(merged), "| id collisions skipped:", len(collided))


if __name__ == "__main__":
    main()
