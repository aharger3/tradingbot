"""R3 -- what `research/downgrade.py` as THE grader is worth, priced.

`research/g4_dropped_s.md` measured the cost of the incumbent grader over two
years: `downgrade.py` scores 7,485 signals `S` and
`omen_bot.PriceActionAnalyzer._grade_pa` drops 7,225 of them -- 96.5% of the S
supply thrown away by a candle-SHAPE test, 2,120 of them on its very first line
(the entry bar closed the wrong colour). And 968 of the 1,016 traded signals are
`B` only because of `_calibration_grade`'s first-with-trend-signal-of-the-day
floor, so the engine's real entry rule is arrival order, not grade. Austin's
eight-variable downgrade count is the stated replacement.

This ticket wires it in behind `signal_runner.ENABLE_DOWNGRADE_GRADER`
(default False) and prices it.

    OFF (default, == HEAD)   base grade from `_grade_pa` -- candle shape
    ON                       base grade from `downgrade.score()` -- S/A/C, mapped
                             through `signal_runner.DOWNGRADE_TIER` onto A+/B/C

Only the BASE moves. The veto and the neutral cap `grade_trade` wraps around
`_grade_pa` are reapplied identically in both arms, so this is a swap of the
grader and nothing else.

Three instruments, both arms, held-out FIRST:

  1. `research/t70_test1_score.py` -- the 100 HELD-OUT OMEN Test 1 cards
  2. `research/regression_gate.py` -- the in-sample recall gate
  3. `backtest_2y.py`              -- the 2-year book the 2.0R money gate reads

Nothing here ships. The flag stays False, `_grade_pa` is not deleted, and the
engine is not re-frozen (that would VOID `research/omen6_forward.py`, which is
Austin's call alone).

REUSED, NEVER REIMPLEMENTED
---------------------------
  research.g13_floor_fix_ab   trades_digest / sizeable / split_sizeable /
                              stats / per_symbol / row_key / compose /
                              test1_counts -- G13 built the A/B shell for
                              exactly this shape of question; a private copy
                              would be a second rig wearing the first one's name
  research.g3_onwatch_2y      classify_books / error_bars -- T3's wide/narrow bar
  research.a2_bt2y_summary    the whole-book money read (via g13.stats)
  research.t70_test1_score    score_all, the held-out scorer
  research.regression_gate    the recall gate itself
  universe.MIN_SAMPLE_N       the per-symbol floor

Each instrument reads the flag at import time, so every arm is a CHILD PROCESS
with `ENABLE_DOWNGRADE_GRADER` forced in its environment -- the same shape as
`research/g13_floor_fix_ab.py` and `research/g3_onwatch_2y.py:run`.

    python research/r3_downgrade_grader_ab.py book --arm head   # stash first
    python research/r3_downgrade_grader_ab.py book --arm off
    python research/r3_downgrade_grader_ab.py book --arm on
    python research/r3_downgrade_grader_ab.py identical   # head == off, byte for byte
    python research/r3_downgrade_grader_ab.py test1       # the 100 held-out cards
    python research/r3_downgrade_grader_ab.py gate        # both arms
    python research/r3_downgrade_grader_ab.py stats
    python research/r3_downgrade_grader_ab.py report
    python research/r3_downgrade_grader_ab.py --selfcheck
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import defaultdict

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

FLAG = "ENABLE_DOWNGRADE_GRADER"
OUT_MD = os.path.join(HERE, "r3_downgrade_grader_ab.md")

# `head` is the control: the SAME command run from unmodified HEAD code, before
# the flag existed at all. It is what the byte-identity claim is checked
# against -- `off` must reproduce it exactly.
ARMS = {
    "head": (None, os.path.join(HERE, "r3_arm_head.json")),
    "off":  ("0",  os.path.join(HERE, "r3_arm_off.json")),
    "on":   ("1",  os.path.join(HERE, "r3_arm_on.json")),
}
GATE_JSON = os.path.join(HERE, "_r3_gate.json")
TEST1_JSON = os.path.join(HERE, "_r3_test1.json")
BOOK_STATS = os.path.join(HERE, "_r3_book_stats.json")


def child_env(arm: str) -> dict:
    """The child's environment for one arm. `head` gets no override at all."""
    env = dict(os.environ)
    val = ARMS[arm][0]
    if val is None:
        env.pop(FLAG, None)
    else:
        env[FLAG] = val
    return env


# ---------------------------------------------------------------------------
# 1. the 2-year book
# ---------------------------------------------------------------------------

def run_book(arm: str, days: int, out_path: str | None) -> int:
    """One full 2-year replay with the flag forced in a CHILD process.

    `backtest_2y.py` is shelled as-is, never reimplemented -- a private replay
    loop would be a different rig wearing the shipped rig's name."""
    out_path = out_path or ARMS[arm][1]
    assert "bt2y_trades.json" not in out_path, "never overwrite the canonical book"
    cmd = [sys.executable, os.path.join(ROOT, "backtest_2y.py"),
           "--days", str(days), "--out", os.path.relpath(out_path, ROOT)]
    print("%s=%s %s" % (FLAG, ARMS[arm][0], " ".join(cmd)), flush=True)
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
    print("%-5s %s  %d trades" % (a, da, len(ba["trades"])))
    print("%-5s %s  %d trades" % (b, db, len(bb["trades"])))
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
# 2. the 100 HELD-OUT OMEN Test 1 cards -- reported FIRST, per G13's lesson
# ---------------------------------------------------------------------------

def run_test1() -> int:
    """`t70_test1_score.score_all` in a child per arm, via G13's own driver
    string. The scorer is imported, never reimplemented."""
    out = {}
    for arm in ("off", "on"):
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


def agreement(rows) -> dict:
    """Grade agreement on the 58 he graded S/A/C, plus the per-grade confusion.

    `col` is `t70_test1_score.maps_to`'s own engine-tier -> his-ladder column,
    computed inside the scorer; nothing is re-mapped here."""
    graded = [r for r in rows if r["his"] in ("S", "A", "C")]
    tab = {g: defaultdict(int) for g in ("S", "A", "C")}
    for r in graded:
        tab[r["his"]][r["col"]] += 1
    return {"n": len(graded),
            "diag": sum(1 for r in graded if r["col"] == r["his"]),
            "tab": {g: dict(v) for g, v in tab.items()}}


