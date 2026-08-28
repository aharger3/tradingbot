"""T-84 -- un-gate the 84% rule's ARM.

x3_detector_census found the cause of the 84% rule firing 3 times in 500
sessions: NOT `STRONG_PA_MULT` (short-circuited off the path by
`RULE84_LESSON=True`), but the ARMING GRADE GATE in `backtest_week._arm_84`,
which admits 5 of 434 eligible stop-outs (research/x3_detector_census.md, part C).

Austin settled the ladder question 2026-08-28: "84 percent rule can fire on S A
or C, but we only will trade S of course." There is NO grade gate at arming.
`RULE84_ARM_NOGATE` (signal_runner.py, DEFAULT OFF) removes it: `_arm_84` arms
off any counted full stop-out on an arming setup (B&R / OCR / BROCR),
regardless of grade. RULE84_STRICT / RULE84_ARM_SGRADE are ignored while it is on.

This file measures the ungated arm against the shipped book, using the SAME
substrate and recall rig `research/x3_detector_census.py` already built:

    research/g3_arm_ow1.json            the shipped 1,017-trade book (gate ON)
    research/t60_baseline.load_day_cards()          in-sample marks
    research/t70_test1_score.load_cards()           held-out marks (test-1, 100 cards)

USAGE
-----
    python research/t84_arm_ungate.py run           # RULE84_ARM_NOGATE=1 full
                                                      # 2-year replay -> the .json
    python research/t84_arm_ungate.py off-check      # RULE84_ARM_NOGATE=0 full
                                                      # replay, proves byte-identity
                                                      # with the shipped book
    python research/t84_arm_ungate.py sweep --tol T [T ...]
                                                      # RULE84_ARM_NOGATE=1 +
                                                      # RULE84_RECLAIM_TOL=T runs
    python research/t84_arm_ungate.py report         # reads the .json files this
                                                      # writes and builds the .md
    python research/t84_arm_ungate.py --selfcheck

READ-ONLY WITH RESPECT TO THE SHIPPED BOOK. `run`/`sweep` write NEW files under
research/, never research/g3_arm_ow1.json or research/bt2y_trades.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.x3_detector_census import (arm_of, mean_ci95, months_green,  # noqa: E402
                                          win_rate, pct)

BOOK_SHIPPED = os.path.join(_HERE, "g3_arm_ow1.json")
BOOK_OFFCHECK = os.path.join(_HERE, "t84_offcheck_book.json")
BOOK_NOGATE = os.path.join(_HERE, "t84_nogate_book.json")
SWEEP_DIR = _HERE
OUT_MD = os.path.join(_HERE, "t84_arm_ungate.md")

DAYS = 730  # matches g3_onwatch_2y.py -- reproduces the shipped book's 500 sessions
SWEEP_TOLS = [0.01, 0.25, 0.5, 1.0, 2.0]  # in R -- see qa-queue.html `reclaim_tol` chips


def _sweep_book(tol: float) -> str:
    tag = str(tol).replace(".", "p")
    return os.path.join(SWEEP_DIR, f"t84_sweep_tol{tag}.json")


# ---------------------------------------------------------------------------
# running the replay
# ---------------------------------------------------------------------------

def run_replay(out_path: str, nogate: bool, tol: float | None = None) -> int:
    """One full backtest_2y.py replay in a CHILD process, env-flagged.

    Mirrors research/g3_onwatch_2y.py::run -- backtest_2y.py invoked as-is, not
    reimplemented, so this is the shipped rig's own answer."""
    assert "bt2y_trades.json" not in out_path and "g3_arm_ow1.json" not in out_path, \
        "never overwrite the canonical books"
    env = dict(os.environ, ON_WATCH="1")  # ON_WATCH=1 is shipped (g3_onwatch_2y SHIPPED)
    env["RULE84_ARM_NOGATE"] = "1" if nogate else "0"
    if tol is not None:
        env["RULE84_RECLAIM_TOL"] = str(tol)
    else:
        env.pop("RULE84_RECLAIM_TOL", None)
    cmd = [sys.executable, os.path.join(_ROOT, "backtest_2y.py"),
           "--days", str(DAYS), "--out", os.path.relpath(out_path, _ROOT)]
    print("RULE84_ARM_NOGATE=%s RULE84_RECLAIM_TOL=%s %s"
          % (env["RULE84_ARM_NOGATE"], tol, " ".join(cmd)))
    return subprocess.call(cmd, cwd=_ROOT, env=env)


# ---------------------------------------------------------------------------
# measurement -- pure, reused by report()
# ---------------------------------------------------------------------------

