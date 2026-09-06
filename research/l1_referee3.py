"""L1 referee, pass 3 -- independent re-derivation of the MIN_PT1_R gate.

Refutation tool for row L1 (`signal_runner.MIN_PT1_R`, the 1R first-target rule).
Nothing here imports `research/loop_cycle.py`, `research/g72_suppress_price.py`,
`research/l1_referee.py` or `research/l1_referee2.py`: the day-policy unit, the
month buckets, the green-month count, $/day and the no-regression gate are all
written out longhand so a bug shared by the builder's script and the two earlier
referee scripts cannot hide in a third.

Unit / fill / exit / window are read from the stamped books themselves, not
asserted:

    unit   = up_to_3_stop_win_or_2loss  (loop.json)
    fill   = close                      (meta.entry_fill, checked)
    exit   = shipped engine, 1R hard stop on the intrabar touch,
             SCALE_PLAN=hod_then_runner_be, LOSS_HALT on  (stamp flags, checked)
    window = meta.first .. meta.last, meta.sessions

Run:  python research/l1_referee3.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"          # loop.json halves_boundary
MAX_DROP_PCT = 5.0               # loop.json gate.max_dollar_drop_pct
MIN_TRADES, MIN_MONTHS = 30, 12  # SWARM law 3

BOOKS = {
    "off":  TAPE / "book_MIN_PT1_R_off.json.gz",
    "on":   TAPE / "book_MIN_PT1_R_on.json.gz",
    "offp": TAPE / "book_MIN_PT1_R_off_postfix.json.gz",
    "onp":  TAPE / "book_MIN_PT1_R_on_postfix.json.gz",
    "base": TAPE / "baseline_2026-09-05.json.gz",
}

CORE = {"TSLA", "NVDA", "AAPL", "AMD", "META", "GOOGL", "AMZN", "MSFT",
        "PLTR", "QQQ", "SPY"}


# ----------------------------------------------------------------- loading

def load(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def book_id_of(meta, rows) -> str:
    """research/book_stamp.book_id, written out here rather than imported, so
    the referee is not trusting the same helper the builder stamped with."""
    h = hashlib.sha256()
    for r in rows:
        h.update(("%s|%s|%s|%s|%.4f|%.4f|%.4f|%s|%s\n" % (
            r.get("sym"), r.get("day"), r.get("et"), r.get("dir"),
            r.get("entry", 0.0), r.get("stop", 0.0), r.get("pnl", 0.0),
            r.get("status"), r.get("traded"))).encode())
    return h.hexdigest()[:16]


# ------------------------------------------------------------------- units

def day_policy_rows(rows):
    """Up to 3 fired-and-traded signals a day in arrival order; stop after the
    first winner or after the second loser. The account-wide two-loss halt's
    own rows join the candidate pool so a halt this unit would not itself have
    reached cannot silently erase the rest of the day."""
    byday = {}
    for r in rows:
        fired = r.get("status") == "fired" and r.get("traded")
        if fired or r.get("status") == "halted":
            byday.setdefault(r["day"], []).append(r)
    out = []
    for day in sorted(byday):
        ordered = sorted(byday[day], key=lambda r: (r.get("et") or "", r.get("sym") or ""))
        losses = 0
        for i, r in enumerate(ordered):
            if i >= 3:
                break
            out.append(r)
            pnl = r.get("pnl", 0.0)
            if pnl > 0:
                break
            if pnl < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


# ------------------------------------------------------------------ figures

def figures(unit_rows, n_days):
    if not unit_rows or not n_days:
        return {"trades": 0, "per_day": 0.0, "mean_r": 0.0, "win_pct": 0.0,
                "months_green": 0, "months": 0, "avg_win": 0.0, "avg_loss": 0.0,
                "awal": None, "total": 0.0, "fires_per_day": 0.0}
    total = 0.0
    by_month = {}
    wins = losses = 0
    win_sum = loss_sum = 0.0
    for r in unit_rows:
        p = r.get("pnl", 0.0)
        total += p
        by_month[r["day"][:7]] = by_month.get(r["day"][:7], 0.0) + p
        if p > 0:
            wins += 1
            win_sum += p
        elif p < 0:
            losses += 1
            loss_sum += -p
    avg_win = win_sum / wins if wins else 0.0
    avg_loss = loss_sum / losses if losses else 0.0
    return {
        "trades": len(unit_rows),
        "total": round(total, 0),
        "per_day": round(total / n_days, 0),
        "mean_r": round(total / len(unit_rows) / RISK, 4),
        "win_pct": round(wins / (wins + losses) * 100, 1) if (wins + losses) else 0.0,
        "months_green": sum(1 for v in by_month.values() if v > 0),
        "months": len(by_month),
        "avg_win": round(avg_win, 0),
        "avg_loss": round(avg_loss, 0),
        "awal": round(avg_win / avg_loss, 3) if avg_loss else None,
        "fires_per_day": round(len(unit_rows) / n_days, 3),
    }


def slice_book(meta, rows, core_only: bool):
    if core_only:
        rows = [r for r in rows if r.get("tier") == "core"]
    n_all = meta.get("sessions") or len({r["day"] for r in rows})
    days = sorted({r["day"] for r in rows if r.get("day")})
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    h1 = [r for r in rows if r.get("day", "") < BOUNDARY]
    h2 = [r for r in rows if r.get("day", "") >= BOUNDARY]
    return {
        "whole": figures(day_policy_rows(rows), n_all),
        "h1": figures(day_policy_rows(h1), n1),
        "h2": figures(day_policy_rows(h2), n2),
        "_n_days": (n_all, n1, n2),
    }


# --------------------------------------------------------------------- gate

def half_gate(before, after):
    """SWARM law 2 on one half: green months may not fall, and $/day may not
    fall more than 5%. Written longhand, including the sign convention for a
    negative baseline (a bigger loss is a fall)."""
    if before["trades"] < MIN_TRADES or after["trades"] < MIN_TRADES \
            or before["months"] < MIN_MONTHS or after["months"] < MIN_MONTHS:
        return {"enough": False, "pass": None,
                "why": "under the 30-trade / 12-month floor"}
    green_ok = after["months_green"] >= before["months_green"]
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        dollar_ok = a >= b * (1 - MAX_DROP_PCT / 100.0)
    elif b == 0:
        dollar_ok = a >= 0
    else:
        # a negative baseline: the loss may not deepen by more than 5%
        dollar_ok = a >= b * (1 + MAX_DROP_PCT / 100.0)
    return {"enough": True, "pass": bool(green_ok and dollar_ok),
            "green_ok": green_ok, "dollar_ok": dollar_ok,
            "green": (before["months_green"], after["months_green"]),
            "dollar": (b, a)}


# ------------------------------------------------------- the skip accounting

def skip_accounting(off_rows, on_rows):
    """How many signals the flag drops, and what they would have done.

    Keyed on (sym, day, et, entry, stop, dir) -- the same key the earlier
    passes used, re-derived here."""
    def key(r):
        return (r.get("sym"), r.get("day"), r.get("et"),
                r.get("entry"), r.get("stop"), r.get("dir"))

    tagged = [r for r in on_rows
              if "MIN_PT1_R" in json.dumps(r.get("tags") or []) + str(r.get("reason") or "")]
    off_traded = {key(r): r for r in off_rows if r.get("traded")}
    would = [off_traded[key(r)] for r in tagged if key(r) in off_traded]
    if would:
        mr = sum(w.get("r", 0.0) for w in would) / len(would)
        w = sum(1 for x in would if x.get("pnl", 0) > 0)
        l = sum(1 for x in would if x.get("pnl", 0) < 0)
    else:
        mr, w, l = 0.0, 0, 0
    core_tagged = sum(1 for r in tagged if r.get("tier") == "core")
    core_would = sum(1 for r in would if r.get("tier") == "core")
    return {"tagged": len(tagged), "tagged_core": core_tagged,
            "would_have_traded": len(would), "would_core": core_would,
            "mean_r": round(mr, 4), "win_pct": round(w / (w + l) * 100, 1) if w + l else 0.0,
            "grades": _count(r.get("grade") for r in tagged)}


def raw_bar_spotcheck(on_rows, n=20):
    """Independent check of the gate's SEMANTICS against raw archived bars.

    For a sample of rows the ON book tagged as skipped, and a sample it fired,
    recompute the session extreme as of (and including) the entry minute from
    `data_archive/<SYM>/<DAY>.csv` and assert the predicate the rulebook
    sentence names: first scale point (session HOD for a call / LOD for a put)
    less than 1R from entry => skipped, else not skipped."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import polygon_feed as pf

    def extreme(sym, day, et):
        bars = pf.rth(pf.fetch_day(sym, day))
        upto = [c for c in bars if c.timestamp[:5] <= et]
        if not upto:
            return None, None
        return max(c.high for c in upto), min(c.low for c in upto)

    tagged, fired = [], []
    for r in on_rows:
        blob = json.dumps(r.get("tags") or []) + str(r.get("reason") or "")
        if "MIN_PT1_R" in blob:
            tagged.append(r)
        elif r.get("status") == "fired" and r.get("traded"):
            fired.append(r)
    step_t = max(1, len(tagged) // n)
    step_f = max(1, len(fired) // n)
    out = {"skipped_ok": 0, "skipped_bad": [], "fired_ok": 0, "fired_bad": []}
    for r in tagged[::step_t][:n]:
        hi, lo = extreme(r["sym"], r["day"], r["et"])
        if hi is None:
            continue
        risk = abs(r["entry"] - r["stop"])
        pt1 = (hi - r["entry"]) if r["dir"] == "call" else (r["entry"] - lo)
        if risk > 0 and pt1 < 1.0 * risk:
            out["skipped_ok"] += 1
        else:
            out["skipped_bad"].append((r["sym"], r["day"], r["et"], r["dir"],
                                       round(pt1, 3), round(risk, 3)))
    for r in fired[::step_f][:n]:
        hi, lo = extreme(r["sym"], r["day"], r["et"])
        if hi is None:
            continue
        risk = abs(r["entry"] - r["stop"])
        pt1 = (hi - r["entry"]) if r["dir"] == "call" else (r["entry"] - lo)
        if risk > 0 and pt1 >= 1.0 * risk:
            out["fired_ok"] += 1
        else:
            out["fired_bad"].append((r["sym"], r["day"], r["et"], r["dir"],
                                     round(pt1, 3), round(risk, 3),
                                     r.get("setup"), r.get("grade")))
    return out


def _count(it):
    d = {}
    for x in it:
        d[x] = d.get(x, 0) + 1
    return dict(sorted(d.items(), key=lambda kv: -kv[1]))


# --------------------------------------------------------------------- main

def stamp_diff(a_meta, b_meta):
    fa = a_meta["stamp"]["flags"]
    fb = b_meta["stamp"]["flags"]
    keys = sorted(set(fa) | set(fb))
    return {k: (fa.get(k), fb.get(k)) for k in keys if fa.get(k) != fb.get(k)}


def main():
    loaded = {k: load(p) for k, p in BOOKS.items()}

    print("=" * 78)
    print("BOOK IDENTITY")
    for k, (m, rows) in loaded.items():
        st = m["stamp"]
        print("  %-5s rows=%-7d book_id=%s commit=%s dirty_py=%s dirty_engine=%s"
              % (k, len(rows), book_id_of(m, rows), st["git"]["commit"][:8],
                 st["git"]["dirty_py_count"], st["git"]["dirty_engine_py"]))
        print("        window %s..%s sessions=%s entry_fill=%s"
              % (m["first"], m["last"], m["sessions"], m["entry_fill"]))
    print("  OFF == baseline book_id : %s"
          % (book_id_of(*loaded["off"]) == book_id_of(*loaded["base"])))
    print("  OFFPOST == baseline     : %s"
          % (book_id_of(*loaded["offp"]) == book_id_of(*loaded["base"])))

    print("\nSTAMP DIFF off -> on      :", stamp_diff(loaded["off"][0], loaded["on"][0]))
    print("STAMP DIFF offp -> onp    :", stamp_diff(loaded["offp"][0], loaded["onp"][0]))
    print("STAMP DIFF off -> offp    :", stamp_diff(loaded["off"][0], loaded["offp"][0]))

    for core_only, tag in ((True, "core-11"), (False, "full-29")):
        print("\n" + "=" * 78)
        print("%s   unit=up_to_3_stop_win_or_2loss  fill=close  "
              "exit=1R hard stop (intrabar touch) + hod_then_runner_be" % tag)
        print("=" * 78)
        arms = {k: slice_book(*loaded[k], core_only=core_only)
                for k in ("off", "on", "offp", "onp", "base")}
        hdr = "%-26s %7s %9s %9s %7s %7s %7s %9s" % (
            "arm / half", "trades", "$/day", "mean R", "win%", "green", "months", "fires/day")
        print(hdr)
        for k in ("base", "off", "on", "offp", "onp"):
            for half in ("whole", "h1", "h2"):
                f = arms[k][half]
                print("%-26s %7d %9.0f %9.4f %7.1f %7d %7d %9.3f"
                      % ("%s %s" % (k, half), f["trades"], f["per_day"], f["mean_r"],
                         f["win_pct"], f["months_green"], f["months"], f["fires_per_day"]))
        for pair, lbl in ((("off", "on"), "as published (pre-x_lift-reorder books)"),
                          (("offp", "onp"), "at the row's shipped code (post-reorder)")):
            b, a = arms[pair[0]], arms[pair[1]]
            h1 = half_gate(b["h1"], a["h1"])
            h2 = half_gate(b["h2"], a["h2"])
            dec = "ship" if (h1.get("pass") and h2.get("pass")) else "hold"
            print("  GATE %-42s H1=%s H2=%s -> %s" % (lbl, h1, h2, dec))

    print("\n" + "=" * 78)
    print("SKIP ACCOUNTING")
    print("  pre-reorder books :", skip_accounting(loaded["off"][1], loaded["on"][1]))
    print("  post-reorder books:", skip_accounting(loaded["offp"][1], loaded["onp"][1]))

    print("\n" + "=" * 78)
    print("RAW-BAR SPOT CHECK (post-reorder ON book vs data_archive)")
    try:
        print("  ", raw_bar_spotcheck(loaded["onp"][1]))
    except Exception as e:                                        # pragma: no cover
        print("   spot check unavailable:", type(e).__name__, e)

    print("\n" + "=" * 78)
    print("CYCLES.MD ROW (what the tape publishes for L1)")
    txt = (TAPE / "cycles.md").read_text(encoding="utf-8")
    for line in txt.splitlines():
        if "MIN_PT1_R" in line:
            print("  " + line)


if __name__ == "__main__":
    main()