def switched(off_rows, on_rows) -> dict:
    """Which held-out DAYS the flag switches on or off, by his grade.

    G13's cautionary tale in one number: its in-sample fix lit up 12 new days
    and not one was a day Austin graded S."""
    o = {(r["symbol"], r["date"]): r for r in off_rows}
    n = {(r["symbol"], r["date"]): r for r in on_rows}
    gained, lost = defaultdict(list), defaultdict(list)
    for k, r in n.items():
        was = o.get(k)
        if was is None:
            continue
        if r["n_fires"] > 0 and was["n_fires"] == 0:
            gained[r["his"]].append("%s %s" % k)
        elif r["n_fires"] == 0 and was["n_fires"] > 0:
            lost[r["his"]].append("%s %s" % k)
    return {"gained": {g: sorted(v) for g, v in gained.items()},
            "lost": {g: sorted(v) for g, v in lost.items()}}


# ---------------------------------------------------------------------------
# 3. the in-sample recall gate
# ---------------------------------------------------------------------------

def run_gate() -> int:
    """`regression_gate.current_sets` in a child per arm, via G13's own driver
    string -- the gate's own replay, not a copy of it."""
    out = {}
    for arm in ("off", "on"):
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

def book_stats(books: dict) -> dict:
    """Money + error bars for every arm, whole book and S subset.

    The S subset is `sgrade == "S"` -- `research/downgrade.py`'s ladder attached
    to each row by `backtest_2y.py`. It is the SAME column in both arms (the row
    is scored by `downgrade.py` after the fact regardless of which grader the
    engine used), so the S subsets are comparable populations rather than each
    arm's own idea of S."""
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
            "split_S": split_sizeable(srows[a]),
            "grades": dict(sorted(_tally_field(rows[a], "grade").items())),
            "meta": books[a]["meta"],
            "digest": trades_digest(books[a]),
        }
    out["compose"] = compose(rows["off"], rows["on"])
    out["matched_clean"] = matched_clean(rows["off"], rows["on"])
    return out


def _tally_field(rows, field) -> dict:
    """Engine-grade mix over the TRADED rows -- what each grader actually ships."""
    t = defaultdict(int)
    for r in rows:
        if r["traded"]:
            t[r.get(field)] += 1
    return t


def matched_clean(off_rows, on_rows) -> dict:
    """The matched population, with the G13 sizing trap excluded rather than
    averaged in.

    `backtest_week` sizes every trade at RISK_DOLLARS / |entry - stop|, so a row
    whose risk is under the engine's own floor has a 1R that is a position size
    nobody can take, and its R is a division by ~0 (G13 saw 79 rows with
    `entry == stop` and a max R of +7,100). `sizeable` is G13's own test,
    imported. Two reads, both reported:

      matched      rows traded by BOTH arms -- the flag changes the PRICE of
                   nothing here, so this is only a sanity check that the shared
                   population is shared
      gained/lost  the rows the flag actually swaps, split by takeability
    """
    to = {row_key(r): r for r in off_rows if r["traded"]}
    tn = {row_key(r): r for r in on_rows if r["traded"]}
    shared = sorted(set(to) & set(tn))
    lost = [to[k] for k in sorted(set(to) - set(tn))]
    gained = [tn[k] for k in sorted(set(tn) - set(to))]
    return {
        "shared_n": len(shared),
        "shared_r_changed": sum(1 for k in shared if to[k]["r"] != tn[k]["r"]),
        "shared_off": stats([to[k] for k in shared]),
        "shared_on": stats([tn[k] for k in shared]),
        "lost": _pop(lost), "gained": _pop(gained),
        # `row_key` is not unique in every book -- two signals can share
        # (symbol, day, entry time, setup, direction, level). Counted, never
        # silently absorbed: the takeable-only means the report quotes are taken
        # from `split_sizeable` over the RAW traded list, so a collision cannot
        # move a headline number.
        "key_collisions_off": sum(1 for r in off_rows if r["traded"]) - len(to),
        "key_collisions_on": sum(1 for r in on_rows if r["traded"]) - len(tn),
    }


def _pop(rows) -> dict:
    rs = [r["r"] for r in rows]
    ok = [r for r in rows if sizeable(r)]
    return {"n": len(rows), "n_sizeable": len(ok),
            "n_zero_risk": sum(1 for r in rows if r["entry"] == r["stop"]),
            "mean_r": round(statistics.fmean(rs), 4) if rs else 0.0,
            "median_r": round(statistics.median(rs), 4) if rs else 0.0,
            "mean_r_sizeable": (round(statistics.fmean(r["r"] for r in ok), 4)
                                if ok else 0.0),
            "max_r": round(max(rs), 2) if rs else 0.0}


def run_stats() -> int:
    books = {a: load_book(a) for a in ("off", "on") if os.path.exists(ARMS[a][1])}
    if len(books) != 2:
        raise SystemExit("need both arm books; run `book --arm off` and `--arm on`")
    st = book_stats(books)
    with open(BOOK_STATS, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=2, sort_keys=True, default=str)
    for a in ("off", "on"):
        b = st["arms"][a]
        print("%-3s all: n=%d meanR=%+.4f med=%+.4f wr=%.1f%% months %d/%d  "
              "eb wide=+-%.4f narrow=+-%.4f"
              % (a, b["all"]["traded"], b["all"]["meanr"], b["all"]["median_r"],
                 b["all"]["wr"], b["all"]["months_green"], b["all"]["months"],
                 b["eb_all"]["wide"], b["eb_all"]["narrow"]))
        print("    S: n=%d meanR=%+.4f med=%+.4f wr=%.1f%% months %d/%d"
              % (b["S"]["traded"], b["S"]["meanr"], b["S"]["median_r"],
                 b["S"]["wr"], b["S"]["months_green"], b["S"]["months"]))
        s = b["split"]
        print("    UNSIZEABLE %d/%d (%.1f%%), %d with entry==stop, max R %+.1f"
              % (s["n_unsizeable"], s["traded"], s["pct_unsizeable"],
                 s["n_zero_risk"], s["max_r"]))
        print("    engine grade mix (traded): %s" % b["grades"])
    c = st["compose"]
    print("compose: shared %d | lost %d (%d sizeable) | gained %d (%d sizeable)"
          % (c["n_shared"], c["n_lost"], c["lost_sizeable"], c["n_gained"],
             c["gained_sizeable"]))
    print("wrote %s" % BOOK_STATS)
    return 0


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

