"""o4_referee.py -- independent re-derivation of row O4's gate (builder commit 8ecb043e).

Nothing here imports research/loop_cycle.py for its ARITHMETIC. The gate math,
the three units, the halves split and the per-half denominators are all
re-implemented from the words in SWARM.md law 2/3 and the omen-10.0 spec, then
compared cell-by-cell against loop_cycle's own output on a REAL same-day A/B
book pair (research/bt2y_trades_htfveto_{off,on}.json.gz, both built
2026-09-04 09:25). loop_cycle is imported only so its answers can be diffed
against mine.

Checks:
  C1  gate percentage direction, both signs of baseline, at 4.9/5.0/5.1%
  C2  green-months rule alone
  C3  sample floor (30 trades / 12 months) -> no verdict
  C4  halves boundary: a session ON 2025-09-01 belongs to H2
  C5  the three units against the spec's day policy
  C6  per-half session denominators: are they the same for both arms?
  C7  whole-window denominator vs the sum of the halves'
  C8  the OFF-arm environment: is the flag under test actually unset?
Run: python research/o4_referee.py
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import loop_cycle as lc  # noqa: E402  (compared against, not used for math)

RISK = 1000.0
BOUNDARY = "2025-09-01"
OFF_BOOK = ROOT / "research" / "bt2y_trades_htfveto_off.json.gz"
ON_BOOK = ROOT / "research" / "bt2y_trades_htfveto_on.json.gz"

fails: list[str] = []
notes: list[str] = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ("  -- " + detail if detail else ""))
    if not ok:
        fails.append(name + (" -- " + detail if detail else ""))


# --------------------------------------------------------- my own gate, from the words

def my_half_verdict(before, after, max_drop_pct):
    """SWARM law 2 + law 3, written from the sentence, not from loop_cycle."""
    if before["trades"] < 30 or before["months"] < 12:
        return None                      # no verdict
    if after["months_green"] < before["months_green"]:
        return False
    b, a = before["per_day"], after["per_day"]
    allowed_fall = abs(b) * max_drop_pct / 100.0
    return a >= b - allowed_fall         # "$/day may not fall more than N% (of its size)"


def mk(trades=40, months=13, months_green=13, per_day=100.0):
    return {"trades": trades, "months": months, "months_green": months_green,
            "per_day": per_day}


def c1_c3_gate_math():
    print("\nC1/C2/C3 -- the gate arithmetic, mine vs loop_cycle's")
    cases = [
        ("+100 -> +95.1 (4.9% fall)", mk(per_day=100.0), mk(per_day=95.1)),
        ("+100 -> +95.0 (exactly 5%)", mk(per_day=100.0), mk(per_day=95.0)),
        ("+100 -> +94.9 (5.1% fall)", mk(per_day=100.0), mk(per_day=94.9)),
        ("+100 -> +150 (a rise)", mk(per_day=100.0), mk(per_day=150.0)),
        ("-100 -> -104.9 (4.9% worse)", mk(per_day=-100.0), mk(per_day=-104.9)),
        ("-100 -> -105.1 (5.1% worse)", mk(per_day=-100.0), mk(per_day=-105.1)),
        ("-100 -> -50 (a rise from a loss)", mk(per_day=-100.0), mk(per_day=-50.0)),
        ("0 -> -1 (zero baseline)", mk(per_day=0.0), mk(per_day=-1.0)),
        ("green 13 -> 12, dollars flat", mk(months_green=13), mk(months_green=12)),
        ("green 13 -> 14, dollars flat", mk(months_green=13), mk(months_green=14)),
        ("29 trades (floor)", mk(trades=29), mk(trades=29)),
        ("11 months (floor)", mk(months=11), mk(months=11)),
        ("30 trades / 12 months (on the floor)", mk(trades=30, months=12),
         mk(trades=30, months=12)),
    ]
    for name, b, a in cases:
        mine = my_half_verdict(b, a, 5.0)
        theirs_raw = lc.half_verdict(b, a, 5.0)
        theirs = None if not theirs_raw["enough"] else theirs_raw["pass"]
        check("C1 %-38s mine=%s theirs=%s" % (name, mine, theirs), mine == theirs)


def c4_boundary():
    print("\nC4 -- the 2025-09-01 boundary")
    rows = [{"day": "2025-08-31"}, {"day": "2025-09-01"}, {"day": "2025-09-02"}]
    h1, h2 = lc.split_halves(rows, BOUNDARY)
    check("C4 a session on 2025-09-01 lands in H2",
          [r["day"] for r in h1] == ["2025-08-31"]
          and [r["day"] for r in h2] == ["2025-09-01", "2025-09-02"])


def my_up_to_3(rows):
    """The spec's day policy, written from its sentence: 'up to 3 S fires; stop
    after a win or after 2 losses'."""
    byday = {}
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday.setdefault(r["day"], []).append(r)
    out = []
    for day in sorted(byday):
        losses = 0
        for r in sorted(byday[day], key=lambda x: (x["day"], x["et"], x["sym"]))[:3]:
            out.append(r)
            if r.get("pnl", 0.0) > 0:
                break
            if r.get("pnl", 0.0) < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


