"""L5 referee, PASS 3 -- independent re-derivation of the day-policy row.

Refereeing builder commit 99b2bf0b ("L5 repair (referee pass 2, 34c1546e):
DAY_POLICY default reverted to first3 (OFF)").

Nothing in this file imports research/loop_cycle.py, research/g72_suppress_price.py
or research/l5_referee*.py -- the unit walk, the monthly buckets, the halves split
and the gate arithmetic are all re-implemented here from the SWARM.md / loop.json
definitions so that a shared bug cannot make the builder's number and the
referee's number agree.

Run:  python research/l5_referee_pass3.py
"""
from __future__ import annotations

import gzip
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"
MIN_TRADES, MIN_MONTHS = 30, 12
MAX_DROP_PCT = 5.0

FAILURES: list[str] = []
NOTES: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    print(("  OK   " if ok else "  FAIL ") + label + ((" -- " + detail) if detail else ""))
    if not ok:
        FAILURES.append(label + ((" -- " + detail) if detail else ""))
    return ok


# ----------------------------------------------------------------- book loading

def load(name: str):
    with gzip.open(TAPE / name, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


# ------------------------------------------------- the unit, re-implemented here
#
# loop.json: unit = "up_to_3_stop_win_or_2loss", universe.row_filter = tier=="core".
# SWARM/spec sentence: "up to 3 S fires; stop after a win or after 2 losses".
# Candidate pool (loop_cycle's own definition, restated): a row the book actually
# put on -- status "fired" AND traded -- plus rows R31's account-wide two-loss halt
# already flipped to status "halted" (they keep their measured pnl).

def core_rows(rows):
    return [r for r in rows if r.get("tier") == "core"]


def unit_rows(rows):
    by_day: dict[str, list] = {}
    for r in rows:
        st, tr = r.get("status"), r.get("traded")
        if (st == "fired" and tr) or st == "halted":
            by_day.setdefault(r["day"], []).append(r)
    picked = []
    for day in sorted(by_day):
        # deterministic chronological order, entry time then symbol
        seq = sorted(by_day[day], key=lambda r: ((r.get("et") or ""), (r.get("sym") or "")))
        taken = 0
        losses = 0
        for r in seq:
            if taken >= 3:
                break
            picked.append(r)
            taken += 1
            pnl = r.get("pnl", 0.0)
            if pnl > 0:
                break            # stop after a win
            if pnl < 0:
                losses += 1
                if losses >= 2:
                    break        # stop after two losses
    return picked


def figures(rows, n_days):
    """$/day, months green, trades, avg win / avg loss -- computed here, not
    imported. n_days is the session count for the slice."""
    if not rows or not n_days:
        return {"trades": 0, "per_day": 0.0, "months_green": 0, "months": 0,
                "total": 0.0, "mean_r": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "awal": None, "fires_per_day": 0.0, "win_pct": 0.0}
    by_month: dict[str, float] = {}
    total = 0.0
    wins, losses = [], []
    for r in rows:
        p = r.get("pnl", 0.0)
        total += p
        by_month[r["day"][:7]] = by_month.get(r["day"][:7], 0.0) + p
        if p > 0:
            wins.append(p)
        elif p < 0:
            losses.append(p)
    aw = round(sum(wins) / len(wins), 0) if wins else 0.0
    al = round(abs(sum(losses) / len(losses)), 0) if losses else 0.0
    return {
        "trades": len(rows),
        "per_day": round(total / n_days, 0),
        "months_green": sum(1 for v in by_month.values() if v > 0),
        "months": len(by_month),
        "total": round(total, 0),
        "mean_r": round(total / len(rows) / RISK, 4),
        "avg_win": aw,
        "avg_loss": al,
        "awal": round(aw / al, 3) if al else None,
        "fires_per_day": round(len(rows) / n_days, 3),
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1) if (wins or losses) else 0.0,
    }


def slice_all(meta, rows):
    """whole / h1 / h2 figures on the core-11 up-to-3 unit."""
    core = core_rows(rows)
    all_days = sorted({r["day"] for r in rows if r.get("day")})
    n_all = meta.get("sessions") or len(all_days)
    n1 = sum(1 for d in all_days if d < BOUNDARY)
    n2 = sum(1 for d in all_days if d >= BOUNDARY)
    h1_src = [r for r in core if r.get("day", "") < BOUNDARY]
    h2_src = [r for r in core if r.get("day", "") >= BOUNDARY]
    return {
        "whole": figures(unit_rows(core), n_all),
        "h1": figures(unit_rows(h1_src), n1),
        "h2": figures(unit_rows(h2_src), n2),
        "_sessions": (n_all, n1, n2),
    }


def gate_half(before, after):
    """SWARM law 2 + law 3, re-implemented."""
    enough = before["trades"] >= MIN_TRADES and before["months"] >= MIN_MONTHS
    if not enough:
        return {"enough": False, "pass": None}
    green_ok = after["months_green"] >= before["months_green"]
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        dollar_ok = a >= b * (1 - MAX_DROP_PCT / 100.0)
    elif b < 0:
        dollar_ok = a >= b * (1 + MAX_DROP_PCT / 100.0)
    else:
        dollar_ok = a >= 0
    return {"enough": True, "pass": bool(green_ok and dollar_ok),
            "green_ok": green_ok, "dollar_ok": dollar_ok}