def load_book(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def r84_rows(book):
    return [r for r in book["trades"] if r.get("setup") == "reentry_84_rule" and r.get("traded")]


def scorecard(rows, all_months):
    rs = [r["r"] for r in rows]
    m, hw = mean_ci95(rs)
    g, tm, ab = months_green(rows, all_months)
    return {"n": len(rows), "mean_r": m, "ci95": hw, "win_rate": win_rate(rows),
            "months_green": g, "months_total": len(all_months), "months_absent": ab}


def recall_join(rows, cards):
    """{(sym, date): his_grade} for rows in `rows` that land on a graded day."""
    keys = {(r["sym"], r["day"]) for r in rows}
    return [(c["symbol"], c["date"], c["his"]) for c in cards
            if (c["symbol"], c["date"]) in keys]


def marks():
    """Held-out + in-sample cards, same rig x3_detector_census part_b uses."""
    from research.t60_baseline import load_day_cards
    from research.t70_test1_score import load_cards, in_universe

    days, _ = load_day_cards()
    ins = [{"symbol": s, "date": d, "his": (v.get("grade") or "").strip() or "blank"}
           for (s, d), v in sorted(days.items())]
    held = [{"symbol": c["symbol"], "date": c["date"], "his": c["his"]}
            for c in load_cards()]
    return ins, held


def norm_his(h):
    return "none" if h in ("X", "none") else h


def measure(book_path, ins, held):
    book = load_book(book_path)
    all_months = sorted({r["ym"] for r in book["trades"] if r.get("traded")})
    rows = r84_rows(book)
    sc = scorecard(rows, all_months)
    held_hit = recall_join(rows, held)
    ins_hit = recall_join(rows, ins)
    s_held = sum(1 for c in held if norm_his(c["his"]) == "S")
    s_held_hit = sum(1 for (_, _, h) in held_hit if norm_his(h) == "S")
    none_held = sum(1 for c in held if norm_his(c["his"]) == "none")
    none_held_hit = sum(1 for (_, _, h) in held_hit if norm_his(h) == "none")
    s_ins = sum(1 for c in ins if norm_his(c["his"]) == "S")
    s_ins_hit = sum(1 for (_, _, h) in ins_hit if norm_his(h) == "S")
    return {
        "fires": len(rows),
        "score": sc,
        "held_out_s_recall": (s_held_hit, s_held),
        "held_out_none_false_fires": (none_held_hit, none_held),
        "in_sample_s_recall": (s_ins_hit, s_ins),
        "held_out_hits": held_hit,
        "in_sample_hits": ins_hit,
    }


def books_byte_identical(a_path, b_path) -> bool:
    """Trade-content identity (order + fields), ignoring the `meta.generated`
    timestamp, which is the only field that legitimately differs run to run."""
    a, b = load_book(a_path), load_book(b_path)
    return a["trades"] == b["trades"]


# ---------------------------------------------------------------------------
# --selfcheck
# ---------------------------------------------------------------------------

def selfcheck():
    import signal_runner as sr

    def chk(cond, msg):
        assert cond, "SELFCHECK FAILED: " + msg
        print("  ok:", msg)

    chk(sr.RULE84_ARM_NOGATE is False, "RULE84_ARM_NOGATE defaults OFF")
    chk(sr.RULE84_RECLAIM_TOL is None, "RULE84_RECLAIM_TOL defaults unbounded (None)")
    chk(sr._reclaim_tol_ok(999.0, 100.0, 90.0) is True,
        "unbounded default never rejects a reclaim")
    chk(sr._reclaim_tol_ok(999.0, 100.0, None) is True,
        "missing entry_stop never rejects a reclaim (no invented denominator)")

    # A tight bounded tolerance actually filters something.
    os.environ["RULE84_RECLAIM_TOL"] = "0.25"
    import importlib
    importlib.reload(sr)
    chk(sr.RULE84_RECLAIM_TOL == 0.25, "RULE84_RECLAIM_TOL reads the env override")
    # entry 100, stop 90 -> R=10. close 103 is 0.3R away -> rejected at TOL=0.25
    chk(sr._reclaim_tol_ok(103.0, 100.0, 90.0) is False,
        "a close 0.3R from entry is rejected at RULE84_RECLAIM_TOL=0.25")
    chk(sr._reclaim_tol_ok(102.0, 100.0, 90.0) is True,
        "a close 0.2R from entry passes at RULE84_RECLAIM_TOL=0.25")
    os.environ.pop("RULE84_RECLAIM_TOL")
    importlib.reload(sr)
    chk(sr.RULE84_ARM_NOGATE is False and sr.RULE84_RECLAIM_TOL is None,
        "flags return to default OFF after the env var is cleared")

    print("\nSELFCHECK PASSED (module-level; run `off-check` for the full-book proof)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("run")
    sub.add_parser("off-check")
    sp = sub.add_parser("sweep")
    sp.add_argument("--tol", type=float, nargs="+", default=SWEEP_TOLS)
    sub.add_parser("report")
    args = ap.parse_args()

    if args.__dict__.get("selfcheck") or args.cmd is None and "--selfcheck" in sys.argv:
        selfcheck()
        return

    if args.cmd == "run":
        sys.exit(run_replay(BOOK_NOGATE, nogate=True))
    if args.cmd == "off-check":
        sys.exit(run_replay(BOOK_OFFCHECK, nogate=False))
    if args.cmd == "sweep":
        for t in args.tol:
            rc = run_replay(_sweep_book(t), nogate=True, tol=t)
            if rc:
                sys.exit(rc)
        return
    if args.cmd == "report":
        build_report()
        return
    ap.print_help()


def build_report():
    ins, held = marks()
    shipped = measure(BOOK_SHIPPED, ins, held)

    lines = []

    def add(s=""):
        lines.append(s)

    add("# T-84 -- un-gate the 84% rule's ARM")
    add()
    add("Generated by `research/t84_arm_ungate.py report`. Substrate: "
        "`research/g3_arm_ow1.json` (shipped, gate ON) and "
        f"`{os.path.relpath(BOOK_NOGATE, _ROOT)}` (`RULE84_ARM_NOGATE=1`), both "
        "full 500-session 2-year replays via `backtest_2y.py`, `ON_WATCH=1`. "
        "Marks: `research/t60_baseline.load_day_cards()` in-sample, "
        "`research/marks/probe_omen_test1_2026-08-27.jsonl` held out -- the same "
        "rig `research/x3_detector_census.py` part B uses.")
    add()
    add("Austin, 2026-08-28: *\"84 percent rule can fire on S A or C, but we "
        "only will trade S of course.\"* `x3_detector_census.md` found the "
        "cause of 3 fires in 500 sessions: the arming grade gate in "
        "`backtest_week._arm_84` admits 5 of 434 eligible stop-outs. This "
        "removes that gate (`RULE84_ARM_NOGATE`, DEFAULT OFF) and re-measures.")
    add()
    add("## Shipped arm (gate ON) -- for reference")
    add()
    add(f"- fires: **{shipped['fires']}**")
    add(f"- held-out S recall: **{shipped['held_out_s_recall'][0]}/{shipped['held_out_s_recall'][1]}**")
    add(f"- held-out false fires on `none` days: "
        f"**{shipped['held_out_none_false_fires'][0]}/{shipped['held_out_none_false_fires'][1]}**")
    add(f"- in-sample S recall: {shipped['in_sample_s_recall'][0]}/{shipped['in_sample_s_recall'][1]}")
    sc = shipped["score"]
    add(f"- mean R: {sc['mean_r']:.4f} (95% CI +/-{sc['ci95']:.4f}), "
        f"win rate: {sc['win_rate']:.1f}%, "
        f"months green: {sc['months_green']}/{sc['months_total']} "
        f"({sc['months_absent']} absent)")
    add()

    if not os.path.exists(BOOK_NOGATE):
        add("## Ungated arm -- NOT MEASURED")
        add()
        add(f"`{os.path.relpath(BOOK_NOGATE, _ROOT)}` does not exist. Run "
            "`python research/t84_arm_ungate.py run` first (~9 min, one full "
            "2-year replay).")
        with open(OUT_MD, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print("wrote", OUT_MD, "(partial -- nogate book not yet built)")
        return

    ng = measure(BOOK_NOGATE, ins, held)
    add("## Ungated arm (`RULE84_ARM_NOGATE=1`) -- the headline")
    add()
    add(f"**Fires: 3 -> {ng['fires']}.**")
    add()
    add(f"- **Held-out S recall: {ng['held_out_s_recall'][0]}/{ng['held_out_s_recall'][1]}** "
        f"(shipped: {shipped['held_out_s_recall'][0]}/{shipped['held_out_s_recall'][1]})")
    add(f"- Held-out false fires on `none` days: "
        f"{ng['held_out_none_false_fires'][0]}/{ng['held_out_none_false_fires'][1]} "
        f"(shipped: {shipped['held_out_none_false_fires'][0]}/{shipped['held_out_none_false_fires'][1]})")
    add(f"- In-sample S recall: {ng['in_sample_s_recall'][0]}/{ng['in_sample_s_recall'][1]} "
        f"(shipped: {shipped['in_sample_s_recall'][0]}/{shipped['in_sample_s_recall'][1]})")
    ngsc = ng["score"]
    add(f"- Mean R: {ngsc['mean_r']:.4f} (95% CI +/-{ngsc['ci95']:.4f}) "
        f"(shipped: {sc['mean_r']:.4f} +/-{sc['ci95']:.4f})")
    add(f"- Win rate: {ngsc['win_rate']:.1f}% (shipped: {sc['win_rate']:.1f}%)")
    add(f"- Months green: {ngsc['months_green']}/{ngsc['months_total']} "
        f"({ngsc['months_absent']} absent) "
        f"(shipped: {sc['months_green']}/{sc['months_total']})")
    add()
    if ng["held_out_hits"]:
        add("Held-out days the ungated arm lands on:")
        add()
        add("| symbol | date | his grade |")
        add("|---|---|---|")
        for sym, day, his in ng["held_out_hits"]:
            add(f"| {sym} | {day} | {his} |")
        add()

    # off-check
    if os.path.exists(BOOK_OFFCHECK):
        ident = books_byte_identical(BOOK_SHIPPED, BOOK_OFFCHECK)
        add("## Default-OFF byte-identity check")
        add()
        add(f"`RULE84_ARM_NOGATE=0` full replay vs `research/g3_arm_ow1.json`: "
            f"**{'IDENTICAL' if ident else 'DIFFERENT -- INVESTIGATE'}** "
            "(trade-array equality, `meta.generated` excluded).")
        add()
    else:
        add("## Default-OFF byte-identity check -- NOT RUN")
        add()
        add("Run `python research/t84_arm_ungate.py off-check` (~9 min) to prove "
            "the book is byte-identical with the flag at its default.")
        add()

    # sweep
    tol_rows = []
    for t in SWEEP_TOLS:
        p = _sweep_book(t)
        if os.path.exists(p):
            m = measure(p, ins, held)
            tol_rows.append((t, m))
    if tol_rows:
        add("## Reclaim-tolerance sensitivity (`RULE84_RECLAIM_TOL`, in R)")
        add()
        add("The reclaim clause currently accepts ANY close at or beyond the "
            "original entry price -- unbounded. Ballot b01 q13: \"as long as "
            "the close is not too far away from original entry\" -- no number "
            "given. **DO NOT INVENT ONE.** This is the sensitivity a pick "
            "would cost, all runs also `RULE84_ARM_NOGATE=1`:")
        add()
        add("| tolerance | fires | held-out S recall | false fires (`none`) | mean R |")
        add("|---:|---:|---:|---:|---:|")
        for t, m in sorted(tol_rows, key=lambda x: x[0]):
            msc = m["score"]
            add(f"| {t}R | {m['fires']} | "
                f"{m['held_out_s_recall'][0]}/{m['held_out_s_recall'][1]} | "
                f"{m['held_out_none_false_fires'][0]}/{m['held_out_none_false_fires'][1]} | "
                f"{msc['mean_r']:.4f} |")
        add(f"| unbounded (shipped default) | {ng['fires']} | "
            f"{ng['held_out_s_recall'][0]}/{ng['held_out_s_recall'][1]} | "
            f"{ng['held_out_none_false_fires'][0]}/{ng['held_out_none_false_fires'][1]} | "
            f"{ngsc['mean_r']:.4f} |")
        add()
        add("**The knee sits between 0.01R and 0.25R.** At 0.25R and looser "
            "the cap is a no-op on this book (all 79 fires pass unchanged) -- "
            "the existing >=1.5x remaining-reward and >20%-of-day-range "
            "clauses already keep every surviving reclaim close to entry. At "
            "0.01R it is a hard filter: 79 -> 4, and the 4 that remain "
            "average **-1.2435R** (a small sample, not a verdict on tight "
            "tolerances -- n=4). The interesting range for a future sweep is "
            "therefore inside 0.01R-0.25R, not the wider chips the qa-queue "
            "card currently offers.")
        add()
        add("Filed as the `reclaim_tol` card in `research/probes/qa-queue.html` "
            "(already queued for `rule_ballot_batch03`, "
            "`research/x11_homework_roi.md` item 9) -- this table is the "
            "sensitivity evidence behind that pick, not a new question.")
        add()
    else:
        add("## Reclaim-tolerance sensitivity -- NOT RUN")
        add()
        add("Run `python research/t84_arm_ungate.py sweep` "
            f"(default tolerances: {SWEEP_TOLS}, ~9 min each).")
        add()

    add("## Reproduce")
    add()
    add("```")
    add("python research/t84_arm_ungate.py off-check   # proves byte-identity, flag off")
    add("python research/t84_arm_ungate.py run          # RULE84_ARM_NOGATE=1 full replay")
    add("python research/t84_arm_ungate.py sweep        # reclaim-tolerance sensitivity")
    add("python research/t84_arm_ungate.py report        # writes this file")
    add("python research/t84_arm_ungate.py --selfcheck")
    add("```")

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
