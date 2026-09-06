"""l3_referee.py -- independent re-derivation of row L3's number.

REFEREE, not builder. Row L3 (omen-10.0 Phase L) added the flag
`OCR_RETEST_DISPLACEMENT` in commit 90dce640 and reported NO number: the
builder started `research/loop_cycle.py --stage build` in the background and
the process died before it wrote a byte of log. This script exists so the
referee's numbers do not come from `loop_cycle.py` -- the arithmetic below is
written from the spec's definitions, not imported from the thing being graded.

WHAT IS RE-DERIVED, FROM SCRATCH:
  * the core-11 row filter  (loop.json universe.row_filter, `tier == "core"`)
  * the unit `up_to_3_stop_win_or_2loss` -- his day policy, spec 2026-09-05:
    "up to 3 S fires; stop after a win or after 2 losses"
  * $/day, mean R, months green, avg win / avg loss, trades, fires/day
  * the halves split at 2025-09-01 and the no-regression gate on each half
  * `book_stamp.book_id` on the OFF arm vs the configured baseline

WHAT IS IMPORTED: `research.book_stamp.book_id` only -- the fingerprint is a
definition of identity, not a measurement, and re-typing a sha256 recipe would
prove nothing. Every dollar below names its fill (the book's own ENTRY_FILL
stamp: the shipped honest CLOSE fill), its exit (the shipped engine ladder with
the 1R intrabar-touch disaster stop), its unit (above) and its script (this
file). 1R = $1,000.

    python research/l3_referee.py [--off PATH] [--on PATH]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import book_stamp  # noqa: E402  (identity, not arithmetic)

TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"
MIN_TRADES = 30
MIN_MONTHS = 12
MAX_DROP_PCT = 5.0


def load(path):
    path = str(path)
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def core11(rows):
    """loop.json's universe.row_filter, spelled out: tier == "core"."""
    return [r for r in rows if r.get("tier") == "core"]


def day_policy_rows(rows):
    """Up to 3 fires a day; stop after the first win or after the second loss.

    Candidate pool = rows the engine actually traded (status "fired" and
    traded true), plus rows the account-wide two-loss halt already killed
    (status "halted"), so a halt this policy would not itself have reached
    cannot silently delete the rest of the day. Ordered by wall-clock time,
    ties broken by symbol so the order is deterministic.
    """
    byday = {}
    for r in rows:
        fired = r.get("status") == "fired" and r.get("traded")
        if fired or r.get("status") == "halted":
            byday.setdefault(r.get("day"), []).append(r)
    kept = []
    for day in sorted(byday):
        losses = 0
        for n, r in enumerate(sorted(byday[day],
                                     key=lambda x: (x.get("et") or "",
                                                    x.get("sym") or ""))):
            if n >= 3:
                break
            kept.append(r)
            pnl = r.get("pnl", 0.0)
            if pnl > 0:
                break
            if pnl < 0:
                losses += 1
                if losses >= 2:
                    break
    return kept


def figures(unit_rows, n_days):
    if not unit_rows or not n_days:
        return {"trades": 0, "total": 0.0, "per_day": 0.0, "mean_r": 0.0,
                "win_pct": 0.0, "months": 0, "months_green": 0,
                "avg_win": 0.0, "avg_loss": 0.0, "awal": None,
                "fires_per_day": 0.0}
    pnls = [r.get("pnl", 0.0) for r in unit_rows]
    total = sum(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    by_m = {}
    for r in unit_rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r.get("pnl", 0.0)
    aw = sum(wins) / len(wins) if wins else 0.0
    al = abs(sum(losses) / len(losses)) if losses else 0.0
    return {
        "trades": len(unit_rows),
        "total": round(total, 0),
        "per_day": round(total / n_days, 0),
        "mean_r": round(total / len(unit_rows) / RISK, 4),
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1)
                   if (wins or losses) else 0.0,
        "months": len(by_m),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "avg_win": round(aw, 0),
        "avg_loss": round(al, 0),
        "awal": round(aw / al, 3) if al else None,
        "fires_per_day": round(len(unit_rows) / n_days, 3),
    }


def slices(meta, rows):
    """whole / h1 / h2, each already core-11 filtered and unit-reduced."""
    rows = core11(rows)
    days = sorted({r["day"] for r in rows if r.get("day")})
    n_all = meta.get("sessions") or len(days)
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    h1 = [r for r in rows if r.get("day", "") < BOUNDARY]
    h2 = [r for r in rows if r.get("day", "") >= BOUNDARY]
    return {
        "whole": figures(day_policy_rows(rows), n_all),
        "h1": figures(day_policy_rows(h1), n1),
        "h2": figures(day_policy_rows(h2), n2),
    }


