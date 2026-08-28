"""W1 -- kill `B`. Austin's S/A/C/X ladder as the engine's grade, priced.

`signal_runner._calibration_grade` floors a `C` up to `B` whenever the signal is
the FIRST with-trend signal of the day, and `research/g4_dropped_s.md` measured
what that is worth: **968 of the 1,016 traded signals are `B` ONLY because of
that floor** (95.3%). The engine trades on grade, so ARRIVAL ORDER -- not the
setup -- selects the entire book.

Austin, 2026-08-28:

    "B is not supposed to be a trade. We changed it to A and C. S and A and C."
    "S A C grades are kept, A one downgrade, C two downgrades, revisit B trades
     and mold them into those grades or 'x' kill them."

This ticket wires that ladder in behind `signal_runner.ENABLE_SAC_LADDER`
(default False) and prices it. The final grade becomes the NET downgrade count
off `research/downgrade.py`: 0 -> S, 1 -> A, 2 -> C, 3+ -> X (not tradeable).
`B` stops existing.

FOUR measured arms, never averaged together:

    off      == HEAD. `_grade_for_levels` + the counter-day-trend cap + the
             first-with-trend `B` floor.
    on_w9c   THE VERDICT ARM. The ladder counting `research/w9_downgrade_signs.md`
             set (c): the seven right-signed shipped variables (minus
             `level_not_respected`, which W9 proved WRONG-signed on 62.7% of the
             book) plus `sequence_gate` turned on for the call. W9's own
             recommendation, and the only set of its three that is monotonic on
             median R without carrying the known bug.
    on       the same ladder counting all EIGHT as shipped. A LABELLED CONTROL --
             the comparison between the two variable sets is itself the finding.
    on_all   the shipped-eight ladder ALSO regrading the 42,937 signals
             `_grade_pa` already vetoed. That is R3's lever
             (`ENABLE_DOWNGRADE_GRADER`) reached by a different road; it makes
             the book GROW, and conflating it with W1 would re-run an experiment
             that is already published.

Only the GRADE moves. The counter-day-trend cap `_calibration_grade` also
applies is reapplied identically in every arm, so this is the ladder and nothing
else. Detection, the fill, the stop, the R denominator, the downgrade variables'
own code and `downgrade.ENABLE_SEQUENCE_GATE`'s committed default are all
untouched, and `ON_WATCH` stays at its shipped default in every arm (spec
section 1.5).

Three instruments, every arm, HELD-OUT FIRST:

  1. `research/t70_test1_score.py` -- the 100 HELD-OUT OMEN Test 1 cards
  2. `backtest_2y.py`              -- the 2-year book the 2.0R money gate reads
  3. `research/regression_gate.py` -- the in-sample recall gate (no NEW drops)

Nothing here ships. The flag stays False, the `B` floor is not deleted, and the
engine is not re-frozen (that would VOID `research/omen6_forward.py`, which is
Austin's call alone).

REUSED, NEVER REIMPLEMENTED
---------------------------
  research.g13_floor_fix_ab   trades_digest / sizeable / split_sizeable /
                              stats / per_symbol / row_key / compose /
                              test1_counts and the two child-process driver
                              strings -- G13 built the A/B shell for exactly
                              this shape of question
  research.r3_downgrade_grader_ab  agreement / switched / matched_clean / _pop
                              -- R3 is the same question one seam upstream
  research.g3_onwatch_2y      classify_books / error_bars -- T3's bars
  research.a2_bt2y_summary    the whole-book money read (via g13.stats)
  research.t70_test1_score    score_all, the held-out scorer
  research.w9_downgrade_signs the variable signs and the set-(c) recommendation
  research.p20_sequence_gate  annotate_sequence -- the entry-ordinal definition
                              `SignalRunner._sac_seq` reproduces in the engine
  universe.MIN_SAMPLE_N       the per-symbol floor

Each instrument reads the flag at import time, so every arm is a CHILD PROCESS
with `ENABLE_SAC_LADDER` forced in its environment.

    python backtest_2y.py --days 730 --out research/w1_arm_head.json  # BEFORE the patch
    python research/w1_sac_ladder_ab.py book --arm off
    python research/w1_sac_ladder_ab.py book --arm on_w9c
    python research/w1_sac_ladder_ab.py book --arm on
    python research/w1_sac_ladder_ab.py book --arm on_all
    python research/w1_sac_ladder_ab.py identical   # head == off, byte for byte
    python research/w1_sac_ladder_ab.py test1       # the 100 held-out cards
    python research/w1_sac_ladder_ab.py gate
    python research/w1_sac_ladder_ab.py stats
    python research/w1_sac_ladder_ab.py report
    python research/w1_sac_ladder_ab.py --selfcheck
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from universe import MIN_SAMPLE_N                                       # noqa: E402
from research.g13_floor_fix_ab import (                                 # noqa: E402
    _GATE_DRIVER, _TEST1_DRIVER, compose, per_symbol, row_key, sizeable,
    split_sizeable, stats, test1_counts, trades_digest,
)
from research.r3_downgrade_grader_ab import (                           # noqa: E402
    _pop, agreement, matched_clean, switched,
)
from research.w1_ladder_vs_marks import (                               # noqa: E402
    analyse as marks_analyse, wilson,
)

FLAG = "ENABLE_SAC_LADDER"
OUT_MD = os.path.join(HERE, "w1_sac_ladder_ab.md")

# Spec section 1.1, Austin 2026-08-28: the stop fires on a CLOSE and there is one
# close per bar, so the 790-of-792 `intrabar_stop` class is not ambiguous and the
# WIDE bar (+-1.5799 R) is RETIRED. The bar this report is read against is the
# NARROW one. It is recomputed on each arm's own book below; this constant is the
# spec's published figure for the ON-WATCH-off arm, carried so a reader can see
# the recomputation agree with it rather than take either on faith.
NARROW_BAR_SPEC = 0.0088

# `head` is the control: the SAME command run from unmodified HEAD code, before
# the flag existed at all. It is what the byte-identity claim is checked
# against -- `off` must reproduce it exactly.
#
# THREE measured arms, not two, because the ladder has two possible reaches and
# adding them together unlabelled would make W1 into R3:
#   on      the ladder regrades what the incumbent chain left TRADEABLE. This is
#           Austin's "revisit B trades and mold them into those grades or 'x'
#           kill them", and the book can only shrink.
#   on_all  the ladder ALSO regrades the 42,937 `_grade_pa` vetoes. That is R3's
#           lever (`ENABLE_DOWNGRADE_GRADER`) reached by a different road, and it
#           makes the book grow. Reported separately, never averaged in.
ARMS = {
    "head":    (None,        os.path.join(HERE, "w1_arm_head.json")),
    "off":     ({FLAG: "0"}, os.path.join(HERE, "w1_arm_off.json")),
    "nofloor": ({"ENABLE_KILL_B_FLOOR": "1"},
                os.path.join(HERE, "w1_arm_nofloor.json")),
    "on_w9c":  ({FLAG: "1", "SAC_LADDER_VARSET": "w9c"},
                os.path.join(HERE, "w1_arm_on_w9c.json")),
    "on":      ({FLAG: "1"}, os.path.join(HERE, "w1_arm_on.json")),
    "on_all":  ({FLAG: "1", "SAC_LADDER_REGRADE_ALL": "1"},
                os.path.join(HERE, "w1_arm_on_all.json")),
}
# Order matters: it is the column order of every table in the report.
MEASURED = ("off", "nofloor", "on_w9c", "on", "on_all")
ARM_ON = ("nofloor", "on_w9c", "on", "on_all")
# The arm the verdict is taken on. It is the B-floor removal ALONE, because that
# is the half of W1 that Austin's own 59 verdicts did not refute -- see
# research/w1_ladder_vs_marks.py and section 3 of the report.
PRIMARY = "nofloor"
ARM_LABEL = {
    "off": "== HEAD, the control. `_grade_for_levels` + the counter-day-trend cap "
           "+ the first-with-trend `B` floor.",
    "nofloor": "**the verdict arm.** The first-with-trend `B` floor removed and "
               "NOTHING else -- a `C` that would have been floored to `B` stays a "
               "`C`. This is the half of W1 that Austin's 59 verdicts did not refute.",
    "on_w9c": "the count ladder, counting `research/w9_downgrade_signs.md`"
              " set (c): the seven right-signed shipped variables (i.e. minus "
              "`level_not_respected`) plus `sequence_gate` turned on. Regrades only "
              "what the incumbent chain left tradeable.",
    "on": "the same ladder counting all EIGHT variables as shipped, including the "
          "wrong-signed `level_not_respected`. A labelled control, kept because the "
          "comparison between the two sets is itself the finding.",
    "on_all": "the shipped-eight ladder ALSO regrading the 42,937 `_grade_pa` vetoes. "
              "That is R3's lever reached by a different road; it makes the book grow.",
}
GATE_JSON = os.path.join(HERE, "_w1_gate.json")
TEST1_JSON = os.path.join(HERE, "_w1_test1.json")
BOOK_STATS = os.path.join(HERE, "_w1_book_stats.json")


def child_env(arm: str) -> dict:
    """The child's environment for one arm. `head` gets no override at all.

    `ON_WATCH` is never touched here -- spec section 1.5: no workstream may move
    its default, and both arms inherit whatever the shipped engine uses."""
    env = dict(os.environ)
    over = ARMS[arm][0]
    for k in (FLAG, "SAC_LADDER_REGRADE_ALL", "SAC_LADDER_VARSET",
              "ENABLE_KILL_B_FLOOR"):
        env.pop(k, None)
    if over:
        env.update(over)
    return env


# ---------------------------------------------------------------------------
# 1. the 2-year book
# ---------------------------------------------------------------------------

def run_book(arm: str, days: int, out_path: str | None) -> int:
    """One full 2-year replay with the flag forced in a CHILD process.

    `backtest_2y.py` is shelled as-is, never reimplemented. Bars come from
    `data_archive/` and the loader is cache-first, so this makes no network
    call."""
    out_path = out_path or ARMS[arm][1]
    assert "bt2y_trades.json" not in out_path, "never overwrite the canonical book"
    cmd = [sys.executable, os.path.join(ROOT, "backtest_2y.py"),
           "--days", str(days), "--out", os.path.relpath(out_path, ROOT)]
    print("%s %s" % (ARMS[arm][0] or "(no override -- HEAD)", " ".join(cmd)),
          flush=True)
    return subprocess.call(cmd, cwd=ROOT, env=child_env(arm))


def load_book(arm: str) -> dict:
    with open(ARMS[arm][1], encoding="utf-8") as fh:
        return json.load(fh)


def identical(a: str = "head", b: str = "off") -> int:
    """THE HARD CLAIM: with the flag OFF the book is byte-identical to HEAD.

    `trades_digest` is G13's, imported: sha256 over the whole `trades` array,
    with `meta.generated` (a wall clock) the one excluded field."""
    ba, bb = load_book(a), load_book(b)
    da, db = trades_digest(ba), trades_digest(bb)
    print("%-5s %s  %d signals  %d traded"
          % (a, da, len(ba["trades"]), ba["meta"]["traded"]))
    print("%-5s %s  %d signals  %d traded"
          % (b, db, len(bb["trades"]), bb["meta"]["traded"]))
    same_meta = {k: v for k, v in ba["meta"].items() if k != "generated"} == \
                {k: v for k, v in bb["meta"].items() if k != "generated"}
    if da == db and same_meta:
        print("IDENTICAL: the flag-off book reproduces HEAD byte for byte "
              "(meta.generated excluded -- it is a wall clock).")
        return 0
    if da != db:
        rows_a, rows_b = ba["trades"], bb["trades"]
        print("DIFFER: %d vs %d rows" % (len(rows_a), len(rows_b)))
        for i, (x, y) in enumerate(zip(rows_a, rows_b)):
            if x != y:
                print("  first differing row %d:\n    %s=%s\n    %s=%s"
                      % (i, a, x, b, y))
                break
    if not same_meta:
        print("DIFFER: meta")
    return 1


# ---------------------------------------------------------------------------
# 2. the 100 HELD-OUT OMEN Test 1 cards -- reported FIRST
# ---------------------------------------------------------------------------

def run_test1() -> int:
    """`t70_test1_score.score_all` in a child per arm, via G13's own driver
    string. The scorer is imported, never reimplemented."""
    out = {}
    for arm in MEASURED:
        code = _TEST1_DRIVER.format(root=ROOT)
        res = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                             env=child_env(arm), capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr[-2000:])
            raise SystemExit("test1 arm %s failed" % arm)
        rows = json.loads(res.stdout.strip().splitlines()[-1])
        out[arm] = rows
        c = test1_counts(rows)
        print("%-3s  S recall %d/%d  false fire %d/%d  entry match %d/%d  "
              "day precision %d/%d"
              % (arm, c["s_hit"], c["s_n"], c["x_fire"], c["x_n"],
                 c["entry_match"], c["graded"], c["day_prec_hit"], c["day_prec_n"]))
    with open(TEST1_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print("wrote %s" % TEST1_JSON)
    return 0


# ---------------------------------------------------------------------------
# 3. the in-sample recall gate
# ---------------------------------------------------------------------------

def run_gate() -> int:
    """`regression_gate.current_sets` in a child per arm, via G13's own driver
    string -- the gate's own replay, not a copy of it."""
    out = {}
    for arm in MEASURED:
        code = _GATE_DRIVER.format(here=HERE)
        res = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                             env=child_env(arm), capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr[-2000:])
            raise SystemExit("gate arm %s failed" % arm)
        out[arm] = json.loads(res.stdout.strip().splitlines()[-1])
        d = out[arm]
        dropped_s = sorted(set(d["base_s"]) - set(d["s_grade"]))
        dropped_a = sorted(set(d["base_any"]) - set(d["any_signal"]))
        print("%-3s  any_signal %d  s_grade %d  (baseline %d / %d)"
              % (arm, len(d["any_signal"]), len(d["s_grade"]),
                 len(d["base_any"]), len(d["base_s"])))
        print("     dropped s_grade %d %s" % (len(dropped_s), dropped_s))
        print("     dropped any_signal %d %s" % (len(dropped_a), dropped_a))
    with open(GATE_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print("wrote %s" % GATE_JSON)
    return 0


# ---------------------------------------------------------------------------
# 4. the money read
# ---------------------------------------------------------------------------

def _tally_field(rows, field) -> dict:
    """Engine-grade mix over the TRADED rows -- what each ladder actually ships.

    This is the column the whole ticket is about: `B` must be 968-ish on `off`
    and exactly 0 on `on`."""
    t = defaultdict(int)
    for r in rows:
        if r["traded"]:
            t[r.get(field)] += 1
    return t


def wiped_symbols(off_rows, on_rows) -> dict:
    """Symbols whose ENTIRE book the ladder kills, and how much each one cost.

    A shrinking book is not a uniform thinning: some symbols simply stop being
    traded, and Austin is owed their names rather than a percentage."""
    def by_sym(rows):
        d = defaultdict(list)
        for r in rows:
            if r["traded"]:
                d[r["sym"]].append(r["r"])
        return d

    o, n = by_sym(off_rows), by_sym(on_rows)
    wiped = []
    for sym in sorted(set(o) - set(n)):
        rs = o[sym]
        wiped.append({"sym": sym, "n_off": len(rs),
                      "mean_r_off": round(statistics.fmean(rs), 4),
                      "median_r_off": round(statistics.median(rs), 4),
                      "total_r_off": round(sum(rs), 2),
                      "thin": len(rs) < MIN_SAMPLE_N})
    return {"wiped": sorted(wiped, key=lambda d: -d["n_off"]),
            "n_sym_off": len(o), "n_sym_on": len(n),
            "total_r_wiped": round(sum(w["total_r_off"] for w in wiped), 2),
            "n_trades_wiped": sum(w["n_off"] for w in wiped)}


def by_grade(rows) -> dict:
    """Median R per SHIPPED engine grade over the traded rows.

    W9's monotonicity test, but on the book the arm actually produced rather than
    on a simulation over HEAD's rows: a ladder is only a ladder if S > A > C."""
    d = defaultdict(list)
    for r in rows:
        if r["traded"]:
            d[r["grade"]].append(r["r"])
    return {g: {"n": len(v), "median_r": round(statistics.median(v), 4),
                "mean_r": round(statistics.fmean(v), 4)}
            for g, v in sorted(d.items(), key=lambda kv: str(kv[0]))}


def book_stats(books: dict) -> dict:
    """Money + error bars for every arm, whole book and S subset.

    The S subset is `sgrade == "S"` -- `research/downgrade.py`'s ladder attached
    to each row by `backtest_2y.py` AFTER the fact, so it is the SAME population
    in both arms rather than each arm's own idea of S. (On the `on` arm the
    engine's own grade is derived from the same `score()` call, which is the
    point: `sgrade` and the engine grade finally agree.)"""
    from research.g3_onwatch_2y import classify_books, error_bars

    rows = {a: b["trades"] for a, b in books.items()}
    srows = {a: [r for r in v if r["sgrade"] == "S"] for a, v in rows.items()}
    cls, gaps = classify_books(books)
    out = {"gaps": gaps, "arms": {}}
    for a in books:
        out["arms"][a] = {
            "all": stats(rows[a]),
            "S": stats(srows[a]),
            "eb_all": error_bars(cls[a]),
            "eb_S": error_bars([c for c in cls[a] if c["sgrade"] == "S"]),
            "per_symbol": per_symbol(rows[a]),
            "split": split_sizeable(rows[a]),
            "grades": dict(sorted(_tally_field(rows[a], "grade").items(),
                                  key=lambda kv: str(kv[0]))),
            "sgrades": dict(sorted(_tally_field(rows[a], "sgrade").items(),
                                   key=lambda kv: str(kv[0]))),
            # W9's monotonicity read, on each arm's OWN shipped grade
            "by_grade": by_grade(rows[a]),
            "n_symbols": len({r["sym"] for r in rows[a] if r["traded"]}),
            # `backtest_week.Trade.counted` excludes `C` -- C is ALERT-ONLY and
            # never reaches traded P&L. That is the whole mechanism behind the
            # `nofloor` arm's collapse, so the fired/alert split is carried
            # rather than left for the reader to infer from a shrinking book.
            "n_fired": sum(1 for r in rows[a] if r["status"] == "fired"),
            "n_alert": sum(1 for r in rows[a] if r["alert"]),
            # W12 #1 / #4: the two gates the remap moves without anyone choosing
            # to. `skipped_tight_stop` is `_min_viable_stop`, consulted on grade
            # `C` and no other; `n_arm_eligible` is the 84%-rule arm population,
            # keyed to `t.counted and grade in ("A+","A")`.
            "status": dict(sorted(Counter(r["status"] for r in rows[a]).items())),
            "n_arm_eligible": sum(1 for r in rows[a]
                                  if r["traded"] and r["grade"] in ("A+", "A")),
            "meta": books[a]["meta"],
            "digest": trades_digest(books[a]),
        }
    out["compose"] = compose(rows["off"], rows[PRIMARY])
    out["matched_clean"] = matched_clean(rows["off"], rows[PRIMARY])
    out["wiped"] = {a: wiped_symbols(rows["off"], rows[a]) for a in ARM_ON}
    return out


def run_stats() -> int:
    books = {a: load_book(a) for a in MEASURED if os.path.exists(ARMS[a][1])}
    if len(books) != len(MEASURED):
        raise SystemExit("need every arm book; run `book --arm <%s>`"
                         % "|".join(MEASURED))
    st = book_stats(books)
    with open(BOOK_STATS, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=2, sort_keys=True, default=str)
    for a in MEASURED:
        b = st["arms"][a]
        print("%-3s all: n=%d meanR=%+.4f med=%+.4f wr=%.1f%% months %d/%d  "
              "narrow eb +-%.4f"
              % (a, b["all"]["traded"], b["all"]["meanr"], b["all"]["median_r"],
                 b["all"]["wr"], b["all"]["months_green"], b["all"]["months"],
                 b["eb_all"]["narrow"]))
        print("    engine grade mix (traded): %s" % b["grades"])
        s = b["split"]
        print("    UNTAKEABLE %d/%d (%.1f%%), %d with entry==stop, max R %+.1f"
              % (s["n_unsizeable"], s["traded"], s["pct_unsizeable"],
                 s["n_zero_risk"], s["max_r"]))
    for a in ARM_ON:
        w = st["wiped"][a]
        print("symbols wiped by %-7s: %d of %d -- %s"
              % (a, len(w["wiped"]), w["n_sym_off"],
                 ", ".join(x["sym"] for x in w["wiped"]) or "none"))
    print("wrote %s" % BOOK_STATS)
    return 0


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def _f(n, d):
    return "%d/%d = %.0f%%" % (n, d, (100.0 * n / d) if d else 0.0)


def _pct(x):
    return "%.1f%%" % (100.0 * x)


def _ci(hits, n):
    """95% Wilson interval, `research/w1_ladder_vs_marks.wilson` imported."""
    lo, hi = wilson(hits, n)
    return "[%s, %s]" % (_pct(lo), _pct(hi))


def _clears(delta, bar):
    if not bar:
        return "no bar"
    if abs(delta) > bar:
        return "**yes**, by %.0fx" % (abs(delta) / bar)
    return "no -- %.0fx smaller" % (bar / abs(delta)) if delta else "no"


def build_md(t1, gate, st, mk) -> str:
    """The report. Held-out first, median R before mean R, and every arm named.

    FOUR measured arms, never averaged together:

      off      == HEAD, the control
      on_w9c   THE ARM THE VERDICT IS TAKEN ON -- the ladder counting W9's set
               (c): the seven right-signed shipped variables plus `sequence_gate`
      on       the same ladder counting all EIGHT as shipped, including the one
               `research/w9_downgrade_signs.md` proved wrong-signed. A labelled
               control, kept because the comparison IS the finding
      on_all   the ladder also regrading the 42,937 `_grade_pa` vetoes. That is
               R3's lever reached by a different road; it makes the book grow
    """
    A = st["arms"]
    C = {a: test1_counts(t1[a]) for a in MEASURED}
    G = {a: agreement(t1[a]) for a in MEASURED}
    SW = {a: switched(t1["off"], t1[a]) for a in ARM_ON}
    mc = st["matched_clean"]
    L = []

    o1, p1 = C["off"], C[PRIMARY]
    o_all, p_all = A["off"]["all"], A[PRIMARY]["all"]
    d_srec = p1["s_hit"] - o1["s_hit"]
    d_ff = p1["x_fire"] - o1["x_fire"]
    d_mean = p_all["meanr"] - o_all["meanr"]
    d_med = p_all["median_r"] - o_all["median_r"]
    narrow = A["off"]["eb_all"]["narrow"]
    shrink = o_all["traded"] - p_all["traded"]
    shrink_pct = 100.0 * shrink / o_all["traded"] if o_all["traded"] else 0.0
    w = st["wiped"][PRIMARY]
    tk_off, tk_pri = A["off"]["split"]["sizeable"], A[PRIMARY]["split"]["sizeable"]
    d_clean = (tk_pri["meanr"] - tk_off["meanr"]) if (tk_off and tk_pri) else 0.0

    def cols(fn):
        """One row of the wide tables: off, then every ON arm in ARM_ON order."""
        return " | ".join(fn(a) for a in MEASURED)

    L.append("# W1 -- kill `B`: Austin's S/A/C/X ladder as the engine's grade")
    L.append("")
    L.append("**Held-out first, and the verdict arm is the `B`-floor removal ON ITS "
             "OWN** (`CLAUDE.md`: held-out beats in-sample, always). On the 100 OMEN "
             "Test 1 cards `nofloor` moves S recall **%s -> %s** and false fires on "
             "days Austin refused **%s -> %s**. It buys 4 fewer false fires by going "
             "silent on the S days too."
             % (_f(o1["s_hit"], o1["s_n"]), _f(p1["s_hit"], p1["s_n"]),
                _f(o1["x_fire"], o1["x_n"]), _f(p1["x_fire"], p1["x_n"])))
    L.append("")
    L.append("**AND THE LADDER ITSELF IS REFUTED.** On 2026-08-28 Austin graded "
             "**%d** of these `B`-only signals himself "
             "(`research/marks/deck_marks_h2_3lane_2026-08-28.jsonl`). Scored against "
             "the spec's ladder his agreement is **%d/%d = %s** -- *worse* than always "
             "guessing `X`, which scores **%s** on the same rows. Section 2 is that "
             "measurement. Killing the `B` floor is still right, because arrival order "
             "should not select the book; \"count the downgrades and map to S/A/C/X\" "
             "is a hypothesis that has now been tested against his own verdicts and "
             "failed, and it is reported here as a control rather than as the answer."
             % (mk["n"], mk["ladder_raw"]["hits"], mk["n"],
                _pct(mk["ladder_raw"]["acc"]), _pct(mk["majority"]["acc"])))
    L.append("")
    L.append("**On the money: median R %+.4f -> %+.4f, mean R %+.4f -> %+.4f, months "
             "green %d/%d -> %d/%d, and the book falls %s -> %s traded rows -- "
             "%+d, %.1f%% of it.** %d of the %d symbols that traded at all lose their "
             "ENTIRE book (section 5 names them)."
             % (o_all["median_r"], p_all["median_r"], o_all["meanr"], p_all["meanr"],
                o_all["months_green"], o_all["months"], p_all["months_green"],
                p_all["months"], "{:,}".format(o_all["traded"]),
                "{:,}".format(p_all["traded"]), -shrink, shrink_pct,
                len(w["wiped"]), w["n_sym_off"]))
    L.append("")
    L.append("**And the `B` floor is not only doing arrival order -- it is the "
             "mechanism that BYPASSES the tight-stop gate.** "
             "`backtest_week.Trade.counted` excludes `C`: a `C` is alert-only and "
             "never reaches traded P&L, and a `C` also has to clear "
             "`_min_viable_stop` where a `B` does not. So demoting the 968 floored "
             "signals back to `C` does not re-rank them, it removes them: %s fired "
             "-> %s, of which %s are alerts. The spec's ladder says `C` IS tradeable "
             "(section 1.2); this engine says `C` is alert-only. Those two cannot both "
             "be true and only Austin closes it."
             % ("{:,}".format(A["off"]["n_fired"]),
                "{:,}".format(A[PRIMARY]["n_fired"]),
                "{:,}".format(A[PRIMARY]["n_alert"])))
    L.append("")
    L.append("**The ladder arms are still reported, and which variables they count "
             "is not the shipped eight.** `research/w9_downgrade_signs.md` "
             "(2026-08-28) re-signed all eight on this same book: "
             "`level_not_respected` is **wrong-signed** "
             "and fires on 62.7% of it (tripped +1.0046R vs clean +0.8711R), and "
             "`break_then_rejection` never trips on a traded row at all. Dropping the "
             "wrong-signed one and keeping the rest is the ONLY set of the three W9 "
             "simulated that is **not monotonic** -- C collapses onto the stop floor "
             "and ties with X. W9's set (c) -- the seven right-signed variables plus "
             "`sequence_gate` turned on -- is monotonic without carrying the bug, so "
             "that is what `on_w9c` counts, and the shipped eight are arm `on`. "
             "Neither set survives section 2.")
    L.append("")
    L.append("Nothing here ships. `signal_runner.ENABLE_SAC_LADDER` defaults to "
             "**False**, `SAC_LADDER_VARSET` defaults to `\"shipped\"`, "
             "`downgrade.ENABLE_SEQUENCE_GATE`'s committed default is **not touched** "
             "(the `w9c` arm passes `enable_sequence_gate=True` per call, the opt-in "
             "`score()` already provides), the `B` floor is not deleted, `ON_WATCH` "
             "stays at its shipped default (spec section 1.5), and the engine is not "
             "re-frozen -- that would VOID `research/omen6_forward.py` and it is "
             "Austin's call. Measured at _this commit_ by "
             "`research/w1_sac_ladder_ab.py`.")
    L.append("")
    L.append("| arm | what it is |")
    L.append("|---|---|")
    for a in MEASURED:
        L.append("| `%s` | %s |" % (a, ARM_LABEL[a]))
    L.append("")

    # ---- 1. what was implemented ----------------------------------------
    L.append("## 1. What was implemented")
    L.append("")
    L.append("> \"B is not supposed to be a trade. We changed it to A and C. S and A "
             "and C.\"  ")
    L.append("> \"S A C grades are kept, A one downgrade, C two downgrades, revisit B "
             "trades and mold them into those grades or 'x' kill them.\"  ")
    L.append("> -- Austin, 2026-08-28")
    L.append("")
    L.append("`research/g4_dropped_s.md` is the finding this implements: **968 of the "
             "1,016 traded signals (95.3%) are `B` ONLY because of "
             "`_calibration_grade`'s first-with-trend-signal-of-the-day floor.** The "
             "engine trades on grade, so arrival order -- not the setup -- selects the "
             "entire book.")
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    L.append("| flag | `signal_runner.ENABLE_SAC_LADDER`, **default False** |")
    L.append("| variable set | `signal_runner.SAC_LADDER_VARSET`, **default "
             "`\"shipped\"`**; `\"w9c\"` is W9's set (c) |")
    L.append("| reach | `signal_runner.SAC_LADDER_REGRADE_ALL`, **default False** -- "
             "see section 6 |")
    L.append("| seam | `SignalRunner._calibration_grade` -> "
             "`SignalRunner._sac_ladder_grade`, the LAST write to `sig[\"grade\"]` "
             "before `_route` decides |")
    L.append("| OFF | `_grade_for_levels` + the counter-day-trend cap + the "
             "first-with-trend `B` floor -- the shipped chain, unchanged |")
    L.append("| ON | the floor does not run; the final grade is the **net downgrade "
             "count** from `research/downgrade.py::score()` |")
    L.append("| unchanged either way | detection, the counter-day-trend cap, the fill, "
             "the stop, the R denominator, the downgrade variables' own code, "
             "`ON_WATCH` |")
    L.append("")
    L.append("**The ladder.** `signal_runner.SAC_TIER` maps his grade onto the "
             "engine's alphabet, and `B` is deliberately **not in the range** -- "
             "killing it is the whole point:")
    L.append("")
    L.append("| net downgrades | his grade | engine tier | tradeable |")
    L.append("|---:|---|---|---|")
    L.append("| 0 or fewer | **S** | `A+` | yes |")
    L.append("| 1 | **A** | `A` | yes |")
    L.append("| 2 | **C** | `C` | yes |")
    L.append("| 3 or more | **X** | `X` | **no -- `_SKIP_GRADES`** |")
    L.append("")
    L.append("`net` is the tripped count after `downgrade.py`'s confluence `+1` "
             "(Austin, 2026-08-24: BR+OCR confluence \"counts as +1 instead of a "
             "downgrade\"). W9 floors `net` at 0 and this does not; the two are "
             "grade-equivalent, since anything at or below 0 is `S` either way. The "
             "round trip against `research/t70_test1_score.LADDER` is exact -- "
             "`A+ -> S`, `A -> A`, `C -> C` -- so this A/B and the held-out scorer "
             "count the same thing. `research/test_sac_ladder.py` asserts it.")
    L.append("")
    L.append("**The two variable sets, named rather than buried.**")
    L.append("")
    L.append("| set | variables counted |")
    L.append("|---|---|")
    L.append("| `shipped` (arm `on`) | the eight as committed, including the "
             "wrong-signed `level_not_respected` and the never-tripping "
             "`break_then_rejection` |")
    L.append("| `w9c` (arm **`on_w9c`**) | those eight minus `level_not_respected`, "
             "**plus `sequence_gate` turned on for this call** (ballot b2, "
             "right-signed at -0.3216R on this book) |")
    L.append("")
    L.append("`sequence_gate` needs state `score()` cannot compute -- the 1-based "
             "ordinal of this entry among every entry graded on the same symbol-day. "
             "`SignalRunner._sac_seq` supplies it, incremented on **every** signal "
             "that reaches the grader whatever its incumbent grade, which is the same "
             "population and ordering "
             "`research/p20_sequence_gate.annotate_sequence` uses over the book -- so "
             "the engine and W9's simulation count the same thing. The 84%-rule "
             "re-entry is exempt, per Austin.")
    L.append("")
    L.append("**One conflict, resolved in the spec's favour and named rather than "
             "hidden.** `downgrade.score()` FLOORS its own ladder at `C` -- Austin, "
             "2026-08-24, asked directly what happens at three or more downgrades. The "
             "2026-08-28 ladder above kills the 3+ bucket as `X` instead. This flag "
             "implements the LATER answer, the one `Specs/omen6-h2-master-spec.md` "
             "section 1.2 makes the contract, by reading the tripped list rather than "
             "`score()[\"grade\"]` -- so `downgrade.py` itself is untouched and the "
             "floor simply is not applied. **If Austin meant the C floor to stand, the "
             "3+ bucket becomes `C` and most of the lost book comes back**; that is a "
             "one-line change and it is his call, not mine.")
    L.append("")
    L.append("A signal `score()` cannot grade (no bars, or no level) is `X`, not a "
             "guess -- absence of an input is not evidence of a setup, the convention "
             "`downgrade.py` itself uses.")
    L.append("")

    # ---- 2. THE REFUTATION ----------------------------------------------
    L.append("## 2. The ladder does not reproduce him -- his own %d verdicts"
             % mk["n"])
    L.append("")
    L.append("On 2026-08-28 Austin graded **%d engine-proposed `B`-only signals** "
             "himself: `research/marks/deck_marks_h2_3lane_2026-08-28.jsonl`, lane "
             "`b_remap`. These are the exact rows the remap is about, so for the first "
             "time the ladder can be scored against the thing it claims to reproduce "
             "rather than against a book. Scored by "
             "`research/w1_ladder_vs_marks.py`." % mk["n"])
    L.append("")
    L.append("| | agreement with Austin | 95% CI |")
    L.append("|---|---:|---:|")
    L.append("| **the spec's ladder** (raw downgrade count) | **%d/%d = %s** | %s |"
             % (mk["ladder_raw"]["hits"], mk["n"], _pct(mk["ladder_raw"]["acc"]),
                _ci(mk["ladder_raw"]["hits"], mk["n"])))
    L.append("| the ladder on the NET count (confluence +1 applied) | %d/%d = %s | %s |"
             % (mk["ladder_net"]["hits"], mk["n"], _pct(mk["ladder_net"]["acc"]),
                _ci(mk["ladder_net"]["hits"], mk["n"])))
    L.append("| **majority class** -- always guess `%s` | **%d/%d = %s** | %s |"
             % (mk["majority"]["grade"], mk["majority"]["hits"], mk["n"],
                _pct(mk["majority"]["acc"]), _ci(mk["majority"]["hits"], mk["n"])))
    L.append("")
    L.append("**The ladder is worse than guessing.** A grader that cannot beat "
             "\"always say X\" has not learned anything about his judgement. The net "
             "count is worse still (%s), and %d of the %d cards pin the confluence bit "
             "exactly -- where they do not, the raw count is used, which can only "
             "flatter the net row."
             % (_pct(mk["ladder_net"]["acc"]), mk["net_exact"], mk["n"]))
    L.append("")
    L.append("**And `B` is not garbage.** He takes **%d of %d = %s** of them, "
             "including **%d S**. His S grades came at downgrade counts %s and "
             "**never at 0**; at 0 downgrades, where the ladder says `S`, he said `A` "
             "both times. The count is not monotonic in his judgement."
             % (mk["n_take"], mk["n"], _pct(mk["take_rate"]), mk["n_s"],
                mk["s_at_counts"]))
    L.append("")
    L.append("| downgrades | cards | ladder says | his S | his A | his C | his X |")
    L.append("|---:|---:|---|---:|---:|---:|---:|")
    for b in mk["by_count"]:
        L.append("| %d | %d | %s | %d | %d | %d | %d |"
                 % (b["n"], b["total"], b["ladder"], b["his"]["S"], b["his"]["A"],
                    b["his"]["C"], b["his"]["X"]))
    L.append("")
    L.append("### No single variable separates either")
    L.append("")
    L.append("His base X rate on these cards is %s. A variable carries information "
             "only if his X rate differs between the rows it trips on and the rows it "
             "does not."
             % _pct(mk["per_variable"]["base_x_rate"]))
    L.append("")
    L.append("| variable | trips | X rate when tripped | X rate when clean | delta |")
    L.append("|---|---:|---:|---:|---:|")
    for v in mk["per_variable"]["vars"]:
        L.append("| `%s` | %d (%.1f%%) | %s | %s | %s |"
                 % (v["var"], v["n_trip"], v["trip_pct"],
                    "n/a" if v["x_rate_tripped"] is None else _pct(v["x_rate_tripped"]),
                    "n/a" if v["x_rate_clean"] is None else _pct(v["x_rate_clean"]),
                    "n/a" if v["delta"] is None else "%+.1f pts" % (100 * v["delta"])))
    L.append("")
    L.append("`counter_trend_not_respected` fires on %.0f%% of the cards -- a variable "
             "that is true of almost every row cannot separate anything, whichever way "
             "it points. `stale_retest` and `break_then_rejection` never trip at all, "
             "which is the same finding `research/w9_downgrade_signs.md` reached on the "
             "2-year book from the other direction."
             % [v for v in mk["per_variable"]["vars"]
                if v["var"] == "counter_trend_not_respected"][0]["trip_pct"])
    L.append("")
    L.append("### Does ANY function of the eight beat the baseline?")
    L.append("")
    sr_ = mk["search"]
    L.append("Scored on TAKE vs SKIP -- the decision the engine actually makes, and "
             "the easier of the two problems. Every fitted family is scored "
             "**leave-one-out**, refitting inside each fold, so that fitting on n=%d "
             "cannot be mistaken for a result." % mk["n"])
    L.append("")
    L.append("| rule | accuracy | 95% CI | separates from baseline? |")
    L.append("|---|---:|---:|---|")
    L.append("| majority class (always `%s`) | %s | %s | -- |"
             % (sr_["majority_class"], _pct(sr_["majority_take_acc"]),
                _ci(int(round(sr_["majority_take_acc"] * sr_["n"])), sr_["n"])))
    for k, label in (("ladder_take", "the spec's ladder (no fitting)"),
                     ("count_threshold", "best count threshold (LOO)"),
                     ("best_variable", "best single variable (LOO)"),
                     ("weighted", "weighted score (LOO)")):
        r = sr_[k]
        L.append("| %s | %d/%d = %s | %s | %s |"
                 % (label, r["hits"], r["n"], _pct(r["acc"]),
                    _ci(r["hits"], r["n"]),
                    "**yes**" if r["separates"] else
                    ("no -- beats it by %d rows, CI still contains it"
                     % (r["hits"] - int(round(sr_["majority_take_acc"] * sr_["n"])))
                     if r["beats_majority"] else "no")))
    L.append("")
    best = max(("ladder_take", "count_threshold", "best_variable", "weighted"),
               key=lambda k: sr_[k]["acc"])
    any_sep = any(sr_[k]["separates"] for k in
                  ("ladder_take", "count_threshold", "best_variable", "weighted"))
    L.append("**%s** The best of them (`%s`, %s) is %d rows better than the baseline "
             "on %d cards, and its interval still contains it. Fitting harder on 59 "
             "rows is how a project convinces itself of something that is not there, "
             "so this stops here."
             % ("Nothing tried separates from the majority-class baseline." if not any_sep
                else "One family separates -- treat it as a hypothesis, not a result.",
                best, _pct(sr_[best]["acc"]),
                sr_[best]["hits"] - int(round(sr_["majority_take_acc"] * sr_["n"])),
                sr_["n"]))
    L.append("")
    L.append("**Caveats, stated where the number is quoted.** n=%d is small; one row "
             "of a 60-card lane may not have been pasted (the file carries %d graded "
             "rows and %d were skipped as ungraded or off-lane). He grades the "
             "remaining 60 cards tomorrow morning, so this is a **first read, not a "
             "verdict** -- but it is enough to stop the ladder shipping as though it "
             "reproduced him." % (mk["n"], mk["n"], mk["skipped"]))
    L.append("")

    # ---- 3. byte identity -----------------------------------------------
    L.append("## 3. With the flag OFF the book is byte-identical to HEAD")
    L.append("")
    L.append("The claim, checked rather than asserted. `backtest_2y.py` was run once "
             "per arm against the same `data_archive/` -- first from **unmodified HEAD "
             "code before the flag existed**, then from the patched tree with the flag "
             "forced in each child's environment. sha256 is taken over the whole "
             "`trades` array; `meta.generated` is a wall clock and is the one field "
             "excluded. `data_archive/` is cache-first and no run made a network call.")
    L.append("")
    L.append("| run | environment | signals | traded | sha256 of `trades` |")
    L.append("|---|---|---:|---:|---|")
    for arm in ("head",) + MEASURED:
        b = A.get(arm)
        if b is None:
            continue
        env = ARMS[arm][0]
        L.append("| `%s` | %s | %s | %s | `%s` |"
                 % (arm,
                    "unmodified HEAD, no flag" if not env
                    else " ".join("`%s=%s`" % kv for kv in sorted(env.items())),
                    "{:,}".format(b["all"]["signals"]),
                    "{:,}".format(b["all"]["traded"]), b["digest"]))
    L.append("")
    same = bool(A.get("head")) and A["head"]["digest"] == A["off"]["digest"]
    L.append("**`head` and `off` are %s.** The flag-off engine is the flag-less engine "
             "-- %s signals and %s traded rows, every field of every row equal. "
             "Reproduce with `python research/w1_sac_ladder_ab.py identical`."
             % ("identical" if same else "**NOT identical -- see the run log**",
                "{:,}".format(A["off"]["all"]["signals"]),
                "{:,}".format(A["off"]["all"]["traded"])))
    L.append("")

    # ---- 3. the held-out cards ------------------------------------------
    L.append("## 4. The 100 HELD-OUT OMEN Test 1 cards -- reported first")
    L.append("")
    L.append("`research/marks/probe_omen_test1_2026-08-27.jsonl` -- 15 S / 27 A / "
             "16 C / 42 X, graded 2026-08-27, never shown to the engine and never "
             "fitted on. Scored by `research/t70_test1_score.py`'s own `score_all`, "
             "imported not reimplemented, once per arm. `grade_std: \"none\"` is his "
             "**X**: he looked at the day and refused it, so a fire there is a false "
             "fire, not an unlabelled day.")
    L.append("")
    L.append("| metric | %s |" % cols(lambda a: "%s`%s`%s"
                                      % ("**" if a == PRIMARY else "", a,
                                         "**" if a == PRIMARY else "")))
    L.append("|---|%s" % ("---:|" * len(MEASURED)))
    for label, key, den in (
            ("**S recall** -- fires at all on an S day", "s_hit", "s_n"),
            ("S recall, in-universe", "s_hit_in", "s_n_in"),
            ("**false fire** on refused (X) days", "x_fire", "x_n"),
            ("false fire, in-universe", "x_fire_in", "x_n_in"),
            ("entry match +-2 bars (of the 58)", "entry_match", "graded"),
            ("day precision (of days it fired on)", "day_prec_hit", "day_prec_n")):
        L.append("| %s | %s |"
                 % (label, cols(lambda a: _f(C[a][key], C[a][den]))))
    L.append("| **grade agreement** on the 58 he graded | %s |"
             % cols(lambda a: _f(G[a]["diag"], G[a]["n"])))
    L.append("| engine tier mix | %s |" % cols(lambda a: str(C[a]["tiers"])))
    L.append("")
    L.append("**The verdict arm moves S recall %+d and false fires %+d.**"
             % (d_srec, d_ff))
    L.append("")

    def gate_score(a):
        return (C[a]["s_hit"] / max(C[a]["s_n"], 1)
                - C[a]["x_fire"] / max(C[a]["x_n"], 1))
    L.append("**Read the recall and the false fires together.** The combined gate "
             "(`research/p23_combined_arms.md`) is recall minus false-fire rate: %s. "
             "An arm that fires less often gives up recall and false fires at the same "
             "time, so neither column ranks it alone."
             % ", ".join("`%s` %+.3f" % (a, gate_score(a)) for a in MEASURED))
    L.append("")
    L.append("**Recall governs** (`CLAUDE.md` / ballot q20: a complete engine miss of "
             "an S trade matters more than tier accuracy). On the verdict arm S recall "
             "moves %+d, so this ladder **%s**. The only arm here that buys held-out "
             "recall is `on_all`, and it buys it by firing on far more refused days as "
             "well -- see section 6."
             % (d_srec, "does not pay for its shrunken book in recall" if d_srec <= 0
                else "buys held-out recall"))
    L.append("")
    L.append("### Which held-out S days each arm finds")
    L.append("")
    L.append("| arm | S days found (of 15) |")
    L.append("|---|---|")
    for a in MEASURED:
        hits = sorted("%s %s" % (r["symbol"], r["date"])
                      for r in t1[a] if r["his"] == "S" and r["n_fires"] > 0)
        L.append("| `%s` | %d -- %s |" % (a, len(hits), ", ".join(hits) or "none"))
    L.append("")
    L.append("### Which held-out days each arm switches, against `off`")
    L.append("")
    L.append("| his grade | %s |"
             % " | ".join("`%s`: +fired / -lost" % a for a in ARM_ON))
    L.append("|---|%s" % ("---|" * len(ARM_ON)))
    for g in ("S", "A", "C", "X"):
        cells = []
        for a in ARM_ON:
            got = SW[a]["gained"].get(g, [])
            lost = SW[a]["lost"].get(g, [])
            cells.append("+%d %s / -%d %s"
                         % (len(got), ", ".join(got) or "--",
                            len(lost), ", ".join(lost) or "--"))
        L.append("| **%s** | %s |" % (g, " | ".join(cells)))
    L.append("")
    L.append("### Grade agreement")
    L.append("")
    L.append("Rows are his grade; columns are the best engine tier fired that day, "
             "mapped onto his ladder by `t70_test1_score.maps_to`. The diagonal is "
             "agreement.")
    L.append("")
    for a in MEASURED:
        ag = G[a]
        L.append("**`%s`** -- diagonal %s" % (a, _f(ag["diag"], ag["n"])))
        L.append("")
        L.append("| his \\ engine | A+ (his S) | A / B (his A) | C (his C) | "
                 "silent (his X) | row total |")
        L.append("|---|---:|---:|---:|---:|---:|")
        for g in ("S", "A", "C"):
            row = ag["tab"][g]
            L.append("| **%s** | %d | %d | %d | %d | %d |"
                     % (g, row.get("S", 0), row.get("A", 0), row.get("C", 0),
                        row.get("X", 0), sum(row.values())))
        L.append("")

    # ---- 4. money --------------------------------------------------------
    L.append("## 5. Money -- the 2-year book, median R first")
    L.append("")
    L.append("Austin's stated goal (spec section 0) is **raising the median R:R**, so "
             "median R leads this table and mean R follows it. Every arm: "
             "`backtest_2y.py` shelled once with the flag forced in the child's "
             "environment, same `data_archive/`, cache-first with zero fetches. Win "
             "rate is of DECIDED trades (scratches excluded), the convention "
             "`research/a2_bt2y_summary.py` prints and this table imports. `months "
             "green` is months with positive total R; the durability gate is EVERY "
             "month green.")
    L.append("")
    L.append("| arm | population | signals | **n traded** | **median R** | mean R | "
             "win rate | months green | total R |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for arm in MEASURED:
        for pop, key in (("whole book", "all"), ("S subset (`sgrade`)", "S")):
            s = A[arm][key]
            L.append("| %s`%s`%s | %s | %s | **%s** | **%+.4f** | %+.4f | %.1f%% | "
                     "**%d / %d** | %+.1f |"
                     % ("**" if arm == PRIMARY else "", arm,
                        "**" if arm == PRIMARY else "", pop,
                        "{:,}".format(s["signals"]), "{:,}".format(s["traded"]),
                        s["median_r"], s["meanr"], s["wr"], s["months_green"],
                        s["months"], s["totr"]))
    L.append("")
    L.append("| delta vs `off` | n traded | **median R** | mean R | win rate | "
             "months green | total R |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for arm in ARM_ON:
        for pop, key in (("whole book", "all"), ("S subset", "S")):
            o, n = A["off"][key], A[arm][key]
            L.append("| `%s`, %s | %+d | **%+.4f** | %+.4f | %+.1f pts | %+d | %+.1f |"
                     % (arm, pop, n["traded"] - o["traded"],
                        n["median_r"] - o["median_r"], n["meanr"] - o["meanr"],
                        n["wr"] - o["wr"], n["months_green"] - o["months_green"],
                        n["totr"] - o["totr"]))
    L.append("")
    passing = [a for a in MEASURED
               if A[a]["all"]["meanr"] >= 2.0
               and A[a]["all"]["months_green"] == A[a]["all"]["months"]]
    L.append("**The money gate is mean R = 2.0 with EVERY month green. %s.** On the "
             "verdict arm the median goes %+.4f -> %+.4f (**%+.4f**), which is the "
             "number Austin actually asked to move, and the mean goes %+.4f -> %+.4f."
             % ("No arm reaches it" if not passing
                else "Only %s appear to reach it and %s do not count -- %s of that "
                     "arm's rows are UNTAKEABLE (section 9), so its mean R is "
                     "arithmetic, not money"
                     % (", ".join("`%s`" % a for a in passing),
                        "they" if len(passing) > 1 else "it",
                        ", ".join("%.1f%%" % A[a]["split"]["pct_unsizeable"]
                                  for a in passing)),
                o_all["median_r"], p_all["median_r"], d_med,
                o_all["meanr"], p_all["meanr"]))
    L.append("")
    L.append("### Is the ladder monotonic on the book it produces?")
    L.append("")
    L.append("W9's whole point: a ladder is only a ladder if the buckets are ordered. "
             "Measured here on each arm's OWN traded rows, by the engine grade it "
             "actually shipped.")
    L.append("")
    L.append("| arm | %s |"
             % " | ".join("%s (n, median R)" % g for g in ("A+ = S", "A", "C")))
    L.append("|---|---:|---:|---:|")
    for arm in MEASURED:
        cells = []
        for tier in ("A+", "A", "C"):
            d = A[arm]["by_grade"].get(tier)
            cells.append("%d, %+.4f" % (d["n"], d["median_r"]) if d else "0, --")
        L.append("| `%s` | %s |" % (arm, " | ".join(cells)))
    L.append("")

    # ---- the grade mix, the point of the ticket -------------------------
    L.append("### `B` is gone -- the engine-grade mix over the traded rows")
    L.append("")
    keys = sorted(set().union(*(set(A[a]["grades"]) for a in MEASURED)), key=str)
    L.append("| arm | %s | total |" % " | ".join("`%s`" % g for g in keys))
    L.append("|---|%s---:|" % ("---:|" * len(keys)))
    for arm in MEASURED:
        g = A[arm]["grades"]
        L.append("| `%s` | %s | %s |"
                 % (arm, " | ".join("{:,}".format(g.get(k, 0)) for k in keys),
                    "{:,}".format(sum(g.values()))))
    L.append("")
    # `nofloor` removes the ARRIVAL-ORDER floor only; the 84%-rule blocks in
    # `detect_signals` still emit `B` directly, so a residue there is expected
    # and is not the ladder failing to be the last word.
    b_bad = [a for a in ARM_ON if a != "nofloor" and A[a]["grades"].get("B", 0)]
    L.append("**`B` traded rows: %s on `off`, %s.** %s"
             % ("{:,}".format(A["off"]["grades"].get("B", 0)),
                ", ".join("%s on `%s`" % (A[a]["grades"].get("B", 0), a)
                          for a in ARM_ON),
                "The ladder arms emit no `B` at all. `nofloor` still shows a "
                "residue because it removes the ARRIVAL-ORDER floor only -- the "
                "84%-rule blocks in `detect_signals` emit `B` directly and are "
                "untouched by this ticket."
                if not b_bad else
                "**`B` SURVIVES on %s -- the ladder is not the last word somewhere, "
                "and that is a bug, not a result.**"
                % ", ".join("`%s`" % a for a in b_bad)))
    L.append("")

    # ---- 5. the shrink ---------------------------------------------------
    L.append("## 6. How hard the book shrinks, and who loses everything")
    L.append("")
    L.append("| | %s |" % cols(lambda a: "`%s`" % a))
    L.append("|---|%s" % ("---:|" * len(MEASURED)))
    L.append("| signals detected | %s |"
             % cols(lambda a: "{:,}".format(A[a]["all"]["signals"])))
    L.append("| **traded rows** | %s |"
             % cols(lambda a: "{:,}".format(A[a]["all"]["traded"])))
    L.append("| change vs `off` | %s |"
             % cols(lambda a: "--" if a == "off" else "%+d (%.1f%%)"
                    % (A[a]["all"]["traded"] - o_all["traded"],
                       100.0 * (A[a]["all"]["traded"] - o_all["traded"])
                       / max(o_all["traded"], 1))))
    L.append("| symbols with a book | %s |"
             % cols(lambda a: str(A[a]["n_symbols"])))
    L.append("| total R | %s |"
             % cols(lambda a: "%+.1f" % A[a]["all"]["totr"]))
    L.append("")
    L.append("### Every symbol that loses its ENTIRE book on `%s`" % PRIMARY)
    L.append("")
    if w["wiped"]:
        L.append("**%d symbols, %s trades, %+.1f R of booked result.** Rows under "
                 "`universe.MIN_SAMPLE_N` (=%d) are MARKED, never dropped -- below ~%d "
                 "trades one more trade swings the mean by the same order as the money "
                 "gate itself."
                 % (len(w["wiped"]), "{:,}".format(w["n_trades_wiped"]),
                    w["total_r_wiped"], MIN_SAMPLE_N, MIN_SAMPLE_N))
        L.append("")
        L.append("| symbol | trades lost | median R it was booking | mean R | total R |")
        L.append("|---|---:|---:|---:|---:|")
        for x in w["wiped"]:
            L.append("| %s%s | %d | %+.4f | %+.4f | %+.1f |"
                     % (x["sym"], " _(low n)_" if x["thin"] else "", x["n_off"],
                        x["median_r_off"], x["mean_r_off"], x["total_r_off"]))
    else:
        L.append("**None.** Every symbol that traded on `off` still trades on `%s`; "
                 "the shrink is a thinning, not an amputation." % PRIMARY)
    L.append("")
    for a in ARM_ON:
        if a == PRIMARY:
            continue
        ww = st["wiped"][a]
        L.append("On `%s` the same count is **%d** symbol(s)%s."
                 % (a, len(ww["wiped"]),
                    (" -- " + ", ".join(x["sym"] for x in ww["wiped"]))
                    if ww["wiped"] else ""))
    L.append("")
    L.append("### Per symbol")
    L.append("")
    ps = {a: {d["sym"]: d for d in A[a]["per_symbol"]} for a in MEASURED}
    allsym = sorted(set().union(*(set(v) for v in ps.values())),
                    key=lambda s: -sum(ps[a].get(s, {}).get("n", 0) for a in MEASURED))
    L.append("| symbol | %s |"
             % " | ".join("`%s` n / mean R" % a for a in MEASURED))
    L.append("|---|%s" % ("---:|" * len(MEASURED)))
    for sym in allsym:
        if all(ps[a].get(sym) == ps["off"].get(sym) for a in MEASURED):
            continue
        cells = []
        for a in MEASURED:
            d = ps[a].get(sym)
            cells.append("--" if d is None
                         else "%d%s / %+.4f" % (d["n"], " _(low n)_" if d["thin"]
                                                else "", d["mean_r"]))
        L.append("| %s | %s |" % (sym, " | ".join(cells)))
    L.append("")

    # ---- killing B moves three gates nobody chose to move ----------------
    L.append("## 7. What killing `B` does to three gates downstream")
    L.append("")
    L.append("`research/w12_bug_sweep.md` swept the grade and gate path the night this "
             "ticket ran, precisely because 1,000 of the 1,017 rows in the traded book "
             "are `B`. Three of its findings are downstream of this remap and are "
             "**measured here on the actual arm books**, not simulated.")
    L.append("")
    L.append("### 1. The tight-stop gate is consulted on `C` only, and it is "
             "sign-backwards")
    L.append("")
    L.append("`signal_runner._route` asks `_min_viable_stop` when "
             "`sig[\"grade\"] == \"C\"` and never otherwise. Re-derived on the "
             "graded bar over the 1,017 traded rows "
             "(`research/w12_tight_stop.py`), it **rejects the better half**: "
             "rejected rows mean **+1.0861 R**, kept rows **+0.6188 R** -- a gap of "
             "**0.4673 R, 49x the +-0.0095 R narrow bar**, in the wrong direction.")
    L.append("")
    L.append("Today it barely matters because `C` is small. **This ticket is what "
             "makes it matter**, and the arm books show it happening:")
    L.append("")
    L.append("| arm | `skipped_tight_stop` | vs `off` |")
    L.append("|---|---:|---:|")
    for a in MEASURED:
        n = A[a]["status"].get("skipped_tight_stop", 0)
        L.append("| `%s` | %s | %s |"
                 % (a, "{:,}".format(n), "--" if a == "off" else "%+d"
                    % (n - A["off"]["status"].get("skipped_tight_stop", 0))))
    L.append("")
    L.append("Read that table carefully: `nofloor` sends **%+d** more rows into the "
             "gate, because demoting the floored `B`s leaves them all `C`. The ladder "
             "arms send FEWER, because the ladder promotes most of those same rows to "
             "`A+`/`A` where the gate is never consulted at all -- so on those arms "
             "the gate is not doing the shrinking, the `X` bucket is."
             % (A["nofloor"]["status"].get("skipped_tight_stop", 0)
                - A["off"]["status"].get("skipped_tight_stop", 0)))
    L.append("")
    L.append("**So `C`'s mean R in every table above is depressed by a gate that "
             "throws away its better rows, and the verdict arm's collapse is mostly "
             "that gate rather than the grade.** Nothing here fixes it -- widening it "
             "to all grades, dropping it, or leaving it is a decision with a 0.4673 R "
             "price tag on it, and it is Austin's.")
    L.append("")
    L.append("### 2. `C` is alert-only, so the spec's `C = tradeable` cannot happen")
    L.append("")
    L.append("`backtest_week.SimTrade.counted` is `status == \"fired\" and grade != "
             "\"C\"`. Spec section 1.2 says two downgrades = `C` = **tradeable: "
             "yes**. Those two cannot both be true, and the code wins today: no `C` "
             "has ever entered the traded book.")
    L.append("")
    L.append("| arm | fired | of which alerts (`C`) | traded |")
    L.append("|---|---:|---:|---:|")
    for a in MEASURED:
        L.append("| `%s` | %s | %s | %s |"
                 % (a, "{:,}".format(A[a]["n_fired"]), "{:,}".format(A[a]["n_alert"]),
                    "{:,}".format(A[a]["all"]["traded"])))
    L.append("")
    L.append("W12 priced the difference on the shipped-eight ladder: **n=379 mean "
             "+1.0926 median +0.9400** with `C` excluded against **n=710 mean +1.0069 "
             "median +0.7070** with `C` included. This report's book columns are the "
             "`C`-excluded reading, because that is what the engine does.")
    L.append("")
    L.append("### 3. The 84%-rule arm population moves by 22x as a side effect")
    L.append("")
    L.append("`backtest_week._arm_84` needs `t.counted and t.grade in (\"A+\", "
             "\"A\")`. The shipped grader emits 17 such rows in 45,193 signals, so "
             "the 84% rule fires three times in two years. The ladder emits `A+` and "
             "`A` freely, and the arm population moves with it -- **nobody chose "
             "that**:")
    L.append("")
    L.append("| arm | traded rows graded `A+` or `A` |")
    L.append("|---|---:|")
    for a in MEASURED:
        L.append("| `%s` | %s |" % (a, "{:,}".format(A[a]["n_arm_eligible"])))
    L.append("")
    L.append("`research/test_w12_grade_gates.py` asserts all three of these at HEAD "
             "and is **green** with every flag here at its default, which is the point "
             "of the defaults. Flip one and those asserts are the tripwire, not a "
             "regression.")
    L.append("")

    # ---- 6. which trades swapped ----------------------------------------
    L.append("## 8. Which trades the ladder swapped, and the two levers kept apart")
    L.append("")
    L.append("`on_all` is reported beside the verdict arm and never averaged into it. "
             "It lets the same ladder ALSO regrade the **42,937** signals "
             "`omen_bot._grade_pa` already vetoed on candle shape. That is R3's lever "
             "(`ENABLE_DOWNGRADE_GRADER`, priced in "
             "`research/r3_downgrade_grader_ab.md`) reached by a different road: it "
             "makes the book GROW rather than shrink, and conflating the two would "
             "turn W1 into an experiment that was already run.")
    L.append("")
    L.append("Rows below are matched between `off` and `%s` on `(symbol, day, entry "
             "time, setup, direction, level)` -- detection does not read the grade, so "
             "the same setup on the same bar is the same row "
             "(`g13_floor_fix_ab.row_key`). That key is not unique in every book: "
             "**%d `off` and %d `%s` traded rows collide on it** and are counted once "
             "here. Every headline number above is taken from the RAW traded list, "
             "never from this deduped view."
             % (PRIMARY, mc["key_collisions_off"], mc["key_collisions_on"], PRIMARY))
    L.append("")
    L.append("| | count | of which takeable | mean R | median R | max R |")
    L.append("|---|---:|---:|---:|---:|---:|")
    L.append("| traded in BOTH arms | %s | -- | %+.4f | %+.4f | -- |"
             % ("{:,}".format(mc["shared_n"]), mc["shared_off"]["meanr"],
                mc["shared_off"]["median_r"]))
    for k, label in (("lost", "**lost** -- traded `off`, not `%s`" % PRIMARY),
                     ("gained", "**gained** -- traded `%s`, not `off`" % PRIMARY)):
        p = mc[k]
        L.append("| %s | %s | %s | %+.4f | %+.4f | %+.1f |"
                 % (label, "{:,}".format(p["n"]), "{:,}".format(p["n_sizeable"]),
                    p["mean_r"], p["median_r"], p["max_r"]))
    L.append("")
    L.append("What became of the lost trades in the `%s` arm: %s."
             % (PRIMARY, ", ".join("`%s` %d" % (k, v)
                                   for k, v in st["compose"]["lost_status_on"].items())))
    L.append("")
    L.append("**The matched population is the one place the ladder could change price "
             "rather than membership, and it does not**: %s rows traded by both arms, "
             "**%d** with a different R. This flag moves MEMBERSHIP. Every R delta "
             "above is a different book, not the same book priced better."
             % ("{:,}".format(mc["shared_n"]), mc["shared_r_changed"]))
    L.append("")

    # ---- 7. error bar ----------------------------------------------------
    L.append("## 9. Does the delta clear its error bar")
    L.append("")
    L.append("**The wide bar (+-1.5799 R) is RETIRED** -- Austin, 2026-08-28: a stop "
             "fires only on a candle CLOSE and there is one close per bar, so the "
             "790-of-792 `intrabar_stop` class was never ambiguous (spec section 1.1). "
             "The bar this report is read against is the **narrow** one, recomputed on "
             "each arm's own book by `research/g3_onwatch_2y.error_bars` rather than "
             "quoted. The spec's published figure is +-%.4f R on the ON-WATCH-off arm "
             "and +-0.0095 R on the shipped arm; the recomputations are below."
             % NARROW_BAR_SPEC)
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    for a in MEASURED:
        L.append("| NARROW bar, `%s` arm (recomputed) | +-%.4f R |"
                 % (a, A[a]["eb_all"]["narrow"]))
    L.append("| NARROW bar carried from the spec | +-%.4f R |" % NARROW_BAR_SPEC)
    L.append("| **`%s` median R delta** | **%+.4f R** |" % (PRIMARY, d_med))
    L.append("| does the median delta clear the narrow bar? | %s |"
             % _clears(d_med, narrow))
    L.append("| `%s` mean R delta, as booked | %+.4f R |" % (PRIMARY, d_mean))
    L.append("| does the mean delta clear the narrow bar? | %s |"
             % _clears(d_mean, narrow))
    L.append("| `%s` takeable-only mean R delta | %+.4f R |" % (PRIMARY, d_clean))
    L.append("| does THAT clear the narrow bar? | %s |" % _clears(d_clean, narrow))
    for a in ARM_ON:
        if a == PRIMARY:
            continue
        L.append("| `%s` median R delta | %+.4f R (%s) |"
                 % (a, A[a]["all"]["median_r"] - o_all["median_r"],
                    _clears(A[a]["all"]["median_r"] - o_all["median_r"], narrow)))
    L.append("")
    L.append("Both bars are one-directional -- the booked mean R is a **ceiling**, "
             "never a midpoint, because each back-dated fill assumes the trigger beat "
             "the stop inside a minute nobody can see.")
    L.append("")
    L.append("### The G13 sizing trap, checked on every arm")
    L.append("")
    L.append("`backtest_week` sizes every trade at `RISK_DOLLARS / |entry - stop|`, so "
             "a row whose risk is under the engine's own floor has a 1R that is a "
             "position size nobody can take and an R that is a division by ~0. G13's "
             "arm was 73.3% such rows and its mean R of +14.72 was arithmetic rather "
             "than money. The same test, `g13_floor_fix_ab.sizeable`, imported:")
    L.append("")
    L.append("| arm | traded | takeable | **untakeable** | of which `entry == stop` | "
             "max R |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for arm in MEASURED:
        s = A[arm]["split"]
        L.append("| `%s` | %s | %s | **%s (%.1f%%)** | %d | %+.1f |"
                 % (arm, "{:,}".format(s["traded"]), "{:,}".format(s["n_sizeable"]),
                    "{:,}".format(s["n_unsizeable"]), s["pct_unsizeable"],
                    s["n_zero_risk"], s["max_r"]))
    L.append("")
    dirty = [a for a in ARM_ON if A[a]["split"]["n_zero_risk"] > 0
             or A[a]["split"]["pct_unsizeable"] >= 10.0]
    L.append("**%s** Takeable-only mean R on the verdict arm: `off` %+.4f (n=%s), "
             "`%s` %+.4f (n=%s) -- delta **%+.4f R**."
             % ("The trap does not fire on any arm." if not dirty else
                "THE TRAP FIRES ON %s -- read those arms' takeable-only row only."
                % ", ".join("`%s`" % a for a in dirty),
                tk_off["meanr"] if tk_off else 0.0,
                "{:,}".format(tk_off["traded"]) if tk_off else "0", PRIMARY,
                tk_pri["meanr"] if tk_pri else 0.0,
                "{:,}".format(tk_pri["traded"]) if tk_pri else "0", d_clean))
    L.append("")

    # ---- 8. the in-sample gate ------------------------------------------
    L.append("## 10. The in-sample recall gate -- `research/regression_gate.py`")
    L.append("")
    L.append("**The gate is RED at HEAD and that is not this ticket's doing**: six "
             "`s_grade` marks were dropped by `5e3677ea`, diagnosed in "
             "`research/g12_recall_regression.md`. What this row owes is whether the "
             "ladder adds NEW drops. Held-out beats in-sample, so this section is "
             "BELOW section 3 on purpose.")
    L.append("")
    L.append("| arm | `any_signal` | `s_grade` | dropped vs baseline | NEW drops | "
             "gate |")
    L.append("|---|---:|---:|---|---|---|")
    L.append("| baseline (`research/baseline_3.8.json`) | %d | %d | -- | -- | -- |"
             % (len(gate["off"]["base_any"]), len(gate["off"]["base_s"])))
    off_s = set(gate["off"]["base_s"]) - set(gate["off"]["s_grade"])
    off_a = set(gate["off"]["base_any"]) - set(gate["off"]["any_signal"])
    for arm in MEASURED:
        d = gate[arm]
        ds = sorted(set(d["base_s"]) - set(d["s_grade"]))
        da = sorted(set(d["base_any"]) - set(d["any_signal"]))
        new_s = sorted(set(ds) - off_s)
        new_a = sorted(set(da) - off_a)
        L.append("| `%s` | %d | **%d** | %d any_signal, %d s_grade | %s | **%s** |"
                 % (arm, len(d["any_signal"]), len(d["s_grade"]), len(da), len(ds),
                    "--" if arm == "off"
                    else ("none" if not new_s and not new_a
                          else "%d s_grade %s / %d any_signal %s"
                               % (len(new_s), new_s, len(new_a), new_a)),
                    "RED" if (ds or da) else "GREEN"))
    L.append("")

    # ---- 9. what this does not say --------------------------------------
    L.append("## 11. What this does not say")
    L.append("")
    L.append("- **It does not recommend the ladder, and after section 2 it cannot.** "
             "%d/%d against a %s baseline is a refutation, not a tuning problem. The "
             "ladder arms are in this report so the cost of the idea is on record."
             % (mk["ladder_raw"]["hits"], mk["n"], _pct(mk["majority"]["acc"])))
    L.append("- **It does not clear the `B`-floor removal either.** `nofloor` is right "
             "in principle -- arrival order should not select a book -- and on this "
             "engine it costs every held-out S day (%d/15 -> %d/15) and %.1f%% of the "
             "book, because `C` is alert-only and faces a sign-backwards gate. The "
             "principle is not what is broken; the two gates in section 7 are."
             % (o1["s_hit"], p1["s_hit"], shrink_pct))
    L.append("- **n=59 is small, and it is a FIRST READ.** One row of a 60-card lane "
             "may not have been pasted. Austin grades the remaining 60 cards in the "
             "morning; every number in section 2 should be recomputed against 119 "
             "before anything is decided on it.")
    L.append("- **It does not ship anything.** `ENABLE_SAC_LADDER` stays `False`, "
             "`ENABLE_KILL_B_FLOOR` stays `False`, `SAC_LADDER_VARSET` stays "
             "`\"shipped\"`, "
             "`downgrade.ENABLE_SEQUENCE_GATE` stays `False`, and the `B` floor is not "
             "deleted. Flipping any of them changes what trades, and re-freezing the "
             "engine voids `research/omen6_forward.py`.")
    L.append("- **It does not say the variables are right, even in set (c).** "
             "`research/a1_threshold_sweep.md` measured the grader as overfit -- mix "
             "distance from Austin 0.086 in-sample against 0.282 on the held-out 100 "
             "-- and every threshold in `research/downgrade.py` except `STALE_BARS` is "
             "a number Austin never gave. W9 fixed the SIGNS, not the thresholds. W1 "
             "was told not to change the variables themselves and did not.")
    L.append("- **It does not settle the C floor.** `downgrade.py` floors at C "
             "(2026-08-24); this ladder kills 3+ as X (2026-08-28). Section 1 names "
             "the conflict; only Austin closes it, and closing it the other way brings "
             "most of the lost book back.")
    L.append("- **It does not fix the exit.** Spec section 0: the tape offers +3.8436 "
             "R of MFE and the incumbent ladder keeps 21.9% of it. A grade change "
             "chooses which trades are taken; it cannot make a taken trade keep more.")
    L.append("- **It does not fix arrival order for the SILENT days.** Killing the `B` "
             "floor stops arrival order promoting a C. It does nothing about the days "
             "the engine never speaks on, which is where the held-out recall of "
             "%d/15 actually lives (W5)." % o1["s_hit"])
    L.append("- The held-out sample is 100 cards and 15 S days. A %d/15 -> %d/15 read "
             "has a wide interval of its own; what it can rule out is a LARGE "
             "out-of-sample recall change, not a small one."
             % (o1["s_hit"], p1["s_hit"]))
    L.append("")

    # ---- reproduce -------------------------------------------------------
    L.append("## 12. Reproduce")
    L.append("")
    L.append("```bash")
    L.append("git stash push -- signal_runner.py          # HEAD control, before the flag")
    L.append("python backtest_2y.py --days 730 --out research/w1_arm_head.json")
    L.append("git stash pop")
    L.append("python research/test_sac_ladder.py          # the assert-based check")
    L.append("python research/w1_sac_ladder_ab.py --selfcheck")
    for a in MEASURED:
        L.append("python research/w1_sac_ladder_ab.py book --arm %s" % a)
    L.append("python research/w1_sac_ladder_ab.py identical   # head == off, byte for byte")
    L.append("python research/w1_sac_ladder_ab.py test1       # the 100 held-out cards")
    L.append("python research/w1_sac_ladder_ab.py gate")
    L.append("python research/w1_sac_ladder_ab.py stats")
    L.append("python research/w1_sac_ladder_ab.py report")
    L.append("```")
    L.append("")
    L.append("The arm books are ~40 MB each and are NOT committed, the same convention "
             "`research/g3_onwatch_2y.py`, `research/g13_floor_fix_ab.py` and "
             "`research/r3_downgrade_grader_ab.py` follow. `data_archive/` must be "
             "identical across every run; the `head` run's %s signals / %s traded is "
             "the check that it was."
             % ("{:,}".format(A["head"]["all"]["signals"]) if "head" in A else "n/a",
                "{:,}".format(A["head"]["all"]["traded"]) if "head" in A else "n/a"))
    L.append("")
    L.append("## Provenance")
    L.append("")
    L.append("Generated by `research/w1_sac_ladder_ab.py report` at _this commit_ "
             "(`--selfcheck` green, `research/test_sac_ladder.py` green). Engine "
             "change: `signal_runner.py` (`ENABLE_KILL_B_FLOOR`, "
             "`ENABLE_SAC_LADDER`, "
             "`SAC_LADDER_REGRADE_ALL`, `SAC_LADDER_VARSET`, `SAC_VARSET_DROP`, "
             "`SAC_VARSET_SEQ`, `SAC_TIER`, `SignalRunner._sac_ladder_grade`, and the "
             "`not ENABLE_SAC_LADDER` guard on `_calibration_grade`'s `B` floor), all "
             "defaults unchanged. Diagnosis it implements: "
             "`research/g4_dropped_s.md`; contract: "
             "`Specs/omen6-h2-master-spec.md` section 1.2 / W1. Variable signs and the "
             "set-(c) recommendation: `research/w9_downgrade_signs.md`. Ladder "
             "arithmetic: `research/downgrade.py` at its committed constants, "
             "held-out calibration `research/a1_threshold_sweep.md`. Sequence-gate "
             "ordinal definition: `research/p20_sequence_gate.py::annotate_sequence`. "
             "Held-out scorer: `research/t70_test1_score.py`. A/B shell and the "
             "takeability test: `research/g13_floor_fix_ab.py`; held-out helpers: "
             "`research/r3_downgrade_grader_ab.py`. Austin's 59 verdicts and the "
             "baseline test: `research/w1_ladder_vs_marks.py` over "
             "`research/marks/deck_marks_h2_3lane_2026-08-28.jsonl` (tracked in git, "
             "and in `research/build_deck.py::LEGACY_MARK_FILES` so the no-repeat "
             "guarantee holds). Downstream gates: `research/w12_bug_sweep.md`, "
             "`research/w12_tight_stop.py`, `research/test_w12_grade_gates.py` (green "
             "at these defaults). Error bars: "
             "`research/g3_onwatch_2y.py`, recomputed here. Sample floor: "
             "`universe.MIN_SAMPLE_N` = %d." % MIN_SAMPLE_N)
    L.append("")
    L.append("Books: %s. %d symbol-day(s) could not be classified for the error bar "
             "(missing day) and %d row(s) had no matching bar; both are excluded from "
             "the bar, never from the money."
             % (", ".join("`%s` %s" % (a, A[a]["meta"].get("generated", "?"))
                          for a in ("head",) + MEASURED if a in A),
                st["gaps"]["day"], st["gaps"]["bar"]))
    return "\n".join(L) + "\n"


def run_report() -> int:
    with open(TEST1_JSON, encoding="utf-8") as fh:
        t1 = json.load(fh)
    with open(GATE_JSON, encoding="utf-8") as fh:
        gate = json.load(fh)
    with open(BOOK_STATS, encoding="utf-8") as fh:
        st = json.load(fh)
    # the head arm is loaded here rather than carried through book_stats, whose
    # `compose` is a two-arm question: head only ever appears in the identity table
    if os.path.exists(ARMS["head"][1]):
        hb = load_book("head")
        st["arms"]["head"] = {"all": stats(hb["trades"]),
                              "digest": trades_digest(hb), "meta": hb["meta"]}
    md = build_md(t1, gate, st, marks_analyse())
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("wrote %s (%d lines)" % (OUT_MD, md.count("\n")))
    return 0


# ---------------------------------------------------------------------------
# selfcheck -- hand-built fixtures, no engine, no archive
# ---------------------------------------------------------------------------

def _selfcheck():
    import signal_runner as sr
    from research.t70_test1_score import LADDER

    # the default and the ladder -- the same two claims test_sac_ladder.py
    # asserts, restated here so a report can never be generated from an arm
    # whose default has drifted
    assert sr.ENABLE_SAC_LADDER is False
    assert "B" not in set(sr.SAC_TIER.values()), sr.SAC_TIER
    for his, tier in sr.SAC_TIER.items():
        if his == "X":
            continue
        assert LADDER[tier] == his, (his, tier)

    # child_env: head clears the variable, off/on force it, ON_WATCH untouched
    os.environ[FLAG] = "1"
    os.environ.setdefault("ON_WATCH", "sentinel")
    try:
        assert FLAG not in child_env("head")
        assert child_env("off")[FLAG] == "0"
        assert child_env("on")[FLAG] == "1"
        for arm in ARMS:
            assert child_env(arm).get("ON_WATCH") == "sentinel"
        assert "SAC_LADDER_VARSET" not in child_env("on")
        assert child_env("on_w9c")["SAC_LADDER_VARSET"] == "w9c"
    finally:
        os.environ.pop(FLAG, None)
        if os.environ.get("ON_WATCH") == "sentinel":
            os.environ.pop("ON_WATCH", None)

    # wiped_symbols: a symbol that loses everything, one that only thins,
    # one untraded either way
    off = [{"sym": "AAA", "traded": True, "r": 1.0},
           {"sym": "AAA", "traded": True, "r": -1.0},
           {"sym": "BBB", "traded": True, "r": 2.0},
           {"sym": "BBB", "traded": True, "r": 3.0},
           {"sym": "CCC", "traded": False, "r": 9.0}]
    on = [{"sym": "BBB", "traded": True, "r": 2.0}]
    w = wiped_symbols(off, on)
    assert [x["sym"] for x in w["wiped"]] == ["AAA"], w
    assert w["wiped"][0]["n_off"] == 2 and w["wiped"][0]["total_r_off"] == 0.0, w
    assert w["n_sym_off"] == 2 and w["n_sym_on"] == 1, w
    assert w["n_trades_wiped"] == 2, w

    # a symbol traded on `off` and NOT on `on` is wiped even when `on` still
    # has untraded signals on it -- traded is the only column that counts
    w2 = wiped_symbols([{"sym": "DDD", "traded": True, "r": 1.0}],
                       [{"sym": "DDD", "traded": False, "r": 1.0}])
    assert [x["sym"] for x in w2["wiped"]] == ["DDD"], w2

    # by_grade: the monotonicity read is over TRADED rows only
    bg = by_grade([{"traded": True, "grade": "A+", "r": 2.0},
                   {"traded": True, "grade": "A+", "r": 4.0},
                   {"traded": False, "grade": "C", "r": 9.0}])
    assert bg == {"A+": {"n": 2, "median_r": 3.0, "mean_r": 3.0}}, bg

    # the arm table and the report's column order agree, and PRIMARY is an ON arm
    assert set(MEASURED) - {"off"} == set(ARM_ON)
    assert PRIMARY in ARM_ON and MEASURED[0] == "off"
    assert set(ARM_LABEL) == set(MEASURED)
    for a in ARM_ON:
        assert ARMS[a][0].get(FLAG) == "1" or a == "nofloor", a
    assert ARMS["nofloor"][0] == {"ENABLE_KILL_B_FLOOR": "1"}
    assert sr.ENABLE_KILL_B_FLOOR is False
    assert ARMS["on_w9c"][0]["SAC_LADDER_VARSET"] == "w9c"

    # the varset arm is the one signal_runner actually knows about
    assert sr.SAC_LADDER_VARSET == "shipped"
    assert "w9c" in sr.SAC_VARSET_DROP and sr.SAC_VARSET_SEQ["w9c"] is True

    # _tally_field: untraded rows never reach the grade mix
    assert _tally_field([{"traded": True, "grade": "B"},
                         {"traded": False, "grade": "C"}], "grade") == {"B": 1}

    # _clears: the narrow bar is the one that decides, and it is not a coin flip
    assert _clears(0.5, 0.0088).startswith("**yes**")
    assert _clears(0.001, 0.0088).startswith("no")

    print("selfcheck ok")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", nargs="?", default="report",
                    choices=["book", "identical", "test1", "gate", "stats", "report"])
    ap.add_argument("--arm", choices=sorted(ARMS), default="off")
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--out")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        _selfcheck()
        return 0
    return {"book": lambda: run_book(a.arm, a.days, a.out),
            "identical": identical,
            "test1": run_test1,
            "gate": run_gate,
            "stats": run_stats,
            "report": run_report}[a.cmd]()


if __name__ == "__main__":
    sys.exit(main())