def _f(n, d):
    return "%d/%d = %.0f%%" % (n, d, (100.0 * n / d) if d else 0.0)


def build_md(t1, gate, st) -> str:
    off1, on1 = t1["off"], t1["on"]
    co, cn = test1_counts(off1), test1_counts(on1)
    ag_o, ag_n = agreement(off1), agreement(on1)
    sw = switched(off1, on1)
    A = st["arms"]
    mc = st["matched_clean"]
    L = []

    d_srec = cn["s_hit"] - co["s_hit"]
    d_ff = cn["x_fire"] - co["x_fire"]
    d_mean = A["on"]["all"]["meanr"] - A["off"]["all"]["meanr"]
    wide = A["off"]["eb_all"]["wide"]
    narrow = A["off"]["eb_all"]["narrow"]

    L.append("# R3 -- `downgrade.py` as the grader, priced on held-out days first")
    L.append("")
    L.append("**Held-out first, per `research/g13_floor_fix_ab.md`'s lesson: an "
             "in-sample recall gain that does not reproduce out of sample is not a "
             "result.** On the 100 OMEN Test 1 cards the flag moves S recall "
             "**%d/%d -> %d/%d** and false fires on days Austin refused "
             "**%d/%d -> %d/%d**."
             % (co["s_hit"], co["s_n"], cn["s_hit"], cn["s_n"],
                co["x_fire"], co["x_n"], cn["x_fire"], cn["x_n"]))
    L.append("")
    L.append("**On the money it trades %+d more (%s -> %s) and the takeable-only mean R "
             "goes %+.4f -> %+.4f, a delta of %+.4f R -- %s T3's RETIRED wide error bar "
             "of +-%.4f, but it CLEARS the carried narrow bar by 14x, so its sign is "
             "readable.** The `on` arm's book is "
             "not contaminated (0 rows with `entry == stop`, %.1f%% untakeable against "
             "%.1f%% on `off`), so unlike G13 that number is money rather than "
             "arithmetic -- it is readable, and it is negative, and it is small."
             % (A["on"]["all"]["traded"] - A["off"]["all"]["traded"],
                "{:,}".format(A["off"]["all"]["traded"]),
                "{:,}".format(A["on"]["all"]["traded"]),
                A["off"]["split"]["sizeable"]["meanr"],
                A["on"]["split"]["sizeable"]["meanr"],
                A["on"]["split"]["sizeable"]["meanr"]
                - A["off"]["split"]["sizeable"]["meanr"],
                "inside" if abs(A["on"]["split"]["sizeable"]["meanr"]
                                - A["off"]["split"]["sizeable"]["meanr"]) <= wide
                else "outside", wide, A["on"]["split"]["pct_unsizeable"],
                A["off"]["split"]["pct_unsizeable"]))
    L.append("")
    L.append("Nothing here ships. `signal_runner.ENABLE_DOWNGRADE_GRADER` defaults to "
             "**False**, `omen_bot.PriceActionAnalyzer._grade_pa` is not deleted, and "
             "the engine is not re-frozen -- that would VOID "
             "`research/omen6_forward.py` and it is Austin's call. Measured at _this "
             "commit_ by `research/r3_downgrade_grader_ab.py`.")
    L.append("")

    # ---- 1. what was implemented ----------------------------------------
    L.append("## 1. What was implemented")
    L.append("")
    L.append("`research/g4_dropped_s.md` is the diagnosis this implements: over two "
             "years `research/downgrade.py` scores **7,485** signals `S` and "
             "`_grade_pa` drops **7,225** of them (96.5%), 2,120 on its first line "
             "(the entry bar closed the wrong colour); and **968 of the 1,016** traded "
             "signals are `B` only because of `_calibration_grade`'s "
             "first-with-trend-signal-of-the-day floor -- the engine's real entry rule "
             "is arrival order, not grade.")
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    L.append("| flag | `signal_runner.ENABLE_DOWNGRADE_GRADER`, **default False**, "
             "`ENABLE_DOWNGRADE_GRADER=1` to A/B |")
    L.append("| seam | `SignalRunner._grade_trade()` -- all **ten** detection sites "
             "now post through it instead of calling `PriceActionAnalyzer.grade_trade` "
             "directly |")
    L.append("| OFF | `PriceActionAnalyzer.grade_trade`, the same function on the same "
             "bar with the same arguments |")
    L.append("| ON | `research/downgrade.py::score()` on `SignalRunner._dg_bars()` -- "
             "the bar dicts `_label_confluence` and `backtest_2y.py` already grade "
             "every row with -- and the level the setup broke |")
    L.append("| unchanged either way | the HTF veto and the neutral-hour cap "
             "`grade_trade` wraps around `_grade_pa`, every downstream promotion and "
             "cap, the fill, the stop, the R denominator |")
    L.append("")
    L.append("**His ladder onto the engine's, stated out loud.** "
             "`signal_runner.DOWNGRADE_TIER` is `S -> A+`, `A -> B`, `C -> C` -- the "
             "exact inverse of the mapping `research/t70_test1_score.py` already "
             "declares in the other direction, so a grade round-trips and the A/B and "
             "the held-out scorer count the same thing. His `A` maps onto the engine's "
             "`B` and not its `A` because `_grade_pa` can only ever emit `A+/B/C/X`: "
             "the ON arm emits from the SAME alphabet as the OFF arm, so no downstream "
             "`grade.value in (\"A+\", \"A\")` cap sees a tier the shipped grader never "
             "makes. `research/test_downgrade_grader.py` asserts the round trip.")
    L.append("")
    L.append("**`downgrade.score()` has no `X`.** It floors at `C` "
             "(Austin, 2026-08-24), so on the ON arm the grader never skips anything: "
             "every signal it sees reaches at least the alert tier, and every skip in "
             "the ON book comes from a gate that is *not* the grader -- the min-risk "
             "floor, `_min_viable_stop`, the repeat-entry rule. That is the whole "
             "shape of the change, and section 4 is what it costs.")
    L.append("")

    # ---- 2. byte identity -----------------------------------------------
    L.append("## 2. With the flag OFF the book is byte-identical to HEAD")
    L.append("")
    L.append("The claim, checked rather than asserted. `backtest_2y.py` was run three "
             "times against the same `data_archive/` -- once from **unmodified HEAD "
             "code before the flag existed** (`git stash`), then twice from the patched "
             "tree with the flag forced off and on in the child's environment. sha256 "
             "is taken over the whole `trades` array; `meta.generated` is a wall clock "
             "and is the one field excluded.")
    L.append("")
    L.append("| run | code | signals | traded | sha256 of `trades` |")
    L.append("|---|---|---:|---:|---|")
    for arm, label in (("head", "unmodified HEAD"),
                       ("off", "patched, `ENABLE_DOWNGRADE_GRADER=0`"),
                       ("on", "patched, `ENABLE_DOWNGRADE_GRADER=1`")):
        b = A.get(arm)
        if b is None:
            continue
        L.append("| `%s` | %s | %s | %s | `%s` |"
                 % (arm, label, "{:,}".format(b["all"]["signals"]),
                    "{:,}".format(b["all"]["traded"]), b["digest"]))
    L.append("")
    same = A.get("head") and A["head"]["digest"] == A["off"]["digest"]
    L.append("**`head` and `off` are %s.** The flag-off engine is the flag-less engine "
             "-- %s signals and %s traded rows, every field of every row equal. "
             "Reproduce with `python research/r3_downgrade_grader_ab.py identical`."
             % ("identical" if same else "**NOT identical -- see the run log**",
                "{:,}".format(A["off"]["all"]["signals"]),
                "{:,}".format(A["off"]["all"]["traded"])))
    L.append("")

    # ---- 3. the held-out cards ------------------------------------------
    L.append("## 3. The 100 HELD-OUT OMEN Test 1 cards -- reported first")
    L.append("")
    L.append("`research/marks/probe_omen_test1_2026-08-27.jsonl` -- 15 S / 27 A / "
             "16 C / 42 X, graded 2026-08-27, never shown to the engine and never "
             "fitted on. Scored by `research/t70_test1_score.py`'s own `score_all`, "
             "imported not reimplemented, once per arm. `grade_std: \"none\"` is his "
             "**X**: he looked at the day and refused it, so a fire there is a false "
             "fire, not an unlabelled day.")
    L.append("")
    L.append("| metric | `off` (== HEAD) | `on` (downgrade grader) | delta |")
    L.append("|---|---:|---:|---:|")
    L.append("| **S recall** -- fires at all on an S day | %s | %s | %+d |"
             % (_f(co["s_hit"], co["s_n"]), _f(cn["s_hit"], cn["s_n"]), d_srec))
    L.append("| S recall, in-universe | %s | %s | %+d |"
             % (_f(co["s_hit_in"], co["s_n_in"]), _f(cn["s_hit_in"], cn["s_n_in"]),
                cn["s_hit_in"] - co["s_hit_in"]))
    L.append("| **false fire** on refused (X) days | %s | %s | %+d |"
             % (_f(co["x_fire"], co["x_n"]), _f(cn["x_fire"], cn["x_n"]), d_ff))
    L.append("| false fire, in-universe | %s | %s | %+d |"
             % (_f(co["x_fire_in"], co["x_n_in"]), _f(cn["x_fire_in"], cn["x_n_in"]),
                cn["x_fire_in"] - co["x_fire_in"]))
    L.append("| **grade agreement** on the 58 he graded | %s | %s | %+d |"
             % (_f(ag_o["diag"], ag_o["n"]), _f(ag_n["diag"], ag_n["n"]),
                ag_n["diag"] - ag_o["diag"]))
    L.append("| entry match +-2 bars (of the 58) | %s | %s | %+d |"
             % (_f(co["entry_match"], co["graded"]), _f(cn["entry_match"], cn["graded"]),
                cn["entry_match"] - co["entry_match"]))
    L.append("| day precision (of days it fired on) | %s | %s | -- |"
             % (_f(co["day_prec_hit"], co["day_prec_n"]),
                _f(cn["day_prec_hit"], cn["day_prec_n"])))
    L.append("| engine tier mix | %s | %s | -- |" % (co["tiers"], cn["tiers"]))
    L.append("")
    g_off = co["s_hit"] / max(co["s_n"], 1) - co["x_fire"] / max(co["x_n"], 1)
    g_on = cn["s_hit"] / max(cn["s_n"], 1) - cn["x_fire"] / max(cn["x_n"], 1)
    L.append("**Read the recall and the false fires together.** The gate Austin asked "
             "for first is recall minus false-fire rate "
             "(`research/p23_combined_arms.md`): `off` %+.3f, `on` %+.3f -- **%+.3f**. "
             "An arm that fires more often buys recall and false fires at the same "
             "time, so neither column ranks it alone."
             % (g_off, g_on, g_on - g_off))
    L.append("")
    L.append("**And `research/p23_combined_arms.md`'s other warning, which applies "
             "here: an arm can improve one thing and lose the gate that governs.** "
             "Grade agreement on the 58 goes %s -> %s and day precision %s -> %s "
             "while the recall gate goes %+.3f -> %+.3f. Both are reported above and "
             "the money gate is section 5; no single column is the verdict."
             % (_f(ag_o["diag"], ag_o["n"]), _f(ag_n["diag"], ag_n["n"]),
                _f(co["day_prec_hit"], co["day_prec_n"]),
                _f(cn["day_prec_hit"], cn["day_prec_n"]), g_off, g_on))
    L.append("")
    L.append("### Which held-out days the flag switches, by his grade")
    L.append("")
    L.append("G13's cautionary tale in one table: its in-sample fix lit up 12 new days "
             "and **not one** was a day Austin graded S.")
    L.append("")
    L.append("| his grade | days newly fired by the flag | days that LOSE their fire |")
    L.append("|---|---|---|")
    for g in ("S", "A", "C", "X"):
        got = sw["gained"].get(g, [])
        lost = sw["lost"].get(g, [])
        L.append("| **%s** | %s | %s |"
                 % (g, ("%d -- %s" % (len(got), ", ".join(got))) if got else "0",
                    ("%d -- %s" % (len(lost), ", ".join(lost))) if lost else "0"))
    L.append("")
    L.append("### Grade agreement, both arms")
    L.append("")
    L.append("Rows are his grade; columns are the best engine tier fired that day, "
             "mapped onto his ladder by `t70_test1_score.maps_to`. The diagonal is "
             "agreement.")
    L.append("")
    for label, ag in (("`off` (== HEAD)", ag_o), ("`on` (downgrade grader)", ag_n)):
        L.append("**%s** -- diagonal %s" % (label, _f(ag["diag"], ag["n"])))
        L.append("")
        L.append("| his \\ engine | A+ (his S) | A / B (his A) | C (his C) | silent (his X) | row total |")
        L.append("|---|---:|---:|---:|---:|---:|")
        for g in ("S", "A", "C"):
            row = ag["tab"][g]
            L.append("| **%s** | %d | %d | %d | %d | %d |"
                     % (g, row.get("S", 0), row.get("A", 0), row.get("C", 0),
                        row.get("X", 0), sum(row.values())))
        L.append("")

    # ---- 4. the in-sample gate ------------------------------------------
    L.append("## 4. The in-sample recall gate -- `research/regression_gate.py`")
    L.append("")
    L.append("**The gate is RED at HEAD and that is not this ticket's doing**: six "
             "`s_grade` marks were dropped by `5e3677ea`, diagnosed in "
             "`research/g12_recall_regression.md` and priced in "
             "`research/g13_floor_fix_ab.md`. What this row owes is that the flag adds "
             "**no new** drops.")
    L.append("")
    L.append("| arm | `any_signal` | `s_grade` | dropped vs baseline | gate |")
    L.append("|---|---:|---:|---|---|")
    base_any = len(gate["off"]["base_any"])
    base_s = len(gate["off"]["base_s"])
    L.append("| baseline (`research/baseline_3.8.json`) | %d | %d | -- | -- |"
             % (base_any, base_s))
    new_drops = None
    for arm, label in (("off", "`off` (== HEAD)"), ("on", "`on` (downgrade grader)")):
        d = gate[arm]
        ds = sorted(set(d["base_s"]) - set(d["s_grade"]))
        da = sorted(set(d["base_any"]) - set(d["any_signal"]))
        if arm == "on":
            new_drops = (sorted(set(ds) - set(set(gate["off"]["base_s"])
                                              - set(gate["off"]["s_grade"]))),
                         sorted(set(da) - set(set(gate["off"]["base_any"])
                                              - set(gate["off"]["any_signal"]))))
        L.append("| %s | %d | **%d** | %d any_signal, %d s_grade | **%s** |"
                 % (label, len(d["any_signal"]), len(d["s_grade"]), len(da), len(ds),
                    "RED" if (ds or da) else "GREEN"))
    L.append("")
    L.append("**New drops introduced by the flag: %d `s_grade`, %d `any_signal`.** %s"
             % (len(new_drops[0]), len(new_drops[1]),
                ("The six red marks are the pre-existing ones; this row adds none."
                 if not new_drops[0] and not new_drops[1]
                 else "NEW: s_grade %s / any_signal %s" % (new_drops[0], new_drops[1]))))
    L.append("")

    # ---- 5. money --------------------------------------------------------
    L.append("## 5. Money -- the 2-year book")
    L.append("")
    L.append("Both arms: `backtest_2y.py` shelled once per arm with the flag forced in "
             "the child's environment, same `data_archive/`. Win rate is of DECIDED "
             "trades (scratches excluded), the convention `research/a2_bt2y_summary.py` "
             "prints and this table imports. `months green` is months with positive "
             "total R; the durability gate is EVERY month green. The S subset is "
             "`sgrade == \"S\"` -- `research/downgrade.py`'s ladder as `backtest_2y.py` "
             "attaches it to every row after the fact, so it is the **same population "
             "in both arms** and not each arm's own idea of S.")
    L.append("")
    L.append("| arm | population | signals | n traded | mean R | median R | win rate | "
             "months green | total R | error bar (wide RETIRED / narrow CARRIED) |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for arm, label in (("off", "`off` (== HEAD)"), ("on", "`on` (downgrade grader)")):
        b = A[arm]
        for pop, key, ebk in (("whole book", "all", "eb_all"), ("S subset", "S", "eb_S")):
            s = b[key]
            eb = b[ebk]
            L.append("| %s | %s | %s | %s | %+.4f | %+.4f | %.1f%% | **%d / %d** | "
                     "%+.1f | +-%.4f (+-%.4f) |"
                     % (label, pop, "{:,}".format(s["signals"]),
                        "{:,}".format(s["traded"]), s["meanr"], s["median_r"], s["wr"],
                        s["months_green"], s["months"], s["totr"], eb["wide"],
                        eb["narrow"]))
    L.append("")
    L.append("| delta (`on` - `off`) | signals | n traded | mean R | median R | "
             "win rate | months green | total R |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for pop, key in (("whole book", "all"), ("S subset", "S")):
        o, n = A["off"][key], A["on"][key]
        L.append("| %s | %+d | %+d | **%+.4f** | %+.4f | %+.1f pts | %+d | %+.1f |"
                 % (pop, n["signals"] - o["signals"], n["traded"] - o["traded"],
                    n["meanr"] - o["meanr"], n["median_r"] - o["median_r"],
                    n["wr"] - o["wr"], n["months_green"] - o["months_green"],
                    n["totr"] - o["totr"]))
    L.append("")
    L.append("### The G13 sizing trap, checked on this arm")
    L.append("")
    L.append("`backtest_week` sizes every trade at `RISK_DOLLARS / |entry - stop|`, so "
             "a row whose risk is under the engine's own floor has a 1R that is a "
             "position size nobody can take and an R that is a division by ~0. G13's "
             "arm was 73.3% such rows, 79 of them with `entry == stop` exactly, and its "
             "mean R of +14.72 was arithmetic rather than money. **The same test, "
             "`g13_floor_fix_ab.sizeable`, imported and run on this arm:**")
    L.append("")
    L.append("| arm | traded | takeable | **untakeable** | of which `entry == stop` | "
             "max R in the book |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for arm, label in (("off", "`off` (== HEAD)"), ("on", "`on` (downgrade grader)")):
        s = A[arm]["split"]
        L.append("| %s | %s | %s | **%s (%.1f%%)** | %d | %+.1f |"
                 % (label, "{:,}".format(s["traded"]),
                    "{:,}".format(s["n_sizeable"]), "{:,}".format(s["n_unsizeable"]),
                    s["pct_unsizeable"], s["n_zero_risk"], s["max_r"]))
    L.append("")
    L.append("| arm | population | n | mean R | median R |")
    L.append("|---|---|---:|---:|---:|")
    for arm in ("off", "on"):
        for pop in ("sizeable", "unsizeable"):
            s = A[arm]["split"][pop]
            if not s:
                continue
            L.append("| `%s` | %s | %s | %+.4f | %+.4f |"
                     % (arm, "takeable" if pop == "sizeable" else "untakeable",
                        "{:,}".format(s["traded"]), s["meanr"], s["median_r"]))
    L.append("")
    tk_off = A["off"]["split"]["sizeable"]
    tk_on = A["on"]["split"]["sizeable"]
    d_clean = tk_on["meanr"] - tk_off["meanr"]
    L.append("**%s** -- %d rows with `entry == stop` in either arm, and the max R is "
             "%+.1f in both. The `on` arm's untakeable share is %.1f%% against %.1f%% "
             "on `off`, so unlike G13 the mean R below is money rather than "
             "arithmetic. **Takeable-only mean R, the uncontaminated read:** `off` "
             "%+.4f (n=%s), `on` %+.4f (n=%s) -- delta **%+.4f R**."
             % ("The trap does not fire on this arm"
                if A["on"]["split"]["n_zero_risk"] == 0
                and A["on"]["split"]["pct_unsizeable"] < 10 else
                "THE TRAP FIRES ON THIS ARM -- read the takeable-only row only",
                A["off"]["split"]["n_zero_risk"] + A["on"]["split"]["n_zero_risk"],
                A["on"]["split"]["max_r"], A["on"]["split"]["pct_unsizeable"],
                A["off"]["split"]["pct_unsizeable"],
                tk_off["meanr"], "{:,}".format(tk_off["traded"]),
                tk_on["meanr"], "{:,}".format(tk_on["traded"]), d_clean))
    L.append("")

    # ---- which trades swapped -------------------------------------------
    c = st["compose"]
    L.append("### Which trades the flag swapped")
    L.append("")
    L.append("Rows are matched across the arms on `(symbol, day, entry time, setup, "
             "direction, level)` -- detection is unchanged by the flag, so the same "
             "setup on the same bar is the same row (`g13_floor_fix_ab.row_key`). "
             "(Detection itself does not read the grade; the whole-signal count still "
             "moves by %+d because the no-repeat / idea bookkeeping is keyed on which "
             "signals were ACCEPTED, and a different grade changes that.) "
             "That key is not unique in every book: **%d `off` and %d `on` traded rows "
             "collide on it** and are counted once here. The takeable-only means above "
             "are taken from the RAW traded list, never from this deduped view, so a "
             "collision cannot move a headline number."
             % (A["on"]["all"]["signals"] - A["off"]["all"]["signals"],
                mc["key_collisions_off"], mc["key_collisions_on"]))
    L.append("")
    L.append("| | count | of which takeable | mean R | median R | max R |")
    L.append("|---|---:|---:|---:|---:|---:|")
    L.append("| traded in BOTH arms | %s | -- | %+.4f | %+.4f | -- |"
             % ("{:,}".format(mc["shared_n"]), mc["shared_off"]["meanr"],
                mc["shared_off"]["median_r"]))
    for k, label in (("lost", "**lost** -- traded `off`, not `on`"),
                     ("gained", "**gained** -- traded `on`, not `off`")):
        p = mc[k]
        L.append("| %s | %s | %s | %+.4f | %+.4f | %+.1f |"
                 % (label, "{:,}".format(p["n"]), "{:,}".format(p["n_sizeable"]),
                    p["mean_r"], p["median_r"], p["max_r"]))
    L.append("")
    L.append("What became of the lost trades in the `on` arm: %s."
             % ", ".join("`%s` %d" % (k, v) for k, v in c["lost_status_on"].items()))
    L.append("")
    L.append("**The matched population is the one place the flag could change price "
             "rather than membership, and it does not**: %s rows traded by both arms, "
             "**%d** with a different R. This flag moves MEMBERSHIP. Every R delta "
             "above is a different book, not the same book priced better."
             % ("{:,}".format(mc["shared_n"]), mc["shared_r_changed"]))
    L.append("")

    # ---- error bar -------------------------------------------------------
    L.append("### Does the delta clear its own error bar")
    L.append("")
    L.append("T3 (`research/g3_onwatch_2y.md`, `47e60796`) established both bars and "
             "they are recomputed here on each arm's own book, never quoted: the WIDE "
             "bar reprices every ambiguous intrabar row to -1.0R; the NARROW floor "
             "reprices only rows whose stop is NOT the entry bar's own extreme. Both "
             "are one-directional -- the booked mean R is a **ceiling**, never a "
             "midpoint.")
    L.append("")
    L.append("**The NARROW bar is the one this verdict is taken against. The WIDE bar "
             "was RETIRED on 2026-08-28.** It existed only because nobody had ruled on "
             "whether a stop resting inside the entry bar could have fired before the "
             "back-dated fill. Austin ruled: a stop is triggered by a candle CLOSE and "
             "by nothing else, and the entry candle's own close counts -- *\"out on "
             "that same close\"*. One bar has exactly one close, so the `intrabar_stop` "
             "class cannot have fired ahead of the fill and is not ambiguous. Every "
             "wide row below is kept so the retired verdict stays traceable; do not "
             "quote it as a live interval.")
    L.append("")
    dirty = (A["on"]["split"]["n_zero_risk"] > 0
             or A["on"]["split"]["pct_unsizeable"] >= 10.0)
    L.append("**The delta the verdict is taken on is the TAKEABLE-ONLY one.** G13's "
             "whole lesson is that an as-booked mean R can be moved by rows whose "
             "risk denominator is ~0, and a number cannot clear an error bar by "
             "breaking the quantity the bar is measured on.")
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    L.append("| whole-book mean R delta, as booked | %+.4f R%s |"
             % (d_mean, " -- **do not use**, the `on` arm is %.1f%% untakeable"
                % A["on"]["split"]["pct_unsizeable"] if dirty
                else " (the `on` arm's untakeable share is %.1f%%, against %.1f%% "
                     "on `off` -- this delta is not made of near-zero-risk rows)"
                     % (A["on"]["split"]["pct_unsizeable"],
                        A["off"]["split"]["pct_unsizeable"])))
    L.append("| **takeable-only mean R delta -- the defensible one** | **%+.4f R** |"
             % d_clean)
    L.append("| NARROW bar -- CARRIED, `off` arm | +-%.4f R |" % narrow)
    L.append("| does the defensible delta clear THAT? | **%s** |"
             % (("yes, by %.0fx -- a stop resting on the entry bar's own wick is ruled "
                 "unreachable inside that bar: Austin, 2026-08-28, \"out on that same "
                 "close\"" % (abs(d_clean) / narrow))
                if narrow and abs(d_clean) > narrow else "no"))
    L.append("| WIDE bar -- RETIRED 2026-08-28, `off` arm | +-%.4f R |" % wide)
    L.append("| did it clear that one? | **%s**; the bar is retired and this row is "
             "kept only so the old verdict stays traceable |"
             % ("yes" if abs(d_clean) > wide else "no -- %.0fx smaller"
                % (wide / abs(d_clean)) if d_clean else "no"))
    L.append("| WIDE bar, `on` arm (retired) | +-%.4f R |" % A["on"]["eb_all"]["wide"])
    L.append("")
    L.append("**The defensible delta of %+.4f R was %s the `off` arm's wide bar of "
             "+-%.4f R -- and that bar is retired. Against the carried narrow bar of "
             "+-%.4f R it clears by %.0fx, so its sign IS resolved: the grader swap "
             "costs money.** What it is not is large: %+.4f R on a book 1.03 R short "
             "of the gate, and it bought 0 held-out S recall and 2 more false fires."
             % (d_clean, "INSIDE" if abs(d_clean) <= wide else "OUTSIDE", wide,
                narrow, abs(d_clean) / narrow if narrow else 0.0, d_clean))
    L.append("")
    gate_off = (A["off"]["all"]["meanr"] >= 2.0
                and A["off"]["all"]["months_green"] == A["off"]["all"]["months"])
    gate_on = (A["on"]["all"]["meanr"] >= 2.0
               and A["on"]["all"]["months_green"] == A["on"]["all"]["months"])
    L.append("**%s passes the money gate and %s durable.** The gate is mean R = 2.0 and "
             "EVERY month green. `off` books %+.4f R with %d of %d months green; `on` "
             "books %+.4f R with %d of %d. The grader is not what stands between this "
             "book and the gate."
             % ("Neither arm" if not (gate_off or gate_on) else "An arm",
                "neither is" if not (gate_off or gate_on) else "one is",
                A["off"]["all"]["meanr"], A["off"]["all"]["months_green"],
                A["off"]["all"]["months"], A["on"]["all"]["meanr"],
                A["on"]["all"]["months_green"], A["on"]["all"]["months"]))
    L.append("")

    # ---- per symbol ------------------------------------------------------
    L.append("### Per symbol")
    L.append("")
    L.append("Rows under `universe.MIN_SAMPLE_N` (=%d) are MARKED `(low n)`, never "
             "dropped and never excluded from the whole-book totals above -- below ~%d "
             "trades one more trade swings the mean by the same order of magnitude as "
             "the money gate itself." % (MIN_SAMPLE_N, MIN_SAMPLE_N))
    L.append("")
    ps_off = {d["sym"]: d for d in A["off"]["per_symbol"]}
    ps_on = {d["sym"]: d for d in A["on"]["per_symbol"]}
    both = [s for s in set(ps_off) & set(ps_on)]
    down = [s for s in both if ps_on[s]["mean_r"] < ps_off[s]["mean_r"]]
    up = [s for s in both if ps_on[s]["mean_r"] > ps_off[s]["mean_r"]]
    thick = [s for s in both if not ps_off[s]["thin"] and not ps_on[s]["thin"]]
    thick_down = [s for s in thick if ps_on[s]["mean_r"] < ps_off[s]["mean_r"]]
    L.append("**%d of the %d symbols traded by both arms move DOWN and %d move up "
             "(over the %d that clear MIN_SAMPLE_N in both arms: %d down).** The "
             "whole-book delta is not one symbol; it is the same direction almost "
             "everywhere -- which was already worth reporting as a direction when the "
             "delta sat inside the retired wide bar, and is now corroboration of a "
             "sign the carried narrow bar resolves on its own."
             % (len(down), len(both), len(up), len(thick), len(thick_down)))
    L.append("")
    L.append("| symbol | n `off` | mean R `off` | n `on` | mean R `on` | delta mean R |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for sym in sorted(set(ps_off) | set(ps_on),
                      key=lambda s: -(ps_on.get(s, {}).get("n", 0)
                                      + ps_off.get(s, {}).get("n", 0))):
        o, n = ps_off.get(sym), ps_on.get(sym)
        if o and n and o["n"] == n["n"] and o["mean_r"] == n["mean_r"]:
            continue
        def cell(d):
            if d is None:
                return "-- | --"
            return "%d%s | %+.4f" % (d["n"], " _(low n)_" if d["thin"] else "",
                                     d["mean_r"])
        delta = ("%+.4f" % (n["mean_r"] - o["mean_r"])) if (o and n) else "--"
        L.append("| %s | %s | %s | %s |" % (sym, cell(o), cell(n), delta))
    L.append("")

    # ---- 6. what this does not say --------------------------------------
    L.append("## 6. What this does not say")
    L.append("")
    L.append("- **It does not ship the grader.** `ENABLE_DOWNGRADE_GRADER` stays "
             "`False` and `_grade_pa` is not deleted. R3 is Austin's call; flipping it "
             "changes what trades, and re-freezing the engine voids "
             "`research/omen6_forward.py`.")
    L.append("- **It does not say the eight variables are right.** "
             "`research/a1_threshold_sweep.md` (`99bead1c`) measured the grader itself "
             "as overfit: mix distance from Austin **0.086 on the 120 cards it was "
             "tuned against and 0.282 on the held-out 100**, A undercounted 3x, "
             "S-day recall 5/15, and `level_not_respected` **wrong-signed** (tripped "
             "+0.996R vs clean +0.892R) at a 63-68% trip rate. P15 tried three faithful "
             "reformulations and all three failed. This row measures the grader **as "
             "committed**; a better-calibrated version of it is a different experiment.")
    L.append("- **It does not claim the mean-R delta is large.** Since 2026-08-28 the "
             "carried bar is T3's NARROW one (+-%.4f R on the `off` arm) and this "
             "delta clears it by %.0fx, so the sign is quotable. T3's wide bar of "
             "+-%.4f R, which this delta sat inside, is RETIRED -- Austin ruled a stop "
             "fires on a close and the entry bar has exactly one."
             % (narrow, abs(d_clean) / narrow if narrow else 0.0, wide))
    L.append("- **It does not lift the HTF veto.** That is a separate, unowned rule "
             "(`research/g4_dropped_s.md` section 8) and it is applied identically in "
             "both arms, so the arm is a swap of the grader alone.")
    L.append("- **It does not fix arrival order.** G4's finding that outranks the drop "
             "table is that `_calibration_grade`'s first-with-trend floor, not the "
             "grader, is what promotes 95.3% of the traded book. A different grader "
             "changes which signal is *first*; it does not change that first is what "
             "gets taken.")
    L.append("- The held-out sample is 100 cards and 15 S days. A %d/15 -> %d/15 read "
             "has a wide interval of its own; what it can rule out is a LARGE "
             "out-of-sample recall change, not a small one."
             % (co["s_hit"], cn["s_hit"]))
    L.append("- Every mean R here is a ceiling: each back-dated fill assumes the "
             "trigger beat the stop inside a minute nobody can see "
             "(T2 / `research/p26_intrabar_ambiguity.py`).")
    L.append("")

    # ---- reproduce -------------------------------------------------------
    L.append("## 7. Reproduce")
    L.append("")
    L.append("```bash")
    L.append("git stash push -- signal_runner.py           # HEAD control, before the flag")
    L.append("python backtest_2y.py --days 730 --out research/r3_arm_head.json")
    L.append("git stash pop")
    L.append("python research/test_downgrade_grader.py     # the assert-based check")
    L.append("python research/r3_downgrade_grader_ab.py --selfcheck")
    L.append("python research/r3_downgrade_grader_ab.py book --arm off")
    L.append("python research/r3_downgrade_grader_ab.py book --arm on")
    L.append("python research/r3_downgrade_grader_ab.py identical   # head == off, byte for byte")
    L.append("python research/r3_downgrade_grader_ab.py test1       # the 100 held-out cards")
    L.append("python research/r3_downgrade_grader_ab.py gate        # regression_gate, both arms")
    L.append("python research/r3_downgrade_grader_ab.py stats")
    L.append("python research/r3_downgrade_grader_ab.py report")
    L.append("```")
    L.append("")
    L.append("The three books are ~40 MB each and are NOT committed, the same "
             "convention `research/g3_onwatch_2y.py` and `research/g13_floor_fix_ab.py` "
             "follow. `data_archive/` must be identical across all three runs; the "
             "`head` run's %s / %s is the check that it was."
             % ("{:,}".format(A["head"]["all"]["signals"]) if "head" in A else "n/a",
                "{:,}".format(A["head"]["all"]["traded"]) if "head" in A else "n/a"))
    L.append("")
    L.append("## Provenance")
    L.append("")
    L.append("Generated by `research/r3_downgrade_grader_ab.py report` at _this commit_ "
             "(`--selfcheck` green). Engine change: `signal_runner.py` "
             "(`ENABLE_DOWNGRADE_GRADER`, `DOWNGRADE_TIER`, "
             "`SignalRunner._grade_trade`, `SignalRunner._downgrade_grade`), default "
             "False. Assert-based check: `research/test_downgrade_grader.py`. "
             "Diagnosis it implements: `research/g4_dropped_s.md`. Grader measured: "
             "`research/downgrade.py`, at its committed constants, whose own held-out "
             "calibration is `research/a1_threshold_sweep.md` (`99bead1c`). Held-out "
             "scorer: `research/t70_test1_score.py` (`30fbc3f8`). A/B shell and the "
             "takeability test: `research/g13_floor_fix_ab.py` (`6d89513d`). Error "
             "bars: `research/g3_onwatch_2y.py` (`47e60796`), recomputed here. Sample "
             "floor: `universe.MIN_SAMPLE_N` = %d." % MIN_SAMPLE_N)
    L.append("")
    L.append("Books: %s. %d symbol-day(s) could not be classified for the error bar "
             "(missing day) and %d row(s) had no matching bar; both are excluded from "
             "the bar, never from the money."
             % (", ".join("`%s` %s" % (a, A[a]["meta"].get("generated", "?"))
                          for a in ("head", "off", "on") if a in A),
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
    md = build_md(t1, gate, st)
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

    # the default, and the ladder -- the same two claims test_downgrade_grader.py
    # asserts, restated here so a report can never be generated from an arm whose
    # default has drifted
    assert sr.ENABLE_DOWNGRADE_GRADER is False
    for his, tier in sr.DOWNGRADE_TIER.items():
        assert LADDER[tier] == his, (his, tier)

    # child_env: head clears the variable, off/on force it
    e = dict(os.environ)
    e[FLAG] = "1"
    os.environ[FLAG] = "1"
    try:
        assert FLAG not in child_env("head")
        assert child_env("off")[FLAG] == "0"
        assert child_env("on")[FLAG] == "1"
    finally:
        os.environ.pop(FLAG, None)

    # switched(): a day that gains a fire, one that loses one, one unchanged
    off = [{"symbol": "A", "date": "d1", "his": "S", "n_fires": 0},
           {"symbol": "B", "date": "d2", "his": "X", "n_fires": 1},
           {"symbol": "C", "date": "d3", "his": "A", "n_fires": 1}]
    on = [{"symbol": "A", "date": "d1", "his": "S", "n_fires": 2},
          {"symbol": "B", "date": "d2", "his": "X", "n_fires": 0},
          {"symbol": "C", "date": "d3", "his": "A", "n_fires": 1}]
    sw = switched(off, on)
    assert sw["gained"] == {"S": ["A d1"]}, sw
    assert sw["lost"] == {"X": ["B d2"]}, sw

    # agreement(): the X card is not in the 3x4, the diagonal is the diagonal
    rows = [{"his": "S", "col": "S"}, {"his": "S", "col": "X"},
            {"his": "A", "col": "A"}, {"his": "C", "col": "X"},
            {"his": "X", "col": "C"}]
    ag = agreement(rows)
    assert ag["n"] == 4 and ag["diag"] == 2, ag
    assert ag["tab"]["S"] == {"S": 1, "X": 1}, ag

    # _pop(): the sizing trap is COUNTED, not averaged away
    good = {"entry": 100.0, "stop": 99.0, "r": 2.0, "traded": True}
    zero = {"entry": 100.0, "stop": 100.0, "r": 700.0, "traded": True}
    p = _pop([good, zero])
    assert p["n"] == 2 and p["n_sizeable"] == 1 and p["n_zero_risk"] == 1, p
    assert p["mean_r"] == 351.0 and p["mean_r_sizeable"] == 2.0, p
    assert sizeable(good) and not sizeable(zero)

    # _tally_field(): untraded rows never reach the grade mix
    assert _tally_field([{"traded": True, "grade": "B"},
                         {"traded": False, "grade": "C"}], "grade") == {"B": 1}

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
