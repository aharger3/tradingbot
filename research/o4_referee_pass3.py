"""O4 referee, pass 3 -- try to REFUTE the repair commit add86484.

Pass 1 = research/o4_referee.py (27e7e04a, upheld with one defect).
Pass 2 = research/o4_referee_pass3.py's predecessor research/o4_referee_pass2.py
         (3ace41cb, refuted: DEFECT-1 --dry-run writes state/ledger,
          DEFECT-2 OFF arm never unsets the flag, FINDING-3 zero-delta ship).
Pass 3 (this file) checks the two repairs actually hold, and re-runs every
row-specific check from scratch rather than trusting either earlier page.

Everything here is retyped from SWARM.md / CLAUDE.md, not imported from
loop_cycle, except where the point is to exercise loop_cycle itself.

    python research/o4_referee_pass3.py            # all checks
    python research/o4_referee_pass3.py --quick    # skip the real-book re-price
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import loop_cycle                                     # noqa: E402
import notify_ntfy                                                  # noqa: E402

RISK = 1000.0
FAILS = []
CHECKS = []


def ok(name, cond, detail=""):
    CHECKS.append((name, bool(cond), detail))
    if not cond:
        FAILS.append("%s -- %s" % (name, detail))
    print("%-58s %s %s" % (name, "ok " if cond else "FAIL", detail))


# ------------------------------------------------------- 1. the gate, retyped

def ref_gate(before, after, max_drop_pct):
    """SWARM.md law 2 + law 3, written from the page, not from loop_cycle."""
    if before["trades"] < 30 or before["months"] < 12:
        return None                      # no verdict
    if after["months_green"] < before["months_green"]:
        return False
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        floor = b - abs(b) * max_drop_pct / 100.0
    elif b < 0:
        floor = b - abs(b) * max_drop_pct / 100.0
    else:
        floor = 0.0
    return a >= floor


def check_gate():
    cases = [
        # (b_trades, b_months, b_green, b_perday, a_green, a_perday)
        (100, 25, 11, 100.0, 11, 100.0),      # flat
        (100, 25, 11, 100.0, 11, 95.0),       # exactly -5%
        (100, 25, 11, 100.0, 11, 94.99),      # just past -5%
        (100, 25, 11, 100.0, 11, 94.9),       # -5.1%
        (100, 25, 11, 100.0, 11, 100000.0),   # any rise passes
        (100, 25, 11, 100.0, 10, 200.0),      # green falls -> fail even on a rise
        (100, 25, 11, 100.0, 12, 95.0),       # green rises, dollars at the floor
        (100, 25, 11, -100.0, 11, -104.9),    # loss 4.9% worse
        (100, 25, 11, -100.0, 11, -105.0),    # loss exactly 5% worse
        (100, 25, 11, -100.0, 11, -105.1),    # loss 5.1% worse
        (100, 25, 11, -100.0, 11, 0.0),       # loss -> flat
        (100, 25, 11, 0.0, 11, 0.0),          # zero baseline, flat
        (100, 25, 11, 0.0, 11, -0.01),        # zero baseline, any fall
        (100, 25, 11, 0.0, 11, 1.0),          # zero baseline, rise
        (29, 25, 11, 100.0, 11, 100.0),       # under the trade floor
        (30, 25, 11, 100.0, 11, 100.0),       # exactly the trade floor
        (100, 11, 11, 100.0, 11, 100.0),      # under the month floor
        (100, 12, 11, 100.0, 11, 100.0),      # exactly the month floor
    ]
    bad = []
    for bt, bm, bg, bp, ag, ap in cases:
        before = {"trades": bt, "months": bm, "months_green": bg, "per_day": bp}
        after = {"trades": bt, "months": bm, "months_green": ag, "per_day": ap}
        mine = ref_gate(before, after, 5.0)
        v = loop_cycle.half_verdict(before, after, 5.0)
        theirs = v["pass"] if v["enough"] else None
        if mine != theirs:
            bad.append((bt, bm, bg, bp, ag, ap, mine, theirs))
    ok("gate: 18 hand cases vs a retyped SWARM.md gate", not bad, str(bad))

    # direction spot checks, stated explicitly
    def p(bp, ap, bg=11, ag=11):
        v = loop_cycle.half_verdict(
            {"trades": 100, "months": 25, "months_green": bg, "per_day": bp},
            {"trades": 100, "months": 25, "months_green": ag, "per_day": ap}, 5.0)
        return v["pass"] if v["enough"] else None
    ok("gate: a fall of more than 5% fails", p(100.0, 94.9) is False)
    ok("gate: exactly 5% passes", p(100.0, 95.0) is True)
    ok("gate: any rise passes", p(100.0, 1e9) is True)
    ok("gate: green months falling fails alone", p(100.0, 100.0, 11, 10) is False)
    ok("gate: negative baseline reads 'loss 5% worse'",
       p(-100.0, -104.9) is True and p(-100.0, -105.1) is False)
    ok("gate: under 30 trades / 12 months -> no verdict",
       p(100.0, 100.0) is True
       and loop_cycle.half_verdict({"trades": 29, "months": 25, "months_green": 1, "per_day": 1},
                                   {"months_green": 1, "per_day": 1}, 5.0)["enough"] is False
       and loop_cycle.half_verdict({"trades": 99, "months": 11, "months_green": 1, "per_day": 1},
                                   {"months_green": 1, "per_day": 1}, 5.0)["enough"] is False)


# ---------------------------------------------------- 2. the halves boundary

def check_boundary():
    rows = [{"day": "2025-08-31", "pnl": 1.0}, {"day": "2025-09-01", "pnl": 1.0},
            {"day": "2025-09-02", "pnl": 1.0}]
    h1, h2 = loop_cycle.split_halves(rows, "2025-09-01")
    ok("boundary: a session dated 2025-09-01 is H2",
       [r["day"] for r in h1] == ["2025-08-31"]
       and [r["day"] for r in h2] == ["2025-09-01", "2025-09-02"])
    n1, n2 = loop_cycle.half_n_days(rows, "2025-09-01")
    ok("boundary: half_n_days agrees with the split", (n1, n2) == (1, 2), "%d/%d" % (n1, n2))
    ok("boundary: halves are scored independently (both must pass to ship)",
       "h1v[\"enough\"] and h1v[\"pass\"] and h2v[\"enough\"] and h2v[\"pass\"]"
       in Path(ROOT / "research" / "loop_cycle.py").read_text(encoding="utf-8")
       .replace("'", '"').replace('h1v["enough"] and h1v["pass"] and h2v["enough"] and h2v["pass"]',
                                  'h1v["enough"] and h1v["pass"] and h2v["enough"] and h2v["pass"]'))


# ------------------------------------------------------------- 3. the units

def R(day, et, sym, pnl, status="fired", traded=True):
    return {"day": day, "et": et, "sym": sym, "pnl": pnl, "status": status,
            "traded": traded, "entry": 1.0, "stop": 0.5, "dir": "long", "setup": "BR"}


def check_units():
    d = "2025-01-02"
    # a win first: stop after it
    rows = [R(d, "09:31", "A", 500), R(d, "09:40", "B", -100), R(d, "09:50", "C", 700)]
    got = [r["sym"] for r in loop_cycle.up_to_3_rows(rows)]
    ok("unit: stops after the first win", got == ["A"], str(got))
    # two losses: stop after the second
    rows = [R(d, "09:31", "A", -100), R(d, "09:40", "B", -100), R(d, "09:50", "C", 900)]
    got = [r["sym"] for r in loop_cycle.up_to_3_rows(rows)]
    ok("unit: stops after the second loss", got == ["A", "B"], str(got))
    # loss, loss avoided by a win in between
    rows = [R(d, "09:31", "A", -100), R(d, "09:40", "B", 400), R(d, "09:50", "C", -100)]
    got = [r["sym"] for r in loop_cycle.up_to_3_rows(rows)]
    ok("unit: a win after one loss ends the day", got == ["A", "B"], str(got))
    # cap at three
    rows = [R(d, "09:31", "A", -100), R(d, "09:40", "B", 0.0), R(d, "09:50", "C", 0.0),
            R(d, "10:00", "D", 900)]
    got = [r["sym"] for r in loop_cycle.up_to_3_rows(rows)]
    ok("unit: caps at three fires a day", got == ["A", "B", "C"], str(got))
    # first_of_day = the earliest candidate
    rows = [R(d, "09:50", "C", 1), R(d, "09:31", "A", 1)]
    got = [r["sym"] for r in loop_cycle.UNIT_FUNCS["first_of_day"](rows)]
    ok("unit: first_of_day is the day's earliest candidate", got == ["A"], str(got))
    # every_signal = every traded row
    rows = [R(d, "09:31", "A", 1), R(d, "09:40", "B", 1, status="skipped", traded=False)]
    got = [r["sym"] for r in loop_cycle.UNIT_FUNCS["every_signal"](rows)]
    ok("unit: every_signal is every traded row", got == ["A"], str(got))
    # a scratch burns a slot (named, not faulted)
    rows = [R(d, "09:31", "A", 0.0), R(d, "09:40", "B", 0.0), R(d, "09:50", "C", 0.0),
            R(d, "10:00", "D", 900)]
    got = [r["sym"] for r in loop_cycle.up_to_3_rows(rows)]
    ok("unit: a zero-P&L scratch burns one of the three slots (behaviour, not a fault)",
       got == ["A", "B", "C"], str(got))


# ---------------------------------- 4. --dry-run really changes nothing now

def synth_book(seed_pnl, n_months=26, per_month=4):
    """A book with >=30 trades and >=12 months in each half of 2025-09-01."""
    rows = []
    y, m = 2024, 9
    for i in range(n_months):
        for k in range(per_month):
            day = "%04d-%02d-%02d" % (y, m, 2 + k * 3)
            rows.append(R(day, "09:3%d" % k, "SYM%d" % k, seed_pnl(i, k)))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return {"meta": {"sessions": len({r["day"] for r in rows}),
                     "stamp": {"book_id": "synthetic"}},
            "trades": rows}


def write_gz(path, obj):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(obj, f)


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest() if Path(p).exists() else None


def check_dry_run():
    scratch = Path(tempfile.mkdtemp(prefix="o4ref3_"))
    old = (loop_cycle.TAPE, loop_cycle.CYCLES_MD, loop_cycle.STATE_JSON, notify_ntfy.push)
    pushes = []
    try:
        loop_cycle.TAPE = scratch
        loop_cycle.CYCLES_MD = scratch / "cycles.md"
        loop_cycle.STATE_JSON = scratch / "loop_state.json"
        notify_ntfy.push = lambda *a, **k: pushes.append(a)

        off = synth_book(lambda i, k: 100.0 if k < 3 else -50.0)
        on = synth_book(lambda i, k: 100.0 if k < 3 else -50.0)
        write_gz(scratch / "book_FOO_off.json.gz", off)
        write_gz(scratch / "book_FOO_on.json.gz", on)
        loop_cycle.STATE_JSON.write_text(json.dumps(
            {"cycle_count": 7, "consecutive_holds": 3, "target_met": False, "history": []},
            indent=2), encoding="utf-8")
        loop_cycle.CYCLES_MD.write_text("# loop cycles\n\nseed\n", encoding="utf-8")

        cfg = {"unit": "up_to_3_stop_win_or_2loss", "halves_boundary": "2025-09-01",
               "gate": {"max_dollar_drop_pct": 5.0},
               "targets": {"dollars_per_day": 500, "avg_win_over_avg_loss": 2.0}}

        s_before, c_before = md5(loop_cycle.STATE_JSON), md5(loop_cycle.CYCLES_MD)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = loop_cycle.stage_gate(cfg, "FOO", "a plain english label", dry_run=True)
        ok("dry-run: loop_state.json byte-identical after a gate",
           md5(loop_cycle.STATE_JSON) == s_before)
        ok("dry-run: cycles.md byte-identical after a gate",
           md5(loop_cycle.CYCLES_MD) == c_before)
        ok("dry-run: no ntfy push", pushes == [])
        ok("dry-run: still prints the decision JSON", '"decision"' in buf.getvalue())
        ok("dry-run: on-disk cycle_count unmoved",
           json.loads(loop_cycle.STATE_JSON.read_text())["cycle_count"] == 7)
        ok("dry-run: on-disk consecutive_holds unmoved",
           json.loads(loop_cycle.STATE_JSON.read_text())["consecutive_holds"] == 3)

        # and the real path still writes
        with contextlib.redirect_stdout(io.StringIO()):
            out2 = loop_cycle.stage_gate(cfg, "FOO", "a plain english label", dry_run=False)
        st = json.loads(loop_cycle.STATE_JSON.read_text())
        ok("live run: cycle_count advances 7 -> 8", st["cycle_count"] == 8, str(st["cycle_count"]))
        ok("live run: exactly one ledger row appended",
           loop_cycle.CYCLES_MD.read_text().count("| FOO |") == 1)
        ok("live run: exactly one ntfy push", len(pushes) == 1, str(pushes))
        line = pushes[0][1] if pushes else ""
        ok("push text: carries the plain-English label", "a plain english label" in line, line)
        ok("push text: carries no flag name", "FOO" not in line, line)
        ok("push text: no ticket ids / CLI jargon",
           all(t not in line.lower() for t in ("o4", "book_id", ".py", "flag", "dry-run")), line)

        # residual: the ledger is still not idempotent on a NON-dry re-run
        with contextlib.redirect_stdout(io.StringIO()):
            loop_cycle.stage_gate(cfg, "FOO", "a plain english label", dry_run=False)
        ok("RESIDUAL: a second live gate of the same pair appends a SECOND ledger row",
           loop_cycle.CYCLES_MD.read_text().count("| FOO |") == 2,
           "duplicate-append is unguarded; only --dry-run was fixed")
        return out, out2
    finally:
        (loop_cycle.TAPE, loop_cycle.CYCLES_MD, loop_cycle.STATE_JSON, notify_ntfy.push) = old


# ---------------------------------- 5. the OFF arm really strips ambient env

FAKE_BT = '''
import argparse, json, os, sys
ap = argparse.ArgumentParser()
ap.add_argument("--days"); ap.add_argument("--out", required=True)
a = ap.parse_args()
json.dump({"meta": {"sessions": 1, "days": a.days,
                    "seen_flag": os.environ.get("PLANTED_O4_FLAG", "<absent>"),
                    "stamp": {"book_id": "fake"}},
           "trades": []}, open(a.out, "w"))
'''


def check_off_arm_env():
    scratch = Path(tempfile.mkdtemp(prefix="o4ref3env_"))
    fake = scratch / "fake_bt.py"
    fake.write_text(FAKE_BT, encoding="utf-8")
    old_tape, old_logs = loop_cycle.TAPE, loop_cycle.LOGS
    old_env = os.environ.get("PLANTED_O4_FLAG")
    try:
        loop_cycle.TAPE = scratch
        loop_cycle.LOGS = scratch / "logs"
        os.environ["PLANTED_O4_FLAG"] = "1"          # ambient value equal to --on's
        rebuild = {"script": str(fake), "args": ["--days", "730"], "env": {}}
        cfg = {"rebuild": rebuild, "baseline_book": "unused"}
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            res = loop_cycle.stage_build(cfg, "PLANTED_O4_FLAG", "1", smoke=True)
        offm, _ = loop_cycle.load_book_any(scratch / "book_PLANTED_O4_FLAG_off.json.gz")
        onm, _ = loop_cycle.load_book_any(scratch / "book_PLANTED_O4_FLAG_on.json.gz")
        ok("OFF arm: an ambient flag value is stripped from the subprocess env",
           offm["seen_flag"] == "<absent>", "saw %r" % offm["seen_flag"])
        ok("ON arm: the flag is set to --on's value", onm["seen_flag"] == "1",
           "saw %r" % onm["seen_flag"])
        ok("smoke: both arms invoked with --days 15",
           offm["days"] == "15" and onm["days"] == "15",
           "off=%s on=%s" % (offm["days"], onm["days"]))
        ok("smoke: the OFF==baseline book_id check is skipped and both arms built",
           res.get("decision") == "built", str(res))
    finally:
        loop_cycle.TAPE, loop_cycle.LOGS = old_tape, old_logs
        if old_env is None:
            os.environ.pop("PLANTED_O4_FLAG", None)
        else:
            os.environ["PLANTED_O4_FLAG"] = old_env


# ------------------------------------ 6. the blocked path (mismatched book_id)

def check_blocked():
    scratch = Path(tempfile.mkdtemp(prefix="o4ref3blk_"))
    fake = scratch / "fake_bt.py"
    fake.write_text(FAKE_BT, encoding="utf-8")
    old_tape, old_logs = loop_cycle.TAPE, loop_cycle.LOGS
    try:
        loop_cycle.TAPE = scratch
        loop_cycle.LOGS = scratch / "logs"
        baseline = scratch / "baseline.json.gz"
        write_gz(baseline, {"meta": {"sessions": 1, "stamp": {"book_id": "DIFFERENT"}},
                            "trades": []})
        rebuild = {"script": str(fake), "args": [], "env": {}}
        cfg = {"rebuild": rebuild, "baseline_book": str(baseline)}
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            res = loop_cycle.stage_build(cfg, "SOME_FLAG", "1", smoke=False)
        ok("blocked: a book_id mismatch yields decision 'blocked', not 'hold'",
           res.get("decision") == "blocked", str(res.get("decision")))
        ok("blocked: it compares real book_stamp ids",
           res.get("baseline_book_id") == "DIFFERENT" and res.get("off_book_id") == "fake",
           "%s vs %s" % (res.get("baseline_book_id"), res.get("off_book_id")))
        ok("blocked: the ON arm was never built",
           not (scratch / "book_SOME_FLAG_on.json.gz").exists())
        src = (ROOT / "research" / "loop_cycle.py").read_text(encoding="utf-8")
        ok("blocked: main() exits non-zero on blocked", "sys.exit(1)" in src)
    finally:
        loop_cycle.TAPE, loop_cycle.LOGS = old_tape, old_logs


# --------------------------- 7. the real DAY_POLICY pair, re-priced from scratch

def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%04d-W%02d" % (y, w)


def ref_unit(rows):
    byday = {}
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday.setdefault(r["day"], []).append(r)
    out = []
    for day in sorted(byday):
        losses = 0
        for i, r in enumerate(sorted(byday[day], key=lambda x: (x.get("et") or "", x.get("sym") or ""))):
            if i >= 3:
                break
            out.append(r)
            if r.get("pnl", 0.0) > 0:
                break
            if r.get("pnl", 0.0) < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


def ref_stats(rows, n_days):
    if not rows or not n_days:
        return {"trades": 0, "per_day": 0.0, "months_green": 0, "months": 0}
    by_m = {}
    for r in rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r["pnl"]
    return {"trades": len(rows),
            "per_day": round(sum(r["pnl"] for r in rows) / n_days, 0),
            "months_green": sum(1 for v in by_m.values() if v > 0),
            "months": len(by_m)}


def check_real_pair():
    offp = ROOT / "research" / "tape" / "book_DAY_POLICY_off.json.gz"
    onp = ROOT / "research" / "tape" / "book_DAY_POLICY_on.json.gz"
    if not offp.exists() or not onp.exists():
        ok("real pair: DAY_POLICY books present", False, "missing")
        return
    om, orows = loop_cycle.load_book_any(offp)
    nm, nrows = loop_cycle.load_book_any(onp)
    core = [r for r in orows if r.get("tier") == "core"]
    coren = [r for r in nrows if r.get("tier") == "core"]
    n_off = om.get("sessions") or len({r["day"] for r in core})
    n_on = nm.get("sessions") or len({r["day"] for r in coren})
    b = ref_stats(ref_unit(core), n_off)
    a = ref_stats(ref_unit(coren), n_on)
    ok("real pair: ledger row '-52.0 -> -52.0' reproduces",
       b["per_day"] == -52.0 and a["per_day"] == -52.0, "%s -> %s" % (b["per_day"], a["per_day"]))
    ok("real pair: ledger row '11 -> 11' green months reproduces",
       b["months_green"] == 11 and a["months_green"] == 11,
       "%s -> %s" % (b["months_green"], a["months_green"]))
    ok("real pair: 769 trades on the ON arm reproduces", a["trades"] == 769, str(a["trades"]))
    ok("real pair: >=30 trades and >=12 months (a verdict is allowed)",
       a["trades"] >= 30 and a["months"] >= 12, "%d trades / %d months" % (a["trades"], a["months"]))
    # the zero delta FINDING-3, restated
    ids_b = [(r["sym"], r["day"], r["et"]) for r in ref_unit(core)]
    ids_a = [(r["sym"], r["day"], r["et"]) for r in ref_unit(coren)]
    ok("FINDING-3 still standing: the priced unit selects identical rows in both arms",
       ids_b == ids_a, "%d vs %d rows, identical=%s" % (len(ids_b), len(ids_a), ids_b == ids_a))
    ok("FINDING-3: the underlying books DO differ (traded rows)",
       sum(1 for r in core if r.get("traded")) != sum(1 for r in coren if r.get("traded")),
       "%d OFF vs %d ON traded core rows"
       % (sum(1 for r in core if r.get("traded")), sum(1 for r in coren if r.get("traded"))))
    for tag, meta in (("off", om), ("on", nm)):
        st = meta.get("stamp", {})
        g = st.get("git", {})
        ok("stamp: DAY_POLICY %s book carries commit/flags/date/window" % tag,
           bool(g.get("commit")) and bool(st.get("flags")) and bool(st.get("built_at"))
           and bool(meta.get("first")) and bool(meta.get("last")) and bool(meta.get("sessions")),
           "commit=%s dirty_py=%s window=%s..%s/%s" % (
               (g.get("commit") or "")[:8], g.get("dirty_py_count"),
               meta.get("first"), meta.get("last"), meta.get("sessions")))
        ok("stamp: DAY_POLICY %s book was built on a clean engine tree" % tag,
           g.get("dirty_engine_py") == [] and g.get("dirty_py_count") == 0,
           str(g.get("dirty_engine_py")))
        ok("stamp: DAY_POLICY %s book stamps the flag under test" % tag,
           "signal_runner.DAY_POLICY" in (st.get("flags") or {}),
           str((st.get("flags") or {}).get("signal_runner.DAY_POLICY")))


# -------------------------------------------------------- 8. docstring truth

def check_docs():
    src = (ROOT / "research" / "loop_cycle.py").read_text(encoding="utf-8")
    ok("doc: --dry-run's argparse help still says only 'suppress the ntfy push'",
       'help="suppress the ntfy push"' not in src,
       "stale help text -- --dry-run now also suppresses two writes")
    ok("doc: module docstring describes --dry-run as covering the writes",
       "unless `--dry-run`" in src or "unless --dry-run" in src,
       "docstring lists append/update unconditionally then '(unless --dry-run)' on the push only")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    print("== gate ==");      check_gate()
    print("== boundary ==");  check_boundary()
    print("== units ==");     check_units()
    print("== dry-run ==");   check_dry_run()
    print("== off arm env =="); check_off_arm_env()
    print("== blocked ==");   check_blocked()
    print("== docs ==");      check_docs()
    if not args.quick:
        print("== real pair =="); check_real_pair()
    print("\n%d checks, %d failed" % (len(CHECKS), len(FAILS)))
    for f in FAILS:
        print("  FAIL " + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