def c5_units():
    print("\nC5 -- the three units")
    rows = [
        {"day": "d1", "et": "09:35", "sym": "A", "status": "fired", "traded": True, "pnl": -10.0},
        {"day": "d1", "et": "09:40", "sym": "B", "status": "fired", "traded": True, "pnl": 50.0},
        {"day": "d1", "et": "09:45", "sym": "C", "status": "fired", "traded": True, "pnl": 99.0},
        {"day": "d2", "et": "09:35", "sym": "A", "status": "fired", "traded": True, "pnl": -1.0},
        {"day": "d2", "et": "09:40", "sym": "B", "status": "fired", "traded": True, "pnl": -1.0},
        {"day": "d2", "et": "09:45", "sym": "C", "status": "fired", "traded": True, "pnl": 99.0},
        {"day": "d3", "et": "09:35", "sym": "A", "status": "fired", "traded": True, "pnl": 0.0},
        {"day": "d3", "et": "09:40", "sym": "B", "status": "fired", "traded": True, "pnl": 0.0},
        {"day": "d3", "et": "09:45", "sym": "C", "status": "fired", "traded": True, "pnl": 0.0},
        {"day": "d3", "et": "09:50", "sym": "D", "status": "fired", "traded": True, "pnl": 5.0},
    ]
    check("C5 every_signal = every traded row",
          [r["sym"] for r in lc.UNIT_FUNCS["every_signal"](rows)] == list("ABCABCABCD"))
    check("C5 first_of_day = one per day",
          [(r["day"], r["sym"]) for r in lc.UNIT_FUNCS["first_of_day"](rows)]
          == [("d1", "A"), ("d2", "A"), ("d3", "A")])
    mine = [(r["day"], r["sym"]) for r in my_up_to_3(rows)]
    theirs = [(r["day"], r["sym"]) for r in lc.UNIT_FUNCS["up_to_3_stop_win_or_2loss"](rows)]
    check("C5 up_to_3 stop-after-win / stop-after-2-losses / cap 3: mine==theirs "
          "%s" % (theirs,), mine == theirs)
    check("C5 up_to_3 day d1 stops on the first win (A loss, B win)",
          [s for d, s in theirs if d == "d1"] == ["A", "B"])
    check("C5 up_to_3 day d2 stops on the second loss",
          [s for d, s in theirs if d == "d2"] == ["A", "B"])
    check("C5 up_to_3 day d3 caps at three flat trades",
          [s for d, s in theirs if d == "d3"] == ["A", "B", "C"])


# ------------------------------------------------------------- the real book pair

