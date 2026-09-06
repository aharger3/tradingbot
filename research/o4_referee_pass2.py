"""o4_referee_pass2.py -- second referee pass on row O4's loop controller.

Pass 1 (research/o4_referee.md / o4_referee.py, commit 27e7e04a) upheld the row
with one defect: build_book() never unsets the flag for the OFF arm. The
builder's re-dispatch report claims that defect "was subsequently repaired by
other rows (d317ff43 L2 repair, 5e8b5b89 L5 repair)". This pass re-derives the
gate independently AGAIN, on the omen-10.0 baseline's own book pair rather than
pass 1's older htfveto pair, and tests that repair claim directly.

Nothing here imports loop_cycle's arithmetic except to diff it against a
from-scratch implementation written from SWARM.md law 2/3.

Checks:
  1  gate percentage math, both signs of the baseline, both edges of 5%
  2  green-months rule and the 30-trade / 12-month sample floor
  3  halves boundary: a session ON 2025-09-01 belongs to H2
  4  the three unit functions vs hand-built row sets
  5  a REAL pair of books (DAY_POLICY off/on, the loop's own baseline pair)
     re-priced from scratch and compared to the row loop_cycle wrote into
     research/tape/cycles.md
  6  the whole-window denominator vs the halves' after universe.row_filter
  7  the OFF-arm book_id equality path: book_stamp ids, mismatch -> blocked
  8  --dry-run never reaches notify_ntfy.push
  9  the ntfy line carries no flag name
 10  DEFECT-1: is --dry-run actually a dry run? (ledger/state side effects)
 11  DEFECT-2: pass 1's OFF-arm env defect -- still open at HEAD?
 12  FINDING-3: the unit that prices a cycle can be the flag under test

Run: python research/o4_referee_pass2.py
"""
from __future__ import annotations

import gzip
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import loop_cycle as lc          # noqa: E402
from research import book_stamp                # noqa: E402

TAPE = ROOT / "research" / "tape"
FAILS = []
NOTES = []


def check(name, ok, detail=""):
    print("%-4s %s%s" % ("OK" if ok else "FAIL", name, ("  -- " + detail) if detail else ""))
    if not ok:
        FAILS.append(name + (" -- " + detail if detail else ""))


def note(s):
    print("     note: " + s)
    NOTES.append(s)


# ---------------------------------------------------------------- 1/2  the gate

def my_half_verdict(before, after, drop_pct=5.0):
    """Written from SWARM.md law 2 + law 3, not from loop_cycle."""
    if before["trades"] < 30 or before["months"] < 12:
        return None                                   # no verdict
    if after["months_green"] < before["months_green"]:
        return False
    b, a = before["per_day"], after["per_day"]
    allowed = b - abs(b) * drop_pct / 100.0           # "may fall at most N%"
    return a >= allowed


def gate_checks():
    cases = [
        # before$/day, after$/day, greenB, greenA, trades, months
        (100.0, 95.1, 13, 13, 40, 13),
        (100.0, 94.9, 13, 13, 40, 13),
        (100.0, 95.0, 13, 13, 40, 13),
        (100.0, 150.0, 13, 13, 40, 13),
        (100.0, 1e9, 13, 13, 40, 13),
        (-100.0, -105.1, 13, 13, 40, 13),
        (-100.0, -104.9, 13, 13, 40, 13),
        (-100.0, -95.0, 13, 13, 40, 13),
        (-100.0, 500.0, 13, 13, 40, 13),
        (0.0, 0.0, 13, 13, 40, 13),
        (0.0, -1.0, 13, 13, 40, 13),
        (100.0, 100.0, 13, 12, 40, 13),      # green falls: must fail
        (100.0, 100.0, 13, 14, 40, 13),
        (100.0, 95.1, 13, 13, 29, 13),       # under the trade floor
        (100.0, 95.1, 13, 13, 40, 11),       # under the month floor
        (100.0, 95.1, 13, 13, 30, 12),       # exactly on the floor
    ]
    agree = True
    for b, a, gb, ga, tr, mo in cases:
        before = {"per_day": b, "months_green": gb, "trades": tr, "months": mo}
        after = {"per_day": a, "months_green": ga, "trades": tr, "months": mo}
        theirs = lc.half_verdict(before, after, 5.0)
        mine = my_half_verdict(before, after)
        theirs_val = None if not theirs["enough"] else theirs["pass"]
        if theirs_val != mine:
            agree = False
            check("gate case b=%s a=%s green %s->%s tr=%s mo=%s" % (b, a, gb, ga, tr, mo),
                  False, "loop_cycle=%r referee=%r" % (theirs_val, mine))
    check("gate: 16 hand cases agree with an independent implementation", agree)

    check("a fall of more than 5 pct fails",
          lc.half_verdict({"per_day": 100, "months_green": 1, "trades": 40, "months": 13},
                          {"per_day": 94.9, "months_green": 1}, 5.0)["pass"] is False)
    check("a rise always passes",
          lc.half_verdict({"per_day": 100, "months_green": 1, "trades": 40, "months": 13},
                          {"per_day": 1e12, "months_green": 1}, 5.0)["pass"] is True)
    check("green months falling fails on its own",
          lc.half_verdict({"per_day": 100, "months_green": 13, "trades": 40, "months": 13},
                          {"per_day": 100, "months_green": 12}, 5.0)["pass"] is False)