# ------------------------------------------------------------------------ main

def main() -> int:
    print("L5 referee pass 3 -- independent re-derivation (builder commit 99b2bf0b)")
    print()

    off_meta, off_rows = load("book_DAY_POLICY_off.json.gz")
    on_meta, on_rows = load("book_DAY_POLICY_on.json.gz")
    bl_meta, bl_rows = load("baseline_2026-09-05.json.gz")
    cfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))

    # -------------------------------------------------- 1. book identity checks
    print("1. book identity")
    off_id = off_meta["stamp"]["book_id"]
    on_id = on_meta["stamp"]["book_id"]
    bl_id = bl_meta["stamp"]["book_id"]
    check(off_id == bl_id == cfg["baseline_book_id"],
          "OFF book_id == baseline book_id == loop.json baseline_book_id",
          "off=%s baseline=%s cfg=%s" % (off_id, bl_id, cfg["baseline_book_id"]))
    check(on_id != off_id, "ON book_id differs from OFF", "on=%s" % on_id)

    fo, fn = off_meta["stamp"]["flags"], on_meta["stamp"]["flags"]
    diff = sorted(k for k in set(fo) | set(fn) if fo.get(k) != fn.get(k))
    check(diff == ["signal_runner.DAY_POLICY"],
          "OFF vs ON stamps differ in EXACTLY one flag", repr(diff))
    check(fo.get("signal_runner.DAY_POLICY") == "first3"
          and fn.get("signal_runner.DAY_POLICY") == "3fires_stop_win_or_2loss",
          "that one flag is first3 -> 3fires_stop_win_or_2loss",
          "%r -> %r" % (fo.get("signal_runner.DAY_POLICY"), fn.get("signal_runner.DAY_POLICY")))

    for nm, m in (("OFF", off_meta), ("ON", on_meta)):
        g = m["stamp"]["git"]
        check(g["dirty_py_count"] == 0 and not g["dirty_engine_py"],
              "%s book built on a clean tree" % nm,
              "dirty_py=%s dirty_engine=%s" % (g["dirty_py_count"], g["dirty_engine_py"]))
        anc = subprocess.run(["git", "merge-base", "--is-ancestor", g["commit"], "99b2bf0b"],
                             cwd=str(ROOT)).returncode == 0
        check(anc, "%s book's stamped commit is an ancestor of 99b2bf0b" % nm, g["commit"][:8])
        check(m["stamp"].get("script") is None,
              "%s stamp carries NO script field (disclosed gap, not a pass)" % nm)
        NOTES.append("%s stamp has no `window` key; meta carries first=%s last=%s sessions=%s"
                     % (nm, m.get("first"), m.get("last"), m.get("sessions")))

    # ---------------------------------------------------- 2. the gate, re-derived
    print()
    print("2. the gate, re-derived on the baseline unit (core-11, up_to_3_stop_win_or_2loss)")
    before = slice_all(off_meta, off_rows)
    after = slice_all(on_meta, on_rows)
    for k in ("whole", "h1", "h2"):
        b, a = before[k], after[k]
        print("   %-5s OFF $/day %7.0f  green %2d/%2d  trades %4d  |  ON $/day %7.0f  green %2d/%2d  trades %4d"
              % (k, b["per_day"], b["months_green"], b["months"], b["trades"],
                 a["per_day"], a["months_green"], a["months"], a["trades"]))
    print("   sessions whole/h1/h2 = %s" % (before["_sessions"],))

    h1v = gate_half(before["h1"], after["h1"])
    h2v = gate_half(before["h2"], after["h2"])
    decision = "ship" if (h1v["enough"] and h1v["pass"] and h2v["enough"] and h2v["pass"]) else "hold"
    print("   H1 %s  H2 %s  -> gate decision: %s" % (h1v, h2v, decision))

    # against the builder's published table (research/l5_day_policy.md) and cycles.md
    check(before["whole"]["per_day"] == -52 and after["whole"]["per_day"] == -52,
          "whole $/day -52 -> -52 as published",
          "%s -> %s" % (before["whole"]["per_day"], after["whole"]["per_day"]))
    check(before["whole"]["months_green"] == 11 and after["whole"]["months_green"] == 11,
          "whole green 11 -> 11 as published")
    check(before["whole"]["trades"] == 769 and after["whole"]["trades"] == 769,
          "whole trades 769 both arms as published",
          "%s / %s" % (before["whole"]["trades"], after["whole"]["trades"]))
    check(before["h1"]["per_day"] == 9 and after["h1"]["per_day"] == 9
          and before["h1"]["months_green"] == 6 and after["h1"]["months_green"] == 6,
          "H1 +9/day 6/12 both arms as published",
          "%s/%s green %s/%s" % (before["h1"]["per_day"], after["h1"]["per_day"],
                                 before["h1"]["months_green"], after["h1"]["months_green"]))
    check(before["h2"]["per_day"] == -111 and after["h2"]["per_day"] == -111
          and before["h2"]["months_green"] == 5 and after["h2"]["months_green"] == 5,
          "H2 -111/day 5/13 both arms as published",
          "%s/%s green %s/%s" % (before["h2"]["per_day"], after["h2"]["per_day"],
                                 before["h2"]["months_green"], after["h2"]["months_green"]))
    check(before["whole"]["awal"] == 1.119 and after["whole"]["awal"] == 1.119,
          "avg win / avg loss 1.119 both arms as published",
          "%s / %s" % (before["whole"]["awal"], after["whole"]["awal"]))
    check(before["whole"]["fires_per_day"] == 1.541 and after["whole"]["fires_per_day"] == 1.541,
          "fires/day 1.541 both arms as published",
          "%s / %s" % (before["whole"]["fires_per_day"], after["whole"]["fires_per_day"]))

    # complete no-op claim: every unit row identical, key for key
    def keyset(rows):
        return sorted((r["day"], r.get("et"), r.get("sym"), round(r.get("pnl", 0.0), 6))
                      for r in unit_rows(core_rows(rows)))
    check(keyset(off_rows) == keyset(on_rows),
          "the ON unit row-set is IDENTICAL to OFF, row for row (the no-op claim)")

    # sample size per cell
    print()
    print("3. sample size per cell")
    for k, n_m in (("whole", 25), ("h1", 12), ("h2", 13)):
        b = before[k]
        ok = b["trades"] >= MIN_TRADES and b["months"] >= MIN_MONTHS
        check(ok, "%s clears the 30-trade / 12-month floor" % k,
              "trades=%d months=%d" % (b["trades"], b["months"]))

    # ------------------------------------------- 4. the flag is stamped, and default
    print()
    print("4. flag plumbing")
    sys.path.insert(0, str(ROOT))
    from research import book_stamp  # noqa: E402
    flat = [n for _mod, names in book_stamp.FLAG_SOURCES for n in names]
    check("DAY_POLICY" in flat, "DAY_POLICY is in book_stamp.FLAG_SOURCES")
    check(("day_policy", ("MAX_FIRES", "LOSS_STOP")) in book_stamp.FLAG_SOURCES,
          "day_policy.MAX_FIRES/LOSS_STOP are stamped too")

    src = (ROOT / "signal_runner.py").read_text(encoding="utf-8")
    m = re.search(r'DAY_POLICY = os\.getenv\("DAY_POLICY", "([^"]+)"\)', src)
    check(bool(m) and m.group(1) == "first3",
          "signal_runner default is first3 (research arm never defaults ON)",
          repr(m.group(1) if m else None))

    # the decision recorded in the ledgers must match the code default
    print()
    print("5. the ledgers agree with the code")
    cyc = (TAPE / "cycles.md").read_text(encoding="utf-8")
    rows_md = [ln for ln in cyc.splitlines()
               if ln.startswith("|") and "DAY_POLICY" in ln and not ln.startswith("|---")]
    last = rows_md[-1] if rows_md else ""
    cells = [c.strip() for c in last.strip("|").split("|")]
    md_decision = cells[3] if len(cells) > 3 else "?"
    check(md_decision == "hold",
          "cycles.md's DAY_POLICY row records the same decision the code holds",
          "cycles.md says %r, code default is first3 (= hold)" % md_decision)

    st = json.loads((TAPE / "loop_state.json").read_text(encoding="utf-8"))
    dp = [h for h in st["history"] if h.get("flag") == "DAY_POLICY"]
    check(bool(dp) and dp[-1].get("decision") == "hold",
          "loop_state.json's DAY_POLICY cycle records the same decision",
          "loop_state says %r" % (dp[-1].get("decision") if dp else None))

    pin = cfg.get("_comment", "")
    stale_pin = "builds book_id 205d3dcee96c5282" in pin
    check(not stale_pin,
          "loop.json's REBUILD PIN comment is true at HEAD",
          "it still says a bare backtest_2y build makes 205d3dcee96c5282; after 99b2bf0b "
          "a bare build makes the baseline 2c39ced2697c26cc again")

    rpt = (ROOT / "research" / "l5_day_policy.md").read_text(encoding="utf-8")
    check("(now the **default**" not in rpt,
          "l5_day_policy.md does not still call the flag the default")
    check("**Decision: ship**" not in rpt,
          "l5_day_policy.md does not still publish 'Decision: ship'")
    check("now that the default is `3fires_stop_win_or_2loss`, **this is live**" not in rpt,
          "l5_day_policy.md does not still publish the live-mismatch-is-live sentence")

    # ---------------------------------------------- 6. the committed parity test
    print()
    print("6. the committed live-parity test at HEAD")
    p = subprocess.run([sys.executable, "research/test_live_follows_loop.py"],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    check(p.returncode == 0,
          "research/test_live_follows_loop.py passes at HEAD",
          (p.stderr.strip().splitlines() or ["?"])[-1][:200])

    print()
    if NOTES:
        print("notes:")
        for n in NOTES:
            print("  -", n)
    print()
    print("FAILURES: %d" % len(FAILURES))
    for f in FAILURES:
        print("  *", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