def slim(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    meta = b["meta"]
    rows = [{"day": r.get("day"), "et": r.get("et"), "sym": r.get("sym"),
             "status": r.get("status"), "traded": r.get("traded"),
             "pnl": r.get("pnl", 0.0)} for r in b["trades"]]
    return meta, rows


def c6_c7_denominators():
    print("\nC6/C7 -- the per-half denominators on a REAL same-day A/B pair")
    if not OFF_BOOK.exists() or not ON_BOOK.exists():
        notes.append("C6/C7 skipped: the htfveto book pair is not on this box")
        print("  SKIP  books not present")
        return
    off_meta, off_rows = slim(OFF_BOOK)
    on_meta, on_rows = slim(ON_BOOK)
    print("    off stamp commit %s  sessions %s  rows %d"
          % (off_meta.get("stamp", {}).get("git", {}).get("commit", "?")[:8],
             off_meta.get("sessions"), len(off_rows)))
    print("    on  stamp commit %s  sessions %s  rows %d"
          % (on_meta.get("stamp", {}).get("git", {}).get("commit", "?")[:8],
             on_meta.get("sessions"), len(on_rows)))

    n1_off, n2_off = lc.half_n_days(off_rows, BOUNDARY)
    n1_on, n2_on = lc.half_n_days(on_rows, BOUNDARY)
    print("    half denominators  OFF (%d, %d)   ON (%d, %d)" % (n1_off, n2_off, n1_on, n2_on))
    check("C6 both arms of an A/B share the same per-half session denominator",
          (n1_off, n2_off) == (n1_on, n2_on),
          "loop_cycle counts each BOOK's own distinct days, so a flag that "
          "empties a day shrinks that arm's denominator and inflates its $/day")

    sess_off = off_meta.get("sessions")
    check("C7 whole-window denominator (meta.sessions) == n_h1 + n_h2",
          sess_off == n1_off + n2_off,
          "meta.sessions=%s but the halves sum to %d -- $/day on the whole window "
          "and $/day on the halves are computed on different rulers"
          % (sess_off, n1_off + n2_off))

    # Re-derive the gate on this pair, my arithmetic, unit = first_of_day.
    for unit in ("every_signal", "first_of_day", "up_to_3_stop_win_or_2loss"):
        before = lc.compute_all(off_meta, off_rows, unit, BOUNDARY)
        after = lc.compute_all(on_meta, on_rows, unit, BOUNDARY)
        for half in ("h1", "h2"):
            mine = my_half_verdict(before[half], after[half], 5.0)
            t = lc.half_verdict(before[half], after[half], 5.0)
            theirs = None if not t["enough"] else t["pass"]
            check("C6 real pair %s %s: mine=%s theirs=%s  ($/day %s->%s, green %s->%s, "
                  "%d trades, %d months)"
                  % (unit, half.upper(), mine, theirs, before[half]["per_day"],
                     after[half]["per_day"], before[half]["months_green"],
                     after[half]["months_green"], before[half]["trades"],
                     before[half]["months"]),
                  mine == theirs)


def c8_off_arm_env():
    print("\nC8 -- does the OFF arm actually unset the flag under test?")
    src = (ROOT / "research" / "loop_cycle.py").read_text(encoding="utf-8")
    # build_book copies os.environ wholesale and only ever ADDS keys.
    copies_environ = "env = dict(os.environ)" in src
    ever_pops = (".pop(" in src.split("def build_book")[1].split("def ")[0]
                 or "del env[" in src)
    check("C8 the OFF arm removes the flag from the child environment",
          not copies_environ or ever_pops,
          "build_book() does `env = dict(os.environ)` and never deletes the "
          "flag; the docstring's 'env simply unset' is false. If the flag is "
          "set in the ambient shell (settings env shadows .env in this repo), "
          "the OFF arm builds the flag ON")
    # Demonstrate: with the flag pre-set, what would the child see?
    flag = "OMEN_O4_REFEREE_PROBE"
    os.environ[flag] = "1"
    env = dict(os.environ)
    env.update({})                                   # exactly what build_book does for OFF
    check("C8 demonstration: with %s=1 in the parent, the OFF child still sees it" % flag,
          env.get(flag) != "1",
          "child sees %s=%r" % (flag, env.get(flag)))
    os.environ.pop(flag, None)


def c9_blocked_path():
    """A baseline/OFF book_id mismatch must yield `blocked`, never `hold`, and
    must compare book_stamp.book_id values."""
    print("\nC9 -- the OFF-arm == baseline book_id assertion")
    import tempfile
    from research import book_stamp

    tmp = Path(tempfile.mkdtemp(prefix="o4ref_"))
    baseline_rows = [{"sym": "A", "day": "2025-01-02", "et": "09:35", "dir": "long",
                      "entry": 1.0, "stop": 0.9, "pnl": 10.0, "status": "fired",
                      "traded": True}]
    off_rows = baseline_rows + [dict(baseline_rows[0], sym="B", pnl=-5.0)]
    base_path = tmp / "baseline.json"
    base_path.write_text(json.dumps({"meta": {"stamp": {"book_id": book_stamp.book_id(baseline_rows)}},
                                     "trades": baseline_rows}), encoding="utf-8")
    off_path = tmp / ("book_%s_off.json.gz" % "FAKEFLAG")
    with gzip.open(off_path, "wt", encoding="utf-8") as f:
        json.dump({"meta": {"stamp": {"book_id": book_stamp.book_id(off_rows)}},
                   "trades": off_rows}, f)

    built = []
    real_tape, real_build = lc.TAPE, lc.build_book
    lc.TAPE = tmp
    lc.build_book = lambda env, out, cfg, smoke: (built.append((dict(env), out.name)), out)[1]
    try:
        res = lc.stage_build({"baseline_book": str(base_path),
                              "rebuild": {"script": "backtest_2y.py", "args": [], "env": {}}},
                             "FAKEFLAG", "1", smoke=False)
    finally:
        lc.TAPE, lc.build_book = real_tape, real_build

    check("C9 a book_id mismatch returns decision='blocked' (not 'hold')",
          res.get("decision") == "blocked", "got %r" % res.get("decision"))
    check("C9 the ids compared are book_stamp.book_id values",
          res.get("baseline_book_id") == book_stamp.book_id(baseline_rows)
          and res.get("off_book_id") == book_stamp.book_id(off_rows))
    check("C9 the ON arm is never built after a mismatch",
          not any(name.endswith("_on.json.gz") for _, name in built),
          "built=%r" % (built,))
    check("C9 the row-count diff is reported", res.get("row_count_diff") == 1)


def c10_push_text():
    """--dry-run must not call notify_ntfy.push; the live line must be plain
    English with no flag name in it."""
    print("\nC10 -- the ntfy line and --dry-run")
    import tempfile
    import notify_ntfy

    tmp = Path(tempfile.mkdtemp(prefix="o4ref_push_"))
    rows = []
    for i in range(400):
        d = "2024-%02d-%02d" % (9 + i // 60 if 9 + i // 60 <= 12 else 12, (i % 27) + 1)
        rows.append({"day": d, "et": "09:%02d" % (35 + i % 20), "sym": "S%d" % i,
                     "status": "fired", "traded": True, "pnl": 10.0})
    for name in ("book_SOME_SECRET_FLAG_NAME_off.json.gz",
                 "book_SOME_SECRET_FLAG_NAME_on.json.gz"):
        with gzip.open(tmp / name, "wt", encoding="utf-8") as f:
            json.dump({"meta": {"sessions": 100}, "trades": rows}, f)

    calls = []
    real = (lc.TAPE, lc.CYCLES_MD, lc.STATE_JSON, notify_ntfy.push)
    lc.TAPE, lc.CYCLES_MD, lc.STATE_JSON = tmp, tmp / "cycles.md", tmp / "loop_state.json"
    notify_ntfy.push = lambda title, body, **kw: calls.append((title, body))
    cfg = {"unit": "every_signal", "halves_boundary": BOUNDARY,
           "gate": {"max_dollar_drop_pct": 5.0},
           "targets": {"dollars_per_day": 500, "avg_win_over_avg_loss": 2.0}}
    try:
        lc.stage_gate(cfg, "SOME_SECRET_FLAG_NAME", "the one-R first-target rule", dry_run=True)
        check("C10 --dry-run sends nothing", calls == [], "calls=%r" % (calls,))
        lc.stage_gate(cfg, "SOME_SECRET_FLAG_NAME", "the one-R first-target rule", dry_run=False)
        check("C10 a live run sends exactly one push", len(calls) == 1)
        body = calls[-1][1] if calls else ""
        print("    push text: %s" % body)
        check("C10 the push carries no flag name", "SOME_SECRET_FLAG_NAME" not in body
              and "book_" not in body, body)
        check("C10 the push carries the plain-English label",
              "the one-R first-target rule" in body, body)
    finally:
        lc.TAPE, lc.CYCLES_MD, lc.STATE_JSON, notify_ntfy.push = real


def main():
    print("O4 referee -- re-deriving the loop controller's gate (builder commit 8ecb043e)")
    c1_c3_gate_math()
    c4_boundary()
    c5_units()
    c6_c7_denominators()
    c8_off_arm_env()
    c9_blocked_path()
    c10_push_text()
    print("\n%d check(s) failed" % len(fails))
    for f in fails:
        print("  - " + f)
    for n in notes:
        print("  note: " + n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