# ------------------------------------------------------------------ 3  halves

def halves_checks():
    rows = [{"day": "2025-08-31"}, {"day": "2025-09-01"}, {"day": "2025-09-02"}]
    h1, h2 = lc.split_halves(rows, "2025-09-01")
    check("2025-09-01 itself lands in H2",
          [r["day"] for r in h1] == ["2025-08-31"]
          and [r["day"] for r in h2] == ["2025-09-01", "2025-09-02"])
    n1, n2 = lc.half_n_days(rows, "2025-09-01")
    check("half_n_days matches the split", (n1, n2) == (1, 2), "got %s" % ((n1, n2),))
    src = inspect.getsource(lc.stage_gate)
    check("ship requires both halves enough AND pass",
          'h1v["enough"] and h1v["pass"] and h2v["enough"] and h2v["pass"]' in src)


# ------------------------------------------------------------------- 4  units

def unit_checks():
    def r(day, et, sym, pnl, status="fired", traded=True):
        return {"day": day, "et": et, "sym": sym, "pnl": pnl,
                "status": status, "traded": traded}

    rows = [r("d1", "09:35", "A", -10), r("d1", "09:40", "B", 50),
            r("d1", "09:45", "C", 99),
            r("d2", "09:35", "A", -10), r("d2", "09:40", "B", -10),
            r("d2", "09:45", "C", 99),
            r("d3", "09:35", "A", -1), r("d3", "09:40", "B", -0.0),
            r("d3", "09:45", "C", -1), r("d3", "09:50", "D", 99)]
    out = lc.UNIT_FUNCS["up_to_3_stop_win_or_2loss"](rows)
    got = {}
    for x in out:
        got.setdefault(x["day"], []).append(x["sym"])
    check("day policy: stop after the first win", got.get("d1") == ["A", "B"],
          "got %s" % got.get("d1"))
    check("day policy: stop after the second loss", got.get("d2") == ["A", "B"],
          "got %s" % got.get("d2"))
    check("day policy: hard cap of 3 fires", got.get("d3") == ["A", "B", "C"],
          "got %s" % got.get("d3"))
    check("every_signal = every traded row",
          len(lc.UNIT_FUNCS["every_signal"](rows)) == 10)
    fod = lc.UNIT_FUNCS["first_of_day"](rows)
    check("first_of_day = one row a day, the earliest",
          [(x["day"], x["sym"]) for x in fod] == [("d1", "A"), ("d2", "A"), ("d3", "A")])

    z = [r("z", "09:35", "A", 0.0), r("z", "09:40", "B", 0.0),
         r("z", "09:45", "C", 0.0), r("z", "09:50", "D", 500.0)]
    if [x["sym"] for x in lc.UNIT_FUNCS["up_to_3_stop_win_or_2loss"](z)] == ["A", "B", "C"]:
        note("a zero-pnl scratch burns one of the three slots -- matches the cap wording")
    h = [r("h", "09:35", "A", 0.0, status="halted", traded=False),
         r("h", "09:40", "B", 500.0)]
    note("halted rows are in the candidate pool: %s (g72.oneaday_rows does the same)"
         % [x["sym"] for x in lc.UNIT_FUNCS["up_to_3_stop_win_or_2loss"](h)])


# ----------------------------------------------- 5/6  a real pair of books

