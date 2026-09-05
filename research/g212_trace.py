"""g212_trace.py -- every number on research/g212_baseline_verdict.md, asserted
against a stamped book in research/tape/. Exits non-zero on drift.

OMEN 10.0 row R3 (the baseline verdict). The page is prose Austin reads; this
file is the proof underneath it. Nothing here re-types arithmetic:

    research/loop_cycle.py   compute_all / figures / up_to_3_rows -- the SAME
                             functions the loop's gate reads, so the baseline
                             figures on the page are, by construction, the
                             figures the gate will compare every L-row against.
    research/book_stamp.py   book_id -- the fingerprint the OFF arm of every
                             cycle must reproduce; recomputed here from the
                             rows, never trusted from the stamp alone.

THE BASELINE (decided by R3, 2026-09-05):
    trade set   backtest_2y.py at the shipped defaults (no env), --days 730,
                built 2026-09-05 at commit 29e4abc6, 499 sessions 2024-09-04 ..
                2026-09-04, ALL 29 archived symbols in the book; the baseline
                SLICE is universe.CORE_SYMBOLS (rows with tier=="core"), the
                settled universe. full29 is reported beside it.
    fill        close -- market at the close of the signal bar
                (entry_fill.ENTRY_FILL default). Phantom column: ENTRY_FILL=
                published, same command, same minute, same commit.
    exit        the shipped engine: 1R hard stop (resting disaster order at
                exactly 1R, fills on an intrabar touch), scale plan
                hod_then_runner_be, account-wide two-loss halt ON.
    unit        up_to_3_stop_win_or_2loss -- his day policy: up to 3 fired-and-
                traded signals a day in arrival order, stop after the first win
                or the second loss. first_of_day and every_signal beside it.
    halves      H1 = sessions before 2025-09-01, H2 = 2025-09-01 onward.
    ceiling     oracle_best_of_day -- the day's best fired-and-traded row,
                chosen after the fact. Proof the setups exist; never a plan.

Usage:
    python research/g212_trace.py            # assert, exit 1 on drift
    python research/g212_trace.py --print    # dump every computed figure as JSON
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import book_stamp                                      # noqa: E402
from research.loop_cycle import (compute_all, load_book_any,         # noqa: E402
                                 UNIT_FUNCS)

TAPE = ROOT / "research" / "tape"
HONEST = TAPE / "baseline_2026-09-05.json.gz"
PHANTOM = TAPE / "baseline_2026-09-05_published.json.gz"
LOOP_JSON = TAPE / "loop.json"
BOUNDARY = "2025-09-01"
BASELINE_UNIT = "up_to_3_stop_win_or_2loss"
UNITS = (BASELINE_UNIT, "first_of_day", "every_signal", "oracle_best_of_day")

# The three books the causal sentence reads (R2's ladder + its pass-2 referee).
# Unit for all three: every filled signal, $/day = sum(pnl) / distinct trading
# days in the population, 29 symbols, 2024-09-04..2026-09-04, next_open fill.
LADDER_BOOKS = {
    "fwd_1_walk_blind2r": TAPE / "reconcile_fwd_1_add_C_grades.json.gz",
    "simD_engine_blind2r": TAPE / "r2ref_simd_next_open_blind2r_real_engine.json.gz",
    "fwd_2_engine_ladder": TAPE / "reconcile_fwd_2_swap_exit_shipped_ladder.json.gz",
}


def oracle_rows(rows):
    """The ceiling: each day's best fired-and-traded row (or halted row),
    chosen after the fact. Same candidate pool as the other units."""
    byday = {}
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday.setdefault(r["day"], []).append(r)
    return [max(v, key=lambda r: r.get("pnl", 0.0)) for _, v in sorted(byday.items())]


UNIT_FUNCS["oracle_best_of_day"] = oracle_rows


def core11(rows):
    return [r for r in rows if r.get("tier") == "core"]


# ----------------------------------------------------------------- expected
# Every figure the page prints, keyed exactly like compute_everything()'s
# output. Dollars are whole dollars; R to 4 places. Any drift raises.
_W = lambda **k: k  # noqa: E731  -- a slice dict, keeps the table readable

EXPECTED = {
    "honest": {
        "identity": {"book_id": "2c39ced2697c26cc", "commit": "29e4abc6",
                     "entry_fill": "close", "sessions": 499,
                     "first": "2024-09-04", "last": "2026-09-04",
                     "signals": 127513, "traded": 4053, "halted": 4186,
                     "dirty_engine_py": [],
                     "flags": {"entry_fill.ENTRY_FILL": "close",
                               "loss_halt.LOSS_HALT": True,
                               "stop_rule.DISASTER_STOP_R": 1.0,
                               "backtest_week.DISASTER_STOP": True,
                               "backtest_week.STOP_ON_CLOSE": True,
                               "backtest_week.SCALE_PLAN": "hod_then_runner_be",
                               "signal_runner.RETEST_REQUIRED": True,
                               "signal_runner.RULE84_OFF": False,
                               "signal_runner.ON_WATCH": True}},
        "core11": {
            BASELINE_UNIT: {
                "whole": _W(trades=769, per_day=-52, mean_r=-0.0335, win_pct=45.0,
                            months_green=11, months=25, weeks_green=45, weeks=105,
                            avg_win=801, avg_loss=716, avg_win_over_avg_loss=1.119,
                            fires_per_day=1.541, total_dollars=-25746,
                            worst_drawdown=51106),
                "h1": _W(trades=382, per_day=9, mean_r=0.0057, win_pct=43.7,
                         months_green=6, months=12, avg_win=917, avg_loss=701,
                         avg_win_over_avg_loss=1.308),
                "h2": _W(trades=387, per_day=-111, mean_r=-0.0722, win_pct=46.3,
                         months_green=5, months=13, avg_win=694, avg_loss=732,
                         avg_win_over_avg_loss=0.948)},
            "first_of_day": {
                "whole": _W(trades=498, per_day=-39, mean_r=-0.0392, win_pct=45.7,
                            months_green=9, months=25, avg_win=731, avg_loss=687,
                            avg_win_over_avg_loss=1.064),
                "h1": _W(trades=248, per_day=32, months_green=6, months=12),
                "h2": _W(trades=250, per_day=-109, months_green=3, months=13)},
            "every_signal": {
                "whole": _W(trades=1909, per_day=-132, mean_r=-0.0346, win_pct=46.4,
                            months_green=10, months=25, fires_per_day=3.826,
                            avg_win=770, avg_loss=731),
                "h1": _W(trades=998, per_day=-7, months_green=6, months=12),
                "h2": _W(trades=911, per_day=-257, months_green=4, months=13)},
            "oracle_best_of_day": {
                "whole": _W(trades=498, per_day=1760, mean_r=1.7633, win_pct=95.0,
                            months_green=25, months=25, avg_win=1880, avg_loss=454)}},
        "full29": {
            BASELINE_UNIT: {
                "whole": _W(trades=773, per_day=-9, mean_r=-0.0059, win_pct=45.8,
                            months_green=12, months=25, avg_win=820, avg_loss=703,
                            avg_win_over_avg_loss=1.166),
                "h1": _W(trades=378, per_day=72, months_green=8, months=12),
                "h2": _W(trades=395, per_day=-89, months_green=4, months=13)},
            "first_of_day": {
                "whole": _W(trades=499, per_day=29, mean_r=0.0294, win_pct=45.9,
                            months_green=14, months=25, avg_win=864, avg_loss=678),
                "h1": _W(trades=248, per_day=119, months_green=9, months=12),
                "h2": _W(trades=251, per_day=-60, months_green=5, months=13)},
            "every_signal": {
                "whole": _W(trades=4053, per_day=-334, mean_r=-0.0412, win_pct=44.9,
                            months_green=8, months=25, fires_per_day=8.122,
                            total_dollars=-166871)},
            "oracle_best_of_day": {
                "whole": _W(trades=499, per_day=2681, mean_r=2.6812, win_pct=99.4,
                            months_green=25, months=25)}}},
    "phantom": {
        "identity": {"book_id": "9a629a9682f0676b", "commit": "29e4abc6",
                     "entry_fill": "published", "sessions": 499,
                     "first": "2024-09-04", "last": "2026-09-04",
                     "signals": 134257, "traded": 4230, "halted": 1372,
                     "dirty_engine_py": []},
        "core11": {
            BASELINE_UNIT: {
                "whole": _W(trades=645, per_day=850, mean_r=0.6572, win_pct=63.9,
                            months_green=23, months=25, avg_win=1583, avg_loss=980,
                            avg_win_over_avg_loss=1.615),
                "h1": _W(trades=328, per_day=813, months_green=10, months=12),
                "h2": _W(trades=317, per_day=886, months_green=13, months=13)},
            "first_of_day": {
                "whole": _W(trades=494, per_day=701, mean_r=0.7083, win_pct=67.2,
                            months_green=24, months=25, avg_win=1534, avg_loss=983)},
            "every_signal": {
                "whole": _W(trades=1973, per_day=2328, mean_r=0.5888, win_pct=61.1,
                            months_green=24, months=25)}},
        "full29": {
            BASELINE_UNIT: {
                "whole": _W(trades=668, per_day=929, mean_r=0.6942, win_pct=64.2,
                            months_green=25, months=25, avg_win=1625, avg_loss=977)},
            "first_of_day": {
                "whole": _W(trades=498, per_day=683, months_green=24, months=25)},
            "every_signal": {
                "whole": _W(trades=4230, per_day=5167, mean_r=0.6096, win_pct=59.9,
                            months_green=25, months=25, total_dollars=2578552,
                            avg_win=1672, avg_loss=977)}}},
    "ladder": {
        "fwd_1_walk_blind2r": _W(trades=14327, days=499, per_day=4569.49, mean_r=0.1592,
                                 win_pct_all=38.8, avg_win_r=1.9835, avg_loss_r=-0.9965,
                                 book_id="43edc1376cad2e66"),
        "simD_engine_blind2r": _W(trades=14332, days=499, per_day=149.80, mean_r=0.0052,
                                  win_pct_all=33.6, avg_win_r=1.9837, avg_loss_r=-0.9973,
                                  book_id="6b3b862ce4ffebe0"),
        "fwd_2_engine_ladder": _W(trades=14332, days=499, per_day=-980.93, mean_r=-0.0342,
                                  win_pct_all=42.7, avg_win_r=1.0312,
                                  book_id="8d34c0af3d3839cd"),
        "legs": _W(whole_step=-5550.42, substrate_leg=-4419.69, ladder_leg=-1130.73,
                   substrate_share_pct=79.6)},
}

TOL = {"trades": 0, "per_day": 1, "mean_r": 0.001, "months_green": 0, "months": 0,
       "weeks_green": 0, "weeks": 0, "win_pct": 0.1, "win_pct_all": 0.1,
       "avg_win": 1, "avg_loss": 1, "avg_win_r": 0.001, "avg_loss_r": 0.001,
       "avg_win_over_avg_loss": 0.01, "total_dollars": 1, "worst_drawdown": 1,
       "fires_per_day": 0.001, "days_traded": 0, "days": 0,
       "whole_step": 0.01, "substrate_leg": 0.01, "ladder_leg": 0.01,
       "substrate_share_pct": 0.1}


def book_figures(path):
    meta, rows = load_book_any(path)
    st = meta.get("stamp", {})
    git = st.get("git", {}) or {}
    out = {"identity": {"book_id": st.get("book_id"),
                        "commit": (git.get("commit") or "")[:8],
                        "dirty_engine_py": git.get("dirty_engine_py"),
                        "dirty_py_count": git.get("dirty_py_count"),
                        "built_at": st.get("built_at"),
                        "entry_fill": meta.get("entry_fill"),
                        "sessions": meta.get("sessions"),
                        "first": meta.get("first"), "last": meta.get("last"),
                        "signals": meta.get("signals"), "traded": meta.get("traded"),
                        "halted": meta.get("halted"),
                        "flags": {k: v for k, v in (st.get("flags") or {}).items()
                                  if k.split(".")[-1] in (
                                      "ENTRY_FILL", "SCALE_PLAN", "DISASTER_STOP",
                                      "STOP_ON_CLOSE", "PESSIMISTIC_FILL", "LOSS_HALT",
                                      "RETEST_REQUIRED", "DEDUPE_MODE", "LADDER_WEIGHTS",
                                      "DISASTER_STOP_R", "RULE84_OFF", "ON_WATCH")}},
           "core11": {}, "full29": {}}
    recomputed = book_stamp.book_id(rows)
    if recomputed != st.get("book_id"):
        raise SystemExit("%s: stamp book_id %s != recomputed %s"
                         % (path.name, st.get("book_id"), recomputed))
    for uni_name, uni_rows in (("core11", core11(rows)), ("full29", rows)):
        for unit in UNITS:
            out[uni_name][unit] = compute_all(meta, uni_rows, unit, BOUNDARY)
    return out


def ladder_figures():
    out = {}
    for name, path in LADDER_BOOKS.items():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            b = json.load(f)
        rows = [r for r in b["trades"] if r.get("filled", True)
                and r.get("pnl") is not None and r.get("r") is not None]
        days = len({r["day"] for r in rows})
        tot = sum(r["pnl"] for r in rows)
        wins = sum(1 for r in rows if r["pnl"] > 0)
        w = [r["r"] for r in rows if r["pnl"] > 0]
        l = [r["r"] for r in rows if r["pnl"] < 0]
        out[name] = {"trades": len(rows), "days": days,
                     "per_day": round(tot / days, 2),
                     "mean_r": round(sum(r["r"] for r in rows) / len(rows), 4),
                     "win_pct_all": round(100.0 * wins / len(rows), 1),
                     "avg_win_r": round(sum(w) / len(w), 4) if w else None,
                     "avg_loss_r": round(sum(l) / len(l), 4) if l else None,
                     "book_id": b["meta"]["stamp"]["book_id"],
                     "exit_plan": b["meta"].get("exit_plan"),
                     "fill": b["meta"].get("fill")}
    a, d, c = (out["fwd_1_walk_blind2r"], out["simD_engine_blind2r"],
               out["fwd_2_engine_ladder"])
    legs = {"whole_step": round(c["per_day"] - a["per_day"], 2),
            "substrate_leg": round(d["per_day"] - a["per_day"], 2),
            "ladder_leg": round(c["per_day"] - d["per_day"], 2)}
    legs["substrate_share_pct"] = round(100.0 * legs["substrate_leg"] / legs["whole_step"], 1)
    out["legs"] = legs
    return out


def compute_everything():
    return {"honest": book_figures(HONEST), "phantom": book_figures(PHANTOM),
            "ladder": ladder_figures()}


# ------------------------------------------------------------------- assert

def _walk(exp, got, path, bad):
    if isinstance(exp, dict):
        if not isinstance(got, dict):
            bad.append("%s: expected a table, book gives %r" % (path, got))
            return
        for k, v in exp.items():
            if k not in got:
                bad.append("%s.%s: missing in computed figures" % (path, k))
                continue
            _walk(v, got[k], "%s.%s" % (path, k), bad)
        return
    field = path.split(".")[-1]
    tol = TOL.get(field, 0)
    if (isinstance(exp, (int, float)) and isinstance(got, (int, float))
            and not isinstance(exp, bool) and not isinstance(got, bool)):
        if abs(exp - got) > tol:
            bad.append("%s: page says %s, book gives %s (tol %s)" % (path, exp, got, tol))
    elif exp != got:
        bad.append("%s: page says %r, book gives %r" % (path, exp, got))


def _leaves(d):
    if isinstance(d, dict):
        for v in d.values():
            yield from _leaves(v)
    else:
        yield d


def main():
    if "--print" in sys.argv:
        print(json.dumps(compute_everything(), indent=1, default=str))
        return 0
    got = compute_everything()
    bad = []
    _walk(EXPECTED, got, "g212", bad)

    # the two fills are the same command on the same sessions, same day, same commit
    hi, pi = got["honest"]["identity"], got["phantom"]["identity"]
    for k in ("sessions", "first", "last", "commit"):
        if hi[k] != pi[k]:
            bad.append("honest vs phantom %s: %r vs %r" % (k, hi[k], pi[k]))
    if (hi["built_at"] or "")[:10] != (pi["built_at"] or "")[:10]:
        bad.append("honest vs phantom built on different days: %s vs %s"
                   % (hi["built_at"], pi["built_at"]))

    # loop.json must point at this book, this unit, this boundary, this id
    if LOOP_JSON.exists():
        cfg = json.loads(LOOP_JSON.read_text(encoding="utf-8"))
        if Path(cfg.get("baseline_book", "")).name != HONEST.name:
            bad.append("loop.json baseline_book %r is not %s" % (cfg.get("baseline_book"), HONEST.name))
        if cfg.get("unit") != BASELINE_UNIT:
            bad.append("loop.json unit %r is not %s" % (cfg.get("unit"), BASELINE_UNIT))
        if cfg.get("halves_boundary") != BOUNDARY:
            bad.append("loop.json halves_boundary %r != %s" % (cfg.get("halves_boundary"), BOUNDARY))
        if cfg.get("baseline_book_id") != hi["book_id"]:
            bad.append("loop.json baseline_book_id %r != stamped %s"
                       % (cfg.get("baseline_book_id"), hi["book_id"]))
        bf = cfg.get("baseline_figures", {})
        base = got["honest"]["core11"][BASELINE_UNIT]
        for sl in ("whole", "h1", "h2"):
            for fld in ("per_day", "months_green", "months", "trades"):
                if bf.get(sl, {}).get(fld) != base[sl].get(fld):
                    bad.append("loop.json baseline_figures.%s.%s %r != book %r"
                               % (sl, fld, bf.get(sl, {}).get(fld), base[sl].get(fld)))
    else:
        bad.append("research/tape/loop.json missing")

    if bad:
        print("FAIL -- %d figure(s) on research/g212_baseline_verdict.md no longer trace:" % len(bad))
        for b in bad:
            print("  " + b)
        return 1
    n = sum(1 for _ in _leaves(EXPECTED))
    print("PASS -- %d figures on research/g212_baseline_verdict.md trace to %s (id %s), "
          "%s (id %s) and the three ladder books"
          % (n, HONEST.name, hi["book_id"], PHANTOM.name, pi["book_id"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