def gate_half(before, after):
    """Green months may not fall; $/day may not fall more than 5%. A negative
    baseline reads as "the loss may not get more than 5% worse"."""
    enough = before["trades"] >= MIN_TRADES and before["months"] >= MIN_MONTHS
    if not enough:
        return {"enough": False, "pass": None,
                "why": "not enough: %d trades / %d months"
                       % (before["trades"], before["months"])}
    green_ok = after["months_green"] >= before["months_green"]
    b, a = before["per_day"], after["per_day"]
    floor = b - abs(b) * MAX_DROP_PCT / 100.0
    money_ok = a >= floor
    return {"enough": True, "pass": bool(green_ok and money_ok),
            "green": "%d -> %d" % (before["months_green"], after["months_green"]),
            "per_day": "%.0f -> %.0f (floor %.1f)" % (b, a, floor),
            "green_ok": green_ok, "money_ok": money_ok}


def ocr_rows(rows):
    """Every one-candle-rule row, traded or not -- the slice L3's flag moves."""
    return [r for r in core11(rows)
            if (r.get("setup") or "").lower() in ("one_candle_rule", "ocr")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--off", default=str(TAPE / "book_OCR_RETEST_DISPLACEMENT_off.json.gz"))
    ap.add_argument("--on", default=str(TAPE / "book_OCR_RETEST_DISPLACEMENT_on.json.gz"))
    ap.add_argument("--config", default=str(TAPE / "loop.json"))
    a = ap.parse_args()

    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    out = {"flag": "OCR_RETEST_DISPLACEMENT", "unit": cfg["unit"],
           "fill": cfg["fill"], "exit": cfg["exit"],
           "universe": cfg["universe"]["row_filter"], "script": __file__}

    for name, p in (("off", a.off), ("on", a.on)):
        if not Path(p).exists():
            out[name] = {"error": "missing book: %s" % p}
            print(json.dumps(out, indent=2))
            return 2

    off_meta, off_rows = load(a.off)
    on_meta, on_rows = load(a.on)
    base_meta, base_rows = load(ROOT / cfg["baseline_book"])

    # --- identity ---------------------------------------------------------
    off_id = book_stamp.book_id(off_rows)
    base_id = book_stamp.book_id(base_rows)
    on_id = book_stamp.book_id(on_rows)
    out["identity"] = {
        "baseline_book_id_configured": cfg["baseline_book_id"],
        "baseline_book_id_recomputed": base_id,
        "off_book_id": off_id,
        "on_book_id": on_id,
        "off_reproduces_baseline": off_id == base_id == cfg["baseline_book_id"],
        "on_differs_from_off": on_id != off_id,
        "rows_off": len(off_rows), "rows_on": len(on_rows),
    }

    # --- the one flag that may differ between the two stamps --------------
    fo = (off_meta.get("stamp") or {}).get("flags") or {}
    fn = (on_meta.get("stamp") or {}).get("flags") or {}
    diff = sorted(k for k in set(fo) | set(fn) if fo.get(k) != fn.get(k))
    out["stamp_flag_diff"] = {"keys": diff,
                              "off": {k: fo.get(k) for k in diff},
                              "on": {k: fn.get(k) for k in diff},
                              "exactly_one_flag":
                                  [k.split(".")[-1] for k in diff]
                                  == ["OCR_RETEST_DISPLACEMENT"]}
    out["stamp_git"] = {"off": (off_meta.get("stamp") or {}).get("git"),
                        "on": (on_meta.get("stamp") or {}).get("git")}

    # --- the OCR slice the flag is supposed to move -----------------------
    o_off, o_on = ocr_rows(off_rows), ocr_rows(on_rows)
    def _traded(rs):
        return [r for r in rs if r.get("status") == "fired" and r.get("traded")]
    out["ocr_slice_core11"] = {
        "rows_off": len(o_off), "rows_on": len(o_on),
        "traded_off": len(_traded(o_off)), "traded_on": len(_traded(o_on)),
        "mean_r_traded_off": round(sum(r.get("r", 0.0) for r in _traded(o_off))
                                   / max(1, len(_traded(o_off))), 4),
        "mean_r_traded_on": round(sum(r.get("r", 0.0) for r in _traded(o_on))
                                  / max(1, len(_traded(o_on))), 4),
    }

    # --- the gate ---------------------------------------------------------
    s_off, s_on = slices(off_meta, off_rows), slices(on_meta, on_rows)
    out["off"], out["on"] = s_off, s_on
    out["gate"] = {h: gate_half(s_off[h], s_on[h]) for h in ("whole", "h1", "h2")}
    h1, h2 = out["gate"]["h1"], out["gate"]["h2"]
    out["decision"] = ("not_enough" if (h1["pass"] is None or h2["pass"] is None)
                       else ("ship" if (h1["pass"] and h2["pass"]) else "hold"))

    # --- baseline cross-check (the OFF arm must reproduce loop.json) ------
    bf = cfg["baseline_figures"]
    out["off_vs_loopjson_baseline"] = {
        k: {"loop.json": bf[k].get("per_day"), "recomputed": s_off[k]["per_day"],
            "trades_cfg": bf[k].get("trades"), "trades_recomputed": s_off[k]["trades"],
            "green_cfg": bf[k].get("months_green"),
            "green_recomputed": s_off[k]["months_green"]}
        for k in ("whole", "h1", "h2")
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