def real_book_check():
    off = TAPE / "book_DAY_POLICY_off.json.gz"
    on = TAPE / "book_DAY_POLICY_on.json.gz"
    if not (off.exists() and on.exists()):
        check("real book pair present", False, "no DAY_POLICY books on disk")
        return

    cfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))
    boundary = cfg["halves_boundary"]

    def load(p):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            b = json.load(f)
        return b["meta"], b["trades"]

    om, orows = load(off)
    nm, nrows = load(on)
    ofil = [r for r in orows if r.get("tier") == "core"]
    nfil = [r for r in nrows if r.get("tier") == "core"]
    check("universe.row_filter selects a non-empty core slice",
          0 < len(ofil) < len(orows), "%d of %d rows" % (len(ofil), len(orows)))
    syms = sorted({r.get("sym") for r in ofil})
    check("the core slice is exactly loop.json's 11 symbols",
          syms == sorted(cfg["universe"]["symbols"]), "got %s" % syms)

    def my_unit(rows):
        byday = {}
        for r in rows:
            if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
                byday.setdefault(r["day"], []).append(r)
        out = []
        for day in sorted(byday):
            losses = 0
            for i, r in enumerate(sorted(byday[day],
                                         key=lambda x: (x.get("et") or "", x.get("sym") or ""))):
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

    def my_figs(rows, n_days):
        bym = {}
        for r in rows:
            bym[r["day"][:7]] = bym.get(r["day"][:7], 0.0) + r["pnl"]
        return {"trades": len(rows),
                "per_day": round(sum(r["pnl"] for r in rows) / n_days, 0) if n_days else 0.0,
                "months": len(bym),
                "months_green": sum(1 for v in bym.values() if v > 0)}

    store = {}
    for tag, meta, fil in (("off", om, ofil), ("on", nm, nfil)):
        u = my_unit(fil)
        days = sorted({r["day"] for r in fil if r.get("day")})
        n1 = sum(1 for d in days if d < boundary)
        n2 = len(days) - n1
        mine_all = {"whole": my_figs(u, meta.get("sessions") or len(days)),
                    "h1": my_figs([r for r in u if r["day"] < boundary], n1),
                    "h2": my_figs([r for r in u if r["day"] >= boundary], n2)}
        theirs = lc.compute_all(meta, fil, cfg["unit"], boundary)
        for sl, mine in mine_all.items():
            t = theirs[sl]
            check("real %s book, %s slice re-derived independently" % (tag, sl),
                  all(abs((t.get(k) or 0) - (mine[k] or 0)) < 1e-6 for k in mine),
                  "referee=%s loop_cycle=%s" % (mine, {k: t.get(k) for k in mine}))
        store[tag] = theirs
        if tag == "off":
            store["days"] = (n1, n2, meta.get("sessions"))

    n1, n2, sessions = store["days"]
    if n1 + n2 != sessions:
        note("whole-window $/day divides by meta['sessions']=%d (the FULL pool) while "
             "the halves divide by core-slice day counts %d+%d=%d" % (sessions, n1, n2, n1 + n2))
    else:
        check("whole and halves share a denominator (%d = %d + %d)" % (sessions, n1, n2), True)

    b, a = store["off"], store["on"]
    v1 = lc.half_verdict(b["h1"], a["h1"], cfg["gate"]["max_dollar_drop_pct"])
    v2 = lc.half_verdict(b["h2"], a["h2"], cfg["gate"]["max_dollar_drop_pct"])
    decision = "ship" if (v1["enough"] and v1["pass"] and v2["enough"] and v2["pass"]) else "hold"
    print("     DAY_POLICY re-derived: $/day %s -> %s, green %s -> %s, trades %s -> %s, "
          "H1 %s H2 %s, decision %s"
          % (b["whole"]["per_day"], a["whole"]["per_day"],
             b["whole"]["months_green"], a["whole"]["months_green"],
             b["whole"]["trades"], a["whole"]["trades"],
             my_half_verdict(b["h1"], a["h1"]), my_half_verdict(b["h2"], a["h2"]), decision))
    row = [l for l in (TAPE / "cycles.md").read_text(encoding="utf-8").splitlines()
           if "| DAY_POLICY |" in l]
    check("a DAY_POLICY row exists in cycles.md", bool(row))
    if row:
        cells = [c.strip() for c in row[-1].strip("|").split("|")]
        check("ledger decision matches the re-derived gate", cells[3] == decision,
              "ledger=%s referee=%s" % (cells[3], decision))
        check("ledger $/day matches the re-derived figures",
              cells[4] == "%s -> %s" % (b["whole"]["per_day"], a["whole"]["per_day"]),
              "ledger=%r" % cells[4])
        check("ledger green months match",
              cells[5] == "%s -> %s" % (b["whole"]["months_green"], a["whole"]["months_green"]),
              "ledger=%r" % cells[5])
        check("ledger trades match the AFTER arm", cells[8] == str(a["whole"]["trades"]),
              "ledger=%r referee=%r" % (cells[8], a["whole"]["trades"]))
    globals()["_STORE"] = store


# ------------------------------------------------- 7  the OFF-arm book_id path

def book_id_path_check():
    src = inspect.getsource(lc.stage_build)
    check("OFF arm compares book_stamp book_ids",
          "book_stamp.book_id" in src and 'stamp", {}).get("book_id"' in src)
    check("a book_id mismatch yields decision 'blocked', not 'hold'",
          '"decision": "blocked"' in src and '"hold"' not in src)
    msrc = inspect.getsource(lc.main)
    check("blocked exits non-zero and never runs the gate",
          'result.get("decision") == "blocked"' in msrc and "sys.exit(1)" in msrc)
    a = [{"sym": "X", "day": "d", "et": "e", "dir": "long", "entry": 1.0,
          "stop": 0.5, "pnl": 10.0, "status": "fired", "traded": True}]
    check("book_id changes when a trade's pnl changes",
          book_stamp.book_id(a) != book_stamp.book_id([dict(a[0], pnl=11.0)]))
    cfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))
    bp = ROOT / cfg["baseline_book"]
    if bp.exists():
        with gzip.open(bp, "rt", encoding="utf-8") as f:
            rid = book_stamp.book_id(json.load(f)["trades"])
        check("baseline book_id in loop.json matches the book on disk",
              rid == cfg["baseline_book_id"], "disk=%s config=%s" % (rid, cfg["baseline_book_id"]))
        offp = TAPE / "book_DAY_POLICY_off.json.gz"
        if offp.exists():
            with gzip.open(offp, "rt", encoding="utf-8") as f:
                oid = book_stamp.book_id(json.load(f)["trades"])
            check("the DAY_POLICY OFF arm reproduces the baseline book_id", oid == rid,
                  "off=%s baseline=%s" % (oid, rid))


# --------------------------------------------------- 8/9  the push, and dry-run

def push_checks():
    src = inspect.getsource(lc.stage_gate)
    i_guard, i_push = src.find("if not dry_run:"), src.find("notify_ntfy.push")
    check("--dry-run guards the only notify_ntfy.push call",
          i_guard != -1 and i_push > i_guard and src.count("notify_ntfy.push") == 1)
    check("no notify_ntfy.push anywhere else in loop_cycle.py",
          Path(lc.__file__).read_text(encoding="utf-8").count("notify_ntfy.push") == 1)
    line_src = src[src.find('line = ('):i_push]
    check("the ntfy line interpolates the plain-English label, never the flag",
          "label" in line_src and "flag" not in line_src)
    for word in ("MIN_PT1_R", "DAY_POLICY", "TREND_DEF", "book_id", "--stage"):
        check("ntfy text carries no jargon token %r" % word, word not in line_src)


# --------------------------------------------------------- the smoke-run claim

def smoke_check():
    src = inspect.getsource(lc.build_book)
    check("--smoke forces --days 15 on BOTH arms", '["--days", "15"] if smoke' in src)
    ssrc = inspect.getsource(lc.stage_build)
    check("--smoke skips the OFF-vs-baseline book_id assertion",
          "skipping the OFF==baseline book_id check" in ssrc)
    hits = []
    logs = TAPE / "logs"
    if logs.exists():
        for p in sorted(logs.glob("*.log")):
            try:
                if "--days 15" in p.read_text(encoding="utf-8", errors="replace"):
                    hits.append(p.name)
            except Exception:
                pass
    check("a log recording a 15-day smoke build exists in research/tape/logs/", bool(hits),
          "none -- logs/ is gitignored; the referee re-ran the smoke by hand, see the md")
    if hits:
        print("     smoke logs: %s" % hits)


# ------------------------------------ 10  DEFECT-1: is --dry-run a dry run?

def dry_run_side_effect_check():
    """stage_gate appends to cycles.md and rewrites loop_state.json BEFORE the
    push guard, so `--dry-run` still mutates the ledger and the stop counter.
    Demonstrated against scratch copies; the live ledger is not touched."""
    import tempfile
    scratch = Path(tempfile.mkdtemp(prefix="o4ref2_"))
    real_cycles, real_state = lc.CYCLES_MD, lc.STATE_JSON
    cfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))
    if not (TAPE / "book_DAY_POLICY_off.json.gz").exists():
        return
    try:
        lc.CYCLES_MD = scratch / "cycles.md"
        lc.STATE_JSON = scratch / "loop_state.json"
        lc.STATE_JSON.write_text(json.dumps(
            {"cycle_count": 7, "consecutive_holds": 3, "target_met": False, "history": []}),
            encoding="utf-8")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = lc.stage_gate(cfg, "DAY_POLICY", "referee dry-run probe", dry_run=True)
        st = json.loads(lc.STATE_JSON.read_text(encoding="utf-8"))
        wrote = lc.CYCLES_MD.exists() and "DAY_POLICY" in lc.CYCLES_MD.read_text(encoding="utf-8")
        check("DEFECT-1: --dry-run does NOT mutate cycles.md", not wrote,
              "a --dry-run gate appended a ledger row")
        check("DEFECT-1: --dry-run does NOT bump loop_state.json's cycle_count",
              st["cycle_count"] == 7, "cycle_count 7 -> %d" % st["cycle_count"])
        check("DEFECT-1: --dry-run does NOT touch consecutive_holds / the stop counter",
              st["consecutive_holds"] == 3,
              "consecutive_holds 3 -> %d (decision=%s); at %d the controller tells the "
              "dispatcher to stop" % (st["consecutive_holds"], out["decision"],
                                      lc.MAX_CONSECUTIVE_HOLDS))
    finally:
        lc.CYCLES_MD, lc.STATE_JSON = real_cycles, real_state


# ---------------- 11  DEFECT-2: pass 1's OFF-arm env defect, still open?

def off_arm_env_check():
    bsrc = inspect.getsource(lc.build_book)
    ssrc = inspect.getsource(lc.stage_build)
    unsets = ("env.pop(" in bsrc) or ("del env[" in bsrc) or ("env.pop(" in ssrc)
    flag_reaches_build = "build_book({}, off_path" not in ssrc
    check("DEFECT-2: the OFF arm unsets the flag under test before building",
          unsets, "build_book() does `env = dict(os.environ)` and only ADDS keys; "
                  "stage_build calls build_book({}, off_path, ...) so the flag name "
                  "never even reaches the builder. Pass 1 (27e7e04a) named this; the "
                  "builder's report claims d317ff43/5e8b5b89 repaired it -- they did "
                  "not (d317ff43 added the universe row filter, 5e8b5b89 scoped "
                  "day_policy). Still open at HEAD.")
    if not flag_reaches_build:
        note("stage_build still passes an empty override dict for the OFF arm, so a "
             "one-line env.pop() fix is not even possible without threading the flag "
             "name through -- unchanged since 8ecb043e")


# ----------------- 12  FINDING-3: the unit can be the flag under test

def unit_masks_flag_check():
    off, on = TAPE / "book_DAY_POLICY_off.json.gz", TAPE / "book_DAY_POLICY_on.json.gz"
    if not (off.exists() and on.exists()):
        return

    def load(p):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)["trades"]

    oc = [r for r in load(off) if r.get("tier") == "core"]
    nc = [r for r in load(on) if r.get("tier") == "core"]
    ot, nt = sum(1 for r in oc if r.get("traded")), sum(1 for r in nc if r.get("traded"))
    ou = lc.UNIT_FUNCS["up_to_3_stop_win_or_2loss"](oc)
    nu = lc.UNIT_FUNCS["up_to_3_stop_win_or_2loss"](nc)

    def key(rs):
        return [(r["day"], r.get("et"), r.get("sym"), round(r.get("pnl", 0), 4)) for r in rs]

    note("FINDING-3: DAY_POLICY core-11 traded rows %d (off) vs %d (on) -- the arms "
         "differ by %d trades in the engine, but the priced unit selects %s rows "
         "(%d vs %d). Cycle 5's 'ship' rests on a delta of exactly zero."
         % (ot, nt, ot - nt, "the IDENTICAL" if key(ou) == key(nu) else "different",
            len(ou), len(nu)))


def main():
    print("=== O4 referee pass 2: research/loop_cycle.py (builder commit 8ecb043e) ===")
    gate_checks()
    halves_checks()
    unit_checks()
    book_id_path_check()
    push_checks()
    smoke_check()
    real_book_check()
    dry_run_side_effect_check()
    off_arm_env_check()
    unit_masks_flag_check()
    print("\nFAILURES: %d" % len(FAILS))
    for f in FAILS:
        print("  - " + f)
    print("NOTES: %d" % len(NOTES))
    for n in NOTES:
        print("  - " + n)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
